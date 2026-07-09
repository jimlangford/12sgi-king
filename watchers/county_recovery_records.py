#!/usr/bin/env python3
"""county_recovery_records.py — pull the COUNTY layer of Lahaina recovery money into the truth-store
(Jimmy 2026-06-21: "pull the county CDBG-DR subaward record ... the local money x votes layer").

Two public, sourced layers:
  1. The County's $1.64B HUD CDBG-DR Action Plan PROGRAM ALLOCATIONS (mauicounty.gov Office of Recovery)
     — these are PUBLISHED (how the County divides the grant by program).
  2. The County PROCUREMENT awards (mauicounty.gov Current Awards) — actual contracts to actual VENDORS.

The procurement vendors are the first county-level money x votes test: cross-check each awarded vendor
against the donor-vendor pattern (vendor_donor_join). Allegation-framed, never a verdict.

HONEST GAP (the real high-risk layer): the program allocations are published, but the SUBRECIPIENT
awards under them — who actually receives the $903M Housing / $400M Infrastructure money — are NOT yet
published as a list. That remains NEEDS-RECORD (the precise next UIPA / DRGR pull). Stdlib only.

Sources (verified public, 2026-06-21):
  - https://hookumuhou.mauicounty.gov/190/Action-PlanProgram-Allocations
  - https://www.mauirecovers.org/cdbgdr
  - https://www.mauicounty.gov/1766/Current-Awards
"""
import os, sys, json
from datetime import datetime, timezone, timedelta

HST = timezone(timedelta(hours=-10))
HOME = os.path.expanduser("~")
PROJ = os.path.join(HOME, "Documents", "Claude", "Projects", "Video System elementLOTUS")
M = os.path.join(PROJ, "reports", "mauios")
OUT = os.path.join(PROJ, "reports", "_status", "prosecutor", "county_recovery_records.json")
sys.path.insert(0, os.path.join(PROJ, "tools", "kilo-aupuni"))
import record_store
usd = lambda n: "${:,.0f}".format(n or 0)

ALLOC_URL = "https://hookumuhou.mauicounty.gov/190/Action-PlanProgram-Allocations"
AWARDS_URL = "https://www.mauicounty.gov/1766/Current-Awards"

# LAYER 1 — published CDBG-DR program allocations (the $1.64B divided by program), verbatim from the
# County Office of Recovery allocations page (updated 2026-04-27, Substantial Amendment 1; approved
# by HUD 2026-04-27; original Action Plan approved by HUD 2025-06-04).
CDBGDR_ALLOC = {
    "grantee": "County of Maui (Office of Recovery / Hookumu Hou)",
    "total_allocation": 1639381000,
    "action_plan": "approved by HUD 2025-06-04; Substantial Amendment 1 approved by HUD 2026-04-27",
    "as_of": "2026-04-27",
    "programs": [
        {"program": "Housing", "allocation": 903579950},
        {"program": "Infrastructure", "allocation": 400000000},
        {"program": "CDBG-DR Mitigation Set-Aside", "allocation": 213832000},
        {"program": "Administration", "allocation": 76529050},
        {"program": "Public Services", "allocation": 25000000},
        {"program": "Economic Revitalization", "allocation": 15000000},
        {"program": "Planning", "allocation": 5440000},
    ],
    "named_subrecipients": [],   # NONE published per-program — this is the gap
}

# LAYER 2 — county procurement awards (Current Awards page), verbatim, Lahaina/recovery-related.
COUNTY_AWARDS = [
    {"title": "Lahaina Recreation Center Improvements", "bid": "Job No. P23/007", "contract": "C8823",
     "vendor": "Blazy Construction Inc.", "amount": 2448050.00, "dept": "Parks and Recreation", "date": "2026-06-09"},
    {"title": "Lahaina Community Center and Field House", "bid": "Job No. P25-004, Q-PK-26-2", "contract": "C8718",
     "vendor": "Group 70 International, Inc.", "amount": 1250000.00, "dept": "Parks and Recreation", "date": "2026-01-13"},
    {"title": "Lahaina Aquatic Center Rehabilitation", "bid": "Job No. P25/005, Q-PK-26-3", "contract": "C8720",
     "vendor": "Mitsunaga and Associates, Inc.", "amount": 541088.00, "dept": "Parks and Recreation", "date": "2026-01-13"},
    {"title": "Lahaina Fire Station Re-Roof", "bid": "QBS No. Q-FR-26-02", "contract": "C8798",
     "vendor": "Allana, Buick, and Bers, Inc.", "amount": 210180.00, "dept": "Fire and Public Safety", "date": "2026-05-19"},
    {"title": "Lahaina Historic District Security", "bid": "RFP No. 25-26/P-105", "contract": "C8781",
     "vendor": "Aegaeon LLC", "amount": 138455.44, "dept": "Management", "date": "2026-03-12"},
    {"title": "Disaster Recovery Management Services (Mar 2026 Kona Low Storm)", "bid": "RFP No. 25-26/P-142",
     "contract": "C8842", "vendor": "Tetra Tech, Inc.", "amount": 3571838.00, "dept": "Management", "date": "2026-06-01"},
]


def load(p, d=None):
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception:
        return d


