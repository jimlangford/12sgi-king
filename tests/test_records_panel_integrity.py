"""
Records & Assets panel integrity tests.

Covers the required test matrix from the panel specification:

  - Records appears only in private mode.
  - Records requires a valid owner token (owner:true in ITEMS).
  - Records.dc.html is present in the deployed site/king/ bundle.
  - Records.dc.html is absent from the public site root artifact (site/Records.dc.html).
  - Remote iPad access resolves /openwebui/, not localhost, as default.
  - Context selectors (civic/media/graph/board) each produce scoped context text.
  - No raw loopback credentials embedded as a primary/default URL in HTML.
  - Existing Naga panels remain unchanged.
  - Open WebUI proxy configuration documents WebSocket and subpath requirements.
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KING_SRC = ROOT / 'king_public_src'
PANEL = KING_SRC / 'Records.dc.html'
SHELL = KING_SRC / 'index.html'
NGINX_CONF = ROOT / 'docs' / 'nginx-tailnet-proxy.example.conf'


class TestRecordsPanelSource(unittest.TestCase):
    """Static analysis of the panel source files — no build required."""

    def setUp(self):
        self.shell = SHELL.read_text(encoding='utf-8')
        self.panel = PANEL.read_text(encoding='utf-8')

    # ── existence ─────────────────────────────────────────────────────────
    def test_panel_file_exists(self):
        self.assertTrue(PANEL.exists(), "Records.dc.html must exist in king_public_src/")

    # ── index.html wiring ─────────────────────────────────────────────────
    def test_items_entry_present(self):
        self.assertIn("id:'records'", self.shell)

    def test_items_entry_is_private_only(self):
        """Records must only appear in private mode."""
        m = re.search(r"\{[^}]*id:'records'[^}]*\}", self.shell)
        self.assertIsNotNone(m, "records ITEMS entry not found")
        entry = m.group()
        self.assertIn("modes:['private']", entry,
                      "Records must be private-only — no 'public' in modes")
        self.assertNotIn("'public'", entry)

    def test_items_entry_requires_owner_token(self):
        m = re.search(r"\{[^}]*id:'records'[^}]*\}", self.shell)
        self.assertIsNotNone(m)
        self.assertIn('owner:true', m.group(),
                      "Records must require owner:true (valid token required)")

    def test_items_entry_is_not_core(self):
        """Records should route through More, not clutter the main nav."""
        m = re.search(r"\{[^}]*id:'records'[^}]*\}", self.shell)
        self.assertIsNotNone(m)
        self.assertIn('core:false', m.group())

    def test_avail_registry_includes_records(self):
        self.assertIn("'records'", self.shell)

    def test_show_records_computed(self):
        self.assertIn('showRecords', self.shell)

    def test_dc_import_present(self):
        self.assertIn('<dc-import name="Records"', self.shell)

    def test_show_records_guarded_by_unlocked_and_avail(self):
        """showRecords must check both unlocked (owner token) and avail()."""
        m = re.search(r"showRecords\s*:[^,\n]+", self.shell)
        self.assertIsNotNone(m, "showRecords assignment not found")
        expr = m.group()
        self.assertIn('unlocked', expr)
        self.assertIn("avail('records')", expr)

    # ── panel HTML / JS content ───────────────────────────────────────────
    def test_four_context_selectors_present(self):
        for ctx in ('civic', 'media', 'graph', 'board'):
            self.assertIn("setRecordsContext('%s')" % ctx, self.panel,
                          "Missing context selector: %s" % ctx)

    def test_context_prompts_include_provenance_instruction(self):
        self.assertIn('source attribution', self.panel)
        self.assertIn('provenance', self.panel)
        self.assertIn('tenant boundaries', self.panel)

    def test_context_prompts_include_all_four_scope_labels(self):
        for label in ('Civic Records', 'Media Assets', 'Graph Nodes', 'Workboard'):
            self.assertIn(label, self.panel,
                          "Scoped context prompt missing label: %s" % label)

    def test_copy_send_open_buttons_present(self):
        self.assertIn('recCopyContext', self.panel)
        self.assertIn('recSendContext', self.panel)
        self.assertIn('recOpenChat', self.panel)

    def test_send_context_is_honest_about_cross_origin(self):
        """Send Context must NOT claim the chat was prefilled; must say paste."""
        self.assertIn('Context copied', self.panel)
        self.assertIn('paste into Open WebUI', self.panel)
        # Must not claim successful injection into the iframe
        self.assertNotIn('chat was prefilled', self.panel)
        self.assertNotIn('chat prefilled', self.panel)

    # ── URL resolution — remote/iPad correctness ──────────────────────────
    def test_default_url_is_same_origin_proxy(self):
        """The first non-override resolution step must be /openwebui/, not localhost."""
        self.assertIn('/openwebui/', self.panel)
        # Check that /openwebui/ appears before the 127.0.0.1 fallback in source order
        idx_proxy = self.panel.index('/openwebui/')
        idx_loop  = self.panel.index('127.0.0.1:3000')
        self.assertLess(idx_proxy, idx_loop,
                        "/openwebui/ must appear before 127.0.0.1:3000 in source")

    def test_window_override_vars_present(self):
        self.assertIn('window.OPEN_WEBUI_URL', self.panel)
        self.assertIn('window.KING_OPEN_WEBUI_URL', self.panel)

    def test_loopback_is_fallback_not_default(self):
        """127.0.0.1:3000 must only appear in a fallback/local-only context."""
        self.assertIn('127.0.0.1:3000', self.panel)
        # The fallback must be clearly labelled as local-only
        self.assertTrue(
            'local' in self.panel.lower() or 'fallback' in self.panel.lower(),
            "127.0.0.1:3000 used but no 'local' or 'fallback' label found in panel"
        )

    def test_no_hardcoded_loopback_as_primary_url_in_resolve_function(self):
        """_resolveOpenWebuiUrl must not return 127.0.0.1 as its last/default value."""
        m = re.search(
            r'function _resolveOpenWebuiUrl\(\)\s*\{(.+?)\}',
            self.panel, re.DOTALL
        )
        self.assertIsNotNone(m, "_resolveOpenWebuiUrl function not found")
        fn_body = m.group(1)
        self.assertNotIn('127.0.0.1', fn_body,
                         "127.0.0.1 must not appear inside _resolveOpenWebuiUrl (loopback is in _localFallback only)")

    # ── public client separation ──────────────────────────────────────────
    def test_panel_is_owner_private_labelled(self):
        self.assertIn('owner · private', self.panel)

    def test_no_public_client_content_in_panel(self):
        """Panel must not expose public client paths, tenants, or rate-limit bypass."""
        for forbidden in ('public_client', 'rate_limit_bypass', 'public.*profile'):
            self.assertIsNone(
                re.search(forbidden, self.panel, re.IGNORECASE),
                "Forbidden public-client pattern '%s' found in panel" % forbidden
            )

    # ── existing panels unchanged ─────────────────────────────────────────
    def test_existing_owner_panels_still_wired(self):
        """Verify known owner panels are still present in index.html."""
        for surface in ('graph', 'gpu', 'events', 'connectors', 'ops', 'hub', 'launch'):
            self.assertIn("id:'%s'" % surface, self.shell,
                          "Existing panel '%s' was removed from ITEMS" % surface)

    def test_existing_avail_entries_intact(self):
        for surface in ('graph', 'gpu', 'events', 'connectors', 'ops', 'hub'):
            self.assertIn("'%s'" % surface, self.shell,
                          "Existing AVAIL entry '%s' removed" % surface)


class TestNginxProxyConfig(unittest.TestCase):
    """Verify the nginx example conf documents the /openwebui/ requirements."""

    def setUp(self):
        self.conf = NGINX_CONF.read_text(encoding='utf-8')

    def test_openwebui_location_block_present(self):
        self.assertIn('location /openwebui/', self.conf)

    def test_proxy_pass_to_loopback_3000(self):
        # The /openwebui/ block must proxy to 127.0.0.1:3000
        m = re.search(
            r'location /openwebui/\s*\{(.+?)\}',
            self.conf, re.DOTALL
        )
        self.assertIsNotNone(m, "location /openwebui/ block not found")
        block = m.group(1)
        self.assertIn('proxy_pass', block)
        self.assertIn('3000', block)

    def test_websocket_upgrade_headers_present(self):
        m = re.search(r'location /openwebui/\s*\{(.+?)\}', self.conf, re.DOTALL)
        self.assertIsNotNone(m)
        block = m.group(1)
        self.assertIn('Upgrade $http_upgrade', block)
        self.assertIn('Connection', block)

    def test_x_forwarded_prefix_present(self):
        m = re.search(r'location /openwebui/\s*\{(.+?)\}', self.conf, re.DOTALL)
        self.assertIsNotNone(m)
        self.assertIn('X-Forwarded-Prefix', m.group(1))

    def test_frame_ancestors_csp_not_wildcard(self):
        """CSP frame-ancestors must not be * — must restrict to Naga origin."""
        # Confirm a CSP directive is present
        self.assertIn('Content-Security-Policy', self.conf)
        self.assertIn('frame-ancestors', self.conf)
        # Must NOT use wildcard in the actual directive (comment text excluded)
        # Split on comments before checking
        non_comment_lines = [l for l in self.conf.splitlines() if not l.strip().startswith('#')]
        conf_no_comments = '\n'.join(non_comment_lines)
        self.assertNotIn("frame-ancestors *", conf_no_comments)
        self.assertNotIn("frame-ancestors '*'", conf_no_comments)

    def test_webui_url_env_var_documented(self):
        """WEBUI_URL env var must be mentioned so operator knows to set it."""
        self.assertIn('WEBUI_URL', self.conf)


class TestRecordsBuildArtifact(unittest.TestCase):
    """
    Full build test: Records.dc.html must be in site/king/ and not at site root.
    Mirrors test_owner_jobs_not_public.py pattern.
    """

    @classmethod
    def setUpClass(cls):
        cls._tmp_site = tempfile.mkdtemp(prefix='king-records-check-')
        env = os.environ.copy()
        env['KA_SITE'] = cls._tmp_site
        result = subprocess.run(
            [sys.executable, 'build_site.py'],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
        )
        cls._build_stdout = result.stdout
        cls._build_returncode = result.returncode

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls._tmp_site, ignore_errors=True)

    def test_build_succeeds(self):
        self.assertEqual(
            self._build_returncode, 0,
            'build_site.py exited non-zero:\n' + self._build_stdout,
        )

    def test_records_panel_in_king_bundle(self):
        """Records.dc.html must be present inside site/king/ (private owner bundle)."""
        path = Path(self._tmp_site) / 'king' / 'Records.dc.html'
        self.assertTrue(
            path.exists(),
            'Records.dc.html not found in site/king/ — deployment allowlist may be missing it',
        )

    def test_records_panel_not_at_site_root(self):
        """Records.dc.html must not be copied directly to the site root."""
        path = Path(self._tmp_site) / 'Records.dc.html'
        self.assertFalse(
            path.exists(),
            'Records.dc.html found at site root — it must only be inside site/king/',
        )

    def test_index_html_in_king_bundle(self):
        """The updated index.html (with records wiring) must be in site/king/."""
        idx = Path(self._tmp_site) / 'king' / 'index.html'
        self.assertTrue(idx.exists(), 'site/king/index.html missing from build')
        text = idx.read_text(encoding='utf-8')
        # After build, the shell is replaced by king_landing.html at index.html;
        # the original app.html with the full Naga shell is at app.html.
        app = Path(self._tmp_site) / 'king' / 'app.html'
        if app.exists():
            app_text = app.read_text(encoding='utf-8')
            self.assertIn("id:'records'", app_text,
                          "records ITEMS entry missing from built app.html")
        else:
            self.assertIn("id:'records'", text,
                          "records ITEMS entry missing from built index.html")


if __name__ == '__main__':
    unittest.main()
