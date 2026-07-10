# -*- coding: utf-8 -*-
"""graph_refresh.py — keep the LOCAL civic graph+vector store current, on the Hina cadence. FREE.

Runs on the sunset (hina/pō) edge — civic/record work rides Hina, not a wall clock (Jimmy 2026-07-08).
Reloads the Maui money-chain into Neo4j (chain_to_graph), refreshes the vector index from the host
Ollama embeddings (graph_vectors), then refreshes the additive PRIVATE skill/workboard spine
(private_spine) and the dedicated pulse geometry lattice (pulse_geometry). Zero Claude tokens.
Resilient: if Neo4j or Ollama is down it logs and skips — never crashes the maintenance tick.

v5.2 ratchet:
  - Neo4j is the local graph language bus for civic, vector, spine, and pulse layers
  - refresh state is persisted for PRIVATE owner surfaces
  - targeted refreshes can update a subset of layers for near-real-time flow
"""
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

REPO = Path(HERE).resolve().parent
DEFAULT_TARGETS = ("graph", "vectors", "private_spine", "pulse_geometry", "sage_trinity")
STATE_PATH = Path(os.environ.get("GRAPH_REFRESH_STATE_PATH", "/tmp/12sgi-graph-refresh-state.json"))
GRAPH_STACK_VERSION = os.environ.get("GRAPH_STACK_VERSION", "5.2")
NEO = os.environ.get("NEO4J_HTTP", "http://127.0.0.1:7474/db/neo4j/tx/commit")
EDGE_CONTEXT_ID = "context:known-universe-edge"
APEX_CONTEXT_ID = "context:shared-apex-spine"
RHYTHM_CONTEXT_ID = "context:ao-po-rhythm"


def _say(m):
    try:
        if sys.stdout:
            print(m, flush=True)
    except Exception:
        pass


def _now_iso():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _default_state():
    return {
        "graph_stack_version": GRAPH_STACK_VERSION,
        "neo4j_http": NEO,
        "state_path": str(STATE_PATH),
        "status": "idle",
        "last_mode": None,
        "last_reason": None,
        "last_started_at": None,
        "last_completed_at": None,
        "last_successful_at": None,
        "requested_targets": list(DEFAULT_TARGETS),
        "last_result": None,
        "layers": {target: "unknown" for target in DEFAULT_TARGETS},
    }


