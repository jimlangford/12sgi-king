"""services/studio_assets/app/fcp_adapter.py — Phase 2.2 Final Cut Pro interchange adapter.

Generates deterministic FCPXML, marker lists, role assignments, proxy manifests,
and caption files from Studio production records. No UI automation — pure file-based
interchange for import into Final Cut Pro on the owner's machine.

FCP timeline records live in a local SQLite store alongside the other Phase 2.2 data.
FCPXML 1.11 is the target schema (Final Cut Pro 10.6+).
"""

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Optional
from xml.sax.saxutils import escape as _xml_escape

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

FCP_DB_PATH = os.environ.get(
    "STUDIO_FCP_DB_PATH",
    str(
        __import__("pathlib").Path(__file__).resolve().parents[3]
        / "data" / "fcp.db"
    ),
)

FCP_ROLES = ["Dialogue", "Music", "Effects", "Ambience", "Narration",
             "Room Tone", "Temporary Score", "Final Score"]

router = APIRouter(prefix="/api/v2/media/fcp", tags=["fcp"])


# ── DB ─────────────────────────────────────────────────────────────────────────

def _init_db(path: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with sqlite3.connect(path, check_same_thread=False) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS fcp_timelines (
                id              TEXT PRIMARY KEY,
                production_id   TEXT NOT NULL DEFAULT '',
                title           TEXT NOT NULL DEFAULT '',
                frame_rate      TEXT NOT NULL DEFAULT '24p',
                resolution      TEXT NOT NULL DEFAULT '1920x1080',
                duration_seconds REAL NOT NULL DEFAULT 0.0,
                shots           TEXT NOT NULL DEFAULT '[]',
                roles           TEXT NOT NULL DEFAULT '[]',
                markers         TEXT NOT NULL DEFAULT '[]',
                color_notes     TEXT NOT NULL DEFAULT '',
                version         INTEGER NOT NULL DEFAULT 1,
                created_at      TEXT NOT NULL,
                updated_at      TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS fcp_cut_versions (
                id              TEXT PRIMARY KEY,
                timeline_id     TEXT NOT NULL REFERENCES fcp_timelines(id),
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
    p = path or FCP_DB_PATH
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


def _get_timeline_or_404(conn: sqlite3.Connection, timeline_id: str) -> dict:
    row = conn.execute("SELECT * FROM fcp_timelines WHERE id = ?", (timeline_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail={"error": "timeline_not_found", "id": timeline_id})
    return _parse(row, ["shots", "roles", "markers"])


# ── FCPXML generation ──────────────────────────────────────────────────────────

def _timecode_from_seconds(seconds: float, fps: int = 24) -> str:
    total_frames = int(round(seconds * fps))
    h = total_frames // (fps * 3600)
    m = (total_frames % (fps * 3600)) // (fps * 60)
    s = (total_frames % (fps * 60)) // fps
    f = total_frames % fps
    return f"{h:02d}:{m:02d}:{s:02d}:{f:02d}"


def _build_fcpxml(tl: dict) -> str:
    shots = tl.get("shots") or []
    roles = tl.get("roles") or []
    markers = tl.get("markers") or []
    fps = 24

    asset_lines = []
    clip_lines = []
    for i, shot in enumerate(shots):
        shot_id = _xml_escape(str(shot.get("shot_id", f"shot_{i}")))
        # Use immutable asset_id from shot record; fall back to positional ref
        # Immutable IDs survive storyboard archival
        raw_asset_id = shot.get("asset_id") or f"r{i+1}"
        asset_id = _xml_escape(str(raw_asset_id))
        src = _xml_escape(str(shot.get("proxy_path", f"placeholder_{i}.mov")))
        start_tc = _timecode_from_seconds(shot.get("start_seconds", 0.0), fps)
        duration_tc = _timecode_from_seconds(shot.get("duration_seconds", 3.0), fps)
        handles_tc = _timecode_from_seconds(shot.get("handles_frames", 24) / fps, fps)
        asset_hash = _xml_escape(str(shot.get("asset_hash", "")))
        asset_lines.append(
            f'    <asset id="{asset_id}" name="{shot_id}" src="{src}" '
            f'start="0s" duration="{duration_tc}" hasAudio="1" hasVideo="1"'
            + (f' comment="hash:{asset_hash}"' if asset_hash else "") + "/>"
        )
        role = _xml_escape(str(shot.get("timeline_role", "Video")))
        marker_xml = ""
        for m in shot.get("marker_notes", []):
            marker_xml += f'\n        <marker start="{start_tc}" value="{_xml_escape(str(m))}"/>'
        clip_lines.append(
            f'      <clip name="{shot_id}" ref="{asset_id}" offset="{start_tc}" '
            f'duration="{duration_tc}" start="{handles_tc}" tcFormat="NDF">\n'
            f'        <video role="{role}"/>{marker_xml}\n'
            f'      </clip>'
        )

    marker_xml_global = ""
    for m in markers:
        tc = _timecode_from_seconds(m.get("timecode_seconds", 0.0), fps)
        note = _xml_escape(str(m.get("note", "")))
        marker_xml_global += f'\n      <marker start="{tc}" value="{note}"/>'

    title = _xml_escape(str(tl.get("title", "Untitled")))
    total_tc = _timecode_from_seconds(tl.get("duration_seconds", 0.0), fps)

    assets_block = "\n".join(asset_lines)
    clips_block = "\n".join(clip_lines)

    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<!DOCTYPE fcpxml>\n'
        '<fcpxml version="1.11">\n'
        '  <resources>\n'
        f'    <format id="r0" name="FFVideoFormat1080p24" frameDuration="100/2400s" '
        f'width="1920" height="1080" colorSpace="1-1-1 (Rec. 709)"/>\n'
        f'{assets_block}\n'
        '  </resources>\n'
        '  <library>\n'
        '    <event name="12SGI Studio">\n'
        f'      <project name="{title}">\n'
        f'        <sequence duration="{total_tc}" format="r0" tcStart="00:00:00:00" tcFormat="NDF">\n'
        '          <spine>\n'
        f'{clips_block}\n'
        f'{marker_xml_global}\n'
        '          </spine>\n'
        '        </sequence>\n'
        '      </project>\n'
        '    </event>\n'
        '  </library>\n'
        '</fcpxml>\n'
    )


# ── Pydantic models ────────────────────────────────────────────────────────────

class CreateTimelineRequest(BaseModel):
    production_id: str
    title: str = ""
    frame_rate: str = "24p"
    resolution: str = "1920x1080"


class UpdateTimelineRequest(BaseModel):
    shots: Optional[list] = None
    roles: Optional[list] = None
    markers: Optional[list] = None
    color_notes: Optional[str] = None
    duration_seconds: Optional[float] = None


class ImportEditDecisionRequest(BaseModel):
    shots: list
    description: str = ""


# ── Routes ─────────────────────────────────────────────────────────────────────

@router.post("/timelines", status_code=201)
def create_timeline(body: CreateTimelineRequest, request: Request,
                    db_path: str | None = None):
    """Create a new FCP timeline record."""
    import uuid
    tl_id = f"FCP-{uuid.uuid4().hex[:10].upper()}"
    now = _now()
    with _conn(db_path) as conn:
        conn.execute(
            """INSERT INTO fcp_timelines
               (id, production_id, title, frame_rate, resolution, duration_seconds,
                shots, roles, markers, color_notes, version, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, 0.0, '[]',
                       ?, '[]', '', 1, ?, ?)""",
            (tl_id, body.production_id, body.title, body.frame_rate,
             body.resolution, json.dumps(FCP_ROLES), now, now),
        )
    return {"timeline_id": tl_id, "production_id": body.production_id, "version": 1}


@router.get("/timelines")
def list_timelines(production_id: Optional[str] = None, db_path: str | None = None):
    with _conn(db_path) as conn:
        if production_id:
            rows = conn.execute(
                "SELECT * FROM fcp_timelines WHERE production_id = ?", (production_id,)
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM fcp_timelines").fetchall()
    return [_parse(r, ["shots", "roles", "markers"]) for r in rows]


@router.get("/timelines/{timeline_id}")
def get_timeline(timeline_id: str, db_path: str | None = None):
    with _conn(db_path) as conn:
        return _get_timeline_or_404(conn, timeline_id)


@router.patch("/timelines/{timeline_id}")
def update_timeline(timeline_id: str, body: UpdateTimelineRequest,
                    db_path: str | None = None):
    """Update shots, markers, roles, or color notes on a timeline."""
    now = _now()
    updates = {}
    if body.shots is not None:
        updates["shots"] = json.dumps(body.shots)
    if body.roles is not None:
        updates["roles"] = json.dumps(body.roles)
    if body.markers is not None:
        updates["markers"] = json.dumps(body.markers)
    if body.color_notes is not None:
        updates["color_notes"] = body.color_notes
    if body.duration_seconds is not None:
        updates["duration_seconds"] = body.duration_seconds
    if not updates:
        raise HTTPException(status_code=422, detail={"error": "no_fields_to_update"})
    updates["updated_at"] = now
    sets = ", ".join(f"{k} = ?" for k in updates)
    with _conn(db_path) as conn:
        _get_timeline_or_404(conn, timeline_id)
        conn.execute(f"UPDATE fcp_timelines SET {sets} WHERE id = ?",
                     list(updates.values()) + [timeline_id])
    return {"timeline_id": timeline_id, "updated": list(body.model_fields_set)}


@router.get("/timelines/{timeline_id}/fcpxml")
def export_fcpxml(timeline_id: str, db_path: str | None = None):
    """Export FCPXML interchange document for the timeline."""
    with _conn(db_path) as conn:
        tl = _get_timeline_or_404(conn, timeline_id)
    return {"timeline_id": timeline_id, "fcpxml": _build_fcpxml(tl)}


@router.get("/timelines/{timeline_id}/markers")
def get_markers(timeline_id: str, db_path: str | None = None):
    """Return the marker list for a timeline."""
    with _conn(db_path) as conn:
        tl = _get_timeline_or_404(conn, timeline_id)
    return {"timeline_id": timeline_id, "markers": tl.get("markers", [])}


@router.get("/timelines/{timeline_id}/roles")
def get_roles(timeline_id: str, db_path: str | None = None):
    """Return role assignments for a timeline."""
    with _conn(db_path) as conn:
        tl = _get_timeline_or_404(conn, timeline_id)
    return {"timeline_id": timeline_id, "roles": tl.get("roles", [])}


@router.post("/timelines/{timeline_id}/import_edit_decisions")
def import_edit_decisions(timeline_id: str, body: ImportEditDecisionRequest,
                          db_path: str | None = None):
    """Import edit decision records into a timeline."""
    now = _now()
    with _conn(db_path) as conn:
        tl = _get_timeline_or_404(conn, timeline_id)
        new_shots = tl.get("shots", []) + body.shots
        conn.execute(
            "UPDATE fcp_timelines SET shots = ?, updated_at = ? WHERE id = ?",
            (json.dumps(new_shots), now, timeline_id),
        )
    return {"timeline_id": timeline_id, "shots_added": len(body.shots)}


@router.post("/timelines/{timeline_id}/archive")
def archive_timeline(timeline_id: str, db_path: str | None = None):
    """Archive the current timeline as a cut version snapshot."""
    import uuid
    ver_id = f"VER-{uuid.uuid4().hex[:8].upper()}"
    now = _now()
    with _conn(db_path) as conn:
        tl = _get_timeline_or_404(conn, timeline_id)
        ver_num = (conn.execute(
            "SELECT COUNT(*) FROM fcp_cut_versions WHERE timeline_id = ?", (timeline_id,)
        ).fetchone()[0]) + 1
        conn.execute(
            "INSERT INTO fcp_cut_versions (id, timeline_id, version_number, description, snapshot, archived, created_at) VALUES (?, ?, ?, '', ?, 1, ?)",
            (ver_id, timeline_id, ver_num, json.dumps(dict(tl)), now),
        )
    return {"version_id": ver_id, "timeline_id": timeline_id, "version_number": ver_num}
