# -*- coding: utf-8 -*-
"""
rep_audit.py — the per-REPRESENTATIVE "silencing" audit as a self-contained graphic console page.

Jimmy 2026-07-08: "a full audit by representative and how they silence other voters votes with their
behavior … they have a logic that overlaps … use neo4j." This is the SCORING + GRAPHIC layer over the
already-sourced engines (votes_watch/officials.json, vendor_donor_join, money_votes_casework, crosswalk_graph).

INTEGRITY (non-negotiable, matches the whole civic pipeline):
  • Every figure carries its source; framed as a QUESTION for the Board of Ethics (Maui Charter Art. 10 /
    HRS ch. 84), NEVER a verdict.
  • Maui does NOT machine-publish per-member roll-call NAYs, named testifier tallies, or council-district
    geometry. Anything needing those renders as **NEEDS-RECORD** with the exact UIPA (HRS 92F) ask — never guessed.
  • PUBLIC page = the sourced questions + public $ (CSC/HANDS) + NEEDS-RECORD, no strength tags.
    OWNER page = + the money_votes_casework EXAMINE/NOTE strength + fuller detail. Owner mirror only.

Self-contained (own <style>, inline SVG relationship graph) so it is CSP-safe and needs no external CDN.
ASCII-safe stdlib only. Writes reports/mauios/rep_<slug>.html (public) + reports/mauios/rep_audit.html (index),
and owner copies to reports/_status/rep_audit/<slug>.html.
"""
import json, os, html, re

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(os.path.dirname(HERE))
MAUIOS = os.path.join(PROJ, "reports", "mauios")
STATUS = os.path.join(PROJ, "reports", "_status")
OWNER_OUT = os.path.join(STATUS, "rep_audit")

SOURCE_NOTE = ("Sourced: Maui County CivicClerk minutes (vote record) · Hawaiʻi Campaign Spending Commission "
               "(donations, keyed by candidate name) · HANDS Notice-of-Award (contracts). A member's donations are "
               "their OWN filings; a predecessor who held the seat earlier raised their own money — never conflated. "
               "Framed as questions for the Board of Ethics (Maui Charter Art. 10 / HRS ch. 84), never verdicts.")

# Seat succession (sourced: Maui County Council public roster). The money a candidate filed is THEIRS (CSC is
# keyed by candidate name); a PREDECESSOR who held the seat earlier raised their own money and did their own
# deals — never attribute one to the other. Jimmy 2026-07-08: "batangan replaced tasha kama who raised the
# money and deals." Add entries only where the succession is sourced.
SEAT_HISTORY = {
    "Batangan": {"predecessor": "Tasha Kama", "since": "November 2025",
                 "source": "https://mauicounty.us/press-release/three-names-on-list-to-fill-vacant-council-seat-for-kahului-residency-area/",
                 "note": "Councilmember Tasha Kama held the Kahului residency seat until her passing in October 2025. "
                         "Kauanoe Batangan was appointed by the Council to fill the vacant seat in November 2025 — his "
                         "tenure is only months old. The donations shown below are his OWN filings; the money raised and "
                         "deals made for this seat during Councilmember Kama's tenure were hers, audited separately and "
                         "with the respect owed a member who has passed. (Source: Maui County Council, Nov. 10, 2025.)"},
}


def _load(path, default=None):
    try:
        return json.load(open(path, encoding="utf-8"))
    except Exception:
        return default


def _esc(s):
    return html.escape(str(s if s is not None else ""))


def _slug(name):
    return re.sub(r"[^a-z0-9]+", "-", str(name).lower()).strip("-")


def _money(x):
    try:
        return "${:,.0f}".format(float(x))
    except Exception:
        return "$0"


