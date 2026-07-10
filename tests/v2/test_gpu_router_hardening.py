import importlib.util
import os
import sqlite3
import sys
import tempfile
import time
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

GPU_MAIN = ROOT / "services" / "gpu_router" / "app" / "main.py"
AUTH_MAIN = ROOT / "services" / "auth" / "app" / "main.py"
WORKFLOW = ROOT / ".github" / "workflows" / "deploy-v2-king-server.yml"
GPU_PANEL = ROOT / "king_public_src" / "Gpu.dc.html"
OWNER_SHELL = ROOT / "king_public_src" / "index.html"
DEPLOYMENT_DOC = ROOT / "docs" / "DEPLOYMENT.md"


def _load_module(path, name, env_overrides=None, env_clear_keys=None):
    saved = dict(os.environ)
    try:
        if env_clear_keys:
            for key in env_clear_keys:
                os.environ.pop(key, None)
        if env_overrides:
            os.environ.update(env_overrides)
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        os.environ.clear()
        os.environ.update(saved)


class GpuRouterHarness(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="gpu-router-hardening-")
        self.db_path = str(Path(self.tmp.name) / "gpu-router.db")

    def tearDown(self):
        self.tmp.cleanup()

    def load_gpu(self, **env):
        module = _load_module(
            GPU_MAIN,
            f"gpu_router_test_{id(self)}_{time.time_ns()}",
            env_overrides={
                "GPU_ROUTER_DB_PATH": self.db_path,
                "COMMIT_SHA": "abc123def456",
                "BUILD_TIMESTAMP": "2026-07-10T23:30:00Z",
                "ENVIRONMENT": "test",
                **env,
            },
        )
        module._require_auth = lambda authorization: {"id": "owner-test"}
        return module

    def connect(self):
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn


