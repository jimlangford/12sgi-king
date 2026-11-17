# CI: owner-only actions, decisions and known debt

Written 2026-11-17 by Claude Code for the Phase 1 CI branch (`copilot/fix-ci-cd-workflows`, PR #387).
Scope: validation only. Nothing here deploys, starts the Docker stack, exposes a private service, rewrites
shared history, or touches tenant isolation or WordPress publishing.

## 1. What is verified, and where

| Item | Result | Where verified |
| --- | --- | --- |
| Shared gate `python tools/local_ci.py` | 387 tests, see section 2 for the Windows result | Windows 11, Python 3.11.9, isolated venv |
| Same gate on Python 3.12 | NOT re-run here (3.12 is not installed on this machine) | Reported only by the earlier Linux run |
| Public build honors `KA_SITE`, excludes private material | Verified (section 4) | Windows, redirected home, 499 pages |
| Accessibility scan of every generated page | 499 of 499 pages scanned, 0 scan errors | Windows, real Chrome |
| Accessibility gate logic (new page, stale entry, shards) | 16 scanner tests pass | Windows |
| **GitHub results** | **NOTHING HAS RUN.** Every run on this branch is `action_required` | `gh run list`, section 5 |

CI is not green. It has not run. Do not read the earlier "all checks pass" lines in
`ACTIVE_AGENT_HANDOFF.md` as covering this branch; they describe the studio release head.

## 2. Owner-only actions (only the repository owner can do these)

1. **Approve the pending workflow runs on PR #387.** All runs for commits `dbdd638`, `707611a` and `8fa5ab8` are
   `action_required`: GitHub is waiting for approval (the PR is authored by a bot) and no job has executed.
   Open the PR's Checks tab (or Actions) and choose "Approve and run workflows". Until then there is no
   GitHub evidence either way. I could not inspect your Actions approval policy from here; it lives under
   Settings, Actions, General, and its exact wording may differ.
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
- PR #387 (draft). All 15 runs listed were `completed` with conclusion `action_required` (no jobs executed).
- Billing is no longer a blocker: recent `main` runs in the CI workflows succeeded.

## 6. Workflow and Dependabot review

- Dependabot: valid. 12 pip directories and 2 Docker directories exist and have manifests; GitHub Actions are
  covered too. Per-service Dockerfiles below `services/` are not separately watched.
- All four `ci-*.yml` files are now pinned to commit SHAs. Before this change `ci-test.yml` and `ci-lint.yml` used
  mutable tags (`@v4`, `@v5`).
- `ci-secret-scan.yml` downloads gitleaks with a pinned SHA-256 check and scans the full history. Its 5 minute limit is
  untested against this repository's history size; the first real run will tell.
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
