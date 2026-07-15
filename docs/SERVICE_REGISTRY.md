# Service Registry — govOS v2

**Last updated:** 2026-07-12  
**Version:** v2 (integrated v1↔v2 bridge in place)

This document lists all govOS v2 services with ownership, API endpoints, health checks, and dependencies. It is the authoritative reference for service topology and contact points.

---

## Service Topology

```
┌──────────────────────────────────────────┐
│           Auth Service (8101)            │
│    JWT signing, OAuth, token introspection
└──────────────────────────────────────────┘
           ↓ (required by all)
┌──────────────┬──────────────┬──────────────┐
│  Tenant      │  Documents   │  Storage     │
│  (8102)      │  (8103)      │  (8104)      │
│  Cases       │  Generate    │  Objects     │
└──────────────┴──────────────┴──────────────┘
       ↓ (optional inference)
┌──────────────────────────────────────────┐
│           AI Service (8105)              │
│    LLM assistance, GPU router integration
└──────────────────────────────────────────┘
           ↓ (forwards to)
┌──────────────────────────────────────────┐
│        GPU Router (8107)                 │
│    Ollama, voice, embedding queue        │
└──────────────────────────────────────────┘
           ↓ (GPU runtime)
┌──────────────────────────────────────────┐
│       Ollama / GPU Runtime               │
│    Local LLM inference                   │
└──────────────────────────────────────────┘

ALSO:
 • Health (8106) — aggregated dependency checks
 • King Bridge (8109) — v1 Ollama router + Neo4j writer
 • Studio Assets (8108) — read-only asset manager
 • Connector Runner — social channel sync (background)
 • GitHub Workflow Monitor (background) — CI repair
```

---

## Services

### 1. Auth Service

**Owner:** James Langford  
**Port:** 8101  
**Version:** 2.0.0  
**Database:** SQLite (`/data/db/govos_v2_auth.db`)

**Purpose:**  
Passwordless authentication, OAuth provider integration, JWT signing, token introspection, audit logging.

**API Endpoints:**

| Method | Path | Purpose | Auth Required |
|--------|------|---------|---|
| GET | `/api/v2/live` | Liveness probe | No |
| GET | `/api/v2/ready` | Readiness probe (DB check) | No |
| GET | `/api/v2/health` | Health (session count) | No |
| GET | `/api/v2/auth/debug` | OAuth config status (no secrets exposed) | No |
| GET | `/api/v2/auth/jwks` | JWT public key set | No |
| POST | `/api/v2/auth/session` | Create session (email/provider) | Service token |
| POST | `/api/v2/auth/introspect` | Verify + introspect JWT | Service token |
| POST | `/api/v2/auth/diagnostics/claims` | Diagnostic token decode | Owner role |
| GET | `/api/v2/auth/github` | GitHub OAuth redirect | No |
| GET | `/api/v2/auth/github/callback` | GitHub OAuth callback | No |
| GET | `/api/v2/auth/google` | Google OAuth redirect | No |
| GET | `/api/v2/auth/google/callback` | Google OAuth callback | No |
| POST | `/api/v2/auth/renew` | Silent owner token renewal | Owner role |

**Dependencies:**
- None (self-contained)

**Consumers:**
- All other v2 services (via introspection)

