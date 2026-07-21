"""govOS v2 Studio-Asset Service - read-mostly manager/serving layer over the elementLOTUS studio vault.

Chartered 2026-07-09 (Jimmy: "work on the docker to manage the studio asset with the server
port as to not interfere with the other work being done").

WHAT IT IS
    A stdlib+FastAPI sibling of the govOS-v2 services (auth/tenant/documents/storage/ai) that
    INDEXES, SEARCHES, and SERVES the studio assets — the ~3800-clip render VAULT (mp4/),
    delivery masters (finals/), source audio (audio/), ComfyUI renders, hero + face-ref art —
    over a private port. It runs as its OWN compose project (docker compose -p studio-assets)
    so it can never recreate/restart the running govOS-v2 containers or disturb a live GPU render.

WHAT IT IS NOT
    NOT a crawler/thumbnailer/tierer. The asset-quad-os lane already owns that
    (tools/assets/asset_tier.py -> reports/_status/asset_index.json + thumbnails/). This service
    INGESTS that existing index (authoritative, with thumbs) and only SUPPLEMENTS it with a cheap
    stat-only scan of the finalized vaults the index doesn't cover (e.g. the flat mp4/ vault).
    It never re-thumbnails, re-tiers, or re-crawls the live ComfyUI/output render target.

NON-INTERFERENCE / SAFETY (every point enforced, not aspirational):
  * Port: publishes ONLY 127.0.0.1:8108 (loopback + Tailscale trust boundary). Never 8107
    (reserved in-file for the not-running gpu-router), never a busy port, never 0.0.0.0.
  * GPU: IO-only. No CUDA, no GPU reservation anywhere in the compose stanza. Cannot contend
    for the 8 GB co-tenant card.
  * Mutation: every asset tree is a READ-ONLY bind mount (kernel-enforced). This module runs a
    FAIL-CLOSED write-probe at import: if ANY configured asset mount is writable, it refuses to
    start (sys.exit 1). The VAULT can never be pruned or mutated from here. Owner-gated maintenance
    POST routes only refresh private SQLite/Neo4j projections; no delete/move/put/patch asset routes
    exist. All writes go to private named volumes (/data/db, /data/derived) only.
  * Live renders: the supplemental scan is stat-only (metadata, no byte reads) and skips the live
    ComfyUI/output render dir. File-serving pre-probes with retry so a file held open by a render
    returns 503 rather than a torn read.
"""

import base64
import hashlib
import json
import mimetypes
import os
import sqlite3
import sys
import threading
import time
import urllib.error
import urllib.request
from contextlib import asynccontextmanager, contextmanager

from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse

from services.studio_assets.app import security

# ── Config (all overridable via env; defaults match the compose stanza) ──────────────────────
VERSION = os.environ.get("VERSION", "1.0.0")
DB_PATH = os.environ.get("STUDIO_ASSETS_DB_PATH", "/data/db/studio_assets.db")
INDEX_JSON = os.environ.get("STUDIO_INDEX_JSON", "/data/index/asset_index.json")
THUMBS_DIR = os.environ.get("STUDIO_THUMBS_DIR", "/data/index/thumbnails")
STUDIO_CROSSWALK_JSON = os.environ.get("STUDIO_CROSSWALK_JSON", "/data/crosswalk/studio_asset_crosswalk.json")
STUDIO_CLIP_CROSSWALK_JSON = os.environ.get(
    "STUDIO_CLIP_CROSSWALK_JSON", "/data/crosswalk/studio_clip_crosswalk.json"
)
STUDIO_CHARACTER_BIBLES_DIR = os.environ.get("STUDIO_CHARACTER_BIBLES_DIR", "/data/crosswalk/character_bibles")
STUDIO_NEO4J_HTTP = os.environ.get("STUDIO_NEO4J_HTTP", "")
STUDIO_NEO4J_USER = os.environ.get("STUDIO_NEO4J_USER", "")
STUDIO_NEO4J_PASSWORD = os.environ.get("STUDIO_NEO4J_PASSWORD", "")

# Container mount points that MUST be read-only. The fail-closed probe checks every one.
ASSET_MOUNTS = [
    m.strip()
    for m in os.environ.get(
        "STUDIO_ASSET_MOUNTS",
        "/data/assets/mp4,/data/assets/finals,/data/assets/audio,/data/assets/hero,"
        "/data/assets/exports,/data/assets/jimmy_lora,/data/assets/comfy_output,"
        "/data/assets/comfy_input,/data/assets/batch,/data/index,/data/crosswalk/studio_asset_crosswalk.json,"
        "/data/crosswalk/studio_clip_crosswalk.json,"
        "/data/crosswalk/character_bibles",
    ).split(",")
    if m.strip()
]

# Finalized vaults to stat-scan for supplemental coverage. Deliberately EXCLUDES the live
# ComfyUI/output render target (covered by asset_index.json) so we never stat a mid-render file.
SCAN_ROOTS = [
    m.strip()
    for m in os.environ.get(
        "STUDIO_SCAN_ROOTS",
        "/data/assets/mp4,/data/assets/finals,/data/assets/audio,/data/assets/hero,/data/assets/exports",
    ).split(",")
    if m.strip()
]
SCAN_MAX_FILES = int(os.environ.get("STUDIO_SCAN_MAX_FILES", "200000"))

# Host<->container path map so asset_index.json's absolute host `rel` paths resolve to a mounted
# container path for serving. Derived from the two host roots; override with STUDIO_HOST_* if moved.
HOST_PROJ = os.environ.get(
    "STUDIO_HOST_PROJ", r"C:\Users\12sgi\Documents\Claude\Projects\Video System elementLOTUS"
)
HOST_COMFY = os.environ.get("STUDIO_HOST_COMFY", r"C:\Users\12sgi\Documents\ComfyUI")

# (host_prefix_lower_backslash, container_mount, label) — longest prefixes first so nested wins.
_PATH_MAP = [
    (os.path.join(HOST_PROJ, "reports", "_status"), "/data/index", "index"),
    (os.path.join(HOST_PROJ, "mp4"), "/data/assets/mp4", "mp4"),
    (os.path.join(HOST_PROJ, "finals"), "/data/assets/finals", "finals"),
    (os.path.join(HOST_PROJ, "audio"), "/data/assets/audio", "audio"),
    (os.path.join(HOST_PROJ, "hero"), "/data/assets/hero", "hero"),
    (os.path.join(HOST_PROJ, "exports"), "/data/assets/exports", "exports"),
    (os.path.join(HOST_PROJ, "JIMMY_LORA"), "/data/assets/jimmy_lora", "jimmy_lora"),
    (os.path.join(HOST_PROJ, "batch"), "/data/assets/batch", "batch"),
    (os.path.join(HOST_COMFY, "output"), "/data/assets/comfy_output", "comfy_output"),
    (os.path.join(HOST_COMFY, "input"), "/data/assets/comfy_input", "comfy_input"),
]
_PATH_MAP.sort(key=lambda t: len(t[0]), reverse=True)

