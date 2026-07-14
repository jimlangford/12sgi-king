import importlib
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


class TestCanonicalJobContract(unittest.TestCase):
    def test_build_and_transition_envelope(self):
        from services.job_envelope import build_job_envelope, transition_job_envelope

        env = build_job_envelope(
            domain="workboard",
            service="v2_workboard",
            action="unit-test",
            state="queued",
            payload={"x": 1},
            lane="engineering",
        )
        self.assertEqual(env["schema"], "canonical-job-envelope-v2")
        self.assertEqual(env["state"], "queued")
        done = transition_job_envelope(env, "done")
        self.assertEqual(done["state"], "done")

    def test_invalid_transition_raises(self):
        from services.job_envelope import build_job_envelope, transition_job_envelope

        env = build_job_envelope(
            domain="gpu-router",
            service="gpu-router",
            action="gpu.infer",
            state="pending",
        )
        with self.assertRaises(ValueError):
            transition_job_envelope(env, "archived")


class TestWorkboardCanonicalEnvelope(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="wb-envelope-")
        self.log_path = Path(self.tmp.name) / "dispatch.jsonl"
        import services.v2_workboard as wb_module
        importlib.reload(wb_module)
        self.wb = wb_module

    def tearDown(self):
        self.tmp.cleanup()

    def test_emit_job_adds_canonical_envelope(self):
        entry = self.wb.emit_workboard_job(
            source="unit",
            action="job.created",
            event="unit event",
            lane="engineering",
            status="queued",
            payload={"hello": "world"},
            log_path=self.log_path,
        )
        envelope = entry["job"]["envelope"]
        self.assertEqual(envelope["domain"], "workboard")
        self.assertEqual(envelope["state"], "queued")
        self.assertEqual(envelope["service"], "v2_workboard")

    def test_resolve_job_enforces_transition_and_sets_done_envelope(self):
        entry = self.wb.emit_workboard_job(
            source="unit",
            action="job.created",
            event="unit event",
            lane="engineering",
            status="queued",
            log_path=self.log_path,
        )
        tombstone = self.wb.resolve_workboard_job(
            entry["job"]["id"],
            outcome="unit-resolved",
            log_path=self.log_path,
        )
        self.assertEqual(tombstone["status"], "done")
        self.assertEqual(tombstone["job"]["envelope"]["state"], "done")


if __name__ == "__main__":
    unittest.main()