class TestGpuRouterHardening(GpuRouterHarness):
    def test_health_reports_provenance_metadata(self):
        module = self.load_gpu()
        client = TestClient(module.app)

        body = client.get("/api/v2/health").json()

        self.assertEqual(body["service"], "gpu-router")
        self.assertEqual(body["version"], module.VERSION)
        self.assertEqual(body["commit_sha"], "abc123def456")
        self.assertEqual(body["build_timestamp"], "2026-07-10T23:30:00Z")
        self.assertEqual(body["environment"], "test")

    def test_auth_service_health_reports_provenance_metadata(self):
        module = _load_module(
            AUTH_MAIN,
            f"auth_meta_{time.time_ns()}",
            env_overrides={
                "AUTH_SIGNING_SECRET": "real-secret",
                "INTERNAL_SERVICE_TOKEN": "real-token",
                "AUTH_DB_PATH": str(Path(self.tmp.name) / "auth.db"),
                "COMMIT_SHA": "abc123def456",
                "BUILD_TIMESTAMP": "2026-07-10T23:30:00Z",
                "ENVIRONMENT": "test",
            },
            env_clear_keys=("GOVOS_ALLOW_DEV_SECRETS",),
        )
        client = TestClient(module.app)

        body = client.get("/api/v2/health").json()

        self.assertEqual(body["service"], "auth")
        self.assertEqual(body["commit_sha"], "abc123def456")
        self.assertEqual(body["build_timestamp"], "2026-07-10T23:30:00Z")
        self.assertEqual(body["environment"], "test")

    def test_claiming_is_atomic_for_one_pending_job(self):
        module = self.load_gpu()
        now = module._now_utc()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO gpu_jobs
                  (id, tenant_id, client_id, priority, job_type, model, prompt, status,
                   created_at, available_at, max_attempts, created_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?, ?)
                """,
                ("job-1", "tenant-a", "tenant-a", 1, "ollama", "llama3", "hello", now, now, 3, "tester"),
            )
            conn.commit()
        with self.connect() as conn1:
            claimed = module._claim_next_pending_job(conn1, {"ollama"}, "gpu-worker")
        with self.connect() as conn2:
            claimed_again = module._claim_next_pending_job(conn2, {"ollama"}, "gpu-worker-2")

        self.assertIsNotNone(claimed)
        self.assertEqual(claimed["status"], "running")
        self.assertIsNone(claimed_again)

    def test_recover_abandoned_job_requeues_before_retry_limit(self):
        module = self.load_gpu()
        lease = (module.datetime.now(module.timezone.utc) - module.timedelta(seconds=5)).isoformat()
        now = module._now_utc()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO gpu_jobs
                  (id, tenant_id, client_id, priority, job_type, model, prompt, status, created_at,
                   available_at, started_at, lease_expires_at, attempt_count, max_attempts, created_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'running', ?, ?, ?, ?, ?, ?, ?)
                """,
                ("job-1", "tenant-a", "tenant-a", 1, "ollama", "llama3", "hello", now, now, now, lease, 1, 3, "tester"),
            )
            recovered = module._recover_abandoned_jobs(conn)
            conn.commit()
            row = conn.execute("SELECT status, error, started_at FROM gpu_jobs WHERE id='job-1'").fetchone()

        self.assertEqual(recovered[0]["event_type"], "job.recovered")
        self.assertEqual(row["status"], "pending")
        self.assertIn("Recovered abandoned job", row["error"])
        self.assertIsNone(row["started_at"])

    def test_recover_abandoned_job_times_out_at_retry_limit(self):
        module = self.load_gpu()
        lease = (module.datetime.now(module.timezone.utc) - module.timedelta(seconds=5)).isoformat()
        now = module._now_utc()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO gpu_jobs
                  (id, tenant_id, client_id, priority, job_type, model, prompt, status, created_at,
                   available_at, started_at, lease_expires_at, attempt_count, max_attempts, created_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'running', ?, ?, ?, ?, ?, ?, ?)
                """,
                ("job-1", "tenant-a", "tenant-a", 1, "ollama", "llama3", "hello", now, now, now, lease, 3, 3, "tester"),
            )
            recovered = module._recover_abandoned_jobs(conn)
            conn.commit()
            row = conn.execute("SELECT status, error, finished_at FROM gpu_jobs WHERE id='job-1'").fetchone()

        self.assertEqual(recovered[0]["event_type"], "job.timeout")
        self.assertEqual(row["status"], "timeout")
        self.assertIn("retry limit", row["error"])
        self.assertIsNotNone(row["finished_at"])

    def test_idempotency_reuses_completed_job(self):
        module = self.load_gpu()
        module._run_job = lambda job: ("done", {"response": f"ok:{job['prompt']}"}, None)
        client = TestClient(module.app)
        headers = {"Authorization": "******", "X-Idempotency-Key": "idem-1"}
        payload = {"client_id": "studio", "tenant_id": "studio", "model": "llama3", "prompt": "Aloha"}

        first = client.post("/api/v2/gpu/infer", json=payload, headers=headers)
        second = client.post("/api/v2/gpu/infer", json=payload, headers=headers)

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(first.json()["job_id"], second.json()["job_id"])
        with self.connect() as conn:
            count = conn.execute("SELECT COUNT(*) FROM gpu_jobs").fetchone()[0]
        self.assertEqual(count, 1)

    def test_conflicting_idempotency_payload_is_rejected(self):
        module = self.load_gpu()
        module._run_job = lambda job: ("done", {"response": "ok"}, None)
        client = TestClient(module.app)
        headers = {"Authorization": "******", "X-Idempotency-Key": "idem-1"}

        first = client.post(
            "/api/v2/gpu/infer",
            json={"client_id": "studio", "tenant_id": "studio", "model": "llama3", "prompt": "Aloha"},
            headers=headers,
        )
        second = client.post(
            "/api/v2/gpu/infer",
            json={"client_id": "studio", "tenant_id": "studio", "model": "llama3", "prompt": "Different"},
            headers=headers,
        )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 409)
        self.assertEqual(second.json()["detail"]["error"]["code"], "idempotency_conflict")

    def test_request_timeout_leaves_job_recoverable_for_idempotent_retry(self):
        module = self.load_gpu(GPU_INFER_TIMEOUT="0.2", GPU_JOB_LEASE_SECONDS="2")

        def slow_success(job):
            time.sleep(0.35)
            return ("done", {"response": "eventual"}, None)

        module._run_job = slow_success
        client = TestClient(module.app)
        headers = {"Authorization": "******", "X-Idempotency-Key": "idem-2"}
        payload = {"client_id": "studio", "tenant_id": "studio", "model": "llama3", "prompt": "slow"}

        timed_out = client.post("/api/v2/gpu/infer", json=payload, headers=headers)
        time.sleep(0.45)
        retried = client.post("/api/v2/gpu/infer", json=payload, headers=headers)

        self.assertEqual(timed_out.status_code, 504)
        self.assertEqual(retried.status_code, 200)
        self.assertEqual(retried.json()["response"], "eventual")
        with self.connect() as conn:
            row = conn.execute("SELECT status FROM gpu_jobs WHERE tenant_id='studio'").fetchone()
        self.assertEqual(row["status"], "done")

    def test_operational_endpoints_require_auth(self):
        module = _load_module(
            GPU_MAIN,
            f"gpu_router_auth_{time.time_ns()}",
            env_overrides={"GPU_ROUTER_DB_PATH": self.db_path},
        )
        client = TestClient(module.app)

        for path in ("/api/v2/gpu/queue", "/api/v2/gpu/usage", "/api/v2/gpu/events"):
            resp = client.get(path)
            self.assertEqual(resp.status_code, 401, path)

    def test_operational_endpoints_can_filter_by_tenant(self):
        module = self.load_gpu()
        now = module._now_utc()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO gpu_jobs
                  (id, tenant_id, client_id, priority, job_type, model, prompt, status,
                   created_at, available_at, max_attempts, created_by)
                VALUES
                  ('job-a', 'tenant-a', 'studio', 1, 'ollama', 'llama3', 'a', 'pending', ?, ?, 3, 'tester'),
                  ('job-b', 'tenant-b', 'reports', 1, 'ollama', 'llama3', 'b', 'pending', ?, ?, 3, 'tester')
                """,
                (now, now, now, now),
            )
            conn.commit()
        module._require_auth = lambda authorization: {"id": "owner-test"}
        client = TestClient(module.app)

        queue = client.get("/api/v2/gpu/queue?tenant_id=tenant-a", headers={"Authorization": "******"}).json()
        usage = client.get("/api/v2/gpu/usage?tenant_id=tenant-a", headers={"Authorization": "******"}).json()

        self.assertEqual([item["tenant_id"] for item in queue["queue"]], ["tenant-a"])
        self.assertEqual([item["tenant_id"] for item in usage["usage"]], ["tenant-a"])


