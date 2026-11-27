"""Owner-gated, journaled publisher for the curated Element LOTUS WordPress pages.

Only page content from content/wordpress/element_lotus/manifest.json is eligible.
WordPress credentials come from the local connector token store and never enter logs.
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None

from services.connectors.token_store import get_token

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "content" / "wordpress" / "element_lotus"
PRIVATE_DIR = Path(os.environ.get("LOCAL_AI_PUBLISH_DATA", Path.home() / ".quad-os" / "publishing"))
DB = PRIVATE_DIR / "elementlotus.sqlite3"
ALLOWED = {"/", "/about/", "/contact/", "/films/", "/music/", "/partner/", "/studio/", "/civic/"}
TRANSIENT = {408, 425, 429, 500, 502, 503, 504}


def _db():
    PRIVATE_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE IF NOT EXISTS runs(id TEXT PRIMARY KEY, status TEXT NOT NULL, started_at TEXT NOT NULL, updated_at TEXT NOT NULL, details TEXT NOT NULL)")
    conn.execute("CREATE TABLE IF NOT EXISTS backups(run_id TEXT NOT NULL, slug TEXT NOT NULL, page_id INTEGER NOT NULL, before_json TEXT NOT NULL, before_hash TEXT NOT NULL, after_hash TEXT, status TEXT NOT NULL, PRIMARY KEY(run_id,slug))")
    conn.commit()
    return conn


def _credentials():
    row = get_token("wordpress")
    if not row or not row.get("access_token"):
        raise RuntimeError("WordPress connector needs an Application Password")
    label = (row.get("account_label") or os.environ.get("WP_SITE_URL", "")).strip().rstrip("/")
    parsed = urlparse(label)
    if parsed.scheme != "https" or parsed.hostname not in {"elementlotus.com", "www.elementlotus.com"}:
        raise RuntimeError("WordPress connector must be configured for the ElementLOTUS.com HTTPS site")
    return label + "/wp-json/wp/v2/", "Basic " + row["access_token"]


def _get(url, headers, params=None):
    if requests is None:
        raise RuntimeError("requests dependency is unavailable")
    for attempt in range(3):
        response = requests.get(url, headers=headers, params=params, timeout=20)
        if response.status_code not in TRANSIENT or attempt == 2:
            response.raise_for_status()
            return response
        time.sleep(0.5 * (attempt + 1))


def _put(url, headers, payload):
    for attempt in range(3):
        response = requests.post(url, headers=headers, json=payload, timeout=25)
        if response.status_code not in TRANSIENT or attempt == 2:
            response.raise_for_status()
            return response
        time.sleep(0.5 * (attempt + 1))


def plan():
    manifest = json.loads((PACKAGE / "manifest.json").read_text(encoding="utf-8"))
    entries = []
    for page in manifest.get("pages", []):
        slug = page.get("slug")
        if slug not in ALLOWED:
            continue
        source = PACKAGE / page["output"]
        content = source.read_text(encoding="utf-8")
        entries.append({"slug": slug, "title": page["title"], "content": content,
                        "sha256": hashlib.sha256(content.encode()).hexdigest()})
    if {p["slug"] for p in entries} != ALLOWED:
        raise RuntimeError("Curated manifest is incomplete; expected exactly eight Element LOTUS pages")
    return entries


def status():
    with _db() as conn:
        row = conn.execute("SELECT id,status,started_at,updated_at,details FROM runs ORDER BY started_at DESC LIMIT 1").fetchone()
    connector = get_token("wordpress")
    return {"service": "elementlotus-wordpress-publisher", "healthy": bool(connector and connector.get("access_token")),
            "connector_configured": bool(connector and connector.get("access_token")),
            "last_run": dict(row) if row else None, "scope": sorted(ALLOWED)}


def preview():
    pages = plan()
    return {"site": "ElementLOTUS.com", "count": len(pages), "pages": [
        {"slug": page["slug"], "title": page["title"], "sha256": page["sha256"]}
        for page in pages
    ]}


def publish(run_id: str):
    """Apply the checked-in eight page package, preserving live backups per page."""
    base, auth = _credentials()
    headers = {"Authorization": auth, "Content-Type": "application/json"}
    pages = plan()
    now = datetime.now(timezone.utc).isoformat()
    with _db() as conn:
        existing = conn.execute("SELECT status FROM runs WHERE id=?", (run_id,)).fetchone()
        if existing:
            if existing["status"] == "complete":
                return {"run_id": run_id, "status": "complete", "idempotent_replay": True}
            raise RuntimeError("This run ID already exists and requires recovery review")
        conn.execute("INSERT INTO runs VALUES(?,?,?,?,?)", (run_id, "running", now, now, "{}"))
        conn.commit()
    outcomes = []
    try:
        for page in pages:
            slug = page["slug"]
            found = _get(urljoin(base, "pages"), headers, {"slug": "home" if slug == "/" else slug.strip("/"), "status": "publish,draft,private", "context": "edit"}).json()
            if not found:
                raise RuntimeError(f"Approved destination page is missing for {slug}; refusing to create a new route")
            current = found[0]
            # The backup is only restorable if we hold the RAW title and block markup (context=edit). Never write without it.
            if "raw" not in (current.get("content") or {}) or "raw" not in (current.get("title") or {}):
                raise RuntimeError(f"No editable copy of {slug} was returned; refusing to overwrite a page that cannot be restored")
            before = {k: current.get(k) for k in ("id", "slug", "status", "title", "content", "link")}
            before_hash = hashlib.sha256(json.dumps(before, sort_keys=True).encode()).hexdigest()
            with _db() as conn:
                conn.execute("INSERT INTO backups VALUES(?,?,?,?,?,?,?)", (run_id, slug, int(current["id"]), json.dumps(before), before_hash, page["sha256"], "write_pending"))
                conn.commit()
            if hashlib.sha256((current.get("content", {}).get("raw") or current.get("content", {}).get("rendered", "")).encode()).hexdigest() == page["sha256"]:
                with _db() as conn:
                    conn.execute("UPDATE backups SET status='already_current' WHERE run_id=? AND slug=?", (run_id, slug))
                    conn.commit()
                outcomes.append({"slug": slug, "status": "already_current", "page_id": current["id"]})
                continue
            updated = _put(urljoin(base, f"pages/{current['id']}"), headers, {"title": page["title"], "content": page["content"]}).json()
            remote_content = updated.get("content", {}).get("raw") or updated.get("content", {}).get("rendered", "")
            after_hash = hashlib.sha256(remote_content.encode()).hexdigest()
            if updated.get("slug") != current.get("slug") or after_hash != page["sha256"]:
                raise RuntimeError(f"Post-write verification failed for {slug}")
            with _db() as conn:
                conn.execute("UPDATE backups SET status='verified' WHERE run_id=? AND slug=?", (run_id, slug))
                conn.commit()
            outcomes.append({"slug": slug, "status": "verified", "page_id": current["id"]})
    except Exception as exc:
        recovery = None
        try:
            recovery = recover(run_id)
        except Exception as recovery_exc:
            recovery = {"status": "recovery_unavailable", "error": str(recovery_exc)[:240]}
        with _db() as conn:
            final_state = "recovered" if recovery and recovery.get("status") == "recovered" else "needs_recovery"
            conn.execute("UPDATE runs SET status=?,updated_at=?,details=? WHERE id=?",
                         (final_state, datetime.now(timezone.utc).isoformat(), json.dumps({"completed": outcomes, "error": str(exc)[:300], "self_heal": recovery}), run_id))
            conn.commit()
        raise
    with _db() as conn:
        conn.execute("UPDATE runs SET status='complete',updated_at=?,details=? WHERE id=?",
                     (datetime.now(timezone.utc).isoformat(), json.dumps({"pages": outcomes}), run_id))
        conn.commit()
    return {"run_id": run_id, "status": "complete", "pages": outcomes}


def recover(run_id: str):
    """Conservative self-heal: restore a backed-up page only if remote still equals our write."""
    base, auth = _credentials()
    headers = {"Authorization": auth, "Content-Type": "application/json"}
    with _db() as conn:
        rows = conn.execute("SELECT * FROM backups WHERE run_id=? AND status IN ('verified','write_pending')", (run_id,)).fetchall()
    restored, skipped = [], []
    for row in rows:
        if not row["after_hash"]:
            skipped.append(row["slug"])
            continue
        live = _get(urljoin(base, f"pages/{row['page_id']}"), headers, {"context": "edit"}).json()
        live_content = live.get("content", {}).get("raw") or live.get("content", {}).get("rendered", "")
        if hashlib.sha256(live_content.encode()).hexdigest() != row["after_hash"]:
            skipped.append(row["slug"])
            continue
        before = json.loads(row["before_json"])
        _put(urljoin(base, f"pages/{row['page_id']}"), headers, {"title": before.get("title", {}).get("raw", ""), "content": before.get("content", {}).get("raw", before.get("content", {}).get("rendered", "")), "status": before["status"]})
        restored.append(row["slug"])
    with _db() as conn:
        conn.execute("UPDATE runs SET status=?,updated_at=?,details=? WHERE id=?", ("recovered" if not skipped else "recovery_partial", datetime.now(timezone.utc).isoformat(), json.dumps({"restored": restored, "skipped_remote_changed": skipped}), run_id))
        conn.commit()
    return {"run_id": run_id, "status": "recovered" if not skipped else "recovery_partial", "restored": restored, "skipped_remote_changed": skipped}
