#!/usr/bin/env python3
"""synthetic_test_case_builder.py — build an UNMISTAKABLY FICTIONAL practice case to validate the
public legal-intake pipeline (document upload -> template match -> drafting aid -> human review)
WITHOUT ever touching a real person's real case.

Chartered by Jimmy 2026-07-01 (item 4 of the public-defender/legal-intake proposal): "make it almost
obvious :)" — the fake case must be so clearly a joke that no one could ever mistake it for a real
filing or a real person's legal matter.

Mirrors the SHAPE of tools/kilo-aupuni/langford_case_builder.py (PROVABLE CORE / SET-ASIDE / MONEY
BRIDGE / RECORDS NEEDED / GATE) so the same intake pipeline that will serve real citizens gets a full
end-to-end test run — but every name, case number, and fact below is invented for testing only.

Output goes to reports/_status/synthetic_test_case/ — a completely separate folder from
reports/_status/langford_legal/ (the real, private case) to prevent any mixing or confusion.

NOT legal advice. NOT a real case. Stdlib only.
"""
import os
from datetime import datetime, timezone, timedelta

HST = timezone(timedelta(hours=-10))
HOME = os.path.expanduser("~")
PROJ = os.path.join(HOME, "Documents", "Claude", "Projects", "Video System elementLOTUS")
OUTDIR = os.path.join(PROJ, "reports", "_status", "synthetic_test_case")
CASE_MD = os.path.join(OUTDIR, "SYNTHETIC_TEST_CASE.md")

BANNER = (
    "############################################################\n"
    "###  SYNTHETIC TEST CASE — 100% FICTIONAL — NOT REAL  #####\n"
    "###  Every name, date, and case number below is MADE UP ###\n"
    "###  for testing the legal-intake pipeline. No real     ###\n"
    "###  person, court, or filing is involved.               ###\n"
    "############################################################"
)

# The PROVABLE CORE — same shape as a real case file, entirely invented facts.
PROVABLE_CORE = [
    {
        "claim": "[FICTIONAL] Emergency Restraining Order Against a Garden Gnome (Case No. 9ZZ-99-0000042-GNOME)",
        "owner_basis": "Test-Citizen 'Barnaby Q. Flapjack' alleges his neighbor's ceramic garden gnome, 'Sir Reginald Pointyhat,' has been staring into his kitchen window in a manner he finds 'aggressively judgmental.'",
        "proves_it": "Fictional eCourt Kokua docket (test data): #1 EX PARTE PETITION FOR TRO AGAINST A LAWN ORNAMENT; #2 MINUTES: 'GNOME PRESENT (STATIONARY). RESPONDENT'S OWNER NOT PRESENT.' Status: TERMINATED (gnome relocated to shed).",
        "needs": "Test only: whether a gnome can be legally served, and whether 'judgmental staring' meets the harassment standard for inanimate garden decor.",
        "forum": "Test forum: Small Claims, Division of Whimsy (fictional).",
        "strength_if_sourced": "TEST VALUE ONLY — validates the TRO/injunction template branch of the intake pipeline.",
    },
    {
        "claim": "[FICTIONAL] Summary Possession — 'Aloha Snack Shack Holdings LLC' vs. Barnaby Q. Flapjack over a food-truck parking spot",
        "owner_basis": "Test-Citizen alleges his beloved malasada cart was displaced from its favorite parking spot by a rival snack empire with 'suspiciously good donut-hole connections at the county level.'",
        "proves_it": "Fictional docket 9ZZ-99-0001138-DONUT: 'Complaint (ASSUMPSIT - SUMMARY POSSESSION / Food-Truck-Landlord, Damages: 400 malasadas).' Plaintiff atty: Test Attorney 'Percy Butterscotch.'",
        "needs": "Test only: pre-eviction parking-spot occupancy history and whether the rival cart's donut supremacy constitutes undue influence.",
        "forum": "Test forum: Civil — wrongful food-truck displacement (fictional cause of action).",
        "strength_if_sourced": "TEST VALUE ONLY — validates the eviction/summary-possession template branch, including the 'under color of law' money-bridge test with an obviously fictional entity.",
    },
    {
        "claim": "[FICTIONAL] Disaster-benefit timing question — the Great Sprinkler Incident",
        "owner_basis": "Test-Citizen's neighbor turned off a lawn sprinkler suspiciously close to a declared 'Backyard BBQ State of Emergency,' then filed for a FEMA-style 'Charcoal Assistance' grant.",
        "proves_it": "Fictional timing record only; no real disaster-benefit program is referenced.",
        "needs": "Test only: timing cross-reference logic for the disaster-benefit template branch.",
        "forum": "Test forum: Referral to the fictional 'Bureau of Backyard Grilling Standards.'",
        "strength_if_sourced": "TEST VALUE ONLY — validates the referral (not-a-private-claim) branch of the drafting aid.",
    },
    {
        "claim": "[FICTIONAL] Business-license denial — the Lemonade Stand Incident",
        "owner_basis": "Test-Citizen's lemonade stand permit was denied for 'excessive deliciousness,' allegedly at the request of a rival juice conglomerate.",
        "proves_it": "Fictional 'Liquor & Lemonade Commission' denial record (test data only).",
        "needs": "Test only: administrative-appeal template logic.",
        "forum": "Test forum: Administrative appeal, Division of Beverages.",
        "strength_if_sourced": "TEST VALUE ONLY — validates the license-denial template branch.",
    },
]

