#!/usr/bin/env python3
# tenant_coverage_heatmap.py - HIDDEN-DATA DASHBOARD (Jimmy 2026-07-01): tenant_registry.json's 9-dimension
# x 16-tenant "reports" coverage matrix already backs the public tenant-switcher on every jurisdiction page,
# but the coverage picture itself (who's fully reported, who's a stub) had zero visual surface -- it just
# sat inside a config file. This renders it as an actual heatmap. Public-safe: the registry is the SAME
# data already embedded in every public tenant page's switcher, nothing new is exposed.
import json, os
from datetime import datetime, timezone, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
SITE = os.path.join(REPO, "site")
REGISTRY = os.path.join(REPO, "tenant_registry.json")
OUT_F = os.path.join(SITE, "tenant_coverage.html")
HST = timezone(timedelta(hours=-10))


def esc(s):
    return str(s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def main():
    reg = json.load(open(REGISTRY, encoding="utf-8"))
    classes = reg.get("report_classes", [])
    tenants = reg.get("civic_tenants", [])
    if not classes or not tenants:
        print("tenant_coverage_heatmap: registry empty or missing report_classes/civic_tenants -- skipping")
        return 0

    cell_w, cell_h, label_w, head_h = 34, 26, 150, 90
    grid_w = label_w + len(classes) * cell_w
    grid_h = head_h + len(tenants) * cell_h

    cells = []
    # column headers (rotated labels)
    for ci, c in enumerate(classes):
        x = label_w + ci * cell_w + cell_w / 2
        cells.append(
            f'<text x="{x}" y="{head_h-8}" font-size="10" fill="#9a957f" font-family="Consolas,monospace" '
            f'text-anchor="start" transform="rotate(-55 {x} {head_h-8})">{esc(c.get("label", c.get("key","")))}</text>'
        )
    filled_total = 0
    cell_total = 0
    for ti, t in enumerate(tenants):
        y = head_h + ti * cell_h
        cells.append(
            f'<text x="0" y="{y+cell_h/2+4}" font-size="11" fill="#e8e4d8" font-family="Consolas,monospace">{esc(t.get("name",""))}</text>'
        )
        for ci, c in enumerate(classes):
            k = c.get("key")
            filled = bool((t.get("reports") or {}).get(k))
            cell_total += 1
            if filled:
                filled_total += 1
            x = label_w + ci * cell_w
            color = "#3a8a60" if filled else "#2a231a"
            cells.append(f'<rect x="{x+2}" y="{y+2}" width="{cell_w-4}" height="{cell_h-4}" rx="3" fill="{color}"/>')
    pct = round(filled_total / cell_total * 100) if cell_total else 0
    svg = f'<svg viewBox="0 0 {grid_w+20} {grid_h+10}" width="100%" height="{grid_h+10}">{"".join(cells)}</svg>'

    g = datetime.now(HST).strftime("%Y-%m-%d %H:%M HST")
    html = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Tenant Coverage - govOS</title>
<style>
 body{{margin:0;background:#0c100e;color:#e8e4d8;font-family:Georgia,serif;line-height:1.5}}
 .wrap{{max-width:1000px;margin:0 auto;padding:32px 22px 60px;overflow-x:auto}}
 .eyebrow{{font-family:Consolas,monospace;font-size:11px;letter-spacing:1.2px;color:#d9b24c;text-transform:uppercase}}
 h1{{font-size:25px;margin:8px 0 2px}}
 .disc{{font-size:12px;color:#9a957f;font-style:italic;border-left:2px solid rgba(224,106,74,.5);padding:7px 12px;margin:12px 0;background:rgba(224,106,74,.05)}}
 .big{{font-size:34px;font-weight:700;color:#d9b24c;font-family:Consolas,monospace}}
 .legend{{font-size:11px;color:#9a957f;margin:8px 0 18px;font-family:Consolas,monospace}}
 .legend span{{display:inline-block;width:11px;height:11px;border-radius:2px;margin-right:5px;vertical-align:middle}}
 footer{{margin-top:36px;border-top:1px solid rgba(255,255,255,.1);padding-top:12px;font-family:Consolas,monospace;font-size:10.5px;color:#9a957f}}
</style></head><body><div class="wrap">
<div class="eyebrow">govOS · Kilo Aupuni · tenant coverage</div>
<h1>How Deep Is Each Government's Record?</h1>
<div class="disc">Every tenant is measured against the same {len(classes)} testimony dimensions Maui County answers
in full (who governs, money behind them, contracts, federal dollars, money&times;votes, agendas, minutes,
charter&harr;law, audit balance). Green = a real sourced page exists; dark = not built yet. This is a coverage
map, not a judgment on any government -- it shows where OUR reporting is thin, and where to build next.</div>
<div class="big">{filled_total} / {cell_total} &middot; {pct}% filled</div>
<div class="legend"><span style="background:#3a8a60"></span>reported &nbsp; <span style="background:#2a231a"></span>not yet built</div>
{svg}
<footer>generated {g} · sourced from tenant_registry.json, the same registry every jurisdiction page's tenant-switcher already reads · govOS</footer>
</div></body></html>"""
    os.makedirs(SITE, exist_ok=True)
    with open(OUT_F, "w", encoding="utf-8") as f:
        f.write(html)
    print("tenant_coverage_heatmap: %d/%d cells filled (%d%%) -> %s" % (filled_total, cell_total, pct, OUT_F))
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
