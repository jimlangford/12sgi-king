import importlib
import importlib.util
import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

SERVICE_METADATA = ROOT / "services" / "service_metadata.py"
HEALTH_MAIN = ROOT / "services" / "health" / "app" / "main.py"


def _load_module(path, name, env_overrides=None, env_clear_keys=None):
    saved = dict(os.environ)
    try:
        if env_clear_keys:
            for key in env_clear_keys:
                os.environ.pop(key, None)
        if env_overrides:
            os.environ.update(env_overrides)
        sys.modules.pop("services.service_metadata", None)
        services_pkg = sys.modules.get("services")
        if services_pkg is not None and hasattr(services_pkg, "service_metadata"):
            delattr(services_pkg, "service_metadata")
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        os.environ.clear()
        os.environ.update(saved)


def _load_health_module(env_overrides=None, env_clear_keys=None):
    saved = dict(os.environ)
    try:
        if env_clear_keys:
            for key in env_clear_keys:
                os.environ.pop(key, None)
        if env_overrides:
            os.environ.update(env_overrides)
        for key in list(sys.modules.keys()):
            if key.startswith("services.health.app"):
                sys.modules.pop(key, None)
        sys.modules.pop("services.service_metadata", None)
        return importlib.import_module("services.health.app.main")
    finally:
        os.environ.clear()
        os.environ.update(saved)


class TestPlatformManifestConsistency(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="platform-manifest-")
        self.manifest_path = Path(self.tmp.name) / "platform_version.json"
        self.manifest_path.write_text(
            json.dumps(
                {
                    "manifest_version": "1.0.0",
                    "platform_version": "2026.07.14-phase1",
                }
            ),
            encoding="utf-8",
        )

    def tearDown(self):
        self.tmp.cleanup()

    def test_service_metadata_uses_manifest_when_env_missing(self):
        module = _load_module(
            SERVICE_METADATA,
            f"service_metadata_manifest_{time.time_ns()}",
            env_overrides={"PLATFORM_VERSION_FILE": str(self.manifest_path)},
            env_clear_keys=("PLATFORM_VERSION",),
        )

        payload = module.service_metadata("health", "1.2.3")
        self.assertEqual(payload["platform_version"], "2026.07.14-phase1")
        self.assertEqual(payload["platform_manifest_version"], "1.0.0")
        self.assertFalse(payload["platform_version_mismatch"])

    def test_service_metadata_flags_env_manifest_disagreement(self):
        module = _load_module(
            SERVICE_METADATA,
            f"service_metadata_disagree_{time.time_ns()}",
            env_overrides={
                "PLATFORM_VERSION_FILE": str(self.manifest_path),
                "PLATFORM_VERSION": "2026.07.99-hotfix",
            },
        )

        payload = module.service_metadata("health", "1.2.3")
        self.assertEqual(payload["platform_version"], "2026.07.99-hotfix")
        self.assertEqual(payload["platform_version_manifest"], "2026.07.14-phase1")
        self.assertTrue(payload["platform_version_mismatch"])

    def test_health_live_reports_platform_disagreement(self):
        module = _load_health_module(
            env_overrides={
                "PLATFORM_VERSION_FILE": str(self.manifest_path),
                "PLATFORM_VERSION": "2026.07.99-hotfix",
            },
        )
        client = TestClient(module.app)

        body = client.get("/api/v1/live").json()

        self.assertEqual(body["platform"]["platform_version"], "2026.07.14-phase1")
        self.assertEqual(body["platform"]["manifest_version"], "1.0.0")
        self.assertTrue(body["platform"]["version_disagreement"])
        self.assertTrue(body["platform_version_mismatch"])


if __name__ == "__main__":
    unittest.main()
