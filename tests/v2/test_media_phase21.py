import importlib.util
import json
import os
import sqlite3
import sys
import tempfile
import time
import unittest
from hashlib import sha256
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
GPU_MAIN = ROOT / "services" / "gpu_router" / "app" / "main.py"


def _load_gpu(db_path: str):
    saved = dict(os.environ)
    try:
        os.environ.update(
            {
                "GPU_ROUTER_DB_PATH": db_path,
                "COMMIT_SHA": "media-test-sha",
                "BUILD_TIMESTAMP": "2026-07-14T00:00:00Z",
                "ENVIRONMENT": "test",
            }
        )
        spec = importlib.util.spec_from_file_location(f"gpu_router_media_{time.time_ns()}", GPU_MAIN)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.require_claims = lambda **kwargs: {
            "sub": "owner-test",
            "role": "Owner",
            "tenant_id": "",
            "scopes": ["gpu:infer", "gpu:read", "ops:owner"],
        }
        return module
    finally:
        os.environ.clear()
        os.environ.update(saved)


class MediaPhase21Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="media-phase21-")
        self.db_path = str(Path(self.tmp.name) / "gpu-router.db")
        self.module = _load_gpu(self.db_path)
        self.client = TestClient(self.module.app)
        self.module._run_job = lambda job: ("done", {"response": "ok"}, None)

    def tearDown(self):
        self.tmp.cleanup()

    def _auth(self):
        return {"Authorization": "******"}

    def _connect(self):
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _create_media_render(self):
        payload = {
            "client_id": "studio",
            "tenant_id": "media",
            "model": "kandinsky-local",
            "prompt": "render scene",
            "media_job_type": "scene_render",
            "capability": "image_generation",
            "workflow_id": "kandinsky5_local_image",
            "resolution": "768x512",
            "frame_count": 1,
            "adapter_set": ["ipadapter_faceid_lock"],
            "lora_set": ["lora_zone_training_support"],
            "model_residency": True,
            "options": {"scene_id": "scene-1"},
            "evidence": {"artifact_uri": "artifact://seed"},
        }
        resp = self.client.post("/api/v2/gpu/infer", json=payload, headers=self._auth())
        self.assertEqual(resp.status_code, 200)
        return resp.json()["job_id"]

    def _transition(self, job_id, to_state, evidence=None, expect=200):
        body = {"to_state": to_state, "reason": "test", "evidence": evidence or {}}
        resp = self.client.post(f"/api/v2/gpu/media/jobs/{job_id}/transition", json=body, headers=self._auth())
        self.assertEqual(resp.status_code, expect)
        return resp

    def test_valid_media_render_path_succeeds(self):
        job_id = self._create_media_render()
        self._transition(job_id, "qc_passed")
        self._transition(job_id, "approval_pending")
        self._transition(job_id, "approved")
        self._transition(job_id, "publish_ready")
        self._transition(job_id, "publishing")
        out = self._transition(
            job_id,
            "published",
            evidence={"output_hash": "hash-1", "provenance_hash": "prov-1", "artifact_uri": "artifact://final"},
        ).json()
        self.assertEqual(out["media_state"], "published")

    def test_render_cannot_publish_before_qc(self):
        job_id = self._create_media_render()
        resp = self._transition(job_id, "publish_ready", expect=409)
        self.assertEqual(resp.json()["detail"]["error"]["code"], "illegal_transition")

    def test_render_cannot_publish_before_approval(self):
        job_id = self._create_media_render()
        self._transition(job_id, "qc_passed")
        resp = self._transition(job_id, "publishing", expect=409)
        self.assertEqual(resp.json()["detail"]["error"]["code"], "illegal_transition")

    def test_rejected_render_cannot_enter_publishing(self):
        job_id = self._create_media_render()
        self._transition(job_id, "qc_passed")
        self._transition(job_id, "approval_pending")
        self._transition(job_id, "rejected")
        resp = self._transition(job_id, "publishing", expect=409)
        self.assertEqual(resp.json()["detail"]["error"]["code"], "illegal_transition")

    def test_media_only_states_rejected_for_gpu_infrastructure_jobs(self):
        payload = {"client_id": "studio", "tenant_id": "gpu", "model": "llama3", "prompt": "infra", "job_type": "ollama"}
        resp = self.client.post("/api/v2/gpu/infer", json=payload, headers=self._auth())
        self.assertEqual(resp.status_code, 200)
        job_id = resp.json()["job_id"]
        out = self._transition(job_id, "qc_passed", expect=409)
        self.assertEqual(out.json()["detail"]["error"]["code"], "illegal_transition")

    def test_civic_jobs_remain_unaffected(self):
        payload = {"client_id": "civic-signal", "tenant_id": "civic", "model": "llama3", "prompt": "hello", "job_type": "ollama"}
        resp = self.client.post("/api/v2/gpu/infer", json=payload, headers=self._auth())
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json().get("done"))

    def test_duplicate_media_transition_suppressed(self):
        job_id = self._create_media_render()
        self._transition(job_id, "qc_passed")
        with self._connect() as conn:
            before = conn.execute(
                "SELECT COUNT(*) FROM gpu_events WHERE event_type='media.transition' AND job_id=?",
                (job_id,),
            ).fetchone()[0]
        self._transition(job_id, "qc_passed")
        with self._connect() as conn:
            after = conn.execute(
                "SELECT COUNT(*) FROM gpu_events WHERE event_type='media.transition' AND job_id=?",
                (job_id,),
            ).fetchone()[0]
        self.assertEqual(after, before)

    def test_tenant_identity_survives_routing_render_qc_publish(self):
        job_id = self._create_media_render()
        self._transition(job_id, "qc_passed")
        self._transition(job_id, "approval_pending")
        self._transition(job_id, "approved")
        self._transition(job_id, "publish_ready")
        self._transition(job_id, "publishing")
        self._transition(job_id, "published", evidence={"output_hash": "h2", "provenance_hash": "p2", "artifact_uri": "artifact://x"})
        with self._connect() as conn:
            row = conn.execute("SELECT tenant_id, media_state FROM gpu_jobs WHERE id=?", (job_id,)).fetchone()
        self.assertEqual(row["tenant_id"], "media")
        self.assertEqual(row["media_state"], "published")

    def test_8gb_profile_rejects_over_safe_vram(self):
        payload = {
            "client_id": "studio",
            "tenant_id": "media",
            "model": "kandinsky-local",
            "prompt": "big render",
            "media_job_type": "scene_render",
            "capability": "image_generation",
            "workflow_id": "kandinsky5_local_image",
            "vram_required_mb": 9001,
            "options": {"scene_id": "scene-vram"},
        }
        resp = self.client.post("/api/v2/gpu/infer", json=payload, headers=self._auth())
        self.assertEqual(resp.status_code, 422)
        self.assertEqual(resp.json()["detail"]["error"]["code"], "gpu_profile_exceeded")

    def test_compatible_jobs_group_while_same_engine_resident(self):
        now = self.module._now_utc()
        with self._connect() as conn:
            for jid in ("a1", "a2", "b1"):
                conn.execute(
                    """
                    INSERT INTO gpu_jobs
                    (id, tenant_id, client_id, priority, job_type, model, prompt, status, created_at, available_at,
                     max_attempts, created_by, media_job_type, media_state, selected_engine, workflow_profile, resolution,
                     frame_count, adapter_set, lora_set, model_residency)
                    VALUES (?, 'media', 'studio', 1, 'comfyui', 'k', 'p', 'pending', ?, ?, 3, 'tester', 'scene_render', 'queued', ?, 'kandinsky5_local_image', '768x512', 1, '[]', '[]', 1)
                    """,
                    (jid, now, now, "kandinsky5_local" if jid != "b1" else "wan"),
                )
            conn.commit()
            self.module._gpu_resident_engine = "kandinsky5_local"
            first = self.module._claim_next_pending_job(conn, {"comfyui"}, "gpu-worker")
        self.assertIn(first["id"], {"a1", "a2"})

    def test_incompatible_engine_jobs_wait_until_unload(self):
        now = self.module._now_utc()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO gpu_jobs
                (id, tenant_id, client_id, priority, job_type, model, prompt, status, created_at, available_at, max_attempts, created_by, media_job_type, media_state, selected_engine)
                VALUES ('same-engine', 'media', 'studio', 1, 'comfyui', 'k', 'p', 'pending', ?, ?, 3, 'tester', 'scene_render', 'queued', 'kandinsky5_local')
                """,
                (now, now),
            )
            conn.execute(
                """
                INSERT INTO gpu_jobs
                (id, tenant_id, client_id, priority, job_type, model, prompt, status, created_at, available_at, max_attempts, created_by, media_job_type, media_state, selected_engine)
                VALUES ('other-engine', 'media', 'studio', 1, 'comfyui', 'k', 'p', 'pending', ?, ?, 3, 'tester', 'scene_render', 'queued', 'wan')
                """,
                (now, now),
            )
            conn.commit()
            self.module._gpu_resident_engine = "kandinsky5_local"
            first = self.module._claim_next_pending_job(conn, {"comfyui"}, "gpu-worker")
        self.assertEqual(first["id"], "same-engine")

    def test_legacy_studio_assets_remain_readable(self):
        with tempfile.TemporaryDirectory(prefix="studio-legacy-") as tmp:
            registry = Path(tmp) / "tenant_registry.json"
            registry.write_text(json.dumps({"creative_tenants": [{"id": "legacy", "name": "Legacy"}]}), encoding="utf-8")
            old = os.environ.get("STUDIO_REGISTRY_PATH")
            os.environ["STUDIO_REGISTRY_PATH"] = str(registry)
            try:
                import services.studio_assets.app.project_api as project_api

                import importlib

                importlib.reload(project_api)
                row = project_api.get_project("legacy")
            finally:
                if old is None:
                    os.environ.pop("STUDIO_REGISTRY_PATH", None)
                else:
                    os.environ["STUDIO_REGISTRY_PATH"] = old
        self.assertEqual(row["id"], "legacy")

    def test_existing_workflow_files_not_mutated_by_registration(self):
        watched = ROOT / "watchers" / "clip_engine_reverse.py"
        before = sha256(watched.read_bytes()).hexdigest()
        resp = self.client.get("/api/v2/gpu/media/workflows", headers=self._auth())
        self.assertEqual(resp.status_code, 200)
        after = sha256(watched.read_bytes()).hexdigest()
        self.assertEqual(before, after)

    def test_failure_and_timeout_paths_preserve_recovery_evidence(self):
        now = self.module._now_utc()
        lease = (self.module.datetime.now(self.module.timezone.utc) - self.module.timedelta(seconds=10)).isoformat()
        evidence = json.dumps({"artifact_uri": "artifact://recover", "output_hash": "h3"})
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO gpu_jobs
                (id, tenant_id, client_id, priority, job_type, model, prompt, status, created_at, available_at, started_at,
                 lease_expires_at, attempt_count, max_attempts, created_by, media_job_type, media_state, selected_engine, evidence_json)
                VALUES ('timeout-job', 'media', 'studio', 1, 'comfyui', 'k', 'p', 'running', ?, ?, ?, ?, 3, 3, 'tester', 'scene_render', 'rendering', 'kandinsky5_local', ?)
                """,
                (now, now, now, lease, evidence),
            )
            self.module._recover_abandoned_jobs(conn)
            conn.commit()
            row = conn.execute("SELECT status, media_state, evidence_json FROM gpu_jobs WHERE id='timeout-job'").fetchone()
        self.assertEqual(row["status"], "timeout")
        self.assertEqual(row["media_state"], "timeout")
        self.assertIn("artifact_uri", json.loads(row["evidence_json"]))

    def test_published_jobs_contain_provenance_and_output_hashes(self):
        job_id = self._create_media_render()
        self._transition(job_id, "qc_passed")
        self._transition(job_id, "approval_pending")
        self._transition(job_id, "approved")
        self._transition(job_id, "publish_ready")
        self._transition(job_id, "publishing")
        self._transition(job_id, "published", evidence={"output_hash": "out-hash", "provenance_hash": "prov-hash", "artifact_uri": "artifact://pub"})
        with self._connect() as conn:
            row = conn.execute("SELECT output_hash, provenance_hash, media_state FROM gpu_jobs WHERE id=?", (job_id,)).fetchone()
        self.assertEqual(row["media_state"], "published")
        self.assertEqual(row["output_hash"], "out-hash")
        self.assertEqual(row["provenance_hash"], "prov-hash")


if __name__ == "__main__":
    unittest.main()
