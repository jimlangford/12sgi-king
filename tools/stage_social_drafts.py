#!/usr/bin/env python3
"""stage_social_drafts.py — stage a batch of social-post drafts as creative-lane workboard jobs.

WHAT THIS IS.
  A thin bridge between the social-content drafting work (done in chat, reviewed by the owner)
  and the existing creative/output-lane workboard in services/v2_workboard.py. It reads a JSON
  batch file of per-platform drafts and emits one "pending-approval" creative-lane job per
  platform into the dispatch log (.dispatch_log.jsonl by default). It does NOT post anything to
  any platform — creative lane jobs are never auto-healed and always require an explicit owner
  approve_workboard_job()/reject_workboard_job() call (see services/v2_workboard.py), which the
  owner triggers from king_public_src/social_drafts_board.html or the CLI flags on
  services/v2_workboard.py (--approve / --reject).

BATCH FILE SHAPE (see config/social_drafts/*.json for a real example):
  {
    "batch_id": "2026-07-10-wildfire-records",
    "theme": "short human label for this run",
    "drafts": [
      {"platform": "x", "copy": "...", "hashtags": ["...", "..."]},
      {"platform": "instagram", "copy": "...", "hashtags": [...], "thumbnail_text": "..."},
      {"platform": "linkedin", "copy": "...", "hashtags": [...]},
      {"platform": "facebook", "copy": "...", "hashtags": [...]},
      {"platform": "youtube", "title": "...", "description": "...", "thumbnail_text": "..."}
    ]
  }

Usage:
  python tools/stage_social_drafts.py config/social_drafts/2026-07-10-wildfire-records.json
  python -m services.v2_workboard --pending   # confirm the staged items show up
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.v2_workboard import emit_workboard_job, _load_owner_policy  # noqa: E402

sys.path.insert(0, str(ROOT / "tools"))


def _maybe_auto_publish(entry: dict, batch_path: Path, platform: str) -> None:
    """If the owner has opted into config/owner_policy.json auto_publish, immediately run
    the PUBLISH step for this just-auto-approved job. No-op unless emit_workboard_job already
    auto-approved the entry (see services/v2_workboard.py). Still routes through
    tools/publish_approved_social.py, so missing channel credentials still fail closed —
    this only removes the human-click step, it does not fabricate connector auth.
    """
    if not entry.get("auto_approved") or not _load_owner_policy().get("auto_publish"):
        return
    if platform not in ("facebook", "instagram", "linkedin", "x", "youtube"):
        return
    import publish_approved_social as pub  # local import: avoids import cost when unused
    result = pub.publish(entry["job"]["id"], batch_path, platform)
    print(f"  auto-publish [{platform}] -> {result.get('status')}")


def stage_batch(batch_path: Path) -> list[dict]:
    batch = json.loads(batch_path.read_text(encoding="utf-8"))
    batch_id = batch.get("batch_id") or batch_path.stem
    theme = batch.get("theme", "")
    entries = []
    for draft in batch.get("drafts", []):
        platform = draft.get("platform", "unknown")
        entry = emit_workboard_job(
            source="stage_social_drafts",
            action="social-draft",
            event=f"Social draft ready for review: {platform} — {theme or batch_id}",
            lane="creative",
            status="pending-approval",
            priority="normal",
            kind="job",
            payload={"batch_id": batch_id, "theme": theme, "platform": platform, "draft": draft},
        )
        entries.append(entry)
        tag = "auto-approved" if entry.get("auto_approved") else "pending-approval"
        print(f"staged [{platform}] job={entry['job']['id']} ({tag})")
        _maybe_auto_publish(entry, batch_path, platform)
    return entries


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: python tools/stage_social_drafts.py <batch_file.json>")
        return 1
    batch_path = Path(sys.argv[1])
    if not batch_path.exists():
        print(f"batch file not found: {batch_path}")
        return 1
    entries = stage_batch(batch_path)
    print(f"Staged {len(entries)} draft(s) as pending-approval creative jobs.")
    print("Review + approve on your owner device: king_public_src/social_drafts_board.html")
    print("Or from the CLI: python -m services.v2_workboard --pending")
    return 0


if __name__ == "__main__":
    sys.exit(main())
