# Engineering Standards

This document defines repository-wide standards for development, CI/CD, branching, reviews, security, and testing.

Branch strategy
- main: production-ready only. Protected. All merges require PR review and passing status checks.
- automation/project-setup: deployment & infra integration branch (kept stable). Feature branches may base from this branch for infra integration work.
- feature/*: feature work. Branch from automation/project-setup or main as appropriate.
- release/*: release stabilization branches.

PR strategy
- One feature per PR. Keep small and focused.
- Draft PRs allowed for early feedback; include checklist of required items.
- PR title format: <scope>: <short summary> (e.g., auth: add passkey registration)
- Require at least one codeowner review and passing CI checks.

Release strategy
- Publish releases via GitHub Releases with release.json metadata.
- Release posts to WordPress default to draft; publishing must be an explicit action.
- Semantic versioning for QUAD OS platform (e.g., 0.2.0-alpha). WordPress content releases are independent.

Workflow conventions
- All workflows default to safe behavior (mutations default to dry-run unless explicitly requested).
- Use least-privilege permissions. Prefer job-level permissions over workflow-level when possible.
- Avoid printing secrets or tokens in logs. Use masked secrets and do not echo them.
- External HTTP calls must check for non-2xx responses and fail safely or log non-fatal warnings.
- Pin actions to a stable minor version (e.g., actions/checkout@v4) and prefer maintained actions.

Coding standards
- Frontend: TypeScript + Next.js, ESLint, Prettier, Tailwind CSS.
- Backend: Python + FastAPI, Black, Flake8, MyPy where appropriate.
- Tests: unit + integration where appropriate. Test coverage goals to be defined per service.

Naming conventions
- Packages: kebab-case (packages/ui)
- Services: lower-hyphen (services/auth)
- Internal events: dot.delimited.namespaced (event.user.created)

Service ownership
- Each service must list an owner in SERVICE_REGISTRY.md and include a service-level README and health endpoints.

Documentation requirements
- Every new service or module must add a README in its folder describing purpose, owner, API, health endpoints, and next steps.

Review requirements
- Code changes that affect security, deployment, or infra require at least two reviewers and an explicit security review.

Security checklist
- Do not commit secrets; use repository secrets or an external secrets manager.
- Run secret-scan on PRs (ci-secret-scan workflow).
- Rotate keys and maintain JWKS for signing keys.
- Passwordless-first auth (no local password storage.)

Testing requirements
- Unit tests required for all libraries/packages.
- Integration tests required for service APIs.
- Accessibility checks for UI changes (WCAG 2.2 AA target).

Appendix: enforcement and exceptions
- Exceptions must be documented in PRs and approved by owners.
