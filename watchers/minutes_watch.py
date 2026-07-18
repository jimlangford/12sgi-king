#!/usr/bin/env python3
# minutes_watch.py - "the people's record" for every govOS tenant (Jimmy 2026-06-16: minutes data for each
#   tenant to make the private work IRON-CLAD and the public face DIGNIFIED). Reads the verified source
#   registry (agenda_sources.json) and, per tenant's REAL platform, harvests the published meeting record:
#     - CivicClerk (Maui): reuse the deep minutes already ingested by votes_watch.py (roll-call evidence).
#     - Legistar API:      Events -> EventMinutesStatus + EventMinutesFile (the finalized minutes doc).
#     - Granicus RSS:      the archived meeting list (date/body/link to the official record).
#     - iCal/HTML/token-gated: honest "official source identified; deep ingestion building" + the real link.
#   INTEGRITY: nothing is ever invented. No record -> an honest empty state, never a fabricated meeting.
#   Output: PRIVATE reports/_status/minutes/index_<tid>.jsonl (evidence spine the prosecutor can cite)
#           PUBLIC  reports/mauios/minutes_<tid>.html  (dignified, fully sourced)
#   Stdlib only (urllib/ssl/json/re) - no popup, no third-party deps.
import os, sys, json, ssl, re, urllib.request, urllib.parse
from datetime import datetime, timedelta, timezone

HOME = os.path.expanduser("~")
TOOL = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.join(HOME, "Documents", "Claude", "Projects", "Video System elementLOTUS")
M = os.path.join(PROJECT, "reports", "mauios")
PRIV = os.path.join(PROJECT, "reports", "_status", "minutes")
REG = os.path.join(TOOL, "agenda_sources.json")
VOTES_IDX = os.path.join(M, "votes_index.jsonl")
HST = timezone(timedelta(hours=-10))
UA = {"User-Agent": "12sgi-kilo-aupuni-minutes/1.0 (civic transparency; public record)"}
CORE = {"hi-maui":"Maui County","hi-state":"State of Hawaiʻi","hi-hawaii":"Hawaiʻi County",
        "hi-kauai":"Kauaʻi County","hi-honolulu":"Honolulu","ny":"New York"}

def esc(s): return str(s or "").replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
def get_text(u, t=25):
    return urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=t,
                                  context=ssl.create_default_context()).read().decode("utf-8","replace")
def get_json(u, t=25): return json.loads(get_text(u, t))

def from_legistar(feed_url):
    """Past meetings + their finalized minutes file, if the client is open (some need a token -> 403)."""
    m = re.search(r"/v1/([a-z0-9_-]+)/", feed_url) or re.search(r"legistar\.com/([a-z0-9_-]+)", feed_url)
    if not m: return None, "no legistar client in feed url"
    client = m.group(1)
    q = urllib.parse.urlencode({"$orderby": "EventDate desc", "$top": "30"})
    try:
        rows = get_json("https://webapi.legistar.com/v1/%s/Events?%s" % (client, q))
    except Exception as e:
        return None, ("API token required" if "403" in str(e) else "fetch error: %s" % str(e)[:60])
    recs = []
    for r in rows:
        recs.append({"date": str(r.get("EventDate") or "")[:10], "body": r.get("EventBodyName") or "Meeting",
                     "minutes_status": r.get("EventMinutesStatusName"),
                     "minutes_url": r.get("EventMinutesFile") or "",
                     "source": r.get("EventInSiteURL") or feed_url})
    return recs, None

def from_granicus_rss(feed_url):
    """Granicus archive RSS = the recorded-meeting list (date/body + link to the official record)."""
    url = feed_url if "mode=" in feed_url else (feed_url + ("&" if "?" in feed_url else "?") + "mode=archive")
    try:
        x = get_text(url)
    except Exception as e:
        return None, "fetch error: %s" % str(e)[:60]
    recs = []
    for it in re.findall(r"<item>(.*?)</item>", x, re.S)[:30]:
        title = re.search(r"<title>(.*?)</title>", it, re.S)
        link = re.search(r"<link>(.*?)</link>", it, re.S)
        ttl = re.sub(r"<!\[CDATA\[|\]\]>", "", title.group(1)).strip() if title else "Meeting"
        d = re.match(r"(\d{4}-\d{2}-\d{2})", ttl)
        recs.append({"date": d.group(1) if d else "", "body": ttl, "minutes_status": "recorded",
                     "minutes_url": (link.group(1).strip() if link else url), "source": url})
    return recs, None

