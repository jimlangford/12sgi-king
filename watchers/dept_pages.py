#!/usr/bin/env python3
"""dept_pages.py — the govOS DEPARTMENT-AS-FUNCTION layer for the Maui tenant.

The civic audit found Maui's biggest "not in full" gap: all 18 departments existed in
config/maui_departments.json as name+blurb, but their links pointed at GENERIC shared pages
(audit_balance, maui_contract_awards) — no department-SCOPED view. The govOS Managing-Director
vision (each department is a real function the people can see) was unrealized.

This generator gives EACH of the 18 Maui departments its own page:
  • the people-first "what this department does" header (sourced from config/maui_departments.json),
  • its serve / record / audit links (where they exist),
  • a DEPARTMENT-SCOPED CONTRACTS slice — real county awards from reports/mauios/hands_maui_awards.json
    matched to the department BY SUBJECT KEYWORD (the method is stated on the page; nothing invented;
    a department with no subject-matched contract honestly shows 0, not fake data).

Plus a departments_maui.html INDEX that links all 18 (so none is an orphan) and is itself linked
from the Maui hub. Output -> reports/mauios/dept_<id>_maui.html + departments_maui.html. build_site.py
copies these (added to EXTRA_PAGES) and injects the shared nav + civic_shell chrome.

Sourced-only (Jimmy doctrine): the contracts are the real awards file; the dept↔contract match is a
transparent keyword rule shown to the reader; no figure is fabricated. Stdlib only.
"""
import os, json, html, re
from datetime import datetime, timezone, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.abspath(os.path.join(HERE, "..", ".."))
MAUIOS = os.path.join(PROJ, "reports", "mauios")
DEPTS_CFG = os.path.join(PROJ, "config", "maui_departments.json")
AWARDS = os.path.join(MAUIOS, "hands_maui_awards.json")
HST = timezone(timedelta(hours=-10))
def esc(s): return html.escape(str(s if s is not None else ""))

# Subject-keyword map: a contract is attributed to a department when its title/category contains one of
# these (lowercased, word-ish) tokens. Transparent + conservative; stated on each page. Admin departments
# that issue few/no subject-specific contracts honestly show 0 (we never invent civic data).
DEPT_KEYWORDS = {
    "water":          ["water", "wastewater", "well", "reservoir", "transmission", "pump station", "waterline", "potable"],
    "public_works":   ["road", "highway", "bridge", "pavement", "drainage", "baseyard", "guardrail", "culvert", "roadway", "improvements", "rehabilitation", "construction"],
    "parks":          ["park", "recreation", "pool", "gym", "playground", "beach park", "golf", "ballfield", "field"],
    "environmental":  ["solid waste", "landfill", "recycling", "reclamation", "environmental", "sewer", "refuse", "compost"],
    "fire":           ["fire", "rescue", "ocean safety", "lifeguard"],
    "police":         ["police", "public safety", "patrol"],
    "planning":       ["planning", "zoning", "land use", "long-range", "general plan", "community plan", "gis"],
    "finance":        ["finance", "audit", "accounting", "treasury", "actuarial", "valuation", "appraisal"],
    "housing":        ["housing", "affordable", "homeless", "human concerns", "shelter", "rent"],
    "transportation": ["transit", "bus", "transportation", "paratransit", "mobility"],
    "agriculture":    ["agriculture", "farm", "ag park", "agricultural", "irrigation"],
    "management":     ["information technology", " it ", "software", "data", "emergency management", "civil defense", "communications"],
    "liquor":         ["liquor", "alcohol", "licensing"],
    "personnel":      ["personnel", "human resources", "civil service", "recruitment", "benefits"],
    "corp_counsel":   ["legal", "counsel", "litigation", "attorney"],
    "prosecutor":     ["prosecut", "victim", "criminal"],
    "council":        ["council", "clerk", "election", "legislative"],
    "mayor":          ["mayor", "executive"],
}

def _load_awards():
    """Return a flat list of individual awards: {vendor, amount, date, title, category, dept}."""
    try:
        d = json.load(open(AWARDS, encoding="utf-8"))
    except Exception:
        return []
    flat = []
    for v in d.get("vendors", []):
        vn = v.get("vendor", "")
        for a in v.get("awards", []) or []:
            flat.append({"vendor": vn, "amount": a.get("amount") or 0, "date": a.get("date") or "",
                         "title": a.get("title") or "", "category": a.get("category") or "",
                         "proc": a.get("dept") or ""})
    return flat

