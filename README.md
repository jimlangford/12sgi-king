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
