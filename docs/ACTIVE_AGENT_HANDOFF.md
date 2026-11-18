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
