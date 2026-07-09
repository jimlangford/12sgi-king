#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""deploy_map_wp.py — build the elementLOTUS-NATIVE map embed from the ONE source of truth.

RESILIENCE (James 2026-07-02): elementLOTUS must NOT depend on 12sgi.com at runtime. So instead of an
iframe pointing at 12sgi, we inline the WHOLE map into the WordPress page via <iframe srcdoc="…"> —
elementLOTUS then serves its OWN independent copy. 12sgi going down never affects elementLOTUS.

SINGLE SOURCE OF TRUTH: reports/mauios/maui_parcel_map.html (the same artifact 12sgi publishes).
BUILD-ONCE → DEPLOY-BOTH: build_site.py → 12sgi.com; THIS tool → the elementLOTUS-native embed.
Re-run after any map change to refresh the WordPress copy. The map loads Leaflet/esri/OSM/GIS directly
from their own CDNs/services (independent of 12sgi) and has a graceful fallback if any is unreachable.

Output: content/embeds/elementlotus_map_native_embed.html  (paste into a WP Custom HTML block, Full width)
Run:    python -X utf8 tools/kilo-aupuni/deploy_map_wp.py
"""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC  = os.path.join(ROOT, "reports", "mauios", "maui_parcel_map.html")
OUT  = os.path.join(ROOT, "content", "embeds", "elementlotus_map_native_embed.html")

WRAP_HEAD = """<!-- elementLOTUS govOS — Maui Interactive Civic Map — NATIVE COPY (no cross-site runtime dependency).
     The full map is inlined below via iframe srcdoc, so elementLOTUS serves its OWN copy and renders
     independently of any other host. Single source of truth: the govOS map artifact — re-run the deploy tool after edits. -->
<style>
.elm-map-wrap{--gold:#e3ad33;--ink:#0b0f0d;max-width:1240px;margin:1.6rem auto;padding:0 clamp(0px,2vw,1rem);font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif}
.elm-map-card{border:1px solid rgba(227,173,51,.38);border-radius:16px;overflow:hidden;box-shadow:0 10px 34px rgba(0,0,0,.14);background:var(--ink)}
.elm-map-bar{display:flex;align-items:center;gap:.7rem 1rem;flex-wrap:wrap;padding:.9rem 1.15rem;background:linear-gradient(90deg,#0b0f0d,#141109);border-bottom:1px solid rgba(227,173,51,.3)}
.elm-map-bar .k{font-size:.62rem;letter-spacing:.17em;text-transform:uppercase;color:var(--gold);font-weight:800;margin-bottom:2px}
.elm-map-bar h3{margin:0;font-size:1.12rem;color:#f4efe2;font-weight:700;line-height:1.2}
.elm-map-bar .sub{color:#9aa08f;font-size:.82rem;flex:1 1 240px;min-width:180px}
.elm-map-frame{width:100%;height:min(82vh,880px);border:0;display:block;background:var(--ink)}
.elm-map-foot{padding:.6rem 1.15rem;background:var(--ink);color:#7f8676;font-size:.72rem;border-top:1px solid rgba(255,255,255,.06)}
@media(max-width:640px){.elm-map-bar h3{font-size:1rem}.elm-map-frame{height:min(76vh,560px)}}
</style>
<div class="elm-map-wrap"><div class="elm-map-card">
  <div class="elm-map-bar">
    <div><div class="k">elementLOTUS &middot; govOS &middot; Maui County</div><h3>Interactive Parcel Map &amp; Civic Overlays</h3></div>
    <span class="sub">Click any parcel (TMK, zoning, SMA) &middot; toggle overlays: county money &middot; 12 Stones wealth &middot; Hawaiian-held &amp; trust lands &middot; cost quote</span>
  </div>
  <iframe class="elm-map-frame" title="Maui interactive parcel map and civic overlays (native copy)" loading="lazy" allow="fullscreen" referrerpolicy="no-referrer" srcdoc="__MAP__"></iframe>
  <div class="elm-map-foot">Live public data &middot; Hawai&#699;i Statewide GIS &middot; sourced, never fabricated &middot; native copy (this page renders independently of any other site).</div>
</div></div>
"""


def build():
    with open(SRC, encoding="utf-8") as f:
        m = f.read()
    # escape for a double-quoted srcdoc attribute value: & and " (browser un-escapes, then parses as HTML)
    esc = m.replace("&", "&amp;").replace('"', "&quot;")
    out = WRAP_HEAD.replace("__MAP__", esc)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write(out)
    return OUT, len(m), len(out)


if __name__ == "__main__":
    path, src_bytes, out_bytes = build()
    print("deploy_map_wp: native WP embed built ->", path)
    print("  single source: reports/mauios/maui_parcel_map.html (%d bytes) -> srcdoc embed (%d bytes)" % (src_bytes, out_bytes))
    print("  NO 12sgi reference (grep):", "12sgi" not in open(path, encoding="utf-8").read())
