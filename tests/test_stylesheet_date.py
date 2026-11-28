"""The site build stamps one Hawaiʻi date, so stylesheet order cannot change with the time of day.

2026-11-27: rebuild_site used the machine's date (UTC in CI) and build_site used Hawaiʻi's. After
2 pm in Hawaiʻi the two differed, a stylesheet stayed below the page's own styles, and the
accessibility gate failed on pages nobody had changed.
"""

import datetime
import pathlib

import rebuild_site

ROOT = pathlib.Path(__file__).resolve().parents[1]


def test_build_date_is_the_hawaii_date_when_utc_is_already_tomorrow():
    evening = datetime.datetime(2026, 11, 28, 2, 40, tzinfo=datetime.timezone.utc)
    assert rebuild_site.build_date(evening) == "2026-11-27"


def test_site_builder_hands_its_own_date_to_the_stamp():
    source = (ROOT / "build_site.py").read_text(encoding="utf-8")
    assert "_rs.BUILD_V = BUILD_V" in source


def test_public_feed_cards_are_light_like_the_text_on_them():
    for rel in ("watchers/prosecutor_public_feed.py", "seed_reports/mauios/prosecutor_public_feed.html"):
        text = (ROOT / rel).read_text(encoding="utf-8")
        card = text[text.index(".finding{"):].split("}", 1)[0]
        assert "background:#fff" in card, rel
