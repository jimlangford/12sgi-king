"""Public oversight pages carry sourced facts only: no working notes, raw records or testifier lists.

2026-11-27: internal notes with unverified claims, raw data and a list of testifiers under a keyword-based label
reached the public oversight page and the public feed.
"""

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "watchers"))

import aloha_oversight  # noqa: E402

BANNED = re.compile(
    r"\boperator(:| alleges)|TO BE IDENTIFIED|cross testifier|real-estate-affiliated|recused \S+ \{|homeowners\s*\(",
    re.I,
)
PAGES = (
    "seed_reports/mauios/oversight_hi-maui.html",
    "reports/mauios/oversight_hi-maui.html",
    "site/oversight_hi-maui.html",
    "seed_reports/mauios/prosecutor_public_feed.html",
    "seed_reports/mauios/prosecutor_public_feed.json",
    "site/prosecutor_public_feed.html",
)


def _case(**over):
    case = {"id": "A", "title": "T", "question": "Does the record answer?", "strength": 4,
            "evidence": [{"k": "money", "v": "donation (CSC)"}], "next": "UIPA: the bid file."}
    case.update(over)
    return case


def test_tracked_public_pages_have_no_working_notes():
    for rel in PAGES:
        path = ROOT / rel
        if path.exists():
            assert not BANNED.search(path.read_text(encoding="utf-8")), rel


def test_builder_shows_only_fact_evidence_and_trims_internal_instructions():
    shaped = aloha_oversight.aloha_finding(_case(
        evidence=[{"k": "money", "v": "donation (CSC)"}, {"k": "lead", "v": "a note"}, {"k": "voice", "v": "A Person"}],
        next="UIPA: the log; cross names to the list.",
    ))
    assert shaped["record"] == ["donation (CSC)"]
    assert shaped["asked"] == "UIPA: the log."


def test_builder_holds_private_matters(monkeypatch):
    cases = [_case(), _case(id="B", question="Private?", private_only="names people"),
             _case(id="C", question="Note only?", evidence=[{"k": "lead", "v": "note (minutes)"}])]
    monkeypatch.setattr(aloha_oversight.CD, "tenant_cases", lambda tenant, maui: cases)
    monkeypatch.setattr(aloha_oversight.CD, "gate", lambda case: ("REVIEW-READY", []))
    shown, held, _ = aloha_oversight.cleared({"id": "hi-maui"}, [])
    assert [item["id"] for item in shown] == ["A"] and held == 2
