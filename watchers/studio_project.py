# -*- coding: utf-8 -*-
"""studio_project.py — Studio Project Brain: project node registry + Neo4j spine.

Manages the Project node as a first-class graph citizen that scopes all
studio department work (scripts, storyboards, shots, audio, assets, releases).

Storage:
  Projects are persisted to a local JSON store at
  ``~/.king/studio_projects.json`` (machine-local, never committed).
  When Neo4j is reachable they are also written to layer='studio_projects'
  in the private graph so provenance and cross-department edges can be
  traversed via Cypher.

Edge types written to Neo4j:
  HAS_SCRIPT       (Project)-[:HAS_SCRIPT]->(Artifact)
  HAS_STORYBOARD   (Project)-[:HAS_STORYBOARD]->(Artifact)
  HAS_SHOT         (Project)-[:HAS_SHOT]->(Artifact)
  HAS_ASSET        (Project)-[:HAS_ASSET]->(Artifact)
  HAS_AUDIO        (Project)-[:HAS_AUDIO]->(Artifact)
  HAS_RELEASE      (Project)-[:HAS_RELEASE]->(Artifact)

Timeline:
  ``timeline_for_project()`` reads the workboard dispatch log for entries
  whose payload carries ``project_id``, groups them by scene/phase, and maps
  each to one of the eight pipeline stages:
    Script · Storyboard · Kandinsky · LTX · Editor · Logic · FCP · Release

  Stage state: done → ✓   running/in-progress → ▶   queued → ○   failed → ✗

Resilience:
  Missing store file, absent Neo4j, or empty workboard all result in soft
  skips rather than crashes, consistent with private_spine.py.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from uuid import uuid4

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
HOME = Path.home()
NEO = os.environ.get("NEO4J_HTTP", "http://127.0.0.1:7474/db/neo4j/tx/commit")
LAYER = "studio_projects"

STORE_SCHEMA_VERSION = "1.0"

# Local store — machine-only, never committed
_DEFAULT_STORE = HOME / ".king" / "studio_projects.json"

# Workboard + event bus — best-effort; import failures never block studio operations.
try:
    if str(REPO) not in sys.path:
        sys.path.insert(0, str(REPO))
    from services.v2_workboard import emit_workboard_job as _emit_workboard
    from services.event_bus import publish_event as _publish_platform_event
except Exception:
    _emit_workboard = None  # type: ignore[assignment]
    _publish_platform_event = None  # type: ignore[assignment]

# Workboard log (same default as private_spine / v2_workboard)
_DEFAULT_WORKBOARD = REPO / ".dispatch_log.jsonl"

# Valid project types
PROJECT_TYPES = {"Film", "Music", "Game", "Civic", "Architecture", "Education"}

# Valid project statuses
PROJECT_STATUSES = {"active", "development", "production", "post", "released", "archived"}

# ── Pipeline stage definitions ─────────────────────────────────────────────────
#
# Full 16-stage production pipeline — order is authoritative for the Timeline
# panel.  Not every project uses every stage; stage profiles below filter by
# project type.
#
# Each stage record:
#   id        — canonical identifier (stable; used as dict key)
#   label     — display label
#   panel     — Naga console panel targeted when clicking the cell
#   dept      — department slug (matches studiodepts routing), or None
#   matchers  — keywords matched against workboard .event / .job.action
#                when no canonical department field is present
#                (source = legacy_inferred, confidence = 0.72)
PIPELINE_STAGES = [
    {
        "id": "writing", "label": "Writing", "panel": "studiodepts", "dept": "writing",
        "matchers": ["script", "writing", "dialogue", "premise", "beat_sheet", "first_draft", "treatment"],
    },
    {
        "id": "director", "label": "Director", "panel": "studiodepts", "dept": "director",
        "matchers": ["director", "director_pass", "director_review", "director_approval"],
    },
    {
        "id": "camera", "label": "Camera Plan", "panel": "studiodepts", "dept": "camera",
        "matchers": ["camera", "camera_plan", "lens_plan", "shot_list", "coverage"],
    },
    {
        "id": "storyboard", "label": "Storyboard", "panel": "studiodepts", "dept": "storyboard",
        "matchers": ["storyboard", "shot_plan", "blocking", "panel_draw"],
    },
    {
        "id": "continuity", "label": "Continuity", "panel": "studiodepts", "dept": "continuity",
        "matchers": ["continuity", "continuity_check", "continuity_review", "slate_check"],
    },
    {
        "id": "storyboard_approval", "label": "Storyboard Approval", "panel": "studiodepts", "dept": "storyboard",
        "matchers": ["storyboard_approval", "sb_approved", "approve_storyboard", "board_approved"],
    },
    {
        "id": "kandinsky", "label": "Kandinsky", "panel": "gpu", "dept": None,
        "matchers": ["kandinsky", "image_gen", "render_still", "deck_render"],
    },
    {
        "id": "motion_plan", "label": "Motion Plan", "panel": "studiodepts", "dept": "animation",
        "matchers": ["motion_plan", "motion", "keyframe_plan", "anim_plan", "rigging"],
    },
    {
        "id": "ltx", "label": "LTX", "panel": "gpu", "dept": None,
        "matchers": ["ltx", "ltx_video", "video_gen", "animate", "motion_gen"],
    },
    {
        "id": "editor", "label": "Editor", "panel": "studiodepts", "dept": "fcp",
        "matchers": ["editor", "edit_cut", "rough_cut", "fine_cut", "assembly"],
    },
    {
        "id": "take_approval", "label": "Take Approval", "panel": "studiodepts", "dept": "fcp",
        "matchers": ["take_approval", "take_approved", "approve_take", "scene_approved"],
    },
    {
        "id": "interpolation", "label": "Interpolation", "panel": "gpu", "dept": None,
        "matchers": ["interpolation", "interp", "frame_interp", "smooth_motion", "twixtor"],
    },
    {
        "id": "fcp", "label": "FCP", "panel": "studiodepts", "dept": "fcp",
        "matchers": ["fcp", "fcpxml", "timeline_export", "final_cut"],
    },
    {
        "id": "logic", "label": "Logic", "panel": "studiodepts", "dept": "logic",
        "matchers": ["logic", "audio_session", "adr", "foley", "music_cue", "mix", "audio_mix"],
    },
    {
        "id": "final_qc", "label": "Final QC", "panel": "studiodepts", "dept": "qc",
        "matchers": ["final_qc", "qc_pass", "qc_review", "quality_check", "master_review"],
    },
    {
        "id": "release", "label": "Release Approval", "panel": "ops", "dept": None,
        "matchers": ["release", "publish", "export_final", "deliver", "release_approval"],
    },
]

# Stage profiles — project types that skip certain stages.
# Unlisted stages are always included.  Values are sets of stage ids to OMIT.
_STAGE_PROFILE_OMIT: dict[str, set[str]] = {
    "Music":        {"camera", "director", "continuity", "storyboard_approval", "motion_plan", "take_approval", "interpolation", "fcp"},
    "Game":         {"continuity", "final_qc"},
    "Civic":        {"kandinsky", "ltx", "interpolation", "motion_plan", "take_approval", "storyboard_approval"},
    "Architecture": {"ltx", "interpolation", "logic", "fcp"},
    "Education":    {"interpolation"},
}

# Status → display glyph mapping
_STATUS_GLYPH = {
    "done": "✓",
    "approved": "✓",
    "in-progress": "▶",
    "running": "▶",
    "queued": "○",
    "waiting": "○",
    "failed": "✗",
    "rejected": "✗",
}

# Confidence values for timeline inference
_CONFIDENCE_CANONICAL = 1.0    # job has explicit department / stage_id field
_CONFIDENCE_INFERRED  = 0.72   # stage derived from keyword match


# ── Path safety ───────────────────────────────────────────────────────────────

def resolve_under(root: Path, requested: str) -> Path:
    """Resolve *requested* path relative to *root*, rejecting any traversal.

    Raises ValueError if the resolved path escapes the approved root (e.g.
    contains ``..``, absolute external paths, or symlink escapes).
    """
    root = root.resolve()
    candidate = (root / requested).resolve()
    if candidate != root and root not in candidate.parents:
        raise ValueError(f"path escapes approved root: {requested!r}")
    return candidate


# ── Helpers ───────────────────────────────────────────────────────────────────

def _iso_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _content_hash(data: dict) -> str:
    raw = json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True)
    return "sha256:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _load_store(store_path: Path | None = None) -> dict:
    path = store_path or _DEFAULT_STORE
    if not path.exists():
        return {"schema_version": STORE_SCHEMA_VERSION, "revision": 0, "projects": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return {"schema_version": STORE_SCHEMA_VERSION, "revision": 0, "projects": []}
        # Migrate legacy stores that lack schema metadata
        data.setdefault("schema_version", STORE_SCHEMA_VERSION)
        data.setdefault("revision", 0)
        data.setdefault("projects", [])
        return data
    except Exception:
        return {"schema_version": STORE_SCHEMA_VERSION, "revision": 0, "projects": []}


def _save_store(data: dict, store_path: Path | None = None) -> None:
    """Atomically write the store: compute hashes, bump revision, write to temp then rename."""
    path = store_path or _DEFAULT_STORE
    path.parent.mkdir(parents=True, exist_ok=True)

    prev_hash = data.get("content_hash", "")
    data["schema_version"] = STORE_SCHEMA_VERSION
    data["revision"] = int(data.get("revision") or 0) + 1
    data["previous_hash"] = prev_hash
    data["updated_by"] = "owner"
    data["updated_at"] = _iso_now()
    data["content_hash"] = _content_hash(data)

    serialized = json.dumps(data, indent=2, ensure_ascii=False)

    # Atomic write: temp file in same directory then os.replace
    tmp_fd, tmp_path = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as fh:
            fh.write(serialized)
        os.replace(tmp_path, path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def _read_workboard(log_path: Path | None = None) -> list[dict]:
    path = log_path or _DEFAULT_WORKBOARD
    if not path or not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


# ── Neo4j write helpers ────────────────────────────────────────────────────────

def _neo_post(statements: list[dict]) -> bool:
    payload = json.dumps({"statements": statements}, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        NEO,
        data=payload,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            body = json.loads(resp.read())
            return not body.get("errors")
    except Exception:
        return False


def _upsert_project_node(project: dict) -> None:
    """Write a Project node to Neo4j under layer='studio_projects'."""
    _neo_post([{
        "statement": (
            "MERGE (p:Project {project_id: $pid}) "
            "SET p.title=$title, p.type=$ptype, p.status=$status, "
            "    p.created_at=$created_at, p.updated_at=$updated_at, "
            "    p.layer=$layer "
            "RETURN p.project_id"
        ),
        "parameters": {
            "pid": project["project_id"],
            "title": project.get("title", ""),
            "ptype": project.get("type", "Film"),
            "status": project.get("status", "active"),
            "created_at": project.get("created_at", ""),
            "updated_at": _iso_now(),
            "layer": LAYER,
        },
    }])


# ── Public API ────────────────────────────────────────────────────────────────

def list_projects(store_path: Path | None = None) -> list[dict]:
    """Return all projects from the local store, newest first."""
    data = _load_store(store_path)
    projects = data.get("projects") or []
    return sorted(projects, key=lambda p: p.get("created_at", ""), reverse=True)


def get_project(project_id: str, store_path: Path | None = None) -> dict | None:
    """Return a single project by ID, or None if not found."""
    for p in list_projects(store_path):
        if p.get("project_id") == project_id:
            return p
    return None


def create_project(
    title: str,
    project_type: str = "Film",
    status: str = "active",
    store_path: Path | None = None,
) -> dict:
    """Create a new Project node, persist to local store, and push to Neo4j.

    Returns the new project dict.
    """
    ptype = project_type if project_type in PROJECT_TYPES else "Film"
    pstatus = status if status in PROJECT_STATUSES else "active"
    project = {
        "project_id": str(uuid4()),
        "title": str(title).strip(),
        "type": ptype,
        "status": pstatus,
        "created_at": _iso_now(),
        "updated_at": _iso_now(),
        "layer": LAYER,
    }
    data = _load_store(store_path)
    data.setdefault("projects", []).append(project)
    _save_store(data, store_path)
    _upsert_project_node(project)
    return project


def update_project_status(
    project_id: str,
    status: str,
    store_path: Path | None = None,
) -> dict | None:
    """Update the status of an existing project. Returns updated project or None."""
    pstatus = status if status in PROJECT_STATUSES else "active"
    data = _load_store(store_path)
    projects = data.get("projects") or []
    for p in projects:
        if p.get("project_id") == project_id:
            p["status"] = pstatus
            p["updated_at"] = _iso_now()
            _save_store(data, store_path)
            _upsert_project_node(p)
            return p
    return None


def release_project(
    project_id: str,
    *,
    release_notes: str | None = None,
    social_caption: str | None = None,
    store_path: Path | None = None,
) -> dict | None:
    """Mark a project as released and queue public-surface actions.

    This is the canonical entry point for the studio release pipeline:
      1. Sets project status → 'released' in the local store + Neo4j.
      2. Emits a ``studio.project.released`` platform event for the event bus.
      3. Queues an *output* lane workboard job (social announcement draft) so
         the owner can review it before anything posts publicly.
      4. Updates ``production_status.json`` in the repo root with latest films.

    Per owner policy (config/owner_policy.json):
      - Social media posts require owner sign-off before public posting.
      - Studio productions are PRIVATE while in production, PUBLIC on release.

    Returns the updated project dict, or None if not found.
    """
    updated = update_project_status(project_id, "released", store_path=store_path)
    if not updated:
        return None

    project_title = updated.get("title") or project_id
    project_type = updated.get("project_type") or "Project"
    released_at = _iso_now()

    # Platform event — traceable audit trail for the release transition.
    if _publish_platform_event:
        try:
            _publish_platform_event(
                event_type="studio.project.released",
                producer="studio_project",
                entity_id=project_id,
                payload={
                    "title": project_title,
                    "project_type": project_type,
                    "released_at": released_at,
                    "release_notes": release_notes or "",
                },
            )
        except Exception:
            pass

    # Output-lane workboard job — owner must approve before social post goes out.
    if _emit_workboard:
        try:
            caption = social_caption or (
                f"🎬 {project_title} — now released. "
                f"#{project_type.lower().replace(' ', '')} #12sgi #aloha"
            )
            _emit_workboard(
                source="studio-release-pipeline",
                action="studio.project.released",
                event=f"RELEASE: {project_title} ({project_type})",
                lane="output",
                payload={
                    "project_id": project_id,
                    "title": project_title,
                    "project_type": project_type,
                    "released_at": released_at,
                    "social_caption": caption,
                    "release_notes": release_notes or "",
                },
            )
        except Exception:
            pass

    # Update production_status.json — best-effort, non-blocking.
    _update_production_status(project_title, project_type, released_at)

    return updated


def _update_production_status(title: str, project_type: str, released_at: str) -> None:
    """Append the newly released title to production_status.json in the repo root."""
    status_path = REPO / "production_status.json"
    try:
        try:
            with status_path.open(encoding="utf-8") as f:
                data: dict = json.load(f)
        except Exception:
            data = {}

        if project_type in {"Film", "film"}:
            count_key = "films_produced"
            recents_key = "latest_films"
        elif project_type in {"Music", "music"}:
            count_key = "quadcast_songs"
            recents_key = "latest_music"
        else:
            count_key = "projects_released"
            recents_key = "latest_releases"

        data[count_key] = int(data.get(count_key) or 0) + 1
        recents: list = list(data.get(recents_key) or [])
        recents.insert(0, title)
        data[recents_key] = recents[:10]  # keep last 10
        data["updated"] = released_at[:16].replace("T", " ") + " UTC"

        _atomic_write_json(status_path, data)
    except Exception:
        pass


def _atomic_write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    tmp.replace(path)


    """Sync all local projects to Neo4j. Soft-skip on graph unavailable."""
    projects = list_projects(store_path)
    if not projects:
        return True
    ok = True
    for p in projects:
        if not _upsert_project_node(p):
            ok = False
    return ok


# ── Timeline builder ──────────────────────────────────────────────────────────

def _stage_for_entry(entry: dict) -> str | None:
    """Return the pipeline stage id that best matches a workboard entry, or None."""
    text = " ".join([
        str(entry.get("event") or ""),
        str((entry.get("job") or {}).get("action") or ""),
        str(((entry.get("job") or {}).get("payload") or {}).get("job_type") or ""),
    ]).lower()
    for stage in PIPELINE_STAGES:
        for m in stage["matchers"]:
            if m in text:
                return stage["id"]
    return None


def _aggregate_stage_status(statuses: list[str]) -> str:
    """Aggregate multiple job statuses for a stage into the worst/best single state."""
    if not statuses:
        return "○"
    priority = ["failed", "rejected", "in-progress", "running", "done", "approved", "queued", "waiting"]
    for p in priority:
        if p in statuses:
            return _STATUS_GLYPH.get(p, "○")
    return "○"


def timeline_for_project(
    project_id: str,
    workboard_log: Path | None = None,
    store_path: Path | None = None,
) -> dict:
    """Build the production timeline for a project from workboard history.

    Returns a dict with:
      project   — project metadata (or minimal fallback)
      stages    — ordered list of pipeline stage defs (id, label, panel, dept)
      scenes    — list of scene rows, each with:
                    scene_id, label, stages (dict stage_id→{status, glyph, job_ids})
    """
    project = get_project(project_id, store_path) or {"project_id": project_id, "title": project_id}
    entries = _read_workboard(workboard_log)

    # Filter to this project
    project_entries = []
    for entry in entries:
        payload = (entry.get("job") or {}).get("payload") or {}
        if str(payload.get("project_id") or "") == project_id:
            project_entries.append(entry)

    # Group by scene_id (or derive from production_id / scene field in payload)
    scene_groups: dict[str, list[dict]] = {}
    for entry in project_entries:
        payload = (entry.get("job") or {}).get("payload") or {}
        scene_id = (
            str(payload.get("scene_id") or "")
            or str(payload.get("production_id") or "")
            or "scene-1"
        )
        scene_groups.setdefault(scene_id, []).append(entry)

    # If no entries found, return a seed row so the UI has something to show
    if not scene_groups:
        scene_groups["scene-1"] = []

    scenes = []
    for scene_id, scene_entries in sorted(scene_groups.items()):
        # Build per-stage status buckets
        stage_statuses: dict[str, list[str]] = {s["id"]: [] for s in PIPELINE_STAGES}
        stage_jobs: dict[str, list[str]] = {s["id"]: [] for s in PIPELINE_STAGES}
        for entry in scene_entries:
            stage = _stage_for_entry(entry)
            if stage:
                raw_status = (
                    (entry.get("job") or {}).get("status")
                    or entry.get("status")
                    or "queued"
                )
                job_id = (entry.get("job") or {}).get("id") or ""
                stage_statuses[stage].append(raw_status)
                if job_id:
                    stage_jobs[stage].append(job_id)

        stage_cells = {}
        for s in PIPELINE_STAGES:
            sid = s["id"]
            glyph = _aggregate_stage_status(stage_statuses[sid])
            stage_cells[sid] = {
                "glyph": glyph,
                "status": stage_statuses[sid][0] if stage_statuses[sid] else "○",
                "job_ids": stage_jobs[sid],
                "done": glyph == "✓",
                "running": glyph == "▶",
                "pending": glyph == "○",
                "failed": glyph == "✗",
            }

        scenes.append({
            "scene_id": scene_id,
            "label": scene_id.replace("-", " ").title(),
            "stages": stage_cells,
        })

    return {
        "project": project,
        "stages": [
            {"id": s["id"], "label": s["label"], "panel": s["panel"], "dept": s.get("dept")}
            for s in PIPELINE_STAGES
        ],
        "scenes": scenes,
        "scene_count": len(scenes),
        "project_id": project_id,
    }
