"""Regression: the magic-link IP limit must not become one global bucket behind the tunnel, and must never lock the owner out."""
import sys
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tests.v2._test_helpers import load_module as _load_module  # noqa: E402

AUTH_MAIN = ROOT / "services" / "auth" / "app" / "main.py"


def _req(peer, cf=None):
    headers = {"cf-connecting-ip": cf} if cf is not None else {}
    return SimpleNamespace(client=SimpleNamespace(host=peer), headers=headers)


class TestMagicLinkIpLimit(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="v2-magic-ip-")
        self.auth = _load_module(
            AUTH_MAIN,
            f"auth_magic_ip_{time.time_ns()}",
            env_overrides={
                "AUTH_SIGNING_SECRET": "magic-ip-secret",
                "INTERNAL_SERVICE_TOKEN": "magic-ip-service-token",
                "AUTH_DB_PATH": str(Path(self.tmp.name) / "auth.db"),
                "MAGIC_LINK_MIN_INTERVAL_SECONDS": "1",
            },
            env_clear_keys=("GOVOS_ALLOW_DEV_SECRETS",),
        )

    def tearDown(self):
        self.tmp.cleanup()

    def test_client_ip_uses_cloudflare_header_only_from_a_private_peer(self):
        self.assertEqual(self.auth._client_ip(_req("127.0.0.1", "203.0.113.9")), "203.0.113.9")
        self.assertEqual(self.auth._client_ip(_req("172.18.0.5", "203.0.113.9")), "203.0.113.9")
        # a direct public peer cannot choose its own bucket by sending the header
        self.assertEqual(self.auth._client_ip(_req("8.8.8.8", "203.0.113.9")), "8.8.8.8")
        # garbage header falls back to the peer
        self.assertEqual(self.auth._client_ip(_req("127.0.0.1", "not-an-ip")), "127.0.0.1")
        self.assertEqual(self.auth._client_ip(_req("127.0.0.1")), "127.0.0.1")

    def test_exhausted_ip_bucket_does_not_block_the_owner_but_blocks_players(self):
        self.auth.MAGIC_LINK_IP_HOURLY_LIMIT = 2
        ip = "203.0.113.50"
        self.assertIsNotNone(self.auth._create_magic_link("a@example.com", role="RegisteredUser", client_ip=ip))
        self.assertIsNotNone(self.auth._create_magic_link("b@example.com", role="RegisteredUser", client_ip=ip))
        # the bucket for this address is now full: a third player is refused
        self.assertIsNone(self.auth._create_magic_link("c@example.com", role="RegisteredUser", client_ip=ip))
        # the owner from the SAME address is still let through
        self.assertIsNotNone(self.auth._create_magic_link("owner@example.com", role="Owner", client_ip=ip))
        # and a different visitor is unaffected
        self.assertIsNotNone(self.auth._create_magic_link("d@example.com", role="RegisteredUser", client_ip="203.0.113.51"))


if __name__ == "__main__":
    unittest.main()
