# 12sgi-king

This repository is organized around a local-first architecture.

## Architecture

- Local machine = primary host for runtime, AI, Neo4j, local CI, and deployment
- GitHub = support layer for source control, PRs, issues, and repo backup
- Tailscale = private network access layer for local services
- Public DNS = optional only when you intentionally expose the site to the public internet

## Local hosting model

Use these URLs depending on access mode:

- Local only:
  http://127.0.0.1:8080/site/

- Private Tailscale:
  http://<tailscale-ip>:8080/site/
  https://<node>.ts.net/

- Public domain (optional):
  https://12sgi.com/

Only use the public domain after DNS points to the host's public IP and the firewall rules intentionally expose it.

## Local CI / deployment

The primary non-deploying entry point is **`tools/local_validation.py`**, a new
file independent of old blocked GitHub workflows. GitHub calls its selected
stages only as corroborating checks; it does not control local validation.

Prepare an isolated environment once (Python 3.11 or 3.12):

```bash
python -m venv .venv
# Linux/macOS:
source .venv/bin/activate
# Windows PowerShell instead: .venv\Scripts\Activate.ps1
python -m pip install -r requirements-ci.txt
# Existing lint tools, also pinned in CI:
python -m pip install ruff==0.17.5 yamllint==1.38.0
```

Also provision Git, ShellCheck, Gitleaks 8.24.3, Node 22+, Chrome/Chromium, and the
locked browser dependencies (`npm ci --ignore-scripts --prefix tools/a11y`).
Set `CHROME_BIN` to your browser executable when it is not in a standard location.
Use your platform's package manager or the checksum-verified Gitleaks release
used by the secret-scan workflow. Provisioning can require a network connection;
the validation runner never installs, downloads, fetches, or deploys anything.

Run the combined gate after provisioning:

```bash
python tools/local_validation.py
# Focused checks use the same implementation, not separate policies:
python tools/local_validation.py --stage test
python tools/local_validation.py --stage build --stage accessibility
```

The default includes tests, Python/YAML/shell lint, current-file and reachable-history
secret scanning, an isolated public build, and browser accessibility validation.
Missing tools, incomplete history, and failed checks return nonzero—not success.
No Docker, Neo4j, Ollama, GitHub credentials, or external AI service is needed.
Local AI may interpret the evidence but cannot override validator results.
Provision complete reachable Git history once for the history scan. Strict local
Python lint must also have a locally available comparison base; use `--base`
with the reviewed base commit if the default remote-branch reference is unavailable.
The runner never fetches missing history or silently limits lint to dirty files.

The runner prints the location of a **PRIVATE local receipt** and its artifacts,
kept outside the checkout by default. Receipts distinguish local results, GitHub
status (not queried), and deployment (not attempted). Do not commit or publish
receipts, stage logs, or generated HTML. Use `--help` for stage and output options.

Public builds redirect `KA_SITE` and all home/profile variables into scratch
storage rather than reading the owner's project or writing the private King mirror.
Do not invoke `build_site.py` directly with your normal owner environment for
validation. See `docs/CI_OWNER_ACTIONS.md` section 4 for the boundary.

`tools/local_ci.py` remains the reusable test-only gate underneath the combined
runner. The accessibility scanner continues to fail on new findings, stale
baseline entries, removed pages, and scan errors. Its baseline is existing debt,
not WCAG conformance; the runner never regenerates it. Owner-only actions and
open decisions remain in `docs/CI_OWNER_ACTIONS.md`.

Deployment is a separate, owner-authorized operation, not a validation step.
The existing local deployment entry points below are not invoked by the runner;
do not start them merely because local checks pass:

```bash
python local_ci_cd_server.py
python service_auto_recovery.py
```

This keeps the active system under local ownership while GitHub remains a support surface rather than a runtime host.

## Approved local PUBLIC publishing and static backup

`tools/public_release.py` is a separate **PUBLIC release** command, not the
private Docker/recovery servers. It never starts services, approves creative/
output jobs, posts to WordPress, or changes DNS. Provision the validators above
and complete Git history first. A failed gate (including the currently recorded
accessibility divergence) blocks release; do not refresh its baseline to deploy.

On the owner's machine, review and commit **only explicitly selected source
files**, then record the full approved SHA and a reviewed prior lint base in the
owner's scheduler configuration. The command refuses dirty/untracked source,
shallow history, unexpected source changes, partial validation, and shard-only
accessibility evidence. The base must be an existing strict ancestor commit;
HEAD-as-base, descendants, unrelated histories, and a first-ever commit are
unsupported. It creates a detached, isolated worktree, copies only
the existing browser tool installation, and runs the existing full validator
itself; supplied receipts cannot authorize publication. It removes its detached
worktree afterward, retaining PRIVATE validation evidence in state.

```bash
# Example POSIX owner paths: choose a short, PRIVATE path outside the checkout.
# Replace both SHAs with explicit reviewed full commits; never approve "$(git rev-parse HEAD)" blindly.
python tools/public_release.py --state /srv/12sgi-release \
  --expected-sha APPROVED_FULL_SHA --base REVIEWED_BASE_SHA
```

Configure the existing owner scheduler (cron/Task Scheduler) to invoke this
**same idempotent once command**, using the absolute interpreter and script
paths. It installs nothing and does not watch or approve changing HEAD.
Updating the approved SHA/base is an owner review action, not an automatic
content-approval bypass. Nothing is scheduled by this change.

