#!/usr/bin/env python3
# great_mahele_overlay.py - Kilo Aupuni: the 1848 Great Mahele land divisions, overlaid on the modern
# ahupuaʻa map, alongside real Land Commission Award (LCA) entries transcribed directly from the
# 1929 territorial government index (public domain, no copyright).
#
# WHAT THIS IS: an honest, sourced overlay of two REAL free public records:
#   1. "Indices of Awards Made by the Board of Commissioners to Quiet Land Titles in the Hawaiian
#      Islands" (Territory of Hawaii, 1929) -- https://ags.hawaii.gov/wp-content/uploads/2023/09/1929_index_of_lca.pdf
#      A scanned-image-only PDF (no OCR text layer, verified). The entries below for four Maui
#      districts -- Honuaʻula, Kula, Lāhainā, and the Wailuku ahupuaʻa -- were transcribed by direct
#      visual reading of the actual page images (pages 581/tbl "148", 611/tbl "178", 641/tbl "208",
#      671/tbl "238" of the PDF, "Alphabetical Index of Awards by Land" section). This is a REAL,
#      BOUNDED sample -- four of many Maui districts in the book -- not a claim of full coverage.
#   2. The free, keyless Hawaii statewide GIS Ahupuaʻa polygon layer --
#      geodata.hawaii.gov/arcgis/rest/services/HistoricCultural/MapServer/1 -- for real geographic
#      boundaries of the traditional land divisions the 1929 Index organizes its awards by.
#
# PRECISION, STATED HONESTLY: this is an AHUPUAʻA-LEVEL overlay (which traditional land division held
# which LCA claims), not a parcel-level reconstruction of each individual claim's exact metes-and-bounds
# boundary -- no free source for that precision was found (see the same evening's research). A claimant
# in "Kalialinui" (within the Kula district) is shown against the Kalialinui/Kula ahupuaʻa shape, not a
# geometrically reconstructed individual-claim polygon.
#
# INTEGRITY (non-negotiable, same rule as every page on this site): this is historical record placed
# alongside modern geography -- never a claim about any living person's modern title, never a legal
# assertion. It restores visibility of who held land in 1848-1855 within each traditional division.
# Stdlib only + one keyless HTTPS call to a public government GIS server.
import json, os, urllib.request, urllib.parse
from datetime import datetime, timezone, timedelta

HOME = os.path.expanduser("~")
PROJECT = os.path.join(HOME, "Documents", "Claude", "Projects", "Video System elementLOTUS")
MAUIOS = os.path.join(PROJECT, "reports", "mauios")
OUT_F = os.path.join(MAUIOS, "great_mahele_overlay.html")
GIS = "https://geodata.hawaii.gov/arcgis/rest/services/HistoricCultural/MapServer/1/query"
HST = timezone(timedelta(hours=-10))

SOURCE_PDF = "https://ags.hawaii.gov/wp-content/uploads/2023/09/1929_index_of_lca.pdf"
SOURCE_CITE = ("Indices of Awards Made by the Board of Commissioners to Quiet Land Titles in the "
               "Hawaiian Islands (Territory of Hawaii, 1929), \"Alphabetical Index of Awards by Land\" "
               "section, public domain, Hawaii State Archives (ags.hawaii.gov)")

