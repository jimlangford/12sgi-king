# gpu-router v3 — multi-engine state orchestrator, single host.
#
# ENGINES:
#   ollama    → Ollama (or llama.cpp) LLM inference; GPU-bound; serialised.
#   voice     → espeak-ng text-to-speech; CPU-bound; serialised on a CPU worker.
#   embedding → Ollama /api/embeddings; lighter GPU call; serialised on CPU worker.
#   comfyui   → ComfyUI image/video render; GPU-bound; future (shares GPU worker).
#
# CLIENTS:  govOS core, Maui tenant, Studio / Element LOTUS, Civic Signal,
#           Workboard, reports — each submits jobs by client_id + job_type.
#
# How it works:
#   POST /api/v2/gpu/infer  → enqueue job by job_type, block until done (or timeout).
#   GET  /api/v2/gpu/queue  → list pending / running jobs (owner only).
#   GET  /api/v2/gpu/usage  → per-client usage stats.
#   GET  /api/v2/gpu/events → recent event bus entries (engine start/done/error).
#   GET  /api/v2/gpu/ready|live|health  → standard govOS health surface.
#
# Workers:
#   GPU worker  — serialises ollama + comfyui calls (one GPU job at a time).
#   CPU worker  — serialises voice + embedding calls (runs concurrently with GPU).
#
# Priority:
#   Jobs from higher-priority clients are pulled first within each worker lane.
#   Priority is configured via CLIENT_PRIORITIES env (see below).
#   Ties broken by arrival order (FIFO within a tier).
#
# Queue persistence:
#   SQLite at GPU_ROUTER_DB_PATH.  A restart drains pending jobs in priority
#   order; any job still in state "running" at startup is reset to "pending" so
#   it can be retried.

import base64
import json
import os
import shutil
import sqlite3
import subprocess
import tempfile
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any
from urllib import error, request
from uuid import uuid4

from fastapi import FastAPI, Header, HTTPException, Response
from pydantic import BaseModel

API_PREFIX = "/api/v2"
VERSION = os.environ.get("VERSION", "3.0.0")
DB_PATH = os.environ.get("GPU_ROUTER_DB_PATH", "/tmp/govos_v2_gpu_router.db")

# Ollama (or llama.cpp) base URL — internal Docker network name.
GPU_RUNTIME_URL = os.environ.get("GPU_RUNTIME_URL", "http://gpu-runtime:11434")

# Auth introspection so callers must hold a valid owner token.
AUTH_INTROSPECTION_URL = os.environ.get("AUTH_INTROSPECTION_URL", "http://localhost:8101/api/v2/auth/introspect")
AUTH_READY_URL = os.environ.get("AUTH_READY_URL", "http://localhost:8101/api/v2/ready")
INTERNAL_SERVICE_TOKEN = os.environ.get("INTERNAL_SERVICE_TOKEN", "dev-internal-token")
REQUEST_TIMEOUT = float(os.environ.get("DEPENDENCY_TIMEOUT_SECONDS", "3"))

# How long to wait for Ollama to finish a job (seconds).
INFER_TIMEOUT = float(os.environ.get("GPU_INFER_TIMEOUT", "120"))

# Job type → engine lane mapping.
#   GPU worker:  ollama, comfyui
#   CPU worker:  voice, embedding
GPU_LANES = {"ollama", "comfyui"}
CPU_LANES = {"voice", "embedding"}
ALL_JOB_TYPES = GPU_LANES | CPU_LANES

# espeak-ng voice synthesis defaults (overridable via options in the request).
VOICE_DEFAULT_LANG = os.environ.get("VOICE_DEFAULT_LANG", "haw")
VOICE_DEFAULT_RATE = int(os.environ.get("VOICE_DEFAULT_RATE", "130"))
VOICE_DEFAULT_PITCH = int(os.environ.get("VOICE_DEFAULT_PITCH", "50"))

# Per-client priority weights (lower number = higher priority).
# Override via env: GPU_CLIENT_PRIORITIES=govos-core:1,maui-tenant:2,studio:3,...
_DEFAULT_PRIORITIES = {
    "govos-core":     1,
    "maui-tenant":    2,
    "studio":         3,
    "civic-signal":   4,
    "workboard":      5,
    "reports":        6,
}

