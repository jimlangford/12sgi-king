# GIS Snapshots — Hawaiian-held & trust lands

Downloaded copies of public GIS layers from the Hawaiʻi Statewide GIS Program
(`geodata.hawaii.gov`), served from our own infrastructure so maps work
without depending on live ArcGIS availability.

## Files

| File | Layer | Description |
|------|-------|-------------|
| `hawaii_dhhl.geojson` | 8 — ParcelsZoning/MapServer | Hawaiian Home Lands (DHHL Official trust designations) |
| `hawaii_govlands.geojson` | 23 — ParcelsZoning/MapServer | Government Lands / Public Land Trust (ceded former crown/government lands) |

## Source

Free, keyless public data — Hawaiʻi Statewide GIS Program:
`https://geodata.hawaii.gov/arcgis/rest/services/ParcelsZoning/MapServer`

Formal land-status public records only. Does NOT indicate private owner
ethnicity — that is private and not knowable from public data.

## Refreshing

Run the download script from the repo root:

```
python watchers/gis_snapshot.py
```

Then commit the updated `.geojson` files. The maps (`govos_signup.html`,
`maui_parcel_map.html`) load these files first and fall back to the live
ArcGIS service if they are absent.
