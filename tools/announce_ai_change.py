"""Append a sanitized, repository-visible change notice for collaborating AIs.

This writes a reviewable feed entry only. It does not call external AI APIs,
post to GitHub, or publish code.
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
FEED = ROOT / "docs" / "AI_CHANGE_FEED.jsonl"
AUDIENCES = {"local-ai", "claude-code", "codex", "github-copilot"}
BOUNDARIES = {"PUBLIC", "BRIDGE"}
SECRET = re.compile(
    r"(?i)(?:bearer\s+\S+|(?:api[_-]?key|token|password|secret)\s*[:=]\s*\S+|"
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----|gh[pousr]_[A-Za-z0-9_]{20,})"
)
PRIVATE_PATH = re.compile(
    r"(?i)(?:^|/)(?:\.env(?:\.|$)|secrets?/|credentials?/|private/|owner[_-]?only/|"
    r"reports/_status/|\.dispatch_log\.jsonl$)"
)


def _safe_text(value: str, label: str) -> str:
    value = " ".join(value.split())
    if not value:
        raise ValueError(f"{label} is required")
    if SECRET.search(value):
        raise ValueError(f"{label} looks like it contains a credential; notice not written")
    if re.search(r"(?:[A-Za-z]:\\|/Users/|/home/|\\\\[^\\]+\\)", value):
        raise ValueError(f"{label} must not include local absolute paths")
    return value


def build_notice(*, actor: str, summary: str, boundary: str, audiences: list[str],
                 changed_paths: list[str], evidence: str, commit: str = "") -> dict:
    boundary = boundary.upper().strip()
    if boundary not in BOUNDARIES:
        raise ValueError("only PUBLIC or BRIDGE notices may enter the shared feed")
    normalized_audiences = sorted({a.strip().lower() for a in audiences})
    if not normalized_audiences or not set(normalized_audiences) <= AUDIENCES:
        raise ValueError(f"audiences must be selected from {sorted(AUDIENCES)}")
    paths = []
    for path in changed_paths:
        path = path.strip().replace("\\", "/")
        if not path or path.startswith("/") or re.match(r"^[A-Za-z]:", path) or ".." in path.split("/"):
            raise ValueError("changed paths must be repository-relative")
        if PRIVATE_PATH.search(path):
            raise ValueError(f"private path cannot be included in shared feed: {path}")
        paths.append(path)
    return {
        "schema": "12sgi-ai-change-v1",
        "event_id": str(uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "actor": _safe_text(actor, "actor"),
        "boundary": boundary,
        "audiences": normalized_audiences,
        "summary": _safe_text(summary, "summary"),
        "changed_paths": sorted(set(paths)),
        "evidence": _safe_text(evidence, "evidence"),
        "commit": _safe_text(commit, "commit") if commit else None,
        "delivery": "shared-feed; external chat delivery not configured",
    }


def append_notice(notice: dict, path: Path = FEED) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(notice, ensure_ascii=False, sort_keys=True) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--actor", required=True, help="Agent or system making the change")
    parser.add_argument("--summary", required=True)
    parser.add_argument("--boundary", required=True, choices=sorted(BOUNDARIES))
    parser.add_argument("--audience", action="append", required=True, choices=sorted(AUDIENCES))
    parser.add_argument("--path", action="append", default=[], dest="paths", help="Safe repo-relative changed path")
    parser.add_argument("--evidence", required=True, help="Verification or current status")
    parser.add_argument("--commit", default="", help="Optional commit SHA")
    args = parser.parse_args()
    try:
        notice = build_notice(actor=args.actor, summary=args.summary, boundary=args.boundary,
                             audiences=args.audience, changed_paths=args.paths,
                             evidence=args.evidence, commit=args.commit)
        append_notice(notice)
    except ValueError as exc:
        parser.error(str(exc))
    print(json.dumps(notice, ensure_ascii=False, indent=2))
    print(f"Appended to {FEED.relative_to(ROOT)}. Commit/push the feed for GitHub-connected agents to read it.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
