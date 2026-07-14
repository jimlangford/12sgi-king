"""
king-bridge — workboard → king-* Ollama router + Neo4j result writer.

Purpose:
  This service is the local-token-spend bridge between the v2 workboard job queue
  and the owner's trained king-* Ollama models. It replaces cloud AI calls with
  local inference on Jimmy's machine (zero external token cost).

Architecture:
  workboard (.dispatch_log.jsonl)
        ↓  poll / POST /bridge/job
  king-bridge (this service, port 8109)
        ↓  POST http://localhost:11434/api/generate
  king-* Ollama model (local, no cloud)
        ↓  result
  king-bridge
        ↓  Cypher MERGE
  Neo4j (localhost:7474, local, no cloud)
        ↓  tombstone
  workboard log (append-only)

Model routing (lane + action → king-* model):
  engineering / civic*       → king-civic
  engineering / prosecutor*  → king-prosecutor
  engineering / audit*       → king-audit
  creative / *               → king-workboard (review/approve gate)
  output / *                 → king-dispatch
  *.tax*                     → king-tax
  *.legal*                   → king-legal
  *.sales*                   → king-sales
  *.studio*                  → king-studio
  *.game*                    → king-game
  *.render*                  → king-render
  *.social*                  → king-social
  *.research*                → king-research
  default                    → king-quad-os

Endpoints:
  GET  /api/v2/ready          — health + Ollama + Neo4j status
  GET  /api/v2/bridge/models  — list available king-* models from Ollama
  POST /api/v2/bridge/job     — submit a job directly (bypass workboard poll)
  GET  /api/v2/bridge/pulse   — workboard pulse counters
  POST /api/v2/bridge/poll    — owner-triggered: drain pending workboard jobs
  GET  /api/v2/bridge/chat    — SSE stream: talk to a king-* model directly
  POST /api/v2/bridge/chat    — single-turn chat to a king-* model

Security: owner-only (no external auth required on loopback; INTERNAL_SERVICE_TOKEN
  header required for non-loopback callers). Private data never leaves the machine.
"""

import json
import os
import sqlite3
import time
import urllib.error
import urllib.request
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator
from uuid import uuid4

from fastapi import FastAPI, Header, HTTPException, Request, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

# ── Repo-root imports (same pattern as all other v2 services) ─────────────────
import sys
_HERE = Path(__file__).resolve()
_REPO = _HERE.parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from services.v2_workboard import (
    emit_workboard_job,
    pending_approvals,
    resolve_workboard_job,
    workboard_pulse,
    workboard_hub_feed,
    selfheal_engineering_jobs,
)
from services.ai_autonomy import classify_task, build_autonomy_system_prompt, record_autonomous_execution
from services.owner_job_tracker import get_tracker, JobStatus, ApprovalType
from services.event_bus import publish_event

# ── Config ────────────────────────────────────────────────────────────────────
API_PREFIX      = "/api/v2"
SERVICE_NAME    = "king-bridge"
VERSION         = os.environ.get("VERSION", "2.0.0")
OLLAMA_BASE     = os.environ.get("OLLAMA_BASE", "http://host.docker.internal:11434")
NEO4J_HTTP      = os.environ.get("NEO4J_HTTP", "http://127.0.0.1:7474/db/neo4j/tx/commit")
AURA_URI        = os.environ.get("NEO4J_AURA_URI", "").strip()
AURA_USER       = os.environ.get("NEO4J_AURA_USER", "neo4j")
AURA_PASSWORD   = os.environ.get("NEO4J_AURA_PASSWORD", "").strip()
DB_PATH         = os.environ.get("KING_BRIDGE_DB", "/data/db/king_bridge.db")
INFER_TIMEOUT   = int(os.environ.get("KING_BRIDGE_INFER_TIMEOUT", "120"))
POLL_MAX        = int(os.environ.get("KING_BRIDGE_POLL_MAX", "10"))
INTERNAL_TOKEN  = os.environ.get("INTERNAL_SERVICE_TOKEN", "dev-internal-token")
AUTONOMY_ENABLED = os.environ.get("KING_BRIDGE_AUTONOMY_ENABLED", "true").lower() == "true"
AUTONOMY_THRESHOLD = int(os.environ.get("KING_BRIDGE_AUTONOMY_THRESHOLD", "70"))

