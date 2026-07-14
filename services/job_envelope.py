import json
import time
from functools import lru_cache
from pathlib import Path


_DEFAULT_CONTRACT = Path(__file__).resolve().parents[1] / "config" / "canonical_job_contract.v2.json"


@lru_cache(maxsize=1)
def canonical_job_contract() -> dict:
    try:
        data = json.loads(_DEFAULT_CONTRACT.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def job_envelope_schema() -> str:
    value = canonical_job_contract().get("job_envelope_schema")
    if isinstance(value, str) and value.strip():
        return value.strip()
    return "canonical-job-envelope-v2"


def _domain_graph(domain: str) -> dict:
    domains = canonical_job_contract().get("domains") or {}
    graph = domains.get(domain) or {}
    return graph if isinstance(graph, dict) else {}


def _initial_states(domain: str) -> set[str]:
    graph = _domain_graph(domain)
    states = graph.get("initial_states") or []
    return {str(s).strip().lower() for s in states if str(s).strip()}


def _transitions(domain: str) -> dict[str, set[str]]:
    graph = _domain_graph(domain)
    raw = graph.get("allowed_transitions") or {}
    if not isinstance(raw, dict):
        return {}
    out: dict[str, set[str]] = {}
    for source, targets in raw.items():
        source_state = str(source).strip().lower()
        target_states = {str(t).strip().lower() for t in (targets or []) if str(t).strip()}
        if source_state:
            out[source_state] = target_states
    return out


def normalise_state(value: str | None) -> str:
    return (value or "").strip().lower()


def is_initial_state(domain: str, state: str | None) -> bool:
    return normalise_state(state) in _initial_states(domain)


def is_allowed_transition(domain: str, from_state: str | None, to_state: str | None) -> bool:
    dst = normalise_state(to_state)
    if not dst:
        return False
    src = normalise_state(from_state)
    if not src:
        return dst in _initial_states(domain)
    allowed = _transitions(domain).get(src, set())
    return dst in allowed


def require_transition(domain: str, from_state: str | None, to_state: str | None, *, context: str = "") -> None:
    if is_allowed_transition(domain, from_state, to_state):
        return
    prefix = f"{context}: " if context else ""
    raise ValueError(
        f"{prefix}invalid state transition for {domain}: "
        f"{normalise_state(from_state) or '<initial>'} -> {normalise_state(to_state) or '<empty>'}"
    )


def build_job_envelope(
    *,
    domain: str,
    service: str,
    action: str,
    state: str,
    payload: dict | None = None,
    lane: str | None = None,
    correlation_id: str | None = None,
    entity_id: str | None = None,
    metadata: dict | None = None,
) -> dict:
    require_transition(domain, None, state, context="build_job_envelope")
    return {
        "schema": job_envelope_schema(),
        "schema_version": str(canonical_job_contract().get("schema_version") or "2.0.0"),
        "domain": domain,
        "service": service,
        "action": action,
        "state": normalise_state(state),
        "lane": lane or "",
        "correlation_id": correlation_id,
        "entity_id": entity_id,
        "ts": int(time.time()),
        "payload": payload or {},
        "metadata": metadata or {},
    }


def transition_job_envelope(
    envelope: dict,
    to_state: str,
    *,
    metadata_update: dict | None = None,
) -> dict:
    domain = str(envelope.get("domain") or "")
    current = envelope.get("state")
    require_transition(domain, current, to_state, context="transition_job_envelope")
    next_envelope = dict(envelope)
    next_envelope["state"] = normalise_state(to_state)
    next_envelope["ts"] = int(time.time())
    merged_meta = dict(next_envelope.get("metadata") or {})
    if metadata_update:
        merged_meta.update(metadata_update)
    next_envelope["metadata"] = merged_meta
    return next_envelope
