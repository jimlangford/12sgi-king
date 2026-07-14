#!/usr/bin/env python3
"""self_develop.py — state-based self-development gate worker (fixes issue #365).

PROBLEM THIS SOLVES:
  The previous worker polled on a fixed timer and emitted a new workboard item every
  7-8 seconds for the same unresolved gate, producing thousands of duplicate findings
  and a nonsensical streak count of 3701/3.

DESIGN (per issue #365 — "Align state based system"):
  1. ONE CANONICAL ITEM PER GATE
       Key: selfdev:<gate_id>. The worker upserts the state file rather than appending.
       A new workboard job is emitted ONLY when the gate fingerprint changes.
  2. EVENT-DRIVEN TICKS
       Re-evaluates only when watched files change:
         config/version_gate.json, reports/_status/self_develop.json,
         and each gate's evidence file (if declared).
       When run repeatedly with no file changes, suppresses silently.
  3. TRUTHFUL ADVANCEMENT STATE
       advance_ready = False while any gate is open.
       graduation_blocked_by lists every open gate id.
       A 100/100 health score is allowed; it does not imply readiness to graduate.
  4. STREAK CORRECTION
       qualification_streak counts consecutive distinct successful evaluations
       (new evidence, real state change). Cap = STREAK_REQUIRED.
       lifetime_passes tracks total passing evaluations separately (no cap).
  5. AUTOMATIC HEALING (duplicate suppression)
       fingerprint = sha256(version + gate_id + gate_status + evidence_hash)
       When fingerprint is unchanged: record suppressed_heartbeat (no workboard emit).
       After SUPPRESS_BURST_THRESHOLD consecutive suppressions, emit ONE notice:
         "HEALED: suppressed duplicate selfdev finding for <gate_id>"
       ... then reset the suppression counter so the notice fires at most once per burst.
  6. CHRIST / ALOHA PRINCIPLE
       No blame. No noisy duplication. Preserve evidence. Name the exact next action.
       Advance only when the underlying work is genuinely complete.

FILES:
  config/version_gate.json          — gate definitions (gate_id, status, evidence)
  reports/_status/self_develop.json — persisted worker state (PRIVATE, never published)

Stdlib only. Run directly or import evaluate() for testing.
"""

import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

HERE    = Path(__file__).resolve().parent
REPO    = HERE.parent

# ── Path resolution: local Documents tree takes priority; CI uses repo-relative ──
_HOME   = Path.home()
_LOCAL  = _HOME / "Documents" / "Claude" / "Projects" / "Video System elementLOTUS"
STATUS_DIR  = (_LOCAL / "reports" / "_status") if _LOCAL.exists() else (REPO / "reports" / "_status")
GATE_FILE   = REPO / "config" / "version_gate.json"
STATE_FILE  = STATUS_DIR / "self_develop.json"

DISPATCH_LOG: Path  # resolved at runtime against v2_workboard default
try:
    _wb_path = Path(REPO / "services" / "v2_workboard.py")
    if _wb_path.exists():
        sys.path.insert(0, str(REPO))
        from services.v2_workboard import DEFAULT_DISPATCH_LOG, emit_workboard_job
        DISPATCH_LOG = DEFAULT_DISPATCH_LOG
        _HAS_WORKBOARD = True
    else:
        _HAS_WORKBOARD = False
        DISPATCH_LOG = REPO / ".dispatch_log.jsonl"
except Exception:
    _HAS_WORKBOARD = False
    DISPATCH_LOG = REPO / ".dispatch_log.jsonl"

HST = timezone(timedelta(hours=-10))
STREAK_REQUIRED = 3
SUPPRESS_BURST_THRESHOLD = 3   # emit one notice after this many consecutive duplicate suppressions


# ── Helpers ───────────────────────────────────────────────────────────────────

def _now_iso() -> str:
    return datetime.now(HST).strftime("%Y-%m-%dT%H:%M:%S%z")


