import sys
import time
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tests.v2._test_helpers import load_module  # noqa: E402


class TestAiGatewaySingleModel(unittest.TestCase):
    def test_chat_profiles_route_to_unified_local_model(self):
        module = load_module(
            ROOT / "services" / "ai_gateway" / "app" / "main.py",
            f"ai_gateway_single_model_{time.time_ns()}",
            env_overrides={"LOCAL_LLM_MODEL": "king-quad-os-unified"},
        )
        module.require_claims = lambda **kwargs: {
            "sub": "owner-test", "role": "Owner", "tenant_id": "tenant-test",
            "scopes": ["gateway:chat"],
        }
        module.enforce_tenant_scope = lambda **kwargs: "tenant-test"
        module._gpu_status = lambda: {"engines": {}}
        called_models = []

        def fake_infer(**kwargs):
            called_models.append(kwargs["model"])
            return {"response": "Local model route confirmed."}

        module._gpu_infer = fake_infer
        with TestClient(module.app) as client:
            response = client.post(
                "/api/v1/chat/completions",
                json={"model": "12sgi-owner", "messages": [{"role": "user", "content": "test"}]},
            )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(called_models, ["king-quad-os-unified"])


if __name__ == "__main__":
    unittest.main()
