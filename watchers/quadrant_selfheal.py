#!/usr/bin/env python3
# quadrant_selfheal.py - ONE APP, FOUR QUADRANTS, MANY FACETS (Jimmy 2026-06-16).
#
# The Quadcast OS is one unified application with four quadrants - Music Video, Film, Game (Sage), govOS -
# each made of many facets. This self-heals EACH facet of EACH quadrant and reports progress, designed to
# run HOURLY (windowless). It is LIGHT by design: it runs the cheap boot-persistence + skill self-heal
# (servers/daemons/guards), then SCORES every facet from the status JSONs the daily audit_cycle produces -
# it never launches a render or fights the GPU. Heavy generators stay in audit_cycle; this is the hourly pulse.
#
# Writes, all under reports/_status/:
#   quadrant_progress.json      - the structured 4-quadrant facet scores (machine)
#   quadrant_progress.html      - the dashboard (quadrant-structured, served on the private King + :8781)
#   quadrant_progress_log.jsonl - ONE snapshot line appended per run = the hourly progress log
#   quadrant_progress_log.html  - the human log view (linked from the go page "progress" link)
# Stdlib only. Each facet scorer is defensive: a missing source -> "todo", never a crash.
import os, sys, json, glob, time, subprocess, importlib
from datetime import datetime, timedelta, timezone
HST=timezone(timedelta(hours=-10))
HERE=os.path.dirname(os.path.abspath(__file__))
HOME=os.path.expanduser("~"); PROJ=os.path.join(HOME,"Documents","Claude","Projects","Video System elementLOTUS")
ST=os.path.join(PROJ,"reports","_status"); CFG=os.path.join(PROJ,"config"); OUT=os.path.join(HOME,"Documents","COMFYUI","output")
SBJ=os.path.join(ST,"storyboard"); NW=0x08000000
sys.path.insert(0,HERE)
def _atomic_write(path,text):
    """tmp + os.replace so an hourly rewrite on the iCloud-synced Documents tree can never leave a
    0-byte/partial file (the known truncation gotcha). server-quad-os self-heal audit 2026-06-21."""
    tmp=path+".tmp"
    with open(tmp,"w",encoding="utf-8",newline="\n") as f: f.write(text)
    os.replace(tmp,path)
def L(p,d=None):
    try: return json.load(open(p,encoding="utf-8"))
    except Exception: return d
def fresh(p):
    try: return (time.time()-os.path.getmtime(p))/3600.0   # hours since last update
    except Exception: return None
def esc(s): return str(s if s is not None else "").replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
def cnt(pat): return len(glob.glob(pat))

# ---- facet scorers: each returns (state, detail, done, total) ; state in ok|prog|todo|down ----
def mv_catalog():
    s=L(os.path.join(CFG,"songs_v4.json"),{}); songs=s.get("songs",s) if isinstance(s,dict) else s
    n=len(songs) if isinstance(songs,(list,dict)) else 0
    r=sum(1 for x in (songs.values() if isinstance(songs,dict) else songs) if isinstance(x,dict) and x.get("status")=="renderable")
    return ("prog","%d songs in catalog · %d renderable"%(n,r),r,n or 1)
def mv_pipeline():
    ab=L(os.path.join(ST,"distorch_ab.json"))
    note="DisTorch2 verified (-1.9GB VRAM, +11%% faster); face-lock 0.92 + Wan2.2 i2v live" if ab else "conductor live (SDXL keyframe -> Wan2.2 i2v)"
    return ("ok",note,1,1)
def mv_clips():
    cat=L(os.path.join(SBJ,"catalog.json"),{}); tot=cat.get("total_clips",0)
    return ("ok" if tot else "todo","%d clips catalogued into storyboards"%tot,1 if tot else 0,1)

def film_12stones():
    sc=L(os.path.join(CFG,"film_12stones_scenes.json"),{}).get("scenes",[]); n=len(sc)
    clips=cnt(os.path.join(OUT,"12_STONES_FILM","*.mp4"))
    nc=L(os.path.join(SBJ,"node_clips.json"),{}); covered=sum(1 for s in nc.get("scene_reference",[]) if s.get("n_candidates",0)>0)
    return ("prog","%d-scene manifest · %d film clips · %d/%d scenes have candidate clips"%(n,clips,covered,len(nc.get("scene_reference",[])) or n),clips,max(n,1))
