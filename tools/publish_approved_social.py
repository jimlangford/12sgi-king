#!/usr/bin/env python3
"""publish_approved_social.py — the PUBLISH step for social_drafts batches, per
docs/SOCIAL_CONNECTORS.md's BUILD -> STAGE -> REVIEW -> PUBLISH -> LOG -> FAIL CLOSED lifecycle.

This is the ONLY script that actually calls a posting connector for the drafts staged by
tools/stage_social_drafts.py. It never runs on its own (no scheduler, no autopost) — it takes
an explicit --job-id (printed by stage_social_drafts.py / visible on
king_public_src/social_drafts_board.html) and REFUSES to post unless that exact job id has an
"approved" tombstone in the dispatch log (written by
services.v2_workboard.approve_workboard_job(), i.e. `python -m services.v2_workboard --approve
<job_id> --approver <name>`). FAIL CLOSED: no tombstone -> nothing posted, ever.

ROUTING (owner decisions, 2026-07-11):
  facebook / instagram / linkedin -> watchers/own_channel_post.py (local self-hosted Postiz,
      free, docker-compose.postiz.yml). Actually posts once config/own_channels.json has the
      channel connected + enabled.
  x (Twitter)                     -> config/x_manual_queue.json (manual lane; X's write API
      has no free tier as of 2026 -- pay-per-call -- so this repo does not auto-post to X).
  youtube                         -> config/youtube_manual_queue.json (these drafts are
      title/description/thumbnail CONCEPTS with no rendered video asset yet; real reel
      posting already exists separately via watchers/agenda_autopost.py).

USAGE:
  python tools/publish_approved_social.py --list-approved
  python tools/publish_approved_social.py --job-id <uuid> --batch config/social_drafts/<file>.json --platform facebook
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "watchers"))

from services.v2_workboard import DISPATCH_LOG  # noqa: E402
import own_channel_post  # noqa: E402

MANUAL_QUEUES = {
    "x": ROOT / "config" / "x_manual_queue.json",
    "youtube": ROOT / "config" / "youtube_manual_queue.json",
}
PUBLISH_LOG = ROOT / "reports" / "_status" / "social_publish_log.jsonl"
OWN_CHANNEL_PLATFORMS = {"facebook", "instagram", "linkedin"}


def _iter_dispatch_log():
    if not DISPATCH_LOG.exists():
        return
    with DISPATCH_LOG.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except Exception:
                continue


def is_approved(job_id: str) -> bool:
    for entry in _iter_dispatch_log():
        job = entry.get("job", {})
        if entry.get("status") == "approved" and job.get("correlation_id") == job_id:
            return True
    return False


def list_approved():
    seen = []
    for entry in _iter_dispatch_log():
        job = entry.get("job", {})
        if entry.get("status") == "approved":
            seen.append(job.get("correlation_id"))
    return seen


def _load_draft(batch_path: Path, platform: str) -> dict | None:
    batch = json.loads(batch_path.read_text(encoding="utf-8"))
    for d in batch.get("drafts", []):
        if d.get("platform") == platform:
            return d
    return None


def _draft_text(platform: str, draft: dict) -> str:
    if platform == "youtube":
        return "%s\n\n%s" % (draft.get("title", ""), draft.get("description", ""))
    copy = draft.get("copy", "")
    tags = draft.get("hashtags") or []
    if tags:
        copy = copy + "\n\n" + " ".join(tags)
    return copy


def _log_publish(rec: dict):
    PUBLISH_LOG.parent.mkdir(parents=True, exist_ok=True)
    with PUBLISH_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def _queue_manual(platform: str, job_id: str, batch_id: str, draft: dict) -> dict:
    qpath = MANUAL_QUEUES[platform]
    q = json.loads(qpath.read_text(encoding="utf-8")) if qpath.exists() else []
    if any(e.get("job_id") == job_id for e in q):
        return {"status": "already_queued", "platform": platform, "job_id": job_id}
    q.append({
        "n": len(q) + 1,
        "job_id": job_id,
        "batch_id": batch_id,
        "platform": platform,
        "draft": draft,
        "posted": None,
        "posted_url": "",
        "queued_at": int(time.time()),
    })
    qpath.parent.mkdir(parents=True, exist_ok=True)
    qpath.write_text(json.dumps(q, indent=1, ensure_ascii=False), encoding="utf-8")
    return {"status": "queued_manual", "platform": platform, "job_id": job_id, "queue": str(qpath)}


def publish(job_id: str, batch_path: Path, platform: str) -> dict:
    if not is_approved(job_id):
        rec = {"status": "refused", "reason": "no 'approved' tombstone found for job_id %s "
               "(run: python -m services.v2_workboard --approve %s --approver <name>)" % (job_id, job_id),
               "job_id": job_id, "platform": platform}
        _log_publish(rec)
        return rec
    draft = _load_draft(batch_path, platform)
    if draft is None:
        rec = {"status": "error", "reason": "no '%s' draft found in %s" % (platform, batch_path),
               "job_id": job_id, "platform": platform}
        _log_publish(rec)
        return rec
    if platform in MANUAL_QUEUES:
        rec = _queue_manual(platform, job_id, batch_path.stem, draft)
    elif platform in OWN_CHANNEL_PLATFORMS:
        text = _draft_text(platform, draft)
        rec = own_channel_post.post(platform, text)
        rec = dict(rec, job_id=job_id, batch=str(batch_path))
    else:
        rec = {"status": "error", "reason": "unknown platform '%s'" % platform, "job_id": job_id}
    _log_publish(rec)
    return rec


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--job-id", default="")
    ap.add_argument("--batch", default="")
    ap.add_argument("--platform", default="", choices=["facebook", "instagram", "linkedin", "x", "youtube"])
    ap.add_argument("--list-approved", action="store_true")
    a = ap.parse_args()
    if a.list_approved:
        approved = list_approved()
        print("Approved job ids in dispatch log (%d):" % len(approved))
        for jid in approved:
            print(" -", jid)
        return 0
    if not (a.job_id and a.batch and a.platform):
        ap.print_help()
        return 1
    result = publish(a.job_id, Path(a.batch), a.platform)
    print(json.dumps(result, ensure_ascii=False, indent=1))
    return 0 if result.get("status") not in ("error", "refused") else 1


if __name__ == "__main__":
    sys.exit(main())
