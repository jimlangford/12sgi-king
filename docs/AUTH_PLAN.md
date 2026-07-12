# Authentication Plan (overview)

Goals
- Passwordless-first approach
- Support passkeys + major OAuth providers for convenience
- No local password storage

Phases
1. Design auth API (token issuance, refresh tokens, JWKS)
2. Implement passkeys registration and login flows
3. Add social OAuth (Google, Apple, Microsoft)
4. Add email magic links as fallback
5. Harden sessions, rotate keys, and provide developer test utilities

---

**See also:** [QUAD_OS_MASTER_ARCHITECTURE.md](QUAD_OS_MASTER_ARCHITECTURE.md) §7 (Security model) | [ADR-005-Authentication-Strategy.md](adr/ADR-005-Authentication-Strategy.md) | `services/auth/`
