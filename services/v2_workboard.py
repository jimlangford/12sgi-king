import json
import os
import sys
import time
from pathlib import Path
from uuid import uuid4

# Platform event bus — best-effort; import failure must never break workboard.
try:
    from services.event_bus import publish_event as _publish_platform_event
except Exception:
    def _publish_platform_event(*args, **kwargs):  # type: ignore[misc]
        return None

WORKBOARD_SCHEMA = "workboard-job-v2"

# ── DAG node schema ───────────────────────────────────────────────────────────
# Each dag_node in a job's dag_nodes list carries:
#   name             — human-readable stage label (e.g. "Scene Build")
#   status           — waiting | running | done | failed
#   engine           — ollama | comfyui | voice | embedding | none
#   inputs_resolved  — True once all predecessor outputs are available
#
# The list is ordered (index 0 = first stage). The router advances each node's
# status as execution progresses. A job is "Waiting on GPU" when any node has
# engine in {comfyui, gpu} and status = "running".
DAG_NODE_STATUSES = {"waiting", "running", "done", "failed"}
DAG_NODE_ENGINES  = {"ollama", "comfyui", "voice", "embedding", "none"}
GPU_ENGINES       = {"comfyui", "gpu"}
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

# Approval-type vocabulary used for multi-gate corporate/legal workflows.
# A job may require one or more of these before it is considered fully approved.
# editorial  — content review by the owner (default for all creative/output jobs)
# legal      — legal clearance (copyright, claims, compliance)
# corporate  — brand / entity alignment across 12SGI corporate family
# rights     — media rights cleared (video clips, music, likeness)
APPROVAL_TYPES = {"editorial", "legal", "corporate", "rights"}
_DEFAULT_APPROVAL_TYPES = ("editorial",)

# Social media platforms requiring owner sign-off before posting.
# All other destinations (civic, casework, prayer feed, king_local, govOS) publish freely.
# Studios are departments of working businesses — no corporate gate (owner decision 2026-07-13).
SOCIAL_MEDIA_PLATFORMS = {"facebook", "instagram", "linkedin", "youtube", "tiktok", "x", "twitter"}


def requires_owner_signoff(payload: dict) -> bool:
    """Return True only if a job targets a public-facing social media platform.

    Civic reports, casework (except personal case data), daily prayer content,
    and all internal/king_local destinations publish freely without owner sign-off.
    Studios are business departments; no corporate gate applies.
    """
    platform = (payload.get("platform") or "").lower()
    targets = payload.get("targets") or []
    if platform in SOCIAL_MEDIA_PLATFORMS:
        return True
    if any(str(t).lower() in SOCIAL_MEDIA_PLATFORMS for t in targets):
        return True
    return False


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


