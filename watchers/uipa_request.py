#!/usr/bin/env python3
"""uipa_request.py — generate UIPA (HRS 92F) records-request letters for the EXAMINE money×votes cases, so
the public can obtain the procurement files + the recorded votes (Jimmy 2026-06-19: "auto-email through my
gmail and tracked").

INTEGRITY: a records request is a citizen RIGHT and a QUESTION to the record — never an accusation. Each
letter is sourced (the firm's county awards from HANDS + its contributions from the CSC, both public) and
asks for the records that would let the public see whether a funded member decided on the funder's matter.
The private casework is the basis; the UIPA seeks the PUBLIC records to verify.

This GENERATES the letters + a tracker; the executor creates them as Gmail DRAFTS (the connected MCP can
draft, not send — the safe posture for official requests in Jimmy's name) and Jimmy sends. Stdlib only.
Output: reports/_status/uipa/<id>.txt (PRIVATE drafts) + reports/_status/uipa/tracker.json
"""
import os, sys, json, re
from datetime import datetime, timezone, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(os.path.dirname(HERE))
ST = os.path.join(PROJ, "reports", "_status")
UIPA = os.path.join(ST, "uipa"); os.makedirs(UIPA, exist_ok=True)
HST = timezone(timedelta(hours=-10))
CLERK = "county.clerk@mauicounty.us"          # sourced (config) — confirm before sending
REQUESTER = "Jimmy Langford"
REPLY = "elementlotus@gmail.com"


def load(p, d):
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception:
        return d


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", str(s).lower()).strip("-")[:32]


def letter(case):
    vendor = case["vendor"]; official = (case.get("official") or "").split(" - ")[0]
    award = "${:,.0f}".format(case.get("award_total") or 0)
    contrib = "${:,.0f}".format(case.get("contrib_total") or 0)
    today = datetime.now(HST).strftime("%B %d, %Y")
    subject = "UIPA records request (HRS 92F) — %s county awards and the related votes" % vendor
    body = (
        "%s\n\nOffice of the County Clerk\nCounty of Maui\n\n"
        "Dear County Clerk,\n\n"
        "Under the Uniform Information Practices Act (HRS Chapter 92F), I respectfully request copies of the "
        "following public records:\n\n"
        "1. All procurement and contract-award records (solicitations, bids, award notices, and contracts) "
        "involving %s.\n"
        "2. The recorded committee and Council votes, and the corresponding minutes, on any matter approving, "
        "funding, or amending those awards.\n"
        "3. Any conflict-of-interest disclosures or recusals filed by Councilmember %s in connection with "
        "those matters.\n\n"
        "Context for the request (public records): the firm holds %s in county awards (HANDS open data), and "
        "campaign-finance records (Hawaiʻi Campaign Spending Commission) show contributions of %s associated "
        "with Councilmember %s. I am asking for the records above so the public can see whether the member who "
        "received this support participated in decisions affecting the firm — a question for the record, not a "
        "conclusion.\n\n"
        "Please advise of any fees before incurring them. I can receive records electronically at the address "
        "below. Thank you for your service to the people of Maui County.\n\n"
        "Respectfully,\n%s\n%s\n"
        % (today, vendor, official or "the relevant member", award, contrib, official or "the member", REQUESTER, REPLY))
    return subject, body


def main():
    cw = load(os.path.join(ST, "casework_maui.json"), {})
    cases = [c for c in cw.get("cases", []) if c.get("verdict") == "EXAMINE"]
    tracker = load(os.path.join(UIPA, "tracker.json"), {"requests": []})
    by_id = {r["id"]: r for r in tracker["requests"]}
    out = []
    for c in cases:
        rid = "uipa-" + slug(c["vendor"])
        subj, body = letter(c)
        open(os.path.join(UIPA, rid + ".txt"), "w", encoding="utf-8", newline="\n").write(subj + "\n\n" + body)
        rec = by_id.get(rid, {"id": rid})
        rec.update({"vendor": c["vendor"], "official": (c.get("official") or "").split(" - ")[0],
                    "award_total": c.get("award_total"), "recipient": CLERK, "subject": subj,
                    "status": rec.get("status", "DRAFTED"), "draft_id": rec.get("draft_id", ""),
                    "generated": datetime.now(HST).strftime("%Y-%m-%d %H:%M:%S HST")})
        by_id[rid] = rec
        out.append(rec)
    tracker["requests"] = list(by_id.values())
    tracker["updated"] = datetime.now(HST).strftime("%Y-%m-%d %H:%M:%S HST")
    json.dump(tracker, open(os.path.join(UIPA, "tracker.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("uipa_request: %d EXAMINE letters generated -> reports/_status/uipa/ (recipient %s)" % (len(out), CLERK))
    for r in out:
        print("  %s | %s -> %s | %s | status=%s" % (r["id"], r["vendor"][:28], r["official"], r["subject"][:40], r["status"]))
    return 0


if __name__ == "__main__":
    if sys.platform == "win32":
        import io; sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(main())
