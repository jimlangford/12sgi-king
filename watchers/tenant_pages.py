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
              ("Legislator scorecard", "lege/legislator_scorecard.html"), ("Federal dollars", "federal_money.html"),
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

CSS = ("body{font-family:system-ui,Segoe UI,sans-serif;max-width:980px;margin:2.2rem auto;padding:0 1.1rem;color:#15212e}"
       "a{color:#0b6bcb;text-decoration:none}a:hover{text-decoration:underline}"
       ".eyebrow{font-size:.72rem;letter-spacing:.16em;text-transform:uppercase;color:#6b7a89}"
       "h1{font-size:1.7rem;margin:.2rem 0 .1rem}.sub{color:#56646f;font-size:.95rem}"
       ".grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:.8rem;margin:1.3rem 0}"
       ".card{border:1px solid #e1e7ec;border-radius:13px;padding:1rem 1.1rem;background:#fafcfe}"
       ".card h3{margin:.1rem 0 .3rem;font-size:1.05rem}.card .d{color:#6b7a89;font-size:.82rem}"
       ".pill{display:inline-block;font-size:.68rem;padding:.12rem .5rem;border-radius:99px;background:#eef3f7;color:#42535f;margin-left:.4rem}"
       ".lens{display:flex;justify-content:space-between;padding:.5rem .2rem;border-bottom:1px solid #eef2f5}"
       ".pending{color:#9aa6b1;font-style:italic}")

def gen(t):
    os.makedirs(M, exist_ok=True)
    sid = short(t["id"]); lenses = LENSES.get(sid, [])
    items = []
    for label, fn in lenses:
        if exists(fn):
            items.append(f'<div class=lens><a href="{esc(fn)}">{esc(label)}</a><span>ready</span></div>')
        else:
            items.append(f'<div class=lens><span>{esc(label)}</span><span class=pending>pending (ingesting)</span></div>')
    html = (f"<!doctype html><meta charset=utf-8><title>{esc(t['name'])} | govOS</title><style>{CSS}</style>"
            f"<div class=eyebrow>govOS · tenant {esc(t['code'])}</div>"
            f"<h1>{esc(t['name'])}<span class=pill>{esc(t['depth'])}</span></h1>"
            f"<div class=sub>In plain words: every public record we track for {esc(t['name'])} — agendas, "
            f"money, contracts, federal dollars — each framed as a question for oversight, never an accusation. "
            f"Prosecutorial files are kept private. <a href='tenants_hub.html'>← all governments</a></div>"
            f"<div style='margin:1.2rem 0'>{''.join(items)}</div>"
            f"<p class=sub>Lenses: {esc(', '.join(t.get('lenses', [])))}.</p>")
    with open(os.path.join(M, f"tenant_{t['id']}.html"), "w", encoding="utf-8") as f:
        f.write(html)

def build_hub(ts):
    os.makedirs(M, exist_ok=True)
    cards = []
    for t in ts:
        pub = "public" if t.get("publish") else "private"
        cards.append(
            f'<a class=card href="tenant_{esc(t["id"])}.html"><h3>{esc(t["name"])}'
            f'<span class=pill>{esc(t["code"])}</span></h3>'
            f'<div class=d>{esc(", ".join(t.get("lenses", [])[:3]))}…</div>'
            f'<div class=d style="margin-top:.4rem">{esc(t["depth"])} · {pub}</div></a>')
    gen_ts = datetime.now(HST).strftime("%Y-%m-%d %H:%M HST")
    html = (f"<!doctype html><meta charset=utf-8><title>govOS — Governments | Kilo Aupuni</title><style>{CSS}</style>"
            f"<div class=eyebrow>govOS · Kilo Aupuni</div>"
            f"<h1>Choose a government</h1>"
            f"<div class=sub>One civic engine, many governments. Pick a tenant to see its public record — "
            f"agendas, money, contracts, and federal dollars — each a question for oversight. "
            f"Maui is the deepest; the others fill as their watchers run.</div>"
            f"<div class=grid>{''.join(cards)}</div>"
            f"<p class=sub>Generated {esc(gen_ts)}. Facts + sourced questions, never accusations. "
            f"Prosecutorial files stay private.</p>")
    with open(os.path.join(M, "tenants_hub.html"), "w", encoding="utf-8") as f:
        f.write(html)

if __name__ == "__main__":
    ts = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "tenants.json"), encoding="utf-8"))["tenants"]
    for t in ts: gen(t)
    build_hub(ts)
    print(f"generated {len(ts)} tenant pages + tenants_hub.html -> {M}")