def _match(award, keywords):
    blob = (award["title"] + " " + award["category"]).lower()
    return any(k in blob for k in keywords)

def _money(n):
    try: return "${:,.0f}".format(float(n))
    except Exception: return "$0"

def _dept_contracts(dept_id, awards):
    kws = DEPT_KEYWORDS.get(dept_id, [])
    if not kws:
        return [], 0.0
    rows = [a for a in awards if _match(a, kws)]
    rows.sort(key=lambda a: a["amount"], reverse=True)
    total = sum(float(a["amount"] or 0) for a in rows)
    return rows, total

CSS = (
    "body{margin:0;background:#f4f7fb;color:#eaf2fc;font-family:'Segoe UI',system-ui,sans-serif;line-height:1.55}"
    ".wrap{max-width:980px;margin:0 auto;padding:20px 18px 80px}"
    ".eyebrow{font-family:Consolas,'JetBrains Mono',monospace;font-size:11px;letter-spacing:1.6px;color:#7fb2ff;text-transform:uppercase}"
    "h1{font-size:26px;margin:6px 0 2px}.icon{font-size:30px;margin-right:8px}"
    ".lede{font-size:15px;color:#33485f;max-width:70ch;margin:6px 0 18px}"
    ".links{display:flex;gap:10px;flex-wrap:wrap;margin:14px 0 22px}"
    ".links a{display:inline-block;text-decoration:none;border:1px solid #bacde6;border-radius:10px;padding:9px 14px;color:#7fb2ff;background:#081420;font-size:14px}"
    ".links a:hover{border-color:#7fb2ff;background:#eef4fc}"
    ".links a b{display:block;font-size:11px;color:#5b6e86;font-weight:600;text-transform:uppercase;letter-spacing:.4px}"
    ".kpi{display:flex;gap:22px;flex-wrap:wrap;margin:6px 0 14px}"
    ".kpi div{background:#081420;border:1px solid #d4e0ee;border-radius:10px;padding:12px 16px;min-width:150px}"
    ".kpi b{display:block;font-family:Consolas,'JetBrains Mono',monospace;font-size:22px;color:#7fb2ff}"
    ".kpi span{font-size:12px;color:#5b6e86}"
    "h2{font-size:17px;margin:24px 0 6px}"
    "table{width:100%;border-collapse:collapse;margin-top:8px;font-size:13.5px;background:#081420}"
    "th,td{text-align:left;padding:8px 10px;border-bottom:1px solid #d4e0ee;vertical-align:top}"
    "th{font-family:Consolas,'JetBrains Mono',monospace;font-size:11px;text-transform:uppercase;color:#5b6e86}"
    "td.amt{font-family:Consolas,'JetBrains Mono',monospace;text-align:right;white-space:nowrap}"
    ".note{font-size:12px;color:#5b6e86;margin-top:10px;max-width:78ch}"
    ".method{background:#eef4fc;border-left:3px solid #00356b;padding:9px 13px;border-radius:0 8px 8px 0;font-size:12.5px;color:#33485f;margin:10px 0}"
    ".empty{color:#5b6e86;font-style:italic;padding:14px 4px}"
    "a.back{display:inline-block;margin:0 0 12px;color:#7fb2ff;text-decoration:none;font-size:13px}"
    ".disc{background:#fff7e6;border:1px solid #e6cf8f;border-left:3px solid #c98a00;border-radius:8px;padding:9px 13px;font-size:12.5px;color:#5a4a1e;margin:10px 0 16px}"
    ".caps{display:flex;gap:10px;flex-wrap:wrap;margin:6px 0 20px}"
    ".caps a,.caps span{display:inline-block;border:1px solid #bacde6;border-radius:10px;padding:9px 13px;font-size:13.5px;text-decoration:none;color:#7fb2ff;background:#081420}"
    ".caps a b,.caps span b{display:block;font-size:11px;color:#5b6e86;font-weight:600;text-transform:uppercase;letter-spacing:.4px}"
    ".caps span.soon{opacity:.65;border-style:dashed;background:#0f2540;color:#5b6e86}"
)

