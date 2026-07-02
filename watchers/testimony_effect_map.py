#!/usr/bin/env python3
# testimony_effect_map.py - Kilo Aupuni: WHERE the real-estate industry's advocacy meets the ground.
#
# Bill 9 (STR phase-out) drew 22 real-estate-industry testimony hits (testimony_crosscheck.json).
# The SAME public record (maui_re_report.json + the county ownership extract) already identifies
# 23 real-estate entities that BOTH fund Maui's deciders AND own recorded parcels. This script joins
# those entities to their ACTUAL parcel geometry (Hawaii statewide GIS, keyless/CORS-open) and plots
# them as an in-house SVG map — no external map service, no API key, no CDN.
#
# INTEGRITY (non-negotiable, same rule as every Kilo Aupuni page): this maps WHERE the industry's
# donor-entities hold property, laid next to the fact that the industry testified. It is NOT a claim
# that any specific testifier owns any specific parcel, nor that testimony caused a vote. The roll-call
# that would complete that triangle is UIPA-requested, not machine-accessible, and not faked here.
# Stdlib only + one keyless HTTPS call to a public government GIS server.
import json, os, re, urllib.request, urllib.parse
from datetime import datetime, timezone, timedelta

HOME = os.path.expanduser("~")
PROJECT = os.path.join(HOME, "Documents", "Claude", "Projects", "Video System elementLOTUS")
MAUIOS = os.path.join(PROJECT, "reports", "mauios")
STATUS = os.path.join(PROJECT, "reports", "_status")
RE_REPORT = os.path.join(STATUS, "maui_re_report.json")
CROSSCHECK = os.path.join(STATUS, "testimony_crosscheck.json")
EXTRACT = os.path.join(MAUIOS, "property", "_rpt_extracts", "fullownr26.txt")
OUT_F = os.path.join(MAUIOS, "testimony_effect_map.html")
GIS = "https://geodata.hawaii.gov/arcgis/rest/services/ParcelsZoning/MapServer/30/query"
HST = timezone(timedelta(hours=-10))
MAX_TMK_PER_ENTITY = 15   # representative sample per entity -- keeps the GIS call light + the map legible


def now_hst():
    return datetime.now(HST)


def esc(s):
    return str(s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def load(p, d=None):
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception:
        return d


def entity_tokens(name):
    stop = {"llc", "lp", "inc", "corp", "ltd", "llp", "lllp", "dba", "the", "and", "of", "co",
            "company", "trust", "revocable", "living", "family", "partnership", "partners",
            "holdings", "group", "et", "al", "ii", "iii", "iv", "jr", "sr"}
    toks = [w for w in re.findall(r"[a-z0-9]+", (name or "").lower()) if len(w) > 2]
    return set(w for w in toks if w not in stop)


def find_tmks_for_entity(entity_names, limit=MAX_TMK_PER_ENTITY):
    """Scan the fixed-width county ownership extract once, matching by core-token subset (same
    conservative rule as maui_re_report.py) -- never a bare substring match. Returns first `limit`
    9-digit GIS-format TMKs (13-digit extract TMK truncated to the 9-digit zone-section-plat-parcel
    the statewide GIS layer keys on -- confirmed by test query, CPR/unit suffix dropped)."""
    wanted = {nm.upper(): entity_tokens(nm) for nm in entity_names}
    found = {nm: [] for nm in entity_names}
    if not os.path.exists(EXTRACT):
        return found
    with open(EXTRACT, encoding="utf-8", errors="ignore") as f:
        for line in f:
            if len(line) < 13:
                continue
            tmk13 = line[:13]
            if not tmk13.isdigit():
                continue
            owner = line[13:].strip()
            if not owner:
                continue
            owner_core = entity_tokens(owner)
            for nm, core in wanted.items():
                if len(found[nm]) >= limit:
                    continue
                if core and core.issubset(owner_core):
                    tmk9 = tmk13[:9]
                    if tmk9 not in found[nm]:
                        found[nm].append(tmk9)
    return found


def fetch_centroids(tmks):
    """Batch-query the keyless statewide GIS parcel layer, chunked to keep URLs short. Returns
    {tmk: (x, y)} in the layer's native projected coords (Hawaii State Plane) -- we never need
    lat/lon since this renders as a relative in-house map, not tiles under a basemap."""
    out = {}
    chunk = 80
    tmk_list = list(tmks)
    for i in range(0, len(tmk_list), chunk):
        batch = tmk_list[i:i + chunk]
        where = "tmk IN (%s)" % ",".join(batch)
        params = {"where": where, "outFields": "tmk", "returnGeometry": "true",
                  "f": "json", "geometryPrecision": "0"}
        url = GIS + "?" + urllib.parse.urlencode(params)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "12sgi-kilo-aupuni/1.0 (civic transparency)"})
            with urllib.request.urlopen(req, timeout=30) as r:
                data = json.loads(r.read().decode("utf-8", "replace"))
        except Exception:
            continue
        for feat in data.get("features", []):
            tmk = str(feat.get("attributes", {}).get("tmk", ""))
            rings = (feat.get("geometry") or {}).get("rings") or []
            if not tmk or not rings:
                continue
            pts = rings[0]
            if not pts:
                continue
            cx = sum(p[0] for p in pts) / len(pts)
            cy = sum(p[1] for p in pts) / len(pts)
            out[tmk] = (cx, cy)
    return out


