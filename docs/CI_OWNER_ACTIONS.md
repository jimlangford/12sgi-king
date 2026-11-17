# CI: owner-only actions, decisions and known debt

Written 2026-11-17 by Claude Code for the Phase 1 CI branch (`copilot/fix-ci-cd-workflows`, PR #387).
Scope: validation only. Nothing here deploys, starts the Docker stack, exposes a private service, rewrites
shared history, or touches tenant isolation or WordPress publishing.

## 1. What is verified, and where

| Item | Result | Where verified |
| --- | --- | --- |
| Shared gate `python tools/local_ci.py` | 387 tests, see section 2 for the Windows result | Windows 11, Python 3.11.9, isolated venv |
| Same gate on Python 3.12 | Not run on this machine (3.12 not installed). GitHub Linux ran 3.11 and 3.12: both SUCCESS on `06b744f` | GitHub Actions |
| Public build honors `KA_SITE`, excludes private material | Verified (section 4) | Windows, redirected home, 499 pages |
| Accessibility scan of every generated page | 499 of 499 pages scanned, 0 scan errors | Windows, real Chrome |
| Accessibility gate logic (new page, stale entry, shards) | 16 scanner tests pass | Windows |
| **GitHub results, head `06b744f` (queried 22:26 UTC)** | Test (Python 3.11 and 3.12), Lint, Secret Scan, Label: SUCCESS. **Accessibility: FAILURE (shard 2 of 4)**, fixed in `af7795c` (section 5b) | `gh run view`, section 5 |
| **Completion review, head `5bca6d9` (queried after 23:07 UTC)** | Test (both Python versions), Lint, Secret Scan, Accessibility (all four shards and aggregate), Label: **SUCCESS** | GitHub Actions API; runs listed below |

**CI is fully green on `5bca6d9`**, as well as `af7795c` (section 5b). Copilot's completion review verified
test run `44192297725`, lint `44192298058`, secret scan `44192297700`, accessibility `44192297689`,
and labeling `44192298442`. The Python 3.12 job log records 387 passing tests and 46% service coverage;
all four accessibility shards completed in under three minutes. This is PR evidence, not a deployment
or a post-merge `main` result. Claude's completed test/build work was not rerun during the review.

The text below that mentions a failure describes the earlier head `06b744f`. (An earlier version of this file said
nothing had run; that was true only before the runs were approved and is superseded.) Do not read the earlier
"all checks pass" lines in `ACTIVE_AGENT_HANDOFF.md` as covering this branch; they describe the studio release head.

## 2. Owner-only actions (only the repository owner can do these)

1. **Check approval requirements for future runs.** Historical runs for commits `dbdd638`, `707611a` and
   `8fa5ab8` were `action_required`; newer runs executed and passed. There is no outstanding approval
   blocker for the reviewed `5bca6d9` checks. If a future run requires approval, use the PR's Checks tab
   or Actions to approve it. Repository approval policy remains an owner-controlled setting.
2. **Mark PR #387 ready for review** after the runs pass. It is a draft.
3. **Branch protection or a ruleset on `main`** (see the decision in section 3 before turning it on).
   Required status checks, once they have run at least once so GitHub lists them:
   `V2 + Studio tests (Python 3.11)`, `V2 + Studio tests (Python 3.12)`, the three lint jobs
   (`lint-python`, `lint-yaml`, `lint-shell`), `detect-secrets`, and `a11y-complete`.
   Require only `a11y-complete` for accessibility, not the four shard jobs: it turns green only if every shard
   passed, and keeps one stable name if the shard count ever changes.
4. **GitHub secret scanning and push protection** (Settings, Code security). This repository is public, so
   they are available. They complement, and do not replace, the gitleaks job: gitleaks scans the whole
   reachable history with the narrow allowlist in `.gitleaks.toml`.
5. **Dependabot alerts and security updates** (Settings, Code security). The version-update config is already
   in `.github/dependabot.yml`; I verified every listed directory has a manifest.
6. **Confirm production overrides the development service token.** `.gitleaks.toml` allows the published
   development default `dev-internal-token` in one historical doc and says production must override it. I cannot
   see production configuration from here.
7. **Codex release coordination.** `docs/ACTIVE_AGENT_HANDOFF.md` says Codex owns PR #380 until it records
   `Status: shipped` or a blocker. I did not edit any release surface (auth, Studio assets, Neo4j projections,
   project mutations, GPU routing, workboard approvals).

## 3. Decisions only the owner can make

**A. Branch protection versus your auto-publisher.** `main` receives direct commits from the content publisher
(`auto: content snapshot ...`, about every few minutes). "Require a pull request before merging" would block it.
Either use a ruleset that lets the publisher's account bypass the PR requirement while still requiring status
checks on pull requests, or keep PRs optional and rely on the checks only. I did not change this.

**B. How the accessibility gate treats data that your publisher regenerates.** The publisher modifies
`seed_reports/mauios/donors/*.html`, and those become public pages. The gate compares exact page, rule, selector
and message. Pages built from data can therefore drift when the data refreshes, and every newly published page with
findings fails by design (the new-page rule). Today 498 of 499 pages have findings, so almost any new page fails.
Options, in my order of preference:
1. Fix the shared page shell. About 11,000 of the findings are structural (content outside landmarks, missing
   `<main>`, duplicate or unlabeled landmarks) and come from shared templates. Fixing the shell removes most of the
   debt and makes new pages pass naturally.
2. Run the accessibility check on pull requests only, not on every publisher push to `main`
   (add `paths-ignore` for `seed_reports/**` and `production_status.json`).
3. Add an explicit per-rule tolerance for data-regenerated pages. I did not build this because it is a policy choice.

## 4. Redirected builds and private material (verified)

`build_site.py` has a lane that writes the PRIVATE King mirror to `~/AppData/Local/king-extract/deploy/king-local`
and reads the private Studio project under `~/Documents/Claude/Projects/`. On Windows, Python resolves `~` from
`USERPROFILE`, not `HOME`. A build is only safe when `HOME`, `USERPROFILE`, `HOMEDRIVE`, `HOMEPATH`, `APPDATA` and
`LOCALAPPDATA` all point at an empty folder. Run with exactly that and `KA_SITE=<scratch>`:

- Build: exit 0, 499 HTML pages, 29 lanes, 0 failed.
- The `king_local_mirror` lane did nothing. The real private mirror's newest file predates the build.
- None of the workflow's forbidden outputs exist: `go`, `go.html`, `king/app.html`, `king/go.html`,
  `king/live.js`, `case_files.html`, `owner_jobs.html`, `king_private_src`, `recusal_evidence.html`.
- The build reported purging 28 owner-only surfaces from the public output.
- No generated page contains a real local path or your tailnet hostname. One page (`join.html`) contains the
  generic suffix `.ts.net` inside a JavaScript check, which is not a host name.
- Do NOT run `python build_site.py` with your normal environment from a CI checkout. It would write to your private
  King deploy folder.

## 5. Actual GitHub state (queried, not assumed)

- Branch `copilot/fix-ci-cd-workflows` at `8fa5ab8`, three commits ahead of `main`, no divergence.
- PR #387 (draft). The first 15 runs (commits `dbdd638`, `707611a`, `8fa5ab8`) were `action_required` and executed nothing.
  After approval, GitHub ran `75028e0` (Test, Secret Scan, Label pass; Lint and Accessibility FAIL) and `06b744f`
  (Test 3.11 and 3.12, Lint, Secret Scan, Label pass; Accessibility shard 2 FAIL, shards 1, 3 and 4 pass).
- Lint failed on `75028e0` with 7 ruff errors in test files that had been touched (6 unsorted imports, 1 unused
  variable); the strict changed-file gate applies to any file you touch. Fixed in `06b744f`.
- Billing is no longer a blocker: recent `main` runs in the CI workflows succeeded.

### 5a. Why accessibility still fails: the baseline is font-metric sensitive

The Windows-built baseline and Linux agreed on all but 3 of ~14,700 entries, and `06b744f` reconciled those. Shard 2 then
failed on Linux with 6 new and 4 stale entries, all in two layout-dependent rules:

- `target-size`: the axe message embeds measured pixel sizes ("71.2px by 19px"), which change with font metrics. The same
  `films.html` entry appears in BOTH the new and stale lists; only the numbers differ.
- `scrollable-region-focusable`: whether a table overflows depends on rendered text width.

Exact-message matching is correct for deterministic rules (contrast ratios come from CSS) but too brittle for these two. The
fix is a decision, not a quiet change: normalize the pixel numbers in `target-size` messages, and decide how to treat
`scrollable-region-focusable` (for example a per-page presence check). Do not simply keep editing the baseline from each
failed run. Linux CI is the authoritative environment; a Windows scan will differ by a handful of nodes.

### 5b. Resolved: all five checks green on `af7795c` (queried 2026-11-17)

- CI - Test (Python 3.11 and 3.12), CI - Lint, CI - Secret Scan, CI - Accessibility (4 shards plus `a11y-complete`) and
  Label PR by changed paths: all `success`. PR #387 is still a draft and nothing was merged.
- Why shard 2 had failed after `06b744f`: (1) the 16-test browser check was killed at its 40 s limit on a slower
  runner (now 150 s); (2) `target-size` messages embed measured pixels that follow the runner's fallback fonts (the
  same link measured 85.9px, then 96.3px, in two runs of identical code).
