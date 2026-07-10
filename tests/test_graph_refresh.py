import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path('/home/runner/work/12sgi-king/12sgi-king')
sys.path.insert(0, str(ROOT))

from watchers import graph_refresh


class TestGraphRefresh(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.state_path = Path(self._tmp.name) / 'graph-refresh-state.json'
        self.old_state_path = graph_refresh.STATE_PATH
        self.old_neo = graph_refresh.NEO
        self.old_version = graph_refresh.GRAPH_STACK_VERSION
        graph_refresh.STATE_PATH = self.state_path
        graph_refresh.NEO = 'http://neo4j:7474/db/neo4j/tx/commit'
        graph_refresh.GRAPH_STACK_VERSION = '5.2'

    def tearDown(self):
        graph_refresh.STATE_PATH = self.old_state_path
        graph_refresh.NEO = self.old_neo
        graph_refresh.GRAPH_STACK_VERSION = self.old_version
        self._tmp.cleanup()

    def test_status_reports_private_graph_stack_defaults(self):
        body = graph_refresh.status()
        self.assertEqual(body['boundary'], 'PRIVATE')
        self.assertEqual(body['graph_stack_version'], '5.2')
        self.assertEqual(body['neo4j_http'], 'http://neo4j:7474/db/neo4j/tx/commit')
        self.assertEqual(body['status'], 'idle')
        self.assertEqual(body['supported_targets'], list(graph_refresh.DEFAULT_TARGETS))
        self.assertIsNone(body['freshness']['last_successful_at'])
        self.assertEqual(body['audit_lens']['frame'], '12-stone-earth-justice-audit')
        self.assertEqual(body['audit_lens']['money_intention']['edge_context_id'], graph_refresh.EDGE_CONTEXT_ID)
        self.assertEqual(len(body['audit_lens']['levi_breastplate']['stones']), 12)
        self.assertEqual(body['audit_lens']['urim']['context_id'], graph_refresh.EDGE_CONTEXT_ID)
        self.assertEqual(
            body['audit_lens']['thummim']['context_ids'],
            [graph_refresh.APEX_CONTEXT_ID, graph_refresh.RHYTHM_CONTEXT_ID],
        )

    def test_incremental_refresh_updates_state_for_targeted_layers(self):
        fake_chain = types.SimpleNamespace(load=lambda: True)
        fake_vectors = types.SimpleNamespace(build=lambda: True)
        fake_spine = types.SimpleNamespace(refresh=lambda: True)
        fake_pulse = types.SimpleNamespace(refresh=lambda: True)
        with mock.patch.dict(
            sys.modules,
            {
                'chain_to_graph': fake_chain,
                'graph_vectors': fake_vectors,
                'private_spine': fake_spine,
                'pulse_geometry': fake_pulse,
            },
        ):
            ok = graph_refresh.refresh(
                mode='incremental',
                reason='unit-test',
                targets=['private_spine', 'pulse_geometry'],
            )
        self.assertTrue(ok)
        body = graph_refresh.status()
        self.assertEqual(body['status'], 'idle')
        self.assertEqual(body['last_mode'], 'incremental')
        self.assertEqual(body['last_reason'], 'unit-test')
        self.assertEqual(body['requested_targets'], ['private_spine', 'pulse_geometry'])
        self.assertEqual(body['layers']['private_spine'], 'current')
        self.assertEqual(body['layers']['pulse_geometry'], 'current')
        self.assertEqual(body['layers']['graph'], 'skipped')
        self.assertEqual(body['layers']['vectors'], 'skipped')
        self.assertEqual(body['last_result'], 'ok')
        self.assertIsNotNone(body['freshness']['last_successful_at'])


if __name__ == '__main__':
    unittest.main()
