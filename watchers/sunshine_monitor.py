#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""sunshine_monitor.py — Legistar Sunshine Law watchdog for kilo-aupuni / 12sgi.com.

Pulls all Maui County council committee meetings from the Legistar Web API (public JSON, no auth)
and computes the ACTUAL notice period the county provided:

    notice_days = meeting_date_HST - agenda_published_HST_date

HRS §92-7(b): the county must electronically post the agenda at least 6 CALENDAR days before the
meeting. Late posting = meeting canceled as a matter of law (§92-7(c)). Calendar days; weekends
and holidays count; meeting day is excluded.

Exception (§92-7(c) waiver): reconvened/recessed meetings — if members were told at the adjourned
meeting when it would reconvene, the 6-day notice is not required for the reconvened session.
EventComment containing "Reconvened" → REVIEW_NEEDED (minutes check required, not auto-FLAGGED).

OUTPUTS:
  reports/_status/sunshine_watch.json — machine-readable findings (always updated)
  reports/_status/sunshine_civic.html — public compliance table for kilo-aupuni / 12sgi-king

ALERTS: emails elementlotus@gmail.com when FLAGGED events are found.
PROSECUTOR: feeds FLAGGED + REVIEW_NEEDED into prosecutor_leads.py (private, owner-only).

Wire into maintenance tick: python tools/kilo-aupuni/sunshine_monitor.py
CLI:    --days-back N   (look N days into the past, default 60)
        --days-fwd N    (look N days ahead, default 90)
        --no-email      (skip email alert; useful for dry-run)
        --no-prosecutor (skip prosecutor intake)
        --html          (regenerate civic table only)

