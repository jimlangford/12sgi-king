import unittest
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class _HrefCollector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.hrefs = set()

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            for name, value in attrs:
                if name == "href" and value:
                    self.hrefs.add(value)


class TestPublicFrontDoor(unittest.TestCase):
    def test_frontdoor_describes_current_public_lanes(self):
        source = (ROOT / "education.html").read_text(encoding="utf-8")
        self.assertNotIn("in development", source.lower())
        self.assertIn("not a claim of state or district approval", source)
        self.assertNotIn("govos-shell.js", source)
        self.assertNotIn('href="govos.css"', source)

        parser = _HrefCollector()
        parser.feed(source)
        self.assertTrue({
            "site/reports.html",
            "site/news_record.html",
            "site/studio.html",
            "site/games/",
            "site/contact.html",
        }.issubset(parser.hrefs))

    def test_publish_workflow_runs_full_site_build(self):
        workflow = (ROOT / ".github" / "workflows" / "publish.yml").read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch:", workflow)
        self.assertIn("python tools/local_validation.py --stage build", workflow)

    def test_public_root_pages_do_not_link_to_private_launcher(self):
        for name in ("grants.html", "platform.html"):
            with self.subTest(page=name):
                source = (ROOT / name).read_text(encoding="utf-8")
                parser = _HrefCollector()
                parser.feed(source)
                self.assertNotIn("go.html", parser.hrefs)
                self.assertIn("site/index.html", parser.hrefs)


if __name__ == "__main__":
    unittest.main()
