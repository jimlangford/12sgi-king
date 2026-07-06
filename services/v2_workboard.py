import json
import os
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
    DISPATCH_LOG.parent.mkdir(parents=True, exist_ok=True)
    with DISPATCH_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry
