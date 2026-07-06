# govOS v2 — repo README additions

This repository includes govOS v2 service and frontend integration scaffolds.

Key points
- Deployment infrastructure is intentionally frozen for Phase 1 (releases + rollback + health service + Tailscale integration).
- v2 contract is published at `/home/runner/work/12sgi-king/12sgi-king/docs/api/v2-openapi.yaml`.
- Local integration guide is available at `/home/runner/work/12sgi-king/12sgi-king/docs/GOVOS_V2_LOCAL_DEV.md`.
- Do NOT commit secrets or internal hostnames. Use environment and secret management at deployment time.

Getting started
- Start backend services in `/services/*` using each service README.
- Start static frontend app scaffolds in `/apps/*/public`.
- Follow the Sprint roadmap in `docs/GOVOS_V2_ROADMAP.md`.
