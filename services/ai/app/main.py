import json
import os
import sqlite3
from datetime import datetime, timezone
from urllib import error, parse, request
from uuid import uuid4

from fastapi import FastAPI, Header, HTTPException, Response
from pydantic import BaseModel

from services.v2_workboard import emit_workboard_job

API_PREFIX = "/api/v2"
VERSION = os.environ.get("VERSION", "2.0.0")
DB_PATH = os.environ.get("AI_DB_PATH", "/tmp/govos_v2_ai.db")
AUTH_INTROSPECTION_URL = os.environ.get("AUTH_INTROSPECTION_URL", "http://localhost:8101/api/v2/auth/introspect")
AUTH_READY_URL = os.environ.get("AUTH_READY_URL", "http://localhost:8101/api/v2/ready")
TENANT_SERVICE_URL = os.environ.get("TENANT_SERVICE_URL", "http://localhost:8102")
TENANT_READY_URL = os.environ.get("TENANT_READY_URL", f"{TENANT_SERVICE_URL}/api/v2/ready")
INTERNAL_SERVICE_TOKEN = os.environ.get("INTERNAL_SERVICE_TOKEN", "dev-internal-token")
REQUEST_TIMEOUT = float(os.environ.get("DEPENDENCY_TIMEOUT_SECONDS", "3"))

# GPU router — inference requests are forwarded here; falls back to stub when unavailable.
GPU_ROUTER_URL = os.environ.get("GPU_ROUTER_URL", "http://gpu-router:8107")
GPU_ROUTER_READY_URL = os.environ.get("GPU_ROUTER_READY_URL", f"{GPU_ROUTER_URL}/api/v2/ready")
GPU_DEFAULT_MODEL = os.environ.get("GPU_DEFAULT_MODEL", "llama3")

app = FastAPI(title="govOS v2 AI Service", version=VERSION)


