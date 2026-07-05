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