def _load_priorities() -> dict[str, int]:
    raw = os.environ.get("GPU_CLIENT_PRIORITIES", "")
    if not raw.strip():
        return dict(_DEFAULT_PRIORITIES)
    out: dict[str, int] = {}
    for part in raw.split(","):
        part = part.strip()
        if ":" in part:
            k, v = part.split(":", 1)
            try:
                out[k.strip()] = int(v.strip())
            except ValueError:
                pass
    return out or dict(_DEFAULT_PRIORITIES)

CLIENT_PRIORITIES = _load_priorities()
DEFAULT_PRIORITY = max(CLIENT_PRIORITIES.values()) + 1  # unknown clients go last

app = FastAPI(title="govOS GPU Router v3", version=VERSION)

# ──────────────────────────────────────────────
# DB
# ──────────────────────────────────────────────

@contextmanager
def _db():
    # sqlite3.Connection.__exit__ only commits/rolls back -- it does not close the connection.
    # Same leak found+fixed across services/{ai,auth,tenant,documents,storage}/app/main.py
    # 2026-07-09; worst offender here since _worker_loop polls _db() in a `while True:` loop.
    # Transactional behavior at call sites is unchanged.
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    # busy_timeout (audit-quad-os 2026-07-10): gpu-router-v3 runs TWO concurrent SQLite writers
    # (GPU + CPU workers) plus the infer poller. Wait up to 30s for a lock instead of raising
    # 'database is locked' immediately, so transient write contention self-resolves rather than
    # surfacing as an error the worker loop has to swallow.
    conn.execute("PRAGMA busy_timeout=30000")
    try:
        yield conn
    finally:
        conn.close()

def init_db() -> None:
    with _db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS gpu_jobs (
                id          TEXT PRIMARY KEY,
                client_id   TEXT NOT NULL,
                priority    INTEGER NOT NULL,
                job_type    TEXT NOT NULL DEFAULT 'ollama',
                model       TEXT NOT NULL,
                prompt      TEXT NOT NULL,
                options_json TEXT,
                status      TEXT NOT NULL DEFAULT 'pending',
                result_json TEXT,
                error       TEXT,
                created_at  TEXT NOT NULL,
                started_at  TEXT,
                finished_at TEXT,
                created_by  TEXT NOT NULL
            )
            """
        )
        # Add job_type column to existing databases that pre-date v3.
        try:
            conn.execute("ALTER TABLE gpu_jobs ADD COLUMN job_type TEXT NOT NULL DEFAULT 'ollama'")
        except sqlite3.OperationalError:
            pass  # column already exists

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS gpu_events (
                id          TEXT PRIMARY KEY,
                event_type  TEXT NOT NULL,
                engine      TEXT NOT NULL,
                job_id      TEXT,
                detail_json TEXT,
                ts          TEXT NOT NULL
            )
            """
        )
        # Reset any job that was mid-flight when the process died.
        conn.execute(
            "UPDATE gpu_jobs SET status = 'pending', started_at = NULL WHERE status = 'running'"
        )
        conn.commit()

def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()

def _log_event(event_type: str, engine: str, job_id: str | None = None, detail: dict | None = None) -> None:
    """Append an event to the gpu_events bus.  Never raises — event loss is acceptable."""
    try:
        with _db() as conn:
            conn.execute(
                "INSERT INTO gpu_events (id, event_type, engine, job_id, detail_json, ts) VALUES (?,?,?,?,?,?)",
                (str(uuid4()), event_type, engine, job_id, json.dumps(detail or {}), _now_utc()),
            )
            conn.commit()
    except Exception:
        pass

# ──────────────────────────────────────────────
# Queue workers — one GPU worker, one CPU worker
# ──────────────────────────────────────────────

_gpu_worker_lock = threading.Lock()   # serialise GPU (Ollama) calls
_cpu_worker_lock = threading.Lock()   # serialise CPU (voice/embedding) calls
_gpu_wakeup = threading.Event()       # signal GPU worker when a job is enqueued
_cpu_wakeup = threading.Event()       # signal CPU worker when a job is enqueued


def _next_pending_job(conn: sqlite3.Connection, lanes: set[str]) -> sqlite3.Row | None:
    placeholders = ",".join("?" for _ in lanes)
    return conn.execute(
        f"""
        SELECT * FROM gpu_jobs
        WHERE status = 'pending' AND job_type IN ({placeholders})
        ORDER BY priority ASC, created_at ASC
        LIMIT 1
        """,
        list(lanes),
    ).fetchone()


