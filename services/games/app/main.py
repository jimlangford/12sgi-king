"""Authenticated public multiplayer circles for the static TribeGameStudios clients."""

import hashlib
import json
import os
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException, Query
from pydantic import BaseModel

from services.authz import audit_auth_event, require_claims
from services.service_metadata import with_service_metadata

API_PREFIX = "/games/api"
SERVICE_NAME = "games"
VERSION = os.environ.get("VERSION", "1.0.0")
DB_PATH = os.environ.get("GAMES_DB_PATH", "/data/db/games.db")
AUTH_INTROSPECTION_URL = os.environ.get(
    "AUTH_INTROSPECTION_URL", "http://auth:8101/api/v2/auth/introspect"
)
INTERNAL_SERVICE_TOKEN = os.environ.get("INTERNAL_SERVICE_TOKEN", "")
REQUEST_TIMEOUT = float(os.environ.get("DEPENDENCY_TIMEOUT_SECONDS", "3"))
LOBBY_TENANT_ID = os.environ.get("GAME_LOBBY_TENANT_ID", "tribegamestudios").strip()
SUPPORTED_GAMES = {"konane", "weiqi"}
PLAYER_LIMIT = 2
MATCH_TTL = timedelta(hours=24)
MAX_STATE_BYTES = 64 * 1024
CODE_ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"
JOIN_RATE_LIMIT_PER_MINUTE = max(
    1, min(300, int(os.environ.get("GAME_JOIN_RATE_LIMIT_PER_MINUTE", "20")))
)
JOIN_RATE_LIMIT_PER_HOUR = max(
    JOIN_RATE_LIMIT_PER_MINUTE,
    min(3600, int(os.environ.get("GAME_JOIN_RATE_LIMIT_PER_HOUR", "200"))),
)

app = FastAPI(title="TribeGameStudios Multiplayer API", version=VERSION)


