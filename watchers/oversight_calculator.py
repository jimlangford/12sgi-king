#!/usr/bin/env python3
"""oversight_calculator.py — the PREMIUM council-oversight calculator (Jimmy 2026-06-18).

The top tier above the public board: a private AI calculator for a Council member (acting as a private
citizen, see docs/COUNCIL_AUDIT_LEGALITY.md) to see how the EXECUTIVE BRANCH is using funds from the
freshest SOURCED public records, and to PREPARE the documents they take to Corporation Counsel — sourced
questions for the lawful oversight channel, never accusations. It computes:
  • award totals + VENDOR CONCENTRATION (is spending pooling in a few hands?),
  • the CONTRACTS × DONORS overlap (county pays X; X gave to deciders — a question, sourced public records),
  • money BY OFFICE + federal dollars,
and prepares: an executive-funds REPORT, a CORPORATION COUNSEL INQUIRY packet, and a UIPA RECORDS-REQUEST list.

INTEGRITY (non-negotiable): every figure traces to a public filing; every finding is framed as a QUESTION
to be resolved through Corporation Counsel / the Board of Ethics — never a verdict. Honest about data
freshness (it reports each source's "as of" date; "real time" = the freshest sourced data we hold).
PRIVATE / owner+council-side — never published. Stdlib only.

API:
  report(tenant)          -> dict (the computed oversight analysis + sourced questions)
  inquiry_packet(tenant)  -> str  (a Corporation Counsel inquiry document, markdown)
  records_request(tenant) -> str  (the UIPA records-request list)
CLI: python oversight_calculator.py --tenant hi-maui [--packet] [--records]
"""
import os, sys, json
HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(os.path.dirname(HERE))
M = os.path.join(PROJ, "reports", "mauios")


def _load(name):
    try:
        return json.load(open(os.path.join(M, name), encoding="utf-8"))
    except Exception:
        return {}


def _usd(n):
    try:
        return "${:,.0f}".format(float(n or 0))
    except Exception:
        return str(n)


def _num(s):
    """Best-effort parse of a dollar value that may be '$480,000' or 480000."""
    if isinstance(s, (int, float)):
        return float(s)
    try:
        return float(str(s).replace("$", "").replace(",", "").strip() or 0)
    except Exception:
        return 0.0


def report(tenant="hi-maui"):
    awards = _load("hands_maui_awards.json")
    join = _load("vendor_donor_join.json")
    money = _load("statewide_money.json")
    federal = _load("federal_money_maui.json")

    out = {"tenant": tenant, "title": "Executive-branch funds — oversight calculator",
           "sources": [], "freshness": {}, "metrics": {}, "questions": [],
           "integrity": "Every figure traces to a public filing. Every item is a QUESTION for Corporation "
                        "Counsel / the Board of Ethics to resolve — not a finding of wrongdoing."}

    # freshness (honest "as of" per source — this is what "real time" means: the freshest sourced data)
    for label, d, key in [("contract awards (HANDS)", awards, "generated"),
                          ("contracts × donors join", join, "generated"),
                          ("campaign money (CSC)", money, "asOf")]:
        if d:
            out["sources"].append(label)
            out["freshness"][label] = d.get(key) or d.get("generated") or "unknown"

    # 1) award totals + vendor concentration
    vendors = awards.get("vendors") or []
    total = _num(awards.get("maui_dollars"))
    ranked = sorted(
        [{"vendor": (v.get("vendor") or v.get("name") or "?"), "amount": _num(v.get("dollars") or v.get("amount") or v.get("total"))}
         for v in vendors if isinstance(v, dict)],
        key=lambda x: -x["amount"])
    top5 = sum(v["amount"] for v in ranked[:5])
    out["metrics"]["awards"] = {
        "as_of": out["freshness"].get("contract awards (HANDS)"),
        "total_dollars": total, "total_display": _usd(total),
        "vendor_count": awards.get("maui_vendors") or len(ranked),
        "top5": [{"vendor": v["vendor"], "amount": _usd(v["amount"])} for v in ranked[:5]],
        "top5_share_pct": round(100.0 * top5 / total, 1) if total else None}
    if total and top5 / total >= 0.5 and ranked:
        out["questions"].append(
            "Concentration: the top 5 vendors hold %.0f%% of tracked Maui awards (%s of %s). What "
            "competitive process produced this distribution, and were sole-source justifications filed?"
            % (100.0 * top5 / total, _usd(top5), _usd(total)))

    # 2) contracts × donors overlap (a question, sourced public records on BOTH sides)
    matched = join.get("matched") or []
    out["metrics"]["contracts_x_donors"] = {
        "as_of": out["freshness"].get("contracts × donors join"),
        "vendors_scanned": join.get("maui_vendors_scanned"),
        "matches": join.get("matches") or len(matched),
        "examples": [{"name": (m.get("vendor") or m.get("name") or "?"),
                      "award": _usd(_num(m.get("award") or m.get("dollars"))),
                      "giving": _usd(_num(m.get("donated") or m.get("giving") or m.get("contributions")))}
                     for m in matched[:8] if isinstance(m, dict)]}
    if (join.get("matches") or len(matched)):
        out["questions"].append(
            "Overlap: %d county vendor(s) also appear in the campaign-finance record of officials who vote "
            "on county matters. For each, is there a recusal on point, and does the timeline of giving vs. "
            "award raise a question Corporation Counsel should review?" % (join.get("matches") or len(matched)))

    # 3) money by office (where giving concentrates)
    by_office = money.get("by_office") or {}
    if isinstance(by_office, dict) and by_office:
        ob = sorted(((k, _num(v if not isinstance(v, dict) else v.get("total"))) for k, v in by_office.items()),
                    key=lambda x: -x[1])[:6]
        out["metrics"]["money_by_office"] = [{"office": k, "total": _usd(a)} for k, a in ob]

    # 4) federal dollars (context)
    if federal:
        ft = _num(federal.get("total") or federal.get("maui_total") or federal.get("grand_total"))
        if ft:
            out["metrics"]["federal_dollars"] = {"total": _usd(ft),
                                                 "note": "Federal funds landing in the county (USAspending) — public, for cross-reference."}

    if not out["questions"]:
        out["questions"].append("No concentration or overlap thresholds were tripped in the current data — "
                                "a clean snapshot is itself a useful oversight record. Re-run as data refreshes.")
    return out


