# Active Agent Handoff

## Issue #403 recovery and explainer-sharing integration — 2026-11-27

- BRANCH: `codex/issue-403-recovery-sharing`, merged with current `main`; PR #410 is review-only,
  with no deployment, public publishing, social queue mutation, or merge.
- INSPECTED: issue #403, merged PR #404, the clean self-hosted runner checkout, the separate
  modified Documents checkout, Docker/AI Gateway/King Bridge/Workboard, Ollama, Neo4j, Tailscale
  Serve, the private NAGA phone-dispatch surface, and the existing social approval workers.
- CHANGED: `watchers/agenda_explainer.py` now gives each sourced agenda card a stable
  `https://12sgi.com/agenda_explainer.html?card=...` URL and mounts the credential-free
  `assets/sgi-share.js` manual sharing controls while preserving the existing image-share fallback.
  `build_site.py` now ships that asset into `site/assets/`. Focused regression coverage is in
  `tests/test_agenda_explainer_sharing.py`.
- LOCAL RECOVERY: Docker's v2 stack is running from the clean runner checkout and aggregate
  `/api/v1/ready` reports ready. The AI Gateway image contains 123 registry tools and its Claude
  bridge URL/token contract is configured. A non-elevated logon task named
  `QUAD OS Claude Read-Only Bridge` now starts the loopback-only authenticated adapter. A real
  stop/task-start test returned task result 0; unauthenticated health returned 401 and authenticated
  host/container health returned 200.
- SECURITY: removed Tailscale TCP forwards for Neo4j ports 7474 and 7687. Docker continues to bind
  them only to `127.0.0.1`; the healthy graph contains 22,695 nodes. Neo4j intentionally has auth
  disabled for its local consumers, so loopback-only exposure is the enforced boundary. The
  `govOS Agenda Reels (auto-publish)` Windows task was disabled while the engineering release gate
  is active; re-enabling that named task is the rollback after Owner release approval.
- VERIFY: 3 focused Python tests, 2 Node share tests, Python compilation, and `git diff --check`
  passed. Workboard board-api health returned alive and no pending approvals were present. No social
  connector is configured and no post was attempted.
- OLLAMA RECOVERY: the first model loads stalled. With no loaded model, no Workboard approvals, and
  free GPU capacity, one bounded Ollama application restart was performed. `qwen3:1.7b` then returned
  `KING_READY`, and the active `king-jrcsl` persona returned `KING_PERSONA_READY`; both were unloaded
  after the probe. This verifies real inference rather than version/catalog reachability alone.
- BLOCKERS: authenticated Claude reached the adapter but returned `Credit balance is too low`.
  AI Gateway-to-Claude invocation still needs a real active Owner JWT; do not mint a synthetic Owner
  session to bypass that claim boundary. Phone-side Tailscale/NAGA submission still needs validation
  from the actual owner device.
- NEXT: complete the real Owner-authenticated Gateway review/status test, then perform phone/mobile
  and reboot verification. Do not re-enable automatic publishing or deploy the explainer change until
  existing release gates pass and the Owner approves.
## Education and local AI coordination review — 2026-11-27

- OWNER REQUEST: create an education system review and verify that the AI participants coordinate through the owner's local system.
- REVIEW: `docs/EDUCATION_AI_SYSTEM_REVIEW.md` records the education manifest, local runtime, agent coordination paths, safety boundaries, and remaining gates.
- RUNTIME: live source fast-forwarded to GitHub `main` at `4142a4fd`; PR #405 education tests pass there. Docker aggregate health is green. The authenticated read-only Claude bridge is running loopback-only and is reachable from AI Gateway.
- LOCAL AI: Ollama completed a small-model response, but `king-civic` did not finish loading within 180 seconds during active GPU work. Treat education persona inference as degraded until a later bounded response succeeds.
- PRESERVED: no Claude review job, graph write, film approval, student account, deployment, or publication occurred. The current owner instruction supersedes the earlier request to keep the bridge stopped only for this authenticated, read-only local coordination use; startup persistence was not changed.
- NEXT: retest `king-civic` when render capacity is free, add a post-reboot coordination check, and obtain educator/film approvals before curriculum assignments.

## GitHub-only manual explainer sharing — 2026-11-27

- OWNER REQUEST: Integrate civic explainer sharing using GitHub while preserving local-first authority and the existing engineering-first release gate.
- CHANGED ON FEATURE BRANCH ONLY: `assets/sgi-share.js`, `tests/test_sgi_share.cjs`, `docs/EXPLAINER_SHARE_INTEGRATION.md`. Safe public URL allowlist, native share, clipboard and manual platform share intents. Does not auto-post or interact with private routes.
- SOURCE BOUNDARY: `/status/explainers.html` was not found in the tracked repository; the local canonical generator must be identified before any live dashboard integration. No runtime, Docker, WordPress, server or social account access was exercised.
- OWNER CLAUDE BOUNDARY: 2026-11-27 Claude change-feed record explicitly says the owner requested the Claude bridge and QUAD OS startup shortcuts stay disabled. Do not recreate or restart them without renewed explicit owner direction.
- VERIFY: source-only review; `node --test tests/test_sgi_share.cjs` and live mobile acceptance still required. No deployment, auto-post, or merge performed.
- NEXT: review draft PR, run focused tests, identify local dashboard generator, integrate manually with public canonical URLs, then validate staged publishing with existing approval workflows.

## Windows startup and Docker recovery — 2026-11-25

- CHANGED: corrected `startup_system.py` to launch the installed Docker Desktop
  executable, avoid `wsl --shutdown`, use the current checkout and `.env.v2`,
  and start the v2 Compose stack. Added a hidden log-writing launcher at
  `tools/startup_system_start.ps1`.
- STARTUP: added user startup entries for Claude, Codex/ChatGPT, GitHub Desktop,
  GitHub Copilot, QUAD OS services, and the Local AI Claude bridge. The QUAD OS
  startup file launches Docker Desktop and waits for its daemon before Compose.
