Deployment and rollback runbook

This document describes the releases + symlink deploy pattern, how to deploy, and how to rollback safely.

## govOS v2 backend (auth/tenant/documents/storage/ai) — where it actually runs

The SSH/rsync/systemd pattern below targets `staging-596d-monkshrooms.wpcomstaging.com`, a
WordPress.com-managed staging host. **Do not target the v2 FastAPI services at that host** — WP.com
managed hosting does not grant sudo/systemd, Docker, or the ability to run arbitrary long-lived
processes on custom ports, so the v2 services (`services/auth`, `services/tenant`,
`services/documents`, `services/storage`, `services/ai`) cannot run there. That deploy path stays
scoped to the WordPress/static side of the project.

The real deploy target for v2 is **king-server** (the Tailscale host `12sgianonymous`, tailnet
`tail760750.ts.net`) — the same private machine already running the workboard/self-heal automation.

**V2 deploy path: self-hosted GitHub Actions runner (not SSH/rsync)**

V2 uses a self-hosted runner installed on king-server, not SSH/rsync into king-server. The runner
polls GitHub over HTTPS; all execution runs locally on king-server with no inbound ports opened and
no Tailscale Funnel required for SSH, Docker, Ollama, logs, or system metrics.

Workflow: `.github/workflows/deploy-v2-king-server.yml`
Trigger: manual (`workflow_dispatch`) → Actions → "Deploy V2 to king-server" → Run workflow
Runner labels: `self-hosted`, `king-server`, `windows`

**To install the runner on king-server:**
1. Go to repo Settings → Actions → Runners → New self-hosted runner → Windows
2. Follow the on-screen PowerShell commands to download, configure, and start the runner
3. When prompted for labels, add: `king-server`
4. The runner registers itself with GitHub and begins polling — no inbound firewall changes needed

**Security boundary:**
- GitHub Actions triggers the work; king-server runner executes it locally
- No V2 service, Docker port, Ollama instance, log, or metric is exposed beyond Tailscale-private
- The public 12sgi.com deploy (publish.yml / deploy-to-server.yml) is completely separate
- Claim-based tenant authorization is enforced service-side from verified token claims (`sub`, `tenant_id`, `role`, `scopes`, `exp`, `iss`, `aud`); deployment must not re-enable client-tenant trust paths.

## Launch readiness (GO / NO-GO)

Treat launch as **NO-GO** until all items below are green and evidenced in private deploy logs:

- Backend sovereign checks:
  - auth claim enforcement (no client-tenant trust fallback),
  - tenant isolation checks,
  - service metadata consistency (`service`, `version`, `commit_sha`, `build_timestamp`, `environment`),
  - gpu-router readiness + queue health,
  - platform event durability (`/events`, `/events/dead-letters`),
  - rollback target + proof captured.
- Public/private boundary checks:
  - owner workflows remain private (`/go`, board, Tailscale paths),
  - public build outputs stay sanitized (`site/`, WordPress layer).

## Launch sequence (private-first)

1. **Stage 1 — PRIVATE validation on king-server**
   - Run deploy workflow dry run first, collect readiness/provenance evidence.
   - Allow controlled restart only if dry-run evidence is clean.
2. **Stage 2 — Limited audience rollout**
   - Monitor queue/event/error signals and owner console feeds.
3. **Stage 3 — Full public launch**
   - Proceed only after stability window passes with no tenant/auth/security regressions.

## Post-launch stabilization

- Daily verify: deploy provenance, queue health, dead letters, rollback readiness.
- Launch-week issues: patch fast with boundary-safe changes only (no private-path exposure).

For local development without the runner, see `docs/GOVOS_V2_LOCAL_DEV.md` for the uvicorn
commands and `docker-compose.v2.yml` for the supervised container stack.

## king-server V2 rollback (PRIVATE / BRIDGE)

Use this procedure for the private king-server V2 Docker stack (`docker-compose.v2.yml`) only.
This rollback preserves the existing named volumes, SQLite databases, Neo4j state, dispatch logs,
and queue evidence while redeploying an earlier known-good commit through the same self-hosted
runner path.

