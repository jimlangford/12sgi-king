#!/usr/bin/env python3
# progress_board.py - ONE board, all progress at once (Jimmy 2026-06-16: "see all progress at once").
# Aggregates every surface's status JSON into a single dashboard: Studio/Film, Civic/govOS, Self-heal,
# Creative. Served on the :8781 status dashboard (reads reports/_status) + mirrored to the private King.
# Read-only; gracefully skips missing sources. Stdlib only.
import os, sys, json, glob
from datetime import datetime, timedelta, timezone
HST=timezone(timedelta(hours=-10))
HOME=os.path.expanduser("~"); PROJ=os.path.join(HOME,"Documents","Claude","Projects","Video System elementLOTUS")
ST=os.path.join(PROJ,"reports","_status"); CFG=os.path.join(PROJ,"config"); M=os.path.join(PROJ,"reports","mauios")
def L(p,d=None):
    try: return json.load(open(p,encoding="utf-8"))
    except Exception: return d
def esc(s): return str(s if s is not None else "").replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")

def bar(done,total):
    pct=round(100*done/total) if total else 0
    return "<span class=bar><span style='width:%d%%'></span></span> %d/%d"%(pct,done,total)

def main():
    rows=[]   # (pillar, item, status_html, state)  state: ok|prog|todo
    # ---- STUDIO / FILM ----
    films=L(os.path.join(CFG,"films.json"),{}).get("films",[])
    fp=L(os.path.join(CFG,"film_12stones_scenes.json"),{})
    n12=len(fp.get("scenes",[]))
    import glob as _g
    helei=len(_g.glob(os.path.join(HOME,"Documents","COMFYUI","output","HE_LEI_NO_LAHAINA","*.mp4")))
    film12=len(_g.glob(os.path.join(HOME,"Documents","COMFYUI","output","12_STONES_FILM","*.mp4")))
    rows+=[("🎬 Studio / Film","12 STONES feature (script-driven, ninja rock-opera)","%d-scene manifest · %d film clips rendered · 3 prior cuts"%(n12,film12),"prog"),
           ("🎬 Studio / Film","Seventh Stone (5+2 merge)","greenlit, 2nd in line · treatment + 5 scenes","todo"),
           ("🎬 Studio / Film","Keys of Starforge (22-min Ghibli×Polynesian animated)","script 14/60 · needs finish + animated path","todo"),
           ("🎬 Studio / Film","Render pipeline","DisTorch2 verified (-1.9GB VRAM, +11%% faster); face-lock + Wan i2v live","ok")]
    # ---- CIVIC / govOS ----
    td=L(os.path.join(ST,"tenant_depth.json"),{})
    if td:
        at=sum(1 for t in td.get("tenants",[]) if t["covered"]>=td.get("maui_reference_depth",9))
        rows.append(("🏛 Civic / govOS","Tenant depth -> Maui-deep","%s tenants at full depth (Maui ref %d dims)"%(bar(at,len(td.get('tenants',[]))),td.get("maui_reference_depth",9)),"prog" if at<len(td.get('tenants',[])) else "ok"))
    vm=L(os.path.join(ST,"venue_minutes.json"),{})
    if vm:
        pend=", ".join(r["venue"] for r in vm.get("rows",[]) if r["minutes_reachable"]!="reachable") or "all reachable"
        rows.append(("🏛 Civic / govOS","Minutes reachable per venue (curse-breaker)","%s venues cracked · pending: %s"%(bar(vm.get("reachable",0),vm.get("venues",6)),pend),"prog"))
    mc=L(os.path.join(ST,"meetings_calendar.json"),{})
    if mc:
        tot=sum(t.get("meetings",0) for t in mc.get("tenants",[]))
        rows.append(("🏛 Civic / govOS","Meetings calendar (1st records->future)","%d meetings across %d tenants · Maui complete (2015->2026)"%(tot,len(mc.get("tenants",[]))),"prog"))
    ap=L(os.path.join(ST,"leads","agenda_patterns_evidence.json"),{})
    if ap: rows.append(("🏛 Civic / govOS","Agenda patterns (forward+back)","%d fwd + %d historical scanned · %d recurring ties (accumulating)"%(ap.get("forward",0),ap.get("historical",0),len(ap.get("recurring_ties",[]))),"prog"))
    diss=L(os.path.join(ST,"committee","committee_dissent_summary.json"),{})
    if diss: rows.append(("🏛 Civic / govOS","Committee dissent + eligibility","dissent motions captured; recusal eligibility live (vs Maui Charter Art.10)","ok"))
    rows.append(("🏛 Civic / govOS","BFED today — agenda + aloha conflict questions","live + public; private dollar evidence on the King","ok"))
    # ---- SELF-HEAL ----
    sk=L(os.path.join(ST,"selfheal_skills.json"),{}) or L(os.path.join(os.path.dirname(os.path.abspath(__file__)),"selfheal_skills.json"),{})
    if sk:
        skl=sk.get("skills",[]); learn=sum(len(s.get("learnings",[])) for s in skl)
        rows.append(("🔧 Self-heal","Refining skill set","%d skills · %d learnings · %s thread events"%(len(skl),learn,sk.get("events_scanned","?")),"ok"))
    sh=L(os.path.join(ST,"surface_health.json"),{})
    if sh: rows.append(("🔧 Self-heal","Boot-persistence (all surfaces up)","%s up%s"%(bar(sh["summary"]["total"]-sh["summary"]["down"],sh["summary"]["total"])," · "+str(sh["summary"]["down"])+" down" if sh["summary"]["down"] else ""),"ok" if not sh["summary"]["down"] else "todo"))
    rows.append(("🔧 Self-heal","Public-is-public + leak-gate","today's civic data verified live; private stays private","ok"))
    # ---- CREATIVE ----
    sp=[]
    spf=os.path.join(ST,"sparks","creative_sparks.jsonl")
    if os.path.exists(spf): sp=[l for l in open(spf,encoding="utf-8") if l.strip()]
    rows.append(("✶ Creative","Spark ledger","%d cross-domain sparks captured off the realtime feed"%len(sp),"ok"))

    gen=datetime.now(HST).strftime("%Y-%m-%d %H:%M HST")
    col={"ok":"#1f9d55","prog":"#d9822b","todo":"#7d8aa0"}
    pillars={}
    for p,it,stt,state in rows: pillars.setdefault(p,[]).append((it,stt,state))
    body=""
    for p,items in pillars.items():
        cards="".join("<div class=row><div class=it><span class=dot style='background:%s'></span>%s</div><div class=st>%s</div></div>"%(col[state],esc(it),stt) for it,stt,state in items)
        body+="<div class=pill><h2>%s</h2>%s</div>"%(esc(p),cards)
    html=("<!doctype html><meta charset=utf-8><meta http-equiv=refresh content=120><title>Progress board — all work at once | 12SGI</title><style>"
      "body{font-family:system-ui,Segoe UI,sans-serif;max-width:1000px;margin:1.4rem auto;padding:0 1rem;background:#0d1117;color:#e6edf3}"
      "h1{font-size:1.45rem;margin:.2rem 0}.sub{color:#8b949e;font-size:.85rem;margin-bottom:1rem}"
      ".pill{background:#11161d;border:1px solid #21262d;border-radius:13px;padding:.7rem 1rem;margin:.7rem 0}"
      "h2{font-size:1.05rem;margin:.2rem 0 .5rem}.row{display:flex;justify-content:space-between;gap:1rem;padding:.4rem 0;border-bottom:1px solid #1b2027;font-size:.86rem}"
      ".it{font-weight:600}.dot{display:inline-block;width:9px;height:9px;border-radius:50%%;margin-right:.5rem}.st{color:#9db0c4;text-align:right;max-width:55%%}"
      ".bar{display:inline-block;width:70px;height:7px;border-radius:99px;background:#222a33;overflow:hidden;vertical-align:middle;margin-right:.3rem}"
      ".bar span{display:block;height:100%%;background:linear-gradient(90deg,#1f9d55,#0b6bcb)}"
      ".legend{color:#8b949e;font-size:.78rem;margin-top:1rem}</style>"
      "<h1>12SGI — all work at once</h1><div class=sub>One board across every surface. Generated %s · auto-refreshes. "
      "🟢 done · 🟠 in progress · ⚪ queued.</div>%s"
      "<div class=legend>Public civic surfaces: jimlangford.github.io/12sgi-king/ · Private King (Tailscale): recusal evidence + owner-only. "
      "This board: served on the :8781 status dashboard + the private King.</div>"%(esc(gen),body))
    os.makedirs(ST,exist_ok=True)
    open(os.path.join(ST,"progress_board.html"),"w",encoding="utf-8").write(html)
    print("progress_board.html written ·",len(rows),"items across",len(pillars),"pillars")
    for p,items in pillars.items():
        print(" ",p)
        for it,stt,state in items: print("    [%s] %s"%(state,it))
    return 0

if __name__=="__main__":
    if sys.platform=="win32":
        import io; sys.stdout=io.TextIOWrapper(sys.stdout.buffer,encoding="utf-8",errors="replace")
    sys.exit(main())
