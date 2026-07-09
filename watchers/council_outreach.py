#!/usr/bin/env python3
"""council_outreach.py — DRAFT (never send) the council-member emails offering the Oversight Calculator
(Jimmy 2026-06-18). "Prepare council person emails so we can share the offering."

This STAGES one personalized draft per Maui County Council seat to reports/_status/council_outreach/ for
Jimmy to review and send himself. It does NOT send anything — sending is the owner's action, by design.
Each draft: a warm, factual offer of the premium private Oversight Calculator (see how the executive
branch uses funds from public records + auto-prepare Corporation Counsel inquiries), the legality posture
(private funds + public records + the Board-of-Ethics advisory-opinion safe harbor), and a clear CTA.
Integrity: an OVERSIGHT tool that surfaces sourced QUESTIONS for the lawful channel — never accusations.
Stdlib only.

CLI: python council_outreach.py            # stage all seats
     python council_outreach.py --print Lee  # print one draft to stdout
"""
import os, sys, json
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path: sys.path.insert(0, HERE)
PROJ = os.path.dirname(os.path.dirname(HERE))
from votes_watch import ROSTER
OUT = os.path.join(PROJ, "reports", "_status", "council_outreach")     # PRIVATE drafts; never published


def _offer():
    try:
        return json.load(open(os.path.join(PROJ, "config", "oversight_offering.json"), encoding="utf-8"))
    except Exception:
        return {}


def _price_line(off):
    if off.get("rate_confirmed") and off.get("price_usd"):
        per = "/mo" if off.get("mode") == "subscription" else ""
        return "Introductory price: $%.0f%s." % (float(off["price_usd"]), per)
    return "Pricing is being finalized — reply and I'll share it the moment it's set."


def draft(seat_key, full_label, off):
    name = full_label.split(" - ")[0].strip()
    district = (full_label.split(" - ", 1)[1].strip() if " - " in full_label else "Maui County")
    first = name.split()[0]
    subject = "A private oversight calculator for your office — see how county funds are spent, prepare the questions"
    body = """Aloha %s,

I built a private oversight calculator for Maui County Council members and wanted to share it with you directly.

What it does, from PUBLIC records only:
  • Shows how the executive branch is using funds — contract awards, where spending concentrates by vendor,
    the overlap between county vendors and campaign donors, money by office, and federal dollars — refreshed
    from the freshest sourced data (Campaign Spending Commission, county awards, USAspending).
  • Auto-prepares the documents you'd take to Corporation Counsel: a sourced inquiry packet and a UIPA
    records-request checklist. Everything is framed as a QUESTION for the lawful channel — never an accusation.

On the legality, briefly (full memo attached / linked): a Council member, acting as a private citizen with
their OWN funds, analyzing ALREADY-PUBLIC records to perform oversight, is generally permissible — the data is
open to anyone (HRS 92F), no county money or staff is used, and oversight + referral to Corporation Counsel is
your proper role. The safeguards: pay with personal funds, run it on a personal device, feed it only public
records, don't accept it free from anyone with business before the county, and — the strongest protection — get
a Board of Ethics advisory opinion (Charter §10-2(5) gives you immunity when you act on it). This note is
informational, not legal advice; please confirm with the Board of Ethics and your own counsel.

%s It's a private tier — your work stays yours; nothing on the public board.

If you'd like a walkthrough on your own device, just reply and I'll set it up.

With aloha and respect for the work,
Jimmy Langford
12 Stones Global / govOS
""" % (first, _price_line(off))
    return {"seat": seat_key, "to_name": name, "district": district,
            "subject": subject, "body": body,
            "status": "DRAFT — owner review + send (this tool never sends)",
            "legality_doc": "docs/COUNCIL_AUDIT_LEGALITY.md"}


def stage_all():
    os.makedirs(OUT, exist_ok=True)
    off = _offer()
    staged = []
    for k, full in ROSTER.items():
        if k == "Bissen":      # the mayor (executive), not a Council seat
            continue
        d = draft(k, full, off)
        p = os.path.join(OUT, "draft_%s.json" % k)
        json.dump(d, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        # also a human-readable .txt for easy copy/paste into the owner's mail client
        open(os.path.join(OUT, "draft_%s.txt" % k), "w", encoding="utf-8", newline="\n").write(
            "TO: %s (%s)\nSUBJECT: %s\n\n%s" % (d["to_name"], d["district"], d["subject"], d["body"]))
        staged.append(d)
    # a manifest so the owner sees the whole set at a glance
    json.dump({"generated_seats": [s["seat"] for s in staged],
               "count": len(staged), "status": "DRAFTS — never auto-sent; owner reviews + sends",
               "dir": "reports/_status/council_outreach/"},
              open(os.path.join(OUT, "_manifest.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return staged


def main():
    import argparse
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--print", dest="who", default=None, help="print one seat's draft (roster key, e.g. Lee)")
    a = ap.parse_args()
    off = _offer()
    if a.who:
        full = ROSTER.get(a.who)
        if not full:
            print("no such seat:", a.who, "| seats:", ", ".join(k for k in ROSTER if k != "Bissen")); return 1
        d = draft(a.who, full, off)
        print("TO: %s (%s)\nSUBJECT: %s\n\n%s" % (d["to_name"], d["district"], d["subject"], d["body"]))
        return 0
    staged = stage_all()
    print("council_outreach: staged %d DRAFTS -> reports/_status/council_outreach/ (review + send yourself; never auto-sent)" % len(staged))
    for s in staged:
        print("  - %s (%s)" % (s["to_name"], s["district"]))
    return 0


if __name__ == "__main__":
    if sys.platform == "win32":
        import io; sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(main())
