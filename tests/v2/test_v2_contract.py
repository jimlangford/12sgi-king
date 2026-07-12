import json
import sys
import tempfile
import unittest
from pathlib import Path

# Repo root, derived from this file's location (tests/v2/<file>.py) instead of hardcoding the
# GitHub Actions runner's checkout path -- that made this suite impossible to run anywhere except
# CI. Works identically in CI and local dev.
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from services.v2_workboard import (
    _batch_resolve_log,
    approve_workboard_job,
    archive_workboard_job,
    emit_workboard_job,
    pending_approvals,
    read_workboard_log,
    reject_workboard_job,
    resolve_workboard_job,
    selfheal_engineering_jobs,
    workboard_pulse,
    workboard_hub_feed,
)
from watchers import pulse_geometry
import importlib.util


class TestV2ContractFiles(unittest.TestCase):
    def test_contract_contains_required_routes(self):
        text = (ROOT / 'docs/api/v2-api-contract.yaml').read_text()
        required = [
            '/api/v2/auth/session',
            '/api/v2/auth/introspect',
            '/api/v2/auth/renew',
            '/api/v2/auth/debug',
            '/api/v2/auth/github',
            '/api/v2/auth/github/callback',
            '/api/v2/auth/google',
            '/api/v2/auth/google/callback',
            '/api/v2/auth/diagnostics/claims',
            '/api/v2/cases',
            '/api/v2/documents/generate',
            '/api/v2/storage/objects',
            '/api/v2/ai/assist',
        ]
        for route in required:
            self.assertIn(route, text)

    def test_error_schema_exists(self):
        text = (ROOT / 'docs/api/v2-api-contract.yaml').read_text()
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
        self.assertEqual(entries[0]['schema'], 'workboard-job-v2')

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
        self.assertEqual(tombstone['schema'], 'workboard-job-v2')

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


# ── Lane-aware workboard tests ────────────────────────────────────────────────

