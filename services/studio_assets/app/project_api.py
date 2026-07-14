"""services/studio_assets/app/project_api.py — studio project management REST API.

Mounted into the studio-assets FastAPI app at /api/v2/projects/*.
Provides: add, reset, restart, status, list — mirroring tools/studio_project.py
but callable over HTTP from gordon.html, the go console, or any internal service.

All mutations emit workboard jobs (append-only, auditable).
Registry file (tenant_registry.json) is mounted read-only in the container, so
add/reset/restart that mutate the registry call back to king-bridge or write
directly if the REGISTRY_PATH env points to a writable location.

Security: loopback + Tailscale trust boundary. No external auth required on 8108.
"""
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

# ── Repo imports ──────────────────────────────────────────────────────────────
_HERE = Path(__file__).resolve()
_REPO = _HERE.parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

try:
    from services.v2_workboard import (
        emit_workboard_job,
        read_workboard_log,
        resolve_workboard_job,
    )
    _WB_AVAILABLE = True
except Exception:
    _WB_AVAILABLE = False

# ── Config ────────────────────────────────────────────────────────────────────
REGISTRY_PATH = Path(os.environ.get("STUDIO_REGISTRY_PATH", str(_REPO / "tenant_registry.json")))
NEO4J_HTTP    = os.environ.get("NEO4J_HTTP", "http://host.docker.internal:7474/db/neo4j/tx/commit")
AUTH_URL      = os.environ.get("AUTH_SESSION_URL", "http://host.docker.internal:8101/api/v2/auth/session")
AUTH_READY    = os.environ.get("AUTH_READY_URL",   "http://host.docker.internal:8101/api/v2/ready")
TIMEOUT       = int(os.environ.get("DEPENDENCY_TIMEOUT_SECONDS", "5"))

VALID_KINDS    = {"film","game","music_video","short","series","documentary","other"}
VALID_RENDERS  = {"photoreal","cartoon-3d","animated","live-action","mixed","other"}
VALID_STATUSES = {
    "in_production","script_partial","script_rebuilt","trailer_only",
    "greenlit_treatment","rd_private","forming","proposed_internal",
    "blessing_gated_preproduction","designed_producible_now","released","archived",
}
_ROLE_MAP = {
    "in_production": "Partner", "script_rebuilt": "Partner", "trailer_only": "Partner",
    "designed_producible_now": "Partner", "released": "Partner",
    "script_partial": "Resident", "greenlit_treatment": "Resident", "rd_private": "Resident",
    "forming": "Resident", "proposed_internal": "Resident",
    "blessing_gated_preproduction": "Resident",
}

router = APIRouter(prefix="/api/v2/projects", tags=["studio-projects"])


# ── Pydantic models ───────────────────────────────────────────────────────────

class AddProjectRequest(BaseModel):
    id:     str
    name:   str
    kind:   str = "film"
    render: str = "photoreal"
    status: str = "proposed_internal"
    note:   Optional[str] = None


class ResetRequest(BaseModel):
    id:  str
    note: Optional[str] = None


class RestartRequest(BaseModel):
    id:     str
    status: Optional[str] = None
    note:   Optional[str] = None


# ── Helpers ───────────────────────────────────────────────────────────────────

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_registry() -> dict:
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


