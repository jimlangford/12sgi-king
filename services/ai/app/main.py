import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from urllib import error, parse, request
from uuid import uuid4

from fastapi import FastAPI, Header, HTTPException, Response
from pydantic import BaseModel

from services.authz import auth_error, enforce_resource_tenant, require_claims
from services.service_metadata import with_service_metadata
from services.v2_workboard import emit_workboard_job

API_PREFIX = "/api/v2"
SERVICE_NAME = "ai"
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
GPU_DEFAULT_MODEL = os.environ.get("GPU_DEFAULT_MODEL", "llama3.2")

app = FastAPI(title="govOS v2 AI Service", version=VERSION)


class AiAssistRequest(BaseModel):
    case_id: str
    prompt: str
    context: dict | None = None


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def _db():
    # sqlite3.Connection.__exit__ only commits/rolls back a transaction -- it does NOT close the
    # connection, so `with _db() as conn:` at every call site was leaking one open handle per
    # request. Harmless on Linux until enough requests accumulate; on Windows it locks the db file
    # against deletion immediately (caught by tests/v2/test_v2_hardening.py). Transactional
    # behavior at call sites is unchanged -- they already commit explicitly where needed.
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def init_db() -> None:
    with _db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS assist_events (
                id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL DEFAULT '',
                case_id TEXT NOT NULL,
                prompt TEXT NOT NULL,
                context_json TEXT,
                summary TEXT NOT NULL,
                created_at TEXT NOT NULL,
                created_by TEXT NOT NULL
            )
            """
        )
        # Migration-safe: ADD COLUMN on a table that predates this field errors if it already
        # exists -- catch and ignore rather than gating on a PRAGMA read every boot.
        try:
            conn.execute("ALTER TABLE assist_events ADD COLUMN grounded INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass
        try:
            conn.execute("ALTER TABLE assist_events ADD COLUMN tenant_id TEXT NOT NULL DEFAULT ''")
        except sqlite3.OperationalError:
            pass
        conn.commit()


def _check_dependency_ready(url: str) -> bool:
    try:
        with request.urlopen(url, timeout=REQUEST_TIMEOUT) as resp:
            if resp.status != 200:
                return False
            data = json.loads(resp.read().decode() or "{}")
            return data.get("status") in {"ready", "healthy"}
    except Exception:
        return False


def _gpu_infer(authorization: str, client_id: str, prompt: str, model: str | None = None, tenant_id: str | None = None) -> str | None:
    """Forward a prompt to the GPU router; return the response text or None on failure."""
    payload = json.dumps({
        "client_id": client_id,
        "tenant_id": tenant_id,
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


def _ensure_case_exists(case_id: str, authorization: str) -> dict:
    encoded_case_id = parse.quote(case_id, safe="")
    req = request.Request(
        f"{TENANT_SERVICE_URL}/api/v2/cases/{encoded_case_id}",
        headers={"Authorization": authorization},
        method="GET",
    )
    try:
        with request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            if resp.status != 200:
                auth_error(503, "dependency_unavailable", "Tenant service unavailable", {"status": resp.status})
            return json.loads(resp.read().decode() or "{}")
    except error.HTTPError as exc:
        if exc.code == 404:
            auth_error(404, "resource_not_found", "Case was not found", {"case_id": case_id})
        if exc.code == 401:
            auth_error(401, "unauthorized", "Session is not active")
        auth_error(503, "dependency_unavailable", "Tenant service unavailable", {"status": exc.code})
    except Exception:
        auth_error(503, "dependency_unavailable", "Tenant service unavailable")


init_db()


@app.get(f"{API_PREFIX}/live")
def live():
    return with_service_metadata(
        {"status": "alive", "timestamp": _now_utc()},
        SERVICE_NAME,
        VERSION,
    )


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
    # gpu_ok is intentionally excluded from is_ready: GPU is a best-effort enhancement —
    # the ai service degrades to stub responses when the router is unavailable, so GPU
    # unavailability does not make the ai service itself un-ready.
    is_ready = db_ok and auth_ok and tenant_ok

    response.status_code = 200 if is_ready else 503
    return with_service_metadata(
        {
            "status": "ready" if is_ready else "not-ready",
            "dependencies": {"database": db_ok, "auth": auth_ok, "tenant": tenant_ok, "gpu_router": gpu_ok},
        },
        SERVICE_NAME,
        VERSION,
    )


@app.get(f"{API_PREFIX}/health")
def health():
    with _db() as conn:
        count = conn.execute("SELECT COUNT(*) FROM assist_events").fetchone()[0]
        grounded_count = conn.execute(
            "SELECT COUNT(*) FROM assist_events WHERE grounded = 1"
        ).fetchone()[0]
    # grounded_ratio makes correctness auditable at a glance: a sustained drop means the GPU
    # router/Ollama backend is unreachable and this service has been silently answering with
    # UNGROUNDED template text -- the same signal workboard_evidence.py's needs_verify backlog
    # gave on the laptop system, surfaced here instead of discovered by reading case notes.
    return {
        **with_service_metadata({}, SERVICE_NAME, VERSION),
        "status": "healthy",
        "assist_count": count,
        "grounded_count": grounded_count,
        "grounded_ratio": round(grounded_count / count, 3) if count else None,
    }


@app.post(f"{API_PREFIX}/ai/assist")
def assist(payload: AiAssistRequest, authorization: str | None = Header(default=None)):
    claims = require_claims(
        service_name=SERVICE_NAME,
        authorization=authorization,
        introspection_url=AUTH_INTROSPECTION_URL,
        internal_service_token=INTERNAL_SERVICE_TOKEN,
        request_timeout=REQUEST_TIMEOUT,
        required_scopes={"ai:assist"},
    )
    case = _ensure_case_exists(payload.case_id, authorization or "")
    case_tenant_id = case.get("tenant_id", "")
    enforce_resource_tenant(service_name=SERVICE_NAME, claims=claims, resource_tenant_id=case_tenant_id)

    prompt = payload.prompt.strip()

    # Try real inference via the GPU router first; fall back to stub if unavailable.
    gpu_response = _gpu_infer(
        authorization=authorization or "",
        client_id="govos-core",
        tenant_id=case_tenant_id,
        prompt=(
            f"You are a govOS legal-case assistant. Case: {payload.case_id}. "
            + (f"Context: {json.dumps(payload.context)}. " if payload.context else "")
            + f"Request: {prompt}"
        ) if prompt else f"Summarise next actions for case {payload.case_id}.",
    )

    # POLICY (2026-07-09, mirrors tools/ops/workboard_evidence.py on the laptop system, and RAG-
    # grounding best practice: never present ungrounded output with the same confidence as a real
    # model answer -- a caller reading "summary" has no way to tell a real GPU-router response from
    # a hardcoded placeholder string unless the response says so explicitly). grounded=False means
    # no inference actually ran; the summary is a template, not analysis, and must be flagged as
    # such rather than worded to sound like the assistant "reviewed" anything. We still answer with
    # 200 (the request itself succeeded) and persist the event so /health's grounded_ratio stays
    # accurate -- a 503 here would drop the event entirely and hide degraded-mode activity.
    grounded = bool(gpu_response)
    if grounded:
        summary = gpu_response
        actions: list[dict] = []
    else:
        summary = (
            "UNGROUNDED: GPU inference was unavailable, so this is a placeholder response, not "
            "real model analysis. This case has been flagged for human review."
        )
        actions = [
            {"type": "flag_for_human_review", "case_id": payload.case_id},
            {"type": "retry_ai_assist", "case_id": payload.case_id},
            {"type": "notify_case_owner", "case_id": payload.case_id},
        ]

    event = {
        "id": str(uuid4()),
        "tenant_id": case_tenant_id,
        "case_id": payload.case_id,
        "prompt": payload.prompt,
        "context_json": json.dumps(payload.context) if payload.context else None,
        "summary": summary,
        "created_at": _now_utc(),
        "created_by": claims.get("sub", "unknown"),
        "grounded": int(grounded),
    }

    with _db() as conn:
        conn.execute(
            """
            INSERT INTO assist_events (id, tenant_id, case_id, prompt, context_json, summary, created_at, created_by, grounded)
            VALUES (:id, :tenant_id, :case_id, :prompt, :context_json, :summary, :created_at, :created_by, :grounded)
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
        "grounded": grounded,
        "actions": actions,
    }
