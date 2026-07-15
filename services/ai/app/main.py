import json
import os
import sqlite3
import base64
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
RENDER_ROUTING_MODE = os.environ.get("RENDER_ROUTING_MODE", "hybrid").strip().lower()
COMFYUI_NATIVE_URL = os.environ.get("COMFYUI_NATIVE_URL", "").strip()
COMFYUI_NATIVE_READY_URL = os.environ.get("COMFYUI_NATIVE_READY_URL", "").strip()
COMFYUI_GPU_WORKER_QUEUE = os.environ.get("COMFYUI_GPU_WORKER_QUEUE", "").strip()
GPU_WORKER_HEARTBEAT_URL = os.environ.get("GPU_WORKER_HEARTBEAT_URL", "").strip()
NEO4J_ENABLED = os.environ.get("NEO4J_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}
NEO4J_URL = os.environ.get("NEO4J_URL", "http://localhost:7474").rstrip("/")
NEO4J_USERNAME = os.environ.get("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD", "neo4j")
NEO4J_DATABASE = os.environ.get("NEO4J_DATABASE", "neo4j")
NEO4J_REQUIRED_FOR_RENDER_DISPATCH = os.environ.get("NEO4J_REQUIRED_FOR_RENDER_DISPATCH", "false").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}

app = FastAPI(title="govOS v2 AI Service", version=VERSION)


class AiAssistRequest(BaseModel):
    case_id: str
    prompt: str
    context: dict | None = None


class RenderDispatchRequest(BaseModel):
    prompt: str
    case_id: str | None = None
    tenant_id: str | None = None
    project_id: str | None = None
    workflow_id: str | None = None
    priority: str | None = "normal"
    route_hint: str | None = None
    assets: list[str] | None = None


class GraphNodeRef(BaseModel):
    kind: str
    id: str


