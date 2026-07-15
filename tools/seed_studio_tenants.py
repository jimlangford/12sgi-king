#!/usr/bin/env python3
"""Seed the tenant service database with creative studio tenant records from tenant_registry.json.

This script:
1. Reads tenant_registry.json creative_tenants[]
2. Creates studio_projects table in govos_v2_tenant.db
3. Inserts one record per creative tenant
4. Reports on seeding

Run once on startup or after adding new tenants to the registry.
"""
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
REGISTRY_PATH = REPO / "tenant_registry.json"
DB_PATH = REPO / "data" / "db" / "govos_v2_tenant.db"


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def seed_studio_tenants() -> int:
    """Load registry and seed studio projects into tenant DB. Returns count of records seeded."""
    if not REGISTRY_PATH.exists():
        print(f"ERROR: {REGISTRY_PATH} not found", file=sys.stderr)
        return 0

    registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    creative = registry.get("creative_tenants", [])

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    # Create table if missing
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS studio_projects (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            kind TEXT,
            quadrant TEXT,
            render_register TEXT,
            status TEXT,
            seeded_at TEXT NOT NULL
        )
        """
    )

    now = _now_utc()
    seeded = 0

    for tenant in creative:
        tid = tenant.get("id")
        if not tid:
            continue
        try:
            conn.execute(
                """
                INSERT OR REPLACE INTO studio_projects
                    (id, name, kind, quadrant, render_register, status, seeded_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    tid,
                    tenant.get("name", tid),
                    tenant.get("kind", "other"),
                    tenant.get("quadrant", "creative"),
                    tenant.get("render_register", ""),
                    tenant.get("status", ""),
                    now,
                ),
            )
            seeded += 1
        except sqlite3.Error as e:
            print(f"WARN: Failed to seed {tid}: {e}", file=sys.stderr)

    conn.commit()
    conn.close()
    return seeded


if __name__ == "__main__":
    count = seed_studio_tenants()
    print(f"✓ Seeded {count} studio tenants into {DB_PATH}")
