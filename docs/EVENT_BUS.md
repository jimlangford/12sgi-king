# Event Bus

Overview
- The Event Bus is an append-only, typed event stream used for cross-service communication and integration.

Event naming
- Use reverse domain style with purpose: <domain>.<entity>.<action>
  - Examples: quados.case.created, quados.user.registered, govos.case.status_changed

Payload schema
- All events must include:
  - id: UUID (event id)
  - type: event type (string)
  - version: semantic version for event schema (e.g., 1.0)
  - timestamp: ISO-8601 UTC
  - producer: service name
  - correlation_id: optional, used to trace across requests
  - data: event payload object (schema versioned)

Versioning
- Event consumers must support unknown additional fields and handle version mismatches.
- Use event.version to coordinate changes. When incompatible changes required, publish a new event type or bump major.

Producers
- Producers should publish events as soon as state change is durable.
- Producers must include provenance and idempotency keys when re-publishing.

Consumers
- Consumers must be idempotent and tolerant of replays.
- Consumers should validate event schema and raise a dead-letter for unparseable events.

Retries and guarantees
- Use durable queues with at-least-once delivery.
- Retries should be exponential with a capped backoff and a dead-letter queue on final failure.

Idempotency
- Events must include an idempotency key where operations are not inherently idempotent.

Auditing
- All events are stored in the Audit Log with full payloads, producer metadata, and delivery attempts.

Security
- Events carrying PII should be encrypted or redacted as appropriate.
- Event authentication should use service tokens with RBAC controls.