**Environment Variables:**
```
AUTH_SIGNING_SECRET              # (REQUIRED) JWT signing key
INTERNAL_SERVICE_TOKEN           # (REQUIRED) Service-to-service trust token
AUTH_ISSUER                      # JWT issuer claim (default: govos-auth)
AUTH_AUDIENCE                    # JWT audience claim (default: govos-v2)
AUTH_TOKEN_TTL_SECONDS           # Token lifetime (default: 3600)
GITHUB_CLIENT_ID                 # GitHub OAuth app ID
GITHUB_CLIENT_SECRET             # GitHub OAuth app secret
GOOGLE_CLIENT_ID                 # Google OAuth app ID
GOOGLE_CLIENT_SECRET             # Google OAuth app secret
APPLE_CLIENT_ID                  # Apple Sign-In app ID
APPLE_TEAM_ID                    # Apple Developer Team ID
APPLE_KEY_ID                     # Apple Sign-In private key ID
APPLE_PRIVATE_KEY                # Apple Sign-In private key (PEM)
MICROSOFT_CLIENT_ID              # Microsoft Entra app ID
MICROSOFT_CLIENT_SECRET          # Microsoft Entra app secret
MICROSOFT_TENANT_ID              # Azure tenant (default: common)
SMTP_HOST                        # Email server for magic links
SMTP_PORT                        # SMTP port (default: 587)
SMTP_USER                        # SMTP authentication user
SMTP_PASS                        # SMTP authentication password
SMTP_FROM                        # Sender address (default: noreply@12sgi.com)
AUTH_PUBLIC_URL                  # Public auth service URL (for OAuth callbacks)
OAUTH_REDIRECT_BASE              # Console redirect after OAuth
CORS_ORIGINS                     # Comma-separated allowed origins
OWNER_GITHUB_LOGINS              # Allowed GitHub logins (comma-separated)
OWNER_GOOGLE_EMAILS              # Allowed Google emails (comma-separated)
OWNER_APPLE_EMAILS               # Allowed Apple emails (comma-separated)
OWNER_MAGIC_EMAILS               # Allowed magic link emails (comma-separated)
WEBAUTHN_RP_ID                   # Passkey RP domain (e.g., 12sgi.com)
WEBAUTHN_ORIGIN                  # Passkey origin (e.g., https://12sgi.com)
AUTH_VERIFICATION_DIAGNOSTICS_ENABLED  # Enable /diagnostics/claims (dev only)
GOVOS_ALLOW_DEV_SECRETS          # Allow published dev secrets (local dev only)
```

**Status Indicators:**
- ✅ GitHub OAuth: Fully implemented
- ✅ Google OAuth: Fully implemented
- ⏳ Apple Sign-In: Stubbed in ALLOWED_PROVIDERS; endpoints not yet implemented
- ⏳ Microsoft Entra: Stubbed in ALLOWED_PROVIDERS; endpoints not yet implemented
- ⏳ Passkeys (WebAuthn): Listed in ALLOWED_PROVIDERS; not yet implemented
- ⏳ Magic Links: Listed in ALLOWED_PROVIDERS; SMTP config ready; not yet implemented

**Documentation:**
- Setup: `docs/OAUTH_SETUP.md`
- V1→V2 upgrade: `docs/V1_TO_V2_UPGRADE_MAP.md` § E

---

### 2. Tenant Service

**Owner:** James Langford  
**Port:** 8102  
**Version:** 2.0.0  
**Database:** SQLite (`/data/db/govos_v2_tenant.db`)

**Purpose:**  
Case lifecycle management, case metadata, case queries by tenant or owner.

**API Endpoints:**

| Method | Path | Purpose | Required Scope |
|--------|------|---------|---|
| GET | `/api/v2/live` | Liveness probe | — |
| GET | `/api/v2/ready` | Readiness (DB + Auth) | — |
| GET | `/api/v2/health` | Health (case count) | — |
| GET | `/api/v2/cases` | List cases (filtered by tenant) | `tenant:read` |
| POST | `/api/v2/cases` | Create case | `tenant:write` |
| GET | `/api/v2/cases/{case_id}` | Get case details | `tenant:read` |

**Dependencies:**
- Auth (required: `/api/v2/ready`)

**Consumers:**
- Documents service (verifies case existence)
- AI service (AI assistant requests reference case data)
- Frontend apps (case list, detail views)

**Database Schema:**

```sql
CREATE TABLE cases (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    title TEXT NOT NULL,
    status TEXT NOT NULL,             -- open, closed, archived
    notes TEXT,
    created_at TEXT NOT NULL,         -- ISO 8601 UTC
    created_by TEXT NOT NULL          -- JWT subject claim
);
```

