#!/usr/bin/env python3
"""calendar_civic.py — Civic quad-OS → Google Calendar bridge.

Reads all live civic data sources (agenda_sources.json, prosecutor daily,
board items, UIPA queue) and writes a pending-events queue to
config/civic_calendar_queue.json.  The executor seat (audit-quad-os /
this Claude session) reads that queue and creates/updates events via the
Google Calendar MCP.  Created event IDs are tracked in
config/civic_calendar_events.json to prevent duplicates on re-runs.

Run:
    python tools/kilo-aupuni/calendar_civic.py          # generate queue
    python tools/kilo-aupuni/calendar_civic.py --status # show queue + done

Event types created:
  [CIVIC]        Council/committee meeting (Peacock blue, color 7)
  [CIVIC ACTION] eComment / testimony deadline (Tangerine, color 6)
  [CIVIC REVIEW] Prosecutor / findings approval needed (Tomato, color 11)
  [CIVIC BRIEF]  Daily civic brief ready (Graphite, color 8)

Stdlib only. Called from tools/ops/maintenance.py daily_awareness block.
"""
import os, json, sys, re
from datetime import datetime, timedelta, timezone, date

HOME    = os.path.expanduser("~")
PROJECT = os.path.join(HOME, "Documents", "Claude", "Projects", "Video System elementLOTUS")
TOOL    = os.path.join(PROJECT, "tools", "kilo-aupuni")
CFG     = os.path.join(PROJECT, "config")
HST     = timezone(timedelta(hours=-10))

AGENDA_SRC  = os.path.join(TOOL, "agenda_sources.json")
QUEUE_OUT   = os.path.join(CFG, "civic_calendar_queue.json")
EVENTS_LOG  = os.path.join(CFG, "civic_calendar_events.json")

# Event color mapping (Google Calendar color IDs)
COLOR_MEETING  = "7"   # Peacock  — civic meeting
COLOR_ACTION   = "6"   # Tangerine — testimony/eComment deadline
COLOR_REVIEW   = "11"  # Tomato   — approval / review needed
COLOR_BRIEF    = "8"   # Graphite — daily brief / awareness

COUNCIL_LOCATION = "Maui County Council Chambers, 200 S High St, Wailuku, HI 96793"
ECOMMENT_URL     = "https://mauicounty.legistar.com/Calendar.aspx"   # Maui default; per-tenant via _ecomment_url()

# Per-tenant canonical agenda/Legistar portal — the WORKING source each calendar event links to.
# VERIFIED LIVE 2026-06-24 (real browser render / title check, not just HTTP 200 — honolulu.gov serves a
# soft-404 with a 200 status, which is exactly what shipped a dead link to James's calendar). ONLY add a
# tenant here once its URL is verified to render the actual agenda; otherwise fall back to the source's
# own url (sourced — never invented).
TENANT_CALENDAR = {
    "maui":     "https://mauicounty.legistar.com/Calendar.aspx",   # Maui County Legistar calendar
    "honolulu": "https://honolulucitycouncil.org/",                # official Honolulu City Council portal (Legistar-backed)
}
# Known-DEAD source URLs → the verified-working replacement (self-heal, like external_links HEAL_MAP).
# The Honolulu City Clerk "clk-council-calendar" page is a dead soft-404 — never link it.
DEAD_URL_HEAL = {
    "https://www.honolulu.gov/clerk/clk-council-calendar/": "https://honolulucitycouncil.org/",
    "https://www.honolulu.gov/clerk/clk-council-calendar":  "https://honolulucitycouncil.org/",
    "https://honolulu.gov/clerk/clk-council-calendar":      "https://honolulucitycouncil.org/",
}

def _canonical_url(tid, url):
    """Resolve to a WORKING canonical source: heal a known-dead URL, else if the url is empty or the dead
    Honolulu clerk page use the per-tenant portal, else keep the source's own url (sourced, never invented)."""
    u = (url or "").strip()
    if u in DEAD_URL_HEAL:
        return DEAD_URL_HEAL[u]
    if not u or "clk-council-calendar" in u:
        return TENANT_CALENDAR.get(tid, u)
    return u

def _ecomment_url(tid):
    """The eComment/testimony portal for the tenant (per-tenant, not Maui-hardcoded)."""
    return TENANT_CALENDAR.get(tid, ECOMMENT_URL)

def _load_json(path, default=None):
    try:
        return json.load(open(path, encoding="utf-8"))
    except Exception:
        return default if default is not None else {}