- VERIFY: launcher syntax and `startup_system.py` compilation passed. Docker
  Desktop was launched but its daemon remained unavailable after 60 seconds;
  the Docker service was stopped. An elevated launch was canceled, so the stack
  is not yet running. The system restart is being used to activate the login
  startup entries; verify Docker and Gateway after Windows returns.

## Local AI to Claude Code bridge — 2026-11-25

- OWNER AUTHORIZATION: James approved building a bridge for Local AI to trigger
  Claude Code.
- CHANGED: added the authenticated host-side `tools/claude_code_bridge.py`,
  Windows start/stop helper, AI Gateway invocation for `claude_code.review`
  and `claude_code.status`, canonical tool entries, Owner profile access, and
  Local AI teaching instructions.
- BOUNDARY: the bridge accepts an explicit Owner instruction and uses the
  existing internal service token. Claude Code runs only in read-only plan
  mode with `Read`, `Grep`, and `Glob`; there is no shell, editing, commit,
  push, deployment, or publish access.
- RUNTIME: verify the service startup and AI Gateway-to-host connectivity
  before claiming Local AI can trigger Claude end to end. Host bridge is
  running and authenticated health returned ready; a request without the Owner
  instruction flag was rejected. Docker Desktop service is stopped and could
  not be opened by this session, so AI Gateway integration is not running.
  Four Ollama personas were rebuilt with the tool instructions; all four
  inference checks timed out. No Claude review job was launched.
- VERIFY: Python compilation, registry/profile JSON parsing, PowerShell parser,
  and Docker Compose config parsing passed. Installed Ollama model templates
  contain the new review workflow. Docker service state prevented runtime
  verification from Local AI through AI Gateway.
- NEXT: start Docker Desktop with an authorized user session, then recreate
  `ai-gateway` using `docker compose --env-file .env.v2 -f docker-compose.v2.yml
  up -d --build ai-gateway`; verify `claude_code.review` queues a job and
  `claude_code.status` returns it. Do not claim end-to-end Local AI dispatch
  until that succeeds. Never echo or log `.env.v2` credentials.

## Local AI WordPress publisher and self-heal — 2026-11-25

- CHANGED: added `services/elementlotus_publisher.py` and Owner-authenticated
  preview, health, publish, and recover routes in `v2/app/main.py`. Added the
  operating contract to `docs/WORDPRESS_PUBLIC_LAYER.md`.
- SCOPE: only the eight existing ElementLOTUS pages in the curated manifest;
  strict `elementlotus.com` host allowlist; no 12sgi.com route writes. Each
  page receives a local backup and journal record before modification.
- SELF-HEAL: transient responses use bounded retries. Failed runs attempt
  compare-before-restore recovery; pages changed remotely after publishing are
  skipped and surfaced for owner review. Navigation and global CSS are not yet
  part of the publisher.
- VERIFY: Python compilation passed and the local preview enumerated all eight
  expected pages. Health currently reports no WordPress connector credential,
  so no live publish has occurred. Changes remain local and uncommitted.
- NEXT: configure the WordPress Application Password for ElementLOTUS.com,
  review the eight-page preview, then publish and verify live pages. Claude and
  other external agents must read this handoff/feed after it is pushed; direct
  Claude chat delivery is not configured in this environment.

## QUAD OS product experience contract — 2026-11-25

- CHANGED: added `docs/QUAD_OS_PRODUCT_EXPERIENCE_CONTRACT.md` and linked it
  from the master architecture. It applies the ElementLOTUS WordPress review
  lessons across civic, creative, member, owner, local, and public surfaces:
  task-based navigation, end-to-end interaction behavior, explicit boundaries,
  local AI independence, connector capability checks, dry-run publishing, and
  evidence-based release readiness.
- LOCAL AI: embedded these rules in `tools/teach_local_ai.py` and ran the
  teaching workflow. Ollama reported all four configured personas updated:
  king-jrcsl, king-civic, king-workboard, and king-server. Their generated
  Modelfiles remain local because they include owner-specific prompt material.
- VERIFY: prompt Python compilation and scoped `git diff --check` passed.
  The teaching workflow's prompt checks completed with exit code 0. No website,
  live WordPress content, DNS, or external AI chat was changed or notified.
- NEXT: external agents can read the contract after the scoped change feed and
  documentation are pushed. A later product implementation should use the
  contract while preserving the separate 12sgi.com civic routes.
## Engineering first release gate — 2026-11-25

- OWNER DIRECTION: pause production publishing and deployment until engineering is complete.
- CHANGED: the AI Gateway now supports a trusted executor URL contract and returns successful results only from that executor. Calls fail closed if it is not configured. Owner approval dispatches the stored, validated arguments before recording execution.
- WORDPRESS: added Studio to primary navigation, split Games and SAGE destinations, and generated the Contact page with editable Jetpack contact fields. The builder package was regenerated.
- VERIFY: `tests/v2/test_ai_gateway_execution_boundary.py` and `tests/v2/test_ai_gateway_policy.py` pass (21 tests); AI Gateway compiles. WordPress builder tests pass (8 tests, 21 subtests).
- BLOCKED FOR PRODUCTION: no trusted executor implementation or URL is configured; dashboard still presents a curated surface launcher rather than all 121 tools and approval/job history; seven of eight WordPress pages still use source HTML inside a single Group rather than reusable native blocks; WordPress credentials/live visual and form-submission verification are unavailable; no private deployment or offline-independence test was performed.
- DELIVERY: no deployment, WordPress publishing, push, or external provider notification. The AI change feed is the shared handoff; active Claude/GitHub AI sessions are not directly notified by it.

## Local AI primary dashboard — 2026-11-25

