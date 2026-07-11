# ADR-001: Public/Private Architecture

Status: Proposed

Context
- The system must separate public presentation from private operations to protect internal services and data.

Decision
- WordPress is the canonical public presentation layer. QUAD OS is the private operating platform.

Consequences
- Public content lifecycle and SEO handled by WordPress. QUAD OS provides APIs and services not exposed directly to public.

Alternatives Considered
- Using a single monolithic public app — rejected due to security and operational concerns.

Future Evolution
- Revisit boundaries when multi-tenant public APIs are required.

---

**See also:** [QUAD_OS_MASTER_ARCHITECTURE.md](../QUAD_OS_MASTER_ARCHITECTURE.md) §2 (Public vs. private boundaries) | [WORDPRESS_PUBLIC_LAYER.md](../WORDPRESS_PUBLIC_LAYER.md)
