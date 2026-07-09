#!/usr/bin/env python3
"""civic_books.py — the CIVIC AUDIT filed like a government's chart of accounts
   (Jimmy 2026-06-18: 'set up the civic side audits like they file taxes too').

Reads config/civic_departments.json (the civic line items mapped to government functions + public
sources + the tools that produce them) and scores each line item's LIVE COVERAGE from its data files
(present? fresh? non-trivial?). Groups by class (Revenue / Expenditure / Governance / Crosswalk /
Forward / Integrity), computes the civic floor, and renders the filing.

Integrity (unchanged): sourced public records only, every finding a QUESTION, private prosecutorial work
never publishes. Public line items render at reports/mauios coverage; the FILING itself is PRIVATE
(reports/_status/civic_books.{json,html}) — it surfaces COVERAGE, never raw private case content.
Stdlib only. Folds into audit_cycle after the prosecutorial fill.
"""
import os, sys, json, html, time
from datetime import datetime, timezone, timedelta

HERE   = os.path.dirname(os.path.abspath(__file__))
HOME   = os.path.expanduser("~")
PROJECT= os.path.join(HOME, "Documents", "Claude", "Projects", "Video System elementLOTUS")
STATUS = os.path.join(PROJECT, "reports", "_status")
CFG    = os.path.join(PROJECT, "config", "civic_departments.json")
HST    = timezone(timedelta(hours=-10))
FRESH_DAYS = 7
esc = lambda s: html.escape(str(s or ""))
def _load(p, d):
    try: return json.load(open(p, encoding="utf-8"))
    except Exception: return d
def now_hst(): return datetime.now(HST)

def _coverage(data_files):
    """Score 0–100 from the line item's data files: presence(50) + freshness(30) + content(20). Honest:
    no files -> 0 (a gap to fill, framed as 'not yet sourced')."""
    if not data_files: return 0, "no data wired"
    present, newest, has_content = 0, 0, 0
    for rel in data_files:
        p = os.path.join(PROJECT, rel)
        if not os.path.isfile(p): continue
        present += 1
        mt = os.path.getmtime(p); newest = max(newest, mt)
        sz = os.path.getsize(p)
        if rel.endswith(".json"):
            j = _load(p, None)
            n = (len(j) if isinstance(j, list) else sum(len(v) for v in j.values() if isinstance(v, (list, dict)))) if j else 0
            if n or sz > 200: has_content += 1
        elif sz > 1500:
            has_content += 1
    if present == 0: return 0, "source not present yet (UIPA / wire it)"
    score = 50
    age_days = (time.time() - newest) / 86400 if newest else 999
    if age_days <= FRESH_DAYS: score += 30
    elif age_days <= 30: score += 15
    if has_content >= present: score += 20
    elif has_content: score += 10
    return min(100, score), "%d/%d source(s) present, freshest %.0fd old%s" % (
        present, len(data_files), age_days, "" if has_content else ", thin")

def build():
    cfg = _load(CFG, {})
    items = []
    for li in cfg.get("line_items", []):
        score, note = _coverage(li.get("data", []))
        items.append({**li, "coverage": score, "cov_note": note})
    by_class = {}
    for x in items: by_class.setdefault(x["class"], []).append(x)
    scored = [x["coverage"] for x in items]
    floor = min(scored) if scored else None
    avg = round(sum(scored) / len(scored)) if scored else None
    gaps = sorted([(x["coverage"], x["code"], x["cov_note"]) for x in items if x["coverage"] < 70])
    summary = {"generated": now_hst().strftime("%Y-%m-%d %H:%M HST"), "civic_floor": floor,
               "civic_avg": avg, "line_items": len(items),
               "gaps": [{"code": c, "coverage": s, "note": n} for s, c, n in gaps]}
    return cfg, by_class, summary

