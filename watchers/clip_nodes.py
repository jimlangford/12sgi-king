#!/usr/bin/env python3
# clip_nodes.py - sort ALL rendered clips into the 54 NODE-WORLDS, then assign candidate clips to each of the
# 60 script scenes (Jimmy 2026-06-16). Each clip's production = a song slug -> its node + zone (film_roster +
# SONG_NODES). Variants (PROOF/OLD/_v#) normalize to the base song. Result: (a) node->clips index = style/
# storyboard reference per node for the node LoRAs; (b) scene->candidate-clips so the 4 zones leaning to the 54
# can inform the 60-scene script. Output: reports/_status/storyboard/node_clips.{json,html}. Stdlib only.
import os, sys, re, json, glob
from collections import defaultdict
from datetime import datetime, timedelta, timezone
HST=timezone(timedelta(hours=-10))
HOME=os.path.expanduser("~"); PROJ=os.path.join(HOME,"Documents","Claude","Projects","Video System elementLOTUS")
OUT=os.path.join(HOME,"Documents","COMFYUI","output")
SB=os.path.join(PROJ,"reports","_status","storyboard")
def esc(s): return str(s or "").replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
def norm(slug):
    s=slug.upper()
    s=re.sub(r"_(PROOF|OLD)\d*","",s); s=re.sub(r"_V\d+$","",s); s=re.sub(r"_TEXTONLY$","",s)
    s=re.sub(r"_\d{6,}$","",s); s=re.sub(r"_(MASTER|FINAL|REMASTERED|FIN|DISTROKID|FULLMASTER)$","",s)
    return s.strip("_")

def _node_list(n):
    """Normalize a node value (int, list, or None) to a list of ints. Songs can legitimately span
    multiple node-worlds (SONG_NODES stores lists like REEF=[53,33,21,30]) -> a clip is reference
    material for EVERY node its song scores, so we fan it out across all of them."""
    if n is None: return []
    if not isinstance(n,(list,tuple)): n=[n]
    out=[]
    for x in n:
        try: out.append(int(x))
        except Exception: pass
    return out

def song_to_node():
    m={}
    # film_roster (54 arc entries) - authoritative single-node + explicit zone
    try:
        for e in json.load(open(os.path.join(PROJ,"config","film_roster.json"),encoding="utf-8")).get("roster",[]):
            if e.get("song"): m[norm(e["song"])]={"nodes":_node_list(e.get("node")),"zone":e.get("zone"),"title":e.get("title")}
    except Exception: pass
    # SONG_NODES (richer, incl variants + multi-node songs) if importable
    try:
        sys.path.insert(0,os.path.join(PROJ,"app","server"))
        import sage_node_system as sn
        for slug,info in getattr(sn,"SONG_NODES",{}).items():
            n=info.get("node") if isinstance(info,dict) else info
            nl=_node_list(n)
            if nl and norm(slug) not in m: m[norm(slug)]={"nodes":nl,"zone":(info.get("zone") if isinstance(info,dict) else None),"title":slug}
    except Exception: pass
    return m

def zone_for_node(n):
    try: n=int(n)
    except Exception: return None
    if not n: return None
    return "Mauka" if n<=18 else ("Farmlands" if n<=36 else ("Makai" if n<=52 else "Universal"))

