"""
Regression tests for watchers/self_develop.py (issue #365 fix).

Verifies:
  - One canonical workboard item per gate (dedup by fingerprint)
  - Suppression after repeated identical evaluations
  - Suppression notice fired at burst threshold
  - Truthful advance_ready=False while gates are open
  - Streak advances only on genuine state transitions
  - State file is written correctly
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import watchers.self_develop as sd


def _make_gates(status: str = "open", evidence: dict | None = None) -> dict:
    return {
        "version": "beta-5",
        "gates": [
            {
                "id": "bill9_rollcall",
                "label": "Bill 9 Roll-Call Verification",
                "status": status,
                "action": "Ingest and verify the authoritative Bill 9 roll-call record.",
                "completion_evidence_fields": [
                    "source_id", "source_url", "meeting_date", "member_votes",
                    "abstentions", "recusals", "absences",
                    "source_hash", "ingest_timestamp", "validation_result",
                ],
                "evidence": evidence or {},
            }
        ],
    }


class TestSelfDevelopDedup(unittest.TestCase):
    """Core dedup and state-based behavior."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._tmp_dir = Path(self._tmp.name)
        self._gate_file = self._tmp_dir / "version_gate.json"
        self._state_file = self._tmp_dir / "self_develop.json"
        self._dispatch_file = self._tmp_dir / "dispatch.jsonl"

        # Patch module-level paths and workboard
        patch.object(sd, "GATE_FILE", self._gate_file).start()
        patch.object(sd, "STATE_FILE", self._state_file).start()
        patch.object(sd, "DISPATCH_LOG", self._dispatch_file).start()
        patch.object(sd, "_HAS_WORKBOARD", False).start()

    def tearDown(self):
        patch.stopall()
        self._tmp.cleanup()

    def _run(self, gate_data: dict) -> dict:
        self._gate_file.write_text(json.dumps(gate_data), encoding="utf-8")
        return sd.evaluate()

    def _dispatch_entries(self) -> list[dict]:
        if not self._dispatch_file.exists():
            return []
        entries = []
        for line in self._dispatch_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                entries.append(json.loads(line))
        return entries

    def test_first_run_emits_exactly_one_job(self):
        gate_data = _make_gates("open")
        result = self._run(gate_data)

        entries = self._dispatch_entries()
        jobs = [e for e in entries if e.get("kind") == "job"]
        self.assertEqual(len(jobs), 1, "Exactly one workboard job on first run")
        self.assertEqual(jobs[0]["source"], "selfdev:bill9_rollcall")

    def test_second_run_same_state_no_new_job(self):
        gate_data = _make_gates("open")
        self._run(gate_data)
        self._run(gate_data)

        entries = self._dispatch_entries()
        jobs = [e for e in entries if e.get("kind") == "job"]
        self.assertEqual(len(jobs), 1, "No duplicate job on second run with same state")

    def test_burst_suppression_fires_notice_once(self):
        gate_data = _make_gates("open")
        threshold = sd.SUPPRESS_BURST_THRESHOLD
        # First run emits job; next `threshold` runs are suppressed
        for _ in range(threshold + 1):
            self._run(gate_data)

        entries = self._dispatch_entries()
        notices = [e for e in entries if e.get("kind") == "notice"]
        self.assertEqual(len(notices), 1, "Exactly one suppression notice at burst threshold")
        self.assertIn("HEALED", notices[0]["event"])
        self.assertIn("bill9_rollcall", notices[0]["event"])

    def test_advance_ready_false_when_gate_open(self):
        gate_data = _make_gates("open")
        result = self._run(gate_data)
        self.assertFalse(result["advance_ready"])
        self.assertIn("bill9_rollcall", result["graduation_blocked_by"])

    def test_advance_ready_true_when_all_gates_closed(self):
        gate_data = _make_gates("closed")
        result = self._run(gate_data)
        self.assertTrue(result["advance_ready"])
        self.assertEqual(result["graduation_blocked_by"], [])

    def test_streak_advances_on_gate_close(self):
        # First run: gate is open (streak should not advance)
        self._run(_make_gates("open"))
        state_open = json.loads(self._state_file.read_text())
        streak_before = state_open["qualification_streak"]

        # Second run: gate is now closed (streak should advance by 1)
        self._run(_make_gates("closed"))
        state_closed = json.loads(self._state_file.read_text())
        self.assertEqual(
            state_closed["qualification_streak"],
            streak_before + 1,
            "Streak advances exactly once when gate closes",
        )

    def test_streak_capped_at_required(self):
        # Close the gate multiple times (by changing evidence each time so fingerprint changes)
        for i in range(sd.STREAK_REQUIRED + 2):
            self._run(_make_gates("closed", evidence={"run": i}))
        state = json.loads(self._state_file.read_text())
        self.assertLessEqual(
            state["qualification_streak"],
            sd.STREAK_REQUIRED,
            "Streak is capped at STREAK_REQUIRED",
        )

    def test_lifetime_passes_not_capped(self):
        for i in range(sd.STREAK_REQUIRED + 5):
            self._run(_make_gates("closed", evidence={"run": i}))
        state = json.loads(self._state_file.read_text())
        self.assertGreater(
            state["lifetime_passes"],
            sd.STREAK_REQUIRED,
            "lifetime_passes is not capped at STREAK_REQUIRED",
        )

    def test_fingerprint_changes_on_evidence_update(self):
        self._run(_make_gates("open", evidence={}))
        jobs_before = len([e for e in self._dispatch_entries() if e.get("kind") == "job"])

        # Update evidence — fingerprint must change
        self._run(_make_gates("open", evidence={"source_hash": "abc123"}))
        jobs_after = len([e for e in self._dispatch_entries() if e.get("kind") == "job"])

        self.assertEqual(jobs_after, jobs_before + 1, "New job emitted when evidence changes")

    def test_dry_run_writes_nothing(self):
        gate_data = _make_gates("open")
        self._gate_file.write_text(json.dumps(gate_data), encoding="utf-8")
        sd.evaluate(dry_run=True)

        self.assertFalse(self._state_file.exists(), "State file not written on dry_run")
        self.assertFalse(self._dispatch_file.exists(), "Dispatch log not written on dry_run")

    def test_health_score_reflects_open_gates(self):
        result = self._run(_make_gates("open"))
        self.assertEqual(result["health_score"], 0)

    def test_health_score_reflects_closed_gates(self):
        result = self._run(_make_gates("closed"))
        self.assertEqual(result["health_score"], 100)

    def test_state_file_persists_gate_fingerprint(self):
        gate_data = _make_gates("open")
        self._run(gate_data)
        state = json.loads(self._state_file.read_text())
        self.assertIn("bill9_rollcall", state["gates"])
        fp = state["gates"]["bill9_rollcall"]["fingerprint"]
        self.assertEqual(len(fp), 64, "Fingerprint is a SHA-256 hex digest (64 chars)")


