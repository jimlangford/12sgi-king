"""services/studio_assets/app/storyboard_api.py — Phase 2.2 storyboard production records.

Provides soft lock, archive, restore, and revision management for storyboard assets.

Lock semantics
  Locked storyboards cannot have prompt, image, camera spec, or continuity metadata
  modified or overwritten. Lock is a toggle; archived state is independent.
  Archiving preserves lock state and all references. Restoring returns both lock and
  active state to what they were before archival.

Archive semantics
  Archive is soft and audited. The asset, provenance, and all project references are
  preserved. The storyboard disappears from active views but is accessible in the
  archive view and via direct ID. Restoration is always possible.

Revision semantics
  Editing a locked storyboard creates a new unlocked revision cloned from the original.
  The original remains locked and immutable.

Auth: all mutation endpoints require the owner role (STUDIO_STORYBOARD_REQUIRE_AUTH
controls whether auth is enforced; defaults to the value of STUDIO_ASSETS_REQUIRE_AUTH).
"""

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

# ── Config ─────────────────────────────────────────────────────────────────────
STORYBOARD_DB_PATH = os.environ.get(
    "STUDIO_STORYBOARD_DB_PATH",
    str(Path(__file__).resolve().parents[3] / "data" / "storyboard.db"),
)
_REQUIRE_AUTH = os.environ.get(
    "STUDIO_STORYBOARD_REQUIRE_AUTH",
    os.environ.get("STUDIO_ASSETS_REQUIRE_AUTH", "0"),
) == "1"

router = APIRouter(prefix="/api/v2/media/storyboards", tags=["storyboard"])


# ── DB ─────────────────────────────────────────────────────────────────────────

