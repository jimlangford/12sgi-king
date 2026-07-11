import json
import os
import sys
import time
from pathlib import Path
from uuid import uuid4

WORKBOARD_SCHEMA = "workboard-job-v1"
WORKBOARD_THREAD = os.environ.get("WORKBOARD_TARGET_THREAD", "workboard-quad-os")
DEFAULT_DISPATCH_LOG = Path(__file__).resolve().parents[1] / ".dispatch_log.jsonl"
DISPATCH_LOG = Path(os.environ.get("WORKBOARD_DISPATCH_LOG") or DEFAULT_DISPATCH_LOG)

# V2 four-lane architecture
# ─────────────────────────────────────────────────────────────────────────────
#  engineering  – internal plumbing (auth, storage, AI analysis, data ingest).
#                 These jobs self-heal automatically; no human gate required.
#  creative     – content that a human must review before it leaves the system
#                 (generated documents, images, civic reports in draft state).
#                 V1 is the review surface for creative approvals.
#  output       – items approved and staged for publish to 12sgi.com / govOS.
#                 Requires explicit owner approval; never auto-healed.
# ─────────────────────────────────────────────────────────────────────────────
LANE_TYPES = {"engineering", "creative", "output"}

# engineering lane: queued → in-progress → done | failed (auto-heal allowed)
# creative/output:  queued → in-progress → pending-approval → approved | rejected
# any lane:         → archived (owner soft-delete, never a raw removal — see
#                      archive_workboard_job() below)
QUEUE_STATUSES = {"queued", "in-progress", "pending-approval", "approved", "rejected", "done", "failed", "archived"}

# Statuses that the self-healer may resolve automatically (engineering only)
_AUTO_HEAL_STATUSES = {"queued", "in-progress"}

# Statuses that require human action (never auto-healed regardless of lane)
_APPROVAL_STATUSES = {"pending-approval"}

# Owner opt-in override: config/owner_policy.json can set auto_approve_creative /
# auto_approve_output to true. This is an explicit, auditable, reversible owner decision
# (see docs/SOCIAL_CONNECTORS.md "Owner Auto-Approval Mode") — default (no file, or flag
# false) is the standard manual-review workflow described above.
OWNER_POLICY_PATH = Path(__file__).resolve().parents[1] / "config" / "owner_policy.json"


def _load_owner_policy() -> dict:
    try:
        return json.loads(OWNER_POLICY_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def auto_approve_enabled(lane: str) -> bool:
    """True only if the owner has explicitly opted this lane into auto-approval.

    Reads config/owner_policy.json at call time (no caching), so toggling the flag off
    (or deleting the file) immediately restores manual review with no code change.
    """
    return bool(_load_owner_policy().get(f"auto_approve_{lane}"))


def _iso_now() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())


def _coerce_status(status: str) -> str:
    candidate = (status or "queued").strip().lower()
    if candidate not in QUEUE_STATUSES:
        return "queued"
    return candidate


def _coerce_lane(lane: str) -> str:
    candidate = (lane or "engineering").strip().lower()
    if candidate not in LANE_TYPES:
        return "engineering"
    return candidate


def emit_workboard_job(
    *,
    source: str,
    action: str,
    event: str,
    payload: dict | None = None,
    status: str = "queued",
    priority: str = "normal",
    kind: str = "job",
    lane: str = "engineering",
    correlation_id: str | None = None,
    log_path: Path | None = None,
) -> dict:
    queue_status = _coerce_status(status)
    job_lane = _coerce_lane(lane)
    entry = {
        "ts": int(time.time()),
        "iso": _iso_now(),
        "schema": WORKBOARD_SCHEMA,
        "source": source,
        "kind": kind,
        "lane": job_lane,
        "target_thread": WORKBOARD_THREAD,
        "priority": priority or "normal",
        "status": queue_status,
        "event": event,
        "job": {
            "id": str(uuid4()),
            "action": action,
            "status": queue_status,
            "correlation_id": correlation_id,
            "payload": payload or {},
        },
    }
    path = log_path or DISPATCH_LOG
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    # Owner opt-in auto-approval (config/owner_policy.json). Off by default; when on, a
    # creative/output job that lands in pending-approval is immediately approved instead
    # of waiting for a human. See docs/SOCIAL_CONNECTORS.md "Owner Auto-Approval Mode".
    if job_lane in ("creative", "output") and queue_status == "pending-approval" and auto_approve_enabled(job_lane):
        approve_workboard_job(
            entry["job"]["id"],
            approver="owner-auto-approve-policy",
            note="auto-approved per config/owner_policy.json",
            log_path=path,
        )
        entry["auto_approved"] = True
    return entry


