# -*- coding: utf-8 -*-
"""sage_trinity.py — Sage Trinity Architecture: LaniAkea to the Human Within the Tenant.

Encodes the three-scale triskelion model into Neo4j under the additive
``sage_trinity`` layer:

  Sage Universe         — the outermost scientific frame (LaniAkea → Earth)
  Sage Civic            — the community and its governance (Earth → tenant)
  Sage Human Initiation — the person inside the tenant (carbon body, chakra geometry)

The triskelion symbol: three SPIRAL_ARM edges linking the three scales in a
closed loop.  The Hoʻi spiral (expanding → holding → returning = Hoʻonui →
Poepoe → Hoʻēmi) runs through all three scales simultaneously.  The chakra
crosswalk table makes explicit how the universe scale and civic scale write their
signatures into the human body.

Scientific anchors:
  - LaniAkea: Tully et al. (2014), Nature 513 71–73
  - Solar Cycle 25: NASA/NOAA DSCOVR + DONKI
  - Schumann resonance: Schumann (1952), 7.83 Hz base; HeartMath cardiac coherence research
  - Circadian rhythm: Nobel Prize 2017 (Hall, Rosbash, Young) — molecular clock mechanism
  - Carbon-6: organic chemistry basis of life; 6-chakra geometry mirrors atomic weight

This layer is additive and isolated under ``layer='sage_trinity'``.  It is resilient:
an unreachable Neo4j instance or a failed science data fetch produces a soft skip.
A weekly gate inside ``refresh()`` prevents redundant universe data fetches.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
NEO = os.environ.get("NEO4J_HTTP", "http://127.0.0.1:7474/db/neo4j/tx/commit")
LAYER = "sage_trinity"

# ── Trinity scale context IDs ─────────────────────────────────────────────────
SAGE_UNIVERSE_CONTEXT_ID = "context:sage-universe"
SAGE_CIVIC_CONTEXT_ID = "context:sage-civic"
HUMAN_INITIATION_CONTEXT_ID = "context:sage-human-initiation"

# ── Reference outer context IDs from pulse_geometry ──────────────────────────
try:
    from watchers.pulse_geometry import (  # type: ignore
        EDGE_CONTEXT_ID,
        APEX_CONTEXT_ID,
        RHYTHM_CONTEXT_ID,
        ORGANIC_CARBON_WEIGHT,
    )
except Exception:
    try:
        from pulse_geometry import (  # type: ignore
            EDGE_CONTEXT_ID,
            APEX_CONTEXT_ID,
            RHYTHM_CONTEXT_ID,
            ORGANIC_CARBON_WEIGHT,
        )
    except Exception:
        EDGE_CONTEXT_ID = "context:known-universe-edge"
        APEX_CONTEXT_ID = "context:shared-apex-spine"
        RHYTHM_CONTEXT_ID = "context:ao-po-rhythm"
        ORGANIC_CARBON_WEIGHT = 6

# ── Versioned science baseline ────────────────────────────────────────────────
LANIAKEA_REF = (
    "Tully R.B. et al. (2014) 'Laniakea: our home supercluster' "
    "Nature 513, 71–73. doi:10.1038/nature13674"
)
SOLAR_CYCLE_NUMBER = 25
SOLAR_CYCLE_START_YEAR = 2019   # Dec 2019 solar minimum (SC24→SC25 transition)
SOLAR_CYCLE_PEAK_YEAR = 2025    # SC25 peak forecast (NOAA/NASA)
SCHUMANN_BASE_HZ = 7.83         # Earth-ionosphere cavity resonance, Schumann 1952
# Six Schumann harmonics aligned to chakra indices 1–6
SCHUMANN_HARMONICS = (7.83, 14.3, 20.8, 27.3, 33.8, 39.0)

# Universe science refresh cadence
SCIENCE_REFRESH_INTERVAL_DAYS = 7

# NASA DONKI solar flare endpoint (DEMO_KEY = unauthenticated low-rate access)
DONKI_BASE = "https://api.nasa.gov/DONKI"
DONKI_API_KEY = os.environ.get("NASA_API_KEY", "DEMO_KEY")

# ── Triskelion arm definitions ────────────────────────────────────────────────
_TRISKELION_ARMS = (
    {
        "id": "triskelion:universe-to-civic",
        "src": SAGE_UNIVERSE_CONTEXT_ID,
        "dst": SAGE_CIVIC_CONTEXT_ID,
        "arm_index": 1,
        "label": "Universe → Civic",
        "hoi_phase": "expanding",
        "hoi_anahulu": "Hoʻonui",
        "description": (
            "Solar and galactic forces expand outward into civic life — seasons, agriculture, "
            "weather patterns, and natural law shape what communities must govern."
        ),
    },
    {
        "id": "triskelion:civic-to-human",
        "src": SAGE_CIVIC_CONTEXT_ID,
        "dst": HUMAN_INITIATION_CONTEXT_ID,
        "arm_index": 2,
        "label": "Civic → Human",
        "hoi_phase": "holding",
        "hoi_anahulu": "Poepoe",
        "description": (
            "Civic choices and governance patterns hold and shape the individual human body — "
            "votes become lived experience; contracts become material conditions."
        ),
    },
    {
        "id": "triskelion:human-to-universe",
        "src": HUMAN_INITIATION_CONTEXT_ID,
        "dst": SAGE_UNIVERSE_CONTEXT_ID,
        "arm_index": 3,
        "label": "Human → Universe",
        "hoi_phase": "returning",
        "hoi_anahulu": "Hoʻēmi",
        "description": (
            "Human intention, prayer, and action return to the universal source — "
            "the Hoʻi loop closes; the initiation completes."
        ),
    },
)

# ── Chakra crosswalk table ─────────────────────────────────────────────────────
# Six chakra centers mapped to:
#   physiology: nerve plexus + endocrine gland (anatomical science)
#   civic:      the civic action domain this register governs
#   universe:   the corresponding physical/astronomical resonance
#
# Scientific note: chakra-nerve plexus mapping is drawn from integrative anatomy
# (Judith 2004, Wheels of Life; Motoyama 1981, Theories of the Chakras).
# Schumann harmonic alignment: HeartMath Institute cardiac coherence research shows
# the heart's ~0.1 Hz rhythm entrains to Schumann 7.83 Hz (McCraty et al. 2017).
_CHAKRA_CROSSWALK = (
    {
        "chakra_index": 1,
        "tone": "rooted",
        "physiology_anchor": "sacrum / adrenal glands / survival and grounding systems",
        "endocrine_gland": "adrenal",
        "nerve_plexus": "sacral plexus / coccygeal nerve",
        "civic_resonance": "land rights, water rights, zoning, territorial boundary, land stewardship",
        "civic_lane_type": "oversight",
        "universe_resonance": "Earth core magnetic field, gravity, tectonic stability",
        "quadrant": "Mauka",
        "schumann_harmonic_hz": SCHUMANN_HARMONICS[0],
        "notes": "Foundation of all other registers. No civic action stands without land sovereignty.",
    },
    {
        "chakra_index": 2,
        "tone": "flow",
        "physiology_anchor": "sacral plexus / gonads / reproductive and creative generation",
        "endocrine_gland": "gonads",
        "nerve_plexus": "sacral plexus",
        "civic_resonance": "grants, creative output, studio production jobs, cultural funding",
        "civic_lane_type": "creative",
        "universe_resonance": "Ocean tides, lunar gravitational pull, fluid dynamics",
        "quadrant": "Makai",
        "schumann_harmonic_hz": SCHUMANN_HARMONICS[1],
        "notes": "Creative generation register. HINA Pō render work rides this register.",
    },
    {
        "chakra_index": 3,
        "tone": "will",
        "physiology_anchor": "solar plexus / pancreas / digestive fire and metabolic action",
        "endocrine_gland": "pancreas",
        "nerve_plexus": "celiac plexus (solar plexus)",
        "civic_resonance": "votes, contracts, budget decisions, procurement, executive action",
        "civic_lane_type": "engineering",
        "universe_resonance": "Solar photon output, nuclear fusion fire, heliospheric pressure, solar cycle amplitude",
        "quadrant": "Kula",
        "schumann_harmonic_hz": SCHUMANN_HARMONICS[2],
        "notes": "Action register. Amplified at solar maximum; suppressed at solar minimum.",
    },
    {
        "chakra_index": 4,
        "tone": "heart",
        "physiology_anchor": "cardiac plexus / thymus gland / immune coherence and relational bonding",
        "endocrine_gland": "thymus",
        "nerve_plexus": "cardiac plexus",
        "civic_resonance": "community testimony, tribute, aloha network, cross-tenant solidarity",
        "civic_lane_type": "output",
        "universe_resonance": "Earth electromagnetic field coherence, Schumann resonance 7.83 Hz baseline",
        "quadrant": "Universal",
        "schumann_harmonic_hz": SCHUMANN_HARMONICS[3],
        "notes": (
            "Universal connector. Schumann resonance (7.83 Hz) maps to cardiac coherence "
            "(McCraty, HeartMath Institute, 2017)."
        ),
    },
    {
        "chakra_index": 5,
        "tone": "voice",
        "physiology_anchor": "pharyngeal plexus / thyroid and parathyroid / metabolic expression and timing",
        "endocrine_gland": "thyroid",
        "nerve_plexus": "pharyngeal plexus / cervical sympathetic ganglion",
        "civic_resonance": "public testimony, ōlelo Hawaiʻi, civic voice, public comment, media signal",
        "civic_lane_type": "publish",
        "universe_resonance": "Electromagnetic wave propagation, radio spectrum, heliospheric communication",
        "quadrant": "Universal",
        "schumann_harmonic_hz": SCHUMANN_HARMONICS[4],
        "notes": "Expression register. ōlelo treated with humility — community review via olelo_watch.py.",
    },
    {
        "chakra_index": 6,
        "tone": "vision",
        "physiology_anchor": "carotid plexus / pituitary gland / neuroendocrine master regulation",
        "endocrine_gland": "pituitary",
        "nerve_plexus": "carotid plexus / internal carotid nerves",
        "civic_resonance": "oversight, audit, transparency, collusion pattern graph, institutional accountability",
        "civic_lane_type": "audit",
        "universe_resonance": "Cosmic light, photon observational science, LaniAkea filament edge proximity",
        "quadrant": "Universal",
        "schumann_harmonic_hz": SCHUMANN_HARMONICS[5],
        "notes": (
            "Closest to LaniAkea boundary. HINA jobs at chakra_index=6 carry the highest scope. "
            "The 7th (crown) is the context:known-universe-edge itself — outside the carbon-6 human register."
        ),
    },
)

# Crown note — 7th position, outside the carbon-6 cycle
_CROWN = {
    "id": "crown:laniakea",
    "name": "LaniAkea Crown",
    "note": (
        "The 7th position is the context:known-universe-edge node — the LaniAkea boundary. "
        "The human chakra system (carbon-6, indices 1–6) points toward but does not contain "
        "the universal boundary. The crown is the outermost context, not a human energy register."
    ),
    "context_id": EDGE_CONTEXT_ID,
    "layer": LAYER,
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _say(m: str) -> None:
    try:
        if sys.stdout:
            print(m, flush=True)
    except Exception:
        pass


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _post(statements: list[dict], timeout: float = 30) -> dict | None:
    body = json.dumps({"statements": statements}).encode("utf-8")
    req = urllib.request.Request(
        NEO,
        data=body,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            out = json.loads(resp.read().decode("utf-8", "replace"))
    except urllib.error.URLError as exc:
        _say("sage_trinity: Neo4j not reachable at %s (%s)" % (NEO, str(exc)[:120]))
        return None
    if out.get("errors"):
        _say("sage_trinity Cypher errors: %s" % json.dumps(out.get("errors"))[:300])
    return out


# ── Universe science data ─────────────────────────────────────────────────────

def _fetch_solar_flares(days_back: int = 30) -> list[dict]:
    """Try NASA DONKI for recent solar flares; return [] on any failure."""
    end = datetime.now(timezone.utc).date()
    start = end - timedelta(days=days_back)
    url = "%s/FLR?startDate=%s&endDate=%s&api_key=%s" % (DONKI_BASE, start, end, DONKI_API_KEY)
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8", "replace"))
            return data if isinstance(data, list) else []
    except Exception:
        return []


def _solar_activity_level(flares: list[dict]) -> str:
    """Classify recent solar activity from flare class list."""
    if not flares:
        return "unknown"
    classes = [str(f.get("classType") or "").upper() for f in flares]
    if any(c.startswith("X") for c in classes):
        return "high"
    if any(c.startswith("M") for c in classes):
        return "moderate"
    return "low"


def _solar_cycle_phase(year: int, month: int) -> str:
    """Approximate Solar Cycle 25 phase from year/month.

    SC25 start: Dec 2019 | Peak: ~mid-2025 | Duration ~11yr | Next min: ~2030
    """
    progress_months = (year - SOLAR_CYCLE_START_YEAR) * 12 + month
    if progress_months < 0:
        return "pre-cycle"
    if progress_months < 36:
        return "rising"
    if progress_months < 66:
        return "near-peak"
    if progress_months < 90:
        return "post-peak-declining"
    if progress_months < 120:
        return "declining"
    return "near-minimum"


def sage_universe_refresh(force: bool = False) -> dict:
    """Fetch/derive current universe science data and write to Neo4j.

    Attempts a live NASA DONKI fetch for recent solar flares; falls back to a
    static baseline on any network failure.  Results are written to the
    ``sage:universe`` context node in Neo4j when Neo4j is reachable.

    Args:
        force: if True, bypass the 7-day cadence gate and always refresh.

    Returns:
        dict with universe science snapshot (always returned even if Neo4j is down).
    """
    now = datetime.now(timezone.utc)
    flares = _fetch_solar_flares(days_back=30)
    activity = _solar_activity_level(flares)
    phase = _solar_cycle_phase(now.year, now.month)

    data: dict = {
        "id": SAGE_UNIVERSE_CONTEXT_ID,
        "science_version": "SC25-v1",
        "laniakea_ref": LANIAKEA_REF,
        "laniakea_extent_mpc": 520,
        "great_attractor_distance_mpc": 65,
        "milky_way_diameter_ly": 100_000,
        "solar_system_extent_au": 287,
        "solar_cycle_number": SOLAR_CYCLE_NUMBER,
        "solar_cycle_start_year": SOLAR_CYCLE_START_YEAR,
        "solar_cycle_peak_year": SOLAR_CYCLE_PEAK_YEAR,
        "solar_cycle_phase": phase,
        "solar_activity_level": activity,
        "solar_flare_count_30d": len(flares),
        "schumann_base_hz": SCHUMANN_BASE_HZ,
        "schumann_harmonics": list(SCHUMANN_HARMONICS),
        "science_source": "NASA-DONKI" if flares else "static-baseline",
        "science_refreshed_at": now.isoformat().replace("+00:00", "Z"),
        "layer": LAYER,
    }

    _post([
        {
            "statement": (
                "MERGE (n:SageTrinity:TrinityContext {id:$id}) SET n += $props"
            ),
            "parameters": {"id": SAGE_UNIVERSE_CONTEXT_ID, "props": data},
        }
    ])
    return data


# ── Row builders ──────────────────────────────────────────────────────────────

def build_trinity_context_rows() -> list[dict]:
    """Return the three Trinity scale context nodes."""
    return [
        {
            "id": SAGE_UNIVERSE_CONTEXT_ID,
            "name": "Sage Universe",
            "trinity_scale": "universe",
            "scope": "outermost",
            "description": (
                "The outermost scientific frame: LaniAkea Supercluster → Milky Way → "
                "Virgo Cluster → Local Group → Solar System → Earth. "
                "Carries versioned solar cycle, Schumann resonance, and LaniAkea reference data."
            ),
            "laniakea_ref": LANIAKEA_REF,
            "solar_cycle_number": SOLAR_CYCLE_NUMBER,
            "schumann_base_hz": SCHUMANN_BASE_HZ,
            "outer_context_id": EDGE_CONTEXT_ID,
            "layer": LAYER,
        },
        {
            "id": SAGE_CIVIC_CONTEXT_ID,
            "name": "Sage Civic",
            "trinity_scale": "civic",
            "scope": "community",
            "description": (
                "The middle scale: Earth → Pacific → Hawaiʻi → island → district → tenant/community. "
                "The civic graph: money chains, votes, testimony, permits, contracts across 17 governments. "
                "Ao choices drive Pō balance via HINA on the kaulana mahina cadence."
            ),
            "civic_scope": "multi-government",
            "government_count": 17,
            "ao_po_rhythm_id": RHYTHM_CONTEXT_ID,
            "apex_spine_id": APEX_CONTEXT_ID,
            "layer": LAYER,
        },
        {
            "id": HUMAN_INITIATION_CONTEXT_ID,
            "name": "Sage Human Initiation",
            "trinity_scale": "human",
            "scope": "individual",
            "description": (
                "The innermost scale: the individual human being inside the tenant. "
                "A carbon body (C₆, atomic number 6) tuned to six energy registers via the chakra geometry. "
                "Circadian rhythm (dawn/day/dusk/night) maps to residence frequencies at place. "
                "The terminal receiver where universe and civic spirals converge."
            ),
            "organic_carbon_weight": ORGANIC_CARBON_WEIGHT,
            "chakra_count": ORGANIC_CARBON_WEIGHT,
            "carbon_atomic_number": 6,
            "human_alignment_system": "chakra",
            "circadian_ref": (
                "Hall, Rosbash, Young (2017) Nobel Prize in Physiology — molecular circadian clock mechanism"
            ),
            "crown_context_id": EDGE_CONTEXT_ID,
            "layer": LAYER,
        },
    ]


def build_chakra_crosswalk_rows() -> list[dict]:
    """Return one ChakraCrossWalk row per chakra index (1–6)."""
    rows = []
    for entry in _CHAKRA_CROSSWALK:
        rows.append(
            {
                "id": "chakra-crosswalk:%d" % entry["chakra_index"],
                "chakra_index": entry["chakra_index"],
                "tone": entry["tone"],
                "physiology_anchor": entry["physiology_anchor"],
                "endocrine_gland": entry["endocrine_gland"],
                "nerve_plexus": entry["nerve_plexus"],
                "civic_resonance": entry["civic_resonance"],
                "civic_lane_type": entry["civic_lane_type"],
                "universe_resonance": entry["universe_resonance"],
                "quadrant": entry["quadrant"],
                "schumann_harmonic_hz": entry["schumann_harmonic_hz"],
                "notes": entry["notes"],
                "trinity_scale": "human",
                "layer": LAYER,
            }
        )
    return rows


def build_triskelion_arm_rows() -> list[dict]:
    """Return three SPIRAL_ARM relationship descriptor rows (triskelion)."""
    return [
        {
            "id": arm["id"],
            "src": arm["src"],
            "dst": arm["dst"],
            "arm_index": arm["arm_index"],
            "label": arm["label"],
            "hoi_phase": arm["hoi_phase"],
            "hoi_anahulu": arm["hoi_anahulu"],
            "description": arm["description"],
            "layer": LAYER,
        }
        for arm in _TRISKELION_ARMS
    ]


def build_crown_row() -> dict:
    return dict(_CROWN)


# ── Snapshot ──────────────────────────────────────────────────────────────────

def snapshot() -> dict:
    """Return a pure-Python snapshot of the Trinity model (no Neo4j needed)."""
    trinity = build_trinity_context_rows()
    chakra = build_chakra_crosswalk_rows()
    arms = build_triskelion_arm_rows()
    crown = build_crown_row()
    return {
        "layer": LAYER,
        "model": "sage_trinity_triskelion",
        "symbol": "triskelion + hoʻi spiral",
        "scales": {
            "universe": SAGE_UNIVERSE_CONTEXT_ID,
            "civic": SAGE_CIVIC_CONTEXT_ID,
            "human": HUMAN_INITIATION_CONTEXT_ID,
        },
        "crown": crown,
        "counts": {
            "trinity_contexts": len(trinity),
            "chakra_crosswalk": len(chakra),
            "triskelion_arms": len(arms),
        },
        "trinity_contexts": trinity,
        "chakra_crosswalk": chakra,
        "triskelion_arms": arms,
    }


# ── Neo4j write ───────────────────────────────────────────────────────────────

def refresh() -> bool:
    """Write the Sage Trinity model into Neo4j.

    Additive layer (``sage_trinity``); never disturbs pulse_geometry or
    private_spine layers.  Soft-skips if Neo4j is unreachable.

    The universe science data fetch (NASA DONKI) is gated to run at most
    once per ``SCIENCE_REFRESH_INTERVAL_DAYS`` days to avoid hammering the API
    on every nightly graph_refresh run.
    """
    trinity_rows = build_trinity_context_rows()
    chakra_rows = build_chakra_crosswalk_rows()
    arm_rows = build_triskelion_arm_rows()
    crown = build_crown_row()

    # Ensure constraint exists
    if _post([{
        "statement": (
            "CREATE CONSTRAINT sage_trinity_id IF NOT EXISTS "
            "FOR (x:SageTrinity) REQUIRE x.id IS UNIQUE"
        ),
    }]) is None:
        return False

    # 1. Trinity context nodes
    _post([{
        "statement": (
            "UNWIND $rows AS r "
            "MERGE (n:SageTrinity:TrinityContext {id:r.id}) SET n += r"
        ),
        "parameters": {"rows": trinity_rows},
    }])

    # 2. Chakra crosswalk nodes
    _post([{
        "statement": (
            "UNWIND $rows AS r "
            "MERGE (n:SageTrinity:ChakraCrossWalk {id:r.id}) SET n += r"
        ),
        "parameters": {"rows": chakra_rows},
    }])

    # 3. Crown node
    _post([{
        "statement": (
            "MERGE (n:SageTrinity:CrownContext {id:$id}) SET n += $props"
        ),
        "parameters": {"id": crown["id"], "props": crown},
    }])

    # 4. Triskelion SPIRAL_ARM edges (the three-arm closed loop)
    _post([{
        "statement": (
            "UNWIND $rows AS r "
            "MATCH (src:SageTrinity {id:r.src}) "
            "MATCH (dst:SageTrinity {id:r.dst}) "
            "MERGE (src)-[e:SPIRAL_ARM {id:r.id}]->(dst) "
            "SET e += {arm_index:r.arm_index, label:r.label, hoi_phase:r.hoi_phase, "
            "hoi_anahulu:r.hoi_anahulu, description:r.description, layer:r.layer}"
        ),
        "parameters": {"rows": arm_rows},
    }])

    # 5. Universe and Civic INFORMS edges into Human Initiation
    _post([
        {
            "statement": (
                "MATCH (universe:SageTrinity {id:$uid}) "
                "MATCH (human:SageTrinity {id:$hid}) "
                "MERGE (universe)-[e:INFORMS {key:'universe-informs-human'}]->(human) "
                "SET e.layer = $layer, "
                "e.note = 'Solar/Schumann/LaniAkea data writes into human body register'"
            ),
            "parameters": {
                "uid": SAGE_UNIVERSE_CONTEXT_ID,
                "hid": HUMAN_INITIATION_CONTEXT_ID,
                "layer": LAYER,
            },
        },
        {
            "statement": (
                "MATCH (civic:SageTrinity {id:$cid}) "
                "MATCH (human:SageTrinity {id:$hid}) "
                "MERGE (civic)-[e:INFORMS {key:'civic-informs-human'}]->(human) "
                "SET e.layer = $layer, "
                "e.note = 'Civic Ao choices shape the lived experience of the person inside the tenant'"
            ),
            "parameters": {
                "cid": SAGE_CIVIC_CONTEXT_ID,
                "hid": HUMAN_INITIATION_CONTEXT_ID,
                "layer": LAYER,
            },
        },
    ])

    # 6. HAS_CHAKRA edges: Human Initiation → ChakraCrossWalk (one per index)
    _post([{
        "statement": (
            "UNWIND $rows AS r "
            "MATCH (cw:SageTrinity:ChakraCrossWalk {id:r.id}) "
            "MATCH (human:SageTrinity {id:$hid}) "
            "MERGE (human)-[e:HAS_CHAKRA {chakra_index:r.chakra_index}]->(cw) "
            "SET e.layer = $layer, e.tone = r.tone"
        ),
        "parameters": {
            "rows": chakra_rows,
            "hid": HUMAN_INITIATION_CONTEXT_ID,
            "layer": LAYER,
        },
    }])

    # 7. TUNES_CELLS: ChakraCrossWalk → PulseGeometry PulseCells by chakra_index
    #    (cross-layer additive edge — links Trinity model into pulse geometry cells)
    _post([{
        "statement": (
            "UNWIND $rows AS r "
            "MATCH (cw:SageTrinity:ChakraCrossWalk {id:r.id}) "
            "MATCH (cell:PulseGeometry:PulseCell {chakra_index:r.chakra_index}) "
            "MERGE (cw)-[e:TUNES_CELLS {key:r.id}]->(cell) "
            "SET e.layer = $layer, e.tone = r.tone, e.civic_lane_type = r.civic_lane_type"
        ),
        "parameters": {"rows": chakra_rows, "layer": LAYER},
    }])

    # 8. Trinity Universe GROUNDS_IN the outer pulse_geometry edge context
    _post([{
        "statement": (
            "MATCH (universe:SageTrinity {id:$uid}) "
            "MATCH (edge:PulseGeometry {id:$eid}) "
            "MERGE (universe)-[e:GROUNDS_IN {key:'trinity-universe-grounds-in-edge'}]->(edge) "
            "SET e.layer = $layer, "
            "e.note = 'Sage Universe Trinity scale grounds in the known-universe-edge context'"
        ),
        "parameters": {
            "uid": SAGE_UNIVERSE_CONTEXT_ID,
            "eid": EDGE_CONTEXT_ID,
            "layer": LAYER,
        },
    }])

    # 9. Universe science refresh (weekly cadence gate)
    _maybe_refresh_universe()

    _say(
        "sage_trinity: loaded %d trinity contexts, %d chakra crosswalk nodes, %d triskelion arms."
        % (len(trinity_rows), len(chakra_rows), len(arm_rows))
    )
    return True


def _maybe_refresh_universe() -> None:
    """Run sage_universe_refresh only if science data is stale (> SCIENCE_REFRESH_INTERVAL_DAYS)."""
    # Read the last science refresh timestamp from the universe node in Neo4j
    result = _post([{
        "statement": (
            "MATCH (n:SageTrinity {id:$id}) "
            "RETURN n.science_refreshed_at AS ts LIMIT 1"
        ),
        "parameters": {"id": SAGE_UNIVERSE_CONTEXT_ID},
    }])
    last_ts = None
    if result:
        for row in result.get("results", [{}])[0].get("data", []):
            last_ts = (row.get("row") or [None])[0]
            break

    if last_ts:
        try:
            last_dt = datetime.fromisoformat(str(last_ts).replace("Z", "+00:00"))
            age_days = (datetime.now(timezone.utc) - last_dt).days
            if age_days < SCIENCE_REFRESH_INTERVAL_DAYS:
                return
        except Exception:
            pass

    sage_universe_refresh()


# ── CLI entry ─────────────────────────────────────────────────────────────────

def main() -> None:
    ok = refresh()
    if ok:
        snap = snapshot()
        _say(json.dumps(snap["counts"], indent=2))


if __name__ == "__main__":
    main()
