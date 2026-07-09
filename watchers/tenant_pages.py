#!/usr/bin/env python3
# tenant_pages.py - per-tenant pages + the simplified tenant-picker landing (hub).
#   gen(tenant)      -> reports/mauios/tenant_<id>.html : that tenant's OWN complete page —
#                       audit-profile cards + its FULL page directory, auto-discovered.
#   build_hub(list)  -> reports/mauios/tenants_hub.html : the SIMPLE landing - pick a
#                       government, enter its pages.
# EVERY tenant renders through the SAME function with the SAME structure (2026-07-09, Jimmy: "I don't
# want Maui's cards different looking from other tenants, that is a system error based on the old
# MauiOS" — govOS treats every tenant identically; Maui just naturally has more real pages today).
# Public-safe: links only to question-framed dashboards; prosecutorial case files are never linked.
import json, os, glob
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

# GENERIC PER-TENANT DIRECTORY (2026-07-09): the SAME auto-discovery mechanism for every tenant — no
# tenant gets a hand-maintained "every page" list (that's how 4 real Maui pages went silently missing
# earlier the same day) and no tenant gets a structurally different page. A page is this tenant's if its
# filename carries the tenant's TOKEN; a handful of shared-name pages (county_dashboard.html etc.) don't
# carry a token at all, so a small CURATED_EXTRA fills those in — honestly empty for tenants that don't
# have their own yet, never fabricated.
TENANT_TOKENS = {
    "hi-maui": ["maui"], "hi-state": ["state"], "hi-hawaii": ["hawaii"],
    "hi-kauai": ["kauai"], "hi-honolulu": ["honolulu"], "ny": ["nyc", "nys"],
}
CURATED_EXTRA = {
    "hi-maui": [
        ("county_dashboard.html", "County dashboard", "Start here"),
        ("aloha_aina.html", "Aloha ʻĀina", "Start here"),
        ("officials_scorecard.html", "Officials scorecard", "Who governs"),
        ("rep_audit.html", "Audit by representative", "Who governs"),
        ("donor_bloc.html", "The donor bloc", "Who governs"),
        ("ka_leo_voice.html", "Ka Leo — the louder voice", "Who governs"),
        ("money_behind_officials.html", "Money behind officials", "Follow the money"),
        ("federal_money.html", "Federal dollars", "Follow the money"),
        ("contracts_x_donors.html", "Contracts × donors", "Money × votes"),
        ("testimony_effect_map.html", "Testimony effect map", "Money × votes"),
        ("lobby_money_watch.html", "Lobby + money", "Money × votes"),
        ("parity_check.html", "Pairs that no longer answer", "Money × votes"),
        ("audit_balance.html", "Audit balance", "Audit & oversight"),
    ],
}
# (needle-in-filename, category label) tried in order, first match wins — same rules for every tenant.
CATEGORY_RULES = [
    ("dept_", "Departments"),
    ("entity_", "Entities & orgs"), ("orgs_", "Entities & orgs"), ("connections_", "Entities & orgs"),
    ("crosswalk_", "Charter & law"),
    ("agendas_", "Agendas & meetings"), ("meetings_", "Agendas & meetings"),
    ("archive_", "Agendas & meetings"), ("sunshine_", "Agendas & meetings"),
    ("minutes_", "The record"), ("council_votes", "The record"),
    ("govos_audit_", "Audit & oversight"), ("oversight_", "Audit & oversight"),
    ("money_chain", "Money × votes"), ("nonprofit", "Follow the money"), ("subcontract", "Follow the money"),
    ("realestate_", "Follow the money"), ("contract_awards", "Follow the money"),
    ("contract", "Follow the money"), ("money_", "Follow the money"),
    ("parcel_map", "Maps"), ("_map", "Maps"),
]
CAT_ORDER = ["Start here", "Who governs", "Departments", "Follow the money", "Money × votes",
            "Agendas & meetings", "The record", "Entities & orgs", "Charter & law",
            "Audit & oversight", "Maps", "More"]
_SKIP_SELF = ("tenant_", "tenants_hub.html", "maui.html")

def _categorize(fn):
    low = fn.lower()
    for needle, label in CATEGORY_RULES:
        if needle in low:
            return label
    return "More"

def directory_sections(tid):
    """Every real page for this tenant — curated extras + token-based auto-discovery, existence-filtered,
    de-duplicated, grouped in a fixed category order. Returns [(category, [(label, filename), ...]), ...]."""
    seen, groups = set(), {}
    def add(fn, label, cat):
        if not fn or fn in seen or not exists(fn):
            return
        seen.add(fn)
        groups.setdefault(cat, []).append((label, fn))
    for fn, label, cat in CURATED_EXTRA.get(tid, []):
        add(fn, label, cat)
    for tok in TENANT_TOKENS.get(tid, []):
        for fpath in glob.glob(os.path.join(M, "*%s*.html" % tok)):
            fn = os.path.basename(fpath)
            if fn in seen or fn.startswith(_SKIP_SELF):
                continue
            label = fn[:-5].replace("_" + tok, " ").replace(tok + "_", " ").replace("_", " ").strip().title() or fn
            add(fn, label, _categorize(fn))
    return [(c, groups[c]) for c in CAT_ORDER if c in groups]

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

# UNIFIED PAGE (2026-07-09, Jimmy "I don't want Maui's cards different looking from other tenants, that
# is a system error based on the old MauiOS"): every tenant — Maui included, NO special case — renders
# through this ONE function: audit-profile cards (tenant_depth.profile_cards_html) + its full page
# directory (directory_sections, auto-discovered). Structure is identical everywhere; only the DATA
# differs, honestly, by how much of the public record each tenant actually has ingested so far.
def gen(t):
    os.makedirs(M, exist_ok=True)
    tid = t["id"]
    profile = TD.profile_cards_html(tid, esc=esc)
    covered, total = depth_of(tid)
    sections = directory_sections(tid)
    page_total = sum(len(items) for _c, items in sections)
    other = "".join(
        '<section class="sec"><h2>%s <span class="n">%d</span></h2><div class="grid">%s</div></section>'
        % (esc(cat), len(items),
           "".join('<a class="tile" href="%s"><span>%s</span><span class="go">&rarr;</span></a>'
                   % (esc(fn), esc(lbl)) for lbl, fn in items))
        for cat, items in sections)
    # real <html>/<head>/<body> structure (2026-07-09 heal-audit fix) so inject_nav's <body[^>]*> regex
    # matches and inserts the standing nav INSIDE the page, never prepended before a body-less doctype.
    html = (f"<!doctype html><html lang=en><head><meta charset=utf-8>"
            f"<meta name=viewport content='width=device-width,initial-scale=1'>"
            f"<title>{esc(t['name'])} | govOS</title><style>{TD_CSS}{TD.PROFILE_CSS}</style></head>"
            f"<body class=govos><div class=wrap>"
            f"<div class=eyebrow><a href='tenants_hub.html'>govOS</a> · tenant {esc(t['code'])} · {page_total} pages</div>"
            f"<h1>{esc(t['name'])}</h1>"
            f"<p class=sub>The public record for {esc(t['name'])}, organized by the questions that matter most. "
            f"Each is framed for oversight, never accusation — and the prosecutorial files stay private.</p>"
            f"{profile}{other}"
            f"<p class=sub style='margin-top:24px'><a href='tenants_hub.html'>&larr; all governments</a></p>"
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
