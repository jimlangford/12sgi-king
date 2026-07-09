#!/usr/bin/env python3
# clip_engine_reverse.py - the OPPOSITE LENS (Jimmy 2026-06-16).
#
# The forward lens (DESCRIBE_STYLE_CLIPS.py -> docs/clip_catalog.csv) watches each clip and reports what the
# WORLD looks like (setting, palette, particle, mood) - vocabulary for writing prompts. This is the inverse:
# it MEASURES, out of the actual pixels and motion, HOW OUR RENDER ENGINE PRODUCED the clip - the engine
# signature - then aggregates per node + per zone so the 4 zone models (Mauka/Farmlands/Makai/Universal)
# can TRAIN on the real reverse-engineered mechanics, not on adjectives.
#
# Per clip, GPU-FREE via ffprobe + one ffmpeg signalstats pass (~0.1s):
#   spec      : width/height/aspect, fps, frame_count, duration, codec, bitrate  -> which engine actually made it
#   motion    : mean/peak YDIF (inter-frame luma delta) -> i2v motion bucket (still/slow/fluid/explosive)
#   grade     : YAVG exposure, YAVG std contrast, SATAVG saturation, HUEMED dominant-hue family -> per-zone LUT
#   declared  : merges render_engine/steps/cfg/seed from the forward CSV where present, and FLAGS when the
#               measured spec contradicts the declared engine (e.g. "Kandinsky5" tagged but 16fps/832x480 = Wan i2v)
# Joins each clip to its node+zone via the song->node map (shared with clip_nodes). Aggregates into:
#   render_recipes.json : per-zone (the 4 models) + per-node (54) reverse-engineered recipe = training targets
#   engine_recipes.html : 4 model recipe cards (what each zone model should reproduce)
# Resumable + capped (REV_CAP); cache keyed by path+mtime+size. Stdlib + ffmpeg/ffprobe only.
import os, sys, re, json, glob, subprocess, statistics
from collections import defaultdict
from datetime import datetime, timedelta, timezone
HST=timezone(timedelta(hours=-10))
HOME=os.path.expanduser("~"); PROJ=os.path.join(HOME,"Documents","Claude","Projects","Video System elementLOTUS")
OUT=os.path.join(HOME,"Documents","COMFYUI","output")
SB=os.path.join(PROJ,"reports","_status","storyboard")
CACHE=os.path.join(SB,"reverse_engine.json")
NW=0x08000000
REV_CAP=int(os.environ.get("REV_CAP","4000"))
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
import clip_nodes as cn   # reuse song->node map + norm
def esc(s): return str(s or "").replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")

# motion buckets on mean inter-frame YDIF (calibrated to the 16fps Wan i2v output; raw value kept for tuning)
def motion_bucket(ydif):
    if ydif is None: return "?"
    return "still" if ydif<1.5 else ("slow" if ydif<5 else ("fluid" if ydif<12 else "explosive"))
def hue_family(h):
    if h is None: return "?"
    h=h%256                                    # ffmpeg HUE is 0-255
    deg=h/255*360
    for lo,hi,name in [(0,20,"red"),(20,45,"amber"),(45,70,"gold"),(70,160,"green"),
                       (160,200,"teal"),(200,255,"blue"),(255,290,"violet"),(290,340,"magenta"),(340,361,"red")]:
        if lo<=deg<hi: return name
    return "neutral"
def infer_engine(w,h,fps,frames):
    # the two real paths: Wan2.2 i2v conductor (832x480, fps16, ~81f/5s) vs Kandinsky5 lite (768x512)
    if (w,h)==(832,480) or abs(fps-16)<0.6: return "Wan2.2-i2v"
    if (w,h)==(768,512) or (h==512 and w in (768,896)): return "Kandinsky5-lite"
    if w and h and w/h>2.0: return "wide/cinemascope"
    return "other"

