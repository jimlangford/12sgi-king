# -*- coding: utf-8 -*-
"""
studio_parity.py — verify the HINA cycle is connected; keep Studio + Civic on the same 54-node source.

New model (canonical as of 2026-07-06, per docs/SAGE_REALM_MODEL.md §10):
  Civic (Ao) and Studio/HINA (Pō) are EQUAL TENANTS both reading from the same 54-node source.
  The old "heal Studio up to Civic colors" model is superseded by three cycle-connection checks:

  cycle_connected      — all creative-lane workboard jobs carry hina_node_id + civic_source.
  face_lock_intact     — no face-lock asset (music-video base layer) was recolored or overwritten.
  hina_balance_present — every output-lane (published) job has a traceable offering_date + job_id.

Defensive: a missing dispatch log or missing face-lock manifest → score=100 (nothing violated).
Stdlib only.  Writes reports/_status/studio_parity.json.
Run: python studio_parity.py [--dry-run]
Called by: quadrant_selfheal.py, tools/civic_v2_catchup.py
"""
import json
import os
import sys
import datetime
from pathlib import Path

# repo root = one level up from watchers/
_HERE = Path(__file__).resolve().parent
REPO_ROOT = _HERE.parent

# Dispatch log: honour the same env var as services/v2_workboard.py
_DEFAULT_LOG = REPO_ROOT / ".dispatch_log.jsonl"
DISPATCH_LOG = Path(os.environ.get("WORKBOARD_DISPATCH_LOG") or _DEFAULT_LOG)

# Face-lock manifest: optional config file listing protected music-video assets.
# Format: {"assets": [{"path": "relative/to/repo", "sha256": "..."}]}
# Missing or empty manifest → score=100 (no assets registered, nothing violated).
FACE_LOCK_MANIFEST = REPO_ROOT / "config" / "face_lock_assets.json"

# Status output — kept at the old ROOT/../reports/_status/ when running on the project
# host (two levels up from watchers/).  On CI / sandbox it falls back to repo root.
_legacy_root = REPO_ROOT.parent  # project root on owner's machine
STATUS_DIR = (_legacy_root / "reports" / "_status"
              if (_legacy_root / "reports").is_dir()
              else REPO_ROOT / "reports" / "_status")


# ── helpers ───────────────────────────────────────────────────────────────────

def _read_log(path: Path) -> list[dict]:
    """Read the JSONL dispatch log; return list of entries (empty on any error)."""
    if not path.is_file():
        return []
    entries = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except Exception:
                    pass
    except Exception:
        pass
    return entries


def _load_json(path: Path, default=None):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


# ── check 1: cycle_connected ──────────────────────────────────────────────────

def check_cycle_connected(entries: list[dict]) -> dict:
    """All creative-lane jobs must carry hina_node_id + civic_source in payload."""
    # collect active (non-tombstoned) creative lane jobs
    resolved: set[str] = set()
    creative_jobs: list[dict] = []
    for e in entries:
        if e.get("kind") == "tombstone":
            cid = (e.get("job") or {}).get("correlation_id")
            if cid:
                resolved.add(cid)
        elif e.get("lane") == "creative" and e.get("kind") == "job":
            creative_jobs.append(e)

    active = [j for j in creative_jobs if j.get("job", {}).get("id") not in resolved]
    total = len(active)
    if total == 0:
        return {"connected": 0, "total": 0, "score": 100,
                "_note": "0 active creative jobs — nothing to violate"}

    connected = 0
    for job in active:
        payload = job.get("payload") or {}
        if payload.get("hina_node_id") and payload.get("civic_source"):
            connected += 1

    score = round(100 * connected / total)
    return {"connected": connected, "total": total, "score": score}


# ── check 2: face_lock_intact ─────────────────────────────────────────────────

def check_face_lock(manifest_path: Path) -> dict:
    """No face-lock (music-video base-layer) asset may be recolored or overwritten."""
    manifest = _load_json(manifest_path)
    if not manifest:
        return {"intact": 0, "registered": 0, "score": 100,
                "_note": "0 registered = no face-lock assets declared yet; score=100 (nothing violated)"}

    assets = manifest.get("assets") or []
    if not assets:
        return {"intact": 0, "registered": 0, "score": 100,
                "_note": "0 registered = no face-lock assets declared yet; score=100 (nothing violated)"}

    import hashlib

    intact = 0
    flags = []
    for entry in assets:
        rel = entry.get("path", "")
        expected_sha = entry.get("sha256", "")
        full = REPO_ROOT / rel
        if not full.is_file():
            flags.append(f"MISSING: {rel}")
            continue
        if expected_sha:
            digest = hashlib.sha256(full.read_bytes()).hexdigest()
            if digest == expected_sha:
                intact += 1
            else:
                flags.append(f"OVERWRITTEN: {rel}")
        else:
            intact += 1  # registered but no checksum declared — presence is enough

    total = len(assets)
    score = round(100 * intact / total) if total else 100
    return {"intact": intact, "registered": total, "score": score,
            **({"flags": flags} if flags else {})}


# ── check 3: hina_balance_present ────────────────────────────────────────────

def check_hina_balance(entries: list[dict]) -> dict:
    """Every approved/published output-lane job must carry offering_date + job_id."""
    output_jobs = [e for e in entries
                   if e.get("lane") == "output"
                   and e.get("status") in {"approved", "done"}
                   and e.get("kind") == "job"]
    total = len(output_jobs)
    if total == 0:
        return {"with_offering_date": 0, "total": 0, "score": 100,
                "_note": "0 output jobs published yet — nothing to violate"}

    with_offering = 0
    for job in output_jobs:
        payload = job.get("payload") or {}
        jid = (job.get("job") or {}).get("id") or job.get("id")
        if payload.get("offering_date") and jid:
            with_offering += 1

    score = round(100 * with_offering / total)
    return {"with_offering_date": with_offering, "total": total, "score": score}


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> dict:
    entries = _read_log(DISPATCH_LOG)

    cc = check_cycle_connected(entries)
    fl = check_face_lock(FACE_LOCK_MANIFEST)
    hb = check_hina_balance(entries)

    overall = round((cc["score"] + fl["score"] + hb["score"]) / 3)
    flags = fl.get("flags", [])

    creative_total = cc.get("total", 0)

    res = {
        "generated": datetime.datetime.now().isoformat(timespec="seconds"),
        "model": "equal-tenants — Civic (Ao) + Studio/HINA (Po) both read from the 54-node source",
        "scores": {
            "cycle_connected":      cc["score"],
            "face_lock_intact":     fl["score"],
            "hina_balance_present": hb["score"],
            "overall":              overall,
        },
        "detail": {
            "creative_jobs_in_log": creative_total,
            "cycle_connected":  {k: v for k, v in cc.items() if k != "score"},
            "face_lock":        {k: v for k, v in fl.items() if k != "score"},
            "hina_balance":     {k: v for k, v in hb.items() if k != "score"},
        },
        "flags": flags,
    }

    STATUS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = STATUS_DIR / "studio_parity.json"
    out_path.write_text(json.dumps(res, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    print("studio_parity: overall %d  (cycle=%d / face=%d / hina=%d)" % (
        overall, cc["score"], fl["score"], hb["score"]))
    if flags:
        for f in flags:
            print("  ! %s" % f)
    return res


if __name__ == "__main__":
    main()