# PRIVATE-SERVICE / NOT-OFFICIAL framing (JRCSL: integrity, no impersonation) — on every mirror page.
NOT_OFFICIAL = ("<div class=disc><b>Private service, public information.</b> This is a 12 Stones Global "
    "civic-transparency mirror reflecting <b>public records</b> about %(tenant)s. It is <b>NOT</b> an official "
    "%(tenant)s system and does not represent the government. Sourced, never invented.</div>")

def _capabilities(tenant_id, map_page):
    """Our govOS tools layered onto EACH department node — live links + honestly-labeled 'in preparation'.
    map_page is the tenant's interactive map (only where one exists); everything else degrades gracefully."""
    live_map = bool(map_page)
    caps = [
        ("Interactive map", map_page if live_map else "", "parcels · zoning · overlays", live_map),
        ("Audit view", "audit_balance.html", "money×votes scorecard", True),
        ("Agendas & records", "agendas_%s.html" % tenant_id, "what's being decided", True),
        ("Cost / quotation", map_page if live_map else "", "modeled run-cost (our model)", live_map),
        ("Staff services", "", "ethics · schedule · local AI — auth-gated, in preparation", False),
        ("Presentations", "", "one-click department briefings — in preparation", False),
    ]
    out = ""
    for lbl, href, sub, live in caps:
        if live and href:
            out += '<a href="%s"><b>%s</b>%s</a>' % (esc(href), esc(lbl), esc(sub))
        else:
            out += '<span class="soon"><b>%s</b>%s</span>' % (esc(lbl), esc(sub))
    return out

def _dept_page(dept, awards, tenant_label, tenant_id, map_page):
    did = dept.get("id"); name = dept.get("name", did); icon = dept.get("icon", "")
    disc = NOT_OFFICIAL % {"tenant": tenant_label}
    caps = _capabilities(tenant_id, map_page)
    rows, total = _dept_contracts(did, awards)
    link_html = ""
    for key, lbl in (("serve", "Serve"), ("record", "Record"), ("audit", "Audit")):
        link = dept.get(key)
        if link and link.get("href"):
            link_html += '<a href="%s"><b>%s</b>%s</a>' % (esc(link["href"]), lbl, esc(link.get("label", "")))
    if not link_html:
        link_html = '<span class="note">No serve/record/audit surface wired yet for this department.</span>'
    src = dept.get("source", "")
    if src:
        link_html += '<a href="%s"><b>Official</b>%s</a>' % (esc(src), "mauicounty.gov")

    if rows:
        body = ("<table><thead><tr><th>Amount</th><th>Contract</th><th>Vendor</th><th>Date</th></tr></thead><tbody>"
                + "".join(
                    "<tr><td class=amt>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>"
                    % (_money(a["amount"]), esc(a["title"]), esc(a["vendor"]), esc(a["date"]))
                    for a in rows[:60]) + "</tbody></table>")
        more = ("<p class=note>Showing the 60 largest of %d matched contracts.</p>" % len(rows)) if len(rows) > 60 else ""
    else:
        body = ('<div class=empty>No county contract was matched to this department by subject keyword. '
                'That is expected for departments that deliver service directly rather than through procurement '
                '(e.g. personnel, corporation counsel, the liquor commission) — it is shown honestly, not hidden.</div>')
        more = ""
    kws = DEPT_KEYWORDS.get(did, [])
    method = ('<div class=method>How this list is built: county contract awards (from the public procurement '
              'record) whose <b>subject</b> matches this department are attributed here by keyword '
              '%s. The dollar figures are the real award amounts; the department attribution is a transparent '
              'subject match, not the procuring office.</div>' % (esc(", ".join(kws)) if kws else "(none defined)"))
    now = datetime.now(HST)
    return (
        "<!DOCTYPE html><html lang=en><head><meta charset=UTF-8>"
        "<meta name=viewport content='width=device-width,initial-scale=1'>"
        "<title>%s &middot; Maui County govOS</title><style>%s</style></head><body><div class=wrap>"
        "<a class=back href='departments_maui.html'>&larr; All Maui departments</a>"
        "<div class=eyebrow>Maui County &middot; govOS &middot; department as a function</div>"
        "<h1><span class=icon>%s</span>%s</h1>"
        "<p class=lede>%s</p>"
        "%s"
        "<h2>What our govOS adds to this department</h2><div class=caps>%s</div>"
        "<div class=links>%s</div>"
        "<h2>Contracts &amp; spending attributed to this department</h2>"
        "<div class=kpi><div><b>%s</b><span>total matched awards</span></div>"
        "<div><b>%d</b><span>contracts</span></div></div>"
        "%s%s%s"
        "<p class=note>Generated %s &middot; source: Maui County procurement record (reports/mauios/hands_maui_awards.json). "
        "Civic data is sourced, never invented.</p>"
        "</div></body></html>"
    ) % (esc(name), CSS, esc(icon), esc(name), esc(dept.get("for_people", "")), disc, caps, link_html,
         _money(total), len(rows), method, body, more, esc(now.strftime("%Y-%m-%d %H:%M HST")))

