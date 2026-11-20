import json
import os
import re
import sys
import tempfile
import time
import unittest
import urllib.parse
from pathlib import Path
from unittest import mock

from fastapi import HTTPException

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tests.v2._test_helpers import load_module as _load_module  # noqa: E402  (see that module's docstring)

AUTH_MAIN = ROOT / "services" / "auth" / "app" / "main.py"
GOVOS_APP = ROOT / "apps" / "govos" / "public" / "app.js"
TENANT_APP = ROOT / "apps" / "tenant" / "public" / "app.js"
CIVIC_APP = ROOT / "apps" / "civic-signal" / "public" / "app.js"
LOCAL_DEV_DOC = ROOT / "docs" / "GOVOS_V2_LOCAL_DEV.md"
MIGRATION_DOC = ROOT / "docs" / "V2_CLAIM_CLIENT_MIGRATION.md"


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
        self.service_headers = {"X-Service-Token": "claim-client-service-token"}

    def tearDown(self):
        self.tmp.cleanup()

    def test_session_mint_requires_service_trust(self):
        resp = self.client.post(
            "/api/v2/auth/session",
            json={"provider": "passkey", "subject": "attacker", "role": "Owner"},
        )
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(resp.json()["detail"]["error"]["code"], "forbidden")

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
            headers=self.service_headers,
        )
        self.assertEqual(resp.status_code, 200)
        claims = resp.json()["claims"]
        for field in ("sub", "tenant_id", "role", "scopes", "exp", "iss", "aud"):
            self.assertIn(field, claims)
        for field in ("entitlement_tier", "entitlement_verified", "entitlement_capabilities", "entitlement_source"):
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
            headers=self.service_headers,
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
            headers=self.service_headers,
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

    def test_google_claims_fail_closed_when_capability_requires_verified_entitlement(self):
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
                            "sub": "google:resident-1",
                            "tenant_id": "tenant-a",
                            "role": "Resident",
                            "provider": "google",
                            "scopes": ["tenant:read"],
                            "exp": 9999999999,
                            "iss": "govos-auth",
                            "aud": "govos-v2",
                            "entitlement_verified": False,
                            "entitlement_tier": "free",
                            "entitlement_capabilities": [],
                            "entitlement_source": "unavailable",
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
                    required_capabilities={"ai_advice"},
                )
        self.assertEqual(ctx.exception.status_code, 403)
        self.assertEqual(ctx.exception.detail["error"]["code"], "forbidden")

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
            headers=self.service_headers,
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
            headers=self.service_headers,
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
            headers=self.service_headers,
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
            headers=self.service_headers,
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

    def test_identity_link_diagnostic_endpoint_reports_link_and_last_reason(self):
        auth_enabled = _load_module(
            AUTH_MAIN,
            f"auth_diag_identity_{time.time_ns()}",
            env_overrides={
                "AUTH_SIGNING_SECRET": "claim-client-secret",
                "INTERNAL_SERVICE_TOKEN": "claim-client-service-token",
                "AUTH_DB_PATH": str(Path(self.tmp.name) / "auth_diag_identity.db"),
                "ENTITLEMENT_DB_PATH": str(Path(self.tmp.name) / "entitlements_diag_identity.db"),
                "AUTH_VERIFICATION_DIAGNOSTICS_ENABLED": "true",
            },
            env_clear_keys=("GOVOS_ALLOW_DEV_SECRETS",),
        )
        from fastapi.testclient import TestClient

        client = TestClient(auth_enabled.app)
        owner = client.post(
            "/api/v2/auth/session",
            json={
                "provider": "google",
                "subject": "google:owner-diag",
                "email": "owner@example.com",
                "role": "Owner",
                "scopes": ["ops:owner"],
            },
            headers=self.service_headers,
        )
        resident = client.post(
            "/api/v2/auth/session",
            json={
                "provider": "passkey",
                "subject": "resident-diag",
                "tenant_id": "tenant-a",
                "role": "Resident",
                "scopes": ["tenant:read"],
            },
            headers=self.service_headers,
        )
        self.assertEqual(owner.status_code, 200)
        self.assertEqual(resident.status_code, 200)
        owner_token = owner.json()["access_token"]

        denied = client.post(
            "/api/v2/auth/diagnostics/identity-link",
            json={},
            headers={"Authorization": "Bearer " + resident.json()["access_token"]},
        )
        self.assertEqual(denied.status_code, 403)

        allowed = client.post(
            "/api/v2/auth/diagnostics/identity-link",
            json={"token": owner_token},
            headers={"Authorization": "Bearer " + owner_token, "X-Request-ID": "req-link-1"},
        )
        self.assertEqual(allowed.status_code, 200)
        payload = allowed.json()
        self.assertEqual(payload["provider"], "google")
        self.assertTrue(str(payload["subject"]).startswith("sha256:"))
        self.assertTrue(str(payload["email"]).startswith("sha256:"))
        self.assertTrue(payload["has_identity_link"])
        self.assertIn(payload["last_entitlement_verification_reason"], {"wordpress_unverified", "cached_link"})
        self.assertEqual(payload["request_id"], "req-link-1")

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
            headers=self.service_headers,
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


