#!/usr/bin/env python3
# hands_statewide.py - Kilo Aupuni "LEARN ALL CONTRACTS" retainer.
#   hands_awards.py fetches all ~10,609 HANDS award notices but RETAINS only the Maui
#   subset. This module reuses that same fetch and RETAINS THE FULL SET, classified by
#   tenant (Maui / State of Hawaii / other county), so the audit can reach "all
#   contracts learned". Focus tenants for the elections audit = Maui + State of Hawaii.
#
# Output: reports/mauios/hands_statewide_awards.json
#   {learned_total, statewide_total, by_tenant{counts,$}, maui_vendors, state_vendors}
# Integrity: 100% public Notice-of-Award records; a contract is a fact, not an accusation.
# Stdlib only (via hands_awards). Windowless.
import json, os, sys, time
from datetime import datetime, timedelta, timezone

TOOL_DIR = os.path.dirname(os.path.abspath(__file__))
HOME     = os.path.expanduser("~")
PROJECT  = os.path.join(HOME, "Documents", "Claude", "Projects", "Video System elementLOTUS")
OUT_JSON = os.path.join(PROJECT, "reports", "mauios", "hands_statewide_awards.json")
DISPATCH = os.path.join(PROJECT, ".dispatch_log.jsonl")
HST      = timezone(timedelta(hours=-10))
if TOOL_DIR not in sys.path:
    sys.path.insert(0, TOOL_DIR)

def now_hst(): return datetime.now(HST)

def dispatch(tag, msg):
    try:
        with open(DISPATCH, "a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": int(time.time()),
                "iso": now_hst().strftime("%Y-%m-%d %H:%M:%S"),
                "source": "kilo-aupuni", "event": f"{tag}: {msg}"}, ensure_ascii=False) + "\n")
    except Exception: pass

OTHER_COUNTY = ("honolulu", "kaua", "county of hawai", "hawaii county", "kalawao", "kalaupapa")

def classify(r, is_maui):
    j = (r.get("jurisdiction") or "").lower(); d = (r.get("department") or "").lower()
    txt = j + " " + d
    if is_maui(r): return "maui"
    if any(k in txt for k in OTHER_COUNTY): return "other_county"
    return "state_hawaii"        # residual = State of Hawaii agencies (the focus tenant)

def rollup(rows, money):
    v = {}
    for r in rows:
        name = (r.get("vendorName") or "").strip()
        if not name: continue
        amt = money(r.get("amount"))
        e = v.setdefault(name, {"vendor": name, "total": 0.0, "count": 0})
        e["total"] += amt; e["count"] += 1
    return sorted(v.values(), key=lambda x: -x["total"])

def main():
    import hands_awards as h
    rows, total = h.pull_all()
    buckets = {"maui": [], "state_hawaii": [], "other_county": []}
    for r in rows:
        buckets[classify(r, h.is_maui)].append(r)
    counts = {k: len(v) for k, v in buckets.items()}
    dollars = {k: round(sum(h.money(r.get("amount")) for r in v), 2) for k, v in buckets.items()}
    payload = {
        "generated": now_hst().strftime("%Y-%m-%d %H:%M:%S HST"),
        "source": "HANDS /hands/api/contract-awards (full statewide set retained)",
        "learned_total": len(rows),            # how many we actually retained
        "statewide_total": total,              # what HANDS reports as available
        "by_tenant_counts": counts,
        "by_tenant_dollars": dollars,
        "maui_vendors": rollup(buckets["maui"], h.money)[:300],
        "state_vendors": rollup(buckets["state_hawaii"], h.money)[:300],
        "note": "All public Notice-of-Award records retained and classified by tenant. "
                "Focus: Maui + State of Hawaii. Contracts are facts; questions for oversight, not accusations.",
    }
    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    with open(OUT_JSON + ".tmp", "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)
    os.replace(OUT_JSON + ".tmp", OUT_JSON)
    dispatch("SHIPPED", f"hands_statewide: learned {len(rows)}/{total} contracts "
                        f"(Maui {counts['maui']}, State of HI {counts['state_hawaii']}, "
                        f"other county {counts['other_county']})")
    print(f"learned {len(rows)}/{total} contracts | Maui {counts['maui']} "
          f"| State of HI {counts['state_hawaii']} | other county {counts['other_county']}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