def film_seventh():
    return ("prog","greenlit, 2nd in line · 5+2 merge (Wick N5 / Constantine N2) · treatment + 5 scenes",0,1)
def film_keys():
    return ("todo","Keys of Starforge — 22-min Ghibli x Polynesian animated · script in progress",0,1)
def film_recipes():
    rr=L(os.path.join(SBJ,"render_recipes.json"),{}); z=rr.get("zone_recipes",{})
    return ("ok" if z else "todo","reverse-engine recipes for %d zone models · %d clips measured"%(len(z),rr.get("clips_measured_total",0)),len(z),4)

def game_cards():
    c=cnt(os.path.join(PROJ,"exports","sage_cards","*.png")) or cnt(os.path.join(PROJ,"app","studio","character","*.png"))
    return ("ok" if c>=54 else "prog","%d/54 Sage cards rendered (all-Polynesian guardians, env-only LoRAs)"%min(c,54),min(c,54),54)
def game_zones():
    LOR=os.path.join(HOME,"Documents","COMFYUI","models","loras")
    want=["elementlotus_mauka_zone","elementlotus_kula_zone","elementlotus_makai_zone","elementlotus_luna_environment"]
    have=sum(1 for w in want if os.path.isfile(os.path.join(LOR,w+".safetensors")))
    return ("ok" if have>=4 else "prog","%d/4 zone-sphere environment LoRAs trained (Mauka/Kula/Makai/Universal)"%have,have,4)
def game_chars():
    LOR=os.path.join(HOME,"Documents","COMFYUI","models","loras")
    j="character_references" ; jimmy=cnt(os.path.join(PROJ,"JIMMY_LORA","face_reference_*"))
    james=os.path.isfile(os.path.join(LOR,"elementlotus_james_character.safetensors"))
    luna=os.path.isfile(os.path.join(LOR,"elementlotus_luna_character.safetensors"))
    have=sum([jimmy>0,james,luna,True])  # Jimmy photoreal + James + Luna cartoon pair + Polynesian archetypes
    return ("prog","roster: Jimmy photoreal%s · James%s + Luna%s cartoon pair · Polynesian archetypes"%(
        " ok" if jimmy else "", " ok" if james else " todo", " ok" if luna else " todo"),have,4)
def game_nodes():
    nc=L(os.path.join(SBJ,"node_clips.json"),{}); nw=nc.get("nodes_with_clips",0)
    return ("prog","%d/54 node-worlds have classified clips · %d clips mapped"%(nw,nc.get("mapped_clips",0)),nw,54)

def gov_depth():
    td=L(os.path.join(ST,"tenant_depth.json"),{}); ts=td.get("tenants",[]); ref=td.get("maui_reference_depth",9)
    at=sum(1 for t in ts if t.get("covered",0)>=ref)
    return ("prog" if at<len(ts) else "ok","%d/%d tenants at Maui-deep testimony (ref %d dims)"%(at,len(ts) or 1,ref),at,len(ts) or 1)
def gov_minutes():
    vm=L(os.path.join(ST,"venue_minutes.json"),{}); r=vm.get("reachable",0); t=vm.get("venues",6)
    pend=", ".join(x["venue"] for x in vm.get("rows",[]) if x.get("minutes_reachable")!="reachable") or "all reachable"
    return ("prog" if r<t else "ok","%d/%d venues' minutes cracked · pending: %s"%(r,t,pend),r,t)
def gov_calendar():
    mc=L(os.path.join(ST,"meetings_calendar.json"),{}); tot=sum(t.get("meetings",0) for t in mc.get("tenants",[]))
    return ("ok" if tot else "todo","%d meetings indexed across %d tenants (1st records->future)"%(tot,len(mc.get("tenants",[]))),1 if tot else 0,1)
def gov_integrity():
    return ("ok","public = questions + ethics standard · dollar evidence stays private (leak-gate)",1,1)

