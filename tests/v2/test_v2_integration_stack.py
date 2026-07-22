import json
import importlib.util
import os
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from urllib import error, request

# Repo root, derived from this file's location (tests/v2/<file>.py) instead of hardcoding the
# GitHub Actions runner's checkout path -- that made this suite impossible to run anywhere except
# CI. Works identically in CI and local dev.
ROOT = Path(__file__).resolve().parents[2]
BASE_PORT = int(os.environ.get('V2_TEST_BASE_PORT', '19101'))


def http_json(method: str, url: str, payload: dict | None = None, headers: dict | None = None, timeout: float = 5.0):
    body = None
    merged_headers = {'Content-Type': 'application/json'}
    if headers:
        merged_headers.update(headers)
    if payload is not None:
        body = json.dumps(payload).encode()

    req = request.Request(url, data=body, headers=merged_headers, method=method)
    try:
        with request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode().strip()
            data = json.loads(raw) if raw else None
            return resp.status, data
    except error.HTTPError as exc:
        raw = exc.read().decode().strip()
        data = json.loads(raw) if raw else None
        return exc.code, data


def wait_for_service(url: str, timeout: float = 20.0):
    end = time.time() + timeout
    last_error = None
    while time.time() < end:
        try:
            status, _ = http_json('GET', url, payload=None, headers={'Content-Type': 'application/json'}, timeout=1.0)
            if status in (200, 503):
                return
        except Exception as exc:  # pragma: no cover - setup helper
            last_error = exc
        time.sleep(0.3)
    raise AssertionError(f'Service did not start: {url} ({last_error})')


