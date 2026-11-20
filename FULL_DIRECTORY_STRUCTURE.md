# 12sgi-king Full Directory Structure & Documentation

## Project Overview

**12sgi-king** is a comprehensive civic transparency and governance platform with:
- 297+ government monitoring dashboards (Kilo Aupuni)
- AI-powered governance analysis (Neo4j graph database, 14,300 nodes)
- Multi-tenant deployment system (18 jurisdictions globally)
- Docker containerized microservices (V2 stack, 11 services)
- Media production & rendering system (game studio, creative assets)
- Real-time civic data collection & publishing

---

## Complete Directory Map

```
12sgi-king/
│
├── Root Configuration Files
│   ├── .github/                           (GitHub Actions & CI/CD)
│   │   └── workflows/
│   │       ├── publish.yml               (Daily civic data → GitHub Pages)
│   │       ├── deploy-v2-king-server.yml (V2 services deployment)
│   │       ├── deploy-v2-node.yml        (Node deployment)
│   │       ├── ci-accessibility.yml
│   │       ├── ci-lint.yml
│   │       ├── ci-secret-scan.yml
│   │       ├── ci-test.yml
│   │       └── [11 more workflows...]
│   │
│   ├── docker-compose.v2.yml             (V2 microservices stack)
│   ├── docker-compose.neo4j.yml          (Isolated Neo4j brain)
│   ├── Dockerfile                        (Multi-stage build for V2 services)
│   ├── .dockerignore                     (Docker build optimization)
│   ├── .gitignore                        (Git exclusions)
│   ├── .gitattributes
│   ├── requirements.txt                  (Python dependencies)
│   ├── packages.json                     (Node/npm packages)
│   ├── VERSION                           (Release versioning)
│   ├── production_status.json             (Deployment status metadata)
│   ├── CODEOWNERS                        (GitHub code ownership)
│   ├── CODE_OF_CONDUCT.md
│   └── README.md                         (Root documentation)
│
├── Documentation Suite (25+ guides)
│   ├── DEPLOYMENT_COMPLETE.md            (V2 deployment summary)
│   ├── TAILSCALE_COMPLETE.md             (Zero-trust networking)
│   ├── TAILSCALE_SETUP_GUIDE.md          (15-min Tailscale setup)
│   ├── TAILSCALE_PUBLIC_PRIVATE_ARCH.md  (Architecture)
│   ├── TAILSCALE_DEPLOYMENT_COMPLETE.md  (95% complete status)
│   ├── TAILSCALE_DEPLOY_STATUS.py        (Status checker)
│   ├── LOCAL_SERVER_GUIDE.md             (Local hosting)
│   ├── LOCAL_SERVER_COMPLETE.md          (Server reference)
│   ├── GITHUB_PAGES_LOCAL.md             (297 dashboards locally)
│   ├── GITHUB_PAGES_LOCAL_COMPLETE.md    (Complete reference)
│   ├── CLAUDE_INTEGRATION_GUIDE.md       (Claude setup)
│   ├── NEO4J_GUIDE.md                    (Graph DB operations)
│   ├── NEO4J_VERIFICATION_*.md           (Neo4j status reports)
│   ├── ARCHITECTURE.md                   (System architecture)
│   ├── DISPATCH_LOG.md
│   ├── HEALING_WORKING_LINKS.txt
│   ├── CANON.md
│   ├── AGENTS.md
│   └── [15+ more documentation files...]
│
├── 📦 Services (V2 Microservices Stack)
│   ├── services/
│   │   ├── Dockerfile                   (Shared build for all V2 services)
│   │   ├── entitlements.py              (Identity bridge to WordPress)
│   │   ├── authz.py                     (Authorization layer)
│   │   ├── v2_workboard.py              (Workboard state management)
│   │   ├── github_workflow_monitor.py   (CI/CD integration)
│   │   ├── github_auto_repair.py        (Workflow repair)
│   │   ├── gordon_*.py                  (Gordon AI assistant integration)
│   │   ├── healing_api.py               (Self-healing services)
│   │   ├── event_bus.py                 (Event streaming)
│   │   ├── error_corrector.py           (Error recovery)
│   │   ├── task_orchestrator.py         (Job orchestration)
│   │   ├── owner_job_tracker.py         (Owner console jobs)
│   │   ├── backend_model.py             (Shared models)
│   │   ├── __pycache__/
│   │   │
│   │   ├── auth/                        (8101 - Identity Service)
│   │   │   ├── requirements.txt
│   │   │   ├── README.md
│   │   │   └── app/
│   │   │       ├── main.py              (FastAPI server)
│   │   │       ├── auth_sprint1.py      (Auth implementation)
│   │   │       └── passkeys.py          (WebAuthn support)
│   │   │
│   │   ├── tenant/                      (8102 - Multi-tenant Service)
│   │   │   ├── requirements.txt
│   │   │   ├── README.md
│   │   │   └── app/
│   │   │       └── main.py
│   │   │
│   │   ├── documents/                   (8103 - Document Management)
│   │   │   ├── requirements.txt
│   │   │   ├── README.md
│   │   │   └── app/
│   │   │       └── main.py
│   │   │
│   │   ├── storage/                     (8104 - File Storage)
│   │   │   ├── requirements.txt
│   │   │   ├── README.md
│   │   │   └── app/
│   │   │       └── main.py
│   │   │
│   │   ├── ai/                          (8105 - AI Inference)
│   │   │   ├── requirements.txt
│   │   │   ├── README.md
│   │   │   └── app/
│   │   │       └── main.py
│   │   │
│   │   ├── ai_gateway/                  (AI Access Layer)
│   │   │   ├── requirements.txt
│   │   │   └── app/
│   │   │       └── main.py
│   │   │
│   │   ├── health/                      (8106 - Fleet Health Aggregator)
│   │   │   ├── requirements.txt
│   │   │   ├── README.md
│   │   │   ├── .env.example
│   │   │   ├── app/
│   │   │   │   ├── main.py
│   │   │   │   └── checks.py
│   │   │   └── templates/
│   │   │       └── admin_status.html
│   │   │
│   │   ├── gpu_router/                  (8107 - GPU Orchestration)
│   │   │   ├── requirements.txt
│   │   │   └── app/
│   │   │       └── main.py
│   │   │
│   │   ├── king_bridge/                 (8109 - Workboard Bridge)
│   │   │   ├── requirements.txt
│   │   │   └── app/
│   │   │       ├── main.py
│   │   │       └── _tree.py             (Neo4j tree building)
│   │   │
│   │   ├── board_api/                   (8799 - Owner Console API)
│   │   │   ├── main.py
│   │   │   └── requirements.txt
│   │   │
│   │   ├── studio_assets/               (8108 - Media Production)
│   │   │   ├── requirements.txt
│   │   │   ├── README.md
│   │   │   └── app/
│   │   │       ├── main.py
│   │   │       ├── fcp_adapter.py       (Final Cut Pro)
│   │   │       ├── game_api.py
│   │   │       ├── logic_adapter.py
│   │   │       ├── project_api.py
│   │   │       ├── script_api.py
│   │   │       ├── security.py
│   │   │       └── storyboard_api.py
│   │   │
│   │   ├── connectors/                  (Background Connector Runner)
│   │   │   ├── registry.py
│   │   │   ├── runner.py
│   │   │   ├── token_store.py
│   │   │   └── __init__.py
│   │   │
│   │   └── studio_interchange/          (Media Format Conversion)
│   │       ├── fcpxml.py                (Final Cut Pro XML)
│   │       ├── logic_manifest.py        (Logic Pro manifests)
│   │       └── __init__.py
│   │
├── 📊 Civic Data & Dashboards
│   ├── site/                            (297+ Published Dashboards - GitHub Pages)
│   │   ├── reports.html                 (Main civic hub)
│   │   ├── tenants_hub.html             (Jurisdiction picker)
│   │   ├── county_dashboard.html        (County overview)
│   │   ├── datasets.html                (Open data)
│   │   ├── govos-shell.js               (Frontend framework)
│   │   ├── govos.css                    (Styling)
│   │   ├── legibility_fix.css
│   │   │
│   │   ├── Agendas (18 jurisdictions)
│   │   │   ├── agendas_maui.html
│   │   │   ├── agendas_honolulu.html
│   │   │   ├── agendas_state.html
│   │   │   ├── agendas_nyc.html
│   │   │   ├── agendas_hawaii.html
│   │   │   ├── agendas_kauai.html
│   │   │   └── [12 more international locations]
│   │   │
│   │   ├── Money & Contracts
│   │   │   ├── money_behind_officials.html
│   │   │   ├── contracts_maui.html
│   │   │   ├── statewide_money_patterns.html
│   │   │   ├── parity_check.html        (Money vs. votes)
│   │   │   └── [30+ more pages]
│   │   │
│   │   ├── Charter & Law
│   │   │   ├── crosswalk_maui.html
│   │   │   ├── charter_law_map.html
│   │   │   └── [18 jurisdiction crosswalks]
│   │   │
│   │   ├── Special Reports
│   │   │   ├── wildfire_recovery_watch.html
│   │   │   ├── n53_engine.html          (Corruption risk scoring)
│   │   │   ├── testimony_watch.html
│   │   │   ├── federal_money.html
│   │   │   └── vatican_finances.html
│   │   │
│   │   ├── donor_profiles.json          (Donor data)
│   │   ├── officials.json               (Official records)
│   │   ├── donors/                      (Individual donor pages)
│   │   ├── games/                       (Civic learning games)
│   │   │   ├── hawaiian_konami.html
│   │   │   ├── konane.html              (Hawaiian chess)
│   │   │   ├── mahjong_crosswalk.html
│   │   │   ├── moon_cal.html
│   │   │   └── weiqi.html
│   │   │
│   │   ├── king/                        (King-specific content)
│   │   │   ├── aupuni.html
│   │   │   ├── charter-explainer.html
│   │   │   ├── civic/templates/        (30+ charter templates)
│   │   │   └── go/                      (Quick access links)
│   │   │
│   │   └── sage/                        (Analytics realm)
│   │       └── index.html
│   │
│   ├── seed_reports/                    (Committed Historical Data Floor)
│   │   └── mauios/                      (400+ cached reports)
│   │       ├── [All 297 pages cached locally]
│   │       ├── bill9/
│   │       ├── donors/
│   │       └── lege/
│   │
│   ├── reports/                         (Runtime-generated reports)
│   │   ├── mauios/
│   │   │   ├── [Generated during watchers run]
│   │   │   ├── _status/
│   │   │   └── selfheal.html
│   │   └── _status/
│   │       ├── self_develop.json
│   │       └── studio_parity.json
│   │
│   └── content/                         (Static content)
│       └── wordpress/                   (WordPress exports)
│           └── branch_pages/
│               ├── maui/
│               ├── honolulu/
│               └── [8 jurisdiction branches]
│
├── 📡 Data Collection & Processing
│   ├── watchers/                        (30+ Civic Data Collectors)
│   │   ├── agenda_watch.py              (Legistar integration)
│   │   ├── votes_watch.py               (Voting records)
│   │   ├── council_watch.py             (Council data)
│   │   ├── minutes_watch.py             (Meeting minutes)
│   │   ├── testimony_watch.py           (Public testimony)
│   │   ├── donor_watch.py               (Campaign finance)
│   │   ├── hands_awards.py              (Contract procurement)
│   │   ├── federal_money.py             (USASpending integration)
│   │   ├── ny_watch.py                  (New York data)
│   │   ├── lobby_money_watch.py         (Lobby + money correlation)
│   │   ├── charter_crosswalk.py         (Charter to law mapping)
│   │   ├── vatican_finances.py          (Holy See financial reports)
│   │   ├── parity_check.py              (Money vs. votes analysis)
│   │   ├── n53_ingest.py                (Corruption risk scoring)
│   │   ├── sage_bridge.py               (AI analysis bridge)
│   │   ├── graph_refresh.py             (Neo4j synchronization)
│   │   │
│   │   ├── sage_trinity.py              (Sage analytics)
│   │   ├── studio_parity.py             (Media parity)
│   │   ├── self_develop.py              (Auto-improvement)
│   │   ├── service_modules_build.py     (Service building)
│   │   ├── selfheal.py                  (Auto-healing)
│   │   │
│   │   ├── commission_inputs.json       (Config)
│   │   ├── departments.json
│   │   ├── tenants.json
│   │   ├── n53_archive.json
│   │   ├── agenda_sources.json
│   │   │
│   │   ├── [60+ more watchers...]
│   │   ├── Media watchers (games, clips, rendering)
│   │   ├── Governance watchers (legislative tracking)
│   │   ├── Analysis watchers (parity, correlation)
│   │   └── Publishing watchers (social, media)
│   │
│   ├── build_site.py                    (HTML generation from data)
│   ├── rebuild_site.py                  (Incremental rebuild)
│   ├── civic_shell.py                   (CLI for civic operations)
│   └── tenant_registry.json             (Multi-tenant configuration)
│
├── 🎬 Media Production
│   ├── game_studio/                     (Game development)
│   │   ├── [Game source files]
│   │   └── [Interactive learning modules]
│   │
│   ├── game_sage/                       (Sage-powered games)
│   │   └── [Sage-integrated gameplay]
│   │
│   ├── king_public_src/                 (King media sources)
│   │   └── [Media assets]
│   │
│   ├── element_lotus_public/            (Element Lotus media)
│   │   └── [Public media]
│   │
│   └── shared-ui/                       (Shared UI components)
│       ├── lab-preview.css
│       ├── shared-ui.css
│       └── [UI components]
│
├── 🔧 Infrastructure & Tools
│   ├── tools/
│   │   ├── reconcile.py                 (Config validation)
│   │   ├── service_module_engine.py     (Service building)
│   │   ├── lint_ai_tool_registry.py     (AI tools validation)
│   │   ├── Modelfile.*                  (Ollama model configs)
│   │   │   ├── Modelfile.king-civic
│   │   │   ├── Modelfile.king-server
│   │   │   ├── Modelfile.king-workboard
│   │   │   └── Modelfile.king-jrcsl
│   │   │
│   │   ├── auth/                        (Authentication tools)
│   │   │   ├── import_google_credentials.py
│   │   │   └── import_smtp_credentials.py
│   │   │
│   │   ├── [20+ more tools...]
│   │   └── title19_share.png
│   │
│   ├── scripts/
│   │   ├── check_surfaces.sh            (Tailscale health check)
│   │   ├── batch_close_workboard.sh
│   │   └── [More automation]
│   │
│   ├── v2/                              (V2 Specific Tools)
│   │   ├── scripts/
│   │   │   ├── tailscale-check.sh
│   │   │   ├── pull-models.sh
│   │   │   ├── start.sh
│   │   │   └── stop.sh
│   │   │
│   │   ├── .env.example
│   │   ├── .gitignore
│   │   ├── docker-compose.yml
│   │   ├── Dockerfile
│   │   ├── README.md
│   │   │
│   │   ├── app/
│   │   │   ├── main.py
│   │   │   ├── healthcheck.py
│   │   │   └── hf_pull.py
│   │   │
│   │   ├── data/                        (Model cache)
│   │   │   └── .gitkeep
│   │   │
│   │   ├── models/                      (Local model storage)
│   │   │   └── .gitkeep
│   │   │
│   │   └── secrets/                     (Credential storage)
│   │       └── .gitkeep
│   │
│   └── deploy/                          (Deployment configs)
│       ├── [Deployment scripts]
│       └── [Infrastructure code]
│
├── 🧪 Testing Suite
│   ├── tests/
│   │   ├── v2/                          (V2 Tests)
│   │   │   ├── test_v2_contract.py      (Smoke tests - 8 cases)
│   │   │   ├── test_v2_integration_stack.py
│   │   │   ├── test_v2_hardening.py
│   │   │   ├── test_gpu_router_hardening.py
│   │   │   ├── test_github_workflow_monitor_service.py
│   │   │   ├── test_platform_manifest_consistency.py
│   │   │   ├── test_ai_gateway_policy.py
│   │   │   ├── test_event_bus.py
│   │   │   ├── test_canonical_job_contract.py
│   │   │   ├── test_v2_client_migration.py
│   │   │   ├── test_media_phase21.py
│   │   │   ├── test_media_phase22.py
│   │   │   ├── _test_helpers.py
│   │   │   └── __pycache__/
│   │   │
│   │   ├── test_entitlements.py
│   │   ├── test_sage_trinity.py
│   │   ├── test_studio_assets_crosswalk.py
│   │   ├── test_release_pipeline.py
│   │   ├── test_self_develop.py
│   │   ├── test_private_spine.py
│   │   ├── [20+ more tests]
│   │   └── __init__.py
│   │
│   └── check_health_local.sh            (Local health check)
│
├── 📦 Packages & Dependencies
│   ├── packages/
│   │   ├── components/                  (UI components)
│   │   │   └── README.md
│   │   │
│   │   ├── ui/                          (UI package)
│   │   │   └── README.md
│   │   │
│   │   └── shared/                      (Shared utilities)
│   │       └── README.md
│   │
│   └── packages.json                    (NPM packages)
│
├── 💾 Data & Configuration
│   ├── data/                            (Runtime data)
│   │   ├── [Generated data files]
│   │   └── [Cached responses]
│   │
│   ├── config/                          (Configuration)
│   │   ├── [Service configs]
│   │   └── [Environment configs]
│   │
│   ├── logs/                            (Deployment logs)
│   │   ├── v2-deploy/                   (V2 deployment logs)
│   │   ├── [Execution logs]
│   │   └── [Error logs]
│   │
│   ├── minutes_text/                    (Extracted meeting minutes)
│   │   └── [Legistar transcripts]
│   │
│   ├── narratives.json                  (Story data)
│   ├── tenant_registry.json             (Tenant configuration)
│   ├── tenant_directory.py              (Tenant lookup)
│   └── blog_posts_seed.json             (Blog content)
│
├── 🌐 Web Applications
│   ├── apps/                            (React/Node.js applications)
│   │   ├── admin/public/                (Admin console)
│   │   │   └── index.html
│   │   │
│   │   ├── civic-signal/public/         (Civic Signal app)
│   │   │   └── index.html
│   │   │
│   │   ├── govos/public/                (GovOS platform)
│   │   │   └── index.html
│   │   │
│   │   └── tenant/public/               (Tenant portal)
│   │       └── index.html
│   │
├── 🚀 Local Development Tools
│   ├── serve.py                         (Local HTTP server - port 8080)
│   ├── start_local_server.py            (Background startup)
│   ├── local_server.py                  (Advanced server)
│   ├── local_server_simple.py           (Minimal variant)
│   ├── health_check.py                  (System validation)
│   ├── startup_system.py                (Automated startup + Docker recovery)
│   ├── status_dashboard.py              (Real-time monitoring)
│   ├── verify_neo4j.py                  (Neo4j verification)
│   ├── TAILSCALE_DEPLOY_STATUS.py       (Tailscale status)
│   │
│   ├── .claude/                         (Claude integration)
│   │   └── [Claude-specific config]
│   │
│   └── [Development utilities]
│
└── 📚 Documentation & References
    ├── Documentation Suite (see above)
    ├── docs/                            (Legacy docs)
    │   └── Tailscale_INTEGRATION_VALIDATION.md
    │
    ├── staging/                         (Staging content)
    │   ├── civic_components.html
    │   └── maui_civic_record_v3.html
    │
    ├── [HTML pages for public routes]
    │   ├── 404.html
    │   ├── about.html
    │   ├── contact.html
    │   ├── education.html
    │   ├── gordon.html
    │   ├── go.html
    │   ├── grants.html
    │   ├── join.html
    │   ├── king_bridge.html
    │   ├── king_landing.html            (Root landing page)
    │   ├── platform.html
    │   ├── take_action.html
    │   └── testify.html
    │
    └── [Version & status files]
        ├── VERSION
        ├── CODEOWNERS
        ├── production_status.json
        └── [Other metadata]
```