# The SET-ASIDE — same honest-counsel shape, fictional over-the-top claims to test the guardrail.
SET_ASIDE = [
    {"item": "[FICTIONAL] Demand that the court declare Barnaby Q. Flapjack 'Emperor of All Snack Carts'",
     "why": "TEST ONLY — validates that the pipeline correctly flags non-justiciable / no-court-can-grant-this requests and routes them to SET-ASIDE instead of drafting a real motion for them."},
    {"item": "[FICTIONAL] Naming 'the entire concept of Tuesdays' as a co-defendant",
     "why": "TEST ONLY — validates the pipeline rejects nonsensical/unjoinable parties rather than drafting a filing that would embarrass the citizen."},
]

GATE_TEXT = (
    "## Gate\n"
    "This is a SYNTHETIC TEST CASE. Nothing above describes a real person, a real court filing, or a "
    "real legal dispute. It exists only to exercise the intake -> template-match -> drafting-aid -> "
    "human-review pipeline end to end before any real citizen's data touches it. No outcome is promised "
    "because there is no real outcome to promise — there is no real case."
)


def main():
    os.makedirs(OUTDIR, exist_ok=True)
    lines = [BANNER, ""]
    lines.append("# SYNTHETIC TEST CASE FILE (fictional — pipeline validation only)")
    lines.append("")
    lines.append(
        "_Generated %s by synthetic_test_case_builder. Every fact below is invented. This is NOT the "
        "real Langford case file — that stays in reports/_status/langford_legal/, private, untouched._"
        % datetime.now(HST).strftime("%Y-%m-%d %H:%M HST")
    )
    lines.append("")
    lines.append("## 1. PROVABLE CORE (test data — validates the drafting-aid template branches)")
    lines.append("")
    for i, c in enumerate(PROVABLE_CORE, 1):
        lines.append("### %d. %s" % (i, c["claim"]))
        lines.append("- **Test basis:** %s" % c["owner_basis"])
        lines.append("- **Test 'proof':** %s" % c["proves_it"])
        lines.append("- **Test gap:** %s" % c["needs"])
        lines.append("- **Test forum:** %s" % c["forum"])
        lines.append("- **Test-strength note:** %s" % c["strength_if_sourced"])
        lines.append("")
    lines.append("## 2. SET ASIDE (test data — validates the non-justiciable-request guardrail)")
    lines.append("")
    for s in SET_ASIDE:
        lines.append("- **%s** — %s" % (s["item"], s["why"]))
    lines.append("")
    lines.append("## 3. MONEY BRIDGE (test data — validates the money x votes template test)")
    lines.append("")
    lines.append(
        "The donut-empire / county-connections thread (fictional) exists purely to validate that the "
        "pipeline can trace a test 'entity + public-money' pattern without any real entity being named."
    )
    lines.append("")
    lines.append("## 4. RECORDS NEEDED (test data — validates the pull-list generator)")
    lines.append("")
    for c in PROVABLE_CORE:
        lines.append("- [ ] [FICTIONAL] %s — blocker: %s" % (c["claim"], c["needs"]))
    lines.append("")
    lines.append(GATE_TEXT)
    lines.append("")
    lines.append(BANNER)

    with open(CASE_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print("Synthetic test case written: %s" % CASE_MD)
    print("Claims: %d fictional | Set-aside: %d fictional" % (len(PROVABLE_CORE), len(SET_ASIDE)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