**Environment Variables:**
```
TENANT_DB_PATH                   # SQLite path (default: /tmp/govos_v2_tenant.db)
AUTH_INTROSPECTION_URL           # Auth service introspection endpoint
INTERNAL_SERVICE_TOKEN           # Service-to-service token
DEPENDENCY_TIMEOUT_SECONDS       # Timeout for dependency checks (default: 3)
```

---

### 3. Documents Service

**Owner:** James Langford  
**Port:** 8103  
**Version:** 2.0.0  
**Database:** SQLite (`/data/db/govos_v2_documents.db`)

**Purpose:**  
Document generation from templates, document lifecycle, PDF/DOCX/HTML export.

**API Endpoints:**

| Method | Path | Purpose | Required Scope |
|--------|------|---------|---|
| GET | `/api/v2/live` | Liveness probe | — |
| GET | `/api/v2/ready` | Readiness (DB + Auth + Tenant) | — |
| GET | `/api/v2/health` | Health (document count) | — |
| POST | `/api/v2/documents/generate` | Request document generation | `documents:write` |
| GET | `/api/v2/documents/{document_id}` | Get document metadata | `documents:read` |

**Dependencies:**
- Auth (required)
- Tenant (required: verifies case exists)

**Consumers:**
- Frontend apps (download documents)
- Workboard (routes to creative lane for human review)

**Database Schema:**

```sql
CREATE TABLE documents (
    id TEXT PRIMARY KEY,
    template_id TEXT NOT NULL,        -- e.g., "affidavit-v1"
    tenant_id TEXT NOT NULL,
    case_id TEXT NOT NULL,
    output_format TEXT NOT NULL,      -- pdf, docx, html
    fields_json TEXT,                 -- template variables
    status TEXT NOT NULL,             -- generated, reviewed, published
    created_at TEXT NOT NULL,
    created_by TEXT NOT NULL
);
```

**Supported Output Formats:**  
`pdf`, `docx`, `html`

**Environment Variables:**
```
DOCUMENTS_DB_PATH                # SQLite path
AUTH_INTROSPECTION_URL
TENANT_SERVICE_URL               # Tenant service for case verification
TENANT_READY_URL
INTERNAL_SERVICE_TOKEN
DEPENDENCY_TIMEOUT_SECONDS
```

---

### 4. Storage Service

**Owner:** James Langford  
**Port:** 8104  
**Version:** 2.0.0  
**Database:** SQLite (`/data/db/govos_v2_storage.db`)

**Purpose:**  
Object storage abstraction, file metadata registry, download URL generation.

**API Endpoints:**

| Method | Path | Purpose | Required Scope |
|--------|------|---------|---|
| GET | `/api/v2/live` | Liveness probe | — |
| GET | `/api/v2/ready` | Readiness (DB + Auth) | — |
| GET | `/api/v2/health` | Health (object count) | — |
| POST | `/api/v2/storage/objects` | Create object metadata | `storage:write` |
| GET | `/api/v2/storage/objects` | List objects (tenant-scoped) | `storage:read` |
| GET | `/api/v2/storage/objects/{object_id}` | Get object metadata | `storage:read` |

**Dependencies:**
- Auth (required)

**Consumers:**
- Tenant (via Storage API for file uploads)
- Documents (references stored assets)

**Database Schema:**

```sql
CREATE TABLE objects (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    name TEXT NOT NULL,
    content_type TEXT NOT NULL,       -- e.g., application/pdf
    size_bytes INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    download_url TEXT NOT NULL,       -- signed or public
    created_by TEXT NOT NULL
);
```

**Environment Variables:**
```
STORAGE_DB_PATH
STORAGE_DOWNLOAD_BASE_URL         # Base for download links (default: https://storage.local/download)
AUTH_INTROSPECTION_URL
INTERNAL_SERVICE_TOKEN
DEPENDENCY_TIMEOUT_SECONDS
```

---

### 5. AI Service

