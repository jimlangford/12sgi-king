#!/usr/bin/env python3
"""civic_post_gate.py — Hawaiʻi Sunshine Law (HRS 92) + UIPA (HRS 92F) compliance gate that
EVERY civic post / agenda reel / social push MUST pass before it publishes.
(Jimmy 2026-07-03, signed James. Law sourced from Hawaiʻi Office of Information Practices, ags.hawaii.gov/oip.)

THE LAW, STRAIGHT — two DISTINCT statutes, never conflate them:
  • HRS Chapter 92 = the SUNSHINE LAW = open MEETINGS. A board must post its agenda/notice
    >= 6 CALENDAR DAYS before a meeting (HRS §92-7(b); if posted electronically < 6 days the meeting
    "shall be canceled as a matter of law", §92-7(c)); agenda must list all items + accommodation
    instructions (§92-7(a)); minutes are a true reflection incl. individual member votes and are
    posted within 40 days (§92-9). This governs the GOVERNMENT's conduct — not ours. Our duty when we
    MIRROR/repost an agenda: never present our repost as the official notice; link to the OFFICIAL
    posting; respect the 6-day framing.  src: https://ags.hawaii.gov/oip/laws-rules-opinions/sunshine-law/
  • HRS Chapter 92F = UIPA = public RECORDS access. "All government records are open to public
    inspection unless access is restricted or closed by law" (§92F-11(a)); personal-record requests
    answered within 10 working days (§92F-23). This is the statute the Bill 9 roll-call request runs
    under. Our duty: cite the record + its retrieval date.  src: https://ags.hawaii.gov/oip/uipa/

COMPLIANCE REQUIREMENTS (all must pass before publish):
  R1 source_link      — a link to the public record / official source
  R2 retrieval_date   — the date the figure/record was retrieved (or an ISO date in the text)
  R3 disclaimer       — the "unofficial mirror · sourced from public record" line
  R4 mirror_official  — if it mirrors an AGENDA: link the OFFICIAL posting; do not claim to be the notice
  R5 not_accusation   — framed as record/question, never accusation (no libel verbs)
"""
import re

SOURCE_URL_SUNSHINE = "https://ags.hawaii.gov/oip/laws-rules-opinions/sunshine-law/"   # HRS 92
SOURCE_URL_UIPA     = "https://ags.hawaii.gov/oip/uipa/"                                # HRS 92F
DISCLAIMER = ("Unofficial mirror — sourced from the public record. This is not the official government "
              "notice; see the official posting linked above. Every figure cites its source and retrieval "
              "date. If the source record changes, this will be corrected — corrections: elementlotus@gmail.com.")
ACCUSATORY = re.compile(r'\b(corrupt|brib\w+|illegal|criminal|guilty|stole|steals|conspir\w+|kickback)\b', re.I)


def check(text, is_agenda_mirror=False, has_source_link=None, retrieval_date=None, official_link=None):
    """Return (ok: bool, missing: list[str]). Non-raising; use enforce() to hard-block a publish."""
    t = text or ""
    missing = []
    has_link = has_source_link if has_source_link is not None else bool(re.search(r'https?://', t))
    if not has_link:
        missing.append("R1 source_link")
    has_date = bool(retrieval_date) or bool(re.search(r'\b20\d\d-\d\d-\d\d\b', t)) or bool(re.search(r'\b(retrieved|as of|sourced)\b', t, re.I))
    if not has_date:
        missing.append("R2 retrieval_date")
    tl = t.lower()
    if 'unofficial mirror' not in tl and 'sourced from the public record' not in tl and 'sourced from public record' not in tl:
        missing.append("R3 disclaimer")
    if is_agenda_mirror and not (official_link or 'official posting' in tl):
        missing.append("R4 mirror_official_link")
    if ACCUSATORY.search(t):
        missing.append("R5 accusatory_language")
    return (len(missing) == 0, missing)


def enforce(text, **kw):
    """Hard gate: raise ValueError if the civic post is not HRS 92/92F compliant. Call this in the publish path."""
    ok, missing = check(text, **kw)
    if not ok:
        raise ValueError("CIVIC-POST GATE FAILED (HRS 92/92F): missing " + ", ".join(missing) +
                         " — see tools/kilo-aupuni/civic_post_gate.py")
    return True


if __name__ == "__main__":
    # self-test
    bad = "Councilmember X took bribes on Bill 9."
    good = ("Bill 9 real-estate testimony, 22 appearances (2026-02-18). Unofficial mirror — sourced from the "
            "public record; official posting: https://mauicounty.portal.civicclerk.com/ retrieved 2026-07-03.")
    print("bad ->", check(bad))
    print("good->", check(good, is_agenda_mirror=True, official_link="https://mauicounty.portal.civicclerk.com/"))