def main():
    m=song_to_node()
    clips=glob.glob(os.path.join(OUT,"*","*.mp4"))
    by_node=defaultdict(list); by_zone=defaultdict(list); unmapped=defaultdict(int); mapped_unique=set()
    for c in clips:
        prod=os.path.basename(os.path.dirname(c)); base=norm(prod)
        info=m.get(base)
        if not info:                                  # try loosest prefix match
            cand=[k for k in m if base.startswith(k[:10]) and len(k)>=8]
            info=m.get(cand[0]) if cand else None
        if not info or not info.get("nodes"):
            unmapped[prod]+=1; continue
        mapped_unique.add(c)
        for node in info["nodes"]:                    # fan the clip out across EVERY node its song scores
            zone=zone_for_node(node) or info.get("zone")
            rec={"clip":os.path.basename(c),"prod":prod,"node":node,"zone":zone}
            by_node[node].append(rec)
        # zone tally counts each clip once per zone it touches (a multi-zone song reaches multiple zones)
        for z in {zone_for_node(n) or info.get("zone") for n in info["nodes"]}:
            by_zone[z].append({"clip":os.path.basename(c),"prod":prod})
    # scenes -> candidate reference clips (by zone; a scene draws style from its zone's node-worlds)
    scenes=json.load(open(os.path.join(PROJ,"config","film_12stones_scenes.json"),encoding="utf-8")).get("scenes",[])
    scene_ref=[]
    for s in scenes:
        z=s.get("zone") or zone_for_node(s.get("scene"))
        cands=by_zone.get(z,[])
        scene_ref.append({"scene":s["scene"],"zone":z,"heading":s.get("heading","")[:60],
                          "candidate_clips":[r["clip"] for r in cands[:8]],"n_candidates":len(cands)})
    gen=datetime.now(HST).strftime("%Y-%m-%d %H:%M HST")
    payload={"generated":gen,"mapped_clips":len(mapped_unique),
             "node_assignments":sum(len(v) for v in by_node.values()),
             "nodes_with_clips":len(by_node),"unmapped_productions":len(unmapped),
             "by_zone_counts":{z:len(v) for z,v in by_zone.items()},
             "node_clips":{str(n):[r["clip"] for r in v] for n,v in sorted(by_node.items(), key=lambda x:(x[0] or 999))},
             "scene_reference":scene_ref}
    os.makedirs(SB,exist_ok=True)
    json.dump(payload,open(os.path.join(SB,"node_clips.json"),"w",encoding="utf-8"),indent=1,ensure_ascii=False)
    # brief HTML: per-node clip counts + per-scene candidate counts
    nrows="".join("<tr><td>N%s</td><td>%s</td><td class=n>%d</td></tr>"%(esc(n),esc(zone_for_node(n)),len(v)) for n,v in sorted(by_node.items(),key=lambda x:(x[0] or 999)))
    srows="".join("<tr><td>S%d</td><td>%s</td><td class=n>%d</td><td class=m>%s</td></tr>"%(r["scene"],esc(r["zone"]),r["n_candidates"],esc(r["heading"])) for r in scene_ref[:60])
    html=("<!doctype html><meta charset=utf-8><title>Clips by node-world | 12SGI</title><style>"
      "body{font-family:system-ui,Segoe UI,sans-serif;max-width:1000px;margin:1.3rem auto;padding:0 1rem;background:#0d1117;color:#e6edf3}"
      "h1{font-size:1.35rem}h2{font-size:1rem;color:#cfae6d;margin:1.2rem 0 .3rem}.sub{color:#8b949e;font-size:.84rem}"
      "table{border-collapse:collapse;width:100%%;font-size:.82rem}td,th{padding:.35rem .5rem;border-bottom:1px solid #21262d;text-align:left}.n{text-align:right}.m{color:#8b949e}"
      ".z{display:inline-block;padding:.1rem .5rem;border-radius:99px;background:#161b22;margin:.1rem;font-size:.78rem}</style>"
      "<h1>Clips sorted into the 54 node-worlds</h1>"
      "<div style='margin:.3rem 0'><a href='engine_recipes.html' style='color:#cfae6d'>&rarr; Reverse-engineered render recipes (the 4 models)</a> · <a href='storyboard.html' style='color:#cfae6d'>&rarr; storyboard</a></div>"
      "<div class=sub>%d unique clips mapped across %d node-worlds (%d total assignments — a song that spans "
      "several nodes is reference for each) · by zone: %s · %d unmapped productions (tests/OLD/the-film-itself). "
      "Each node's clips = style/storyboard reference for that node's LoRA; each scene draws candidates from its zone. Generated %s.</div>"
      "<div style='margin:.6rem 0'>%s</div>"
      "<h2>Node-worlds (clip count each)</h2><table><thead><tr><th>node</th><th>zone</th><th class=n>clips</th></tr></thead><tbody>%s</tbody></table>"
      "<h2>60-scene script — candidate reference clips per scene (by zone)</h2><table><thead><tr><th>scene</th><th>zone</th><th class=n>candidates</th><th>heading</th></tr></thead><tbody>%s</tbody></table>"
      %(payload["mapped_clips"],len(by_node),payload["node_assignments"],
        " · ".join("%s %d"%(z,c) for z,c in payload["by_zone_counts"].items()),
        len(unmapped),esc(gen),
        " ".join("<span class=z>%s: %d</span>"%(esc(z),c) for z,c in payload["by_zone_counts"].items()),
        nrows,srows))
    open(os.path.join(SB,"node_clips.html"),"w",encoding="utf-8").write(html)
    print("clip_nodes: %d clips mapped -> %d node-worlds (%d unmapped prods)"%(payload["mapped_clips"],len(by_node),len(unmapped)))
    print("  by zone:",payload["by_zone_counts"])
    print("  scene-reference: %d scenes, each with zone-matched candidate clips"%len(scene_ref))
    print("  -> reports/_status/storyboard/node_clips.html")
    return 0

if __name__=="__main__":
    if sys.platform=="win32":
        import io; sys.stdout=io.TextIOWrapper(sys.stdout.buffer,encoding="utf-8",errors="replace")
    sys.exit(main())
