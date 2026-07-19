"""Regression coverage for the 2026-07-09 hardening pass on govOS v2's auth + ai services.

Two real gaps, both flagged by docs/architecture/V1_TO_V2_UPGRADE_MAP.md (2026-07-07) and left
open until this pass:

  1. services/auth/app/main.py silently defaulted AUTH_SIGNING_SECRET / INTERNAL_SERVICE_TOKEN to
     well-known values published in this repo's own docker-compose.v2.yml comments -- an auth
     bypass the instant a deploy forgot to override them. It now fails to start on those defaults
     unless GOVOS_ALLOW_DEV_SECRETS is explicitly set.
  2. services/ai/app/main.py's /ai/assist endpoint returned a hardcoded, confident-sounding
     sentence whenever GPU inference was unavailable, indistinguishable from a real model answer --
     the same class of bug as tools/ops/workboard_evidence.py's pre-fix "auto-done on text alone"
     problem on the laptop system. Responses are now tagged grounded:true/false, ungrounded
     fallbacks are explicitly flagged, and /health exposes an auditable grounded_ratio.
"""
import json
import hashlib
import hmac
import os
import requests
import sqlite3
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tests.v2._test_helpers import load_module as _load_module  # noqa: E402  (see that module's docstring)

AUTH_MAIN = ROOT / 'services' / 'auth' / 'app' / 'main.py'
AI_MAIN = ROOT / 'services' / 'ai' / 'app' / 'main.py'
HEALTH_MAIN = ROOT / 'services' / 'health' / 'app' / 'main.py'


_AUTH_SECRET_KEYS = ('AUTH_SIGNING_SECRET', 'INTERNAL_SERVICE_TOKEN', 'GOVOS_ALLOW_DEV_SECRETS')


class TestAuthSecretsGuard(unittest.TestCase):
    """The auth service must fail closed on the published dev-default secrets unless the opt-in
    flag is explicitly set (V1_TO_V2_UPGRADE_MAP.md Section E)."""

    def test_boots_with_real_secrets_no_flag(self):
        module = _load_module(
            AUTH_MAIN, 'auth_real_secrets',
            env_overrides={'AUTH_SIGNING_SECRET': 'a-real-secret',
                            'INTERNAL_SERVICE_TOKEN': 'a-real-token',
                            'AUTH_DB_PATH': str(Path(tempfile.mkdtemp()) / 'auth.db')},
            env_clear_keys=_AUTH_SECRET_KEYS,
        )
        self.assertEqual(module.SIGNING_SECRET, 'a-real-secret')
        self.assertEqual(module.INTERNAL_SERVICE_TOKEN, 'a-real-token')

    def test_boots_on_dev_defaults_with_explicit_flag(self):
        module = _load_module(
            AUTH_MAIN, 'auth_dev_flag',
            env_overrides={'GOVOS_ALLOW_DEV_SECRETS': '1',
                            'AUTH_DB_PATH': str(Path(tempfile.mkdtemp()) / 'auth.db')},
            env_clear_keys=('AUTH_SIGNING_SECRET', 'INTERNAL_SERVICE_TOKEN'),
        )
        self.assertEqual(module.SIGNING_SECRET, module._DEV_SIGNING_SECRET)
        self.assertEqual(module.INTERNAL_SERVICE_TOKEN, module._DEV_SERVICE_TOKEN)

    def test_refuses_to_boot_on_default_signing_secret_without_flag(self):
        with self.assertRaises(RuntimeError) as ctx:
            _load_module(AUTH_MAIN, 'auth_fail_signing', env_clear_keys=_AUTH_SECRET_KEYS)
        self.assertIn('AUTH_SIGNING_SECRET', str(ctx.exception))

    def test_refuses_to_boot_on_default_service_token_without_flag(self):
        with self.assertRaises(RuntimeError) as ctx:
            _load_module(
                AUTH_MAIN, 'auth_fail_token',
                env_overrides={'AUTH_SIGNING_SECRET': 'a-real-secret'},
                env_clear_keys=_AUTH_SECRET_KEYS,
            )
        self.assertIn('INTERNAL_SERVICE_TOKEN', str(ctx.exception))

    def test_blank_flag_value_is_treated_as_unset(self):
        # docker-compose `${VAR:-}` with nothing supplied yields an empty string, not an absent
        # var -- that must NOT silently satisfy the opt-in.
        with self.assertRaises(RuntimeError):
            _load_module(
                AUTH_MAIN, 'auth_blank_flag',
                env_overrides={'GOVOS_ALLOW_DEV_SECRETS': ''},
                env_clear_keys=('AUTH_SIGNING_SECRET', 'INTERNAL_SERVICE_TOKEN'),
            )


