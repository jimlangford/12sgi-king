#!/usr/bin/env python3
# _quados_style.py - the ONE Yale-blue Quad-OS stylesheet for the PRIVATE owner pages (RE report, curse-breaker,
# onboarding, RAM loop). These are written straight to king-local and DON'T pass through build_site's recolor,
# so they must carry the palette themselves. Matches go.html / 12sgi-design 2026-06-16 (light, easier to read).
# Import: from _quados_style import STYLE, moon_banner, pono_note
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path: sys.path.insert(0, HERE)

STYLE = """<style>
:root{--bg:#081420;--panel:#0f2540;--panel2:#16324e;--line:#26456a;--ink:#eaf2fc;--dim:#9fb2c8;--faint:#7f93aa;
 --accent:#4a9eff;--accent2:#6cb0f0;--ok:#1f8a5b;--gold:#e3ad33;--warn:#b07d1a;--moon:#2e2a5c;--err:#b4242c}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font-family:'Segoe UI Variable Text','Segoe UI',system-ui,sans-serif;line-height:1.55;padding:22px}
.wrap{max-width:940px;margin:0 auto}
h1{font-size:22px;margin:.2rem 0;color:var(--ink)} h2{color:var(--accent);font-size:1.06rem;margin:1rem 0 .3rem}
.priv{display:inline-block;font:600 10.5px/1 Consolas,monospace;letter-spacing:1px;text-transform:uppercase;color:var(--err);border:1px solid #6a3030;background:#2a1416;border-radius:6px;padding:3px 9px;margin-left:8px;vertical-align:middle}
.sub{color:var(--dim);font-size:13px;margin:6px 0 12px;line-height:1.5}
.moon{background:linear-gradient(180deg,#eef1fb,#f6f8fc);border:1px solid #d3d8ef;border-left:3px solid var(--moon);border-radius:10px;padding:.6rem .9rem;margin:.6rem 0;color:#3a3766;font-size:.92rem}
.moon .ml{font:600 10.5px/1 Consolas,monospace;letter-spacing:.06em;text-transform:uppercase;color:#5b5fb0}.moon b{color:var(--moon)}
.pono{background:#0f2540;border:1px solid #bfe0cc;border-left:3px solid var(--ok);border-radius:10px;padding:.7rem 1rem;color:#1f5a3c;font-size:.88rem;margin:.8rem 0;line-height:1.5}.pono b{color:#13402a}
.kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin:1rem 0}
@media(max-width:560px){.kpis{grid-template-columns:repeat(2,1fr)}}
.kp{background:var(--panel);border:1px solid var(--line);border-radius:11px;padding:.7rem .85rem}
.kv{font:700 19px/1 'JetBrains Mono',Consolas,monospace;color:var(--accent)}.kl{font-size:10px;color:var(--faint);text-transform:uppercase;letter-spacing:.5px;margin-top:4px}
.card,.e{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:.75rem 1rem;margin:.7rem 0}
.eh{display:flex;align-items:baseline;gap:12px;flex-wrap:wrap}.eh h2{color:var(--ink);font-size:1.05rem;margin:.2rem 0}
.kpi{font:600 12px/1 'JetBrains Mono',Consolas,monospace;color:var(--accent)}
.role{font:600 10.5px/1 Consolas,monospace;letter-spacing:.04em;text-transform:uppercase;color:#1f5a3c;background:#0f2540;border:1px solid #bfe0cc;border-radius:99px;padding:3px 9px}
.gave{font-size:.9rem;color:var(--accent2);margin:.35rem 0}
.q{font-size:.95rem;color:var(--ink);margin:.45rem 0;line-height:1.5}
.top{margin:.2rem 0 .4rem;padding-left:1.1rem;color:var(--dim);font-size:.85rem}.top li{margin:.15rem 0}
.cb{background:#241d0e;border:1px solid #5c4a1e;border-left:3px solid var(--gold);border-radius:10px;padding:.6rem .9rem;color:#e3c98a;font-size:.9rem;margin-top:.5rem;line-height:1.5}.cb b{color:#3f3410}
.foot{color:var(--faint);font-size:11px;margin-top:1.2rem;line-height:1.6}
a{color:var(--accent2)}
/* industry % bars (donor/federal breakdowns) */
.ind{margin:.5rem 0 1rem}.ind .row{display:grid;grid-template-columns:170px 1fr 64px;gap:10px;align-items:center;margin:.28rem 0;font-size:.86rem}
.ind .nm{color:var(--ink);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.ind .tr{background:var(--panel2);border-radius:99px;height:13px;overflow:hidden}
.ind .tr i{display:block;height:13px;border-radius:99px;background:linear-gradient(90deg,var(--accent),var(--accent2))}
.ind .pc{font:700 12px/1 'JetBrains Mono',Consolas,monospace;color:var(--accent);text-align:right}
@media(max-width:560px){.ind .row{grid-template-columns:120px 1fr 52px}}
</style>"""

def moon_banner(reading, ao_po=None):
    """A kaulana-mahina banner from moon_calendar.reading(today). Pass ao_po if known."""
    if not reading: return ""
    ap = (" · %s key" % ao_po) if ao_po else ""
    return ("<div class=moon><span class=ml>&#9790; kaulana mahina &middot; p&#333; %s %s &middot; %s%s</span>"
            "<div style='margin-top:.25rem'>%s</div></div>") % (
            reading.get("night","?"), _e(reading.get("po","")), _e(reading.get("phase","")), ap,
            _e(reading.get("nature","")))

def _e(s): return str(s if s is not None else "").replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
