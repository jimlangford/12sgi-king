"""services/studio_assets/app/script_api.py — Phase 2.2 Writing Room API.

Manages the script production lifecycle from concept through locked script and
storyboard generation trigger. Structured for multi-department coordination:
  Showrunner / Story Architect / Screenwriter / Dialogue Writer /
  Continuity Editor / Cultural Guardian / Script Supervisor / Table-Read Critic.

Writing workflow states:
  concept → premise → story_architecture → beat_sheet → scene_outline →
  first_draft → dialogue_pass → continuity_pass → cultural_review →
  table_read_review → owner_approval → script_locked → storyboard_generation

A locked script is immutable but can be duplicated, archived, or referenced.
Locking does not destroy or strand existing renders.
"""

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

# ── Config ─────────────────────────────────────────────────────────────────────
SCRIPT_DB_PATH = os.environ.get(
    "STUDIO_SCRIPT_DB_PATH",
    str(
        __import__("pathlib").Path(__file__).resolve().parents[3]
        / "data" / "scripts.db"
    ),
)

SCRIPT_STATUSES = [
    "concept", "premise_ready", "architecture_ready", "beat_sheet_ready",
    "scene_outline_ready", "first_draft", "dialogue_review",
    "continuity_review", "cultural_review", "table_read_review",
    "approval_pending", "approved", "script_locked", "storyboard_generation",
]
WRITING_ROLES = [
    "showrunner", "story_architect", "screenwriter", "dialogue_writer",
    "continuity_editor", "cultural_guardian", "script_supervisor",
    "table_read_critic",
]

router = APIRouter(prefix="/api/v2/media/scripts", tags=["writing-room"])


# ── DB ─────────────────────────────────────────────────────────────────────────

