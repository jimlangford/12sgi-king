#!/usr/bin/env python3
# gis_snapshot.py — download and cache Hawaii GIS layers we depend on.
#
# Downloads the Hawaiian-held & trust lands layers from the free, keyless
# Hawaiʻi Statewide GIS Program (geodata.hawaii.gov) and saves them as
# static GeoJSON files served from our own infrastructure (GitHub Pages /
# king-local), so maps work reliably without depending on live ArcGIS
# availability.
#
# Layers downloaded from ParcelsZoning/MapServer:
#   8  — Hawaiian Home Lands (DHHL Official trust designations)
#  23  — Government Lands (Public Land Trust — ceded former crown/gov lands)
#
# These are the same layers used by maui_parcel_map.html and govos_signup.html
# for the Hawaiian-held & trust lands overlay.
#
# Output paths:
#   king_public_src/gis/hawaii_dhhl.geojson         (DHHL layer 8)
#   king_public_src/gis/hawaii_govlands.geojson     (Government Lands layer 23)
#   Documents/Claude/.../reports/mauios/gis/ (local backup mirror)
#
# Stdio only — no subprocess, no external packages (stdlib only).
# Politely paginated: 1000 features/page, 0.5s pause between pages.
#
# Run:  python watchers/gis_snapshot.py
# Re-run any time to refresh; new features replace old ones atomically.
import json, os, ssl, sys, time, urllib.parse, urllib.request
from datetime import datetime, timezone, timedelta

# ── paths ────────────────────────────────────────────────────────────────────
HERE     = os.path.dirname(os.path.abspath(__file__))
REPO     = os.path.dirname(HERE)
GIS_DIR  = os.path.join(REPO, "king_public_src", "gis")          # committed / served
HOME     = os.path.expanduser("~")
PROJECT  = os.path.join(HOME, "Documents", "Claude", "Projects", "Video System elementLOTUS")
LOCAL    = os.path.join(PROJECT, "reports", "mauios", "gis")      # local backup
DISPATCH = os.path.join(PROJECT, ".dispatch_log.jsonl")
HST      = timezone(timedelta(hours=-10))

# ── GIS service ──────────────────────────────────────────────────────────────
SVC      = "https://geodata.hawaii.gov/arcgis/rest/services/ParcelsZoning/MapServer"
LAYERS   = [
    (8,  "hawaii_dhhl.geojson",
         "DHHL Hawaiian Home Lands — layer 8, ParcelsZoning/MapServer",
         "DHHL Official trust designations (Hawaiian Home Lands Act 1920)"),
    (23, "hawaii_govlands.geojson",
         "Government Lands / Public Land Trust — layer 23, ParcelsZoning/MapServer",
         "Ceded former crown and government lands (Public Land Trust)"),
]
PAGE_SZ  = 1000
PAUSE    = 0.5   # seconds between pages — polite pacing


def now_hst():
    return datetime.now(HST)


def dispatch(tag, msg):
    line = {"ts": int(time.time()), "iso": now_hst().strftime("%Y-%m-%d %H:%M:%S"),
            "source": "gis-snapshot", "event": f"{tag}: {msg}"}
    try:
        os.makedirs(os.path.dirname(DISPATCH), exist_ok=True)
        with open(DISPATCH, "a", encoding="utf-8") as f:
            f.write(json.dumps(line, ensure_ascii=False) + "\n")
    except Exception:
        pass


def http_get(url):
    ctx = ssl.create_default_context()
    req = urllib.request.Request(url, headers={
        "User-Agent": "12sgi-kilo-aupuni-gis-snapshot/1.0 (civic transparency; owner copy)"
    })
    with urllib.request.urlopen(req, timeout=90, context=ctx) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def download_layer(layer_id, label):
    """Download all features for a single MapServer layer, paginating until done.
    Returns a list of GeoJSON feature dicts (geometry in WGS84 / EPSG:4326)."""
    features = []
    offset   = 0
    page     = 1
    print(f"  layer {layer_id} ({label})")
    while True:
        params = urllib.parse.urlencode({
            "where":             "1=1",
            "outFields":         "*",
            "returnGeometry":    "true",
            "geometryPrecision": "5",          # ~1m precision — keeps file size sane
            "inSR":              "4326",
            "outSR":             "4326",        # WGS84 so Leaflet can use it directly
            "resultOffset":      str(offset),
            "resultRecordCount": str(PAGE_SZ),
            "f":                 "geojson",
        })
        url = f"{SVC}/{layer_id}/query?{params}"
        try:
            data = http_get(url)
        except Exception as e:
            print(f"    page {page} fetch failed: {e}")
            if features:
                print(f"    stopping early — returning {len(features)} features already collected")
            break

        batch = data.get("features") or []
        if not batch:
            break
        features.extend(batch)
        exceeded = data.get("exceededTransferLimit", False)
        print(f"    page {page}: +{len(batch)} features (total so far: {len(features)})"
              + (" [more]" if exceeded else " [done]"))
        if not exceeded:
            break
        offset += PAGE_SZ
        page   += 1
        time.sleep(PAUSE)

    return features


def write_geojson(path, features, description, generated):
    """Write a merged FeatureCollection to disk atomically (write-then-rename)."""
    fc = {
        "type":     "FeatureCollection",
        "_source":  "geodata.hawaii.gov — Hawaiʻi Statewide GIS Program (keyless public)",
        "_description": description,
        "_generated":   generated,
        "_note":    ("Formal land-status public records. Does NOT indicate private owner ethnicity "
                     "— that is private and not knowable from public data."),
        "features": features,
    }
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(fc, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, path)   # atomic on POSIX and Windows


def main():
    os.makedirs(GIS_DIR, exist_ok=True)
    os.makedirs(LOCAL,   exist_ok=True)

    generated  = now_hst().strftime("%Y-%m-%d %H:%M HST")
    any_err    = False

    for layer_id, filename, label, description in LAYERS:
        print(f"\nDownloading: {label}")
        try:
            features = download_layer(layer_id, label)
        except Exception as e:
            print(f"  ERROR: {e}")
            dispatch("ERROR", f"gis-snapshot layer {layer_id} failed: {e}")
            any_err = True
            continue

        if not features:
            print(f"  WARNING: no features returned for layer {layer_id} — skipping write")
            any_err = True
            continue

        # write to repo (committed, served via GitHub Pages / king-local)
        repo_path  = os.path.join(GIS_DIR, filename)
        write_geojson(repo_path, features, description, generated)
        kb = os.path.getsize(repo_path) // 1024
        print(f"  wrote {len(features)} features → {repo_path} ({kb} KB)")

        # mirror to local Documents path (private backup)
        local_path = os.path.join(LOCAL, filename)
        write_geojson(local_path, features, description, generated)
        print(f"  mirrored → {local_path}")

        dispatch("SHIPPED", f"gis-snapshot layer {layer_id}: {len(features)} features, {kb}KB → {filename}")

    print()
    if any_err:
        print("Completed with errors — check output above.")
        return 1
    print("Done. Commit king_public_src/gis/*.geojson to publish the snapshot.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