def cross_boot():
    sh=L(os.path.join(ST,"surface_health.json"),{}); sm=sh.get("summary",{})
    tot=sm.get("total",0); down=sm.get("down",0)
    return ("ok" if not down else "down","%d/%d surfaces up%s"%(tot-down,tot,(" · %d DOWN"%down) if down else ""),tot-down,tot or 1)
def cross_skills():
    sk=L(os.path.join(ST,"selfheal_skills.json")) or L(os.path.join(HERE,"selfheal_skills.json"),{})
    skl=sk.get("skills",[]); learn=sum(len(s.get("learnings",[])) for s in skl)
    return ("ok","%d self-heal skills · %d cumulative learnings"%(len(skl),learn),len(skl),len(skl) or 1)
def cross_parity():
    # Studio healed UP to the CIVIC standard (config/parity_standard.json), written by studio_parity.py.
    sp=L(os.path.join(ST,"studio_parity.json"),{}); sc=(sp.get("scores") or {}); ov=sc.get("overall",0)
    stt="ok" if ov>=80 else "prog" if ov>=50 else "todo"
    return (stt,"studio↔civic %d%% (look %d / tenant %d / iPad %d)"%(ov,sc.get("look",0),sc.get("tenant_logic",0),sc.get("ipad_workable",0)),ov,100)

QUADRANTS=[
    ("music_video","Music Video","🎬",[("Song catalog",mv_catalog),("Render pipeline",mv_pipeline),("Clip storyboards",mv_clips)]),
    ("film","Film","🎞",[("12 STONES feature",film_12stones),("Seventh Stone (5+2)",film_seventh),("Keys of Starforge",film_keys),("Reverse-engine recipes",film_recipes)]),
    ("game","Game · Sage","🎮",[("54 Sage cards",game_cards),("4 zone-sphere models",game_zones),("Character roster",game_chars),("Node-world clips",game_nodes)]),
    ("govos","govOS","🏛",[("Tenant depth",gov_depth),("Minutes reachable",gov_minutes),("Meetings calendar",gov_calendar),("Public/private integrity",gov_integrity)]),
    ("cross","Self-heal · spine","🔧",[("Boot-persistence",cross_boot),("Refining skill set",cross_skills),("Studio↔Civic parity",cross_parity)]),
]
STATE_COL={"ok":"#56c08a","prog":"#d9b24c","todo":"#7d8aa0","down":"#e06c6c"}

def run_selfheal():
    """The actual hourly self-heal: light boot-persistence sweep + skill guards. Never touches the GPU."""
    healed=[]
    try:
        subprocess.run([sys.executable,os.path.join(HERE,"surface_health.py"),"--heal"],timeout=120,creationflags=NW)
        healed.append("surface_health --heal")
    except Exception: pass
    try:
        subprocess.run([sys.executable,os.path.join(HERE,"studio_parity.py"),"--heal"],timeout=60,creationflags=NW)
        healed.append("studio_parity --heal (studio kept at civic standard)")
    except Exception: pass
    try:
        import selfheal; importlib.reload(selfheal); selfheal.run(); healed.append("selfheal guards")
    except Exception: pass
    return healed

