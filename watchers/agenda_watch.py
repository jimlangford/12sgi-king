#!/usr/bin/env python3
"""agenda_watch.py — "Know the agenda" for every govOS tenant, the Maui way.

Reads a VERIFIED source registry (agenda_sources.json, produced by the agenda-discovery workflow:
each tenant's real agenda system + URL + machine-readable feed + a snapshot of currently-published
upcoming meetings). For each tenant it renders agendas_<id>.html showing the upcoming meetings as
far ahead as published, the authoritative source link, and a LAST-CHECKED timestamp.

This is the DAILY CHECKER: run on the CI cron (and a local windowless task) it re-stamps and, where a
machine-readable feed exists (iCalendar / Legistar Web API), live-refreshes the list. Where there is
no feed, it shows the verified snapshot + a link to check the source directly — and says so honestly.
No agenda, date, or meeting is ever invented; an empty list is correct when nothing is confirmed.

Stdlib only (urllib/json/ssl) — no third-party deps, no subprocess, no popup.
Output: reports/mauios/agendas_<id>.html (+ agendas.html index)
"""
import os, json, ssl, urllib.request, urllib.parse, html, re
from datetime import datetime, timezone, timedelta

HOME    = os.path.expanduser("~")
TOOL_DIR= os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.join(HOME, "Documents", "Claude", "Projects", "Video System elementLOTUS")
MAUIOS  = os.path.join(PROJECT, "reports", "mauios")
REG     = os.path.join(TOOL_DIR, "agenda_sources.json")
HST     = timezone(timedelta(hours=-10))
esc     = lambda s: html.escape(str(s or ""))
UA      = {"User-Agent": "12sgi-kilo-aupuni-agenda/1.0 (civic transparency; public record)"}
def now_hst(): return datetime.now(HST)

NAMES = {"state":"State of Hawaiʻi","maui":"Maui County","honolulu":"City & County of Honolulu",
         "hawaii":"Hawaiʻi County","kauai":"Kauaʻi County","nyc":"New York City","nys":"New York State",
         "liverpool":"Village of Liverpool","london":"City of London / Greater London","tokyo":"Tokyo Metropolis",
         "hongkong":"Hong Kong SAR","singapore":"Singapore","zurich":"Zürich","frankfurt":"Frankfurt am Main",
         "paris":"Paris","dubai":"Dubai"}
# cross-nav: which other tenant pages exist to link back to
def xlinks(tid):
    out = []
    for pat, lbl in [("crosswalk_%s.html","charter ⇄ law"), ("money_%s.html","money"), ("parity_%s.html","parity")]:
        fn = pat % tid
        if os.path.exists(os.path.join(MAUIOS, fn)): out.append('<a href="%s">%s</a>' % (fn, lbl))
    out.append('<a href="jurisdictions.html">all jurisdictions</a>')
    return " &middot; ".join(out)

# ── best-effort LIVE refresh (only for real machine-readable feeds) ──────────────────────────
def _get(url, timeout=20):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout, context=ssl.create_default_context()) as r:
        return r.read().decode("utf-8", "replace")

def fetch_ical(url, days=120):
    """Parse VEVENTs from an .ics feed; return upcoming meetings within `days`."""
    txt = _get(url)
    today = now_hst().date()
    out = []
    for blk in re.findall(r"BEGIN:VEVENT(.*?)END:VEVENT", txt, re.S):
        m = re.search(r"\nDTSTART[^:]*:([0-9T]+)", blk)
        s = re.search(r"\nSUMMARY[^:]*:(.+)", blk)
        u = re.search(r"\nURL[^:]*:(.+)", blk)
        if not m: continue
        raw = m.group(1).strip()
        try:
            d = datetime.strptime(raw[:8], "%Y%m%d").date()
        except ValueError:
            continue
        if today <= d <= today + timedelta(days=days):
            out.append({"date": d.isoformat(), "body": "", "title": (s.group(1).strip() if s else "Meeting"),
                        "url": (u.group(1).strip() if u else url)})
    out.sort(key=lambda x: x["date"])
    return out[:20]

def fetch_legistar(client, days=120):
    """Legistar Web API: upcoming Events for a client (e.g. 'nyc')."""
    iso = now_hst().strftime("%Y-%m-%dT00:00:00")
    q = urllib.parse.urlencode({"$orderby": "EventDate", "$top": "20",
                                "$filter": "EventDate ge datetime'%s'" % iso})
    rows = json.loads(_get("https://webapi.legistar.com/v1/%s/Events?%s" % (client, q)))
    out = []
    for r in rows:
        d = (r.get("EventDate") or "")[:10]
        if not d: continue
        out.append({"date": d, "body": r.get("EventBodyName", ""),
                    "title": (r.get("EventComment") or r.get("EventBodyName") or "Meeting"),
                    "url": r.get("EventInSiteURL", "")})
    return out[:20]

