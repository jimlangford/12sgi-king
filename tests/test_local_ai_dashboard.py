import json
import unittest
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "go" / "local-ai-functions.json"
DASHBOARD_PATH = ROOT / "go" / "local-ai.html"
GO_INDEX_PATH = ROOT / "go" / "index.html"
GO_LAUNCHER_PATH = ROOT / "go.html"


class _StrictEnoughHtmlParser(HTMLParser):
    def error(self, message):  # pragma: no cover - required by old Python only
        raise AssertionError(message)


class LocalAiDashboardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
        cls.dashboard = DASHBOARD_PATH.read_text(encoding="utf-8")
        cls.go_index = GO_INDEX_PATH.read_text(encoding="utf-8")
        cls.go_launcher = GO_LAUNCHER_PATH.read_text(encoding="utf-8")

    def test_registry_covers_the_required_operating_domains(self):
        self.assertEqual(self.registry["schema"], "quados-local-ai-functions-v1")
        self.assertEqual(self.registry["authority"], "local-primary")
        section_ids = {section["id"] for section in self.registry["sections"]}
        self.assertEqual(
            section_ids,
            {"local-ai", "work", "civic", "studio", "corporate", "knowledge", "system"},
        )
        self.assertGreaterEqual(
            sum(len(section["functions"]) for section in self.registry["sections"]),
            30,
        )

    def test_function_contract_is_unique_safe_and_boundary_labeled(self):
        ids = []
        for section in self.registry["sections"]:
            self.assertTrue(section["description"].strip())
            for function in section["functions"]:
                ids.append(function["id"])
                self.assertIn(function["boundary"], {"PUBLIC", "PRIVATE", "BRIDGE"})
                self.assertIn(
                    function["authority"],
                    {"local-primary", "owner-gated", "optional-bridge"},
                )
                self.assertTrue(function["label"].strip())
                self.assertTrue(function["description"].strip())
                href = function["href"]
                parsed = urlparse(href)
                self.assertFalse(parsed.scheme, href)
                self.assertFalse(parsed.netloc, href)
                self.assertTrue(href.startswith("/"), href)
        self.assertEqual(len(ids), len(set(ids)))

    def test_dashboard_is_private_local_first_and_has_no_embedded_credentials(self):
        parser = _StrictEnoughHtmlParser()
        parser.feed(self.dashboard)
        self.assertIn('meta name="robots" content="noindex,nofollow"', self.dashboard)
        self.assertIn("Your Local AI is the main system.", self.dashboard)
        self.assertIn("./local-ai-functions.json", self.dashboard)
        self.assertIn("optional-bridge", self.dashboard)
        lowered = self.dashboard.lower()
        self.assertNotIn("dev-internal-token", lowered)
        self.assertNotIn("x-service-token", lowered)
        self.assertNotIn("buy.stripe.com", lowered)
        self.assertNotIn("api.anthropic.com", lowered)
        self.assertNotIn("api.openai.com", lowered)

    def test_private_go_route_leads_to_the_launcher_that_headlines_the_local_ai_dashboard(self):
        # /go/ redirects to the King launcher (tests/test_king_go_wrapper_parity.py pins that); the launcher is where the
        # Local AI dashboard is the headline entry.
        self.assertIn("/king/go.html", self.go_index)
        self.assertIn('href="/go/local-ai.html"', self.go_launcher)
        self.assertIn("Local AI is the primary operating system", self.go_launcher)


if __name__ == "__main__":
    unittest.main()