def svg_map(points, width=760, height=560, pad=40):
    """points: list of (x, y, radius, color, label). Projects the true GIS coordinates into the SVG
    viewBox (flip Y -- screen space grows down, map space grows up) -- a genuine relative map, not a
    schematic; clustering/spread reflects real geography even without a basemap underneath it."""
    if not points:
        return ""
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    minx, maxx = min(xs), max(xs)
    miny, maxy = min(ys), max(ys)
    spanx = (maxx - minx) or 1
    spany = (maxy - miny) or 1
    scale = min((width - 2 * pad) / spanx, (height - 2 * pad) / spany)

    def proj(x, y):
        sx = pad + (x - minx) * scale
        sy = height - pad - (y - miny) * scale   # flip: north stays up
        return sx, sy

    circles = []
    for x, y, r, color, label in points:
        sx, sy = proj(x, y)
        circles.append(f'<circle cx="{sx:.1f}" cy="{sy:.1f}" r="{r:.1f}" fill="{color}" opacity="0.65" stroke="{color}" stroke-width="1"><title>{esc(label)}</title></circle>')
    return (f'<svg viewBox="0 0 {width} {height}" width="100%" height="{height}" style="background:#0f1712;border-radius:8px" '
            f'role="img" aria-label="parcel effect map">{"".join(circles)}</svg>')


def main():
    re_report = load(RE_REPORT, {})
    cross = load(CROSSCHECK, {})
    entities = re_report.get("entities", [])
    if not entities:
        print("testimony_effect_map: no entities in maui_re_report.json -- skipping")
        return 0

    names = [e["entity"] for e in entities]
    tmk_by_entity = find_tmks_for_entity(names)
    all_tmks = sorted({t for lst in tmk_by_entity.values() for t in lst})
    centroids = fetch_centroids(all_tmks) if all_tmks else {}

    max_donated = max((e.get("donated") or 0) for e in entities) or 1
    points = []
    legend_rows = []
    matched_entities = 0
    matched_parcels = 0
    for e in entities:
        nm = e["entity"]
        tmks = tmk_by_entity.get(nm, [])
        donated = e.get("donated") or 0
        r = 4 + min(14, (donated / max_donated) * 14)
        color = "#e06a4a" if donated > 5000 else "#d9b24c" if donated > 1000 else "#6a9ad9"
        found_here = 0
        for t in tmks:
            c = centroids.get(t)
            if c:
                points.append((c[0], c[1], r, color, "%s -- TMK %s -- $%s donated" % (nm, t, "{:,.0f}".format(donated))))
                found_here += 1
        if found_here:
            matched_entities += 1
            matched_parcels += found_here
            legend_rows.append((nm, found_here, donated, e.get("parcels", 0)))

    legend_rows.sort(key=lambda r: -r[2])
    svg = svg_map(points)
    industry_testimony = ((cross.get("industries") or {}).get("real_estate") or {}).get("testimony", [])
    hits_total = sum(t.get("industry_hits", 0) for t in industry_testimony)

    legend_html = "".join(
        f'<div class="lg"><span class="dot" style="background:{"#e06a4a" if d>5000 else "#d9b24c" if d>1000 else "#6a9ad9"}"></span>'
        f'<span class="nm">{esc(nm)}</span><span class="ct">{n} of {tot} parcels mapped &middot; ${d:,.0f} donated</span></div>'
        for nm, n, d, tot in legend_rows
    )

    g = now_hst().strftime("%Y-%m-%d %H:%M HST")
    html = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Testimony Effect Map - Maui - 12 Stones</title>
