import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "watchers" / "agenda_explainer.py"


def _module():
    spec = importlib.util.spec_from_file_location("agenda_explainer_under_test", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_each_card_has_public_safe_stable_share_url():
    module = _module()
    meeting = {
        "body": "County Council",
        "title": "Housing agenda",
        "date": "2026-12-01",
        "url": "https://example.gov/agenda/1",
    }
    rendered = module.card("maui", meeting, 7)
    reordered = module.card("maui", meeting, 99)
    card_id = module.stable_card_id("maui", meeting)

    assert rendered == reordered
    assert ('id="explainer-%s"' % card_id) in rendered
    assert ('data-card-id="%s"' % card_id) in rendered
    assert ('data-url="https://12sgi.com/agenda_explainer.html?card=%s"' % card_id) in rendered
    assert "data-manual-share" in rendered
    assert "jimlangford.github.io" not in rendered


def test_built_page_loads_reusable_share_module_and_keeps_no_autopost_boundary():
    module = _module()
    rendered = module.build()

    assert '<script src="assets/sgi-share.js" defer></script>' in rendered
    assert "SGIShare.addShareTools" in rendered
    assert "no auto-posting" in rendered
    assert "publish_approved_social" not in rendered


def test_static_builder_ships_the_share_asset_without_connector_code():
    source = (ROOT / "build_site.py").read_text(encoding="utf-8")

    assert 'os.path.join(_here, "assets", "sgi-share.js")' in source
    assert 'os.path.join(_share_dir, "sgi-share.js")' in source
    assert "publish_approved_social" not in source
