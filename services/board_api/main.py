"""services/board_api/main.py — Board API server.

Serves /board/api/* endpoints consumed by the go/ owner console subpages:
  /board/api/docker    → docker container status
  /board/api/ollama    → Ollama model list + running inference
  /board/api/system    → CPU, RAM, disk, GPU metrics
  /board/api/github    → GitHub Actions runs, PRs, commits
  /board/api/llm-watch → LLM request log + active requests
  /board/api/logs      → Aggregated service logs
  /board/api/comfyui   → ComfyUI render queue + GPU

Also serves static files at / (the king repo root) so go.html, gordon.html,
and the go/* subpages are accessible via Tailscale.

Port: 8799  (Tailscale-accessible, loopback-only bind)
Canon: PRIVATE — never expose beyond Tailscale trust boundary.

Usage:
  python -m uvicorn services.board_api.main:app --host 127.0.0.1 --port 8799
  (king-watchdog.py manages this automatically)
"""

import json
import os
import platform
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

# ── Repo root ─────────────────────────────────────────────────────────────────
_HERE = Path(__file__).resolve()
_REPO = _HERE.parents[2]

# ── Config ────────────────────────────────────────────────────────────────────
OLLAMA_BASE    = os.environ.get("OLLAMA_BASE",    "http://localhost:11434")
COMFYUI_BASE   = os.environ.get("COMFYUI_BASE",   "http://localhost:8188")
KING_BRIDGE    = os.environ.get("KING_BRIDGE",    "http://localhost:8109")
GITHUB_TOKEN   = os.environ.get("GITHUB_TOKEN",   "")
GITHUB_REPO    = os.environ.get("GITHUB_REPO",    "jimlangford/12sgi-king")
LOG_DIR        = Path(os.environ.get("DEPLOY_LOG_DIR",
                  str(_REPO / "logs" / "v2-deploy")))
DISPATCH_LOG   = Path(os.environ.get("WORKBOARD_DISPATCH_LOG",
                  str(_REPO / ".dispatch_log.jsonl")))
TIMEOUT        = 4

app = FastAPI(title="King Board API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _get(url: str, headers: dict | None = None) -> dict | None:
    req = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return json.loads(r.read().decode("utf-8", "replace"))
    except Exception:
        return None


def _docker_cmd(*args) -> str:
    try:
        return subprocess.check_output(
            ["docker"] + list(args),
            stderr=subprocess.DEVNULL, text=True, timeout=6
        ).strip()
    except Exception:
        return ""


# ── /board/api/docker ─────────────────────────────────────────────────────────

@app.get("/board/api/docker")
def board_docker():
    # docker ps -a --format json
    raw = _docker_cmd("ps", "-a", "--format",
                       "{{json .}}")
    containers = []
    daemon_ok = bool(raw is not None)

    if raw:
        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                c = json.loads(line)
            except Exception:
                continue
            name   = c.get("Names", c.get("Name", ""))
            status = c.get("Status", c.get("State", ""))
            image  = c.get("Image", "")
            ports  = [p.strip() for p in (c.get("Ports") or "").split(",") if p.strip()]

            # restart count
            restarts = 0
            ri = _docker_cmd("inspect", "--format",
                             "{{.RestartCount}}", name)
            try:
                restarts = int(ri)
            except Exception:
                pass

            # health state
            health = _docker_cmd("inspect", "--format",
                                 "{{.State.Health.Status}}", name)
            if health in ("", "<no value>"):
                health = None

            containers.append({
                "name":          name,
                "status":        status,
                "image":         image,
                "ports":         ports,
                "restart_count": restarts,
                "health":        health,
            })

    return {
        "daemon_ok":    daemon_ok,
        "containers":   containers,
        "compose_file": "docker-compose.v2.yml",
        "compose_status": "active" if containers else "stopped",
        "ts": _now(),
    }


# ── /board/api/ollama ─────────────────────────────────────────────────────────

@app.get("/board/api/ollama")
def board_ollama():
    tags = _get(f"{OLLAMA_BASE}/api/tags")
    ps   = _get(f"{OLLAMA_BASE}/api/ps")

    models  = (tags or {}).get("models", [])
    running = (ps   or {}).get("models", [])

    # GPU VRAM from nvidia-smi
    gpu_total = 0
    gpu_used  = 0
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=memory.used,memory.total",
             "--format=csv,noheader,nounits"],
            text=True, timeout=3
        ).strip()
        parts = out.split(",")
        if len(parts) >= 2:
            gpu_used  = int(parts[0].strip()) * 1024 * 1024
            gpu_total = int(parts[1].strip()) * 1024 * 1024
    except Exception:
        pass

    return {
        "models":         models,
        "running":        running,
        "gpu_total_vram": gpu_total,
        "gpu_used_vram":  gpu_used,
        "online":         tags is not None,
        "ts": _now(),
    }