def _call_ollama(model: str, prompt: str, options: dict | None) -> dict[str, Any]:
    payload = {"model": model, "prompt": prompt, "stream": False}
    if options:
        payload["options"] = options
    data = json.dumps(payload).encode()
    req = request.Request(
        f"{GPU_RUNTIME_URL}/api/generate",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with request.urlopen(req, timeout=INFER_TIMEOUT) as resp:
        return json.loads(resp.read().decode() or "{}")


def _call_embedding(model: str, prompt: str, options: dict | None) -> dict[str, Any]:
    """Generate a text embedding vector via Ollama /api/embeddings."""
    payload = {"model": model or "nomic-embed-text", "prompt": prompt}
    data = json.dumps(payload).encode()
    req = request.Request(
        f"{GPU_RUNTIME_URL}/api/embeddings",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with request.urlopen(req, timeout=INFER_TIMEOUT) as resp:
        return json.loads(resp.read().decode() or "{}")


_VOICE_LANGS_CACHE: set[str] | None = None


def _voice_langs() -> set[str]:
    """The set of espeak-ng voice names actually installed, queried once and cached. Used to
    validate the requested `lang` so it can't smuggle an espeak flag. Falls back to a small
    known-safe set (the ones this stack ships: Hawaiian + English) if the query fails."""
    global _VOICE_LANGS_CACHE
    if _VOICE_LANGS_CACHE is None:
        langs: set[str] = set()
        try:
            out = subprocess.run(["espeak-ng", "--voices"], capture_output=True,
                                  stdin=subprocess.DEVNULL, timeout=10)
            for line in out.stdout.decode(errors="replace").splitlines()[1:]:
                parts = line.split()
                if len(parts) >= 2:
                    langs.add(parts[1])          # column 2 = voice name
        except Exception:
            pass
        _VOICE_LANGS_CACHE = langs or {"haw", "en-us", "en-gb", "en"}
    return _VOICE_LANGS_CACHE


def _call_voice(model: str, prompt: str, options: dict | None) -> dict[str, Any]:
    """Synthesise speech from *prompt* using espeak-ng.

    model   = voice/language tag, e.g. "haw" (Hawaiian), "en-us", "en-gb".
    options = {"rate": int, "pitch": int} — espeak-ng -s / -p flags.

    Returns {"audio_b64": <base64 WAV>, "duration_s": float, "engine": "espeak-ng"}.
    Falls back to a dict with "error" key if espeak-ng is not installed.
    """
    if not shutil.which("espeak-ng"):
        return {"error": "espeak-ng not found on PATH; install it in the container image"}

    opts = options or {}
    lang = model or VOICE_DEFAULT_LANG
    rate = int(opts.get("rate", VOICE_DEFAULT_RATE))
    pitch = int(opts.get("pitch", VOICE_DEFAULT_PITCH))
    text = (prompt or "").strip()
    if not text:
        return {"error": "empty text — nothing to synthesise"}

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp_path = tmp.name
    try:
        # "--" ends espeak-ng option parsing so a prompt/lang beginning with '-' is spoken as TEXT,
        # not interpreted as an espeak flag (e.g. --phonout=<path> or -f <file>/--stdin, which an
        # authenticated caller could otherwise use to write to an arbitrary path or hang the shared
        # CPU worker to the 60s timeout = voice+embedding lane DoS). argv form + no shell already
        # blocks shell RCE; this closes the residual espeak-own-flag argument-injection surface.
        # lang is validated against the installed-voice allowlist so it can't smuggle a flag either.
        if lang not in _voice_langs():
            return {"error": f"unknown voice '{lang}'; install it or pick an available voice"}
        result = subprocess.run(
            ["espeak-ng", "-v", lang, "-s", str(rate), "-p", str(pitch), "-w", tmp_path, "--", text],
            capture_output=True,
            stdin=subprocess.DEVNULL,
            timeout=60,
        )
        if result.returncode != 0:
            err = result.stderr.decode(errors="replace").strip()
            return {"error": f"espeak-ng exited {result.returncode}: {err}"}
        with open(tmp_path, "rb") as f:
            wav_bytes = f.read()
        if not wav_bytes:
            return {"error": "espeak-ng produced an empty WAV file"}
        # WAV frame rate is 22050 Hz, 16-bit mono — approximate duration from file size.
        header_bytes = 44
        frame_bytes = max(1, len(wav_bytes) - header_bytes)
        duration_s = round(frame_bytes / (22050 * 2), 2)
        return {
            "audio_b64": base64.b64encode(wav_bytes).decode(),
            "duration_s": duration_s,
            "engine": "espeak-ng",
            "voice": lang,
            "rate": rate,
            "pitch": pitch,
        }
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


def _run_job(job: sqlite3.Row) -> tuple[str, dict | None, str | None]:
    """Dispatch one job to the correct engine.  Returns (status, result, error)."""
    job_type = job["job_type"] or "ollama"
    model = job["model"]
    prompt = job["prompt"]
    options = json.loads(job["options_json"]) if job["options_json"] else None
    try:
        if job_type == "ollama":
            result = _call_ollama(model, prompt, options)
        elif job_type == "embedding":
            result = _call_embedding(model, prompt, options)
        elif job_type == "voice":
            result = _call_voice(model, prompt, options)
            if "error" in result:
                return "error", None, result["error"]
        else:
            return "error", None, f"unknown job_type '{job_type}'"
        return "done", result, None
    except Exception as exc:
        return "error", None, str(exc)


def _worker_loop(worker_name: str, lanes: set[str], lock: threading.Lock, wakeup: threading.Event) -> None:
    """Generic worker loop for a set of engine lanes.

    Hardened (audit-quad-os 2026-07-10): the whole inner body is wrapped in try/except so a
    transient sqlite3.OperationalError('database is locked') — now more likely because this branch
    runs TWO concurrent SQLite writers (the GPU and CPU workers) plus the infer poller — can no
    longer propagate out and permanently kill the worker thread (there is no supervisor to restart
    it), which would silently stall a whole engine lane. On error we log and continue; _db()'s
    connections also carry PRAGMA busy_timeout to absorb the contention in the first place.
    """
    while True:
        wakeup.wait(timeout=5)
        wakeup.clear()
        try:
            with lock:
                while True:
                    with _db() as conn:
                        job = _next_pending_job(conn, lanes)
                        if not job:
                            break
                        conn.execute(
                            "UPDATE gpu_jobs SET status='running', started_at=? WHERE id=?",
                            (_now_utc(), job["id"]),
                        )
                        conn.commit()

                    job_id = job["id"]
                    engine = job["job_type"] or "ollama"
                    _log_event("job.start", engine, job_id, {"client_id": job["client_id"]})

                    status, result, err = _run_job(job)

                    with _db() as conn:
                        conn.execute(
                            "UPDATE gpu_jobs SET status=?, result_json=?, error=?, finished_at=? WHERE id=?",
                            (status, json.dumps(result) if result else None, err, _now_utc(), job_id),
                        )
                        conn.commit()

                    _log_event(
                        f"job.{status}", engine, job_id,
                        {"client_id": job["client_id"], "error": err} if err else {"client_id": job["client_id"]},
                    )
        except Exception as exc:
            # Never let a worker die: log via the event bus (best-effort) and loop again.
            try:
                _log_event("worker.error", worker_name, None, {"error": str(exc)[:300]})
            except Exception:
                pass


# ──────────────────────────────────────────────
# Auth
# ──────────────────────────────────────────────

def _error(status_code: int, code: str, message: str, details: dict | None = None):
    raise HTTPException(
        status_code=status_code,
        detail={"error": {"code": code, "message": message, "details": details or {}}},
    )

def _require_auth(authorization: str | None) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        _error(401, "unauthorized", "Missing or invalid bearer token")
    token = authorization.split(" ", 1)[1].strip()
    payload = json.dumps({"token": token}).encode()
    req = request.Request(
        AUTH_INTROSPECTION_URL,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "X-Service-Token": INTERNAL_SERVICE_TOKEN,
        },
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            data = json.loads(resp.read().decode() or "{}")
    except error.HTTPError as exc:
        if exc.code == 403:
            _error(503, "dependency_denied", "Auth service rejected service trust")
        _error(503, "dependency_unavailable", "Auth service unavailable", {"status": exc.code})
    except Exception:
        _error(503, "dependency_unavailable", "Auth service unavailable")
    if not data.get("active"):
        _error(401, "unauthorized", "Session is not active")
    return data.get("user") or {}


def _check_dependency_ready(url: str) -> bool:
    try:
        with request.urlopen(url, timeout=REQUEST_TIMEOUT) as resp:
            if resp.status != 200:
                return False
            data = json.loads(resp.read().decode() or "{}")
            return data.get("status") in {"ready", "healthy"}
    except Exception:
        return False


def _ollama_ready() -> bool:
    try:
        with request.urlopen(f"{GPU_RUNTIME_URL}/api/tags", timeout=REQUEST_TIMEOUT) as resp:
            return resp.status == 200
    except Exception:
        return False


# ──────────────────────────────────────────────
# Request / response models
# ──────────────────────────────────────────────

class InferRequest(BaseModel):
    client_id: str           # e.g. "govos-core", "studio", "workboard"
    model: str               # Ollama model name e.g. "llama3"; or voice tag e.g. "haw"
    prompt: str              # LLM prompt or text to synthesise (voice lane)
    options: dict | None = None  # Ollama options (temperature, …) or voice options (rate, pitch)
    job_type: str = "ollama"     # "ollama" | "voice" | "embedding" | "comfyui"


# ──────────────────────────────────────────────
# Routes
# ──────────────────────────────────────────────

@app.get(f"{API_PREFIX}/live")
def live():
    return {"status": "alive", "service": "gpu-router", "version": VERSION, "timestamp": _now_utc()}


@app.get(f"{API_PREFIX}/ready")
def ready(response: Response):
    db_ok = True
    try:
        with _db() as conn:
            conn.execute("SELECT 1").fetchone()
    except sqlite3.Error:
        db_ok = False

    auth_ok = _check_dependency_ready(AUTH_READY_URL)
    runtime_ok = _ollama_ready()
    voice_ok = bool(shutil.which("espeak-ng"))
    # voice lane is best-effort — router is ready as long as DB + auth + GPU runtime are up.
    is_ready = db_ok and auth_ok and runtime_ok

    response.status_code = 200 if is_ready else 503
    return {
        "status": "ready" if is_ready else "not-ready",
        "service": "gpu-router",
        "version": VERSION,
        "dependencies": {
            "database": db_ok,
            "auth": auth_ok,
            "gpu_runtime": runtime_ok,
            "voice_engine": voice_ok,
        },
    }


@app.get(f"{API_PREFIX}/health")
def health():
    with _db() as conn:
        total = conn.execute("SELECT COUNT(*) FROM gpu_jobs").fetchone()[0]
        pending = conn.execute("SELECT COUNT(*) FROM gpu_jobs WHERE status='pending'").fetchone()[0]
        running = conn.execute("SELECT COUNT(*) FROM gpu_jobs WHERE status='running'").fetchone()[0]
        # Per-lane pending/running counts.
        lane_rows = conn.execute(
            """
            SELECT job_type,
                   SUM(CASE WHEN status='pending' THEN 1 ELSE 0 END) AS pending,
                   SUM(CASE WHEN status='running' THEN 1 ELSE 0 END) AS running
            FROM gpu_jobs
            WHERE status IN ('pending','running')
            GROUP BY job_type
            """
        ).fetchall()
    lanes = {r["job_type"]: {"pending": r["pending"], "running": r["running"]} for r in lane_rows}
    return {
        "status": "healthy",
        "service": "gpu-router",
        "version": VERSION,
        "jobs": {"total": total, "pending": pending, "running": running},
        "lanes": lanes,
        "engines": {
            "gpu": list(GPU_LANES),
            "cpu": list(CPU_LANES),
        },
        "voice_engine": "espeak-ng" if shutil.which("espeak-ng") else "unavailable",
        "priorities": CLIENT_PRIORITIES,
    }


@app.post(f"{API_PREFIX}/gpu/infer")
def infer(payload: InferRequest, authorization: str | None = Header(default=None)):
    """Enqueue a job and block until it completes (or times out).

    job_type controls which engine lane handles the job:
      "ollama"    — LLM inference via Ollama (GPU).
      "voice"     — Text-to-speech via espeak-ng (CPU).  model = voice lang, e.g. "haw".
      "embedding" — Text embeddings via Ollama (CPU-light).
    """
    user = _require_auth(authorization)

    job_type = payload.job_type if payload.job_type in ALL_JOB_TYPES else "ollama"
    priority = CLIENT_PRIORITIES.get(payload.client_id, DEFAULT_PRIORITY)
    job_id = str(uuid4())
    now = _now_utc()

    with _db() as conn:
        conn.execute(
            """
            INSERT INTO gpu_jobs
                (id, client_id, priority, job_type, model, prompt, options_json, status, created_at, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?)
            """,
            (
                job_id,
                payload.client_id,
                priority,
                job_type,
                payload.model,
                payload.prompt,
                json.dumps(payload.options) if payload.options else None,
                now,
                user.get("id", "unknown"),
            ),
        )
        conn.commit()

    _log_event("job.queued", job_type, job_id, {"client_id": payload.client_id})

    # Wake the right worker.
    if job_type in CPU_LANES:
        _cpu_wakeup.set()
    else:
        _gpu_wakeup.set()

    # Poll until done or timeout.
    deadline = time.monotonic() + INFER_TIMEOUT
    while time.monotonic() < deadline:
        with _db() as conn:
            row = conn.execute("SELECT * FROM gpu_jobs WHERE id=?", (job_id,)).fetchone()
        if row and row["status"] == "done":
            result = json.loads(row["result_json"] or "{}")
            resp: dict[str, Any] = {
                "job_id": job_id,
                "job_type": job_type,
                "client_id": payload.client_id,
                "model": payload.model,
                "done": True,
                "started_at": row["started_at"],
                "finished_at": row["finished_at"],
            }
            if job_type == "voice":
                resp["audio_b64"] = result.get("audio_b64", "")
                resp["duration_s"] = result.get("duration_s")
                resp["engine"] = result.get("engine", "espeak-ng")
            elif job_type == "embedding":
                resp["embedding"] = result.get("embedding", [])
            else:
                resp["response"] = result.get("response", "")
            return resp
        if row and row["status"] == "error":
            engine_label = "CPU" if job_type in CPU_LANES else "GPU"
            _error(502, f"{job_type}_error", f"{engine_label} error: {row['error']}", {"job_id": job_id})
        time.sleep(0.5)

    # Timed out — mark the job so it is not orphaned.
    with _db() as conn:
        conn.execute(
            "UPDATE gpu_jobs SET status='timeout', finished_at=? WHERE id=? AND status IN ('pending','running')",
            (_now_utc(), job_id),
        )
        conn.commit()
    _log_event("job.timeout", job_type, job_id, {"client_id": payload.client_id})
    _error(504, "infer_timeout", "Job did not complete within the allowed time", {"job_id": job_id})


@app.get(f"{API_PREFIX}/gpu/queue")
def queue_status(authorization: str | None = Header(default=None)):
    """List pending and running jobs (owner/internal use)."""
    _require_auth(authorization)
    with _db() as conn:
        rows = conn.execute(
            """
            SELECT id, client_id, priority, job_type, model, status, created_at, started_at
            FROM gpu_jobs
            WHERE status IN ('pending', 'running')
            ORDER BY priority ASC, created_at ASC
            """
        ).fetchall()
    return {"queue": [dict(r) for r in rows]}


@app.get(f"{API_PREFIX}/gpu/usage")
def usage(authorization: str | None = Header(default=None)):
    """Per-client job counts."""
    _require_auth(authorization)
    with _db() as conn:
        rows = conn.execute(
            """
            SELECT client_id,
                   COUNT(*) AS total,
                   SUM(CASE WHEN status='done'    THEN 1 ELSE 0 END) AS done,
                   SUM(CASE WHEN status='error'   THEN 1 ELSE 0 END) AS errors,
                   SUM(CASE WHEN status='timeout' THEN 1 ELSE 0 END) AS timeouts,
                   SUM(CASE WHEN status='pending' THEN 1 ELSE 0 END) AS pending
            FROM gpu_jobs
            GROUP BY client_id
            ORDER BY client_id
            """
        ).fetchall()
    return {"usage": [dict(r) for r in rows]}


@app.get(f"{API_PREFIX}/gpu/events")
def events(authorization: str | None = Header(default=None), limit: int = 50):
    """Recent events from the engine event bus (job start / done / error)."""
    _require_auth(authorization)
    limit = min(max(1, limit), 500)
    with _db() as conn:
        rows = conn.execute(
            "SELECT id, event_type, engine, job_id, detail_json, ts FROM gpu_events ORDER BY ts DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return {
        "events": [
            {**dict(r), "detail": json.loads(r["detail_json"] or "{}")}
            for r in rows
        ]
    }


# ──────────────────────────────────────────────
# Startup
# ──────────────────────────────────────────────

init_db()

# GPU worker: handles ollama + comfyui lanes.
_gpu_thread = threading.Thread(
    target=_worker_loop,
    args=("gpu-worker", GPU_LANES, _gpu_worker_lock, _gpu_wakeup),
    daemon=True,
)
_gpu_thread.start()

# CPU worker: handles voice + embedding lanes concurrently with GPU work.
_cpu_thread = threading.Thread(
    target=_worker_loop,
    args=("cpu-worker", CPU_LANES, _cpu_worker_lock, _cpu_wakeup),
    daemon=True,
)
_cpu_thread.start()
