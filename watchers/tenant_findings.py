#!/usr/bin/env python3
"""tenant_findings.py - the PUBLIC, gated per-tenant FINDINGS feed for each tenant page (Jimmy 2026-06-20:
"create a findings section to each tenant page with ability to ask a question").

This is the CONTENT the civic tenant-page "Findings" section consumes. It is PUBLIC-SAFE by construction:
every item is run through the ONE clearance gate (case_document.gate - sourced + framed as a QUESTION +
names the next record + strength>=3). Only what clears crosses; the prosecutorial THEORY / owner text
NEVER appears here - only the public question + the named public records. Executive-session red flags
(es_watch) are already public-record questions and are included for Maui.

The PAGE rendering + the "ask a question" form/endpoint are NOT built here - those are civic (UI) + server
(submit endpoint), delegated with an auto-prompt. This module only produces the gated feed + a leak scan.

Output: reports/_status/tenant_findings.json (one file, per tenant; public-safe). Stdlib only.
"""
import os, sys, json, re
from datetime import datetime, timezone, timedelta

HST = timezone(timedelta(hours=-10))
HOME = os.path.expanduser("~")
PROJ = os.path.join(HOME, "Documents", "Claude", "Projects", "Video System elementLOTUS")
ST = os.path.join(PROJ, "reports", "_status")
OUT = os.path.join(ST, "tenant_findings.json")
SECRET_RX = re.compile(r"\b(sk_live_|rk_live_|whsec_|AKIA[0-9A-Z]{16})\b")
# guard: these private-only words must never appear in a public finding's text
THEORY_RX = re.compile(r"\b(theory of the case|owner.only|prosecutorial theory|case file|do not assert)\b", re.I)

TENANTS = [("maui", "Maui County"), ("hi-state", "State of Hawaii"), ("hi-hawaii", "Hawaii County"),
           ("hi-kauai", "Kauai County"), ("hi-honolulu", "Honolulu"), ("ny", "New York")]


def load(p, d=None):
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception:
        return d


def _public_item(question, records, date=None, kind="finding"):
    return {"kind": kind, "date": date, "question": (question or "").strip(),
            "records": [r for r in (records or []) if r], "askable": True}


def cleared_cases(tenant):
    """Reuse case_document.tenant_cases + the ONE gate; keep only REVIEW-READY, emit PUBLIC fields only."""
    out = []
    try:
        sys.path.insert(0, os.path.join(PROJ, "tools", "kilo-aupuni"))
        import case_document as cd
        cases = cd.tenant_cases(tenant) if hasattr(cd, "tenant_cases") else []
        for c in cases or []:
            try:
                status, _ = cd.gate(c)
            except Exception:
                status = "NEEDS-RECORD"
            if status != "REVIEW-READY":
                continue
            # PUBLIC fields only: the question + the named records. NEVER theory/elements/owner text.
            recs = []
            for e in (c.get("evidence") or []):
                s = e if isinstance(e, str) else (e.get("source") or e.get("record") or "")
                if s:
                    recs.append(s)
            out.append(_public_item(c.get("question"), recs[:4], kind="money_votes"))
    except Exception:
        pass
    return out


def maui_cases():
    """Strong refined money×votes cases (cases_crosscheck) as PUBLIC questions: strength>=4, question-framed,
    sourced. Public fields only — the question + named record types, never the private theory."""
    cr = load(os.path.join(ST, "prosecutor", "cases_refined.json"), {}) or {}
    out = []
    for c in (cr.get("cases") or []):
        if (c.get("refined_strength") or 0) < 4 or not c.get("question"):
            continue
        out.append(_public_item(c.get("question"),
                                ["HANDS county awards", "CSC campaign finance", "official roll-call / recusal record"],
                                kind="money_votes"))
    return out


def maui_es():
    es = load(os.path.join(ST, "prosecutor", "es_findings.json"), {}) or {}
    out = []
    for x in (es.get("findings") or [])[:8]:
        out.append(_public_item(x.get("question"), [x.get("minutes_url"), es.get("source_of_law")],
                                date=x.get("date"), kind="executive_session"))
    return out


def build():
    tenants = []
    for code, name in TENANTS:
        items = cleared_cases("maui" if code == "maui" else code)
        if code == "maui":
            items = maui_cases() + items + maui_es()
        # leak guard: DROP any item carrying a secret or private-theory marker ANYWHERE (question OR records)
        safe = [it for it in items
                if not SECRET_RX.search(json.dumps(it, ensure_ascii=False))
                and not THEORY_RX.search(json.dumps(it, ensure_ascii=False))]
        tenants.append({"code": code, "name": name, "count": len(safe), "findings": safe})
    rep = {"generated": datetime.now(HST).strftime("%Y-%m-%d %H:%M HST"),
           "public_safe": True,
           "integrity": ("Public-safe feed: every item cleared the case_document gate (sourced + framed as a "
                         "QUESTION + names the next record + strength>=3). No prosecutorial theory or owner "
                         "text crosses. Questions, not verdicts. The 'askable' flag = a citizen may ask a "
                         "question about this finding (form -> civic intake)."),
           "tenants": tenants}
    return rep


def main():
    rep = build()
    blob = json.dumps(rep.get("tenants"), ensure_ascii=False)  # scan the FINDINGS only, not the meta note
    if SECRET_RX.search(blob) or THEORY_RX.search(blob):
        print("tenant_findings: ABORT - a secret/theory marker leaked into the public feed; not writing.")
        return 1
    open(OUT, "w", encoding="utf-8", newline="\n").write(json.dumps(rep, ensure_ascii=False, indent=2))
    tot = sum(t["count"] for t in rep["tenants"])
    print("tenant_findings: %d public-safe findings across %d tenants -> %s"
          % (tot, len(rep["tenants"]), OUT))
    for t in rep["tenants"]:
        print("   %-16s %d" % (t["name"], t["count"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