def main():
    # store layer 1 — the program allocations (one sourced record)
    record_store.put(source="county_cdbgdr", tenant="hi-maui", doc_id="maui_cdbgdr_action_plan_alloc",
                     text=json.dumps(CDBGDR_ALLOC, ensure_ascii=False, indent=2), url=ALLOC_URL,
                     tier="primary", doc_type="cdbgdr_allocation",
                     title="County of Maui CDBG-DR Action Plan program allocations (%s)" % usd(CDBGDR_ALLOC["total_allocation"]),
                     fetch_tool="county_recovery_records")

    # store layer 2 — each county procurement award (sourced records)
    stored = 1
    for a in COUNTY_AWARDS:
        record_store.put(source="county_procurement", tenant="hi-maui",
                         doc_id="maui_award_%s" % a["contract"],
                         text=json.dumps(a, ensure_ascii=False, indent=2), url=AWARDS_URL,
                         tier="primary", doc_type="county_contract_award",
                         title="%s %s (%s)" % (usd(a["amount"]), a["vendor"], a["title"]),
                         fetch_tool="county_recovery_records")
        stored += 1

    # county-level money x votes test: do these awarded vendors appear in the donor-vendor pattern?
    vdj = load(os.path.join(M, "vendor_donor_join.json"), {}) or {}
    pairs = vdj.get("matched") or vdj.get("matches") or vdj.get("pairs") or []
    donor_vendors = set()
    if isinstance(pairs, list):
        for p in pairs:
            if isinstance(p, dict):
                v = (p.get("vendor") or "").upper().strip()
                if v:
                    donor_vendors.add(v)
    STOP = {"INC", "LLC", "LTD", "CORP", "CO", "COMPANY", "THE", "AND", "ASSOCIATES", "INTERNATIONAL",
            "CONSTRUCTION", "SERVICES", "GROUP", "MAUI", "HAWAII"}
    def toks(name):
        return {t for t in (name or "").upper().replace(",", " ").replace(".", " ").split() if t and t not in STOP and len(t) > 2}
    overlaps = []
    for a in COUNTY_AWARDS:
        at = toks(a["vendor"])
        for dv in donor_vendors:
            if at and at & toks(dv):
                overlaps.append({"award": a["title"], "vendor": a["vendor"], "amount": a["amount"],
                                 "donor_vendor_match": dv})

    alloc_total = sum(p["allocation"] for p in CDBGDR_ALLOC["programs"])
    awards_total = sum(a["amount"] for a in COUNTY_AWARDS)
    rep = {
        "generated": datetime.now(HST).strftime("%Y-%m-%d %H:%M HST"),
        "sources": [ALLOC_URL, AWARDS_URL, "https://www.mauirecovers.org/cdbgdr"],
        "integrity": ("Public record only; allegation-framed questions, never verdicts. Program ALLOCATIONS "
                      "are published; the per-program SUBRECIPIENT awards (who receives the money) are NOT — "
                      "that remains the precise NEEDS-RECORD."),
        "layer1_cdbgdr_allocation": {"total": CDBGDR_ALLOC["total_allocation"], "by_program_sum": alloc_total,
                                     "programs": CDBGDR_ALLOC["programs"],
                                     "action_plan": CDBGDR_ALLOC["action_plan"]},
        "layer2_county_awards": {"count": len(COUNTY_AWARDS), "total": awards_total, "awards": COUNTY_AWARDS},
        "money_x_votes_overlaps": overlaps,
        "records_stored": stored,
        "NEEDS_RECORD": ("The published Action Plan divides $1.64B into 7 programs but names NO subrecipients. "
                         "The high-risk layer is the per-program SUBRECIPIENT/subaward list — esp. Housing "
                         "($903.6M) and Infrastructure ($400M). LAWFUL NEXT PULL: (a) HUD DRGR public quarterly "
                         "performance reports for the County of Maui grant (subrecipient activity), (b) the "
                         "County's published subrecipient agreements / NOFAs, (c) UIPA request for the executed "
                         "CDBG-DR subrecipient award list. Then re-run case_money_bridge on the subrecipients."),
        "post_disaster_question": ("Of the county recovery money already AWARDED to vendors, do any go to "
                                   "vendors who donated to the deciding council members (the case_money_bridge "
                                   "officials)? Current procurement-vendor overlap with the donor pattern = %d. "
                                   "The larger test waits on the CDBG-DR subrecipient list." % len(overlaps)),
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    open(OUT, "w", encoding="utf-8", newline="\n").write(json.dumps(rep, ensure_ascii=False, indent=2))
    print("county_recovery_records: alloc total %s (7 programs) | %d county awards %s | vendor-donor overlaps=%d | stored=%d -> %s"
          % (usd(CDBGDR_ALLOC["total_allocation"]), len(COUNTY_AWARDS), usd(awards_total), len(overlaps), stored, OUT))
    for p in CDBGDR_ALLOC["programs"]:
        print("   ALLOC  %s  %s" % (usd(p["allocation"]), p["program"]))
    for a in COUNTY_AWARDS:
        print("   AWARD  %s  %s  (%s)" % (usd(a["amount"]), a["vendor"][:34], a["title"][:34]))
    if overlaps:
        for o in overlaps:
            print("   ** OVERLAP  %s ~ donor-vendor %s (%s)" % (o["vendor"], o["donor_vendor_match"], usd(o["amount"])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
