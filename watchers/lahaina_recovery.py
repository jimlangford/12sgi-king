#!/usr/bin/env python3
"""lahaina_recovery.py — pull the Lahaina post-disaster RECOVERY money (public record) into the truth-store
and test it against the money x votes pattern (Jimmy 2026-06-21: "pull up the Lahaina recovery contracts ...
feed post-disaster corruption into money patterns").

Public, sourced (USASpending/federal awards already ingested as federal_money_maui.json + county HANDS).
Stores each recovery award VERBATIM to the truth-store (source=recovery_contracts, primary) and cross-checks
recovery RECIPIENTS against the donor-vendor pattern (vendor_donor_join) — the post-disaster money x votes
QUESTION, allegation-framed, never a verdict. Honest about gaps (the county's spend of the $1.6B HUD
CDBG-DR — the subawards/subrecipients — is the local-risk layer and is NOT yet ingested = NEEDS-RECORD).
Stdlib only.
"""
import os, sys, json
from datetime import datetime, timezone, timedelta

HST = timezone(timedelta(hours=-10))
HOME = os.path.expanduser("~")
PROJ = os.path.join(HOME, "Documents", "Claude", "Projects", "Video System elementLOTUS")
M = os.path.join(PROJ, "reports", "mauios")
OUT = os.path.join(PROJ, "reports", "_status", "prosecutor", "lahaina_recovery.json")
sys.path.insert(0, os.path.join(PROJ, "tools", "kilo-aupuni"))
import record_store
KW = ("lahaina", "wildfire", "fire", "recovery", "debris", "disaster", "rebuild", "displaced", "emergency", "cdbg")
usd = lambda n: "${:,.0f}".format(n or 0)


def load(p, d=None):
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception:
        return d


def fnum(x):
    try:
        return float(x or 0)
    except Exception:
        return 0.0


def main():
    fm = load(os.path.join(M, "federal_money_maui.json"), {}) or {}
    rows = fm.get("awards") or fm.get("rows") or (fm if isinstance(fm, list) else [])
    rec = [r for r in rows if isinstance(r, dict) and any(kw in json.dumps(r).lower() for kw in KW)]
    rec.sort(key=lambda r: -fnum(r.get("amount")))

    # store each recovery award verbatim to the truth-store (sourced public record)
    stored = 0
    for r in rec:
        rid = str(r.get("id") or r.get("award_id") or ("rec_%d" % stored))
        record_store.put(source="recovery_contracts", tenant="hi-maui", doc_id="maui_rec_%s" % rid,
                         text=json.dumps(r, ensure_ascii=False, indent=2),
                         url=r.get("url") or "https://www.usaspending.gov/", tier="primary",
                         doc_type="federal_award", title="%s %s" % (usd(fnum(r.get("amount"))), r.get("recipient")),
                         fetch_tool="lahaina_recovery")
        stored += 1

    # cross-check recovery RECIPIENTS vs the donor-vendor pattern (money x votes)
    vdj = load(os.path.join(M, "vendor_donor_join.json"), {}) or {}
    pairs = vdj.get("matched") or vdj.get("matches") or vdj.get("pairs") or []
    donor_vendors = set()
    if isinstance(pairs, list):
        for p in pairs:
            if isinstance(p, dict):
                donor_vendors.add((p.get("vendor") or "").upper())
    overlaps = []
    for r in rec:
        recip = (r.get("recipient") or "").upper()
        for dv in donor_vendors:
            if dv and (dv in recip or recip in dv):
                overlaps.append({"recipient": r.get("recipient"), "amount": fnum(r.get("amount")),
                                 "donor_vendor_match": dv})

    top = [{"recipient": r.get("recipient"), "amount": fnum(r.get("amount")),
            "agency": r.get("sub_agency") or r.get("agency"), "id": r.get("id")} for r in rec[:15]]
    total = sum(fnum(r.get("amount")) for r in rec)

    rep = {
        "generated": datetime.now(HST).strftime("%Y-%m-%d %H:%M HST"),
        "source": "USASpending federal awards (federal_money_maui) — public record",
        "integrity": ("Public record only; allegation-framed questions, never verdicts. The federal PRIMES "
                      "(ECC, Hui Huliau, FEMA-to-state) are mostly out-of-state contractors — the LOCAL money x "
                      "votes risk lives in how the COUNTY spends its $1.6B HUD CDBG-DR (subawards), which is "
                      "NOT yet ingested."),
        "recovery_awards_found": len(rec), "stored_to_truth_store": stored,
        "total_recovery_dollars": total, "top_awards": top,
        "donor_vendor_overlaps": overlaps,
        "NEEDS_RECORD": ("The COUNTY's recovery spend — HUD CDBG-DR subrecipients/subawards + county "
                         "debris/rebuild procurement (hands_maui_awards is empty in our data) — is the "
                         "high-risk local layer. NEXT PULL (lawful, public): the County CDBG-DR Action Plan + "
                         "subrecipient list, and county procurement awards. That is where post-disaster money x "
                         "votes would show, if anywhere."),
        "post_disaster_question": ("Of the recovery money the COUNTY controls, do any awards/subawards go to "
                                   "vendors who donated to the deciding members (the case_money_bridge "
                                   "officials)? Answer requires the county subaward record."),
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    open(OUT, "w", encoding="utf-8", newline="\n").write(json.dumps(rep, ensure_ascii=False, indent=2))
    print("lahaina_recovery: %d recovery awards (%s) stored=%d | donor-vendor overlaps=%d -> %s"
          % (len(rec), usd(total), stored, len(overlaps), OUT))
    for t in top[:8]:
        print("   %s  %s  (%s)" % (usd(t["amount"]), str(t["recipient"])[:40], str(t["agency"])[:32]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
