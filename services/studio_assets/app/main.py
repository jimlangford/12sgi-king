"""govOS v2 Studio-Asset Service — read-only manager/serving layer over the elementLOTUS studio vault.

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
    start (sys.exit 1). The VAULT can never be pruned or mutated from here. GET-only HTTP surface;
    no delete/move/put/patch routes exist. All writes go to private named volumes (/data/db,
    /data/derived) only.
  * Live renders: the supplemental scan is stat-only (metadata, no byte reads) and skips the live
    ComfyUI/output render dir. File-serving pre-probes with retry so a file held open by a render
    returns 503 rather than a torn read.
"""

import hashlib
import json
import mimetypes
import os
import sqlite3
import sys
import time
from contextlib import asynccontextmanager, contextmanager

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse

# ── Config (all overridable via env; defaults match the compose stanza) ──────────────────────
VERSION = os.environ.get("VERSION", "1.0.0")
DB_PATH = os.environ.get("STUDIO_ASSETS_DB_PATH", "/data/db/studio_assets.db")
INDEX_JSON = os.environ.get("STUDIO_INDEX_JSON", "/data/index/asset_index.json")
THUMBS_DIR = os.environ.get("STUDIO_THUMBS_DIR", "/data/index/thumbnails")

# Container mount points that MUST be read-only. The fail-closed probe checks every one.
ASSET_MOUNTS = [
    m.strip()
    for m in os.environ.get(
        "STUDIO_ASSET_MOUNTS",
        "/data/assets/mp4,/data/assets/finals,/data/assets/audio,/data/assets/hero,"
        "/data/assets/exports,/data/assets/jimmy_lora,/data/assets/comfy_output,"
        "/data/assets/comfy_input,/data/assets/batch,/data/index",
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

REQUIRE_AUTH = os.environ.get("STUDIO_ASSETS_REQUIRE_AUTH", "0") == "1"

WORKBOARD_SOURCE = "govos-v2-studio-assets"


# ── FAIL-CLOSED write-probe: prove every asset mount is read-only, or refuse to start ─────────
def _assert_mounts_readonly() -> None:
    """Ground-truth guarantee that the VAULT cannot be mutated: attempt to create a probe file in
    each configured asset mount. If the write SUCCEEDS the mount is read-WRITE -> abort (fail
    closed). This is stronger than parsing /proc/self/mountinfo because it is kernel-enforced."""
    violations = []
    checked = []
    for mount in ASSET_MOUNTS:
        if not os.path.isdir(mount):
            # Not present (e.g. running unit tests outside the container). Can't prune what isn't
            # mounted; log and continue rather than false-fail.
            print(f"[studio-assets] WARN mount not present, skipping RO probe: {mount}", file=sys.stderr)
            continue
        probe = os.path.join(mount, ".studio_asset_ro_probe")
        try:
            fd = os.open(probe, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except OSError:
            checked.append(mount)  # write refused == read-only == good
            continue
        # Write SUCCEEDED -> mount is writable -> catastrophic. Clean up and fail closed.
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
                indexed_at INTEGER
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_assets_name ON assets(name)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_assets_label ON assets(label)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_assets_ext ON assets(ext)")
        conn.commit()


# ── Path mapping ────────────────────────────────────────────────────────────────────────────
def _norm_host(p: str) -> str:
    return (p or "").replace("/", "\\").lower()


def host_to_container(host_path: str) -> str | None:
    """Map an absolute Windows host path (as stored in asset_index.json `rel`) to the mounted
    container path, or None if it falls outside any mount."""
    if not host_path:
        return None
    hp = _norm_host(host_path)
    for prefix, mount, _label in _PATH_MAP:
        pref = _norm_host(prefix)
        if hp == pref or hp.startswith(pref + "\\"):
            rest = host_path[len(prefix):].lstrip("\\/").replace("\\", "/")
            return mount + ("/" + rest if rest else "")
    return None


def _label_for_host(host_path: str) -> str | None:
    hp = _norm_host(host_path)
    for prefix, _mount, label in _PATH_MAP:
        pref = _norm_host(prefix)
        if hp == pref or hp.startswith(pref + "\\"):
            return label
    return None


def container_to_host(container_path: str, mount: str) -> str:
    """Best-effort inverse: build a display host path for a scanned container file."""
    for prefix, m, _label in _PATH_MAP:
        if m == mount:
            rest = container_path[len(mount):].lstrip("/").replace("/", "\\")
            return prefix + ("\\" + rest if rest else "")
    return container_path


# ── Ingest ────────────────────────────────────────────────────────────────────────────────────
def _upsert(conn, row: dict) -> None:
    conn.execute(
        """
        INSERT INTO assets (key,label,name,ext,host_path,container_path,size,mtime,thumb_file,
                            archivable,archived,source,indexed_at)
        VALUES (:key,:label,:name,:ext,:host_path,:container_path,:size,:mtime,:thumb_file,
                :archivable,:archived,:source,:indexed_at)
        ON CONFLICT(key) DO UPDATE SET
            label=excluded.label, name=excluded.name, ext=excluded.ext,
            container_path=excluded.container_path, size=excluded.size, mtime=excluded.mtime,
            thumb_file=excluded.thumb_file, archivable=excluded.archivable,
            archived=excluded.archived, source=excluded.source, indexed_at=excluded.indexed_at
        """,
        row,
    )


def ingest_index() -> int:
    """Ingest the asset-quad-os lane's existing catalog (authoritative, carries thumbnails)."""
    if not os.path.isfile(INDEX_JSON):
        print(f"[studio-assets] no asset_index.json at {INDEX_JSON}; skipping index ingest", file=sys.stderr)
        return 0
    with open(INDEX_JSON, encoding="utf-8") as f:
        data = json.load(f)
    items = data.get("items", []) if isinstance(data, dict) else (data or [])
    now = int(time.time())
    n = 0
    with _db() as conn:
        for it in items:
            host_path = it.get("rel") or ""
            cpath = host_to_container(host_path)
            thumb = it.get("thumb") or ""
            thumb_file = None
            if thumb:
                thumb_file = os.path.join(THUMBS_DIR, os.path.basename(thumb.replace("\\", "/")))
            name = it.get("name") or os.path.basename(host_path.replace("\\", "/"))
            _upsert(
                conn,
                {
                    "key": it.get("key") or hashlib.sha1(host_path.encode("utf-8")).hexdigest()[:16],
                    "label": it.get("label") or _label_for_host(host_path) or "renders",
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
                    "indexed_at": now,
                },
            )
            n += 1
        conn.commit()
    print(f"[studio-assets] ingested {n} item(s) from asset_index.json", file=sys.stderr)
    return n


def scan_supplemental() -> int:
    """Stat-only supplemental scan of finalized vaults the index misses (e.g. the flat mp4/ vault).
    Metadata only — never opens a file for reading. Skips anything already catalogued by host path."""
    now = int(time.time())
    added = 0
    seen = 0
    with _db() as conn:
        known = {r["host_path"] for r in conn.execute("SELECT host_path FROM assets").fetchall()}
        for root in SCAN_ROOTS:
            if not os.path.isdir(root):
                continue
            for dirpath, _dirs, files in os.walk(root):
                for fn in files:
                    if fn.startswith(".studio_asset_ro_probe"):
                        continue
                    seen += 1
                    if seen > SCAN_MAX_FILES:
                        print(f"[studio-assets] scan cap {SCAN_MAX_FILES} hit; stopping", file=sys.stderr)
                        conn.commit()
                        return added
                    cpath = os.path.join(dirpath, fn)
                    mount = root
                    host_path = container_to_host(cpath, mount)
                    if host_path in known:
                        continue
                    try:
                        st = os.stat(cpath)  # metadata only; no byte read
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
                            "indexed_at": now,
                        },
                    )
                    known.add(host_path)
                    added += 1
        conn.commit()
    print(f"[studio-assets] supplemental scan added {added} file(s)", file=sys.stderr)
    return added


def _emit(action: str, event: str, payload: dict) -> None:
    """Report to the board like a lane (best-effort; a bus hiccup never breaks the service)."""
    try:
        from services.v2_workboard import emit_workboard_job

        emit_workboard_job(
            source=WORKBOARD_SOURCE,
            action=action,
            event=event,
            lane="engineering",  # IO-only asset indexing self-heals; no human gate
            payload=payload,
        )
    except Exception:
        pass


def reindex() -> dict:
    n_index = ingest_index()
    n_scan = scan_supplemental()
    with _db() as conn:
        total = conn.execute("SELECT COUNT(*) FROM assets").fetchone()[0]
    _emit(
        "studio.index.rescanned",
        f"STUDIO ASSET INDEX: {total} assets ({n_index} indexed + {n_scan} scanned)",
        {"total": total, "from_index": n_index, "from_scan": n_scan},
    )
    return {"total": total, "from_index": n_index, "from_scan": n_scan}


# ── App ─────────────────────────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(_app: FastAPI):
    _init_db()
    try:
        stats = reindex()
        _emit("studio.assets.online", f"STUDIO ASSETS ONLINE: {stats['total']} assets on :8108", stats)
    except Exception as exc:  # never let a bad ingest stop the read API from serving
        print(f"[studio-assets] startup ingest error (serving anyway): {exc}", file=sys.stderr)
    yield


app = FastAPI(title="govOS v2 Studio-Asset Service", version=VERSION, lifespan=lifespan)

API = "/api/v2"


def _row(r: sqlite3.Row) -> dict:
    d = dict(r)
    d["has_thumb"] = bool(d.get("thumb_file") and os.path.isfile(d["thumb_file"]))
    d.pop("thumb_file", None)
    d.pop("container_path", None)  # internal; not exposed
    return d


@app.get(f"{API}/live")
def live():
    return {"status": "alive", "service": "studio-assets", "version": VERSION, "port": 8108}


@app.get(f"{API}/ready")
def ready():
    try:
        with _db() as conn:
            conn.execute("SELECT 1").fetchone()
        return {"status": "ready", "service": "studio-assets"}
    except sqlite3.Error:
        return JSONResponse(status_code=503, content={"status": "not-ready", "service": "studio-assets"})


@app.get(f"{API}/health")
def health():
    with _db() as conn:
        total = conn.execute("SELECT COUNT(*) FROM assets").fetchone()[0]
        by_source = {r[0]: r[1] for r in conn.execute("SELECT source, COUNT(*) FROM assets GROUP BY source")}
    return {"status": "healthy", "service": "studio-assets", "version": VERSION,
            "asset_count": total, "by_source": by_source}


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
            "by_label": by_label, "by_ext": by_ext}


@app.get(f"{API}/assets")
def list_assets(
    q: str | None = Query(default=None, description="substring match on name/path"),
    label: str | None = Query(default=None),
    ext: str | None = Query(default=None),
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


@app.get(f"{API}/assets/{{key}}/thumb")
def get_thumb(key: str):
    r = _get_row(key)
    tf = r["thumb_file"]
    if not tf or not os.path.isfile(tf):
        raise HTTPException(status_code=404, detail={"error": "no thumbnail", "key": key})
    return FileResponse(tf, media_type="image/jpeg")


def _path_is_allowed(path: str) -> bool:
    """Path-traversal guard: only serve files that resolve INSIDE a configured read-only mount."""
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
    # Pre-probe with retry so a file a render still holds open returns 503, not a torn read.
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
def post_reindex():
    """Re-ingest the existing catalog + re-stat the finalized vaults. Writes ONLY to this
    service's private SQLite — never mutates any asset. Safe, idempotent."""
    return reindex()