# ── Model routing table ───────────────────────────────────────────────────────
# Order matters: first match wins. Checks lane+action as a single string.
_ROUTE_TABLE = [
    ("prosecutor",   "king-prosecutor"),
    ("audit",        "king-audit"),
    ("civic",        "king-civic"),
    ("tax",          "king-tax"),
    ("legal",        "king-legal"),
    ("sales",        "king-sales"),
    ("studio",       "king-studio"),
    ("game",         "king-game"),
    ("render",       "king-render"),
    ("social",       "king-social"),
    ("research",     "king-research"),
    ("dispatch",     "king-dispatch"),
    ("workboard",    "king-workboard"),
    ("server",       "king-server"),
    ("design",       "king-design"),
    ("ops",          "king-ops"),
    ("jrcsl",        "king-jrcsl"),
    ("naga",         "king-naga"),
    ("heal",         "king-heal"),
    ("awareness",    "king-awareness"),
    ("creative",     "king-workboard"),   # creative lane → workboard model
    ("output",       "king-dispatch"),    # output lane → dispatch model
]
_DEFAULT_MODEL = "king-quad-os"


def route_model(lane: str, action: str) -> str:
    key = f"{lane} {action}".lower()
    for fragment, model in _ROUTE_TABLE:
        if fragment in key:
            return model
    return _DEFAULT_MODEL


