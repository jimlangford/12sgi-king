# PR body for Draft PR from feature/govos-v2-foundation → automation/project-setup

Summary

This Draft PR introduces the govOS v2 skeletal structure to enable application development on top of the reviewed deployment and infra work in automation/project-setup. It does not touch deployment infra or secrets.

Infrastructure freeze

- The automation/project-setup branch contains the foundational deployment framework which should remain stable. Do not merge this PR until the application-level auth prototype and initial dashboard are reviewed.

Sprint plan

- See docs/GOVOS_V2_ROADMAP.md for sprint breakdown (auth, dashboard, tenant assistant, case mgmt, docs, UI, AI).

Acceptance checklist

- Tests pass
- Lint passes
- Health endpoints operational
- Accessibility reviewed
- Mobile responsive
- Documentation updated
- No secrets committed

No-merge warning

This PR is a Draft and should not be merged until core auth + dashboard prototype are complete and reviewed.

Security requirements

- No hard-coded Tailscale hosts
- Secrets provided via repo secrets or runtime environment
- Passwordless auth only (no local password storage)
