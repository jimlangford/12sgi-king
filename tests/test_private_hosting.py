import copy
import hashlib
import hmac
from http.client import HTTPConnection
from http.server import HTTPServer
import json
import os
from pathlib import Path
import subprocess
import tempfile
import threading
import time
import unittest
from unittest.mock import Mock, patch

import yaml

import cleanup_system
import health_check
import local_ci_cd_server as ci
import service_auto_recovery as recovery
import setup_tailscale_hosting as hosting

ROOT = Path(__file__).resolve().parents[1]


class CleanupTests(unittest.TestCase):
    def test_only_stale_untracked_artifacts_are_selected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in (".dispatch_cursor_old.txt", ".dispatch_cursor_tracked.txt",
                         ".dispatch_cursor_new.txt", "docker-compose.postiz.yml"):
                path = root / name
                path.write_text("keep", encoding="utf-8")
                if "new" not in name:
                    os.utime(path, (time.time() - 172800,) * 2)
            link = root / ".dispatch_cursor_link.txt"
            link.symlink_to(root / ".dispatch_cursor_old.txt")
            with patch.object(cleanup_system.subprocess, "run",
                              return_value=Mock(stdout=b".dispatch_cursor_tracked.txt\0")):
                self.assertEqual(list(cleanup_system.candidates(root)),
                                 [root / ".dispatch_cursor_old.txt"])
            self.assertTrue((root / "docker-compose.postiz.yml").exists())

    def test_git_failure_does_not_allow_cleanup(self):
        with patch.object(cleanup_system.subprocess, "run",
                          side_effect=subprocess.CalledProcessError(1, "git")):
            with self.assertRaises(subprocess.CalledProcessError):
                list(cleanup_system.candidates(ROOT))

    def test_default_is_preview(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "artifact"
            path.write_text("keep")
            with patch.object(cleanup_system, "HERE", Path(directory)), patch.object(
                cleanup_system, "candidates", return_value=[path]
            ):
                self.assertEqual(cleanup_system.main([]), 0)
            self.assertTrue(path.exists())


class RecoveryTests(unittest.TestCase):
    def test_compose_json_formats(self):
        container = {"Service": "auth", "State": "running", "Health": "healthy"}
        monitor = recovery.ServiceMonitor()
        for output in (json.dumps(container), json.dumps([container]),
                       json.dumps(container) + "\n" + json.dumps(container)):
            with self.subTest(output=output), patch.object(
                recovery.subprocess, "run", return_value=Mock(returncode=0, stdout=output)
            ) as run:
                self.assertTrue(monitor.check_health())
                self.assertIn("--all", run.call_args.args[0])
                self.assertIn("--env-file", run.call_args.args[0])

    def test_failed_restart_attempts_are_bounded(self):
        monitor = recovery.ServiceMonitor()
        with patch.object(recovery.subprocess, "run",
                          return_value=Mock(returncode=1, stderr="failed")) as run:
            for _ in range(5):
                monitor.restart_service("auth")
        self.assertEqual(run.call_count, 3)

    def test_never_restarts_database_or_unknown_services(self):
        with patch.object(recovery.subprocess, "run") as run:
            self.assertFalse(recovery.ServiceMonitor().restart_service("neo4j"))
            self.assertFalse(recovery.ServiceMonitor().restart_service("--all"))
        run.assert_not_called()

    def test_running_unhealthy_is_restarted(self):
        monitor = recovery.ServiceMonitor()
        with patch.object(monitor, "check_health", return_value=[
            {"Service": "auth", "State": "running", "Health": "unhealthy"}
        ]), patch.object(monitor, "restart_service") as restart, patch.object(
            recovery.time, "sleep", side_effect=KeyboardInterrupt
        ):
            monitor.monitor()
        restart.assert_called_once_with("auth")


class ConfigTests(unittest.TestCase):
    def setUp(self):
        self.config = {"services": {name: {} for name in health_check.EXPECTED_SERVICES}}

    def test_private_defaults(self):
        hosting.validate_config(self.config)
        document = yaml.safe_load((ROOT / "docker-compose.v2.yml").read_text())
        services = document["services"]
        for service in services.values():
            for port in service.get("ports", []):
                self.assertTrue(port.startswith("127.0.0.1:"))
        self.assertNotIn("neo4j", services)
        self.assertIn("studio-assets=host.docker.internal:8108",
                      services["health"]["environment"]["SURFACES_LIST"])
        self.assertEqual(services["health"]["environment"]["SURFACES_HEALTH_PATH"], "/api/v2/ready")

    def test_rejects_unsafe_resolved_config(self):
        for key, value in (
            ("GOVOS_ALLOW_DEV_SECRETS", "1"), ("INTERNAL_SERVICE_TOKEN", "short"),
            ("NEO4J_AURA_ENABLED", "true"), ("GPU_RUNTIME_URL", "https://api.example.com"),
        ):
            config = copy.deepcopy(self.config)
            config["services"]["auth"]["environment"] = {key: value}
            with self.subTest(key=key), self.assertRaises(ValueError):
                hosting.validate_config(config)
        for port in ({}, {"host_ip": "0.0.0.0"}, {"host_ip": "::"}):
            config = copy.deepcopy(self.config)
            config["services"]["auth"]["ports"] = [port]
            with self.subTest(port=port), self.assertRaises(ValueError):
                hosting.validate_config(config)

    def test_private_inference_urls(self):
        for url in ("http://host.docker.internal:11434", "http://127.0.0.1:11434",
                    "http://100.124.152.3:11434", "https://king.example.ts.net"):
            self.assertTrue(hosting.private_url(url), url)
        for url in ("https://api.openai.com", "http://100.1.1.1", "file:///tmp/model",
                    "http://king.example.ts.net.evil.test"):
            self.assertFalse(hosting.private_url(url), url)

    def test_start_stops_without_tailscale(self):
        with patch.object(hosting.health_check, "check_tailscale",
                          return_value=(False, "offline")), patch.object(hosting.subprocess, "run") as run:
            self.assertEqual(hosting.main(["--start"]), 1)
        run.assert_not_called()

    def test_instructions_never_enable_funnel_or_write_files(self):
        with patch.object(Path, "write_text") as write:
            self.assertEqual(hosting.main([]), 0)
        write.assert_not_called()
        self.assertNotIn("tailscale funnel --bg", hosting.INSTRUCTIONS)


class HealthTests(unittest.TestCase):
    def test_missing_or_unhealthy_services_fail(self):
        healthy = [{"Service": name, "State": "running", "Health": "healthy"}
                   for name in health_check.EXPECTED_SERVICES]
        with patch.object(health_check.ServiceMonitor, "check_health", return_value=healthy):
            self.assertTrue(health_check.check_compose_stack()[0])
        healthy[0]["Health"] = "unhealthy"
        with patch.object(health_check.ServiceMonitor, "check_health", return_value=healthy):
            self.assertFalse(health_check.check_compose_stack()[0])
        with patch.object(health_check.ServiceMonitor, "check_health", return_value=[]):
            self.assertFalse(health_check.check_compose_stack()[0])

    def test_graph_count_is_read_only_and_checked(self):
        for count, expected in ((14299, False), (14300, True)):
            response = Mock()
            response.read.return_value = json.dumps(
                {"errors": [], "results": [{"data": [{"row": [count]}]}]}
            ).encode()
            response.__enter__ = Mock(return_value=response)
            response.__exit__ = Mock()
            with patch.object(health_check.urllib.request, "urlopen", return_value=response) as urlopen:
                self.assertEqual(health_check.check_neo4j()[0], expected)
                statement = json.loads(urlopen.call_args.args[0].data)["statements"][0]["statement"]
                self.assertEqual(statement, "MATCH (n) RETURN count(n) AS nodes")


class WebhookTests(unittest.TestCase):
    def setUp(self):
        self.pipeline = Mock()
        handler = type("TestHandler", (ci.GitWebhookHandler,), {
            "pipeline": self.pipeline, "webhook_secret": "test-only-signature-key",
        })
        self.server = HTTPServer(("127.0.0.1", 0), handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def post(self, payload, signed=True, event="push"):
        body = json.dumps(payload).encode()
        headers = {"Content-Type": "application/json", "X-GitHub-Event": event}
        if signed:
            headers["X-Hub-Signature-256"] = "sha256=" + hmac.new(
                b"test-only-signature-key", body, hashlib.sha256
            ).hexdigest()
        connection = HTTPConnection(*self.server.server_address, timeout=3)
        connection.request("POST", "/webhook", body, headers)
        response = connection.getresponse()
        response.read()
        status = response.status
        connection.close()
        return status

    def payload(self, ref="refs/heads/main"):
        return {"ref": ref, "after": "a" * 40,
                "repository": {"full_name": "jimlangford/12sgi-king"}}

    def test_unsigned_requests_are_rejected(self):
        self.assertEqual(self.post(self.payload(), signed=False), 403)
        self.pipeline.run.assert_not_called()

    def test_signed_main_push_starts_deployment(self):
        self.assertEqual(self.post(self.payload()), 202)
        self.pipeline.run.assert_called_once_with("a" * 40, "main")

    def test_other_refs_repositories_and_events_do_not_deploy(self):
        payload = self.payload()
        payload["repository"]["full_name"] = "other/repo"
        for data, event in ((self.payload("refs/heads/feature/main"), "push"),
                            (payload, "push"), (self.payload(), "issues"),
                            (self.payload("refs/tags/main"), "push")):
            self.assertEqual(self.post(data, event=event), 200)
        self.pipeline.run.assert_not_called()

    def test_non_object_payload_is_rejected(self):
        self.assertEqual(self.post([]), 400)
        self.pipeline.run.assert_not_called()


class PipelineTests(unittest.TestCase):
    def test_test_and_health_exceptions_fail_closed(self):
        pipeline = ci.DeploymentPipeline(ROOT)
        with patch.object(ci.subprocess, "run", side_effect=subprocess.TimeoutExpired("test", 1)):
            self.assertFalse(pipeline._run_tests())
            self.assertFalse(pipeline._verify_health())

    def test_unhealthy_result_fails_deployment(self):
        with patch.object(ci.subprocess, "run", return_value=Mock(returncode=1, stdout="not ready")):
            self.assertFalse(ci.DeploymentPipeline(ROOT)._verify_health())

    def test_concurrent_deployments_are_rejected(self):
        pipeline = ci.DeploymentPipeline(ROOT)
        pipeline._deploy_lock.acquire()
        try:
            self.assertFalse(pipeline.run("a" * 40))
        finally:
            pipeline._deploy_lock.release()

    def test_local_deployment_does_not_pull(self):
        pipeline = ci.DeploymentPipeline(ROOT)
        with patch.object(pipeline, "_git_pull") as pull, patch.object(
            pipeline, "_preflight", return_value=False
        ):
            self.assertFalse(pipeline.run("a" * 40, update_code=False))
        pull.assert_not_called()


if __name__ == "__main__":
    unittest.main()
