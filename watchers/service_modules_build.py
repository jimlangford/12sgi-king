# -*- coding: utf-8 -*-
"""service_modules_build.py - regenerate every config-driven civic service page.

Runs the County Service Module Engine (service_module_engine.py) over every
tools/kilo-aupuni/service_modules/*.config.json, guardrail-checking each (no
Stripe secret keys; law sections need a source) and writing the page to
reports/mauios/service_modules/<outFile>. Adding a civic title = drop a
<id>.config.json here; the maintenance tick rebuilds it. Additive: does NOT
touch the bespoke title19_calculators.py. Stdlib only; never fails the tick.

  python tools/kilo-aupuni/service_modules_build.py            # build all
  python tools/kilo-aupuni/service_modules_build.py --check     # guardrail only, no write
"""
from __future__ import annotations
import os, sys, glob, json

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
CFG_DIR = os.path.join(HERE, "service_modules")
OUT_DIR = os.path.join(ROOT, "reports", "mauios", "service_modules")
sys.path.insert(0, HERE)


def main():
    check = "--check" in sys.argv
    try:
        import service_module_engine as eng
    except Exception as e:
        print("service_modules_build: engine import failed:", e)
        return 0
    os.makedirs(OUT_DIR, exist_ok=True)
    built = failed = 0
    for cfg_path in sorted(glob.glob(os.path.join(CFG_DIR, "*.config.json"))):
        name = os.path.basename(cfg_path)
        try:
            cfg = json.load(open(cfg_path, encoding="utf-8"))
            html = eng.render(cfg)
            problems = eng.guardrail_check(cfg, html)
            for p in problems:
                print("  [%s] %s" % (name, p))
            if any(p.startswith("FAIL") for p in problems):
                failed += 1
                continue  # guardrail FAIL -> never write
            if not check:
                out = os.path.join(OUT_DIR, cfg["meta"]["outFile"])
                with open(out, "w", encoding="utf-8", newline="\n") as fh:
                    fh.write(html)
            built += 1
            print("  OK  %s -> %s (%d sections)" % (name, cfg["meta"]["outFile"], len(cfg["sections"])))
        except Exception as e:
            failed += 1
            print("  ERR %s: %s" % (name, str(e)[:120]))
    print("service_modules_build: %d built, %d failed%s" % (built, failed, " (check-only)" if check else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
