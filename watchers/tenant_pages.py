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
import tenant_depth as TD   # one source of truth for the 8 testimony dimensions + per-tenant file map
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

CSS = ("body{font-family:system-ui,Segoe UI,sans-serif;max-width:980px;margin:2.2rem auto;padding:0 1.1rem;color:#15212e}"
       "a{color:#0b6bcb;text-decoration:none}a:hover{text-decoration:underline}"
       ".eyebrow{font-size:.72rem;letter-spacing:.16em;text-transform:uppercase;color:#6b7a89}"
       "h1{font-size:1.7rem;margin:.2rem 0 .1rem}.sub{color:#56646f;font-size:.95rem}"
       ".grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:.8rem;margin:1.3rem 0}"
       ".card{border:1px solid #e1e7ec;border-radius:13px;padding:1rem 1.1rem;background:#fafcfe}"
       ".card h3{margin:.1rem 0 .3rem;font-size:1.05rem}.card .d{color:#6b7a89;font-size:.82rem}"
       ".pill{display:inline-block;font-size:.68rem;padding:.12rem .5rem;border-radius:99px;background:#eef3f7;color:#42535f;margin-left:.4rem}"
       ".lens{display:flex;justify-content:space-between;padding:.5rem .2rem;border-bottom:1px solid #eef2f5}"
       ".pending{color:#9aa6b1;font-style:italic;font-size:.8rem}"
       # friendlier question-grid + depth bar
       ".depth{display:flex;align-items:center;gap:.6rem;margin:.6rem 0 1rem;color:#42535f;font-size:.9rem}"
       ".bar{flex:0 0 160px;height:9px;border-radius:99px;background:#e7edf2;overflow:hidden}"
       ".bar span{display:block;height:100%;background:linear-gradient(90deg,#1f9d55,#0b6bcb)}"
       ".qs{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:.7rem;margin:1.1rem 0}"
       ".q{display:block;border:1px solid #e1e7ec;border-radius:13px;padding:.9rem 1rem;background:#fafcfe}"
       ".q.off{background:#f6f8fa;border-style:dashed;color:#9aa6b1}"
       ".ql{font-weight:650;font-size:1rem;color:#15212e}.q.off .ql{color:#8b99a6}"
       ".qd{color:#6b7a89;font-size:.8rem;margin:.2rem 0 .5rem}"
       ".go{color:#0b6bcb;font-size:.82rem;font-weight:600}"
       ".meter{flex:0 0 56px;height:7px;border-radius:99px;background:#e7edf2;overflow:hidden;display:inline-block}"
       ".meter span{display:block;height:100%;background:linear-gradient(90deg,#1f9d55,#0b6bcb)}")

def depth_of(tid):
    """(covered, total) civic questions answered for this tenant — shared with the hub + depth sweep."""
    covered = sum(1 for k, _l, _d in TD.DIMS if TD.cell_status(tid, k)[0] == "ok")
    return covered, len(TD.DIMS)

def gen(t):
    os.makedirs(M, exist_ok=True)
    tid = t["id"]
    cards = []
    for key, label, desc in TD.DIMS:        # navigate by QUESTION, not filename
        st, fn = TD.cell_status(tid, key)
        if st == "ok":
            href = fn.replace("/", "_")     # build_site flattens subdir paths when publishing
            cards.append(f'<a class=q href="{esc(href)}"><div class=ql>{esc(label)}</div>'
                         f'<div class=qd>{esc(desc)}</div><div class=go>View the record →</div></a>')
        elif fn:                            # page exists but the record is still being gathered (honest, sourced)
            href = fn.replace("/", "_")
            cards.append(f'<a class=q href="{esc(href)}"><div class=ql>{esc(label)}</div>'
                         f'<div class=qd>{esc(desc)}</div><div class=go>See the source · gathering →</div></a>')
        else:
            cards.append(f'<div class="q off"><div class=ql>{esc(label)}</div>'
                         f'<div class=qd>{esc(desc)}</div>'
                         f'<div class=pending>building — added as {esc(t["name"])}’s public records are ingested</div></div>')
    covered, total = depth_of(tid); pct = round(100 * covered / total)
    tag = "complete coverage" if covered >= total else f"{total - covered} more to full depth"
    html = (f"<!doctype html><meta charset=utf-8><title>{esc(t['name'])} | govOS</title><style>{CSS}</style>"
            f"<div class=eyebrow><a href='tenants_hub.html'>govOS</a> · tenant {esc(t['code'])}</div>"
            f"<h1>{esc(t['name'])}</h1>"
            f"<div class=depth><span class=bar><span style='width:{pct}%'></span></span>"
            f"<span><b>{covered} of {total}</b> civic questions answered · {tag}</span></div>"
            f"<div class=sub>The public record for {esc(t['name'])}, organized by the questions that matter most. "
            f"Each is framed for oversight, never accusation — and the prosecutorial files stay private.</div>"
            f"<div class=qs>{''.join(cards)}</div>"
            f"<p class=sub><a href='tenants_hub.html'>← all governments</a></p>")
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
            f'<a class=card href="tenant_{esc(t["id"])}.html"><h3>{esc(t["name"])}'
            f'<span class=pill>{esc(t["code"])}</span></h3>'
            f'<div class=depth style="margin:.3rem 0"><span class=meter><span style="width:{pct}%"></span></span>'
            f'<span class=d>{covered}/{total} questions</span></div>'
            f'<div class=d>Agendas, money, contracts, federal dollars — what you can see for {esc(t["name"])}.</div></a>')
    gen_ts = datetime.now(HST).strftime("%Y-%m-%d %H:%M HST")
    html = (f"<!doctype html><meta charset=utf-8><title>govOS — Governments | Kilo Aupuni</title><style>{CSS}</style>"
            f"<div class=eyebrow>govOS · Kilo Aupuni</div>"
            f"<h1>Pick your government</h1>"
            f"<div class=sub>One civic engine, many governments. Choose one to see its public record in plain words — "
            f"who governs, where the money comes from, who gets the contracts — each a question for oversight, "
            f"never an accusation. The bar shows how complete each government’s record is; Maui is the deepest, "
            f"and the others fill in as their public records are gathered.</div>"
            f"<div class=grid>{''.join(cards)}</div>"
            f"<p class=sub>Generated {esc(gen_ts)}. Facts and sourced questions only — never accusations. "
            f"Prosecutorial files stay private.</p>")
    with open(os.path.join(M, "tenants_hub.html"), "w", encoding="utf-8") as f:
        f.write(html)

if __name__ == "__main__":
    ts = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "tenants.json"), encoding="utf-8"))["tenants"]
    for t in ts: gen(t)
    build_hub(ts)
    print(f"generated {len(ts)} tenant pages + tenants_hub.html -> {M}")
