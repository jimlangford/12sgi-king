#!/usr/bin/env python3
"""
uipa_daily.py — generate daily UIPA (HRS 92F) records-request letters from
the previous day's JRCSL live-meeting leads (jrcsl_leads.jsonl).

Jimmy 2026-06-24: "prepare all of the UIPA requests daily from the day before
— our audit system needs truth."

INTEGRITY (JRCSL doctrine, non-negotiable):
- A UIPA request is a CITIZEN RIGHT and a QUESTION to the record, never an accusation.
- Every letter is sourced from what was heard on the public record.
- Findings are framed as requests to verify, not as conclusions.
- gate_hint=NEEDS-RECORD leads → generate the request that closes the gap.
- gate_hint=REVIEW-READY leads → already sourced; still generate for completeness.

PRIVATE — owner only. Jimmy reviews and sends; this script NEVER auto-sends.
Output: reports/_status/uipa/YYYY-MM-DD/<agency>.txt + tracker.json
Runs: daily maintenance tick, after prosecutor_daily.py.

Usage:
  python uipa_daily.py                  # yesterday's leads
  python uipa_daily.py --date 2026-06-24  # specific date
  python uipa_daily.py --today           # today's leads (for same-day session)
"""
import os, sys, re, json, textwrap
from datetime import datetime, timezone, timedelta
from collections import defaultdict

HST = timezone(timedelta(hours=-10))
HOME = os.path.expanduser("~")
PROJ = os.path.join(HOME, "Documents", "Claude", "Projects", "Video System elementLOTUS")
ST   = os.path.join(PROJ, "reports", "_status")
LEADS_FILE  = os.path.join(ST, "prosecutor", "jrcsl_leads.jsonl")
UIPA_BASE   = os.path.join(ST, "uipa")
TRACKER     = os.path.join(UIPA_BASE, "tracker.json")

REQUESTER   = "Jimmy Langford"
REPLY_EMAIL = "elementlotus@gmail.com"

# ── Agency routing ────────────────────────────────────────────────────────────
# Each rule: (priority, agency_key, display_name, email, match_keywords)
# First matching rule wins for a lead. Order = most specific first.
AGENCIES = [
    (1, "dws",      "Department of Water Supply",
     "water.supply@mauicounty.us",
     ["water", "tank", "gallon", "dws", "kahoma", "stream", "well", "aquifer"]),
    (2, "planning", "Department of Planning",
     "planning.department@mauicounty.us",
     ["planning", "director", "zoning", "commission", "land use", "bill 73",
      "pro forma", "permit", "review", "developer", "project", "phase"]),
    (3, "finance",  "Department of Finance / Office of Recovery",
     "finance.department@mauicounty.us",
     ["hud", "cdbg", "grant", "funding", "fund", "billion", "million",
      "award", "contract", "fema", "recovery", "allocation"]),
    (4, "clerk",    "Office of the County Clerk",
     "county.clerk@mauicounty.us",
     ["motion", "vote", "minutes", "sunshine", "document", "transmit",
      "agenda", "meeting", "motion", "second", "board", "council",
      "subpoena", "letter", "haley", "mason"]),
]

def route_agency(lead):
    matter = (lead.get("matter") or "").lower()
    question = (lead.get("question") or "").lower()
    text = matter + " " + question
    for priority, key, name, email, keywords in AGENCIES:
        if any(kw in text for kw in keywords):
            return key, name, email
    return "clerk", "Office of the County Clerk", "county.clerk@mauicounty.us"


# ── Date parsing ──────────────────────────────────────────────────────────────
def load_leads(target_date_str):
    leads = []
    try:
        for line in open(LEADS_FILE, encoding="utf-8"):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue
            ts = obj.get("ts", "")
            if ts.startswith(target_date_str):
                leads.append(obj)
    except FileNotFoundError:
        pass
    return leads