class TestOwnerOAuthLaunchReadiness(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="v2-owner-oauth-")
        self.auth_db = str(Path(self.tmp.name) / "auth.db")
        self.auth_env = {
            "AUTH_SIGNING_SECRET": "owner-oauth-secret",
            "INTERNAL_SERVICE_TOKEN": "owner-oauth-service-token",
            "AUTH_DB_PATH": self.auth_db,
            "GITHUB_CLIENT_ID": "github-client-id",
            "GITHUB_CLIENT_SECRET": "github-client-secret",
            "GOOGLE_CLIENT_ID": "google-client-id",
            "GOOGLE_CLIENT_SECRET": "google-client-secret",
            "OWNER_GITHUB_LOGINS": " JimLangford , second-owner ",
            "OWNER_GOOGLE_EMAILS": " Owner@Example.com , backup@example.com ",
            "OWNER_MAGIC_EMAILS": " Owner@Example.com , backup@example.com ",
            "SMTP_HOST": "smtp.example.com",
            "SMTP_PORT": "587",
            "SMTP_USER": "mailer@example.com",
            "SMTP_PASS": "test-app-password",
            "SMTP_FROM": "mailer@example.com",
            "AUTH_PUBLIC_URL": "https://auth.example.com",
            "OAUTH_REDIRECT_BASE": "https://console.example.com/king/",
        }
        self.auth = _load_module(
            AUTH_MAIN,
            f"auth_owner_oauth_{time.time_ns()}",
            env_overrides=self.auth_env,
            env_clear_keys=("GOVOS_ALLOW_DEV_SECRETS",),
        )
        from fastapi.testclient import TestClient

        self.client = TestClient(self.auth.app)

    def tearDown(self):
        self.tmp.cleanup()

    def test_owner_allowlists_are_trimmed_and_normalized(self):
        self.assertEqual(self.auth.OWNER_GITHUB_LOGINS, {"jimlangford", "second-owner"})
        self.assertEqual(self.auth.OWNER_GOOGLE_EMAILS, {"owner@example.com", "backup@example.com"})
        self.assertEqual(self.auth.OWNER_MAGIC_EMAILS, {"owner@example.com", "backup@example.com"})

    def test_wordpress_provider_discovery_exposes_google_and_magic_email(self):
        resp = self.client.get("/api/v2/auth/providers")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertTrue(body["google"]["available"])
        self.assertTrue(body["magic_email"]["available"])
        self.assertEqual(
            body["google"]["callback_uri"],
            "https://auth.example.com/api/v2/auth/google/callback",
        )
        self.assertEqual(
            body["magic_email"]["request_url"],
            "https://auth.example.com/api/v2/auth/magic-link",
        )

    def test_github_oauth_callback_accepts_case_insensitive_allowlist(self):
        state = self.auth._make_oauth_state("github")

        token_resp = mock.Mock()
        token_resp.raise_for_status.return_value = None
        token_resp.json.return_value = {"access_token": "gh-access-token"}

        user_resp = mock.Mock()
        user_resp.raise_for_status.return_value = None
        user_resp.json.return_value = {"login": "JimLangford", "email": "owner@example.com"}

        with mock.patch.object(self.auth._requests, "post", return_value=token_resp), mock.patch.object(
            self.auth._requests, "get", return_value=user_resp
        ):
            resp = self.client.get(
                "/api/v2/auth/github/callback",
                params={"code": "oauth-code", "state": state},
                follow_redirects=False,
            )

        self.assertEqual(resp.status_code, 307)
        redirect = resp.headers["location"]
        self.assertTrue(redirect.startswith("https://console.example.com/king/#token="))
        token = urllib.parse.unquote(redirect.split("#token=", 1)[1])
        claims = self.auth._decode_and_verify_token(token)[1]
        self.assertEqual(claims["sub"], "github:JimLangford")
        self.assertEqual(claims["role"], "Owner")

    def test_google_oauth_callback_rejects_wrong_audience(self):
        state = self.auth._make_oauth_state("google")
        payload = {
            "email": "owner@example.com",
            "sub": "google-subject",
            "aud": "wrong-client-id",
            "iss": "https://accounts.google.com",
            "email_verified": True,
            "exp": int(time.time()) + 300,
        }

        token_resp = mock.Mock()
        token_resp.raise_for_status.return_value = None
        token_resp.json.return_value = {"id_token": "google-signed-id-token"}
        verify_resp = mock.Mock()
        verify_resp.raise_for_status.return_value = None
        verify_resp.json.return_value = payload

        with mock.patch.object(self.auth._requests, "post", return_value=token_resp), mock.patch.object(
            self.auth._requests, "get", return_value=verify_resp
        ):
            resp = self.client.get(
                "/api/v2/auth/google/callback",
                params={"code": "oauth-code", "state": state},
                follow_redirects=False,
            )

        self.assertEqual(resp.status_code, 400)
        self.assertIn("did not match this configured app", resp.text)

    def test_google_oauth_callback_requires_verified_email(self):
        state = self.auth._make_oauth_state("google")
        payload = {
            "email": "owner@example.com",
            "sub": "google-subject",
            "aud": "google-client-id",
            "iss": "https://accounts.google.com",
            "email_verified": False,
            "exp": int(time.time()) + 300,
        }

        token_resp = mock.Mock()
        token_resp.raise_for_status.return_value = None
        token_resp.json.return_value = {"id_token": "google-signed-id-token"}
        verify_resp = mock.Mock()
        verify_resp.raise_for_status.return_value = None
        verify_resp.json.return_value = payload

        with mock.patch.object(self.auth._requests, "post", return_value=token_resp), mock.patch.object(
            self.auth._requests, "get", return_value=verify_resp
        ):
            resp = self.client.get(
                "/api/v2/auth/google/callback",
                params={"code": "oauth-code", "state": state},
                follow_redirects=False,
            )

        self.assertEqual(resp.status_code, 400)
        self.assertIn("e-mail is not verified", resp.text)

    def test_google_oauth_callback_accepts_google_verified_owner(self):
        state = self.auth._make_oauth_state("google")
        token_resp = mock.Mock()
        token_resp.raise_for_status.return_value = None
        token_resp.json.return_value = {"id_token": "google-signed-id-token"}
        verify_resp = mock.Mock()
        verify_resp.raise_for_status.return_value = None
        verify_resp.json.return_value = {
            "email": "Owner@Example.com",
            "sub": "google-subject",
            "aud": "google-client-id",
            "iss": "accounts.google.com",
            "email_verified": "true",
            "exp": str(int(time.time()) + 300),
        }
        with mock.patch.object(self.auth._requests, "post", return_value=token_resp), mock.patch.object(
            self.auth._requests, "get", return_value=verify_resp
        ):
            resp = self.client.get(
                "/api/v2/auth/google/callback",
                params={"code": "oauth-code", "state": state},
                follow_redirects=False,
            )
        self.assertEqual(resp.status_code, 307)
        token = urllib.parse.unquote(resp.headers["location"].split("#token=", 1)[1])
        claims = self.auth._decode_and_verify_token(token)[1]
        self.assertEqual(claims["sub"], "google:google-subject")
        self.assertEqual(claims["role"], "Owner")

    def test_magic_email_token_survives_restart_and_rejects_replay(self):
        delivered_urls = []
        with mock.patch.object(
            self.auth,
            "_send_magic_email",
            side_effect=lambda _email, url: delivered_urls.append(url) or True,
        ):
            requested = self.client.post(
                "/api/v2/auth/magic-link",
                json={"email": "OWNER@example.com"},
            )
        self.assertEqual(requested.status_code, 202)
        self.assertEqual(len(delivered_urls), 1)
        parsed = urllib.parse.urlparse(delivered_urls[0])
        token = urllib.parse.parse_qs(parsed.query)["token"][0]

        restarted = _load_module(
            AUTH_MAIN,
            f"auth_owner_oauth_restart_{time.time_ns()}",
            env_overrides=self.auth_env,
            env_clear_keys=("GOVOS_ALLOW_DEV_SECRETS",),
        )
        from fastapi.testclient import TestClient

        restarted_client = TestClient(restarted.app)
        verified = restarted_client.get(
            "/api/v2/auth/magic-link/verify",
            params={"token": token},
            follow_redirects=False,
        )
        self.assertEqual(verified.status_code, 307)
        session_token = urllib.parse.unquote(verified.headers["location"].split("#token=", 1)[1])
        claims = restarted._decode_and_verify_token(session_token)[1]
        self.assertEqual(claims["sub"], "magic:owner@example.com")
        self.assertEqual(claims["role"], "Owner")

        replay = restarted_client.get(
            "/api/v2/auth/magic-link/verify",
            params={"token": token},
            follow_redirects=False,
        )
        self.assertEqual(replay.status_code, 400)
        self.assertIn("invalid or has already been used", replay.text)

    def test_magic_email_does_not_disclose_allowlist_membership(self):
        with mock.patch.object(self.auth, "_send_magic_email") as sender:
            resp = self.client.post(
                "/api/v2/auth/magic-link",
                json={"email": "not-authorized@example.com"},
            )
        self.assertEqual(resp.status_code, 202)
        self.assertEqual(resp.json(), self.auth._MAGIC_LINK_ACCEPTED)
        sender.assert_not_called()


if __name__ == "__main__":
    unittest.main()
