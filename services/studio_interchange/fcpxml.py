"""services/studio_interchange/fcpxml.py — Phase 2.2 FCPXML generation.

Deterministic FCPXML 1.11 generation from Studio timeline records.
No UI automation. Pure file-based interchange for Final Cut Pro 10.6+.

Archiving a storyboard does not invalidate FCPXML references. Asset IDs and
hashes are immutable and remain addressable after archival.
"""

import json
from xml.sax.saxutils import escape as _xml_escape


def timecode_from_seconds(seconds: float, fps: int = 24) -> str:
    """Convert decimal seconds to HH:MM:SS:FF timecode."""
    total_frames = int(round(seconds * fps))
    h = total_frames // (fps * 3600)
    m = (total_frames % (fps * 3600)) // (fps * 60)
    s = (total_frames % (fps * 60)) // fps
    f = total_frames % fps
    return f"{h:02d}:{m:02d}:{s:02d}:{f:02d}"


def frame_rate_to_duration(fps: int) -> str:
    """Return the FCPXML frameDuration rational string for a frame rate."""
    durations = {24: "100/2400s", 25: "100/2500s", 30: "100/3000s",
                 48: "100/4800s", 60: "100/6000s"}
    return durations.get(fps, "100/2400s")


def build_fcpxml(timeline: dict, fps: int = 24) -> str:
    """
    Build an FCPXML 1.11 document from a Studio timeline record.

    Asset IDs are written directly from shot['asset_id'] so that archived
    storyboards remain addressable by their immutable ID.
    """
    shots = timeline.get("shots") or []
    markers = timeline.get("markers") or []
    title = _xml_escape(str(timeline.get("title", "Untitled")))
    total_tc = timecode_from_seconds(timeline.get("duration_seconds", 0.0), fps)
    fd = frame_rate_to_duration(fps)

    asset_lines = []
    clip_lines = []
    for i, shot in enumerate(shots):
        shot_id = _xml_escape(str(shot.get("shot_id", f"shot_{i}")))
        # Use immutable asset_id if present; fall back to positional ref
        asset_id = _xml_escape(str(shot.get("asset_id") or f"r{i+1}"))
        src = _xml_escape(str(shot.get("proxy_path") or f"placeholder_{i}.mov"))
        start_tc = timecode_from_seconds(shot.get("start_seconds", 0.0), fps)
        dur_tc = timecode_from_seconds(shot.get("duration_seconds", 3.0), fps)
        handle_tc = timecode_from_seconds((shot.get("handles_frames", 24)) / fps, fps)
        asset_hash = _xml_escape(str(shot.get("asset_hash", "")))

        asset_lines.append(
            f'    <asset id="{asset_id}" name="{shot_id}" src="{src}" '
            f'start="0s" duration="{dur_tc}" hasAudio="1" hasVideo="1"'
            + (f' comment="hash:{asset_hash}"' if asset_hash else "") + "/>"
        )

        role = _xml_escape(str(shot.get("timeline_role", "Video")))
        storyboard_id = _xml_escape(str(shot.get("storyboard_id") or ""))
        clip_comment = f' comment="storyboard:{storyboard_id}"' if storyboard_id else ""

        shot_markers = ""
        for note in shot.get("marker_notes", []):
            shot_markers += f'\n        <marker start="{start_tc}" value="{_xml_escape(str(note))}"/>'

        clip_lines.append(
            f'      <clip name="{shot_id}" ref="{asset_id}" offset="{start_tc}" '
            f'duration="{dur_tc}" start="{handle_tc}" tcFormat="NDF"{clip_comment}>\n'
            f'        <video role="{role}"/>{shot_markers}\n'
            f'      </clip>'
        )

    global_markers = ""
    for m in markers:
        tc = timecode_from_seconds(m.get("timecode_seconds", 0.0), fps)
        note = _xml_escape(str(m.get("note", "")))
        mtype = m.get("type", "standard")
        global_markers += f'\n      <marker start="{tc}" value="{note}" completed="{str(mtype == "completed").lower()}"/>'

    assets_block = "\n".join(asset_lines)
    clips_block = "\n".join(clip_lines)

    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<!DOCTYPE fcpxml>\n'
        '<fcpxml version="1.11">\n'
        '  <resources>\n'
        f'    <format id="r0" name="FFVideoFormat1080p{fps}" frameDuration="{fd}" '
        f'width="1920" height="1080" colorSpace="1-1-1 (Rec. 709)"/>\n'
        f'{assets_block}\n'
        '  </resources>\n'
        '  <library>\n'
        '    <event name="12SGI Studio">\n'
        f'      <project name="{title}">\n'
        f'        <sequence duration="{total_tc}" format="r0" tcStart="00:00:00:00" tcFormat="NDF">\n'
        '          <spine>\n'
        f'{clips_block}\n'
        f'{global_markers}\n'
        '          </spine>\n'
        '        </sequence>\n'
        '      </project>\n'
        '    </event>\n'
        '  </library>\n'
        '</fcpxml>\n'
    )


def build_proxy_manifest(timeline: dict) -> dict:
    """Return a proxy file manifest mapping asset IDs to local proxy paths."""
    return {
        "timeline_id": timeline.get("timeline_id", ""),
        "proxies": [
            {
                "asset_id": shot.get("asset_id", ""),
                "shot_id": shot.get("shot_id", ""),
                "proxy_path": shot.get("proxy_path"),
                "asset_hash": shot.get("asset_hash", ""),
            }
            for shot in (timeline.get("shots") or [])
        ],
    }


def build_marker_list(timeline: dict) -> list:
    """Return a flat marker list for export to Final Cut Pro or spreadsheet."""
    markers = []
    for shot in (timeline.get("shots") or []):
        for note in shot.get("marker_notes", []):
            markers.append({
                "shot_id": shot.get("shot_id"),
                "asset_id": shot.get("asset_id"),
                "timecode_seconds": shot.get("start_seconds", 0.0),
                "note": note,
                "type": "shot",
            })
    for m in (timeline.get("markers") or []):
        markers.append({
            "shot_id": None,
            "asset_id": None,
            "timecode_seconds": m.get("timecode_seconds", 0.0),
            "note": m.get("note", ""),
            "type": m.get("type", "standard"),
        })
    return sorted(markers, key=lambda x: x["timecode_seconds"])


def build_caption_list(timeline: dict, dialogue_blocks: list | None = None) -> list:
    """Return a subtitle/caption list from shot dialogue assignments."""
    captions = []
    dialogue_map = {d["dialogue_id"]: d for d in (dialogue_blocks or [])}
    for shot in (timeline.get("shots") or []):
        editorial = shot.get("editorial") or {}
        dlg_id = editorial.get("dialogue_id")
        if dlg_id and dlg_id in dialogue_map:
            dlg = dialogue_map[dlg_id]
            captions.append({
                "shot_id": shot.get("shot_id"),
                "start_seconds": shot.get("start_seconds", 0.0),
                "duration_seconds": shot.get("duration_seconds", 3.0),
                "character": dlg.get("character", ""),
                "text": dlg.get("text", ""),
                "fcp_role": dlg.get("fcp_role", "Narration"),
            })
    return captions
