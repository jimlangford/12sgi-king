import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path('/home/runner/work/12sgi-king/12sgi-king')
sys.path.insert(0, str(ROOT))

from watchers import chain_to_graph, graph_vectors


class TestGraphDataPaths(unittest.TestCase):
    def test_chain_path_resolves_repo_reports_from_watchers_layout(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            chain = base / 'repo' / 'reports' / 'mauios' / 'money_chain_maui.json'
            chain.parent.mkdir(parents=True)
            chain.write_text('{}', encoding='utf-8')
            fake_file = base / 'repo' / 'watchers' / 'chain_to_graph.py'
            with mock.patch.object(chain_to_graph, '__file__', str(fake_file)):
                resolved = chain_to_graph._chain_path()
            self.assertEqual(resolved, chain)

    def test_chain_path_resolves_repo_reports_from_legacy_tools_layout(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            chain = base / 'repo' / 'reports' / 'mauios' / 'money_chain_maui.json'
            chain.parent.mkdir(parents=True)
            chain.write_text('{}', encoding='utf-8')
            fake_file = base / 'repo' / 'tools' / 'kilo-aupuni' / 'chain_to_graph.py'
            with mock.patch.object(chain_to_graph, '__file__', str(fake_file)):
                resolved = chain_to_graph._chain_path()
            self.assertEqual(resolved, chain)

    def test_chain_load_returns_false_when_source_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing_dir = Path(tmp) / 'missing'
            with mock.patch.dict(os.environ, {'MAUIOS_REPORTS_DIR': str(missing_dir)}, clear=False):
                self.assertFalse(chain_to_graph.load())

    def test_graph_vectors_honors_override_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            mauios = Path(tmp)
            (mauios / 'money_chain_maui.json').write_text(json.dumps({
                'nodes': [{'id': 'node:a', 'label': 'Aloha Org'}],
                'edges': [{
                    'src': 'node:a',
                    'dst': 'node:a',
                    'kind': 'grant',
                    'amount': 5,
                    'verify': 'source note',
                    'source_url': 'https://example.test',
                    'source_type': 'sourced',
                }],
            }), encoding='utf-8')
            (mauios / 'nonprofits_maui.json').write_text(json.dumps([
                {
                    'name': 'Aloha Org',
                    'city': 'Maui',
                    'category': 'civic',
                    'ein': '12-3456789',
                    'revenue': 10,
                    'expenses': 7,
                    'source_url': 'https://example.test/nonprofit',
                }
            ]), encoding='utf-8')
            with mock.patch.dict(os.environ, {'MAUIOS_REPORTS_DIR': str(mauios)}, clear=False):
                docs = graph_vectors.gather_docs()
            self.assertEqual(len(docs), 2)
            self.assertEqual(docs[0]['kind'], 'grant')
            self.assertEqual(docs[1]['kind'], 'nonprofit_990')


if __name__ == '__main__':
    unittest.main()
