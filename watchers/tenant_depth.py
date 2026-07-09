#!/usr/bin/env python3
# tenant_depth.py - the CIVIC analog of surface_health.py (Jimmy 2026-06-16: "make the data of each tenant
#   as testimony deep as maui county ... the git public must be flawless"). Same boot-skill discipline:
#   define the reference set (Maui's testimony DIMENSIONS), sweep EVERY tenant against it, score coverage,
#   flag the gaps as the work-list, and catch flawlessness problems (a lens shown 'ready' whose file is
#   missing/empty/placeholder). Drives the "prosecutorial push until balanced" toward Maui depth everywhere.
#   Output: reports/_status/tenant_depth.{json,html} + a public-safe matrix. Stdlib only.
import json, os, sys
from datetime import datetime, timedelta, timezone

HOME = os.path.expanduser("~")
PROJECT = os.path.join(HOME, "Documents", "Claude", "Projects", "Video System elementLOTUS")
M = os.path.join(PROJECT, "reports", "mauios")
OUT = os.path.join(PROJECT, "reports", "_status")
HST = timezone(timedelta(hours=-10))
MIN_BYTES = 700          # below this = stub/placeholder, not real testimony

# The 8 canonical testimony DIMENSIONS every tenant should answer (Maui answers ~all of them).
DIMS = [
    ("govern",   "Who governs",        "officials / representatives + their voting record"),
    ("money",    "Money behind them",  "campaign finance — who funds the officials"),
    ("contracts","Contracts & spending","who the government pays"),
    ("federal",  "Federal dollars",    "federal money flowing into the jurisdiction"),
    ("crossref", "Money × votes",  "contracts crossed with donors / parity — the pattern"),
    ("agendas",  "Upcoming agendas",   "what is being decided next"),
    ("minutes",  "Meeting minutes",    "the official record — who moved, who voted, what carried"),
    ("council_votes", "Council votes & dissent", "every split vote + the dissenter's own recorded words, public record framed as questions"),
    ("charter",  "Charter ↔ Law",  "the governing rules, crosswalked to real law"),
    ("audit",    "Audit balance",      "the money×votes equation scorecard"),
]
_MIN_SUMMARY = os.path.join(PROJECT, "reports", "_status", "minutes_summary.json")
def _minutes_records(tid):
    """Real sourced minutes records for a tenant (from minutes_watch). 0 = page exists but 'building'."""
    try:
        d = json.load(open(_MIN_SUMMARY, encoding="utf-8"))
        for t in d.get("tenants", []):
            if t.get("tenant") == tid: return t.get("records", 0)
    except Exception:
        pass
    return 0
# Per-tenant candidate filenames for each dimension (real conventions in reports/mauios). [] = no source yet.
FILES = {
    "hi-maui":     {"govern":["officials_scorecard.html"], "money":["money_behind_officials.html"],
                    "contracts":["maui_contract_awards.html"], "federal":["federal_money.html"],
                    "crossref":["contracts_x_donors.html"], "agendas":["agendas_maui.html"],
                    "council_votes":["council_votes_maui.html"],
                    "charter":["crosswalk_maui.html"], "audit":["audit_balance.html"]},
    "hi-state":    {"govern":["lege/legislator_scorecard.html"], "money":["statewide_money_patterns.html"],
                    "contracts":["contracts_state.html"], "federal":["federal_money.html"],
                    "crossref":["parity_state.html"], "agendas":["agendas_state.html"],
                    "charter":["crosswalk_state.html"], "audit":["audit_balance.html"]},
    "hi-hawaii":   {"govern":[], "money":["statewide_money_patterns.html"], "contracts":["contracts_hawaii.html"],
                    "federal":["federal_money_hawaii.html"], "crossref":["parity_hawaii.html"],
                    "agendas":["agendas_hawaii.html"], "charter":["crosswalk_hawaii.html"], "audit":["audit_balance.html"]},
    "hi-kauai":    {"govern":[], "money":["statewide_money_patterns.html"], "contracts":["contracts_kauai.html"],
                    "federal":["federal_money_kauai.html"], "crossref":["parity_kauai.html"],
                    "agendas":["agendas_kauai.html"], "charter":["crosswalk_kauai.html"], "audit":["audit_balance.html"]},
    "hi-honolulu": {"govern":[], "money":["statewide_money_patterns.html"], "contracts":["contracts_honolulu.html"],
                    "federal":["federal_money_honolulu.html"], "crossref":["parity_honolulu.html"],
                    "agendas":["agendas_honolulu.html"], "charter":["crosswalk_honolulu.html"], "audit":["audit_balance.html"]},
    "ny":          {"govern":[], "money":["money_nyc.html"], "contracts":["contracts_nyc.html","contracts_nys.html"],
                    "federal":[], "crossref":["parity_nyc.html"], "agendas":["agendas_nyc.html"],
                    "charter":[], "audit":[]},
}
NAMES = {"hi-maui":"Maui County","hi-state":"State of Hawaiʻi","hi-hawaii":"Hawaiʻi County",
         "hi-kauai":"Kauaʻi County","hi-honolulu":"Honolulu","ny":"New York"}

