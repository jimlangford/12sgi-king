#!/usr/bin/env python3
"""sunshine_compliance.py — speed up HRS §92 (Sunshine Law) meeting-notice compliance + distribution
(Jimmy 2026-06-18). Cuts the friction so a council/clerk never misses the 6-day rule and never re-drafts a
notice by hand. It computes the deadline, validates the required elements, generates a ready-to-file
§92-compliant notice + the notification-list email, and prepares a newspaper legal-notice package for the
"send to newspaper" button.

GROUNDED IN THE STATUTE (verified vs HRS §92-7 + OIP "Quick Review", 2026-06-18):
  • DEADLINE = meeting_date − 6 CALENDAR days. The controlling act is ELECTRONIC POSTING on the county
    calendar; if it posts < 6 calendar days out, the meeting is CANCELED AS A MATTER OF LAW (§92-7(c)).
    Calendar days (weekends/holidays count); the meeting day is excluded. We keep a safety buffer.
  • REQUIRED ELEMENTS (§92-7(a)): date, time, location(s), agenda listing ALL items, the board's
    electronic + postal testimony contact, and disability-accommodation (ADA) instructions (+ exec-meeting
    purpose / remote-ICT info when applicable).
  • CHANNELS (§92-7(b)): county-calendar electronic post (controlling) · county-clerk filing · office
    posting · meeting-site posting · mail/email to the notification list. (We prepare these; the county
    performs the official calendar/clerk acts.)
  • NEWSPAPER: OIP is explicit — newspaper publication is NOT required for §92 meeting notices. It is a
    MATTER-SPECIFIC legal-notice requirement (rezoning HRS §46-4, budget/charter hearings, etc.). The
    "send to newspaper" action is therefore an OPT-IN for those matters + extra public awareness — never
    a substitute for the calendar/clerk filing. The tool says so plainly.

This is an ASSIST — confirm with the County Clerk / Corporation Counsel; OIP Attorney of the Day
(808) 586-1400 for edge cases. Stdlib only.

API:
  deadline(meeting_date, buffer_days=1)  -> {deadline, days_to_deadline, status, auto_cancel_risk}
  required_elements()                    -> [elements]
  validate(notice)                       -> {ok, missing:[...]}
  notice_text(meeting)                   -> str   (the §92-compliant public notice, ready to file/post)
  notification_email(meeting)            -> {subject, body}    (to the notification list)
  newspaper_package(meeting)             -> {legal_notice, cover, matter_specific_flag}
  status(meeting)                        -> the full compliance dashboard for one meeting
CLI: python sunshine_compliance.py --date 2026-06-25 --board "Maui County Council" [--newspaper]
"""
import os, sys, json
from datetime import date as _date, datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(os.path.dirname(HERE))
NEWS_CFG = os.path.join(PROJ, "config", "newspaper.json")          # public-safe contact; PASTE_ => "opening soon"
STAGE = os.path.join(PROJ, "reports", "_status", "sunshine")        # staged packages (owner reviews/sends)

NOTICE_DAYS = 6            # HRS §92-7(b): at least 6 CALENDAR days before the meeting
DEFAULT_BUFFER = 1        # safety margin so a borderline post is never late (recommend posting by day 7 prior)


def _parse(d):
    if isinstance(d, (_date, datetime)):
        return d if isinstance(d, _date) and not isinstance(d, datetime) else d.date()
    for f in ("%Y-%m-%d", "%m/%d/%Y", "%Y-%m-%dT%H:%M:%S"):
        try: return datetime.strptime(str(d)[:19] if "T" in str(d) else str(d), f).date()
        except Exception: pass
    return None


def deadline(meeting_date, buffer_days=DEFAULT_BUFFER, today=None):
    """The §92-7 notice deadline = meeting_date − 6 calendar days. Returns status + auto-cancel risk."""
    md = _parse(meeting_date)
    if not md:
        return {"error": "unparseable meeting_date: %r" % meeting_date}
    dl = md - timedelta(days=NOTICE_DAYS)                  # last lawful day to post the electronic notice
    safe = dl - timedelta(days=buffer_days)                # recommended post-by (buffer)
    t = today or _date.today()
    days_to_deadline = (dl - t).days
    days_to_meeting = (md - t).days
    if days_to_meeting < 0:
        status = "past"
    elif days_to_deadline > buffer_days:
        status = "on_track"
    elif 0 <= days_to_deadline <= buffer_days:
        status = "post_now"                                # in the buffer window — post immediately
    else:
        status = "LATE"                                    # past the 6-day mark
    return {"meeting_date": md.isoformat(), "notice_deadline": dl.isoformat(),
            "recommended_post_by": safe.isoformat(), "days_to_deadline": days_to_deadline,
            "days_to_meeting": days_to_meeting, "status": status,
            "auto_cancel_risk": status == "LATE",
            "rule": "HRS §92-7(b): file/electronically post at least 6 calendar days before the meeting; "
                    "late electronic posting cancels the meeting as a matter of law (§92-7(c)). Calendar days; "
                    "meeting day excluded; weekends/holidays count. Verify edge cases with OIP (808) 586-1400."}


