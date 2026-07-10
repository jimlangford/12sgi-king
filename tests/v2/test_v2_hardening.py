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
import importlib.util
import os
import requests
import sqlite3
import sys
import tempfile
import time
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

AUTH_MAIN = ROOT / 'services' / 'auth' / 'app' / 'main.py'
AI_MAIN = ROOT / 'services' / 'ai' / 'app' / 'main.py'
HEALTH_MAIN = ROOT / 'services' / 'health' / 'app' / 'main.py'


def _load_module(path, name, env_overrides=None, env_clear_keys=None):
    """Load a service's main.py fresh under a controlled environment, so import-time guards (the
    auth fail-closed secret check, the ai schema migration) run exactly as they would on process
    boot. Restores the real environment afterward regardless of outcome."""
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
        module._require_auth = lambda authorization: {'id': 'test-user'}
        module._ensure_case_exists = lambda case_id, authorization: None
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
    def _client(self, surfaces='auth=auth:8101,tenant=tenant:8102'):
        module = _load_module(
            HEALTH_MAIN,
            f'health_test_{id(self)}_{time.time_ns()}',
            env_overrides={
                'SURFACES_LIST': surfaces,
                'SURFACES_HEALTH_PATH': '/api/v2/ready',
                'COMMIT_SHA': 'abc123def456',
                'BUILD_TIMESTAMP': '2026-07-10T23:30:00Z',
                'ENVIRONMENT': 'king-server-private',
            },
        )
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


if __name__ == '__main__':
    unittest.main()
