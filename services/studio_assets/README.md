# studio_assets — govOS v2 Studio-Asset Service (:8108)

Read-only manager / serving layer over the elementLOTUS studio vault. Runs as its **own** compose
project so it never disturbs the running govOS-v2 stack or a live GPU render.

- **Port:** `127.0.0.1:8108` only (loopback + Tailscale trust boundary). Never 8107 (reserved for the
  not-running gpu-router), never a busy port, never public.
- **IO-only:** no GPU reservation — cannot contend for the 8 GB co-tenant card.
- **Never prunes:** every asset tree is a `read_only: true` bind mount (kernel-enforced) and the app
  fail-closed write-probes each mount at boot (refuses to start if any is writable). GET-only API.
- **Extends, doesn't duplicate:** ingests the asset-quad-os lane's existing catalog
  (`reports/_status/asset_index.json` + `thumbnails/`) and supplements it with a **stat-only** scan
  of the finalized vaults it misses (e.g. the flat `mp4/` clip vault). Never re-crawls the live
  `ComfyUI/output` render dir, never re-thumbnails, never re-tiers.

## Run

```
cd 12sgi-king/deploy/studio-assets
docker compose -p studio-assets -f docker-compose.studio-assets.yml up -d --no-recreate --build
docker compose -p studio-assets -f docker-compose.studio-assets.yml logs -f
docker compose -p studio-assets -f docker-compose.studio-assets.yml down
```

## API (all GET unless noted)

| Route | Purpose |
|---|---|
| `/api/v2/live` · `/api/v2/ready` · `/api/v2/health` | health probes (health carries `asset_count`) |
| `/api/v2/stats` | counts + bytes by label and extension |
| `/api/v2/assets?q=&label=&ext=&limit=&offset=` | list / filter |
| `/api/v2/assets/search?q=` | "where is X" search over name + path |
| `/api/v2/assets/{key}` | one asset's metadata |
| `/api/v2/assets/{key}/thumb` | serve the cached thumbnail (jpeg) |
| `/api/v2/assets/{key}/file` | stream the asset bytes (read-only; 503 if a render holds it) |
| `POST /api/v2/reindex` | re-ingest the catalog + re-stat finalized vaults (writes only to own DB) |

Reports to the board like a lane via `services.v2_workboard.emit_workboard_job`
(`source="govos-v2-studio-assets"`, `lane="engineering"`).

Coordinate catalog/crawl changes with the **asset-quad-os** lane (`tools/assets/asset_tier.py`) —
this service reads what that lane produces; it does not own the crawl/thumbnail/tier pipeline.