class AiAssistRequest(BaseModel):
    case_id: str
    prompt: str
    context: dict | None = None


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS assist_events (
                id TEXT PRIMARY KEY,
                case_id TEXT NOT NULL,
                prompt TEXT NOT NULL,
                context_json TEXT,
                summary TEXT NOT NULL,
                created_at TEXT NOT NULL,
                created_by TEXT NOT NULL
            )
            """
        )
        conn.commit()


def _error(status_code: int, code: str, message: str, details: dict | None = None):
    raise HTTPException(status_code=status_code, detail={"error": {"code": code, "message": message, "details": details or {}}})


def _check_dependency_ready(url: str) -> bool:
    try:
        with request.urlopen(url, timeout=REQUEST_TIMEOUT) as resp:
            if resp.status != 200:
                return False
            data = json.loads(resp.read().decode() or "{}")
            return data.get("status") in {"ready", "healthy"}
    except Exception:
        return False


def _gpu_infer(authorization: str, client_id: str, prompt: str, model: str | None = None) -> str | None:
    """Forward a prompt to the GPU router; return the response text or None on failure."""
    payload = json.dumps({
        "client_id": client_id,
        "model": model or GPU_DEFAULT_MODEL,
        "prompt": prompt,
    }).encode()
    req = request.Request(
        f"{GPU_ROUTER_URL}/api/v2/gpu/infer",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": authorization,
        },
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=float(os.environ.get("GPU_INFER_TIMEOUT", "120"))) as resp:
            data = json.loads(resp.read().decode() or "{}")
            return data.get("response") or None
    except Exception:
        return None


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


def _ensure_case_exists(case_id: str, authorization: str) -> None:
    encoded_case_id = parse.quote(case_id, safe="")
    req = request.Request(
        f"{TENANT_SERVICE_URL}/api/v2/cases/{encoded_case_id}",
        headers={"Authorization": authorization},
        method="GET",
    )
    try:
        with request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            if resp.status != 200:
                _error(503, "dependency_unavailable", "Tenant service unavailable", {"status": resp.status})
    except error.HTTPError as exc:
        if exc.code == 404:
            _error(404, "resource_not_found", "Case was not found", {"case_id": case_id})
        if exc.code == 401:
            _error(401, "unauthorized", "Session is not active")
        _error(503, "dependency_unavailable", "Tenant service unavailable", {"status": exc.code})
    except Exception:
        _error(503, "dependency_unavailable", "Tenant service unavailable")


init_db()


@app.get(f"{API_PREFIX}/live")
def live():
    return {"status": "alive", "service": "ai", "timestamp": _now_utc()}


@app.get(f"{API_PREFIX}/ready")
def ready(response: Response):
    db_ok = True
    try:
        with _db() as conn:
            conn.execute("SELECT 1").fetchone()
    except sqlite3.Error:
        db_ok = False

    auth_ok = _check_dependency_ready(AUTH_READY_URL)
    tenant_ok = _check_dependency_ready(TENANT_READY_URL)
    gpu_ok = _check_dependency_ready(GPU_ROUTER_READY_URL)
    is_ready = db_ok and auth_ok and tenant_ok

    response.status_code = 200 if is_ready else 503
    return {
        "status": "ready" if is_ready else "not-ready",
        "service": "ai",
        "dependencies": {"database": db_ok, "auth": auth_ok, "tenant": tenant_ok, "gpu_router": gpu_ok},
    }


@app.get(f"{API_PREFIX}/health")
def health():
    with _db() as conn:
        count = conn.execute("SELECT COUNT(*) FROM assist_events").fetchone()[0]
    return {"status": "healthy", "service": "ai", "version": VERSION, "assist_count": count}


@app.post(f"{API_PREFIX}/ai/assist")
def assist(payload: AiAssistRequest, authorization: str | None = Header(default=None)):
    user = _require_auth(authorization)
    _ensure_case_exists(payload.case_id, authorization)

    prompt = payload.prompt.strip()

    # Try real inference via the GPU router first; fall back to stub if unavailable.
    gpu_response = _gpu_infer(
        authorization=authorization or "",
        client_id="govos-core",
        prompt=(
            f"You are a govOS legal-case assistant. Case: {payload.case_id}. "
            + (f"Context: {json.dumps(payload.context)}. " if payload.context else "")
            + f"Request: {prompt}"
        ) if prompt else f"Summarise next actions for case {payload.case_id}.",
    )

    if gpu_response:
        summary = gpu_response
    elif prompt:
        summary = f"Assistant reviewed your prompt and prepared next actions for case {payload.case_id}."
    else:
        summary = (
            f"Suggested next step for case {payload.case_id}: gather timeline facts, "
            f"organize evidence, and generate a draft document."
        )

    event = {
        "id": str(uuid4()),
        "case_id": payload.case_id,
        "prompt": payload.prompt,
        "context_json": json.dumps(payload.context) if payload.context else None,
        "summary": summary,
        "created_at": _now_utc(),
        "created_by": user.get("id", "unknown"),
    }

    with _db() as conn:
        conn.execute(
            """
            INSERT INTO assist_events (id, case_id, prompt, context_json, summary, created_at, created_by)
            VALUES (:id, :case_id, :prompt, :context_json, :summary, :created_at, :created_by)
            """,
            event,
        )
        conn.commit()

    try:
        emit_workboard_job(
            source="govos-v2-ai",
            action="ai.assist.completed",
            event=f"V2 AI ASSIST QUEUED: {event['id']}",
            lane="engineering",  # AI analysis is private intelligence; self-heals
            payload={
                "assist_id": event["id"],
                "case_id": event["case_id"],
                "created_by": event["created_by"],
            },
        )
    except Exception:
        pass

    return {
        "case_id": payload.case_id,
        "summary": summary,
        "actions": [
            "Review latest timeline events",
            "Generate notice draft from template",
            "Upload supporting files to evidence storage",
        ],
    }