def _init_db(path: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with sqlite3.connect(path, check_same_thread=False) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS studio_storyboards (
                id               TEXT PRIMARY KEY,
                production_id    TEXT NOT NULL DEFAULT '',
                scene_id         TEXT NOT NULL DEFAULT '',
                shot_id          TEXT NOT NULL DEFAULT '',
                revision         INTEGER NOT NULL DEFAULT 1,
                parent_id        TEXT,
                prompt           TEXT NOT NULL DEFAULT '',
                camera_spec      TEXT NOT NULL DEFAULT '{}',
                continuity_meta  TEXT NOT NULL DEFAULT '{}',
                engine           TEXT NOT NULL DEFAULT 'kandinsky5',
                image_hash       TEXT NOT NULL DEFAULT '',
                image_uri        TEXT NOT NULL DEFAULT '',
                provenance_hash  TEXT NOT NULL DEFAULT '',
                source_refs      TEXT NOT NULL DEFAULT '[]',
                used_by          TEXT NOT NULL DEFAULT '[]',
                status           TEXT NOT NULL DEFAULT 'active',
                locked           INTEGER NOT NULL DEFAULT 0,
                archived         INTEGER NOT NULL DEFAULT 0,
                archived_at      TEXT,
                archived_by      TEXT,
                archive_reason   TEXT,
                created_at       TEXT NOT NULL,
                updated_at       TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS storyboard_audit (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                storyboard_id TEXT NOT NULL,
                event_type  TEXT NOT NULL,
                previous    TEXT,
                current     TEXT,
                actor       TEXT NOT NULL DEFAULT 'owner',
                reason      TEXT,
                timestamp   TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_sb_production
                ON studio_storyboards(production_id);
            CREATE INDEX IF NOT EXISTS idx_sb_archived
                ON studio_storyboards(archived);
            CREATE INDEX IF NOT EXISTS idx_sb_audit_sbid
                ON storyboard_audit(storyboard_id);
            """
        )
        conn.commit()


def _db(path: str | None = None) -> sqlite3.Connection:
    p = path or STORYBOARD_DB_PATH
    _init_db(p)
    conn = sqlite3.connect(p, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def _conn(path: str | None = None):
    c = _db(path)
    try:
        yield c
        c.commit()
    finally:
        c.close()


# ── Helpers ─────────────────────────────────────────────────────────────────────

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row_to_dict(row: sqlite3.Row) -> dict:
    d = dict(row)
    for key in ("camera_spec", "continuity_meta", "source_refs", "used_by"):
        try:
            d[key] = json.loads(d[key])
        except (json.JSONDecodeError, TypeError, KeyError):
            pass
    d["locked"] = bool(d.get("locked"))
    d["archived"] = bool(d.get("archived"))
    return d


def _audit(conn: sqlite3.Connection, storyboard_id: str, event_type: str,
           previous, current, actor: str, reason: str | None = None) -> None:
    conn.execute(
        "INSERT INTO storyboard_audit "
        "(storyboard_id, event_type, previous, current, actor, reason, timestamp) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (storyboard_id, event_type,
         json.dumps(previous), json.dumps(current),
         actor, reason or "", _now()),
    )


def _require_owner(request: Request) -> str:
    if not _REQUIRE_AUTH:
        return "owner"
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer ") and not auth.startswith("Token "):
        raise HTTPException(status_code=401, detail={"error": "unauthorized"})
    token = auth.split(" ", 1)[1]
    if not token:
        raise HTTPException(status_code=401, detail={"error": "unauthorized"})
    return "owner"


def _get_storyboard_or_404(conn: sqlite3.Connection, storyboard_id: str) -> dict:
    row = conn.execute(
        "SELECT * FROM studio_storyboards WHERE id = ?", (storyboard_id,)
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail={"error": "storyboard_not_found", "id": storyboard_id})
    return _row_to_dict(row)


# ── Pydantic models ────────────────────────────────────────────────────────────

class CreateStoryboardRequest(BaseModel):
    production_id: str
    scene_id: str
    shot_id: str
    prompt: str
    engine: str = "kandinsky5"
    camera_spec: dict = {}
    continuity_meta: dict = {}
    image_hash: str = ""
    image_uri: str = ""
    provenance_hash: str = ""
    source_refs: list = []
    used_by: list = []


class LockToggleRequest(BaseModel):
    locked: bool
    actor: str = "owner"
    reason: str = "owner_toggle"


class ArchiveRequest(BaseModel):
    actor: str = "owner"
    reason: str = "archived"
    preserve_lock: bool = True


class RestoreRequest(BaseModel):
    actor: str = "owner"
    reason: str = "restored"


class NewRevisionRequest(BaseModel):
    actor: str = "owner"
    reason: str = "revision"


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("", status_code=201)
def create_storyboard(body: CreateStoryboardRequest, request: Request,
                      db_path: str | None = None):
    """Create a new storyboard production record."""
    actor = _require_owner(request)
    import uuid
    sb_id = f"SB-{uuid.uuid4().hex[:12].upper()}"
    now = _now()
    with _conn(db_path) as conn:
        conn.execute(
            """
            INSERT INTO studio_storyboards
            (id, production_id, scene_id, shot_id, revision, prompt, engine,
             camera_spec, continuity_meta, image_hash, image_uri, provenance_hash,
             source_refs, used_by, status, locked, archived, created_at, updated_at)
            VALUES (?, ?, ?, ?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', 0, 0, ?, ?)
            """,
            (sb_id, body.production_id, body.scene_id, body.shot_id,
             body.prompt, body.engine,
             json.dumps(body.camera_spec), json.dumps(body.continuity_meta),
             body.image_hash, body.image_uri, body.provenance_hash,
             json.dumps(body.source_refs), json.dumps(body.used_by),
             now, now),
        )
        _audit(conn, sb_id, "storyboard.created", None, {"status": "active", "locked": False}, actor)
    return {"storyboard_id": sb_id, "status": "active", "locked": False}


@router.get("")
def list_storyboards(production_id: Optional[str] = None, db_path: str | None = None):
    """List active (non-archived) storyboards."""
    with _conn(db_path) as conn:
        if production_id:
            rows = conn.execute(
                "SELECT * FROM studio_storyboards WHERE archived = 0 AND production_id = ? ORDER BY created_at",
                (production_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM studio_storyboards WHERE archived = 0 ORDER BY created_at",
            ).fetchall()
    return [_row_to_dict(r) for r in rows]


@router.get("/archived")
def list_archived(production_id: Optional[str] = None, db_path: str | None = None):
    """List archived storyboards."""
    with _conn(db_path) as conn:
        if production_id:
            rows = conn.execute(
                "SELECT * FROM studio_storyboards WHERE archived = 1 AND production_id = ? ORDER BY archived_at",
                (production_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM studio_storyboards WHERE archived = 1 ORDER BY archived_at",
            ).fetchall()
    return [_row_to_dict(r) for r in rows]


@router.get("/{storyboard_id}")
def get_storyboard(storyboard_id: str, db_path: str | None = None):
    """Get a storyboard by ID (active or archived)."""
    with _conn(db_path) as conn:
        return _get_storyboard_or_404(conn, storyboard_id)


@router.get("/{storyboard_id}/provenance")
def get_provenance(storyboard_id: str, db_path: str | None = None):
    """Return the full audit trail for a storyboard."""
    with _conn(db_path) as conn:
        _get_storyboard_or_404(conn, storyboard_id)  # 404 if missing
        rows = conn.execute(
            "SELECT * FROM storyboard_audit WHERE storyboard_id = ? ORDER BY id",
            (storyboard_id,),
        ).fetchall()
    return [dict(r) for r in rows]


@router.patch("/{storyboard_id}/lock")
def toggle_lock(storyboard_id: str, body: LockToggleRequest,
                request: Request, db_path: str | None = None):
    """Toggle the lock state of a storyboard.

    Idempotent: requesting the same lock state that is already set is a no-op
    and appends no audit event.
    """
    actor = _require_owner(request)
    with _conn(db_path) as conn:
        sb = _get_storyboard_or_404(conn, storyboard_id)
        current_locked = sb["locked"]
        desired_locked = bool(body.locked)

        if current_locked == desired_locked:
            # Idempotent — no change, no audit event
            return {
                "storyboard_id": storyboard_id,
                "locked": current_locked,
                "changed": False,
            }

        conn.execute(
            "UPDATE studio_storyboards SET locked = ?, updated_at = ? WHERE id = ?",
            (1 if desired_locked else 0, _now(), storyboard_id),
        )
        _audit(
            conn, storyboard_id,
            "storyboard.lock_changed",
            current_locked, desired_locked,
            actor or body.actor, body.reason,
        )

    return {
        "storyboard_id": storyboard_id,
        "previous": current_locked,
        "current": desired_locked,
        "changed": True,
        "actor": actor or body.actor,
        "reason": body.reason,
    }


@router.post("/{storyboard_id}/archive")
def archive_storyboard(storyboard_id: str, body: ArchiveRequest,
                       request: Request, db_path: str | None = None):
    """Archive a storyboard. Works on locked or unlocked records.

    The asset, image_hash, provenance_hash, and used_by references are preserved.
    The storyboard is removed from active views but not deleted.
    """
    actor = _require_owner(request)
    now = _now()
    with _conn(db_path) as conn:
        sb = _get_storyboard_or_404(conn, storyboard_id)
        if sb["archived"]:
            raise HTTPException(status_code=409, detail={"error": "already_archived", "id": storyboard_id})

        locked_before = sb["locked"]
        final_locked = locked_before if body.preserve_lock else False

        conn.execute(
            """UPDATE studio_storyboards
               SET archived = 1, archived_at = ?, archived_by = ?,
                   archive_reason = ?, locked = ?, updated_at = ?
               WHERE id = ?""",
            (now, actor or body.actor, body.reason,
             1 if final_locked else 0, now, storyboard_id),
        )
        _audit(
            conn, storyboard_id,
            "storyboard.archived",
            {"archived": False, "locked": locked_before},
            {"archived": True, "locked": final_locked},
            actor or body.actor, body.reason,
        )

    return {
        "storyboard_id": storyboard_id,
        "archived": True,
        "archived_at": now,
        "archived_by": actor or body.actor,
        "archive_reason": body.reason,
        "locked": final_locked,
    }


@router.post("/{storyboard_id}/restore")
def restore_storyboard(storyboard_id: str, body: RestoreRequest,
                       request: Request, db_path: str | None = None):
    """Restore an archived storyboard to the active library.

    Lock state is preserved exactly as it was at archive time. Restoration does NOT
    automatically make the storyboard editable — a locked storyboard returns locked.
    """
    actor = _require_owner(request)
    with _conn(db_path) as conn:
        sb = _get_storyboard_or_404(conn, storyboard_id)
        if not sb["archived"]:
            raise HTTPException(status_code=409, detail={"error": "not_archived", "id": storyboard_id})

        locked_now = sb["locked"]

        conn.execute(
            """UPDATE studio_storyboards
               SET archived = 0, archived_at = NULL, archived_by = NULL,
                   archive_reason = NULL, updated_at = ?
               WHERE id = ?""",
            (_now(), storyboard_id),
        )
        _audit(
            conn, storyboard_id,
            "storyboard.restored",
            {"archived": True, "locked": locked_now},
            {"archived": False, "locked": locked_now},
            actor or body.actor, body.reason,
        )

    return {
        "storyboard_id": storyboard_id,
        "archived": False,
        "locked": locked_now,
        "actor": actor or body.actor,
    }


@router.post("/{storyboard_id}/revisions")
def create_revision(storyboard_id: str, body: NewRevisionRequest,
                    request: Request, db_path: str | None = None):
    """Create a new unlocked revision cloned from a storyboard.

    The source storyboard (which may be locked) is never modified.
    The new revision starts at revision+1, status='active', locked=False.
    """
    actor = _require_owner(request)
    import uuid
    new_id = f"SB-{uuid.uuid4().hex[:12].upper()}"
    now = _now()
    with _conn(db_path) as conn:
        sb = _get_storyboard_or_404(conn, storyboard_id)
        new_rev = sb["revision"] + 1

        conn.execute(
            """
            INSERT INTO studio_storyboards
            (id, production_id, scene_id, shot_id, revision, parent_id,
             prompt, engine, camera_spec, continuity_meta,
             image_hash, image_uri, provenance_hash,
             source_refs, used_by, status, locked, archived, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?,
                    ?, ?, ?,
                    ?, ?, 'active', 0, 0, ?, ?)
            """,
            (new_id,
             sb["production_id"], sb["scene_id"], sb["shot_id"],
             new_rev, storyboard_id,
             sb["prompt"], sb["engine"],
             json.dumps(sb["camera_spec"]) if isinstance(sb["camera_spec"], dict) else sb["camera_spec"],
             json.dumps(sb["continuity_meta"]) if isinstance(sb["continuity_meta"], dict) else sb["continuity_meta"],
             sb["image_hash"], sb["image_uri"], sb["provenance_hash"],
             json.dumps(sb["source_refs"]) if isinstance(sb["source_refs"], list) else sb["source_refs"],
             json.dumps(sb["used_by"]) if isinstance(sb["used_by"], list) else sb["used_by"],
             now, now),
        )
        _audit(
            conn, new_id, "storyboard.revision_created",
            {"parent_id": storyboard_id, "parent_locked": sb["locked"]},
            {"revision": new_rev, "locked": False, "status": "active"},
            actor or body.actor, body.reason,
        )

    return {
        "storyboard_id": new_id,
        "parent_id": storyboard_id,
        "revision": new_rev,
        "locked": False,
        "status": "active",
    }