### Rollback triggers

Rollback is required when any of these conditions persists after a dry run or deploy attempt:

- mixed commit SHAs across V2 services
- persistent readiness failure
- authentication failure
- tenant data exposure
- queue corruption
- database damage
- core service outage

### 1. Identify the previously known-good commit

1. Open the most recent successful king-server V2 deployment evidence in:
   `C:\Users\12sgi\Documents\Claude\logs\v2-deploy\deploy-*.json`
2. Confirm all required services reported:
   - `environment = king-server-private`
   - the same `commit_sha`
   - healthy readiness/provenance responses
3. Record that commit SHA as the rollback target.
4. Cross-check the GitHub Actions run history for `.github/workflows/deploy-v2-king-server.yml` and
   the repo history so the rollback target is an actual previously known-good revision.

### 2. Preserve volumes, databases, and queue state

- Keep the existing named volumes intact:
  - `v2-db`
  - `v2-dispatch`
  - `v2-ollama`
  - `v2-neo4j-data`
  - `v2-neo4j-logs`
- Before rollback, inspect queue/dispatch state and capture it in deployment evidence:
  - `docker compose -f docker-compose.v2.yml logs --tail 200 gpu-router`
  - `docker compose -f docker-compose.v2.yml logs --tail 200 ai`
  - `docker compose -f docker-compose.v2.yml exec gpu-router python - <<'PY'` (or equivalent local
    inspection) to review queued/running jobs if the service is reachable
  - review `/data/dispatch/govos_v2_dispatch.jsonl` on the host if queue evidence needs a durable
    snapshot
- Repeat the same queue inspection immediately after rollback so before/after state is preserved.

### 3. Redeploy the previous commit with the same Compose file

1. Check out the previously known-good commit on the king-server runner worktree (or dispatch the
   workflow against that commit/ref).
2. Reuse the same `docker-compose.v2.yml`; do not substitute another compose definition during
   routine rollback.
3. Re-run `docker compose -f docker-compose.v2.yml config` before restart.
4. Re-run the private deploy workflow with `restart_services=true` only after the rollback target is
   confirmed.
5. Let `docker compose up -d --build --no-deps` refresh the stack in place so the named volumes and
   databases remain attached.

### 4. Verify health and provenance after rollback

After the rollback restart completes, verify every required V2 surface reports:

- readiness endpoint HTTP 200 where expected
- valid JSON response bodies
- non-empty `service`, `version`, `commit_sha`, `build_timestamp`, and `environment`
- `commit_sha` exactly equal to the rollback target commit
- `environment` exactly equal to `king-server-private`

Also verify `/api/v1/ready` on the health service reports aggregated dependency status with the same
rollback provenance and that `/go` / `board.html` are still present at the king-local path.

### 5. Capture logs and deployment evidence

- Save the workflow run URL, run number, rollback target commit SHA, and resulting deploy log JSON.
- Capture:
  - `docker compose -f docker-compose.v2.yml ps`
  - `docker compose -f docker-compose.v2.yml logs --tail 200 auth tenant documents storage ai health gpu-router`
  - any queue/dispatch snapshots gathered before and after rollback
- Preserve evidence in the same private log/evidence locations already used for king-server deploys.

### Routine rollback prohibitions

During a normal rollback, do **not** run any destructive volume cleanup commands:

- `docker compose down -v`
- manual Docker volume deletion
- `docker system prune`
- `docker volume prune`

Those commands risk queue loss, database loss, Neo4j damage, and destruction of rollback evidence.
Use them only in a separately authorized recovery operation, never as part of routine rollback.

Overview
- Deploys are written to: DEPLOY_PATH/releases/<timestamp>/
- The live site is the symlink: DEPLOY_PATH/current -> releases/<timestamp>
- The workflow keeps the last 3 releases; older releases are removed automatically.

