# gpu-router — single GPU, many clients.
#
# ONE GPU OWNER: Ollama (or llama.cpp / ComfyUI) runs at GPU_RUNTIME_URL.
# MANY CLIENTS:  govOS core, Maui tenant, Studio / Element LOTUS, Civic Signal,
#                Workboard, reports — each submits inference jobs by client_id.
#
# How it works:
#   POST /api/v2/gpu/infer  → enqueue job, block until Ollama returns (or timeout).
#   GET  /api/v2/gpu/queue  → list pending / running jobs (owner only).
#   GET  /api/v2/gpu/usage  → per-client usage stats.
#   GET  /api/v2/gpu/ready|live|health  → standard govOS health surface.
#
# Priority:
#   The router serialises Ollama calls — only one job runs at a time so the
#   single GPU is never overloaded.  Jobs from higher-priority clients are
#   pulled first.  Priority is configured via CLIENT_PRIORITIES env (see below).
#   Ties are broken by arrival order (FIFO within a tier).
#
# Queue persistence:
#   SQLite at GPU_ROUTER_DB_PATH.  A restart drains pending jobs in priority
#   order; any job still in state "running" at startup is reset to "pending" so
#   it can be retried (the Ollama call did not complete).

import json
import os
import sqlite3
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
VERSION = os.environ.get("VERSION", "2.0.0")
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

app = FastAPI(title="govOS GPU Router", version=VERSION)

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
        # Reset any job that was mid-flight when the process died.
        conn.execute(
            "UPDATE gpu_jobs SET status = 'pending', started_at = NULL WHERE status = 'running'"
        )
        conn.commit()

def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()

# ──────────────────────────────────────────────
# Queue worker — single background thread
# ──────────────────────────────────────────────

_worker_lock = threading.Lock()   # serialise Ollama calls
_wakeup = threading.Event()       # signal worker when a job is enqueued


def _next_pending_job(conn: sqlite3.Connection) -> sqlite3.Row | None:
    return conn.execute(
        """
        SELECT * FROM gpu_jobs
        WHERE status = 'pending'
        ORDER BY priority ASC, created_at ASC
        LIMIT 1
        """
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


def _worker_loop() -> None:
    while True:
        _wakeup.wait(timeout=5)
        _wakeup.clear()
        with _worker_lock:
            while True:
                with _db() as conn:
                    job = _next_pending_job(conn)
                    if not job:
                        break
                    conn.execute(
                        "UPDATE gpu_jobs SET status='running', started_at=? WHERE id=?",
                        (_now_utc(), job["id"]),
                    )
                    conn.commit()

                job_id = job["id"]
                model = job["model"]
                prompt = job["prompt"]
                options = json.loads(job["options_json"]) if job["options_json"] else None

                try:
                    result = _call_ollama(model, prompt, options)
                    with _db() as conn:
                        conn.execute(
                            "UPDATE gpu_jobs SET status='done', result_json=?, finished_at=? WHERE id=?",
                            (json.dumps(result), _now_utc(), job_id),
                        )
                        conn.commit()
                except Exception as exc:
                    with _db() as conn:
                        conn.execute(
                            "UPDATE gpu_jobs SET status='error', error=?, finished_at=? WHERE id=?",
                            (str(exc), _now_utc(), job_id),
                        )
                        conn.commit()


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
    model: str               # Ollama model name e.g. "llama3"
    prompt: str
    options: dict | None = None  # Ollama options (temperature, num_predict, …)


# ──────────────────────────────────────────────
# Routes
# ──────────────────────────────────────────────

@app.get(f"{API_PREFIX}/live")
def live():
    return {"status": "alive", "service": "gpu-router", "timestamp": _now_utc()}


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
    is_ready = db_ok and auth_ok and runtime_ok

    response.status_code = 200 if is_ready else 503
    return {
        "status": "ready" if is_ready else "not-ready",
        "service": "gpu-router",
        "dependencies": {
            "database": db_ok,
            "auth": auth_ok,
            "gpu_runtime": runtime_ok,
        },
    }


@app.get(f"{API_PREFIX}/health")
def health():
    with _db() as conn:
        total = conn.execute("SELECT COUNT(*) FROM gpu_jobs").fetchone()[0]
        pending = conn.execute("SELECT COUNT(*) FROM gpu_jobs WHERE status='pending'").fetchone()[0]
        running = conn.execute("SELECT COUNT(*) FROM gpu_jobs WHERE status='running'").fetchone()[0]
    return {
        "status": "healthy",
        "service": "gpu-router",
        "version": VERSION,
        "jobs": {"total": total, "pending": pending, "running": running},
        "priorities": CLIENT_PRIORITIES,
    }


@app.post(f"{API_PREFIX}/gpu/infer")
def infer(payload: InferRequest, authorization: str | None = Header(default=None)):
    """Enqueue an inference job and block until it completes (or times out)."""
    user = _require_auth(authorization)

    priority = CLIENT_PRIORITIES.get(payload.client_id, DEFAULT_PRIORITY)
    job_id = str(uuid4())
    now = _now_utc()

    with _db() as conn:
        conn.execute(
            """
            INSERT INTO gpu_jobs
                (id, client_id, priority, model, prompt, options_json, status, created_at, created_by)
            VALUES (?, ?, ?, ?, ?, ?, 'pending', ?, ?)
            """,
            (
                job_id,
                payload.client_id,
                priority,
                payload.model,
                payload.prompt,
                json.dumps(payload.options) if payload.options else None,
                now,
                user.get("id", "unknown"),
            ),
        )
        conn.commit()

    _wakeup.set()  # wake the worker

    # Poll until done or timeout.
    deadline = time.monotonic() + INFER_TIMEOUT
    while time.monotonic() < deadline:
        with _db() as conn:
            row = conn.execute("SELECT * FROM gpu_jobs WHERE id=?", (job_id,)).fetchone()
        if row and row["status"] == "done":
            result = json.loads(row["result_json"] or "{}")
            return {
                "job_id": job_id,
                "client_id": payload.client_id,
                "model": payload.model,
                "response": result.get("response", ""),
                "done": True,
                "started_at": row["started_at"],
                "finished_at": row["finished_at"],
            }
        if row and row["status"] == "error":
            _error(502, "gpu_error", f"Ollama error: {row['error']}", {"job_id": job_id})
        time.sleep(0.5)

    # Timed out — mark the job so it is not orphaned.
    with _db() as conn:
        conn.execute(
            "UPDATE gpu_jobs SET status='timeout', finished_at=? WHERE id=? AND status IN ('pending','running')",
            (_now_utc(), job_id),
        )
        conn.commit()
    _error(504, "gpu_timeout", "GPU inference did not complete within the allowed time", {"job_id": job_id})


@app.get(f"{API_PREFIX}/gpu/queue")
def queue_status(authorization: str | None = Header(default=None)):
    """List pending and running jobs (owner/internal use)."""
    _require_auth(authorization)
    with _db() as conn:
        rows = conn.execute(
            """
            SELECT id, client_id, priority, model, status, created_at, started_at
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


# ──────────────────────────────────────────────
# Startup
# ──────────────────────────────────────────────

init_db()
_thread = threading.Thread(target=_worker_loop, daemon=True)
_thread.start()