class TestV2IntegrationStack(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if importlib.util.find_spec('uvicorn') is None:
            raise unittest.SkipTest('uvicorn is required to run full-stack v2 integration tests')

        cls.tempdir = tempfile.TemporaryDirectory(prefix='v2-stack-')
        cls.processes = []
        cls.service_token = 'integration-service-token'
        # A real (non-default) signing secret -- exercises the same fail-closed startup guard
        # production runs under (services/auth/app/main.py refuses to boot on the published dev
        # default unless GOVOS_ALLOW_DEV_SECRETS=1), rather than routing the test suite around it.
        cls.auth_signing_secret = 'integration-test-signing-secret-not-the-dev-default'
        cls.dispatch_log = Path(cls.tempdir.name) / 'workboard-dispatch.jsonl'

        cls.ports = {
            'auth': BASE_PORT,
            'tenant': BASE_PORT + 1,
            'documents': BASE_PORT + 2,
            'storage': BASE_PORT + 3,
            'ai': BASE_PORT + 4,
            'health': BASE_PORT + 5,
            'tenant_fail': BASE_PORT + 6,
        }

        cls.urls = {
            name: f"http://127.0.0.1:{port}" for name, port in cls.ports.items()
        }

        cls._start_full_stack()

    @classmethod
    def tearDownClass(cls):
        for proc in cls.processes:
            if proc.poll() is None:
                proc.terminate()
        for proc in cls.processes:
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
        cls.tempdir.cleanup()

    @classmethod
    def _start_service(cls, name: str, app_dir: str, port: int, extra_env: dict | None = None):
        env = os.environ.copy()
        env.update(
            {
                'PYTHONUNBUFFERED': '1',
                'INTERNAL_SERVICE_TOKEN': cls.service_token,
                'AUTH_SIGNING_SECRET': cls.auth_signing_secret,
                'AUTH_INTROSPECTION_URL': f"{cls.urls['auth']}/api/v2/auth/introspect",
                'AUTH_READY_URL': f"{cls.urls['auth']}/api/v2/ready",
                'TENANT_SERVICE_URL': cls.urls['tenant'],
                'TENANT_READY_URL': f"{cls.urls['tenant']}/api/v2/ready",
                'WORKBOARD_DISPATCH_LOG': str(cls.dispatch_log),
                'WORKBOARD_TARGET_THREAD': 'workboard-quad-os',
                # Explicitly unset -- these tests must prove the stack boots on REAL secrets, not
                # the dev-bypass flag. If GOVOS_ALLOW_DEV_SECRETS leaks in from the outer CI/dev
                # environment, this test would silently stop exercising the fail-closed guard.
                'GOVOS_ALLOW_DEV_SECRETS': '',
            }
        )
        if extra_env:
            env.update(extra_env)

        proc = subprocess.Popen(
            [
                sys.executable,
                '-m',
                'uvicorn',
                'app.main:app',
                '--app-dir',
                str(ROOT / app_dir),
                '--host',
                '127.0.0.1',
                '--port',
                str(port),
            ],
            cwd=str(ROOT),
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        cls.processes.append(proc)

    def _dispatch_entries(self):
        if not self.dispatch_log.exists():
            return []
        entries = []
        for line in self.dispatch_log.read_text(encoding='utf-8').splitlines():
            if not line.strip():
                continue
            entries.append(json.loads(line))
        return entries

    @classmethod
    def _start_full_stack(cls):
        base = Path(cls.tempdir.name)
        cls._start_service(
            'auth',
            'services/auth',
            cls.ports['auth'],
            {'AUTH_DB_PATH': str(base / 'auth.db')},
        )
        cls._start_service(
            'tenant',
            'services/tenant',
            cls.ports['tenant'],
            {'TENANT_DB_PATH': str(base / 'tenant.db')},
        )
        cls._start_service(
            'documents',
            'services/documents',
            cls.ports['documents'],
            {'DOCUMENTS_DB_PATH': str(base / 'documents.db')},
        )
        cls._start_service(
            'storage',
            'services/storage',
            cls.ports['storage'],
            {'STORAGE_DB_PATH': str(base / 'storage.db')},
        )
        cls._start_service(
            'ai',
            'services/ai',
            cls.ports['ai'],
            {'AI_DB_PATH': str(base / 'ai.db')},
        )
        surfaces = ','.join(
            [
                f"auth=127.0.0.1:{cls.ports['auth']}",
                f"tenant=127.0.0.1:{cls.ports['tenant']}",
                f"documents=127.0.0.1:{cls.ports['documents']}",
                f"storage=127.0.0.1:{cls.ports['storage']}",
                f"ai=127.0.0.1:{cls.ports['ai']}",
            ]
        )
        cls._start_service(
            'health',
            'services/health',
            cls.ports['health'],
            {
                'SURFACES_LIST': surfaces,
                'SURFACES_HEALTH_PATH': '/api/v2/ready',
            },
        )

        wait_for_service(f"{cls.urls['auth']}/api/v2/live")
        wait_for_service(f"{cls.urls['tenant']}/api/v2/live")
        wait_for_service(f"{cls.urls['documents']}/api/v2/live")
        wait_for_service(f"{cls.urls['storage']}/api/v2/live")
        wait_for_service(f"{cls.urls['ai']}/api/v2/live")
        wait_for_service(f"{cls.urls['health']}/api/v1/live")

    def _create_session(
        self,
        *,
        subject: str = "integration-user-1",
        tenant_id: str = "tenant-1",
        role: str = "Municipality",
        scopes: list[str] | None = None,
    ):
        status, body = http_json(
            'POST',
            f"{self.urls['auth']}/api/v2/auth/session",
            {
                'provider': 'passkey',
                'subject': subject,
                'email': 'integration@example.com',
                'tenant_id': tenant_id,
                'role': role,
                'scopes': scopes,
            },
            headers={'X-Service-Token': self.service_token},
        )
        self.assertEqual(status, 200)
        return body['access_token']

    def test_end_to_end_stack_flow(self):
        before = len(self._dispatch_entries())
        token = self._create_session(scopes=["tenant:write", "tenant:read", "documents:write", "documents:read", "storage:write", "storage:read", "ai:assist"])
        auth_headers = {'Authorization': 'Bearer ' + token}

        status, case = http_json(
            'POST',
            f"{self.urls['tenant']}/api/v2/cases",
            {'tenant_id': 'tenant-1', 'title': 'Noise complaint package', 'notes': 'Initial filing'},
            headers=auth_headers,
        )
        self.assertEqual(status, 201)

        status, document = http_json(
            'POST',
            f"{self.urls['documents']}/api/v2/documents/generate",
            {
                'template_id': 'notice-template',
                'case_id': case['id'],
                'output_format': 'pdf',
                'fields': {'address': '123 Test St'},
            },
            headers=auth_headers,
        )
        self.assertEqual(status, 201)
        self.assertEqual(document['case_id'], case['id'])

        status, obj = http_json(
            'POST',
            f"{self.urls['storage']}/api/v2/storage/objects",
            {'name': 'evidence.pdf', 'content_type': 'application/pdf', 'size_bytes': 12},
            headers=auth_headers,
        )
        self.assertEqual(status, 201)
        self.assertIn('download_url', obj)

        status, ai = http_json(
            'POST',
            f"{self.urls['ai']}/api/v2/ai/assist",
            {'case_id': case['id'], 'prompt': 'How should I proceed?', 'context': {'priority': 'high'}},
            headers=auth_headers,
        )
        self.assertEqual(status, 200)
        self.assertEqual(ai['case_id'], case['id'])

        status, ready = http_json('GET', f"{self.urls['health']}/api/v1/ready")
        self.assertEqual(status, 200)
        self.assertEqual(ready['status'], 'ready')
        for service_name in ['auth', 'tenant', 'documents', 'storage', 'ai']:
            self.assertTrue(ready['services'][service_name]['ok'])

        queued = self._dispatch_entries()[before:]
        self.assertGreaterEqual(len(queued), 4)
        expected_actions = {
            'case.created',
            'document.generated',
            'storage.object.created',
            'ai.assist.completed',
        }
        seen_actions = {entry.get('job', {}).get('action') for entry in queued}
        self.assertTrue(expected_actions.issubset(seen_actions))

        # V2 lane contract: every dispatch entry must carry a lane field.
        # engineering jobs self-heal; creative jobs (document.generated) need human review.
        engineering_actions = {'case.created', 'storage.object.created', 'ai.assist.completed'}
        creative_actions = {'document.generated'}
        for entry in queued:
            action = entry.get('job', {}).get('action')
            if action not in expected_actions:
                continue
            self.assertEqual(entry.get('schema'), 'workboard-job-v2')
            self.assertEqual(entry.get('target_thread'), 'workboard-quad-os')
            self.assertEqual(entry.get('status'), 'queued')
            self.assertIn(entry.get('lane'), {'engineering', 'creative', 'output'}, msg=f"lane missing on {action}")
            if action in engineering_actions:
                self.assertEqual(entry.get('lane'), 'engineering', msg=f"{action} must be engineering lane")
            elif action in creative_actions:
                self.assertEqual(entry.get('lane'), 'creative', msg=f"{action} must be creative lane")

    def test_auth_and_failure_paths(self):
        status, body = http_json(
            'POST',
            f"{self.urls['tenant']}/api/v2/cases",
            {'tenant_id': 'tenant-1', 'title': 'Missing auth'},
            headers={},
        )
        self.assertEqual(status, 401)
        self.assertEqual(body['detail']['error']['code'], 'unauthorized')

        token = self._create_session(scopes=["tenant:write", "tenant:read", "documents:write"])
        auth_headers = {'Authorization': 'Bearer ' + token}

        status, body = http_json(
            'POST',
            f"{self.urls['documents']}/api/v2/documents/generate",
            {'template_id': 'notice-template', 'case_id': 'missing-case', 'output_format': 'pdf'},
            headers=auth_headers,
        )
        self.assertEqual(status, 404)
        self.assertEqual(body['detail']['error']['code'], 'resource_not_found')

    def test_case_status_update_emits_event(self):
        token = self._create_session(subject="u-status", tenant_id="tenant-status", scopes=["tenant:write", "tenant:read"])
        auth_headers = {'Authorization': 'Bearer ' + token}

        status, created = http_json(
            'POST',
            f"{self.urls['tenant']}/api/v2/cases",
            {'tenant_id': 'tenant-status', 'title': 'Status update test case', 'status': 'open'},
            headers=auth_headers,
        )
        self.assertEqual(status, 201)
        case_id = created['id']
        self.assertEqual(created['status'], 'open')

        status, updated = http_json(
            'PATCH',
            f"{self.urls['tenant']}/api/v2/cases/{case_id}/status",
            {'status': 'in_progress', 'actor': 'u-status', 'reason': 'Case picked up for active work',
             'notes': 'Moving to active work'},
            headers=auth_headers,
        )
        self.assertEqual(status, 200)
        self.assertEqual(updated['status'], 'in_progress')
        self.assertEqual(updated['notes'], 'Moving to active work')

        status, final = http_json(
            'PATCH',
            f"{self.urls['tenant']}/api/v2/cases/{case_id}/status",
            {'status': 'closed', 'actor': 'u-status', 'reason': 'Work complete'},
            headers=auth_headers,
        )
        self.assertEqual(status, 200)
        self.assertEqual(final['status'], 'closed')

    def test_case_status_update_cross_tenant_is_blocked(self):
        owner_token = self._create_session(subject="u-owner-s", tenant_id="tenant-s", scopes=["tenant:write"])
        other_token = self._create_session(subject="u-other-s", tenant_id="tenant-other-s", scopes=["tenant:write", "tenant:read"])

        status, created = http_json(
            'POST',
            f"{self.urls['tenant']}/api/v2/cases",
            {'tenant_id': 'tenant-s', 'title': 'Cross-tenant status test'},
            headers={'Authorization': 'Bearer ' + owner_token},
        )
        self.assertEqual(status, 201)

        status, body = http_json(
            'PATCH',
            f"{self.urls['tenant']}/api/v2/cases/{created['id']}/status",
            {'status': 'closed', 'actor': 'u-other-s', 'reason': 'Cross-tenant attempt (must be blocked)'},
            headers={'Authorization': 'Bearer ' + other_token},
        )
        self.assertEqual(status, 403)
        self.assertEqual(body['detail']['error']['code'], 'forbidden')

    def test_cross_tenant_access_is_blocked(self):
        tenant_a_token = self._create_session(subject="u-a", tenant_id="tenant-a", scopes=["tenant:write", "tenant:read"])
        tenant_b_token = self._create_session(subject="u-b", tenant_id="tenant-b", scopes=["tenant:read"])

        status, created = http_json(
            'POST',
            f"{self.urls['tenant']}/api/v2/cases",
            {'tenant_id': 'tenant-a', 'title': 'Tenant A case'},
            headers={'Authorization': 'Bearer ' + tenant_a_token},
        )
        self.assertEqual(status, 201)

        status, body = http_json(
            'GET',
            f"{self.urls['tenant']}/api/v2/cases/{created['id']}",
            headers={'Authorization': 'Bearer ' + tenant_b_token},
        )
        self.assertEqual(status, 403)
        self.assertEqual(body['detail']['error']['code'], 'forbidden')

    def test_missing_tenant_claim_is_rejected(self):
        status, body = http_json(
            'POST',
            f"{self.urls['auth']}/api/v2/auth/session",
            {
                'provider': 'passkey',
                'subject': 'u-no-tenant',
                'role': 'Resident',
                'scopes': ['tenant:read'],
            },
            headers={'X-Service-Token': self.service_token},
        )
        self.assertEqual(status, 400)
        self.assertEqual(body['detail']['error']['code'], 'missing_tenant_claim')

    def test_client_tenant_override_is_rejected(self):
        token = self._create_session(subject="u-override", tenant_id="tenant-a", scopes=["tenant:write"])
        status, body = http_json(
            'POST',
            f"{self.urls['tenant']}/api/v2/cases",
            {'tenant_id': 'tenant-b', 'title': 'Bad override'},
            headers={'Authorization': 'Bearer ' + token},
        )
        self.assertEqual(status, 403)
        self.assertEqual(body['detail']['error']['code'], 'tenant_mismatch')

    def test_owner_access_succeeds(self):
        token = self._create_session(subject="owner-1", tenant_id="", role="Owner")
        status, body = http_json(
            'GET',
            f"{self.urls['tenant']}/api/v2/cases",
            headers={'Authorization': 'Bearer ' + token},
        )
        self.assertEqual(status, 200)
        self.assertIn("cases", body)

    def test_resident_cannot_request_owner_scope(self):
        status, body = http_json(
            'POST',
            f"{self.urls['auth']}/api/v2/auth/session",
            {
                'provider': 'passkey',
                'subject': 'resident-bad-scope',
                'tenant_id': 'tenant-r',
                'role': 'Resident',
                'scopes': ['ops:owner'],
            },
            headers={'X-Service-Token': self.service_token},
        )
        self.assertEqual(status, 400)
        self.assertEqual(body['detail']['error']['code'], 'invalid_scope')

    def test_service_tokens_must_declare_scopes(self):
        status, body = http_json(
            'POST',
            f"{self.urls['auth']}/api/v2/auth/session",
            {
                'provider': 'magic_link',
                'subject': 'svc:router',
                'role': 'Service',
                'tenant_id': 'tenant-s',
                'scopes': [],
            },
            headers={'X-Service-Token': self.service_token},
        )
        self.assertEqual(status, 400)
        self.assertEqual(body['detail']['error']['code'], 'invalid_scope')

    def test_malformed_and_wrong_audience_tokens_fail(self):
        wrong_audience_token = None
        status, body = http_json(
            'POST',
            f"{self.urls['auth']}/api/v2/auth/session",
            {
                'provider': 'passkey',
                'subject': 'u-bad-aud',
                'tenant_id': 'tenant-c',
                'role': 'Municipality',
                'scopes': ['tenant:read'],
                'audience': 'wrong-audience',
            },
            headers={'X-Service-Token': self.service_token},
        )
        self.assertEqual(status, 200)
        wrong_audience_token = body['access_token']
        for bad_token in (wrong_audience_token, wrong_audience_token + ".broken"):
            status, body = http_json(
                'GET',
                f"{self.urls['tenant']}/api/v2/cases",
                headers={'Authorization': 'Bearer ' + bad_token},
            )
            self.assertEqual(status, 401)
            self.assertEqual(body['detail']['error']['code'], 'unauthorized')

    def test_dependency_readiness_failure(self):
        base = Path(self.tempdir.name)
        self._start_service(
            'tenant_fail',
            'services/tenant',
            self.ports['tenant_fail'],
            {
                'TENANT_DB_PATH': str(base / 'tenant-fail.db'),
                'AUTH_READY_URL': 'http://127.0.0.1:9/api/v2/ready',
                'AUTH_INTROSPECTION_URL': f"{self.urls['auth']}/api/v2/auth/introspect",
            },
        )
        wait_for_service(f"{self.urls['tenant_fail']}/api/v2/live")

        status, body = http_json('GET', f"{self.urls['tenant_fail']}/api/v2/ready")
        self.assertEqual(status, 503)
        self.assertEqual(body['status'], 'not-ready')
        self.assertFalse(body['dependencies']['auth'])


if __name__ == '__main__':
    unittest.main()
