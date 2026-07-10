# QUAD OS Master Architecture

This document is the canonical architecture reference for QUAD OS (the private operating platform underlying govOS and Element LOTUS). All new services, modules, and high-level design decisions should reference this document.

1. Platform vision
------------------
QUAD OS is a modular civic operating system that separates the public presentation layer (WordPress) from the private operating layer (QUAD OS). The platform provides secure, auditable workflows, AI-assisted guidance, and a repeatable deployment model for civic services.

2. Public vs. private boundaries
--------------------------------
- Public layer: WordPress — public pages, SEO, media, marketing, public posts. WordPress is the canonical public interface.
- Private layer: QUAD OS — internal APIs, case management, AI services, event bus, worker queues, health endpoints. All private services run on the internal Tailnet and behind authenticated reverse proxies.
- Rule: Public visitors must never directly access private endpoints.

3. Module registry
------------------
Each module MUST declare:
- Name, owner, and contact
- API surface (public and internal endpoints)
- Health checks (/ready, /live)
- Data ownership and retention policy
- Deployment footprint (ports, resource needs)

Planned modules (phase 2):
- govOS (core app)
- Tenant Assistant
- Civic Signal
- Element LOTUS
- Transparency Engine
- AI Services
- Public API
- Authentication
- Document Generator

4. Service registry
-------------------
- Centralized service discovery via DNS + Tailnet MagicDNS for internal calls
- Each service exposes /api/v1/health, /api/v1/ready, /api/v1/live
- Services register with the health service and include metadata (version, release id)

5. Event model
--------------
- Adopt an append-only event model for cross-service communication (Event Bus)
- Events are typed, versioned, and include provenance and correlation ids
- Store event audit trail in the Audit Log service
- Use durable queues for long-running jobs and retries

6. Deployment topology
----------------------
- GitHub Actions builds artifacts and produces releases under releases/<timestamp>
- Deploys use atomic symlink swap: releases/<id> → current
- Health checks gate symlink swap (post-deploy checks fail the swap)
- Tailscale used for private mesh (no internal IPs committed to git)
- Reverse proxy (Nginx/Caddy) at the public edge; only proxy public routes to internal services

7. Security model
-----------------
- Passwordless-first authentication (Passkeys + OAuth + Magic Links)
- Short-lived tokens, rotating keys, JWKS for public keys
- RBAC/permissions service for fine-grained access control
- Audit log for all administrative actions
- Secrets stored in repo secrets or external secret manager (never in repo)
- Admin pages protected by IP allowlist or basic auth behind the reverse proxy

8. Data ownership
-----------------
- Define canonical owner for each data domain (cases, documents, user profiles, logs)
- Backup and retention policies documented per domain
- Sensitive PII encrypted at rest and in transit; minimize PII in logs

9. Coding standards
-------------------
- Tests and lint required for every PR
- Accessibility (WCAG 2.2 AA) reviews for UI changes
- Mobile-first responsive design
- Use TypeScript/Next.js for frontend, FastAPI for backend services
- No secrets in commits; run secret-scan CI on PRs

10. API versioning
------------------
- All public APIs must be versioned: /api/v1/... and include compatibility guarantees
- Internal-only APIs may choose independent versioning but must be documented in the service registry

11. Branch strategy
-------------------
- main: production-ready (do not alter without reviews and CI passing)
- automation/project-setup: deployment & infra integration branch (frozen for Phase 1)
- feature/*: feature branches; branch off the reviewed integration branch as appropriate
- release/*: release preparation branches

12. CI/CD strategy
------------------
- Workflows default to safe behaviors (dry-run by default for mutating actions)
- Least-privilege permissions in workflows and job-level permission scoping
- All mutation workflows must be reviewable and run with secrets stored in repo secrets
- Deploys gated by health checks and staged promotion (staging → canary → prod if needed)

13. Release lifecycle
---------------------
- Releases are created by Actions and include release.json metadata (branch, commit, version, deployed_at)
- Release notes generation is draft-first and must be reviewable before publish
- Rollbacks use the symlink swap to the previous release and trigger a post-rollback hook if configured

14. Long-term roadmap
---------------------
- Phase 2: CI stability, WordPress public layer completion, QUAD OS core services
- Phase 3: govOS apps, Element LOTUS integration, AI RAG and local models as appropriate
- Phase 4+: scale, multi-tenant hardening, federated deployments

15. Governance
--------------
- All major architecture changes must be documented here and reviewed by platform leads
- Each module must register a maintainer and include an OWNERS entry or CODEOWNERS rule
- See docs/adr/ADR-006-Ordinance-Level-Charter-Crosswalk.md — the Charter Crosswalk module
  (watchers/charter_crosswalk.py) now carries ordinance-level detail for tenants with a sourced
  per-ordinance corpus (Maui only, today); CANON.md's "Apex Spine" section documents the model so it is
  extended (never forked or fabricated) as more tenants build their own corpora.

16. Completion governance rubric
--------------------------------
- Platform completion checkpoints and latest execution status are tracked in:
  `/home/runner/work/12sgi-king/12sgi-king/docs/QUAD_OS_COMPLETION_RUBRIC.md`
- Update that rubric checkpoint-by-checkpoint as operational evidence changes (especially deploy-v2 dry-run/restart evidence).

Appendix: Implementation checklist (first actions)
- [ ] Verify label-by-path workflow passes for PR #313 (dry-run then apply)
- [ ] Audit all workflows for least-privilege permissions and deprecated actions
- [ ] Finalize wp-publish.yml: draft-first, Python/jq payload, non-2xx fail handling, Jetpack fallback guarded
- [ ] Create Auth service scaffold and API spec
- [ ] Create RBAC/Permissions service scaffold
- [ ] Implement centralized Event Bus and Audit Log scaffolds

