#!/usr/bin/env python3
# audit_cycle.py - Kilo Aupuni RECURRING AUDIT entrypoint.
#   ONE windowless call that runs the full Maui + State-of-Hawaii + federal audit chain
#   and reports whether the money x votes "equation" is balanced yet. This is what the
#   scheduled task runs daily; it keeps the recurring work going UNTIL audit_balance
#   reports BALANCED (coverage complete + every flagged pair examined).
#
#   1) kilo_aupuni --run-watchers : council, votes, donor, bids, permits, federal, charter
#   2) money/contracts chain      : hands_awards, statewide_money, vendor_donor_join,
#                                    parity_check, lobby_money_watch  (each if present)
#   3) prosecutorial fill         : prosecutor.py  (private; fills case_files from the above)
#   4) audit_balance              : the completion scorecard (the "equation")
#
# Stdlib only, all in-process (no window). Each step is defensive: a failure logs a
# FINDING and the cycle continues. Run: py -3 audit_cycle.py
import importlib, json, os, sys, time
from datetime import datetime, timedelta, timezone

TOOL_DIR = os.path.dirname(os.path.abspath(__file__))
HOME     = os.path.expanduser("~")
PROJECT  = os.path.join(HOME, "Documents", "Claude", "Projects", "Video System elementLOTUS")
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

def step(modname, label):
    """Import a module and call its main(); never let one step kill the cycle."""
    try:
        m = importlib.import_module(modname)
        importlib.reload(m)
        if hasattr(m, "main"):
            m.main()
        print(f"  + {label}")
        return True
    except Exception as e:
        dispatch("FINDING", f"audit_cycle step '{label}' failed: {e}")
        print(f"  x {label}: {e}")
        return False

def main():
    print(f"=== Kilo Aupuni audit cycle {now_hst():%Y-%m-%d %H:%M HST} (Maui + State of Hawaii + federal) ===")
    dispatch("FINDING", "audit_cycle START (recurring Maui+State+federal audit)")

    # 1) live watchers (incl. federal-money) + dashboard
    try:
        import kilo_aupuni
        importlib.reload(kilo_aupuni)
        reg = kilo_aupuni.load_registry()
        ran = kilo_aupuni.run_live_watchers(reg)
        kilo_aupuni.build_dashboard(reg)
        print(f"  + watchers: {', '.join(ran) if ran else '(none ran)'}")
    except Exception as e:
        dispatch("FINDING", f"audit_cycle watchers failed: {e}")
        print(f"  x watchers: {e}")

    # 2) money / contracts chain (each optional)
    for mod, label in [
        ("hands_awards",      "county contracts (HANDS)"),
        ("statewide_money",   "statewide campaign money"),
        ("hands_statewide",   "statewide contracts learn-all"),   # built if present
        ("vendor_donor_join", "contracts x donors (money x votes)"),
        ("parity_check",      "money x votes parity"),
        ("lobby_money_watch", "lobby + donate"),
    ]:
        step(mod, label)

    # 3) prosecutorial fill (private; marshals the above into case_files)
    step("prosecutor", "prosecutorial case files (private)")

    # 4) the equation scorecard
    ok = step("audit_balance", "audit_balance scorecard")

    # report verdict
    try:
        bal = json.load(open(os.path.join(PROJECT, "reports", "mauios", "audit_balance.json"), encoding="utf-8"))
        v = bal.get("verdict", "?")
        dispatch("SHIPPED" if bal.get("balanced") else "FINDING", f"audit_cycle DONE: {v}")
        print(f"=== verdict: {v} ===")
    except Exception:
        dispatch("FINDING", "audit_cycle DONE (no balance file)")
    return 0

if __name__ == "__main__":
    sys.exit(main())