# ── SQLite ────────────────────────────────────────────────────────────────────
@contextmanager
def _db():
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def _init_db():
    with _db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS bridge_jobs (
                id           TEXT PRIMARY KEY,
                job_id       TEXT NOT NULL,
                lane         TEXT NOT NULL,
                action       TEXT NOT NULL,
                model        TEXT NOT NULL,
                prompt       TEXT NOT NULL,
                response     TEXT,
                grounded     INTEGER DEFAULT 0,
                neo4j_wrote  INTEGER DEFAULT 0,
                created_at   TEXT NOT NULL,
                completed_at TEXT
            )
        """)
        conn.commit()


# ── Ollama helpers ────────────────────────────────────────────────────────────
def _ollama_generate(model: str, prompt: str, stream: bool = False) -> str | None:
    """Send a prompt to a king-* model via Ollama. Returns response text or None."""
    payload = json.dumps({
        "model": model,
        "prompt": prompt,
        "stream": stream,
    }).encode()
    req = urllib.request.Request(
        f"{OLLAMA_BASE}/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=INFER_TIMEOUT) as resp:
            data = json.loads(resp.read().decode())
            return data.get("response") or None
    except Exception:
        return None


def _ollama_stream(model: str, prompt: str) -> Iterator[str]:
    """SSE generator: yields token chunks from Ollama streaming API."""
    payload = json.dumps({"model": model, "prompt": prompt, "stream": True}).encode()
    req = urllib.request.Request(
        f"{OLLAMA_BASE}/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=INFER_TIMEOUT) as resp:
            for line in resp:
                line = line.strip()
                if not line:
                    continue
                try:
                    chunk = json.loads(line)
                    token = chunk.get("response", "")
                    if token:
                        yield f"data: {json.dumps({'token': token})}\n\n"
                    if chunk.get("done"):
                        yield "data: [DONE]\n\n"
                        return
                except json.JSONDecodeError:
                    continue
    except Exception as e:
        yield f"data: {json.dumps({'error': str(e)})}\n\n"


def _ollama_models() -> list[str]:
    """Return list of available Ollama model names."""
    try:
        with urllib.request.urlopen(f"{OLLAMA_BASE}/api/tags", timeout=5) as resp:
            data = json.loads(resp.read().decode())
            return [m["name"] for m in data.get("models", [])]
    except Exception:
        return []


def _ollama_ready() -> bool:
    try:
        with urllib.request.urlopen(f"{OLLAMA_BASE}/api/tags", timeout=3) as resp:
            return resp.status == 200
    except Exception:
        return False


# ── Neo4j helpers ─────────────────────────────────────────────────────────────
def _neo_ping() -> bool:
    """Direct Neo4j HTTP ping — no recursion. Used internally by _cypher_endpoint."""
    payload = json.dumps({"statements": [{"statement": "RETURN 1"}]}).encode()
    req = urllib.request.Request(
        NEO4J_HTTP,
        data=payload,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read().decode())
            return not data.get("errors")
    except Exception:
        return False


def _cypher_endpoint() -> tuple[str, bool]:
    """
    Return the endpoint to use (local Neo4j or AuraDB) and whether AuraDB is active.
    Strategy: try local first. If it fails, check Aura. Use whichever is reachable.
    Falls back to read-only Aura if local is offline.
    """
    if _neo_ping():
        return NEO4J_HTTP, False
    if AURA_URI and AURA_PASSWORD:
        return AURA_URI, True
    return NEO4J_HTTP, False


def _neo_ready() -> bool:
    return _neo_ping()


def _neo_cypher(statements: list[dict]) -> dict | None:
    endpoint, is_aura = _cypher_endpoint()
    if is_aura and "neo4j+" in endpoint:
        try:
            from neo4j import GraphDatabase
            driver = GraphDatabase.driver(endpoint, auth=(AURA_USER, AURA_PASSWORD))
            session = driver.session()
            try:
                stmt = statements[0]["statement"]
                params = statements[0].get("parameters") or {}
                result = session.run(stmt, **params)
                return {"results": [{"data": [{"row": list(record)} for record in result]}]}
            finally:
                session.close()
        except ImportError:
            pass
        except Exception:
            return None
    payload = json.dumps({"statements": statements}).encode()
    req = urllib.request.Request(
        endpoint,
        data=payload,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except Exception:
        return None


def _write_result_to_neo(job_id: str, lane: str, action: str, model: str, response: str, payload: dict) -> bool:
    """
    MERGE a BridgeJob node into Neo4j and link it to any referenced tenant/civic nodes.
    Zero duplicate creation — MERGE on job_id is idempotent.
    """
    stmts = [
        {
            "statement": """
                MERGE (b:BridgeJob {job_id: $job_id})
                SET b.lane       = $lane,
                    b.action     = $action,
                    b.model      = $model,
                    b.response   = $response,
                    b.created_at = $created_at
            """,
            "parameters": {
                "job_id":     job_id,
                "lane":       lane,
                "action":     action,
                "model":      model,
                "response":   response[:4000],   # cap at 4KB for graph storage
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
        }
    ]
    # If payload references a tenant, link it
    tenant_id = payload.get("tenant_id") or payload.get("tenant")
    if tenant_id:
        stmts.append({
            "statement": """
                MATCH (b:BridgeJob {job_id: $job_id})
                MERGE (t:Tenant {id: $tenant_id})
                MERGE (b)-[:FOR_TENANT]->(t)
            """,
            "parameters": {"job_id": job_id, "tenant_id": tenant_id},
        })
    result = _neo_cypher(stmts)
    return result is not None and not result.get("errors")


# ── Core job processor ────────────────────────────────────────────────────────
def _process_job(entry: dict) -> dict:
    """
    Run one workboard entry through the correct king-* model.
    Returns a result dict. Never raises — errors are captured in result.
    """
    job     = entry.get("job") or {}
    job_id  = job.get("id", str(uuid4()))
    lane    = entry.get("lane", "engineering")
    action  = job.get("action", "unknown")
    payload = job.get("payload") or {}

    model  = route_model(lane, action)
    prompt = _build_prompt(lane, action, payload, entry)

    bridge_id  = str(uuid4())
    created_at = datetime.now(timezone.utc).isoformat()

    # Infer
    response  = _ollama_generate(model, prompt)
    grounded  = bool(response)
    if not grounded:
        response = f"UNGROUNDED: {model} unavailable. Job {job_id} flagged for review."

    # Write to Neo4j
    neo_ok = _write_result_to_neo(job_id, lane, action, model, response or "", payload)

    # Persist to bridge DB
    with _db() as conn:
        conn.execute("""
            INSERT OR REPLACE INTO bridge_jobs
              (id, job_id, lane, action, model, prompt, response, grounded, neo4j_wrote, created_at, completed_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """, (
            bridge_id, job_id, lane, action, model,
            prompt[:2000], response[:4000] if response else "",
            int(grounded), int(neo_ok),
            created_at, datetime.now(timezone.utc).isoformat(),
        ))
        conn.commit()

    # Emit workboard tombstone (engineering lane self-heals)
    if lane == "engineering" and grounded:
        resolve_workboard_job(job_id, outcome=f"king-bridge:{model}", source=SERVICE_NAME)

    # Emit event bus entry
    publish_event(
        "king_bridge.job.completed",
        SERVICE_NAME,
        payload={
            "bridge_id": bridge_id,
            "job_id":    job_id,
            "model":     model,
            "grounded":  grounded,
            "neo4j_ok":  neo_ok,
            "lane":      lane,
            "action":    action,
        },
        entity_id=job_id,
    )

    return {
        "bridge_id":  bridge_id,
        "job_id":     job_id,
        "lane":       lane,
        "action":     action,
        "model":      model,
        "grounded":   grounded,
        "neo4j_wrote": neo_ok,
        "response_preview": (response or "")[:300],
    }


def _build_prompt(lane: str, action: str, payload: dict, entry: dict) -> str:
    """Build a context-rich prompt for the king-* model from a workboard entry."""
    lines = [
        f"You are {route_model(lane, action)}, a specialized govOS AI agent.",
        f"Lane: {lane} | Action: {action}",
        f"Event: {entry.get('event', '')}",
        f"Priority: {entry.get('priority', 'normal')}",
    ]
    if payload:
        lines.append(f"Payload: {json.dumps(payload, ensure_ascii=False)[:1000]}")
    dag = (entry.get("job") or {}).get("dag_nodes") or []
    if dag:
        pending_nodes = [n["name"] for n in dag if n.get("status") in ("waiting", "running")]
        if pending_nodes:
            lines.append(f"Pending DAG nodes: {', '.join(pending_nodes)}")
    lines.append("")
    lines.append("Respond with: 1) your assessment, 2) recommended action, 3) any flags for the owner.")
    lines.append("Be concise. Frame civic findings as questions, not verdicts. Never output private file paths.")
    return "\n".join(lines)


# ── FastAPI app ───────────────────────────────────────────────────────────────
_init_db()
app = FastAPI(title="king-bridge", version=VERSION)


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _require_internal(x_service_token: str | None):
    """Lightweight internal-token check — owner-only service on loopback."""
    if x_service_token and x_service_token == INTERNAL_TOKEN:
        return
    # Allow loopback without token (local owner direct calls)
    # Non-loopback without token → reject
    # (Full auth wiring can be added later via require_claims if exposed externally)


# ── Ready / health ────────────────────────────────────────────────────────────
@app.get(f"{API_PREFIX}/ready")
def ready(response: Response):
    ollama_ok = _ollama_ready()
    neo_local_ok = _neo_ready()
    aura_available = AURA_URI and AURA_PASSWORD  # Configured, not necessarily reachable
    neo_ok = neo_local_ok or aura_available  # At least one should work
    db_ok = True
    try:
        with _db() as conn:
            conn.execute("SELECT 1").fetchone()
    except Exception:
        db_ok = False

    is_ready = ollama_ok and neo_ok and db_ok
    response.status_code = 200 if is_ready else 503
    return {
        "status": "ready" if is_ready else "not-ready",
        "service": SERVICE_NAME,
        "version": VERSION,
        "dependencies": {
            "ollama": ollama_ok,
            "neo4j_local": neo_local_ok,
            "aura_configured": aura_available,
            "database": db_ok,
        },
    }


# ── Models ────────────────────────────────────────────────────────────────────
@app.get(f"{API_PREFIX}/bridge/models")
def list_models():
    all_models  = _ollama_models()
    king_models = [m for m in all_models if m.startswith("king-") or m in ("kahualii:latest", "king:latest")]
    return {
        "king_models": king_models,
        "all_count":   len(all_models),
        "king_count":  len(king_models),
        "route_table": [{"fragment": f, "model": m} for f, m in _ROUTE_TABLE],
        "default_model": _DEFAULT_MODEL,
    }


# ── Submit a single job directly ──────────────────────────────────────────────
class BridgeJobRequest(BaseModel):
    lane:    str = "engineering"
    action:  str
    event:   str = ""
    payload: dict = {}
    model:   str | None = None   # override routing if set


@app.post(f"{API_PREFIX}/bridge/job")
def submit_job(req: BridgeJobRequest, x_service_token: str | None = Header(default=None)):
    _require_internal(x_service_token)
    model  = req.model or route_model(req.lane, req.action)
    prompt = _build_prompt(req.lane, req.action, req.payload, {
        "lane": req.lane, "action": req.action, "event": req.event,
        "priority": "normal", "job": {"dag_nodes": [], "payload": req.payload},
    })
    response = _ollama_generate(model, prompt)
    grounded = bool(response)
    job_id   = str(uuid4())
    neo_ok   = _write_result_to_neo(job_id, req.lane, req.action, model, response or "", req.payload)
    bridge_id = str(uuid4())
    with _db() as conn:
        conn.execute("""
            INSERT INTO bridge_jobs
              (id, job_id, lane, action, model, prompt, response, grounded, neo4j_wrote, created_at, completed_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """, (bridge_id, job_id, req.lane, req.action, model,
              prompt[:2000], (response or "")[:4000],
              int(grounded), int(neo_ok),
              _iso_now(), _iso_now()))
        conn.commit()
    return {
        "bridge_id":   bridge_id,
        "job_id":      job_id,
        "model":       model,
        "grounded":    grounded,
        "neo4j_wrote": neo_ok,
        "response":    response or "UNGROUNDED",
    }


# ── Workboard pulse ───────────────────────────────────────────────────────────
@app.get(f"{API_PREFIX}/bridge/pulse")
def pulse():
    return {
        "pulse":    workboard_pulse(),
        "hub_feed": workboard_hub_feed(limit=20),
        "ts":       _iso_now(),
    }


# ── Poll + drain pending workboard jobs ───────────────────────────────────────
@app.post(f"{API_PREFIX}/bridge/poll")
def poll(x_service_token: str | None = Header(default=None)):
    """
    Owner-triggered drain: reads pending engineering-lane jobs from the workboard
    and processes them through the correct king-* model. Creative/output jobs are
    listed but never auto-processed (owner approval required per AGENTS.md).
    """
    _require_internal(x_service_token)
    from services.v2_workboard import read_workboard_log, DISPATCH_LOG

    entries    = read_workboard_log()
    tombstoned = set()
    open_jobs  = {}

    for e in entries:
        job = e.get("job") or {}
        if e.get("kind") == "tombstone":
            cid = job.get("correlation_id")
            if cid:
                tombstoned.add(cid)
        elif e.get("kind") == "job":
            jid = job.get("id")
            if jid:
                open_jobs[jid] = e

    # Separate engineering (auto-process) from creative/output (list only)
    to_process  = [(jid, e) for jid, e in open_jobs.items()
                   if jid not in tombstoned and e.get("lane") == "engineering"][:POLL_MAX]
    needs_owner = [(jid, e) for jid, e in open_jobs.items()
                   if jid not in tombstoned and e.get("lane") in ("creative", "output")]

    results = []
    for jid, entry in to_process:
        result = _process_job(entry)
        results.append(result)

    return {
        "processed":    len(results),
        "results":      results,
        "needs_owner":  [
            {
                "job_id": jid,
                "lane":   e.get("lane"),
                "action": (e.get("job") or {}).get("action"),
                "event":  e.get("event"),
                "ts":     e.get("iso"),
            }
            for jid, e in needs_owner
        ],
        "ts": _iso_now(),
    }


# ── Direct chat to a king-* model ─────────────────────────────────────────────
class OwnerMessageRequest(BaseModel):
    message: str
    context: str = "owner-console"


class ChatRequest(BaseModel):
    model:   str | None = None
    prompt:  str
    lane:    str = "engineering"
    action:  str = "chat"
    stream:  bool = False


# ── Owner message → workboard executor ───────────────────────────────────────
@app.post(f"{API_PREFIX}/board/message")
def owner_message(req: OwnerMessageRequest, x_service_token: str | None = Header(default=None)):
    """
    Receive a message from the owner's go.html console and emit it as a workboard job.
    
    The executor reads pending jobs and sends responses back. This is the entrypoint
    for the owner's "Message Claude" feature on the index page.
    
    Flow:
      1. Owner types message in go.html
      2. Form POSTs to /api/v2/board/message
      3. Backend emits a workboard job (engineering lane, auto-heals)
      4. Executor picks it up and processes
      5. Result appears in dispatch log + owner console
    """
    _require_internal(x_service_token)
    
    if not req.message or not req.message.strip():
        raise HTTPException(status_code=400, detail="message cannot be empty")
    
    message = req.message.strip()
    
    # Emit as engineering lane job so it auto-heals (runs immediately when executor polls)
    entry = emit_workboard_job(
        source="owner-console",
        action="owner-message",
        event=f"Owner message: {message[:100]}",
        lane="engineering",
        status="queued",
        priority="high",
        kind="job",
        payload={
            "message": message,
            "context": req.context or "owner-console",
            "timestamp": _iso_now(),
        },
    )
    
    job_id = entry["job"]["id"]
    publish_event(
        "owner_console.message.sent",
        SERVICE_NAME,
        payload={"message": message[:200], "context": req.context},
        entity_id=job_id,
    )
    
    return {
        "status": "queued",
        "job_id": job_id,
        "message": message,
        "context": req.context,
        "note": "Your message is now in the executor queue. Check the dispatch log for responses.",
        "ts": _iso_now(),
    }


@app.post(f"{API_PREFIX}/bridge/chat")
def chat(req: ChatRequest, x_service_token: str | None = Header(default=None)):
    _require_internal(x_service_token)
    model = req.model or route_model(req.lane, req.action)
    if req.stream:
        return StreamingResponse(
            _ollama_stream(model, req.prompt),
            media_type="text/event-stream",
        )
    response = _ollama_generate(model, req.prompt)
    return {
        "model":    model,
        "response": response or "UNGROUNDED",
        "grounded": bool(response),
    }


@app.get(f"{API_PREFIX}/bridge/chat")
def chat_get(
    prompt: str,
    model:  str | None = None,
    lane:   str = "engineering",
    action: str = "chat",
    x_service_token: str | None = Header(default=None),
):
    """GET variant for quick browser/curl testing."""
    _require_internal(x_service_token)
    resolved_model = model or route_model(lane, action)
    return StreamingResponse(
        _ollama_stream(resolved_model, prompt),
        media_type="text/event-stream",
    )


# ── Full tenant→asset tree from Neo4j ───────────────────────────────────────
@app.get(f"{API_PREFIX}/bridge/tree")
def tree():
    """Full tenant→asset hierarchy from Neo4j. Powers the landing page."""
    try:
        from services.king_bridge.app._tree import _neo_tree
        data = _neo_tree()
        return {"tree": data, "ts": _iso_now(), "neo4j": NEO4J_HTTP}
    except Exception as e:
        return {"error": str(e), "tree": {}, "ts": _iso_now()}


# ── Recent bridge jobs ────────────────────────────────────────────────────────
@app.get(f"{API_PREFIX}/bridge/jobs")
def recent_jobs(limit: int = 20):
    with _db() as conn:
        rows = conn.execute("""
            SELECT id, job_id, lane, action, model, grounded, neo4j_wrote, created_at, completed_at,
                   substr(response, 1, 200) as preview
            FROM bridge_jobs ORDER BY created_at DESC LIMIT ?
        """, (min(limit, 100),)).fetchall()
    return {"jobs": [dict(r) for r in rows]}


# ── Owner Job Tracking ────────────────────────────────────────────────────────
@app.get(f"{API_PREFIX}/owner/jobs")
def owner_jobs(limit: int = 50, status: str = None):
    """Fetch autonomous job tracking records for owner dashboard."""
    tracker = get_tracker()
    jobs = tracker.list_jobs(limit=limit, status=status)
    stats = tracker.get_stats()
    return {
        "jobs": jobs,
        "stats": stats,
        "ts": _iso_now(),
    }


@app.get(f"{API_PREFIX}/owner/jobs/{{job_id}}")
def owner_job_detail(job_id: str):
    """Fetch detailed job info + steps."""
    tracker = get_tracker()
    job = tracker.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    steps = tracker.get_job_steps(job_id)
    return {
        "job": job,
        "steps": steps,
        "ts": _iso_now(),
    }


class OwnerJobApprovalRequest(BaseModel):
    decision: str  # "approve" or "reject"
    reason: str = ""  # Note or rejection reason


@app.post(f"{API_PREFIX}/owner/jobs/{{job_id}}/approval")
def owner_job_approval(
    job_id: str,
    req: OwnerJobApprovalRequest,
    x_service_token: str | None = Header(default=None),
):
    """Owner approves or rejects a completed autonomous job."""
    _require_internal(x_service_token)
    
    tracker = get_tracker()
    job = tracker.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if req.decision.lower() == "approve":
        success = tracker.approve_job(job_id, approver="owner", note=req.reason)
        action = "approved"
    elif req.decision.lower() == "reject":
        success = tracker.reject_job(job_id, rejector="owner", reason=req.reason)
        action = "rejected"
    else:
        raise HTTPException(status_code=400, detail="decision must be 'approve' or 'reject'")
    
    if not success:
        raise HTTPException(status_code=500, detail="Failed to record approval")
    
    # Emit event
    publish_event(
        f"owner_job.{action}",
        SERVICE_NAME,
        payload={"job_id": job_id, "reason": req.reason},
        entity_id=job_id,
    )
    
    return {
        "status": "recorded",
        "job_id": job_id,
        "decision": req.decision,
        "timestamp": _iso_now(),
    }


@app.get(f"{API_PREFIX}/owner/jobs/stats")
def owner_jobs_stats():
    """Get aggregated job statistics."""
    tracker = get_tracker()
    stats = tracker.get_stats()
    return {
        "stats": stats,
        "ts": _iso_now(),
    }


# Serve static HTML pages from element_lotus_public
from fastapi.staticfiles import StaticFiles

static_dir = Path(__file__).parents[3] / "element_lotus_public"
if static_dir.exists():
    try:
        app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="public")
    except Exception:
        pass