class GraphStringEdgeRequest(BaseModel):
    source: GraphNodeRef
    relation: str
    target: GraphNodeRef
    weight: float | None = 1.0
    context: dict | None = None
    case_id: str | None = None
    tenant_id: str | None = None
    project_id: str | None = None


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
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS render_dispatch_events (
                id TEXT PRIMARY KEY,
                case_id TEXT,
                tenant_id TEXT,
                project_id TEXT,
                workflow_id TEXT,
                prompt TEXT NOT NULL,
                assets_json TEXT,
                route TEXT NOT NULL,
                target TEXT NOT NULL,
                priority TEXT NOT NULL,
                graph_status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                created_by TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS graph_string_edges (
                id TEXT PRIMARY KEY,
                source_kind TEXT NOT NULL,
                source_id TEXT NOT NULL,
                relation TEXT NOT NULL,
                target_kind TEXT NOT NULL,
                target_id TEXT NOT NULL,
                weight REAL NOT NULL,
                context_json TEXT,
                case_id TEXT,
                tenant_id TEXT,
                project_id TEXT,
                graph_status TEXT NOT NULL,
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


def _check_dependency_live(url: str) -> bool:
    try:
        with request.urlopen(url, timeout=REQUEST_TIMEOUT) as resp:
            return 200 <= resp.status < 400
    except Exception:
        return False


def _neo4j_headers() -> dict[str, str]:
    token = base64.b64encode(f"{NEO4J_USERNAME}:{NEO4J_PASSWORD}".encode()).decode()
    return {"Authorization": f"Basic {token}", "Content-Type": "application/json"}


def _neo4j_commit(statements: list[dict]) -> None:
    payload = json.dumps({"statements": statements}).encode()
    req = request.Request(
        f"{NEO4J_URL}/db/{parse.quote(NEO4J_DATABASE, safe='')}/tx/commit",
        data=payload,
        headers=_neo4j_headers(),
        method="POST",
    )
    with request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
        if resp.status != 200:
            _error(503, "dependency_unavailable", "Neo4j unavailable", {"status": resp.status})
        body = json.loads(resp.read().decode() or "{}")
    if body.get("errors"):
        _error(503, "dependency_unavailable", "Neo4j query failed", {"errors": body.get("errors")})


def _neo4j_ready() -> bool:
    try:
        _neo4j_commit([{"statement": "RETURN 1 AS ok"}])
        return True
    except HTTPException:
        return False
    except Exception:
        return False


ALLOWED_NODE_KINDS = {
    "tenant": "Tenant",
    "project": "Project",
    "case": "Case",
    "workflow": "Workflow",
    "render_dispatch": "RenderDispatch",
    "scene": "Scene",
    "shot": "Shot",
    "asset": "Asset",
    "prompt": "Prompt",
    "model": "Model",
}
ALLOWED_RELATIONS = {
    "CONNECTS_TO",
    "INFLUENCES",
    "USES_ASSET",
    "USES_MODEL",
    "PART_OF",
    "PRECEDES",
    "DERIVES_FROM",
    "LINKS_TO",
}


def _normalize_node_kind(kind: str) -> tuple[str, str]:
    key = (kind or "").strip().lower()
    if key not in ALLOWED_NODE_KINDS:
        _error(400, "invalid_input", "Unsupported node kind", {"kind": kind, "allowed": sorted(ALLOWED_NODE_KINDS.keys())})
    return key, ALLOWED_NODE_KINDS[key]


def _normalize_relation(relation: str) -> str:
    key = (relation or "").strip().upper()
    if key not in ALLOWED_RELATIONS:
        _error(400, "invalid_input", "Unsupported relation", {"relation": relation, "allowed": sorted(ALLOWED_RELATIONS)})
    return key


def _persist_string_edge_graph(event: dict) -> dict:
    if not NEO4J_ENABLED:
        return {"status": "disabled"}
    source_label = event["source_label"]
    target_label = event["target_label"]
    relation = event["relation"]
    statement = (
        f"MERGE (s:{source_label} {{id: $source_id}}) "
        f"MERGE (t:{target_label} {{id: $target_id}}) "
        f"MERGE (s)-[r:{relation}]->(t) "
        "SET r.weight = $weight, r.updated_at = $created_at, r.updated_by = $created_by, r.context = $context_json "
        "MERGE (e:StringEdge {id: $edge_id}) "
        "SET e.relation = $relation, e.weight = $weight, e.updated_at = $created_at, e.updated_by = $created_by, e.context = $context_json "
        "MERGE (s)-[:EDGE_SOURCE]->(e) "
        "MERGE (e)-[:EDGE_TARGET]->(t) "
        "WITH e "
        "FOREACH (_ IN CASE WHEN $tenant_id IS NULL THEN [] ELSE [1] END | "
        "  MERGE (tn:Tenant {id: $tenant_id}) MERGE (tn)-[:HAS_STRING_EDGE]->(e)) "
        "FOREACH (_ IN CASE WHEN $project_id IS NULL THEN [] ELSE [1] END | "
        "  MERGE (pn:Project {id: $project_id}) MERGE (pn)-[:HAS_STRING_EDGE]->(e)) "
        "FOREACH (_ IN CASE WHEN $case_id IS NULL THEN [] ELSE [1] END | "
        "  MERGE (cn:Case {id: $case_id}) MERGE (cn)-[:HAS_STRING_EDGE]->(e))"
    )
    _neo4j_commit(
        [
            {
                "statement": statement,
                "parameters": {
                    "source_id": event["source_id"],
                    "target_id": event["target_id"],
                    "edge_id": event["id"],
                    "relation": event["relation"],
                    "weight": event["weight"],
                    "created_at": event["created_at"],
                    "created_by": event["created_by"],
                    "context_json": event["context_json"],
                    "tenant_id": event["tenant_id"],
                    "project_id": event["project_id"],
                    "case_id": event["case_id"],
                },
            }
        ]
    )
    return {"status": "recorded"}


def _routing_target(route_hint: str | None = None) -> tuple[str, str, dict]:
    native_enabled = bool(COMFYUI_NATIVE_URL)
    queue_enabled = bool(COMFYUI_GPU_WORKER_QUEUE)
    native_ok = _check_dependency_live(COMFYUI_NATIVE_READY_URL) if COMFYUI_NATIVE_READY_URL else native_enabled
    queue_ok = _check_dependency_live(GPU_WORKER_HEARTBEAT_URL) if GPU_WORKER_HEARTBEAT_URL else queue_enabled
    details = {
        "mode": RENDER_ROUTING_MODE,
        "native_enabled": native_enabled,
        "native_ok": native_ok,
        "queue_enabled": queue_enabled,
        "queue_ok": queue_ok,
    }

    requested = (route_hint or "").strip().lower()
    if requested:
        if requested == "native":
            if not native_enabled or not native_ok:
                _error(503, "dependency_unavailable", "Native ComfyUI route is unavailable", details)
            return "native_comfyui", COMFYUI_NATIVE_URL, details
        if requested == "queue":
            if not queue_enabled or not queue_ok:
                _error(503, "dependency_unavailable", "GPU worker queue route is unavailable", details)
            return "gpu_worker_queue", COMFYUI_GPU_WORKER_QUEUE, details
        _error(400, "invalid_input", "route_hint must be either 'native' or 'queue'")

    if RENDER_ROUTING_MODE == "native_only":
        if not native_enabled or not native_ok:
            _error(503, "dependency_unavailable", "Native ComfyUI route is unavailable", details)
        return "native_comfyui", COMFYUI_NATIVE_URL, details

    if RENDER_ROUTING_MODE == "queue_only":
        if not queue_enabled or not queue_ok:
            _error(503, "dependency_unavailable", "GPU worker queue route is unavailable", details)
        return "gpu_worker_queue", COMFYUI_GPU_WORKER_QUEUE, details

    if native_enabled and native_ok:
        return "native_comfyui", COMFYUI_NATIVE_URL, details
    if queue_enabled and queue_ok:
        return "gpu_worker_queue", COMFYUI_GPU_WORKER_QUEUE, details

    _error(503, "dependency_unavailable", "No render route is currently available", details)


def _persist_render_graph(event: dict) -> dict:
    if not NEO4J_ENABLED:
        return {"status": "disabled"}
    _neo4j_commit(
        [
            {
                "statement": (
                    "MERGE (r:RenderDispatch {id: $dispatch_id}) "
                    "SET r.case_id = $case_id, r.workflow_id = $workflow_id, r.route = $route, r.target = $target, "
                    "r.priority = $priority, r.created_at = $created_at, r.created_by = $created_by "
                    "WITH r "
                    "FOREACH (_ IN CASE WHEN $tenant_id IS NULL THEN [] ELSE [1] END | "
                    "  MERGE (t:Tenant {id: $tenant_id}) MERGE (t)-[:HAS_RENDER_DISPATCH]->(r)) "
                    "FOREACH (_ IN CASE WHEN $project_id IS NULL THEN [] ELSE [1] END | "
                    "  MERGE (p:Project {id: $project_id}) MERGE (p)-[:HAS_RENDER_DISPATCH]->(r))"
                ),
                "parameters": {
                    "dispatch_id": event["id"],
                    "case_id": event["case_id"],
                    "tenant_id": event["tenant_id"],
                    "project_id": event["project_id"],
                    "workflow_id": event["workflow_id"],
                    "route": event["route"],
                    "target": event["target"],
                    "priority": event["priority"],
                    "created_at": event["created_at"],
                    "created_by": event["created_by"],
                },
            }
        ]
    )
    return {"status": "recorded"}


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
    deps = {"database": db_ok, "auth": auth_ok, "tenant": tenant_ok}
    if NEO4J_ENABLED:
        deps["neo4j"] = _neo4j_ready()
    is_ready = all(deps.values())

    response.status_code = 200 if is_ready else 503
    return {
        "status": "ready" if is_ready else "not-ready",
        "service": "ai",
        "dependencies": deps,
        "render_routing": {
            "mode": RENDER_ROUTING_MODE,
            "native_configured": bool(COMFYUI_NATIVE_URL),
            "queue_configured": bool(COMFYUI_GPU_WORKER_QUEUE),
        },
    }


@app.get(f"{API_PREFIX}/health")
def health():
    with _db() as conn:
        count = conn.execute("SELECT COUNT(*) FROM assist_events").fetchone()[0]
        dispatch_count = conn.execute("SELECT COUNT(*) FROM render_dispatch_events").fetchone()[0]
        string_edge_count = conn.execute("SELECT COUNT(*) FROM graph_string_edges").fetchone()[0]
    return {
        "status": "healthy",
        "service": "ai",
        "version": VERSION,
        "assist_count": count,
        "render_dispatch_count": dispatch_count,
        "string_edge_count": string_edge_count,
    }


@app.post(f"{API_PREFIX}/ai/assist")
def assist(payload: AiAssistRequest, authorization: str | None = Header(default=None)):
    user = _require_auth(authorization)
    _ensure_case_exists(payload.case_id, authorization)

    prompt = payload.prompt.strip()
    summary = (
        f"Suggested next step for case {payload.case_id}: gather timeline facts, "
        f"organize evidence, and generate a draft document."
    )
    if prompt:
        summary = f"Assistant reviewed your prompt and prepared next actions for case {payload.case_id}."

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


@app.post(f"{API_PREFIX}/ai/render/dispatch")
def dispatch_render(payload: RenderDispatchRequest, authorization: str | None = Header(default=None)):
    user = _require_auth(authorization)
    if payload.case_id:
        _ensure_case_exists(payload.case_id, authorization)
    route, target, route_details = _routing_target(payload.route_hint)

    event = {
        "id": str(uuid4()),
        "case_id": payload.case_id,
        "tenant_id": payload.tenant_id,
        "project_id": payload.project_id,
        "workflow_id": payload.workflow_id,
        "prompt": payload.prompt,
        "assets_json": json.dumps(payload.assets or []),
        "route": route,
        "target": target,
        "priority": payload.priority or "normal",
        "graph_status": "pending",
        "created_at": _now_utc(),
        "created_by": user.get("id", "unknown"),
    }

    graph = {"status": "disabled"}
    try:
        graph = _persist_render_graph(event)
    except HTTPException:
        if NEO4J_REQUIRED_FOR_RENDER_DISPATCH:
            raise
        graph = {"status": "error", "message": "neo4j_write_failed_non_blocking"}

    event["graph_status"] = graph.get("status", "unknown")

    with _db() as conn:
        conn.execute(
            """
            INSERT INTO render_dispatch_events
            (id, case_id, tenant_id, project_id, workflow_id, prompt, assets_json, route, target, priority, graph_status, created_at, created_by)
            VALUES
            (:id, :case_id, :tenant_id, :project_id, :workflow_id, :prompt, :assets_json, :route, :target, :priority, :graph_status, :created_at, :created_by)
            """,
            event,
        )
        conn.commit()

    entry = emit_workboard_job(
        source="govos-v2-ai",
        action="render.dispatch.queued",
        event=f"V2 RENDER DISPATCH QUEUED: {event['id']} -> {route}",
        payload={
            "dispatch_id": event["id"],
            "case_id": event["case_id"],
            "tenant_id": event["tenant_id"],
            "project_id": event["project_id"],
            "workflow_id": event["workflow_id"],
            "route": event["route"],
            "target": event["target"],
            "assets": payload.assets or [],
            "prompt": payload.prompt,
        },
        priority=event["priority"],
    )

    return {
        "dispatch_id": event["id"],
        "status": "queued",
        "route": route,
        "target": target,
        "queue_entry_id": entry["job"]["id"],
        "graph": graph,
        "routing": route_details,
    }


@app.post(f"{API_PREFIX}/ai/graph/string-edge")
def upsert_string_edge(payload: GraphStringEdgeRequest, authorization: str | None = Header(default=None)):
    user = _require_auth(authorization)
    if payload.case_id:
        _ensure_case_exists(payload.case_id, authorization)
    source_key, source_label = _normalize_node_kind(payload.source.kind)
    target_key, target_label = _normalize_node_kind(payload.target.kind)
    relation = _normalize_relation(payload.relation)

    event = {
        "id": str(uuid4()),
        "source_kind": source_key,
        "source_label": source_label,
        "source_id": payload.source.id.strip(),
        "relation": relation,
        "target_kind": target_key,
        "target_label": target_label,
        "target_id": payload.target.id.strip(),
        "weight": float(payload.weight or 1.0),
        "context_json": json.dumps(payload.context or {}),
        "case_id": payload.case_id,
        "tenant_id": payload.tenant_id,
        "project_id": payload.project_id,
        "graph_status": "pending",
        "created_at": _now_utc(),
        "created_by": user.get("id", "unknown"),
    }

    graph = {"status": "disabled"}
    try:
        graph = _persist_string_edge_graph(event)
    except HTTPException:
        if NEO4J_REQUIRED_FOR_RENDER_DISPATCH:
            raise
        graph = {"status": "error", "message": "neo4j_write_failed_non_blocking"}
    event["graph_status"] = graph.get("status", "unknown")

    with _db() as conn:
        conn.execute(
            """
            INSERT INTO graph_string_edges
            (id, source_kind, source_id, relation, target_kind, target_id, weight, context_json, case_id, tenant_id, project_id, graph_status, created_at, created_by)
            VALUES
            (:id, :source_kind, :source_id, :relation, :target_kind, :target_id, :weight, :context_json, :case_id, :tenant_id, :project_id, :graph_status, :created_at, :created_by)
            """,
            event,
        )
        conn.commit()

    entry = emit_workboard_job(
        source="govos-v2-ai",
        action="graph.string_edge.upserted",
        event=f"V2 STRING EDGE UPSERTED: {event['id']} {source_key}:{event['source_id']} -[{relation}]-> {target_key}:{event['target_id']}",
        payload={
            "string_edge_id": event["id"],
            "source": {"kind": source_key, "id": event["source_id"]},
            "target": {"kind": target_key, "id": event["target_id"]},
            "relation": relation,
            "weight": event["weight"],
            "tenant_id": event["tenant_id"],
            "project_id": event["project_id"],
            "case_id": event["case_id"],
        },
        priority="normal",
    )
    return {
        "string_edge_id": event["id"],
        "status": "upserted",
        "source": {"kind": source_key, "id": event["source_id"]},
        "relation": relation,
        "target": {"kind": target_key, "id": event["target_id"]},
        "weight": event["weight"],
        "graph": graph,
        "queue_entry_id": entry["job"]["id"],
    }
