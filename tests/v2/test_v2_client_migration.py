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
MIGRATION_DOC = ROOT / "docs" / "V2_CLAIM_CLIENT_MIGRATION.md"


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

    def test_diagnostic_endpoint_is_disabled_by_default(self):
        owner = self.client.post(
            "/api/v2/auth/session",
            json={"provider": "passkey", "subject": "owner-diag", "role": "Owner", "scopes": ["ops:owner"]},
        )
        self.assertEqual(owner.status_code, 200)
        token = owner.json()["access_token"]
        resp = self.client.post(
            "/api/v2/auth/diagnostics/claims",
            json={},
            headers={"Authorization": "Bearer " + token, "X-Request-ID": "req-disabled"},
        )
        self.assertEqual(resp.status_code, 404)

    def test_diagnostic_endpoint_owner_only_and_redacted(self):
        auth_enabled = _load_module(
            AUTH_MAIN,
            f"auth_diag_{time.time_ns()}",
            env_overrides={
                "AUTH_SIGNING_SECRET": "claim-client-secret",
                "INTERNAL_SERVICE_TOKEN": "claim-client-service-token",
                "AUTH_DB_PATH": str(Path(self.tmp.name) / "auth_diag.db"),
                "AUTH_VERIFICATION_DIAGNOSTICS_ENABLED": "true",
            },
            env_clear_keys=("GOVOS_ALLOW_DEV_SECRETS",),
        )
        from fastapi.testclient import TestClient

        client = TestClient(auth_enabled.app)
        owner = client.post(
            "/api/v2/auth/session",
            json={"provider": "passkey", "subject": "owner-1", "role": "Owner", "scopes": ["ops:owner"]},
        )
        resident = client.post(
            "/api/v2/auth/session",
            json={
                "provider": "passkey",
                "subject": "resident-1",
                "tenant_id": "tenant-a",
                "role": "Resident",
                "scopes": ["tenant:read"],
            },
        )
        self.assertEqual(owner.status_code, 200)
        self.assertEqual(resident.status_code, 200)

        denied = client.post(
            "/api/v2/auth/diagnostics/claims",
            json={},
            headers={"Authorization": "Bearer " + resident.json()["access_token"]},
        )
        self.assertEqual(denied.status_code, 403)

        allowed = client.post(
            "/api/v2/auth/diagnostics/claims",
            json={},
            headers={"Authorization": "Bearer " + owner.json()["access_token"], "X-Request-ID": "req-123"},
        )
        self.assertEqual(allowed.status_code, 200)
        payload = allowed.json()
        self.assertTrue(str(payload["subject"]).startswith("sha256:"))
        self.assertTrue(str(payload["tenant_id"]).startswith("sha256:") or payload["tenant_id"] == "")
        self.assertEqual(payload["request_id"], "req-123")
        self.assertIn(payload["authorization_decision"], {"accepted", "denied"})

    def test_diagnostic_endpoint_never_leaks_token_or_service_secret(self):
        auth_enabled = _load_module(
            AUTH_MAIN,
            f"auth_diag_leak_{time.time_ns()}",
            env_overrides={
                "AUTH_SIGNING_SECRET": "claim-client-secret",
                "INTERNAL_SERVICE_TOKEN": "claim-client-service-token",
                "AUTH_DB_PATH": str(Path(self.tmp.name) / "auth_diag_leak.db"),
                "AUTH_VERIFICATION_DIAGNOSTICS_ENABLED": "true",
            },
            env_clear_keys=("GOVOS_ALLOW_DEV_SECRETS",),
        )
        from fastapi.testclient import TestClient

        client = TestClient(auth_enabled.app)
        owner = client.post(
            "/api/v2/auth/session",
            json={"provider": "passkey", "subject": "owner-1", "role": "Owner", "scopes": ["ops:owner"]},
        )
        token = owner.json()["access_token"]
        resp = client.post(
            "/api/v2/auth/diagnostics/claims",
            json={"token": token},
            headers={"Authorization": "Bearer " + token, "X-Request-ID": "req-leak"},
        )
        self.assertEqual(resp.status_code, 200)
        payload = json.dumps(resp.json())
        self.assertNotIn(token, payload)
        self.assertNotIn("claim-client-service-token", payload)

    def test_diagnostic_request_id_correlates_with_audit_event(self):
        auth_enabled = _load_module(
            AUTH_MAIN,
            f"auth_diag_audit_{time.time_ns()}",
            env_overrides={
                "AUTH_SIGNING_SECRET": "claim-client-secret",
                "INTERNAL_SERVICE_TOKEN": "claim-client-service-token",
                "AUTH_DB_PATH": str(Path(self.tmp.name) / "auth_diag_audit.db"),
                "AUTH_VERIFICATION_DIAGNOSTICS_ENABLED": "true",
            },
            env_clear_keys=("GOVOS_ALLOW_DEV_SECRETS",),
        )
        from fastapi.testclient import TestClient

        client = TestClient(auth_enabled.app)
        owner = client.post(
            "/api/v2/auth/session",
            json={"provider": "passkey", "subject": "owner-audit", "role": "Owner", "scopes": ["ops:owner"]},
        )
        from services import authz

        with mock.patch.object(authz._log, "warning") as warning:
            resp = client.post(
                "/api/v2/auth/diagnostics/claims",
                json={},
                headers={"Authorization": "Bearer " + owner.json()["access_token"], "X-Request-ID": "req-corr-42"},
            )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        matched = False
        for call in warning.call_args_list:
            if not call.args or call.args[0] != "auth_audit %s":
                continue
            payload = json.loads(call.args[1])
            if payload.get("event_type") == "diagnostic_claim_snapshot":
                matched = True
                self.assertEqual(payload["details"]["request_id"], "req-corr-42")
                self.assertEqual(payload["details"]["audit_event_id"], body["audit_event_id"])
        self.assertTrue(matched)

    def test_caller_tracker_includes_required_columns_and_callers(self):
        text = MIGRATION_DOC.read_text(encoding="utf-8")
        for field in (
            "caller name",
            "source path",
            "owner",
            "environment",
            "target service and endpoint",
            "expected role",
            "expected scopes",
            "expected tenant behavior",
            "token issuer and audience",
            "verification method",
            "current status",
            "rollback action",
            "evidence location",
        ):
            self.assertIn(field, text.lower())
        for caller in (
            "govOS scaffold session creator",
            "Tenant scaffold session creator",
            "Civic Signal scaffold session creator",
            "Naga owner console OAuth",
            "Naga GPU Brain panel",
            "AI service -> GPU router",
            "Documents service -> Tenant service",
            "V2 services -> Auth introspection",
        ):
            self.assertIn(caller, text)

    def test_acceptance_criteria_and_no_compatibility_mode_are_documented(self):
        text = MIGRATION_DOC.read_text(encoding="utf-8")
        self.assertIn("## ACCEPTANCE CRITERIA", text)
        self.assertIn("No broad compatibility mode is permitted.", text)
        self.assertIn("FINAL LIVE-VERIFICATION READINESS", text)
        self.assertIn("NO-GO", text)


if __name__ == "__main__":
    unittest.main()
