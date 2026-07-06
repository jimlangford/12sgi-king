import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path('/home/runner/work/12sgi-king/12sgi-king')
sys.path.insert(0, str(ROOT))

from services.v2_workboard import (
    _batch_resolve_log,
    emit_workboard_job,
    read_workboard_log,
    resolve_workboard_job,
)


class TestV2ContractFiles(unittest.TestCase):
    def test_openapi_contains_required_routes(self):
        text = (ROOT / 'docs/api/v2-openapi.yaml').read_text()
        required = [
            '/api/v2/auth/session',
            '/api/v2/cases',
            '/api/v2/documents/generate',
            '/api/v2/storage/objects',
            '/api/v2/ai/assist',
        ]
        for route in required:
            self.assertIn(route, text)

    def test_error_schema_exists(self):
        text = (ROOT / 'docs/api/v2-openapi.yaml').read_text()
        self.assertIn('ErrorResponse', text)
        self.assertIn('code', text)
        self.assertIn('message', text)

    def test_health_service_uses_v2_readiness_path(self):
        text = (ROOT / 'services/health/app/checks.py').read_text()
        self.assertIn("SURFACES_HEALTH_PATH", text)
        self.assertIn("/api/v2/ready", text)


class TestWorkboardResolve(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.log_path = Path(self._tmp.name) / 'test-dispatch.jsonl'

    def tearDown(self):
        self._tmp.cleanup()

    # --- emit / read round-trip ---

    def test_read_empty_log_returns_list(self):
        self.assertEqual(read_workboard_log(self.log_path), [])

    def test_read_missing_log_returns_list(self):
        missing = Path(self._tmp.name) / 'nonexistent.jsonl'
        self.assertEqual(read_workboard_log(missing), [])

    def test_emit_then_read(self):
        emit_workboard_job(
            source='test-src',
            action='test.action',
            event='TEST EVENT',
            log_path=self.log_path,
        )
        entries = read_workboard_log(self.log_path)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]['source'], 'test-src')
        self.assertEqual(entries[0]['status'], 'queued')
        self.assertEqual(entries[0]['schema'], 'workboard-job-v1')

    # --- resolve_workboard_job ---

    def test_resolve_appends_tombstone(self):
        job = emit_workboard_job(
            source='test-src',
            action='case.created',
            event='CASE CREATED',
            log_path=self.log_path,
        )
        job_id = job['job']['id']

        tombstone = resolve_workboard_job(job_id, 'completed-ok', log_path=self.log_path)

        self.assertEqual(tombstone['kind'], 'tombstone')
        self.assertEqual(tombstone['status'], 'done')
        self.assertEqual(tombstone['job']['action'], 'resolved')
        self.assertEqual(tombstone['job']['correlation_id'], job_id)
        self.assertEqual(tombstone['job']['payload']['outcome'], 'completed-ok')
        self.assertEqual(tombstone['schema'], 'workboard-job-v1')

    def test_resolve_original_entry_unchanged(self):
        job = emit_workboard_job(
            source='test-src',
            action='case.created',
            event='CASE CREATED',
            log_path=self.log_path,
        )
        job_id = job['job']['id']
        resolve_workboard_job(job_id, 'done', log_path=self.log_path)

        entries = read_workboard_log(self.log_path)
        original = entries[0]
        self.assertEqual(original['status'], 'queued')  # original entry untouched
        tombstone = entries[1]
        self.assertEqual(tombstone['kind'], 'tombstone')

    def test_resolve_returns_written_entry(self):
        job = emit_workboard_job(
            source='test-src',
            action='doc.generated',
            event='DOC GEN',
            log_path=self.log_path,
        )
        result = resolve_workboard_job(job['job']['id'], 'ok', log_path=self.log_path)
        # Verify the returned dict is also in the log
        entries = read_workboard_log(self.log_path)
        written_ids = {e['job']['id'] for e in entries}
        self.assertIn(result['job']['id'], written_ids)

    # --- _batch_resolve_log ---

    def test_batch_resolve_closes_open_jobs(self):
        for i in range(3):
            emit_workboard_job(
                source='svc',
                action=f'action.{i}',
                event=f'EVENT {i}',
                log_path=self.log_path,
            )
        closed = _batch_resolve_log(log_path=self.log_path, outcome='batch-test')
        self.assertEqual(closed, 3)

        entries = read_workboard_log(self.log_path)
        tombstones = [e for e in entries if e.get('kind') == 'tombstone']
        self.assertEqual(len(tombstones), 3)

    def test_batch_resolve_skips_already_resolved(self):
        job = emit_workboard_job(
            source='svc',
            action='already.done',
            event='DONE',
            log_path=self.log_path,
        )
        resolve_workboard_job(job['job']['id'], 'pre-closed', log_path=self.log_path)

        # Second batch run should close 0 new jobs
        closed = _batch_resolve_log(log_path=self.log_path, outcome='re-run')
        self.assertEqual(closed, 0)

    def test_batch_resolve_idempotent_on_empty_log(self):
        closed = _batch_resolve_log(log_path=self.log_path, outcome='nothing')
        self.assertEqual(closed, 0)

    def test_batch_resolve_mixed_log(self):
        open_job = emit_workboard_job(
            source='svc',
            action='open.action',
            event='OPEN',
            log_path=self.log_path,
        )
        already_job = emit_workboard_job(
            source='svc',
            action='done.action',
            event='ALREADY DONE',
            log_path=self.log_path,
        )
        resolve_workboard_job(already_job['job']['id'], 'pre-done', log_path=self.log_path)

        closed = _batch_resolve_log(log_path=self.log_path, outcome='batch')
        self.assertEqual(closed, 1)

        entries = read_workboard_log(self.log_path)
        resolved_ids = {
            e['job']['correlation_id']
            for e in entries
            if e.get('kind') == 'tombstone'
        }
        self.assertIn(open_job['job']['id'], resolved_ids)


if __name__ == '__main__':
    unittest.main()