def _read_state():
    base = _default_state()
    try:
        if STATE_PATH.exists():
            payload = json.loads(STATE_PATH.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                base.update(payload)
                layers = payload.get("layers")
                if isinstance(layers, dict):
                    merged_layers = {target: "unknown" for target in DEFAULT_TARGETS}
                    merged_layers.update({str(k): str(v) for k, v in layers.items()})
                    base["layers"] = merged_layers
    except Exception:
        pass
    base["graph_stack_version"] = GRAPH_STACK_VERSION
    base["neo4j_http"] = NEO
    base["state_path"] = str(STATE_PATH)
    return base


def _write_state(**updates):
    state = _read_state()
    state.update(updates)
    state["graph_stack_version"] = GRAPH_STACK_VERSION
    state["neo4j_http"] = NEO
    state["state_path"] = str(STATE_PATH)
    if "layers" in updates and isinstance(updates["layers"], dict):
        merged_layers = {target: "unknown" for target in DEFAULT_TARGETS}
        merged_layers.update(state.get("layers") or {})
        merged_layers.update({str(k): str(v) for k, v in updates["layers"].items()})
        state["layers"] = merged_layers
    try:
        STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp = STATE_PATH.with_suffix(STATE_PATH.suffix + ".tmp")
        tmp.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")
        tmp.replace(STATE_PATH)
    except Exception as exc:
        _say("graph_refresh state write skip: %s" % str(exc)[:160])
    return state


def _normalize_targets(targets):
    if not targets:
        return list(DEFAULT_TARGETS)
    wanted = []
    for target in targets:
        label = str(target or "").strip().lower()
        if label in DEFAULT_TARGETS and label not in wanted:
            wanted.append(label)
    return wanted or list(DEFAULT_TARGETS)


def _age_seconds(iso_text):
    if not iso_text:
        return None
    try:
        parsed = datetime.fromisoformat(str(iso_text).replace("Z", "+00:00"))
        return max(0, int((datetime.now(timezone.utc) - parsed).total_seconds()))
    except Exception:
        return None


def _audit_lens():
    return {
        "frame": "12-stone-earth-justice-audit",
        "boundary": "PRIVATE",
        "money_intention": {
            "question": "How does money intention move through civic flow and touch the edge of nature?",
            "source_layer": "graph",
            "source_dataset": "maui money-chain",
            "edge_context_id": EDGE_CONTEXT_ID,
            "earth_justice_target": "align money flow before public action or publish",
        },
        "levi_breastplate": {
            "concept": "12-stone audit",
            "stones": [
                {"slot": 1, "name": "foundation", "layer": "graph", "lens": "origin of record"},
                {"slot": 2, "name": "witness", "layer": "graph", "lens": "who is seen in the chain"},
                {"slot": 3, "name": "source", "layer": "graph", "lens": "where money begins"},
                {"slot": 4, "name": "flow", "layer": "graph", "lens": "where money moves"},
                {"slot": 5, "name": "intention", "layer": "graph", "lens": "what the flow claims to serve"},
                {"slot": 6, "name": "ledger", "layer": "vectors", "lens": "what can be recalled and compared"},
                {"slot": 7, "name": "approval", "layer": "private_spine", "lens": "who cleared the action"},
                {"slot": 8, "name": "lineage", "layer": "private_spine", "lens": "what the work derives from"},
                {"slot": 9, "name": "boundary", "layer": "pulse_geometry", "lens": "edge of nature and quadrant boundary"},
                {"slot": 10, "name": "balance", "layer": "pulse_geometry", "lens": "Ao/Pō rhythm and cadence"},
                {"slot": 11, "name": "justice", "layer": "pulse_geometry", "lens": "earth-serving quadrant fit"},
                {"slot": 12, "name": "renewal", "layer": "graph_refresh", "lens": "whether the ratchet has been refreshed"},
            ],
        },
        "urim": {
            "signal": "edge reading",
            "layer": "pulse_geometry",
            "context_id": EDGE_CONTEXT_ID,
            "reads": ["nature", "quadrant boundary", "human residence cadence"],
        },
        "thummim": {
            "signal": "justice reading",
            "layers": ["private_spine", "pulse_geometry"],
            "context_ids": [APEX_CONTEXT_ID, RHYTHM_CONTEXT_ID],
            "reads": ["approval lineage", "governing context", "balance before publish"],
        },
        "earth_justice": {
            "approach": "money flow must stay accountable to boundary, balance, and civic lineage",
            "checks": ["graph flow", "vector recall", "private approvals", "edge/apex/rhythm contexts"],
        },
    }


def status():
    state = _read_state()
    return {
        "boundary": "PRIVATE",
        "graph_stack_version": GRAPH_STACK_VERSION,
        "neo4j_http": NEO,
        "state_path": str(STATE_PATH),
        "status": state.get("status", "idle"),
        "last_mode": state.get("last_mode"),
        "last_reason": state.get("last_reason"),
        "requested_targets": state.get("requested_targets") or list(DEFAULT_TARGETS),
        "supported_targets": list(DEFAULT_TARGETS),
        "layers": state.get("layers") or {target: "unknown" for target in DEFAULT_TARGETS},
        "freshness": {
            "last_started_at": state.get("last_started_at"),
            "last_completed_at": state.get("last_completed_at"),
            "last_successful_at": state.get("last_successful_at"),
            "age_seconds": _age_seconds(state.get("last_successful_at")),
        },
        "last_result": state.get("last_result"),
        "audit_lens": _audit_lens(),
    }


def refresh(mode="full", reason="manual", targets=None):
    wanted = _normalize_targets(targets)
    started_at = _now_iso()
    layer_state = {target: "skipped" for target in DEFAULT_TARGETS}
    _write_state(
        status="running",
        last_mode=str(mode or "full"),
        last_reason=str(reason or "manual"),
        last_started_at=started_at,
        requested_targets=wanted,
        last_result=None,
        layers=layer_state,
    )
    notes = []
    ok = True
    try:
        graph_loaded = True
        if "graph" in wanted:
            import chain_to_graph as G
            graph_loaded = bool(G.load())  # returns False + logs if Neo4j is down
            layer_state["graph"] = "current" if graph_loaded else "failed"
            if graph_loaded:
                notes.append("graph current")
            else:
                notes.append("graph skipped")
                ok = False
        if "vectors" in wanted:
            vectors_ready = False
            if graph_loaded or "graph" not in wanted:
                import graph_vectors as V
                vectors_ready = bool(V.build())
            layer_state["vectors"] = "current" if vectors_ready else "failed"
            notes.append("vectors current" if vectors_ready else "vectors skipped")
            ok = ok and vectors_ready
        spine_note = "private spine skipped"
        if "private_spine" in wanted:
            try:
                import private_spine as P
                if P.refresh():
                    layer_state["private_spine"] = "current"
                    spine_note = "private spine current"
                else:
                    layer_state["private_spine"] = "failed"
                    spine_note = "private spine skipped"
                    ok = False
            except Exception as spine_exc:
                layer_state["private_spine"] = "failed"
                spine_note = "private spine skipped"
                ok = False
                _say("graph_refresh spine skip: %s" % str(spine_exc)[:160])
        notes.append(spine_note)
        pulse_note = "pulse geometry skipped"
        if "pulse_geometry" in wanted:
            try:
                import pulse_geometry as PG
                if PG.refresh():
                    layer_state["pulse_geometry"] = "current"
                    pulse_note = "pulse geometry current"
                else:
                    layer_state["pulse_geometry"] = "failed"
                    pulse_note = "pulse geometry skipped"
                    ok = False
            except Exception as pulse_exc:
                layer_state["pulse_geometry"] = "failed"
                pulse_note = "pulse geometry skipped"
                ok = False
                _say("graph_refresh pulse skip: %s" % str(pulse_exc)[:160])
        notes.append(pulse_note)
        trinity_note = "sage trinity skipped"
        if "sage_trinity" in wanted:
            try:
                import sage_trinity as ST
                if ST.refresh():
                    layer_state["sage_trinity"] = "current"
                    trinity_note = "sage trinity current"
                else:
                    layer_state["sage_trinity"] = "failed"
                    trinity_note = "sage trinity skipped"
                    ok = False
            except Exception as trinity_exc:
                layer_state["sage_trinity"] = "failed"
                trinity_note = "sage trinity skipped"
                ok = False
                _say("graph_refresh trinity skip: %s" % str(trinity_exc)[:160])
        notes.append(trinity_note)
        completed_at = _now_iso()
        result = "ok" if ok else "degraded"
        _write_state(
            status="idle",
            last_mode=str(mode or "full"),
            last_reason=str(reason or "manual"),
            last_completed_at=completed_at,
            last_successful_at=completed_at if ok else _read_state().get("last_successful_at"),
            requested_targets=wanted,
            last_result=result,
            layers=layer_state,
        )
        if "graph" in wanted and not graph_loaded:
            _say("graph_refresh: Neo4j unreachable — skipped (no crash).")
        else:
            _say("graph_refresh: %s (%s, Hina)." % (result, "; ".join(notes)))
        return ok
    except Exception as e:
        _write_state(
            status="idle",
            last_mode=str(mode or "full"),
            last_reason=str(reason or "manual"),
            last_completed_at=_now_iso(),
            requested_targets=wanted,
            last_result="error",
            layers=layer_state,
        )
        _say("graph_refresh error: %s" % str(e)[:160])
        return False


def main():
    refresh(mode="full", reason="cli")


if __name__ == "__main__":
    main()
