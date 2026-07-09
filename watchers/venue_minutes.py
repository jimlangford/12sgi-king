#!/usr/bin/env python3
# venue_minutes.py - the CURSE-BREAKER, generalized to ALL venues (Jimmy 2026-06-16: "selfheal this process
#   for all venues ... like a curse breaker"). THE CURSE: concluding "no dissent data" from one empty API
#   layer (EventMinutesFile / Votes API). THE BREAKER: for every venue, TEST THE ACTUAL DOCUMENT PATH (the
#   human meeting page) before ever concluding inaccessible. This probes each venue's real minutes document
#   path per platform and reports reachability, so no venue stays falsely "cursed". Self-healing: re-runs
#   each cycle; a venue that newly publishes minutes flips to reachable on its own.
#     Legistar  -> event -> EventInSiteURL meeting page -> scrape View.ashx?M=M  (proven on Maui)
#     Granicus  -> archive RSS -> meeting page -> MinutesViewer/.pdf link
#     CivicClerk-> GetMeetingFileStream (votes_watch path)
#     other/token-gated -> honest 'method-not-yet-mapped' / 'blocked' (NOT 'no data')
#   Output: reports/_status/venue_minutes.{json,html}. Stdlib only. PRIVATE/internal status surface.
import os, sys, json, ssl, re, urllib.request, urllib.parse
from datetime import datetime, timedelta, timezone

HOME = os.path.expanduser("~")
TOOL = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.join(HOME, "Documents", "Claude", "Projects", "Video System elementLOTUS")
OUT = os.path.join(PROJECT, "reports", "_status")
REG = os.path.join(TOOL, "agenda_sources.json")
HST = timezone(timedelta(hours=-10))
UA = {"User-Agent": "Mozilla/5.0 12sgi-kilo-aupuni/1.0 (civic transparency; public record)"}

def gt(u, t=35):
    return urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=t, context=ssl.create_default_context()).read().decode("utf-8", "replace")
def jj(u, t=35): return json.loads(gt(u, t))

def probe_legistar(feed_url):
    m = re.search(r"/v1/([a-z0-9_-]+)/", feed_url) or re.search(r"legistar\.com/([a-z0-9_-]+)", feed_url)
    if not m: return ("unknown", "no legistar client", None)
    client = m.group(1)
    try:
        rows = jj("https://webapi.legistar.com/v1/%s/Events?%s" % (client,
                  urllib.parse.urlencode({"$orderby": "EventDate desc", "$top": "120"})))
    except Exception as e:
        return ("blocked", "API token required" if "403" in str(e) else "api error", None)
    finals = [r for r in rows if r.get("EventMinutesStatusName") == "Final" and r.get("EventInSiteURL")]
    for e in finals[:8]:                       # THE BREAKER: test the actual meeting page, not the API field
        try: html = gt(e["EventInSiteURL"])
        except Exception: continue
        mm = re.search(r'View\.ashx\?M=M&[^"\'<> ]+', html)
        if mm:
            return ("reachable", "Legistar meeting-page M=M scrape -> PDF", "https://%s.legistar.com/%s" % (client, mm.group(0).replace("&amp;", "&")))
    return ("not-cracked", "Legistar client open; no M=M on sampled finals (older mtgs may have them)", None)

def probe_granicus(feed_url):
    # CURSE-BREAKER chain (cracked on Honolulu 2026-06-16): Granicus is JS — follow RSS clip -> MinutesViewer
    # -> scrape the doc portal link (e.g. hnldoc.ehawaii.gov/.../document-download?id=N) -> a real PDF.
    sub = re.search(r"https?://([a-z0-9\-]+)\.granicus\.com", feed_url, re.I)
    sub = sub.group(1) if sub else None
    url = feed_url if "mode=" in feed_url else feed_url + ("&" if "?" in feed_url else "?") + "mode=archive"
    try: x = gt(url)
    except Exception as e: return ("not-cracked", "RSS error: %s" % str(e)[:40], None)
    for it in re.findall(r"<item>(.*?)</item>", x, re.S)[:6]:
        clip = re.search(r"clip_id=(\d+)", it)
        if not (clip and sub): continue
        try:
            mv = gt("https://%s.granicus.com/MinutesViewer.php?view_id=%s&clip_id=%s" % (
                sub, (re.search(r"view_id=(\d+)", feed_url) or re.search(r"view_id=(\d+)", it) or [None, "1"])[1], clip.group(1)))
        except Exception:
            continue
        # any external doc portal that serves the minutes document
        doc = re.search(r'(https?://[a-z0-9.\-]+/[^"\']*document-download\?id=\d+)', mv, re.I) \
              or re.search(r'([a-z0-9.\-]+\.gov)/[^"\']*document-download\?id=\d+', mv, re.I)
        host = re.search(r'(https?://[a-z0-9.\-]+\.ehawaii\.gov)', mv) or re.search(r'(https?://[a-z0-9.\-]+\.gov)/\w+/document', mv)
        if "document-download" in mv:
            base = (host.group(1) if host else "")
            return ("reachable", "Granicus->MinutesViewer->doc portal (%s/.../document-download?id=N) -> PDF" % (base or "gov doc portal"),
                    (base + "/.../document-download?id=N") if base else None)
    return ("not-cracked", "Granicus archive reached; MinutesViewer doc-portal link not located yet (per-county portal differs)", None)