def from_civicclerk_maui():
    """Maui's deep minutes are already ingested by votes_watch.py -> votes_index.jsonl (roll-call evidence)."""
    if not os.path.exists(VOTES_IDX): return None, "votes_index not built yet (run votes_watch.py)"
    recs = []
    for ln in open(VOTES_IDX, encoding="utf-8"):
        ln = ln.strip()
        if not ln: continue
        try: v = json.loads(ln)
        except Exception: continue
        recs.append({"date": str(v.get("date") or "")[:10], "body": v.get("body") or v.get("event") or "Council meeting",
                     "minutes_status": "parsed (roll-call extracted)", "minutes_url": v.get("url") or v.get("source") or "",
                     "source": v.get("url") or ""})
    return recs, None

def harvest(src):
    ft = (src.get("feed_type") or "").lower()
    feed = src.get("feed_url") or src.get("source_url") or ""
    tid = src.get("tenant_id")
    if tid == "hi-maui":
        recs, err = from_civicclerk_maui()
        if recs is not None: return recs, err, "CivicClerk (deep minutes via votes_watch)"
    if ft == "legistar_api":
        recs, err = from_legistar(feed); return recs, err, "Legistar API"
    if ft == "rss":
        recs, err = from_granicus_rss(feed); return recs, err, "Granicus archive"
    return None, "deep ingestion building for this platform", src.get("agenda_system") or "official source"

