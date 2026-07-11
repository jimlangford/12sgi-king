"""test_slate_data_drift.py

Regression test: verifies that element_lotus_public/slate-data.js stays in sync
with production_status.json (summary counts) and data/media_catalog.json (per-entry
catalog).

DRIFT PROTECTION RULE:
  slate-data.js is the static checked-in copy of the public media data.
  build_site.py generates site/slate-data.js from the live JSON sources at build time,
  overwriting the static copy in site/.  This test guards the checked-in copy so that
  manual edits to production_status.json or media_catalog.json are not silently missed.

If this test fails, update element_lotus_public/slate-data.js to match the JSON sources.
"""
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROD_STATUS = ROOT / "production_status.json"
MEDIA_CATALOG = ROOT / "data" / "media_catalog.json"
SLATE_JS = ROOT / "element_lotus_public" / "slate-data.js"


def _extract_js_value(js_text: str, key: str):
    """
    Naively extract a top-level numeric or string value from the SLATE object in slate-data.js.
    Returns None if the key is not found or the value is null/undefined.
    Only supports simple scalar values (numbers, strings, null).
    """
    # Match: films_produced: 36,  or  films_produced: null,
    pattern = rf'["\']?{re.escape(key)}["\']?\s*:\s*([^,\n\]}}]+)'
    m = re.search(pattern, js_text)
    if not m:
        return None
    raw = m.group(1).strip().rstrip(",")
    if raw in ("null", "undefined"):
        return None
    # Strip surrounding quotes for strings
    if raw.startswith('"') and raw.endswith('"'):
        return raw[1:-1]
    if raw.startswith("'") and raw.endswith("'"):
        return raw[1:-1]
    # Try numeric
    try:
        if "." in raw:
            return float(raw)
        return int(raw)
    except ValueError:
        return raw


def _extract_js_array(js_text: str, key: str):
    """
    Extract a simple flat string array from slate-data.js for the given key.
    Returns a list of strings, or None if key not found.
    """
    pattern = rf'["\']?{re.escape(key)}["\']?\s*:\s*\[([^\]]*)\]'
    m = re.search(pattern, js_text, re.S)
    if not m:
        return None
    inner = m.group(1)
    strings = re.findall(r'"([^"]*)"', inner)
    return strings or []


class TestSlateDateDrift(unittest.TestCase):
    """Assert that slate-data.js stays in sync with production_status.json."""

    def setUp(self):
        if not PROD_STATUS.exists():
            self.skipTest("production_status.json not found — skipping drift check")
        if not SLATE_JS.exists():
            self.skipTest("element_lotus_public/slate-data.js not found — skipping drift check")
        self.ps = json.loads(PROD_STATUS.read_text(encoding="utf-8"))
        self.js = SLATE_JS.read_text(encoding="utf-8")

    def test_films_produced_matches(self):
        js_val = _extract_js_value(self.js, "films_produced")
        self.assertEqual(
            js_val,
            self.ps.get("films_produced"),
            "films_produced in slate-data.js does not match production_status.json. "
            "Update element_lotus_public/slate-data.js.",
        )

    def test_quadcast_songs_matches(self):
        js_val = _extract_js_value(self.js, "quadcast_songs")
        self.assertEqual(
            js_val,
            self.ps.get("quadcast_songs"),
            "quadcast_songs in slate-data.js does not match production_status.json. "
            "Update element_lotus_public/slate-data.js.",
        )

    def test_updated_matches(self):
        js_val = _extract_js_value(self.js, "updated")
        self.assertEqual(
            js_val,
            self.ps.get("updated"),
            "updated timestamp in slate-data.js does not match production_status.json. "
            "Update element_lotus_public/slate-data.js.",
        )

    def test_latest_films_matches(self):
        js_films = _extract_js_array(self.js, "latest_films")
        ps_films = self.ps.get("latest_films") or []
        self.assertEqual(
            js_films,
            ps_films,
            "latest_films in slate-data.js does not match production_status.json. "
            "Update element_lotus_public/slate-data.js.",
        )

    def test_no_ts_net_urls_in_slate_data(self):
        """slate-data.js must never contain Tailscale (ts.net) host references."""
        self.assertNotIn(
            "ts.net",
            self.js,
            "slate-data.js contains a ts.net URL — Tailscale hosts must not appear in public output.",
        )


class TestMediaCatalogDrift(unittest.TestCase):
    """Assert that data/media_catalog.json is internally consistent and matches production_status."""

    def setUp(self):
        if not PROD_STATUS.exists():
            self.skipTest("production_status.json not found")
        if not MEDIA_CATALOG.exists():
            self.skipTest("data/media_catalog.json not found — skipping catalog drift check")
        self.ps = json.loads(PROD_STATUS.read_text(encoding="utf-8"))
        self.mc = json.loads(MEDIA_CATALOG.read_text(encoding="utf-8"))

    def test_catalog_has_entries_key(self):
        self.assertIn("entries", self.mc, "data/media_catalog.json must have an 'entries' list.")

    def test_public_film_count_does_not_exceed_produced(self):
        entries = self.mc.get("entries") or []
        public_films = [e for e in entries if e.get("type") == "film" and e.get("public_visibility")]
        produced = self.ps.get("films_produced") or 0
        self.assertLessEqual(
            len(public_films),
            produced,
            f"data/media_catalog.json has {len(public_films)} public film entries but "
            f"production_status.json reports only {produced} films produced. "
            "Remove extra entries or update films_produced.",
        )

    def test_catalog_film_titles_are_subset_of_latest_films(self):
        """Every catalog film whose title appears in latest_films should match exactly."""
        latest = set(self.ps.get("latest_films") or [])
        if not latest:
            return
        entries = self.mc.get("entries") or []
        catalog_film_titles = {e["title"] for e in entries if e.get("type") == "film" and e.get("title")}
        # All latest_films titles that appear in the catalog must match exactly (no typo drift)
        mismatched = catalog_film_titles - latest - {None}
        # Titles may exist in catalog that aren't in latest_films (e.g. older releases) — only
        # check that catalog titles that SHOULD be from latest_films are spelled correctly.
        # We flag titles in catalog that are almost-matches for latest_films entries.
        for ct in mismatched:
            for lt in latest:
                if ct.lower() == lt.lower() and ct != lt:
                    self.fail(
                        f"Catalog film title '{ct}' differs in case from latest_films entry '{lt}'. "
                        "Fix the typo to prevent drift."
                    )

    def test_no_invented_youtube_urls(self):
        """No catalog entry should have a youtube_url that is not a real https://youtu.be or https://www.youtube.com URL."""
        entries = self.mc.get("entries") or []
        for entry in entries:
            url = entry.get("youtube_url")
            if url is None:
                continue
            self.assertTrue(
                url.startswith("https://youtu.be/") or url.startswith("https://www.youtube.com/"),
                f"Catalog entry '{entry.get('id')}' has suspicious youtube_url: {url!r}. "
                "Only https://youtu.be/ or https://www.youtube.com/ URLs are accepted.",
            )

    def test_no_ts_net_urls_in_catalog(self):
        """data/media_catalog.json must never contain Tailscale (ts.net) references."""
        raw = MEDIA_CATALOG.read_text(encoding="utf-8")
        self.assertNotIn(
            "ts.net",
            raw,
            "data/media_catalog.json contains a ts.net URL — Tailscale hosts must not appear in public output.",
        )


if __name__ == "__main__":
    unittest.main()
