"""services/studio_assets/app/game_api.py — Phase 2.2 Game Development Controls.

Game is a Media department, not a separate infrastructure stack.
Assets, storyboards, scripts, and audio are shared with film production.

Hierarchy: game → chapter → level → zone → encounter → quest → objective
           → dialogue → cinematic → asset → build

Generates structured artifacts for Unreal Engine:
  DataTables, JSON, CSV, Sequencer shot manifests, dialogue trees,
  quest graphs, asset manifests, Blueprint implementation briefs,
  build checklists.

Archive must preserve all storyboard, FCP, and Logic references.
"""

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

GAME_DB_PATH = os.environ.get(
    "STUDIO_GAME_DB_PATH",
    str(
        __import__("pathlib").Path(__file__).resolve().parents[3]
        / "data" / "game.db"
    ),
)

router = APIRouter(prefix="/api/v2/media/game", tags=["game"])


# ── DB ─────────────────────────────────────────────────────────────────────────

def _init_db(path: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with sqlite3.connect(path, check_same_thread=False) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS game_projects (
                id              TEXT PRIMARY KEY,
                production_id   TEXT NOT NULL DEFAULT '',
                title           TEXT NOT NULL DEFAULT '',
                engine          TEXT NOT NULL DEFAULT 'unreal_engine_5',
                status          TEXT NOT NULL DEFAULT 'pre_production',
                chapters        TEXT NOT NULL DEFAULT '[]',
                shared_assets   TEXT NOT NULL DEFAULT '[]',
                archived        INTEGER NOT NULL DEFAULT 0,
                created_at      TEXT NOT NULL,
                updated_at      TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS game_levels (
                id              TEXT PRIMARY KEY,
                game_id         TEXT NOT NULL REFERENCES game_projects(id),
                chapter_id      TEXT,
                title           TEXT NOT NULL DEFAULT '',
                description     TEXT NOT NULL DEFAULT '',
                zones           TEXT NOT NULL DEFAULT '[]',
                created_at      TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS game_quests (
                id              TEXT PRIMARY KEY,
                game_id         TEXT NOT NULL REFERENCES game_projects(id),
                level_id        TEXT,
                title           TEXT NOT NULL DEFAULT '',
                description     TEXT NOT NULL DEFAULT '',
                type            TEXT NOT NULL DEFAULT 'main',
                status          TEXT NOT NULL DEFAULT 'draft',
                objectives      TEXT NOT NULL DEFAULT '[]',
                rewards         TEXT NOT NULL DEFAULT '[]',
                triggers        TEXT NOT NULL DEFAULT '[]',
                dialogue_tree_ids TEXT NOT NULL DEFAULT '[]',
                cinematic_ids   TEXT NOT NULL DEFAULT '[]',
                created_at      TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS game_cinematics (
                id              TEXT PRIMARY KEY,
                game_id         TEXT NOT NULL REFERENCES game_projects(id),
                scene_id        TEXT,
                title           TEXT NOT NULL DEFAULT '',
                type            TEXT NOT NULL DEFAULT 'cutscene',
                status          TEXT NOT NULL DEFAULT 'draft',
                shots           TEXT NOT NULL DEFAULT '[]',
                camera_rig      TEXT NOT NULL DEFAULT '{}',
                sequencer_manifest TEXT NOT NULL DEFAULT '{}',
                audio_cue_ids   TEXT NOT NULL DEFAULT '[]',
                archived        INTEGER NOT NULL DEFAULT 0,
                created_at      TEXT NOT NULL,
                updated_at      TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS game_dialogue_trees (
                id              TEXT PRIMARY KEY,
                game_id         TEXT NOT NULL REFERENCES game_projects(id),
                scene_id        TEXT,
                character       TEXT NOT NULL DEFAULT '',
                nodes           TEXT NOT NULL DEFAULT '[]',
                created_at      TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS game_builds (
                id              TEXT PRIMARY KEY,
                game_id         TEXT NOT NULL REFERENCES game_projects(id),
                version         TEXT NOT NULL DEFAULT '',
                type            TEXT NOT NULL DEFAULT 'development',
                status          TEXT NOT NULL DEFAULT 'pending',
                manifest        TEXT NOT NULL DEFAULT '{}',
                archived        INTEGER NOT NULL DEFAULT 0,
                created_at      TEXT NOT NULL
            );
            """
        )
        conn.commit()


@contextmanager
def _conn(path: str | None = None):
    p = path or GAME_DB_PATH
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
    for b in ("archived",):
        if b in d:
            d[b] = bool(d[b])
    return d


def _get_game_or_404(conn: sqlite3.Connection, game_id: str) -> dict:
    row = conn.execute("SELECT * FROM game_projects WHERE id = ?", (game_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail={"error": "game_not_found", "id": game_id})
    return _parse(row, ["chapters", "shared_assets"])


# ── Pydantic models ────────────────────────────────────────────────────────────

class CreateGameRequest(BaseModel):
    production_id: str
    title: str
    engine: str = "unreal_engine_5"
    status: str = "pre_production"
    shared_assets: list = []


class CreateLevelRequest(BaseModel):
    chapter_id: Optional[str] = None
    title: str
    description: str = ""
    zones: list = []


class CreateQuestRequest(BaseModel):
    level_id: Optional[str] = None
    title: str
    description: str = ""
    type: str = "main"
    objectives: list = []
    rewards: list = []
    triggers: list = []
    dialogue_tree_ids: list = []
    cinematic_ids: list = []


class CreateCinematicRequest(BaseModel):
    scene_id: Optional[str] = None
    title: str = ""
    type: str = "cutscene"
    shots: list = []
    camera_rig: dict = {}
    audio_cue_ids: list = []


class CreateDialogueTreeRequest(BaseModel):
    scene_id: Optional[str] = None
    character: str
    nodes: list = []


class CreateBuildRequest(BaseModel):
    version: str
    type: str = "development"
    manifest: dict = {}


class UnrealDataTableRequest(BaseModel):
    table_type: str  # "quest", "dialogue", "cinematic", "asset"


# ── Routes ─────────────────────────────────────────────────────────────────────

@router.post("/projects", status_code=201)
def create_game(body: CreateGameRequest, request: Request,
                db_path: str | None = None):
    """Create a new game project under a Studio production."""
    import uuid
    game_id = f"GAME-{uuid.uuid4().hex[:10].upper()}"
    now = _now()
    with _conn(db_path) as conn:
        conn.execute(
            """INSERT INTO game_projects
               (id, production_id, title, engine, status, chapters,
                shared_assets, archived, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, '[]', ?, 0, ?, ?)""",
            (game_id, body.production_id, body.title, body.engine,
             body.status, json.dumps(body.shared_assets), now, now),
        )
    return {"game_id": game_id, "production_id": body.production_id}


@router.get("/projects")
def list_games(production_id: Optional[str] = None, db_path: str | None = None):
    with _conn(db_path) as conn:
        if production_id:
            rows = conn.execute(
                "SELECT * FROM game_projects WHERE production_id = ?", (production_id,)
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM game_projects").fetchall()
    return [_parse(r, ["chapters", "shared_assets"]) for r in rows]


@router.get("/projects/{game_id}")
def get_game(game_id: str, db_path: str | None = None):
    with _conn(db_path) as conn:
        return _get_game_or_404(conn, game_id)


@router.post("/projects/{game_id}/levels", status_code=201)
def create_level(game_id: str, body: CreateLevelRequest, db_path: str | None = None):
    import uuid
    level_id = f"LVL-{uuid.uuid4().hex[:10].upper()}"
    with _conn(db_path) as conn:
        _get_game_or_404(conn, game_id)
        conn.execute(
            "INSERT INTO game_levels (id, game_id, chapter_id, title, description, zones, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (level_id, game_id, body.chapter_id, body.title, body.description,
             json.dumps(body.zones), _now()),
        )
    return {"level_id": level_id, "game_id": game_id}


@router.get("/projects/{game_id}/levels")
def list_levels(game_id: str, db_path: str | None = None):
    with _conn(db_path) as conn:
        _get_game_or_404(conn, game_id)
        rows = conn.execute("SELECT * FROM game_levels WHERE game_id = ?", (game_id,)).fetchall()
    return [_parse(r, ["zones"]) for r in rows]


@router.post("/projects/{game_id}/quests", status_code=201)
def create_quest(game_id: str, body: CreateQuestRequest, db_path: str | None = None):
    import uuid
    quest_id = f"QST-{uuid.uuid4().hex[:10].upper()}"
    with _conn(db_path) as conn:
        _get_game_or_404(conn, game_id)
        conn.execute(
            """INSERT INTO game_quests
               (id, game_id, level_id, title, description, type, status,
                objectives, rewards, triggers, dialogue_tree_ids, cinematic_ids, created_at)
               VALUES (?, ?, ?, ?, ?, ?, 'draft', ?, ?, ?, ?, ?, ?)""",
            (quest_id, game_id, body.level_id, body.title, body.description, body.type,
             json.dumps(body.objectives), json.dumps(body.rewards),
             json.dumps(body.triggers), json.dumps(body.dialogue_tree_ids),
             json.dumps(body.cinematic_ids), _now()),
        )
    return {"quest_id": quest_id, "game_id": game_id}


@router.get("/projects/{game_id}/quests")
def list_quests(game_id: str, db_path: str | None = None):
    with _conn(db_path) as conn:
        _get_game_or_404(conn, game_id)
        rows = conn.execute("SELECT * FROM game_quests WHERE game_id = ?", (game_id,)).fetchall()
    return [_parse(r, ["objectives", "rewards", "triggers", "dialogue_tree_ids", "cinematic_ids"])
            for r in rows]


@router.post("/projects/{game_id}/cinematics", status_code=201)
def create_cinematic(game_id: str, body: CreateCinematicRequest, db_path: str | None = None):
    import uuid
    cine_id = f"CIN-{uuid.uuid4().hex[:10].upper()}"
    now = _now()
    with _conn(db_path) as conn:
        _get_game_or_404(conn, game_id)
        conn.execute(
            """INSERT INTO game_cinematics
               (id, game_id, scene_id, title, type, status,
                shots, camera_rig, sequencer_manifest, audio_cue_ids, archived, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, 'draft', ?, ?, '{}', ?, 0, ?, ?)""",
            (cine_id, game_id, body.scene_id, body.title, body.type,
             json.dumps(body.shots), json.dumps(body.camera_rig),
             json.dumps(body.audio_cue_ids), now, now),
        )
    return {"cinematic_id": cine_id, "game_id": game_id}


@router.get("/projects/{game_id}/cinematics")
def list_cinematics(game_id: str, db_path: str | None = None):
    with _conn(db_path) as conn:
        _get_game_or_404(conn, game_id)
        rows = conn.execute(
            "SELECT * FROM game_cinematics WHERE game_id = ? AND archived = 0", (game_id,)
        ).fetchall()
    return [_parse(r, ["shots", "camera_rig", "sequencer_manifest", "audio_cue_ids"]) for r in rows]


@router.post("/projects/{game_id}/dialogue_trees", status_code=201)
def create_dialogue_tree(game_id: str, body: CreateDialogueTreeRequest,
                         db_path: str | None = None):
    import uuid
    tree_id = f"DLG-{uuid.uuid4().hex[:10].upper()}"
    with _conn(db_path) as conn:
        _get_game_or_404(conn, game_id)
        conn.execute(
            "INSERT INTO game_dialogue_trees (id, game_id, scene_id, character, nodes, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (tree_id, game_id, body.scene_id, body.character, json.dumps(body.nodes), _now()),
        )
    return {"tree_id": tree_id, "game_id": game_id}


@router.get("/projects/{game_id}/dialogue_trees")
def list_dialogue_trees(game_id: str, db_path: str | None = None):
    with _conn(db_path) as conn:
        _get_game_or_404(conn, game_id)
        rows = conn.execute("SELECT * FROM game_dialogue_trees WHERE game_id = ?", (game_id,)).fetchall()
    return [_parse(r, ["nodes"]) for r in rows]


@router.post("/projects/{game_id}/builds", status_code=201)
def create_build(game_id: str, body: CreateBuildRequest, db_path: str | None = None):
    import uuid
    build_id = f"BUILD-{uuid.uuid4().hex[:8].upper()}"
    with _conn(db_path) as conn:
        _get_game_or_404(conn, game_id)
        conn.execute(
            "INSERT INTO game_builds (id, game_id, version, type, status, manifest, archived, created_at) VALUES (?, ?, ?, ?, 'pending', ?, 0, ?)",
            (build_id, game_id, body.version, body.type, json.dumps(body.manifest), _now()),
        )
    return {"build_id": build_id, "game_id": game_id, "version": body.version}


@router.get("/projects/{game_id}/builds")
def list_builds(game_id: str, db_path: str | None = None):
    with _conn(db_path) as conn:
        _get_game_or_404(conn, game_id)
        rows = conn.execute("SELECT * FROM game_builds WHERE game_id = ?", (game_id,)).fetchall()
    return [_parse(r, ["manifest"]) for r in rows]


@router.post("/projects/{game_id}/builds/{build_id}/archive")
def archive_build(game_id: str, build_id: str, db_path: str | None = None):
    """Archive a build. Preserves storyboard, FCP, and Logic references in the manifest."""
    with _conn(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM game_builds WHERE id = ? AND game_id = ?", (build_id, game_id)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail={"error": "build_not_found"})
        conn.execute(
            "UPDATE game_builds SET archived = 1 WHERE id = ?", (build_id,)
        )
    return {"build_id": build_id, "archived": True}


@router.post("/projects/{game_id}/builds/{build_id}/restore")
def restore_build(game_id: str, build_id: str, db_path: str | None = None):
    """Restore an archived build."""
    with _conn(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM game_builds WHERE id = ? AND game_id = ?", (build_id, game_id)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail={"error": "build_not_found"})
        conn.execute(
            "UPDATE game_builds SET archived = 0 WHERE id = ?", (build_id,)
        )
    return {"build_id": build_id, "archived": False}


@router.post("/projects/{game_id}/unreal/datatable")
def generate_unreal_datatable(game_id: str, body: UnrealDataTableRequest,
                              db_path: str | None = None):
    """Generate a structured Unreal DataTable artifact from game production records."""
    with _conn(db_path) as conn:
        _get_game_or_404(conn, game_id)
        if body.table_type == "quest":
            rows = conn.execute("SELECT * FROM game_quests WHERE game_id = ?", (game_id,)).fetchall()
            records = [_parse(r, ["objectives", "rewards", "triggers", "dialogue_tree_ids", "cinematic_ids"])
                       for r in rows]
        elif body.table_type == "dialogue":
            rows = conn.execute("SELECT * FROM game_dialogue_trees WHERE game_id = ?", (game_id,)).fetchall()
            records = [_parse(r, ["nodes"]) for r in rows]
        elif body.table_type == "cinematic":
            rows = conn.execute("SELECT * FROM game_cinematics WHERE game_id = ?", (game_id,)).fetchall()
            records = [_parse(r, ["shots", "camera_rig", "sequencer_manifest", "audio_cue_ids"])
                       for r in rows]
        else:
            records = []

    return {
        "game_id": game_id,
        "table_type": body.table_type,
        "format": "unreal_datatable_json",
        "row_count": len(records),
        "rows": records,
    }


@router.post("/projects/{game_id}/unreal/sequencer_manifest")
def generate_sequencer_manifest(game_id: str, cinematic_id: Optional[str] = None,
                                db_path: str | None = None):
    """Generate a Sequencer shot manifest retaining storyboard and camera references."""
    with _conn(db_path) as conn:
        _get_game_or_404(conn, game_id)
        if cinematic_id:
            rows = conn.execute(
                "SELECT * FROM game_cinematics WHERE id = ? AND game_id = ?",
                (cinematic_id, game_id),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM game_cinematics WHERE game_id = ? AND archived = 0", (game_id,)
            ).fetchall()
        cinematics = [_parse(r, ["shots", "camera_rig", "sequencer_manifest", "audio_cue_ids"])
                      for r in rows]

    shots_manifest = []
    for cine in cinematics:
        for shot in cine.get("shots", []):
            shots_manifest.append({
                "cinematic_id": cine["id"],
                "shot_id": shot.get("shot_id"),
                "storyboard_id": shot.get("storyboard_id"),
                "camera_spec": shot.get("camera_spec", {}),
                "duration_seconds": shot.get("duration_seconds"),
                "dialogue_id": shot.get("dialogue_id"),
                "sequencer_shot_id": shot.get("sequencer_shot_id"),
            })

    return {
        "game_id": game_id,
        "format": "sequencer_manifest",
        "shot_count": len(shots_manifest),
        "shots": shots_manifest,
        "storyboard_refs": list({s["storyboard_id"] for s in shots_manifest if s.get("storyboard_id")}),
    }
