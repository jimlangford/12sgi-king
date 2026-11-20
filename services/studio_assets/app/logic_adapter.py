"""services/studio_assets/app/logic_adapter.py — Phase 2.2 Logic Pro session packaging.

Generates deterministic Logic session manifests, cue sheets, ADR lists, Foley lists,
and stem layouts from Studio production records. Pure file-based interchange — no
UI automation. Designed for the owner's local Logic Pro installation.

Audio package layout:
  /production/audio/
    dialogue/   narration/   adr/   music/   ambience/
    foley/      effects/     stems/ mixes/   cue_sheets/
"""

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

def _resolve_db_path(env_key: str, default: str) -> str:
    """Resolve the DB path from an environment variable and validate it is within
    an allowed directory. Allowed: the default data directory, or the system temp
    directory (used by test fixtures). Owner-only service; env vars are set by the
    local machine owner, not by web input."""
    import tempfile
    raw = os.environ.get(env_key, default)
    resolved = os.path.realpath(raw)
    allowed = (
        os.path.realpath(default),
        os.path.realpath(os.path.dirname(default)),
        os.path.realpath(tempfile.gettempdir()),
    )
    for a in allowed:
        if resolved == a or resolved.startswith(a + os.sep):
            return resolved
    raise ValueError(
        f"{env_key}: DB path {resolved!r} must be within the data or temp directory."
    )

LOGIC_DB_PATH = _resolve_db_path(
    "STUDIO_LOGIC_DB_PATH",
    str(__import__("pathlib").Path(__file__).resolve().parents[3] / "data" / "logic.db"),
)

AUDIO_STEMS = [
    "dialogue", "narration", "adr", "music",
    "ambience", "foley", "effects", "stems", "mixes",
]

router = APIRouter(prefix="/api/v2/media/logic", tags=["logic"])


# ── DB ─────────────────────────────────────────────────────────────────────────