def _save_json(path, obj):
    tmp = path + ".tmp"
    open(tmp, "w", encoding="utf-8").write(json.dumps(obj, indent=2, ensure_ascii=False))
    os.replace(tmp, path)

LOOKAHEAD_DAYS = 30   # only queue events within this many days from today

def _today_hst():
    return datetime.now(HST).date()

def _event_key(tenant, date_str, kind, body_slug):
    """Stable dedup key — same across re-runs."""
    slug = (body_slug or "")[:40].lower().replace(" ", "_").replace(",","")
    return "%s|%s|%s|%s" % (tenant, date_str, kind, slug)

# ── MEETING events ────────────────────────────────────────────────────────────

TENANT_NAMES = {
    "maui":     "Maui County",
    "state":    "State of Hawaiʻi",
    "honolulu": "City & County of Honolulu",
    "hawaii":   "Hawaiʻi County",
    "kauai":    "Kauaʻi County",
    "nyc":      "New York City",
    "nys":      "New York State",
}

# UTC offset per tenant — Hawaii has no DST; all Hawaii counties are always UTC-10.
TENANT_TZ_OFFSET = {
    "maui":     -10,   # Hawaii Standard Time (no DST)
    "honolulu": -10,
    "hawaii":   -10,
    "kauai":    -10,
    "state":    -10,
    "nyc":       -5,   # Eastern Standard Time (adjust if EDT needed)
    "nys":       -5,
}

def _local_iso(date_str, hour, minute=0, tz_offset=-10):
    """Return ISO 8601 datetime string at `hour:minute` in the tenant's local timezone."""
    sign = "+" if tz_offset >= 0 else "-"
    return "%sT%02d:%02d:00%s%02d:00" % (date_str, hour, minute, sign, abs(tz_offset))

_hst_iso = lambda d, h, m=0: _local_iso(d, h, m, -10)   # HST alias for deadline/brief events

def _parse_time(time_str):
    """Parse a time string ('9:00 AM', '1:30 PM') to (hour_24, minute).
    Returns (9, 0) as default when unparseable."""
    m = re.search(r"(\d{1,2}):(\d{2})\s*(a\.?m\.?|p\.?m\.?)", (time_str or ""), re.I)
    if not m:
        return 9, 0
    h = int(m.group(1)); mn = int(m.group(2)); ap = m.group(3).lower().replace(".", "")
    if ap == "pm" and h != 12: h += 12
    if ap == "am" and h == 12: h = 0
    return h, mn

def _infer_time(title, body):
    """Fallback: extract time from meeting title/body text when no structured 'time' field exists."""
    h, mn = _parse_time(title + " " + body)
    return h, mn

def _meeting_events(sources, today):
    """Yield pending meeting events from agenda_sources."""
    horizon = (today + timedelta(days=LOOKAHEAD_DAYS)).isoformat()
    for src in sources:
        tid = src.get("tenant_id", "")
        tname = TENANT_NAMES.get(tid, tid)
        agenda_url = src.get("source_url", "")
        for mt in (src.get("upcoming") or []):
            dt = mt.get("date","")
            if not dt or dt < today.isoformat() or dt > horizon:
                continue
            body  = mt.get("body","")
            title = mt.get("title","Meeting")
            url   = mt.get("url","") or agenda_url
            tz_off = TENANT_TZ_OFFSET.get(tid, -10)
            time_field = mt.get("time", "")
            if time_field:
                sh, sm = _parse_time(time_field)
            else:
                sh, sm = _infer_time(title, body)  # fallback: parse from title text
            eh, em = sh + 3, sm                     # assume 3-hour block
            # primary meeting event
            key = _event_key(tid, dt, "meeting", body or title)
            summary = "[CIVIC] %s — %s" % (tname, (body or title)[:60])
            desc = ("%s\n\n%s\n\nSource: Legistar/official live feed\nAgenda: %s\n"
                    "eComment: %s\n\ngovOS civic calendar · kilo-aupuni · calendar_civic.py"
                    % (body, title, _canonical_url(tid, url), _ecomment_url(tid)))
            yield {
                "key":      key,
                "summary":  summary,
                "start":    _local_iso(dt, sh, sm, tz_off),
                "end":      _local_iso(dt, eh, em, tz_off),
                "color":    COLOR_MEETING,
                "desc":     desc,
                "location": COUNCIL_LOCATION if tid == "maui" else "",
                "reminders": [{"method":"popup","minutes":1440},
                               {"method":"email","minutes":2880}],
                "tenant":   tid,
                "kind":     "meeting",
            }
            # eComment / testimony deadline event (48h before = Hawaii Sunshine Law minimum)
            mtdate = date.fromisoformat(dt)
            deadline = mtdate - timedelta(days=2)
            if deadline >= today:
                dkey = _event_key(tid, deadline.isoformat(), "action", body or title)
                dsum = "[CIVIC ACTION] eComment closes — %s %s" % (tname, dt)
                ddesc = ("48-hour Hawaii Sunshine Law testimony window closes "
                         "before the %s meeting.\n\nSubmit written testimony / "
                         "eComment before this deadline.\n\neComment: %s\nAgenda: %s"
                         "\n\ngovOS civic calendar · kilo-aupuni · calendar_civic.py"
                         % (body or title, _ecomment_url(tid), _canonical_url(tid, url)))
                yield {
                    "key":      dkey,
                    "summary":  dsum,
                    "start":    _hst_iso(deadline.isoformat(), 8),
                    "end":      _hst_iso(deadline.isoformat(), 9),
                    "color":    COLOR_ACTION,
                    "desc":     ddesc,
                    "location": "",
                    "reminders":[{"method":"popup","minutes":60},
                                 {"method":"email","minutes":480}],
                    "tenant":   tid,
                    "kind":     "action",
                }