**Owner:** James Langford  
**Port:** 8105  
**Version:** 2.0.0  
**Database:** SQLite (`/data/db/govos_v2_ai.db`)

**Purpose:**  
LLM-assisted case analysis, tenant AI guidance, inference via GPU router (Ollama).

**API Endpoints:**

| Method | Path | Purpose | Required Scope |
|--------|------|---------|---|
| GET | `/api/v2/live` | Liveness probe | — |
| GET | `/api/v2/ready` | Readiness (DB + Auth + Tenant + GPU Router optional) | — |
| GET | `/api/v2/health` | Health (assist count, grounded ratio) | — |
| POST | `/api/v2/ai/assist` | Request AI guidance on case | `ai:assist` |

**Dependencies:**
- Auth (required)
- Tenant (required: case verification)
- GPU Router (optional: if unavailable, returns `grounded=false` with template response)

**Consumers:**
- Tenant app (AI chat sidebar)
- Custom agents / external systems

**Database Schema:**

```sql
CREATE TABLE assist_events (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    case_id TEXT NOT NULL,
    prompt TEXT NOT NULL,
    context_json TEXT,                -- structured context
    summary TEXT NOT NULL,
    grounded INTEGER,                 -- 1 = real inference, 0 = template (GPU unavailable)
    created_at TEXT NOT NULL,
    created_by TEXT NOT NULL
);
```

**Grounded Ratio:**  
The `/health` endpoint reports `grounded_ratio`: a running count of real inferences vs. template responses. A sustained drop indicates GPU router / Ollama unavailability.

**Environment Variables:**
```
AI_DB_PATH
AUTH_INTROSPECTION_URL
TENANT_SERVICE_URL
TENANT_READY_URL
GPU_ROUTER_URL                    # GPU Router endpoint (default: http://gpu-router:8107)
GPU_ROUTER_READY_URL
GPU_DEFAULT_MODEL                 # Default Ollama model (default: llama3)
GPU_INFER_TIMEOUT                 # Max inference time in seconds (default: 120)
INTERNAL_SERVICE_TOKEN
DEPENDENCY_TIMEOUT_SECONDS
```

---

### 6. GPU Router

**Owner:** James Langford  
**Port:** 8107  
**Version:** 3.0.0  
**Database:** SQLite (`/data/db/govos_v2_gpu_router.db`)

**Purpose:**  
Multi-engine job queue orchestrator. Serializes Ollama inference (GPU), espeak-ng voice synthesis (CPU), embeddings. Tenant-aware concurrency limits, per-client priority, automatic retry on failure.

**API Endpoints:**

| Method | Path | Purpose | Required Scope |
|--------|------|---------|---|
| GET | `/api/v2/live` | Liveness probe | — |
| GET | `/api/v2/ready` | Readiness (DB + Auth + GPU Runtime) | — |
| GET | `/api/v2/health` | Health (queue depth, lane stats) | — |
| POST | `/api/v2/gpu/infer` | Enqueue job + block until done | `gpu:infer` |
| GET | `/api/v2/gpu/queue` | List pending/running jobs | `gpu:read` |
| GET | `/api/v2/gpu/usage` | Per-client usage stats | `gpu:read` |
| GET | `/api/v2/gpu/events` | Recent engine events (start/done/error) | `gpu:read` |

**Job Types:**

| Type | Engine | Resource | Parallel |
|------|--------|----------|----------|
| `ollama` | Ollama | GPU | Serialized (one at a time) |
| `embedding` | Ollama `/api/embeddings` | GPU-light | Serialized (CPU worker) |
| `voice` | espeak-ng | CPU | Serialized (CPU worker) |
| `comfyui` | ComfyUI (future) | GPU | Serialized |

**Dependencies:**
- Auth (required)
- GPU Runtime / Ollama (required for ollama + embedding lanes)
- espeak-ng (required for voice lane; best-effort if missing)

**Consumers:**
- AI service (inference requests)
- External clients (voice synthesis, embeddings)

**Database Schema:**