REQUIRED = [
    ("date", "Meeting date"),
    ("time", "Meeting time"),
    ("location", "Location(s) — every site members are physically present; public site if remote"),
    ("agenda", "Agenda listing ALL items to be considered"),
    ("testimony_contact", "Board's electronic + postal contact for submitting testimony"),
    ("ada", "Disability-accommodation (ADA) instructions"),
]


def required_elements():
    return [{"key": k, "label": v} for k, v in REQUIRED]


def validate(notice):
    missing = [v for k, v in REQUIRED if not str((notice or {}).get(k, "")).strip()]
    return {"ok": not missing, "missing": missing}


def _board_meta(meeting):
    return {
        "board": meeting.get("board") or meeting.get("committee") or "County Council",
        "date": _parse(meeting.get("meeting_date") or meeting.get("date") or meeting.get("when")),
        "time": meeting.get("time") or "9:00 a.m.",
        "location": meeting.get("location") or "Council Chamber, 8th Floor, Kalana O Maui Building, 200 S. High St., Wailuku, and online",
        "items": meeting.get("items") or meeting.get("agenda") or [],
        "testimony_contact": meeting.get("testimony_contact") or "county.clerk@mauicounty.us / County Clerk, 200 S. High St., Wailuku, HI 96793",
        "ada_phone": meeting.get("ada_phone") or "(808) 270-7748",
    }


def notice_text(meeting):
    """The §92-compliant public notice, ready to file with the clerk + post on the county calendar."""
    m = _board_meta(meeting)
    d = m["date"].isoformat() if m["date"] else "[date]"
    items = m["items"] if isinstance(m["items"], list) else []
    agenda = "\n".join("  %d. %s" % (i + 1, (it if isinstance(it, str) else it.get("title", str(it)))) for i, it in enumerate(items)) \
             or "  [agenda items — list ALL items to be considered]"
    return (
        "NOTICE OF MEETING\n%s\n\n"
        "DATE: %s\nTIME: %s\nPLACE: %s\n\n"
        "AGENDA\n%s\n\n"
        "TESTIMONY: Written testimony may be submitted to %s. Oral testimony is taken at the meeting.\n\n"
        "ACCOMMODATIONS: If you require an auxiliary aid or accommodation due to a disability, contact %s "
        "as early as possible; requests made less than 3 working days before may not be fulfilled.\n\n"
        "Filed with the County Clerk and posted on the county calendar at least six (6) calendar days before "
        "the meeting, per HRS §92-7." % (m["board"], d, m["time"], m["location"], agenda,
                                          m["testimony_contact"], m["ada_phone"]))


def notification_email(meeting):
    m = _board_meta(meeting)
    d = m["date"].isoformat() if m["date"] else "[date]"
    return {"subject": "Public notice — %s, %s" % (m["board"], d),
            "body": "Aloha,\n\nPublic notice of the following meeting (HRS §92-7). The full notice + agenda are "
                    "attached/below.\n\n" + notice_text(meeting) +
                    "\n\nYou are receiving this as a member of the board's notification list."}


def _news_cfg():
    try: c = json.load(open(NEWS_CFG, encoding="utf-8"))
    except Exception: c = {}
    def ok(v): return bool(v) and not str(v).startswith("PASTE_")
    return {"name": c.get("newspaper_name") if ok(c.get("newspaper_name")) else "",
            "legal_email": c.get("legal_notices_email") if ok(c.get("legal_notices_email")) else ""}


