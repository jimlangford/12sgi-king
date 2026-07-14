import importlib.util
import os
import tempfile
import time
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ENTITLEMENTS = ROOT / "services" / "entitlements.py"


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


class TestEntitlementBridge(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="entitlements-")
        self.db = str(Path(self.tmp.name) / "entitlements.db")
        self.map_path = str(ROOT / "config" / "entitlement_map.json")
        self.mod = _load_module(
            ENTITLEMENTS,
            f"entitlements_{time.time_ns()}",
            env_overrides={
                "ENTITLEMENT_DB_PATH": self.db,
                "ENTITLEMENT_MAP_PATH": self.map_path,
            },
            env_clear_keys=("JETPACK_TOKEN", "JETPACK_SITE_ID", "WP_BRIDGE_SUBSCRIPTION_STATUS", "WP_BRIDGE_PRODUCTS"),
        )

    def tearDown(self):
        self.tmp.cleanup()

    def test_bind_identity_falls_closed_when_wordpress_unavailable(self):
        out = self.mod.bind_identity(provider="google", subject="google:abc123", email="user@example.com")
        self.assertFalse(out["verified"])
        self.assertEqual(out["tier"], "free")
        self.assertEqual(out["source"], "unverified")
        linked = self.mod.get_identity_link("google", "google:abc123")
        self.assertIsNotNone(linked)
        self.assertEqual(linked["tier"], "free")

    def test_resolve_identity_uses_cached_link_consistently(self):
        first = self.mod.bind_identity(provider="google", subject="google:sub-one", email="owner@example.com")
        second = self.mod.resolve_identity_entitlement(provider="google", subject="google:sub-one", email="owner@example.com")
        self.assertEqual(first["tier"], second["tier"])
        self.assertEqual(second["source"], "identity_link")
        self.assertIn("capabilities", second)


if __name__ == "__main__":
    unittest.main()