def inquiry_packet(tenant="hi-maui"):
    r = report(tenant)
    L = []
    L.append("# Oversight inquiry — executive-branch fund usage")
    L.append("**To:** Department of the Corporation Counsel, County of Maui")
    L.append("**From:** [Council Member name], in the Council's oversight capacity")
    L.append("**Re:** Questions arising from analysis of public fund-usage records\n")
    L.append("> Prepared from PUBLIC records only. These are QUESTIONS for your review, not allegations. "
             "Sources and \"as of\" dates are listed so each item can be independently verified.\n")
    L.append("## Data reviewed")
    for s in r["sources"]:
        L.append("- %s — as of %s" % (s, r["freshness"].get(s, "unknown")))
    aw = r["metrics"].get("awards", {})
    if aw:
        L.append("\n## What the records show")
        L.append("- Tracked Maui awards: **%s** across %s vendors." % (aw.get("total_display"), aw.get("vendor_count")))
        if aw.get("top5_share_pct") is not None:
            L.append("- Top 5 vendors hold **%s%%** of tracked awards." % aw["top5_share_pct"])
        for v in aw.get("top5", [])[:5]:
            L.append("    - %s — %s" % (v["vendor"], v["amount"]))
    L.append("\n## Questions for Corporation Counsel")
    for i, q in enumerate(r["questions"], 1):
        L.append("%d. %s" % (i, q))
    L.append("\n## Requested")
    L.append("- Guidance on whether any item warrants referral (Board of Ethics, Auditor, or further review).")
    L.append("- Confirmation of the correct procurement/recusal records to request next.")
    L.append("\n---")
    L.append("_%s_" % r["integrity"])
    L.append("_This inquiry was prepared by a Council member acting in their oversight role from public "
             "records; see the legality + safeguards note (docs/COUNCIL_AUDIT_LEGALITY.md). Informational, "
             "not legal advice._")
    return "\n".join(L)


def records_request(tenant="hi-maui"):
    L = []
    L.append("# UIPA records-request checklist (HRS ch. 92F)")
    L.append("> Public records any citizen may request — to confirm or close each question above.\n")
    for item in [
        "All county contract awards for the current + prior fiscal year (vendor, amount, department, date, procurement method).",
        "Sole-source / exemption justifications filed for any award above the bid threshold.",
        "Department expenditure reports / checkbook-level disbursements for the executive departments named.",
        "Procurement evaluation records (scoring) for the largest awards by dollar value.",
        "Recusal records / disclosures for any official whose campaign record overlaps a vendor.",
        "Current budget vs. actual by department (the executive's fund usage against appropriation).",
    ]:
        L.append("- [ ] " + item)
    L.append("\n_Tip: UIPA requests need no reason and no identification (OIP guidance). Route legal "
             "questions to Corporation Counsel; route ethics questions to the Board of Ethics (an advisory "
             "opinion carries immunity, Charter §10-2(5))._")
    return "\n".join(L)


def main():
    import argparse
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tenant", default="hi-maui")
    ap.add_argument("--packet", action="store_true")
    ap.add_argument("--records", action="store_true")
    a = ap.parse_args()
    if a.packet:
        print(inquiry_packet(a.tenant)); return 0
    if a.records:
        print(records_request(a.tenant)); return 0
    r = report(a.tenant)
    print("OVERSIGHT CALCULATOR — %s" % a.tenant)
    print("  sources:", ", ".join("%s (as of %s)" % (s, r["freshness"].get(s)) for s in r["sources"]) or "none loaded")
    aw = r["metrics"].get("awards", {})
    if aw:
        print("  awards: %s across %s vendors; top-5 share %s%%" % (aw.get("total_display"), aw.get("vendor_count"), aw.get("top5_share_pct")))
    cd = r["metrics"].get("contracts_x_donors", {})
    if cd:
        print("  contracts x donors: %s matches of %s scanned" % (cd.get("matches"), cd.get("vendors_scanned")))
    print("  QUESTIONS (for Corporation Counsel — not verdicts):")
    for q in r["questions"]:
        print("    - " + q)
    return 0


if __name__ == "__main__":
    if sys.platform == "win32":
        import io; sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(main())
