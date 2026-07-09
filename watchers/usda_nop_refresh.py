#!/usr/bin/env python3
"""usda_nop_refresh.py — daily USDA NOP cache warmer for ʻŌnaehana Holo.

Queries USDA NOP for all Hawaii certified organic operations and caches the result.
Wired into inloop_schedule.py (daily at 02:00 HST). Logs result to dispatch.

Run manually: python tools/kilo-aupuni/usda_nop_refresh.py
"""
import os, sys, json, time

PROJECT = r"C:\Users\12sgi\Documents\Claude\Projects\Video System elementLOTUS"
ONAEHANA = os.path.join(PROJECT, "tools", "kilo-aupuni", "onaehana_holo")

sys.path.insert(0, os.path.join(PROJECT, "tools", "ops"))
try:
    from utf8_ready import force
    force()
except Exception:
    pass

def _load_holo():
    import importlib.util
    spec = importlib.util.spec_from_file_location("onaehana_holo", os.path.join(ONAEHANA, "__init__.py"))
    mod = importlib.util.module_from_spec(spec)
    # pre-load sub-modules so relative imports work
    for sub in ("data_models", "wfcf_connector", "usda_integration", "civic_mapper", "grant_stacker"):
        sspec = importlib.util.spec_from_file_location(
            "onaehana_holo." + sub, os.path.join(ONAEHANA, sub + ".py"))
        smod = importlib.util.module_from_spec(sspec)
        sspec.loader.exec_module(smod)
        sys.modules["onaehana_holo." + sub] = smod
    sys.modules["onaehana_holo"] = mod
    spec.loader.exec_module(mod)
    return mod

def _log(msg, source="kilo-aupuni"):
    try:
        dp = os.path.join(PROJECT, "app", "server", "dispatch.py")
        import subprocess
        subprocess.run([sys.executable, "-X", "utf8", dp, PROJECT,
                        "--log-event", msg, "--source", source],
                       capture_output=True, timeout=15)
    except Exception:
        pass

def main():
    t0 = time.time()
    try:
        mod = _load_holo()
        holo = mod.OnaehanaHolo()
        ops = holo.search_hawaii_operations(state="HI")
        elapsed = round(time.time() - t0, 1)
        msg = "SHIPPED: usda_nop_refresh complete — %d Hawaii certified ops cached (%.1fs, mode=%s)" % (
            len(ops), elapsed, holo.mode)
        print(msg)
        _log(msg)
    except Exception as e:
        msg = "BLOCKER: usda_nop_refresh FAILED — %s" % str(e)[:200]
        print(msg)
        _log(msg)
        sys.exit(1)

if __name__ == "__main__":
    main()