# Transcribed DIRECTLY from the scanned page images (real entries, real page numbers cited per group).
# Columns per the original: Location(ahupuaʻa/place) | Awardee | LCA no. | Area
MAHELE_ENTRIES = {
    "Honuaʻula": {
        "pdf_page": 581, "book_page_label": "148",
        "entries": [
            ("Kaeo", "Kahaleokaia", "4157", "0.50 Ac"),
            ("Kaeo", "Kaihe", "2395", "0.20 Ac"),
            ("Kaeo", "Kaili", "2395-B", "0.25 Ac"),
            ("Kaeo", "Kalili", "2399", "0.21 Ac"),
            ("Kaeo, Mohopilo", "Hiapo", "8071 / 2579", "9.76 Acs"),
            ("Kaeo, Ulupalakua", "Kalama", "4292-B", "7.70 Acs"),
            ("Kalihi", "Mahoe", "2525", "0.08 Ac"),
            ("Kanahena", "Luaha", "5472, 9942", "2.86 Acs"),
            ("Kanahena", "Keelikolani, R.", "7716", "Ap. 7"),
            ("Kanahena, Kaloa", "Hao", "5489", "4.69 Acs"),
        ],
    },
    "Kula": {
        "pdf_page": 611, "book_page_label": "178",
        "entries": [
            ("Aapueo", "Kaaipohuehue", "9026", "0.79 Ac"),
            ("Aapueo", "Keohokalole, A.", "8452", "Ahupuaʻa award"),
            ("Aapueo, Apopo", "Kama", "9025", "11.25 Acs"),
            ("Alae", "Kauaua", "5267-B", "2.18 Acs"),
            ("Kalialinui", "Kamaikaaloa", "7124", "19.838 Acs"),
            ("Kamaole", "Ahulau", "8038", "6.50 Acs"),
            ("Kamaole", "Holani", "10891", "16.00 Acs"),
            ("Kamaole", "Ili", "7971-D", "49.87 Acs"),
            ("Kamaole", "Kaili", "6471 / 3107", "1.75 Acs"),
            ("Kamaole", "Kalauao", "8881", "47.50 Acs"),
        ],
    },
    "Lāhainā": {
        "pdf_page": 641, "book_page_label": "208",
        "entries": [
            ("Waianae, Luaehu", "Pikanele", "310 / 10667", "1.087 Acs"),
            ("Wainee", "Alu", "3425-B", "1 Ac 1 rood 32 rods"),
            ("Wainee", "Birch, Alex. M.", "782", "0.35 Ac"),
            ("Wainee", "Burrows, Sol. D.", "241", "0.81 Ac"),
            ("Wainee, Waiokama", "Kuakini, J. A.", "302", "1 rood"),
            ("Waineenui", "Hanaumua", "6787", "1.75 Acs"),
            ("Waineenui", "Kaluahinenui", "6785", "2 Acs 12 rods"),
            ("Waiokama", "Kaihupaa", "7598", "6 rods"),
            ("Waiokama", "Kalanimoku", "526", "33 rods"),
        ],
    },
    "Wailuku": {
        "pdf_page": 671, "book_page_label": "238",
        "entries": [
            ("Papohaku", "Kawahie", "3495", "3.41 Acs"),
            ("Papohaku", "Kuaele", "8459", "0.41 Ac"),
            ("Papohaku", "Moo", "3289", "1.46 Ac"),
            ("Papohaku", "Pepee", "515 / 2627", "0.48 Ac"),
            ("Pauku", "Kaianui", "3234-C", "3.50 Ac"),
            ("Paukukalo", "Hiona", "3253", "0.97 Ac"),
            ("Paukukalo", "Kahale", "435 / 7742", "1.60 Acs"),
            ("Pauniu", "Kaolulo", "2409", "4.73 Acs"),
            ("Peepee", "Lunalilo, Wm. C.", "8559-B", "255.70 Acs"),
            ("Pilipili", "Kaelepulu", "2451", "3.13 Acs"),
        ],
    },
}

# ahupuaa-layer name for each district header above (moku name, except Wailuku which is an ahupuaʻa
# within the Pūʻali Komohana moku) -- confirmed by direct query against the live GIS layer.
DISTRICT_TO_MOKU = {"Honuaʻula": "moku", "Kula": "moku", "Lāhainā": "moku"}  # matched by moku field
WAILUKU_AHUPUAA = "Wailuku"  # matched by ahupuaa field (single ahupuaʻa, not a whole moku)


def now_hst():
    return datetime.now(HST)