def measure(clip):
    """One ffprobe + one ffmpeg signalstats pass. Returns engine signature dict or None."""
    try:
        p=subprocess.run(["ffprobe","-v","error","-select_streams","v:0","-show_entries",
            "stream=width,height,r_frame_rate,nb_frames,codec_name,bit_rate","-show_entries","format=duration",
            "-of","default=nw=1",clip],capture_output=True,text=True,timeout=20,creationflags=NW)
        sp={}
        for ln in p.stdout.splitlines():
            if "=" in ln: k,v=ln.split("=",1); sp[k.strip()]=v.strip()
        def num(x,d=0.0):
            try: return float(x)
            except Exception: return d
        w=int(num(sp.get("width"))); h=int(num(sp.get("height")))
        fr=sp.get("r_frame_rate","0/1"); fps=(num(fr.split("/")[0])/num(fr.split("/")[1])) if "/" in fr and num(fr.split("/")[1]) else num(fr)
        frames=int(num(sp.get("nb_frames"))); dur=num(sp.get("duration")); br=num(sp.get("bit_rate"))
    except Exception:
        return None
    yav=[]; sat=[]; hue=[]; ydf=[]
    try:
        r=subprocess.run(["ffmpeg","-hide_banner","-v","error","-i",clip,"-vf",
            "scale=96:-2,fps=6,signalstats,metadata=print:file=-","-f","null","-"],
            capture_output=True,text=True,timeout=40,creationflags=NW)
        for ln in r.stdout.splitlines()+r.stderr.splitlines():
            m=re.search(r"signalstats\.(YAVG|SATAVG|HUEMED|YDIF)=([\d.\-]+)",ln)
            if not m: continue
            k,v=m.group(1),float(m.group(2))
            {"YAVG":yav,"SATAVG":sat,"HUEMED":hue,"YDIF":ydf}[k].append(v)
    except Exception:
        pass
    mean=lambda a: round(statistics.mean(a),2) if a else None
    sig={"w":w,"h":h,"aspect":round(w/h,3) if h else None,"fps":round(fps,2),"frames":frames,
         "dur":round(dur,2),"bitrate_k":round(br/1000) if br else None,
         "exposure":mean(yav),"contrast":round(statistics.pstdev(yav),2) if len(yav)>1 else None,
         "saturation":mean(sat),"hue":mean(hue),"hue_family":hue_family(mean(hue)),
         "ydif_mean":mean(ydf),"ydif_peak":round(max(ydf),2) if ydf else None,
         "motion":motion_bucket(mean(ydf)),"engine":infer_engine(w,h,fps,frames)}
    return sig

# ---- optional VLM "engine lens": watch the clip and describe HOW IT WAS RENDERED (reverse of the forward
#      STYLE_DESCRIBE_PROMPT). GPU/Ollama-bound + slow -> off unless --vlm/REV_VLM=1 and Ollama is up. ----
ENGINE_LENS_PROMPT=(
    "You are reverse-engineering an AI VIDEO render. Look at this frame and describe, in production terms, "
    "HOW a diffusion video engine most likely PRODUCED it - not what the scene depicts. Cover ONLY:\n"
    "  - pipeline: image-to-video from a single keyframe, or pure text-to-video? evidence?\n"
    "  - motion intensity the engine applied (still / subtle drift / moderate / strong) and any camera move simulated\n"
    "  - denoise / sampler feel: clean and sharp (high steps) vs soft/dreamy (low steps), any diffusion artifacts\n"
    "  - color grade applied (warm/cool, lifted/crushed blacks, saturation push, LUT character)\n"
    "  - identity/face-lock consistency if a person is present (locked likeness vs drifting)\n"
    "  - resolution/aspect feel and any upscaling tell\n"
    "Output ONE dense paragraph of production/engine nouns. Do NOT describe the story or location."
)
def vlm_engine_describe(frame_png, model, url):
    try:
        sys.path.insert(0,os.path.join(PROJ,"app","server"))
        from image_describer import describe_via_ollama
        r=describe_via_ollama(frame_png,model=model,prompt=ENGINE_LENS_PROMPT,ollama_url=url,timeout_s=180.0)
        return (r.get("description") or "").strip() if r.get("ok") else None
    except Exception:
        return None

def load_declared():
    """Forward CSV (docs/clip_catalog.csv): filename -> declared render params + style words."""
    d={}; path=os.path.join(PROJ,"docs","clip_catalog.csv")
    try:
        import csv
        for row in csv.DictReader(open(path,encoding="utf-8",errors="replace")):
            fn=(row.get("filename") or "").strip()
            if fn: d[fn]={"declared_engine":row.get("render_engine"),"steps":row.get("comfyui_steps"),
                          "cfg":row.get("comfyui_cfg"),"seed":row.get("seed"),
                          "style":row.get("style"),"palette":row.get("color_palette"),"motion_word":row.get("motion")}
    except Exception: pass
    return d

def _gpu_free_mib():
    try:
        r=subprocess.run(["nvidia-smi","--query-gpu=memory.used,memory.total","--format=csv,noheader,nounits"],
                         capture_output=True,text=True,timeout=10,creationflags=NW)
        used,tot=[int(x) for x in r.stdout.strip().splitlines()[0].split(",")]
        return tot-used
    except Exception:
        return None
def _frame(clip,dst):
    if os.path.exists(dst): return True
    try:
        subprocess.run(["ffmpeg","-y","-v","error","-ss","1.5","-i",clip,"-vframes","1","-vf","scale=768:-2",dst],
                       capture_output=True,timeout=20,creationflags=NW); return os.path.exists(dst)
    except Exception: return False

