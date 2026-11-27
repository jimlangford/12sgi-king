"""Owner job tracking must use verified owner sessions, never a browser service secret."""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tests.v2._test_helpers import load_module  # noqa: E402


class TestKingBridgeOwnerAuth(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory(prefix="king-bridge-auth-")
        cls.module = load_module(
            ROOT / "services" / "king_bridge" / "app" / "main.py",
            "king_bridge_owner_auth_test",
            env_overrides={"KING_BRIDGE_DB": str(Path(cls._tmp.name) / "bridge.db")},
        )
        cls.client = TestClient(cls.module.app)

    @classmethod
    def tearDownClass(cls):
        cls.client.close()
        cls._tmp.cleanup()

    def test_owner_job_endpoints_reject_anonymous_requests(self):
        endpoints = [
            ("GET", "/api/v2/owner/jobs"),
            ("GET", "/api/v2/owner/jobs/stats"),
            ("GET", "/api/v2/owner/jobs/example"),
            ("POST", "/api/v2/owner/jobs/example/approval"),
        ]
        for method, path in endpoints:
            with self.subTest(method=method, path=path):
                response = self.client.request(method, path, json={"decision": "approve"})
                self.assertEqual(response.status_code, 401)

    def test_non_owner_claims_are_rejected(self):
        with mock.patch.object(
            self.module, "require_claims", return_value={"role": "Resident", "sub": "u1"}
        ):
            with self.assertRaises(self.module.HTTPException) as ctx:
                self.module._require_owner_claims("Bearer resident-token")
        self.assertEqual(ctx.exception.status_code, 403)

    def test_private_dashboard_has_no_service_credential(self):
        source = (ROOT / "element_lotus_public" / "owner_jobs.html").read_text(encoding="utf-8")
        self.assertNotIn("dev-internal-token", source)
        self.assertNotIn('"X-Service-Token"', source)
        self.assertIn('"Authorization": "Bearer " + token', source)


if __name__ == "__main__":
    unittest.main()
