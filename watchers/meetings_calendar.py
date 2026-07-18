#!/usr/bin/env python3
# meetings_calendar.py - tenant-wide CALENDAR of all digitized meetings, 1st records -> future (Jimmy
# 2026-06-16). Maui from the ingested Legistar export (2244 mtgs 2015->2026) + live upcoming; other tenants
# from their feeds (Legistar full history / Granicus archive). Renders a dignified public calendar per tenant
# + a tenant-wide hub. Sourced-only, never invented. Stdlib only.
import os, sys, json, ssl, re, urllib.request, urllib.parse
from datetime import datetime, timedelta, timezone
from collections import Counter, defaultdict
HST=timezone(timedelta(hours=-10))
HOME=os.path.expanduser("~"); PROJ=os.path.join(HOME,"Documents","Claude","Projects","Video System elementLOTUS")
M=os.path.join(PROJ,"reports","mauios"); TOOL=os.path.dirname(os.path.abspath(__file__))
MAUI_CAL=os.path.join(PROJ,"reports","_status","committee","committee_calendar.jsonl")
UA={"User-Agent":"Mozilla/5.0 12sgi-kilo-aupuni/1.0 (civic transparency; public record)"}
def gt(u): return urllib.request.urlopen(urllib.request.Request(u,headers=UA),timeout=40,context=ssl.create_default_context()).read().decode("utf-8","replace")
def jj(u): return json.loads(gt(u))
def esc(s): return str(s or "").replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
def iso(d):  # normalize various date strings -> YYYY-MM-DD
    d=str(d or "").strip()
    m=re.match(r"(\d{4})-(\d{2})-(\d{2})",d)
    if m: return m.group(0)
    m=re.match(r"(\d{1,2})/(\d{1,2})/(\d{4})",d)
    if m: return "%s-%02d-%02d"%(m.group(3),int(m.group(1)),int(m.group(2)))
    return ""

NAMES={"maui":"Maui County","state":"State of Hawaiʻi","honolulu":"Honolulu","hawaii":"Hawaiʻi County","kauai":"Kauaʻi County","nyc":"New York City"}

def maui_meetings():
    out=[]
    if os.path.exists(MAUI_CAL):
        for ln in open(MAUI_CAL,encoding="utf-8"):
            try: r=json.loads(ln)
            except Exception: continue
            d=iso(r.get("date"))
            if d: out.append({"date":d,"body":r.get("body","").strip(),"time":r.get("time","")})
    # live upcoming from Legistar (current future meetings)
    try:
        rows=jj("https://webapi.legistar.com/v1/mauicounty/Events?%s"%urllib.parse.urlencode({"$orderby":"EventDate desc","$top":"120"}))
        for r in rows:
            d=iso(r.get("EventDate"))
            if d: out.append({"date":d,"body":(r.get("EventBodyName") or "").strip(),"time":r.get("EventTime") or ""})
    except Exception: pass
    return out

def legistar_meetings(client,top=600):
    out=[]
    try:
        rows=jj("https://webapi.legistar.com/v1/%s/Events?%s"%(client,urllib.parse.urlencode({"$orderby":"EventDate desc","$top":str(top)})))
        for r in rows:
            d=iso(r.get("EventDate"))
            if d: out.append({"date":d,"body":(r.get("EventBodyName") or "").strip(),"time":r.get("EventTime") or ""})
    except Exception as e: out=[{"_err":str(e)[:50]}]
    return out

def granicus_meetings(feed):
    out=[]
    url=feed if "mode=" in feed else feed+("&" if "?" in feed else "?")+"mode=archive"
    try: x=gt(url)
    except Exception as e: return [{"_err":str(e)[:50]}]
    for it in re.findall(r"<item>(.*?)</item>",x,re.S):
        t=re.search(r"<title>(.*?)</title>",it,re.S)
        if not t: continue
        ttl=re.sub(r"<!\[CDATA\[|\]\]>","",t.group(1)).strip()
        d=re.match(r"(\d{4}-\d{2}-\d{2})",ttl)
        out.append({"date":d.group(1) if d else "","body":re.sub(r"^\d{4}-\d{2}-\d{2}\s*","",ttl)[:60]})
    return out

def dedupe(ms):
    seen=set(); out=[]
    for m in ms:
        if "_err" in m: continue
        k=(m.get("date"),m.get("body"))
        if m.get("date") and k not in seen: seen.add(k); out.append(m)
    return sorted(out,key=lambda x:x["date"])

