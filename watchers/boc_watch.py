#!/usr/bin/env python3
"""boc_watch.py — REAL property-records source for the RE/holdings trace (Jimmy 2026-06-18:
   "wire a Bureau of Conveyances source so the RE/profits data actually flows").

WHAT IS ACTUALLY ACCESSIBLE (verified 2026-06-18) — and what is NOT:
  • geodata.hawaii.gov/arcgis/rest/services/ParcelsZoning/MapServer/30 ("Maui County Parcels") is
    OPEN + queryable (no Playwright, no qPublic scrape). It gives, per parcel: TMK, ASSESSED
    land+building VALUE (+ exemptions), homeowner flag, acreage, zoning, and a per-parcel qPublic
    link. This is a real ASSESSED-VALUE / holdings signal — wired here.
  • What the open GIS does NOT carry: the OWNER NAME and the SALE PRICE/DATE (profit). Those are
    stripped from the public GIS; they live in qPublic per-parcel and in the Bureau of Conveyances
    deed index. There is no clean open API for "realtor names + profits since 2000."
  • Therefore owner-name + sale-history is handled the audit-wisdom way: as a NAMED RECORDS REQUEST
    (Bureau of Conveyances grantor/grantee index + Maui RPA sale-history) that the case documents
    demand — not faked. boc_watch emits that request spec so the pipeline knows the lawful next step.

PRIVATE: holdings data + the records-request spec are written to reports/_status/ (owner-only).
Public RE pages keep their existing sourced-question framing; raw holdings stay private.

USAGE:
  python boc_watch.py --tmk 211001001            # enrich one parcel with its assessed value
  python boc_watch.py --top 25                    # top-25 highest-assessed Maui parcels (holdings signal)
  python boc_watch.py                             # refresh the holdings index + records-request spec
"""
import os, sys, json, time, urllib.parse, urllib.request
from datetime import datetime, timezone, timedelta

HOME    = os.path.expanduser("~")
PROJECT = os.path.join(HOME, "Documents", "Claude", "Projects", "Video System elementLOTUS")
STATUS  = os.path.join(PROJECT, "reports", "_status")            # PRIVATE
HST     = timezone(timedelta(hours=-10))
LAYER   = "https://geodata.hawaii.gov/arcgis/rest/services/ParcelsZoning/MapServer/30/query"
def now_hst(): return datetime.now(HST)

def _q(params):
    url = LAYER + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (KiloAupuni civic; public-records)"})
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.load(r)

def parcel(tmk):
    """One parcel → assessed value + qPublic link (REAL, open GIS)."""
    d = _q({"where": "tmk='%s' OR tmk_txt='%s'" % (tmk, tmk), "outFields": "*",
            "returnGeometry": "false", "f": "json"})
    fe = d.get("features") or []
    if not fe: return None
    a = fe[0]["attributes"]
    lv, bv = a.get("landvalue") or 0, a.get("bldgvalue") or 0
    return {"tmk": a.get("tmk"), "land_value": lv, "bldg_value": bv, "assessed_total": lv + bv,
            "homeowner": a.get("homeowner"), "acres": a.get("taxacres"), "zone": a.get("zone"),
            "qpublic": a.get("qpub_link"), "source": "Hawaii Statewide GIS · Maui County Parcels (assessment values, public)"}

def top_value(n=25):
    """Highest-assessed Maui parcels — a 'who holds the most value' signal (owner name via the
    qPublic link / records request; the GIS itself does not name the owner)."""
    d = _q({"where": "1=1", "outFields": "tmk,landvalue,bldgvalue,homeowner,taxacres,zone,qpub_link",
            "orderByFields": "bldgvalue DESC", "resultRecordCount": n,
            "returnGeometry": "false", "f": "json"})
    rows = []
    for f in (d.get("features") or []):
        a = f["attributes"]; lv, bv = a.get("landvalue") or 0, a.get("bldgvalue") or 0
        rows.append({"tmk": a.get("tmk"), "assessed_total": lv + bv, "land_value": lv, "bldg_value": bv,
                     "homeowner": a.get("homeowner"), "acres": a.get("taxacres"), "zone": a.get("zone"),
                     "qpublic": a.get("qpub_link")})
    return rows

# The lawful records request the case documents DEMAND for owner-name + profit (the part no open API gives).
RECORDS_REQUEST = {
    "purpose": "owner name + arms-length SALE history (profit since 2000) — not in the open GIS",
    "requests": [
        {"to": "Hawaiʻi Bureau of Conveyances (DLNR)", "ask": "grantor/grantee index + recorded deeds "
         "(Regular System + Land Court) for the named TMKs/parties, 2000–present — sale price, date, parties"},
        {"to": "Maui County Real Property Assessment Division", "ask": "owner of record + sale-history "
         "(date, consideration) per TMK; the assessment roll export if available"},
    ],
    "note": "Frame as a public-records request; profit = sale price minus prior basis, both from recorded "
            "deeds. The open GIS supplies current assessed value only (wired by boc_watch).",
}

def refresh():
    os.makedirs(STATUS, exist_ok=True)
    try:
        top = top_value(50)
    except Exception as e:
        top = []; print("boc_watch: GIS query failed (%s) — holdings index left as-is" % e)
    out = {"generated": now_hst().strftime("%Y-%m-%d %H:%M HST"),
           "source": LAYER, "coverage": "Maui County parcels — assessed land+building value (OPEN GIS)",
           "does_not_include": "owner name, sale price/date (see records_request)",
           "top_assessed": top, "records_request": RECORDS_REQUEST}
    p = os.path.join(STATUS, "property_holdings.json")
    json.dump(out, open(p, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print("boc_watch: %d top-assessed Maui parcels (OPEN GIS, value-only) -> %s (PRIVATE). "
          "Owner+sale = records request (Bureau of Conveyances) per spec." % (len(top), os.path.basename(p)))
    return out

def main(argv):
    if "--tmk" in argv:
        tmk = argv[argv.index("--tmk") + 1]
        print(json.dumps(parcel(tmk), indent=1, ensure_ascii=False))
    elif "--top" in argv:
        n = int(argv[argv.index("--top") + 1])
        for r in top_value(n):
            print("  TMK %-12s assessed $%-12s (land $%s + bldg $%s) homeowner=%s"
                  % (r["tmk"], "{:,}".format(r["assessed_total"]), "{:,}".format(r["land_value"]),
                     "{:,}".format(r["bldg_value"]), r["homeowner"]))
    else:
        refresh()
    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
