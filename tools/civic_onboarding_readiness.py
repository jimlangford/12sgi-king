#!/usr/bin/env python3
"""civic_onboarding_readiness.py — read-only readiness + onboarding-model check for civic tenants.

WHAT THIS IS.
  Two problems, one tool:

  1. READINESS (the "influencer works backward from agenda items" rule): cross-reference each
     agenda-tracked jurisdiction's NEXT upcoming meeting/hearing date (watchers/agenda_sources.json)
     against its civic testimony-depth coverage (watchers/tenant_depth.py's 12 DIMS). Content tied
     to an agenda item should never go out claiming complete civic data when dimensions are still a
     gap and the deadline is close. This flags exactly that, ahead of time.

  2. ONBOARDING MODEL (the "not loops" fix): agenda_sources.json has grown to track far more
     jurisdictions (16, as of this writing) than tenant_depth.py's civic-depth registry has ever
     onboarded (6). Ten agenda-tracked tenants (e.g. london, tokyo, hongkong, singapore, zurich,
     frankfurt, paris, dubai, liverpool) were wired into agenda-tracking during v1 build-out but were
     never given a corresponding civic-depth intake entry — they are not "gap" (12 dims marked
     missing), they are simply ABSENT from the registry, which is silent and easy to miss. This
     script makes that absence loud (UNREGISTERED) and prints the fixed, single-pass checklist a new
     tenant must complete at intake, so future onboarding is one deliberate pass instead of
     discovering gaps piecemeal across sessions.

WHAT THIS IS NOT.
  Read-only. Never writes a file, never emits a workboard job, never touches the dispatch log,
  never posts content. It only answers "are we ready" and "what does 'onboarded' mean" — a plain
  report. Wiring any of this into an actual publish gate is a separate, future, explicitly
  owner-approved decision.

CLI:
  python tools/civic_onboarding_readiness.py                  # readiness report (default lead=14d)
  python tools/civic_onboarding_readiness.py --lead-days 21   # widen/narrow the "at risk" window
  python tools/civic_onboarding_readiness.py --checklist      # print the fixed onboarding model

Stdlib only.
"""
import json
import os
import sys
from datetime import date

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_WATCHERS = os.path.join(_REPO, "watchers")
if _WATCHERS not in sys.path:
    sys.path.insert(0, _WATCHERS)

AGENDA_SRC = os.path.join(_WATCHERS, "agenda_sources.json")

try:
    import tenant_depth as td  # canonical civic DIMS + FILES + cell_status()
except Exception:
    td = None

LEAD_DAYS_DEFAULT = 14

# Bridges an agenda_sources.json tenant_id to the civic-depth tenant_id it rolls up to.
# This alias table IS the intake seam: every agenda tenant_id must resolve here to exactly one
# civic-depth id, or it is flagged UNREGISTERED below — never silently dropped.
AGENDA_TO_DEPTH = {
    "state": "hi-state",
    "maui": "hi-maui",
    "honolulu": "hi-honolulu",
    "hawaii": "hi-hawaii",
    "kauai": "hi-kauai",
    "nyc": "ny",
    "nys": "ny",
}

# Fallback mirror of tenant_depth.DIMS, used only if tenant_depth cannot be imported, so this
# check never silently degrades into reporting nothing.
_FALLBACK_DIMS = [
    ("govern", "Who governs", "officials / representatives + their voting record"),
    ("money", "Money behind them", "campaign finance — who funds the officials"),
    ("contracts", "Contracts & spending", "who the government pays"),
    ("federal", "Federal dollars", "federal money flowing into the jurisdiction"),
    ("crossref", "Money x votes", "contracts crossed with donors / parity — the pattern"),
    ("nonprofits", "990 Nonprofits", "nonprofit filings — revenue, expenses, officer comp"),
    ("subcontracts", "Subcontractor chain", "federal subaward money one hop further down"),
    ("agendas", "Upcoming agendas", "what is being decided next"),
    ("minutes", "Meeting minutes", "the official record — who moved, who voted, what carried"),
    ("council_votes", "Council votes & dissent", "every split vote + the dissenter's own words"),
    ("charter", "Charter <-> Law", "the governing rules, crosswalked to real law"),
    ("audit", "Audit balance", "the money x votes equation scorecard"),
]


def _load_json(path, default=None):
    try:
        return json.load(open(path, encoding="utf-8"))
    except Exception:
        return default if default is not None else {}


def _today():
    return date.today()


def _next_upcoming(upcoming, today):
    """Earliest date >= today among an agenda source's 'upcoming' list. None if there isn't one."""
    best = None
    for m in upcoming or []:
        try:
            dd = date.fromisoformat(m.get("date", ""))
        except Exception:
            continue
        if dd >= today and (best is None or dd < best):
            best = dd
    return best


def onboarding_checklist():
    """The single fixed onboarding model: the 12 civic-testimony dimensions every tenant must be
    accounted for in ONE pass at intake — never accreted piecemeal across sessions.
    Returns [(key, label, desc)]."""
    if td is not None:
        try:
            return list(td.DIMS)
        except Exception:
            pass
    return list(_FALLBACK_DIMS)


