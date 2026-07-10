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
        rows.append(
            {
                "id": f"pulse-skill:{idx:02d}",
                "skill_index": idx,
                "name": f"Pulse Skill {idx:02d}",
                "source_node": idx,
                "role": "",
                "zone": "",
                "akua": "",
                "phase": "",
                "balance": "pono",
                "moon13": ((idx - 1) % 13) + 1,
                "source": "fallback",
            }
        )
    return rows


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
                "akua": node.get("akua", ""),
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
        rows.append(
            {
                "id": f"pulse-lane:{idx:02d}",
                "lane_index": idx,
                "po": po_name,
                "anahulu": anahulu,
                "nature": nature,
                "trigger": offering,
                "direction": _DIRECTION_BY_ANAHULU.get(anahulu, "holding"),
                "cadence": _CADENCE_BY_ANAHULU.get(anahulu, "steady"),
            }
        )
    if len(rows) < limit:
        for idx in range(len(rows) + 1, limit + 1):
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


def build_cell_rows(lanes: list[dict], skills: list[dict]) -> list[dict]:
    rows = []
    for lane in lanes:
        for skill in skills:
            balance = skill.get("balance") or "pono"
            direction = lane.get("direction") or "holding"
            cadence = lane.get("cadence") or "steady"
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
                    "source_node": skill.get("source_node"),
                    "akua": skill.get("akua", ""),
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
    }

    return [monthly, *quarterly, yearly]


def snapshot(sample_cells: int = 16) -> dict:
    lanes = build_lane_rows()
    skills = build_skill_rows()
    cells = build_cell_rows(lanes, skills)
    forecasts = build_forecast_rows(lanes, skills, cells)
    return {
        "layer": LAYER,
        "minimum_geometry": {"lanes": MIN_LANES, "skills": MIN_SKILLS, "cells": MIN_LANES * MIN_SKILLS},
        "full_hina_cycle": {"lanes": FULL_LANE_COUNT, "cycle": "28-30 day monthly pulse"},
        "counts": {"lanes": len(lanes), "skills": len(skills), "cells": len(cells), "forecasts": len(forecasts)},
        "geometry_complete": len(lanes) >= MIN_LANES and len(skills) >= MIN_SKILLS and len(cells) >= MIN_LANES * MIN_SKILLS,
        "lanes": lanes,
        "skills": skills,
        "cells_sample": cells[:sample_cells],
        "forecasts": forecasts,
    }


def build_graph_payload() -> dict:
    lanes = build_lane_rows()
    skills = build_skill_rows()
    cells = build_cell_rows(lanes, skills)
    forecasts = build_forecast_rows(lanes, skills, cells)
    return {
        "lanes": [dict(row, layer=LAYER) for row in lanes],
        "skills": [dict(row, layer=LAYER) for row in skills],
        "cells": [dict(row, layer=LAYER) for row in cells],
        "forecasts": [dict(row, layer=LAYER) for row in forecasts],
        "counts": {"lanes": len(lanes), "skills": len(skills), "cells": len(cells), "forecasts": len(forecasts)},
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

    for label, rows in (("PulseLane", payload["lanes"]), ("PulseSkill", payload["skills"]), ("PulseCell", payload["cells"]), ("ForecastWindow", payload["forecasts"])):
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
                    "MATCH (forecast:PulseGeometry:ForecastWindow {id:r.id}) "
                    "MATCH (yearly:PulseGeometry:ForecastWindow {id:'forecast:yearly:hina-13-moon'}) "
                    "FOREACH (_ IN CASE WHEN r.window = 'quarterly' THEN [1] ELSE [] END | "
                    "MERGE (forecast)-[e:ROLLS_UP_TO {key:r.id}]->(yearly) SET e.layer = $layer)"
                ),
                "parameters": {"rows": payload["forecasts"], "layer": LAYER},
            },
        ]
    )

    _say(
        "pulse_geometry: loaded %d lanes, %d skills, %d cells, %d forecast windows."
        % (payload["counts"]["lanes"], payload["counts"]["skills"], payload["counts"]["cells"], payload["counts"]["forecasts"])
    )
    return True