```sql
CREATE TABLE gpu_jobs (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    client_id TEXT NOT NULL,          -- e.g., govos-core, studio, workboard
    priority INTEGER NOT NULL,        -- lower = higher priority
    job_type TEXT NOT NULL,           -- ollama, voice, embedding, comfyui
    model TEXT NOT NULL,              -- e.g., llama3, haw, nomic-embed-text
    prompt TEXT NOT NULL,
    options_json TEXT,
    idempotency_key TEXT,
    status TEXT NOT NULL,             -- pending, running, done, error, timeout, retry
    result_json TEXT,
    error TEXT,
    created_at TEXT NOT NULL,
    started_at TEXT,
    available_at TEXT,
    lease_expires_at TEXT,
    finished_at TEXT,
    attempt_count INTEGER,
    max_attempts INTEGER,
    worker_name TEXT,
    claim_token TEXT,
    created_by TEXT NOT NULL
);

CREATE TABLE gpu_events (
    id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL,        -- job.queued, job.start, job.done, job.error, job.retry, job.timeout
    engine TEXT NOT NULL,            -- ollama, voice, embedding, worker-error
    job_id TEXT,
    detail_json TEXT,
    ts TEXT NOT NULL
);
```

**Priority Clients:**
```
govos-core:     1  (highest)
maui-tenant:    2
studio:         3
civic-signal:   4
workboard:      5
reports:        6
(unknown):      7  (default)
```

**Environment Variables:**
```
GPU_ROUTER_DB_PATH
GPU_RUNTIME_URL                   # Ollama endpoint (default: http://gpu-runtime:11434)
AUTH_INTROSPECTION_URL
AUTH_READY_URL
INTERNAL_SERVICE_TOKEN
DEPENDENCY_TIMEOUT_SECONDS
GPU_INFER_TIMEOUT                 # Max job time (default: 120s)
GPU_JOB_LEASE_SECONDS             # Worker lease TTL (default: 150s)
GPU_RETRY_BACKOFF_SECONDS         # Backoff before retry (default: 2s)
GPU_MAX_RETRIES                   # Retries per job (default: 2)
GPU_TENANT_CONCURRENCY_LIMIT      # Concurrent jobs per tenant (default: 1)
GPU_CLIENT_PRIORITIES             # Priority map (CSV k:v pairs)
VOICE_DEFAULT_LANG                # espeak-ng voice (default: haw)
VOICE_DEFAULT_RATE                # espeak-ng rate (default: 130)
VOICE_DEFAULT_PITCH               # espeak-ng pitch (default: 50)
```

---

### 7. Health Service

**Owner:** James Langford  
**Port:** 8106 (mapped to 8000 internally)  
**Version:** 0.1.0

**Purpose:**  
Aggregated health checks. Polls all govOS v2 services + external dependencies (Ollama, Neo4j, GitHub, etc.). Publishes unified status dashboard.