def live_refresh(src):
    """Return (meetings, ok). Never raises — falls back to the verified snapshot."""
    ft, feed = src.get("feed_type"), src.get("feed_url") or ""
    try:
        if ft == "ical" and feed:
            r = fetch_ical(feed); return (r, True) if r else ([], False)
        if ft == "legistar_api":
            mm = re.search(r"/v1/([a-z0-9_-]+)/", feed) or re.search(r"legistar\.com/([a-z0-9_-]+)", feed)
            client = mm.group(1) if mm else src.get("tenant_id")
            r = fetch_legistar(client); return (r, True) if r else ([], False)
    except Exception:
        return ([], False)
    return ([], False)

def meeting_row(mt):
    when = esc(mt.get("date", "")); body = esc(mt.get("body", "")); title = esc(mt.get("title", "Meeting"))
    url = mt.get("url", "")
    t = '<a href="%s" target="_blank" rel="noopener">%s</a>' % (esc(url), title) if url else title
    return '<div class="mt"><span class="md">%s</span><span class="mb">%s</span><span class="mtt">%s</span></div>' % (
        when or "—", (" · " + body) if body else "", t)

def build(src):
    tid = src["tenant_id"]; name = NAMES.get(tid, tid)
    g = now_hst().strftime("%Y-%m-%d %H:%M HST")
    live, ok = live_refresh(src)
    meetings = live if ok else (src.get("upcoming") or [])
    mode = "live feed" if ok else ("verified snapshot" if meetings else "no meetings posted / source check needed")
    rows = "".join(meeting_row(m) for m in meetings) or '<div class="none">No upcoming meetings confirmed in the published window. Use the source link to check directly.</div>'
    conf_badge = ('<span class="cf v">source verified</span>' if src.get("conf") == "v"
                  else '<span class="cf p">source identified · daily checker pending</span>')
    src_link = ('<a href="%s" target="_blank" rel="noopener">%s &#8599;</a>' % (esc(src["source_url"]), esc(src.get("agenda_system") or "official source"))
                if src.get("source_url") else esc(src.get("agenda_system") or "source pending"))
    feed_line = ("Machine-readable feed: <b>%s</b> — refreshed automatically each day." % esc(src["feed_type"]) if src.get("feed_type") not in (None, "", "none", "html")
                 else "No machine-readable feed found — the daily checker re-checks the source page and re-stamps; meetings shown are the last verified snapshot.")
    return """<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Agendas — %s — govOS · Kilo Aupuni</title>
<style>
 body{margin:0;background:#0c100e;color:#e8e4d8;font-family:Georgia,'Iowan Old Style',serif;line-height:1.6}
 .wrap{max-width:860px;margin:0 auto;padding:30px 22px 70px}
 .eyebrow{font-family:Consolas,monospace;font-size:11px;letter-spacing:1.4px;color:#d9b24c;text-transform:uppercase}
 h1{font-size:27px;font-weight:600;margin:8px 0 4px}
 .lead{font-size:14px;color:#cfc9b6;max-width:78ch}
 .meta{font-family:Consolas,monospace;font-size:11.5px;color:#9a957f;margin:10px 0}
 .meta b{color:#cfc9b6}
 .cf{font-family:Consolas,monospace;font-size:9.5px;letter-spacing:.4px;padding:1px 7px;border-radius:8px}
 .cf.v{background:rgba(86,192,138,.14);color:#56c08a} .cf.p{background:rgba(224,106,74,.14);color:#e06a4a}
 .checked{font-family:Consolas,monospace;font-size:11px;color:#9fd9bf;border:1px solid rgba(159,217,191,.3);border-radius:9px;padding:8px 12px;margin:14px 0;display:inline-block}
 .mt{display:flex;gap:8px;align-items:baseline;border-bottom:1px solid rgba(255,255,255,.07);padding:9px 2px;flex-wrap:wrap}
 .md{font-family:Consolas,monospace;font-size:12.5px;color:#d9b24c;min-width:96px}
 .mb{font-size:12px;color:#9a957f} .mtt{font-size:13.5px;color:#e8e4d8;flex:1;min-width:200px} .mtt a{color:#e8e4d8}
 .none{font-size:13px;color:#9a957f;font-style:italic;padding:12px 0}
 .disc{font-size:12px;color:#9a957f;font-style:italic;border-left:2px solid rgba(217,178,76,.4);padding:7px 12px;margin:16px 0}
 a{color:#d9b24c}
 footer{margin-top:30px;border-top:1px solid rgba(255,255,255,.1);padding-top:12px;font-family:Consolas,monospace;font-size:10.5px;color:#9a957f}
</style></head><body><div class="wrap">
<div class="eyebrow">12 Stones Global &middot; Kilo Aupuni &middot; %s &middot; agendas</div>
<h1>Agendas &mdash; %s</h1>
<p class="lead">Know what is being decided <b>before</b> it is decided. Upcoming public meetings as far
ahead as this government posts them &mdash; so the community can show up, testify, and participate in time.</p>
<div class="meta">Source: %s &nbsp;%s<br>Horizon: <b>%s</b> &middot; showing: <b>%s</b></div>
<div class="checked">&#10003; last checked %s &middot; daily</div>
<div>%s</div>
<div class="disc">%s Note: %s</div>
<p style="margin-top:14px">%s</p>
<footer>generated %s &middot; agenda-watch v1 &middot; daily checker (CI cron + local task) &middot; source: official %s agenda system &middot; Kilo Aupuni &middot; aloha &middot; pono</footer>
</div></body></html>""" % (
        esc(name), esc(name), esc(name), src_link, conf_badge, esc(src.get("horizon") or "unknown"),
        esc(mode), g, rows, feed_line,
        esc(src.get("note") or ""), xlinks(tid), g, esc(name))