# asset_index.json contains both absolute Windows paths and project-relative paths. Keep a
# canonical host path in SQLite so the index and supplemental scan cannot create two rows for the
# same file. Longest relative prefixes win (reports/_status before reports).
_RELATIVE_PATH_MAP = [
    ("reports/_status", os.path.join(HOST_PROJ, "reports", "_status"), "/data/index", "index"),
    ("mp4", os.path.join(HOST_PROJ, "mp4"), "/data/assets/mp4", "mp4"),
    ("finals", os.path.join(HOST_PROJ, "finals"), "/data/assets/finals", "finals"),
    ("audio", os.path.join(HOST_PROJ, "audio"), "/data/assets/audio", "audio"),
    ("hero", os.path.join(HOST_PROJ, "hero"), "/data/assets/hero", "hero"),
    ("exports", os.path.join(HOST_PROJ, "exports"), "/data/assets/exports", "exports"),
    ("jimmy_lora", os.path.join(HOST_PROJ, "JIMMY_LORA"), "/data/assets/jimmy_lora", "jimmy_lora"),
    ("batch", os.path.join(HOST_PROJ, "batch"), "/data/assets/batch", "batch"),
]
_RELATIVE_PATH_MAP.sort(key=lambda row: len(row[0]), reverse=True)

_LAST_INDEX_STATUS = {
    "present": False,
    "records": 0,
    "unmapped": 0,
    "missing": 0,
    "offline_archived": 0,
    "pruned": 0,
}
_LAST_SCAN_STATUS = {
    "complete": False,
    "records": 0,
    "pruned": 0,
    "missing_roots": list(SCAN_ROOTS),
    "cap_hit": False,
}
_CATALOG_STATUS = {
    "ready": False,
    "unavailable": 0,
    "index": dict(_LAST_INDEX_STATUS),
    "scan": dict(_LAST_SCAN_STATUS),
}


