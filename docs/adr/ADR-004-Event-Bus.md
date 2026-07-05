# ADR-004: Event Bus

Status: Proposed

Context
- Services need an asynchronous integration channel for cross-cutting events.

Decision
- Implement an append-only Event Bus with typed events, idempotency, retries, and an audit log.

Consequences
- Promotes decoupling and replayability of histories.

Alternatives Considered
- Point-to-point webhooks — rejected due to reliability and replay limitations.

Future Evolution
- Evaluate Kafka or cloud-native event streaming solutions as scale demands.
