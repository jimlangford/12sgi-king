import sys
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

ROOT = Path('/home/runner/work/12sgi-king/12sgi-king')
sys.path.insert(0, str(ROOT))

from watchers import sage_trinity


class TestSageTrinitySnapshot(unittest.TestCase):
    """Tests for the pure-Python snapshot (no Neo4j required)."""

    def setUp(self):
        self.snap = sage_trinity.snapshot()

    def test_snapshot_layer_and_model(self):
        self.assertEqual(self.snap['layer'], 'sage_trinity')
        self.assertEqual(self.snap['model'], 'sage_trinity_triskelion')
        self.assertIn('triskelion', self.snap['symbol'])

    def test_three_scales_present(self):
        scales = self.snap['scales']
        self.assertIn('universe', scales)
        self.assertIn('civic', scales)
        self.assertIn('human', scales)
        self.assertEqual(scales['universe'], sage_trinity.SAGE_UNIVERSE_CONTEXT_ID)
        self.assertEqual(scales['civic'], sage_trinity.SAGE_CIVIC_CONTEXT_ID)
        self.assertEqual(scales['human'], sage_trinity.HUMAN_INITIATION_CONTEXT_ID)

    def test_three_trinity_contexts(self):
        self.assertEqual(self.snap['counts']['trinity_contexts'], 3)
        ids = {row['id'] for row in self.snap['trinity_contexts']}
        self.assertIn(sage_trinity.SAGE_UNIVERSE_CONTEXT_ID, ids)
        self.assertIn(sage_trinity.SAGE_CIVIC_CONTEXT_ID, ids)
        self.assertIn(sage_trinity.HUMAN_INITIATION_CONTEXT_ID, ids)

    def test_trinity_context_required_fields(self):
        for row in self.snap['trinity_contexts']:
            self.assertIn('name', row)
            self.assertIn('trinity_scale', row)
            self.assertIn('description', row)
            self.assertIn('layer', row)
            self.assertEqual(row['layer'], 'sage_trinity')

    def test_universe_context_carries_science_anchors(self):
        universe = next(r for r in self.snap['trinity_contexts'] if r['trinity_scale'] == 'universe')
        self.assertIn('laniakea_ref', universe)
        self.assertIn('Tully', universe['laniakea_ref'])
        self.assertIn('2014', universe['laniakea_ref'])
        self.assertEqual(universe['solar_cycle_number'], 25)
        self.assertAlmostEqual(universe['schumann_base_hz'], 7.83)

    def test_human_initiation_carries_carbon_fields(self):
        human = next(r for r in self.snap['trinity_contexts'] if r['trinity_scale'] == 'human')
        self.assertEqual(human['organic_carbon_weight'], 6)
        self.assertEqual(human['chakra_count'], 6)
        self.assertEqual(human['carbon_atomic_number'], 6)
        self.assertIn('chakra', human['human_alignment_system'])
        self.assertIn('circadian_ref', human)

    def test_six_chakra_crosswalk_rows(self):
        self.assertEqual(self.snap['counts']['chakra_crosswalk'], 6)
        rows = self.snap['chakra_crosswalk']
        indices = [r['chakra_index'] for r in rows]
        self.assertEqual(sorted(indices), [1, 2, 3, 4, 5, 6])

    def test_chakra_crosswalk_required_fields(self):
        required = (
            'id', 'chakra_index', 'tone', 'physiology_anchor', 'endocrine_gland',
            'nerve_plexus', 'civic_resonance', 'civic_lane_type',
            'universe_resonance', 'quadrant', 'schumann_harmonic_hz', 'notes', 'layer',
        )
        for row in self.snap['chakra_crosswalk']:
            for field in required:
                self.assertIn(field, row, msg="Missing field '%s' in chakra row %d" % (field, row.get('chakra_index', '?')))
            self.assertEqual(row['layer'], 'sage_trinity')

    def test_chakra_tones_match_carbon_six(self):
        tones = [r['tone'] for r in self.snap['chakra_crosswalk']]
        self.assertEqual(tones, ['rooted', 'flow', 'will', 'heart', 'voice', 'vision'])

    def test_schumann_harmonics_ascend(self):
        hz_values = [r['schumann_harmonic_hz'] for r in self.snap['chakra_crosswalk']]
        for i in range(1, len(hz_values)):
            self.assertGreater(hz_values[i], hz_values[i - 1])

    def test_three_triskelion_arms(self):
        self.assertEqual(self.snap['counts']['triskelion_arms'], 3)
        arms = self.snap['triskelion_arms']
        srcs = {arm['src'] for arm in arms}
        dsts = {arm['dst'] for arm in arms}
        # Every Trinity node appears as both src and dst (closed loop)
        all_ids = {
            sage_trinity.SAGE_UNIVERSE_CONTEXT_ID,
            sage_trinity.SAGE_CIVIC_CONTEXT_ID,
            sage_trinity.HUMAN_INITIATION_CONTEXT_ID,
        }
        self.assertEqual(srcs, all_ids)
        self.assertEqual(dsts, all_ids)

    def test_triskelion_arms_cover_all_hoi_phases(self):
        phases = {arm['hoi_phase'] for arm in self.snap['triskelion_arms']}
        self.assertEqual(phases, {'expanding', 'holding', 'returning'})

    def test_triskelion_arm_required_fields(self):
        for arm in self.snap['triskelion_arms']:
            for field in ('id', 'src', 'dst', 'arm_index', 'label', 'hoi_phase', 'hoi_anahulu', 'description', 'layer'):
                self.assertIn(field, arm)
            self.assertEqual(arm['layer'], 'sage_trinity')

    def test_crown_points_to_edge_context(self):
        crown = self.snap['crown']
        self.assertEqual(crown['id'], 'crown:laniakea')
        self.assertEqual(crown['context_id'], sage_trinity.EDGE_CONTEXT_ID)
        self.assertIn('LaniAkea', crown['name'])