**API Endpoints:**

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/v1/live` | Liveness probe |
| GET | `/api/v1/ready` | Readiness (all dependencies up) |
| GET | `/api/v1/health` | Full health report |
| GET | `/admin/status` | Owner-only admin status page |

**Dependencies:**
- All v2 services (polled via `/api/v2/ready`)
- Ollama (optional)
- Neo4j (optional)
- GitHub API (optional)

**Configuration:**

Configured at startup via `SURFACES_LIST` env var:

```
SURFACES_LIST=auth=auth:8101,tenant=tenant:8102,documents=documents:8103,storage=storage:8104,ai=ai:8105,gpu-router=gpu-router:8107,king-bridge=king-bridge:8109,studio-assets=host.docker.internal:8108
```

**Environment Variables:**
```
SURFACES_LIST                     # Service discovery (name=host:port pairs)
SURFACES_HEALTH_PATH              # Health endpoint path (default: /api/v2/ready)
DEPENDENCY_TIMEOUT_SECONDS        # Poll timeout per service (default: 5)
ADMIN_BASIC_USER                  # Basic auth username (optional)
ADMIN_BASIC_PASS                  # Basic auth password (optional)
ADMIN_ALLOWED_IPS                 # Comma-separated IP/CIDR whitelist (optional)
RELEASE_FILE                      # Path to release.json for metadata (optional)
```

---

### 8. King Bridge

**Owner:** James Langford  
**Port:** 8109  
**Version:** 2.0.0  
**Database:** SQLite (`/data/db/king_bridge.db`)

**Purpose:**  
V1→V2 integration bridge. Routes workboard jobs to owner-trained Ollama models (local, zero cloud cost). Writes results to Neo4j. Replaces cloud AI calls with local inference.

**API Endpoints:**

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/v2/live` | Liveness probe |
| GET | `/api/v2/ready` | Readiness (Ollama + Neo4j) |
| GET | `/api/v2/bridge/models` | List available king-* models |
| POST | `/api/v2/bridge/job` | Submit job directly |
| GET | `/api/v2/bridge/pulse` | Workboard pulse counters |
| POST | `/api/v2/bridge/poll` | Drain pending workboard jobs |
| GET\|POST | `/api/v2/bridge/chat` | Direct LLM chat (SSE stream) |
| GET | `/api/v2/bridge/jobs` | Recent bridge job history |
| GET | `/owner_jobs.html` | Owner job tracking dashboard |

**Dependencies:**
- Neo4j (localhost:7474 or Aura)
- Ollama / GPU runtime
- Workboard dispatch log

**Model Routing:**

Jobs are routed to specialized models based on lane + action:

```
lawyer.*           → king-legal
prosecutor.*       → king-prosecutor
audit.*            → king-audit
civic.*            → king-civic
tax.*              → king-tax
sales.*            → king-sales
studio.*           → king-studio
game.*             → king-game
render.*           → king-render
social.*           → king-social
research.*         → king-research
creative/*         → king-workboard  (review/approve gate)
output/*           → king-dispatch
*.dispatch         → king-dispatch
default            → king-quad-os
```

**Environment Variables:**
```
KING_BRIDGE_DB
OLLAMA_BASE                       # Ollama endpoint (default: http://host.docker.internal:11434)
NEO4J_HTTP                        # Neo4j HTTP endpoint (default: http://127.0.0.1:7474/db/neo4j/tx/commit)
NEO4J_AURA_URI                    # Neo4j Aura URI (optional)
NEO4J_AURA_USER                   # Neo4j Aura username
NEO4J_AURA_PASSWORD               # Neo4j Aura password
INTERNAL_SERVICE_TOKEN
DEPENDENCY_TIMEOUT_SECONDS
KING_BRIDGE_INFER_TIMEOUT         # Max inference time (default: 120s)
KING_BRIDGE_POLL_MAX              # Max jobs per poll (default: 10)
KING_BRIDGE_AUTONOMY_ENABLED      # Enable autonomous execution (default: true)
KING_BRIDGE_AUTONOMY_THRESHOLD    # Autonomy score threshold % (default: 70)
```

---

### 9. Studio-Assets Service

**Owner:** James Langford  
**Port:** 8108  
**Version:** 1.0.0  
**Database:** SQLite (`/data/db/studio_assets.db`)  
**Compose Project:** `studio-assets` (isolated, non-interfering)

**Purpose:**  
Read-only asset manager for render vaults, delivery masters, audio. Indexes from existing asset_index.json and supplements via stat-only scan of finalized vaults.

