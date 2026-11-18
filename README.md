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