def probe(src):
    ft = (src.get("feed_type") or "").lower()
    feed = src.get("feed_url") or src.get("source_url") or ""
    tid = src.get("tenant_id")
    if tid == "maui":                          # CivicClerk full-council already harvested (votes_watch)
        return ("reachable", "CivicClerk GetMeetingFileStream (council, via votes_watch) + Legistar M=M (committees)", None)
    if ft == "legistar_api": return probe_legistar(feed)
    if ft == "rss":         return probe_granicus(feed)
    return ("method-not-yet-mapped", "%s — document path not yet adapted (do NOT read as 'no data')" % (src.get("agenda_system") or ft), None)

CORE = ["state", "maui", "honolulu", "hawaii", "kauai", "nyc"]

def main():
    reg = json.load(open(REG, encoding="utf-8"))
    srcs = reg.get("sources", reg) if isinstance(reg, dict) else reg
    by = {s.get("tenant_id"): s for s in srcs if isinstance(s, dict)}
    only = sys.argv[1:] or CORE
    rows = []
    for tid in only:
        src = by.get(tid) or {"tenant_id": tid}
        try: status, method, sample = probe(src)
        except Exception as e: status, method, sample = ("error", str(e)[:60], None)
        rows.append({"venue": tid, "system": src.get("agenda_system") or src.get("feed_type"),
                     "minutes_reachable": status, "method": method, "sample": sample})
    reach = sum(1 for r in rows if r["minutes_reachable"] == "reachable")
    payload = {"generated": datetime.now(HST).strftime("%Y-%m-%d %H:%M HST"),
               "principle": "CURSE-BREAKER: test the actual document path before concluding inaccessible; an empty API field != unavailable data.",
               "reachable": reach, "venues": len(rows), "rows": rows}
    os.makedirs(OUT, exist_ok=True)
    json.dump(payload, open(os.path.join(OUT, "venue_minutes.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    _html(payload)
    print("venue_minutes (curse-breaker across venues): %d/%d reachable" % (reach, len(rows)))
    for r in rows:
        print("  %-10s %-18s %s" % (r["venue"], r["minutes_reachable"], r["method"]))
    return 0

def _esc(s): return str(s or "").replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
def _html(p):
    c = {"reachable":"#1f9d55","not-cracked":"#d9822b","method-not-yet-mapped":"#8b6fc0","blocked":"#c0392b","error":"#c0392b"}
    rows = "".join("<tr><td>%s</td><td class=m>%s</td><td style='color:%s;font-weight:700'>%s</td><td class=m>%s</td></tr>" % (
        _esc(r["venue"]), _esc(r["system"]), c.get(r["minutes_reachable"],"#999"), _esc(r["minutes_reachable"]), _esc(r["method"])) for r in p["rows"])
    html = ("<!doctype html><meta charset=utf-8><meta http-equiv=refresh content=600><title>Minutes reachability — curse-breaker</title>"
        "<style>body{font-family:system-ui,Segoe UI,sans-serif;max-width:940px;margin:1.4rem auto;padding:0 1rem;background:#0d1117;color:#e6edf3}"
        "h1{font-size:1.3rem}.sub{color:#8b949e;font-size:.85rem}table{border-collapse:collapse;width:100%%;font-size:.85rem}"
        "td,th{padding:.45rem .55rem;border-bottom:1px solid #21262d;text-align:left}.m{color:#8b949e}</style>"
        "<h1>Minutes reachability across venues <span class=sub>the curse-breaker, self-healing</span></h1>"
        "<div class=sub>%s<br>%d of %d venues confirmed reachable. 'not-cracked' / 'method-not-yet-mapped' = work to do, "
        "NOT 'no data'. Re-runs each cycle; a venue that starts publishing minutes flips to reachable on its own.</div>"
        "<table><thead><tr><th>venue</th><th>system</th><th>minutes</th><th>method / status</th></tr></thead><tbody>%s</tbody></table>" % (
        _esc(p["principle"]), p["reachable"], p["venues"], rows))
    open(os.path.join(OUT, "venue_minutes.html"), "w", encoding="utf-8").write(html)

if __name__ == "__main__":
    if sys.platform == "win32":
        import io; sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(main())
