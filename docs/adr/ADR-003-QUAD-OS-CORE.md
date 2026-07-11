# ADR-003: QUAD OS Core

Status: Proposed

Context
- Platform core services need to be clearly defined and discoverable.

Decision
- Define a core set of services: Auth, RBAC, Event Bus, Audit Log, Health, Config, Notifications.

Consequences
- All modules will reuse these services rather than reimplementing functionality.

Alternatives Considered
- Let each module implement its own auth/notifications — rejected to avoid fragmentation.

Future Evolution
- Expand core services with scale and multi-region capabilities.

---

**See also:** [QUAD_OS_MASTER_ARCHITECTURE.md](../QUAD_OS_MASTER_ARCHITECTURE.md) §3 (Module registry) | [SERVICE_REGISTRY.md](../SERVICE_REGISTRY.md) | [EVENT_BUS.md](../EVENT_BUS.md)
