# govOS v2 Local Integration

This guide wires backend services, health checks, auth trust, and frontend scaffolds for local v2 integration.

## 1) Shared environment

Set a shared internal trust token once for all services:

```bash
export INTERNAL_SERVICE_TOKEN="dev-internal-token"
```

Optional local DB paths (defaults use `/tmp/govos_v2_*.db`):

```bash
export AUTH_DB_PATH="/tmp/govos_v2_auth.db"
export TENANT_DB_PATH="/tmp/govos_v2_tenant.db"
export DOCUMENTS_DB_PATH="/tmp/govos_v2_documents.db"
export STORAGE_DB_PATH="/tmp/govos_v2_storage.db"
export AI_DB_PATH="/tmp/govos_v2_ai.db"
```

Optional unified workboard queue path (v2 + legacy share `workboard-quad-os`):

```bash
export WORKBOARD_DISPATCH_LOG="/tmp/govos_v2_dispatch.jsonl"
export WORKBOARD_TARGET_THREAD="workboard-quad-os"
```

Optional flip-ready render routing (hybrid ComfyUI/GPU-worker):

```bash
export RENDER_ROUTING_MODE="hybrid"                 # hybrid | native_only | queue_only
export COMFYUI_NATIVE_URL="http://127.0.0.1:8188"   # optional direct native route
export COMFYUI_NATIVE_READY_URL="http://127.0.0.1:8188/system_stats"
export COMFYUI_GPU_WORKER_QUEUE="comfyui-gpu-worker"   # queue lane name
export GPU_WORKER_HEARTBEAT_URL=""                     # optional queue worker heartbeat URL
```

Optional Neo4j graph persistence for render dispatch:

```bash
export NEO4J_ENABLED="true"
export NEO4J_URL="http://127.0.0.1:7474"
export NEO4J_USERNAME="neo4j"
export NEO4J_PASSWORD="change-me"
export NEO4J_DATABASE="neo4j"
export NEO4J_REQUIRED_FOR_RENDER_DISPATCH="false"
```

## 2) Start backend services

```bash
uvicorn app.main:app --app-dir services/auth --port 8101
uvicorn app.main:app --app-dir services/tenant --port 8102
uvicorn app.main:app --app-dir services/documents --port 8103
uvicorn app.main:app --app-dir services/storage --port 8104
uvicorn app.main:app --app-dir services/ai --port 8105
uvicorn app.main:app --app-dir services/health --port 8000
```

Service defaults expect:

- auth at `http://localhost:8101`
- tenant at `http://localhost:8102`
- documents at `http://localhost:8103`
- storage at `http://localhost:8104`
- ai at `http://localhost:8105`

Override with service envs if needed:

- `AUTH_INTROSPECTION_URL`
- `AUTH_READY_URL`
- `TENANT_SERVICE_URL`
- `TENANT_READY_URL`

## 3) Configure health aggregation

Set environment variables for health service:

```bash
export SURFACES_LIST="auth=localhost:8101,tenant=localhost:8102,documents=localhost:8103,storage=localhost:8104,ai=localhost:8105"
export SURFACES_HEALTH_PATH="/api/v2/ready"
```

## 4) Load frontend scaffolds

Serve each app folder statically (example):

```bash
python -m http.server 4173 --directory apps/govos/public
python -m http.server 4174 --directory apps/tenant/public
python -m http.server 4175 --directory apps/admin/public
python -m http.server 4176 --directory apps/civic-signal/public
```

Defaults point to localhost service ports above. You can override with globals:

- `AUTH_SERVICE_URL`
- `TENANT_SERVICE_URL`
- `DOCUMENTS_SERVICE_URL`
- `STORAGE_SERVICE_URL`
- `AI_SERVICE_URL`
- `HEALTH_SERVICE_URL`

## 5) End-to-end checks

1. Create auth session (`POST /api/v2/auth/session`) and keep the returned access token.
2. Create tenant case with an `Authorization` header that uses the access token.
3. Generate document for the case with the same `Authorization` header.
4. Create/list storage objects with the same `Authorization` header.
5. Ask AI guidance for the same case with the same `Authorization` header.
6. Queue render work via `POST /api/v2/ai/render/dispatch` and verify route/target + workboard dispatch entry.
7. Upsert a graph string-edge via `POST /api/v2/ai/graph/string-edge` and verify `graph.string_edge.upserted` in dispatch.
8. Check `/api/v1/ready` and `/api/v1/health` from health service and verify all v2 services are reachable.

## 6) Run integration tests

```bash
python -m unittest tests.v2.test_v2_integration_stack
```
