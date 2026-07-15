# AI services

Purpose

Tenant assistant guidance API for govOS v2.

Owner

- AI engineering

API

- `/api/v2/live`
- `/api/v2/ready`
- `/api/v2/health`
- `/api/v2/ai/assist`
- `/api/v2/ai/render/dispatch`
- `/api/v2/ai/graph/string-edge`

Run locally

```bash
uvicorn app.main:app --app-dir services/ai --host 0.0.0.0 --port 8105
```

Notes

- Assist events are persisted in SQLite (`AI_DB_PATH`, default `/tmp/govos_v2_ai.db`).
- Render dispatch events are persisted in SQLite and emitted to workboard dispatch (`render.dispatch.queued`).
- String-edge graph events are persisted in SQLite and emitted to workboard dispatch (`graph.string_edge.upserted`).
- Business endpoints require bearer auth sessions validated by auth introspection.
- Case references are validated against the tenant service.
- Hybrid render routing is controlled by env:
  - `RENDER_ROUTING_MODE`: `hybrid` (default), `native_only`, or `queue_only`
  - `COMFYUI_NATIVE_URL` / `COMFYUI_NATIVE_READY_URL`
  - `COMFYUI_GPU_WORKER_QUEUE` / `GPU_WORKER_HEARTBEAT_URL`
- Neo4j graph writes for render dispatch are optional and controlled by env:
  - `NEO4J_ENABLED`, `NEO4J_URL`, `NEO4J_USERNAME`, `NEO4J_PASSWORD`, `NEO4J_DATABASE`
  - `NEO4J_REQUIRED_FOR_RENDER_DISPATCH` to make graph persistence hard-required