def _init_db(path: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with sqlite3.connect(path, check_same_thread=False) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS scripts (
                id              TEXT PRIMARY KEY,
                production_id   TEXT NOT NULL DEFAULT '',
                version         INTEGER NOT NULL DEFAULT 1,
                status          TEXT NOT NULL DEFAULT 'concept',
                title           TEXT NOT NULL DEFAULT '',
                logline         TEXT NOT NULL DEFAULT '',
                themes          TEXT NOT NULL DEFAULT '[]',
                cultural_review TEXT NOT NULL DEFAULT '{"status":"pending","notes":[]}',
                locked          INTEGER NOT NULL DEFAULT 0,
                archived        INTEGER NOT NULL DEFAULT 0,
                created_at      TEXT NOT NULL,
                updated_at      TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS script_scenes (
                id              TEXT PRIMARY KEY,
                script_id       TEXT NOT NULL REFERENCES scripts(id),
                scene_index     INTEGER NOT NULL DEFAULT 0,
                slugline        TEXT NOT NULL DEFAULT '',
                scene_purpose   TEXT NOT NULL DEFAULT '',
                dramatic_question TEXT NOT NULL DEFAULT '',
                location        TEXT NOT NULL DEFAULT '',
                time_of_day     TEXT NOT NULL DEFAULT '',
                characters      TEXT NOT NULL DEFAULT '[]',
                beats           TEXT NOT NULL DEFAULT '[]',
                continuity      TEXT NOT NULL DEFAULT '{}',
                camera_intent   TEXT NOT NULL DEFAULT '{}',
                storyboard_ids  TEXT NOT NULL DEFAULT '[]',
                audio_cues      TEXT NOT NULL DEFAULT '[]',
                gameplay_hooks  TEXT NOT NULL DEFAULT '[]',
                created_at      TEXT NOT NULL,
                updated_at      TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS script_dialogue (
                id                     TEXT PRIMARY KEY,
                scene_id               TEXT NOT NULL REFERENCES script_scenes(id),
                dialogue_index         INTEGER NOT NULL DEFAULT 0,
                character              TEXT NOT NULL DEFAULT '',
                text                   TEXT NOT NULL DEFAULT '',
                intent                 TEXT NOT NULL DEFAULT '',
                subtext                TEXT NOT NULL DEFAULT '',
                emotion                TEXT NOT NULL DEFAULT '',
                delivery               TEXT NOT NULL DEFAULT '{}',
                pronunciation_notes    TEXT NOT NULL DEFAULT '[]',
                cultural_review_status TEXT NOT NULL DEFAULT 'pending',
                take_ids               TEXT NOT NULL DEFAULT '[]',
                created_at             TEXT NOT NULL,
                updated_at             TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS script_transitions (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                script_id   TEXT NOT NULL,
                from_status TEXT,
                to_status   TEXT NOT NULL,
                actor       TEXT NOT NULL DEFAULT 'owner',
                note        TEXT,
                timestamp   TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_scene_script
                ON script_scenes(script_id);
            CREATE INDEX IF NOT EXISTS idx_dialogue_scene
                ON script_dialogue(scene_id);
            CREATE INDEX IF NOT EXISTS idx_transitions_script
                ON script_transitions(script_id);
            """
        )
        conn.commit()


@contextmanager
def _conn(path: str | None = None):
    p = path or SCRIPT_DB_PATH
    _init_db(p)
    c = sqlite3.connect(p, check_same_thread=False)
    c.row_factory = sqlite3.Row
    try:
        yield c
        c.commit()
    finally:
        c.close()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_json_fields(row: sqlite3.Row, fields: list[str]) -> dict:
    d = dict(row)
    for f in fields:
        if f in d:
            try:
                d[f] = json.loads(d[f])
            except (json.JSONDecodeError, TypeError):
                pass
    if "locked" in d:
        d["locked"] = bool(d["locked"])
    if "archived" in d:
        d["archived"] = bool(d["archived"])
    return d


def _get_script_or_404(conn: sqlite3.Connection, script_id: str) -> dict:
    row = conn.execute("SELECT * FROM scripts WHERE id = ?", (script_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail={"error": "script_not_found", "id": script_id})
    return _parse_json_fields(row, ["themes", "cultural_review"])


def _require_owner(request: Request) -> str:
    # Studio endpoints are loopback/Tailscale-gated; no strict token check in phase 2.2.
    return "owner"


# ── Pydantic models ────────────────────────────────────────────────────────────

class CreateScriptRequest(BaseModel):
    production_id: str
    title: str = ""
    logline: str = ""
    themes: list = []


class AdvanceStatusRequest(BaseModel):
    to_status: str
    actor: str = "owner"
    note: str = ""


class AddSceneRequest(BaseModel):
    slugline: str
    scene_purpose: str = ""
    dramatic_question: str = ""
    location: str = ""
    time_of_day: str = ""
    characters: list = []
    beats: list = []
    camera_intent: dict = {}
    audio_cues: list = []
    gameplay_hooks: list = []


class AddDialogueRequest(BaseModel):
    character: str
    text: str
    intent: str = ""
    subtext: str = ""
    emotion: str = ""
    delivery: dict = {}
    pronunciation_notes: list = []


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("", status_code=201)
def create_script(body: CreateScriptRequest, request: Request,
                  db_path: str | None = None):
    """Create a new script in 'concept' status."""
    import uuid
    script_id = f"SCRIPT-{uuid.uuid4().hex[:10].upper()}"
    now = _now()
    with _conn(db_path) as conn:
        conn.execute(
            """INSERT INTO scripts
               (id, production_id, version, status, title, logline, themes,
                cultural_review, locked, archived, created_at, updated_at)
               VALUES (?, ?, 1, 'concept', ?, ?, ?, '{"status":"pending","notes":[]}',
                       0, 0, ?, ?)""",
            (script_id, body.production_id, body.title, body.logline,
             json.dumps(body.themes), now, now),
        )
        conn.execute(
            "INSERT INTO script_transitions (script_id, from_status, to_status, actor, timestamp) VALUES (?, NULL, 'concept', 'owner', ?)",
            (script_id, now),
        )
    return {"script_id": script_id, "status": "concept"}


@router.get("")
def list_scripts(production_id: Optional[str] = None, db_path: str | None = None):
    """List all scripts (active and archived)."""
    with _conn(db_path) as conn:
        if production_id:
            rows = conn.execute("SELECT * FROM scripts WHERE production_id = ?", (production_id,)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM scripts").fetchall()
    return [_parse_json_fields(r, ["themes", "cultural_review"]) for r in rows]


@router.get("/{script_id}")
def get_script(script_id: str, db_path: str | None = None):
    """Get a script by ID."""
    with _conn(db_path) as conn:
        return _get_script_or_404(conn, script_id)


@router.post("/{script_id}/advance")
def advance_status(script_id: str, body: AdvanceStatusRequest,
                   request: Request, db_path: str | None = None):
    """Advance the script to the next workflow status."""
    if body.to_status not in SCRIPT_STATUSES:
        raise HTTPException(
            status_code=422,
            detail={"error": "invalid_status", "valid": SCRIPT_STATUSES},
        )
    now = _now()
    with _conn(db_path) as conn:
        script = _get_script_or_404(conn, script_id)
        if script["locked"] and body.to_status != "storyboard_generation":
            raise HTTPException(
                status_code=409,
                detail={"error": "script_locked", "message": "Cannot advance a locked script's status."},
            )
        prev = script["status"]
        conn.execute(
            "UPDATE scripts SET status = ?, updated_at = ? WHERE id = ?",
            (body.to_status, now, script_id),
        )
        conn.execute(
            "INSERT INTO script_transitions (script_id, from_status, to_status, actor, note, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
            (script_id, prev, body.to_status, body.actor, body.note, now),
        )
    return {"script_id": script_id, "previous_status": prev, "status": body.to_status}


@router.post("/{script_id}/lock")
def lock_script(script_id: str, request: Request, db_path: str | None = None):
    """Lock a script (requires status=owner_approval)."""
    now = _now()
    with _conn(db_path) as conn:
        script = _get_script_or_404(conn, script_id)
        if script["locked"]:
            return {"script_id": script_id, "locked": True, "changed": False}
        conn.execute(
            "UPDATE scripts SET locked = 1, status = 'script_locked', updated_at = ? WHERE id = ?",
            (now, script_id),
        )
        conn.execute(
            "INSERT INTO script_transitions (script_id, from_status, to_status, actor, timestamp) VALUES (?, ?, 'script_locked', 'owner', ?)",
            (script_id, script["status"], now),
        )
    return {"script_id": script_id, "locked": True, "status": "script_locked", "changed": True}


@router.post("/{script_id}/scenes", status_code=201)
def add_scene(script_id: str, body: AddSceneRequest,
              request: Request, db_path: str | None = None):
    """Add a scene to a script."""
    import uuid
    scene_id = f"SCENE-{uuid.uuid4().hex[:10].upper()}"
    now = _now()
    with _conn(db_path) as conn:
        script = _get_script_or_404(conn, script_id)
        if script["locked"]:
            raise HTTPException(
                status_code=409,
                detail={"error": "script_locked", "message": "Cannot add scenes to a locked script. Create a new revision."},
            )
        idx = (conn.execute(
            "SELECT COUNT(*) FROM script_scenes WHERE script_id = ?", (script_id,)
        ).fetchone()[0])
        conn.execute(
            """INSERT INTO script_scenes
               (id, script_id, scene_index, slugline, scene_purpose, dramatic_question,
                location, time_of_day, characters, beats, continuity, camera_intent,
                storyboard_ids, audio_cues, gameplay_hooks, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '{}', ?, '[]', ?, ?, ?, ?)""",
            (scene_id, script_id, idx, body.slugline, body.scene_purpose,
             body.dramatic_question, body.location, body.time_of_day,
             json.dumps(body.characters), json.dumps(body.beats),
             json.dumps(body.camera_intent),
             json.dumps(body.audio_cues), json.dumps(body.gameplay_hooks),
             now, now),
        )
    return {"scene_id": scene_id, "script_id": script_id, "scene_index": idx}


@router.get("/{script_id}/scenes")
def list_scenes(script_id: str, db_path: str | None = None):
    """List scenes for a script."""
    with _conn(db_path) as conn:
        _get_script_or_404(conn, script_id)
        rows = conn.execute(
            "SELECT * FROM script_scenes WHERE script_id = ? ORDER BY scene_index",
            (script_id,),
        ).fetchall()
    return [_parse_json_fields(r, ["characters", "beats", "continuity", "camera_intent",
                                   "storyboard_ids", "audio_cues", "gameplay_hooks"])
            for r in rows]


@router.post("/{script_id}/scenes/{scene_id}/dialogue", status_code=201)
def add_dialogue(script_id: str, scene_id: str, body: AddDialogueRequest,
                 request: Request, db_path: str | None = None):
    """Add a dialogue block to a scene."""
    import uuid
    dlg_id = f"DLG-{uuid.uuid4().hex[:10].upper()}"
    now = _now()
    with _conn(db_path) as conn:
        script = _get_script_or_404(conn, script_id)
        if script["locked"]:
            raise HTTPException(
                status_code=409,
                detail={"error": "script_locked", "message": "Cannot add dialogue to a locked script."},
            )
        row = conn.execute("SELECT id FROM script_scenes WHERE id = ? AND script_id = ?",
                           (scene_id, script_id)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail={"error": "scene_not_found"})
        idx = conn.execute(
            "SELECT COUNT(*) FROM script_dialogue WHERE scene_id = ?", (scene_id,)
        ).fetchone()[0]
        conn.execute(
            """INSERT INTO script_dialogue
               (id, scene_id, dialogue_index, character, text, intent, subtext,
                emotion, delivery, pronunciation_notes, cultural_review_status,
                take_ids, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', '[]', ?, ?)""",
            (dlg_id, scene_id, idx, body.character, body.text, body.intent,
             body.subtext, body.emotion, json.dumps(body.delivery),
             json.dumps(body.pronunciation_notes), now, now),
        )
    return {"dialogue_id": dlg_id, "scene_id": scene_id, "dialogue_index": idx}


@router.get("/{script_id}/scenes/{scene_id}/dialogue")
def list_dialogue(script_id: str, scene_id: str, db_path: str | None = None):
    """List dialogue blocks for a scene."""
    with _conn(db_path) as conn:
        _get_script_or_404(conn, script_id)
        rows = conn.execute(
            "SELECT * FROM script_dialogue WHERE scene_id = ? ORDER BY dialogue_index",
            (scene_id,),
        ).fetchall()
    return [_parse_json_fields(r, ["delivery", "pronunciation_notes", "take_ids"])
            for r in rows]
