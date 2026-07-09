#!/usr/bin/env python3
# storyboard_scan.py - scan ALL rendered mp4 clips into film STORYBOARDS (Jimmy 2026-06-16). Catalogs every
# clip in ComfyUI/output (1400+), groups by production (the output dir = a song or 12_STONES_FILM), orders by
# scene, and extracts a first-frame thumbnail (ffmpeg) so clips become a visual storyboard for the film.
# Film-priority productions thumbnailed first; thumbnails are incremental (skip if present) so re-runs are cheap.
# Output: reports/_status/storyboard/storyboard.html + catalog.json (+ thumbs/). Stdlib + ffmpeg.
import os, sys, re, json, glob, subprocess
from datetime import datetime, timedelta, timezone
HST=timezone(timedelta(hours=-10))
HOME=os.path.expanduser("~"); PROJ=os.path.join(HOME,"Documents","Claude","Projects","Video System elementLOTUS")
OUT=os.path.join(HOME,"Documents","COMFYUI","output")
SB=os.path.join(PROJ,"reports","_status","storyboard"); TH=os.path.join(SB,"thumbs")
NW=0x08000000
# film-priority productions (thumbnail these first): the 12 STONES film + its anchor songs
PRIORITY=["12_STONES_FILM","HE_LEI_NO_LAHAINA","ASHES_OF_TRUST_DISTROKID","AN_ON_Y_MO_US","BUDDHA_DON_T_BURN",
          "ASH_ON_THE_BADGE","KAULA_LANI","AINA_LANI_FA","HAMAKUA_FULLMASTER","CHILDREN_OF_NATURE_S_SOURCE"]
THUMB_CAP=int(os.environ.get("THUMB_CAP","160"))
def esc(s): return str(s or "").replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
def scene_of(fn):
    m=re.search(r"scene[_-]?(\d+)",fn,re.I) or re.search(r"_(\d{4,5})_",fn)
    return int(m.group(1)) if m else 9999

def thumb(clip,dest):
    if os.path.exists(dest): return True
    try:
        subprocess.run(["ffmpeg","-y","-ss","1","-i",clip,"-frames:v","1","-vf","scale=320:-1",dest],
                       capture_output=True,timeout=30,creationflags=NW)
        return os.path.exists(dest)
    except Exception:
        return False

def main():
    os.makedirs(TH,exist_ok=True)
    clips=glob.glob(os.path.join(OUT,"*","*.mp4"))+glob.glob(os.path.join(OUT,"*.mp4"))
    prods={}
    for c in clips:
        prod=os.path.basename(os.path.dirname(c))
        if os.path.dirname(c)==OUT: prod="(root)"
        prods.setdefault(prod,[]).append(c)
    # order productions: priority first, then the rest alpha; skip the OLD/junk dirs to the back
    def prank(p):
        if p in PRIORITY: return (0,PRIORITY.index(p))
        if re.search(r"OLD|_v\d|textonly|\d{8,}",p): return (2,p)
        return (1,p)
    order=sorted(prods,key=prank)
    made=0; cat={}
    for prod in order:
        items=sorted(prods[prod],key=lambda c:scene_of(os.path.basename(c)))
        rec=[]
        for c in items:
            fn=os.path.basename(c); sc=scene_of(fn)
            th=os.path.join(TH,"%s__%s.jpg"%(re.sub(r'[^A-Za-z0-9]','_',prod)[:30],re.sub(r'[^A-Za-z0-9]','_',fn)[:40]))
            has=os.path.exists(th)
            if not has and made<THUMB_CAP and (prank(prod)[0]<2):   # thumbnail priority + normal, not junk
                if thumb(c,th): has=True; made+=1
            rec.append({"file":fn,"scene":sc,"thumb":os.path.relpath(th,SB) if has else None,
                        "path":c,"mtime":int(os.path.getmtime(c))})
        cat[prod]=rec
    gen=datetime.now(HST).strftime("%Y-%m-%d %H:%M HST")
    total=sum(len(v) for v in cat.values())
    json.dump({"generated":gen,"total_clips":total,"productions":len(cat),"thumbs_made_this_run":made,"catalog":cat},
              open(os.path.join(SB,"catalog.json"),"w",encoding="utf-8"),indent=1,ensure_ascii=False)
    # storyboard html (priority productions first, clip thumbnails in scene order)
    secs=""
    for prod in order:
        if prank(prod)[0]==2 and prod!="(root)": continue   # hide OLD/junk from the board (still in catalog.json)
        rec=cat[prod]; tiles=""
        for r in rec[:60]:
            t=("<img loading=lazy src='thumbs/%s'>"%esc(os.path.basename(r["thumb"])) ) if r["thumb"] else "<div class=noimg>scene %d</div>"%r["scene"]
            tiles+="<div class=clip title='%s'>%s<div class=sc>%d</div></div>"%(esc(r["file"]),t,r["scene"])
        tag=" ★" if prod in PRIORITY else ""
        secs+="<div class=prod><h2>%s%s <span class=n>%d clips</span></h2><div class=row>%s</div></div>"%(esc(prod),tag,len(rec),tiles)
    html=("<!doctype html><meta charset=utf-8><meta http-equiv=refresh content=600><title>Storyboards — every clip | 12SGI</title><style>"
      "body{font-family:system-ui,Segoe UI,sans-serif;max-width:1100px;margin:1.3rem auto;padding:0 1rem;background:#0d1117;color:#e6edf3}"
      "h1{font-size:1.4rem}.sub{color:#8b949e;font-size:.85rem;margin-bottom:1rem}.prod{margin:1.1rem 0}"
      "h2{font-size:1rem;color:#cfae6d;margin:.3rem 0}.n{color:#8b949e;font-weight:400;font-size:.8rem}"
      ".row{display:flex;gap:6px;overflow-x:auto;padding:4px 0}.clip{flex:none;width:160px;position:relative}"
      ".clip img{width:160px;height:90px;object-fit:cover;border-radius:6px;border:1px solid #21262d}"
      ".noimg{width:160px;height:90px;border-radius:6px;border:1px dashed #30363d;display:flex;align-items:center;justify-content:center;color:#566;font-size:.7rem}"
      ".sc{position:absolute;top:3px;left:5px;background:#000a;border-radius:4px;padding:0 5px;font-size:.7rem}</style>"
      "<h1>Film storyboards — every rendered clip</h1>"
      "<div class=sub>%d clips across %d productions, ordered by scene. Film-priority (★) first; OLD/junk hidden. "
      "Thumbnails: %d new this run (incremental). Generated %s. The visual storyboard for the films. "
      "<a href='node_clips.html' style='color:#cfae6d'>&rarr; Clips sorted into the 54 node-worlds</a></div>%s"
      %(total,len(cat),made,esc(gen),secs))
    open(os.path.join(SB,"storyboard.html"),"w",encoding="utf-8").write(html)
    print("storyboard_scan: %d clips, %d productions, %d new thumbnails"%(total,len(cat),made))
    for prod in order[:8]:
        if prank(prod)[0]<2: print("  %-30s %d clips"%(prod[:30],len(cat[prod])))
    print("-> reports/_status/storyboard/storyboard.html")
    return 0

if __name__=="__main__":
    if sys.platform=="win32":
        import io; sys.stdout=io.TextIOWrapper(sys.stdout.buffer,encoding="utf-8",errors="replace")
    sys.exit(main())
