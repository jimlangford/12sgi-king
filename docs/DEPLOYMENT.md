Deployment and runner notes

Secrets required (already expected in your repo):
- SSH_PRIVATE_KEY: private key for the DEPLOY_USER
- DEPLOY_HOST: elementlotus host (staging-596d-monkshrooms.wpcomstaging.com)
- DEPLOY_USER: user to SSH as (e.g., deploy)
- DEPLOY_PATH: target webroot (e.g., /var/www/elementlotus)
- DEPLOY_SSH_PORT: SSH port (22)
- WP_URL, WP_USER, WP_APP_PASSWORD (if using App Passwords) OR JETPACK_TOKEN and JETPACK_SITE_ID
- POST_DEPLOY_BUILD: set to 'true' if you want the runner to invoke ./deploy-build.sh on the remote host after rsync

Runners
- Workflows use GitHub-hosted runners by default. If your server is accessible from the public internet over SSH (port 22) this will work.
- If you later want the Actions to run inside your Tailnet, install a self-hosted runner on your server.

Deploy notes
- The deploy workflow uses rsync and excludes .git and .github by default.
- For atomic deploy and zero-downtime, place a deploy-build.sh script on the server that moves files into place safely. The workflow will call it if POST_DEPLOY_BUILD is 'true'.
