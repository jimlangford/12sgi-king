#!/usr/bin/env python3
"""uipa_track.py - close the loop on the UIPA records requests: track each from DRAFT -> SENT -> RESPONDED
(Jimmy 2026-06-19: "auto-emailed through my gmail and tracked").

Reads reports/_status/uipa/tracker.json (the requests + their Gmail draft ids) and, when Gmail OAUTH is set
up (config/gmail_token.json, gmail.readonly - same token the server's gmail_keywatch uses), advances each:
  - DRAFT-IN-GMAIL -> SENT      when a message with the request's subject appears in Sent
  - SENT           -> RESPONDED when a reply from @mauicounty.us appears on that thread
On each transition it dispatches ONE FINDING + a board WBITEM (dedup - never spam).

STANDBY-SAFE (mirrors gmail_keywatch): if the Gmail token/libs are absent it writes an 'awaiting_setup'
status and exits 0 - tracking goes live the moment server-quad-os wires the gmail OAuth. Read-only on
Gmail; never sends; never prints email bodies; ASCII only.
Output: reports/_status/uipa/track_status.json (+ updates tracker.json)
"""
import os, sys, json
from datetime import datetime, timezone, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(os.path.dirname(HERE))
CONFIG = os.path.join(PROJ, "config")
UIPA = os.path.join(PROJ, "reports", "_status", "uipa")
TRACKER = os.path.join(UIPA, "tracker.json")
STATUS = os.path.join(UIPA, "track_status.json")
TOKEN = os.path.join(CONFIG, "gmail_token.json")
HST = timezone(timedelta(hours=-10))
CLERK_DOMAIN = "mauicounty.us"
NW = 0x08000000 if os.name == "nt" else 0


def load(p, d):
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception:
        return d


def _status(state, detail):
    json.dump({"state": state, "detail": detail, "checked": datetime.now(HST).strftime("%Y-%m-%d %H:%M:%S HST")},
              open(STATUS, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def _dispatch(msg):
    try:
        import subprocess
        subprocess.run([sys.executable, os.path.join(PROJ, "app", "server", "dispatch.py"), PROJ,
                        "--log-event", msg, "--source", "kilo-aupuni"],
                       capture_output=True, timeout=30, creationflags=NW)
    except Exception:
        pass


def _gmail_service():
    """gmail.readonly client from config/gmail_token.json (same as gmail_keywatch). None if not set up."""
    if not os.path.exists(TOKEN):
        return None
    try:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
        creds = Credentials.from_authorized_user_file(TOKEN, ["https://www.googleapis.com/auth/gmail.readonly"])
        if not creds.valid and creds.refresh_token:
            from google.auth.transport.requests import Request
            creds.refresh(Request())
        return build("gmail", "v1", credentials=creds, cache_discovery=False)
    except Exception:
        return None


def _q(svc, query):
    try:
        return svc.users().messages().list(userId="me", q=query, maxResults=5).execute().get("messages", [])
    except Exception:
        return []


def main():
    os.makedirs(UIPA, exist_ok=True)
    t = load(TRACKER, {"requests": []})
    reqs = t.get("requests", [])
    if not reqs:
        _status("idle", "no UIPA requests to track")
        print("uipa_track: no requests in the tracker."); return 0

    svc = _gmail_service()
    if svc is None:
        _status("awaiting_setup",
                "Gmail OAuth not set up (config/gmail_token.json). Tracking goes live once server-quad-os "
                "wires gmail.readonly (python tools/auth/gmail_keywatch.py --authorize). Until then, drafts "
                "are placed + status is held at DRAFT-IN-GMAIL.")
        print("uipa_track: STANDBY — Gmail OAuth not set up; %d requests held at DRAFT-IN-GMAIL." % len(reqs))
        return 0

    changed = 0
    for r in reqs:
        subj = (r.get("subject") or "").replace('"', "")
        if not subj:
            continue
        if r.get("status") == "DRAFT-IN-GMAIL":
            if _q(svc, 'in:sent subject:"%s"' % subj[:60]):
                r["status"] = "SENT"; r["sent_detected"] = datetime.now(HST).strftime("%Y-%m-%d")
                changed += 1
                _dispatch("FINDING (UIPA tracker): SENT — '%s' left the outbox. Now awaiting the Clerk's response." % r["vendor"])
        if r.get("status") == "SENT":
            if _q(svc, 'from:%s subject:"%s"' % (CLERK_DOMAIN, subj[:50])):
                r["status"] = "RESPONDED"; r["responded_detected"] = datetime.now(HST).strftime("%Y-%m-%d")
                changed += 1
                _dispatch("FINDING (UIPA tracker): RESPONDED — the County Clerk replied on '%s'. Audit-quad-os: ingest the records." % r["vendor"])
    if changed:
        t["updated"] = datetime.now(HST).strftime("%Y-%m-%d %H:%M:%S HST")
        json.dump(t, open(TRACKER, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    from collections import Counter
    c = Counter(r.get("status") for r in reqs)
    _status("live", dict(c))
    print("uipa_track: %d requests | %s | %d transition(s) this run" % (len(reqs), dict(c), changed))
    return 0


if __name__ == "__main__":
    if sys.platform == "win32":
        import io; sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(main())
