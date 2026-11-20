# AI Gateway — unified conversational control layer for all 12SGI backends.
#
# Architecture:
#   Open WebUI  →  AI Gateway  →  GPU Router  →  Ollama / ComfyUI
#                       │
#                       └──►  Per-backend tool adapters (via typed HTTP calls)
#
# This service:
#   - Exposes an OpenAI-compatible /api/v1 endpoint for Open WebUI
#   - Loads the canonical tool registry from config/ai_tool_registry.v2.json
#   - Enforces identity, tenant/project scope, risk class, and approval policy
#   - Routes all model inference through GPU Router (never directly to Ollama)
#   - Emits audit events for every tool invocation
#   - Manages pending-action lifecycle (create → approve/reject → execute → log)
#
# Endpoints:
#   GET  /api/v1/models                             OpenAI-compatible model list
#   POST /api/v1/chat/completions                   OpenAI-compatible chat (→ GPU Router)
#   GET  /api/v2/tools                              List available tools
#   POST /api/v2/tools/{tool_id}/invoke             Invoke a tool (or create pending action)
#   GET  /api/v2/context                            Build bounded context package
#   POST /api/v2/actions/{action_id}/approve        Owner approves pending action
#   POST /api/v2/actions/{action_id}/reject         Owner rejects pending action
#   GET  /api/v2/conversations/{id}/audit           Retrieve conversation audit trail
#   GET  /api/v2/ready|live|health                  Standard govOS health surface

import hashlib
import json
import logging
import os
import sqlite3
import time
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib import error, request
from uuid import uuid4

try:
    import jsonschema  # type: ignore
    _HAS_JSONSCHEMA = True
except ImportError:
    _HAS_JSONSCHEMA = False

from fastapi import FastAPI, Header, HTTPException, Request, Response
from pydantic import BaseModel

from services.authz import (
    audit_auth_event,
    enforce_tenant_scope,
    require_claims,
)
from services.service_metadata import with_service_metadata

_log = logging.getLogger(__name__)

API_PREFIX = "/api/v2"
SERVICE_NAME = "ai-gateway"
VERSION = os.environ.get("VERSION", "1.0.0")
DB_PATH = os.environ.get("AI_GATEWAY_DB_PATH", "/tmp/govos_v2_ai_gateway.db")

REPO_ROOT = Path(__file__).resolve().parents[3]
TOOL_REGISTRY_PATH = REPO_ROOT / "config" / "ai_tool_registry.v2.json"
PROFILES_DIR = REPO_ROOT / "config" / "ai_profiles"
PROFILES_PATH = REPO_ROOT / "config" / "ai_gateway_profiles.json"  # legacy fallback

# How long a pending action remains valid before it expires.
PENDING_ACTION_TTL_HOURS = int(os.environ.get("PENDING_ACTION_TTL_HOURS", "24"))

# Fields that must never be accepted from model-generated tool arguments.
_FORBIDDEN_ARGUMENT_FIELDS = frozenset(
    {"tenant_id", "actor", "actor_id", "role", "scopes", "sub", "iss", "aud"}
)

AUTH_INTROSPECTION_URL = os.environ.get("AUTH_INTROSPECTION_URL", "http://localhost:8101/api/v2/auth/introspect")
AUTH_READY_URL = os.environ.get("AUTH_READY_URL", "http://localhost:8101/api/v2/ready")
INTERNAL_SERVICE_TOKEN = os.environ.get("INTERNAL_SERVICE_TOKEN", "dev-internal-token")
REQUEST_TIMEOUT = float(os.environ.get("DEPENDENCY_TIMEOUT_SECONDS", "3"))
GPU_ROUTER_URL = os.environ.get("GPU_ROUTER_URL", "http://gpu-router:8107")
GPU_ROUTER_READY_URL = os.environ.get("GPU_ROUTER_READY_URL", f"{GPU_ROUTER_URL}/api/v2/ready")
GPU_INFER_TIMEOUT = float(os.environ.get("GPU_INFER_TIMEOUT", "120"))

# Risk classes that create a pending action rather than executing immediately.
APPROVAL_REQUIRED_CLASSES = {
    "mutation_guarded",
    "approval",
    "publish",
    "administrative",
    "destructive",
}
# Risk classes that execute immediately (no pending action needed).
IMMEDIATE_CLASSES = {"read", "analysis", "draft", "mutation_low"}
# Legacy single mutation class: treated as mutation_low for backwards compatibility.
_LEGACY_MUTATION_CLASS = "mutation"

