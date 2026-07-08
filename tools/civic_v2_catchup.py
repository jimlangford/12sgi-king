#!/usr/bin/env python3
"""civic_v2_catchup.py — wire the Studio civic tenant into v2 and catch up the workboard.

Bridges the local civic record (Maui minutes, agenda snapshots, n53 corpus) into the
v2 workboard dispatch log so that studio_parity.py can verify the HINA cycle is connected.

Emits two classes of jobs:

  HINA creative jobs (via emit_hina_creative_job):
    One per confirmed Maui County Council full-council meeting found in minutes_text/hi-maui/.
    Each job carries hina_node_id + civic_source + offering_date so studio_parity passes all
    three checks (cycle_connected / hina_balance_present / face_lock_intact).

  Engineering ingest jobs (via emit_workboard_job):
    maui-minutes-backfill   — signals council_watch --backfill for the gap period
    agenda-refresh          — one per tenant whose upcoming snapshot is stale
    n53-corpus-sync         — refresh n53 corpus with newly captured meetings
    sage-bridge-refresh     — recompute sage_bridge.json with today's data

Usage:
    python tools/civic_v2_catchup.py [--dry-run]

    # against the v2 Docker dispatch volume:
    WORKBOARD_DISPATCH_LOG=/data/dispatch/govos_v2_dispatch.jsonl python tools/civic_v2_catchup.py

Stdlib only (+ services.v2_workboard + watchers.moon_calendar from repo).
"""
import json
import os
import re
import sys
from datetime import date, timedelta
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from services.v2_workboard import emit_hina_creative_job, emit_workboard_job

try:
    from watchers.moon_calendar import reading as moon_reading
except ImportError:
    moon_reading = None

# ── constants ─────────────────────────────────────────────────────────────────

MINUTES_DIR = _REPO / "minutes_text" / "hi-maui"
AGENDA_SRC  = _REPO / "watchers" / "agenda_sources.json"
TODAY       = date.today()

# 54-node cycle anchor: June 15, 2026 = node 21 (from seed_reports/mauios/sage_bridge.json)
_ANCHOR_DATE = date(2026, 6, 15)
_ANCHOR_NODE = 21

# node metadata from the sage_bridge seed (54 nodes)
_SAGE_BRIDGE_SEED = _REPO / "seed_reports" / "mauios" / "sage_bridge.json"


def _load_node_map():
    """Return {node_id: {name, akua, wa_phase, particles}} from sage_bridge seed."""
    try:
        data = json.loads(_SAGE_BRIDGE_SEED.read_text(encoding="utf-8"))
        return {n["node"]: n for n in data.get("nodes", [])}
    except Exception:
        return {}


def _node_for_date(d: date) -> int:
    """54-node cycle: which node is active on date d (anchored to June 15 = node 21)."""
    delta = (d - _ANCHOR_DATE).days
    return (((_ANCHOR_NODE - 1) + delta) % 54) + 1


def _po_for_date(d: date) -> str:
    """Return the Hawaiian pō night name for a date (best-effort; empty string on failure)."""
    if moon_reading:
        try:
            r = moon_reading(d.isoformat())
            return r.get("po", "") if r else ""
        except Exception:
            pass
    return ""


# ── civic meeting discovery ────────────────────────────────────────────────────

def _maui_regular_council_meetings() -> list[tuple[date, str]]:
    """Return [(meeting_date, fileId)] for all confirmed Maui full-council meetings."""
    if not MINUTES_DIR.exists():
        return []
    results = []
    for f in sorted(MINUTES_DIR.iterdir()):
        m = re.match(r"(\d{4}-\d{2}-\d{2})__cc(\d+)\.txt", f.name)
        if not m:
            continue
        try:
            head = f.read_text(encoding="utf-8", errors="replace")[:400]
        except Exception:
            continue
        # Match the header tag AND the minutes body text to confirm full council meeting
        if "County Council Meeting" in head or "REGULAR COUNCIL MEETING" in head:
            results.append((date.fromisoformat(m.group(1)), m.group(2)))
    return results


def _stale_tenants() -> list[str]:
    """Return tenant IDs whose upcoming snapshot contains dates already in the past."""
    try:
        data = json.loads(AGENDA_SRC.read_text(encoding="utf-8"))
    except Exception:
        return []
    stale = []
    for s in data.get("sources", []):
        for m in s.get("upcoming", []):
            d = m.get("date", "")
            if d and d < TODAY.isoformat():
                stale.append(s["tenant_id"])
                break
    return stale


# ── emit functions ─────────────────────────────────────────────────────────────