def esc(s):
    return str(s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def fetch_maui_ahupuaa():
    """Fetch every Maui ahupuaʻa polygon (all ~141) from the free, keyless statewide GIS layer --
    used as the base map so the four highlighted districts sit in real geographic context."""
    params = {"where": "mokupuni='Maui'", "outFields": "ahupuaa,moku,mokupuni",
              "returnGeometry": "true", "geometryPrecision": "4", "f": "json",
              "resultRecordCount": "2000"}
    url = GIS + "?" + urllib.parse.urlencode(params)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "12sgi-kilo-aupuni/1.0 (civic transparency)"})
        with urllib.request.urlopen(req, timeout=60) as r:
            data = json.loads(r.read().decode("utf-8", "replace"))
        return data.get("features", [])
    except Exception:
        return []


def svg_overlay(features, width=820, height=620, pad=30):
    """Base map = every Maui ahupuaʻa in a faint neutral fill; the four districts with real 1929-index
    entries get a warm highlight fill. True projected coordinates (Hawaii State Plane) -- a genuine
    relative map, not a schematic."""
    if not features:
        return ""
    all_pts = []
    for f in features:
        for ring in (f.get("geometry") or {}).get("rings", []):
            all_pts.extend(ring)
    if not all_pts:
        return ""
    xs = [p[0] for p in all_pts]
    ys = [p[1] for p in all_pts]
    minx, maxx = min(xs), max(xs)
    miny, maxy = min(ys), max(ys)
    spanx = (maxx - minx) or 1
    spany = (maxy - miny) or 1
    scale = min((width - 2 * pad) / spanx, (height - 2 * pad) / spany)

    def proj(x, y):
        return pad + (x - minx) * scale, height - pad - (y - miny) * scale

    highlighted_moku = set(DISTRICT_TO_MOKU.keys())
    parts = []
    for f in features:
        attrs = f.get("attributes", {})
        moku = attrs.get("moku") or ""
        ahupuaa = attrs.get("ahupuaa") or ""
        is_hl = moku in highlighted_moku or ahupuaa == WAILUKU_AHUPUAA
        fill = "#c8a060" if is_hl else "#2a3428"
        stroke = "#e8dcc8" if is_hl else "#3a4438"
        opacity = "0.75" if is_hl else "0.35"
        for ring in (f.get("geometry") or {}).get("rings", []):
            pts = " ".join(f"{proj(x,y)[0]:.1f},{proj(x,y)[1]:.1f}" for x, y in ring)
            title = esc(f"{ahupuaa} ({moku})")
            parts.append(f'<polygon points="{pts}" fill="{fill}" stroke="{stroke}" stroke-width="0.6" opacity="{opacity}"><title>{title}</title></polygon>')
    return (f'<svg viewBox="0 0 {width} {height}" width="100%" height="{height}" '
            f'style="background:#0f1712;border-radius:8px" role="img" '
            f'aria-label="Maui ahupuaa map with four Great Mahele districts highlighted">{"".join(parts)}</svg>')


def main():
    features = fetch_maui_ahupuaa()
    svg = svg_overlay(features)

    sections = []
    for district, d in MAHELE_ENTRIES.items():
        rows = "".join(
            f'<div class="m"><span class="loc">{esc(loc)}</span><span class="claim">{esc(claimant)}</span>'
            f'<span class="lca">LCA {esc(lca)}</span><span class="area">{esc(area)}</span></div>'
            for loc, claimant, lca, area in d["entries"]
        )
        sections.append(
            f'<div class="district"><h2>{esc(district)}, Maui</h2>'
            f'<div class="cite">Source: 1929 Index, page {d["pdf_page"]} (book page "{d["book_page_label"]}")</div>'
            f'<div class="hd"><span>Location</span><span>Awardee</span><span>LCA No.</span><span>Area</span></div>'
            f'{rows}</div>'
        )

    g = now_hst().strftime("%Y-%m-%d %H:%M HST")
    html = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>The Great Mahele on the Modern Map - Maui - 12 Stones</title>