- Branch: `codex/local-ai-dashboard`, based on the published AI change-broadcast commit `c3027d0`; local implementation only, no deployment or push.
- OWNER DIRECTION: the Local AI is the main QUAD OS authority and needs one dashboard with all functions. Paid/cloud systems remain optional bridges rather than runtime owners.
- CHANGED: added `go/local-ai.html` and the machine-readable `go/local-ai-functions.json`. The registry exposes 33 functions under Local AI, Work, Civic, Studio, Corporate, Knowledge, and System, with `PUBLIC`/`PRIVATE`/`BRIDGE` boundaries and `local-primary`/`owner-gated`/`optional-bridge` authority labels. `/go/` now opens the Local AI dashboard, while `go.html` keeps the consolidated launcher and adds a primary dashboard door.
- SAFETY: the dashboard performs read-only health probes and routes actions to their existing authenticated or owner-gated surfaces. It embeds no service token, paid-AI API, Stripe checkout, or external AI dependency. The private page is `noindex,nofollow`; public build purge behavior remains the governing boundary.
- VERIFY: four dashboard contract tests pass; HTML and JSON parse; `git diff --check` passes. Browser QA verified the responsive page, 33 function cards, search (`docker` narrowed to one function), and optional-bridge filter. Live probes correctly fail closed as `Not confirmed` under the source-only preview. An existing `tests.test_public_frontdoor` workflow expectation fails independently because the current local-first publish workflow no longer contains the older quoted `education.html` path. Two redirected full-site builds were stopped after they continued in the background without reaching final output; no production or checked-in site tree was touched.
- NEXT: review the registry names/routes with the owner, then integrate it into the private deployment. Before enabling direct dashboard mutations, require verified Owner claims rather than a browser-held internal service token.

## Cross-agent change broadcast — 2026-11-25

- CHANGED: added `docs/AI_CHANGE_BROADCAST.md`, the tracked append-only
  `docs/AI_CHANGE_FEED.jsonl`, and `tools/announce_ai_change.py`. `AGENTS.md`
  now requires agents to read the feed at session start and record material
  changes with boundary, audience, changed paths, and evidence.
- DELIVERY: the shared feed is published on the dedicated
  `codex/ai-change-broadcast` branch for GitHub-connected agents to read. No
  direct provider chat connector is configured, so a branch push does not
  actively notify a live Claude, Codex, or Copilot thread.
- PRESERVED: private owner data and sensitive paths are rejected from the
  shared feed; no external inference, GitHub comment, or deployment was
  performed. The branch contains only the broadcast coordination files listed
  above.
- LOCAL AI: `tools/teach_local_ai.py` now gives the Ollama models the same
  session-start and after-change feed workflow.
- VERIFY: `python -m unittest tests.test_ai_change_broadcast -v` passed all 4;
  `python -m py_compile tools/announce_ai_change.py
  tests/test_ai_change_broadcast.py` passed; scoped `git diff --check` passed.
  Whole-tree `git diff --check` also surfaced pre-existing generated-site
  whitespace and line-ending warnings outside this change.
- NEXT: review the broadcast branch; add provider delivery connectors only
  after recipient scope and authorization are clear.

## ElementLOTUS WordPress navigation rebuild — 2026-11-25

- SCOPE: ElementLOTUS.com WordPress shell only; 12sgi.com civic routes remain
  separate and intact. The public WordPress REST API currently lists 491 pages;
  this package changes eight curated landing pages and leaves archive/content
  pages untouched.
- INSPECTED: current WordPress navigation and its destinations, local
  `element_lotus_public/` sources, the WordPress bundle generator, and public
  civic/game destinations on 12sgi.com.
- CHANGED: rebuilt the eight-page local shell, added consistent grouped
  navigation and installation instructions, made the partnership and studio
  pages part of the WordPress bundle, removed the civic page's private API/
  Tailscale fallback, and excluded duplicate theme navigation from fragments.
- OUTPUT: `content/wordpress/element_lotus/` is a review package only. The
  builder does not update WordPress. No live WordPress page, global menu, or
  public post was changed.
- PRESERVED: WordPress archive routes and the 12sgi.com civic site. No
  application owner paths, credentials, private service hosts, or local API
  calls are included in the WordPress fragments.
- VERIFY: 7 focused WordPress builder tests passed; changed Python files
  compiled; lxml structural checks passed for all 8 sources and fragments;
  29 selected live WordPress and 12sgi public routes returned HTTP 200.
  Browser visual review of the local bundle remains pending.
- NEXT: review the generated menu and page package, then apply it to WordPress
  with an approved WordPress editing path and verify the signed-out mobile and
  desktop experience. Do not alter the separate 12sgi.com civic routes.

## Cross-workstream review snapshot — 2026-11-25

- INSPECTED: GitHub open PRs and latest checks for `jimlangford/12sgi-king`; main checkout and local Copilot worktrees; Docker service status and King Bridge/AI Gateway logs. This is a point-in-time read-only review, not a deployment approval.
- GITHUB: PR #386 is the only open PR found. Its title/body describe prerequisite documentation, while its 26-file diff adds public RegisteredUser game signup, auth changes, a games API, Nginx routing, and Compose wiring. The automated review text says it reviewed the dispatch documentation, so it does not establish a review of the full implementation. Python lint and all four accessibility shards fail; Python 3.11/3.12 tests, secret scan, shell lint, and YAML lint pass. Public host forwarding and live multiplayer remain unverified.
- LOCAL MAIN: checkout is at `f2b953d`, equal to `origin/main`, on `codex/owner-job-authentication`; the owner-auth and public-navigation changes remain uncommitted together. Keep those review scopes separate before preparing PRs.
- LOCAL GOVOS V2: `jimlangford-probable-guacamole` is 47 commits behind main with a large uncommitted diff. Its `docs/GOVOS_V2_AUDIT.md` identifies the dispatch log/worker mismatch, missing verified Owner authorization for privileged actions, unconstrained file references, and separate database/dispatch writes. Treat these APIs as queued only until authorization, path policy, durable dispatch, and end-to-end execution are verified.
- RUNTIME: AI Gateway is restarting because `/repo/config/ai_tool_registry.v2.json` is absent or invalid in the container. Neo4j currently publishes ports 7474 and 7687 on all host interfaces; external reachability is unverified and should be reconciled with the local-only architecture. The games service from PR #386 is not running in the inspected local Compose stack.
- NEXT: resolve PR #386 scope and failed CI gates; restore Gateway registry availability; verify the Neo4j host/firewall boundary; keep GovOS v2 in queue-validation status; separate the local navigation and owner-auth changes. No GitHub changes, deployments, service changes, or merge were made during this review.