def main(vlm=False):
    os.makedirs(SB,exist_ok=True)
    cache=json.load(open(CACHE,encoding="utf-8")) if os.path.exists(CACHE) else {}
    m=cn.song_to_node(); declared=load_declared()
    clips=glob.glob(os.path.join(OUT,"*","*.mp4"))
    measured=0; vlm_done=0
    # VLM engine-lens gate: opt-in only, Ollama up, and GPU not saturated by a render (co-tenant rule)
    vlm=vlm or os.environ.get("REV_VLM")=="1"
    vlm_model=None
    if vlm:
        free=_gpu_free_mib()
        if free is not None and free<2500:
            print("  VLM engine-lens SKIPPED: only %dMiB free VRAM (render in progress) - measurement-only this run"%free); vlm=False
        else:
            try:
                sys.path.insert(0,os.path.join(PROJ,"app","server"))
                from image_describer import pick_vision_model
                vlm_model=pick_vision_model("http://127.0.0.1:11434")
                if not vlm_model: print("  VLM engine-lens SKIPPED: no Ollama vision model"); vlm=False
                else: print("  VLM engine-lens ON via %s (%d clips/run cap)"%(vlm_model,REV_CAP))
            except Exception as e:
                print("  VLM engine-lens SKIPPED: %s"%e); vlm=False
    for c in clips:
        st=os.stat(c); key="%s|%d|%d"%(os.path.basename(c),int(st.st_mtime),st.st_size)
        prod=os.path.basename(os.path.dirname(c)); base=cn.norm(prod)
        info=m.get(base) or next((m[k] for k in m if base.startswith(k[:10]) and len(k)>=8),None)
        nodes=info.get("nodes") if info else []
        rec=cache.get(c)
        if not rec or rec.get("key")!=key:
            if measured>=REV_CAP: continue          # bounded per run; resumable next cycle
            sig=measure(c)
            if not sig: continue
            measured+=1
            rec={"key":key,"prod":prod,"nodes":nodes,"sig":sig}
            dec=declared.get(os.path.basename(c))
            if dec:
                rec["declared"]=dec
                de=(dec.get("declared_engine") or "").lower()
                if de and "kand" in de and sig["engine"]=="Wan2.2-i2v": rec["engine_conflict"]=True
                if de and "wan" in de and sig["engine"]=="Kandinsky5-lite": rec["engine_conflict"]=True
            cache[c]=rec
        else:
            rec["nodes"]=nodes                       # refresh node map even on cache hit
        # optional VLM engine-lens (separate cap: describe how it was rendered, in production terms)
        if vlm and vlm_model and not rec.get("engine_lens") and vlm_done<REV_CAP:
            fr=os.path.join(SB,".rev_frames"); os.makedirs(fr,exist_ok=True)
            fp=os.path.join(fr,re.sub(r"[^A-Za-z0-9]","_",os.path.basename(c))[:50]+".png")
            if _frame(c,fp):
                txt=vlm_engine_describe(fp,vlm_model,"http://127.0.0.1:11434")
                if txt: rec["engine_lens"]=txt; vlm_done+=1; cache[c]=rec
    json.dump(cache,open(CACHE,"w",encoding="utf-8"),indent=1,ensure_ascii=False)

    # ---- aggregate into reverse-engineered recipes: per ZONE (the 4 models) + per NODE (54) ----
    def agg(recs):
        if not recs: return None
        sigs=[r["sig"] for r in recs]
        def col(k): return [s[k] for s in sigs if s.get(k) is not None]
        def med(a): return round(statistics.median(a),2) if a else None
        from collections import Counter
        mot=Counter(s["motion"] for s in sigs); hue=Counter(s["hue_family"] for s in sigs); eng=Counter(s["engine"] for s in sigs)
        asp=Counter("%dx%d"%(s["w"],s["h"]) for s in sigs if s.get("w"))
        return {"n_clips":len(recs),
                "spec":dict(asp.most_common(3)),"engine":dict(eng.most_common()),
                "fps_median":med(col("fps")),"dur_median":med(col("dur")),"frames_median":med(col("frames")),
                "motion_mix":dict(mot.most_common()),"ydif_median":med(col("ydif_mean")),
                "exposure_median":med(col("exposure")),"contrast_median":med(col("contrast")),
                "saturation_median":med(col("saturation")),"hue_family_mix":dict(hue.most_common(4))}
    by_zone=defaultdict(list); by_node=defaultdict(list); conflicts=0
    for c,rec in cache.items():
        if not rec.get("sig"): continue
        if rec.get("engine_conflict"): conflicts+=1
        for n in (rec.get("nodes") or []):
            by_node[n].append(rec)
            z=cn.zone_for_node(n)
            if z: by_zone[z].append(rec)
    zone_recipes={z:agg(v) for z,v in by_zone.items()}
    node_recipes={str(n):agg(v) for n,v in sorted(by_node.items(),key=lambda x:(x[0] or 999))}
    gen=datetime.now(HST).strftime("%Y-%m-%d %H:%M HST")
    payload={"generated":gen,"clips_measured_total":sum(1 for r in cache.values() if r.get("sig")),
             "measured_this_run":measured,"engine_conflicts":conflicts,
             "zone_recipes":zone_recipes,"node_recipes":node_recipes}
    json.dump(payload,open(os.path.join(SB,"render_recipes.json"),"w",encoding="utf-8"),indent=1,ensure_ascii=False)

    # ---- the 4 model recipe cards ----
    ZONES=["Mauka","Farmlands","Makai","Universal"]
    def card(z):
        r=zone_recipes.get(z)
        if not r: return "<div class=card><h2>%s</h2><div class=sub>no measured clips yet</div></div>"%esc(z)
        def mix(d): return " · ".join("%s %d"%(esc(k),v) for k,v in d.items())
        return ("<div class=card><h2>%s <span class=n>%d clips</span></h2>"
          "<table>"
          "<tr><td>engine (measured)</td><td>%s</td></tr>"
          "<tr><td>spec</td><td>%s</td></tr>"
          "<tr><td>fps / dur / frames</td><td>%s · %ss · %s</td></tr>"
          "<tr><td>motion mix</td><td>%s</td></tr>"
          "<tr><td>motion strength (YDIF med)</td><td>%s</td></tr>"
          "<tr><td>exposure / contrast</td><td>%s / %s</td></tr>"
          "<tr><td>saturation</td><td>%s</td></tr>"
          "<tr><td>hue families</td><td>%s</td></tr>"
          "</table></div>")%(esc(z),r["n_clips"],mix(r["engine"]),mix(r["spec"]),
            r["fps_median"],r["dur_median"],r["frames_median"],mix(r["motion_mix"]),
            r["ydif_median"],r["exposure_median"],r["contrast_median"],r["saturation_median"],mix(r["hue_family_mix"]))
    cards="".join(card(z) for z in ZONES)
    html=("<!doctype html><meta charset=utf-8><title>Reverse-engine recipes — the 4 models | 12SGI</title><style>"
      "body{font-family:system-ui,Segoe UI,sans-serif;max-width:1000px;margin:1.3rem auto;padding:0 1rem;background:#0d1117;color:#e6edf3}"
      "h1{font-size:1.35rem}.sub{color:#8b949e;font-size:.84rem}.card{background:#11161d;border:1px solid #21262d;border-radius:10px;padding:.8rem 1rem;margin:.8rem 0}"
      "h2{font-size:1.05rem;color:#cfae6d;margin:.2rem 0}.n{color:#8b949e;font-weight:400;font-size:.8rem}"
      "table{border-collapse:collapse;width:100%%;font-size:.84rem}td{padding:.3rem .5rem;border-bottom:1px solid #1b2027;vertical-align:top}"
      "td:first-child{color:#8b949e;width:38%%}</style>"
      "<h1>Reverse-engineered render recipes — the 4 zone models</h1>"
      "<div class=sub>The opposite lens: measured out of the actual pixels + motion of %d clips (not from prompts) "
      "what each engine DID, aggregated per zone. These are the training targets the 4 models reproduce. "
      "%d engine-conflict clips (declared engine != measured signature). Generated %s. "
      "<a href='node_clips.html' style='color:#cfae6d'>&rarr; clip node-worlds</a> · "
      "<a href='storyboard.html' style='color:#cfae6d'>&rarr; storyboard</a></div>"
      "%s"%(payload["clips_measured_total"],conflicts,esc(gen),cards))
    open(os.path.join(SB,"engine_recipes.html"),"w",encoding="utf-8").write(html)
    print("clip_engine_reverse: measured %d this run, %d total; %d engine-conflicts"%(measured,payload["clips_measured_total"],conflicts))
    for z in ZONES:
        r=zone_recipes.get(z)
        if r: print("  %-10s %4d clips | %s | motion %s | hue %s"%(z,r["n_clips"],
            list(r["engine"])[0] if r["engine"] else "?",list(r["motion_mix"])[0] if r["motion_mix"] else "?",
            list(r["hue_family_mix"])[0] if r["hue_family_mix"] else "?"))
    if vlm: print("  VLM engine-lens descriptions added this run: %d"%vlm_done)
    print("  -> reports/_status/storyboard/engine_recipes.html + render_recipes.json")
    return 0

if __name__=="__main__":
    if sys.platform=="win32":
        import io; sys.stdout=io.TextIOWrapper(sys.stdout.buffer,encoding="utf-8",errors="replace")
    sys.exit(main(vlm=("--vlm" in sys.argv)))
