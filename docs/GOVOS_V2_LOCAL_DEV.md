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

`services/v2_workboard.py` is lane-aware (`engineering` self-heals automatically;
`creative`/`output` require human `approve_workboard_job()` /
`reject_workboard_job()`). It now also has `archive_workboard_job()`, the v2
counterpart of the legacy board consumer's job-management actions
(archive/restore/retry/reschedule): no job is ever hard-deleted on either
side — archiving appends an `archived` tombstone to the shared append-only
dispatch log, preserving the original entry, same as the legacy consumer's
soft-delete-as-archive + audit-trail pattern (e.g. clearing stale
engineering-lane jobs once a newer backend supersedes them). Use
`python -m services.v2_workboard --archive JOB_ID [--archiver who] [--note "..."]`
from the CLI, or call `archive_workboard_job()` directly.

Optional graph-layer wiring (defaults now match the Dockerized Neo4j v5 stack):

```bash
export NEO4J_HTTP="http://127.0.0.1:7474/db/neo4j/tx/commit"
export GRAPH_REFRESH_STATE_PATH="/tmp/govos_v2_graph_refresh_state.json"
export GRAPH_STACK_VERSION="5.2"
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

1. Create auth session (`POST /api/v2/auth/session`) with explicit claims (`sub`, `tenant_id`, `role`, `scopes`, `exp`, `iss`, `aud`) and keep the returned access token.
2. Create tenant case with an `Authorization` header that uses the access token; request tenant must match token tenant unless role is `Owner`.
3. Generate document for the case with the same `Authorization` header (cross-tenant case access is denied).
4. Create/list storage objects with the same `Authorization` header (tenant scope is claim-derived).
5. Ask AI guidance for the same case with the same `Authorization` header (tenant scope is claim-derived).
6. Check `/api/v1/ready` and `/api/v1/health` from health service and verify all v2 services are reachable.

## 6) Run integration tests

```bash
python -m unittest tests.v2.test_v2_integration_stack
```

## 7) V2 four-lane approval workflow

V2 uses three workboard lanes to control what flows from private to public:

| Lane | Who resolves | Rule |
|---|---|---|
| `engineering` | Self-heals automatically | Internal plumbing — auth events, storage uploads, AI analysis. Never blocks the system. |
| `creative` | Human review required | Generated documents, images, reports in draft state. V1 is the review surface. |
| `output` | Owner approval required | Staged content ready to publish to 12sgi.com or govOS. Always needs explicit sign-off. |

**Core rule:** V2 does not think in public. It processes privately, then only clean approved outputs leave.

### Check pending approvals (CLI)

```bash
python -m services.v2_workboard --pending
```

### Self-heal stalled engineering jobs (CLI)

```bash
python -m services.v2_workboard --outcome self-healed
```

Engineering jobs (case creation, storage, AI analysis) are approved to fix themselves forward.  
This command is always safe — it never touches creative or output jobs.

### Owner node approval API (local Tailscale only — port 8088)

```bash
# List items needing review
GET http://127.0.0.1:8088/approvals/pending

# Approve a creative/output job
POST http://127.0.0.1:8088/approvals/{job_id}/approve
{"approver": "owner", "note": "Approved for publish"}

# Reject a creative/output job
POST http://127.0.0.1:8088/approvals/{job_id}/reject
{"reason": "Wrong template", "rejector": "owner"}

# Trigger engineering self-heal manually
POST http://127.0.0.1:8088/selfheal

# Inspect graph freshness / stack status
GET http://127.0.0.1:8088/graph/status

# Refresh all graph layers or a targeted subset
POST http://127.0.0.1:8088/graph/refresh
{"mode": "incremental", "reason": "owner-manual", "targets": ["private_spine", "pulse_geometry"]}
```

### Inspect the pulse geometry lattice

```bash
GET http://127.0.0.1:8088/pulse/geometry
POST http://127.0.0.1:8088/pulse/geometry/refresh
```

The pulse geometry is a dedicated PRIVATE Neo4j-backed lane×skill lattice. It now uses the full 28–30 day Hina moon cycle, adds Maui / `Pacific/Honolulu` human-residence frequency tuning for the geometry layer, carries a deterministic six-step human/chakra alignment keyed to organic carbon weight `6`, and projects a Sage element view into Neo4j from the existing `akua` / skill geometry, all as an audited, deterministic, non-experimental human-serving surface without changing the existing workboard lanes.

The graph ratchet now persists PRIVATE freshness/status metadata for the owner node and supports targeted `incremental` refreshes for `graph`, `vectors`, `private_spine`, and `pulse_geometry`. Full refreshes remain available for bootstrap or repair.

### Lane assignment by service action

| Action | Lane | Reason |
|---|---|---|
| `case.created` | engineering | Internal case plumbing |
| `document.generated` | creative | Human should review before output |
| `storage.object.created` | engineering | File upload plumbing |
| `ai.assist.completed` | engineering | Private AI analysis |
| `publish.staged` (future v2-publish) | output | Owner must approve before 12sgi.com publish |


---

## GPU layer smoke tests

All gpu-router endpoints require a valid owner bearer token.  
Obtain one by signing in via the Naga console and copying `king.ownerToken` from localStorage,  
or use the dev signing secret to mint a token directly from the auth service.

```bash
# Set token once for the session
TOKEN="<paste owner token here>"

# 1. Check Ollama is alive (no auth required — direct to gpu-runtime)
curl http://127.0.0.1:11434/api/tags

# 2. Check the router is ready (no auth required — health surface)
curl http://127.0.0.1:8107/api/v2/ready

# 3. Inspect the queue (auth required)
curl http://127.0.0.1:8107/api/v2/gpu/queue \
  -H "Authorization: ******"

# 4. Per-client usage stats (auth required)
curl http://127.0.0.1:8107/api/v2/gpu/usage \
  -H "Authorization: ******"

# 5. Test inference through the router — do NOT call Ollama directly
#    Field is client_id (not client); timeout is set server-side via GPU_INFER_TIMEOUT.
curl -X POST http://127.0.0.1:8107/api/v2/gpu/infer \
  -H "Content-Type: application/json" \
  -H "Authorization: ******" \
  -d '{
    "client_id": "govos-core",
    "model": "llama3",
    "prompt": "Confirm you are the shared govOS GPU runtime."
  }'

# 6. Test the AI service (uses gpu-router internally)
curl http://127.0.0.1:8105/api/v2/ready
```

### Pull models on first run

```bash
# Smoke test model
docker exec -it 12sgi-king-gpu-runtime-1 ollama pull llama3

# Reasoning model (after stack is stable on the 8 GB card)
docker exec -it 12sgi-king-gpu-runtime-1 ollama pull qwen3:8b
```

### Traffic must flow through gpu-router

```
govOS AI / Maui tenant / Studio / Civic / Workboard
        ↓
gpu-router  :8107
        ↓
gpu-runtime / Ollama  :11434
```

Clients must not call port 11434 directly.  One brain, one queue, no VRAM fighting.

## Service-token governance (local/dev)

- Do not commit tokens, service secrets, or long-lived credentials.
- Keep machine scopes explicit and narrow; avoid wildcard scopes.
- Use short-lived tokens only; rotate local secrets by replacing env values and restarting services.
- Treat `INTERNAL_SERVICE_TOKEN` as private service trust material and keep it out of examples/log dumps.