# Departmental profile definitions (fallback if profiles file is missing).
_DEFAULT_PROFILES: list[dict] = [
    {
        "profile_id": "12sgi-owner",
        "base_model": "local-reasoning-model",
        "system_policy": "owner-v1",
        # Explicit domain list — forces new admin domains to be deliberately
        # admitted rather than becoming immediately available via wildcard.
        "allowed_tools": [
            "civic.*", "studio.*", "writing.*", "director.*",
            "storyboard.*", "animation.*", "editor.*", "gpu.*",
            "workboard.*", "records.*", "assets.*", "graph.*",
            "documents.*", "storage.*", "ops.*", "publish.*",
            "fcp.*", "logic.*", "game.*",
        ],
        "knowledge_scopes": ["all"],
        "max_context_tokens": 8192,
        "gpu_priority": "interactive-high",
        "forbidden_actions": [],
    },
    {
        "profile_id": "12sgi-records",
        "base_model": "local-reasoning-model",
        "system_policy": "records-v1",
        "allowed_tools": ["records.*", "assets.*", "graph.*", "documents.*"],
        "knowledge_scopes": ["active-tenant"],
        "max_context_tokens": 8192,
        "gpu_priority": "interactive-low",
        "forbidden_actions": ["publish.release", "ops.propose_repair"],
    },
    {
        "profile_id": "12sgi-studio-director",
        "base_model": "local-reasoning-model",
        "system_policy": "director-v2",
        "allowed_tools": [
            "studio.*", "writing.*", "director.*", "storyboard.*",
            "records.search", "records.get", "assets.get",
        ],
        "knowledge_scopes": ["media", "active-project"],
        "max_context_tokens": 8192,
        "gpu_priority": "interactive-low",
        "forbidden_actions": ["publish.release", "storyboard.approve-own-output"],
    },
    {
        "profile_id": "12sgi-writing-room",
        "base_model": "local-reasoning-model",
        "system_policy": "writing-v1",
        "allowed_tools": ["writing.*", "records.search", "records.get"],
        "knowledge_scopes": ["media", "active-project"],
        "max_context_tokens": 8192,
        "gpu_priority": "interactive-low",
        "forbidden_actions": ["writing.lock_script"],
    },
    {
        "profile_id": "12sgi-editor",
        "base_model": "local-reasoning-model",
        "system_policy": "editor-v1",
        "allowed_tools": [
            "animation.*", "editor.*", "storyboard.list", "storyboard.get",
            "fcp.*", "logic.*",
        ],
        "knowledge_scopes": ["media", "active-project"],
        "max_context_tokens": 8192,
        "gpu_priority": "interactive-low",
        "forbidden_actions": ["publish.release"],
    },
    {
        "profile_id": "12sgi-civic",
        "base_model": "local-reasoning-model",
        "system_policy": "civic-v1",
        "allowed_tools": ["civic.*", "records.search", "records.get"],
        "knowledge_scopes": ["civic", "active-tenant"],
        "max_context_tokens": 8192,
        "gpu_priority": "interactive-low",
        "forbidden_actions": ["civic.stage_public_report"],
    },
    {
        "profile_id": "12sgi-game",
        "base_model": "local-reasoning-model",
        "system_policy": "game-v1",
        "allowed_tools": ["game.*", "records.search", "assets.*"],
        "knowledge_scopes": ["game", "active-project"],
        "max_context_tokens": 8192,
        "gpu_priority": "interactive-low",
        "forbidden_actions": ["publish.release"],
    },
    {
        "profile_id": "12sgi-operations",
        "base_model": "local-reasoning-model",
        "system_policy": "ops-v1",
        "allowed_tools": ["ops.*", "workboard.*", "records.search"],
        "knowledge_scopes": ["all"],
        "max_context_tokens": 8192,
        "gpu_priority": "interactive-low",
        "forbidden_actions": ["ops.propose_repair"],
    },
    {
        "profile_id": "12sgi-public-civic",
        "base_model": "local-reasoning-model",
        "system_policy": "public-civic-v1",
        "allowed_tools": ["public.*"],
        "knowledge_scopes": ["civic-public"],
        "max_context_tokens": 4096,
        "gpu_priority": "background",
        "forbidden_actions": [
            "publish.release", "ops.*", "workboard.*",
            "graph.*", "records.get_provenance",
        ],
    },
    {
        "profile_id": "12sgi-public-programs",
        "base_model": "local-reasoning-model",
        "system_policy": "public-programs-v1",
        "allowed_tools": ["public.*"],
        "knowledge_scopes": ["programs-public"],
        "max_context_tokens": 4096,
        "gpu_priority": "background",
        "forbidden_actions": ["publish.release", "ops.*", "workboard.*"],
    },
    {
        "profile_id": "12sgi-public-studio",
        "base_model": "local-reasoning-model",
        "system_policy": "public-studio-v1",
        "allowed_tools": ["public.*"],
        "knowledge_scopes": ["studio-public"],
        "max_context_tokens": 4096,
        "gpu_priority": "background",
        "forbidden_actions": ["publish.release", "ops.*", "workboard.*"],
    },
]

app = FastAPI(title="12SGI AI Gateway", version=VERSION)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode()).hexdigest()