def load_all():
    officials = _load(os.path.join(MAUIOS, "officials.json"), {}) or {}
    vdj = _load(os.path.join(MAUIOS, "vendor_donor_join.json"), {}) or {}
    graph = _load(os.path.join(MAUIOS, "crosswalk_graph.json"), {"nodes": [], "edges": []}) or {}
    casework = _load(os.path.join(STATUS, "casework_maui.json"), {}) or {}
    # label map: surname -> full label, from the graph's official nodes (falls back to hit labels)
    labels = {}
    for n in graph.get("nodes", []):
        if n.get("type") == "official" and n.get("name"):
            labels[n["name"]] = n.get("label") or n["name"]
    return officials, vdj, graph, casework, labels


def hits_for(vdj, rep):
    """Every money x vendor x THIS-rep hit (public CSC/HANDS)."""
    out = []
    for m in vdj.get("matched", []):
        for h in m.get("hits", []):
            if h.get("official") == rep:
                out.append({"vendor": m.get("vendor"), "award_total": m.get("award_total", 0),
                            "award_count": m.get("award_count", 0), "contributor": h.get("contributor"),
                            "amount": h.get("amount", 0), "n": h.get("n", 1), "basis": h.get("basis")})
    return out


def cases_for(casework, rep):
    out = []
    for c in casework.get("cases", []):
        offs = c.get("officials") or ([c.get("official")] if c.get("official") else [])
        if rep in offs or c.get("official") == rep:
            out.append(c)
    return out


def rep_subgraph(graph, rep):
    """rep node + the donor/vendor nodes one hop away (the overlapping logic), for the inline-SVG diagram."""
    rid = "off:" + _slug(rep)
    nodes = {n["id"]: n for n in graph.get("nodes", [])}
    center = nodes.get(rid) or {"id": rid, "name": rep, "type": "official", "label": rep}
    neigh = []
    for e in graph.get("edges", []):
        a, b = e.get("src"), e.get("dst")   # crosswalk_graph uses src/dst
        other = None
        if a == rid:
            other = b
        elif b == rid:
            other = a
        if other and other in nodes and nodes[other] not in neigh:
            neigh.append(nodes[other])
    return center, neigh[:14]


# ---------- inline SVG: the overlapping-logic relationship graph (self-contained, CSP-safe) ----------
def svg_graph(center, neigh):
    import math
    W, H, cx, cy, R = 640, 380, 320, 190, 130
    parts = ['<svg viewBox="0 0 %d %d" width="100%%" style="max-width:640px;display:block;margin:0 auto" '
             'xmlns="http://www.w3.org/2000/svg" role="img" aria-label="relationship graph">' % (W, H)]
    col = {"official": "#e3ad33", "donor": "#5fc0d8", "vendor": "#e0872f", "contributor": "#5fc0d8"}
    pos = []
    k = max(1, len(neigh))
    for i, n in enumerate(neigh):
        ang = (2 * math.pi * i / k) - math.pi / 2
        x, y = cx + R * math.cos(ang), cy + R * math.sin(ang)
        pos.append((x, y, n))
        parts.append('<line x1="%.0f" y1="%.0f" x2="%.0f" y2="%.0f" stroke="#3a2e20" stroke-width="1.4"/>' % (cx, cy, x, y))
    for x, y, n in pos:
        c = col.get(n.get("type"), "#8aa06a")
        lbl = _esc((n.get("name") or n.get("label") or "")[:18])
        parts.append('<circle cx="%.0f" cy="%.0f" r="7" fill="%s"/>' % (x, y, c))
        anchor = "start" if x >= cx else "end"
        dx = 11 if x >= cx else -11
        parts.append('<text x="%.0f" y="%.0f" fill="#c3b79c" font-size="10" text-anchor="%s" font-family="system-ui">%s</text>'
                     % (x + dx, y + 3, anchor, lbl))
    parts.append('<circle cx="%d" cy="%d" r="13" fill="#e3ad33"/>' % (cx, cy))
    parts.append('<text x="%d" y="%d" fill="#1a1510" font-size="11" font-weight="700" text-anchor="middle" font-family="system-ui">%s</text>'
                 % (cx, cy + 4, _esc((center.get("name") or "")[:10])))
    parts.append('</svg>')
    return "".join(parts)