<style>
 body{{margin:0;background:#0c100e;color:#e8e4d8;font-family:Georgia,serif;line-height:1.5}}
 .wrap{{max-width:900px;margin:0 auto;padding:32px 22px 60px}}
 .eyebrow{{font-family:Consolas,monospace;font-size:11px;letter-spacing:1.2px;color:#d9b24c;text-transform:uppercase}}
 h1{{font-size:25px;margin:8px 0 2px}}
 .disc{{font-size:12px;color:#9a957f;font-style:italic;border-left:2px solid rgba(224,106,74,.5);padding:7px 12px;margin:12px 0;background:rgba(224,106,74,.05)}}
 .big{{font-size:15px;color:#bdb8a4;font-family:Consolas,monospace;margin:10px 0 16px}}
 .lg{{display:flex;gap:10px;align-items:baseline;font-size:12px;padding:4px 0;border-bottom:1px solid rgba(255,255,255,.06)}}
 .dot{{display:inline-block;width:10px;height:10px;border-radius:50%;flex-shrink:0}}
 .nm{{color:#e8e4d8;min-width:220px}}
 .ct{{color:#9a957f;font-family:Consolas,monospace;font-size:11px}}
 footer{{margin-top:36px;border-top:1px solid rgba(255,255,255,.1);padding-top:12px;font-family:Consolas,monospace;font-size:10.5px;color:#9a957f}}
</style></head><body><div class="wrap">
<div class="eyebrow">12 Stones Global &middot; Kilo Aupuni &middot; testimony effect map</div>
<h1>Where the Advocacy Meets the Ground</h1>
<div class="disc">This maps WHERE real-estate-industry donor-entities hold recorded Maui parcels, next to
the fact that the same industry testified {hits_total} times on Bill 9 (short-term-rental phase-out).
It does <b>not</b> claim any specific testifier owns any specific parcel, and it does not claim testimony
caused a vote -- the committee roll-call that would complete that triangle is UIPA-requested and
withheld from machine access, never faked. Circle size and color = campaign dollars donated by that
entity; position = real recorded parcel location (Hawai&#699;i statewide GIS, public record).</div>
<div class="big">{matched_entities} of {len(entities)} donor-entities mapped &middot; {matched_parcels} parcels plotted (sampled, max {MAX_TMK_PER_ENTITY}/entity) &middot; {hits_total} industry testimony hits on Bill 9</div>
{svg or '<div style="color:#9a957f;font-size:13px">No parcel geometry resolved this run -- GIS server may be unavailable.</div>'}
<h2 style="font-size:16px;margin-top:22px">Entities mapped</h2>
{legend_html or '<div style="color:#9a957f;font-size:12px">none</div>'}
<footer>generated {g} &middot; sources: Hawai&#699;i statewide parcels GIS (geodata.hawaii.gov, keyless public) + Maui County ownership extract + HI Campaign Spending Commission &middot; questions, not accusations &middot; govOS</footer>
</div></body></html>"""
    os.makedirs(MAUIOS, exist_ok=True)
    with open(OUT_F, "w", encoding="utf-8") as f:
        f.write(html)
    print("testimony_effect_map: %d/%d entities, %d parcels plotted -> %s" % (
        matched_entities, len(entities), matched_parcels, OUT_F))
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
