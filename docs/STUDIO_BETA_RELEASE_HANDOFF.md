# Studio Beta Release Handoff

## Public Integration Scope

This branch completes the public govOS integration boundary for the local Studio release:

- standalone Studio asset service on loopback port 8108
- tenant/style/character render provenance in SQLite
- scoped Studio asset and clip-learning projections in Neo4j
- crosswalk, assignment, asset, clip recommendation, health, and readiness APIs
- owner-scoped auth enforcement for graph sync and reindex maintenance routes when enabled
- read-only vault mounts and an independent Docker Compose project
- Studio asset regression tests in GitHub Actions
- `.env.v2` excluded from Git

The service is read-mostly. Its maintenance POST routes update only private SQLite/Neo4j projections;
the mounted Studio vault remains read-only.

## Private Local Studio Snapshot

The application and workflow handoff is intentionally not published to this public repository. It is a
separate local Git repository at:

`C:\Users\12sgi\Documents\Codex\2026-07-11\github-plugin-github-openai-curated-remote\work\studio-release-stage`

Reviewed snapshot commit: `03346b3 release: snapshot reviewed Studio beta handoff`

That snapshot includes the Studio/storyboard UI, LTX/Wan and lip-sync workflows, full-script timing,
character bibles, tenant/style render assignments, clip learning, resource governance, WordPress member
pages, 3D/Reallusion/Bambu planners, social staging, and tests. It has no remote by design.

## Routing Contract

Local AI is the default. `local_ai.ask(..., prefer="local")` tries the on-device Ollama ladder before
Hugging Face or configured cloud AI. Private lanes never leave the device. External AI and Comfy Cloud
are fallback or explicit owner-selected routes, not automatic first choices.

## Verification

- private Studio snapshot: 45 tests pass
- govOS contracts: 72 tests pass
- govOS integration: 10 tests pass
- govOS hardening: 27 tests pass
- Studio asset service: 8 tests pass
- Docker Compose configuration validates

## Environment-Gated Finish Checks

1. Render one approved full episode through landscape and portrait outputs, then inspect voice, lip sync,
   identity continuity, timing, archive receipts, and editorial exports.
2. Keep external AI and Comfy Cloud disabled for that canary unless local execution fails or the owner
   explicitly selects cloud.
3. When the OAuth/auth service is reachable from the container, inject `INTERNAL_SERVICE_TOKEN`, set
   `STUDIO_ASSETS_REQUIRE_AUTH=1`, and smoke-test all three maintenance POST routes.
4. Re-run the WordPress account-page check after any plugin or permalink change.