def _save_registry(reg: dict) -> None:
    REGISTRY_PATH.write_text(
        json.dumps(reg, indent=1, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def _emit(source: str, action: str, event: str, lane: str, status: str, payload: dict) -> str:
    if not _WB_AVAILABLE:
        return ""
    entry = emit_workboard_job(
        source=source, action=action, event=event,
        lane=lane, status=status, payload=payload,
    )
    return (entry.get("job") or {}).get("id", "")


def _neo(stmt: str, params: dict | None = None) -> bool:
    body = json.dumps({"statements": [{"statement": stmt, "parameters": params or {}}]}).encode()
    req = urllib.request.Request(
        NEO4J_HTTP, data=body,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return not json.loads(r.read()).get("errors")
    except Exception:
        return False


def _neo_merge(tenant: dict) -> bool:
    return _neo(
        "MERGE (p:StudioProject {id:$id}) SET p.name=$name, p.kind=$kind, "
        "p.render_register=$render, p.status=$status, p.updated_at=$ts",
        {"id": tenant["id"], "name": tenant["name"], "kind": tenant.get("kind",""),
         "render": tenant.get("render_register",""), "status": tenant.get("status",""),
         "ts": _now()},
    )


def _neo_clear(tenant_id: str) -> bool:
    return _neo(
        "MATCH (n:StoryboardNode {project_id:$id}) DETACH DELETE n",
        {"id": tenant_id},
    )


def _auth_verify(tenant_id: str, role: str) -> bool:
    scopes = (
        ["tenant:read","documents:read","documents:write","storage:read","storage:write","ai:assist","gpu:infer"]
        if role == "Partner" else
        ["tenant:read","documents:read","storage:read","ai:assist","gpu:infer"]
    )
    body = json.dumps({
        "provider":"magic_link","subject":f"seed:{tenant_id}",
        "email":"seed@king-server.internal","tenant_id":tenant_id,
        "role":role,"scopes":scopes,"expires_in":300,
    }).encode()
    req = urllib.request.Request(AUTH_URL, data=body,
                                  headers={"Content-Type":"application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return bool(json.loads(r.read()).get("access_token"))
    except Exception:
        return False


def _open_jobs(tenant_id: str) -> list[str]:
    """Return IDs of open (non-tombstoned) workboard jobs for this tenant."""
    if not _WB_AVAILABLE:
        return []
    entries   = read_workboard_log()
    tombstoned = set()
    open_ids   = []
    for e in entries:
        job = e.get("job") or {}
        if e.get("kind") == "tombstone":
            cid = job.get("correlation_id")
            if cid:
                tombstoned.add(cid)
        elif e.get("kind") == "job":
            if (job.get("payload") or {}).get("tenant_id") == tenant_id:
                jid = job.get("id")
                if jid:
                    open_ids.append(jid)
    return [jid for jid in open_ids if jid not in tombstoned]


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("")
def list_projects(kind: str = ""):
    """List all studio projects from tenant_registry.json."""
    reg = _load_registry()
    tenants = reg.get("creative_tenants", [])
    if kind:
        tenants = [t for t in tenants if t.get("kind") == kind]
    return {"projects": tenants, "count": len(tenants)}


@router.get("/{tenant_id}")
def get_project(tenant_id: str):
    """Get a single studio project."""
    reg = _load_registry()
    tenant = next((t for t in reg.get("creative_tenants", []) if t["id"] == tenant_id), None)
    if not tenant:
        raise HTTPException(status_code=404, detail={"error": f"project '{tenant_id}' not found"})
    open_jobs = _open_jobs(tenant_id)
    return {**tenant, "open_job_count": len(open_jobs), "open_job_ids": open_jobs}


@router.post("", status_code=201)
def add_project(req: AddProjectRequest):
    """Add a new studio project to the registry."""
    tid = req.id.strip().replace(" ", "_").lower()
    if not tid:
        raise HTTPException(status_code=400, detail={"error": "id is required"})

    reg = _load_registry()
    if any(t["id"] == tid for t in reg.get("creative_tenants", [])):
        raise HTTPException(status_code=409, detail={"error": f"tenant_id '{tid}' already exists"})

    kind   = req.kind.strip().lower()
    render = req.render.strip().lower()
    status = req.status.strip().lower()

    if kind not in VALID_KINDS:
        raise HTTPException(status_code=400, detail={"error": f"kind must be one of {sorted(VALID_KINDS)}"})
    if render not in VALID_RENDERS:
        raise HTTPException(status_code=400, detail={"error": f"render must be one of {sorted(VALID_RENDERS)}"})

    role = _ROLE_MAP.get(status, "Resident")
    tenant = {
        "id": tid, "name": req.name or tid, "kind": kind,
        "quadrant": kind, "render_register": render,
        "status": status, "_added_at": _now(),
    }

    reg["creative_tenants"].append(tenant)
    reg["counts"]["creative"] = len(reg["creative_tenants"])
    _save_registry(reg)

    neo_ok   = _neo_merge(tenant)
    verified = _auth_verify(tid, role)

    job_id = _emit(
        "studio-assets-api", "studio.project.added",
        f"STUDIO PROJECT ADDED: {tid} ({tenant['name']}) kind={kind} status={status}",
        "engineering", "done",
        {"tenant_id": tid, "name": tenant["name"], "kind": kind,
         "render_register": render, "status": status, "role": role,
         "auth_verified": verified, "neo4j_ok": neo_ok,
         "note": req.note or "", "added_at": _now()},
    )

    return {
        "tenant_id": tid, "name": tenant["name"], "kind": kind,
        "render_register": render, "status": status, "role": role,
        "auth_verified": verified, "neo4j_merged": neo_ok,
        "workboard_job_id": job_id,
    }


@router.post("/{tenant_id}/reset")
def reset_project(tenant_id: str, req: ResetRequest):
    """Reset a project's storyboard — clears neo4j storyboard nodes + tombstones open jobs."""
    reg = _load_registry()
    tenant = next((t for t in reg.get("creative_tenants", []) if t["id"] == tenant_id), None)
    if not tenant:
        raise HTTPException(status_code=404, detail={"error": f"project '{tenant_id}' not found"})

    neo_ok   = _neo_clear(tenant_id)
    open_ids = _open_jobs(tenant_id)

    if _WB_AVAILABLE:
        for jid in open_ids:
            resolve_workboard_job(jid, outcome=f"reset:{tenant_id}", source="studio-assets-api")

    job_id = _emit(
        "studio-assets-api", "studio.project.reset",
        f"STUDIO STORYBOARD RESET: {tenant_id} ({tenant['name']}) — {len(open_ids)} job(s) tombstoned",
        "engineering", "done",
        {"tenant_id": tenant_id, "name": tenant["name"],
         "jobs_tombstoned": len(open_ids), "neo4j_cleared": neo_ok,
         "note": req.note or "", "reset_at": _now()},
    )

    return {
        "tenant_id": tenant_id, "neo4j_cleared": neo_ok,
        "jobs_tombstoned": len(open_ids), "workboard_job_id": job_id,
    }


@router.post("/{tenant_id}/restart")
def restart_project(tenant_id: str, req: RestartRequest):
    """Full restart — reset storyboard + optional status update + re-seed auth + creative lane job."""
    reg = _load_registry()
    tenants = reg.get("creative_tenants", [])
    idx = next((i for i, t in enumerate(tenants) if t["id"] == tenant_id), None)
    if idx is None:
        raise HTTPException(status_code=404, detail={"error": f"project '{tenant_id}' not found"})

    tenant = dict(tenants[idx])
    new_status = (req.status or "").strip() or tenant.get("status", "in_production")

    if new_status != tenant.get("status"):
        tenants[idx]["status"] = new_status
        reg["creative_tenants"] = tenants
        _save_registry(reg)
        tenant["status"] = new_status

    role     = _ROLE_MAP.get(new_status, "Resident")
    neo_ok   = _neo_clear(tenant_id)
    open_ids = _open_jobs(tenant_id)

    if _WB_AVAILABLE:
        for jid in open_ids:
            resolve_workboard_job(jid, outcome=f"restart:{tenant_id}", source="studio-assets-api")

    _neo_merge(tenant)
    verified = _auth_verify(tenant_id, role)

    job_id = _emit(
        "studio-assets-api", "studio.project.restart",
        f"STUDIO PROJECT RESTART: {tenant_id} ({tenant['name']}) — full start-over queued",
        "creative", "queued",
        {"tenant_id": tenant_id, "name": tenant["name"],
         "kind": tenant.get("kind"), "render_register": tenant.get("render_register"),
         "status": new_status, "role": role,
         "jobs_tombstoned": len(open_ids), "neo4j_cleared": neo_ok,
         "auth_verified": verified, "note": req.note or "Full project restart.",
         "restart_at": _now()},
    )

    return {
        "tenant_id": tenant_id, "status": new_status, "role": role,
        "neo4j_cleared": neo_ok, "jobs_tombstoned": len(open_ids),
        "auth_verified": verified, "workboard_job_id": job_id,
        "note": "Creative lane job queued — approve to begin production.",
    }
