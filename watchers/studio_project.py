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

import json
import os
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

# Local store — machine-only, never committed
_DEFAULT_STORE = HOME / ".king" / "studio_projects.json"

# Workboard log (same default as private_spine / v2_workboard)
_DEFAULT_WORKBOARD = REPO / ".dispatch_log.jsonl"

# Valid project types
PROJECT_TYPES = {"Film", "Music", "Game", "Civic", "Architecture", "Education"}

# Valid project statuses
PROJECT_STATUSES = {"active", "development", "production", "post", "released", "archived"}

# Pipeline stage definitions — order is authoritative for the Timeline panel.
# Each stage has:
#   id        — canonical identifier
#   label     — display label
#   panel     — Naga console panel to navigate to when clicking
#   matchers  — list of regex patterns matched against workboard entry .event / .job.action
PIPELINE_STAGES = [
    {"id": "script",     "label": "Script",      "panel": "studiodepts", "dept": "writing",    "matchers": ["script", "writing", "dialogue", "premise", "beat_sheet", "first_draft"]},
    {"id": "storyboard", "label": "Storyboard",  "panel": "studiodepts", "dept": "storyboard", "matchers": ["storyboard", "continuity", "shot_plan", "blocking"]},
    {"id": "kandinsky",  "label": "Kandinsky",   "panel": "gpu",         "dept": None,         "matchers": ["kandinsky", "image_gen", "render_still", "deck_render"]},
    {"id": "ltx",        "label": "LTX",         "panel": "gpu",         "dept": None,         "matchers": ["ltx", "ltx_video", "video_gen", "animate", "motion"]},
    {"id": "editor",     "label": "Editor",      "panel": "studiodepts", "dept": "fcp",        "matchers": ["editor", "edit_cut", "rough_cut", "fine_cut", "assembly"]},
    {"id": "logic",      "label": "Logic",       "panel": "studiodepts", "dept": "logic",      "matchers": ["logic", "audio_session", "adr", "foley", "music_cue", "mix"]},
    {"id": "fcp",        "label": "FCP",         "panel": "studiodepts", "dept": "fcp",        "matchers": ["fcp", "fcpxml", "timeline_export", "final_cut"]},
    {"id": "release",    "label": "Release",     "panel": "ops",         "dept": None,         "matchers": ["release", "publish", "export_final", "deliver"]},
]

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


# ── Helpers ───────────────────────────────────────────────────────────────────

def _iso_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _load_store(store_path: Path | None = None) -> dict:
    path = store_path or _DEFAULT_STORE
    if not path.exists():
        return {"projects": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {"projects": []}
    except Exception:
        return {"projects": []}


def _save_store(data: dict, store_path: Path | None = None) -> None:
    path = store_path or _DEFAULT_STORE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


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


def refresh(store_path: Path | None = None) -> bool:
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