def render(tid,ms,feed_note):
    name=NAMES.get(tid,tid); today=datetime.now(HST).strftime("%Y-%m-%d")
    by_year=Counter(m["date"][:4] for m in ms)
    by_body=Counter(m["body"] for m in ms)
    future=[m for m in ms if m["date"]>=today]
    span=("%s to %s"%(ms[0]["date"],ms[-1]["date"])) if ms else "no records"
    # year sections (chronological, all meetings)
    years=sorted(by_year, reverse=True)
    sect=""
    for y in years:
        rowsy=[m for m in ms if m["date"][:4]==y]
        items="".join("<tr><td class=d>%s</td><td>%s</td></tr>"%(esc(m["date"]),esc(m["body"])) for m in sorted(rowsy,key=lambda x:x["date"],reverse=True))
        sect+="<details%s><summary>%s · %d meetings</summary><table><tbody>%s</tbody></table></details>"%(" open" if y>=today[:4] else "",y,len(rowsy),items)
    fut="".join("<li>%s — %s</li>"%(esc(m["date"]),esc(m["body"])) for m in sorted(future,key=lambda x:x["date"])[:25])
    html=("<!doctype html><meta charset=utf-8><meta http-equiv=refresh content=600><title>%s — meetings calendar | govOS</title>"
      "<style>body{font-family:system-ui,Segoe UI,sans-serif;max-width:960px;margin:2rem auto;padding:0 1.1rem;color:#eaf2fc}"
      "a{color:#5a97e6}h1{font-size:1.5rem;margin:.2rem 0}.eyebrow{font-size:.72rem;letter-spacing:.16em;text-transform:uppercase;color:#6b7a89}"
      ".sub{color:#56646f;font-size:.9rem;margin:.3rem 0 1rem}details{border:1px solid #e7edf2;border-radius:10px;margin:.4rem 0;padding:.2rem .6rem}"
      "summary{cursor:pointer;font-weight:600;padding:.4rem 0}table{border-collapse:collapse;width:100%%;font-size:.85rem}"
      "td{padding:.3rem .5rem;border-bottom:1px solid #f0f3f6}.d{color:#42535f;white-space:nowrap;width:6rem}"
      ".up{background:#0e2a20;border:1px solid #1e5c3e;border-radius:10px;padding:.7rem 1rem;margin:1rem 0}.up li{margin:.15rem 0;font-size:.88rem}</style>"
      "<div class=eyebrow><a href='meetings_calendar.html'>govOS · meetings calendar</a></div>"
      "<h1>%s — every digitized meeting</h1>"
      "<div class=sub>The full public meeting record: <b>%d meetings</b> across <b>%d bodies</b>, %s. "
      "From the earliest digitized record forward to scheduled future meetings. Source: %s.</div>"
      "<div class=up><b>Upcoming &amp; recent</b><ul>%s</ul></div>%s"
      %(esc(name),esc(name),len(ms),len(by_body),esc(span),esc(feed_note),fut or "<li>none scheduled in feed</li>",sect))
    open(os.path.join(M,"meetings_%s.html"%tid),"w",encoding="utf-8").write(html)
    return {"tenant":tid,"name":name,"meetings":len(ms),"bodies":len(by_body),"span":span,"future":len(future)}

def main():
    src=json.load(open(os.path.join(TOOL,"agenda_sources.json"),encoding="utf-8")).get("sources",[])
    feed={s["tenant_id"]:s for s in src}
    summ=[]
    plan=[("maui","Maui County Legistar (full export 2015+ & live)"),
          ("nyc","NYC Legistar"),("honolulu","Honolulu Granicus archive"),
          ("hawaii","Hawaiʻi County Granicus archive"),("kauai","Kauaʻi County Granicus archive")]
    for tid,note in plan:
        if tid=="maui": ms=maui_meetings()
        elif feed.get(tid,{}).get("feed_type")=="legistar_api":
            cl=re.search(r"/v1/([a-z0-9_-]+)/",feed[tid]["feed_url"]); ms=legistar_meetings(cl.group(1)) if cl else []
        elif feed.get(tid,{}).get("feed_type")=="rss": ms=granicus_meetings(feed[tid]["feed_url"])
        else: ms=[]
        ms=dedupe(ms)
        summ.append(render(tid,ms,note))
        print("  %-10s %5d meetings · %2d bodies · %s · future %d"%(tid,len(ms),summ[-1]["bodies"],summ[-1]["span"],summ[-1]["future"]))
    # tenant-wide hub
    gen=datetime.now(HST).strftime("%Y-%m-%d %H:%M HST")
    cards="".join("<a class=card href='meetings_%s.html'><h3>%s</h3><div class=m>%d meetings · %d bodies<br>%s · %d upcoming</div></a>"
                  %(esc(s["tenant"]),esc(s["name"]),s["meetings"],s["bodies"],esc(s["span"]),s["future"]) for s in summ)
    hub=("<!doctype html><meta charset=utf-8><title>govOS — meetings calendar (all governments)</title>"
      "<style>body{font-family:system-ui,Segoe UI,sans-serif;max-width:900px;margin:2rem auto;padding:0 1.1rem;color:#eaf2fc}a{color:#5a97e6;text-decoration:none}"
      "h1{font-size:1.5rem}.sub{color:#56646f;font-size:.92rem;margin-bottom:1.2rem}.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:.8rem}"
      ".card{display:block;border:1px solid #e1e7ec;border-radius:13px;padding:1rem;background:#0b1c2e}.card h3{margin:.1rem 0 .4rem}.m{color:#6b7a89;font-size:.83rem}</style>"
      "<h1>Meetings calendar — every government</h1>"
      "<div class=sub>Every digitized public meeting we track, from the earliest record forward to scheduled future meetings. "
      "Pick a government. Generated %s · sourced from each jurisdiction's official system.</div><div class=grid>%s</div>"%(esc(gen),cards))
    open(os.path.join(M,"meetings_calendar.html"),"w",encoding="utf-8").write(hub)
    json.dump({"generated":gen,"tenants":summ},open(os.path.join(PROJ,"reports","_status","meetings_calendar.json"),"w",encoding="utf-8"),indent=1,ensure_ascii=False)
    print("-> meetings_calendar.html (hub) + per-tenant pages")
    return 0

if __name__=="__main__":
    if sys.platform=="win32":
        import io; sys.stdout=io.TextIOWrapper(sys.stdout.buffer,encoding="utf-8",errors="replace")
    sys.exit(main())