# ── /board/api/system ─────────────────────────────────────────────────────────

@app.get("/board/api/system")
def board_system():
    # CPU
    cpu_pct = 0.0
    try:
        import psutil
        cpu_pct = psutil.cpu_percent(interval=0.2)
    except ImportError:
        # fallback: no psutil — use wmic on Windows
        try:
            out = subprocess.check_output(
                ["wmic", "cpu", "get", "LoadPercentage", "/value"],
                text=True, timeout=4
            )
            for line in out.splitlines():
                if "LoadPercentage" in line:
                    cpu_pct = float(line.split("=")[1].strip())
        except Exception:
            pass

    # RAM
    mem_pct = mem_used = mem_total = 0
    try:
        import psutil as _p
        vm = _p.virtual_memory()
        mem_pct   = int(vm.percent)
        mem_used  = vm.used
        mem_total = vm.total
    except ImportError:
        pass

    # Disk
    disks = []
    try:
        import psutil as _p
        for part in _p.disk_partitions(all=False):
            try:
                usage = _p.disk_usage(part.mountpoint)
                disks.append({
                    "mount": part.mountpoint,
                    "used":  usage.used,
                    "free":  usage.free,
                    "total": usage.total,
                    "pct":   int(usage.percent),
                })
            except Exception:
                pass
    except ImportError:
        # fallback disk usage via shutil
        try:
            t, u, f = shutil.disk_usage("/")
            disks = [{"mount": "/", "used": u, "free": f, "total": t,
                      "pct": int(u / t * 100) if t else 0}]
        except Exception:
            pass

    # GPU
    gpu_temp = gpu_util = vram_used = vram_total = vram_pct = None
    gpu_name = None
    try:
        out = subprocess.check_output(
            ["nvidia-smi",
             "--query-gpu=temperature.gpu,utilization.gpu,memory.used,memory.total,name",
             "--format=csv,noheader,nounits"],
            text=True, timeout=3
        ).strip()
        parts = [p.strip() for p in out.split(",")]
        if len(parts) >= 4:
            gpu_temp   = int(parts[0])
            gpu_util   = int(parts[1].replace("%", "").strip())
            vram_used  = int(parts[2]) * 1024 * 1024
            vram_total = int(parts[3]) * 1024 * 1024
            vram_pct   = int(vram_used / vram_total * 100) if vram_total else 0
            gpu_name   = parts[4] if len(parts) > 4 else None
    except Exception:
        pass

    # Uptime
    uptime = ""
    try:
        import psutil as _p
        boot = _p.boot_time()
        up_s = int(time.time() - boot)
        d, r = divmod(up_s, 86400)
        h, r = divmod(r, 3600)
        m    = r // 60
        uptime = f"{d}d {h}h {m}m" if d else f"{h}h {m}m"
    except ImportError:
        pass

    return {
        "cpu_pct":       round(cpu_pct, 1),
        "mem_pct":       mem_pct,
        "mem_used":      mem_used,
        "mem_total":     mem_total,
        "disks":         disks,
        "gpu_temp":      gpu_temp,
        "gpu_util":      gpu_util,
        "gpu_vram_used":  vram_used,
        "gpu_vram_total": vram_total,
        "gpu_vram_pct":  vram_pct,
        "gpu_name":      gpu_name,
        "uptime":        uptime,
        "hostname":      platform.node(),
        "os":            platform.system() + " " + platform.release(),
        "ts": _now(),
    }


