# Active Agent Handoff

Updated: 2026-07-18 HST
Owner: Codex
Status: integrating

## Current Release Work

- Public branch: `agent/complete-studio-auth-release`
- Public scope: Google owner auth, magic email, Studio asset readiness, shared Neo4j projections,
  authenticated project mutations, local GPU routing, and multi-gate workboard approvals.
- Private Studio main: `0f5d526 integrate Studio SAGE civic and shared-agent release work`
- Private continuity: `AGENTS.md`, `config/ai_shared_work_state.json`, system awareness, and local-AI
  request context now make the active owner request mandatory reading for Claude, Codex, and local AI.

## Validation So Far

- Private Studio: 62 tests pass; changed Python compiles; changed JSON parses.
- Public focused release suite: 149 tests plus 3 subtests pass before final integration with `main`.
- Docker Compose plans validate for govOS v2 and the standalone Studio asset service.

## Coordination Rule

Codex owns this integration until this file says `Status: shipped` or records a blocker. Other agents
may inspect and report findings, but should not rewrite the listed release surfaces or push this branch
without first recording a coordinated handoff.

## Next

Merge current `origin/main`, rerun the full test and Compose checks, push a fresh PR, wait for required
checks, merge, then update this file with the public merge commit and final evidence.
