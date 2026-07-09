#!/usr/bin/env python3
"""vendor_donor_join_tenant.py — TENANT-AWARE SCAFFOLD for the contracts x donors join (hub-prepped 2026-06-20,
Jimmy "prep + autoprompt civic"). PROPOSED scaffold, NOT a rewrite: it REUSES vendor_donor_join.py's tested
matching and only swaps the per-tenant config (awards file, output files, tracked officials) so each tenant runs
in its OWN separate database. Maui stays byte-identical (the default + canonical unsuffixed output).

TENANT ISOLATION: officials come from config/tenant_officials.json[<tenant>]; an EMPTY list => honest empty
(NEEDS-RECORD), never Maui's data. No cross-tenant pooling.

CIVIC OWNS (the sourcing judgment this scaffold deliberately leaves blank):
  (a) fill config/tenant_officials.json for hi-honolulu/hi-hawaii/hi-kauai/hi-state/ny — each county's tracked
      officials + CSC candidate_name LIKE pattern (keep in sync with donor_watch.py);
  (b) make hands_awards.py tenant-aware so hands_<tenant>_awards.json exists (HANDS county-filtered).
Then: python vendor_donor_join_tenant.py --tenant hi-honolulu  -> vendor_donor_join_hi-honolulu.json
      python money_votes_casework.py --tenant hi-honolulu       -> casework_hi-honolulu.json (already tenant-ready)

CLI: --tenant <t> [--dryrun]   (dryrun resolves the per-tenant config without hitting the CSC API)
"""
import os, sys, json

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import vendor_donor_join as vdj   # reuse its tested matching/fetch/build — only the config differs per tenant

CFG = os.path.join(vdj.PROJECT, "config", "tenant_officials.json")
MAUIOS = os.path.join(vdj.PROJECT, "reports", "mauios")


def officials_for(tenant):
    try:
        cfg = json.load(open(CFG, encoding="utf-8"))
    except Exception:
        cfg = {}
    raw = cfg.get(tenant, [])
    if not raw and tenant == "maui":          # maui falls back to the live module's canonical list
        return list(vdj.OFFICIALS)
    return [tuple(x) for x in raw]


def paths_for(tenant):
    a = "hands_maui_awards.json" if tenant == "maui" else "hands_%s_awards.json" % tenant
    j = "vendor_donor_join.json" if tenant == "maui" else "vendor_donor_join_%s.json" % tenant   # canonical name money_votes_casework expects
    h = "contracts_x_donors.html" if tenant == "maui" else "contracts_x_donors_%s.html" % tenant
    return os.path.join(MAUIOS, a), os.path.join(MAUIOS, j), os.path.join(MAUIOS, h)


def run(tenant, dryrun=False):
    officials = officials_for(tenant)
    awards, out_json, out_html = paths_for(tenant)
    print("[tenant=%s] officials=%d  awards=%s -> %s" % (tenant, len(officials),
                                                         os.path.basename(awards), os.path.basename(out_json)))
    if not officials:
        print("  NEEDS-RECORD: no tracked officials configured for '%s' — CIVIC must SOURCE them into "
              "config/tenant_officials.json (no fabrication). Empty join by design." % tenant)
        return 0
    if not os.path.exists(awards):
        print("  NEEDS-DATA: %s absent — make hands_awards.py tenant-aware to produce it first." % os.path.basename(awards))
        return 0
    if dryrun:
        print("  dryrun: per-tenant config resolves cleanly; not hitting the CSC API.")
        return 0
    # swap the live module's module-level config for THIS tenant, then reuse its tested join end-to-end
    vdj.OFFICIALS, vdj.AWARDS_F, vdj.OUT_JSON, vdj.OUT_HTML = officials, awards, out_json, out_html
    return vdj.main()


def main(argv):
    tenant = "maui"
    if "--tenant" in argv:
        tenant = argv[argv.index("--tenant") + 1]
    return run(tenant, "--dryrun" in argv)


if __name__ == "__main__":
    if sys.platform == "win32":
        import io; sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(main(sys.argv))
