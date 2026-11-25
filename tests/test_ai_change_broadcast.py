from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.announce_ai_change import append_notice, build_notice


class AiChangeBroadcastTests(unittest.TestCase):
    def test_builds_sanitized_notice_for_known_agents(self):
        notice = build_notice(
            actor="Codex",
            summary="Added shared AI change feed",
            boundary="BRIDGE",
            audiences=["codex", "claude-code", "github-copilot", "local-ai"],
            changed_paths=["docs/AI_CHANGE_BROADCAST.md"],
            evidence="Contract and publisher added",
        )
        self.assertEqual(notice["schema"], "12sgi-ai-change-v1")
        self.assertEqual(len(notice["audiences"]), 4)
        self.assertIsNone(notice["commit"])

    def test_rejects_private_boundary_and_credentials(self):
        base = dict(actor="Codex", boundary="BRIDGE", audiences=["codex"],
                    changed_paths=[], evidence="Not deployed")
        with self.assertRaisesRegex(ValueError, "only PUBLIC or BRIDGE"):
            build_notice(**{**base, "summary": "Private work", "boundary": "PRIVATE"})
        with self.assertRaisesRegex(ValueError, "credential"):
            build_notice(**{**base, "summary": "token=supersecretvalue"})

    def test_rejects_private_or_absolute_paths(self):
        base = dict(actor="Codex", summary="Change", boundary="PUBLIC",
                    audiences=["codex"], evidence="Done")
        with self.assertRaisesRegex(ValueError, "private path"):
            build_notice(**{**base, "changed_paths": ["reports/_status/private.json"]})
        with self.assertRaisesRegex(ValueError, "repository-relative"):
            build_notice(**{**base, "changed_paths": ["C:\\Users\\owner\\secret.txt"]})

    def test_appends_one_jsonl_record(self):
        notice = build_notice(actor="Codex", summary="Feed test", boundary="PUBLIC",
                              audiences=["codex"], changed_paths=[], evidence="Unit test")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "feed.jsonl"
            append_notice(notice, path)
            records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(records, [notice])


if __name__ == "__main__":
    unittest.main()