# ── Letter generation ─────────────────────────────────────────────────────────
def letter(date_str, agency_name, agency_email, leads):
    today = datetime.now(HST).strftime("%B %d, %Y")
    meeting_date = date_str          # e.g. 2026-06-24 (verify before sending)
    flags = sorted(set(f for L in leads for f in (L.get("flags") or [])))
    flag_label = " / ".join(flags).upper() if flags else "PUBLIC RECORD"

    # Build specific-records section from each lead's question
    records_section = ""
    for i, L in enumerate(leads, 1):
        matter = (L.get("matter") or "").strip()
        question = (L.get("question") or "").strip()
        meeting_time = (L.get("meeting_date") or "").strip()
        if question:
            records_section += "  %d. %s\n     (Meeting time ref: %s)\n\n" % (i, question, meeting_time or "see transcript")

    subject = ("UIPA records request (HRS 92F) — %s meeting records, %s"
               % (agency_name, meeting_date))

    body = textwrap.dedent("""\
        {today}

        {agency_name}
        County of Maui
        {agency_email}

        Dear Records Custodian,

        Under the Uniform Information Practices Act (Hawaii Revised Statutes Chapter 92F),
        I respectfully request copies of the following public records related to the Maui
        County Council / {agency_name} meeting or proceeding on or around {meeting_date}.

        RECORDS REQUESTED:

        {records_section}
        Additionally, please provide:

        A. Any written correspondence, memoranda, or formal declinations issued by or to
           {agency_name} in connection with the above matters during the period
           {meeting_date} ± 30 days.

        B. The official meeting minutes and any attached exhibits or submitted documents
           from proceedings on {meeting_date} that touch on the above matters.

        C. Any conflict-of-interest disclosures or recusal notices filed in connection
           with votes taken on these matters.

        BASIS FOR REQUEST: The above matters were discussed in a public proceeding on
        approximately {meeting_date} (source: Maui County public broadcast / Ch53). This
        request is made to obtain the primary records so the public can verify the facts —
        a question for the record, not a conclusion.

        NOTE TO CUSTODIAN: Please confirm the exact meeting date if the {meeting_date}
        reference requires clarification. I can receive records electronically at the
        address below. Please advise of any fees before incurring them.

        Thank you for your service to the people of Maui County.

        Respectfully,
        {requester}
        {reply}

        — DRAFT — REVIEW BEFORE SENDING — PRIVATE / OWNER ONLY —
        Generated: {generated}
        Source leads: {n_leads} JRCSL flags ({flag_label})
        """).format(
            today=today,
            agency_name=agency_name,
            agency_email=agency_email,
            meeting_date=meeting_date,
            records_section=records_section if records_section else "  (See source leads.)\n\n",
            requester=REQUESTER,
            reply=REPLY_EMAIL,
            generated=datetime.now(HST).strftime("%Y-%m-%d %H:%M HST"),
            n_leads=len(leads),
            flag_label=flag_label,
        )
    return subject, body


# ── Tracker ───────────────────────────────────────────────────────────────────
def load_tracker():
    try:
        return json.load(open(TRACKER, encoding="utf-8"))
    except Exception:
        return {"requests": []}

def save_tracker(t):
    t["updated"] = datetime.now(HST).strftime("%Y-%m-%d %H:%M HST")
    json.dump(t, open(TRACKER, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


# ── Main ──────────────────────────────────────────────────────────────────────
def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]

    # Determine target date
    if "--today" in argv:
        target_date = datetime.now(HST).strftime("%Y-%m-%d")
    elif "--date" in argv:
        idx = argv.index("--date")
        target_date = argv[idx + 1] if idx + 1 < len(argv) else datetime.now(HST).strftime("%Y-%m-%d")
    else:
        yesterday = datetime.now(HST) - timedelta(days=1)
        target_date = yesterday.strftime("%Y-%m-%d")

    leads = load_leads(target_date)
    if not leads:
        print("uipa_daily: no JRCSL leads for %s — nothing to generate" % target_date)
        return 0

    # Cluster by agency
    clusters = defaultdict(list)
    for L in leads:
        key, name, email = route_agency(L)
        clusters[(key, name, email)].append(L)

    # Output directory
    out_dir = os.path.join(UIPA_BASE, target_date)
    os.makedirs(out_dir, exist_ok=True)

    tracker = load_tracker()
    by_id = {r["id"]: r for r in tracker["requests"]}
    generated = []

    for (key, name, email), cluster_leads in sorted(clusters.items()):
        rid = "uipa-%s-%s" % (target_date, key)
        subj, body = letter(target_date, name, email, cluster_leads)
        out_path = os.path.join(out_dir, "uipa-%s.txt" % key)
        open(out_path, "w", encoding="utf-8", newline="\n").write(subj + "\n\n" + body)

        rec = by_id.get(rid, {"id": rid})
        rec.update({
            "date": target_date,
            "agency_key": key,
            "agency_name": name,
            "recipient": email,
            "subject": subj,
            "status": rec.get("status", "DRAFTED"),
            "draft_id": rec.get("draft_id", ""),
            "n_leads": len(cluster_leads),
            "flags": sorted(set(f for L in cluster_leads for f in (L.get("flags") or []))),
            "out_path": out_path,
            "generated": datetime.now(HST).strftime("%Y-%m-%d %H:%M HST"),
        })
        by_id[rid] = rec
        generated.append(rec)

    tracker["requests"] = list(by_id.values())
    save_tracker(tracker)

    print("uipa_daily [%s]: %d letter(s) drafted -> %s" % (target_date, len(generated), out_dir))
    for r in generated:
        print("  [%s] %d leads -> %s (%s)" % (r["agency_key"], r["n_leads"], r["agency_name"], r["status"]))
    print("  REVIEW BEFORE SENDING — Jimmy sends, never auto-sent.")
    return 0


if __name__ == "__main__":
    if sys.platform == "win32":
        import io; sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(main())
