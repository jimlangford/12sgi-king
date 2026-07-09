#!/usr/bin/env python3
"""reports_index.py - the ONE durable link to every report the system finds + refines daily (Jimmy
2026-06-19: "send me an email with links to all of the reports that you find and refine daily").

Scans the private King serve root (king-local) against a curated catalog of the daily-refined owner
reports, keeps only the ones that actually exist (so the index never shows a dead link), and writes:
  - king-local/reports_index.html  -> served PRIVATE at /king/reports_index.html (Tailscale, owner-only)
  - reports/_status/reports_index.json -> the manifest the email builder reads (title + url + group)

PRIVATE / owner-only. The links resolve only on Jimmy's Tailscale-authenticated devices; nothing here
is public. Stdlib only; windowless-safe. Usage: python reports_index.py
"""
import os, sys, json, html
from datetime import datetime, timezone, timedelta

HST = timezone(timedelta(hours=-10))
HOME = os.path.expanduser("~")
PROJ = os.path.join(HOME, "Documents", "Claude", "Projects", "Video System elementLOTUS")
ST = os.path.join(PROJ, "reports", "_status")
KING_DIRS = [os.path.join(HOME, "AppData", "Local", "king-extract", "deploy", "king-local"),
             os.path.join(PROJ, "king-local")]
BASE = "https://12sgianonymous.tail760750.ts.net/king/"
esc = lambda s: html.escape(str(s if s is not None else ""))

# Curated catalog of the daily-refined owner reports. (group, filename, title, one-line description)
CATALOG = [
    ("Prosecutor (owner-only)", "prosecutor_daily.html", "Prosecutor — daily cross-tenant findings",
     "Money×votes, committee dissent, cross-checked testimony & freshest minutes per tenant, with an EDUCATE line + a 'new since yesterday' delta."),
    ("Prosecutor (owner-only)", "prosecutor_dashboard.html", "Cases dashboard — cross-checked + refined",
     "Each money×votes case scored by independent-source corroboration (parity · watchlist · testimony · role); opens in any browser; the daily review email attaches it."),
    ("Prosecutor (owner-only)", "case_files.html", "Case files — the prosecutorial back end",
     "Theory of the case, elements, the sourced evidence chain, an evidence-strength score, and the next record to demand."),
    ("Prosecutor (owner-only)", "casework_maui.html", "Maui money×votes casework",
     "Vendor × donor × decider cases, each a question answered by a named record (EXAMINE / NOTE / likely-coincidence)."),
    ("Prosecutor (owner-only)", "testimony_crosscheck.html", "Cross-checked testimony",
     "Industry testimony corroborated against campaign money and county contracts (≥2 independent public sources)."),
    ("Prosecutor (owner-only)", "accountability_record.html", "Accountability record",
     "The standing public-record accountability ledger."),
    ("Prosecutor (owner-only)", "maui_re_report.html", "Maui real-estate report",
     "Property-transaction lens on the Maui record."),
    ("Civic", "daily_brief.html", "Daily brief",
     "Cross-thread awareness: what's open, missed, blocked, and the carried backlog."),
    ("Civic", "king_message.html", "Daily King message",
     "Aloha + curse-breaker kindness — the prosecutor signal and the moon turned toward a pono path."),
    ("Civic", "agenda_explainer.html", "Agenda explainer",
     "Plain-language explainer of upcoming county agenda items."),
    ("Civic", "agendas_maui.html", "Maui agendas",
     "Upcoming Maui County agenda items (get ahead of the vote)."),
    ("Awareness & system", "system_status.html", "Live system status",
     "Servers, locks, GPU, and attention items — the live operational picture."),
    ("Awareness & system", "daily_learnings.html", "Daily self-heal learnings",
     "What the self-heal learner caught and improved to next-best."),
    ("Awareness & system", "progress_board.html", "Progress board",
     "Cross-lane progress at a glance."),
    ("Awareness & system", "quadrant_progress.html", "Quadrant progress",
     "Per-quadrant (MV · Film · Game · govOS) facet scores."),
    ("Awareness & system", "private_completeness.html", "Private completeness",
     "Owner-side completeness audit of the private surfaces."),
    ("Awareness & system", "onboard_readiness.html", "Onboard readiness",
     "Tenant onboarding readiness."),
    ("Awareness & system", "surface_health.html", "Surface health",
     "Health of every served surface (links, mobile, styling)."),
]