def _coerce_dag_nodes(nodes: list | None) -> list:
    """Validate and normalise a dag_nodes list.

    Each element must be a dict; unknown keys are preserved so future node
    metadata (e.g. retry counts, time estimates) round-trips cleanly.
    Invalid status/engine values are coerced to "waiting"/"none".
    """
    if not nodes:
        return []
    out = []
    for raw in nodes:
        if not isinstance(raw, dict):
            continue
        node = dict(raw)
        st = (node.get("status") or "waiting").strip().lower()
        if st not in DAG_NODE_STATUSES:
            st = "waiting"
        eng = (node.get("engine") or "none").strip().lower()
        if eng not in DAG_NODE_ENGINES:
            eng = "none"
        out.append({
            **node,
            "name": str(node.get("name") or "unnamed"),
            "status": st,
            "engine": eng,
            "inputs_resolved": bool(node.get("inputs_resolved", False)),
        })
    return out


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
    approval_types: list | None = None,
    dag_nodes: list | None = None,
    log_path: Path | None = None,
) -> dict:
    queue_status = _coerce_status(status)
    job_lane = _coerce_lane(lane)
    # Normalise and validate approval_types; fall back to the default set.
    if approval_types is not None:
        atypes = [a.strip().lower() for a in approval_types if a.strip().lower() in APPROVAL_TYPES]
    else:
        atypes = list(_DEFAULT_APPROVAL_TYPES)
    coerced_nodes = _coerce_dag_nodes(dag_nodes)
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
        "approval_types": atypes,
        "job": {
            "id": str(uuid4()),
            "action": action,
            "status": queue_status,
            "correlation_id": correlation_id,
            "payload": payload or {},
            "dag_nodes": coerced_nodes,
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

    _publish_platform_event(
        "workboard.job.created",
        "v2_workboard",
        payload={"lane": job_lane, "action": action, "event": event, "status": queue_status},
        entity_id=entry["job"]["id"],
        correlation_id=correlation_id,
    )
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
    approval_type: str = "editorial",
    log_path: Path | None = None,
) -> dict:
    """Record an approval tombstone for a creative or output lane job.

    Appends an ``approved`` tombstone so the job is considered resolved via
    human sign-off.  Only creative and output lane jobs should normally flow
    through here; engineering jobs should self-heal instead.

    ``approval_type`` identifies *which* gate was cleared (editorial / legal /
    corporate / rights).  Callers that do not specify it default to
    ``"editorial"`` — the standard owner content review.  Use
    :func:`approvals_cleared` to check which types have been recorded and
    :func:`all_required_approvals_met` to decide whether a job is fully cleared.

    Returns the tombstone entry dict.
    """
    atype = approval_type.strip().lower() if approval_type else "editorial"
    if atype not in APPROVAL_TYPES:
        atype = "editorial"
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
        "event": f"APPROVED[{atype}]: {job_id}",
        "approval_type": atype,
        "job": {
            "id": str(uuid4()),
            "action": "approved",
            "status": "approved",
            "correlation_id": job_id,
            "payload": {"approver": approver, "note": note or "", "approval_type": atype},
        },
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(tombstone, ensure_ascii=False) + "\n")
    _publish_platform_event(
        "workboard.job.approved",
        "v2_workboard",
        payload={"approver": approver, "note": note or ""},
        entity_id=job_id,
    )
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
    _publish_platform_event(
        "workboard.job.rejected",
        "v2_workboard",
        payload={"rejector": rejector, "reason": reason},
        entity_id=job_id,
    )
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


def approvals_cleared(job_id: str, log_path: Path | None = None) -> list[str]:
    """Return the list of approval types that have been recorded for *job_id*.

    Each call to :func:`approve_workboard_job` with a different ``approval_type``
    adds one entry.  This function scans the append-only log and returns the
    unique set of types that have been approved, so callers can compare against
    the job's ``approval_types`` list to see what is still outstanding.

    Example::

        cleared = approvals_cleared(job_id)
        # ['editorial']  — legal and corporate still pending
    """
    entries = read_workboard_log(log_path)
    cleared: list[str] = []
    for entry in entries:
        job = entry.get("job") or {}
        if (
            entry.get("kind") == "tombstone"
            and entry.get("status") == "approved"
            and job.get("correlation_id") == job_id
        ):
            atype = entry.get("approval_type") or job.get("payload", {}).get("approval_type", "editorial")
            if atype and atype not in cleared:
                cleared.append(atype)
    return cleared


def all_required_approvals_met(
    job_id: str,
    required_types: list | None = None,
    log_path: Path | None = None,
) -> bool:
    """Return True only when every required approval type has been recorded.

    If *required_types* is not provided, looks up the job entry in the log and
    uses its ``approval_types`` field; falls back to ``["editorial"]``.

    This is the single check that determines whether a job is fully cleared for
    the PUBLISH step — callers must call this instead of checking for any single
    ``approved`` tombstone when corporate/legal gates are required.
    """
    if required_types is None:
        entries = read_workboard_log(log_path)
        for entry in entries:
            if entry.get("job", {}).get("id") == job_id and entry.get("kind") == "job":
                required_types = entry.get("approval_types") or ["editorial"]
                break
        else:
            required_types = ["editorial"]
    cleared = set(approvals_cleared(job_id, log_path))
    return all(t in cleared for t in required_types)


