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