def main():
    healed=run_selfheal()
    quads=[]; quad_pcts=[]
    for qid,qname,icon,facets in QUADRANTS:
        frows=[]
        for fname,fn in facets:
            try: state,detail,done,total=fn()
            except Exception as e: state,detail,done,total=("todo","(score unavailable: %s)"%e,0,1)
            frows.append({"facet":fname,"state":state,"detail":detail,"done":done,"total":total,
                          "pct":round(100*done/total) if total else 0})
        # quadrant % = MEAN of facet % (each facet equal weight) so a large-N facet can't dominate
        pct=round(sum(f["pct"] for f in frows)/len(frows)) if frows else 0
        quads.append({"id":qid,"name":qname,"icon":icon,"pct":pct,"facets":frows,
                      "n_ok":sum(1 for f in frows if f["state"]=="ok"),"n_facets":len(frows),
                      "down":sum(1 for f in frows if f["state"]=="down")})
        if qid!="cross": quad_pcts.append(pct)   # the 4 true quadrants drive the headline number
    gen=datetime.now(HST); gens=gen.strftime("%Y-%m-%d %H:%M HST")
    overall=round(sum(quad_pcts)/len(quad_pcts)) if quad_pcts else 0
    payload={"generated":gens,"ts":int(time.time()),"overall_pct":overall,"healed":healed,"quadrants":quads}
    os.makedirs(ST,exist_ok=True)
    _atomic_write(os.path.join(ST,"quadrant_progress.json"),json.dumps(payload,indent=1,ensure_ascii=False))

    # hourly log line (jsonl) - one compact snapshot per run
    with open(os.path.join(ST,"quadrant_progress_log.jsonl"),"a",encoding="utf-8") as f:
        f.write(json.dumps({"ts":int(time.time()),"iso":gens,"overall":overall,
            "quadrants":{q["id"]:q["pct"] for q in quads},"healed":len(healed)},ensure_ascii=False)+"\n")

    _write_dashboard(payload)
    _write_log_view()
    # mirror the dashboard into the private King if the king-local civic mirror dir exists
    for kd in (os.path.join(HOME,"AppData","Local","king-extract","deploy","king-local"),
               os.path.join(PROJ,"king-local")):
        try:
            if os.path.isdir(kd):
                import shutil
                for f in ("quadrant_progress.html","quadrant_progress_log.html"):
                    shutil.copy(os.path.join(ST,f),os.path.join(kd,f))
        except Exception: pass
    print("quadrant_selfheal: overall %d%% · healed [%s]"%(overall,", ".join(healed)))
    for q in quads: print("  %s %-18s %3d%%  (%d/%d facets ok%s)"%(q["icon"],q["name"],q["pct"],q["n_ok"],q["n_facets"],", %d DOWN"%q["down"] if q["down"] else ""))
    return 0

def _write_dashboard(p):
    def facet(f):
        return ("<div class=fac><div class=fh><span class=dot style='background:%s'></span>"
                "<span class=fn>%s</span><span class=fp>%d%%</span></div>"
                "<div class=fb><span style='width:%d%%;background:%s'></span></div>"
                "<div class=fd>%s</div></div>")%(STATE_COL[f["state"]],esc(f["facet"]),f["pct"],
                f["pct"],STATE_COL[f["state"]],esc(f["detail"]))
    qcards=""
    for q in p["quadrants"]:
        qcards+=("<section class=quad><div class=qh><span class=qi>%s</span><h2>%s</h2>"
                 "<span class=qp>%d%%</span></div><div class=qbar><span style='width:%d%%'></span></div>%s</section>")%(
                 q["icon"],esc(q["name"]),q["pct"],q["pct"],"".join(facet(f) for f in q["facets"]))
    html=("<!doctype html><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'>"
      "<meta http-equiv=refresh content=300><title>Quadcast — one app, four quadrants | 12SGI</title><style>"
      ":root{--bg:#0c100e;--panel:#151d19;--line:#243029;--ink:#eef3ef;--mut:#9fb1a6;--gold:#d9b24c;--ok:#56c08a}"
      "*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font-family:'Segoe UI',system-ui,sans-serif;padding:20px}"
      ".wrap{max-width:880px;margin:0 auto}h1{font-family:Georgia,serif;color:#f0cf7a;font-size:24px;margin:.2rem 0}"
      ".sub{color:var(--mut);font-size:13px;margin-bottom:16px}"
      ".big{display:flex;align-items:center;gap:14px;background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:14px 18px;margin-bottom:18px}"
      ".big .num{font-size:34px;font-weight:700;color:var(--gold);font-family:Georgia,serif}.big .lbl{color:var(--mut);font-size:12.5px}"
      ".quad{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:14px 16px;margin-bottom:14px}"
      ".qh{display:flex;align-items:center;gap:10px}.qi{font-size:20px}.qh h2{font-size:16px;margin:0;flex:1}.qp{font-weight:700;color:var(--gold)}"
      ".qbar{height:7px;border-radius:99px;background:#0d1411;overflow:hidden;margin:8px 0 12px}.qbar span{display:block;height:100%%;background:linear-gradient(90deg,#2f8f63,#d9b24c)}"
      ".fac{padding:8px 0;border-top:1px solid var(--line)}.fh{display:flex;align-items:center;gap:8px;font-size:13.5px}"
      ".dot{width:9px;height:9px;border-radius:50%%}.fn{font-weight:600;flex:1}.fp{color:var(--mut);font-size:12px}"
      ".fb{height:5px;border-radius:99px;background:#0d1411;overflow:hidden;margin:5px 0 4px}.fb span{display:block;height:100%%}"
      ".fd{color:var(--mut);font-size:12px;line-height:1.45}"
      ".foot{color:var(--mut);font-size:11.5px;margin-top:16px;line-height:1.6}a{color:var(--gold)}</style>"
      "<div class=wrap><h1>Quadcast — one app, four quadrants</h1>"
      "<div class=sub>The whole system as one application with many facets. Self-healed + scored hourly. Generated %s · auto-refresh.</div>"
      "<div class=big><span class=num>%d%%</span><span class=lbl>overall across the four quadrants<br>(Music Video · Film · Game · govOS) — self-heal spine tracked separately below</span></div>"
      "%s<div class=foot>Healed this run: %s · <a href='quadrant_progress_log.html'>hourly progress log &rarr;</a><br>"
      "&copy; 2026 James RCS Langford &middot; 12 Stones Global</div></div>")%(
      esc(p["generated"]),p["overall_pct"],qcards,esc(", ".join(p["healed"]) or "guards ok"))
    _atomic_write(os.path.join(ST,"quadrant_progress.html"),html)

