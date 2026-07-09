#!/usr/bin/env python3
# tenant_pages.py - per-tenant pages + the simplified tenant-picker landing (hub).
#   gen(tenant)      -> reports/mauios/tenant_<id>.html : that tenant's own page, listing
#                       the lenses it has (links to existing dashboards) + honest "pending".
#   build_hub(list)  -> reports/mauios/tenants_hub.html : the SIMPLE landing - pick a
#                       government, enter its pages. (Maui-level detail per tenant as data fills.)
# Public-safe: links only to question-framed dashboards; prosecutorial case files are never linked.
import json, os
from datetime import datetime, timedelta, timezone

HOME = os.path.expanduser("~")
PROJECT = os.path.join(HOME, "Documents", "Claude", "Projects", "Video System elementLOTUS")
M = os.path.join(PROJECT, "reports", "mauios")
HST = timezone(timedelta(hours=-10))

def esc(s): return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
def exists(fn): return os.path.exists(os.path.join(M, fn))
import tenant_depth as TD          # one source of truth for the testimony dimensions + per-tenant file map
import tenant_directory as _tdir   # the fresh Yale-navy .govos design tokens — ONE shared register (2026-07-09)
TD_CSS = _tdir.CSS
def short(tid): return tid.replace("hi-", "").replace("ny", "ny")

# The lens menu per tenant short-id: (label, filename). Filenames already produced by the
# watchers; gen() shows present ones as links and absent ones as "pending (ingesting)".
LENSES = {
    "maui": [("County dashboard", "county_dashboard.html"), ("Officials scorecard", "officials_scorecard.html"),
             ("Money behind officials", "money_behind_officials.html"), ("County contracts", "maui_contract_awards.html"),
             ("Federal dollars", "federal_money.html"), ("Contracts × donors", "contracts_x_donors.html"),
             ("Upcoming agendas", "agendas_maui.html"), ("Charter ⇔ Law", "crosswalk_maui.html"),
             ("Audit balance", "audit_balance.html")],
    "state": [("Statewide money patterns", "statewide_money_patterns.html"),
              # source lives at lege/ (subdir); build_site.py flattens "/"->"_" when publishing, so the
              # served href is lege_legislator_scorecard.html. 3rd tuple element = published href.
              ("Legislator scorecard", "lege/legislator_scorecard.html", "lege_legislator_scorecard.html"),
              ("Federal dollars", "federal_money.html"),
              ("Upcoming agendas", "agendas_state.html"), ("Charter ⇔ Law", "crosswalk_state.html"),
              ("Audit balance", "audit_balance.html")],
    "hawaii": [("Upcoming agendas", "agendas_hawaii.html"), ("Statewide money patterns", "statewide_money_patterns.html"),
               ("Charter ⇔ Law", "crosswalk_hawaii.html"), ("Audit balance", "audit_balance.html")],
    "kauai": [("Upcoming agendas", "agendas_kauai.html"), ("Statewide money patterns", "statewide_money_patterns.html"),
              ("Charter ⇔ Law", "crosswalk_kauai.html"), ("Audit balance", "audit_balance.html")],
    "honolulu": [("Upcoming agendas", "agendas_honolulu.html"), ("Statewide money patterns", "statewide_money_patterns.html"),
                 ("Charter ⇔ Law", "crosswalk_honolulu.html"), ("Audit balance", "audit_balance.html")],
    "ny": [("Upcoming agendas", "agendas_nyc.html")],
}

# UNIFIED DESIGN (2026-07-09, Jimmy "rethought with the new audit profiles"): every tenant page now shares
# ONE register — tenant_directory.CSS (the .govos tokens + .tile/.sec/.grid classes) + tenant_depth.PROFILE_CSS
# (the .pcard audit-dimension cards). HUB_CSS below is the small addendum just for tenants_hub.html's
# government-picker cards (name + code + progress bar), reusing the same custom properties.
HUB_CSS = """
.govos .gc-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:12px;margin:20px 0}
.govos .gcard{display:block;padding:16px 17px;border-radius:14px;border:1px solid var(--glass-line);
  background:var(--glass-bg);box-shadow:var(--glass-shadow);-webkit-backdrop-filter:blur(14px) saturate(1.15);
  backdrop-filter:blur(14px) saturate(1.15);text-decoration:none;color:var(--ink);transition:.16s}
.govos .gcard:hover{border-color:var(--blue-2);transform:translateY(-2px);color:#fff}
.govos .gc-top{display:flex;align-items:center;justify-content:space-between;gap:8px;margin-bottom:10px}
.govos .gc-name{font-weight:650;font-size:15px}
.govos .bar{height:7px;border-radius:99px;background:var(--line);overflow:hidden;margin-bottom:8px}
.govos .bar span{display:block;height:100%;background:linear-gradient(90deg,var(--ok),var(--blue-2))}
.govos .gc-meta{color:var(--ink-dim);font-size:12.5px}
"""

def depth_of(tid):
    """(covered, total) civic questions answered for this tenant — shared with the hub + depth sweep."""
    covered = sum(1 for k, _l, _d in TD.DIMS if TD.cell_status(tid, k)[0] == "ok")
    return covered, len(TD.DIMS)