def king_dir():
    for d in KING_DIRS:
        if os.path.isdir(d):
            return d
    return None


def build():
    kd = king_dir()
    if not kd:
        print("reports_index: no king-local dir found", file=sys.stderr)
        return 1
    now = datetime.now(HST).strftime("%Y-%m-%d %H:%M HST")
    groups = {}
    manifest = {"generated": now, "base": BASE, "reports": []}
    for group, fn, title, desc in CATALOG:
        if not os.path.exists(os.path.join(kd, fn)):
            continue
        url = BASE + fn
        groups.setdefault(group, []).append((title, desc, url, fn))
        manifest["reports"].append({"group": group, "title": title, "desc": desc, "url": url, "file": fn})

    # ---- HTML (served private) ----
    sec = []
    for group in ["Prosecutor (owner-only)", "Civic", "Awareness & system"]:
        items = groups.get(group) or []
        if not items:
            continue
        cards = "".join(
            "<a class='rep' href='%s'><div class='rt'>%s</div><div class='rd'>%s</div>"
            "<div class='ru'>%s</div></a>" % (esc(u), esc(t), esc(d), esc(f))
            for (t, d, u, f) in items)
        sec.append("<section><h2>%s</h2>%s</section>" % (esc(group), cards))
    htm = """<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Daily reports — OWNER ONLY</title><style>
 body{margin:0;background:#0a0c10;color:#e8e4d8;font-family:Georgia,'Iowan Old Style',serif;line-height:1.5}
 .wrap{max-width:920px;margin:0 auto;padding:26px 22px 70px}
 .owner{background:rgba(224,106,74,.12);border:1px solid rgba(224,106,74,.4);border-radius:10px;padding:10px 14px;font-family:Consolas,monospace;font-size:12px;color:#e9b48a;margin-bottom:14px}
 .eyebrow{font-family:Consolas,monospace;font-size:11px;letter-spacing:1.4px;color:#d9b24c;text-transform:uppercase}
 h1{font-size:26px;font-weight:600;margin:8px 0 4px} .lead{font-size:13.5px;color:#cfc9b6;max-width:80ch}
 h2{font-size:15px;color:#9fd9bf;font-family:Consolas,monospace;text-transform:uppercase;letter-spacing:1px;margin:22px 0 8px;border-bottom:1px solid rgba(255,255,255,.1);padding-bottom:5px}
 .rep{display:block;border:1px solid rgba(255,255,255,.12);border-radius:11px;padding:12px 15px;margin:9px 0;background:rgba(255,255,255,.02);text-decoration:none;color:inherit}
 .rep:hover{border-color:rgba(159,217,191,.5);background:rgba(42,107,78,.1)}
 .rt{font-size:15.5px;font-weight:600;color:#f0ead8} .rd{font-size:12.5px;color:#cfc9b6;margin:3px 0 5px}
 .ru{font-family:Consolas,monospace;font-size:10.5px;color:#7a8a80}
 footer{margin-top:28px;border-top:1px solid rgba(255,255,255,.1);padding-top:12px;font-family:Consolas,monospace;font-size:10.5px;color:#9a957f}
</style></head><body><div class="wrap">
<div class="owner">🔒 OWNER ONLY · private King (Tailscale) · these links resolve only on your authenticated devices · NOT public.</div>
<div class="eyebrow">12 Stones Global · Kilo Aupuni · daily reports index</div>
<h1>Daily reports</h1>
<p class="lead">Every report the system finds and refines each day, in one place. Refreshed daily;
this page always points to the latest. Prosecutorial detail stays here behind the private link — it
never leaves the laptop.</p>
%s
<footer>generated %s · %d reports · reports_index v1 · OWNER ONLY</footer>
</div></body></html>""" % ("".join(sec), esc(now), len(manifest["reports"]))

    open(os.path.join(kd, "reports_index.html"), "w", encoding="utf-8", newline="\n").write(htm)
    os.makedirs(ST, exist_ok=True)
    open(os.path.join(ST, "reports_index.json"), "w", encoding="utf-8", newline="\n").write(
        json.dumps(manifest, ensure_ascii=False, indent=2))
    print("reports_index: %d reports -> %sreports_index.html" % (len(manifest["reports"]), BASE))
    for r in manifest["reports"]:
        print("   [%s] %s" % (r["group"], r["url"]))
    return 0


if __name__ == "__main__":
    sys.exit(build())
