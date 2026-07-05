# Tailscale Integration Validation

This document describes the validation steps reviewers should perform for the Tailscale integration.

Continue to keep everything on the feature branch: automation/project-setup. Do NOT merge into main until review is complete.

Steps

1) Verify tailscaled is active
   - SSH to the homepage server (or a machine with Tailscale access) and run:
     sudo systemctl status tailscaled
     tailscale status
   - Confirm tailscaled is running and peers are visible.

2) Verify MagicDNS resolution (if you use MagicDNS)
   - From the homepage server:
     ping -c1 <surface-hostname>
   - Or confirm tailscale status shows the hostnames.

3) Verify ACL permissions
   - Confirm your Tailscale ACLs allow the homepage server to connect to surface hosts on port 8782.

4) Validate healthchecks
   - Ensure .env (or repository variable SURFACES_LIST) contains the host list.
   - From repo root, run:
     chmod +x scripts/check_surfaces.sh
     SURFACES_LIST="surfaceA=100.101.102.103:8782,surfaceB=100.101.102.104:8782" ./scripts/check_surfaces.sh
   - Expected: script prints per-surface OK lines and exits 0.

5) Confirm homepage proxy routes
   - Review docs/nginx-tailnet-proxy.example.conf for mapping of /surfaceA/ and /surfaceB/
   - Confirm the homepage server reverse-proxy is configured similarly in your test environment.

6) Confirm rollback still succeeds
   - Deploy a test release (on the feature branch) and then run the rollback workflow (leave target blank to pick previous release) to verify the symlink switch works and the previous release becomes current.

Logging & expected outputs

- The healthcheck script logs in this format:
  [2026-07-05T02:00:00Z] Checking Tailscale...
  Checking surfaceA (100.x.y.z:8782) ... OK
  [2026-07-05T02:00:01Z] Checking surfaceA... ✓ OK
  Checking surfaceB (100.a.b.c:8782) ... FAILED
  [2026-07-05T02:00:02Z] Checking surfaceB... ✗ FAILED
  -> surfaceB unreachable at http://100.a.b.c:8782/
  [2026-07-05T02:00:02Z] One or more surfaces are unreachable. Exiting with failure.

If any surface fails, do not merge. Investigate Tailscale ACLs, host status, and firewall rules.
