#!/usr/bin/env python3
"""donor_watch_tenant.py — tenant-aware wrapper for donor_watch.py.

Reads officials from config/tenant_officials.json[<tenant>] and runs the
same CSC donor-profile pull against them, writing per-tenant output files.
Maui (default) routes straight through to the production donor_watch.main().

CLI: --tenant <t>   (e.g. hi-honolulu, hi-hawaii, hi-kauai, hi-state)
     --dryrun       resolve config, skip API calls
"""
import os, sys, json

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import donor_watch as dw

CFG = os.path.join(dw.PROJECT, "config", "tenant_officials.json")
MAUIOS = os.path.join(dw.PROJECT, "reports", "mauios")


def officials_for(tenant):
    try:
        cfg = json.load(open(CFG, encoding="utf-8"))
    except Exception:
        cfg = {}
    raw = cfg.get(tenant, [])
    if not raw and tenant == "maui":
        return list(dw.OFFICIALS)
    return [tuple(x) for x in raw]


def paths_for(tenant):
    if tenant == "maui":
        return dw.OUT_DIR, dw.PROFILES_F, dw.PAGE_F, dw.VDJOIN_F
    suffix = "_" + tenant
    return (
        os.path.join(MAUIOS, "donors" + suffix),
        os.path.join(MAUIOS, "donor_profiles" + suffix + ".json"),
        os.path.join(MAUIOS, "money_behind_officials" + suffix + ".html"),
        os.path.join(MAUIOS, "vendor_donor_join" + suffix + ".json"),
    )


def run(tenant, dryrun=False):
    officials = officials_for(tenant)
    out_dir, profiles_f, page_f, vdjoin_f = paths_for(tenant)
    print("[tenant=%s] officials=%d  profiles -> %s" % (
        tenant, len(officials), os.path.basename(profiles_f)))
    if not officials:
        print("  NEEDS-RECORD: no officials configured for '%s' in config/tenant_officials.json" % tenant)
        return 0
    if dryrun:
        print("  dryrun: per-tenant config resolves cleanly; skipping API calls.")
        return 0
    # Monkeypatch module-level config then run
    dw.OFFICIALS  = officials
    dw.OUT_DIR    = out_dir
    dw.PROFILES_F = profiles_f
    dw.PAGE_F     = page_f
    dw.VDJOIN_F   = vdjoin_f
    return dw.main()


def main(argv):
    tenant = "maui"
    if "--tenant" in argv:
        tenant = argv[argv.index("--tenant") + 1]
    return run(tenant, "--dryrun" in argv)


if __name__ == "__main__":
    if sys.platform == "win32":
        import io; sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(main(sys.argv))
