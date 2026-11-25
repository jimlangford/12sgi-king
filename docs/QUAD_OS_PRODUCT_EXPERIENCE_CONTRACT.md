# QUAD OS Product Experience and Integration Contract

This contract applies lessons from the ElementLOTUS WordPress rebuild and repository review to every QUAD OS surface: civic, creative, member, owner, local, and public. It complements `QUAD_OS_MASTER_ARCHITECTURE.md` and `CANON.md`.

## Product outcome

People should complete their real task without learning QUAD OS internals. Residents find civic records; creators manage creative work; members reach their tools; the owner sees approvals and system health. Preserve backend capabilities while making the paths understandable.

## Experience and navigation

- Organize pages around user tasks, roles, and devices, not service names, ports, models, or implementation teams.
- Keep public, member, and owner navigation distinct. Links guide users; authorization must still be enforced by the backend.
- Treat navigation as a product contract: links resolve to canonical routes; important destinations are reachable; direct entry, refresh, back/forward, and unknown routes behave predictably.
- Preserve route ownership. ElementLOTUS/WordPress and civic 12sgi.com are separate surfaces; changes must not silently redirect, shadow, or break the other site.
- Use semantic HTML, clear heading structure, landmarks, descriptive links, keyboard access, visible focus, accessible names, and responsive layouts. No pointer-only controls.
- Keep labels and interaction patterns consistent. Do not duplicate theme chrome supplied by the host platform.

## Full-stack behavior

- Trace each control end to end: user action → frontend state → authorized API or public route → owning service/data → visible success, empty, loading, and error states. A styled control without a real outcome is incomplete.
- Declare module owner, API/routes, authorization, data source and retention, health/readiness, and deployment footprint. Version public contracts.
- Keep one canonical source per page or data domain. Generated output is an artifact; edit source and regenerate deterministically.
- Keep public HTML free of private hosts, credentials, owner data, internal service calls, and Tailscale fallbacks. Public pages must render without the private operating plane.
- Fail clearly and safely when an API, model, or integration is unavailable. Distinguish stale/unavailable from verified data; never fabricate success.
- Preserve civic provenance and tenant boundaries from verified identity through query, storage, and rendered response.

## Local-first AI and infrastructure

- Local AI, Ollama, local data, and local services are first-class operating paths. Core work should not require paid cloud AI when local capabilities can do it.
- Register tools/models with clear inputs, outputs, permissions, availability, and fallback. The agent must discover tools from the same runtime in which it executes.
- Treat external AI and publishing services as bounded bridges. Record what was shared and whether delivery was confirmed. A repository feed is not proof that a live external agent received it.
- Use typed, versioned, provenance-bearing events and correlation IDs. Long-running jobs need durable status, retries, idempotency, and understandable user-facing explanations.
- Verify health and dependency visibility inside the deployed/container runtime. Passing unit tests alone does not establish runtime readiness, disconnected operation, or reboot recovery.

## Integration and release discipline

- Map existing connectors before adding one. Determine whether it reads, previews, writes, creates, or only stores credentials. Record its exact source, target, auth, ownership, secret store, and rollback path.
- Use least-privilege credentials. Never print or commit them or place them in public output/AI feeds. Report presence without exposing values.
- Make publishing/deployment reviewable and dry-run by default. Match targets by stable ID or exact intended identity; surface unmatched or ambiguous targets instead of silently overwriting or creating.
- Separate source readiness, generated-package readiness, connector readiness, authenticated delivery, and live verification. Never call a bundle or dry run published.
- Stage from source to preview to approved publish. Verify structure, links, interactions, mobile/desktop, signed-out access, redirects, critical routes, and rendered production pages. Preserve rollback.
- Keep the change feed, active handoff, and delivery claims aligned: say what changed, what was verified, what remains unverified, and the next action. Do not claim another AI was notified without confirmed delivery.

## Completion standard

A feature is ready when its intended user can find it, understand it, finish the task, recover from normal failures, and trust the boundary and status. Verify source, built artifact, runtime integration, and public/private routes separately; record evidence and gaps.