Jimmy 2026-06-22: "lets make sure we are on top of that with emails et al. from 12sgi.com"
Source: Legistar Web API https://webapi.legistar.com/v1/mauicounty/Events
"""
from __future__ import annotations
import os, sys, json, subprocess, datetime, urllib.request, urllib.error, urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
OPS  = os.path.join(ROOT, "tools", "ops")
if OPS not in sys.path: sys.path.insert(0, OPS)
if HERE not in sys.path: sys.path.insert(0, HERE)

WATCH_STORE = os.path.join(ROOT, "reports", "_status", "sunshine_watch.json")
CIVIC_HTML  = os.path.join(ROOT, "reports", "_status", "sunshine_civic.html")
PROS_SCRIPT = os.path.join(HERE, "prosecutor_leads.py")

HST = datetime.timezone(datetime.timedelta(hours=-10))
REQUIRED_DAYS = 6     # HRS §92-7(b)
LEGISTAR_CLIENT = "mauicounty"
LEGISTAR_API    = "https://webapi.legistar.com/v1/%s/Events" % LEGISTAR_CLIENT
LEGISTAR_DETAIL = "https://mauicounty.legistar.com/MeetingDetail.aspx?ID=%s"

# Council committee bodies we specifically track (exact substrings)
TRACKED_BODIES = [
    "Budget, Finance",
    "Government Relations, Ethics",
    "Housing and Land Use",
    "Water Authority, Social Services",
    "Water and Infrastructure",
    "Disaster Recovery, International",
    "Maui County Council",
]


# ── helpers ──────────────────────────────────────────────────────────────────

def _hst_now():
    return datetime.datetime.now(HST)


def _hst_date(utc_str):
    """Parse a Legistar UTC datetime string and return the HST date."""
    if not utc_str:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d %H:%M:%S"):
        try:
            dt = datetime.datetime.strptime(utc_str[:19], fmt).replace(tzinfo=datetime.timezone.utc)
            return dt.astimezone(HST).date()
        except Exception:
            pass
    return None


def _meeting_date(event):
    """Parse EventDate as the LOCAL meeting date. Legistar stores the meeting date as
    a UTC midnight string (e.g. '2026-06-22T00:00:00') but the date itself is already
    the local HST meeting date — do NOT do UTC->HST conversion or the date shifts back one day."""
    s = (event.get("EventDate") or "")[:10]   # just 'YYYY-MM-DD'
    try:
        return datetime.date.fromisoformat(s)
    except Exception:
        return None


def _body_tracked(name):
    if not name:
        return False
    return any(k.lower() in name.lower() for k in TRACKED_BODIES)


def _notice_days(agenda_pub_utc, meeting_date):
    """Calendar days between agenda publication (HST date) and meeting date."""
    pub = _hst_date(agenda_pub_utc)
    if pub is None or meeting_date is None:
        return None
    return (meeting_date - pub).days


def _classify(event, meeting_date, n_days):
    """Return (status, reason) for this event."""
    comment = (event.get("EventComment") or "").lower()
    agenda_pub = event.get("EventAgendaLastPublishedUTC")
    is_past = meeting_date < _hst_now().date() if meeting_date else False

    if n_days is None:
        if is_past and not agenda_pub:
            return "NO_AGENDA", "Past meeting — no agenda ever published on Legistar"
        if not is_past and not agenda_pub:
            return "UPCOMING_UNPOSTED", "Future meeting — agenda not yet published; watch for late notice"
        return "UNKNOWN", "Cannot determine notice period"

    if n_days >= REQUIRED_DAYS:
        return "COMPLIANT", "%d days notice (>= 6 required)" % n_days

    # Below 6 days — check reconvened exception
    if "reconvened" in comment or "recessed" in comment or "continuation" in comment:
        return ("REVIEW_NEEDED",
                "%d days notice — EventComment indicates reconvened session. "
                "Check §92-7(c): were members told at the adjourned meeting? Minutes review required." % n_days)

    return "FLAGGED", "%d days notice — BELOW 6-day HRS §92-7 threshold. No reconvened exception detected." % n_days


# ── Legistar API fetch ────────────────────────────────────────────────────────

def fetch_events(days_back=60, days_fwd=90):
    today = _hst_now().date()
    start = (today - datetime.timedelta(days=days_back)).isoformat() + "T00:00:00"
    end   = (today + datetime.timedelta(days=days_fwd)).isoformat()  + "T23:59:59"
    filt = "EventDate ge datetime'%s' and EventDate le datetime'%s'" % (start, end)
    url = "%s?$top=200&$filter=%s&$orderby=EventDate%%20asc" % (
        LEGISTAR_API, urllib.parse.quote(filt, safe="'"))
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json",
                                                    "User-Agent": "kilo-aupuni-sunshine-monitor/1.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception as e:
        return {"_error": str(e)}


# ── compliance analysis ───────────────────────────────────────────────────────

def analyze(events):
    findings = []
    for ev in events:
        body = ev.get("EventBodyName") or ""
        if not _body_tracked(body):
            continue
        eid = ev.get("EventId")
        md  = _meeting_date(ev)
        pub = ev.get("EventAgendaLastPublishedUTC")
        n   = _notice_days(pub, md)
        status, reason = _classify(ev, md, n)
        findings.append({
            "event_id":     eid,
            "body":         body,
            "meeting_date": md.isoformat() if md else None,
            "meeting_time": (ev.get("EventTime") or "").strip(),
            "agenda_published_utc": pub,
            "agenda_published_hst": _hst_date(pub).isoformat() if _hst_date(pub) else None,
            "notice_days":  n,
            "status":       status,
            "reason":       reason,
            "comment":      ev.get("EventComment") or "",
            "legistar_url": LEGISTAR_DETAIL % eid if eid else None,
            "agenda_url":   ev.get("EventAgendaFile") or None,
            "checked_iso":  _hst_now().date().isoformat(),
        })
    return findings


# ── data store ────────────────────────────────────────────────────────────────

def load_store():
    try:
        return json.load(open(WATCH_STORE, encoding="utf-8"))
    except Exception:
        return {"_doc": "Sunshine Law watchdog findings — kilo-aupuni", "findings": {}}


def save_store(store):
    os.makedirs(os.path.dirname(WATCH_STORE), exist_ok=True)
    tmp = WATCH_STORE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(store, f, ensure_ascii=False, indent=2)
    os.replace(tmp, WATCH_STORE)


def merge(store, findings):
    for f in findings:
        key = "%s_%s_%s" % (f["event_id"], f["meeting_date"] or "nodate", f["meeting_time"].replace(":", ""))
        store["findings"][key] = f
    store["last_checked"] = _hst_now().date().isoformat()
    return store


# ── email alert ───────────────────────────────────────────────────────────────

def send_alert(flagged, review):
    try:
        from mail_send import send
    except Exception:
        print("WARN: mail_send not importable — email skipped")
        return

    lines = []
    if flagged:
        lines.append("=== FLAGGED (potential HRS §92-7 violation) ===")
        for f in flagged:
            lines.append("  %s — %s %s" % (f["body"], f["meeting_date"], f["meeting_time"]))
            lines.append("  Notice: %s days (required: 6) | %s" % (f["notice_days"], f["reason"]))
            lines.append("  Legistar: %s" % f["legistar_url"])
            lines.append("")
    if review:
        lines.append("=== REVIEW NEEDED (reconvened session — check §92-7(c)) ===")
        for f in review:
            lines.append("  %s — %s %s" % (f["body"], f["meeting_date"], f["meeting_time"]))
            lines.append("  Notice: %s days | %s" % (f["notice_days"], f["reason"]))
            lines.append("  Comment: %s" % f["comment"])
            lines.append("  Legistar: %s" % f["legistar_url"])
            lines.append("")

    lines.append("Source: Legistar Web API / HRS §92-7. Frame as allegation; verify with OIP.")
    lines.append("Law: HRS §92-7(b) — 6 calendar days notice required. §92-7(c) — late notice cancels meeting.")

    subject = "Sunshine Law Alert — %d potential violation(s) — Maui County [kilo-aupuni]" % (len(flagged) + len(review))
    body = "\n".join(lines)
    to = "elementlotus@gmail.com"
    try:
        send(to_addr=to, subject=subject, body_text=body)
        print("EMAIL SENT -> %s: %s" % (to, subject))
    except Exception as e:
        print("WARN: email failed: %s" % e)


# ── prosecutor intake ─────────────────────────────────────────────────────────

def prosecutor_intake(findings_to_flag):
    if not os.path.isfile(PROS_SCRIPT):
        print("WARN: prosecutor_leads.py not found — skipping intake")
        return
    for f in findings_to_flag:
        claim = (
            "Maui County council committee meeting — %s on %s at %s — "
            "formal agenda allegedly published %s (%s days notice). "
            "HRS §92-7(b) requires 6 calendar days. %s"
            "Primary record: Legistar EventId %s (%s)."
        ) % (f["body"], f["meeting_date"], f["meeting_time"],
             f["agenda_published_hst"] or "unknown",
             f["notice_days"] if f["notice_days"] is not None else "unknown",
             ("EventComment: '%s'. " % f["comment"] if f["comment"] else ""),
             f["event_id"], f["legistar_url"])
        cmd = [sys.executable, PROS_SCRIPT, "add",
               "--source", "sunshine-monitor",
               "--claim", claim,
               "--url", f["legistar_url"] or "",
               "--scope", "civic_official"]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            print("PROSECUTOR: %s" % (r.stdout.strip() or r.stderr.strip() or "ok"))
        except Exception as e:
            print("WARN: prosecutor intake failed for %s: %s" % (f["event_id"], e))


# ── public civic HTML table ───────────────────────────────────────────────────

_STATUS_DISPLAY = {
    "COMPLIANT":          ('<span style="color:#1a7f4a;font-weight:700">✓ Compliant</span>',    "#eaf7ef"),
    "REVIEW_NEEDED":      ('<span style="color:#b07d00;font-weight:700">⚠ Review needed</span>', "#fffbe6"),
    "FLAGGED":            ('<span style="color:#c0392b;font-weight:700">✗ Flagged</span>',       "#fdecea"),
    "UPCOMING_UNPOSTED":  ('<span style="color:#5a6b7b">Agenda pending</span>',                  "#f5f8fc"),
    "NO_AGENDA":          ('<span style="color:#888">No agenda posted</span>',                   "#f8f8f8"),
    "UNKNOWN":            ('<span style="color:#aaa">—</span>',                                  "#fff"),
}


def _esc(s):
    return str(s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def build_civic_html(findings):
    today = _hst_now().date().isoformat()
    rows = []
    for f in sorted(findings, key=lambda x: (x["meeting_date"] or "", x["meeting_time"] or "")):
        label, bg = _STATUS_DISPLAY.get(f["status"], ("—", "#fff"))
        n = f["notice_days"]
        notice_cell = (str(n) + " days") if n is not None else "—"
        pub_cell    = f["agenda_published_hst"] or "—"
        lurl        = f["legistar_url"] or ""
        src         = ('<a href="' + _esc(lurl) + '" target="_blank" rel="noopener noreferrer" style="color:#0e4a84">Legistar ↗</a>') if lurl else "—"
        row = (
            '<tr style="background:' + bg + '">'
            '<td style="font-size:.82rem;max-width:260px">' + _esc(f["body"]) + '</td>'
            '<td style="white-space:nowrap">' + _esc(f["meeting_date"] or "") + '</td>'
            '<td style="white-space:nowrap">' + _esc(f["meeting_time"] or "") + '</td>'
            '<td style="white-space:nowrap">' + pub_cell + '</td>'
            '<td style="white-space:nowrap;text-align:center">' + notice_cell + '</td>'
            '<td>' + label + '</td>'
            '<td style="font-size:.78rem;color:#5a6b7b">' + _esc(f["reason"]) + '</td>'
            '<td>' + src + '</td>'
            '</tr>'
        )
        rows.append(row)

    rows_html = "\n".join(rows)
    html = (
        '<!doctype html>\n<html lang="en">\n<head><meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width,initial-scale=1">\n'
        '<title>Sunshine Law Compliance — Maui County Council — kilo-aupuni</title>\n'
        '<style>\n'
        'body{font-family:system-ui,sans-serif;color:#1a2233;margin:0;padding:1rem}\n'
        'h1{color:#0e4a84;font-size:1.2rem;margin-bottom:.3rem}\n'
        'p.lead{font-size:.88rem;color:#3a4a5a;margin:.3rem 0 .8rem}\n'
        'table{border-collapse:collapse;width:100%;font-size:.83rem}\n'
        'th{background:#0e4a84;color:#fff;padding:.4rem .6rem;text-align:left;font-weight:600}\n'
        'td{padding:.35rem .5rem;border-bottom:1px solid #e3edf6;vertical-align:top}\n'
        '.note{font-size:.75rem;color:#5a6b7b;margin-top:.6rem;border-top:1px solid #e3edf6;padding-top:.4rem}\n'
        '/* self-theme guard (James 2026-07-17): build_site injects govos.css + legibility_fix.css AFTER\n'
        '   this style, flipping body text to a light dark-theme color -> this light-cell table went\n'
        '   invisible (light text on light cells). Force this page own dark table text with html body\n'
        '   specificity + !important so the injected CSS cannot override it. */\n'
        'html body{color:#1a2233 !important;background:#ffffff !important}\n'
        'html body h1{color:#0e4a84 !important}\n'
        'html body p.lead{color:#3a4a5a !important}html body .note{color:#5a6b7b !important}\n'
        'html body table th{background:#0e4a84 !important;color:#ffffff !important}\n'
        'html body table td{color:#1a2233 !important;background:#ffffff !important;border-bottom:1px solid #e3edf6 !important}\n'
        'html body table tr:nth-child(even) td{background:#f6f9fc !important}\n'
        'html body a, html body td a{color:#0e4a84 !important}\n'
        '</style>\n</head>\n<body>\n'
        '<h1>Sunshine Law Compliance Monitor — Maui County Council Committee Meetings</h1>\n'
        '<p class="lead">'
        'Hawaii Revised Statutes §92-7(b) requires public bodies to electronically post the notice and agenda '
        'at least 6 calendar days before each meeting. This table shows the actual notice period for each '
        'Maui County Council committee meeting based on when the agenda was published on '
        '<a href="https://mauicounty.legistar.com/Calendar.aspx" target="_blank" rel="noopener noreferrer">Legistar</a>. '
        'Weekends and holidays count; the meeting day is excluded. '
        'This is a factual record. “Flagged” and “Review needed” are not legal determinations — consult an '
        'attorney or the <a href="https://oip.hawaii.gov" target="_blank" rel="noopener noreferrer">Office of Information Practices</a> '
        '(OIP Attorney of the Day: 808-586-1400) for legal rulings.'
        '</p>\n'
        '<table>\n<thead><tr>'
        '<th>Committee</th><th>Meeting date</th><th>Meeting time</th>'
        '<th>Agenda published (HST)</th><th>Notice days</th><th>Status</th><th>Notes</th><th>Source</th>'
        '</tr></thead>\n<tbody>\n'
        + rows_html +
        '\n</tbody>\n</table>\n'
        '<div class="note">'
        '<b>Source:</b> <a href="https://webapi.legistar.com/v1/mauicounty/Events" target="_blank" rel="noopener noreferrer">Legistar Web API (mauicounty)</a>'
        ' via sunshine_monitor.py (kilo-aupuni). Updated: ' + str(today) + ' HST. |'
        ' <b>Law:</b> HRS §92-7 (Hawaii Sunshine Law). |'
        ' <b>Exception:</b> Reconvened sessions may not require new 6-day notice if members were told at the prior meeting (§92-7(c)); those are marked “Review needed.”'
        '</div>\n</body></html>\n'
    )

    os.makedirs(os.path.dirname(CIVIC_HTML), exist_ok=True)
    with open(CIVIC_HTML, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(html)
    # Mirror to reports/mauios/ so build_site.py picks it up for the public 12sgi-king site
    mauios_dir = os.path.join(ROOT, "reports", "mauios")
    os.makedirs(mauios_dir, exist_ok=True)
    import shutil
    shutil.copy2(CIVIC_HTML, os.path.join(mauios_dir, "sunshine_maui.html"))
    return CIVIC_HTML


# ── main ─────────────────────────────────────────────────────────────────────

def run(days_back=60, days_fwd=90, do_email=True, do_prosecutor=True):
    print("sunshine_monitor: fetching Legistar events (%d days back, %d days fwd)..." % (days_back, days_fwd))
    raw = fetch_events(days_back, days_fwd)
    if isinstance(raw, dict) and "_error" in raw:
        print("ERROR fetching Legistar API: %s" % raw["_error"])
        return 1
    print("  %d events fetched" % len(raw))

    findings = analyze(raw)
    print("  %d tracked-body meetings analyzed" % len(findings))

    store = load_store()
    store = merge(store, findings)
    save_store(store)
    print("  store updated -> %s" % WATCH_STORE)

    flagged = [f for f in findings if f["status"] == "FLAGGED"]
    review  = [f for f in findings if f["status"] == "REVIEW_NEEDED"]
    compliant = [f for f in findings if f["status"] == "COMPLIANT"]
    pending = [f for f in findings if f["status"] in ("UPCOMING_UNPOSTED", "NO_AGENDA")]

    print("\n  COMPLIANT:        %d" % len(compliant))
    print("  REVIEW_NEEDED:    %d  (reconvened — minutes check)" % len(review))
    print("  FLAGGED:          %d  *** POTENTIAL VIOLATION ***" % len(flagged))
    print("  AGENDA PENDING:   %d  (upcoming; watch for late notice)" % len(pending))

    for f in flagged + review:
        print("  [%s] %s — %s %s — %s days notice — %s" % (
            f["status"], f["body"], f["meeting_date"], f["meeting_time"],
            f["notice_days"] if f["notice_days"] is not None else "?", f["legistar_url"]))

    html_out = build_civic_html(findings)
    print("\n  civic table -> %s" % html_out)

    if do_email and (flagged or review):
        send_alert(flagged, review)

    if do_prosecutor and (flagged or review):
        prosecutor_intake(flagged + review)

    return 0 if not flagged else 2   # exit 2 = violations found (non-zero for CI/monitoring)


def main():
    if sys.platform == "win32":
        import io; sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    import argparse
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--days-back",      type=int, default=60)
    ap.add_argument("--days-fwd",       type=int, default=90)
    ap.add_argument("--no-email",       action="store_true")
    ap.add_argument("--no-prosecutor",  action="store_true")
    ap.add_argument("--html",           action="store_true", help="regenerate civic HTML from store only")
    a = ap.parse_args()

    if a.html:
        store = load_store()
        findings = list(store.get("findings", {}).values())
        out = build_civic_html(findings)
        print("civic table rebuilt -> %s (%d findings)" % (out, len(findings)))
        return 0

    return run(days_back=a.days_back, days_fwd=a.days_fwd,
               do_email=not a.no_email, do_prosecutor=not a.no_prosecutor)


if __name__ == "__main__":
    sys.exit(main())
