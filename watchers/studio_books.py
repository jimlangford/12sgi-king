#!/usr/bin/env python3
"""studio_books.py — the STUDIO BOOKS: elementLOTUS rendered as a film studio's departmental ledger
   (Jimmy 2026-06-18: file the system the way a major studio files taxes — departments as line items).

Reads config/studio_departments.json (the chart of accounts) + reports/_status/progressive_selfheal.json
(the live floor per area) and produces a per-department "books" view: each department a line item with its
owner, line items, cost center, outputs, and LIVE HEALTH (score + trend) where it has a health signal.
Computes the studio FLOOR per class + overall, and a cloud_ready flag per department (health held >= 90
across the last N cycles = world-class continuity, the gate Jimmy set before lifting to the cloud).

PRIVATE: writes reports/_status/studio_books.{json,html} (owner-only; never the public site). Stdlib only.
Folds into audit_cycle after progressive_selfheal so the books reflect the freshest floor.
"""
import os, sys, json, html
from datetime import datetime, timezone, timedelta

HERE   = os.path.dirname(os.path.abspath(__file__))
HOME   = os.path.expanduser("~")
PROJECT= os.path.join(HOME, "Documents", "Claude", "Projects", "Video System elementLOTUS")
STATUS = os.path.join(PROJECT, "reports", "_status")
DEPTS  = os.path.join(PROJECT, "config", "studio_departments.json")
SERIES = os.path.join(STATUS, "progressive_selfheal.json")
HST    = timezone(timedelta(hours=-10))
CLOUD_FLOOR = 90          # "world-class" bar
CLOUD_HOLD  = 3           # cycles the floor must hold at/above the bar before a dept is cloud_ready
esc = lambda s: html.escape(str(s or ""))
def _load(p, d):
    try: return json.load(open(p, encoding="utf-8"))
    except Exception: return d
def now_hst(): return datetime.now(HST)

def _area_history(series, area):
    """The scored history for a progressive-selfheal area, oldest->newest (numeric scores only)."""
    return [r for r in series if r.get("area") == area and isinstance(r.get("score"), (int, float))]

def build():
    cfg = _load(DEPTS, {})
    series = _load(SERIES, [])
    classes = cfg.get("classes", {})
    out_depts = []
    for d in cfg.get("departments", []):
        sig = d.get("health_signal")
        health = {"signal": sig, "score": None, "trend": None, "cloud_ready": False, "note": "no health signal (creative/owner dept)"}
        if sig:
            hist = _area_history(series, sig)
            if hist:
                cur = hist[-1]["score"]; prev = hist[-2]["score"] if len(hist) > 1 else None
                recent = [h["score"] for h in hist[-CLOUD_HOLD:]]
                cloud = len(recent) >= CLOUD_HOLD and all(s >= CLOUD_FLOOR for s in recent)
                health = {"signal": sig, "score": cur, "trend": (None if prev is None else cur - prev),
                          "cloud_ready": cloud,
                          "note": ("world-class continuity (held >=%d for %d cycles)" % (CLOUD_FLOOR, CLOUD_HOLD)) if cloud
                                  else ("floor %s — proving continuity" % cur)}
            else:
                health["note"] = "signal '%s' not scored yet (run progressive_selfheal)" % sig
        out_depts.append({**d, "health": health})
    # studio floor = min live score across departments that HAVE a signal
    scored = [x["health"]["score"] for x in out_depts if isinstance(x["health"]["score"], (int, float))]
    floor = min(scored) if scored else None
    by_class = {}
    for x in out_depts:
        by_class.setdefault(x["class"], []).append(x)
    summary = {"generated": now_hst().strftime("%Y-%m-%d %H:%M HST"),
               "studio_floor": floor,
               "cloud_ready_departments": [x["code"] for x in out_depts if x["health"]["cloud_ready"]],
               "departments_total": len(out_depts)}
    return cfg, classes, by_class, summary

