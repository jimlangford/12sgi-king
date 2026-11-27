import json
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tests.v2._test_helpers import load_module  # noqa: E402


class TestAiGatewayExecutionBoundary(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.module = load_module(
            ROOT / "services" / "ai_gateway" / "app" / "main.py",
            f"ai_gateway_execution_{time.time_ns()}",
            env_overrides={"AI_GATEWAY_DB_PATH": str(Path(self.tmp.name) / "gateway.db")},
        )
        self.module.require_claims = lambda **kwargs: {
            "sub": "owner-test", "role": "Owner", "tenant_id": "tenant-test",
            "scopes": ["civic:read", "actions:approve", "actions:reject", "audit:read"],
        }
        self.client = TestClient(self.module.app)

    def tearDown(self):
        self.client.close()
        self.tmp.cleanup()

    def test_tool_invocation_fails_closed_without_executor(self):
        self.module.TOOL_EXECUTOR_URL = ""
        response = self.client.post(
            "/api/v2/tools/civic.search/invoke", json={"parameters": {"q": "records"}}
        )
        self.assertEqual(response.status_code, 503)
        self.assertIn("executor", response.json()["detail"])

    def test_dispatch_sends_registry_contract_and_returns_real_executor_result(self):
        self.module.TOOL_EXECUTOR_URL = "http://executor.test"
        response_body = b'{"records":[]}'

        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self): return response_body

        with patch.object(self.module.request, "urlopen", return_value=Response()) as urlopen:
            result = self.module._dispatch_tool(
                {"tool_id": "civic.search", "endpoint": "/api/v2/civic/search", "http_method": "GET"},
                {"q": "records"}, "Bearer test", actor="owner-test",
            )
        self.assertEqual(result, {"records": []})
        sent = json.loads(urlopen.call_args.args[0].data)
        self.assertEqual(sent["endpoint"], "/api/v2/civic/search")
        self.assertEqual(sent["parameters"], {"q": "records"})


if __name__ == "__main__":
    unittest.main()