def tenant_gaps(depth_tid):
    """Sorted list of dimension keys with NO real source ('gap', not just 'thin') for a
    civic-depth tenant id. If tenant_depth can't be imported, every dimension counts as a gap —
    this fails toward visibility, never toward a false 'complete'."""
    dims = onboarding_checklist()
    if td is None:
        return [k for k, _, _ in dims]
    gaps = []
    for k, _, _ in dims:
        try:
            status, _fn = td.cell_status(depth_tid, k)
        except Exception:
            status = "gap"
        if status == "gap":
            gaps.append(k)
    return gaps


def readiness_report(lead_days=LEAD_DAYS_DEFAULT):
    """Read-only sweep: for every agenda-tracked tenant, resolve its civic-depth id (or flag
    UNREGISTERED), compute days until its next upcoming agenda item, and cross-reference that
    against its dimension gaps. Sorted most-urgent first."""
    today = _today()
    sources = _load_json(AGENDA_SRC, {}).get("sources", [])
    rows = []
    for src in sources:
        atid = src.get("tenant_id", "")
        next_dt = _next_upcoming(src.get("upcoming"), today)
        days_until = (next_dt - today).days if next_dt else None
        depth_tid = AGENDA_TO_DEPTH.get(atid)

        if depth_tid is None:
            rows.append({
                "agenda_tenant": atid,
                "depth_tenant": None,
                "next_agenda": next_dt.isoformat() if next_dt else None,
                "days_until": days_until,
                "gaps": None,
                "verdict": "UNREGISTERED",
            })
            continue

        gaps = tenant_gaps(depth_tid)
        if not gaps:
            verdict = "READY"
        elif days_until is not None and days_until <= lead_days:
            verdict = "BLOCKED"
        else:
            verdict = "AT_RISK"  # gaps exist, but nothing imminent on the calendar (yet)

        rows.append({
            "agenda_tenant": atid,
            "depth_tenant": depth_tid,
            "next_agenda": next_dt.isoformat() if next_dt else None,
            "days_until": days_until,
            "gaps": gaps,
            "verdict": verdict,
        })

    order = {"BLOCKED": 0, "UNREGISTERED": 1, "AT_RISK": 2, "READY": 3}
    rows.sort(key=lambda r: (order.get(r["verdict"], 9),
                              r["days_until"] if r["days_until"] is not None else 9999))
    return rows


def print_report(lead_days=LEAD_DAYS_DEFAULT):
    rows = readiness_report(lead_days)
    print("civic_onboarding_readiness -- lead time = %d day(s), today = %s"
          % (lead_days, _today().isoformat()))
    print("(read-only: no files written, no jobs emitted, no content posted)\n")

    for r in rows:
        if r["verdict"] == "UNREGISTERED":
            print("  [UNREGISTERED] %-12s next_agenda=%-12s -- agenda-tracked but never onboarded "
                  "into the civic-depth registry" % (r["agenda_tenant"], r["next_agenda"] or "none"))
            continue
        gaps = ", ".join(r["gaps"]) if r["gaps"] else "none"
        due = ("in %dd" % r["days_until"]) if r["days_until"] is not None else "no upcoming item"
        print("  [%-9s] %-12s -> %-10s next_agenda=%-12s (%s)  gaps: %s"
              % (r["verdict"], r["agenda_tenant"], r["depth_tenant"], r["next_agenda"] or "none",
                 due, gaps))

    unreg = sum(1 for r in rows if r["verdict"] == "UNREGISTERED")
    blocked = sum(1 for r in rows if r["verdict"] == "BLOCKED")
    at_risk = sum(1 for r in rows if r["verdict"] == "AT_RISK")
    ready = sum(1 for r in rows if r["verdict"] == "READY")
    print("\nSummary: %d BLOCKED, %d UNREGISTERED, %d AT_RISK, %d READY"
          % (blocked, unreg, at_risk, ready))
    if blocked or unreg:
        print("Zero-missing-data is NOT met yet -- see BLOCKED/UNREGISTERED rows above.")


def print_checklist():
    print("Civic tenant onboarding model -- ONE pass, not loops.\n")
    print("Whenever a new tenant_id is added to watchers/agenda_sources.json, the SAME intake")
    print("must also, in one pass:")
    print("  1. Add an alias in AGENDA_TO_DEPTH (this file) pointing at its civic-depth id.")
    print("  2. Add a NAMES + FILES entry in watchers/tenant_depth.py covering ALL 12 dimensions")
    print("     below (empty [] lists are fine -- a declared gap, never a silent omission).")
    print("  3. Regenerate config/tenant_registry.json via watchers/tenant_registry.py so the")
    print("     tenant switcher / nav reflect it.")
    print("A tenant is 'onboarded' only when all three are done -- not just the first one that")
    print("happened to get built first.\n")
    for k, label, desc in onboarding_checklist():
        print("  - %-14s %-26s %s" % (k, label, desc))


def main():
    argv = sys.argv[1:]
    lead_days = LEAD_DAYS_DEFAULT
    if "--lead-days" in argv:
        i = argv.index("--lead-days")
        try:
            lead_days = int(argv[i + 1])
        except Exception:
            pass
    if "--checklist" in argv:
        print_checklist()
        return 0
    print_report(lead_days)
    return 0


if __name__ == "__main__":
    if sys.platform == "win32":
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(main())