class TestSelfDevelopTransitionHistory(unittest.TestCase):
    """Transition history audit trail."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._tmp_dir = Path(self._tmp.name)
        self._gate_file = self._tmp_dir / "version_gate.json"
        self._state_file = self._tmp_dir / "self_develop.json"
        self._dispatch_file = self._tmp_dir / "dispatch.jsonl"

        patch.object(sd, "GATE_FILE", self._gate_file).start()
        patch.object(sd, "STATE_FILE", self._state_file).start()
        patch.object(sd, "DISPATCH_LOG", self._dispatch_file).start()
        patch.object(sd, "_HAS_WORKBOARD", False).start()

    def tearDown(self):
        patch.stopall()
        self._tmp.cleanup()

    def _run(self, gate_data: dict) -> dict:
        self._gate_file.write_text(json.dumps(gate_data), encoding="utf-8")
        return sd.evaluate()

    def _gate_state(self) -> dict:
        return json.loads(self._state_file.read_text())["gates"]["bill9_rollcall"]

    def test_first_transition_recorded(self):
        self._run(_make_gates("open"))
        history = self._gate_state()["transition_history"]
        self.assertEqual(len(history), 1)
        t = history[0]
        self.assertEqual(t["gate"], "bill9_rollcall")
        self.assertEqual(t["previous"], "unknown")
        self.assertEqual(t["current"], "open")
        self.assertEqual(t["worker"], "self_develop")
        self.assertIn("changed_at", t)
        self.assertIn("fingerprint", t)
        self.assertIn("evidence_hash", t)

    def test_transition_on_gate_close(self):
        self._run(_make_gates("open"))
        self._run(_make_gates("closed"))
        history = self._gate_state()["transition_history"]
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0]["current"], "open")
        self.assertEqual(history[1]["previous"], "open")
        self.assertEqual(history[1]["current"], "closed")

    def test_no_duplicate_transition_on_same_state(self):
        self._run(_make_gates("open"))
        self._run(_make_gates("open"))
        history = self._gate_state()["transition_history"]
        self.assertEqual(len(history), 1, "Suppressed run must not append a transition")

    def test_transition_history_capped_at_limit(self):
        limit = sd.TRANSITION_HISTORY_LIMIT
        for i in range(limit + 5):
            self._run(_make_gates("open", evidence={"run": i}))
        history = self._gate_state()["transition_history"]
        self.assertLessEqual(len(history), limit)

    def test_evidence_hash_changes_with_evidence(self):
        self._run(_make_gates("open", evidence={}))
        self._run(_make_gates("open", evidence={"source_hash": "abc"}))
        history = self._gate_state()["transition_history"]
        self.assertEqual(len(history), 2)
        self.assertNotEqual(history[0]["evidence_hash"], history[1]["evidence_hash"])

    def test_transition_in_result_dict(self):
        result = self._run(_make_gates("open"))
        gate_result = result["gate_results"][0]
        self.assertIn("transition", gate_result)
        t = gate_result["transition"]
        self.assertEqual(t["gate"], "bill9_rollcall")
        self.assertEqual(t["worker"], "self_develop")

    def test_dry_run_has_transition_but_no_state_written(self):
        self._gate_file.write_text(json.dumps(_make_gates("open")), encoding="utf-8")
        result = sd.evaluate(dry_run=True)
        gate_result = result["gate_results"][0]
        self.assertIn("transition", gate_result)
        self.assertFalse(self._state_file.exists(), "State file must not be written on dry_run")


if __name__ == "__main__":
    unittest.main()
