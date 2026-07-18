#!/usr/bin/env python3
"""tools/studio_project.py — studio project lifecycle management CLI.

Commands
--------
  add        Add a new studio project to tenant_registry.json + seed auth + emit workboard job
  reset      Reset a project's storyboard/DAG/dispatch state (keeps registry entry, wipes jobs)
  restart    Full project restart — reset storyboard + clear neo4j node + re-seed + re-queue
  status     Show current state of one or all studio projects
  list       List all studio projects

Canon (JRCSL): Christ aloha engineering — preserve intention, protect private, report clearly.
  - add/reset/restart all emit workboard jobs so the log is always auditable
  - reset/restart never delete registry entries — they are append-only decisions
  - private content stays private; the registry entry is the only public-safe record

Usage
-----
  python tools/studio_project.py add --id film_new --name "New Film" --kind film --render photoreal
  python tools/studio_project.py reset --id film_12stones
  python tools/studio_project.py restart --id film_12stones
  python tools/studio_project.py status --id film_12stones
  python tools/studio_project.py list
  python tools/studio_project.py list --kind film
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from services.v2_workboard import emit_workboard_job, read_workboard_log

# ── Config ────────────────────────────────────────────────────────────────────
REGISTRY_PATH   = _REPO / "tenant_registry.json"
AUTH_URL        = "http://localhost:8101/api/v2/auth/session"
AUTH_READY_URL  = "http://localhost:8101/api/v2/ready"
NEO4J_HTTP      = "http://localhost:7474/db/neo4j/tx/commit"
STUDIO_ASSETS   = "http://localhost:8108/api/v2"
INTERNAL_SERVICE_TOKEN = os.environ.get("INTERNAL_SERVICE_TOKEN", "")
TIMEOUT         = 5

VALID_KINDS         = {"film", "game", "music_video", "short", "series", "documentary", "other"}
VALID_RENDERS       = {"photoreal", "cartoon-3d", "animated", "live-action", "mixed", "other"}
VALID_STATUSES      = {
    "in_production", "script_partial", "script_rebuilt", "trailer_only",
    "greenlit_treatment", "rd_private", "forming", "proposed_internal",
    "blessing_gated_preproduction", "designed_producible_now", "released", "archived",
}
DEFAULT_ROLE_MAP    = {
    "in_production": "Partner", "script_rebuilt": "Partner", "trailer_only": "Partner",
    "designed_producible_now": "Partner", "released": "Partner",
    "script_partial": "Resident", "greenlit_treatment": "Resident", "rd_private": "Resident",
    "forming": "Resident", "proposed_internal": "Resident",
    "blessing_gated_preproduction": "Resident",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_registry() -> dict:
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


def _save_registry(reg: dict) -> None:
    REGISTRY_PATH.write_text(
        json.dumps(reg, indent=1, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _auth_ready() -> bool:
    try:
        with urllib.request.urlopen(AUTH_READY_URL, timeout=TIMEOUT) as r:
            d = json.loads(r.read())
            return d.get("status") in ("ready", "healthy")
    except Exception:
        return False


def _issue_token(tenant_id: str, role: str) -> bool:
    scopes = (
        ["tenant:read","documents:read","documents:write","storage:read","storage:write","ai:assist","gpu:infer"]
        if role == "Partner" else
        ["tenant:read","documents:read","storage:read","ai:assist","gpu:infer"]
    )
    body = json.dumps({
        "provider": "magic_link", "subject": f"seed:{tenant_id}",
        "email": "seed@king-server.internal", "tenant_id": tenant_id,
        "role": role, "scopes": scopes, "expires_in": 300,
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


def _neo_cypher(stmt: str, params: dict | None = None) -> bool:
    body = json.dumps({"statements": [{"statement": stmt, "parameters": params or {}}]}).encode()
    req = urllib.request.Request(
        NEO4J_HTTP, data=body,
        headers={"Content-Type": "application/json", "Accept": "application/json"}, method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            d = json.loads(r.read())
            return not d.get("errors")
    except Exception:
        return False


def _neo_merge_project(tenant: dict) -> bool:
    return _neo_cypher(
        """
        MERGE (p:StudioProject {id: $id})
        SET p.name            = $name,
            p.kind            = $kind,
            p.render_register = $render,
            p.status          = $status,
            p.quadrant        = $quadrant,
            p.updated_at      = $updated_at
        """,
        {
            "id": tenant["id"], "name": tenant["name"], "kind": tenant["kind"],
            "render": tenant.get("render_register", "other"),
            "status": tenant.get("status", "proposed_internal"),
            "quadrant": tenant.get("quadrant", "film"),
            "updated_at": _now(),
        },
    )


def _neo_clear_storyboard(tenant_id: str) -> bool:
    """Delete all StoryboardNode and StoryboardEdge nodes for a project."""
    ok1 = _neo_cypher(
        "MATCH (n:StoryboardNode {project_id: $id}) DETACH DELETE n",
        {"id": tenant_id},
    )
    ok2 = _neo_cypher(
        "MATCH (n:BridgeJob {job_id: $id}) DETACH DELETE n",
        {"id": tenant_id},
    )
    return ok1


def _reindex_studio_assets() -> bool:
    """Tell studio-assets service to re-ingest its catalog."""
    req = urllib.request.Request(
        f"{STUDIO_ASSETS}/reindex", data=b"", method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status == 200
    except Exception:
        return False


def _open_jobs_for(tenant_id: str) -> list[dict]:
    """Return open (non-tombstoned) workboard jobs for this tenant_id."""
    entries = read_workboard_log()
    tombstoned = set()
    open_jobs = []
    for e in entries:
        job = e.get("job") or {}
        if e.get("kind") == "tombstone":
            cid = job.get("correlation_id")
            if cid:
                tombstoned.add(cid)
        elif e.get("kind") == "job":
            payload = job.get("payload") or {}
            if payload.get("tenant_id") == tenant_id:
                open_jobs.append(e)
    return [e for e in open_jobs if (e.get("job") or {}).get("id") not in tombstoned]


# ── Commands ──────────────────────────────────────────────────────────────────

def cmd_add(args) -> int:
    """Add a new studio project."""
    tid = args.id.strip().replace(" ", "_").lower()
    if not tid:
        print("ERROR: --id is required", file=sys.stderr)
        return 1

    reg = _load_registry()
    existing_ids = {t["id"] for t in reg.get("creative_tenants", [])}
    if tid in existing_ids:
        print(f"ERROR: tenant_id '{tid}' already exists. Use --id with a unique name.", file=sys.stderr)
        return 1

    kind   = (args.kind   or "film").strip().lower()
    render = (args.render or "photoreal").strip().lower()
    status = (args.status or "proposed_internal").strip().lower()

    if kind not in VALID_KINDS:
        print(f"ERROR: --kind must be one of: {sorted(VALID_KINDS)}", file=sys.stderr)
        return 1
    if render not in VALID_RENDERS:
        print(f"ERROR: --render must be one of: {sorted(VALID_RENDERS)}", file=sys.stderr)
        return 1
    if status not in VALID_STATUSES:
        print(f"WARN: --status '{status}' is not in the standard set — adding anyway.", file=sys.stderr)

    quadrant = kind  # game → game, film → film, music_video → music_video
    role = DEFAULT_ROLE_MAP.get(status, "Resident")

    tenant = {
        "id":              tid,
        "name":            args.name or tid,
        "kind":            kind,
        "quadrant":        quadrant,
        "render_register": render,
        "status":          status,
        "_added_at":       _now(),
    }

    print(f"\n── ADD STUDIO PROJECT ──────────────────────────────")
    print(f"  id      : {tid}")
    print(f"  name    : {tenant['name']}")
    print(f"  kind    : {kind}  render={render}  status={status}")
    print(f"  role    : {role}")

    # 1. Registry
    reg["creative_tenants"].append(tenant)
    reg["counts"]["creative"] = len(reg["creative_tenants"])
    _save_registry(reg)
    print(f"  ✓ registry updated ({len(reg['creative_tenants'])} creative tenants)")

    # 2. Auth verification token
    auth_ok = _auth_ready()
    verified = _issue_token(tid, role) if auth_ok else False
    print(f"  {'✓' if verified else '~'} auth {'verified' if verified else 'offline — skipped'}")

    # 3. Neo4j node
    neo_ok = _neo_merge_project(tenant)
    print(f"  {'✓' if neo_ok else '~'} neo4j {'node merged' if neo_ok else 'offline — skipped'}")

    # 4. Workboard
    emit_workboard_job(
        source="studio-project-add",
        action="studio.project.added",
        event=f"STUDIO PROJECT ADDED: {tid} ({tenant['name']}) kind={kind} status={status}",
        lane="engineering",
        status="done",
        payload={
            "tenant_id": tid, "name": tenant["name"], "kind": kind,
            "render_register": render, "status": status, "role": role,
            "auth_verified": verified, "neo4j_ok": neo_ok, "added_at": _now(),
        },
    )
    print(f"  ✓ workboard job emitted")

    # 5. Studio-assets reindex
    sa_ok = _reindex_studio_assets()
    print(f"  {'✓' if sa_ok else '~'} studio-assets {'reindexed' if sa_ok else 'offline — skipped'}")

    print(f"\n✓ Project '{tid}' added. Run seed to verify auth:")
    print(f"  python tools/seed_studio_tenants.py --apply")
    return 0


def cmd_reset(args) -> int:
    """Reset a project's storyboard and open workboard jobs — keeps registry entry."""
    tid = (args.id or "").strip()
    if not tid:
        print("ERROR: --id required", file=sys.stderr)
        return 1

    reg = _load_registry()
    tenant = next((t for t in reg.get("creative_tenants", []) if t["id"] == tid), None)
    if not tenant:
        print(f"ERROR: '{tid}' not found in registry.", file=sys.stderr)
        return 1

    print(f"\n── RESET STORYBOARD: {tid} ──────────────────────────")
    print(f"  name    : {tenant['name']}")
    print(f"  This clears: storyboard nodes in neo4j + open workboard jobs for this tenant.")
    print(f"  Registry entry is preserved. Auth tokens are preserved.")

    if not args.yes:
        answer = input("  Continue? [y/N] ").strip().lower()
        if answer != "y":
            print("  Aborted.")
            return 0

    # 1. Clear neo4j storyboard nodes
    neo_ok = _neo_clear_storyboard(tid)
    print(f"  {'✓' if neo_ok else '~'} neo4j storyboard nodes {'cleared' if neo_ok else 'offline — skipped'}")

    # 2. Count open jobs (we tombstone them all as reset)
    open_jobs = _open_jobs_for(tid)
    from services.v2_workboard import resolve_workboard_job
    for entry in open_jobs:
        jid = (entry.get("job") or {}).get("id")
        if jid:
            resolve_workboard_job(jid, outcome=f"reset by owner: {tid}", source="studio-project-reset")
    print(f"  ✓ {len(open_jobs)} open workboard job(s) tombstoned")

    # 3. Emit reset event
    emit_workboard_job(
        source="studio-project-reset",
        action="studio.project.reset",
        event=f"STUDIO STORYBOARD RESET: {tid} ({tenant['name']}) — storyboard cleared, jobs tombstoned",
        lane="engineering",
        status="done",
        payload={
            "tenant_id": tid, "name": tenant["name"],
            "jobs_tombstoned": len(open_jobs), "neo4j_cleared": neo_ok,
            "reset_at": _now(),
        },
    )
    print(f"  ✓ workboard reset event emitted")

    print(f"\n✓ Storyboard for '{tid}' reset. Registry and auth intact.")
    print(f"  To rebuild: python tools/studio_project.py restart --id {tid}")
    return 0