# ── PROSECUTOR REVIEW events ──────────────────────────────────────────────────

def _prosecutor_events(today):
    """Yield a daily [CIVIC REVIEW] slot if the prosecutor daily has new findings."""
    priv = os.path.join(PROJECT, "reports", "_status", "prosecutor_daily_latest.json")
    if not os.path.exists(priv):
        return
    try:
        data = json.load(open(priv, encoding="utf-8"))
    except Exception:
        return
    gen = (data.get("generated") or "")[:10]
    if not gen or gen < today.isoformat():
        return
    count = len(data.get("findings", []))
    if count == 0:
        return
    key = _event_key("system", gen, "review", "prosecutor_daily")
    yield {
        "key":      key,
        "summary":  "[CIVIC REVIEW] %d prosecutor finding(s) — approve/hold" % count,
        "start":    _hst_iso(gen, 7),
        "end":      _hst_iso(gen, 8),
        "color":    COLOR_REVIEW,
        "desc":     ("Prosecutor daily digest has %d finding(s) ready for JRCSL "
                     "approval review.  Open the private prosecutor back-end to "
                     "classify: approve for case file / hold for more record / dismiss.\n\n"
                     "PRIVATE — never publish.\n\ngovOS civic calendar · kilo-aupuni"
                     % count),
        "location": "",
        "reminders":[{"method":"popup","minutes":30},
                     {"method":"email","minutes":120}],
        "tenant":   "system",
        "kind":     "review",
    }

# ── BOARD ITEMS (civic lane) ──────────────────────────────────────────────────

def _board_civic_events(today):
    """Yield [CIVIC REVIEW] events for overdue/due civic board items."""
    wb = os.path.join(CFG, "workboard_items.json")
    if not os.path.exists(wb):
        return
    try:
        items = json.load(open(wb, encoding="utf-8")).get("items", [])
    except Exception:
        return
    civic_lanes = {"kilo-aupuni","civic","prosecutor-quad-os"}
    for it in items:
        if it.get("lane","") not in civic_lanes:
            continue
        if it.get("status","") in ("done","closed","cancelled"):
            continue
        due = (it.get("due") or "")[:10]
        if not due or due < today.isoformat():
            continue
        iid = it.get("id","")
        key = _event_key("board", due, "review", iid)
        yield {
            "key":      key,
            "summary":  "[CIVIC REVIEW] Board: %s" % it.get("title","")[:60],
            "start":    _hst_iso(due, 8),
            "end":      _hst_iso(due, 9),
            "color":    COLOR_REVIEW,
            "desc":     ("Civic board item due.\n\nLane: %s\nStatus: %s\n\n%s"
                         "\n\nWork Board: https://king.tail760750.ts.net/board"
                         "\n\ngovOS civic calendar · kilo-aupuni"
                         % (it.get("lane",""),it.get("status",""),it.get("body","")[:300])),
            "location": "",
            "reminders":[{"method":"popup","minutes":60}],
            "tenant":   "system",
            "kind":     "review",
        }