def _init_db(path: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with sqlite3.connect(path, check_same_thread=False) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS logic_sessions (
                id              TEXT PRIMARY KEY,
                production_id   TEXT NOT NULL DEFAULT '',
                title           TEXT NOT NULL DEFAULT '',
                sample_rate     INTEGER NOT NULL DEFAULT 48000,
                bit_depth       INTEGER NOT NULL DEFAULT 24,
                frame_rate      TEXT NOT NULL DEFAULT '24fps',
                cues            TEXT NOT NULL DEFAULT '[]',
                tempo_map       TEXT NOT NULL DEFAULT '[]',
                stems           TEXT NOT NULL DEFAULT '[]',
                version         INTEGER NOT NULL DEFAULT 1,
                archived        INTEGER NOT NULL DEFAULT 0,
                created_at      TEXT NOT NULL,
                updated_at      TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS logic_mix_versions (
                id              TEXT PRIMARY KEY,
                session_id      TEXT NOT NULL REFERENCES logic_sessions(id),
                version_number  INTEGER NOT NULL DEFAULT 1,
                description     TEXT NOT NULL DEFAULT '',
                snapshot        TEXT NOT NULL DEFAULT '{}',
                archived        INTEGER NOT NULL DEFAULT 0,
                created_at      TEXT NOT NULL
            );
            """
        )
        conn.commit()


@contextmanager
def _conn(path: str | None = None):
    p = path or LOGIC_DB_PATH
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


def _parse(row: sqlite3.Row, fields: list[str]) -> dict:
    d = dict(row)
    for f in fields:
        if f in d:
            try:
                d[f] = json.loads(d[f])
            except (json.JSONDecodeError, TypeError):
                pass
    return d


def _get_session_or_404(conn: sqlite3.Connection, session_id: str) -> dict:
    row = conn.execute(
        "SELECT * FROM logic_sessions WHERE id = ?", (session_id,)
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail={"error": "session_not_found", "id": session_id})
    return _parse(row, ["cues", "tempo_map", "stems"])


# ── Pydantic models ────────────────────────────────────────────────────────────

class CreateSessionRequest(BaseModel):
    production_id: str
    title: str = ""
    sample_rate: int = 48000
    bit_depth: int = 24
    frame_rate: str = "24fps"


class AddCueRequest(BaseModel):
    cue_id: str
    scene_id: str
    start_timecode: str
    duration_seconds: float
    tempo_bpm: Optional[float] = None
    key: Optional[str] = None
    purpose: str = ""
    logic_marker: str = ""
    stem_requirements: list = []


class AddTempoRequest(BaseModel):
    timecode: str
    bpm: float
    time_signature: str = "4/4"


# ── Routes ─────────────────────────────────────────────────────────────────────

@router.post("/sessions", status_code=201)
def create_session(body: CreateSessionRequest, request: Request,
                   db_path: str | None = None):
    """Create a Logic Pro session manifest."""
    import uuid
    session_id = f"LGCX-{uuid.uuid4().hex[:10].upper()}"
    now = _now()
    default_stems = [{"stem": s, "path": f"audio/{s}/"} for s in AUDIO_STEMS]
    with _conn(db_path) as conn:
        conn.execute(
            """INSERT INTO logic_sessions
               (id, production_id, title, sample_rate, bit_depth, frame_rate,
                cues, tempo_map, stems, version, archived, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, '[]', '[]', ?, 1, 0, ?, ?)""",
            (session_id, body.production_id, body.title,
             body.sample_rate, body.bit_depth, body.frame_rate,
             json.dumps(default_stems), now, now),
        )
    return {"session_id": session_id, "production_id": body.production_id}


@router.get("/sessions")
def list_sessions(production_id: Optional[str] = None, db_path: str | None = None):
    with _conn(db_path) as conn:
        if production_id:
            rows = conn.execute(
                "SELECT * FROM logic_sessions WHERE production_id = ?", (production_id,)
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM logic_sessions").fetchall()
    return [_parse(r, ["cues", "tempo_map", "stems"]) for r in rows]


@router.get("/sessions/{session_id}")
def get_session(session_id: str, db_path: str | None = None):
    with _conn(db_path) as conn:
        return _get_session_or_404(conn, session_id)


@router.post("/sessions/{session_id}/cues", status_code=201)
def add_cue(session_id: str, body: AddCueRequest, db_path: str | None = None):
    """Add a music or audio cue to a session."""
    with _conn(db_path) as conn:
        sess = _get_session_or_404(conn, session_id)
        cues = sess.get("cues", [])
        cue = {
            "cue_id": body.cue_id,
            "scene_id": body.scene_id,
            "start_timecode": body.start_timecode,
            "duration_seconds": body.duration_seconds,
            "tempo_bpm": body.tempo_bpm,
            "key": body.key,
            "purpose": body.purpose,
            "logic_marker": body.logic_marker,
            "stem_requirements": body.stem_requirements,
        }
        cues.append(cue)
        conn.execute(
            "UPDATE logic_sessions SET cues = ?, updated_at = ? WHERE id = ?",
            (json.dumps(cues), _now(), session_id),
        )
    return {"session_id": session_id, "cue_id": body.cue_id}


@router.get("/sessions/{session_id}/cue_sheet")
def export_cue_sheet(session_id: str, db_path: str | None = None):
    """Export cue sheet for the session."""
    with _conn(db_path) as conn:
        sess = _get_session_or_404(conn, session_id)
    cues = sess.get("cues", [])
    return {
        "session_id": session_id,
        "production_id": sess["production_id"],
        "title": sess["title"],
        "frame_rate": sess["frame_rate"],
        "cue_count": len(cues),
        "cues": cues,
    }


@router.post("/sessions/{session_id}/tempo_map", status_code=201)
def add_tempo(session_id: str, body: AddTempoRequest, db_path: str | None = None):
    """Add a tempo map entry."""
    with _conn(db_path) as conn:
        sess = _get_session_or_404(conn, session_id)
        tempo_map = sess.get("tempo_map", [])
        tempo_map.append({
            "timecode": body.timecode,
            "bpm": body.bpm,
            "time_signature": body.time_signature,
        })
        conn.execute(
            "UPDATE logic_sessions SET tempo_map = ?, updated_at = ? WHERE id = ?",
            (json.dumps(tempo_map), _now(), session_id),
        )
    return {"session_id": session_id, "tempo_entries": len(tempo_map)}


@router.get("/sessions/{session_id}/adr_list")
def get_adr_list(session_id: str, db_path: str | None = None):
    """Return the ADR list derived from cues with adr in their stem requirements."""
    with _conn(db_path) as conn:
        sess = _get_session_or_404(conn, session_id)
    adr = [c for c in sess.get("cues", [])
           if "adr" in (c.get("stem_requirements") or [])]
    return {"session_id": session_id, "adr_list": adr}


@router.get("/sessions/{session_id}/foley_list")
def get_foley_list(session_id: str, db_path: str | None = None):
    """Return the Foley list derived from cues with foley in their stem requirements."""
    with _conn(db_path) as conn:
        sess = _get_session_or_404(conn, session_id)
    foley = [c for c in sess.get("cues", [])
             if "foley" in (c.get("stem_requirements") or [])]
    return {"session_id": session_id, "foley_list": foley}


@router.post("/sessions/{session_id}/archive")
def archive_session(session_id: str, db_path: str | None = None):
    """Archive the current session as a mix version snapshot."""
    import uuid
    ver_id = f"MIX-{uuid.uuid4().hex[:8].upper()}"
    now = _now()
    with _conn(db_path) as conn:
        sess = _get_session_or_404(conn, session_id)
        ver_num = (conn.execute(
            "SELECT COUNT(*) FROM logic_mix_versions WHERE session_id = ?",
            (session_id,),
        ).fetchone()[0]) + 1
        conn.execute(
            "INSERT INTO logic_mix_versions (id, session_id, version_number, description, snapshot, archived, created_at) VALUES (?, ?, ?, '', ?, 1, ?)",
            (ver_id, session_id, ver_num, json.dumps(dict(sess)), now),
        )
    return {"version_id": ver_id, "session_id": session_id, "version_number": ver_num}
