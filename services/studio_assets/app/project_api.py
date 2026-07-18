"""services/studio_assets/app/project_api.py — studio project management REST API.

Mounted into the studio-assets FastAPI app at /api/v2/projects/*.
Provides: add, reset, restart, status, list — mirroring tools/studio_project.py
but callable over HTTP from gordon.html, the go console, or any internal service.

All mutations emit workboard jobs (append-only, auditable). The canonical
tenant_registry.json stays read-only in the container. Mutations persist to an
app-owned registry overlay and merge with the canonical source on every read.

Security: reads stay on the loopback/Tailscale boundary; every mutation requires an
owner bearer token with the ``ops:owner`` scope when Studio auth is enabled.
"""
import json
import os
import re
import sys
import tempfile
import threading
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from services.studio_assets.app.security import require_studio_owner

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
REGISTRY_SOURCE_PATH = Path(
    os.environ.get("STUDIO_REGISTRY_SOURCE_PATH", str(_REPO / "tenant_registry.json"))
)
REGISTRY_PATH = Path(os.environ.get("STUDIO_REGISTRY_PATH", str(REGISTRY_SOURCE_PATH)))
NEO4J_HTTP    = os.environ.get("NEO4J_HTTP", "http://host.docker.internal:7474/db/neo4j/tx/commit")
AUTH_URL      = os.environ.get("AUTH_SESSION_URL", "http://host.docker.internal:8101/api/v2/auth/session")
AUTH_READY    = os.environ.get("AUTH_READY_URL",   "http://host.docker.internal:8101/api/v2/ready")
INTERNAL_SERVICE_TOKEN = os.environ.get("INTERNAL_SERVICE_TOKEN", "")
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
_TENANT_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
_REGISTRY_LOCK = threading.RLock()

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


def _read_registry(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("creative_tenants", []), list):
        raise ValueError(f"invalid Studio registry: {path}")
    return data


def _merge_registry(source: dict, local: dict) -> dict:
    """Merge Studio-owned additions/status changes over the regenerated source registry."""
    merged = dict(source)
    source_rows = [dict(row) for row in source.get("creative_tenants", [])]
    source_by_id = {row.get("id"): row for row in source_rows if row.get("id")}
    for local_row in local.get("creative_tenants", []):
        tenant_id = local_row.get("id")
        if not tenant_id:
            continue
        if tenant_id not in source_by_id:
            row = dict(local_row)
            source_rows.append(row)
            source_by_id[tenant_id] = row
        elif local_row.get("_studio_status_updated_at"):
            source_by_id[tenant_id]["status"] = local_row.get(
                "status", source_by_id[tenant_id].get("status")
            )
            source_by_id[tenant_id]["_studio_status_updated_at"] = local_row[
                "_studio_status_updated_at"
            ]
    merged["creative_tenants"] = source_rows
    counts = dict(merged.get("counts") or {})
    counts["creative"] = len(source_rows)
    merged["counts"] = counts
    return merged


def _load_registry() -> dict:
    with _REGISTRY_LOCK:
        source = _read_registry(REGISTRY_SOURCE_PATH)
        if REGISTRY_PATH == REGISTRY_SOURCE_PATH or not REGISTRY_PATH.exists():
            return source
        return _merge_registry(source, _read_registry(REGISTRY_PATH))


def _save_registry(reg: dict) -> None:
    if REGISTRY_PATH == REGISTRY_SOURCE_PATH:
        raise RuntimeError("Studio registry mutations require a writable overlay path")
    REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    handle, temp_name = tempfile.mkstemp(
        prefix=f".{REGISTRY_PATH.name}.", dir=REGISTRY_PATH.parent, text=True
    )
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(reg, stream, indent=1, ensure_ascii=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_name, REGISTRY_PATH)
    except Exception:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise


def _normalise_tenant_id(value: str) -> str:
    tenant_id = (value or "").strip().replace(" ", "_").lower()
    if not _TENANT_ID_PATTERN.fullmatch(tenant_id):
        raise HTTPException(
            status_code=400,
            detail={"error": "id must be 1-64 lowercase letters, digits, underscores, or hyphens"},
        )
    return tenant_id


def _normalise_status(value: str) -> str:
    status = (value or "").strip().lower()
    if status not in VALID_STATUSES:
        raise HTTPException(
            status_code=400,
            detail={"error": f"status must be one of {sorted(VALID_STATUSES)}"},
        )
    return status


def _require_matching_id(body_id: str, tenant_id: str) -> None:
    if _normalise_tenant_id(body_id) != tenant_id:
        raise HTTPException(status_code=400, detail={"error": "body id must match path tenant_id"})


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
    req = urllib.request.Request(
        AUTH_URL,
        data=body,
        headers={
            "Content-Type": "application/json",
            "X-Service-Token": INTERNAL_SERVICE_TOKEN,
        },
        method="POST",
    )
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


@router.post("", status_code=201, dependencies=[Depends(require_studio_owner)])
def add_project(req: AddProjectRequest):
    """Add a new studio project to the registry."""
    tid = _normalise_tenant_id(req.id)

    kind   = req.kind.strip().lower()
    render = req.render.strip().lower()
    status = _normalise_status(req.status)

    if kind not in VALID_KINDS:
        raise HTTPException(status_code=400, detail={"error": f"kind must be one of {sorted(VALID_KINDS)}"})
    if render not in VALID_RENDERS:
        raise HTTPException(status_code=400, detail={"error": f"render must be one of {sorted(VALID_RENDERS)}"})

    name = (req.name or "").strip()
    if not name or len(name) > 160:
        raise HTTPException(status_code=400, detail={"error": "name must be 1-160 characters"})

    role = _ROLE_MAP.get(status, "Resident")
    tenant = {
        "id": tid, "name": name, "kind": kind,
        "quadrant": kind, "render_register": render,
        "status": status, "_added_at": _now(),
    }

    with _REGISTRY_LOCK:
        reg = _load_registry()
        if any(t["id"] == tid for t in reg.get("creative_tenants", [])):
            raise HTTPException(status_code=409, detail={"error": f"tenant_id '{tid}' already exists"})
        reg.setdefault("creative_tenants", []).append(tenant)
        reg.setdefault("counts", {})["creative"] = len(reg["creative_tenants"])
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


@router.post("/{tenant_id}/reset", dependencies=[Depends(require_studio_owner)])
def reset_project(tenant_id: str, req: ResetRequest):
    """Reset a project's storyboard — clears neo4j storyboard nodes + tombstones open jobs."""
    tenant_id = _normalise_tenant_id(tenant_id)
    _require_matching_id(req.id, tenant_id)
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


@router.post("/{tenant_id}/restart", dependencies=[Depends(require_studio_owner)])
def restart_project(tenant_id: str, req: RestartRequest):
    """Full restart — reset storyboard + optional status update + re-seed auth + creative lane job."""
    tenant_id = _normalise_tenant_id(tenant_id)
    _require_matching_id(req.id, tenant_id)
    with _REGISTRY_LOCK:
        reg = _load_registry()
        tenants = reg.get("creative_tenants", [])
        idx = next((i for i, t in enumerate(tenants) if t["id"] == tenant_id), None)
        if idx is None:
            raise HTTPException(status_code=404, detail={"error": f"project '{tenant_id}' not found"})

        tenant = dict(tenants[idx])
        new_status = _normalise_status(req.status or tenant.get("status", "in_production"))

        if new_status != tenant.get("status"):
            updated_at = _now()
            tenants[idx]["status"] = new_status
            tenants[idx]["_studio_status_updated_at"] = updated_at
            reg["creative_tenants"] = tenants
            _save_registry(reg)
            tenant["status"] = new_status
            tenant["_studio_status_updated_at"] = updated_at

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
