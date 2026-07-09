#!/usr/bin/env python3
"""case_template_engine.py — the GENERIC drafting-aid engine behind the legal-intake pipeline.

Chartered by Jimmy 2026-07-01 (item 2 of the public-defender/legal-intake proposal, decided per the
JRCSL decide-gate: ALIGNED + reversible + not owner-gated -> proceed without re-asking). Extracted from
tools/kilo-aupuni/langford_case_builder.py so ONE engine produces the PROVABLE CORE / SET-ASIDE / MONEY
BRIDGE / RECORDS NEEDED / GATE structure for ANY case — proven first on James's own real case (per his
explicit sequencing: "perfect it with mine" before it ever serves anyone else), then reusable as-is for
the synthetic test case and, later, for real citizen intake once that public surface is built.

This module NEVER decides what a case IS — callers supply the claims. It only renders the disciplined
structure and the standing disclaimers. NOT legal advice. NOT a lawyer. No outcome promised. Stdlib only.
"""
import json
from datetime import datetime, timezone, timedelta

HST = timezone(timedelta(hours=-10))

DISCLAIMER = (
    "NOT legal advice; no outcome promised; the author is not your attorney. This organizes the "
    "ingested record into a winnable, sourced structure and names the records that prove each claim. "
    "A human — you, or a licensed attorney/public defender — makes every real judgment call; this "
    "engine only prepares the packet."
)

PRINCIPLE = (
    "## The principle: a case that can't lose is NARROW + SOURCED\n"
    "Every count is tied to ONE primary record and ONE forum, framed as an allegation the record "
    "proves. Anything that can't be sourced, or that no court can grant, is set aside from the legal "
    "vehicle (it lives in the private record and the civic/creative work)."
)

GATE_TEXT = (
    "## Gate\n"
    "Nothing above is asserted as proven. Each claim is an allegation the named record will confirm or "
    "refute. Promotion to a finding requires the primary record attached (verify-gate). No outcome is "
    "promised."
)


def render_case_file(case_label, title, provable_core, set_aside, money_bridge_lines,
                      records_needed_extra=None, priority_1_note=None, source_status_line=None,
                      synthetic_banner=None):
    """Render the disciplined case-file structure for ANY case.

    case_label: short id used in the generated-by line (e.g. "langford_case_builder", "synthetic_test_case_builder")
    title: the H1 heading (e.g. "LANGFORD CASE FILE — STRUCTURED (PRIVATE / owner-only)")
    provable_core: list of dicts with keys claim/owner_basis/proves_it/needs/forum/strength_if_sourced
    set_aside: list of dicts with keys item/why
    money_bridge_lines: list of markdown lines for the MONEY BRIDGE section
    records_needed_extra: optional list of extra record-pull lines (strings) beyond provable_core
    priority_1_note: optional string for the top-of-records-needed priority callout
    source_status_line: optional string describing what source docs are present on disk
    synthetic_banner: optional string printed above/below the whole doc (fictional-case marker)

    Returns (markdown_text, records_needed_json_dict).
    """
    records_needed = [
        {"for_claim": c["claim"], "record": c["proves_it"], "blocker": c["needs"]}
        for c in provable_core
    ]

    lines = []
    if synthetic_banner:
        lines.append(synthetic_banner)
        lines.append("")
    lines.append("# %s" % title)
    lines.append("")
    lines.append(
        "_Generated %s by %s. %s_"
        % (datetime.now(HST).strftime("%Y-%m-%d %H:%M HST"), case_label, DISCLAIMER)
    )
    lines.append("")
    if source_status_line:
        lines.append(source_status_line)
        lines.append("")
    lines.append(PRINCIPLE)
    lines.append("")
    lines.append("## 1. PROVABLE CORE (build the case on these)")
    for i, c in enumerate(provable_core, 1):
        lines.append("")
        lines.append("### %d. %s" % (i, c["claim"]))
        lines.append("- **Basis (record):** %s" % c["owner_basis"])
        lines.append("- **What proves it (primary record):** %s" % c["proves_it"])
        lines.append("- **Still needed:** %s" % c["needs"])
        lines.append("- **Forum:** %s" % c["forum"])
        lines.append("- **Strength if sourced:** %s" % c["strength_if_sourced"])
    lines.append("")
    lines.append("## 2. SET ASIDE from the legal vehicle (honest counsel — keep these OUT of a filing meant to win)")
    for s in set_aside:
        lines.append("- **%s** — %s" % (s["item"], s["why"]))
    lines.append("")
    lines.append("## 3. MONEY BRIDGE")
    for ml in money_bridge_lines:
        lines.append("- %s" % ml)
    lines.append("")
    lines.append("## 4. RECORDS NEEDED (the lawful pull-list — turns ALLEGED into VERIFIED)")
    if priority_1_note:
        lines.append(priority_1_note)
        lines.append("")
    for r in records_needed:
        lines.append("- [ ] **%s** — %s _(blocker: %s)_" % (r["for_claim"], r["record"], r["blocker"]))
    for extra in (records_needed_extra or []):
        lines.append("- [ ] %s" % extra)
    lines.append("")
    lines.append(GATE_TEXT)
    lines.append("")
    if synthetic_banner:
        lines.append(synthetic_banner)

    md_text = "\n".join(lines) + "\n"
    json_payload = {
        "generated": datetime.now(HST).strftime("%Y-%m-%d %H:%M HST"),
        "provable_core": provable_core,
        "set_aside": set_aside,
        "records_needed": records_needed,
        "priority_1_blocker": priority_1_note,
    }
    return md_text, json_payload


def write_case_file(md_path, json_path, md_text, json_payload):
    with open(md_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(md_text)
    if json_path:
        with open(json_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(json_payload, ensure_ascii=False, indent=2))
