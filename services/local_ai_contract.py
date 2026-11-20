from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any

BOUNDARY_LABELS = {"PUBLIC", "PRIVATE", "BRIDGE", "DO NOT TOUCH", "VERIFY"}
LANES = {"engineering", "creative", "output"}


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_iso(ts: str | None) -> datetime | None:
    if not ts:
        return None
    candidate = ts.strip()
    if candidate.endswith("Z"):
        candidate = candidate[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(candidate)
    except ValueError:
        return None


def _seconds_between(start_ts: str | None, end_ts: str | None) -> float | None:
    start = _parse_iso(start_ts)
    end = _parse_iso(end_ts)
    if not start or not end:
        return None
    return max(0.0, (end - start).total_seconds())


def validate_task_packet(packet: dict[str, Any]) -> dict[str, Any]:
    """Validate and normalize a Local AI -> Copilot task packet."""
    errors: list[str] = []
    normalized: dict[str, Any] = {}

    if not isinstance(packet, dict):
        return {"ok": False, "errors": ["packet must be an object"], "normalized": {}}

    goal = str(packet.get("goal") or "").strip()
    if not goal:
        errors.append("goal is required")
    else:
        normalized["goal"] = goal

    constraints = packet.get("constraints")
    if not isinstance(constraints, list) or not constraints or not all(str(item).strip() for item in constraints):
        errors.append("constraints must be a non-empty list of strings")
    else:
        normalized["constraints"] = [str(item).strip() for item in constraints]

    boundary_label = str(packet.get("boundary_label") or "").strip().upper()
    if boundary_label not in BOUNDARY_LABELS:
        errors.append(f"boundary_label must be one of: {sorted(BOUNDARY_LABELS)}")
    else:
        normalized["boundary_label"] = boundary_label

    expected_output = str(packet.get("expected_output") or "").strip()
    if not expected_output:
        errors.append("expected_output is required")
    else:
        normalized["expected_output"] = expected_output

    verification_target = packet.get("verification_target")
    if isinstance(verification_target, str):
        verification_target = verification_target.strip()
    if not verification_target:
        errors.append("verification_target is required")
    else:
        normalized["verification_target"] = verification_target

    lane = str(packet.get("lane") or "").strip().lower()
    if lane not in LANES:
        errors.append(f"lane must be one of: {sorted(LANES)}")
    else:
        normalized["lane"] = lane

    packet_id = str(packet.get("packet_id") or "").strip()
    normalized["packet_id"] = packet_id or f"packet-{int(datetime.now(timezone.utc).timestamp())}"

    return {"ok": not errors, "errors": errors, "normalized": normalized}


def lane_resolution_policy(
    packet: dict[str, Any],
    *,
    confidence: float,
    visibility: str,
    local_ai_authority: bool = True,
) -> dict[str, Any]:
    """Return deterministic auto-resolve vs owner-review behavior by lane + confidence."""
    lane = str(packet.get("lane") or "").strip().lower()
    confidence = max(0.0, min(1.0, confidence))
    visibility_mode = str(visibility or "unknown").strip().lower()

    approval_required = lane in {"creative", "output"}
    auto_resolve = lane == "engineering" and confidence >= 0.70 and visibility_mode == "full"

    fallback_reason = None
    if not local_ai_authority:
        fallback_reason = "local_ai_authority_disabled"
        auto_resolve = False
    elif lane != "engineering":
        fallback_reason = "lane_requires_owner_approval"
        auto_resolve = False
    elif confidence < 0.70:
        fallback_reason = "low_confidence"
        auto_resolve = False
    elif visibility_mode != "full":
        fallback_reason = "limited_visibility"
        auto_resolve = False

    return {
        "lane": lane,
        "confidence": confidence,
        "visibility": visibility_mode,
        "local_ai_authority": bool(local_ai_authority),
        "approval_required": approval_required,
        "auto_resolve": auto_resolve,
        "decision": "auto-resolve" if auto_resolve else "owner-review",
        "fallback_reason": fallback_reason,
    }


def build_handoff_record(
    *,
    task_packet: dict[str, Any],
    context_in: dict[str, Any],
    decision_request: dict[str, Any],
    execution_result: dict[str, Any],
    verification_result: dict[str, Any],
    next_action: dict[str, Any],
) -> dict[str, Any]:
    """Build one standard handoff record for each task cycle."""
    return {
        "ts": _iso_now(),
        "packet_id": task_packet.get("packet_id"),
        "lane": task_packet.get("lane"),
        "context_in": context_in,
        "decision_request": decision_request,
        "execution_result": execution_result,
        "verification_result": verification_result,
        "next_action": next_action,
    }


def append_jsonl(path: str | Path, entry: dict[str, Any]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")


def record_refinement_entry(
    path: str | Path,
    *,
    packet_id: str,
    friction: list[str],
    missing_context: list[str],
    promote_to_memory: list[str],
    tuning_actions: list[str],
) -> dict[str, Any]:
    """Record post-task refinement signals for future prompt/routing updates."""
    entry = {
        "ts": _iso_now(),
        "packet_id": packet_id,
        "friction": friction,
        "missing_context": missing_context,
        "promote_to_memory": promote_to_memory,
        "tuning_actions": tuning_actions,
    }
    append_jsonl(path, entry)
    return entry


def scorecard_from_cycles(cycles: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute collaboration efficiency metrics from handoff cycles."""
    total = len(cycles)
    if total == 0:
        return {
            "tasks_total": 0,
            "rework_count": 0,
            "clarification_count": 0,
            "avg_turnaround_seconds": 0.0,
            "approval_pass_rate": 0.0,
        }

    rework_count = 0
    clarification_count = 0
    turnaround_samples: list[float] = []
    approvals_total = 0
    approvals_passed = 0

    for cycle in cycles:
        execution = cycle.get("execution_result") or {}
        decision_request = cycle.get("decision_request") or {}
        verification = cycle.get("verification_result") or {}
        lane = str(cycle.get("lane") or "").lower()

        outcome = str(execution.get("outcome") or "").lower()
        if outcome in {"rework", "retry_required", "failed"} or bool((cycle.get("next_action") or {}).get("requires_rework")):
            rework_count += 1

        clarification_count += int(decision_request.get("clarification_count") or 0)

        turnaround = _seconds_between(execution.get("started_at"), execution.get("completed_at"))
        if turnaround is not None:
            turnaround_samples.append(turnaround)

        if lane in {"creative", "output"}:
            approvals_total += 1
            if str(verification.get("approval_status") or "").lower() == "approved":
                approvals_passed += 1

    return {
        "tasks_total": total,
        "rework_count": rework_count,
        "clarification_count": clarification_count,
        "avg_turnaround_seconds": round(mean(turnaround_samples), 2) if turnaround_samples else 0.0,
        "approval_pass_rate": round((approvals_passed / approvals_total), 4) if approvals_total else 1.0,
    }


def scorecard_from_jsonl(path: str | Path) -> dict[str, Any]:
    target = Path(path)
    if not target.exists():
        return scorecard_from_cycles([])

    cycles: list[dict[str, Any]] = []
    for line in target.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            cycles.append(payload)

    return scorecard_from_cycles(cycles)
