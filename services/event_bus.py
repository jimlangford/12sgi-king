"""
Platform event bus — append-only SQLite-backed event log.

This is the durable transport layer described in docs/EVENT_BUS.md and
ADR-004-Event-Bus. It is separate from the GPU router's gpu_events table
(which is engine-specific) and provides a platform-level audit trail for
cross-service events (workboard transitions, auth events, case state changes).

Design principles (per EVENT_BUS.md):
  - Append-only: events are never deleted, only read and optionally archived.
  - Typed, versioned: every event carries a type string and schema_version.
  - Idempotency: callers may supply an idempotency_key; duplicate keys are
    silently ignored.
  - Never raises: publish_event() swallows all exceptions so callers are
    never blocked by event-bus unavailability (at-least-once delivery intent;
    in-process availability is still best-effort for the local DB).
  - Dead-letter: payloads over MAX_PAYLOAD_BYTES are stored as dead-letter
    events with a truncated reference instead of being silently dropped.

Environment:
  PLATFORM_EVENTS_DB — path to the SQLite file (default: .platform_events.db
  next to this module). Override in tests or Docker.
"""

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

# ── Configuration ─────────────────────────────────────────────────────────────

_DEFAULT_DB = Path(__file__).resolve().parent.parent / ".platform_events.db"
_DB_PATH = Path(os.environ.get("PLATFORM_EVENTS_DB") or _DEFAULT_DB)

MAX_PAYLOAD_BYTES = 65_536  # 64 KB; oversized payloads go to dead-letter
SCHEMA_VERSION = "1.0"


# ── Internal helpers ──────────────────────────────────────────────────────────

@contextmanager
def _db():
    conn = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    _ensure_schema(conn)
    try:
        yield conn
    finally:
        conn.close()


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS platform_events (
            id               TEXT PRIMARY KEY,
            schema_version   TEXT NOT NULL DEFAULT '1.0',
            event_type       TEXT NOT NULL,
            producer         TEXT NOT NULL,
            entity_id        TEXT,
            correlation_id   TEXT,
            idempotency_key  TEXT,
            payload_json     TEXT NOT NULL DEFAULT '{}',
            ts               TEXT NOT NULL
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_platform_events_type ON platform_events (event_type)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_platform_events_producer ON platform_events (producer)"
    )
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_platform_events_idempotency "
        "ON platform_events (producer, idempotency_key) "
        "WHERE idempotency_key IS NOT NULL"
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS platform_dead_letters (
            id              TEXT PRIMARY KEY,
            event_type      TEXT NOT NULL,
            producer        TEXT NOT NULL,
            entity_id       TEXT,
            reason          TEXT NOT NULL,
            payload_ref     TEXT,
            ts              TEXT NOT NULL
        )
        """
    )
    conn.commit()


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Public API ────────────────────────────────────────────────────────────────

def publish_event(
    event_type: str,
    producer: str,
    payload: dict | None = None,
    entity_id: str | None = None,
    correlation_id: str | None = None,
    idempotency_key: str | None = None,
) -> str | None:
    """Append one event to the platform event log.

    Returns the event id on success, or None if the event was silently
    dropped (duplicate idempotency key) or if the bus is unavailable.
    Never raises.

    Args:
        event_type:      Reverse-domain event name, e.g. 'workboard.job.created'.
        producer:        Service/module name, e.g. 'v2_workboard'.
        payload:         Arbitrary dict (must be JSON-serialisable).
        entity_id:       Optional primary entity the event concerns (job id, case id…).
        correlation_id:  Optional request/trace correlation id.
        idempotency_key: Optional key; second call with the same producer+key is a no-op.
    """
    try:
        payload_json = json.dumps(payload or {}, separators=(",", ":"))
        if len(payload_json.encode()) > MAX_PAYLOAD_BYTES:
            _send_dead_letter(
                event_type=event_type,
                producer=producer,
                entity_id=entity_id,
                reason="payload_too_large",
                payload_ref=f"payload size={len(payload_json)} bytes",
            )
            return None

        event_id = str(uuid4())
        with _db() as conn:
            try:
                conn.execute(
                    """
                    INSERT INTO platform_events
                        (id, schema_version, event_type, producer, entity_id,
                         correlation_id, idempotency_key, payload_json, ts)
                    VALUES (?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        event_id,
                        SCHEMA_VERSION,
                        event_type,
                        producer,
                        entity_id,
                        correlation_id,
                        idempotency_key,
                        payload_json,
                        _iso_now(),
                    ),
                )
                conn.commit()
                return event_id
            except sqlite3.IntegrityError:
                # Duplicate idempotency key — silent no-op, not an error.
                return None
    except Exception:
        return None


def get_recent_events(
    limit: int = 50,
    event_type: str | None = None,
    producer: str | None = None,
) -> list[dict]:
    """Return up to *limit* recent events, newest first.

    Filters:
        event_type: exact match on event_type column.
        producer:   exact match on producer column.
    """
    try:
        clauses: list[str] = []
        params: list = []
        if event_type:
            clauses.append("event_type = ?")
            params.append(event_type)
        if producer:
            clauses.append("producer = ?")
            params.append(producer)
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        params.append(max(1, min(limit, 1000)))
        with _db() as conn:
            rows = conn.execute(
                f"""
                SELECT id, schema_version, event_type, producer, entity_id,
                       correlation_id, idempotency_key, payload_json, ts
                FROM platform_events
                {where}
                ORDER BY ts DESC
                LIMIT ?
                """,
                params,
            ).fetchall()
            return [
                {
                    "id": r["id"],
                    "schema_version": r["schema_version"],
                    "event_type": r["event_type"],
                    "producer": r["producer"],
                    "entity_id": r["entity_id"],
                    "correlation_id": r["correlation_id"],
                    "payload": json.loads(r["payload_json"] or "{}"),
                    "ts": r["ts"],
                }
                for r in rows
            ]
    except Exception:
        return []


def get_dead_letters(limit: int = 20) -> list[dict]:
    """Return recent dead-letter events (oversized or undeliverable payloads)."""
    try:
        with _db() as conn:
            rows = conn.execute(
                """
                SELECT id, event_type, producer, entity_id, reason, payload_ref, ts
                FROM platform_dead_letters
                ORDER BY ts DESC
                LIMIT ?
                """,
                (max(1, min(limit, 200)),),
            ).fetchall()
            return [dict(r) for r in rows]
    except Exception:
        return []


def _send_dead_letter(
    event_type: str,
    producer: str,
    entity_id: str | None,
    reason: str,
    payload_ref: str | None = None,
) -> None:
    """Internal: record a dead-letter entry. Never raises."""
    try:
        with _db() as conn:
            conn.execute(
                """
                INSERT INTO platform_dead_letters
                    (id, event_type, producer, entity_id, reason, payload_ref, ts)
                VALUES (?,?,?,?,?,?,?)
                """,
                (str(uuid4()), event_type, producer, entity_id, reason, payload_ref, _iso_now()),
            )
            conn.commit()
    except Exception:
        pass