---

## Key Statistics

| Category | Count | Details |
|----------|-------|---------|
| **Services** | 11 | auth, tenant, documents, storage, ai, gpu-router, health, king-bridge, board-api, studio_assets, connectors |
| **Dashboards** | 297+ | Civic transparency pages |
| **Watchers** | 60+ | Data collection agents |
| **Jurisdictions** | 18 | Hawaii (state + 4 counties), NYC, NY State, + 11 international |
| **Graph Nodes** | 14,300 | Neo4j knowledge graph |
| **Games** | 5+ | Hawaiian Konami, Konane, Mahjong, Moon Cal, Weiqi |
| **Tests** | 20+ | Unit + integration tests |
| **Workflows** | 15+ | GitHub Actions pipelines |
| **Python Files** | 150+ | Services, watchers, tools |
| **HTML Files** | 400+ | Static dashboards + templates |

---

## Core Layers

### Layer 1: Data Collection (Watchers)
- 60+ Python scripts collecting from 30+ civic data sources
- Runs daily via GitHub Actions
- Outputs: HTML dashboards, JSON data, Neo4j graph updates

### Layer 2: Backend Services (V2 Microservices)
- 11 FastAPI services in Docker
- Shared Neo4j database (14,300 nodes)
- Ports: 8101-8109, 8799
- Deployment via docker-compose.v2.yml

