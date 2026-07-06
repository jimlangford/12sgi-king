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

ROOT = Path('/home/runner/work/12sgi-king/12sgi-king')
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
                'AUTH_INTROSPECTION_URL': f"{cls.urls['auth']}/api/v2/auth/introspect",
                'AUTH_READY_URL': f"{cls.urls['auth']}/api/v2/ready",
                'TENANT_SERVICE_URL': cls.urls['tenant'],
                'TENANT_READY_URL': f"{cls.urls['tenant']}/api/v2/ready",
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

    def _create_session(self):
        status, body = http_json(
            'POST',
            f"{self.urls['auth']}/api/v2/auth/session",
            {
                'provider': 'passkey',
                'subject': 'integration-user-1',
                'email': 'integration@example.com',
            },
        )
        self.assertEqual(status, 200)
        return body['access_token']

    def test_end_to_end_stack_flow(self):
        token = self._create_session()
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

    def test_auth_and_failure_paths(self):
        status, body = http_json(
            'POST',
            f"{self.urls['tenant']}/api/v2/cases",
            {'tenant_id': 'tenant-1', 'title': 'Missing auth'},
            headers={},
        )
        self.assertEqual(status, 401)
        self.assertEqual(body['detail']['error']['code'], 'unauthorized')

        token = self._create_session()
        auth_headers = {'Authorization': 'Bearer ' + token}

        status, body = http_json(
            'POST',
            f"{self.urls['documents']}/api/v2/documents/generate",
            {'template_id': 'notice-template', 'case_id': 'missing-case', 'output_format': 'pdf'},
            headers=auth_headers,
        )
        self.assertEqual(status, 404)
        self.assertEqual(body['detail']['error']['code'], 'resource_not_found')

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