## Public HTML/navigation verification — 2026-11-24

- Branch: `codex/owner-job-authentication`; verification and source fix only, no commit or deployment.
- FINDING: the isolated Python build succeeded, but the post-build link crawler found `grants.html` and `platform.html` still linked to private `go.html`, which the public owner-ops purge correctly removes.
- CHANGED: both source pages now link to `site/index.html` (normalized to public `index.html` by the builder); `tests/test_public_frontdoor.py` covers the public/private navigation boundary and now verifies the current local-first workflow invokes the full validation build.
- VERIFY: redirected `KA_SITE` build completed 29/29 lanes; Python parsed 658 rendered HTML pages with zero structural or duplicate-ID findings; `tools/link_audit.py` scanned 10,869 links/assets with zero broken internal links and zero broken anchors; five focused tests plus two subtests passed; reviewed private owner pages were absent from public output; `git diff --check` passed.
- PRESERVED / NEXT: generated `site/` was not overwritten, owner-only routes remain private, and no publish occurred. Review and commit this navigation fix separately or with the active owner-authentication patch as appropriate.

## Owner job authentication — 2026-11-24

- Branch: `codex/owner-job-authentication`, based on `main`; no commit or deployment.
- INSPECTED: `AGENTS.md`, `CANON.md`, `README.md`, the owner job dashboard, King Bridge owner job routes, shared `services/authz.py`, existing token usage in King frontend/apps, and public build exclusion test. Source inventory count: 81 HTML/JS files in `king_public_src/`, 9 in `element_lotus_public/`, 17 in `go/`, and 8 in `apps/`. No `dev-internal-token` or `X-Service-Token` literal found in those frontend directories beyond the reviewed owner dashboard before this change.
- FINDING: `GET /api/v2/owner/jobs*` had no authentication. Approval relied on a browser-embedded `dev-internal-token`; the backend required only internal service trust for writes. This makes authenticated Owner identity unavailable for auditing approval actor attribution.
- CHANGED: owner job list/stats/detail/approval routes require shared auth-service introspection and `Owner` role. Approval actor uses the verified subject. Dashboard sends bearer credentials and migrates `king_ownerToken` to the existing `king.ownerToken` key. Added focused regression tests.
- PRESERVED: existing bridge routes, local-first services, public build exclusion for `owner_jobs.html`, and internal service authentication for other bridge mutation/inference endpoints. No publishing, deployment, DNS, or merge.
- VERIFY: `python -m unittest tests.test_king_bridge_owner_auth -v` passed (3 tests); `git diff --check` passed. `python tools/local_validation.py --stage test` ran 548 tests and failed 6 unrelated Windows/environment tests: two scanner setup/exit checks (including missing npm), coverage reporting, Windows newline filename handling, and two `PermissionError` failures in public release pointer tests. The focused auth tests passed in that full run. Live auth-service integration remains unverified.
- NEXT: review this focused diff; then continue the full interface and API-routing inventory. Before production use, confirm King Bridge can reach the configured auth introspection endpoint and align auth-service service credentials in deployment configuration.
## Education and creative connections — 2026-11-24

- Branch: `copilot/enable-registered-users-access-backend`.
- PUBLIC: connect education, games, films, music, and civic source pages with
  descriptive links; regenerate the existing WordPress fragments.
- PRIVATE: align the existing Neo education activities with the current page.
  The loader marks current `USES` edges with a revision; its reader filters by
  revision and falls back to the current static map until the loader runs.
  Older edges remain intact, and other graph readers may still see them.
- VERIFY: isolated public build, built-link checks at root and project mounts,
  12 focused education/graph/bundle tests, Python compilation, and secret scan
  passed. No live graph, public route, publishing, or deployment was exercised.
- NEXT: owner review the links and mapping, reconcile other graph consumers, and
  arrange an owner-machine graph load and verification before claiming live status.

## Registered-user branch merge coordination — 2026-11-24

- Branch: `copilot/enable-registered-users-access-backend`; merge current `main`.
- Scope: retain both handoffs and dispatch entries, plus both game and AI-gateway
  health dependencies and container ports. No deployment or owner-machine action.
- VERIFY: Compose configuration, YAML lint, private-defaults test, and secret scan
  passed. CodeQL found zero Python or JavaScript alerts. Focused auth/game tests
  could not run here because FastAPI is unavailable.
- NEXT: run the auth/game tests with dependencies available; verify the public game
  route before claiming production availability.

## CI YAML lint repair — 2026-11-23

- Branch: `copilot/fix-compose-yaml-lint`, based on `738fe2c`; no deployment.
- INSPECTED: the GitHub job reported only a PRIVATE receipt; reproduction
  showed an indentation warning promoted to failure by strict yamllint.
- Scope: whitespace-only alignment of the `ai-gateway` volume list in
  `docker-compose.v2.yml` to repair the strict YAML lint job. This overlaps
  deployment configuration but does not change mounts or service behavior.
- PRESERVED: existing release ownership, PRIVATE/BRIDGE configuration, and
  creative/output approval gates.
- VERIFY: `python tools/local_validation.py --stage lint-yaml` passed on Python
  3.12 with yamllint 1.38.0; the parsed Compose model is unchanged, and
  `tests.test_private_hosting.ConfigTests.test_private_defaults` passed.
- NEXT: review the change and confirm GitHub lint on the resulting head;
  no post-fix GitHub run is claimed.

## Active implementation — game-player magic links and multiplayer — 2026-11-20

- INSPECTED: PR #380 (auth/Studio release) and PR #385 (local deployment hardening)
  are merged. Work is isolated on `copilot/enable-registered-users-access-backend`.
- CHANGED: public verified-email magic-link onboarding now issues a game-only
  `RegisteredUser` session; a separate Compose-only service serves Konane/Weiqi
  shared circles through the narrow `/games/api/` route. Owner allowlisting and
  private backend routes remain unchanged.
- PRESERVED: no general backend/Tailscale access, direct host publish for the game
  API, production cutover, or owner-machine operation was performed.
