import importlib.util
import json
import os
import re
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from fastapi import HTTPException

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

AUTH_MAIN = ROOT / "services" / "auth" / "app" / "main.py"
GOVOS_APP = ROOT / "apps" / "govos" / "public" / "app.js"
TENANT_APP = ROOT / "apps" / "tenant" / "public" / "app.js"
CIVIC_APP = ROOT / "apps" / "civic-signal" / "public" / "app.js"
LOCAL_DEV_DOC = ROOT / "docs" / "GOVOS_V2_LOCAL_DEV.md"


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


class TestClaimClientMigration(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="v2-claim-client-")
        self.auth_db = str(Path(self.tmp.name) / "auth.db")
        self.auth = _load_module(
            AUTH_MAIN,
            f"auth_claim_client_{time.time_ns()}",
            env_overrides={
                "AUTH_SIGNING_SECRET": "claim-client-secret",
                "INTERNAL_SERVICE_TOKEN": "claim-client-service-token",
                "AUTH_DB_PATH": self.auth_db,
            },
            env_clear_keys=("GOVOS_ALLOW_DEV_SECRETS",),
        )
        from fastapi.testclient import TestClient  # local import to avoid global dependency during discovery
        self.client = TestClient(self.auth.app)

    def tearDown(self):
        self.tmp.cleanup()

    def test_auth_session_response_includes_required_claim_fields(self):
        resp = self.client.post(
            "/api/v2/auth/session",
            json={
                "provider": "passkey",
                "subject": "migration-user-1",
                "tenant_id": "tenant-a",
                "role": "Municipality",
                "scopes": ["tenant:read"],
            },
        )
        self.assertEqual(resp.status_code, 200)
        claims = resp.json()["claims"]
        for field in ("sub", "tenant_id", "role", "scopes", "exp", "iss", "aud"):
            self.assertIn(field, claims)
        self.assertIsInstance(claims["exp"], int)

    def test_service_scope_must_be_allowlisted(self):
        resp = self.client.post(
            "/api/v2/auth/session",
            json={
                "provider": "magic_link",
                "subject": "svc:bad",
                "role": "Service",
                "scopes": ["not:real"],
            },
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["detail"]["error"]["code"], "invalid_scope")

    def test_wildcard_scope_is_blocked_by_default(self):
        resp = self.client.post(
            "/api/v2/auth/session",
            json={
                "provider": "passkey",
                "subject": "wildcard-user",
                "tenant_id": "tenant-a",
                "role": "Municipality",
                "scopes": ["tenant:*"],
            },
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["detail"]["error"]["code"], "invalid_scope")

    def test_owner_override_is_audited(self):
        from services import authz

        with mock.patch.object(authz._log, "warning") as warning:
            scoped = authz.enforce_tenant_scope(
                service_name="tenant",
                claims={"role": "Owner", "tenant_id": ""},
                requested_tenant_id="tenant-b",
                owner_override_allowed=True,
            )
            self.assertEqual(scoped, "tenant-b")
            self.assertTrue(warning.called)
            payload = json.loads(warning.call_args[0][1])
            self.assertEqual(payload["event_type"], "owner_override")

    def test_legacy_claim_pattern_is_rejected(self):
        from services.authz import require_claims

        class _Resp:
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return json.dumps(
                    {
                        "active": True,
                        "claims": {
                            "sub": "u1",
                            "tenant_id": "tenant-a",
                            "role": "Municipality",
                            "scopes": ["tenant:read"],
                            "exp": 9999999999,
                        },
                    }
                ).encode()

        with mock.patch("services.authz.request.urlopen", return_value=_Resp()):
            with self.assertRaises(HTTPException) as ctx:
                require_claims(
                    service_name="tenant",
                    authorization=("Bearer " + "test-token"),
                    introspection_url="http://auth/api/v2/auth/introspect",
                    internal_service_token="svc-token",
                    request_timeout=1.0,
                    required_scopes={"tenant:read"},
                )
        self.assertEqual(ctx.exception.status_code, 401)
        self.assertEqual(ctx.exception.detail["error"]["code"], "unauthorized")

    def test_client_callers_send_bearer_authorization(self):
        for path in (GOVOS_APP, TENANT_APP, CIVIC_APP):
            text = path.read_text(encoding="utf-8")
            self.assertIn("Authorization", text, msg=str(path))
            self.assertIn("Bearer ", text, msg=str(path))

    def test_no_tokens_embedded_in_examples_or_fixtures(self):
        jwt_pattern = re.compile(r"eyJ[a-zA-Z0-9_-]{10,}\\.[a-zA-Z0-9_-]{10,}\\.[a-zA-Z0-9_-]{10,}")
        for path in (GOVOS_APP, TENANT_APP, CIVIC_APP, LOCAL_DEV_DOC):
            text = path.read_text(encoding="utf-8")
            self.assertIsNone(jwt_pattern.search(text), msg=str(path))


if __name__ == "__main__":
    unittest.main()