def tile(v, label, sub=""):
    return ('<div class="tl"><div class="tv">%s</div><div class="tk">%s</div>%s</div>'
            % (_esc(v), _esc(label), ('<div class="ts">%s</div>' % _esc(sub)) if sub else ""))


def render_rep(rep, label, off, hits, cases, center, neigh, owner=False):
    tv = off.get("total_votes", 0) or 0
    noes = off.get("noes", 0) or 0
    recused = off.get("recused", 0) or 0
    dissent = (100.0 * noes / tv) if tv else 0.0
    money_total = sum(float(h.get("amount", 0) or 0) for h in hits)
    at_stake = sum(float(h.get("award_total", 0) or 0) for h in hits)
    n_flags = len(hits)
    # per-matter silencing rows — one sourced QUESTION per money x vendor tie, + the NEEDS-RECORD gaps
    rows = []
    for h in sorted(hits, key=lambda z: -float(z.get("award_total", 0) or 0)):
        q = ('Did %s, having received %s from %s (%s), act on county business with %s — which holds %s '
             'across %d award(s) — without recusing?'
             % (_esc(label.split(" - ")[0]), _money(h["amount"]), _esc(h["contributor"]), _esc(h["basis"]),
                _esc(h["vendor"]), _money(h["award_total"]), h.get("award_count", 0)))
        strength = ""
        if owner:
            cs = next((c for c in cases if (c.get("vendor") == h["vendor"] or h["vendor"] in json.dumps(c))), None)
            tag = (cs.get("strength") or cs.get("verdict") or cs.get("class")) if isinstance(cs, dict) else None
            if tag:
                strength = '<span class="stag">%s</span>' % _esc(tag)
        rows.append(
            '<tr><td>%s</td><td class="mono">%s</td><td class="mono">%s</td>'
            '<td><div class="q">%s%s</div>'
            '<div class="nr">NEEDS-RECORD: per-member roll-call NAY + named testimony on this matter are not '
            'machine-published by Maui &mdash; request via UIPA (HRS 92F) to the County Clerk.</div></td></tr>'
            % (_esc(h["vendor"]), _money(h["award_total"]), _money(h["amount"]), q, strength))
    rows_html = ("".join(rows) if rows
                 else '<tr><td colspan="4" class="nr">No donor&harr;vendor tie on record for this member in the current scan.</td></tr>')

    css = (":root{--bg:#0d0b08;--pan:#16130d;--ln:#2a241a;--ink:#efe9da;--mut:#b3a98f;--fn:#8a7c60;"
           "--gold:#e3ad33;--g2:#f3d589;--sea:#5fc0d8}"
           "*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);"
           "font-family:'Segoe UI',system-ui,sans-serif;line-height:1.55}"
           ".wrap{max-width:900px;margin:0 auto;padding:24px 20px 70px}"
           ".hd{border-bottom:1px solid rgba(227,173,51,.25);padding-bottom:16px;margin-bottom:22px}"
           ".hd h1{margin:0 0 4px;font-size:clamp(24px,4.6vw,34px);color:var(--g2)}"
           ".hd .seat{color:var(--mut);font-size:15px}"
           ".hd .role{display:inline-block;margin-top:8px;font:600 11px/1 Consolas,monospace;letter-spacing:.06em;"
           "text-transform:uppercase;color:var(--gold);background:rgba(227,173,51,.12);border-radius:20px;padding:4px 11px}"
           "h2{font-size:14px;letter-spacing:.06em;text-transform:uppercase;color:var(--gold);margin:30px 0 12px}"
           ".tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px}"
           ".tl{background:var(--pan);border:1px solid var(--ln);border-radius:10px;padding:14px}"
           ".tl .tv{font:700 24px/1 Consolas,monospace;color:var(--g2)}.tl .tk{color:var(--mut);font-size:12px;margin-top:5px}"
           ".tl .ts{color:var(--fn);font-size:11px;margin-top:3px}"
           "table{width:100%;border-collapse:collapse;font-size:14px}"
           "th{text-align:left;color:var(--fn);font:600 11px/1 Consolas,monospace;letter-spacing:.05em;"
           "text-transform:uppercase;padding:8px 10px;border-bottom:1px solid var(--ln)}"
           "td{padding:11px 10px;border-bottom:1px solid rgba(255,255,255,.05);vertical-align:top}"
           ".mono{font-family:Consolas,monospace;color:var(--g2);white-space:nowrap}"
           ".q{color:var(--ink)}.nr{color:var(--fn);font-size:12.5px;font-style:italic;margin-top:6px}"
           ".stag{display:inline-block;margin-left:8px;font:700 10px/1 Consolas,monospace;color:#e0872f;"
           "border:1px solid #5a3a1e;border-radius:5px;padding:2px 6px}"
           ".gr{background:var(--pan);border:1px solid var(--ln);border-radius:12px;padding:18px 10px}"
           ".foot{color:var(--fn);font-size:12px;margin-top:34px;padding-top:16px;border-top:1px solid var(--ln)}"
           "a{color:var(--sea)}.back{color:var(--gold);text-decoration:none;font-size:13px}")

    silence = ('<div class="tiles" style="margin-top:6px">'
               + tile(n_flags, "money+vote flags", "their donors who hold county contracts")
               + tile(_money(money_total), "their own donations", "from those donor-vendors (CSC filings)")
               + tile(_money(at_stake), "vendor county $", "the vendors' contracts — NOT the member's money")
               + tile("%.0f%%" % dissent, "dissent rate", "%d NAY of %d votes" % (noes, tv))
               + tile(recused, "recorded recusals", "of %d total votes" % tv)
               + "</div>")
    tenure = SEAT_HISTORY.get(rep)
    tenure_html = ""
    if tenure:
        src = ('&nbsp;<a href="%s" style="color:var(--sea)">[source]</a>' % _esc(tenure["source"])) if tenure.get("source") else ""
        tenure_html = ('<div style="background:rgba(95,192,216,.07);border:1px solid #2a3f47;border-radius:10px;'
                       'padding:13px 16px;margin:16px 0 4px;font-size:14px;color:var(--mut)">'
                       '<b style="color:var(--sea)">Seat history &mdash;</b> %s%s</div>' % (_esc(tenure["note"]), src))

    body = ('<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>%s &mdash; silencing audit | govOS</title><style>%s</style></head><body><div class="wrap">'
            '<a class="back" href="rep_audit.html">&larr; all representatives</a>'
            '<div class="hd"><h1>%s</h1><div class="seat">%s</div>'
            '<div class="role">%s &middot; silencing audit</div></div>'
            '<p style="color:var(--mut);max-width:64ch">How does this member&rsquo;s recorded behavior &mdash; votes, the '
            'money behind them, and recusals &mdash; line up against the will of the voters they represent? '
            'Every figure below is sourced; each is a <b style="color:var(--ink)">question for the Board of Ethics</b>, not a finding. '
            'The donations shown are this member&rsquo;s OWN campaign filings (matched by candidate name); the large dollar '
            'figures are the <i>vendors&rsquo;</i> county contracts set beside those donations &mdash; not the member&rsquo;s money.</p>'
            '%s'
            '<h2>Silence(R) &mdash; the rollup</h2>%s'
            '<h2>The overlapping logic</h2><div class="gr">%s'
            '<p style="text-align:center;color:var(--fn);font-size:12px;margin:8px 0 0">%s at center &middot; '
            'donors (teal) and vendors (amber) one hop away &middot; from the sourced crosswalk graph</p></div>'
            '<h2>Per-matter &mdash; the questions</h2>'
            '<table><thead><tr><th>Vendor / party</th><th>County $</th><th>To this member</th><th>The question &amp; what to request</th></tr></thead>'
            '<tbody>%s</tbody></table>'
            '<div class="foot">%s%s</div>'
            '</div></body></html>'
            % (_esc(label.split(" - ")[0]), css, _esc(label.split(" - ")[0]),
               _esc(label.split(" - ")[1] if " - " in label else "Maui County Council"),
               "OWNER" if owner else "PUBLIC",
               tenure_html,
               silence, svg_graph(center, neigh), _esc(rep), rows_html,
               _esc(SOURCE_NOTE),
               (' &middot; OWNER VIEW: strength tags from the money&times;votes casework are shown; this copy is never published.'
                if owner else "")))
    return body