@contextmanager
def _db():
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=5)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout = 5000")
    try:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS game_matches (
                id TEXT PRIMARY KEY,
                game_id TEXT NOT NULL,
                tenant_id TEXT NOT NULL,
                code TEXT NOT NULL UNIQUE,
                status TEXT NOT NULL,
                turn_seat INTEGER NOT NULL DEFAULT 0,
                state TEXT,
                revision INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS game_match_players (
                match_id TEXT NOT NULL,
                player_id TEXT NOT NULL,
                display_name TEXT NOT NULL,
                seat INTEGER NOT NULL,
                joined_at TEXT NOT NULL,
                PRIMARY KEY (match_id, player_id),
                UNIQUE (match_id, seat),
                FOREIGN KEY (match_id) REFERENCES game_matches(id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_game_matches_lobby
                ON game_matches (tenant_id, game_id, status, created_at);
            CREATE TABLE IF NOT EXISTS game_join_attempts (
                player_id TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_game_join_attempts_player_created
                ON game_join_attempts (player_id, created_at);
            """
        )
        conn.execute("PRAGMA foreign_keys = ON")
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _player_id(subject: str) -> str:
    return hashlib.sha256(subject.encode("utf-8")).hexdigest()[:20]


def _display_name(player_id: str) -> str:
    return f"Player-{player_id[:6].upper()}"


def _require_game_claims(
    authorization: str | None,
    required_scope: str,
    game_id: str,
) -> dict:
    if game_id not in SUPPORTED_GAMES:
        raise HTTPException(status_code=404, detail={"error": "game_not_found"})
    claims = require_claims(
        service_name=SERVICE_NAME,
        authorization=authorization,
        introspection_url=AUTH_INTROSPECTION_URL,
        internal_service_token=INTERNAL_SERVICE_TOKEN,
        request_timeout=REQUEST_TIMEOUT,
        required_scopes={required_scope},
    )
    role = claims.get("role")
    if role not in {"RegisteredUser", "Owner"}:
        audit_auth_event(SERVICE_NAME, "denied_access", {"reason": "role_not_allowed", "role": role})
        raise HTTPException(status_code=403, detail={"error": "game_access_denied"})
    if role == "RegisteredUser" and claims.get("tenant_id") != LOBBY_TENANT_ID:
        audit_auth_event(SERVICE_NAME, "denied_access", {"reason": "wrong_game_lobby"})
        raise HTTPException(status_code=403, detail={"error": "game_access_denied"})
    claims["game_tenant_id"] = LOBBY_TENANT_ID
    claims["player_id"] = _player_id(str(claims["sub"]))
    claims["display_name"] = _display_name(claims["player_id"])
    return claims


def _member(conn: sqlite3.Connection, match_id: str, player_id: str):
    return conn.execute(
        """
        SELECT player_id, display_name, seat
        FROM game_match_players
        WHERE match_id = ? AND player_id = ?
        """,
        (match_id, player_id),
    ).fetchone()


def _record_join_attempt(conn: sqlite3.Connection, player_id: str, now: str) -> None:
    minute_ago = (_now() - timedelta(minutes=1)).isoformat()
    hour_ago = (_now() - timedelta(hours=1)).isoformat()
    conn.execute(
        "DELETE FROM game_join_attempts WHERE created_at < ?",
        (hour_ago,),
    )
    attempts = conn.execute(
        "SELECT COUNT(*) FROM game_join_attempts WHERE player_id = ? AND created_at >= ?",
        (player_id, minute_ago),
    ).fetchone()[0]
    hourly_attempts = conn.execute(
        "SELECT COUNT(*) FROM game_join_attempts WHERE player_id = ? AND created_at >= ?",
        (player_id, hour_ago),
    ).fetchone()[0]
    if attempts >= JOIN_RATE_LIMIT_PER_MINUTE or hourly_attempts >= JOIN_RATE_LIMIT_PER_HOUR:
        raise HTTPException(status_code=429, detail={"error": "join_rate_limited"})
    conn.execute(
        "INSERT INTO game_join_attempts (player_id, created_at) VALUES (?, ?)",
        (player_id, now),
    )


def _view(conn: sqlite3.Connection, match: sqlite3.Row, claims: dict) -> dict:
    player = _member(conn, match["id"], claims["player_id"])
    if not player:
        raise HTTPException(status_code=404, detail={"error": "match_not_found"})
    players = conn.execute(
        """
        SELECT player_id, display_name, seat
        FROM game_match_players
        WHERE match_id = ?
        ORDER BY seat
        """,
        (match["id"],),
    ).fetchall()
    names = [row["display_name"] for row in players]
    turn_of = names[match["turn_seat"]] if match["turn_seat"] < len(names) else ""
    return {
        "ok": True,
        "id": match["id"],
        "game": match["game_id"],
        "code": match["code"],
        "status": match["status"],
        "players": names,
        "seat": player["seat"],
        "your_turn": match["status"] == "active" and player["seat"] == match["turn_seat"],
        "turn_of": turn_of if match["status"] == "active" else "waiting for another player",
        "state": match["state"],
        "rev": match["revision"],
    }


class JoinRequest(BaseModel):
    code: str


class TurnRequest(BaseModel):
    id: str
    rev: int
    state: str


@app.get("/api/v2/live")
def live():
    return with_service_metadata({"status": "alive"}, SERVICE_NAME, VERSION)


@app.get("/api/v2/ready")
def ready():
    try:
        with _db() as conn:
            conn.execute("SELECT 1").fetchone()
    except sqlite3.Error:
        raise HTTPException(status_code=503, detail={"status": "not-ready"})
    return with_service_metadata({"status": "ready"}, SERVICE_NAME, VERSION)


@app.get(f"{API_PREFIX}/{{game_id}}/me")
def me(game_id: str, authorization: str | None = Header(default=None)):
    if game_id not in SUPPORTED_GAMES:
        raise HTTPException(status_code=404, detail={"error": "game_not_found"})
    if not authorization:
        return {"ok": True, "logged_in": False}
    try:
        claims = _require_game_claims(authorization, "game:read", game_id)
    except HTTPException as exc:
        if exc.status_code in {401, 403}:
            return {"ok": True, "logged_in": False}
        raise
    return {
        "ok": True,
        "logged_in": True,
        "who": claims["display_name"],
        "role": claims["role"],
        "tenant_id": claims["game_tenant_id"],
    }


@app.get(f"{API_PREFIX}/{{game_id}}/lobby")
def list_lobby(game_id: str, authorization: str | None = Header(default=None)):
    claims = _require_game_claims(authorization, "game:read", game_id)
    cutoff = (_now() - MATCH_TTL).isoformat()
    with _db() as conn:
        matches = conn.execute(
            """
            SELECT m.code, m.created_at, COUNT(p.player_id) AS player_count
            FROM game_matches AS m
            JOIN game_match_players AS p ON p.match_id = m.id
            WHERE m.tenant_id = ? AND m.game_id = ? AND m.status = 'waiting'
              AND m.created_at >= ?
            GROUP BY m.id
            ORDER BY m.created_at ASC
            LIMIT 25
            """,
            (claims["game_tenant_id"], game_id, cutoff),
        ).fetchall()
    return {
        "ok": True,
        "matches": [
            {
                "game": game_id,
                "code": row["code"],
                "players": row["player_count"],
                "created_at": row["created_at"],
            }
            for row in matches
        ],
    }


@app.post(f"{API_PREFIX}/{{game_id}}/match/new", status_code=201)
def create_match(game_id: str, authorization: str | None = Header(default=None)):
    claims = _require_game_claims(authorization, "game:write", game_id)
    now = _now().isoformat()
    with _db() as conn:
        conn.execute("BEGIN IMMEDIATE")
        active = conn.execute(
            """
            SELECT COUNT(*)
            FROM game_match_players AS p
            JOIN game_matches AS m ON m.id = p.match_id
            WHERE p.player_id = ? AND m.status IN ('waiting', 'active')
              AND m.created_at >= ?
            """,
            (claims["player_id"], (_now() - MATCH_TTL).isoformat()),
        ).fetchone()[0]
        if active >= 5:
            raise HTTPException(status_code=429, detail={"error": "too_many_active_matches"})
        for _ in range(5):
            code = "".join(secrets.choice(CODE_ALPHABET) for _ in range(6))
            if not conn.execute("SELECT 1 FROM game_matches WHERE code = ?", (code,)).fetchone():
                break
        else:
            raise HTTPException(status_code=503, detail={"error": "lobby_unavailable"})
        match_id = secrets.token_urlsafe(18)
        conn.execute(
            """
            INSERT INTO game_matches
              (id, game_id, tenant_id, code, status, turn_seat, state, revision, created_at, updated_at)
            VALUES (?, ?, ?, ?, 'waiting', 0, NULL, 0, ?, ?)
            """,
            (match_id, game_id, claims["game_tenant_id"], code, now, now),
        )
        conn.execute(
            """
            INSERT INTO game_match_players (match_id, player_id, display_name, seat, joined_at)
            VALUES (?, ?, ?, 0, ?)
            """,
            (match_id, claims["player_id"], claims["display_name"], now),
        )
        match = conn.execute("SELECT * FROM game_matches WHERE id = ?", (match_id,)).fetchone()
        result = _view(conn, match, claims)
    audit_auth_event(
        SERVICE_NAME,
        "game_match_created",
        {"user": claims["player_id"], "game": game_id, "match": match_id},
    )
    return result


@app.post(f"{API_PREFIX}/{{game_id}}/match/join")
def join_match(game_id: str, body: JoinRequest,
               authorization: str | None = Header(default=None)):
    claims = _require_game_claims(authorization, "game:write", game_id)
    code = body.code.strip().upper()
    if len(code) != 6 or any(char not in CODE_ALPHABET for char in code):
        raise HTTPException(status_code=404, detail={"error": "match_not_found"})
    now = _now().isoformat()
    with _db() as conn:
        conn.execute("BEGIN IMMEDIATE")
        _record_join_attempt(conn, claims["player_id"], now)
        match = conn.execute(
            """
            SELECT * FROM game_matches
            WHERE code = ? AND game_id = ? AND tenant_id = ?
              AND created_at >= ?
            """,
            (code, game_id, claims["game_tenant_id"], (_now() - MATCH_TTL).isoformat()),
        ).fetchone()
        if not match:
            conn.commit()
            raise HTTPException(status_code=404, detail={"error": "match_not_found"})
        existing = _member(conn, match["id"], claims["player_id"])
        if not existing:
            if match["status"] != "waiting":
                raise HTTPException(status_code=409, detail={"error": "match_full"})
            player_count = conn.execute(
                "SELECT COUNT(*) FROM game_match_players WHERE match_id = ?",
                (match["id"],),
            ).fetchone()[0]
            if player_count >= PLAYER_LIMIT:
                raise HTTPException(status_code=409, detail={"error": "match_full"})
            conn.execute(
                """
                INSERT INTO game_match_players (match_id, player_id, display_name, seat, joined_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (match["id"], claims["player_id"], claims["display_name"], player_count, now),
            )
            conn.execute(
                "UPDATE game_matches SET status = 'active', updated_at = ? WHERE id = ?",
                (now, match["id"]),
            )
            match = conn.execute(
                "SELECT * FROM game_matches WHERE id = ?", (match["id"],)
            ).fetchone()
        result = _view(conn, match, claims)
    audit_auth_event(
        SERVICE_NAME,
        "game_match_joined",
        {"user": claims["player_id"], "game": game_id, "match": match["id"]},
    )
    return result


@app.get(f"{API_PREFIX}/{{game_id}}/match")
def get_match(game_id: str, match_id: str = Query(default="", alias="id"),
              authorization: str | None = Header(default=None)):
    claims = _require_game_claims(authorization, "game:read", game_id)
    with _db() as conn:
        match = conn.execute(
            """
            SELECT * FROM game_matches
            WHERE id = ? AND game_id = ? AND tenant_id = ?
              AND created_at >= ?
            """,
            (
                match_id,
                game_id,
                claims["game_tenant_id"],
                (_now() - MATCH_TTL).isoformat(),
            ),
        ).fetchone()
        if not match:
            raise HTTPException(status_code=404, detail={"error": "match_not_found"})
        return _view(conn, match, claims)


@app.post(f"{API_PREFIX}/{{game_id}}/match/turn")
def post_turn(game_id: str, body: TurnRequest,
              authorization: str | None = Header(default=None)):
    claims = _require_game_claims(authorization, "game:write", game_id)
    if len(body.state.encode("utf-8")) > MAX_STATE_BYTES:
        raise HTTPException(status_code=413, detail={"error": "state_too_large"})
    try:
        state = json.loads(body.state)
    except (TypeError, json.JSONDecodeError):
        raise HTTPException(status_code=400, detail={"error": "invalid_state"})
    if not isinstance(state, dict):
        raise HTTPException(status_code=400, detail={"error": "invalid_state"})
    now = _now().isoformat()
    with _db() as conn:
        conn.execute("BEGIN IMMEDIATE")
        match = conn.execute(
            """
            SELECT * FROM game_matches
            WHERE id = ? AND game_id = ? AND tenant_id = ?
              AND created_at >= ?
            """,
            (
                body.id,
                game_id,
                claims["game_tenant_id"],
                (_now() - MATCH_TTL).isoformat(),
            ),
        ).fetchone()
        if not match or not _member(conn, body.id, claims["player_id"]):
            raise HTTPException(status_code=404, detail={"error": "match_not_found"})
        player = _member(conn, body.id, claims["player_id"])
        if match["status"] != "active":
            raise HTTPException(status_code=409, detail={"error": "match_not_active"})
        if body.rev != match["revision"]:
            raise HTTPException(status_code=409, detail={"error": "stale_turn"})
        if player["seat"] != match["turn_seat"]:
            raise HTTPException(status_code=403, detail={"error": "not_your_turn"})
        conn.execute(
            """
            UPDATE game_matches
            SET state = ?, revision = revision + 1,
                turn_seat = ?, updated_at = ?
            WHERE id = ? AND revision = ?
            """,
            (
                json.dumps(state, separators=(",", ":"), ensure_ascii=False),
                (match["turn_seat"] + 1) % PLAYER_LIMIT,
                now,
                body.id,
                body.rev,
            ),
        )
        updated = conn.execute(
            "SELECT * FROM game_matches WHERE id = ?", (body.id,)
        ).fetchone()
        result = _view(conn, updated, claims)
    audit_auth_event(
        SERVICE_NAME,
        "game_turn_posted",
        {"user": claims["player_id"], "game": game_id, "match": body.id},
    )
    return result