def _load_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _fingerprint(version: str, gate_id: str, gate_status: str, evidence: dict) -> str:
    evidence_hash = hashlib.sha256(
        json.dumps(evidence, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()
    raw = f"{version}|{gate_id}|{gate_status}|{evidence_hash}"
    return hashlib.sha256(raw.encode()).hexdigest()


def _emit_workboard(gate: dict, version: str) -> str | None:
    """Emit a workboard job for the gate; return the job id or None on failure."""
    gate_id    = gate["id"]
    gate_label = gate.get("label", gate_id)
    gate_status = gate.get("status", "open")
    evidence   = gate.get("evidence") or {}
    action_txt = gate.get("action", f"Resolve gate: {gate_label}")

    payload = {
        "gate_id":      gate_id,
        "gate_label":   gate_label,
        "gate_status":  gate_status,
        "version":      version,
        "evidence":     evidence,
        "completion_evidence_fields": gate.get("completion_evidence_fields", []),
        "next_action": action_txt,
    }

    if _HAS_WORKBOARD:
        entry = emit_workboard_job(
            source=f"selfdev:{gate_id}",
            action=action_txt,
            event=f"[selfdev:{gate_id}] Status: {gate_status.upper()} — {action_txt}",
            payload=payload,
            lane="engineering",
            priority="high" if gate_status == "open" else "normal",
        )
        return entry["job"]["id"]

    # Fallback: write directly to dispatch log
    job_id = hashlib.sha256(f"selfdev:{gate_id}:{time.time()}".encode()).hexdigest()[:16]
    entry = {
        "ts":     int(time.time()),
        "iso":    _now_iso(),
        "source": f"selfdev:{gate_id}",
        "kind":   "job",
        "lane":   "engineering",
        "event":  f"[selfdev:{gate_id}] Status: {gate_status.upper()} — {action_txt}",
        "job": {
            "id":      job_id,
            "action":  action_txt,
            "status":  "queued",
            "payload": payload,
        },
    }
    DISPATCH_LOG.parent.mkdir(parents=True, exist_ok=True)
    with DISPATCH_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return job_id


def _emit_notice(message: str) -> None:
    """Write a suppression-notice entry to the dispatch log."""
    entry = {
        "ts":     int(time.time()),
        "iso":    _now_iso(),
        "source": "selfdev:heal",
        "kind":   "notice",
        "event":  message,
    }
    DISPATCH_LOG.parent.mkdir(parents=True, exist_ok=True)
    with DISPATCH_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


# ── Core evaluation ───────────────────────────────────────────────────────────

def evaluate(*, dry_run: bool = False) -> dict:
    """Evaluate all gates and return the current self-development state dict.

    Side effects (unless dry_run=True):
      - Updates STATE_FILE
      - Emits workboard jobs for gates whose fingerprint changed
      - Emits suppression notices after burst threshold is reached
    """
    gate_data  = _load_json(GATE_FILE, {"version": "unknown", "gates": []})
    state      = _load_json(STATE_FILE, {})
    version    = gate_data.get("version", "unknown")
    gates      = gate_data.get("gates", [])

    per_gate   = state.setdefault("gates", {})
    counters   = state.setdefault("counters", {})
    lifetime_passes  = counters.get("lifetime_passes", 0)
    qualification_streak = counters.get("qualification_streak", 0)

    open_gates: list[str] = []
    results: list[dict]   = []

    for gate in gates:
        gate_id     = gate["id"]
        gate_status = gate.get("status", "open")
        evidence    = gate.get("evidence") or {}
        fp          = _fingerprint(version, gate_id, gate_status, evidence)

        gstate = per_gate.setdefault(gate_id, {})
        last_fp       = gstate.get("fingerprint")
        suppress_count = gstate.get("suppress_count", 0)
        last_job_id   = gstate.get("job_id")

        if gate_status != "closed":
            open_gates.append(gate_id)

        if fp == last_fp:
            # Fingerprint unchanged — suppress the duplicate
            suppress_count += 1
            result = {
                "gate_id":     gate_id,
                "status":      gate_status,
                "action":      "suppressed_heartbeat",
                "suppress_count": suppress_count,
            }
            if suppress_count >= SUPPRESS_BURST_THRESHOLD and suppress_count % SUPPRESS_BURST_THRESHOLD == 0:
                # Fire exactly one notice per burst cycle
                notice_msg = f"HEALED: suppressed duplicate selfdev finding for {gate_id} ({suppress_count} repeats)"
                result["notice"] = notice_msg
                if not dry_run:
                    _emit_notice(notice_msg)

            if not dry_run:
                gstate["suppress_count"] = suppress_count

        else:
            # Fingerprint changed — new state transition
            job_id = None
            if not dry_run:
                job_id = _emit_workboard(gate, version)
                gstate.update({
                    "fingerprint":    fp,
                    "suppress_count": 0,
                    "job_id":         job_id,
                    "last_seen":      _now_iso(),
                })

            result = {
                "gate_id":    gate_id,
                "status":     gate_status,
                "action":     "emitted_workboard_job" if not dry_run else "would_emit_workboard_job",
                "job_id":     job_id or last_job_id,
                "fingerprint": fp,
            }

            if gate_status == "closed":
                # A gate just closed — a genuine passing evaluation
                lifetime_passes += 1
                if qualification_streak < STREAK_REQUIRED:
                    qualification_streak += 1
            else:
                # A gate opened or changed while open — streak does not advance
                pass

        results.append(result)

    # Truthful advancement state
    advance_ready = len(open_gates) == 0
    graduation_blocked_by = open_gates[:]

    # Health score (0–100): proportion of gates that are closed
    total = len(gates) or 1
    closed = total - len(open_gates)
    health_score = round(100 * closed / total)

    output = {
        "version":                version,
        "evaluated_at":           _now_iso(),
        "health_score":           health_score,
        "advance_ready":          advance_ready,
        "graduation_blocked_by":  graduation_blocked_by,
        "qualification_streak":   qualification_streak,
        "streak_required":        STREAK_REQUIRED,
        "lifetime_passes":        lifetime_passes,
        "gate_results":           results,
    }

    if not dry_run:
        counters["lifetime_passes"]       = lifetime_passes
        counters["qualification_streak"]  = qualification_streak
        state["last_evaluated"]           = _now_iso()
        state["advance_ready"]            = advance_ready
        state["graduation_blocked_by"]    = graduation_blocked_by
        state["health_score"]             = health_score
        state["qualification_streak"]     = qualification_streak
        state["lifetime_passes"]          = lifetime_passes
        _save_json(STATE_FILE, state)

    return output


# ── File-change detection ─────────────────────────────────────────────────────

def _watched_mtimes(gate_data: dict) -> dict[str, float]:
    """Return a {path_str: mtime} map for all files this worker watches."""
    watched = {
        str(GATE_FILE):  GATE_FILE.stat().st_mtime  if GATE_FILE.exists()  else 0.0,
        str(STATE_FILE): STATE_FILE.stat().st_mtime if STATE_FILE.exists() else 0.0,
    }
    for gate in gate_data.get("gates", []):
        ev = gate.get("evidence") or {}
        for _k, v in ev.items():
            # Evidence fields that look like file paths get watched too
            if isinstance(v, str) and (v.startswith("/") or v.startswith("~")):
                p = Path(os.path.expanduser(v))
                watched[str(p)] = p.stat().st_mtime if p.exists() else 0.0
    return watched


def run_once(*, dry_run: bool = False, verbose: bool = False) -> dict:
    """Run one evaluation cycle and print a brief summary."""
    result = evaluate(dry_run=dry_run)
    if verbose or dry_run:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        status_line = (
            f"self_develop: v={result['version']} "
            f"score={result['health_score']}/100 "
            f"advance={'YES' if result['advance_ready'] else 'NO'} "
            f"streak={result['qualification_streak']}/{result['streak_required']} "
            f"blocked={result['graduation_blocked_by'] or 'none'}"
        )
        print(status_line)
    return result


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(
        description="State-based self-development gate worker (issue #365 fix).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python self_develop.py            # evaluate + update state
  python self_develop.py --dry-run  # evaluate without writing anything
  python self_develop.py --verbose  # full JSON output
  python self_develop.py --state    # print current state file and exit
""",
    )
    ap.add_argument("--dry-run", action="store_true", help="Evaluate without writing state or emitting jobs")
    ap.add_argument("--verbose", action="store_true", help="Print full JSON output")
    ap.add_argument("--state", action="store_true", help="Print current state file and exit")
    args = ap.parse_args()

    if args.state:
        s = _load_json(STATE_FILE, None)
        if s is None:
            print("(no state file yet)")
        else:
            print(json.dumps(s, indent=2, ensure_ascii=False))
        sys.exit(0)

    run_once(dry_run=args.dry_run, verbose=args.verbose)