def render_html(cfg, classes, by_class, summary):
    ORDER = ["above_the_line", "production", "post", "distribution", "ga"]
    def arrow(t): return "" if t in (None,) else (" ▲+%d" % t if t > 0 else (" ▼%d" % t if t < 0 else " ="))
    def color(s): return "#1f9d55" if (isinstance(s,(int,float)) and s>=90) else ("#d9822b" if (isinstance(s,(int,float)) and s>=70) else ("#d64545" if isinstance(s,(int,float)) else "#9a957f"))
    sections = ""
    for cl in ORDER:
        if cl not in by_class: continue
        rows = ""
        for d in by_class[cl]:
            h = d["health"]; sc = h["score"]
            badge = ("<span style='color:#1f9d55'>☁ cloud-ready</span>" if h["cloud_ready"]
                     else ("<span style='color:%s'>%s%s</span>" % (color(sc), (str(sc) if sc is not None else "—"), arrow(h["trend"]))))
            rows += ("<tr><td class=c>%s</td><td><b>%s</b><div class=li>%s</div></td><td class=o>%s</td>"
                     "<td class=cc>%s</td><td class=h>%s</td></tr>") % (
                esc(d["code"]), esc(d["name"]), esc(" · ".join(d.get("line_items", [])[:6])),
                esc(d.get("owner","")), esc(d.get("cost_center","")), badge)
        sections += ("<h2>%s <span class=cd>%s</span></h2><table><thead><tr><th>code</th><th>department · line items</th>"
                     "<th>owner</th><th>cost center</th><th>health</th></tr></thead><tbody>%s</tbody></table>") % (
            esc(cl.replace("_"," ").title()), esc(classes.get(cl,"")), rows)
    css = ("body{margin:0;background:#0e1311;color:#e8e4d6;font-family:-apple-system,Segoe UI,Roboto,sans-serif;line-height:1.5}"
           ".wrap{max-width:1000px;margin:0 auto;padding:24px 18px 60px}"
           ".owner{background:rgba(224,106,74,.12);border:1px solid rgba(224,106,74,.4);border-radius:9px;padding:9px 13px;font:12px Consolas,monospace;color:#e9b48a;margin-bottom:14px}"
           "h1{font-size:23px;margin:.1em 0}.sub{color:#9a957f;font-size:13px;margin-bottom:14px}"
           "h2{font-size:14px;color:#9fd9bf;margin:22px 0 4px;text-transform:capitalize}.cd{color:#7d8a99;font-weight:400;font-size:12px}"
           "table{width:100%;border-collapse:collapse;font-size:13px;margin-top:4px}"
           "th{text-align:left;color:#7d8a99;font:11px Consolas,monospace;padding:5px 8px;border-bottom:1px solid rgba(255,255,255,.1)}"
           "td{padding:7px 8px;border-bottom:1px solid rgba(255,255,255,.06);vertical-align:top}"
           ".c{font:11px Consolas,monospace;color:#9a957f}.li{color:#9a957f;font-size:11.5px;margin-top:2px}.o{color:#bdb8a4;font-size:12px}.cc{color:#9a957f;font-size:11.5px}.h{font:12px Consolas,monospace;text-align:right}"
           ".floor{font-size:15px;color:#e8e4d6;margin:8px 0}.floor b{color:#1f9d55}")
    fl = str(summary["studio_floor"])
    cready = esc(", ".join(summary["cloud_ready_departments"]) or "none yet (proving continuity)")
    return ("<!DOCTYPE html><html lang=en><head><meta charset=utf-8>"
            "<meta name=viewport content=\"width=device-width,initial-scale=1\">"
            "<title>Studio Books — OWNER ONLY</title><style>" + css + "</style></head><body><div class=wrap>"
            "<div class=owner>\U0001F512 OWNER ONLY · the studio's books — every part of elementLOTUS as a film-studio "
            "department. PRIVATE, never published.</div>"
            "<h1>Studio Books — departments &amp; line items</h1>"
            "<div class=sub>elementLOTUS filed the way a major studio files: Above-the-Line · Production · Post · "
            "Distribution · G&amp;A. " + esc(summary["generated"]) + " · floor " + fl + "</div>"
            "<div class=floor>Studio floor (lowest live department health): <b>" + fl + "</b> &middot; "
            "cloud-ready departments: " + cready + "</div>"
            + sections +
            "<footer style=\"margin-top:22px;color:#9a957f;font:11px Consolas,monospace\">Health = the progressive "
            "self-heal floor per area (audit quad-os). A department goes ☁ cloud-ready only when its floor holds &ge;"
            + str(CLOUD_FLOOR) + " for " + str(CLOUD_HOLD) + " cycles — prove world-class continuity locally, then lift "
            "it to the cloud. · Kilo Aupuni</footer></div></body></html>")

def main():
    os.makedirs(STATUS, exist_ok=True)
    cfg, classes, by_class, summary = build()
    json.dump({"summary": summary, "classes": classes,
               "departments": [d for ds in by_class.values() for d in ds]},
              open(os.path.join(STATUS, "studio_books.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    open(os.path.join(STATUS, "studio_books.html"), "w", encoding="utf-8", newline="\n").write(render_html(cfg, classes, by_class, summary))
    print("studio_books: %d departments across %d classes; studio floor=%s; cloud-ready=%s -> reports/_status/studio_books.{json,html} (PRIVATE)" % (
        summary["departments_total"], len(by_class), summary["studio_floor"],
        (", ".join(summary["cloud_ready_departments"]) or "none yet")))
    return 0

if __name__ == "__main__":
    sys.exit(main())
