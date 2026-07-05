# govOS v2 — repo README additions

This repository now includes the govOS v2 skeleton branch (feature/govos-v2-foundation) and the integration/infrastructure work on automation/project-setup.

Key points
- Deployment infrastructure is intentionally frozen for Phase 1 (releases + rollback + health service + Tailscale integration).
- Development should proceed on feature/govos-v2-foundation (base: automation/project-setup).
- Do NOT commit secrets or internal hostnames. Use environment and secret management at deployment time.

Getting started
- Create feature branches from feature/govos-v2-foundation for specific workstreams (auth, dashboard, tenant assistant).
- Follow the Sprint roadmap in docs/GOVOS_V2_ROADMAP.md