- VERIFY: 33 focused auth/game tests and the repository test stage pass. The isolated
  public build, YAML lint, Compose config, targeted Ruff, Python compilation,
  JavaScript syntax, whitespace, explicit-base Python lint, and secret checks pass.
  Final read-only review found no significant remaining issues. Initial CodeQL
  flagged polynomial backtracking in email validation; this was replaced with
  bounded linear validation and covered by a regression test. The post-fix CodeQL
  request timed out, so a clean CodeQL result is not established.
- NEXT: obtain a successful CodeQL verification when available and confirm the static
  host forwards `/games/api/` to the Compose web-server. GitHub Pages static backup
  alone cannot run multiplayer; do not claim production availability until the host
  route and live service are verified.

## Deployment branch merge coordination — 2026-11-20

- Owner requested conflict resolution on `copilot/fix-12sgi-king` (PR #385).
- Merge latest `main`, retaining both the private deployment maintenance notes and
  the newer CI/public-release handoffs. No deployment activation, source rewrites,
  DNS changes, owner-machine operations, or release ownership changes are intended.
- VERIFY: targeted merged-tree checks follow the merge commit; host-only deployment
  verification remains pending as documented below.
- NEXT: review updated PR checks before merge; preserve the newer public-release
  approval/validation requirements independently of private deployment maintenance.

## Held-request triage — 2026-11-20 (repository evidence only)

**Scope / ownership:** Copilot reviewed the six owner-supplied summaries on
`copilot/fix-ci-cd-workflows`. This is not a claim of live workboard ownership:
the owner-machine Claude session must identify the actual jobs and coordinate
with their current lanes. Existing auth/Studio and release ownership below is
preserved. Waiting is safe; do not infer that a stale request is still broken.

**VERIFY:** the cloud checkout was clean before this documentation change.
`.dispatch_log.jsonl` (the default workboard event log) and
`reports/_status/remote_threads.json` are absent here. Complete job descriptions,
IDs (except a historical WordPress reference), lane reports, and current local
runtime evidence are therefore unavailable. No owner-machine service was
probed through cloud localhost. The reported ages, 7904 MiB usage, four rungs,
27 lanes, and 13 threads are owner-provided snapshots, not current measurements.

| Request | Disposition | Observed evidence / next responsible lane |
| --- | --- | --- |
| EI / audit-quad-os Fable v3 | **awaiting decision** | No request-specific ladder or adoption artifact located in this checkout. Owner-machine Claude should ask the EI/audit lane for the four rung definitions, complete 27-lane roster, and per-lane selection evidence; witness the result without changing selections or inventing ladder values. |
| Wā8 ComfyUI restart | **awaiting decision** | `watchers/surface_health.py` explicitly makes ComfyUI/Ollama report-only. No current owner GPU/queue readings are available. `comfyui-quad-os` should confirm current service readiness, VRAM and active Ollama/render jobs against the actual 7800 MiB gate; coordinate any unload/restart and preserve queued work. Do not equate unavailable queue data with an empty queue. |
| Yale-blue guided onboarding tour | **awaiting decision** | The actual `onboarding_tour` target and owning dashboard checkout were not located. `design-system-thread` should identify the source, existing dashboard tokens and current implementation, then coordinate styling and `design:accessibility-review` before publication. Generic recolor history does not verify this tour. |
| ComfyUI-hub render audit | **awaiting decision** | `watchers/comfy_client.py` documents completion as `executing` with `node == None` for the same prompt ID, and outputs from history. This contract is not evidence that the owner's conductor produced a playable `scene_NN.mp4`. Render lane must supply its fix report and the complete untruncated audit checklist; audit lane then verifies prompt identity, actual finished media and playback. |
| Remote-activated thread audit | **awaiting decision** | Requested status JSON is absent. Owner-machine audit lane should locate the actual report, check its timestamp and reconcile every reported entry with its original source, activation and latest outcome. The stated count of 13 is not a forced target. Retain stale/unresolved distinctions and private evidence locally. |
| `wp-go-live` milestone | **awaiting decision** | Historical dispatch references #299 and a bundle ready for WordPress paste; neither proves current milestone identity, READY, or PUBLISHED. WordPress/output lane should retrieve current gates, lane reports and MILESTONE markers, reuse matching evidence, and obtain authenticated delivery plus live-page verification before claiming publication. |

**Next evidence record (PRIVATE, on owner machine):** for each actual job record
its ID, owning lane, source/report timestamp, observed acceptance evidence,
disposition, and next responsible lane. Use **verified complete** only when the
full current checklist is met; **needs action** for a confirmed unmet criterion;
**awaiting decision** for missing evidence or a required coordination decision.
Update the live board only after reconciling its current state; do not create
duplicate jobs or mark existing ones done from these summaries.

**Verified complete (repository subcheck only):**
`python -m unittest tests.test_deploy_elementlotus_wp` passed all **4 tests**
during this triage. This confirms the tested bundle generation/parity behavior,
not the live WordPress configuration, rendered site, or go-live milestone.

**Safe inspection:** read the actual configured workboard event log or use an
explicit read-only board view. `services/v2_workboard.py` defaults to
`selfheal_engineering_jobs()` when invoked without an action: do not run the
bare CLI as an inventory command. `--pending` lists creative/output approvals
only, not all six requests. Do not approve/reject/archive jobs merely to triage.
Keep credentials, job payloads and private evidence out of this public handoff.

**PRESERVED / NEXT:** no model upgrades, GPU operations, restarts, UI changes,
workboard mutations, milestone completion, WordPress publication, DNS changes,
or gate changes were performed. Claude on the owner's machine should reconcile
these six requests against fresh evidence first. READY remains distinct from
PUBLISHED; creative/output approvals and existing privacy boundaries remain.

## Active implementation — local primary and public static backup, 2026-11-19

- Owner requested implementation of the prepared local-first plan. Copilot is
  working on repository-side public release automation on
  `copilot/fix-ci-cd-workflows`; the auth/Studio release ownership below is
  unchanged. Local machine integration requires Claude on that machine.
- CHANGED: `tools/public_release.py` provides full validation before promotion,
  isolated detached worktrees, overlap protection, hash-verified retained
  releases, atomic serving-pointer promotion/rollback, bounded source backup,
  and PRIVATE per-phase status. The source backup requires an explicit reviewed
  clean commit and branch; it never stages arbitrary files or force-pushes.
- PUBLIC packaging: the existing isolated validator removes only explicit
  non-runtime implementation/backup artifacts before accessibility scans the
  output. `tools/public_build_hygiene.py` does not alter source files or the
  private mirror. `tools/fix_link_prefixes.py` makes existing public root-relative
  HTML links mount-independent before validation. Export checks reject private
  paths/content and emit a minimal public commit marker without private logs.
- GITHUB: `.github/workflows/public-static-backup.yml` is disabled unless owner
  approval variables match the release. Read-only Pages checks require the
  explicit default github.io backup URL and no custom domain; the workflow
  must not replace a primary/custom-domain Pages deployment. Protected
  environments and actual Pages settings still require owner verification.
- Boundaries: no private Docker/server changes, DNS changes, WordPress posts,
  traffic failover, creative/output auto-approval, or accessibility allowances.
  Only isolated, validated PUBLIC output may become a hosting artifact.
- ACTIVATION / NEXT (Claude): follow the exact CLI, state-path, rollback,
  scheduler, source credential-manager, Pages environment/approval-variable,
  and serving-root instructions in `README.md`. Locate and inspect the real
  checkout first. Approve explicit prior-base and release SHAs rather than
  blindly accepting changing HEAD. Do not start the old private deployment
  servers or serve the release-state parent. Keep Windows state ACLs private.
- VERIFY (implementation agent): `python tools/local_ci.py` passed **511 tests**.
  Ruff, yamllint, compilation, and whitespace checks passed. An actual isolated
  build produced **29 lanes / 499 pages**; structural/privacy export checks
  accepted **722 public files** after the explicit artifact cleanup. Export
  checks alone are not a successful full release gate or WCAG conformance.
  Read-only review found no remaining significant issues; changed-file secret
  scanning passed.
- SECURITY / source: implementation commit `2be4abca`; post-commit CodeQL
  analyzed Python and Actions with **zero alerts**. This is repository evidence,
  not a deployed commit or verification of owner-machine/backup freshness.
- VERIFY (limits): this checkout still lacks Gitleaks/browser prerequisites for
  the complete release gate. The previously recorded accessibility divergence
  remains unresolved; no allowances were regenerated. A meaningful local base
  and complete history must be provisioned where missing. No full-gate success
  or current full-site browser result is claimed.
- Status: **Approved for repository review and owner-machine preparation**;
  not activated on the owner machine. No local scheduler/server was configured,
  source backup invoked, Pages deployment triggered, DNS changed, or WordPress
  post created here. Live URLs and owner-machine synchronization remain
  unverified. A source push is not proof of a healthy served release.

## Claude restart priority — owner direction, 2026-11-19 UTC

**Owner request:** "I want 12sgi to work locally with GitHub backup".
This section is the restart entry point; historical release ownership below
is preserved, not superseded by permission to merge or deploy.

### Confirmed follow-up — automatic updates and public backup hosting

The owner subsequently requested automatic local-site publishing and GitHub
updates, then confirmed **public backup hosting too**. This expands the requested
implementation beyond source backup; the older no-deployment instructions below
describe the initial inventory, not a rejection of this new requirement.

- LOCAL PRIMARY: automate updates to the existing local educational site using
  reviewed public inputs and the existing validators. This is not permission
  to auto-approve creative/output work, publish private content, or bypass a
  failed check.
- GITHUB SOURCE BACKUP: automate backup of reviewed source changes only. Use
  explicit file scope, secret scanning, and conflict-safe synchronization;
  never blanket-add local files, overwrite owner edits, or force-push.
- PUBLIC BACKUP HOSTING: implement a separately reachable GitHub-hosted static
  backup of validated PUBLIC educational pages and assets. Reuse an existing
  Pages path if appropriate after checking repository settings and ownership.
  Do not upload the checkout, private receipts, databases, models, credentials,
  owner pages, or Tailscale services.
- SAFETY: publish only a successfully validated release; retain the last known
  good version on failure. Record source commit, validation evidence, deployment
  URL, and backup freshness. A successful source push alone is not hosting
  success, and a static backup does not provide private backend functionality.
- SEPARATE DECISIONS: automatic DNS/traffic failover and the relationship between
  12sgi.com and ElementLOTUS.com remain unconfirmed. This confirmation does not
  authorize WordPress posts or changes to its existing approval policy.
- STATUS: **Approved for implementation scope: local automatic updates and public
  static backup hosting, owner direction.** Operational readiness remains pending
  verification. This handoff update configures no scheduler, backup host, DNS,
  or deployment; Claude must inspect the real local environment and existing
  publishing paths before implementing and verifying them.

### Operating intent and scope

- PRIVATE: the owner's machine remains the primary runtime, educational-data
  host, local AI/Neo4j environment, and validation authority.
- BRIDGE: GitHub holds reviewed source, history, and coordination backups. It
  is not required for local runtime operation. A source push does not back up
  ignored databases, private content, model files, credentials, or running state.
  Inventory existing private backup mechanisms before proposing any changes;
  never upload those assets to this public repository.
- PUBLIC: the owner identified ElementLOTUS.com as the WordPress site.
  The relationship between that site, 12sgi.com, and locally hosted educational
  pages still needs confirmation. Local operation does not require public DNS.
  Leave DNS, Cloudflare/Tailscale bridges, and WordPress publishing unchanged.
- Scope labels should say "Approved for" a specific use, with the approver,
  commit, evidence, and limitations. The request names personal use but does not
  define all other categories or grant deployment approval. Record unverified
  scopes as "pending verification"; do not relabel failed checks as passing.

### First actions for Claude Code on the owner's machine

1. Read `CANON.md`, this file, `docs/CI_OWNER_ACTIONS.md`, and the newest
   `DISPATCH_LOG.md` entries. Locate the real local checkout(s); do not assume
   this cloud path is the owner's filesystem location.
2. Before changing anything, record each relevant checkout's branch, commit,
   dirty status, configured upstream, and any already-recorded running service
   or build version. Inspect only; do not dump environment variables,
   authenticated remote URLs, credentials, or private content into shared logs.
   Cloud head at preparation: `8f623eec`, branch
   `copilot/fix-ci-cd-workflows`; the handoff commit will be newer. This is not
   evidence that the owner's checkout, main, or running system matches it.
3. Preserve uncommitted edits and other agents' release ownership. Compare local
   refs first; any needed fetch is an explicit network operation. Do not reset,
   force-pull, merge, or overwrite the owner's work automatically. Review this
   branch's changes before bringing them into the owner-approved local branch.
4. Reuse the isolated environment and existing dependencies. Run the existing
   `tools/local_validation.py` from the identified checkout, using an available
   reviewed comparison base when required. It isolates public builds and home/
   profile paths and saves PRIVATE receipts outside the checkout. Do not run
   `build_site.py` directly in the owner's normal private environment.
5. Establish local readiness with the actual validator results and read-only
   checks of the already-running local site's educational links and assets.
   Verify the existing approved serving root and loopback/private binding;
   never serve the whole repository or a private directory as a public root.
   Do not start deployment/recovery servers, restart Docker, expose Tailscale,
   or publish a test WordPress post as part of this inventory.
6. Report `INSPECTED`, `CHANGED`, `PRESERVED`, `VERIFY`, and `NEXT`, plus
   "Approved for" scopes only where supported by explicit approval and evidence.
   Keep local validation, GitHub source backup/check status, local runtime
   status, public domain routing, and WordPress delivery as separate results.
   Update this handoff and the dispatch log before passing work to another agent.

### Evidence carried forward — not a new local-machine verification

The prior cloud working-tree run passed 440 tests, the isolated 499-page build,
and 21 browser self-tests. Its overall result remained FAIL: 35 new/changed
accessibility findings and 40 resolved baseline entries on
`prosecutor_public_feed.html`, missing default lint comparison refs, missing
Gitleaks, and shallow history. Preserve those results and the unchanged baseline
until properly investigated. This preparation runs no validators or services
on the owner's machine and establishes no new approval for runtime or publishing.

---

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

## Local-first Validation Follow-up — Copilot, 2026-11-18

- Branch: `copilot/fix-ci-cd-workflows` (continuation of PR #387).
  Scope coordinated in `DISPATCH_LOG.md`; Codex's release ownership above
  remains unchanged.
- CHANGED: distinctly named `tools/local_validation.py` combines
  existing validators with isolated builds and private receipts;
  `tools/ci_checks.py` shares lint/secret policy with validation workflows.
  Validation-only callers and local operating instructions use the new entry point.
- PRESERVED: no baseline regeneration, source HTML changes, private deployment
  changes, Docker/Tailscale exposure, runtime integration, automatic installs,
  or automatic history fetching.
- VERIFY: shared-gate implementation agent reports 30 regression tests passing,
  pinned yamllint 1.38.0, maintained ShellCheck 0.9.0, and compilation passing.
  YAML validation included the manual validation-build caller. Missing tools
  fail by name. Read-only review found and resolved timeout-descendant cleanup
  and committed-file local lint gaps; follow-up found no significant issues.
- VERIFY (combined, Python 3.12 working tree): 440 tests passed, 45.73% service
  coverage; all 29 public build lanes and 499 pages passed isolation checks.
  Twenty-one real browser self-tests passed. Final focused runner/test-gate
  tests: 27 passed. Focused Ruff E/W/F/I passed all five changed Python files.
  One-time provisioning used existing pinned dependencies; the runner itself
  never installs. Provisioning caches were removed from the checkout.
- SECURITY REVIEW: changed-file secret scanning found no secrets before commit.
  Post-commit CodeQL Actions/Python analysis reported zero alerts. These checks
  do not replace the blocked full-history Gitleaks gate.
- LOCAL RESULT: **failed, not approved for deployment**. The full 499-page
  browser scan completed with zero scan errors but found 35 new/changed
  findings and 40 resolved baseline entries, all on `prosecutor_public_feed.html`.
  This is separate from the unchanged 14,694-finding reviewed baseline.
  No baseline entries, exceptions, or HTML sources were changed to hide it.
  A passing 136-page shard does not override this full-site failure.
- PRIVATE evidence: the full working-tree receipt is in the external run
  `run-173bf754c22641a2a547e5213241b424`, under the sibling
  `.12sgi-local-validation-check` output directory. Reports, coverage, logs,
  and isolated HTML remain outside source control and are not uploaded.
- LOCAL LIMITATIONS: this checkout is shallow and has no default remote-branch
  comparison ref. The local gates must fail rather than fetch or silently
  ignore committed changes. Provision full history and an available reviewed
  lint base manually; use `--base`/`--head` for explicit offline comparisons.
  The default Python lint stage failed on missing comparison refs; the secret
  stage failed on missing Gitleaks. A changed-file secret check passed, but that
  is not a full-history scan.
- NEXT: inspect the public-feed renderer (`watchers/prosecutor_public_feed.py`)
  and the full report to establish the cause of the baseline divergence before
  any coordinated source fix or manually reviewed baseline pruning. Do not
  regenerate allowances. Provision Gitleaks and complete local refs/history,
  rerun the full gate, then obtain separate GitHub approval/status evidence.
  Historical GitHub green results below do not certify the new head; local
  validation, GitHub approval, and deployment authorization remain distinct.

## Separate Phase 1 CI Work — Copilot, 2026-11-17

- Branch: `copilot/fix-ci-cd-workflows`. Scope coordinated in `DISPATCH_LOG.md`;
  the Codex release ownership and next action above are unchanged.
- INSPECTED: four `ci-*.yml` workflows, existing V2/Studio tests, and GitHub runs.
  Main checks were green with suppressed failures; the initial PR runs reported
  `action_required` without jobs or logs. Do not equate that state with code failure.
- CHANGED: strict Python 3.11/3.12 test matrix, CI-only pinned dependencies,
  pytest configuration, non-vacuous contract assertions, and cleanup on failed
  integration startup. The owner's follow-up local-workflow request is handled
  by `python tools/local_ci.py`, also called by GitHub; setup is in `README.md`.
  This runner never installs packages or deploys. Lint, accessibility, secret scan,
  and Dependabot repairs are part of this separate CI branch, not the Studio release.
- PRESERVED: auth/Studio service implementation, local Neo4j/Ollama,
  Tailscale/Cloudflare paths, creative/output gates, and all deployment workflows.
  These checks do not change private deployment ordering or automatically
  promote artifacts.
- VERIFY: all 73 focused tests passed on Python 3.11 and 3.12 without Docker or
  external services; dependency checks passed. Negative contract mutations and
  a simulated failed integration startup were rejected/cleaned up as expected.
  The final shared local runner passed all 387 V2/Studio/runner tests on both
  Python versions (46% service coverage, reported without a fabricated threshold).
  Changed-file Ruff/import sorting, the explicit full-tree correctness baseline,
  workflow/Compose YAML, and maintained-automation ShellCheck gates passed.
  Five real-scanner regression tests passed; the tracked tree and reachable
  history were clean after exact documented false-positive exceptions.
  CodeQL Actions/Python analysis reported zero alerts.
- COMPLETED — Claude's full-site migration supersedes the earlier eight-page
  pilot blocker. Copilot reviewed the implementation and queried GitHub on
  2026-11-17 after 23:07 UTC: all five validation workflows passed on `5bca6d9`.
  Accessibility run `44192297689` passed all four shards and `a11y-complete`;
  every shard finished in under three minutes. The reviewed baseline contains
  all 499 pages and 14,694 existing node findings, with no excluded pages.
  New findings, missing/fixed baseline entries, scan errors, and removed pages
  fail the gate. Seventeen scanner tests cover browser checks and gate behavior.
  Only `target-size` message pixel measurements are normalized for runner font
  variation; other messages, including contrast ratios, remain exact.
- VERIFY (GitHub evidence): test run `44192297725` passed both Python versions;
  the Python 3.12 log records 387 passed and 46% service coverage. Lint run
  `44192298058`, secret scan `44192297700`, and labeling `44192298442` passed.
  This completion review did not rerun Claude's completed tests/builds.
- REVIEW FIX: replaced broad missing-stylesheet substring exceptions with 11
  exact normalized paths. A new missing file in the same directory now fails,
  and every individually resolved exception must be pruned. The implementation
  agent verified 21 scanner tests, a sanitized 499-page/29-lane build, and the
  actual Sage page (11 expected missing paths, five unchanged baseline findings).
  No source HTML or accessibility baseline was changed. Follow-up review found
  no further significant issues. The full-site scan was not repeated locally.
- FINAL-HEAD STATUS: the review push `3318cb3` triggered GitHub approval-required
  runs (for example accessibility `44196827567`); owner approval of the latest
  PR checks is still required. Prior green evidence above is for `5bca6d9`,
  not an assertion that the later review commits have executed in GitHub.
- KNOWN DEBT: this is a desktop static accessibility regression gate, not WCAG
  conformance. Existing findings, incomplete checks needing human review, and
  the explicitly reported Sage Realm missing stylesheets remain documented in
  `docs/CI_OWNER_ACTIONS.md` and the scanner baseline/scope. Fix shared templates
  in separately coordinated work; never refresh the baseline merely to hide
  regressions. Production deployment and post-merge `main` results are not
  established by a passing PR.
- NEXT (owner): review PR #387 for readiness and merge authorization; configure
  branch protection to require the resulting check names. Enable GitHub secret
  scanning/push protection and any custom patterns in repository settings.
  History scanning cannot prove that inaccessible/deleted remote refs are clean;
  rotate/revoke any exposed credential before considering history remediation.
  Never rewrite shared history or redeploy private services as part of this CI PR.

## Backend HTML navigation — 2026-11-25

- Branch: `codex/simplify-backend-html-navigation`, based on `main` at `84ef6ef`.
- Scope: PRIVATE `/king/go.html` launcher and `/king/go/` owner routes.
- CHANGED: add concise section navigation; point owner-tool cards at their working `.html` routes; return owner pages and the `/king/go/` index to `/king/go.html`.
- PRESERVED: public WordPress, civic routes, Tailscale boundaries, and deployment configuration.
- VERIFY: live route inventory returned HTTP 200 for all eight `.html` pages; old extensionless owner links returned 404. Source diff passes `git diff --check`. Live post-deploy verification is pending.
- NEXT: merge the reviewed change to `main`; the existing path-filtered private deployment workflow should deploy it. Confirm launcher navigation and owner-page back links on `king.tail760750.ts.net`.
## Local AI guarded self-heal teaching — 2026-11-25

- Codex updated `tools/teach_local_ai.py` so every generated persona inherits a
  self-heal covenant: continuous diagnosis and bounded safe actions, with
  ownership, active-job, approval, and post-repair verification checks.
- Removed the old blanket permission for free engineering self-heal, Docker
  restart/prune, service restarts, and package installs. ComfyUI remains solely
  owned by `app/server/studio_supervisor.py`; cleanup, installs, restarts,
  deployments, publishing, credential changes, and destructive edits require
  the documented owner gate.
- Ollama `0.40.18` accepted updates for `king-jrcsl`, `king-civic`,
  `king-workboard`, and `king-server`. `/api/show` confirmed the covenant and
  ComfyUI ownership instruction in all four active model templates.
- The teaching script's four inference checks timed out. Prompt installation is
  confirmed; responsive inference is not. Do not report end-to-end self-heal or
  service recovery as runtime-proven until a model response and approved repair
  path are verified. No service was restarted and no jobs were interrupted.
- Shared AI change feed entry added for Local AI, Claude Code, Codex, and GitHub
  Copilot. It is shared-file visibility, not a direct external chat notification.
