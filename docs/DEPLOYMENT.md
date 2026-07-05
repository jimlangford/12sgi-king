Deployment and rollback runbook

This document describes the releases + symlink deploy pattern, how to deploy, and how to rollback safely.

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