**API Endpoints:**

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/v2/live` | Liveness probe |
| GET | `/api/v2/ready` | Readiness (DB check) |
| GET | `/api/v2/health` | Health (asset count, by-source breakdown) |
| GET | `/api/v2/stats` | Asset statistics (total bytes, by label, by ext) |
| GET | `/api/v2/assets` | List assets (filtered by q/label/ext/tenant) |
| GET | `/api/v2/assets/search` | Full-text search by name/path |
| GET | `/api/v2/assets/{key}` | Get asset metadata |
| GET | `/api/v2/assets/{key}/thumb` | Get asset thumbnail (JPEG) |
| GET | `/api/v2/assets/{key}/file` | Download asset file |
| POST | `/api/v2/reindex` | Trigger full reindex |

**Safety Guarantees:**
- Port: 127.0.0.1:8108 only (loopback + Tailscale boundary)
- GPU: None (IO-only, no CUDA reservation)
- Mutations: Fail-closed write probe ensures all asset mounts are read-only (kernel-enforced). No PUT/PATCH/DELETE endpoints exist.
- Live renders: Stat-only scan (no byte reads); skips ComfyUI/output render dir.

**Dependencies:**
- None (standalone)

**Consumers:**
- Browser (asset discovery, thumbnail browsing)
- Frontend apps (asset references in cases)

**Database Schema:**

```sql
CREATE TABLE assets (
    key TEXT PRIMARY KEY,
    label TEXT,
    name TEXT,
    ext TEXT,
    host_path TEXT UNIQUE,
    container_path TEXT,
    size INTEGER,
    mtime INTEGER,
    thumb_file TEXT,
    archivable INTEGER,
    archived INTEGER,
    source TEXT,                     -- "index" or "scan"
    indexed_at INTEGER
);
```

**Environment Variables:**
```
STUDIO_ASSETS_DB_PATH
STUDIO_INDEX_JSON                 # asset_index.json path (default: /data/index/asset_index.json)
STUDIO_THUMBS_DIR                 # Thumbnail directory (default: /data/index/thumbnails)
STUDIO_ASSET_MOUNTS               # Comma-separated read-only mount list
STUDIO_SCAN_ROOTS                 # Finalized vaults to stat-scan (excludes live render target)
STUDIO_SCAN_MAX_FILES             # Scan cap (default: 200000)
STUDIO_HOST_*                     # Host path mappings (for asset_index.json resolution)
STUDIO_ASSETS_REQUIRE_AUTH        # Require auth (default: 0)
```

---

### 10. Connector Runner

**Type:** Background worker (not HTTP service)  
**Purpose:** Sync social channels (Facebook, Instagram, LinkedIn, TikTok, X/Twitter) with approved posts from the workboard.

**Workflow:**
1. Approve draft in workboard (creative lane)
2. Connector runner polls workboard
3. Routes to Postiz (self-hosted, free, local Docker at 127.0.0.1:4008)
4. Post goes live on configured channels
5. Never auto-publishes without explicit approval tombstone

**Configuration:**
- Manual queue for X/Twitter (no free write API tier as of 2026)
- Manual queue for TikTok (platform-specific restrictions)
- Automated for Facebook, Instagram, LinkedIn (via Postiz)

**Dependencies:**
- Postiz instance (docker-compose.postiz.yml)
- Workboard dispatch log
- Config files in `config/social_drafts/`

---

### 11. GitHub Workflow Monitor

**Type:** Background worker (not HTTP service)  
**Version:** Auto-repair enabled for failed CI runs (75%+ autonomy threshold, up to 3 concurrent retries)

**Purpose:** Monitor GitHub Actions CI/CD. Auto-repair failing builds on 2026-07-10+ deployments when autonomy confidence ≥ 75%.

**Configuration:**
```
GITHUB_TOKEN                      # GitHub PAT for Actions API
GITHUB_OWNER                      # Repo owner (default: jimlangford)
GITHUB_REPO                       # Repo name (default: 12sgi-king)
GITHUB_WORKFLOW_MONITOR_ENABLED   # Enable monitoring (default: true)
GITHUB_REPAIR_LOOKBACK_MINUTES    # Window for failed runs (default: 60)
GITHUB_REPAIR_INTERVAL_SECONDS    # Check interval (default: 300)
GITHUB_REPAIR_AUTONOMY_THRESHOLD  # Repair if confidence ≥ (default: 75)
GITHUB_REPAIR_MAX_CONCURRENT      # Concurrent repairs (default: 3)
GITHUB_AUTO_REPAIR_DRY_RUN        # Dry-run only (default: false)
```

---

## Dependency Graph

```
                    ┌─ Auth (8101)
                    │
        ┌───────────┼─ Tenant (8102)
        │           │
        │           ├─ Documents (8103)
        │           │
        │           ├─ Storage (8104)
        │           │
        │           └─ AI (8105) ──→ GPU Router (8107) ──→ Ollama
        │
        └─ Health (8106) ← all of the above

        king-bridge (8109) ← Workboard ← Ollama + Neo4j
        studio-assets (8108) ← (standalone)