def newspaper_package(meeting):
    """Prepare a NEWSPAPER legal-notice package. HONEST: newspaper publication is NOT a §92 requirement —
    it applies to matter-specific hearings (rezoning HRS §46-4, budget/charter hearings). Opt-in + extra reach."""
    m = _board_meta(meeting); cfg = _news_cfg()
    d = m["date"].isoformat() if m["date"] else "[date]"
    legal = "PUBLIC NOTICE\n\n" + notice_text(meeting)
    cover = ("To the Legal Notices desk%s,\n\nPlease publish the attached public notice for the %s meeting on "
             "%s. Confirm the publication date and rate; a tear sheet/affidavit of publication is requested for "
             "our records.\n\nMahalo." % ((" at %s" % cfg["name"]) if cfg["name"] else "", m["board"], d))
    return {"legal_notice": legal, "cover": cover, "to": cfg["legal_email"],
            "newspaper": cfg["name"] or "(set config/newspaper.json)",
            "matter_specific_flag": "Newspaper publication is NOT required for §92 meeting notices (OIP). It "
                                    "applies to matter-specific legal notices (rezoning §46-4, budget/charter "
                                    "hearings). Use for those matters or for extra public awareness — never as a "
                                    "substitute for the county-calendar electronic posting + clerk filing.",
            "sendable": bool(cfg["legal_email"])}


def status(meeting):
    m = _board_meta(meeting)
    dl = deadline(meeting.get("meeting_date") or meeting.get("date") or meeting.get("when"))
    notice = {"date": m["date"], "time": m["time"], "location": m["location"],
              "agenda": m["items"], "testimony_contact": m["testimony_contact"], "ada": m["ada_phone"]}
    return {"board": m["board"], "deadline": dl, "elements": validate(notice),
            "channels": [
                {"channel": "county calendar (electronic posting)", "required": True, "controlling": True,
                 "who": "county", "note": "the act that satisfies §92 + starts the 6-day clock"},
                {"channel": "county clerk filing", "required": True, "who": "county"},
                {"channel": "office posting", "required": True, "who": "county"},
                {"channel": "meeting-site posting", "required": True, "who": "county"},
                {"channel": "notification list (mail/email)", "required": True, "who": "prepared here",
                 "prepared": True},
                {"channel": "newspaper legal notice", "required": False, "who": "prepared here (opt-in)",
                 "prepared": True, "note": "matter-specific, not §92"},
            ],
            "prepared": {"notice_text": True, "notification_email": True, "newspaper_package": True},
            "assist_note": "An assist to speed compliance — confirm with the County Clerk / Corporation Counsel."}


def stage_package(meeting):
    """Write the prepared notice + emails to a private staging dir for owner review (never auto-sent)."""
    os.makedirs(STAGE, exist_ok=True)
    m = _board_meta(meeting)
    slug = "%s_%s" % ((m["date"].isoformat() if m["date"] else "nodate"),
                      "".join(c for c in m["board"] if c.isalnum())[:24])
    pkg = {"board": m["board"], "status": status(meeting), "notice_text": notice_text(meeting),
           "notification_email": notification_email(meeting), "newspaper": newspaper_package(meeting),
           "staged": "owner reviews + files/sends; this tool never auto-sends or files to the county"}
    p = os.path.join(STAGE, "sunshine_%s.json" % slug)
    json.dump(pkg, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    open(os.path.join(STAGE, "notice_%s.txt" % slug), "w", encoding="utf-8", newline="\n").write(pkg["notice_text"])
    return p


def main():
    import argparse
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--date", required=True, help="meeting date YYYY-MM-DD")
    ap.add_argument("--board", default="Maui County Council")
    ap.add_argument("--newspaper", action="store_true")
    a = ap.parse_args()
    meeting = {"board": a.board, "meeting_date": a.date}
    dl = deadline(a.date)
    print("SUNSHINE COMPLIANCE — %s — meeting %s" % (a.board, a.date))
    print("  notice deadline: %s (post by %s) — %s — %d day(s) to deadline%s"
          % (dl["notice_deadline"], dl["recommended_post_by"], dl["status"], dl["days_to_deadline"],
             "  *** AUTO-CANCEL RISK ***" if dl["auto_cancel_risk"] else ""))
    if a.newspaper:
        np = newspaper_package(meeting)
        print("\nNEWSPAPER PACKAGE (opt-in; %s):\n  to: %s\n  %s\n\n%s" %
              (np["newspaper"], np["to"] or "(no legal-notices email set)", np["matter_specific_flag"], np["cover"]))
    else:
        print("\n" + notice_text(meeting))
    print("\nstaged ->", stage_package(meeting))
    return 0


if __name__ == "__main__":
    if sys.platform == "win32":
        import io; sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(main())