def read_workboard_log(log_path: Path | None = None) -> list[dict]:
    """Read and parse all entries from the dispatch log.

    Returns a list of parsed entry dicts in append order.  Missing or empty
    log files return an empty list without raising.
    """
    path = log_path or DISPATCH_LOG
    if not path.exists():
        return []
    entries = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return entries


def resolve_workboard_job(
    job_id: str,
    outcome: str,
    *,
    source: str = "workboard-resolver",
    log_path: Path | None = None,
) -> dict:
    """Append a done-status tombstone for *job_id* to the dispatch log.

    The log is append-only and auditable — this never modifies existing
    entries.  The tombstone carries ``kind: "tombstone"`` so readers can
    distinguish it from a normal job entry, and references the original
    job via ``job.correlation_id``.

    Returns the tombstone entry dict.
    """
    path = log_path or DISPATCH_LOG
    tombstone = {
        "ts": int(time.time()),
        "iso": _iso_now(),
        "schema": WORKBOARD_SCHEMA,
        "source": source,
        "kind": "tombstone",
        "target_thread": WORKBOARD_THREAD,
        "priority": "normal",
        "status": "done",
        "event": f"RESOLVED: {job_id}",
        "job": {
            "id": str(uuid4()),
            "action": "resolved",
            "status": "done",
            "correlation_id": job_id,
            "payload": {"outcome": outcome},
        },
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(tombstone, ensure_ascii=False) + "\n")
    return tombstone


def approve_workboard_job(
    job_id: str,
    approver: str,
    *,
    note: str | None = None,
    log_path: Path | None = None,
) -> dict:
    """Record an approval tombstone for a creative or output lane job.

    Appends an ``approved`` tombstone so the job is considered resolved via
    human sign-off.  Only creative and output lane jobs should normally flow
    through here; engineering jobs should self-heal instead.

    Returns the tombstone entry dict.
    """
    path = log_path or DISPATCH_LOG
    tombstone = {
        "ts": int(time.time()),
        "iso": _iso_now(),
        "schema": WORKBOARD_SCHEMA,
        "source": approver,
        "kind": "tombstone",
        "target_thread": WORKBOARD_THREAD,
        "priority": "normal",
        "status": "approved",
        "event": f"APPROVED: {job_id}",
        "job": {
            "id": str(uuid4()),
            "action": "approved",
            "status": "approved",
            "correlation_id": job_id,
            "payload": {"approver": approver, "note": note or ""},
        },
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(tombstone, ensure_ascii=False) + "\n")
    return tombstone


def reject_workboard_job(
    job_id: str,
    reason: str,
    *,
    rejector: str = "owner",
    log_path: Path | None = None,
) -> dict:
    """Record a rejection tombstone for a creative or output lane job.

    Appends a ``rejected`` tombstone.  The original job entry is not modified;
    the log remains fully auditable.

    Returns the tombstone entry dict.
    """
    path = log_path or DISPATCH_LOG
    tombstone = {
        "ts": int(time.time()),
        "iso": _iso_now(),
        "schema": WORKBOARD_SCHEMA,
        "source": rejector,
        "kind": "tombstone",
        "target_thread": WORKBOARD_THREAD,
        "priority": "normal",
        "status": "rejected",
        "event": f"REJECTED: {job_id}",
        "job": {
            "id": str(uuid4()),
            "action": "rejected",
            "status": "rejected",
            "correlation_id": job_id,
            "payload": {"rejector": rejector, "reason": reason},
        },
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(tombstone, ensure_ascii=False) + "\n")
    return tombstone