# ── /board/api/github ─────────────────────────────────────────────────────────

@app.get("/board/api/github")
def board_github():
    if not GITHUB_TOKEN:
        # Return graceful empty — the page shows the "configure GITHUB_TOKEN" error card
        return JSONResponse(status_code=503, content={
            "error": "GITHUB_TOKEN not configured",
            "workflow_runs": [], "pull_requests": [], "commits": [],
        })

    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    base = f"https://api.github.com/repos/{GITHUB_REPO}"

    runs_data    = _get(f"{base}/actions/runs?per_page=10", headers) or {}
    prs_data     = _get(f"{base}/pulls?state=open&per_page=10", headers) or {}
    commits_data = _get(f"{base}/commits?per_page=6", headers) or []

    runs = []
    for r in runs_data.get("workflow_runs", []):
        runs.append({
            "name":       r.get("name"),
            "workflow":   r.get("workflow_id"),
            "status":     r.get("status"),
            "conclusion": r.get("conclusion"),
            "head_branch": r.get("head_branch"),
            "head_sha":   r.get("head_sha", "")[:7],
            "event":      r.get("event"),
            "updated_at": r.get("updated_at"),
            "html_url":   r.get("html_url"),
        })

    prs = []
    for p in (prs_data if isinstance(prs_data, list) else []):
        prs.append({
            "number":      p.get("number"),
            "title":       p.get("title"),
            "head_branch": p.get("head", {}).get("ref"),
            "base_branch": p.get("base", {}).get("ref"),
            "author":      p.get("user", {}).get("login"),
            "updated_at":  p.get("updated_at"),
            "html_url":    p.get("html_url"),
        })

    commits = []
    for c in (commits_data if isinstance(commits_data, list) else []):
        commits.append({
            "sha":     c.get("sha", ""),
            "message": (c.get("commit") or {}).get("message", ""),
            "author":  (c.get("commit", {}).get("author") or {}).get("name"),
            "date":    (c.get("commit", {}).get("author") or {}).get("date"),
            "html_url": c.get("html_url"),
        })

    return {"workflow_runs": runs, "pull_requests": prs, "commits": commits, "ts": _now()}


# ── /board/api/llm-watch ─────────────────────────────────────────────────────

@app.get("/board/api/llm-watch")
def board_llm_watch():
    # Active inference from Ollama /api/ps
    ps   = _get(f"{OLLAMA_BASE}/api/ps") or {}
    active = ps.get("models", [])

    # Recent requests from king-bridge jobs
    bridge = _get(f"{KING_BRIDGE}/api/v2/bridge/jobs?limit=20") or {}
    recent = []
    for job in bridge.get("jobs", []):
        recent.append({
            "model":        job.get("model"),
            "duration_ms":  None,
            "grounded":     job.get("grounded"),
            "error":        None if job.get("grounded") else "ungrounded",
            "ts":           job.get("created_at"),
            "prompt_tokens": None,
            "completion_tokens": None,
        })

    # Pulse counters from king-bridge
    pulse_data = _get(f"{KING_BRIDGE}/api/v2/bridge/pulse") or {}
    pulse = pulse_data.get("pulse", {})

    return {
        "active":        active,
        "recent":        recent,
        "queue_depth":   pulse.get("waiting_gpu", 0),
        "total_requests": len(recent),
        "avg_duration_ms": None,
        "error_rate":    0,
        "ts": _now(),
    }


# ── /board/api/logs ──────────────────────────────────────────────────────────