class TestAuthClaimValidation(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix='auth-claims-')
        self.db_path = str(Path(self._tmp.name) / 'auth.db')
        self.module = _load_module(
            AUTH_MAIN,
            f'auth_claims_{time.time_ns()}',
            env_overrides={
                'AUTH_SIGNING_SECRET': 'claims-test-secret',
                'INTERNAL_SERVICE_TOKEN': 'claims-test-service-token',
                'AUTH_DB_PATH': self.db_path,
            },
            env_clear_keys=('GOVOS_ALLOW_DEV_SECRETS',),
        )
        self.client = TestClient(self.module.app)

    def tearDown(self):
        self.client.close()
        self._tmp.cleanup()

    def _mint_token(self, *, sub='u1', tenant_id='tenant-a', role='Municipality', scopes=None, iss=None, aud=None, exp=None):
        claims = {
            'iss': iss if iss is not None else self.module.AUTH_ISSUER,
            'aud': aud if aud is not None else self.module.AUTH_AUDIENCE,
            'sub': sub,
            'tenant_id': tenant_id,
            'role': role,
            'scopes': scopes if scopes is not None else ['tenant:read'],
            'exp': exp if exp is not None else int(self.module._now_utc().timestamp()) + 3600,
            'jti': 'jti-1',
            'provider': 'passkey',
        }
        header = {'alg': 'HS256', 'typ': 'JWT'}
        header_part = self.module._b64url(json.dumps(header, separators=(',', ':')).encode())
        payload_part = self.module._b64url(json.dumps(claims, separators=(',', ':')).encode())
        sig = hmac.new(self.module.SIGNING_SECRET.encode(), f'{header_part}.{payload_part}'.encode(), hashlib.sha256).digest()
        token = f'{header_part}.{payload_part}.{self.module._b64url(sig)}'
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                """
                INSERT OR REPLACE INTO sessions
                  (token, provider, subject, email, tenant_id, role, scopes_json, issuer, audience, issued_at, expires_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    token,
                    'passkey',
                    sub,
                    '',
                    tenant_id,
                    role,
                    json.dumps(claims['scopes']),
                    claims['iss'],
                    claims['aud'],
                    self.module._now_utc().isoformat(),
                    claims['exp'],
                ),
            )
            conn.commit()
        finally:
            conn.close()
        return token

    def _introspect(self, token):
        return self.client.post(
            '/api/v2/auth/introspect',
            json={'token': token},
            headers={'X-Service-Token': 'claims-test-service-token'},
        )

    def test_passkey_registration_requires_an_active_owner_session(self):
        cases = (
            (
                '/api/v2/auth/passkey/register/begin',
                {'user_id': 'owner-1', 'email': 'owner@example.com', 'display_name': 'Owner'},
            ),
            (
                '/api/v2/auth/passkey/register/complete',
                {'user_id': 'owner-1', 'credential_json': '{}', 'transports': []},
            ),
        )
        for path, payload in cases:
            with self.subTest(path=path):
                response = self.client.post(path, json=payload)
                self.assertEqual(response.status_code, 401)

        resident_token = self._mint_token(role='Resident', scopes=['tenant:read'])
        with mock.patch.object(self.module, 'OWNER_PASSKEY_EMAILS', {'owner@example.com'}):
            response = self.client.post(
                '/api/v2/auth/passkey/register/begin',
                json={'user_id': 'owner-1', 'email': 'owner@example.com', 'display_name': 'Owner'},
                headers={'Authorization': f'Bearer {resident_token}'},
            )
        self.assertEqual(response.status_code, 403)

    def test_expired_token_fails_introspection(self):
        token = self._mint_token(exp=int(self.module._now_utc().timestamp()) - 10)
        resp = self._introspect(token)
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.json()['active'])

    def test_malformed_token_fails_introspection(self):
        resp = self._introspect('not-a-jwt')
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.json()['active'])

    def test_wrong_issuer_fails_introspection(self):
        token = self._mint_token(iss='wrong-issuer')
        resp = self._introspect(token)
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.json()['active'])

    def test_wrong_audience_fails_introspection(self):
        token = self._mint_token(aud='wrong-audience')
        resp = self._introspect(token)
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.json()['active'])


class TestOAuthDebugEndpoint(unittest.TestCase):
    """GET /api/v2/auth/debug returns non-sensitive config status with no auth required."""

    def _make_client(self, extra_env=None):
        env = {
            'AUTH_SIGNING_SECRET': 'debug-test-secret',
            'INTERNAL_SERVICE_TOKEN': 'debug-test-service-token',
            'AUTH_DB_PATH': str(Path(tempfile.mkdtemp()) / 'auth.db'),
        }
        if extra_env:
            env.update(extra_env)
        module = _load_module(AUTH_MAIN, f'auth_debug_{time.time_ns()}',
                              env_overrides=env,
                              env_clear_keys=('GOVOS_ALLOW_DEV_SECRETS',))
        return module, TestClient(module.app)

    def test_debug_returns_200_without_auth(self):
        _, client = self._make_client()
        resp = client.get('/api/v2/auth/debug')
        self.assertEqual(resp.status_code, 200)

    def test_debug_shows_unconfigured_when_no_client_ids(self):
        _, client = self._make_client()
        body = client.get('/api/v2/auth/debug').json()
        self.assertFalse(body['github']['configured'])
        self.assertFalse(body['google']['configured'])

    def test_debug_shows_configured_when_github_client_id_set(self):
        _, client = self._make_client({'GITHUB_CLIENT_ID': 'gh-client-id-test'})
        body = client.get('/api/v2/auth/debug').json()
        self.assertTrue(body['github']['configured'])
        self.assertFalse(body['google']['configured'])

    def test_debug_includes_callback_uris(self):
        _, client = self._make_client()
        body = client.get('/api/v2/auth/debug').json()
        self.assertIn('/api/v2/auth/github/callback', body['github']['callback_uri'])
        self.assertIn('/api/v2/auth/google/callback', body['google']['callback_uri'])

    def test_debug_does_not_expose_secrets(self):
        _, client = self._make_client({
            'GITHUB_CLIENT_ID': 'gh-id',
            'GITHUB_CLIENT_SECRET': 'gh-secret-value',
            'GOOGLE_CLIENT_ID': 'gg-id',
            'GOOGLE_CLIENT_SECRET': 'gg-secret-value',
        })
        text = client.get('/api/v2/auth/debug').text
        self.assertNotIn('gh-secret-value', text)
        self.assertNotIn('gg-secret-value', text)
        self.assertNotIn('debug-test-secret', text)

    def test_debug_includes_owner_counts(self):
        _, client = self._make_client({
            'OWNER_GITHUB_LOGINS': 'alice,bob',
            'OWNER_GOOGLE_EMAILS': 'carol@example.com',
        })
        body = client.get('/api/v2/auth/debug').json()
        self.assertEqual(body['owner_github_login_count'], 2)
        self.assertEqual(body['owner_google_email_count'], 1)


class TestAiGroundingCorrectness(unittest.TestCase):
    """/ai/assist must never present an ungrounded template response with the same confidence as
    a real GPU-router answer."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix='ai-hardening-')
        self.db_path = Path(self._tmp.name) / 'ai.db'
        self._dispatch_log = Path(self._tmp.name) / 'dispatch.jsonl'

    def tearDown(self):
        self._tmp.cleanup()

    def _client(self):
        module = _load_module(
            AI_MAIN, 'ai_test_%s' % id(self),
            env_overrides={'AI_DB_PATH': str(self.db_path),
                            'WORKBOARD_DISPATCH_LOG': str(self._dispatch_log)},
        )
        module.require_claims = lambda **kwargs: {
            'sub': 'test-user',
            'role': 'Municipality',
            'tenant_id': 'tenant-a',
            'scopes': ['ai:assist'],
        }
        module._ensure_case_exists = lambda case_id, authorization: {'id': case_id, 'tenant_id': 'tenant-a'}
        return module, TestClient(module.app)

    def test_grounded_response_is_not_flagged_and_carries_no_stub_actions(self):
        module, client = self._client()
        module._gpu_infer = lambda **kwargs: 'Real model analysis of the case.'

        resp = client.post('/api/v2/ai/assist',
                            json={'case_id': 'c1', 'prompt': 'help'},
                            headers={'Authorization': 'Bearer x'})

        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertTrue(body['grounded'])
        self.assertEqual(body['summary'], 'Real model analysis of the case.')
        self.assertNotIn('UNGROUNDED', body['summary'])
        self.assertEqual(body['actions'], [])

    def test_ungrounded_response_is_explicitly_flagged(self):
        module, client = self._client()
        module._gpu_infer = lambda **kwargs: None

        resp = client.post('/api/v2/ai/assist',
                            json={'case_id': 'c1', 'prompt': 'help'},
                            headers={'Authorization': 'Bearer x'})

        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertFalse(body['grounded'])
        self.assertIn('UNGROUNDED', body['summary'])
        self.assertIn('human review', body['summary'].lower())
        self.assertEqual(len(body['actions']), 3)

    def test_grounded_flag_is_persisted_per_event(self):
        module, client = self._client()

        module._gpu_infer = lambda **kwargs: 'Grounded answer'
        client.post('/api/v2/ai/assist', json={'case_id': 'c1', 'prompt': 'p'},
                    headers={'Authorization': 'Bearer x'})

        module._gpu_infer = lambda **kwargs: None
        client.post('/api/v2/ai/assist', json={'case_id': 'c2', 'prompt': 'p'},
                    headers={'Authorization': 'Bearer x'})

        conn = sqlite3.connect(str(self.db_path))
        rows = dict(conn.execute('SELECT case_id, grounded FROM assist_events').fetchall())
        conn.close()
        self.assertEqual(rows, {'c1': 1, 'c2': 0})

    def test_health_reports_accurate_grounded_ratio(self):
        module, client = self._client()

        module._gpu_infer = lambda **kwargs: 'Grounded'
        client.post('/api/v2/ai/assist', json={'case_id': 'c1', 'prompt': 'p'},
                    headers={'Authorization': 'Bearer x'})
        module._gpu_infer = lambda **kwargs: None
        client.post('/api/v2/ai/assist', json={'case_id': 'c2', 'prompt': 'p'},
                    headers={'Authorization': 'Bearer x'})
        client.post('/api/v2/ai/assist', json={'case_id': 'c3', 'prompt': 'p'},
                    headers={'Authorization': 'Bearer x'})

        health = client.get('/api/v2/health').json()
        self.assertEqual(health['assist_count'], 3)
        self.assertEqual(health['grounded_count'], 1)
        self.assertAlmostEqual(health['grounded_ratio'], round(1 / 3, 3))

    def test_health_grounded_ratio_is_none_with_no_events(self):
        _, client = self._client()
        health = client.get('/api/v2/health').json()
        self.assertEqual(health['assist_count'], 0)
        self.assertIsNone(health['grounded_ratio'])