def archive_workboard_job(
    job_id: str,
    archiver: str,
    *,
    note: str | None = None,
    log_path: Path | None = None,
) -> dict:
    """Record an archive tombstone for any lane's job (owner soft-delete).

    This is the v2 counterpart of the legacy workboard consumer's
    archive/restore/retry/reschedule job-management actions: a job is never
    hard-deleted here or there. Archiving only appends an ``archived``
    tombstone so the original job entry is preserved and the log stays fully
    auditable — mirroring the legacy consumer's soft-delete-as-archive +
    append-only audit-trail pattern (e.g. clearing stale engineering-lane
    jobs once a newer backend supersedes them).

    Returns the tombstone entry dict.
    """
    path = log_path or DISPATCH_LOG
    tombstone = {
        "ts": int(time.time()),
        "iso": _iso_now(),
        "schema": WORKBOARD_SCHEMA,
        "source": archiver,
        "kind": "tombstone",
        "target_thread": WORKBOARD_THREAD,
        "priority": "normal",
        "status": "archived",
        "event": f"ARCHIVED: {job_id}",
        "job": {
            "id": str(uuid4()),
            "action": "archived",
            "status": "archived",
            "correlation_id": job_id,
            "payload": {"archiver": archiver, "note": note or ""},
        },
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(tombstone, ensure_ascii=False) + "\n")
    return tombstone


def emit_hina_creative_job(
    *,
    offering_date: str,
    hina_node_id: int,
    akua: str,
    wa_phase: str,
    particles: str,
    civic_source: str,
    output_types: list | None = None,
    source: str = "hina-nightly",
    log_path: "Path | None" = None,
) -> dict:
    """Emit a HINA-driven creative lane job to the workboard dispatch log.

    This is the canonical entry point for HINA's nightly Pō balancing work.
    Every call is traceable back to a civic date + node, satisfying the
    studio_parity.py cycle_connected and hina_balance_present checks.

    Parameters
    ----------
    offering_date:  The civic date HINA is balancing (ISO format YYYY-MM-DD).
    hina_node_id:   Node id (1–54) whose energy answers today's Ao imbalance.
    akua:           Presiding source-energy (Pele / Kāne / Lono / Kanaloa).
    wa_phase:       Kumulipo era key: "Ao" or "Pō".
    particles:      Creative expression layer bound to this akua + zone.
    civic_source:   The civic event that created the Ao imbalance (e.g.
                    "agenda/2026-07-06/item-3 — Lahaina recovery vote").
    output_types:   Which content jobs this balance reading drives.
                    Defaults to ["cut-scene", "card-render"].
    source:         Originating process name (default: "hina-nightly").
    log_path:       Override the dispatch log path (default: DISPATCH_LOG).

    Returns the emitted workboard job entry dict.
    """
    return emit_workboard_job(
        source=source,
        action="hina-balance",
        event=f"HINA Pō balance: node {hina_node_id} ({akua}) answers {offering_date}",
        lane="creative",
        status="queued",
        priority="normal",
        kind="job",
        payload={
            "offering_date": offering_date,
            "hina_node_id": hina_node_id,
            "akua": akua,
            "wa_phase": wa_phase,
            "particles": particles,
            "civic_source": civic_source,
            "output_types": output_types or ["cut-scene", "card-render"],
        },
        log_path=log_path,
    )


def pending_approvals(log_path: Path | None = None) -> list[dict]:
    """Return all creative and output lane jobs that have not yet been resolved.

    These are the items waiting for human review before any content goes public.
    Engineering lane jobs are excluded — they self-heal and never need this queue.
    """
    entries = read_workboard_log(log_path)
    resolved_ids: set[str] = set()
    pending: dict[str, dict] = {}

    for entry in entries:
        job = entry.get("job") or {}
        if entry.get("kind") == "tombstone":
            cid = job.get("correlation_id")
            if cid:
                resolved_ids.add(cid)
        elif entry.get("lane") in {"creative", "output"} and entry.get("kind") == "job":
            jid = job.get("id")
            if jid:
                pending[jid] = entry

    return [entry for jid, entry in pending.items() if jid not in resolved_ids]


def selfheal_engineering_jobs(
    log_path: Path | None = None,
    outcome: str = "self-healed",
) -> int:
    """Self-heal all stalled engineering lane jobs that have no tombstone yet.

    Engineering jobs (auth, storage, AI analysis, data ingest) are approved to
    fix themselves forward — this is the one-place implementation of that rule.

    Creative and output lane jobs are deliberately skipped: they require human
    approval before any content leaves the private system.  Calling this
    function will never close a creative or output job.

    Returns the count of newly resolved engineering jobs.
    """
    path = log_path or DISPATCH_LOG
    entries = read_workboard_log(path)

    resolved_ids: set[str] = set()
    open_engineering: dict[str, dict] = {}

    for entry in entries:
        job = entry.get("job") or {}
        if entry.get("kind") == "tombstone":
            cid = job.get("correlation_id")
            if cid:
                resolved_ids.add(cid)
        elif (
            entry.get("kind") == "job"
            and entry.get("lane", "engineering") == "engineering"
            and entry.get("status") in _AUTO_HEAL_STATUSES
        ):
            jid = job.get("id")
            if jid:
                open_engineering[jid] = entry

    to_heal = {jid: e for jid, e in open_engineering.items() if jid not in resolved_ids}
    for jid in to_heal:
        resolve_workboard_job(
            jid,
            outcome,
            source="workboard-self-healer",
            log_path=path,
        )
    return len(to_heal)


