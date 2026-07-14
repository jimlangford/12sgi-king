import importlib
import json
import os
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
        self.assertIsInstance(done.get("transition_history"), list)

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

    def test_transition_history_suppresses_duplicate_transitions(self):
        from services.job_envelope import build_job_envelope, transition_job_envelope

        env = build_job_envelope(
            domain="gpu-router",
            service="gpu-router",
            action="gpu.infer",
            state="pending",
        )
        running = transition_job_envelope(env, "running", actor="worker-1", engine="gpu", reason="claim")
        running_again = transition_job_envelope(running, "running", actor="worker-1", engine="gpu", reason="claim")

        self.assertEqual(running_again["state"], "running")
        self.assertEqual(len(running_again["transition_history"]), 1)
        self.assertEqual(running_again["transition_history"][0]["to_state"], "running")

    def test_transition_history_truncates_to_configured_limit(self):
        from services.job_envelope import transition_history_policy

        policy = transition_history_policy()
        max_entries = policy["max_entries"]
        env = {
            "domain": "gpu-router",
            "service": "gpu-router",
            "action": "gpu.infer",
            "state": "running",
            "transition_history": [
                {"from_state": "pending", "to_state": "running", "ts": i, "actor": "", "engine": "", "reason": "", "evidence_hash": ""}
                for i in range(max_entries + 5)
            ],
        }
        from services.job_envelope import normalise_envelope

        normalised = normalise_envelope(env, domain="gpu-router", fallback_state="running")
        self.assertEqual(len(normalised["transition_history"]), max_entries)
        self.assertEqual(normalised["transition_history"][0]["ts"], 5)

    def test_contract_declares_authoritative_state_and_transition_history_schema(self):
        contract = json.loads((ROOT / "config" / "canonical_job_contract.v2.json").read_text(encoding="utf-8"))
        self.assertEqual(contract["lifecycle_authority"], "domain_status_authoritative")
        required = contract["transition_history"]["entry_schema"]["required"]
        self.assertIn("from_state", required)
        self.assertIn("to_state", required)
        self.assertIn("evidence_hash", required)
        self.assertGreaterEqual(contract["transition_history"]["max_entries"], 1)

    def test_tenant_profiles_document_distinct_state_paths(self):
        contract = json.loads((ROOT / "config" / "canonical_job_contract.v2.json").read_text(encoding="utf-8"))
        tenant_profiles = contract["tenant_state_profiles"]
        self.assertIn("civic", tenant_profiles)
        self.assertIn("media", tenant_profiles)
        self.assertIn("gpu", tenant_profiles)
        self.assertNotEqual(
            tenant_profiles["civic"]["example_state_path"],
            tenant_profiles["media"]["example_state_path"],
        )

    def test_gpu_domain_rejects_media_only_state_names(self):
        from services.job_envelope import build_job_envelope, transition_job_envelope

        env = build_job_envelope(
            domain="gpu-router",
            service="gpu-router",
            action="gpu.infer",
            state="pending",
        )
        with self.assertRaises(ValueError):
            transition_job_envelope(env, "reference_ready")


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

    def test_legacy_workboard_entry_without_envelope_is_still_readable(self):
        legacy_entry = {
            "ts": 1,
            "iso": "2026-01-01 00:00:00",
            "schema": "workboard-job-v2",
            "source": "legacy",
            "kind": "job",
            "lane": "engineering",
            "status": "queued",
            "event": "LEGACY",
            "job": {
                "id": "legacy-job",
                "action": "legacy.action",
                "status": "queued",
                "payload": {"tenant_id": "legacy"},
            },
        }
        self.log_path.write_text(json.dumps(legacy_entry) + "\n", encoding="utf-8")
        rows = self.wb.read_workboard_log(self.log_path)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["job"]["id"], "legacy-job")
        self.assertEqual(rows[0]["status"], "queued")
        self.assertNotIn("envelope", rows[0]["job"])


class TestStudioAssetsCanonicalEnvelope(unittest.TestCase):
    def test_studio_emit_keeps_status_and_envelope_state_aligned(self):
        import services.studio_assets.app.main as studio_main
        import services.v2_workboard as wb

        captured = {}
        original_emit = wb.emit_workboard_job

        def _capture_emit(**kwargs):
            captured.update(kwargs)
            return {"job": {"id": "captured-job"}}

        wb.emit_workboard_job = _capture_emit
        try:
            studio_main._emit(
                "studio.index.rescanned",
                "STUDIO ASSET INDEX: 1 assets",
                {"total": 1},
                status="done",
            )
        finally:
            wb.emit_workboard_job = original_emit

        envelope = captured["payload"]["job_envelope"]
        self.assertEqual(captured["status"], "done")
        self.assertEqual(envelope["state"], "done")
        self.assertEqual(envelope["domain"], "studio-assets")


class TestStudioAssetsLegacyProjectCompatibility(unittest.TestCase):
    def test_legacy_project_record_without_new_fields_remains_readable(self):
        with tempfile.TemporaryDirectory(prefix="studio-legacy-") as tmp:
            registry_path = Path(tmp) / "tenant_registry.json"
            registry_path.write_text(
                json.dumps(
                    {
                        "creative_tenants": [{"id": "legacy-project", "name": "Legacy Project"}],
                        "counts": {"creative": 1},
                    }
                ),
                encoding="utf-8",
            )
            original = os.environ.get("STUDIO_REGISTRY_PATH")
            os.environ["STUDIO_REGISTRY_PATH"] = str(registry_path)
            try:
                import services.studio_assets.app.project_api as project_api

                importlib.reload(project_api)
                project = project_api.get_project("legacy-project")
            finally:
                if original is None:
                    os.environ.pop("STUDIO_REGISTRY_PATH", None)
                else:
                    os.environ["STUDIO_REGISTRY_PATH"] = original
            self.assertEqual(project["id"], "legacy-project")
            self.assertEqual(project["name"], "Legacy Project")


if __name__ == "__main__":
    unittest.main()
