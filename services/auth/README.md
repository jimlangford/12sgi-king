# Auth service

Purpose

Authentication and authorization services. Focus on passwordless and modern auth flows (Passkeys, OAuth providers, Magic Links). No local password storage.

Ownership

- Security / Auth engineering

Next steps

- Design auth API (token issuance, JWKS, session management)
- Plan credential storage for passkeys (relying on secure hardware-backed attestation as appropriate)
- Implement developer-friendly test harness (local test clients)

Security notes

- Do not commit secrets. Use runtime environment or secret manager.
