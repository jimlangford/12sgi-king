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

Run the same non-deploying test gate used by GitHub on Python 3.11 or 3.12:

```bash
python -m venv .venv
# Linux/macOS:
source .venv/bin/activate
# Windows PowerShell instead: .venv\Scripts\Activate.ps1
python -m pip install -r requirements-ci.txt
python tools/local_ci.py
```

After the one-time dependency installation, this gate needs no GitHub connection,
Docker, Neo4j, Ollama, or external credentials. It runs the V2 and Studio asset
tests with temporary databases and loopback services, returns nonzero on failure,
and keeps coverage scratch files outside the repository. Add
`--junitxml=/path/to/results.xml` to save a report. It never deploys.

Run the accessibility check on every generated public page (Node 22 and Chrome, no network needed):

```bash
cd tools/a11y && npm ci --ignore-scripts
# 1. Build the PUBLIC site into a scratch folder. HOME, USERPROFILE, HOMEDRIVE, HOMEPATH, APPDATA and
#    LOCALAPPDATA must ALL point at an empty folder, or the build can read your private project and write
#    your private King mirror. See docs/CI_OWNER_ACTIONS.md section 4. KA_SITE=tools/a11y/.work/site
# 2. Scan (set CHROME_BIN to your Chrome if it is not at the default path):
npm test                      # scanner self-tests, including the gate rules
npm run scan                  # every page; A11Y_SHARD=2/4 scans one quarter
npm run scan:propose          # writes .work/proposed-baseline.json ONLY; inspect it, then copy it by hand
```

The scan fails on any finding not in `tools/a11y/baseline.json`, on any baseline entry that is no longer
observed (fixed findings must be pruned), and on pages the build no longer generates. The baseline is a
regression budget for existing debt, not a conformance claim. Owner-only actions and open decisions are in
`docs/CI_OWNER_ACTIONS.md`.

Run the local deployment pipeline on your local system, not GitHub Actions:

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
