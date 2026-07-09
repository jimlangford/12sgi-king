#!/usr/bin/env python3
# tenant_registry.py - the ONE consolidated tenant + report registry (Jimmy 2026-06-16: "consolidate first").
#
# Before this, the tenant model was scattered across 3 places:
#   - tenant_depth.py  : civic tenants (NAMES) + their report classes (DIMS) + per-tenant file map (FILES)
#   - config/tenants.json : creative tenants (films / game / music-video)
#   - build_site.py    : the Governments nav + LABELS (a hardcoded copy of the civic tenant list)
# This DERIVES one unified view from the canonical sources (it does NOT copy/replace them - the generators
# stay the single owners of their data), writes config/tenant_registry.json, and exposes a clean API so the
# NEW per-tenant report template (and the nav, going forward) read from ONE place. Each tenant is tracked
# separately + uniquely; onboarding a new one is: add it to its canonical source, and it flows here.
# Stdlib only.
import os, sys, json
from datetime import datetime, timedelta, timezone
HST=timezone(timedelta(hours=-10))
HERE=os.path.dirname(os.path.abspath(__file__))
HOME=os.path.expanduser("~"); PROJ=os.path.join(HOME,"Documents","Claude","Projects","Video System elementLOTUS")
OUT=os.path.join(PROJ,"config","tenant_registry.json")
sys.path.insert(0,HERE)

def _civic():
    """Civic tenants + report classes, derived from tenant_depth (the canonical civic source)."""
    import tenant_depth as td
    classes=[{"key":k,"label":l,"desc":d} for k,l,d in td.DIMS]
    out=[]
    for tid,name in td.NAMES.items():
        # reflect REALITY via cell_status: a report is listed only if its page actually EXISTS (status ok).
        # mapped-but-missing (a gap) -> [] so the tenant-switcher shows it "building", never a broken link.
        reports={}
        for k,_,_ in td.DIMS:
            try: status, fn = td.cell_status(tid, k)
            except Exception: status, fn = "gap", None
            reports[k] = [fn] if (status=="ok" and fn) else []
        present=sum(1 for v in reports.values() if v)
        out.append({"id":tid,"name":name,"kind":"civic","quadrant":"govos",
                    "reports":reports,"report_classes_filled":present,"report_classes_total":len(td.DIMS)})
    return classes, out

def _creative():
    """Creative project tenants from config/tenants.json (the canonical creative source)."""
    try:
        d=json.load(open(os.path.join(PROJ,"config","tenants.json"),encoding="utf-8"))
        return [{"id":t["id"],"name":t.get("name"),"kind":t.get("kind"),"quadrant":t.get("quadrant"),
                 "render_register":t.get("render_register"),"status":t.get("status")} for t in d.get("tenants",[])]
    except Exception:
        return []

def build():
    classes, civic = _civic()
    creative = _creative()
    reg={"generated":datetime.now(HST).strftime("%Y-%m-%d %H:%M HST"),
         "_note":"DERIVED registry — one source of truth for tenants + report classes. Canonical owners: "
                 "civic=tenant_depth.py (DIMS/FILES/NAMES), creative=config/tenants.json. Regenerate via tenant_registry.py.",
         "report_classes":classes,
         "civic_tenants":civic,"creative_tenants":creative,
         "counts":{"civic":len(civic),"creative":len(creative),"report_classes":len(classes)}}
    return reg

def selfcheck(reg):
    """Consistency guards so the foundation is sound before anything new is built on it."""
    errs=[]
    keys={c["key"] for c in reg["report_classes"]}
    for t in reg["civic_tenants"]:
        missing=keys - set(t["reports"].keys())
        if missing: errs.append("%s missing report-class keys: %s"%(t["id"],sorted(missing)))
        if not t["name"]: errs.append("%s has no name"%t["id"])
    ids=[t["id"] for t in reg["civic_tenants"]+reg["creative_tenants"]]
    if len(ids)!=len(set(ids)): errs.append("duplicate tenant id across civic+creative")
    return errs

# ---- the clean API the new per-tenant template (and nav) read from ----
def load():
    try: return json.load(open(OUT,encoding="utf-8"))
    except Exception: return build()
def report_classes(): return load()["report_classes"]
def civic_tenants():  return load()["civic_tenants"]
def reports_for(tid):
    for t in load()["civic_tenants"]:
        if t["id"]==tid: return t["reports"]
    return {}

def main():
    reg=build(); errs=selfcheck(reg)
    os.makedirs(os.path.dirname(OUT),exist_ok=True)
    json.dump(reg,open(OUT,"w",encoding="utf-8"),indent=1,ensure_ascii=False)
    print("tenant_registry: %d civic + %d creative tenants, %d report classes -> config/tenant_registry.json"%(
          reg["counts"]["civic"],reg["counts"]["creative"],reg["counts"]["report_classes"]))
    print("  civic report coverage:")
    for t in reg["civic_tenants"]:
        print("    %-14s %d/%d report classes filled"%(t["name"][:14],t["report_classes_filled"],t["report_classes_total"]))
    print("  selfcheck:", "PASS" if not errs else "FAIL: "+"; ".join(errs))
    return 0 if not errs else 1

if __name__=="__main__":
    if sys.platform=="win32":
        import io; sys.stdout=io.TextIOWrapper(sys.stdout.buffer,encoding="utf-8",errors="replace")
    sys.exit(main())