<style>
 body{{margin:0;background:#0c100e;color:#e8e4d8;font-family:Georgia,serif;line-height:1.5}}
 .wrap{{max-width:900px;margin:0 auto;padding:32px 22px 60px}}
 .eyebrow{{font-family:Consolas,monospace;font-size:11px;letter-spacing:1.2px;color:#d9b24c;text-transform:uppercase}}
 h1{{font-size:25px;margin:8px 0 2px}}
 h2{{font-size:17px;margin:0 0 4px;color:#c8a060}}
 .disc{{font-size:12px;color:#9a957f;font-style:italic;border-left:2px solid rgba(224,106,74,.5);padding:7px 12px;margin:12px 0;background:rgba(224,106,74,.05)}}
 .legend{{font-size:11px;color:#9a957f;margin:10px 0;font-family:Consolas,monospace}}
 .legend span{{display:inline-block;width:11px;height:11px;border-radius:2px;margin-right:5px;vertical-align:middle}}
 .district{{margin-top:26px;border-top:1px solid rgba(255,255,255,.08);padding-top:14px}}
 .cite{{font-size:11px;color:#9a957f;font-family:Consolas,monospace;margin-bottom:8px}}
 .hd{{display:grid;grid-template-columns:1.3fr 1.3fr 1fr 1fr;gap:10px;font-family:Consolas,monospace;font-size:10.5px;color:#9a957f;text-transform:uppercase;border-bottom:1px solid rgba(217,178,76,.25);padding-bottom:5px}}
 .m{{display:grid;grid-template-columns:1.3fr 1.3fr 1fr 1fr;gap:10px;align-items:baseline;border-bottom:1px solid rgba(255,255,255,.06);padding:5px 0;font-size:13px}}
 .m .loc{{color:#e8e4d8}} .m .claim{{color:#bdb8a4}} .m .lca{{color:#d9b24c;font-family:Consolas,monospace;font-size:11.5px}} .m .area{{color:#9a957f;font-family:Consolas,monospace;font-size:11.5px}}
 footer{{margin-top:36px;border-top:1px solid rgba(255,255,255,.1);padding-top:12px;font-family:Consolas,monospace;font-size:10.5px;color:#9a957f}}
</style></head><body><div class="wrap">
<div class="eyebrow">12 Stones Global &middot; Kilo Aupuni &middot; the Great Mahele on the modern map</div>
<h1>Where the Land Was Divided</h1>
<div class="disc">In 1848 the Great Mahele divided Hawaiian land among the Crown, the government, the aliʻi,
and (via the 1850 Kuleana Act) the makaʻāinana. This page overlays four real Maui districts from the
1929 territorial government's official index of those awards onto the modern ahupuaʻa map -- a
traditional land division, not a legal claim about any current owner. This is an <b>ahupuaʻa-level</b>
overlay (which district held which claims), not a reconstruction of each individual claim's exact
historical boundary -- no free source for that finer precision exists yet (checked: Ulukau's free
database covers only Kauaʻi/Niʻihau; a true parcel-level GIS join would require confirming export terms
with OHA's Kipuka database). Four of many Maui districts are shown here -- a real, bounded sample, not
full coverage of the 1929 Index's ~1,700 pages.</div>
<div class="legend"><span style="background:#c8a060;opacity:.75"></span>the four districts shown below &nbsp; <span style="background:#2a3428;opacity:.6"></span>other Maui ahupuaʻa (context)</div>
{svg or '<div style="color:#9a957f;font-size:13px">No ahupuaʻa geometry resolved this run -- GIS server may be unavailable.</div>'}
{''.join(sections)}
<footer>generated {g} &middot; sources: {esc(SOURCE_CITE)} ({esc(SOURCE_PDF)}) + Hawaiʻi statewide Ahupuaʻa GIS layer (geodata.hawaii.gov, keyless public) &middot; questions and restoration, never a title claim &middot; govOS</footer>
</div></body></html>"""
    os.makedirs(MAUIOS, exist_ok=True)
    tmp = OUT_F + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(html)
    os.replace(tmp, OUT_F)
    print("great_mahele_overlay: %d Maui ahupuaʻa polygons, %d districts with real 1929-index entries -> %s" % (
        len(features), len(MAHELE_ENTRIES), OUT_F))
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