```

---

## Starting All Services

```bash
cd 12sgi-king

# Create .env.v2 with OAuth credentials (see docs/OAUTH_SETUP.md)
cp .env.v2.example .env.v2
# Edit .env.v2 with real GitHub/Google credentials

# Start v2 stack
docker compose -f docker-compose.v2.yml --env-file .env.v2 up -d

# Verify all services are ready
curl http://127.0.0.1:8106/api/v1/health

# Check auth config
curl http://127.0.0.1:8101/api/v2/auth/debug
```

---

## Healthchecks

**Per-service health endpoints:**

```bash
curl http://127.0.0.1:8101/api/v2/health  # auth
curl http://127.0.0.1:8102/api/v2/health  # tenant
curl http://127.0.0.1:8103/api/v2/health  # documents
curl http://127.0.0.1:8104/api/v2/health  # storage
curl http://127.0.0.1:8105/api/v2/health  # ai (includes grounded ratio)
curl http://127.0.0.1:8106/api/v1/health  # health aggregator
curl http://127.0.0.1:8107/api/v2/health  # gpu-router
curl http://127.0.0.1:8109/api/v2/ready   # king-bridge
curl http://127.0.0.1:8108/api/v2/health  # studio-assets
```

**Readiness probes (for k8s/compose healthchecks):**

```bash
curl http://127.0.0.1:8101/api/v2/ready   # auth: DB ready
curl http://127.0.0.1:8102/api/v2/ready   # tenant: DB + Auth ready
curl http://127.0.0.1:8103/api/v2/ready   # documents: DB + Auth + Tenant ready
curl http://127.0.0.1:8104/api/v2/ready   # storage: DB + Auth ready
curl http://127.0.0.1:8105/api/v2/ready   # ai: DB + Auth + Tenant ready (GPU optional)
curl http://127.0.0.1:8106/api/v1/ready   # health: all deps ready
curl http://127.0.0.1:8107/api/v2/ready   # gpu-router: DB + Auth + GPU Runtime ready
```

**Liveness probes (for k8s/compose restart on crash):**

```bash
curl http://127.0.0.1:8101/api/v2/live    # auth
curl http://127.0.0.1:8102/api/v2/live    # tenant
# ... etc.
```

---

## Adding a New Service

1. Create `services/<name>/app/main.py` with FastAPI app
2. Add to `docker-compose.v2.yml` with:
   - Dockerfile: `services/Dockerfile`
   - Command: `uvicorn services.<name>.app.main:app --host 0.0.0.0 --port 81XX`
   - Environment: inherit from `x-common-env` + service-specific vars
   - Health check: depends_on + healthcheck stanza
   - Volume: `/data/db` for SQLite
3. Add entry to `SERVICE_REGISTRY.md` (this file)
4. Add entry to Health service's `SURFACES_LIST` env var
5. Update `INTERNAL_SERVICE_TOKEN` and `AUTH_SIGNING_SECRET` in `.env.v2`
6. Restart: `docker compose -f docker-compose.v2.yml up -d`

---

## Contact & Issues

- **Platform architect:** James Langford (@jimlangford)
- **Bug reports:** GitHub Issues (12sgi-king)
- **Architecture questions:** See `docs/QUAD_OS_MASTER_ARCHITECTURE.md`
- **Auth/OAuth issues:** See `docs/OAUTH_SETUP.md`
- **OAuth cred management:** See `.env.v2` template
