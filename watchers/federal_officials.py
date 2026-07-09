#!/usr/bin/env python3
# federal_officials.py - the FEDERAL layer of Maui's governance chain (Jimmy 2026-06-16: "up through the
# federal chain"). Sources Hawaiʻi's current Congressional delegation from the maintained public dataset
# (unitedstates.github.io/congress-legislators — no key) and builds the federal "Who governs" page: the two
# U.S. Senators + the two U.S. House members, flagging HI-02 (Jill Tokuda) as Maui's representative.
# Ties to the federal-money lens (federal_money.html) — who represents Maui where the federal dollars decide.
# INTEGRITY: facts + the official source link only. Sourced, never invented. Stdlib only.
import os, sys, json, urllib.request
from datetime import datetime, timedelta, timezone
HST=timezone(timedelta(hours=-10))
HOME=os.path.expanduser("~"); PROJ=os.path.join(HOME,"Documents","Claude","Projects","Video System elementLOTUS")
M=os.path.join(PROJ,"reports","mauios"); DISPATCH=os.path.join(PROJ,".dispatch_log.jsonl")
SRC="https://unitedstates.github.io/congress-legislators/legislators-current.json"
HTML=os.path.join(M,"federal_officials.html"); JSONF=os.path.join(M,"federal_officials.json")
def esc(s): return str(s if s is not None else "").replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
def now(): return datetime.now(HST)

def fetch_hi():
    req=urllib.request.Request(SRC,headers={"User-Agent":"12sgi-kilo-aupuni/1.0 civic-transparency"})
    with urllib.request.urlopen(req,timeout=40) as r: data=json.loads(r.read().decode())
    out=[]
    for m in data:
        terms=m.get("terms") or []
        if not terms: continue
        t=terms[-1]
        if t.get("state")!="HI": continue
        if str(t.get("end","")) < "2026-01-01": continue   # current
        nm=m.get("name",{}); ids=m.get("id",{})
        out.append({"name":("%s %s"%(nm.get("first",""),nm.get("last",""))).strip(),
            "type":t.get("type"),"district":t.get("district"),"party":t.get("party"),
            "start":t.get("start"),"end":t.get("end"),"url":t.get("url") or "",
            "phone":t.get("phone") or "","office":t.get("office") or "",
            "represents_maui": (t.get("type")=="sen") or (t.get("type")=="rep" and str(t.get("district"))=="2"),
            "bioguide":ids.get("bioguide","")})
    # senators first, then reps by district
    out.sort(key=lambda x:(0 if x["type"]=="sen" else 1, x.get("district") or 0))
    return out

def main():
    try: mem=fetch_hi()
    except Exception as e:
        with open(DISPATCH,"a",encoding="utf-8") as f:
            f.write(json.dumps({"ts":int(now().timestamp()),"iso":now().strftime("%Y-%m-%d %H:%M:%S"),
                "source":"kilo-aupuni","event":"FINDING: federal_officials fetch failed: %s"%e},ensure_ascii=False)+"\n")
        print("federal_officials: fetch failed:",e); return 1
    gen=now().strftime("%Y-%m-%d %H:%M HST")
    json.dump({"generated":gen,"source":SRC,"state":"HI","members":mem},
              open(JSONF,"w",encoding="utf-8"),indent=1,ensure_ascii=False)
    def card(x):
        seat=("U.S. Senator" if x["type"]=="sen" else "U.S. Representative · HI-%s"%x.get("district"))
        maui=("<span class=maui>represents Maui</span>" if x["represents_maui"] else "")
        link=(" · <a href='%s'>official office</a>"%esc(x["url"])) if x["url"] else ""
        party={"Democrat":"D","Republican":"R"}.get(x.get("party",""),esc(x.get("party","")))
        return ("<div class=off><div class=oh><h2>%s</h2>%s</div><div class=seat>%s · %s%s</div>"
                "<div class=meta>term %s &ndash; %s%s</div></div>")%(
                esc(x["name"]),maui,esc(seat),party,link,esc(x.get("start","")),esc(x.get("end","")),
                (" · "+esc(x["phone"])) if x["phone"] else "")
    body="".join(card(x) for x in mem)
    html=("<!doctype html><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'>"
      "<title>Federal — who governs Maui in Washington | govOS</title><style>"
      "body{font-family:'Segoe UI',system-ui,sans-serif;max-width:920px;margin:1.3rem auto;padding:0 1rem;color:#13243d;background:#fff}"
      "h1{font-size:1.5rem;margin:.3rem 0}.sub{color:#41536b;font-size:.9rem;line-height:1.5}"
      ".off{background:#e7eef8;border:1px solid #1f3d5f;border-radius:12px;padding:.7rem 1rem;margin:.7rem 0}"
      ".oh{display:flex;align-items:center;gap:10px}.oh h2{font-size:1.05rem;margin:.2rem 0;color:#00356b}"
      ".maui{font-size:10px;letter-spacing:.5px;text-transform:uppercase;font-weight:700;color:#1f8a5b;background:rgba(31,138,91,.13);border-radius:99px;padding:3px 9px}"
      ".seat{font-size:.85rem;color:#1259a3;font-family:Consolas,monospace}.meta{font-size:.8rem;color:#6d7f97;margin-top:3px}a{color:#1259a3}"
      ".disc{background:#0f2540;border:1px solid #1f3d5f;border-radius:10px;padding:.7rem 1rem;color:#41536b;font-size:.85rem;margin:.8rem 0}</style>"
      "<h1>Federal — who governs Maui in Washington</h1>"
      "<div class=sub>The top of the chain over Maui County: Hawaiʻi&rsquo;s U.S. Senate + House delegation. "
      "Maui is in the 2nd Congressional District (HI-02). These are the federal deciders where the "
      "<a href='federal_money.html'>federal dollars</a> are set. Source: "
      "<a href='%s'>congress-legislators</a> (public) · generated %s.</div>"
      "<div class=disc>Public record, presented as facts. Who represents you federally, and where the federal "
      "money is decided &mdash; offered so any neighbor can follow the chain from the county up.</div>%s"
      "<p class=sub style='margin-top:1rem'><a href='tenant_hi-state.html'>&larr; State of Hawaiʻi</a> &middot; "
      "<a href='federal_money.html'>federal dollars</a> &middot; <a href='tenants_hub.html'>all governments</a></p>")%(
      esc(SRC),esc(gen),body)
    with open(HTML,"w",encoding="utf-8",newline="\n") as f: f.write(html)
    with open(DISPATCH,"a",encoding="utf-8") as f:
        f.write(json.dumps({"ts":int(now().timestamp()),"iso":now().strftime("%Y-%m-%d %H:%M:%S"),
            "source":"kilo-aupuni","event":"SHIPPED: federal_officials sourced HI delegation (%d) -> federal_officials.html"%len(mem)},ensure_ascii=False)+"\n")
    print("federal_officials: %d HI members -> reports/mauios/federal_officials.html"%len(mem))
    for x in mem: print("  %-20s %s%s"%(x["name"],x["type"].upper(),(" HI-%s"%x["district"]) if x.get("district") else ""))
    return 0

if __name__=="__main__":
    if sys.platform=="win32":
        import io; sys.stdout=io.TextIOWrapper(sys.stdout.buffer,encoding="utf-8",errors="replace")
    sys.exit(main())