- Decision taken, not a quiet baseline edit: `canonicalFailure()` in `tools/a11y/scan.mjs` ignores the measured pixel
  numbers for the `target-size` rule ONLY. Page, rule, selector and the rest of the message must still match, a
  vanished finding is still stale, and contrast and every other rule stay exact. Pinned by a unit test (17 scanner
  tests pass, twice in a row). Recorded in `baseline.json` `review.matching`.
- Still exact, and worth watching: `scrollable-region-focusable` (4 tables on two civic templates). It matched on
  three consecutive Linux runs, so it is not flaking today. If it ever does, the right fix is a per-page presence
  check, not a baseline edit from a failed run.
- Baseline now equals the four Linux shard reports: 14,694 findings on 499 of 499 pages. Windows differs by a few
  nodes; Linux CI is authoritative.
## 6. Workflow and Dependabot review

- Dependabot: valid. 12 pip directories and 2 Docker directories exist and have manifests; GitHub Actions are
  covered too. Per-service Dockerfiles below `services/` are not separately watched.
- All four `ci-*.yml` files are now pinned to commit SHAs. Before this change `ci-test.yml` and `ci-lint.yml` used
  mutable tags (`@v4`, `@v5`).
- `ci-secret-scan.yml` downloads gitleaks with a pinned SHA-256 check and scans reachable history.
  Run `44192297700` completed successfully in under one minute, within its five-minute limit.
- `ci-accessibility.yml` now runs four shards plus an `a11y-complete` summary job.

## 7. Known debt this branch reports and does not hide

- Accessibility: a regression budget, not conformance. See `tools/a11y/baseline.json` (`review.backlog`).
- A real broken page: `king/civic/templates/sage-realm/Sage Realm.html` requests 10 stylesheets relative to its own
  folder (`styles.css`, `tokens/*.css`) that return 404. Recorded in `tools/a11y/scope.json` `knownDefects`;
  fix it in `king_public_src/civic/templates/sage-realm/`.
- A real resource leak in `services/gpu_router/app/main.py` (a SQLite connection is opened and never closed).
  On Windows it prevented test cleanup. The tests now tolerate it; the leak itself is in Codex's release scope
  and is unchanged.
- Ruff correctness baseline: 9 pre-existing findings are listed in `ci-lint.yml`, not hidden.
- `watchers/*`, `_fix_failing.py` and others hard-code `C:\Users\12sgi\...` paths.
- The Windows build takes about 5 minutes against the workflow's 90 second limit on Linux. This is a local
  speed note, not a CI failure.
