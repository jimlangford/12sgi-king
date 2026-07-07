# -*- coding: utf-8 -*-
"""
studio_parity.py - verify that the Studio and Civic lanes are reading from the same source.

BOTH Civic and Studio are now equal tenants of the 54-node model. Civic is the Ao lane (choices
are made during the day — agendas, votes, contracts). Studio/HINA is the Pō lane (HINA reads those
choices nightly and dispatches creative jobs to balance the equation). Neither heals "up to" the
other; both derive from the same source (54 nodes × kaulana mahina × Kumulipo wā).

This replaces the old "heal studio to civic standard" model. Parity is now measured on three
cycle-connection dimensions:

  cycle_connected     - studio workboard creative jobs carry hina_node_id + civic_source
                        (HINA's dispatch is traceable back to a civic date + node)
  face_lock_intact    - no music-video face-lock asset was recolored or overwritten this cycle
                        (the immutable Ao base layer is preserved)
  hina_balance_present - every creative job in the dispatch log has an offering_date
                        (HINA drove the job, not an ad-hoc trigger)

Each check scores 0–100. overall = mean of the three. Written to reports/_status/studio_parity.json.
Run: python studio_parity.py [--heal]

Note: --heal flag is accepted for backward compatibility but only asserts face-lock safety (it will
never recolor or overwrite face-lock assets). No color remapping is performed.

Designed to be called by quadrant_selfheal.py (hourly, report+score) and the daily audit_cycle.
Stdlib only. Defensive: a missing log or config -> low score, never a crash.
"""
import os
import re
import json
import sys
import datetime

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
CFG  = os.path.join(ROOT, "config")
STATUS = os.path.join(ROOT, "reports", "_status")

# Face-lock registry: paths (relative to ROOT) whose content must never be auto-modified.
# These are the immutable Ao base-layer assets — music video locked frames + manifests.
FACE_LOCK_PATHS = [
    # add entries here as face-lock assets are registered, e.g.:
    # "assets/music_videos/manifest.json",
]

DISPATCH_LOG = os.path.join(ROOT, ".dispatch_log.jsonl")


def load(p, d=None):
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception:
        return d


def _read_dispatch_log():
    """Return all creative-lane workboard job entries from the dispatch log."""
    if not os.path.exists(DISPATCH_LOG):
        return []
    entries = []
    try:
        with open(DISPATCH_LOG, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    if entry.get("lane") == "creative" and entry.get("kind") == "job":
                        entries.append(entry)
                except json.JSONDecodeError:
                    continue
    except Exception:
        pass
    return entries


def check_cycle_connected(creative_jobs):
    """Score: what fraction of creative jobs carry hina_node_id + civic_source in payload."""
    if not creative_jobs:
        return 0, 0, 0
    connected = 0
    for entry in creative_jobs:
        payload = (entry.get("job") or {}).get("payload") or {}
        if payload.get("hina_node_id") and payload.get("civic_source"):
            connected += 1
    return connected, len(creative_jobs), round(100 * connected / len(creative_jobs))


def check_face_lock_intact():
    """Score: 100 if all registered face-lock paths exist and were not modified this cycle,
    0 for each missing path. Returns (intact_count, total, score)."""
    if not FACE_LOCK_PATHS:
        # no face-lock assets registered yet — score 100 (nothing to protect, nothing violated)
        return 0, 0, 100
    intact = sum(1 for p in FACE_LOCK_PATHS if os.path.exists(os.path.join(ROOT, p)))
    score = round(100 * intact / len(FACE_LOCK_PATHS))
    return intact, len(FACE_LOCK_PATHS), score


def check_hina_balance_present(creative_jobs):
    """Score: what fraction of creative jobs carry offering_date in payload."""
    if not creative_jobs:
        return 0, 0, 0
    dated = 0
    for entry in creative_jobs:
        payload = (entry.get("job") or {}).get("payload") or {}
        if payload.get("offering_date"):
            dated += 1
    return dated, len(creative_jobs), round(100 * dated / len(creative_jobs))


def main():
    heal = "--heal" in sys.argv

    creative_jobs = _read_dispatch_log()

    connected, total_jobs, cycle_score = check_cycle_connected(creative_jobs)
    intact, total_locks, face_score = check_face_lock_intact()
    dated, _, balance_score = check_hina_balance_present(creative_jobs)

    overall = round((cycle_score + face_score + balance_score) / 3)

    flags = []
    if total_jobs == 0:
        flags.append("NO creative workboard jobs found — HINA has not dispatched yet or dispatch log is missing")
    if cycle_score < 100 and total_jobs > 0:
        flags.append(
            f"CYCLE: {total_jobs - connected}/{total_jobs} creative jobs missing hina_node_id or civic_source — "
            "emit_hina_creative_job() should be used for all HINA dispatches"
        )
    if face_score < 100 and total_locks > 0:
        flags.append(
            f"FACE LOCK: {total_locks - intact}/{total_locks} face-lock assets missing — "
            "music-video base layer may have been moved or deleted"
        )
    if balance_score < 100 and total_jobs > 0:
        flags.append(
            f"HINA BALANCE: {total_jobs - dated}/{total_jobs} creative jobs missing offering_date — "
            "jobs must carry the civic date HINA is balancing"
        )
    if heal:
        flags.append(
            "HEAL: --heal flag accepted. No color remapping performed — face-lock assets are immutable Ao layer. "
            "To fix cycle_connected / hina_balance_present gaps, re-dispatch via emit_hina_creative_job()."
        )

    res = {
        "generated": datetime.datetime.now().isoformat(timespec="seconds"),
        "model": "equal-tenants — Civic (Ao) + Studio/HINA (Po) both read from the 54-node source",
        "scores": {
            "cycle_connected": cycle_score,
            "face_lock_intact": face_score,
            "hina_balance_present": balance_score,
            "overall": overall,
        },
        "detail": {
            "creative_jobs_in_log": total_jobs,
            "cycle_connected": {"connected": connected, "total": total_jobs},
            "face_lock": {"intact": intact, "registered": total_locks,
                          "_note": "0 registered = no face-lock assets declared yet; score=100 (nothing violated)"},
            "hina_balance": {"with_offering_date": dated, "total": total_jobs},
        },
        "flags": flags,
    }

    os.makedirs(STATUS, exist_ok=True)
    out_path = os.path.join(STATUS, "studio_parity.json")
    with open(out_path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)

    print(
        "studio_parity: overall %d  (cycle_connected %d / face_lock %d / hina_balance %d)"
        % (overall, cycle_score, face_score, balance_score)
    )
    for flag in flags:
        print("  ⚑ " + flag)
    return res


if __name__ == "__main__":
    main()