def selfheal_engineering_jobs(
    log_path: Path | None = None,
    outcome: str = "stale-requeued",
) -> int:
    """Close out stalled engineering lane jobs that have no tombstone yet.

    HONESTY NOTE: this function performs NO actual work on the jobs — it only
    tombstones stalled queue entries so they stop clogging the board.  It must
    therefore never record an outcome that implies the work was done.  Any
    heal-flavored outcome (e.g. the legacy "self-healed") is coerced to
    "stale-requeued": the job is closed as stale and should be re-emitted by
    its owner service if the work is still wanted (verify-before-done doctrine).

    Creative and output lane jobs are deliberately skipped: they require human
    approval before any content leaves the private system.  Calling this
    function will never close a creative or output job.

    Returns the count of newly tombstoned engineering jobs.
    """
    # Coerce fake-done outcomes at this single choke point so legacy callers
    # (v2 /selfheal endpoint, CLI, tests) passing "self-healed" cannot mint
    # done-with-no-work-performed tombstones.
    if "heal" in (outcome or "").lower():
        outcome = "stale-requeued"
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
    if to_heal:
        _publish_platform_event(
            "workboard.engineering.selfhealed",
            "v2_workboard",
            payload={"healed_count": len(to_heal), "outcome": outcome},
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


def workboard_pulse(log_path: Path | None = None) -> dict:
    """Compute the six operational pulse counters from the dispatch log.

    Returns a dict with:
      jobs_running      — open jobs in any lane with status "in-progress"
      waiting_gpu       — open in-progress jobs where any dag_node uses a GPU engine
      waiting_owner     — creative/output jobs in pending-approval (human gate)
      auto_healed_today — engineering tombstones resolved today (UTC) with a
                          self-heal outcome
      deploy_ready      — output lane jobs with an "approved" tombstone
      critical          — log entries whose event field starts with "BLOCKER"
                          and that have no subsequent RESOLVED entry

    All values are non-negative integers.  Safe to call when the log is
    missing (returns all zeros).  Does not write to the log.
    """
    import re as _re

    entries = read_workboard_log(log_path)
    today_prefix = time.strftime("%Y-%m-%d", time.gmtime())  # UTC date

    # Collect all job ids that have tombstones (resolved/approved/rejected/archived)
    tombstoned_ids: set[str] = set()
    # Engineering healed today
    auto_healed_today = 0
    # Deploy-ready: output lane + approved tombstone
    deploy_ready_ids: set[str] = set()
    # Blocked event tracking: key = identifier string → True if unresolved
    blocker_events: dict[str, bool] = {}

    for entry in entries:
        job = entry.get("job") or {}
        ev = entry.get("event") or ""
        iso = entry.get("iso") or ""

        if entry.get("kind") == "tombstone":
            cid = job.get("correlation_id")
            if cid:
                tombstoned_ids.add(cid)
            # Count self-healed engineering today
            outcome = job.get("payload", {}).get("outcome") or ""
            if (
                entry.get("source") == "workboard-self-healer"
                and "heal" in outcome.lower()
                and iso.startswith(today_prefix)
            ):
                auto_healed_today += 1
            # Track approved output lane jobs
            if entry.get("status") == "approved":
                orig_id = job.get("correlation_id")
                if orig_id:
                    deploy_ready_ids.add(orig_id)
            # RESOLVED prefix clears a BLOCKER
            if ev.startswith("RESOLVED:") or ev.startswith("DONE") or ev.startswith("SHIPPED"):
                pass  # tombstone presence covers resolution for jobs

        elif ev.upper().startswith("BLOCKER"):
            # Watcher-style BLOCKER entries — key on the message text
            blocker_events[ev] = True
        elif ev.upper().startswith("RESOLVED"):
            # Clear matching blocker if watcher emitted explicit resolution
            for key in list(blocker_events):
                if ev[len("RESOLVED:"):].strip() in key:
                    blocker_events.pop(key, None)

    # Open jobs: has a job entry with no tombstone
    open_jobs: list[dict] = []
    for entry in entries:
        if entry.get("kind") != "job":
            continue
        jid = (entry.get("job") or {}).get("id")
        if jid and jid not in tombstoned_ids:
            open_jobs.append(entry)

    jobs_running = sum(1 for e in open_jobs if e.get("status") == "in-progress")

    # Waiting on GPU: in-progress open jobs with any dag_node on a GPU engine
    waiting_gpu = 0
    for e in open_jobs:
        if e.get("status") != "in-progress":
            continue
        nodes = (e.get("job") or {}).get("dag_nodes") or []
        if any(n.get("engine") in GPU_ENGINES for n in nodes):
            waiting_gpu += 1

    # Waiting on owner: pending-approval in creative/output lane
    waiting_owner = sum(
        1 for e in open_jobs
        if e.get("lane") in {"creative", "output"} and e.get("status") == "pending-approval"
    )

    # Deploy ready: output lane jobs approved but not yet archived/rejected
    # (approved tombstone exists AND no archive/reject tombstone supersedes it)
    rejected_archived: set[str] = set()
    for entry in entries:
        if entry.get("kind") == "tombstone" and entry.get("status") in {"rejected", "archived"}:
            cid = (entry.get("job") or {}).get("correlation_id")
            if cid:
                rejected_archived.add(cid)
    # Only count output lane originals
    output_original_ids: set[str] = {
        (e.get("job") or {}).get("id")
        for e in entries
        if e.get("kind") == "job" and e.get("lane") == "output"
        and (e.get("job") or {}).get("id")
    }
    deploy_ready = len(
        deploy_ready_ids & output_original_ids - rejected_archived
    )

    critical = len(blocker_events)

    return {
        "jobs_running":      jobs_running,
        "waiting_gpu":       waiting_gpu,
        "waiting_owner":     waiting_owner,
        "auto_healed_today": auto_healed_today,
        "deploy_ready":      deploy_ready,
        "critical":          critical,
    }


# ── Hub feed: the prefix vocabulary the system uses for log entries ───────────
# FINDING   — evidence of a state mismatch; may trigger automatic repair
# SHIPPED   — work completed and pushed
# BLOCKER   — unresolved obstacle requiring owner attention
# DECISION  — owner-recorded policy or direction
# POLICY    — standing rule recorded for future reference
# HANDOFF   — cross-agent or cross-session handover note
# OWNERSHIP — domain or component ownership recorded
# DONE      — task closure note
_HUB_PREFIX_ORDER = ["BLOCKER", "FINDING", "SHIPPED", "DECISION", "POLICY", "HANDOFF", "OWNERSHIP", "DONE"]
_HUB_PREFIX_SET   = set(_HUB_PREFIX_ORDER)


def _hub_prefix(event: str) -> str:
    """Extract the capitalised prefix from a dispatch log event string."""
    upper = (event or "").upper()
    for pfx in _HUB_PREFIX_ORDER:
        if upper.startswith(pfx):
            return pfx
    return "INFO"


def workboard_hub_feed(limit: int = 60, log_path: Path | None = None) -> list[dict]:
    """Return the last *limit* dispatch log entries formatted for the Hub panel.

    Each returned dict carries:
      ts      — Unix timestamp (int)
      iso     — ISO datetime string
      source  — originating watcher or service
      prefix  — capitalised event prefix (FINDING / SHIPPED / BLOCKER / …)
      event   — full event string
      lane    — workboard lane if applicable, else ""
      kind    — "job" | "tombstone" | "watcher"

    Sorted newest-first.  Safe to call when the log is missing.
    """
    entries = read_workboard_log(log_path)
    result = []
    for entry in entries:
        ev = entry.get("event") or ""
        kind = entry.get("kind") or ("watcher" if "schema" not in entry else "job")
        result.append({
            "ts":     entry.get("ts") or 0,
            "iso":    entry.get("iso") or "",
            "source": entry.get("source") or "",
            "prefix": _hub_prefix(ev),
            "event":  ev,
            "lane":   entry.get("lane") or "",
            "kind":   kind,
        })
    result.sort(key=lambda x: x["ts"], reverse=True)
    return result[:limit]


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
            "\n"
            "Approval types (--approval-type):\n"
            "  editorial    Owner content review (default).\n"
            "  legal        Legal clearance: copyright, claims, compliance.\n"
            "  corporate    Brand/entity alignment across the 12SGI corporate family.\n"
            "  rights       Media rights cleared: clips, music, likeness.\n"
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
    parser.add_argument("--approval-type", default="editorial", dest="approval_type",
                        choices=sorted(APPROVAL_TYPES),
                        help="Approval gate being cleared (editorial/legal/corporate/rights). Default: editorial")
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
        tombstone = approve_workboard_job(
            args.approve, args.approver,
            note=args.note,
            approval_type=args.approval_type,
            log_path=log_path,
        )
        print(f"Approved[{args.approval_type}] {args.approve} -> {tombstone['job']['id']} (approver={args.approver})")
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
