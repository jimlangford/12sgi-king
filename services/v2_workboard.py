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
QUEUE_STATUSES = {"queued", "in-progress", "done", "failed"}


def _iso_now() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())


def _coerce_status(status: str) -> str:
    candidate = (status or "queued").strip().lower()
    if candidate not in QUEUE_STATUSES:
        return "queued"
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
    correlation_id: str | None = None,
    log_path: Path | None = None,
) -> dict:
    queue_status = _coerce_status(status)
    entry = {
        "ts": int(time.time()),
        "iso": _iso_now(),
        "schema": WORKBOARD_SCHEMA,
        "source": source,
        "kind": kind,
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


def _batch_resolve_log(log_path: Path | None = None, outcome: str = "batch-closed") -> int:
    """Close every open (queued / in-progress) job that has no tombstone yet.

    Reads the log, computes the set of job IDs already resolved via
    tombstone entries, then appends a done tombstone for every remaining
    open entry.  Returns the count of newly resolved jobs.
    """
    path = log_path or DISPATCH_LOG
    entries = read_workboard_log(path)

    resolved_ids: set[str] = set()
    open_jobs: dict[str, dict] = {}

    for entry in entries:
        job = entry.get("job") or {}
        if entry.get("kind") == "tombstone":
            cid = job.get("correlation_id")
            if cid:
                resolved_ids.add(cid)
        elif entry.get("status") in {"queued", "in-progress"}:
            jid = job.get("id")
            if jid:
                open_jobs[jid] = entry

    to_close = {jid: e for jid, e in open_jobs.items() if jid not in resolved_ids}
    for jid, entry in to_close.items():
        action = (entry.get("job") or {}).get("action", "unknown")
        resolve_workboard_job(
            jid,
            outcome,
            source="workboard-batch-resolver",
            log_path=path,
        )
    return len(to_close)


if __name__ == "__main__":
    # CLI: python -m services.v2_workboard [--log PATH] [--outcome TEXT]
    import argparse

    parser = argparse.ArgumentParser(
        description="Batch-close all open workboard jobs in the dispatch log."
    )
    parser.add_argument("--log", default=None, help="Path to dispatch log (default: WORKBOARD_DISPATCH_LOG env or repo default)")
    parser.add_argument("--outcome", default="batch-closed", help="Outcome label to record on each tombstone")
    args = parser.parse_args()

    log_path = Path(args.log) if args.log else None
    closed = _batch_resolve_log(log_path=log_path, outcome=args.outcome)
    print(f"Resolved {closed} open job(s).")
    sys.exit(0)
