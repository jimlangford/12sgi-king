import json
import time
from functools import lru_cache
from pathlib import Path
from typing import Any


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


def lifecycle_authority() -> str:
    value = canonical_job_contract().get("lifecycle_authority")
    return str(value or "domain_status_authoritative")


def transition_history_policy() -> dict[str, Any]:
    raw = canonical_job_contract().get("transition_history") or {}
    if not isinstance(raw, dict):
        raw = {}
    max_entries = raw.get("max_entries")
    if not isinstance(max_entries, int) or max_entries < 1:
        max_entries = 64
    return {
        "max_entries": max_entries,
        "ordering": str(raw.get("ordering") or "oldest-first"),
        "truncate": str(raw.get("truncate") or "drop-oldest"),
    }


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


def _normalise_transition_history(value: Any) -> list[dict]:
    if not isinstance(value, list):
        return []
    out: list[dict] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        out.append(
            {
                "from_state": normalise_state(item.get("from_state")),
                "to_state": normalise_state(item.get("to_state")),
                "ts": int(item.get("ts") or int(time.time())),
                "actor": str(item.get("actor") or ""),
                "engine": str(item.get("engine") or ""),
                "reason": str(item.get("reason") or ""),
                "evidence_hash": str(item.get("evidence_hash") or ""),
            }
        )
    policy = transition_history_policy()
    if len(out) > policy["max_entries"]:
        out = out[-policy["max_entries"] :]
    return out


def _normalise_base_envelope(envelope: dict, *, domain: str | None = None, fallback_state: str | None = None) -> dict:
    src = dict(envelope or {})
    target_domain = str(src.get("domain") or domain or "").strip()
    state = normalise_state(src.get("state") or fallback_state)
    if target_domain and state:
        if src.get("state") is None:
            require_transition(target_domain, None, state, context="normalise_envelope")
    return {
        "schema": str(src.get("schema") or job_envelope_schema()),
        "schema_version": str(src.get("schema_version") or canonical_job_contract().get("schema_version") or "2.0.0"),
        "domain": target_domain,
        "service": str(src.get("service") or ""),
        "action": str(src.get("action") or ""),
        "state": state,
        "lane": str(src.get("lane") or ""),
        "correlation_id": src.get("correlation_id"),
        "entity_id": src.get("entity_id"),
        "ts": int(src.get("ts") or int(time.time())),
        "payload": src.get("payload") if isinstance(src.get("payload"), dict) else {},
        "metadata": src.get("metadata") if isinstance(src.get("metadata"), dict) else {},
        "transition_history": _normalise_transition_history(src.get("transition_history")),
    }


def normalise_envelope(envelope: dict, *, domain: str | None = None, fallback_state: str | None = None) -> dict:
    return _normalise_base_envelope(envelope, domain=domain, fallback_state=fallback_state)


def sync_envelope_state(
    envelope: dict,
    state: str,
    *,
    actor: str = "guardian",
    engine: str = "guardian",
    reason: str = "domain_status_sync",
) -> dict:
    target = normalise_state(state)
    current = _normalise_base_envelope(envelope, domain=envelope.get("domain"), fallback_state=target)
    if current.get("state") == target:
        return current
    return transition_job_envelope(
        current,
        target,
        metadata_update={"sync_reason": reason},
        actor=actor,
        engine=engine,
        reason=reason,
        evidence_hash="",
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
    return _normalise_base_envelope(
        {
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
    },
        domain=domain,
        fallback_state=state,
    )


def transition_job_envelope(
    envelope: dict,
    to_state: str,
    *,
    metadata_update: dict | None = None,
    actor: str = "",
    engine: str = "",
    reason: str = "",
    evidence_hash: str = "",
) -> dict:
    current_envelope = _normalise_base_envelope(envelope)
    domain = str(current_envelope.get("domain") or "")
    current = current_envelope.get("state")
    target = normalise_state(to_state)
    if not target:
        raise ValueError("transition_job_envelope: to_state is required")
    if current == target:
        merged_meta = dict(current_envelope.get("metadata") or {})
        if metadata_update:
            merged_meta.update(metadata_update)
        current_envelope["metadata"] = merged_meta
        return current_envelope
    require_transition(domain, current, to_state, context="transition_job_envelope")
    next_envelope = dict(current_envelope)
    next_envelope["state"] = target
    next_envelope["ts"] = int(time.time())
    merged_meta = dict(next_envelope.get("metadata") or {})
    if metadata_update:
        merged_meta.update(metadata_update)
    next_envelope["metadata"] = merged_meta
    history = list(next_envelope.get("transition_history") or [])
    entry = {
        "from_state": normalise_state(current),
        "to_state": target,
        "ts": int(time.time()),
        "actor": str(actor or ""),
        "engine": str(engine or ""),
        "reason": str(reason or ""),
        "evidence_hash": str(evidence_hash or ""),
    }
    if not history or history[-1] != entry:
        history.append(entry)
    policy = transition_history_policy()
    if len(history) > policy["max_entries"]:
        history = history[-policy["max_entries"] :]
    next_envelope["transition_history"] = history
    return next_envelope
