# ARCHITECTURE.md

This document is the canonical engineering reference for the deployment and runtime architecture for 12SGI.

Overview
--------
The platform is deployed from GitHub Actions using a releases + atomic symlink pattern. Each release is
written to DEPLOY_PATH/releases/<timestamp> and the live site is served from DEPLOY_PATH/current which is a
symlink to a specific release. The deploy workflow writes release metadata (release.json) which is used by
operational tooling and the health/dashboard service.

Key components
--------------
- Reverse proxy (Nginx/Caddy): public-facing gateway which terminates TLS and reverse-proxies selected paths to
  internal services running on the Tailscale mesh.
- Tailscale mesh (Tailnet): private network connecting internal services (govOS, Tenant Assistant, Element LOTUS, Civic Signal, etc.)
- Health service (FastAPI): provides /api/v1/live, /api/v1/ready, /api/v1/health and an internal /admin/status dashboard.
- Deployment automation: GitHub Actions workflows that rsync releases, run remote build hooks, atomically update symlink, and allow rollback via workflow_dispatch.

Reverse proxy
-------------
- The Nginx gateway receives public traffic and proxies requests to internal services over Tailscale.
- Example mapping: /surfaceA/ → TS_IP:8782
- TLS is terminated at the gateway; backend connections over Tailnet may be plain HTTP for simplicity.

Tailscale topology
------------------
- Tailnet nodes: homepage gateway, govOS, Tenant Assistant, Element LOTUS, Civic Signal, AI services.
- Use MagicDNS + ACLs. The homepage gateway should be allowed to connect to the service nodes on required ports (e.g., 8782).
- Do NOT commit Tailscale internal IPs into git. Use runtime configuration (env vars or secrets).

Health service
--------------
- Implemented in services/health using FastAPI (services/health/app).
- Endpoints:
  - /api/v1/live : is the service process running
  - /api/v1/ready: readiness checks (critical dependencies like surfaces)
  - /api/v1/health: structured dependency checks and release metadata
  - /admin/status: operational dashboard (protected by admin rules)
- Admin access policy:
  1. Allow listed admin CIDRs (ADMIN_ALLOWED_IPS) — preferred
  2. Or require HTTP Basic Auth (ADMIN_BASIC_USER / ADMIN_BASIC_PASS)
  3. If neither is configured, /admin/status is disabled and returns 403

Rollback flow
-------------
- Releases are kept in releases/ and the deploy workflow keeps the last N releases (default 3).
- A rollback workflow switches the DEPLOY_PATH/current symlink to the previous release atomically.
- For DB or content rollbacks, restore from backups or use CMS revision histories.

Release process
---------------
- Feature branches are created for integration and testing (automation/project-setup is the current integration branch).
- Draft PRs allow reviewers to run deploys against staging and exercise the health checks before merging.
- release.json metadata is written at deploy time to the release folder and contains: branch, commit, version, deployed_at, deployed_by.

Future govOS modules (module registry placeholders)
--------------------------------------------------
- govOS
- Tenant Assistant
- Civic Signal
- Element LOTUS
- Transparency Engine
- AI Services
- Public API
- Authentication
- Document Generator

Each module should:
- Declare the ports and routes it exposes
- Register health check hooks with the central Health service
- Use the internal Tailnet for private communication

Operational runbook (summary)
-----------------------------
- To test integration changes: create a Draft PR against automation/project-setup and run the deploy workflow with POST_DEPLOY_BUILD=true.
- If a deploy fails, use the rollback workflow to restore the previous release.
- For major changes involving DB schema, take backups and use maintenance mode.

