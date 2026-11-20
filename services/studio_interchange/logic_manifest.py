"""services/studio_interchange/logic_manifest.py — Phase 2.2 Logic Pro session packaging.

Deterministic session manifest generation. No UI automation.

Traceability: every dialogue block is traceable from
  script line → recording take → selected take → Logic track → FCP role → stem
"""

import json
from datetime import datetime, timezone


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_session_manifest(session: dict) -> dict:
    """Return the complete Logic session manifest for export."""
    return {
        "session_id": session.get("session_id", ""),
        "production_id": session.get("production_id", ""),
        "title": session.get("title", ""),
        "sample_rate": session.get("sample_rate", 48000),
        "bit_depth": session.get("bit_depth", 24),
        "frame_rate": session.get("frame_rate", "24fps"),
        "stems": session.get("stems", []),
        "cue_count": len(session.get("cues", [])),
        "cues": session.get("cues", []),
        "tempo_map": session.get("tempo_map", []),
        "generated_at": _now(),
    }


def build_dialogue_assembly(session: dict, dialogue_blocks: list | None = None) -> dict:
    """
    Build a dialogue assembly document linking every dialogue block through:
    script line → recording take → selected take → Logic track → FCP role → final mix stem.
    """
    dialogue_map = {d["dialogue_id"]: d for d in (dialogue_blocks or [])}
    assembly_lines = []

    for cue in session.get("cues", []):
        dlg_id = cue.get("dialogue_id")
        dlg = dialogue_map.get(dlg_id) if dlg_id else None
        assembly_lines.append({
            "cue_id": cue.get("cue_id"),
            "scene_id": cue.get("scene_id"),
            "dialogue_id": dlg_id,
            "character": dlg.get("character") if dlg else None,
            "text": dlg.get("text") if dlg else None,
            "take_ids": dlg.get("take_ids", []) if dlg else [],
            "selected_take_id": dlg.get("selected_take_id") if dlg else None,
            "logic_track": dlg.get("logic_track") if dlg else cue.get("logic_marker"),
            "fcp_role": dlg.get("fcp_role") if dlg else None,
            "stem": (cue.get("stem_requirements") or [None])[0],
            "start_timecode": cue.get("start_timecode"),
            "duration_seconds": cue.get("duration_seconds"),
        })

    return {
        "session_id": session.get("session_id"),
        "production_id": session.get("production_id"),
        "assembly_type": "dialogue",
        "line_count": len(assembly_lines),
        "lines": assembly_lines,
        "generated_at": _now(),
    }


def build_cue_sheet(session: dict) -> dict:
    """Build a music cue sheet from the session's cues."""
    music_cues = [
        c for c in session.get("cues", [])
        if any(s in (c.get("stem_requirements") or []) for s in ("music", "stems", "mixes"))
    ]
    return {
        "session_id": session.get("session_id"),
        "production_id": session.get("production_id"),
        "title": session.get("title"),
        "frame_rate": session.get("frame_rate"),
        "cue_count": len(music_cues),
        "cues": [
            {
                "cue_id": c.get("cue_id"),
                "scene_id": c.get("scene_id"),
                "start_timecode": c.get("start_timecode"),
                "duration_seconds": c.get("duration_seconds"),
                "tempo_bpm": c.get("tempo_bpm"),
                "key": c.get("key"),
                "purpose": c.get("purpose"),
                "logic_marker": c.get("logic_marker"),
            }
            for c in music_cues
        ],
        "generated_at": _now(),
    }


def build_adr_list(session: dict, dialogue_blocks: list | None = None) -> list:
    """Return ADR lines needing re-recording (no selected take yet or flagged)."""
    dialogue_map = {d["dialogue_id"]: d for d in (dialogue_blocks or [])}
    adr = []
    for cue in session.get("cues", []):
        if "adr" not in (cue.get("stem_requirements") or []):
            continue
        dlg = dialogue_map.get(cue.get("dialogue_id"))
        adr.append({
            "cue_id": cue.get("cue_id"),
            "scene_id": cue.get("scene_id"),
            "dialogue_id": cue.get("dialogue_id"),
            "character": dlg.get("character") if dlg else None,
            "text": dlg.get("text") if dlg else None,
            "selected_take_id": dlg.get("selected_take_id") if dlg else None,
            "needs_adr": True,
        })
    return adr


def build_foley_list(session: dict) -> list:
    """Return Foley cues needing performance."""
    return [
        {
            "cue_id": c.get("cue_id"),
            "scene_id": c.get("scene_id"),
            "start_timecode": c.get("start_timecode"),
            "duration_seconds": c.get("duration_seconds"),
            "purpose": c.get("purpose"),
        }
        for c in session.get("cues", [])
        if "foley" in (c.get("stem_requirements") or [])
    ]


def build_stem_layout(session: dict) -> dict:
    """Return the full stem layout for the production."""
    return {
        "session_id": session.get("session_id"),
        "production_id": session.get("production_id"),
        "stems": session.get("stems", []),
        "sample_rate": session.get("sample_rate", 48000),
        "bit_depth": session.get("bit_depth", 24),
        "generated_at": _now(),
    }


def build_tempo_map(session: dict) -> list:
    """Return the tempo map entries."""
    return session.get("tempo_map", [])


def build_marker_track(session: dict) -> list:
    """Return Logic markers derived from cue logic_marker fields."""
    markers = []
    for cue in session.get("cues", []):
        if cue.get("logic_marker"):
            markers.append({
                "timecode": cue.get("start_timecode"),
                "label": cue.get("logic_marker"),
                "cue_id": cue.get("cue_id"),
            })
    return markers