@app.get("/board/api/logs")
def board_logs():
    entries = []

    # Read dispatch log (workboard hub feed)
    if DISPATCH_LOG.exists():
        try:
            lines = DISPATCH_LOG.read_text(encoding="utf-8").splitlines()[-200:]
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                try:
                    e = json.loads(line)
                    event = e.get("event") or e.get("message") or ""
                    entries.append({
                        "ts":      e.get("iso") or e.get("ts") or "",
                        "source":  e.get("source", "workboard"),
                        "level":   "ERROR" if "BLOCKER" in event.upper()
                                   else "WARN" if "WARN" in event.upper()
                                   else "INFO",
                        "msg":     event,
                    })
                except Exception:
                    continue
        except Exception:
            pass

    # Read deploy logs
    if LOG_DIR.exists():
        for lf in sorted(LOG_DIR.glob("deploy-*.json"))[-5:]:
            try:
                d = json.loads(lf.read_text(encoding="utf-8"))
                entries.append({
                    "ts":     d.get("timestamp", ""),
                    "source": "deploy",
                    "level":  "INFO",
                    "msg":    f"deploy sha={d.get('sha','')[:7]} outcome={d.get('outcome','?')}",
                })
            except Exception:
                pass

    # Docker container logs (last 20 lines of each running container)
    raw = _docker_cmd("ps", "--format", "{{.Names}}")
    if raw:
        for name in raw.splitlines()[:6]:  # cap at 6 containers
            name = name.strip()
            if not name:
                continue
            logs = _docker_cmd("logs", "--tail", "10", "--timestamps", name)
            for line in logs.splitlines()[-10:]:
                level = "ERROR" if " error" in line.lower() or " err " in line.lower() else \
                        "WARN"  if " warn"  in line.lower() else "INFO"
                entries.append({
                    "ts":     "",
                    "source": name.split("-")[-1],  # short name
                    "level":  level,
                    "msg":    line.strip()[:200],
                })

    # Sort by ts descending (rough)
    entries.sort(key=lambda x: x.get("ts") or "", reverse=True)
    entries = entries[:300]

    return {"entries": entries, "count": len(entries), "ts": _now()}


# ── /board/api/comfyui ────────────────────────────────────────────────────────

@app.get("/board/api/comfyui")
def board_comfyui():
    queue   = _get(f"{COMFYUI_BASE}/queue")    or {}
    history = _get(f"{COMFYUI_BASE}/history")  or {}

    running = queue.get("queue_running", [])
    pending = queue.get("queue_pending", [])

    # Simplify running jobs
    running_out = []
    for job in running[:3]:
        if isinstance(job, list) and len(job) >= 3:
            # ComfyUI running item: [index, prompt_id, prompt_data, ...]
            running_out.append({
                "prompt_id": str(job[1])[:16] if len(job) > 1 else "?",
                "progress":  0,
                "node":      None,
                "value":     None,
                "max":       None,
            })
        elif isinstance(job, dict):
            running_out.append(job)

    pending_out = []
    for job in pending[:10]:
        if isinstance(job, list) and len(job) >= 2:
            pending_out.append({"prompt_id": str(job[1])[:16]})
        elif isinstance(job, dict):
            pending_out.append(job)

    # GPU stats via nvidia-smi
    vram_used = vram_total = gpu_temp = None
    try:
        out = subprocess.check_output(
            ["nvidia-smi",
             "--query-gpu=memory.used,memory.total,temperature.gpu",
             "--format=csv,noheader,nounits"],
            text=True, timeout=3
        ).strip()
        parts = [p.strip() for p in out.split(",")]
        if len(parts) >= 3:
            vram_used  = int(parts[0]) * 1024 * 1024
            vram_total = int(parts[1]) * 1024 * 1024
            gpu_temp   = int(parts[2])
    except Exception:
        pass

    return {
        "queue_running": running_out,
        "queue_pending": pending_out,
        "vram_used":     vram_used,
        "vram_total":    vram_total,
        "gpu_temp":      gpu_temp,
        "online":        queue != {},
        "ts": _now(),
    }


# ── Static file serving ───────────────────────────────────────────────────────
# Serve the repo root so /go/docker.html etc. are accessible at their natural paths.
# Mounted AFTER the /board/api routes so API takes priority.

@app.get("/")
async def root():
    return FileResponse(str(_REPO / "go.html"))


@app.get("/go")
async def go_index():
    return FileResponse(str(_REPO / "king_public_src" / "go" / "index.html"))


@app.get("/gordon")
async def gordon():
    return FileResponse(str(_REPO / "gordon.html"))


@app.get("/health")
async def health():
    return {"status": "alive", "service": "board-api", "ts": _now()}


# Mount static files last (catch-all)
try:
    app.mount("/", StaticFiles(directory=str(_REPO), html=True), name="static")
except Exception:
    pass