def render_html(cfg, by_class, summary):
    ORDER = ["revenue", "expenditure", "governance", "crosswalk", "forward", "integrity"]
    classes = cfg.get("classes", {})
    def color(s): return "#1f9d55" if s >= 90 else ("#d9822b" if s >= 70 else "#d64545")
    css = ("body{margin:0;background:#0a0f14;color:#e7ecf2;font-family:'Segoe UI',system-ui,sans-serif;line-height:1.5}"
           ".wrap{max-width:1000px;margin:0 auto;padding:24px 18px 60px}"
           ".owner{background:rgba(80,140,210,.12);border:1px solid rgba(80,140,210,.4);border-radius:9px;padding:9px 13px;font:12px Consolas,monospace;color:#9cc4ee;margin-bottom:14px}"
           "h1{font-size:23px;margin:.1em 0;color:#cfe0f4}.sub{color:#7d8a99;font-size:13px;margin-bottom:12px}"
           ".floor{font-size:15px;margin:8px 0}.floor b{color:#1f9d55}"
           "h2{font-size:14px;color:#9fc8f0;margin:22px 0 4px;text-transform:capitalize}.cd{color:#5b6e86;font-weight:400;font-size:12px}"
           "table{width:100%;border-collapse:collapse;font-size:13px;margin-top:4px}"
           "th{text-align:left;color:#5b6e86;font:11px Consolas,monospace;padding:5px 8px;border-bottom:1px solid rgba(255,255,255,.1)}"
           "td{padding:7px 8px;border-bottom:1px solid rgba(255,255,255,.06);vertical-align:top}"
           ".c{font:11px Consolas,monospace;color:#5b6e86}.f{color:#8a97a8;font-size:11.5px;margin-top:2px}.s{color:#8a97a8;font-size:11.5px}.h{font:12px Consolas,monospace;text-align:right}")
    sections = ""
    for cl in ORDER:
        if cl not in by_class: continue
        rows = ""
        for x in by_class[cl]:
            sc = x["coverage"]
            rows += ("<tr><td class=c>" + esc(x["code"]) + "</td><td><b>" + esc(x["name"]) + "</b><div class=f>"
                     + esc(x.get("gov_function","")) + "</div></td><td class=s>" + esc(x.get("source",""))
                     + "</td><td class=h style='color:" + color(sc) + "'>" + str(sc) + "</td></tr>")
        sections += ("<h2>" + esc(cl.title()) + " <span class=cd>" + esc(classes.get(cl,"")) + "</span></h2>"
                     "<table><thead><tr><th>code</th><th>line item · government function</th><th>public source</th>"
                     "<th>coverage</th></tr></thead><tbody>" + rows + "</tbody></table>")
    fl = str(summary["civic_floor"]); av = str(summary["civic_avg"])
    return ("<!DOCTYPE html><html lang=en><head><meta charset=utf-8>"
            "<meta name=viewport content=\"width=device-width,initial-scale=1\">"
            "<title>Civic Books — OWNER ONLY</title><style>" + css + "</style></head><body><div class=wrap>"
            "<div class=owner>\U0001F512 OWNER ONLY · the civic audit filed like a government's chart of accounts. "
            "Coverage only — sourced public records; every finding a question, never an accusation; private case work stays private.</div>"
            "<h1>Civic Books — the audit, by line item</h1>"
            "<div class=sub>Revenue (money in) · Expenditure (money out, by dept) · Governance (decisions) · "
            "Crosswalk (does the spending answer the money?) · Forward · Integrity. " + esc(summary["generated"]) + "</div>"
            "<div class=floor>Civic coverage floor (lowest line item): <b>" + fl + "</b> &middot; average " + av
            + " &middot; " + str(len(summary["gaps"])) + " line item(s) under 70 (source to wire / UIPA)</div>"
            + sections +
            "<footer style=\"margin-top:22px;color:#5b6e86;font:11px Consolas,monospace\">Coverage = presence + "
            "freshness + content of each line item's public-record sources. A low score is a QUESTION — a record to "
            "request, not a fault. · Kilo Aupuni · aloha · pono</footer></div></body></html>")

def main():
    os.makedirs(STATUS, exist_ok=True)
    cfg, by_class, summary = build()
    json.dump({"summary": summary, "classes": cfg.get("classes", {}),
               "line_items": [x for xs in by_class.values() for x in xs]},
              open(os.path.join(STATUS, "civic_books.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    open(os.path.join(STATUS, "civic_books.html"), "w", encoding="utf-8", newline="\n").write(render_html(cfg, by_class, summary))
    print("civic_books: %d line items across %d classes; civic floor=%s avg=%s; %d gap(s) <70 -> reports/_status/civic_books.{json,html} (PRIVATE)" % (
        summary["line_items"], len(by_class), summary["civic_floor"], summary["civic_avg"], len(summary["gaps"])))
    return 0

if __name__ == "__main__":
    sys.exit(main())