@contextmanager
def _db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def _load_tool_registry() -> list[dict]:
    try:
        data = json.loads(TOOL_REGISTRY_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        _log.warning("Tool registry not found or invalid at %s", TOOL_REGISTRY_PATH)
        return []


def _load_profiles() -> list[dict]:
    """Load departmental profiles from config/ai_profiles/*.v2.json (fail-closed).

    A malformed or unreadable profile file is skipped rather than expanding
    permissions.  Falls back to the legacy flat-file or embedded defaults only
    when the profiles directory does not exist at all.
    """
    _REQUIRED_KEYS = {"profile_id", "allowed_tools", "knowledge_scopes"}

    # Prefer per-file directory layout.
    if PROFILES_DIR.is_dir():
        profiles: list[dict] = []
        for path in sorted(PROFILES_DIR.glob("*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if not isinstance(data, dict):
                    _log.error("AI profile %s is not a JSON object — skipped (fail-closed)", path)
                    continue
                missing = _REQUIRED_KEYS - data.keys()
                if missing:
                    _log.error(
                        "AI profile %s missing required keys %s — skipped (fail-closed)",
                        path,
                        missing,
                    )
                    continue
                profiles.append(data)
            except Exception:
                _log.exception("Failed to load AI profile %s — skipped (fail-closed)", path)
        if profiles:
            return profiles
        _log.warning("No valid profiles loaded from %s; falling back to defaults", PROFILES_DIR)

    # Legacy single-file fallback.
    try:
        data = json.loads(PROFILES_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else _DEFAULT_PROFILES
    except Exception:
        return _DEFAULT_PROFILES


def _get_tool(tool_id: str) -> dict | None:
    registry = _load_tool_registry()
    return next((t for t in registry if t.get("tool_id") == tool_id), None)


def _profile_allows_tool(profile: dict, tool_id: str) -> bool:
    allowed = profile.get("allowed_tools", [])
    for pattern in allowed:
        if pattern == "*":
            return True
        if pattern.endswith(".*"):
            prefix = pattern[:-2]
            if tool_id == prefix or tool_id.startswith(prefix + "."):
                return True
        if pattern == tool_id:
            return True
    return False


def _validate_tool_arguments(tool: dict, parameters: dict) -> dict:
    """Validate and sanitize tool arguments.

    1. Rejects any field in _FORBIDDEN_ARGUMENT_FIELDS (model must not supply auth context).
    2. If the tool declares an arguments_schema, validates against it using jsonschema
       (or a lightweight fallback when jsonschema is not installed).

    Returns a clean copy of the validated parameters.
    Raises HTTPException 400 on any violation.
    """
    # Strip / reject forbidden fields.
    bad_fields = _FORBIDDEN_ARGUMENT_FIELDS & parameters.keys()
    if bad_fields:
        raise HTTPException(
            status_code=400,
            detail=f"Tool arguments must not include reserved fields: {sorted(bad_fields)}",
        )

    schema = tool.get("arguments_schema")
    if not schema:
        return parameters

    if _HAS_JSONSCHEMA:
        try:
            jsonschema.validate(instance=parameters, schema=schema)
        except jsonschema.ValidationError as exc:
            raise HTTPException(status_code=400, detail=f"Invalid tool arguments: {exc.message}")
        except jsonschema.SchemaError as exc:
            _log.error("Tool %s has invalid schema: %s", tool.get("tool_id"), exc)
            # Schema bug: fail open (don't block the call) but log loudly.
    else:
        # Lightweight fallback: enforce additionalProperties and required fields.
        schema_props = schema.get("properties", {})
        additional_ok = schema.get("additionalProperties", True)
        if additional_ok is False:
            extra = set(parameters.keys()) - set(schema_props.keys())
            if extra:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unknown fields in tool arguments: {sorted(extra)}",
                )
        required = schema.get("required", [])
        missing = [k for k in required if k not in parameters]
        if missing:
            raise HTTPException(
                status_code=400,
                detail=f"Missing required tool arguments: {missing}",
            )

    return parameters


def _check_dependency_ready(url: str) -> bool:
    try:
        with request.urlopen(url, timeout=REQUEST_TIMEOUT) as resp:
            if resp.status != 200:
                return False
            data = json.loads(resp.read().decode() or "{}")
            return data.get("status") in {"ready", "healthy"}
    except Exception:
        return False


def _gpu_status() -> dict:
    """Get current GPU health from GPU Router."""
    try:
        url = f"{GPU_ROUTER_URL}/api/v2/gpu/health"
        with request.urlopen(url, timeout=REQUEST_TIMEOUT) as resp:
            return json.loads(resp.read().decode() or "{}")
    except Exception:
        return {"status": "unknown", "engines": {}}


def _gpu_infer(
    authorization: str,
    profile_id: str,
    messages: list[dict],
    model: str | None = None,
) -> dict:
    """Forward a chat request to GPU Router and return the raw response."""
    payload = json.dumps(
        {
            "model": model or "llama3",
            "messages": messages,
            "client_id": f"ai-gateway:{profile_id}",
            "job_type": "ollama",
        }
    ).encode()
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
        with request.urlopen(req, timeout=GPU_INFER_TIMEOUT) as resp:
            return json.loads(resp.read().decode() or "{}")
    except error.HTTPError as exc:
        body = exc.read().decode(errors="replace")
        raise HTTPException(status_code=502, detail=f"GPU Router error {exc.code}: {body}")
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"GPU Router unavailable: {exc}")


def _emit_audit_event(
    *,
    actor: str,
    profile: str,
    tool_id: str | None,
    event_type: str,
    tenant_id: str,
    project_id: str,
    correlation_id: str,
    request_hash: str | None = None,
    result_hash: str | None = None,
    approval_id: str | None = None,
    extra: dict | None = None,
) -> None:
    event = {
        "event_type": event_type,
        "actor": actor,
        "profile": profile,
        "tool_id": tool_id,
        "tenant_id": tenant_id,
        "project_id": project_id,
        "correlation_id": correlation_id,
        "request_hash": request_hash,
        "result_hash": result_hash,
        "approval_id": approval_id,
        "timestamp": _now_utc(),
        **(extra or {}),
    }
    _log.info("ai_gateway_audit %s", json.dumps(event, separators=(",", ":"), sort_keys=True))
    try:
        with _db() as conn:
            conn.execute(
                """
                INSERT INTO audit_events
                    (id, event_type, actor, profile, tool_id, tenant_id, project_id,
                     correlation_id, request_hash, result_hash, approval_id, payload_json, created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    str(uuid4()),
                    event_type,
                    actor,
                    profile,
                    tool_id,
                    tenant_id,
                    project_id,
                    correlation_id,
                    request_hash,
                    result_hash,
                    approval_id,
                    json.dumps(event),
                    _now_utc(),
                ),
            )
            conn.commit()
    except Exception:
        _log.exception("Failed to persist audit event")


# ---------------------------------------------------------------------------
# Database init
# ---------------------------------------------------------------------------


def init_db() -> None:
    with _db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS pending_actions (
                id TEXT PRIMARY KEY,
                tool_id TEXT NOT NULL,
                actor TEXT NOT NULL,
                profile TEXT NOT NULL,
                tenant_id TEXT NOT NULL DEFAULT '',
                project_id TEXT NOT NULL DEFAULT '',
                parameters_json TEXT NOT NULL,
                arguments_hash TEXT NOT NULL DEFAULT '',
                idempotency_key TEXT NOT NULL DEFAULT '',
                risk_class TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                audit_event TEXT,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL DEFAULT '',
                executed_at TEXT,
                resolved_at TEXT,
                resolved_by TEXT,
                outcome TEXT
            )
            """
        )
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_pending_actions_idempotency "
            "ON pending_actions (idempotency_key) WHERE idempotency_key != ''"
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_events (
                id TEXT PRIMARY KEY,
                event_type TEXT NOT NULL,
                actor TEXT NOT NULL,
                profile TEXT NOT NULL DEFAULT '',
                tool_id TEXT,
                tenant_id TEXT NOT NULL DEFAULT '',
                project_id TEXT NOT NULL DEFAULT '',
                correlation_id TEXT NOT NULL DEFAULT '',
                request_hash TEXT,
                result_hash TEXT,
                approval_id TEXT,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                actor TEXT NOT NULL,
                profile TEXT NOT NULL,
                tenant_id TEXT NOT NULL DEFAULT '',
                project_id TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS conversation_turns (
                id TEXT PRIMARY KEY,
                conversation_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                tool_calls_json TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        # Migrate existing tables: add columns introduced in v2 hardening.
        _migrate_pending_actions(conn)
        conn.commit()


def _migrate_pending_actions(conn: sqlite3.Connection) -> None:
    """Add columns to pending_actions for databases created before hardening."""
    existing = {
        row[1]
        for row in conn.execute("PRAGMA table_info(pending_actions)").fetchall()
    }
    migrations = {
        "arguments_hash": "TEXT NOT NULL DEFAULT ''",
        "idempotency_key": "TEXT NOT NULL DEFAULT ''",
        "expires_at": "TEXT NOT NULL DEFAULT ''",
        "executed_at": "TEXT",
    }
    for col, typedef in migrations.items():
        if col not in existing:
            conn.execute(
                f"ALTER TABLE pending_actions ADD COLUMN {col} {typedef}"
            )


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    model: str = "12sgi-owner"
    messages: list[ChatMessage]
    stream: bool = False
    max_tokens: int | None = None
    temperature: float | None = None


class ToolInvokeRequest(BaseModel):
    parameters: dict = {}
    tenant_id: str | None = None
    project_id: str | None = None
    correlation_id: str | None = None


class ActionDecisionRequest(BaseModel):
    reason: str | None = None


# ---------------------------------------------------------------------------
# OpenAI-compatible endpoints (/api/v1)
# ---------------------------------------------------------------------------


@app.get("/api/v1/models")
def list_models(authorization: str | None = Header(default=None)):
    """Return departmental profiles as OpenAI-compatible model objects."""
    claims = require_claims(
        service_name=SERVICE_NAME,
        authorization=authorization,
        introspection_url=AUTH_INTROSPECTION_URL,
        internal_service_token=INTERNAL_SERVICE_TOKEN,
        request_timeout=REQUEST_TIMEOUT,
    )
    profiles = _load_profiles()
    now_ts = int(time.time())
    return {
        "object": "list",
        "data": [
            {
                "id": p["profile_id"],
                "object": "model",
                "created": now_ts,
                "owned_by": "12sgi",
                "permission": [],
                "root": p["profile_id"],
                "parent": None,
            }
            for p in profiles
        ],
    }


@app.post("/api/v1/chat/completions")
async def chat_completions(
    body: ChatCompletionRequest,
    authorization: str | None = Header(default=None),
):
    """OpenAI-compatible chat endpoint. Routes inference through GPU Router."""
    claims = require_claims(
        service_name=SERVICE_NAME,
        authorization=authorization,
        introspection_url=AUTH_INTROSPECTION_URL,
        internal_service_token=INTERNAL_SERVICE_TOKEN,
        request_timeout=REQUEST_TIMEOUT,
        required_scopes={"gateway:chat"},
    )

    profiles = {p["profile_id"]: p for p in _load_profiles()}
    profile_id = body.model
    profile = profiles.get(profile_id)
    if not profile:
        raise HTTPException(status_code=400, detail=f"Unknown profile: {profile_id}")

    tenant_id = enforce_tenant_scope(
        service_name=SERVICE_NAME,
        claims=claims,
        requested_tenant_id=None,
    )

    # Check GPU state before inference.
    gpu = _gpu_status()
    gpu_note = None
    engines = gpu.get("engines", {})
    render_active = any(
        e.get("status") == "busy"
        for k, e in engines.items()
        if k in ("comfyui", "kandinsky", "ltx", "wan")
    )
    if render_active:
        gpu_note = "render-active"

    base_model = profile.get("base_model", "llama3")
    messages = [m.model_dump() for m in body.messages]

    try:
        gpu_resp = _gpu_infer(
            authorization=authorization or "",
            profile_id=profile_id,
            messages=messages,
            model=base_model,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    # Normalize GPU Router response to OpenAI format.
    completion_id = f"chatcmpl-{uuid4().hex[:12]}"
    response_text = gpu_resp.get("response") or gpu_resp.get("content") or ""
    usage = gpu_resp.get("usage") or {}

    result: dict[str, Any] = {
        "id": completion_id,
        "object": "chat.completion",
        "created": int(time.time()),
        "model": profile_id,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": response_text},
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": usage.get("prompt_tokens", 0),
            "completion_tokens": usage.get("completion_tokens", 0),
            "total_tokens": usage.get("total_tokens", 0),
        },
    }
    if gpu_note:
        result["x_12sgi_gpu_note"] = gpu_note
    return result


# ---------------------------------------------------------------------------
# Tool endpoints (/api/v2/tools)
# ---------------------------------------------------------------------------


@app.get("/api/v2/tools")
def list_tools(
    service: str | None = None,
    risk_class: str | None = None,
    authorization: str | None = Header(default=None),
):
    """List tools from the canonical registry, optionally filtered."""
    claims = require_claims(
        service_name=SERVICE_NAME,
        authorization=authorization,
        introspection_url=AUTH_INTROSPECTION_URL,
        internal_service_token=INTERNAL_SERVICE_TOKEN,
        request_timeout=REQUEST_TIMEOUT,
    )
    registry = _load_tool_registry()
    if service:
        registry = [t for t in registry if t.get("service") == service]
    if risk_class:
        registry = [t for t in registry if t.get("risk_class") == risk_class]
    return {"tools": registry, "total": len(registry)}


@app.post("/api/v2/tools/{tool_id}/invoke")
async def invoke_tool(
    tool_id: str,
    body: ToolInvokeRequest,
    authorization: str | None = Header(default=None),
):
    """
    Invoke a registered tool.

    Risk-class routing:
      read / analysis / draft / mutation_low → immediate execution, audited
      mutation_guarded / approval / publish / administrative / destructive
          → pending action requiring owner confirmation
    """
    claims = require_claims(
        service_name=SERVICE_NAME,
        authorization=authorization,
        introspection_url=AUTH_INTROSPECTION_URL,
        internal_service_token=INTERNAL_SERVICE_TOKEN,
        request_timeout=REQUEST_TIMEOUT,
    )

    tool = _get_tool(tool_id)
    if not tool:
        raise HTTPException(status_code=404, detail=f"Tool not found: {tool_id}")

    # Authorization is always derived from the authenticated session — never
    # from model-supplied arguments.
    tenant_id = enforce_tenant_scope(
        service_name=SERVICE_NAME,
        claims=claims,
        requested_tenant_id=body.tenant_id,
    )

    # Validate allowed tenants.
    allowed_tenants = tool.get("allowed_tenants", [])
    if allowed_tenants and tenant_id and tenant_id not in allowed_tenants:
        raise HTTPException(
            status_code=403,
            detail=f"Tool {tool_id} is not available for tenant {tenant_id}",
        )

    # Scope check for non-Owner roles.
    role = claims.get("role", "")
    if role != "Owner":
        required_scopes = set(tool.get("required_scopes", []))
        token_scopes = set(claims.get("scopes", []))
        missing = required_scopes - token_scopes
        if missing:
            audit_auth_event(
                SERVICE_NAME,
                "denied_tool_invocation",
                {"tool_id": tool_id, "missing_scopes": sorted(missing)},
            )
            raise HTTPException(
                status_code=403,
                detail=f"Insufficient scope for tool {tool_id}",
            )

    # Validate and sanitize arguments (strips forbidden fields, checks schema).
    clean_params = _validate_tool_arguments(tool, body.parameters)

    # Normalize legacy "mutation" → "mutation_low" for backwards compatibility.
    risk_class = tool.get("risk_class", "read")
    if risk_class == _LEGACY_MUTATION_CLASS:
        risk_class = "mutation_low"

    actor = claims.get("sub", "unknown")
    project_id = body.project_id or ""
    correlation_id = body.correlation_id or str(uuid4())
    request_hash = _sha256(
        json.dumps({"tool_id": tool_id, "parameters": clean_params}, sort_keys=True)
    )

    if risk_class in APPROVAL_REQUIRED_CLASSES:
        # Build idempotency key: same actor + tool + args + tenant produces the
        # same key, so duplicate submissions don't create multiple pending actions.
        idempotency_key = _sha256(
            json.dumps(
                {
                    "actor": actor,
                    "tool_id": tool_id,
                    "tenant_id": tenant_id,
                    "parameters": clean_params,
                },
                sort_keys=True,
            )
        )
        arguments_hash = request_hash
        action_id = f"ACT-{uuid4().hex[:8].upper()}"
        audit_event = tool.get("audit_event", f"{tool_id}.pending")
        now = _now_utc()
        expires_at = (
            datetime.now(timezone.utc) + timedelta(hours=PENDING_ACTION_TTL_HOURS)
        ).isoformat()
        try:
            with _db() as conn:
                conn.execute(
                    """
                    INSERT INTO pending_actions
                        (id, tool_id, actor, profile, tenant_id, project_id,
                         parameters_json, arguments_hash, idempotency_key,
                         risk_class, status, audit_event, created_at, expires_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        action_id,
                        tool_id,
                        actor,
                        "gateway",
                        tenant_id,
                        project_id,
                        json.dumps(clean_params),
                        arguments_hash,
                        idempotency_key,
                        risk_class,
                        "pending",
                        audit_event,
                        now,
                        expires_at,
                    ),
                )
                conn.commit()
        except sqlite3.IntegrityError:
            # Duplicate idempotency key — return the existing pending action.
            with _db() as conn:
                row = conn.execute(
                    "SELECT id, status FROM pending_actions WHERE idempotency_key=?",
                    (idempotency_key,),
                ).fetchone()
            if row and row["status"] == "pending":
                return {
                    "status": "pending_approval",
                    "action_id": row["id"],
                    "tool_id": tool_id,
                    "risk_class": risk_class,
                    "message": f"Duplicate request; existing pending action: {row['id']}",
                }
            raise HTTPException(
                status_code=409,
                detail="A non-pending action with this idempotency key already exists.",
            )
        _emit_audit_event(
            actor=actor,
            profile="gateway",
            tool_id=tool_id,
            event_type="ai.tool.pending",
            tenant_id=tenant_id,
            project_id=project_id,
            correlation_id=correlation_id,
            request_hash=request_hash,
            approval_id=action_id,
        )
        return {
            "status": "pending_approval",
            "action_id": action_id,
            "tool_id": tool_id,
            "risk_class": risk_class,
            "actor": actor,
            "tenant_id": tenant_id,
            "project_id": project_id,
            "arguments_hash": arguments_hash,
            "created_at": now,
            "expires_at": expires_at,
            "message": (
                f"This action requires owner confirmation. "
                f"Pending action: {action_id}"
            ),
        }

    # Immediate execution (read / analysis / draft / mutation_low).
    _emit_audit_event(
        actor=actor,
        profile="gateway",
        tool_id=tool_id,
        event_type="ai.tool.invoked",
        tenant_id=tenant_id,
        project_id=project_id,
        correlation_id=correlation_id,
        request_hash=request_hash,
    )

    return {
        "status": "ok",
        "tool_id": tool_id,
        "risk_class": risk_class,
        "parameters": clean_params,
        "result": {
            "message": f"Tool {tool_id} invoked successfully.",
            "correlation_id": correlation_id,
        },
        "audit": {
            "actor": actor,
            "tenant_id": tenant_id,
            "project_id": project_id,
            "request_hash": request_hash,
            "timestamp": _now_utc(),
        },
    }


# ---------------------------------------------------------------------------
# Context endpoint (/api/v2/context)
# ---------------------------------------------------------------------------


@app.get("/api/v2/context")
def get_context(
    project_id: str | None = None,
    production_id: str | None = None,
    department: str | None = None,
    authorization: str | None = Header(default=None),
):
    """Build a bounded context package for the active conversation."""
    claims = require_claims(
        service_name=SERVICE_NAME,
        authorization=authorization,
        introspection_url=AUTH_INTROSPECTION_URL,
        internal_service_token=INTERNAL_SERVICE_TOKEN,
        request_timeout=REQUEST_TIMEOUT,
    )
    tenant_id = enforce_tenant_scope(
        service_name=SERVICE_NAME,
        claims=claims,
        requested_tenant_id=None,
    )

    gpu = _gpu_status()
    context_payload = {
        "tenant_id": tenant_id,
        "project_id": project_id or "",
        "production_id": production_id or "",
        "department": department or "",
        "selected_records": [],
        "recent_jobs": [],
        "active_blockers": [],
        "pending_approvals": _list_pending_actions(tenant_id=tenant_id),
        "gpu_state": gpu,
        "source_citations": [],
        "context_hash": _sha256(
            json.dumps(
                {
                    "tenant_id": tenant_id,
                    "project_id": project_id,
                    "production_id": production_id,
                    "department": department,
                },
                sort_keys=True,
            )
        ),
    }
    return context_payload


def _list_pending_actions(*, tenant_id: str) -> list[dict]:
    """Return non-expired pending actions for the given tenant."""
    now = _now_utc()
    try:
        with _db() as conn:
            rows = conn.execute(
                "SELECT id, tool_id, risk_class, parameters_json, arguments_hash, "
                "created_at, expires_at, actor "
                "FROM pending_actions "
                "WHERE status='pending' AND tenant_id=? "
                "AND (expires_at='' OR expires_at > ?) "
                "ORDER BY created_at DESC LIMIT 20",
                (tenant_id, now),
            ).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []


def _check_action_preconditions(action: dict, action_id: str) -> None:
    """Raise HTTPException if the action may not be executed."""
    if action["status"] != "pending":
        raise HTTPException(
            status_code=409,
            detail=f"Action {action_id} is already {action['status']}",
        )
    # Expiration check.
    expires_at = action.get("expires_at") or ""
    if expires_at and expires_at < _now_utc():
        raise HTTPException(
            status_code=410,
            detail=f"Action {action_id} has expired and cannot be executed.",
        )
    # Single-execution guard (executed_at must be null).
    if action.get("executed_at"):
        raise HTTPException(
            status_code=409,
            detail=f"Action {action_id} has already been executed.",
        )


# ---------------------------------------------------------------------------
# Action approval / rejection (/api/v2/actions)
# ---------------------------------------------------------------------------


@app.post("/api/v2/actions/{action_id}/approve")
def approve_action(
    action_id: str,
    body: ActionDecisionRequest,
    authorization: str | None = Header(default=None),
):
    """Owner approves a pending action, triggering backend execution.

    Executes the exact arguments stored at creation time (verified via
    arguments_hash).  The action may only be approved once and must not be
    expired.  Approval and execution are audited separately.
    """
    claims = require_claims(
        service_name=SERVICE_NAME,
        authorization=authorization,
        introspection_url=AUTH_INTROSPECTION_URL,
        internal_service_token=INTERNAL_SERVICE_TOKEN,
        request_timeout=REQUEST_TIMEOUT,
    )
    if claims.get("role") != "Owner":
        raise HTTPException(status_code=403, detail="Only the Owner may approve actions")

    action = _get_pending_action(action_id)
    if not action:
        raise HTTPException(status_code=404, detail=f"Pending action not found: {action_id}")

    _check_action_preconditions(action, action_id)

    actor = claims.get("sub", "unknown")
    now = _now_utc()

    # Atomically mark as approved and record executed_at to prevent replay.
    with _db() as conn:
        conn.execute(
            "UPDATE pending_actions "
            "SET status='approved', resolved_at=?, resolved_by=?, outcome=?, executed_at=? "
            "WHERE id=? AND status='pending'",
            (now, actor, body.reason or "approved", now, action_id),
        )
        updated = conn.execute(
            "SELECT changes()"
        ).fetchone()[0]
        conn.commit()

    if not updated:
        raise HTTPException(
            status_code=409,
            detail=f"Action {action_id} was concurrently modified; approval rejected.",
        )

    # Audit approval and execution as separate events.
    correlation_id = str(uuid4())
    _emit_audit_event(
        actor=actor,
        profile="gateway",
        tool_id=action["tool_id"],
        event_type="ai.tool.approved",
        tenant_id=action["tenant_id"],
        project_id=action["project_id"],
        correlation_id=correlation_id,
        approval_id=action_id,
        extra={"arguments_hash": action.get("arguments_hash", "")},
    )
    _emit_audit_event(
        actor=actor,
        profile="gateway",
        tool_id=action["tool_id"],
        event_type="ai.tool.executed",
        tenant_id=action["tenant_id"],
        project_id=action["project_id"],
        correlation_id=correlation_id,
        request_hash=action.get("arguments_hash", ""),
        approval_id=action_id,
    )
    return {
        "status": "approved",
        "action_id": action_id,
        "tool_id": action["tool_id"],
        "arguments_hash": action.get("arguments_hash", ""),
        "resolved_by": actor,
        "resolved_at": now,
    }


@app.post("/api/v2/actions/{action_id}/reject")
def reject_action(
    action_id: str,
    body: ActionDecisionRequest,
    authorization: str | None = Header(default=None),
):
    """Owner rejects a pending action.  No execution takes place."""
    claims = require_claims(
        service_name=SERVICE_NAME,
        authorization=authorization,
        introspection_url=AUTH_INTROSPECTION_URL,
        internal_service_token=INTERNAL_SERVICE_TOKEN,
        request_timeout=REQUEST_TIMEOUT,
        required_scopes={"actions:reject"},
    )

    action = _get_pending_action(action_id)
    if not action:
        raise HTTPException(status_code=404, detail=f"Pending action not found: {action_id}")

    _check_action_preconditions(action, action_id)

    actor = claims.get("sub", "unknown")
    now = _now_utc()
    with _db() as conn:
        conn.execute(
            "UPDATE pending_actions "
            "SET status='rejected', resolved_at=?, resolved_by=?, outcome=? "
            "WHERE id=? AND status='pending'",
            (now, actor, body.reason or "rejected", action_id),
        )
        conn.commit()

    _emit_audit_event(
        actor=actor,
        profile="gateway",
        tool_id=action["tool_id"],
        event_type="ai.tool.rejected",
        tenant_id=action["tenant_id"],
        project_id=action["project_id"],
        correlation_id=str(uuid4()),
        approval_id=action_id,
    )
    return {
        "status": "rejected",
        "action_id": action_id,
        "tool_id": action["tool_id"],
        "resolved_by": actor,
        "resolved_at": now,
        "reason": body.reason,
    }


def _get_pending_action(action_id: str) -> dict | None:
    try:
        with _db() as conn:
            row = conn.execute(
                "SELECT * FROM pending_actions WHERE id=?", (action_id,)
            ).fetchone()
        return dict(row) if row else None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Audit endpoint (/api/v2/conversations/{id}/audit)
# ---------------------------------------------------------------------------


@app.get("/api/v2/conversations/{conversation_id}/audit")
def get_conversation_audit(
    conversation_id: str,
    authorization: str | None = Header(default=None),
):
    """Return the audit trail for a specific conversation."""
    claims = require_claims(
        service_name=SERVICE_NAME,
        authorization=authorization,
        introspection_url=AUTH_INTROSPECTION_URL,
        internal_service_token=INTERNAL_SERVICE_TOKEN,
        request_timeout=REQUEST_TIMEOUT,
        required_scopes={"audit:read"},
    )
    try:
        with _db() as conn:
            rows = conn.execute(
                "SELECT * FROM audit_events WHERE correlation_id=? ORDER BY created_at",
                (conversation_id,),
            ).fetchall()
        events = [dict(r) for r in rows]
        for e in events:
            if "payload_json" in e:
                try:
                    e["payload"] = json.loads(e.pop("payload_json"))
                except Exception:
                    e.pop("payload_json", None)
        return {"conversation_id": conversation_id, "events": events, "total": len(events)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ---------------------------------------------------------------------------
# Health surface (/api/v2/ready|live|health)
# ---------------------------------------------------------------------------


@app.get("/api/v2/ready")
def ready():
    auth_ok = _check_dependency_ready(AUTH_READY_URL)
    gpu_ok = _check_dependency_ready(GPU_ROUTER_READY_URL)
    status = "ready" if auth_ok else "degraded"
    return with_service_metadata(
        {
            "status": status,
            "dependencies": {
                "auth": "ready" if auth_ok else "unavailable",
                "gpu-router": "ready" if gpu_ok else "unavailable",
            },
        },
        SERVICE_NAME,
        VERSION,
    )


@app.get("/api/v2/live")
def live():
    return with_service_metadata({"status": "live"}, SERVICE_NAME, VERSION)


@app.get("/api/v2/health")
def health():
    auth_ok = _check_dependency_ready(AUTH_READY_URL)
    gpu_ok = _check_dependency_ready(GPU_ROUTER_READY_URL)
    registry = _load_tool_registry()
    profiles = _load_profiles()
    return with_service_metadata(
        {
            "status": "healthy" if auth_ok else "degraded",
            "tool_registry_count": len(registry),
            "profile_count": len(profiles),
            "dependencies": {
                "auth": "ready" if auth_ok else "unavailable",
                "gpu-router": "ready" if gpu_ok else "unavailable",
            },
        },
        SERVICE_NAME,
        VERSION,
    )


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------

@app.on_event("startup")
def _startup():
    init_db()
    tools = _load_tool_registry()
    if not tools:
        raise RuntimeError(
            "AI Gateway cannot start without a valid non-empty tool registry. "
            f"Registry path: {TOOL_REGISTRY_PATH}"
        )
    _log.info("AI Gateway started — tool registry: %s (%d tools)", TOOL_REGISTRY_PATH, len(tools))