class TestAiSchemaMigration(unittest.TestCase):
    """The 'grounded' column must land on both fresh and pre-existing databases without error."""

    def test_fresh_database_gets_grounded_column(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / 'ai.db'
            module = _load_module(AI_MAIN, 'ai_migration_fresh',
                                   env_overrides={'AI_DB_PATH': str(db_path)})
            # init_db() already ran once at import; re-running it must be a no-op, not an error --
            # this is the guard against a table that predates the column being re-migrated on
            # every restart.
            module.init_db()
            module.init_db()

            conn = sqlite3.connect(str(db_path))
            cols = [row[1] for row in conn.execute('PRAGMA table_info(assist_events)')]
            conn.close()
            self.assertIn('grounded', cols)

    def test_pre_existing_old_schema_database_is_migrated_in_place(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / 'ai.db'
            # Simulate a database created by the pre-fix schema (no 'grounded' column), as would
            # exist on a real deployment upgrading in place.
            conn = sqlite3.connect(str(db_path))
            conn.execute(
                """
                CREATE TABLE assist_events (
                    id TEXT PRIMARY KEY,
                    case_id TEXT NOT NULL,
                    prompt TEXT NOT NULL,
                    context_json TEXT,
                    summary TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    created_by TEXT NOT NULL
                )
                """
            )
            conn.commit()
            conn.close()

            _load_module(AI_MAIN, 'ai_migration_old_schema',
                         env_overrides={'AI_DB_PATH': str(db_path)})

            conn = sqlite3.connect(str(db_path))
            cols = [row[1] for row in conn.execute('PRAGMA table_info(assist_events)')]
            conn.close()
            self.assertIn('grounded', cols)


class _FakeResponse:
    def __init__(self, status_code, payload=None, json_error=None):
        self.status_code = status_code
        self._payload = payload
        self._json_error = json_error

    def json(self):
        if self._json_error is not None:
            raise self._json_error
        return self._payload


class TestHealthReadinessHardening(unittest.TestCase):
    def setUp(self):
        self._saved_env = dict(os.environ)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._saved_env)

    def _load_health_module(self, surfaces):
        saved = dict(os.environ)
        try:
            os.environ.update(
                {
                    'SURFACES_LIST': surfaces,
                    'SURFACES_HEALTH_PATH': '/api/v2/ready',
                    'COMMIT_SHA': 'abc123def456',
                    'BUILD_TIMESTAMP': '2026-07-10T23:30:00Z',
                    'ENVIRONMENT': 'king-server-private',
                }
            )
            for key in (
                'services.health.app.main',
                'services.health.app.checks',
                'services.service_metadata',
            ):
                sys.modules.pop(key, None)
            import services.health.app.main as health_main
            return health_main
        finally:
            os.environ.clear()
            os.environ.update(saved)

    def _client(self, surfaces='auth=auth:8101,tenant=tenant:8102'):
        module = self._load_health_module(surfaces)
        os.environ['SURFACES_HEALTH_PATH'] = '/api/v2/ready'
        module.load_surfaces_from_env = lambda: {
            name.strip(): hostport.strip()
            for name, hostport in (
                part.split('=', 1) for part in surfaces.split(',') if '=' in part
            )
        }
        return module, TestClient(module.app)

    def _install_requests_stub(self, module, handlers):
        def fake_get(url, timeout):
            for needle, result in handlers.items():
                if needle in url:
                    if isinstance(result, Exception):
                        raise result
                    return result
            raise AssertionError(f'unexpected URL {url}')

        module.requests.get = fake_get

    def assertTopLevelProvenance(self, body):
        self.assertEqual(body['service'], 'health')
        self.assertEqual(body['commit_sha'], 'abc123def456')
        self.assertEqual(body['build_timestamp'], '2026-07-10T23:30:00Z')
        self.assertEqual(body['environment'], 'king-server-private')
        self.assertTrue(body['version'])

    def test_ready_returns_200_when_all_dependencies_ready(self):
        module, client = self._client()
        self._install_requests_stub(
            module,
            {
                'auth:8101': _FakeResponse(
                    200,
                    {
                        'status': 'ready',
                        'service': 'auth',
                        'version': '1.0.0',
                        'commit_sha': 'abc123def456',
                        'build_timestamp': '2026-07-10T23:30:00Z',
                        'environment': 'king-server-private',
                    },
                ),
                'tenant:8102': _FakeResponse(
                    200,
                    {
                        'status': 'ready',
                        'service': 'tenant',
                        'version': '1.0.0',
                        'commit_sha': 'abc123def456',
                        'build_timestamp': '2026-07-10T23:30:00Z',
                        'environment': 'king-server-private',
                    },
                ),
            },
        )

        resp = client.get('/api/v1/ready')

        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertTopLevelProvenance(body)
        self.assertEqual(body['status'], 'ready')
        self.assertTrue(body['services']['auth']['ok'])
        self.assertTrue(body['services']['tenant']['ok'])
        self.assertEqual(body['services']['auth']['provenance']['service'], 'auth')

    def test_ready_returns_503_when_dependency_unreachable(self):
        module, client = self._client()
        self._install_requests_stub(
            module,
            {
                'auth:8101': _FakeResponse(
                    200,
                    {
                        'status': 'ready',
                        'service': 'auth',
                        'version': '1.0.0',
                        'commit_sha': 'abc123def456',
                        'build_timestamp': '2026-07-10T23:30:00Z',
                        'environment': 'king-server-private',
                    },
                ),
                'tenant:8102': requests.ConnectionError(
                    'connection failed token=super-secret-value'
                ),
            },
        )

        resp = client.get('/api/v1/ready')

        self.assertEqual(resp.status_code, 503)
        body = resp.json()
        self.assertTopLevelProvenance(body)
        self.assertEqual(body['status'], 'not-ready')
        self.assertEqual(body['services']['tenant']['failure'], 'unreachable')
        self.assertIn('connection failed', body['services']['tenant']['detail'])
        self.assertNotIn('super-secret-value', body['services']['tenant']['detail'])

    def test_ready_returns_503_on_malformed_dependency_json(self):
        module, client = self._client()
        self._install_requests_stub(
            module,
            {
                'auth:8101': _FakeResponse(
                    200,
                    {
                        'status': 'ready',
                        'service': 'auth',
                        'version': '1.0.0',
                        'commit_sha': 'abc123def456',
                        'build_timestamp': '2026-07-10T23:30:00Z',
                        'environment': 'king-server-private',
                    },
                ),
                'tenant:8102': _FakeResponse(200, json_error=ValueError('bad json')),
            },
        )

        resp = client.get('/api/v1/ready')

        self.assertEqual(resp.status_code, 503)
        body = resp.json()
        self.assertTopLevelProvenance(body)
        self.assertEqual(body['services']['tenant']['failure'], 'malformed-json')
        self.assertIn('valid JSON', body['services']['tenant']['detail'])

    def test_ready_returns_503_when_dependency_reports_not_ready(self):
        module, client = self._client()
        self._install_requests_stub(
            module,
            {
                'auth:8101': _FakeResponse(
                    200,
                    {
                        'status': 'ready',
                        'service': 'auth',
                        'version': '1.0.0',
                        'commit_sha': 'abc123def456',
                        'build_timestamp': '2026-07-10T23:30:00Z',
                        'environment': 'king-server-private',
                    },
                ),
                'tenant:8102': _FakeResponse(
                    503,
                    {
                        'status': 'not-ready',
                        'service': 'tenant',
                        'version': '1.0.0',
                        'commit_sha': 'abc123def456',
                        'build_timestamp': '2026-07-10T23:30:00Z',
                        'environment': 'king-server-private',
                        'dependencies': {'database': False},
                    },
                ),
            },
        )

        resp = client.get('/api/v1/ready')

        self.assertEqual(resp.status_code, 503)
        body = resp.json()
        self.assertTopLevelProvenance(body)
        self.assertEqual(body['services']['tenant']['failure'], 'not-ready')
        self.assertEqual(body['services']['tenant']['reported_status'], 'not-ready')
        self.assertEqual(body['services']['tenant']['dependencies'], {'database': False})

    def test_provenance_fields_remain_present_on_success_and_failure(self):
        ready_module, ready_client = self._client()
        self._install_requests_stub(
            ready_module,
            {
                'auth:8101': _FakeResponse(
                    200,
                    {
                        'status': 'ready',
                        'service': 'auth',
                        'version': '1.0.0',
                        'commit_sha': 'abc123def456',
                        'build_timestamp': '2026-07-10T23:30:00Z',
                        'environment': 'king-server-private',
                    },
                ),
                'tenant:8102': _FakeResponse(
                    200,
                    {
                        'status': 'ready',
                        'service': 'tenant',
                        'version': '1.0.0',
                        'commit_sha': 'abc123def456',
                        'build_timestamp': '2026-07-10T23:30:00Z',
                        'environment': 'king-server-private',
                    },
                ),
            },
        )
        fail_module, fail_client = self._client()
        self._install_requests_stub(
            fail_module,
            {
                'auth:8101': _FakeResponse(
                    200,
                    {
                        'status': 'ready',
                        'service': 'auth',
                        'version': '1.0.0',
                        'commit_sha': 'abc123def456',
                        'build_timestamp': '2026-07-10T23:30:00Z',
                        'environment': 'king-server-private',
                    },
                ),
                'tenant:8102': _FakeResponse(200, json_error=ValueError('bad json')),
            },
        )

        ready_body = ready_client.get('/api/v1/ready').json()
        fail_body = fail_client.get('/api/v1/ready').json()

        for body in (ready_body, fail_body):
            for key in ('service', 'version', 'commit_sha', 'build_timestamp', 'environment'):
                self.assertIn(key, body)


class TestAuthDbPathIsolationAcrossLoads(unittest.TestCase):
    """Regression test for the 2026-07-16 CI failure (commit 4f35f13): loading
    services/auth/app/main.py fresh per test does NOT by itself isolate the AUTH_DB_PATH
    env override, because main.py's `from services.auth.app.passkeys import init_passkeys_db`
    is a plain import -- Python caches services.auth.app.passkeys in
    sys.modules, so a SECOND load in the same process silently reused the FIRST load's
    DB_PATH (a tempdir that was often already deleted by then), instead of honoring its
    own env_overrides. This test loads auth's main.py twice, each with its own fresh
    tempdir, and asserts BOTH actually create their passkeys db at their OWN path -- the
    exact behavior _test_helpers.load_module's sys.modules clearing exists to guarantee."""

    def test_second_load_uses_its_own_db_path_not_the_first_loads(self):
        tmp_a = tempfile.TemporaryDirectory(prefix='auth-db-isolation-a-')
        tmp_b = tempfile.TemporaryDirectory(prefix='auth-db-isolation-b-')
        self.addCleanup(tmp_a.cleanup)
        self.addCleanup(tmp_b.cleanup)
        db_path_a = str(Path(tmp_a.name) / 'auth.db')
        db_path_b = str(Path(tmp_b.name) / 'auth.db')
        self.assertNotEqual(db_path_a, db_path_b)

        common_env = {
            'AUTH_SIGNING_SECRET': 'isolation-test-secret',
            'INTERNAL_SERVICE_TOKEN': 'isolation-test-service-token',
        }

        module_a = _load_module(
            AUTH_MAIN, f'auth_isolation_a_{time.time_ns()}',
            env_overrides={**common_env, 'AUTH_DB_PATH': db_path_a},
            env_clear_keys=('GOVOS_ALLOW_DEV_SECRETS',),
        )
        self.assertTrue(
            os.path.exists(db_path_a),
            'first load did not create its passkeys db at its own AUTH_DB_PATH',
        )

        # Second load, different tempdir, same process -- this is exactly the scenario that
        # silently broke before the sys.modules clearing fix: without it, passkeys.py
        # stays cached from the first load and never re-reads AUTH_DB_PATH.
        module_b = _load_module(
            AUTH_MAIN, f'auth_isolation_b_{time.time_ns()}',
            env_overrides={**common_env, 'AUTH_DB_PATH': db_path_b},
            env_clear_keys=('GOVOS_ALLOW_DEV_SECRETS',),
        )
        self.assertTrue(
            os.path.exists(db_path_b),
            'second load did not create its own passkeys db -- it likely reused the first '
            "load's cached DB_PATH (the exact regression this test guards against)",
        )

        # Both modules' own DB_PATH constant (read fresh at each load) must reflect the
        # load that produced them, not whichever loaded last.
        self.assertEqual(module_a.DB_PATH, db_path_a)
        self.assertEqual(module_b.DB_PATH, db_path_b)


if __name__ == '__main__':
    unittest.main()