class TestGpuRouterDeploymentSurfaces(unittest.TestCase):
    def test_workflow_tracks_gpu_router_and_service_metadata(self):
        text = WORKFLOW.read_text()
        self.assertIn("services\\gpu_router\\app\\main.py", text)
        self.assertIn("V2_GPU_ROUTER_PORT", text)
        self.assertIn("SERVICE_METADATA", text)
        self.assertIn("commit_sha", text)

    def test_owner_gpu_panel_surfaces_provenance(self):
        panel = GPU_PANEL.read_text()
        shell = OWNER_SHELL.read_text()
        self.assertIn("gpu-commit", panel)
        self.assertIn("gpu-build-ts", panel)
        self.assertIn("gpu-environment", panel)
        self.assertIn("commit_sha", panel)
        self.assertIn("'gpu'", shell)


class TestDeployWorkflowHardening(unittest.TestCase):
    def test_workflow_validates_compose_before_restart(self):
        text = WORKFLOW.read_text()
        self.assertIn("Validate V2 compose plan and print inventory", text)
        self.assertIn("docker compose -f docker-compose.v2.yml config", text)
        self.assertLess(
            text.index("Validate V2 compose plan and print inventory"),
            text.index("Restart V2 Docker services"),
        )

    def test_workflow_declares_explicit_service_inventory_and_ports(self):
        text = WORKFLOW.read_text()
        for service in (
            "neo4j",
            "auth",
            "tenant",
            "documents",
            "gpu-runtime",
            "gpu-router",
            "ai",
            "storage",
            "health",
        ):
            self.assertIn(service, text)
        for port in (
            "auth=8101",
            "tenant=8102",
            "documents=8103",
            "storage=8104",
            "ai=8105",
            "health=8106",
            "gpu-router=8107",
        ):
            self.assertIn(port, text)

    def test_workflow_validates_provenance_fields_sha_timestamp_and_environment(self):
        text = WORKFLOW.read_text()
        for field in (
            "service",
            "version",
            "commit_sha",
            "build_timestamp",
            "environment",
        ):
            self.assertIn(field, text)
        self.assertIn("ConvertFrom-Json", text)
        self.assertIn("mismatched_commit_sha", text)
        self.assertIn("Test-Iso8601", text)
        self.assertIn("king-server-private", text)

    def test_workflow_fails_on_high_or_critical_findings(self):
        text = WORKFLOW.read_text()
        self.assertIn("service_unreachable", text)
        self.assertIn("malformed_metadata", text)
        self.assertIn("mixed_commit_sha", text)
        self.assertIn('if ($severityRank[$maxSeverity] -ge $severityRank["high"])', text)
        self.assertIn("exit 1", text)


class TestDeploymentRollbackDocs(unittest.TestCase):
    def test_v2_rollback_section_covers_required_triggers_and_safeguards(self):
        text = DEPLOYMENT_DOC.read_text()
        self.assertIn("king-server V2 rollback", text)
        for trigger in (
            "mixed commit SHAs",
            "persistent readiness failure",
            "authentication failure",
            "tenant data exposure",
            "queue corruption",
            "database damage",
            "core service outage",
        ):
            self.assertIn(trigger, text)
        for safeguard in (
            "docker compose down -v",
            "docker system prune",
            "docker volume prune",
            "named volumes",
            "queue/dispatch",
            "previously known-good commit",
            "docker compose -f docker-compose.v2.yml config",
        ):
            self.assertIn(safeguard, text)


if __name__ == "__main__":
    unittest.main()