def emit_hina_jobs(meetings: list[tuple[date, str]], nodes: dict, dry_run: bool) -> int:
    """Emit one HINA creative job per confirmed Maui council meeting."""
    emitted = 0
    for mtg_date, file_id in meetings:
        node_id  = _node_for_date(mtg_date)
        node_rec = nodes.get(node_id, {})
        akua     = node_rec.get("akua", "Kāne")
        wa_phase = node_rec.get("phase", "Ao")
        particles = node_rec.get("particles") or (
            f"node {node_id} energy — {node_rec.get('name', 'civic balance')}"
        )
        po_name  = _po_for_date(mtg_date)
        civic_src = (
            f"maui-council/{mtg_date.isoformat()}/regular-council-meeting/fileId={file_id}"
        )
        print(
            f"  [HINA] {mtg_date} → node {node_id} {node_rec.get('name','?')} "
            f"({akua}, {wa_phase}) civic_src={civic_src}"
        )
        if not dry_run:
            emit_hina_creative_job(
                offering_date=mtg_date.isoformat(),
                hina_node_id=node_id,
                akua=akua,
                wa_phase=wa_phase,
                particles=particles,
                civic_source=civic_src,
                output_types=["cut-scene", "card-render"],
                source="civic-v2-catchup",
            )
        emitted += 1
    return emitted


def emit_engineering_jobs(stale_tenants: list[str], last_minutes: date, dry_run: bool) -> int:
    """Emit engineering-lane ingest/refresh jobs."""
    emitted = 0
    backfill_start = (last_minutes + timedelta(days=1)).isoformat()
    backfill_end   = TODAY.isoformat()

    jobs = [
        {
            "action": "maui-minutes-backfill",
            "event":  f"Maui minutes backfill {backfill_start} → {backfill_end}",
            "payload": {
                "tenant": "hi-maui",
                "start": backfill_start,
                "end":   backfill_end,
                "tool":  "council_watch --backfill",
                "source_api": "https://mauicounty.api.civicclerk.com/v1",
            },
        },
        {
            "action": "n53-corpus-sync",
            "event":  "N53 corpus sync after minutes backfill",
            "payload": {
                "tenant": "hi-maui",
                "tool":   "n53_ingest",
                "votes_index": "reports/mauios/votes_index.jsonl",
            },
        },
        {
            "action": "sage-bridge-refresh",
            "event":  f"Sage bridge refresh for {TODAY.isoformat()}",
            "payload": {
                "date": TODAY.isoformat(),
                "tool": "sage_bridge",
                "output": "reports/mauios/sage_bridge.json",
            },
        },
    ]

    for tid in stale_tenants:
        jobs.append({
            "action": "agenda-refresh",
            "event":  f"Agenda live-refresh: {tid}",
            "payload": {
                "tenant": tid,
                "tool":   "agenda_watch",
                "feed_url": f"agenda_sources[{tid}].feed_url",
            },
        })

    for j in jobs:
        print(f"  [ENG]  {j['action']} — {j['event']}")
        if not dry_run:
            emit_workboard_job(
                source="civic-v2-catchup",
                action=j["action"],
                event=j["event"],
                lane="engineering",
                status="queued",
                payload=j["payload"],
            )
        emitted += 1

    return emitted


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    dry_run = "--dry-run" in sys.argv
    log_path = os.environ.get("WORKBOARD_DISPATCH_LOG", "")
    if log_path:
        log_hint = f"→ {log_path}"
    else:
        log_hint = "→ repo default (.dispatch_log.jsonl)"

    print(f"civic-v2-catchup  {'[DRY RUN] ' if dry_run else ''}today={TODAY}  dispatch {log_hint}")
    print()

    nodes    = _load_node_map()
    meetings = _maui_regular_council_meetings()
    stale    = _stale_tenants()

    if not meetings:
        print("  ! No confirmed Maui regular council meetings found in minutes_text/hi-maui/")
        last_minutes = date(2026, 5, 15)  # known last capture
    else:
        last_minutes = max(m[0] for m in meetings)
        print(f"  Maui regular council meetings confirmed: {len(meetings)}")
        print(f"  Last captured: {last_minutes}")

    print(f"  Stale agenda tenants: {len(stale)} ({', '.join(stale) if stale else 'none'})")
    print()

    # 1. HINA creative jobs — one per confirmed council meeting
    print("── HINA creative jobs ──")
    hina_n = emit_hina_jobs(meetings, nodes, dry_run)
    print(f"  {hina_n} HINA job(s) {'would be ' if dry_run else ''}emitted")
    print()

    # 2. Engineering ingest jobs
    print("── Engineering ingest jobs ──")
    eng_n = emit_engineering_jobs(stale, last_minutes, dry_run)
    print(f"  {eng_n} engineering job(s) {'would be ' if dry_run else ''}emitted")
    print()

    if not dry_run:
        # Run studio_parity immediately so the result is visible
        try:
            sys.path.insert(0, str(_REPO / "watchers"))
            import importlib
            sp = importlib.import_module("watchers.studio_parity")
            res = sp.main()
            scores = res.get("scores", {})
            print(
                f"studio_parity after catchup: overall {scores.get('overall',0)}  "
                f"(cycle={scores.get('cycle_connected',0)} / "
                f"face={scores.get('face_lock_intact',0)} / "
                f"hina={scores.get('hina_balance_present',0)})"
            )
        except Exception as e:
            print(f"  (studio_parity check skipped: {e})")

    print()
    print("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
