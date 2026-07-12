# Service Registry

This document lists services, owners, and essential metadata. Use this as the canonical place to learn who owns what and how to reach services.

Template for each service
- Owner: 
- Purpose: 
- API: 
- Health endpoint: 
- Dependencies: 
- Authentication: 
- Deployment target: 
- Monitoring: 

Pre-populated services

QUAD OS Core
- Owner: James Langford
- Purpose: Platform core functionality and orchestration
- API: TBD
- Health: /api/v1/health
- Dependencies: Auth, Event Bus, Config
- Authentication: Service tokens, RBAC
- Deployment: Internal Tailnet
- Monitoring: Prometheus metrics, health checks

govOS
- Owner: James Langford
- Purpose: Civic interface and case management UX
- API: /api/v1/
- Health: /api/v1/health
- Dependencies: Auth, Documents, Event Bus
- Authentication: OAuth/passkeys
- Deployment: Internal + public proxy for UI
- Monitoring: UI metrics, error reporting

Element LOTUS
- Owner: James Langford
- Purpose: Creative/AI experiences for content generation and publishing
- Health: /api/v1/health
- Dependencies: AI, Storage, Event Bus
- Owner contact: @jimlangford
- Current implementation (2026-07-10): the `creative` lane of `services/v2_workboard.py`.
  Drafts are staged via `tools/stage_social_drafts.py` (batch files under
  `config/social_drafts/*.json`), reviewed on `king_public_src/social_drafts_board.html`
  (owner device, Tailscale `/social.html`), and closed out with
  `python -m services.v2_workboard --approve|--reject <job_id>`. Never auto-publishes on
  approval alone — an explicit `tools/publish_approved_social.py` call is required to actually
  post (see below), per `docs/SOCIAL_CONNECTORS.md`.
- Resolved 2026-07-11 (owner in-session decision): actual PUBLISH for Facebook/Instagram/
  LinkedIn now goes through `watchers/own_channel_post.py` + a self-hosted Postiz instance
  (`docker-compose.postiz.yml`, free, local, `127.0.0.1:4008`), gated by
  `tools/publish_approved_social.py` (fail-closed on the same approval tombstone this doc
  already required). X/Twitter is intentionally NOT auto-posted — its write API has no free
  tier as of 2026 — and stays in a manual queue (`config/x_manual_queue.json`) alongside the
  existing TikTok manual lane. See `docs/SOCIAL_CONNECTORS.md` "Own-Channel Posting" section.

Health Service
- Owner: TBD
- Purpose: Centralized health endpoints and registration

Auth
- Owner: TBD
- Purpose: Authentication (passwordless/passkeys, OAuth, magic links)

AI
- Owner: TBD
- Purpose: Embeddings, models orchestration, RAG pipelines

Documents
- Owner: TBD
- Purpose: Document generation, templates, rendering

Storage
- Owner: TBD
- Purpose: Object storage abstraction

Notifications
- Owner: TBD
- Purpose: Notification dispatch (email, SMS, in-app)

Notes
- Each service must add a README under its directory describing the above fields in detail.