def render_former(key, meta):
    """A FORMER member's page — real donations + real recorded dissents, handled respectfully
    (she is deceased). Not a 'silencing' score (that's a current-member accountability frame); this is
    her own record, sourced, so the seat's history isn't erased or wrongly folded into her successor's."""
    money = meta.get("money") or {}
    deals = meta.get("deals") or []
    ds = meta.get("deals_summary") or {}

    donors_rows = "".join(
        '<tr><td>%s</td><td class="mono">%s</td></tr>' % (_esc(d["name"]), _money(d["amount"]))
        for d in (money.get("top_donors") or [])[:12])

    deal_rows = ""
    for d in deals:
        coalition = (", ".join(d.get("coalition") or [])) if d.get("coalition") else ""
        with_note = (' — with %s' % _esc(coalition)) if coalition else ""
        quote = ""
        if d.get("quotes"):
            nm, txt = d["quotes"][0]
            quote = '<div class="q">&ldquo;%s&hellip;&rdquo; &mdash; %s</div>' % (_esc(txt), _esc(nm))
        src = (' &middot; <a href="%s">source minutes</a>' % _esc(d["url"])) if d.get("url") else ""
        deal_rows += ('<tr><td class="mono">%s</td><td>%s%s</td><td class="mono">%s</td>'
                     '<td>%s%s</td></tr>'
                     % (_esc(d.get("date") or ""), _esc(d.get("item") or "Motion (item not parsed)"), with_note,
                        _esc(d.get("tally") or ""), quote, src))

    css = (":root{--bg:#0d0b08;--pan:#16130d;--ln:#2a241a;--ink:#efe9da;--mut:#b3a98f;--fn:#8a7c60;"
           "--gold:#e3ad33;--g2:#f3d589;--sea:#5fc0d8}"
           "*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);"
           "font-family:'Segoe UI',system-ui,sans-serif;line-height:1.55}"
           ".wrap{max-width:920px;margin:0 auto;padding:24px 20px 70px}"
           ".hd{border-bottom:1px solid rgba(227,173,51,.25);padding-bottom:16px;margin-bottom:22px}"
           ".hd h1{margin:0 0 4px;font-size:clamp(24px,4.6vw,34px);color:var(--g2)}"
           ".hd .seat{color:var(--mut);font-size:15px}"
           ".hd .role{display:inline-block;margin-top:8px;font:600 11px/1 Consolas,monospace;letter-spacing:.06em;"
           "text-transform:uppercase;color:var(--sea);background:rgba(95,192,216,.12);border-radius:20px;padding:4px 11px}"
           "h2{font-size:14px;letter-spacing:.06em;text-transform:uppercase;color:var(--gold);margin:30px 0 12px}"
           ".memo{background:rgba(95,192,216,.07);border:1px solid #2a3f47;border-radius:10px;padding:16px 18px;"
           "color:var(--mut);font-size:14.5px;font-style:italic}"
           ".tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin-top:6px}"
           ".tl{background:var(--pan);border:1px solid var(--ln);border-radius:10px;padding:14px}"
           ".tl .tv{font:700 24px/1 Consolas,monospace;color:var(--g2)}.tl .tk{color:var(--mut);font-size:12px;margin-top:5px}"
           "table{width:100%;border-collapse:collapse;font-size:13.5px}"
           "th{text-align:left;color:var(--fn);font:600 11px/1 Consolas,monospace;letter-spacing:.05em;"
           "text-transform:uppercase;padding:8px 10px;border-bottom:1px solid var(--ln)}"
           "td{padding:10px;border-bottom:1px solid rgba(255,255,255,.05);vertical-align:top}"
           ".mono{font-family:Consolas,monospace;color:var(--g2);white-space:nowrap}"
           ".q{color:var(--ink);font-style:italic;margin-top:5px;font-size:13px}"
           "a{color:var(--sea)}.back{color:var(--gold);text-decoration:none;font-size:13px}"
           ".foot{color:var(--fn);font-size:12px;margin-top:34px;padding-top:16px;border-top:1px solid var(--ln)}")

    sources = " &middot; ".join('<a href="%s">source</a>' % _esc(u) for u in meta.get("sources", []))

    body = ('<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>%s &mdash; former member record | govOS</title><style>%s</style></head><body><div class="wrap">'
            '<a class="back" href="rep_audit.html">&larr; all representatives</a>'
            '<div class="hd"><h1>%s</h1><div class="seat">%s</div>'
            '<div class="role">FORMER MEMBER &middot; %s</div></div>'
            '<div class="memo">%s held this seat until %s. The donations and votes below are HERS &mdash; her '
            'own record, kept separate and intact rather than folded into her successor\'s. %s</div>'
            '<h2>Her campaign money (Hawaiʻi Campaign Spending Commission)</h2>'
            '<div class="tiles">%s%s</div>'
            '<table style="margin-top:14px"><thead><tr><th>Top donor</th><th>Amount</th></tr></thead><tbody>%s</tbody></table>'
            '<h2>Her recorded votes &mdash; where she dissented (%d)</h2>'
            '<p style="color:var(--mut);font-size:14px">Every recorded NO vote of hers in the ingested minutes '
            'corpus, sourced to the meeting minutes. %d carry an item number; %d carry her own recorded words.</p>'
            '<table><thead><tr><th>Date</th><th>Matter</th><th>Tally</th><th>Record</th></tr></thead>'
            '<tbody>%s</tbody></table>'
            '<div class="foot">Sourced: Hawaiʻi Campaign Spending Commission (reg_no %s) &middot; Maui County '
            'CivicClerk minutes, parsed by rollcall_parser.py &middot; %s. Framed as the public record, in '
            'memory and with respect.</div>'
            '</div></body></html>'
            % (_esc(meta["name"]), css, _esc(meta["name"]), _esc(meta["seat"]), _esc(meta["role"]),
               _esc(meta["name"]), _esc(meta["tenure"].split(" - ")[1] if " - " in meta["tenure"] else meta["tenure"]),
               ("Successor: %s." % _esc(meta.get("successor", "")) if meta.get("successor") else ""),
               tile(money.get("rows", 0), "donation filings"), tile(_money(money.get("total", 0)), "total raised"),
               donors_rows or '<tr><td colspan="2">No donor rows resolved.</td></tr>',
               ds.get("total", 0), ds.get("with_item", 0), ds.get("with_quote", 0),
               deal_rows or '<tr><td colspan="4">No recorded dissents found.</td></tr>',
               meta.get("reg_no", ""), sources))
    slug = "rep_%s_former" % key.lower()
    out_path = os.path.join(MAUIOS, "%s.html" % slug)
    with open(out_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(body)
    return slug


def render_index(reps_meta):
    css = ("body{margin:0;background:#0d0b08;color:#efe9da;font-family:'Segoe UI',system-ui,sans-serif}"
           ".w{max-width:960px;margin:0 auto;padding:26px 20px 70px}"
           "h1{color:#f3d589;font-size:clamp(26px,5vw,36px);margin:0 0 6px}p.l{color:#b3a98f;max-width:64ch}"
           ".grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:12px;margin-top:22px}"
           ".c{background:#16130d;border:1px solid #2a241a;border-radius:12px;padding:16px;text-decoration:none;color:#efe9da;transition:.14s}"
           ".c:hover{border-color:#e3ad33;transform:translateY(-1px)}"
           ".c .n{font-size:17px;color:#f3d589}.c .s{color:#8a7c60;font-size:12.5px;margin:3px 0 10px}"
           ".c .m{font:700 13px/1 Consolas,monospace;color:#e0872f}.c .m span{color:#8a7c60;font-weight:400}"
           ".foot{color:#8a7c60;font-size:12px;margin-top:34px;padding-top:16px;border-top:1px solid #2a241a}")
    cards = ""
    for m in reps_meta:
        if m.get("kind") == "former":
            cards += ('<a class="c" href="%s"><div class="n">%s</div><div class="s">%s &middot; FORMER MEMBER</div>'
                      '<div class="m">%d <span>recorded dissents</span> &middot; %s <span>raised</span></div></a>'
                      % (_esc(m["href"]), _esc(m["name"]), _esc(m["seat"]), m["flags"], _money(m["at_stake"])))
        else:
            cards += ('<a class="c" href="%s"><div class="n">%s</div><div class="s">%s</div>'
                      '<div class="m">%d <span>money+vote flags</span> &middot; %s <span>at stake</span></div></a>'
                      % (_esc(m["href"]), _esc(m["name"]), _esc(m["seat"]), m["flags"], _money(m["at_stake"])))
    return ('<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>Maui County &mdash; audit by representative | govOS</title><style>%s</style></head><body><div class="w">'
            '<h1>Audit by representative</h1>'
            '<p class="l">For each Maui County Council member: how their recorded behavior &mdash; votes, the money behind '
            'them, recusals &mdash; lines up against the will of the voters they represent. Sourced; framed as questions for '
            'the Board of Ethics, never verdicts.</p><div class="grid">%s</div>'
            '<div class="foot">%s</div></div></body></html>' % (css, cards, _esc(SOURCE_NOTE)))


def main():
    officials, vdj, graph, casework, labels = load_all()
    os.makedirs(OWNER_OUT, exist_ok=True)
    reps_meta = []
    for rep in sorted(officials.keys()):
        off = officials[rep]
        label = labels.get(rep) or rep
        hits = hits_for(vdj, rep)
        cases = cases_for(casework, rep)
        center, neigh = rep_subgraph(graph, rep)
        slug = _slug(rep)
        # PUBLIC (question-only)
        pub = render_rep(rep, label, off, hits, cases, center, neigh, owner=False)
        with open(os.path.join(MAUIOS, "rep_%s.html" % slug), "w", encoding="utf-8", newline="\n") as f:
            f.write(pub)
        # OWNER (strength tags) -> private _status only
        own = render_rep(rep, label, off, hits, cases, center, neigh, owner=True)
        with open(os.path.join(OWNER_OUT, "rep_%s.html" % slug), "w", encoding="utf-8", newline="\n") as f:
            f.write(own)
        reps_meta.append({"name": label.split(" - ")[0], "seat": (label.split(" - ")[1] if " - " in label else ""),
                          "href": "rep_%s.html" % slug, "flags": len(hits),
                          "at_stake": sum(float(h.get("award_total", 0) or 0) for h in hits), "kind": "current"})

    # FORMER members — their own record, sourced, kept separate from any successor (2026-07-08).
    former = _load(os.path.join(MAUIOS, "officials_former.json"), {}) or {}
    for key, meta in former.items():
        slug = render_former(key, meta)
        deals = meta.get("deals") or []
        reps_meta.append({"name": meta["name"], "seat": meta.get("seat", ""),
                          "href": "%s.html" % slug, "flags": len(deals),
                          "at_stake": (meta.get("money") or {}).get("total", 0), "kind": "former"})

    with open(os.path.join(MAUIOS, "rep_audit.html"), "w", encoding="utf-8", newline="\n") as f:
        f.write(render_index(reps_meta))
    print("rep_audit: %d representatives + %d former -> reports/mauios/rep_*.html + rep_audit.html (public) + _status/rep_audit/ (owner)"
          % (len(officials), len(former)))
    for m in reps_meta:
        print("  %-26s %d flags  %s at stake" % (m["name"], m["flags"], _money(m["at_stake"])))


if __name__ == "__main__":
    main()