# UNIFIED CARD DESIGN (2026-07-09, Jimmy "rethought with the new audit profiles"): every tenant page
# renders through tenant_depth.profile_cards_html() — the SAME function maui.html's directory uses (via
# tenant_directory.page_html's profile_html slot) — so there is exactly one audit-profile card design,
# never two that can quietly drift apart. This page adds the fresh-navy .govos wrapper (tenant_directory.CSS)
# + a lightweight "other pages" section from LENSES for pages outside the 12 core dimensions.
def gen(t):
    os.makedirs(M, exist_ok=True)
    tid = t["id"]
    profile = TD.profile_cards_html(tid, esc=esc)
    covered, total = depth_of(tid)
    lens_items = []
    for entry in LENSES.get(short(tid), []):
        lbl, src_fn = entry[0], entry[1]
        pub_fn = entry[2] if len(entry) > 2 else src_fn   # published (flattened) href when it differs
        if exists(src_fn) or exists(pub_fn):
            lens_items.append((lbl, pub_fn))
    other = ""
    if lens_items:
        tiles = "".join('<a class="tile" href="%s"><span>%s</span><span class="go">&rarr;</span></a>'
                        % (esc(fn), esc(lbl)) for lbl, fn in lens_items)
        other = ('<section class="sec"><h2>Other pages <span class="n">%d</span></h2>'
                '<div class="grid">%s</div></section>' % (len(lens_items), tiles))
    # real <html>/<head>/<body> structure (2026-07-09 heal-audit fix) so inject_nav's <body[^>]*> regex
    # matches and inserts the standing nav INSIDE the page, never prepended before a body-less doctype.
    html = (f"<!doctype html><html lang=en><head><meta charset=utf-8>"
            f"<meta name=viewport content='width=device-width,initial-scale=1'>"
            f"<title>{esc(t['name'])} | govOS</title><style>{TD_CSS}{TD.PROFILE_CSS}</style></head>"
            f"<body class=govos><div class=wrap>"
            f"<div class=eyebrow><a href='tenants_hub.html'>govOS</a> · tenant {esc(t['code'])}</div>"
            f"<h1>{esc(t['name'])}</h1>"
            f"<p class=sub>The public record for {esc(t['name'])}, organized by the questions that matter most. "
            f"Each is framed for oversight, never accusation — and the prosecutorial files stay private.</p>"
            f"{profile}{other}"
            f"<p class=sub style='margin-top:24px'><a href='tenants_hub.html'>&larr; all governments</a> "
            f"&middot; <a href='maui.html'>Maui — every page &rarr;</a></p>"
            f"</div></body></html>")
    with open(os.path.join(M, f"tenant_{tid}.html"), "w", encoding="utf-8") as f:
        f.write(html)

def build_hub(ts):
    os.makedirs(M, exist_ok=True)
    # deepest first, so people see the fullest record at the top
    ordered = sorted(ts, key=lambda t: -depth_of(t["id"])[0])
    cards = []
    for t in ordered:
        covered, total = depth_of(t["id"]); pct = round(100 * covered / total)
        cards.append(
            f'<a class=gcard href="tenant_{esc(t["id"])}.html"><div class=gc-top>'
            f'<span class=gc-name>{esc(t["name"])}</span><span class="pill">{esc(t["code"])}</span></div>'
            f'<div class=bar><span style="width:{pct}%"></span></div>'
            f'<div class=gc-meta>{covered}/{total} audit-profile questions answered</div></a>')
    gen_ts = datetime.now(HST).strftime("%Y-%m-%d %H:%M HST")
    # real <html>/<head>/<body> structure (2026-07-09 heal-audit fix, see CSS comment above)
    html = (f"<!doctype html><html lang=en><head><meta charset=utf-8>"
            f"<meta name=viewport content='width=device-width,initial-scale=1'>"
            f"<title>govOS — Governments | Kilo Aupuni</title><style>{TD_CSS}{HUB_CSS}</style></head>"
            f"<body class=govos><div class=wrap>"
            f"<div class=hero><div class=eyebrow>govOS &middot; Kilo Aupuni</div>"
            f"<h1>Pick your <span class=u>government</span></h1>"
            f"<p class=sub>One civic engine, many governments. Choose one to see its public record in plain words — "
            f"who governs, where the money comes from, who gets the contracts — each a question for oversight, "
            f"never an accusation. The bar shows how complete each government's audit profile is; Maui is the "
            f"deepest, and the others fill in as their public records are gathered.</p></div>"
            f"<div class=gc-grid>{''.join(cards)}</div>"
            f"<p class=sub style='margin-top:20px'>Generated {esc(gen_ts)}. Facts and sourced questions only — "
            f"never accusations. Prosecutorial files stay private.</p>"
            f"</div></body></html>")
    with open(os.path.join(M, "tenants_hub.html"), "w", encoding="utf-8") as f:
        f.write(html)

if __name__ == "__main__":
    ts = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "tenants.json"), encoding="utf-8"))["tenants"]
    for t in ts: gen(t)
    build_hub(ts)
    print(f"generated {len(ts)} tenant pages + tenants_hub.html -> {M}")
