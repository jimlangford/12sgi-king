"""Applicant names and addresses appear only when a visitor asks for one (owner, 2026-11-28:
"I'm okay with contact info if click for more is requested not just blasting")."""
import base64
import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "watchers"))

import rebuild_first  # noqa: E402

ROWS = [{"type": "Disaster Recovery", "address": "1 EXAMPLE ST LAHAINA HI", "applied": "2026-05-13", "status": "In Review",
         "desc": "(2023 FIRE) PERSONSON, PAT ʻŌLINO - MAIN DWELLING <b>"}]


def build(tmp_path, monkeypatch):
    index = tmp_path / "permits_index.jsonl"
    index.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in ROWS), encoding="utf-8")
    monkeypatch.setattr(rebuild_first, "IDX", str(index))
    monkeypatch.setattr(rebuild_first, "OUT", str(tmp_path / "page.html"))
    rebuild_first.main()
    return (tmp_path / "page.html").read_text(encoding="utf-8")


def test_the_page_lists_permits_without_names_or_street_addresses(tmp_path, monkeypatch):
    page = build(tmp_path, monkeypatch)
    assert "PERSONSON" not in page and "EXAMPLE ST" not in page and 'class="po"' not in page
    assert "2026-05-13" in page and "In Review" in page and "Lahaina" in page


def test_each_permit_has_its_own_button_that_carries_only_its_details(tmp_path, monkeypatch):
    page = build(tmp_path, monkeypatch)
    buttons = re.findall(r'<button type="button" class="more" data-d="([A-Za-z0-9+/=]+)">Show applicant and address</button>', page)
    assert len(buttons) == 1
    details = json.loads(base64.b64decode(buttons[0]).decode("utf-8"))
    assert details["a"].startswith("PERSONSON, PAT ʻŌLINO") and details["s"] == "1 EXAMPLE ST LAHAINA HI"
    assert "textContent" in page and "innerHTML" not in page


def test_tracked_copies_of_the_page_list_no_names_openly():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for rel in ("reports/mauios/rebuild_first.html", "seed_reports/mauios/rebuild_first.html", "site/rebuild_first.html"):
        path = os.path.join(root, rel)
        if os.path.exists(path):
            with open(path, encoding="utf-8") as page:
                text = page.read()
            assert 'class="po"' not in text and 'class="more" data-d="' in text, rel