def index(srcs):
    g = now_hst().strftime("%Y-%m-%d %H:%M HST")
    rows = ""
    for s in srcs:
        tid = s["tenant_id"]; nm = NAMES.get(tid, tid)
        rows += '<a class="jrow" href="agendas_%s.html"><span class="jn">%s</span><span class="js">%s &middot; %s</span></a>' % (
            tid, esc(nm), esc(s.get("agenda_system") or "source pending"), esc(s.get("feed_type") or "—"))
    return """<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Agendas — every govOS tenant</title><style>
 body{margin:0;background:#0c100e;color:#e8e4d8;font-family:Georgia,serif;line-height:1.6}
 .wrap{max-width:860px;margin:0 auto;padding:30px 22px 70px}
 .eyebrow{font-family:Consolas,monospace;font-size:11px;letter-spacing:1.4px;color:#d9b24c;text-transform:uppercase}
 h1{font-size:26px;margin:8px 0 6px} .lead{font-size:14px;color:#cfc9b6}
 .jrow{display:flex;justify-content:space-between;gap:10px;align-items:baseline;text-decoration:none;color:inherit;border-bottom:1px solid rgba(255,255,255,.08);padding:11px 4px}
 .jrow:hover{background:rgba(217,178,76,.05)} .jn{font-size:15px;font-weight:600} .js{font-family:Consolas,monospace;font-size:11px;color:#9a957f}
 a{color:#d9b24c} footer{margin-top:24px;font-family:Consolas,monospace;font-size:10.5px;color:#9a957f}
</style></head><body><div class="wrap">
<div class="eyebrow">12 Stones Global &middot; Kilo Aupuni &middot; agendas</div>
<h1>Agendas &mdash; every govOS tenant</h1>
<p class="lead">Each government's upcoming public meetings, as far ahead as posted, checked daily. Pick a jurisdiction.</p>
<div style="margin-top:14px">%s</div>
<p style="margin-top:16px"><a href="jurisdictions.html">&larr; all jurisdictions</a></p>
<footer>generated %s &middot; agenda-watch index &middot; Kilo Aupuni</footer></div></body></html>""" % (rows, g)

def main():
    os.makedirs(MAUIOS, exist_ok=True)
    if not os.path.exists(REG):
        print("! agenda_sources.json not found — run the agenda-discovery workflow first"); return 1
    srcs = json.load(open(REG, encoding="utf-8")).get("sources", [])
    live_n = 0
    for s in srcs:
        open(os.path.join(MAUIOS, "agendas_%s.html" % s["tenant_id"]), "w", encoding="utf-8", newline="\n").write(build(s))
        _, ok = live_refresh(s); live_n += 1 if ok else 0
    open(os.path.join(MAUIOS, "agendas.html"), "w", encoding="utf-8", newline="\n").write(index(srcs))
    print("agenda-watch: %d tenant pages + index; %d live-feed refreshed this run" % (len(srcs), live_n))
    return 0

if __name__ == "__main__":
    import sys; sys.exit(main())
