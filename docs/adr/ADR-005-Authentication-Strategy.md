# ADR-005: Authentication Strategy

Status: Proposed

Context
- Need a modern, secure, passwordless-first authentication strategy.

Decision
- Passwordless by default (passkeys, magic links). Support major OAuth providers as convenience.
- No local passwords stored.

Consequences
- Reduced user-password risk surface; requires additional integration effort for passkeys.

Alternatives Considered
- Continue local password storage — rejected for security reasons.

Future Evolution
- Add support for enterprise identity providers (SSO) with SCIM user provisioning.
