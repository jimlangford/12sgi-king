# Studio Beta Release Handoff

## Public Integration Scope

This branch completes the public govOS integration boundary for the local Studio release:

- standalone Studio asset service on loopback port 8108
- tenant/style/character render provenance in SQLite
- atomic label-swap Studio asset and clip-learning projections in the shared govOS Neo4j; failed
  staging leaves the previous complete projection live and retries heal forward from JSON
- crosswalk, assignment, asset, clip recommendation, health, and readiness APIs
- owner-scoped auth enforcement for every project and maintenance mutation, enabled by default in Compose
- read-only vault mounts and an independent Docker Compose project
- Studio asset regression tests in GitHub Actions
- `.env.v2` excluded from Git
- routine Studio index/startup health logged as receipts instead of queued workboard jobs

The service is read-mostly. Its maintenance POST routes update only private SQLite/Neo4j projections;
the mounted Studio vault remains read-only.

## Private Local Studio Snapshot

The application and workflow handoff is intentionally not published to this public repository. It is a
separate local Git repository at:

`C:\Users\12sgi\Documents\Claude\Projects\Video System elementLOTUS`

Reviewed private main commit: `0f5d526 integrate Studio SAGE civic and shared-agent release work`

That snapshot includes the Studio/storyboard UI, LTX/Wan and lip-sync workflows, full-script timing,
character bibles, tenant/style render assignments, clip learning, resource governance, WordPress member
pages, 3D/Reallusion/Bambu planners, social staging, and tests. It is mirrored only to the owner's
local private Git mirror; no private Studio source is published by this repository.

## Routing Contract

Local AI is the default. `local_ai.ask(..., prefer="local")` tries the on-device Ollama ladder before
Hugging Face or configured cloud AI. Private lanes never leave the device. External AI and Comfy Cloud
are fallback or explicit owner-selected routes, not automatic first choices.

## Verification

- private Studio main: 62 tests pass
- govOS contracts: 72 tests pass
- govOS integration: 10 tests pass
- govOS hardening: 27 tests pass
- Studio asset/auth/GPU focused release suite: 149 tests + 3 subtests pass before final main merge
- Docker Compose configuration validates

## Environment-Gated Finish Checks

1. Render one approved full episode through landscape and portrait outputs, then inspect voice, lip sync,
   identity continuity, timing, archive receipts, and editorial exports.
2. Keep external AI and Comfy Cloud disabled for that canary unless local execution fails or the owner
   explicitly selects cloud.
3. Keep the Studio and auth services on the same `INTERNAL_SERVICE_TOKEN`; smoke-test missing,
   invalid, and owner-scoped bearer behavior on every mutation after an auth configuration change.
4. Re-run the WordPress account-page check after any plugin or permalink change.