def _index_page(depts, awards, tenant_label):
    now = datetime.now(HST)
    disc = NOT_OFFICIAL % {"tenant": tenant_label}
    rows = ""
    grand = 0.0
    for d in depts:
        did = d.get("id"); _r, tot = _dept_contracts(did, awards); grand += tot
        rows += ("<tr><td><a href='dept_%s_maui.html'>%s %s</a></td>"
                 "<td>%s</td><td class=amt>%s</td><td class=amt>%d</td></tr>"
                 % (esc(did), esc(d.get("icon", "")), esc(d.get("name", did)),
                    esc((d.get("for_people", "") or "")[:90] + ("…" if len(d.get("for_people", "") or "") > 90 else "")),
                    _money(tot), len(_r)))
    return (
        "<!DOCTYPE html><html lang=en><head><meta charset=UTF-8>"
        "<meta name=viewport content='width=device-width,initial-scale=1'>"
        "<title>Maui County departments &middot; govOS</title><style>%s</style></head><body><div class=wrap>"
        "<div class=eyebrow>Maui County &middot; govOS &middot; the people's government, as functions</div>"
        "<h1>Maui County departments</h1>"
        "<p class=lede>Every Maui County department as a function you can see into — what it does for you, "
        "where to act, and the public contracts attributed to it by subject. Each department node carries our "
        "govOS tools: interactive map, audit, agendas, modeled cost/quote, staff services, presentations. %d departments.</p>"
        "%s"
        "<div class=kpi><div><b>%d</b><span>departments</span></div>"
        "<div><b>%s</b><span>attributed contract dollars</span></div></div>"
        "<table><thead><tr><th>Department</th><th>What it does</th><th>Matched $</th><th>Contracts</th></tr></thead>"
        "<tbody>%s</tbody></table>"
        "<p class=note>Generated %s &middot; departments sourced from the County Charter (config/maui_departments.json); "
        "contracts from the Maui County procurement record. Sourced, never invented.</p>"
        "</div></body></html>"
    ) % (CSS, len(depts), disc, len(depts), _money(grand), rows, esc(now.strftime("%Y-%m-%d %H:%M HST")))

def main(tenant_id="maui", tenant_label="Maui County", map_page="maui_parcel_map.html"):
    # REUSABLE TEMPLATE (James 2026-07-02: teach-once-here-replicates-everywhere). Maui is the template
    # tenant; a new tenant inherits the whole department mirror by supplying config/<tenant>_departments.json
    # (+ its awards file + its map, where they exist) and calling main(tenant_id, tenant_label, map_page).
    cfg = json.load(open(DEPTS_CFG, encoding="utf-8"))
    depts = cfg.get("departments", [])
    awards = _load_awards()
    os.makedirs(MAUIOS, exist_ok=True)
    written = []
    for d in depts:
        fn = "dept_%s_%s.html" % (d.get("id"), tenant_id)
        with open(os.path.join(MAUIOS, fn), "w", encoding="utf-8", newline="\n") as f:
            f.write(_dept_page(d, awards, tenant_label, tenant_id, map_page))
        written.append(fn)
    with open(os.path.join(MAUIOS, "departments_%s.html" % tenant_id), "w", encoding="utf-8", newline="\n") as f:
        f.write(_index_page(depts, awards, tenant_label))
    written.append("departments_%s.html" % tenant_id)
    matched = sum(1 for d in depts if _dept_contracts(d.get("id"), awards)[0])
    print("dept_pages: wrote %d pages (%d depts, %d with matched contracts, %d total awards parsed)"
          % (len(written), len(depts), matched, len(awards)))
    for fn in written:
        print("  ", fn)
    return written

if __name__ == "__main__":
    main()