def cmd_restart(args) -> int:
    """Full project restart — reset storyboard + update registry status + re-seed auth + re-queue."""
    tid = (args.id or "").strip()
    if not tid:
        print("ERROR: --id required", file=sys.stderr)
        return 1

    reg = _load_registry()
    tenants = reg.get("creative_tenants", [])
    idx = next((i for i, t in enumerate(tenants) if t["id"] == tid), None)
    if idx is None:
        print(f"ERROR: '{tid}' not found in registry.", file=sys.stderr)
        return 1

    tenant = tenants[idx]
    print(f"\n── FULL RESTART: {tid} ──────────────────────────────")
    print(f"  name    : {tenant['name']}")
    print(f"  current : status={tenant.get('status')} kind={tenant.get('kind')}")
    print(f"  This resets the storyboard, re-seeds auth, and re-queues a start-over job.")

    if not args.yes:
        answer = input("  Continue? [y/N] ").strip().lower()
        if answer != "y":
            print("  Aborted.")
            return 0

    # Optionally update status
    new_status = (args.status or "").strip() or tenant.get("status", "in_production")
    if new_status != tenant.get("status"):
        tenants[idx]["status"] = new_status
        reg["creative_tenants"] = tenants
        _save_registry(reg)
        tenant = tenants[idx]
        print(f"  ✓ status updated to '{new_status}'")

    role = DEFAULT_ROLE_MAP.get(new_status, "Resident")

    # 1. Clear storyboard
    neo_ok = _neo_clear_storyboard(tid)
    print(f"  {'✓' if neo_ok else '~'} storyboard cleared in neo4j")

    # 2. Tombstone open jobs
    open_jobs = _open_jobs_for(tid)
    from services.v2_workboard import resolve_workboard_job
    for entry in open_jobs:
        jid = (entry.get("job") or {}).get("id")
        if jid:
            resolve_workboard_job(jid, outcome=f"full restart: {tid}", source="studio-project-restart")
    print(f"  ✓ {len(open_jobs)} open job(s) tombstoned")

    # 3. Re-merge neo4j project node
    neo_ok2 = _neo_merge_project(tenant)
    print(f"  {'✓' if neo_ok2 else '~'} neo4j project node re-merged")

    # 4. Re-seed auth
    auth_ok = _auth_ready()
    verified = _issue_token(tid, role) if auth_ok else False
    print(f"  {'✓' if verified else '~'} auth re-seeded (role={role})")

    # 5. Emit restart job (creative lane — start-over is a creative decision)
    emit_workboard_job(
        source="studio-project-restart",
        action="studio.project.restart",
        event=f"STUDIO PROJECT RESTART: {tid} ({tenant['name']}) — full start-over queued",
        lane="creative",
        status="queued",
        priority="high",
        payload={
            "tenant_id": tid, "name": tenant["name"],
            "kind": tenant.get("kind"), "render_register": tenant.get("render_register"),
            "status": new_status, "role": role,
            "jobs_tombstoned": len(open_jobs),
            "neo4j_cleared": neo_ok, "auth_verified": verified,
            "restart_at": _now(),
            "note": args.note or "Full project restart — start over from scratch.",
        },
    )
    print(f"  ✓ restart job queued in creative lane (awaiting owner review)")

    # 6. Reindex studio assets
    sa_ok = _reindex_studio_assets()
    print(f"  {'✓' if sa_ok else '~'} studio-assets reindexed")

    print(f"\n✓ '{tid}' restarted. Creative lane job queued — approve to begin:")
    print(f"  python -m services.v2_workboard --pending")
    print(f"  python -m services.v2_workboard --approve <job_id> --approver owner")
    return 0