def status_of(cands):
    """('ok'|'thin'|'gap', filename-or-None). ok = real file >= MIN_BYTES; thin = exists but stub; gap = none."""
    if not cands: return "gap", None
    for fn in cands:
        p = os.path.join(M, fn)
        if os.path.exists(p):
            return ("ok" if os.path.getsize(p) >= MIN_BYTES else "thin"), fn
    return "gap", None

def cell_status(tid, key):
    """(status, file) for one tenant×dimension. Centralized so the depth sweep AND the tenant pages agree.
    'minutes' is special: covered only when there are REAL sourced records (an honest 'building' page = thin)."""
    if key == "minutes":
        fn = "minutes_%s.html" % tid
        exists = os.path.exists(os.path.join(M, fn))
        if _minutes_records(tid) > 0: return "ok", fn
        return ("thin" if exists else "gap"), (fn if exists else None)
    return status_of(FILES.get(tid, {}).get(key, []))

def main():
    now = datetime.now(HST)
    rows, tenants = [], []
    ref = sum(1 for d in DIMS if cell_status("hi-maui", d[0])[0] == "ok")  # Maui depth
    for tid, fmap in FILES.items():
        cells, covered, thin = [], 0, 0
        for key, label, _desc in DIMS:
            st, fn = cell_status(tid, key)
            if st == "ok": covered += 1
            elif st == "thin": thin += 1
            cells.append({"dim": key, "label": label, "status": st, "file": fn})
        tenants.append({"id": tid, "name": NAMES.get(tid, tid), "covered": covered, "thin": thin,
                        "total": len(DIMS), "pct": round(100*covered/len(DIMS)), "cells": cells,
                        "to_maui": max(0, ref - covered)})
    tenants.sort(key=lambda t: -t["covered"])
    flaws = [(t["id"], c["label"]) for t in tenants for c in t["cells"] if c["status"] == "thin"]
    payload = {"generated": now.strftime("%Y-%m-%d %H:%M HST"), "maui_reference_depth": ref,
               "dimensions": [{"key":k,"label":l,"desc":d} for k,l,d in DIMS],
               "tenants": tenants, "flaws_thin": flaws}
    os.makedirs(OUT, exist_ok=True)
    json.dump(payload, open(os.path.join(OUT, "tenant_depth.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    _html(payload)
    print("tenant_depth: Maui reference depth = %d/%d dimensions" % (ref, len(DIMS)))
    for t in tenants:
        gaps = [c["label"] for c in t["cells"] if c["status"] == "gap"]
        print("  %-18s %d/%d (%d%%)  +%d to Maui  gaps: %s" % (
            t["name"], t["covered"], t["total"], t["pct"], t["to_maui"], ", ".join(gaps) or "none"))
    if flaws:
        print("  FLAW (shown but stub/empty): " + "; ".join("%s/%s" % f for f in flaws))
    return 0

def _esc(s): return str(s).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
def _html(p):
    mark = {"ok":"<span style='color:#1f9d55'>✓</span>", "thin":"<span style='color:#d9822b'>○</span>",
            "gap":"<span style='color:#c0392b'>—</span>"}
    head = "".join("<th title='%s'>%s</th>" % (_esc(d["desc"]), _esc(d["label"])) for d in p["dimensions"])
    body = ""
    for t in p["tenants"]:
        bar = int(t["pct"]/10)
        cells = "".join("<td style='text-align:center'>%s</td>" % mark[c["status"]] for c in t["cells"])
        body += ("<tr><td><b>%s</b><div class=m>%d/%d · %d%%%s</div></td>%s</tr>" % (
            _esc(t["name"]), t["covered"], t["total"], t["pct"],
            (" · +%d to Maui depth" % t["to_maui"]) if t["to_maui"] else " · at reference depth", cells))
    html = ("<!doctype html><meta charset=utf-8><meta http-equiv=refresh content=600>"
        "<title>Tenant testimony depth</title><style>"
        "body{font-family:system-ui,Segoe UI,sans-serif;max-width:1000px;margin:1.4rem auto;padding:0 1rem;color:#eaf2fc}"
        "h1{font-size:1.35rem;margin:.2rem 0}.sub{color:#5b6b78;font-size:.9rem;margin-bottom:1rem}"
        "table{border-collapse:collapse;width:100%%;font-size:.82rem}th,td{padding:.45rem .5rem;border-bottom:1px solid #e7edf2}"
        "th{text-align:left;color:#42535f;font-weight:600;font-size:.74rem}.m{color:#8b99a6;font-size:.72rem}"
        "thead th{position:sticky;top:0;background:#fff}</style>"
        "<h1>Testimony depth by government</h1>"
        "<div class=sub>Every tenant is measured against Maui County's depth (the reference: %d of %d civic-testimony "
        "dimensions). ✓ = sourced &amp; published · ○ = present but thin · — = gap (work to do). "
        "The goal: bring every government to Maui-deep, with flawless sourced data.</div>"
        "<table><thead><tr><th>Government</th>%s</tr></thead><tbody>%s</tbody></table>" % (
        p["maui_reference_depth"], len(p["dimensions"]), head, body))
    open(os.path.join(OUT, "tenant_depth.html"), "w", encoding="utf-8").write(html)

if __name__ == "__main__":
    if sys.platform == "win32":
        import io; sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(main())