### Layer 3: Frontend (GitHub Pages + Local)
- 297+ static HTML dashboards
- CDN-backed via GitHub Pages
- Locally hosted via serve.py (port 8080)
- Accessible at: https://12sgi.com/site/

### Layer 4: Analytics (Sage)
- AI-powered analysis
- Real-time correlation analysis
- Graph-based insights

### Layer 5: Media Production
- Game studio (5+ games)
- Media rendering (ComfyUI integration)
- Script management (Final Cut Pro, Logic Pro)

---

## Deployment Modes

### Mode 1: CI/CD Automated
```
GitHub push → Actions workflow → 
  1. Watchers collect data → 
  2. Build static site → 
  3. Deploy to GitHub Pages → 
  4. Notify king-server via Tailscale
```
**Time**: ~5-10 minutes daily

### Mode 2: Local Development
```
serve.py (port 8080) →
  Docker compose stack → 
  Neo4j (7474, 7687) →
  V2 services (8101-8109, 8799)
```
**Time**: Start immediately

### Mode 3: Private Backend (Tailscale)
```
Tailscale network (100.124.152.3) →
  Zero-trust ACL control →
  All backend services protected →
  CI/CD connects via pre-auth key
```
**Time**: Always-on

---

## Quick Access Paths

### Public Content
- **Hub**: `/site/reports.html`
- **Agendas**: `/site/agendas_[jurisdiction].html`
- **Money**: `/site/money_behind_officials.html`
- **Charter**: `/site/crosswalk_[jurisdiction].html`

### Private Services (Tailscale)
- **Neo4j**: `http://100.124.152.3:7474/`
- **Auth**: `http://100.124.152.3:8101/`
- **Board API**: `http://100.124.152.3:8799/api/dispatch/log`
- **Health**: `http://100.124.152.3:8106/api/v1/ready`

### Local Development
- **Local server**: `http://localhost:8080/`
- **Local dashboards**: `http://localhost:8080/site/`
- **Neo4j**: `http://localhost:7474/` (when running)

---

## Integration Points

1. **GitHub Actions** → Triggers watchers daily
2. **GitHub Pages** → Hosts 297 dashboards publicly
3. **Tailscale** → Protects backend services
4. **Neo4j** → Central knowledge graph (14.3k nodes)
5. **Docker** → Containerizes all services
6. **LocalAI/Ollama** → Powers AI analysis
7. **ComfyUI** → Media rendering

---

**This is a production-grade civic transparency platform with automation, protection, and monitoring at every layer.**