def cmd_status(args) -> int:
    """Show status of one or all projects."""
    reg = _load_registry()
    tenants = reg.get("creative_tenants", [])

    if args.id:
        tenants = [t for t in tenants if t["id"] == args.id]
        if not tenants:
            print(f"ERROR: '{args.id}' not found.", file=sys.stderr)
            return 1

    entries = read_workboard_log()
    tombstoned = set()
    jobs_by_tenant: dict[str, list] = {}
    for e in entries:
        job = e.get("job") or {}
        if e.get("kind") == "tombstone":
            cid = job.get("correlation_id")
            if cid:
                tombstoned.add(cid)
        elif e.get("kind") == "job":
            tid = (job.get("payload") or {}).get("tenant_id") or ""
            if tid:
                jobs_by_tenant.setdefault(tid, []).append(e)

    print(f"\n{'ID':<35} {'KIND':<14} {'STATUS':<30} {'OPEN JOBS'}")
    print(f"{'-'*35} {'-'*14} {'-'*30} {'-'*10}")
    for t in tenants:
        tid = t["id"]
        open_count = sum(
            1 for e in jobs_by_tenant.get(tid, [])
            if (e.get("job") or {}).get("id") not in tombstoned
        )
        print(f"{tid:<35} {t.get('kind',''):<14} {str(t.get('status','')):<30} {open_count}")
    print(f"\nTotal: {len(tenants)} project(s)")
    return 0