Secrets required (already in repo)
- SSH_PRIVATE_KEY: private key for DEPLOY_USER
- DEPLOY_HOST: staging-596d-monkshrooms.wpcomstaging.com
- DEPLOY_USER: user to SSH as (e.g., deploy)
- DEPLOY_PATH: target base path on server (e.g., /var/www/elementlotus)
- DEPLOY_SSH_PORT: SSH port (22)
- POST_DEPLOY_BUILD: 'true' to run ./deploy-build.sh after rsync
- POST_DEPLOY_HEALTHCHECK_URL: optional healthcheck URL to verify deploy
- POST_ROLLBACK_HOOK: set to 'true' to run ./post-rollback.sh after rollback

How the deploy workflow works
1. Creates a new release folder on the remote host: $DEPLOY_PATH/releases/<timestamp>
2. Rsyncs the repository contents (excluding .git and .github) into that folder
3. Optionally runs ./deploy-build.sh inside the new release folder on the remote
4. Atomically updates the symlink $DEPLOY_PATH/current to point at the new folder
5. Keeps only the 3 most recent releases
6. Optionally performs a health check (POST_DEPLOY_HEALTHCHECK_URL)

How to run a deployment manually
- Go to Actions → "Deploy to elementlotus server" → Run workflow → choose branch (main) → Run

Server-side recommended files (install these on server)
- /var/www/elementlotus/releases/   (populated by workflow)
- /var/www/elementlotus/current -> symlink managed by workflow
- /var/www/elementlotus/CURRENT_RELEASE  (file containing current release id)
- /usr/local/bin/rollback.sh  (optional helper - sample provided in .github/deploy/rollback.sh)
- Optionally: post-rollback.sh in the release dir for custom hooks

Rollback options
A) Quick rollback (symlink switch) - recommended
- Use the GitHub Action: Actions → "Rollback deployed release on remote server" → Run workflow
  - Optionally pass target_release (folder name under releases/). If left blank, the workflow will pick the previous release.

B) Manual rollback via SSH
- List releases:
  ssh -p 22 deploy@staging-596d-monkshrooms.wpcomstaging.com "ls -1t /var/www/elementlotus/releases"
- Switch to a previous release:
  ssh -p 22 deploy@staging-596d-monkshrooms.wpcomstaging.com "ln -sfn /var/www/elementlotus/releases/<previous> /var/www/elementlotus/current && echo '<previous>' > /var/www/elementlotus/CURRENT_RELEASE && sudo systemctl reload nginx"

C) Revert code via Git (safer for code-only rollbacks)
- On your local machine:
  git checkout main
  git pull origin main
  git revert -m 1 <merge_commit_sha>
  git push origin main
- Then run the deploy workflow or wait for it to run on push.

D) Database/content rollbacks (WordPress)
- For database restore, use your hosting panel snapshot or run a mysql restore on the server.
- For single post/page restore, use WP Admin → Post → Revisions

Post-rollback validation
- Visit the site URL and confirm it returns 200 OK
- Run the healthcheck endpoint if configured
- Check application logs and webserver status

Automating rollback safely
- You can use the provided rollback workflow (.github/workflows/rollback.yml) which will run on GitHub-hosted runners and SSH into the server to switch releases.
- Protect the workflow by requiring approvals or limiting who can dispatch it (use repo permissions for Actions).

Notes & cautions
- The deploy workflow executes remote commands via SSH. Ensure the DEPLOY_USER has permission to write to DEPLOY_PATH and to create symlinks.
- Keep backups of your DB before running migrations. Use maintenance mode for complex deploys that include DB schema changes.
- If you need zero-downtime for uploads or shared assets, ensure they are stored in DEPLOY_PATH/shared and symlinked into each release (you can extend deploy-build.sh to create shared symlinks).

If you want, I can:
- Add support for shared directories (uploads, caches) to the deploy workflow and deploy-build.sh
- Add a protected rollback workflow (require approvals) so rollbacks cannot be run by anyone
- Add a nightly backup job that stores DB dumps to S3 (or similar)