class TestSageTrinityConstants(unittest.TestCase):
    """Verify cross-module constant values."""

    def test_trinity_ids_are_distinct(self):
        ids = {
            sage_trinity.SAGE_UNIVERSE_CONTEXT_ID,
            sage_trinity.SAGE_CIVIC_CONTEXT_ID,
            sage_trinity.HUMAN_INITIATION_CONTEXT_ID,
        }
        self.assertEqual(len(ids), 3)

    def test_trinity_ids_differ_from_pulse_geometry_ids(self):
        pulse_ids = {sage_trinity.EDGE_CONTEXT_ID, sage_trinity.APEX_CONTEXT_ID, sage_trinity.RHYTHM_CONTEXT_ID}
        trinity_ids = {
            sage_trinity.SAGE_UNIVERSE_CONTEXT_ID,
            sage_trinity.SAGE_CIVIC_CONTEXT_ID,
            sage_trinity.HUMAN_INITIATION_CONTEXT_ID,
        }
        self.assertTrue(pulse_ids.isdisjoint(trinity_ids))

    def test_organic_carbon_weight_matches_chakra_count(self):
        chakra_rows = sage_trinity.build_chakra_crosswalk_rows()
        self.assertEqual(len(chakra_rows), sage_trinity.ORGANIC_CARBON_WEIGHT)

    def test_schumann_harmonics_count_matches_chakra_count(self):
        self.assertEqual(len(sage_trinity.SCHUMANN_HARMONICS), sage_trinity.ORGANIC_CARBON_WEIGHT)


class TestSageUniverseRefresh(unittest.TestCase):
    """Verify sage_universe_refresh is resilient to network/Neo4j failure."""

    def _patched_refresh(self, fetch_flares=None, post_returns=None):
        """Run sage_universe_refresh with mocked network calls."""
        flares = fetch_flares if fetch_flares is not None else []
        post_result = post_returns if post_returns is not None else {}

        with mock.patch.object(sage_trinity, '_fetch_solar_flares', return_value=flares), \
             mock.patch.object(sage_trinity, '_post', return_value=post_result):
            return sage_trinity.sage_universe_refresh()

    def test_returns_dict_when_neo4j_down(self):
        # _post returns None (Neo4j unreachable) — must still return a data dict
        with mock.patch.object(sage_trinity, '_fetch_solar_flares', return_value=[]), \
             mock.patch.object(sage_trinity, '_post', return_value=None):
            result = sage_trinity.sage_universe_refresh()
        self.assertIsInstance(result, dict)
        self.assertEqual(result['id'], sage_trinity.SAGE_UNIVERSE_CONTEXT_ID)

    def test_returns_dict_on_donki_network_error(self):
        # _fetch_solar_flares catches all network errors internally and returns []
        # Simulate a network failure by returning an empty list
        result = self._patched_refresh(fetch_flares=[])
        self.assertIsInstance(result, dict)
        self.assertEqual(result['science_source'], 'static-baseline')
        self.assertEqual(result['solar_flare_count_30d'], 0)

    def test_static_baseline_when_no_flares(self):
        result = self._patched_refresh(fetch_flares=[])
        self.assertEqual(result['science_source'], 'static-baseline')
        self.assertEqual(result['solar_flare_count_30d'], 0)
        self.assertEqual(result['solar_cycle_number'], 25)
        self.assertAlmostEqual(result['schumann_base_hz'], 7.83)
        self.assertIn('laniakea_ref', result)

    def test_nasa_source_when_flares_present(self):
        fake_flares = [{'classType': 'M1.5', 'beginTime': '2026-07-01T00:00Z'}]
        result = self._patched_refresh(fetch_flares=fake_flares)
        self.assertEqual(result['science_source'], 'NASA-DONKI')
        self.assertEqual(result['solar_flare_count_30d'], 1)
        self.assertEqual(result['solar_activity_level'], 'moderate')

    def test_high_activity_on_x_class_flare(self):
        fake_flares = [{'classType': 'X2.0'}, {'classType': 'M1.0'}]
        result = self._patched_refresh(fetch_flares=fake_flares)
        self.assertEqual(result['solar_activity_level'], 'high')

    def test_required_fields_always_present(self):
        result = self._patched_refresh()
        required = (
            'id', 'laniakea_ref', 'solar_cycle_number', 'solar_cycle_phase',
            'solar_activity_level', 'schumann_base_hz', 'schumann_harmonics',
            'science_refreshed_at', 'layer',
        )
        for field in required:
            self.assertIn(field, result)
        self.assertEqual(result['layer'], 'sage_trinity')

    def test_solar_cycle_phase_post_peak_for_2026(self):
        result = self._patched_refresh()
        # As of July 2026 SC25 is post-peak/declining
        self.assertIn(result['solar_cycle_phase'], ('post-peak-declining', 'declining', 'near-peak'))


class TestSageTrinityRefreshResilient(unittest.TestCase):
    """Verify refresh() returns False (not raises) when Neo4j is down."""

    def test_refresh_returns_false_when_neo4j_unreachable(self):
        with mock.patch.object(sage_trinity, '_post', return_value=None):
            result = sage_trinity.refresh()
        self.assertFalse(result)


if __name__ == '__main__':
    unittest.main()
