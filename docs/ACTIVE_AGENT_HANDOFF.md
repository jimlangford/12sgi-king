# Active Agent Handoff

Updated: 2026-07-18 HST
Owner: Codex
Status: public-ready

## Current Release Work

- Public branch: `agent/complete-studio-auth-release`
- Public PR: `#380 Complete Studio auth and release integration`
- Public scope: Google owner auth, magic email, Studio asset readiness, shared Neo4j projections,
  authenticated project mutations, local GPU routing, and multi-gate workboard approvals.
- Private Studio main: `0f5d526 integrate Studio SAGE civic and shared-agent release work`
- Private continuity: `AGENTS.md`, `config/ai_shared_work_state.json`, system awareness, and local-AI
  request context now make the active owner request mandatory reading for Claude, Codex, and local AI.

## Validation So Far

- Private Studio: 62 tests pass; changed Python compiles; changed JSON parses.
- Public focused release suite: 182 tests plus 5 subtests pass after integration with `main`.
- Public full suite: 256 tests plus 13 subtests pass.
- Docker Compose plans validate for govOS v2 and the standalone Studio asset service.
- The current Element Lotus WordPress bundle is regenerated and parity-checked against the public shell.
- All eight GitHub checks pass on the reviewed release head: V2 and Studio tests, Python/YAML/shell
  lint, accessibility, secret scan, and path labeling.

## Coordination Rule

Codex owns this integration until this file says `Status: shipped` or records a blocker. Other agents
may inspect and report findings, but should not rewrite the listed release surfaces or push this branch
without first recording a coordinated handoff.

## Next

Merge PR #380, record its merge commit in the shared private Studio state and dispatch log, then run
the environment-gated paired-aspect episode canary before declaring the complete Studio beta shipped.

## Parallel Deployment Maintenance — 2026-11-17

- Agent: Copilot; branch: `copilot/fix-12sgi-king`.
- Scope: PRIVATE/BRIDGE Tailscale deployment configuration, host cleanup, local CI,
  recovery, health verification, and focused regression tests. No auth, Studio application,
  creative/output approval, public publishing, or Neo4j data changes.
- Coordination: existing release ownership above remains intact; deployment configuration
  overlaps are recorded in `DISPATCH_LOG.md` for owner review before merge.
- Changed: loopback publishing; host nginx routes (including Studio project/media APIs and
  private native owner routes); signed CI with local mode; safe stale-artifact/PID cleanup;
  bounded recovery; Studio readiness; read-only host preflight/verification and runbook.
- VERIFY: 61 focused/existing tests pass, including live nginx and static-path isolation tests.
  Python compilation, v2/standalone-Neo4j Compose models, nginx configuration, and PowerShell
  parsing pass. Secret scan clean; initial CodeQL Python analysis found no alerts.
- Limits: broader tests require FastAPI and generated site artifacts absent here. No host
  cleanup, DNS/TLS/ACL change, RAM observation, or live graph count was performed.
- Next: owner/release agent reviews overlap before merge; follow `COMPLETE_INDEPENDENCE.md`
  on king-server, verify native owner routes and separate Studio startup, and export
  `DEPLOYMENT_HOSTNAME=12sgi.com` only when intentionally verifying custom-domain cutover.