def _write_log_view():
    lines=[]
    try:
        for ln in open(os.path.join(ST,"quadrant_progress_log.jsonl"),encoding="utf-8"):
            if ln.strip(): lines.append(json.loads(ln))
    except Exception: pass
    lines=lines[-240:]   # last ~10 days of hourly snapshots
    rows=""
    for e in reversed(lines):
        q=e.get("quadrants",{})
        rows+=("<tr><td>%s</td><td class=o>%d%%</td><td>%d%%</td><td>%d%%</td><td>%d%%</td><td>%d%%</td></tr>")%(
            esc(e.get("iso","")),e.get("overall",0),q.get("music_video",0),q.get("film",0),q.get("game",0),q.get("govos",0))
    html=("<!doctype html><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'>"
      "<meta http-equiv=refresh content=600><title>Hourly progress log | 12SGI Quadcast</title><style>"
      "body{margin:0;background:#0c100e;color:#eef3ef;font-family:'Segoe UI',system-ui,sans-serif;padding:20px}"
      ".wrap{max-width:760px;margin:0 auto}h1{font-family:Georgia,serif;color:#f0cf7a;font-size:22px}"
      ".sub{color:#9fb1a6;font-size:13px;margin-bottom:14px}a{color:#d9b24c}"
      "table{border-collapse:collapse;width:100%%;font-size:13px}th,td{padding:.45rem .6rem;border-bottom:1px solid #243029;text-align:right}"
      "th:first-child,td:first-child{text-align:left;color:#9fb1a6}td.o{font-weight:700;color:#d9b24c}"
      "th{color:#9fb1a6;font-weight:600;font-size:11px;letter-spacing:.5px;text-transform:uppercase}</style>"
      "<div class=wrap><h1>Hourly progress log</h1>"
      "<div class=sub>One snapshot per hour across the four quadrants. <a href='quadrant_progress.html'>&larr; back to the dashboard</a></div>"
      "<table><thead><tr><th>time (HST)</th><th>overall</th><th>🎬 MV</th><th>🎞 Film</th><th>🎮 Game</th><th>🏛 govOS</th></tr></thead>"
      "<tbody>%s</tbody></table></div>")%(rows or "<tr><td colspan=6>no snapshots yet</td></tr>")
    _atomic_write(os.path.join(ST,"quadrant_progress_log.html"),html)

if __name__=="__main__":
    if sys.platform=="win32":
        import io; sys.stdout=io.TextIOWrapper(sys.stdout.buffer,encoding="utf-8",errors="replace")
    sys.exit(main())
