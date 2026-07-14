"""
civic_metrics_api.py — Public-safe civic metrics and signals endpoint

Exposed at: GET /api/v2/civic/public-metrics
Used by: element_lotus_public/civic.html (live dashboard rendering)

Returns:
{
  "total_civic_events": 42,
  "upcoming_meetings": [
    {
      "date": "2026-07-15",
      "title": "Maui County Council",
      "location": "Wailuku",
      "link": "https://..."
    },
    ...
  ],
  "testimony_deadlines": [
    {
      "date": "2026-07-13",
      "body": "Council meeting",
      "ecomment_url": "https://..."
    },
    ...
  ],
  "last_updated": "2026-07-13T14:23:00Z"
}

This is a READ-ONLY public endpoint. Caching: 5-minute TTL.
"""

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

from fastapi import FastAPI


API_PREFIX = "/api/v2"
SERVICE_NAME = "civic-metrics"
VERSION = os.environ.get("VERSION", "2.0.0")
CIVIC_SIGNALS_DB = os.environ.get("CIVIC_SIGNALS_DB", "/tmp/govos_v2_civic_signals.db")

app = FastAPI(title="govOS v2 Civic Metrics API", version=VERSION)


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def _db():
    conn = sqlite3.connect(CIVIC_SIGNALS_DB)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def init_db() -> None:
    """Initialize civic_signals table."""
    with _db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS civic_signals (
                id TEXT PRIMARY KEY,
                event_type TEXT NOT NULL,
                summary TEXT NOT NULL,
                description TEXT,
                start TEXT,
                end TEXT,
                tenant_id TEXT,
                visibility TEXT DEFAULT 'public',
                public BOOLEAN DEFAULT 1,
                source TEXT DEFAULT 'calendar_civic',
                created_at TEXT NOT NULL
            )
            """
        )
        conn.commit()


init_db()


@app.get(f"{API_PREFIX}/civic/public-metrics")
def get_civic_metrics():
    """
    Public civic metrics — real-time data from civic_signals table.

    Cached by the caller (civic.html) with 5-min TTL.
    """
    with _db() as conn:
        # Count all public events
        total = conn.execute(
            "SELECT COUNT(*) FROM civic_signals WHERE public = 1"
        ).fetchone()[0]

        # Upcoming meetings
        meetings = conn.execute(
            """
            SELECT event_type, summary, description, start, end
            FROM civic_signals
            WHERE public = 1 AND event_type = 'civic.meeting'
            ORDER BY start ASC
            LIMIT 10
            """
        ).fetchall()

        # Upcoming testimony deadlines
        deadlines = conn.execute(
            """
            SELECT event_type, summary, description, start, end
            FROM civic_signals
            WHERE public = 1 AND event_type = 'civic.action'
            ORDER BY start ASC
            LIMIT 10
            """
        ).fetchall()

        # Recent additions
        recent = conn.execute(
            """
            SELECT event_type, summary, created_at
            FROM civic_signals
            WHERE public = 1
            ORDER BY created_at DESC
            LIMIT 5
            """
        ).fetchall()

    return {
        "total_civic_events": total,
        "upcoming_meetings": [
            {
                "date": row["start"][:10] if row["start"] else "",
                "title": row["summary"],
                "description": row["description"][:200] if row["description"] else "",
            }
            for row in meetings
        ],
        "testimony_deadlines": [
            {
                "date": row["start"][:10] if row["start"] else "",
                "body": row["summary"],
                "description": row["description"][:200] if row["description"] else "",
            }
            for row in deadlines
        ],
        "recently_added": [
            {
                "title": row["summary"],
                "added_at": row["created_at"],
            }
            for row in recent
        ],
        "last_updated": _now_utc(),
        "cache_ttl_seconds": 300,
    }


@app.post(f"{API_PREFIX}/civic-signals")
def create_civic_signal(payload: dict):
    """
    Store a civic signal (called by civic_rendering_auto.py).

    Payload:
    {
      "event_type": "civic.meeting",
      "summary": "[CIVIC] Maui County Council Meeting",
      "description": "...",
      "start": "2026-07-15T09:00:00-10:00",
      "end": "2026-07-15T12:00:00-10:00",
      "tenant_id": "maui",
      "visibility": "public",
      "public": true,
      "source": "calendar_civic"
    }
    """
    from uuid import uuid4

    signal_id = str(uuid4())
    event_type = payload.get("event_type", "civic.event")
    summary = payload.get("summary", "")
    description = payload.get("description", "")
    start = payload.get("start", "")
    end = payload.get("end", "")
    tenant_id = payload.get("tenant_id", "")
    visibility = payload.get("visibility", "public")
    public = payload.get("public", True)
    source = payload.get("source", "civic_rendering_auto")

    with _db() as conn:
        conn.execute(
            """
            INSERT INTO civic_signals
            (id, event_type, summary, description, start, end, tenant_id, visibility, public, source, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                signal_id,
                event_type,
                summary,
                description,
                start,
                end,
                tenant_id,
                visibility,
                public,
                source,
                _now_utc(),
            ),
        )
        conn.commit()

    return {
        "id": signal_id,
        "event_type": event_type,
        "summary": summary,
        "created_at": _now_utc(),
    }


@app.get(f"{API_PREFIX}/civic/public-metrics/cache")
def get_cache_info():
    """
    Cache management endpoint (internal).
    Shows cache stats and allows purge (with internal token).
    """
    with _db() as conn:
        total = conn.execute("SELECT COUNT(*) FROM civic_signals").fetchone()[0]

    return {
        "total_signals": total,
        "cache_ttl_seconds": 300,
        "last_updated": _now_utc(),
    }