class TestWorkboardLanes(unittest.TestCase):
    """V2 lane separation: engineering self-heals, creative/output need approval."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.log_path = Path(self._tmp.name) / 'lane-test.jsonl'

    def tearDown(self):
        self._tmp.cleanup()

    # --- lane field is written and preserved ---

    def test_emit_defaults_to_engineering_lane(self):
        job = emit_workboard_job(
            source='svc',
            action='case.created',
            event='CASE',
            log_path=self.log_path,
        )
        self.assertEqual(job['lane'], 'engineering')

    def test_emit_creative_lane(self):
        job = emit_workboard_job(
            source='svc',
            action='document.generated',
            event='DOC',
            lane='creative',
            log_path=self.log_path,
        )
        self.assertEqual(job['lane'], 'creative')

    def test_emit_output_lane(self):
        job = emit_workboard_job(
            source='svc',
            action='publish.staged',
            event='PUBLISH',
            lane='output',
            log_path=self.log_path,
        )
        self.assertEqual(job['lane'], 'output')

    def test_emit_unknown_lane_coerced_to_engineering(self):
        job = emit_workboard_job(
            source='svc',
            action='x.action',
            event='X',
            lane='unknown-lane',
            log_path=self.log_path,
        )
        self.assertEqual(job['lane'], 'engineering')

    # --- selfheal only touches engineering ---

    def test_selfheal_heals_engineering_jobs(self):
        emit_workboard_job(
            source='svc', action='auth.event', event='AUTH',
            lane='engineering', log_path=self.log_path,
        )
        healed = selfheal_engineering_jobs(log_path=self.log_path, outcome='self-healed')
        self.assertEqual(healed, 1)

    def test_selfheal_does_not_touch_creative_jobs(self):
        emit_workboard_job(
            source='svc', action='document.generated', event='DOC',
            lane='creative', log_path=self.log_path,
        )
        healed = selfheal_engineering_jobs(log_path=self.log_path, outcome='self-healed')
        self.assertEqual(healed, 0)

    def test_selfheal_does_not_touch_output_jobs(self):
        emit_workboard_job(
            source='svc', action='publish.staged', event='PUBLISH',
            lane='output', log_path=self.log_path,
        )
        healed = selfheal_engineering_jobs(log_path=self.log_path, outcome='self-healed')
        self.assertEqual(healed, 0)

    def test_selfheal_mixed_log_only_heals_engineering(self):
        emit_workboard_job(
            source='svc', action='case.created', event='CASE',
            lane='engineering', log_path=self.log_path,
        )
        emit_workboard_job(
            source='svc', action='document.generated', event='DOC',
            lane='creative', log_path=self.log_path,
        )
        healed = selfheal_engineering_jobs(log_path=self.log_path, outcome='self-healed')
        self.assertEqual(healed, 1)

        # creative job still open
        pending = pending_approvals(log_path=self.log_path)
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0]['lane'], 'creative')

    # --- _batch_resolve_log is lane-aware (backward compat wrapper) ---

    def test_batch_resolve_only_heals_engineering(self):
        emit_workboard_job(
            source='svc', action='eng.action', event='ENG',
            lane='engineering', log_path=self.log_path,
        )
        emit_workboard_job(
            source='svc', action='doc.action', event='DOC',
            lane='creative', log_path=self.log_path,
        )
        closed = _batch_resolve_log(log_path=self.log_path, outcome='batch')
        self.assertEqual(closed, 1)

    # --- approve / reject ---

    def test_approve_creative_job(self):
        job = emit_workboard_job(
            source='svc', action='document.generated', event='DOC',
            lane='creative', log_path=self.log_path,
        )
        job_id = job['job']['id']

        tombstone = approve_workboard_job(job_id, 'owner', note='Looks good', log_path=self.log_path)

        self.assertEqual(tombstone['kind'], 'tombstone')
        self.assertEqual(tombstone['status'], 'approved')
        self.assertEqual(tombstone['job']['action'], 'approved')
        self.assertEqual(tombstone['job']['correlation_id'], job_id)
        self.assertEqual(tombstone['job']['payload']['approver'], 'owner')
        self.assertEqual(tombstone['job']['payload']['note'], 'Looks good')

    def test_approve_removes_from_pending(self):
        job = emit_workboard_job(
            source='svc', action='document.generated', event='DOC',
            lane='creative', log_path=self.log_path,
        )
        job_id = job['job']['id']
        self.assertEqual(len(pending_approvals(log_path=self.log_path)), 1)

        approve_workboard_job(job_id, 'owner', log_path=self.log_path)
        self.assertEqual(len(pending_approvals(log_path=self.log_path)), 0)

    def test_reject_creative_job(self):
        job = emit_workboard_job(
            source='svc', action='document.generated', event='DOC',
            lane='creative', log_path=self.log_path,
        )
        job_id = job['job']['id']

        tombstone = reject_workboard_job(job_id, 'Wrong template used', rejector='owner', log_path=self.log_path)

        self.assertEqual(tombstone['kind'], 'tombstone')
        self.assertEqual(tombstone['status'], 'rejected')
        self.assertEqual(tombstone['job']['payload']['reason'], 'Wrong template used')
        self.assertEqual(tombstone['job']['correlation_id'], job_id)

    def test_reject_removes_from_pending(self):
        job = emit_workboard_job(
            source='svc', action='publish.staged', event='PUBLISH',
            lane='output', log_path=self.log_path,
        )
        job_id = job['job']['id']
        self.assertEqual(len(pending_approvals(log_path=self.log_path)), 1)

        reject_workboard_job(job_id, 'Not ready', log_path=self.log_path)
        self.assertEqual(len(pending_approvals(log_path=self.log_path)), 0)

    # --- archive (soft-delete, any lane) ---

    def test_archive_job(self):
        job = emit_workboard_job(
            source='svc', action='case.created', event='CASE',
            lane='engineering', log_path=self.log_path,
        )
        job_id = job['job']['id']

        tombstone = archive_workboard_job(job_id, 'owner', note='superseded by v2', log_path=self.log_path)

        self.assertEqual(tombstone['kind'], 'tombstone')
        self.assertEqual(tombstone['status'], 'archived')
        self.assertEqual(tombstone['job']['action'], 'archived')
        self.assertEqual(tombstone['job']['correlation_id'], job_id)
        self.assertEqual(tombstone['job']['payload']['archiver'], 'owner')
        self.assertEqual(tombstone['job']['payload']['note'], 'superseded by v2')

    def test_archive_does_not_modify_original_entry(self):
        job = emit_workboard_job(
            source='svc', action='case.created', event='CASE',
            lane='engineering', log_path=self.log_path,
        )
        job_id = job['job']['id']
        archive_workboard_job(job_id, 'owner', log_path=self.log_path)

        entries = read_workboard_log(self.log_path)
        original = entries[0]
        self.assertEqual(original['status'], 'queued')
        self.assertEqual(original['kind'], 'job')
        # archiving appended a second entry; it never rewrote the first
        self.assertEqual(len(entries), 2)

    def test_archive_removes_creative_job_from_pending(self):
        job = emit_workboard_job(
            source='svc', action='document.generated', event='DOC',
            lane='creative', log_path=self.log_path,
        )
        job_id = job['job']['id']
        self.assertEqual(len(pending_approvals(log_path=self.log_path)), 1)

        archive_workboard_job(job_id, 'owner', log_path=self.log_path)
        self.assertEqual(len(pending_approvals(log_path=self.log_path)), 0)

    def test_archive_excludes_engineering_job_from_selfheal(self):
        job = emit_workboard_job(
            source='svc', action='case.created', event='CASE',
            lane='engineering', log_path=self.log_path,
        )
        job_id = job['job']['id']
        archive_workboard_job(job_id, 'owner', log_path=self.log_path)

        healed = selfheal_engineering_jobs(log_path=self.log_path)
        self.assertEqual(healed, 0)

    # --- pending_approvals only returns creative/output ---

    def test_pending_approvals_excludes_engineering(self):
        emit_workboard_job(
            source='svc', action='case.created', event='CASE',
            lane='engineering', log_path=self.log_path,
        )
        self.assertEqual(pending_approvals(log_path=self.log_path), [])

    def test_pending_approvals_returns_creative_and_output(self):
        emit_workboard_job(
            source='svc', action='doc.gen', event='DOC',
            lane='creative', log_path=self.log_path,
        )
        emit_workboard_job(
            source='svc', action='publish.staged', event='PUBLISH',
            lane='output', log_path=self.log_path,
        )
        pending = pending_approvals(log_path=self.log_path)
        self.assertEqual(len(pending), 2)
        lanes = {e['lane'] for e in pending}
        self.assertEqual(lanes, {'creative', 'output'})

    def test_pending_approvals_empty_log(self):
        self.assertEqual(pending_approvals(log_path=self.log_path), [])

    # --- original entries are never modified ---

    def test_approve_does_not_modify_original_entry(self):
        job = emit_workboard_job(
            source='svc', action='doc.gen', event='DOC',
            lane='creative', log_path=self.log_path,
        )
        job_id = job['job']['id']
        approve_workboard_job(job_id, 'owner', log_path=self.log_path)

        entries = read_workboard_log(self.log_path)
        original = entries[0]
        self.assertEqual(original['lane'], 'creative')
        self.assertEqual(original['status'], 'queued')
        self.assertEqual(original['kind'], 'job')


class TestPulseGeometry(unittest.TestCase):
    def test_snapshot_meets_minimum_geometry(self):
        snap = pulse_geometry.snapshot(sample_cells=4)
        self.assertEqual(snap['counts']['contexts'], 3)
        self.assertEqual(snap['counts']['quadrants'], 4)
        self.assertGreaterEqual(snap['counts']['lanes'], pulse_geometry.FULL_LANE_COUNT)
        self.assertGreaterEqual(snap['counts']['skills'], pulse_geometry.MIN_SKILLS)
        self.assertGreaterEqual(snap['counts']['cells'], pulse_geometry.MIN_LANES * pulse_geometry.MIN_SKILLS)
        self.assertTrue(snap['geometry_complete'])
        self.assertEqual(snap['full_hina_cycle']['lanes'], pulse_geometry.FULL_LANE_COUNT)
        self.assertEqual(snap['counts']['forecasts'], 6)
        self.assertGreaterEqual(snap['counts']['elements'], 1)
        self.assertEqual(
            snap['counts']['forecast_elements'],
            snap['counts']['forecasts'] * snap['counts']['elements'],
        )
        self.assertEqual(snap['place_tuning']['model'], 'human_residence_frequencies')
        self.assertEqual(snap['place_tuning']['timezone'], pulse_geometry.RESIDENCE_TIMEZONE)
        self.assertEqual(snap['place_tuning']['audit_status'], 'audited')
        self.assertEqual(snap['place_tuning']['serves'], 'humans')
        self.assertFalse(snap['place_tuning']['experiments_enabled'])
        self.assertEqual(snap['place_tuning']['human_alignment_system'], 'chakra')
        self.assertEqual(snap['place_tuning']['organic_carbon_weight'], 6)
        self.assertEqual(snap['place_tuning']['chakra_count'], 6)
        self.assertEqual(len(snap['residence_frequencies']), 4)

    def test_cells_carry_pulse_engine_fields(self):
        snap = pulse_geometry.snapshot(sample_cells=1)
        cell = snap['cells_sample'][0]
        for field in (
            'trigger', 'direction', 'cadence', 'balance', 'output', 'state', 'resonance',
            'residence_frequency', 'residence_secondary_frequency', 'residence_alignment',
            'chakra_index', 'chakra_tone', 'organic_carbon_weight', 'element',
            'quadrant', 'quadrant_id', 'outer_boundary_context_id', 'governing_context_id', 'rhythm_context_id',
        ):
            self.assertIn(field, cell)

    def test_graph_payload_is_cartesian(self):
        payload = pulse_geometry.build_graph_payload()
        self.assertEqual(payload['counts']['contexts'], 3)
        self.assertEqual(payload['counts']['quadrants'], 4)
        self.assertEqual(
            payload['counts']['cells'],
            payload['counts']['lanes'] * payload['counts']['skills'],
        )
        self.assertEqual(payload['counts']['forecasts'], 6)
        self.assertGreaterEqual(payload['counts']['elements'], 1)
        self.assertEqual(payload['counts']['context_edges'], 14)
        self.assertEqual(
            payload['counts']['forecast_elements'],
            payload['counts']['forecasts'] * payload['counts']['elements'],
        )
        self.assertEqual(payload['counts']['residence_frequencies'], 4)

    def test_forecasts_cover_month_quarter_year(self):
        snap = pulse_geometry.snapshot(sample_cells=1)
        windows = {row['window'] for row in snap['forecasts']}
        self.assertEqual(windows, {'monthly', 'quarterly', 'yearly'})
        labels = {row['label'] for row in snap['forecasts']}
        self.assertIn('28-30 day Hina moon cycle', labels)
        self.assertIn('13-moon annual accounting cycle', labels)
        self.assertTrue(all('residence_frequency_counts' in row for row in snap['forecasts']))
        self.assertTrue(all('chakra_counts' in row for row in snap['forecasts']))
        self.assertTrue(all('element_counts' in row for row in snap['forecasts']))
        self.assertTrue(all(set(row['element_counts']) == set(pulse_geometry._DEFAULT_ELEMENTS) for row in snap['forecasts']))

    def test_quadrants_carry_context_model_directly(self):
        snap = pulse_geometry.snapshot(sample_cells=1)
        quadrants = {row['quadrant']: row for row in snap['quadrants']}
        self.assertEqual(set(quadrants), {'Mauka', 'Kula', 'Makai', 'Universal'})
        for row in quadrants.values():
            self.assertEqual(row['outer_boundary_context_id'], pulse_geometry.EDGE_CONTEXT_ID)
            self.assertEqual(row['governing_context_id'], pulse_geometry.APEX_CONTEXT_ID)
            self.assertEqual(row['rhythm_context_id'], pulse_geometry.RHYTHM_CONTEXT_ID)
            self.assertEqual(row['local_boundary_scale'], pulse_geometry.LOCAL_BOUNDARY_SCALE)
            self.assertEqual(row['tenant_overlap_surface'], pulse_geometry.TENANT_OVERLAP_SURFACE)
        edge_context = next(row for row in snap['contexts'] if row['id'] == pulse_geometry.EDGE_CONTEXT_ID)
        self.assertEqual(edge_context['local_boundary_scale'], pulse_geometry.LOCAL_BOUNDARY_SCALE)
        self.assertEqual(edge_context['tenant_overlap_surface'], pulse_geometry.TENANT_OVERLAP_SURFACE)
        edges = {(row['rel'], row['src_id'], row['dst_id']) for row in snap['context_edges']}
        self.assertIn(('CONTAINS', pulse_geometry.EDGE_CONTEXT_ID, 'quadrant:mauka'), edges)
        self.assertIn(('GOVERNS', pulse_geometry.APEX_CONTEXT_ID, 'quadrant:kula'), edges)
        self.assertIn(('FRAMES', pulse_geometry.RHYTHM_CONTEXT_ID, 'quadrant:makai'), edges)


class TestPulseGeometryApiSurface(unittest.TestCase):
    def test_v2_main_declares_pulse_routes(self):
        text = (ROOT / 'v2' / 'app' / 'main.py').read_text(encoding='utf-8')
        self.assertIn('/pulse/geometry', text)
        self.assertIn('/pulse/geometry/refresh', text)
        self.assertIn('/graph/status', text)
        self.assertIn('/graph/refresh', text)

    def test_snapshot_handler_returns_geometry_summary(self):
        if importlib.util.find_spec('fastapi') is None:
            raise unittest.SkipTest('fastapi is not installed in this environment')
        import v2.app.main as v2_main
        body = v2_main.pulse_geometry_snapshot()
        self.assertEqual(body['layer'], pulse_geometry.LAYER)
        self.assertTrue(body['geometry_complete'])
        self.assertEqual(body['full_hina_cycle']['lanes'], pulse_geometry.FULL_LANE_COUNT)
        self.assertEqual(len(body['forecast_sample']), 6)
        self.assertEqual(len(body['context_sample']), 3)
        self.assertEqual(len(body['quadrant_sample']), 4)
        self.assertLessEqual(len(body['lane_sample']), 6)
        self.assertLessEqual(len(body['skill_sample']), 6)
        self.assertLessEqual(len(body['element_sample']), 6)
        self.assertEqual(body['place_tuning']['timezone'], pulse_geometry.RESIDENCE_TIMEZONE)
        self.assertFalse(body['place_tuning']['experiments_enabled'])
        self.assertEqual(body['place_tuning']['organic_carbon_weight'], 6)
        self.assertEqual(len(body['residence_frequency_sample']), 4)

    def test_refresh_handler_returns_layer(self):
        if importlib.util.find_spec('fastapi') is None:
            raise unittest.SkipTest('fastapi is not installed in this environment')
        import v2.app.main as v2_main
        original = v2_main.pulse_geometry.refresh
        v2_main.pulse_geometry.refresh = lambda: True
        try:
            body = v2_main.refresh_pulse_geometry()
        finally:
            v2_main.pulse_geometry.refresh = original
        self.assertEqual(body['layer'], pulse_geometry.LAYER)
        self.assertTrue(body['refreshed'])

    def test_graph_status_handler_returns_stack_summary(self):
        if importlib.util.find_spec('fastapi') is None:
            raise unittest.SkipTest('fastapi is not installed in this environment')
        import v2.app.main as v2_main
        original = v2_main.graph_refresh.status
        v2_main.graph_refresh.status = lambda: {'boundary': 'PRIVATE', 'graph_stack_version': '5.2'}
        try:
            body = v2_main.graph_status()
        finally:
            v2_main.graph_refresh.status = original
        self.assertEqual(body['boundary'], 'PRIVATE')
        self.assertEqual(body['graph_stack_version'], '5.2')

    def test_owner_shell_declares_graph_panel(self):
        shell = (ROOT / 'king_public_src' / 'index.html').read_text(encoding='utf-8')
        panel = (ROOT / 'king_public_src' / 'Graph.dc.html').read_text(encoding='utf-8')
        self.assertIn("id:'graph'", shell)
        self.assertIn("'graph'", shell)
        self.assertIn('showGraph', shell)
        self.assertIn('<dc-import name="Graph"', shell)
        self.assertIn('/graph/status', panel)
        self.assertIn('/graph/refresh', panel)

    def test_graph_refresh_handler_returns_status_payload(self):
        if importlib.util.find_spec('fastapi') is None:
            raise unittest.SkipTest('fastapi is not installed in this environment')
        import v2.app.main as v2_main
        original_refresh = v2_main.graph_refresh.refresh
        original_status = v2_main.graph_refresh.status
        calls = []
        v2_main.graph_refresh.refresh = lambda mode, reason, targets: calls.append((mode, reason, targets)) or True
        v2_main.graph_refresh.status = lambda: {'status': 'idle', 'requested_targets': ['pulse_geometry']}
        try:
            body = v2_main.refresh_graph(
                v2_main.GraphRefreshRequest(
                    mode='incremental',
                    reason='unit-test',
                    targets=['pulse_geometry'],
                )
            )
        finally:
            v2_main.graph_refresh.refresh = original_refresh
            v2_main.graph_refresh.status = original_status
        self.assertEqual(calls, [('incremental', 'unit-test', ['pulse_geometry'])])
        self.assertTrue(body['refreshed'])
        self.assertEqual(body['status']['requested_targets'], ['pulse_geometry'])


class TestDagNodes(unittest.TestCase):
    """Tests for the dag_nodes field on emit_workboard_job."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.log_path = Path(self._tmp.name) / 'test-dag.jsonl'

    def tearDown(self):
        self._tmp.cleanup()

    def test_dag_nodes_stored_on_job(self):
        nodes = [
            {'name': 'Scene Build', 'status': 'waiting', 'engine': 'none', 'inputs_resolved': False},
            {'name': 'GPU Render',  'status': 'running', 'engine': 'comfyui', 'inputs_resolved': True},
        ]
        entry = emit_workboard_job(
            source='test', action='render', event='RENDER',
            dag_nodes=nodes, log_path=self.log_path,
        )
        stored = entry['job']['dag_nodes']
        self.assertEqual(len(stored), 2)
        self.assertEqual(stored[0]['name'], 'Scene Build')
        self.assertEqual(stored[1]['engine'], 'comfyui')
        self.assertEqual(stored[1]['inputs_resolved'], True)

    def test_dag_nodes_persisted_in_log(self):
        nodes = [{'name': 'Audio Sync', 'status': 'done', 'engine': 'voice', 'inputs_resolved': True}]
        emit_workboard_job(
            source='test', action='audio', event='AUDIO',
            dag_nodes=nodes, log_path=self.log_path,
        )
        entries = read_workboard_log(self.log_path)
        stored = entries[0]['job']['dag_nodes']
        self.assertEqual(stored[0]['engine'], 'voice')
        self.assertEqual(stored[0]['status'], 'done')

    def test_invalid_dag_node_status_coerced(self):
        nodes = [{'name': 'X', 'status': 'BOGUS', 'engine': 'none', 'inputs_resolved': False}]
        entry = emit_workboard_job(
            source='test', action='x', event='X',
            dag_nodes=nodes, log_path=self.log_path,
        )
        self.assertEqual(entry['job']['dag_nodes'][0]['status'], 'waiting')

    def test_invalid_dag_node_engine_coerced(self):
        nodes = [{'name': 'X', 'status': 'waiting', 'engine': 'BOGUS', 'inputs_resolved': False}]
        entry = emit_workboard_job(
            source='test', action='x', event='X',
            dag_nodes=nodes, log_path=self.log_path,
        )
        self.assertEqual(entry['job']['dag_nodes'][0]['engine'], 'none')

    def test_no_dag_nodes_gives_empty_list(self):
        entry = emit_workboard_job(
            source='test', action='x', event='X',
            log_path=self.log_path,
        )
        self.assertEqual(entry['job']['dag_nodes'], [])

    def test_none_dag_nodes_gives_empty_list(self):
        entry = emit_workboard_job(
            source='test', action='x', event='X',
            dag_nodes=None, log_path=self.log_path,
        )
        self.assertEqual(entry['job']['dag_nodes'], [])

    def test_non_dict_items_skipped(self):
        nodes = ['not-a-dict', None, {'name': 'Valid', 'status': 'waiting', 'engine': 'none', 'inputs_resolved': False}]
        entry = emit_workboard_job(
            source='test', action='x', event='X',
            dag_nodes=nodes, log_path=self.log_path,
        )
        self.assertEqual(len(entry['job']['dag_nodes']), 1)
        self.assertEqual(entry['job']['dag_nodes'][0]['name'], 'Valid')

    def test_extra_node_keys_preserved(self):
        nodes = [{'name': 'A', 'status': 'waiting', 'engine': 'ollama', 'inputs_resolved': False, 'retry_count': 3}]
        entry = emit_workboard_job(
            source='test', action='x', event='X',
            dag_nodes=nodes, log_path=self.log_path,
        )
        self.assertEqual(entry['job']['dag_nodes'][0]['retry_count'], 3)


