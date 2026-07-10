# -*- coding: utf-8 -*-
"""pulse_geometry.py — dedicated lane/skill pulse geometry bound to Neo4j.

This module does NOT alter the existing v2 workboard lanes.  It builds a separate
PRIVATE geometry model for the requested lane×skill lattice and projects that
model into Neo4j under its own additive layer (``pulse_geometry``).

Source of truth:
  - lanes come from the existing moon-calendar pulse cadence
  - skills come from the existing Sage bridge node set
  - geometry cells bind trigger/direction/cadence/balance/output together

Resilience is intentional: missing source files or an unreachable Neo4j instance
produce soft fallbacks / soft skips rather than breaking the rest of the system.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

try:
    from watchers import moon_calendar
except Exception:  # pragma: no cover - import style varies by caller
    import moon_calendar  # type: ignore

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
NEO = os.environ.get("NEO4J_HTTP", "http://127.0.0.1:7474/db/neo4j/tx/commit")
LAYER = "pulse_geometry"
MIN_LANES = 28
FULL_LANE_COUNT = len(moon_calendar.PO)
MIN_SKILLS = 28
RESIDENCE_PLACE = os.environ.get("PULSE_RESIDENCE_PLACE", "Maui")
RESIDENCE_TIMEZONE = os.environ.get("PULSE_RESIDENCE_TZ", "Pacific/Honolulu")
ORGANIC_CARBON_WEIGHT = 6
EDGE_CONTEXT_ID = "context:known-universe-edge"
APEX_CONTEXT_ID = "context:shared-apex-spine"
RHYTHM_CONTEXT_ID = "context:ao-po-rhythm"

_DIRECTION_BY_ANAHULU = {
    "Hoʻonui": "expanding",
    "Poepoe": "holding",
    "Hoʻēmi": "returning",
}
_CADENCE_BY_ANAHULU = {
    "Hoʻonui": "build",
    "Poepoe": "crest",
    "Hoʻēmi": "release",
}
_OUTPUT_BY_BALANCE = {
    "hewa": "repair",
    "opportunity": "prepare",
    "pono": "stabilize",
}
_RESIDENCE_FREQUENCIES = (
    {
        "id": "residence:dawn",
        "frequency": "dawn",
        "label": "pre-dawn to morning rise",
        "hours": "05:00-08:59",
        "ao_po": "Ao",
        "cadences": ("build", "steady"),
    },
    {
        "id": "residence:day",
        "frequency": "day",
        "label": "daylight work and civic action",
        "hours": "09:00-16:59",
        "ao_po": "Ao",
        "cadences": ("build", "crest"),
    },
    {
        "id": "residence:dusk",
        "frequency": "dusk",
        "label": "return home and integrate",
        "hours": "17:00-20:59",
        "ao_po": "Ao→Pō",
        "cadences": ("crest", "release"),
    },
    {
        "id": "residence:night",
        "frequency": "night",
        "label": "quiet home, rest, and reset",
        "hours": "21:00-04:59",
        "ao_po": "Pō",
        "cadences": ("release", "steady"),
    },
)
_CARBON_SIX_TONES = (
    "rooted",
    "flow",
    "will",
    "heart",
    "voice",
    "vision",
)
_ELEMENT_BY_AKUA = {
    "Pele": "Fire",
    "Kanaloa": "Ocean",
    "Kāne": "Fresh Water",
    "Lono": "Growth",
    "Kū": "Structure",
}
_DEFAULT_ELEMENTS = tuple(sorted(set(_ELEMENT_BY_AKUA.values()) | {"Earth"}))
_QUADRANT_ORDER = ("Mauka", "Kula", "Makai", "Universal")
_QUADRANT_ALIASES = {"Farmlands": "Kula", "Po": "Pō"}


def _say(message: str) -> None:
    try:
        if sys.stdout:
            print(message, flush=True)
    except Exception:
        pass


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _slug(text: object) -> str:
    return "".join(ch.lower() if ch.isalnum() else "-" for ch in str(text or "")).strip("-") or "unknown"


def _source_candidates() -> list[Path]:
    return [
        REPO / "seed_reports" / "mauios" / "sage_bridge.json",
        REPO / "reports" / "mauios" / "sage_bridge.json",
        REPO.parent / "config" / "sage_deck_cards.json",  # external project mirror
    ]


def load_sage_nodes() -> list[dict]:
    for candidate in _source_candidates()[:2]:
        data = _read_json(candidate)
        nodes = data.get("nodes") or []
        if isinstance(nodes, list) and nodes:
            return [node for node in nodes if isinstance(node, dict)]
    return []


def _fallback_skills(limit: int) -> list[dict]:
    rows = []
    for idx in range(1, limit + 1):
        quadrant = _quadrant_for({"zone": _QUADRANT_ORDER[(idx - 1) % len(_QUADRANT_ORDER)]})
        rows.append(
            {
                "id": f"pulse-skill:{idx:02d}",
                "skill_index": idx,
                "name": f"Pulse Skill {idx:02d}",
                "source_node": idx,
                "role": "",
                "zone": quadrant,
                "quadrant": quadrant,
                "akua": "",
                "element": "Earth",
                "phase": "",
                "balance": "pono",
                "moon13": ((idx - 1) % 13) + 1,
                "source": "fallback",
            }
        )
    return rows


def build_context_rows() -> list[dict]:
    return [
        {
            "id": EDGE_CONTEXT_ID,
            "name": "Known universe boundary",
            "context_kind": "edge",
            "scope": "outermost",
            "note": "Outer containment boundary carried directly by the quadrant lattice.",
        },
        {
            "id": APEX_CONTEXT_ID,
            "name": "Shared apex spine",
            "context_kind": "apex",
            "scope": "governing",
            "note": "Governing hierarchy for civic and accountability alignment.",
        },
        {
            "id": RHYTHM_CONTEXT_ID,
            "name": "Ao/Pō rhythm",
            "context_kind": "rhythm",
            "scope": "balancing",
            "note": "Rhythm layer for Ao action, Pō balancing, and Hina cadence.",
        },
    ]


def build_skill_rows(limit: int = MIN_SKILLS) -> list[dict]:
    nodes = load_sage_nodes()
    if not nodes:
        return _fallback_skills(limit)

    rows = []
    for idx, node in enumerate(nodes[: max(limit, len(nodes))], start=1):
        rows.append(
            {
                "id": f"pulse-skill:{idx:02d}",
                "skill_index": idx,
                "name": node.get("name") or f"Node {node.get('node', idx)}",
                "source_node": node.get("node", idx),
                "role": node.get("role", ""),
                "zone": node.get("zone", ""),
                "quadrant": _quadrant_for(node),
                "akua": node.get("akua", ""),
                "element": _element_for(node),
                "phase": node.get("phase", ""),
                "balance": node.get("balance", "pono"),
                "moon13": node.get("moon13") or ((idx - 1) % 13) + 1,
                "source": "sage_bridge",
            }
        )
    return rows[: max(limit, MIN_SKILLS)]


def build_lane_rows(limit: int = FULL_LANE_COUNT) -> list[dict]:
    rows = []
    for idx, (po_name, anahulu, nature, offering) in enumerate(moon_calendar.PO[:limit], start=1):
        cadence = _CADENCE_BY_ANAHULU.get(anahulu, "steady")
        primary_frequency, secondary_frequency = _residence_tuning_for(cadence)
        chakra_index = _chakra_index_for(idx)
        rows.append(
            {
                "id": f"pulse-lane:{idx:02d}",
                "lane_index": idx,
                "po": po_name,
                "anahulu": anahulu,
                "nature": nature,
                "trigger": offering,
                "direction": _DIRECTION_BY_ANAHULU.get(anahulu, "holding"),
                "cadence": cadence,
                "residence_frequency": primary_frequency,
                "residence_secondary_frequency": secondary_frequency,
                "chakra_index": chakra_index,
                "chakra_tone": _CARBON_SIX_TONES[chakra_index - 1],
                "organic_carbon_weight": ORGANIC_CARBON_WEIGHT,
                "place": RESIDENCE_PLACE,
                "timezone": RESIDENCE_TIMEZONE,
            }
        )
    if len(rows) < limit:
        for idx in range(len(rows) + 1, limit + 1):
            primary_frequency, secondary_frequency = _residence_tuning_for("steady")
            chakra_index = _chakra_index_for(idx)
            rows.append(
                {
                    "id": f"pulse-lane:{idx:02d}",
                    "lane_index": idx,
                    "po": f"Pulse {idx:02d}",
                    "anahulu": "generated",
                    "nature": "generated pulse lane",
                    "trigger": "advance the pulse lattice",
                    "direction": "holding",
                    "cadence": "steady",
                    "residence_frequency": primary_frequency,
                    "residence_secondary_frequency": secondary_frequency,
                    "chakra_index": chakra_index,
                    "chakra_tone": _CARBON_SIX_TONES[chakra_index - 1],
                    "organic_carbon_weight": ORGANIC_CARBON_WEIGHT,
                    "place": RESIDENCE_PLACE,
                    "timezone": RESIDENCE_TIMEZONE,
                }
            )
    return rows


def _state_for(direction: str, balance: str) -> str:
    if balance == "hewa":
        return "corrective"
    if direction == "expanding" and balance == "opportunity":
        return "charging"
    if direction == "holding":
        return "holding"
    if direction == "returning":
        return "releasing"
    return "steady"


def _resonance_for(lane_index: int, moon13: int | str | None) -> str:
    try:
        moon_slot = int(moon13 or 0)
    except Exception:
        moon_slot = 0
    if not moon_slot:
        return "open"
    lane_slot = ((lane_index - 1) % 13) + 1
    if lane_slot == moon_slot:
        return "aligned"
    if abs(lane_slot - moon_slot) == 1:
        return "adjacent"
    return "cross"


def build_residence_frequency_rows() -> list[dict]:
    rows = []
    for idx, row in enumerate(_RESIDENCE_FREQUENCIES, start=1):
        rows.append(
            {
                "id": row["id"],
                "sequence": idx,
                "frequency": row["frequency"],
                "label": row["label"],
                "hours": row["hours"],
                "ao_po": row["ao_po"],
                "cadences": list(row["cadences"]),
                "place": RESIDENCE_PLACE,
                "timezone": RESIDENCE_TIMEZONE,
            }
        )
    return rows


def _element_for(node: dict) -> str:
    explicit = node.get("element")
    if isinstance(explicit, dict):
        return str(explicit.get("value") or explicit.get("name") or "Unknown")
    if explicit:
        return str(explicit)
    return _ELEMENT_BY_AKUA.get(str(node.get("akua") or ""), "Earth")


def _quadrant_for(node: dict) -> str:
    quadrant = str(node.get("quadrant") or node.get("zone") or "").strip()
    if quadrant in _QUADRANT_ALIASES:
        return _QUADRANT_ALIASES[quadrant]
    return quadrant or "Universal"


def _chakra_index_for(lane_index: int) -> int:
    return ((lane_index - 1) % ORGANIC_CARBON_WEIGHT) + 1


def _residence_tuning_for(cadence: str) -> tuple[str, str]:
    if cadence == "build":
        return ("dawn", "day")
    if cadence == "crest":
        return ("day", "dusk")
    if cadence == "release":
        return ("dusk", "night")
    return ("night", "dawn")


def _residence_alignment_for(cadence: str, balance: str) -> str:
    if cadence == "release":
        return "settling"
    if cadence == "crest" and balance == "pono":
        return "gathered"
    if cadence == "build" and balance != "hewa":
        return "rising"
    if balance == "hewa":
        return "corrective"
    return "steady"


def build_element_rows(skills: list[dict]) -> list[dict]:
    counts = _count_all_elements(skills, "element")
    rows = []
    for idx, element in enumerate(sorted(counts), start=1):
        rows.append(
            {
                "id": f"element:{element.lower().replace(' ', '-')}",
                "element": element,
                "skill_count": counts[element],
                "layer": LAYER,
            }
        )
    return rows


def build_forecast_element_rows(forecasts: list[dict]) -> list[dict]:
    rows = []
    for forecast in forecasts:
        element_counts = forecast.get("element_counts") or {}
        for element in _DEFAULT_ELEMENTS:
            rows.append(
                {
                    "id": f"{forecast['id']}:{element.lower().replace(' ', '-')}",
                    "forecast_id": forecast["id"],
                    "element_id": f"element:{element.lower().replace(' ', '-')}",
                    "element": element,
                    "count": int(element_counts.get(element, 0) or 0),
                }
            )
    return rows


def build_cell_rows(lanes: list[dict], skills: list[dict]) -> list[dict]:
    rows = []
    for lane in lanes:
        for skill in skills:
            balance = skill.get("balance") or "pono"
            direction = lane.get("direction") or "holding"
            cadence = lane.get("cadence") or "steady"
            quadrant = _quadrant_for(skill)
            rows.append(
                {
                    "id": f"pulse-cell:{lane['lane_index']:02d}:{skill['skill_index']:02d}",
                    "lane_id": lane["id"],
                    "skill_id": skill["id"],
                    "lane_index": lane["lane_index"],
                    "skill_index": skill["skill_index"],
                    "trigger": lane.get("trigger", ""),
                    "direction": direction,
                    "cadence": cadence,
                    "balance": balance,
                    "output": _OUTPUT_BY_BALANCE.get(balance, "observe"),
                    "state": _state_for(direction, balance),
                    "resonance": _resonance_for(lane["lane_index"], skill.get("moon13")),
                    "residence_frequency": lane.get("residence_frequency", "night"),
                    "residence_secondary_frequency": lane.get("residence_secondary_frequency", "dawn"),
                    "residence_alignment": _residence_alignment_for(cadence, balance),
                    "chakra_index": lane.get("chakra_index", 1),
                    "chakra_tone": lane.get("chakra_tone", _CARBON_SIX_TONES[0]),
                    "organic_carbon_weight": lane.get("organic_carbon_weight", ORGANIC_CARBON_WEIGHT),
                    "place": lane.get("place", RESIDENCE_PLACE),
                    "timezone": lane.get("timezone", RESIDENCE_TIMEZONE),
                    "source_node": skill.get("source_node"),
                    "quadrant": quadrant,
                    "quadrant_id": f"quadrant:{_slug(quadrant)}",
                    "outer_boundary_context_id": EDGE_CONTEXT_ID,
                    "governing_context_id": APEX_CONTEXT_ID,
                    "rhythm_context_id": RHYTHM_CONTEXT_ID,
                    "context_model": "edge_apex_rhythm",
                    "akua": skill.get("akua", ""),
                    "element": skill.get("element", "Earth"),
                    "zone": skill.get("zone", ""),
                    "phase": skill.get("phase", ""),
                }
            )
    return rows


def _count_by(rows: list[dict], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        label = str(row.get(key) or "unknown")
        counts[label] = counts.get(label, 0) + 1
    return counts


def _count_all_elements(rows: list[dict], key: str = "element") -> dict[str, int]:
    counts = {element: 0 for element in _DEFAULT_ELEMENTS}
    counts.update(_count_by(rows, key))
    return counts


def build_quadrant_rows(skills: list[dict]) -> list[dict]:
    rows = []
    for idx, quadrant in enumerate(_QUADRANT_ORDER, start=1):
        quadrant_skills = [skill for skill in skills if _quadrant_for(skill) == quadrant]
        rows.append(
            {
                "id": f"quadrant:{_slug(quadrant)}",
                "sequence": idx,
                "quadrant": quadrant,
                "skill_count": len(quadrant_skills),
                "balance_counts": _count_by(quadrant_skills, "balance"),
                "phase_counts": _count_by(quadrant_skills, "phase"),
                "element_counts": _count_all_elements(quadrant_skills, "element"),
                "outer_boundary_context_id": EDGE_CONTEXT_ID,
                "governing_context_id": APEX_CONTEXT_ID,
                "rhythm_context_id": RHYTHM_CONTEXT_ID,
                "context_model": "edge_apex_rhythm",
            }
        )
    return rows


def build_context_edge_rows(quadrants: list[dict]) -> list[dict]:
    rows = [
        {
            "id": "context-edge-apex",
            "rel": "CONTAINS",
            "src_id": EDGE_CONTEXT_ID,
            "dst_id": APEX_CONTEXT_ID,
            "props": {"layer": LAYER, "context_model": "edge_apex_rhythm"},
        },
        {
            "id": "context-edge-rhythm",
            "rel": "CONTAINS",
            "src_id": EDGE_CONTEXT_ID,
            "dst_id": RHYTHM_CONTEXT_ID,
            "props": {"layer": LAYER, "context_model": "edge_apex_rhythm"},
        },
    ]
    for quadrant in quadrants:
        qid = quadrant["id"]
        qslug = _slug(quadrant["quadrant"])
        rows.extend(
            [
                {
                    "id": f"edge-quadrant:{qslug}",
                    "rel": "CONTAINS",
                    "src_id": EDGE_CONTEXT_ID,
                    "dst_id": qid,
                    "props": {"layer": LAYER, "quadrant": quadrant["quadrant"], "context_model": "edge_apex_rhythm"},
                },
                {
                    "id": f"apex-quadrant:{qslug}",
                    "rel": "GOVERNS",
                    "src_id": APEX_CONTEXT_ID,
                    "dst_id": qid,
                    "props": {"layer": LAYER, "quadrant": quadrant["quadrant"], "context_model": "edge_apex_rhythm"},
                },
                {
                    "id": f"rhythm-quadrant:{qslug}",
                    "rel": "FRAMES",
                    "src_id": RHYTHM_CONTEXT_ID,
                    "dst_id": qid,
                    "props": {"layer": LAYER, "quadrant": quadrant["quadrant"], "context_model": "edge_apex_rhythm"},
                },
            ]
        )
    return rows


def build_forecast_rows(lanes: list[dict], skills: list[dict], cells: list[dict]) -> list[dict]:
    monthly = {
        "id": "forecast:monthly:hina-30",
        "window": "monthly",
        "label": "28-30 day Hina moon cycle",
        "start_lane": 1,
        "end_lane": len(lanes),
        "lane_count": len(lanes),
        "direction_counts": _count_by(lanes, "direction"),
        "cadence_counts": _count_by(lanes, "cadence"),
        "balance_counts": _count_by(cells, "balance"),
        "output_counts": _count_by(cells, "output"),
        "residence_frequency_counts": _count_by(cells, "residence_frequency"),
        "chakra_counts": _count_by(cells, "chakra_tone"),
        "element_counts": _count_all_elements(cells, "element"),
    }

    quarter_spans = [("Q1", 1, 3), ("Q2", 4, 6), ("Q3", 7, 9), ("Q4", 10, 13)]
    quarterly = []
    for label, start, end in quarter_spans:
        quarter_skills = [skill for skill in skills if start <= int(skill.get("moon13") or 0) <= end]
        quarter_ids = {skill["id"] for skill in quarter_skills}
        quarter_cells = [cell for cell in cells if cell["skill_id"] in quarter_ids]
        quarterly.append(
            {
                "id": f"forecast:quarter:{label.lower()}",
                "window": "quarterly",
                "label": label,
                "moon_start": start,
                "moon_end": end,
                "skill_count": len(quarter_skills),
                "balance_counts": _count_by(quarter_cells, "balance"),
                "output_counts": _count_by(quarter_cells, "output"),
                "residence_frequency_counts": _count_by(quarter_cells, "residence_frequency"),
                "chakra_counts": _count_by(quarter_cells, "chakra_tone"),
                "element_counts": _count_all_elements(quarter_cells, "element"),
            }
        )

    yearly = {
        "id": "forecast:yearly:hina-13-moon",
        "window": "yearly",
        "label": "13-moon annual accounting cycle",
        "skill_count": len(skills),
        "lane_count": len(lanes),
        "balance_counts": _count_by(skills, "balance"),
        "phase_counts": _count_by(skills, "phase"),
        "zone_counts": _count_by(skills, "zone"),
        "output_counts": _count_by(cells, "output"),
        "residence_frequency_counts": _count_by(cells, "residence_frequency"),
        "chakra_counts": _count_by(cells, "chakra_tone"),
        "element_counts": _count_all_elements(cells, "element"),
    }

    return [monthly, *quarterly, yearly]


def snapshot(sample_cells: int = 16) -> dict:
    lanes = build_lane_rows()
    skills = build_skill_rows()
    contexts = build_context_rows()
    quadrants = build_quadrant_rows(skills)
    elements = build_element_rows(skills)
    cells = build_cell_rows(lanes, skills)
    forecasts = build_forecast_rows(lanes, skills, cells)
    forecast_elements = build_forecast_element_rows(forecasts)
    residence_frequencies = build_residence_frequency_rows()
    context_edges = build_context_edge_rows(quadrants)
    return {
        "layer": LAYER,
        "minimum_geometry": {"lanes": MIN_LANES, "skills": MIN_SKILLS, "cells": MIN_LANES * MIN_SKILLS},
        "full_hina_cycle": {"lanes": FULL_LANE_COUNT, "cycle": "28-30 day monthly pulse"},
        "counts": {
            "contexts": len(contexts),
            "quadrants": len(quadrants),
            "lanes": len(lanes),
            "skills": len(skills),
            "elements": len(elements),
            "context_edges": len(context_edges),
            "forecast_elements": len(forecast_elements),
            "cells": len(cells),
            "forecasts": len(forecasts),
        },
        "place_tuning": {
            "model": "human_residence_frequencies",
            "place": RESIDENCE_PLACE,
            "timezone": RESIDENCE_TIMEZONE,
            "natural_rhythm": "Ao→Pō",
            "frequency_count": len(residence_frequencies),
            "audit_status": "audited",
            "serves": "humans",
            "experiments_enabled": False,
            "mode": "deterministic",
            "human_alignment_system": "chakra",
            "organic_carbon_weight": ORGANIC_CARBON_WEIGHT,
            "chakra_count": ORGANIC_CARBON_WEIGHT,
        },
        "geometry_complete": len(lanes) >= MIN_LANES and len(skills) >= MIN_SKILLS and len(cells) >= MIN_LANES * MIN_SKILLS,
        "contexts": contexts,
        "quadrants": quadrants,
        "lanes": lanes,
        "skills": skills,
        "elements": elements,
        "residence_frequencies": residence_frequencies,
        "cells_sample": cells[:sample_cells],
        "forecasts": forecasts,
        "context_edges": context_edges,
    }


def build_graph_payload() -> dict:
    lanes = build_lane_rows()
    skills = build_skill_rows()
    contexts = build_context_rows()
    quadrants = build_quadrant_rows(skills)
    elements = build_element_rows(skills)
    cells = build_cell_rows(lanes, skills)
    forecasts = build_forecast_rows(lanes, skills, cells)
    forecast_elements = build_forecast_element_rows(forecasts)
    residence_frequencies = build_residence_frequency_rows()
    context_edges = build_context_edge_rows(quadrants)
    return {
        "contexts": [dict(row, layer=LAYER) for row in contexts],
        "quadrants": [dict(row, layer=LAYER) for row in quadrants],
        "lanes": [dict(row, layer=LAYER) for row in lanes],
        "skills": [dict(row, layer=LAYER) for row in skills],
        "elements": [dict(row, layer=LAYER) for row in elements],
        "residence_frequencies": [dict(row, layer=LAYER) for row in residence_frequencies],
        "cells": [dict(row, layer=LAYER) for row in cells],
        "forecasts": [dict(row, layer=LAYER) for row in forecasts],
        "forecast_elements": forecast_elements,
        "context_edges": context_edges,
        "counts": {
            "contexts": len(contexts),
            "quadrants": len(quadrants),
            "lanes": len(lanes),
            "skills": len(skills),
            "elements": len(elements),
            "context_edges": len(context_edges),
            "forecast_elements": len(forecast_elements),
            "residence_frequencies": len(residence_frequencies),
            "cells": len(cells),
            "forecasts": len(forecasts),
        },
    }


def _post(statements: list[dict], timeout: float = 120):
    body = json.dumps({"statements": statements}).encode("utf-8")
    req = urllib.request.Request(NEO, data=body, headers={"Content-Type": "application/json", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            out = json.loads(resp.read().decode("utf-8", "replace"))
    except urllib.error.URLError as exc:
        _say(f"pulse_geometry: Neo4j not reachable at {NEO} ({str(exc)[:140]})")
        return None
    if out.get("errors"):
        _say("pulse_geometry Cypher errors: %s" % json.dumps(out.get("errors"))[:300])
    return out


def refresh() -> bool:
    payload = build_graph_payload()
    if _post([{"statement": "MATCH (n:PulseGeometry {layer:$layer}) DETACH DELETE n", "parameters": {"layer": LAYER}}]) is None:
        return False

    _post([{"statement": "CREATE CONSTRAINT pulse_geometry_id IF NOT EXISTS FOR (x:PulseGeometry) REQUIRE x.id IS UNIQUE"}])

    for label, rows in (
        ("Context", payload["contexts"]),
        ("Quadrant", payload["quadrants"]),
        ("PulseLane", payload["lanes"]),
        ("PulseSkill", payload["skills"]),
        ("SageElement", payload["elements"]),
        ("ResidenceFrequency", payload["residence_frequencies"]),
        ("PulseCell", payload["cells"]),
        ("ForecastWindow", payload["forecasts"]),
    ):
        _post(
            [
                {
                    "statement": f"UNWIND $rows AS r MERGE (n:PulseGeometry:{label} {{id:r.id}}) SET n += r",
                    "parameters": {"rows": rows},
                }
            ]
        )

    _post(
        [
            {
                "statement": (
                    "UNWIND $rows AS r "
                    "MATCH (lane:PulseGeometry:PulseLane {id:r.lane_id}) "
                    "MATCH (cell:PulseGeometry:PulseCell {id:r.id}) "
                    "MERGE (lane)-[e:DRIVES {key:r.id}]->(cell) "
                    "SET e.layer = $layer, e.direction = r.direction, e.cadence = r.cadence"
                ),
                "parameters": {"rows": payload["cells"], "layer": LAYER},
            },
            {
                "statement": (
                    "UNWIND $rows AS r "
                    "MATCH (skill:PulseGeometry:PulseSkill {id:r.skill_id}) "
                    "MATCH (cell:PulseGeometry:PulseCell {id:r.id}) "
                    "MERGE (skill)-[e:ACTIVATES {key:r.id}]->(cell) "
                    "SET e.layer = $layer, e.balance = r.balance, e.output = r.output"
                ),
                "parameters": {"rows": payload["cells"], "layer": LAYER},
            },
            {
                "statement": (
                    "UNWIND $rows AS r "
                    "MATCH (skill:PulseGeometry:PulseSkill {id:r.id}) "
                    "MATCH (element:PulseGeometry:SageElement {id:'element:' + toLower(replace(r.element, ' ', '-'))}) "
                    "MERGE (skill)-[e:EXPRESSES {key:r.id}]->(element) "
                    "SET e.layer = $layer, e.akua = r.akua"
                ),
                "parameters": {"rows": payload["skills"], "layer": LAYER},
            },
            {
                "statement": (
                    "UNWIND $rows AS r "
                    "MATCH (forecast:PulseGeometry:ForecastWindow {id:r.forecast_id}) "
                    "MATCH (element:PulseGeometry:SageElement {id:r.element_id}) "
                    "MERGE (forecast)-[e:FORECASTS_ELEMENT {key:r.id}]->(element) "
                    "SET e.layer = $layer, e.count = r.count"
                ),
                "parameters": {"rows": payload["forecast_elements"], "layer": LAYER},
            },
            {
                "statement": (
                    "UNWIND $rows AS r "
                    "MATCH (freq:PulseGeometry:ResidenceFrequency {id:'residence:' + r.residence_frequency}) "
                    "MATCH (cell:PulseGeometry:PulseCell {id:r.id}) "
                    "MERGE (freq)-[e:TUNES {key:r.id}]->(cell) "
                    "SET e.layer = $layer, e.alignment = r.residence_alignment"
                ),
                "parameters": {"rows": payload["cells"], "layer": LAYER},
            },
            {
                "statement": (
                    "UNWIND $rows AS r "
                    "MATCH (forecast:PulseGeometry:ForecastWindow {id:r.id}) "
                    "MATCH (yearly:PulseGeometry:ForecastWindow {id:'forecast:yearly:hina-13-moon'}) "
                    "FOREACH (_ IN CASE WHEN r.window = 'quarterly' THEN [1] ELSE [] END | "
                    "MERGE (forecast)-[e:ROLLS_UP_TO {key:r.id}]->(yearly) SET e.layer = $layer)"
                ),
                "parameters": {"rows": payload["forecasts"], "layer": LAYER},
            },
        ]
    )

    for rel in ("CONTAINS", "GOVERNS", "FRAMES"):
        rel_rows = [row for row in payload["context_edges"] if row["rel"] == rel]
        if not rel_rows:
            continue
        _post(
            [
                {
                    "statement": (
                        f"UNWIND $rows AS r "
                        f"MATCH (src:PulseGeometry {{id:r.src_id}}) "
                        f"MATCH (dst:PulseGeometry {{id:r.dst_id}}) "
                        f"MERGE (src)-[e:{rel} {{key:r.id}}]->(dst) "
                        f"SET e += r.props"
                    ),
                    "parameters": {"rows": rel_rows},
                }
            ]
        )

    _say(
        "pulse_geometry: loaded %d contexts, %d quadrants, %d lanes, %d skills, %d elements, %d residence frequencies, %d cells, %d forecast windows, %d forecast-element edges, %d context edges."
        % (
            payload["counts"]["contexts"],
            payload["counts"]["quadrants"],
            payload["counts"]["lanes"],
            payload["counts"]["skills"],
            payload["counts"]["elements"],
            payload["counts"]["residence_frequencies"],
            payload["counts"]["cells"],
            payload["counts"]["forecasts"],
            payload["counts"]["forecast_elements"],
            payload["counts"]["context_edges"],
        )
    )
    return True