def cmd_list(args) -> int:
    """List all studio projects, optionally filtered by kind."""
    reg = _load_registry()
    tenants = reg.get("creative_tenants", [])
    if args.kind:
        tenants = [t for t in tenants if t.get("kind") == args.kind]

    print(f"\n{'#':<4} {'ID':<35} {'KIND':<14} {'RENDER':<14} {'STATUS'}")
    print(f"{'-'*4} {'-'*35} {'-'*14} {'-'*14} {'-'*30}")
    for i, t in enumerate(tenants, 1):
        print(f"{i:<4} {t['id']:<35} {t.get('kind',''):<14} {t.get('render_register',''):<14} {t.get('status','')}")
    print(f"\n{len(tenants)} project(s)")
    return 0


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> int:
    p = argparse.ArgumentParser(
        prog="studio_project",
        description="Studio project lifecycle management (add / reset / restart / status / list).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    # add
    pa = sub.add_parser("add", help="Add a new studio project")
    pa.add_argument("--id",     required=True,  help="Unique tenant_id (snake_case, e.g. film_new_project)")
    pa.add_argument("--name",   required=True,  help="Human-readable project name")
    pa.add_argument("--kind",   default="film", help=f"Kind: {sorted(VALID_KINDS)}")
    pa.add_argument("--render", default="photoreal", help=f"Render register: {sorted(VALID_RENDERS)}")
    pa.add_argument("--status", default="proposed_internal", help=f"Initial status")

    # reset
    pr = sub.add_parser("reset", help="Reset storyboard for a project (keeps registry entry)")
    pr.add_argument("--id",  required=True, help="tenant_id to reset")
    pr.add_argument("--yes", action="store_true", help="Skip confirmation prompt")

    # restart
    prr = sub.add_parser("restart", help="Full project restart (reset + re-seed + re-queue)")
    prr.add_argument("--id",     required=True, help="tenant_id to restart")
    prr.add_argument("--status", default="",    help="Update production status (optional)")
    prr.add_argument("--note",   default="",    help="Note recorded on restart job")
    prr.add_argument("--yes",    action="store_true", help="Skip confirmation prompt")

    # status
    ps = sub.add_parser("status", help="Show project status and open jobs")
    ps.add_argument("--id", default="", help="tenant_id to inspect (omit for all)")

    # list
    pl = sub.add_parser("list", help="List all studio projects")
    pl.add_argument("--kind", default="", help="Filter by kind (film/game/music_video/…)")

    args = p.parse_args()
    dispatch = {
        "add":     cmd_add,
        "reset":   cmd_reset,
        "restart": cmd_restart,
        "status":  cmd_status,
        "list":    cmd_list,
    }
    return dispatch[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