def _batch_resolve_log(log_path: Path | None = None, outcome: str = "batch-closed") -> int:
    """Backward-compatible wrapper: self-heal engineering lane jobs only.

    The old behavior of closing ALL open jobs unconditionally is replaced by
    lane-aware healing.  Creative and output jobs are never auto-closed here —
    they require explicit human approval via approve_workboard_job().

    Use selfheal_engineering_jobs() for new code.  This wrapper exists so
    existing CLI calls (``python -m services.v2_workboard --outcome ...``) and
    tests that import ``_batch_resolve_log`` continue to work unchanged.
    """
    return selfheal_engineering_jobs(log_path=log_path, outcome=outcome)


if __name__ == "__main__":
    # CLI: python -m services.v2_workboard [--log PATH] [--outcome TEXT] [--pending]
    import argparse

    parser = argparse.ArgumentParser(
        description=(
            "Workboard CLI — self-heal engineering jobs or list pending approvals.\n"
            "\n"
            "Lanes:\n"
            "  engineering  Auto-healed by this tool (--outcome flag applies).\n"
            "  creative     Needs human approval — never auto-healed.\n"
            "  output       Needs owner approval before publish — never auto-healed.\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--log", default=None, help="Path to dispatch log (default: WORKBOARD_DISPATCH_LOG env or repo default)")
    parser.add_argument("--outcome", default="self-healed", help="Outcome label recorded on each self-healed engineering tombstone")
    parser.add_argument("--pending", action="store_true", help="List pending creative/output jobs that need human approval")
    parser.add_argument("--archive", metavar="JOB_ID", default=None, help="Archive (soft-delete) a job by id; appends an audit tombstone, never deletes")
    parser.add_argument("--archiver", default="owner", help="Identity recorded as the archiver (used with --archive)")
    parser.add_argument("--note", default=None, help="Optional note recorded on the archive tombstone (used with --archive)")
    parser.add_argument("--approve", metavar="JOB_ID", default=None, help="Approve a pending creative/output lane job by id; appends an approved tombstone")
    parser.add_argument("--approver", default="owner", help="Identity recorded as the approver (used with --approve)")
    parser.add_argument("--reject", metavar="JOB_ID", default=None, help="Reject a pending creative/output lane job by id; appends a rejected tombstone")
    parser.add_argument("--rejector", default="owner", help="Identity recorded as the rejector (used with --reject)")
    parser.add_argument("--reason", default=None, help="Reason recorded on the rejection tombstone (used with --reject)")
    args = parser.parse_args()

    log_path = Path(args.log) if args.log else None

    if args.archive:
        tombstone = archive_workboard_job(args.archive, args.archiver, note=args.note, log_path=log_path)
        print(f"Archived {args.archive} -> {tombstone['job']['id']}")
        sys.exit(0)

    if args.approve:
        tombstone = approve_workboard_job(args.approve, args.approver, note=args.note, log_path=log_path)
        print(f"Approved {args.approve} -> {tombstone['job']['id']} (approver={args.approver})")
        sys.exit(0)

    if args.reject:
        tombstone = reject_workboard_job(args.reject, args.reason or "(no reason given)", rejector=args.rejector, log_path=log_path)
        print(f"Rejected {args.reject} -> {tombstone['job']['id']} (rejector={args.rejector})")
        sys.exit(0)

    if args.pending:
        items = pending_approvals(log_path=log_path)
        if not items:
            print("No pending approvals.")
        else:
            print(f"{len(items)} item(s) pending approval:")
            for item in items:
                job = item.get("job") or {}
                print(f"  [{item.get('lane')}] {job.get('id')} | {job.get('action')} | {item.get('iso')}")
        sys.exit(0)

    healed = selfheal_engineering_jobs(log_path=log_path, outcome=args.outcome)
    print(f"Self-healed {healed} engineering job(s).")
    sys.exit(0)
