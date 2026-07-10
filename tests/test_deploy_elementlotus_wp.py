import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path('/home/runner/work/12sgi-king/12sgi-king')
sys.path.insert(0, str(ROOT))

from watchers import deploy_elementlotus_wp


class TestDeployElementLotusWp(unittest.TestCase):
    def test_rewrite_url_preserves_wordpress_and_static_boundaries(self):
        self.assertEqual(deploy_elementlotus_wp.rewrite_url('index.html'), '/')
        self.assertEqual(deploy_elementlotus_wp.rewrite_url('about.html'), '/about/')
        self.assertEqual(deploy_elementlotus_wp.rewrite_url('games/'), 'https://12sgi.com/games/')
        self.assertEqual(
            deploy_elementlotus_wp.rewrite_url('games/mahjong_crosswalk.html'),
            'https://12sgi.com/games/mahjong_crosswalk.html',
        )
        self.assertEqual(
            deploy_elementlotus_wp.rewrite_url('reports.html'),
            'https://12sgi.com/reports.html',
        )
        self.assertEqual(
            deploy_elementlotus_wp.rewrite_url('https://elementlotus.com/join/'),
            'https://elementlotus.com/join/',
        )

    def test_prefix_css_scopes_root_and_media_rules(self):
        css = ':root{--gold:#fff} html,body{margin:0} a,.card{color:gold}@media (max-width:600px){body{padding:0}}'
        scoped = deploy_elementlotus_wp.prefix_css(css)
        self.assertIn('.element-lotus-shell{--gold:#fff}', scoped)
        self.assertIn('.element-lotus-shell{margin:0}', scoped)
        self.assertIn('.element-lotus-shell a, .element-lotus-shell .card{color:gold}', scoped)
        self.assertIn('@media (max-width:600px){.element-lotus-shell{padding:0}', scoped)

    def test_build_writes_manifest_fragments_and_scoped_css(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            src = base / 'src'
            out = base / 'out'
            src.mkdir()
            (src / 'studio.css').write_text(':root{--bg:#000} body{margin:0}', encoding='utf-8')
            sample = (
                '<!doctype html><html><head><title>Sample</title>'
                '<meta name="description" content="desc"></head>'
                '<body><div class="shell"><a href="games/">Games</a>'
                '<a href="about.html">About</a><a href="reports.html">Reports</a></div></body></html>'
            )
            for page in deploy_elementlotus_wp.PAGES:
                (src / page['source']).write_text(sample, encoding='utf-8')
            manifest = deploy_elementlotus_wp.build(src_dir=src, out_dir=out)
            self.assertEqual(len(manifest['pages']), len(deploy_elementlotus_wp.PAGES))
            fragment = (out / 'front-page.html').read_text(encoding='utf-8')
            self.assertIn('https://12sgi.com/games/', fragment)
            self.assertIn('/about/', fragment)
            self.assertIn('https://12sgi.com/reports.html', fragment)
            css_out = (out / 'additional-css.css').read_text(encoding='utf-8')
            self.assertIn('.element-lotus-shell{--bg:#000}', css_out)
            self.assertIn('.element-lotus-shell{margin:0}', css_out)
            saved_manifest = json.loads((out / 'manifest.json').read_text(encoding='utf-8'))
            self.assertEqual(saved_manifest['pages'][0]['output'], 'front-page.html')


if __name__ == '__main__':
    unittest.main()
