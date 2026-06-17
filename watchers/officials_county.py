#!/usr/bin/env python3
# officials_county.py - 'Who governs' roster pages for the Hawaiʻi county tenants (Jimmy 2026-06-16).
# Renders officials_<county>.html from config/county_officials.json (sourced rosters from each council's
# OFFICIAL site). Closes the 'Who governs' gap for the counties that had no roster. Facts + source link only;
# nothing invented. Stdlib only. Add a county to the config and re-run -> its page + registry mapping follow.
import os, sys, json
from datetime import datetime, timedelta, timezone
HST=timezone(timedelta(hours=-10))
HOME=os.path.expanduser("~"); PROJ=os.path.join(HOME,"Documents","Claude","Projects","Video System elementLOTUS")
M=os.path.join(PROJ,"reports","mauios"); CFG=os.path.join(PROJ,"config","county_officials.json")
def esc(s): return str(s if s is not None else "").replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")

def page(slug, c, gen):
    rows="".join(
        "<tr><td class=d>%s</td><td class=nm>%s</td><td class=role>%s</td></tr>"%(
            esc(m["district"]),esc(m["name"]),esc(m.get("role") or ""))
        for m in c["members"])
    html=("<!doctype html><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'>"
      "<title>%s — who governs | govOS</title><style>"
      "body{font-family:'Segoe UI',system-ui,sans-serif;max-width:900px;margin:1.3rem auto;padding:0 1rem;color:#13243d;background:#fff}"
      "h1{font-size:1.5rem;margin:.3rem 0}.sub{color:#41536b;font-size:.9rem;line-height:1.5}"
      ".disc{background:#eef2f7;border:1px solid #bacde6;border-radius:10px;padding:.7rem 1rem;color:#41536b;font-size:.85rem;margin:.8rem 0}"
      "table{border-collapse:collapse;width:100%%;font-size:.9rem;margin-top:.4rem}td,th{padding:.45rem .6rem;border-bottom:1px solid #e3e9f1;text-align:left}"
      ".d{font-family:Consolas,monospace;color:#1259a3;white-space:nowrap;width:1%%}.nm{font-weight:600;color:#00356b}"
      ".role{color:#1f8a5b;font-size:.82rem;font-family:Consolas,monospace}th{color:#6d7f97;font-size:.72rem;letter-spacing:.5px;text-transform:uppercase}a{color:#1259a3}</style>"
      "<h1>%s — who governs</h1>"
      "<div class=sub>The %d-seat council for %s. Source: <a href='%s'>%s</a> · generated %s.</div>"
      "<div class=disc>Public record, presented as facts — who represents each district, and who chairs the body. "
      "The voting record + money behind each seat fills in as this council's minutes are parsed (the way Maui's did).</div>"
      "<table><thead><tr><th>district</th><th>member</th><th>role</th></tr></thead><tbody>%s</tbody></table>"
      "<p class=sub style='margin-top:1rem'><a href='tenant_%s.html'>&larr; %s overview</a> &middot; "
      "<a href='federal_officials.html'>federal delegation</a> &middot; <a href='tenants_hub.html'>all governments</a></p>")%(
      esc(c["name"]),esc(c["name"]),c.get("seats",len(c["members"])),esc(c.get("jurisdiction","")),
      esc(c["source"]),esc(c["source_label"]),esc(gen),rows,esc(c["tenant"]),esc(c["name"]),)
    fn="officials_%s.html"%slug
    with open(os.path.join(M,fn),"w",encoding="utf-8",newline="\n") as f: f.write(html)
    return fn

def main():
    d=json.load(open(CFG,encoding="utf-8"))
    gen=datetime.now(HST).strftime("%Y-%m-%d %H:%M HST")
    made=[]
    for slug,c in d.get("counties",{}).items():
        fn=page(slug,c,gen); made.append((c["tenant"],fn,len(c["members"])))
    print("officials_county: %d roster page(s) written"%len(made))
    for tid,fn,n in made: print("  %-14s %d members -> %s"%(tid,n,fn))
    print("  WIRE: map each tenant's 'govern' dimension to its officials_<county>.html in tenant_depth.FILES")
    return 0

if __name__=="__main__":
    if sys.platform=="win32":
        import io; sys.stdout=io.TextIOWrapper(sys.stdout.buffer,encoding="utf-8",errors="replace")
    sys.exit(main())