# ── FAIL-CLOSED write-probe: prove every asset mount is read-only, or refuse to start ─────────
def _assert_mounts_readonly() -> None:
    """Ground-truth guarantee that the VAULT cannot be mutated: attempt to create a probe file in
    each configured asset mount. If the write SUCCEEDS the mount is read-WRITE -> abort (fail
    closed). This is stronger than parsing /proc/self/mountinfo because it is kernel-enforced."""
    violations = []
    checked = []
    for mount in ASSET_MOUNTS:
        if os.path.isfile(mount):
            try:
                fd = os.open(mount, os.O_WRONLY)
            except OSError:
                checked.append(mount)
                continue
            os.close(fd)
            violations.append(mount)
            continue
        if not os.path.isdir(mount):
            print(f"[studio-assets] WARN mount not present, skipping RO probe: {mount}", file=sys.stderr)
            continue
        probe = os.path.join(mount, ".studio_asset_ro_probe")
        try:
            fd = os.open(probe, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except OSError:
            checked.append(mount)
            continue
        os.close(fd)
        try:
            os.unlink(probe)
        except OSError:
            pass
        violations.append(mount)
    if violations:
        print(
            "[studio-assets] FATAL: asset mount(s) are WRITABLE (VAULT at risk) -> "
            + ", ".join(violations)
            + " . Every asset bind mount must be read_only: true. Refusing to start.",
            file=sys.stderr,
        )
        sys.exit(1)
    print(f"[studio-assets] read-only guarantee OK on {len(checked)} mount(s).", file=sys.stderr)


_assert_mounts_readonly()


# ── DB ────────────────────────────────────────────────────────────────────────────────────────
@contextmanager
def _db():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    try:
        yield conn
    finally:
        conn.close()


def _init_db() -> None:
    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
    with _db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS assets (
                key TEXT PRIMARY KEY,
                label TEXT,
                name TEXT,
                ext TEXT,
                host_path TEXT UNIQUE,
                container_path TEXT,
                size INTEGER,
                mtime INTEGER,
                thumb_file TEXT,
                archivable INTEGER DEFAULT 0,
                archived INTEGER DEFAULT 0,
                source TEXT,
                tenant TEXT,
                character_id TEXT,
                style_id TEXT,
                assignment_id TEXT,
                scene TEXT,
                shot TEXT,
                aspect TEXT,
                workflow TEXT,
                provenance_json TEXT,
                indexed_at INTEGER
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_assets_name ON assets(name)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_assets_label ON assets(label)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_assets_ext ON assets(ext)")
        columns = {row[1] for row in conn.execute("PRAGMA table_info(assets)")}
        for name in ("tenant", "character_id", "style_id", "assignment_id", "scene", "shot", "aspect",
                     "workflow", "provenance_json"):
            if name not in columns:
                conn.execute(f"ALTER TABLE assets ADD COLUMN {name} TEXT")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_assets_tenant ON assets(tenant)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_assets_character ON assets(character_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_assets_style ON assets(style_id)")
        conn.commit()


# ── Path mapping ────────────────────────────────────────────────────────────────────────────
def _norm_host(p: str) -> str:
    return (p or "").replace("/", "\\").lower()


def _resolve_asset_path(host_path: str) -> tuple[str, str, str] | None:
    if not host_path:
        return None
    hp = _norm_host(host_path)
    for prefix, mount, _label in _PATH_MAP:
        pref = _norm_host(prefix)
        if hp == pref or hp.startswith(pref + "\\"):
            rest = host_path[len(prefix):].lstrip("\\/").replace("\\", "/")
            canonical = prefix + ("\\" + rest.replace("/", "\\") if rest else "")
            return canonical, mount + ("/" + rest if rest else ""), _label

    # A drive-qualified or UNC path that missed the allowlist must not be treated as relative.
    normalized = host_path.replace("\\", "/").lstrip("/")
    if (len(normalized) >= 2 and normalized[1] == ":") or host_path.startswith(("\\\\", "//")):
        return None
    folded = normalized.casefold()
    if folded == ".." or folded.startswith("../") or "/../" in folded:
        return None
    for relative_prefix, host_prefix, mount, label in _RELATIVE_PATH_MAP:
        rel_folded = relative_prefix.casefold()
        if folded == rel_folded or folded.startswith(rel_folded + "/"):
            rest = normalized[len(relative_prefix):].lstrip("/")
            canonical = host_prefix + ("\\" + rest.replace("/", "\\") if rest else "")
            return canonical, mount + ("/" + rest if rest else ""), label
    return None


def canonical_host_path(host_path: str) -> str:
    resolved = _resolve_asset_path(host_path)
    return resolved[0] if resolved else host_path


def host_to_container(host_path: str) -> str | None:
    resolved = _resolve_asset_path(host_path)
    return resolved[1] if resolved else None


def _label_for_host(host_path: str) -> str | None:
    resolved = _resolve_asset_path(host_path)
    return resolved[2] if resolved else None


def container_to_host(container_path: str, mount: str) -> str:
    for prefix, m, _label in _PATH_MAP:
        if m == mount:
            rest = container_path[len(mount):].lstrip("\\/").replace("/", "\\")
            return prefix + ("\\" + rest if rest else "")
    return container_path


# ── Ingest ────────────────────────────────────────────────────────────────────────────────────
def _upsert(conn, row: dict) -> None:
    conn.execute(
        """
        INSERT INTO assets (key,label,name,ext,host_path,container_path,size,mtime,thumb_file,
                            archivable,archived,source,tenant,character_id,style_id,assignment_id,
                            scene,shot,aspect,workflow,provenance_json,indexed_at)
        VALUES (:key,:label,:name,:ext,:host_path,:container_path,:size,:mtime,:thumb_file,
                :archivable,:archived,:source,:tenant,:character_id,:style_id,:assignment_id,
                :scene,:shot,:aspect,:workflow,:provenance_json,:indexed_at)
        ON CONFLICT(key) DO UPDATE SET
            label=excluded.label, name=excluded.name, ext=excluded.ext,
            host_path=excluded.host_path, container_path=excluded.container_path,
            size=excluded.size, mtime=excluded.mtime,
            thumb_file=excluded.thumb_file, archivable=excluded.archivable,
            archived=excluded.archived, source=excluded.source, tenant=excluded.tenant,
            character_id=excluded.character_id, style_id=excluded.style_id,
            assignment_id=excluded.assignment_id, scene=excluded.scene, shot=excluded.shot,
            aspect=excluded.aspect, workflow=excluded.workflow,
            provenance_json=excluded.provenance_json, indexed_at=excluded.indexed_at
        """,
        row,
    )


def _metadata_text(value) -> str:
    return "" if value is None else str(value)


def ingest_index() -> int:
    global _LAST_INDEX_STATUS
    if not os.path.isfile(INDEX_JSON):
        print(f"[studio-assets] no asset_index.json at {INDEX_JSON}; skipping index ingest", file=sys.stderr)
        _LAST_INDEX_STATUS = {
            "present": False, "records": 0, "unmapped": 0, "missing": 0,
            "offline_archived": 0, "pruned": 0,
        }
        return 0
    with open(INDEX_JSON, encoding="utf-8") as f:
        data = json.load(f)
    items = data.get("items", []) if isinstance(data, dict) else (data or [])
    generation = time.time_ns()
    n = 0
    availability: dict[str, str] = {}
    with _db() as conn:
        for it in items:
            source_path = it.get("rel") or ""
            host_path = canonical_host_path(source_path)
            meta = it.get("meta") if isinstance(it.get("meta"), dict) else {}
            cpath = host_to_container(source_path)
            thumb = it.get("thumb") or ""
            thumb_file = None
            if thumb:
                thumb_file = os.path.join(THUMBS_DIR, os.path.basename(thumb.replace("\\", "/")))
            name = it.get("name") or os.path.basename(source_path.replace("\\", "/"))
            key = it.get("key") or hashlib.sha1(source_path.encode("utf-8")).hexdigest()[:16]

            # The supplemental scanner may already own the same canonical file under a different
            # key. The authoritative index wins, without leaving a duplicate behind.
            conn.execute(
                "DELETE FROM assets WHERE host_path=? AND key<>? AND source IN ('index','scan')",
                (host_path, key),
            )
            _upsert(
                conn,
                {
                    "key": key,
                    "label": it.get("label") or _label_for_host(source_path) or "renders",
                    "name": name,
                    "ext": os.path.splitext(name)[1].lower().lstrip("."),
                    "host_path": host_path,
                    "container_path": cpath,
                    "size": int(it.get("size") or 0),
                    "mtime": int(it.get("mtime") or 0),
                    "thumb_file": thumb_file,
                    "archivable": 1 if it.get("archivable") else 0,
                    "archived": 1 if it.get("archived") else 0,
                    "source": "index",
                    "tenant": meta.get("tenant") or "",
                    "character_id": meta.get("character_id") or "",
                    "style_id": meta.get("style") or meta.get("style_id") or meta.get("look") or "",
                    "assignment_id": meta.get("assignment_id") or "",
                    "scene": _metadata_text(meta.get("scene")),
                    "shot": _metadata_text(meta.get("shot")),
                    "aspect": meta.get("aspect") or "",
                    "workflow": meta.get("workflow") or "",
                    "provenance_json": json.dumps(meta, ensure_ascii=False, sort_keys=True) if meta else "",
                    "indexed_at": generation,
                },
            )
            if cpath and os.path.isfile(cpath):
                availability[key] = "available"
            elif it.get("archived"):
                # Cold-archive pointers intentionally keep searchable metadata after their hot
                # bytes move off disk. They are not a broken active delivery or a readiness fault.
                availability[key] = "offline_archived"
            elif not cpath:
                availability[key] = "unmapped"
            else:
                availability[key] = "missing"
            n += 1
        pruned = conn.execute(
            "DELETE FROM assets WHERE source='index' AND indexed_at<>?", (generation,)
        ).rowcount
        conn.commit()
        records = conn.execute("SELECT COUNT(*) FROM assets WHERE source='index'").fetchone()[0]
    _LAST_INDEX_STATUS = {
        "present": True,
        "records": records,
        "unmapped": sum(state == "unmapped" for state in availability.values()),
        "missing": sum(state == "missing" for state in availability.values()),
        "offline_archived": sum(state == "offline_archived" for state in availability.values()),
        "pruned": pruned,
    }
    print(
        f"[studio-assets] ingested {n} item(s), retained {records}, pruned {pruned} stale index row(s)",
        file=sys.stderr,
    )
    return n


def scan_supplemental() -> int:
    global _LAST_SCAN_STATUS
    generation = time.time_ns()
    scanned = 0
    seen = 0
    pruned = 0
    missing_roots = []
    cap_hit = False
    with _db() as conn:
        indexed = {
            _norm_host(r["host_path"])
            for r in conn.execute("SELECT host_path FROM assets WHERE source='index'").fetchall()
        }
        for root in SCAN_ROOTS:
            if not os.path.isdir(root):
                missing_roots.append(root)
                continue
            root_complete = True
            for dirpath, _dirs, files in os.walk(root):
                for fn in files:
                    if fn.startswith(".studio_asset_ro_probe"):
                        continue
                    seen += 1
                    if seen > SCAN_MAX_FILES:
                        print(f"[studio-assets] scan cap {SCAN_MAX_FILES} hit; stopping", file=sys.stderr)
                        cap_hit = True
                        root_complete = False
                        break
                    cpath = os.path.join(dirpath, fn)
                    mount = root
                    host_path = container_to_host(cpath, mount)
                    if _norm_host(host_path) in indexed:
                        continue
                    try:
                        st = os.stat(cpath)
                    except OSError:
                        continue
                    key = hashlib.sha1(host_path.encode("utf-8")).hexdigest()[:16]
                    _upsert(
                        conn,
                        {
                            "key": key,
                            "label": os.path.basename(mount),
                            "name": fn,
                            "ext": os.path.splitext(fn)[1].lower().lstrip("."),
                            "host_path": host_path,
                            "container_path": cpath,
                            "size": int(st.st_size),
                            "mtime": int(st.st_mtime),
                            "thumb_file": None,
                            "archivable": 0,
                            "archived": 0,
                            "source": "scan",
                            "tenant": "",
                            "character_id": "",
                            "style_id": "",
                            "assignment_id": "",
                            "scene": "",
                            "shot": "",
                            "aspect": "",
                            "workflow": "",
                            "provenance_json": "",
                            "indexed_at": generation,
                        },
                    )
                    scanned += 1
                if cap_hit:
                    break
            if root_complete:
                root_path = os.path.normcase(os.path.abspath(root))
                stale_keys = []
                for row in conn.execute(
                    "SELECT key, container_path FROM assets WHERE source='scan' AND indexed_at<>?",
                    (generation,),
                ):
                    try:
                        candidate = os.path.normcase(os.path.abspath(row["container_path"]))
                        if os.path.commonpath([root_path, candidate]) == root_path:
                            stale_keys.append(row["key"])
                    except (OSError, TypeError, ValueError):
                        continue
                if stale_keys:
                    conn.executemany("DELETE FROM assets WHERE key=?", [(key,) for key in stale_keys])
                    pruned += len(stale_keys)
            if cap_hit:
                break
        conn.commit()
        records = conn.execute("SELECT COUNT(*) FROM assets WHERE source='scan'").fetchone()[0]
    _LAST_SCAN_STATUS = {
        "complete": not cap_hit and not missing_roots,
        "records": records,
        "pruned": pruned,
        "missing_roots": missing_roots,
        "cap_hit": cap_hit,
    }
    print(
        f"[studio-assets] supplemental scan retained {records}, pruned {pruned} stale row(s)",
        file=sys.stderr,
    )
    return scanned


def _log_receipt(action: str, event: str, payload: dict) -> None:
    """Keep routine service health out of the actionable workboard queue."""
    try:
        print(json.dumps({"kind": "studio-assets-receipt", "action": action,
                          "event": event, "payload": payload}, ensure_ascii=False), file=sys.stderr)
    except Exception:
        pass


def reindex() -> dict:
    global _CATALOG_STATUS
    n_index = ingest_index()
    n_scan = scan_supplemental()
    with _db() as conn:
        total = conn.execute("SELECT COUNT(*) FROM assets").fetchone()[0]
    unavailable = _LAST_INDEX_STATUS["unmapped"] + _LAST_INDEX_STATUS["missing"]
    _CATALOG_STATUS = {
        "ready": bool(_LAST_INDEX_STATUS["present"] and _LAST_SCAN_STATUS["complete"] and unavailable == 0),
        "unavailable": unavailable,
        "index": dict(_LAST_INDEX_STATUS),
        "scan": dict(_LAST_SCAN_STATUS),
    }
    _log_receipt(
        "studio.index.rescanned",
        f"STUDIO ASSET INDEX: {total} assets ({n_index} indexed + {n_scan} scanned)",
        {"total": total, "from_index": n_index, "from_scan": n_scan, "catalog": _CATALOG_STATUS},
    )
    return {"total": total, "from_index": n_index, "from_scan": n_scan, "catalog": _CATALOG_STATUS}


# ── Tenant/style/character crosswalk + scoped Neo4j projection ──────────────────────────────
_CROSSWALK_CACHE = {"mtime": -1.0, "data": {}}
_CLIP_CACHE = {"mtime": -1.0, "data": {}}


def _crosswalk() -> dict:
    try:
        mtime = os.path.getmtime(STUDIO_CROSSWALK_JSON)
        if mtime != _CROSSWALK_CACHE["mtime"]:
            with open(STUDIO_CROSSWALK_JSON, encoding="utf-8") as handle:
                data = json.load(handle)
            if data.get("_schema") != "studio-asset-crosswalk-v1":
                raise ValueError("unsupported crosswalk schema")
            _CROSSWALK_CACHE.update({"mtime": mtime, "data": data})
    except (OSError, ValueError, json.JSONDecodeError):
        return {}
    return _CROSSWALK_CACHE["data"]


def _clip_crosswalk() -> dict:
    try:
        mtime = os.path.getmtime(STUDIO_CLIP_CROSSWALK_JSON)
        if mtime != _CLIP_CACHE["mtime"]:
            with open(STUDIO_CLIP_CROSSWALK_JSON, encoding="utf-8") as handle:
                data = json.load(handle)
            if data.get("_schema") != "studio-clip-learning-v1":
                raise ValueError("unsupported clip crosswalk schema")
            _CLIP_CACHE.update({"mtime": mtime, "data": data})
    except (OSError, ValueError, json.JSONDecodeError):
        return {}
    return _CLIP_CACHE["data"]


def _norm(value: str) -> str:
    value = (value or "").replace("ʻ", "").replace("’", "").replace("'", "")
    return " ".join("".join(ch if ch.isalnum() else " " for ch in value.lower()).split())


def resolve_assignment(tenant: str, character: str, style: str = "") -> dict | None:
    data = _crosswalk()
    tenant_row = next((row for row in data.get("tenants", [])
                       if tenant in {row.get("id"), row.get("film_key")}), None)
    if not tenant_row:
        return None
    chosen_style = style or tenant_row.get("default_style", "")
    wanted = _norm(character)
    for row in data.get("assignments", []):
        if row.get("tenant") != tenant_row.get("id") or row.get("style") != chosen_style:
            continue
        names = [row.get("character", ""), row.get("character_id", ""), *(row.get("aliases") or [])]
        if wanted in {_norm(name) for name in names}:
            return row
    return None


def _neo4j(statements: list[dict], timeout: int = 90) -> dict:
    if not STUDIO_NEO4J_HTTP:
        return {"results": [], "errors": []}
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if STUDIO_NEO4J_USER:
        token = base64.b64encode(f"{STUDIO_NEO4J_USER}:{STUDIO_NEO4J_PASSWORD}".encode()).decode("ascii")
        headers["Authorization"] = "Basic " + token
    request = urllib.request.Request(
        STUDIO_NEO4J_HTTP,
        data=json.dumps({"statements": statements}).encode("utf-8"),
        headers=headers,
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        result = json.loads(response.read().decode("utf-8", "replace"))
    if result.get("errors"):
        raise RuntimeError(json.dumps(result["errors"], ensure_ascii=False))
    return result


def _graph_props(row: dict) -> dict:
    result = {}
    for key, value in row.items():
        if key in {"id", "src", "dst", "eid"}:
            continue
        if isinstance(value, (str, int, float, bool)) or value is None:
            result[key] = value
        elif isinstance(value, list) and all(isinstance(item, (str, int, float, bool)) for item in value):
            result[key] = value
        else:
            result[key + "_json"] = json.dumps(value, ensure_ascii=False, sort_keys=True)
    return result


def _result_scalar(block: dict, default=0):
    data = block.get("data") or []
    return data[0].get("row", [default])[0] if data else default


def _delete_projection_label(label: str, batch_size: int = 500) -> None:
    for _attempt in range(1000):
        result = _neo4j([{"statement": f"MATCH (n:{label}) RETURN count(n)"}])
        blocks = result.get("results", [])
        if not blocks or _result_scalar(blocks[0]) == 0:
            return
        _neo4j([{"statement": f"MATCH (n:{label}) WITH n LIMIT $limit DETACH DELETE n",
                 "parameters": {"limit": batch_size}}])
    raise RuntimeError(f"Neo4j cleanup did not converge for {label}")


def _sync_projection(
    data: dict,
    *,
    projection_id: str,
    active_label: str,
    stage_label: str,
    retired_label: str,
    relation_type: str,
    constraint_name: str,
    node_batch_size: int,
    edge_batch_size: int,
) -> dict:
    nodes = [{"id": row["id"], "props": _graph_props(row)} for row in data.get("nodes", [])]
    edges = [{"eid": row["eid"], "src": row["src"], "dst": row["dst"],
              "kind": row["kind"], "props": _graph_props(row)} for row in data.get("edges", [])]
    fingerprint = hashlib.sha256(json.dumps(
        {"nodes": data.get("nodes", []), "edges": data.get("edges", [])},
        ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")).hexdigest()

    current = _neo4j([
        {"statement": "MATCH (s:StudioProjectionState {id:$id}) RETURN s.fingerprint",
         "parameters": {"id": projection_id}},
        {"statement": f"MATCH (n:{active_label}) RETURN count(n)"},
        {"statement": f"MATCH (:{active_label})-[r:{relation_type}]->(:{active_label}) RETURN count(r)"},
    ])
    current_blocks = current.get("results", [])
    current_fingerprint = _result_scalar(current_blocks[0], "") if len(current_blocks) > 0 else ""
    current_nodes = _result_scalar(current_blocks[1]) if len(current_blocks) > 1 else 0
    current_edges = _result_scalar(current_blocks[2]) if len(current_blocks) > 2 else 0
    if current_fingerprint == fingerprint and [current_nodes, current_edges] == [len(nodes), len(edges)]:
        try:
            _delete_projection_label(retired_label)
            _delete_projection_label(stage_label)
        except Exception:
            pass
        return {"ok": True, "nodes": current_nodes, "edges": current_edges, "unchanged": True}

    _neo4j([{"statement": f"CREATE CONSTRAINT {constraint_name} IF NOT EXISTS "
                           f"FOR (n:{active_label}) REQUIRE n.id IS UNIQUE"}])
    _delete_projection_label(stage_label)
    _delete_projection_label(retired_label)
    generation = f"{time.time_ns():x}"

    for start in range(0, len(nodes), node_batch_size):
        _neo4j([{
            "statement": f"UNWIND $rows AS row MERGE (n:{stage_label} "
                         "{id:row.id, projection_generation:$generation}) "
                         "SET n = row.props, n.id=row.id, n.projection_generation=$generation",
            "parameters": {"rows": nodes[start:start + node_batch_size], "generation": generation},
        }])
    for start in range(0, len(edges), edge_batch_size):
        _neo4j([{
            "statement": f"UNWIND $rows AS row MATCH (a:{stage_label} "
                         "{id:row.src, projection_generation:$generation}) "
                         f"MATCH (b:{stage_label} {{id:row.dst, projection_generation:$generation}}) "
                         f"MERGE (a)-[r:{relation_type} "
                         "{eid:row.eid, projection_generation:$generation}]->(b) "
                         "SET r = row.props, r.eid=row.eid, r.kind=row.kind, "
                         "r.projection_generation=$generation",
            "parameters": {"rows": edges[start:start + edge_batch_size], "generation": generation},
        }])

    staged = _neo4j([
        {"statement": f"MATCH (n:{stage_label} {{projection_generation:$generation}}) RETURN count(n)",
         "parameters": {"generation": generation}},
        {"statement": f"MATCH (:{stage_label} {{projection_generation:$generation}})"
                      f"-[r:{relation_type} {{projection_generation:$generation}}]->"
                      f"(:{stage_label} {{projection_generation:$generation}}) RETURN count(r)",
         "parameters": {"generation": generation}},
    ])
    staged_counts = [_result_scalar(block) for block in staged.get("results", [])]
    if staged_counts != [len(nodes), len(edges)]:
        return {"ok": False, "error": "staged Neo4j projection is incomplete",
                "nodes": staged_counts[0] if staged_counts else 0,
                "edges": staged_counts[1] if len(staged_counts) > 1 else 0}

    switched = _neo4j([
        {"statement": f"MATCH (n:{active_label}) REMOVE n:{active_label} SET n:{retired_label}"},
        {"statement": f"MATCH (n:{stage_label} {{projection_generation:$generation}}) "
                      f"REMOVE n:{stage_label} SET n:{active_label} REMOVE n.projection_generation",
         "parameters": {"generation": generation}},
        {"statement": f"MATCH (:{active_label})-[r:{relation_type} "
                      "{projection_generation:$generation}]->(:"
                      f"{active_label}) REMOVE r.projection_generation",
         "parameters": {"generation": generation}},
        {"statement": "MERGE (s:StudioProjectionState {id:$id}) "
                      "SET s.fingerprint=$fingerprint, s.updated_at=$updated_at",
         "parameters": {"id": projection_id, "fingerprint": fingerprint,
                        "updated_at": int(time.time())}},
        {"statement": f"MATCH (n:{active_label}) RETURN count(n)"},
        {"statement": f"MATCH (:{active_label})-[r:{relation_type}]->(:{active_label}) RETURN count(r)"},
    ], timeout=90)
    counts = [_result_scalar(block) for block in switched.get("results", [])[-2:]]
    if counts != [len(nodes), len(edges)]:
        return {"ok": False, "error": "Neo4j projection switch returned incomplete counts",
                "nodes": counts[0] if counts else 0, "edges": counts[1] if len(counts) > 1 else 0}

    cleanup_pending = False
    try:
        _delete_projection_label(retired_label)
    except Exception:
        cleanup_pending = True
    return {"ok": True, "nodes": counts[0], "edges": counts[1],
            "unchanged": False, "cleanup_pending": cleanup_pending}


def sync_crosswalk_graph() -> dict:
    data = _crosswalk()
    if not data:
        return {"ok": False, "error": "crosswalk missing"}
    if not STUDIO_NEO4J_HTTP:
        return {"ok": False, "error": "Neo4j endpoint not configured"}
    return _sync_projection(
        data,
        projection_id="studio-assets",
        active_label="StudioAssetNode",
        stage_label="StudioAssetStage",
        retired_label="StudioAssetRetired",
        relation_type="STUDIO_REL",
        constraint_name="studio_asset_node_id",
        node_batch_size=400,
        edge_batch_size=400,
    )


def sync_clip_graph() -> dict:
    data = _clip_crosswalk()
    if not data:
        return {"ok": False, "error": "clip crosswalk missing"}
    if not STUDIO_NEO4J_HTTP:
        return {"ok": False, "error": "Neo4j endpoint not configured"}
    return _sync_projection(
        data,
        projection_id="studio-clips",
        active_label="StudioClipNode",
        stage_label="StudioClipStage",
        retired_label="StudioClipRetired",
        relation_type="CLIP_REL",
        constraint_name="studio_clip_node_id",
        node_batch_size=300,
        edge_batch_size=300,
    )


def neo4j_ready() -> bool:
    if not STUDIO_NEO4J_HTTP:
        return False
    try:
        _neo4j([{"statement": "RETURN 1"}], timeout=5)
        return True
    except (OSError, urllib.error.URLError, RuntimeError):
        return False


def neo4j_projection_status() -> dict:
    data = _crosswalk()
    expected = data.get("counts", {})
    if not STUDIO_NEO4J_HTTP:
        return {"configured": False, "ready": False, "nodes": 0, "edges": 0}
    try:
        result = _neo4j([
            {"statement": "MATCH (n:StudioAssetNode) RETURN count(n)"},
            {"statement": "MATCH (:StudioAssetNode)-[r:STUDIO_REL]->(:StudioAssetNode) RETURN count(r)"},
        ], timeout=5)
        counts = [block.get("data", [{}])[0].get("row", [0])[0] if block.get("data") else 0
                  for block in result.get("results", [])]
        nodes = counts[0] if len(counts) > 0 else 0
        edges = counts[1] if len(counts) > 1 else 0
        expected_nodes = expected.get("nodes", len(data.get("nodes", [])))
        expected_edges = expected.get("edges", len(data.get("edges", [])))
        return {"configured": True, "ready": nodes == expected_nodes and edges == expected_edges,
                "nodes": nodes, "edges": edges, "expected_nodes": expected_nodes,
                "expected_edges": expected_edges}
    except (OSError, urllib.error.URLError, RuntimeError):
        return {"configured": True, "ready": False, "nodes": 0, "edges": 0,
                "expected_nodes": expected.get("nodes", len(data.get("nodes", []))),
                "expected_edges": expected.get("edges", len(data.get("edges", [])))}


def clip_projection_status() -> dict:
    data = _clip_crosswalk()
    expected = data.get("counts", {})
    expected_nodes = expected.get("nodes", len(data.get("nodes", [])))
    expected_edges = expected.get("edges", len(data.get("edges", [])))
    if not STUDIO_NEO4J_HTTP:
        return {"configured": False, "ready": False, "nodes": 0, "edges": 0,
                "expected_nodes": expected_nodes, "expected_edges": expected_edges}
    try:
        result = _neo4j([
            {"statement": "MATCH (n:StudioClipNode) RETURN count(n)"},
            {"statement": "MATCH (:StudioClipNode)-[r:CLIP_REL]->(:StudioClipNode) RETURN count(r)"},
        ], timeout=5)
        counts = [block.get("data", [{}])[0].get("row", [0])[0] if block.get("data") else 0
                  for block in result.get("results", [])]
        nodes = counts[0] if len(counts) > 0 else 0
        edges = counts[1] if len(counts) > 1 else 0
        return {"configured": True, "ready": nodes == expected_nodes and edges == expected_edges,
                "nodes": nodes, "edges": edges, "expected_nodes": expected_nodes,
                "expected_edges": expected_edges}
    except (OSError, urllib.error.URLError, RuntimeError):
        return {"configured": True, "ready": False, "nodes": 0, "edges": 0,
                "expected_nodes": expected_nodes, "expected_edges": expected_edges}


# ── App ─────────────────────────────────────────────────────────────────────────────────────
_STARTUP_REFRESH = {"state": "pending", "error": "", "started_at": 0, "finished_at": 0}


def _startup_refresh() -> None:
    _STARTUP_REFRESH.update({"state": "running", "error": "", "started_at": int(time.time()),
                             "finished_at": 0})
    try:
        stats = reindex()
        graph = sync_crosswalk_graph() if STUDIO_NEO4J_HTTP else {"ok": False, "error": "not configured"}
        clip_graph = sync_clip_graph() if STUDIO_NEO4J_HTTP else {"ok": False, "error": "not configured"}
        stats["crosswalk"] = (_crosswalk().get("counts") or {})
        stats["clips"] = (_clip_crosswalk().get("counts") or {})
        stats["neo4j"] = graph
        stats["neo4j_clips"] = clip_graph
        _log_receipt("studio.assets.online", f"STUDIO ASSETS ONLINE: {stats['total']} assets on :8108", stats)
        state = "ready" if (not STUDIO_NEO4J_HTTP or (graph.get("ok") and clip_graph.get("ok"))) else "degraded"
        _STARTUP_REFRESH.update({"state": state, "finished_at": int(time.time())})
    except Exception as exc:
        _STARTUP_REFRESH.update({"state": "error", "error": str(exc)[:240],
                                 "finished_at": int(time.time())})
        print(f"[studio-assets] startup ingest error (serving anyway): {exc}", file=sys.stderr)


def _start_startup_refresh() -> threading.Thread:
    worker = threading.Thread(target=_startup_refresh, name="studio-assets-startup-refresh", daemon=True)
    worker.start()
    return worker


@asynccontextmanager
async def lifespan(_app: FastAPI):
    _init_db()
    _start_startup_refresh()
    yield


app = FastAPI(title="govOS v2 Studio-Asset Service", version=VERSION, lifespan=lifespan)

API = "/api/v2"

# ── Project management API ────────────────────────────────────────────────────
try:
    from services.studio_assets.app.project_api import router as _project_router
    app.include_router(_project_router)
except Exception as _proj_err:
    print(f"[studio-assets] project_api not loaded: {_proj_err}", file=sys.stderr)



def _require_maintenance_auth(authorization: str | None) -> dict | None:
    return security.require_studio_owner(authorization)


def auth_dependency_status() -> dict:
    required = security.REQUIRE_AUTH
    configured = bool(security.INTERNAL_SERVICE_TOKEN and security.AUTH_INTROSPECTION_URL)
    if not required:
        return {"required": False, "configured": configured, "ready": True}
    if not configured:
        return {"required": True, "configured": False, "ready": False}
    try:
        # A public /ready response only proves that auth is alive. Probe introspection with a
        # deliberately inactive token to prove this service's X-Service-Token is trusted too.
        request = urllib.request.Request(
            security.AUTH_INTROSPECTION_URL,
            data=json.dumps({"token": "studio-assets-readiness-probe"}).encode(),
            headers={"Content-Type": "application/json",
                     "X-Service-Token": security.INTERNAL_SERVICE_TOKEN},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=security.AUTH_REQUEST_TIMEOUT) as response:
            ready = response.status == 200
    except (OSError, urllib.error.URLError):
        ready = False
    return {"required": True, "configured": True, "ready": ready}


def _row(r: sqlite3.Row) -> dict:
    d = dict(r)
    d["has_thumb"] = bool(d.get("thumb_file") and os.path.isfile(d["thumb_file"]))
    try:
        d["provenance"] = json.loads(d.get("provenance_json") or "{}")
    except json.JSONDecodeError:
        d["provenance"] = {}
    d.pop("provenance_json", None)
    d.pop("thumb_file", None)
    d.pop("container_path", None)
    return d


@app.get(f"{API}/live")
def live():
    return {"status": "alive", "service": "studio-assets", "version": VERSION, "port": 8108,
            "crosswalk_schema": _crosswalk().get("_schema"),
            "clip_crosswalk_schema": _clip_crosswalk().get("_schema"),
            "startup_refresh": _STARTUP_REFRESH.get("state", "unknown")}


@app.get(f"{API}/ready")
def ready():
    try:
        with _db() as conn:
            conn.execute("SELECT 1").fetchone()
        crosswalk_ready = bool(_crosswalk())
        clip_crosswalk_ready = bool(_clip_crosswalk())
        graph = neo4j_projection_status()
        clip_graph = clip_projection_status()
        auth = auth_dependency_status()
        is_ready = (
            crosswalk_ready
            and clip_crosswalk_ready
            and _CATALOG_STATUS["ready"]
            and auth["ready"]
            and (not STUDIO_NEO4J_HTTP or (graph["ready"] and clip_graph["ready"]))
        )
        content = {
            "status": "ready" if is_ready else "not-ready",
            "service": "studio-assets",
            "catalog": _CATALOG_STATUS,
            "auth": auth,
            "neo4j": graph,
            "neo4j_clips": clip_graph,
        }
        return content if is_ready else JSONResponse(status_code=503, content=content)
    except sqlite3.Error:
        return JSONResponse(status_code=503, content={"status": "not-ready", "service": "studio-assets"})


@app.get(f"{API}/health")
def health():
    with _db() as conn:
        total = conn.execute("SELECT COUNT(*) FROM assets").fetchone()[0]
        by_source = {r[0]: r[1] for r in conn.execute("SELECT source, COUNT(*) FROM assets GROUP BY source")}
    crosswalk = _crosswalk()
    clips = _clip_crosswalk()
    graph = neo4j_projection_status()
    clip_graph = clip_projection_status()
    auth = auth_dependency_status()
    graph_ok = graph["ready"] and clip_graph["ready"] if STUDIO_NEO4J_HTTP else True
    healthy = bool(crosswalk and clips and graph_ok and auth["ready"] and _CATALOG_STATUS["ready"])
    return {"status": "healthy" if healthy else "degraded",
            "service": "studio-assets", "version": VERSION, "asset_count": total, "by_source": by_source,
            "crosswalk": crosswalk.get("counts", {}), "clips": clips.get("counts", {}),
            "catalog": _CATALOG_STATUS, "auth": auth, "neo4j": graph, "neo4j_clips": clip_graph}


@app.get(f"{API}/stats")
def stats():
    with _db() as conn:
        total = conn.execute("SELECT COUNT(*) FROM assets").fetchone()[0]
        total_bytes = conn.execute("SELECT COALESCE(SUM(size),0) FROM assets").fetchone()[0]
        by_label = [dict(r) for r in conn.execute(
            "SELECT label, COUNT(*) n, COALESCE(SUM(size),0) bytes FROM assets GROUP BY label ORDER BY bytes DESC")]
        by_ext = [dict(r) for r in conn.execute(
            "SELECT ext, COUNT(*) n FROM assets GROUP BY ext ORDER BY n DESC LIMIT 25")]
    return {"total": total, "total_bytes": total_bytes, "total_gb": round(total_bytes / 1e9, 2),
            "by_label": by_label, "by_ext": by_ext, "crosswalk": _crosswalk().get("counts", {}),
            "clips": _clip_crosswalk().get("counts", {})}


@app.get(f"{API}/crosswalk")
def get_crosswalk(
    tenant: str | None = Query(default=None),
    character: str | None = Query(default=None),
    style: str | None = Query(default=None),
    graph: bool = Query(default=False),
):
    data = _crosswalk()
    if not data:
        raise HTTPException(status_code=503, detail={"error": "crosswalk unavailable"})
    tenant_ids = {tenant} if tenant else set()
    if tenant:
        tenant_ids.update(row.get("id") for row in data.get("tenants", []) if row.get("film_key") == tenant)
    wanted = _norm(character or "")
    assignments = []
    for row in data.get("assignments", []):
        if tenant_ids and row.get("tenant") not in tenant_ids:
            continue
        if style and row.get("style") != style:
            continue
        names = [row.get("character", ""), row.get("character_id", ""), *(row.get("aliases") or [])]
        if wanted and wanted not in {_norm(name) for name in names}:
            continue
        assignments.append(row)
    result = {"schema": data.get("_schema"), "generated_at": data.get("generated_at"),
              "render_contract": data.get("render_contract", {}), "counts": data.get("counts", {}),
              "styles": data.get("styles", {}), "tenants": data.get("tenants", []),
              "characters": data.get("characters", []), "assignments": assignments,
              "assets": data.get("assets", [])}
    if graph:
        result.update({"nodes": data.get("nodes", []), "edges": data.get("edges", [])})
    return result


@app.get(f"{API}/crosswalk/resolve")
def get_assignment(tenant: str = Query(..., min_length=1),
                   character: str = Query(..., min_length=1), style: str = Query(default="")):
    assignment = resolve_assignment(tenant, character, style)
    if not assignment:
        raise HTTPException(status_code=404, detail={"error": "assignment not found", "tenant": tenant,
                                                     "character": character, "style": style})
    return {"assignment": assignment}


@app.get(f"{API}/tenants")
def crosswalk_tenants():
    return {"tenants": _crosswalk().get("tenants", [])}


@app.get(f"{API}/characters")
def crosswalk_characters():
    return {"characters": _crosswalk().get("characters", [])}


@app.get(f"{API}/styles")
def crosswalk_styles():
    return {"styles": _crosswalk().get("styles", {})}


def _maintenance_failure(operation: str, exc: Exception) -> JSONResponse:
    print(f"[studio-assets] {operation} failed: {type(exc).__name__}", file=sys.stderr)
    return JSONResponse(
        status_code=503,
        content={"ok": False, "error": f"{operation} unavailable", "error_type": type(exc).__name__},
    )


@app.post(f"{API}/crosswalk/sync")
def post_crosswalk_sync(authorization: str | None = Header(default=None)):
    _require_maintenance_auth(authorization)
    try:
        result = sync_crosswalk_graph()
    except Exception as exc:
        return _maintenance_failure("crosswalk sync", exc)
    if not result.get("ok"):
        return JSONResponse(status_code=503, content=result)
    return result


@app.get(f"{API}/clips/recommendations")
def clip_recommendations(
    emotion: str = Query(default=""),
    role: str = Query(default=""),
    project: str = Query(default=""),
    state: str = Query(default="semantic_ready"),
    limit: int = Query(default=24, ge=1, le=500),
):
    data = _clip_crosswalk()
    if not data:
        raise HTTPException(status_code=503, detail={"error": "clip crosswalk unavailable"})
    rows = data.get("clips", [])
    if emotion:
        rows = [row for row in rows if _norm(row.get("emotion", "")) == _norm(emotion)]
    if role:
        wanted = _norm(role)
        rows = [row for row in rows if wanted == _norm(row.get("role", "")) or
                wanted in {_norm(value) for value in row.get("tracking_roles", [])}]
    if project:
        rows = [row for row in rows if _norm(row.get("project", "")) == _norm(project)]
    if state:
        rows = [row for row in rows if _norm(row.get("semantic_state", "")) == _norm(state)]
    rows = sorted(rows, key=lambda row: (
        float(row.get("confidence", 0)), float(row.get("rig_reference_score", 0)),
        float(row.get("size", 0))), reverse=True)[:limit]
    return {"schema": data.get("_schema"), "count": len(rows), "filters": {
        "emotion": emotion, "role": role, "project": project, "state": state}, "clips": rows}


@app.post(f"{API}/clips/sync")
def post_clip_sync(authorization: str | None = Header(default=None)):
    _require_maintenance_auth(authorization)
    try:
        result = sync_clip_graph()
    except Exception as exc:
        return _maintenance_failure("clip sync", exc)
    if not result.get("ok"):
        return JSONResponse(status_code=503, content=result)
    return result


@app.get(f"{API}/assets")
def list_assets(
    q: str | None = Query(default=None, description="substring match on name/path"),
    label: str | None = Query(default=None),
    ext: str | None = Query(default=None),
    tenant: str | None = Query(default=None),
    character_id: str | None = Query(default=None),
    style: str | None = Query(default=None),
    tenant_id: str | None = Query(default=None, description="filter by studio project folder (e.g. film_12stones)"),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
):
    where, params = [], {}
    if q:
        where.append("(name LIKE :q OR host_path LIKE :q)")
        params["q"] = f"%{q}%"
    if label:
        where.append("label = :label")
        params["label"] = label
    if ext:
        where.append("ext = :ext")
        params["ext"] = ext.lower().lstrip(".")
    if tenant:
        where.append("tenant = :tenant")
        params["tenant"] = tenant
    if character_id:
        where.append("character_id = :character_id")
        params["character_id"] = character_id
    if style:
        where.append("style_id = :style")
        params["style"] = style
    if tenant_id:
        where.append("host_path LIKE :tenant_folder")
        params["tenant_folder"] = f"%{tenant_id}%"
    clause = (" WHERE " + " AND ".join(where)) if where else ""
    params["limit"] = limit
    params["offset"] = offset
    with _db() as conn:
        total = conn.execute(f"SELECT COUNT(*) FROM assets{clause}", params).fetchone()[0]
        rows = conn.execute(
            f"SELECT * FROM assets{clause} ORDER BY mtime DESC LIMIT :limit OFFSET :offset", params
        ).fetchall()
    return {"total": total, "limit": limit, "offset": offset, "assets": [_row(r) for r in rows]}


@app.get(f"{API}/assets/search")
def search(q: str = Query(..., min_length=1), limit: int = Query(default=50, ge=1, le=500)):
    with _db() as conn:
        rows = conn.execute(
            "SELECT * FROM assets WHERE name LIKE :q OR host_path LIKE :q ORDER BY mtime DESC LIMIT :limit",
            {"q": f"%{q}%", "limit": limit},
        ).fetchall()
    return {"query": q, "count": len(rows), "assets": [_row(r) for r in rows]}


def _get_row(key: str) -> sqlite3.Row:
    with _db() as conn:
        r = conn.execute("SELECT * FROM assets WHERE key = ?", (key,)).fetchone()
    if not r:
        raise HTTPException(status_code=404, detail={"error": "asset not found", "key": key})
    return r


@app.get(f"{API}/assets/{{key}}")
def get_asset(key: str):
    return _row(_get_row(key))


@app.get(f"{API}/assets/{{key}}/crosswalk")
def get_asset_crosswalk(key: str):
    asset = _row(_get_row(key))
    assignment = None
    data = _crosswalk()
    if asset.get("assignment_id"):
        assignment = next((row for row in data.get("assignments", [])
                           if row.get("id") == asset["assignment_id"]), None)
    if not assignment and asset.get("tenant") and asset.get("character_id"):
        assignment = resolve_assignment(asset["tenant"], asset["character_id"], asset.get("style_id") or "")
    assignment_id = asset.get("assignment_id") or (assignment or {}).get("id")
    return {"asset": asset, "assignment": assignment,
            "edges": [edge for edge in data.get("edges", [])
                      if assignment_id and ("assignment:" + assignment_id) in
                      {edge.get("src"), edge.get("dst")} ]}


@app.get(f"{API}/assets/{{key}}/thumb")
def get_thumb(key: str):
    r = _get_row(key)
    tf = r["thumb_file"]
    if not tf or not os.path.isfile(tf):
        raise HTTPException(status_code=404, detail={"error": "no thumbnail", "key": key})
    return FileResponse(tf, media_type="image/jpeg")


def _path_is_allowed(path: str) -> bool:
    try:
        real = os.path.realpath(path)
    except OSError:
        return False
    return any(real == m or real.startswith(m.rstrip("/") + "/") for m in ASSET_MOUNTS)


@app.get(f"{API}/assets/{{key}}/file")
def get_file(key: str):
    r = _get_row(key)
    cpath = r["container_path"]
    if not cpath or not _path_is_allowed(cpath) or not os.path.isfile(cpath):
        raise HTTPException(status_code=404, detail={"error": "file not available", "key": key})
    for attempt in range(3):
        try:
            with open(cpath, "rb") as fh:
                fh.read(1)
            break
        except OSError:
            if attempt == 2:
                raise HTTPException(status_code=503,
                                    detail={"error": "asset temporarily locked (render in progress)", "key": key})
            time.sleep(0.2)
    media = mimetypes.guess_type(r["name"])[0] or "application/octet-stream"
    return FileResponse(cpath, media_type=media, filename=r["name"])


@app.post(f"{API}/reindex")
def post_reindex(authorization: str | None = Header(default=None)):
    """Re-ingest the existing catalog + re-stat the finalized vaults. Writes ONLY to this
    service's private SQLite — never mutates any asset. Safe, idempotent."""
    _require_maintenance_auth(authorization)
    try:
        return reindex()
    except Exception as exc:
        return _maintenance_failure("catalog reindex", exc)
