#!/usr/bin/env python3
# king_recolor.py - the standing Yale-blue recolor for the PRIVATE King (Jimmy 2026-06-16: drive the private
# server to 100% blue). The public build recolors site/; the private owner-only pages + King-app .dc components
# land in king-local and bypass that. This applies the SAME dark->Yale-blue map IN PLACE to any king-local .html
# still in the old dark theme (case_files, daily_learnings, the .dc components). Re-runnable + idempotent — run it
# after any King rebuild (king-extract is volatile). Color-only: never touches structure/scripts/data. Stdlib only.
import os, sys, glob
HOME=os.path.expanduser("~")
KLS=[os.path.join(HOME,"AppData","Local","king-extract","deploy","king-local"),
     os.path.join(HOME,"Documents","Claude","Projects","Video System elementLOTUS","king-local")]
# dark -> Yale-blue (mirrors build_site._RECOLOR; cosmology zone hexes left alone)
MAP=[("#0c100e","#ffffff"),("#0b0f12","#ffffff"),("#0b0f0d","#f3f7fc"),("#080c12","#ffffff"),("#0a0e14","#ffffff"),
     ("#0c0b09","#ffffff"),("#0a0c10","#ffffff"),("#0b0e14","#f3f7fc"),("#0e1622","#eef1fb"),
     ("#151d19","#e7eef8"),("#121714","#e7eef8"),("#16140f","#e7eef8"),("#11160f","#e7eef8"),("#1a2420","#e7eef8"),("#13171a","#e7eef8"),
     ("#1e1b14","#dae5f3"),("#1a1610","#dae5f3"),("#1a130d","#fbf6ea"),("#2a261c","#ccddef"),("#241c06","#ccddef"),
     ("#243029","#26456a"),("#2a2f29","#26456a"),("#34301f","#26456a"),("#213049","#d3d8ef"),("#25323a","#26456a"),("#5a3a1a","#5c4a1e"),
     ("#efe9da","#13243d"),("#e8e4d8","#13243d"),("#eef3ef","#13243d"),("#f0ead8","#13243d"),("#f4eeda","#13243d"),
     ("#cfc9b6","#41536b"),("#bdb8a4","#41536b"),("#b3a98f","#41536b"),("#e8d9b0","#5a4a16"),
     ("#9a957f","#5b6e86"),("#8a8674","#5b6e86"),("#756b56","#5b6e86"),("#9fb1a6","#5b6e86"),("#6f8278","#5b6e86"),("#9fb4c0","#41536b"),
     ("#d9b24c","#00356b"),("#e3ad33","#00356b"),("#f0cf7a","#1259a3"),("#f4c95d","#1259a3"),("#f3d589","#1259a3"),("#e7c361","#1259a3"),("#e0a45a","#b8860b"),
     ("#9fd9bf","#1f8a5b"),("#c8efd9","#1f8a5b"),("#56c08a","#1f8a5b"),("#5fc0d8","#1259a3"),("#3a8fb7","#00356b"),
     ("#ecdfff","#2e2a5c"),("#efe4ff","#2e2a5c"),("#cdb4f0","#5b5fb0"),
     ("#d9622b","#b8860b"),("#e06c6c","#b4242c"),("#4a2222","#6a3030"),("#7f8a78","#5b6e86"),("#bcd0ea","#41536b"),("#cfe0c9","#1f5a3c"),("#8fae7e","#1f5a3c"),
     ("background:#0b0f","background:#fff")]
DARK_MARK=("#0c100e","#0b0f12","#151d19","#11160f","#1a130d","#0e1622","#1a2420","#243029",
           "#0c0b09","#0a0c10","#0b0e14","#0b0f0d","#16140f")
# NEVER-TOUCH GUARD (2026-07-09 heal-audit fix): the FRESH Yale-blue civic register (Jimmy 2026-07-08,
# artifact govOS-civic-fresh-yale-blue — deep navy #081420 + glass, a DELIBERATE dark design, not stale
# old-King obsidian) must never be flattened by this script, even if a future page happens to carry one
# of the old DARK_MARK hexes for an unrelated reason. Any page carrying this marker is skipped entirely.
FRESH_REGISTER_MARK = 'class="govos"'
def is_dark(h): return any(d in h for d in DARK_MARK)
import re as _re
_VIEWPORT=('<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">'
           '<meta name="theme-color" content="#00356b">')
_MOBILE_CSS=('<style id="mobile-heal">img,video,svg{max-width:100%;height:auto}table,pre{max-width:100%}'
             '@media(max-width:680px){html{overflow-x:hidden}table{display:block;overflow-x:auto;-webkit-overflow-scrolling:touch}'
             'td,th{word-break:break-word;overflow-wrap:anywhere}pre{white-space:pre-wrap}}</style>')
def ensure_mobile(html):
    """Same mobile-heal as build_site: viewport meta + no-overflow CSS if missing, so the private King reads on iPhone/iPad."""
    add=("" if "width=device-width" in html else _VIEWPORT)+("" if 'id="mobile-heal"' in html else _MOBILE_CSS)
    if not add: return html
    for pat in (r"<meta\s+charset[^>]*>", r"<head[^>]*>", r"<!doctype[^>]*>"):
        m=_re.search(pat,html,_re.I)
        if m: return html[:m.end()]+add+html[m.end():]
    return add+html

def main():
    total=recolored=mobiled=0
    for KL in KLS:
        if not os.path.isdir(KL): continue
        for f in glob.glob(os.path.join(KL,"*.html")):
            try: h=open(f,encoding="utf-8",errors="replace").read()
            except Exception: continue
            if FRESH_REGISTER_MARK in h:
                continue  # the new fresh-navy civic register — never recolor
            total+=1; new=h
            if is_dark(new):
                for a,b in MAP: new=new.replace(a,b)
                if new!=h: recolored+=1
            m=ensure_mobile(new)
            if m!=new: mobiled+=1; new=m
            if new!=h:
                open(f,"w",encoding="utf-8",newline="\n").write(new)
    print("king_recolor: %d page(s) recolored Yale-blue, %d given the mobile viewport (private King)"%(recolored,mobiled))
    return 0

if __name__=="__main__":
    if sys.platform=="win32":
        import io; sys.stdout=io.TextIOWrapper(sys.stdout.buffer,encoding="utf-8",errors="replace")
    sys.exit(main())
