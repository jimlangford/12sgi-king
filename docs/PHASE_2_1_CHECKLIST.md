# Phase 2.1 Checklist

Files changed on branch: feature/govos-v2-foundation

Manual verification steps for you (admin-run required for some)
1. Run label-by-path workflow (dry_run=true) on PR #313 and paste run id/logs.
2. Run label-by-path workflow (dry_run=false) if you want labels applied; paste run id/logs.
3. Run wp-publish workflow in a safe test mode against a staging WordPress site (ensure credentials are staging-only).
4. Confirm deploy/rollback SSH secrets are rotated and stored appropriately.

Deliverables produced
- workflow audit report
- security audit report
- architecture gap report
- technical debt report
- ENGINEERING_STANDARDS.md, SERVICE_REGISTRY.md, EVENT_BUS.md
- ADRs and PLATFORM_PRINCIPLES.md
- CODEOWNERS and QUAD_OS_MASTER_ARCHITECTURE.md updated

