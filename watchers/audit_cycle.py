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
        ("crosswalk_learn",   "per-tenant learning crosswalk (ingest->update->reassess)"),
    ]:
        step(mod, label)

    # 2b) minutes: the people's record per tenant (private evidence spine + dignified public page)
    step("minutes_watch", "meeting minutes per tenant")

    # 3) prosecutorial fill (private; marshals the above into case_files)
    step("prosecutor", "prosecutorial case files (private)")

    # 4) the equation scorecard
    ok = step("audit_balance", "audit_balance scorecard")

    # 4b) boot-persistence sweep across ALL surfaces - relaunch any dark server/daemon (NEVER ComfyUI/GPU).
    #     Generalized from the :8799 King + publish-watcher reboot gaps (Jimmy 2026-06-16).
    try:
        import subprocess, sys as _s
        subprocess.run([_s.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), "surface_health.py"), "--heal"],
                       timeout=120)
        print("  + surface health sweep (--heal)")
    except Exception as e:
        dispatch("FINDING", f"audit_cycle surface_health failed: {e}")

    # 4c) storyboard: auto-catalog newly-rendered clips into the film storyboard (incremental thumbnails).
    try:
        import subprocess as _sp, sys as _sy, os as _o
        env = dict(_o.environ); env["THUMB_CAP"] = "40"   # bounded per cycle; incremental skips existing
        _sp.run([_sy.executable, _o.path.join(_o.path.dirname(_o.path.abspath(__file__)), "storyboard_scan.py")],
                env=env, timeout=180)
        print("  + storyboard scan (new clips catalogued)")
    except Exception as e:
        dispatch("FINDING", f"audit_cycle storyboard_scan failed: {e}")

    # 4d) clip->node-world classifier: sort every rendered clip into its 54-node world (song->node->zone)
    #     and assign zone-matched candidate clips to each of the 60 script scenes. Feeds node-LoRA
    #     style/storyboard reference sets + per-scene storyboard candidates (Jimmy 2026-06-16).
    try:
        import clip_nodes; importlib.reload(clip_nodes); clip_nodes.main()
        print("  + clip->node classifier (clips sorted into the 54 node-worlds)")
    except Exception as e:
        dispatch("FINDING", f"audit_cycle clip_nodes failed: {e}")

    # 4e) reverse-engine lens: measure (GPU-free, ffprobe+signalstats) how the render engine ACTUALLY produced
    #     each clip -> per-zone (the 4 models) + per-node reverse-engineered recipes = training targets.
    #     Bounded per cycle via REV_CAP; resumable cache so it sweeps the backlog over successive runs.
    try:
        import os as _o; _o.environ.setdefault("REV_CAP","400")
        import clip_engine_reverse; importlib.reload(clip_engine_reverse); clip_engine_reverse.main()
        print("  + reverse-engine recipes (how the engine actually rendered each clip)")
    except Exception as e:
        dispatch("FINDING", f"audit_cycle clip_engine_reverse failed: {e}")

    # 5) self-heal: integrity guards + CUMULATIVE skill refinement (the covenant - every run refines).
    #    selfheal.run() invokes selfheal_learn.py via its progress hook, so the skill tally + dashboard
    #    refresh on every daily cycle. Never lets a self-heal hiccup kill the audit.
    try:
        import selfheal; importlib.reload(selfheal); selfheal.run()
        print("  + self-heal guard + cumulative skill refinement")
    except Exception as e:
        dispatch("FINDING", f"audit_cycle self-heal step failed: {e}")
        print(f"  x self-heal: {e}")

    # 5b) MASTER PRACTICES: consolidate every best practice (canon + live learnings + dated policies +
    #     source index) into the ONE master doc, self-healed each cycle (Jimmy 2026-06-16).
    try:
        import master_practices; importlib.reload(master_practices); master_practices.main()
        print("  + master practices consolidated (docs/MASTER_PRACTICES.md)")
    except Exception as e:
        dispatch("FINDING", f"audit_cycle master_practices failed: {e}")

    # 5c) TENANT REGISTRY: the ONE consolidated tenant + report-class source of truth (derived from
    #     tenant_depth + config/tenants.json). Regenerate + selfcheck each cycle so the foundation the
    #     per-tenant report template builds on stays consistent (Jimmy 2026-06-16: "consolidate first").
    try:
        import tenant_registry; importlib.reload(tenant_registry)
        _reg = tenant_registry.build(); _errs = tenant_registry.selfcheck(_reg)
        tenant_registry.main()
        if _errs: dispatch("FINDING", f"tenant_registry selfcheck FAIL: {'; '.join(_errs)}")
        print("  + tenant registry consolidated (config/tenant_registry.json)")
    except Exception as e:
        dispatch("FINDING", f"audit_cycle tenant_registry failed: {e}")

    # 5d) DAILY BRIEF: consolidate the cross-thread WORKFLOW + open blockers/handoffs into the daily
    #     current-state (docs/DAILY_BRIEF.md + owner-only Naga page) so Jimmy stays current each day.
    try:
        import daily_brief; importlib.reload(daily_brief); daily_brief.main()
        print("  + daily brief (docs/DAILY_BRIEF.md + Naga daily_brief.html)")
    except Exception as e:
        dispatch("FINDING", f"audit_cycle daily_brief failed: {e}")

    # 5e) AGENDA CADENCE: Sunshine-Law timed agenda posts (T-6/T-3/T-1/day-of) staged private per
    #     config/agenda_post_policy.json — one of the two allowed public lanes (with the daily moon message).
    try:
        import agenda_cadence; importlib.reload(agenda_cadence); agenda_cadence.run()
        print("  + agenda cadence (Sunshine-Law timed posts staged)")
    except Exception as e:
        dispatch("FINDING", f"audit_cycle agenda_cadence failed: {e}")

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