def page(src, recs, err, sysname):
    tid = src.get("tenant_id"); name = CORE.get(tid, tid)
    surl = src.get("source_url") or src.get("feed_url") or ""
    when = datetime.now(HST).strftime("%Y-%m-%d %H:%M HST")
    n = len(recs) if recs else 0
    with_doc = sum(1 for r in (recs or []) if r.get("minutes_url"))
    if recs:
        rows = ""
        for r in recs[:40]:
            link = r.get("minutes_url") or r.get("source") or surl
            label = "View the record &#8599;" if link else "on file"
            rows += ("<tr><td class=dt>%s</td><td>%s</td><td class=st>%s</td>"
                     "<td>%s</td></tr>" % (esc(r.get("date") or "—"), esc(r.get("body")),
                     esc(r.get("minutes_status") or ""),
                     ('<a href="%s" target=_blank rel=noopener>%s</a>' % (esc(link), label)) if link else "on file"))
        bodyhtml = ("<p class=note>%d recorded meetings from the official source%s. Every entry links to the "
                    "government's own record — read it yourself.</p><table><thead><tr><th>Date</th><th>Body</th>"
                    "<th>Minutes</th><th>Source</th></tr></thead><tbody>%s</tbody></table>" % (
                    n, (" · %d with the minutes document on file" % with_doc) if with_doc else "", rows))
    else:
        bodyhtml = ("<div class=building><b>The record is being gathered.</b><br>%s is identified as the official "
                    "source%s. We publish nothing until it is sourced from there — no meeting, vote, or date is "
                    "ever invented.</div>" % (esc(sysname), (" (%s)" % esc(err)) if err else ""))
    src_link = ('<a href="%s" target=_blank rel=noopener>%s &#8599;</a>' % (esc(surl), esc(sysname))) if surl else esc(sysname)
    html = ("<!doctype html><meta charset=utf-8><title>%s — Meeting minutes | govOS</title><style>"
        "body{font-family:system-ui,Segoe UI,sans-serif;max-width:980px;margin:2.1rem auto;padding:0 1.1rem;color:#eaf2fc}"
        "a{color:#5a97e6;text-decoration:none}a:hover{text-decoration:underline}"
        ".eyebrow{font-size:.72rem;letter-spacing:.16em;text-transform:uppercase;color:#6b7a89}"
        "h1{font-size:1.6rem;margin:.2rem 0 .15rem}.sub{color:#56646f;font-size:.93rem;margin-bottom:1rem}"
        "table{border-collapse:collapse;width:100%%;font-size:.85rem;margin-top:.6rem}"
        "th,td{padding:.45rem .5rem;border-bottom:1px solid #eef2f5;text-align:left;vertical-align:top}"
        "th{color:#42535f;font-size:.74rem;text-transform:uppercase;letter-spacing:.05em}"
        ".dt{white-space:nowrap;color:#42535f}.st{color:#6b7a89;font-size:.8rem}.note{color:#56646f;font-size:.88rem}"
        ".building{background:#0f2540;border:1px dashed #26456a;border-radius:12px;padding:1rem 1.1rem;color:#9fb2c8}"
        "</style>"
        "<div class=eyebrow><a href='tenants_hub.html'>govOS</a> · %s</div>"
        "<h1>%s — the public record</h1>"
        "<div class=sub>Meeting minutes are where decisions become accountable: who moved, who voted, what carried. "
        "This is %s's own record, presented with dignity and linked to the source — facts for oversight, never "
        "accusation. Source: %s.</div>%s"
        "<p class=sub style='margin-top:1.2rem'><a href='%s'>← %s overview</a> · "
        "<a href='tenants_hub.html'>all governments</a> · generated %s</p>" % (
        esc(name), esc(name), esc(name), esc(name), src_link, bodyhtml,
        esc(_TENANT_PAGE.get(tid, "tenant_%s.html" % tid)), esc(name), esc(when)))
    os.makedirs(M, exist_ok=True)
    open(os.path.join(M, "minutes_%s.html" % tid), "w", encoding="utf-8").write(html)
    # PRIVATE evidence spine
    os.makedirs(PRIV, exist_ok=True)
    with open(os.path.join(PRIV, "index_%s.jsonl" % tid), "w", encoding="utf-8") as f:
        for r in (recs or []):
            f.write(json.dumps({**r, "tenant": tid}, ensure_ascii=False) + "\n")
    return {"tenant": tid, "name": name, "records": n, "with_doc": with_doc, "system": sysname, "note": err}

REGMAP = {"hi-maui":"maui","hi-state":"state","hi-hawaii":"hawaii","hi-kauai":"kauai","hi-honolulu":"honolulu","ny":"nyc"}
# tenant_ny.html doesn't exist (there's tenant_nyc.html + tenant_nys.html); link to hub instead
_TENANT_PAGE = {"ny": "tenants_hub.html"}

def main():
    reg = json.load(open(REG, encoding="utf-8"))
    srcs = reg.get("sources", reg) if isinstance(reg, dict) else reg
    by_reg = {s.get("tenant_id"): s for s in srcs if isinstance(s, dict)}
    results = []
    for tid in CORE:
        src = dict(by_reg.get(REGMAP[tid], {})); src["tenant_id"] = tid   # canonical id for filenames + Maui check
        try:
            recs, err, sysname = harvest(src)
        except Exception as e:
            recs, err, sysname = None, "error: %s" % str(e)[:80], src.get("agenda_system") or "source"
        results.append(page(src, recs, err, sysname))
    print("minutes_watch: %d tenants" % len(results))
    for r in results:
        print("  %-16s %3d records (%d w/ doc) · %s%s" % (
            r["name"], r["records"], r["with_doc"], r["system"], (" — " + r["note"]) if r["note"] and not r["records"] else ""))
    json.dump({"generated": datetime.now(HST).strftime("%Y-%m-%d %H:%M HST"), "tenants": results},
              open(os.path.join(PROJECT, "reports", "_status", "minutes_summary.json"), "w", encoding="utf-8"),
              indent=1, ensure_ascii=False)
    return 0

if __name__ == "__main__":
    if sys.platform == "win32":
        import io; sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(main())