The owner-configured static server must serve **only**
`/srv/12sgi-release/current/`, never the checkout, state parent, or `work/`.
No server is started/reconfigured here. `current` is an atomically replaced
symlink to a write-once `releases/SHA/public/` export. Keep the existing server
unchanged until its serving-root selection has been reviewed. Windows requires
working directory-symlink privileges; otherwise promotion fails closed. Use a
short state path for Chromium socket limits. State must be a **new directory** on
first use; existing directories without the tool's ownership marker are refused
without changing their permissions. Managed paths and existing serving pointers
must belong to this tool, not another deployment. PRIVATE receipts, manifests, and
logs remain outside the serving root. Do not upload them. The PUBLIC export
rejects private paths/declarations, symlinks, databases, models, unreviewed
file types; custom-domain `CNAME` and original build metadata are omitted.
A minimal PUBLIC `buildinfo.json` contains only the approved SHA and validation
time, and is included in the integrity hashes. Export is separately secret-scanned.
Existing same-site root-relative HTML asset/navigation links are normalized
against actual generated targets **before** accessibility validation, so they
also work under the Pages project prefix; external and dynamic `/api` URLs are
not repointed.

On Windows, configure owner-only ACLs for PRIVATE state explicitly: POSIX
mode bits/umask are not Windows access controls. A separate static-server
account should read only the intended PUBLIC target, never state work,
receipts, or logs. This command does not change Windows ACLs or server accounts.

The shared isolated build stage removes only reviewed implementation/backup
artifacts (`.py`, `.pyc`, `.pyo`, `.bak`, and the `sage/no-reopen` build marker)
from its generated PUBLIC copy **before** build checks/accessibility. Original
sources and the builder's earlier private mirror remain unchanged. The exporter
still refuses these artifacts if present; it never silently strips leaking HTML.
Public `.mjs` browser modules, `.geojson` civic maps, and `.md` reference documents
are accepted static types and receive the same private-content checks.
Nondeploying verification built **499 pages/29 lanes** and exported **722 files**.
This is not full release approval: accessibility/history/tool gates remain
independent blockers, and export secret scanning still requires Gitleaks.

```bash
# Select an intact retained release atomically; no build, push, or content edits:
python tools/public_release.py --state /srv/12sgi-release \
  --expected-sha PREVIOUS_APPROVED_FULL_SHA --rollback
# Optional source backup, only when this checked-out branch is explicitly approved:
python tools/public_release.py --state /srv/12sgi-release \
  --expected-sha APPROVED_FULL_SHA --base REVIEWED_BASE_SHA \
  --sync-source --repository jimlangford/12sgi-king --branch OWNER_SELECTED_BRANCH
```

Source backup re-scans current files and **all reachable history before network
access**, verifies a single credential-free GitHub `origin` matching the expected
repository (no URL rewrites), and refuses divergent/ahead remote history. It
pushes only the approved commit with a normal fast-forward push: no automatic
add/commit, pull/reset, branch switching, or force. Ignored private data is not
backed up; secrets already in committed history block synchronization. Configure
credentials locally through the owner's normal credential manager. Backup
failure returns **2** but retains the validated local release; release refusal
returns **1**. Successful local promotion does not imply source/Pages freshness.
PRIVATE `latest.json` records separate promotion/backup results and times
without credential URLs; it does not pretend an unprobed serving URL is healthy.
Manifests record source SHA, validation time, and export hashes; Actions records
the backup deployment URL/status separately. Retained releases are not pruned.
A crash can leave `release.lock`; inspect its PID and any active run before
manually removing that exact lock. Never automatically clear another run's lock.

### GitHub Pages backup — owner activation required

`.github/workflows/public-static-backup.yml` runs only on approved `main` pushes
or manual dispatch at the default branch. It uses the same full local validator
and export policy, then uploads **only** `releases/SHA/public/` with pinned Pages
actions. No checkout, receipts, reports, models, or private runtime are uploaded.
Serialized runs never cancel an active deployment; failed validation/upload
does not replace the previous Pages release.
After a successful deployment, a bounded HTTPS check reads only the approved
backup's `buildinfo.json` (no redirects), requires its SHA to match this run, and
records the verified PUBLIC URL, served commit, and UTC time in the Actions step
summary. A failed freshness check fails verification explicitly: Pages may
already have deployed, no Pages rollback is claimed, and local releases are
unaffected.

Before enabling, the owner must verify repository Pages is **unused as primary
hosting**, uses Actions, has **no custom domain**, and can safely serve the
separate `https://jimlangford.github.io/12sgi-king/` backup. Read-only API
preflights before packaging and deployment refuse unknown settings, any CNAME,
or a different URL/build mode. No Pages settings are changed automatically.
If Pages already serves a primary/custom domain, **do not enable this workflow**;
select a separately coordinated backup hosting repository instead.

Configure protected environments `public-static-backup` and `github-pages`
with appropriate required owner reviewers/default-branch restrictions. Set
repository variables `PUBLIC_BACKUP_ENABLED=true`,
`PUBLIC_BACKUP_APPROVED_SHA=APPROVED_FULL_SHA`,
`PUBLIC_BACKUP_BASE_SHA=REVIEWED_BASE_SHA`, and
`PUBLIC_BACKUP_URL=https://jimlangford.github.io/12sgi-king/`.
Each changed release needs its reviewed SHA updated, then dispatch (a variable
update alone does not trigger a workflow). Keep unreviewed publishers from
updating these approvals. The current implementation does not establish that
Pages settings, credentials, required approvals, or owner scheduling are ready.
It performs no automatic primary-domain/traffic failover. Static backup cannot
replace private API, AI, Neo4j, owner controls, or databases.

## Repository role

GitHub is for:
- code storage
- branching and pull requests
- documentation and issue tracking
- support workflows and backups

GitHub is not the site host for the live system unless you intentionally choose to expose a public deployment.

## Notes

- Keep secrets and private data local.
- Do not commit tokens, model weights, or personal records.
- Prefer local-first deployment and private-only access.