class TestWorkboardPulse(unittest.TestCase):
    """Tests for the workboard_pulse() operational counter function."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.log_path = Path(self._tmp.name) / 'test-pulse.jsonl'

    def tearDown(self):
        self._tmp.cleanup()

    def _write_raw(self, obj):
        import json as _json, time as _time
        obj.setdefault('ts', int(_time.time()))
        obj.setdefault('iso', _time.strftime('%Y-%m-%d %H:%M:%S', _time.gmtime()))
        with self.log_path.open('a', encoding='utf-8') as f:
            f.write(_json.dumps(obj) + '\n')

    def test_empty_log_all_zeros(self):
        p = workboard_pulse(log_path=self.log_path)
        self.assertEqual(p['jobs_running'], 0)
        self.assertEqual(p['waiting_gpu'], 0)
        self.assertEqual(p['waiting_owner'], 0)
        self.assertEqual(p['auto_healed_today'], 0)
        self.assertEqual(p['deploy_ready'], 0)
        self.assertEqual(p['critical'], 0)

    def test_missing_log_all_zeros(self):
        missing = Path(self._tmp.name) / 'no-such.jsonl'
        p = workboard_pulse(log_path=missing)
        self.assertEqual(p['jobs_running'], 0)

    def test_in_progress_job_counted(self):
        emit_workboard_job(
            source='s', action='a', event='E',
            status='in-progress', lane='engineering',
            log_path=self.log_path,
        )
        p = workboard_pulse(log_path=self.log_path)
        self.assertEqual(p['jobs_running'], 1)

    def test_queued_job_not_in_running(self):
        emit_workboard_job(
            source='s', action='a', event='E',
            status='queued', lane='engineering',
            log_path=self.log_path,
        )
        p = workboard_pulse(log_path=self.log_path)
        self.assertEqual(p['jobs_running'], 0)

    def test_resolved_job_not_counted(self):
        job = emit_workboard_job(
            source='s', action='a', event='E',
            status='in-progress', log_path=self.log_path,
        )
        resolve_workboard_job(job['job']['id'], 'done', log_path=self.log_path)
        p = workboard_pulse(log_path=self.log_path)
        self.assertEqual(p['jobs_running'], 0)

    def test_gpu_engine_node_counted(self):
        emit_workboard_job(
            source='s', action='render', event='E',
            status='in-progress', lane='engineering',
            dag_nodes=[{'name': 'GPU', 'status': 'running', 'engine': 'comfyui', 'inputs_resolved': True}],
            log_path=self.log_path,
        )
        p = workboard_pulse(log_path=self.log_path)
        self.assertEqual(p['waiting_gpu'], 1)

    def test_non_gpu_engine_not_counted(self):
        emit_workboard_job(
            source='s', action='render', event='E',
            status='in-progress', lane='engineering',
            dag_nodes=[{'name': 'LLM', 'status': 'running', 'engine': 'ollama', 'inputs_resolved': True}],
            log_path=self.log_path,
        )
        p = workboard_pulse(log_path=self.log_path)
        self.assertEqual(p['waiting_gpu'], 0)

    def test_pending_approval_counted(self):
        emit_workboard_job(
            source='s', action='doc', event='DOC',
            status='pending-approval', lane='creative',
            log_path=self.log_path,
        )
        p = workboard_pulse(log_path=self.log_path)
        self.assertEqual(p['waiting_owner'], 1)

    def test_blocker_watcher_entry_counted_as_critical(self):
        self._write_raw({'source': 'watcher', 'event': 'BLOCKER: server disk 90%'})
        p = workboard_pulse(log_path=self.log_path)
        self.assertEqual(p['critical'], 1)

    def test_no_blocker_critical_zero(self):
        self._write_raw({'source': 'watcher', 'event': 'FINDING: server fine'})
        p = workboard_pulse(log_path=self.log_path)
        self.assertEqual(p['critical'], 0)

    def test_pulse_keys_present(self):
        p = workboard_pulse(log_path=self.log_path)
        for key in ('jobs_running', 'waiting_gpu', 'waiting_owner', 'auto_healed_today', 'deploy_ready', 'critical'):
            self.assertIn(key, p)


class TestWorkboardHubFeed(unittest.TestCase):
    """Tests for workboard_hub_feed()."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.log_path = Path(self._tmp.name) / 'test-hub.jsonl'

    def tearDown(self):
        self._tmp.cleanup()

    def _write_raw(self, obj):
        import json as _json, time as _time
        obj.setdefault('ts', int(_time.time()))
        obj.setdefault('iso', _time.strftime('%Y-%m-%d %H:%M:%S', _time.gmtime()))
        with self.log_path.open('a', encoding='utf-8') as f:
            f.write(_json.dumps(obj) + '\n')

    def test_empty_log_returns_empty_list(self):
        self.assertEqual(workboard_hub_feed(log_path=self.log_path), [])

    def test_missing_log_returns_empty_list(self):
        missing = Path(self._tmp.name) / 'nope.jsonl'
        self.assertEqual(workboard_hub_feed(log_path=missing), [])

    def test_workboard_job_appears_in_feed(self):
        emit_workboard_job(
            source='svc', action='a', event='FINDING: disk low',
            log_path=self.log_path,
        )
        feed = workboard_hub_feed(log_path=self.log_path)
        self.assertEqual(len(feed), 1)
        self.assertEqual(feed[0]['prefix'], 'FINDING')
        self.assertEqual(feed[0]['source'], 'svc')

    def test_watcher_entry_prefix_extracted(self):
        self._write_raw({'source': 'watcher', 'event': 'BLOCKER: disk full'})
        feed = workboard_hub_feed(log_path=self.log_path)
        self.assertEqual(feed[0]['prefix'], 'BLOCKER')

    def test_unknown_prefix_becomes_info(self):
        self._write_raw({'source': 'misc', 'event': 'Something happened'})
        feed = workboard_hub_feed(log_path=self.log_path)
        self.assertEqual(feed[0]['prefix'], 'INFO')

    def test_feed_sorted_newest_first(self):
        import time as _time
        self._write_raw({'source': 'a', 'event': 'FINDING: old', 'ts': 1000})
        self._write_raw({'source': 'b', 'event': 'SHIPPED: new', 'ts': 2000})
        feed = workboard_hub_feed(log_path=self.log_path)
        self.assertEqual(feed[0]['source'], 'b')
        self.assertEqual(feed[1]['source'], 'a')

    def test_limit_respected(self):
        for i in range(10):
            self._write_raw({'source': f's{i}', 'event': f'FINDING: item {i}', 'ts': i})
        feed = workboard_hub_feed(limit=3, log_path=self.log_path)
        self.assertEqual(len(feed), 3)

    def test_feed_entry_has_required_keys(self):
        emit_workboard_job(
            source='svc', action='a', event='SHIPPED: done',
            log_path=self.log_path,
        )
        entry = workboard_hub_feed(log_path=self.log_path)[0]
        for key in ('ts', 'iso', 'source', 'prefix', 'event', 'lane', 'kind'):
            self.assertIn(key, entry)


if __name__ == '__main__':
    unittest.main()