# ── MAIN ─────────────────────────────────────────────────────────────────────

def build_queue():
    today    = _today_hst()
    sources  = _load_json(AGENDA_SRC, {}).get("sources", [])
    done_log = _load_json(EVENTS_LOG, {})   # key -> {google_id, created_at}

    pending = []
    for ev in list(_meeting_events(sources, today)) + \
               list(_prosecutor_events(today))      + \
               list(_board_civic_events(today)):
        if ev["key"] in done_log:
            continue  # already created in a prior session
        pending.append(ev)

    _save_json(QUEUE_OUT, {
        "generated":     datetime.now(HST).strftime("%Y-%m-%d %H:%M HST"),
        "pending_count": len(pending),
        "pending":       pending,
        "already_done":  len(done_log),
    })
    return pending

def _safe(s): return s.encode("ascii","replace").decode("ascii")

def show_status():
    q    = _load_json(QUEUE_OUT, {})
    done = _load_json(EVENTS_LOG, {})
    print("civic_calendar: queue=%d pending  already_done=%d"
          % (q.get("pending_count",0), len(done)))
    for ev in q.get("pending",[]):
        print("  + %-14s %s  %s" % (ev["kind"], ev["start"][:10], _safe(ev["summary"][:70])))

def mark_done(key, google_id):
    """Called by the executor after successfully creating a Calendar event."""
    done = _load_json(EVENTS_LOG, {})
    done[key] = {
        "google_id":  google_id,
        "created_at": datetime.now(HST).strftime("%Y-%m-%d %H:%M HST"),
    }
    _save_json(EVENTS_LOG, done)

_SOFT404 = re.compile(r"can.?t find the page|page you.?re looking for|\bSorry,? we\b|404 (?:error|not found)", re.I)

def verify_sources():
    """Liveness-check every tenant's calendar source URL (the link events embed). Catches the
    soft-404 trap: honolulu.gov returns HTTP 200 while RENDERING a 'we can't find the page' body, so
    a status check alone ships a dead link. Returns [(tid, url, status)] with status in
    confirmed/SOFT-404/unreachable. Stdlib only; never raises."""
    import urllib.request, ssl, re as _re
    sources = _load_json(AGENDA_SRC, {}).get("sources", [])
    out = []
    for src in sources:
        tid = src.get("tenant_id", "")
        url = _canonical_url(tid, src.get("source_url", ""))
        if not url:
            continue
        status = "unreachable"
        try:
            req = urllib.request.Request(url, method="GET",
                                         headers={"User-Agent": "Mozilla/5.0 (12sgi civic-calendar linkcheck)"})
            with urllib.request.urlopen(req, timeout=20, context=ssl.create_default_context()) as r:
                body = r.read(20000).decode("utf-8", "ignore")
                code = getattr(r, "status", 200) or 200
            status = "SOFT-404" if (_SOFT404.search(body) or "clk-council-calendar" in url) else (
                "confirmed" if 200 <= code < 400 else "http-%s" % code)
        except Exception as e:
            status = "unreachable(%s)" % type(e).__name__
        out.append((tid, url, status))
    return out

def main():
    if "--verify" in sys.argv:
        print("civic_calendar source liveness (real-render check, soft-404 aware):")
        bad = []
        for tid, url, st in verify_sources():
            mark = "OK " if st == "confirmed" else "!! "
            print("  %s%-9s %-12s %s" % (mark, tid, st, url))
            if st != "confirmed":
                bad.append("%s=%s(%s)" % (tid, url, st))
        if bad:
            try:
                import subprocess
                subprocess.run([sys.executable, os.path.join(PROJECT, "app", "server", "dispatch.py"), PROJECT,
                                "--log-event", "FINDING: civic-calendar source link(s) NOT live (soft-404/dead) — "
                                + "; ".join(bad) + " — fix the source_url before events ship to the calendar.",
                                "--source", "kilo-aupuni"], timeout=20)
            except Exception:
                pass
            print("  -> %d source link(s) flagged (logged to dispatch)" % len(bad))
        else:
            print("  all source links confirmed live")
        return
    if "--status" in sys.argv:
        show_status(); return
    pending = build_queue()
    print("civic_calendar: %d event(s) queued to config/civic_calendar_queue.json" % len(pending))
    if pending:
        print("  -> audit-quad-os: run process_civic_calendar() to push to Google Calendar")

if __name__ == "__main__":
    main()
