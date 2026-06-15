#!/usr/bin/env python3
"""n53_ingest.py — feed the N53 integrity engine (Ka Luna Kiaʻi, the Overseer/Override) the REAL
past record: meeting MINUTES, SUPPLEMENTAL MATERIALS, and ROLL-CALL VOTES.

N53 flags a broken pair — "a vote that doesn't answer its district, a contract that doesn't answer
its donor." Money side: CSC donations × HANDS contracts (already real). This builds the VOTES side:

  - MAUI: ingests the REAL parsed record that votes_watch.py already extracts from the County's
    minutes (CivicClerk PDFs) — votes_index.jsonl (per-meeting items, outcomes, recusals, minutes
    URL) + officials.json (per-member AYE/NO/recused vote logs). 70 meetings, individual roll-call.
  - OTHER TENANTS: carries the verified minutes / supplemental-materials LINKS from the n53-archive
    discovery workflow (the archive). Structured roll-call parsing of those minutes is marked pending
    where the votes live inside PDF prose or a non-English record — captured, never invented.

Outputs: reports/mauios/n53_corpus.json, archive_<tenant>.html, archive.html, n53_engine.html.
Stdlib only. Defensive. Nothing fabricated — empty/pending is correct over invention.
"""
import os, json, html
from datetime import datetime, timezone, timedelta

HOME    = os.path.expanduser("~")
TOOL_DIR= os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.join(HOME, "Documents", "Claude", "Projects", "Video System elementLOTUS")
MAUIOS  = os.path.join(PROJECT, "reports", "mauios")
ARCHIVE = os.path.join(TOOL_DIR, "n53_archive.json")      # n53-archive discovery workflow output
AGENDA  = os.path.join(TOOL_DIR, "agenda_sources.json")
VOTES_IDX = os.path.join(MAUIOS, "votes_index.jsonl")     # votes_watch.py: parsed Maui minutes
OFFICIALS = os.path.join(MAUIOS, "officials.json")        # votes_watch.py: per-member vote logs
CORPUS  = os.path.join(MAUIOS, "n53_corpus.json")
HST     = timezone(timedelta(hours=-10))
esc     = lambda s: html.escape(str(s or ""))
def now_hst(): return datetime.now(HST)
MAXMTG  = 40   # cap meetings rendered per tenant (corpus stays representative + page stays light)

NAMES = {"state":"State of Hawaiʻi","maui":"Maui County","honolulu":"City & County of Honolulu",
         "hawaii":"Hawaiʻi County","kauai":"Kauaʻi County","nyc":"New York City","nys":"New York State",
         "liverpool":"Village of Liverpool","london":"City of London / Greater London","tokyo":"Tokyo Metropolis",
         "hongkong":"Hong Kong SAR","singapore":"Singapore","zurich":"Zürich","frankfurt":"Frankfurt am Main",
         "paris":"Paris","dubai":"Dubai"}

def load(p, d):
    try: return json.load(open(p, encoding="utf-8"))
    except Exception: return d

# ── MAUI: the real parsed-minutes corpus from votes_watch.py ────────────────────────────────
def ingest_maui():
    vi = []
    try:
        for ln in open(VOTES_IDX, encoding="utf-8"):
            ln = ln.strip()
            if ln: vi.append(json.loads(ln))
    except Exception:
        vi = []
    off = load(OFFICIALS, {})
    vi.sort(key=lambda x: x.get("date", ""), reverse=True)
    meetings = []
    for m in vi[:MAXMTG]:
        oc = m.get("outcomes") or {}
        meetings.append({"date": m.get("date", ""), "body": m.get("meeting", "Meeting"),
                         "minutes_url": m.get("url", ""), "report": m.get("report", ""),
                         "items": m.get("items", []), "carried": oc.get("carried", 0),
                         "failed": oc.get("failed", 0), "recusals": m.get("recusals", []),
                         "money": m.get("agenda_money", "")})
    officials = []
    for name, v in sorted(off.items(), key=lambda kv: -kv[1].get("total_votes", 0)):
        officials.append({"name": name, "meetings": v.get("meetings", 0), "ayes": v.get("ayes", 0),
                          "noes": v.get("noes", 0), "recused": v.get("recused", 0),
                          "recusals": v.get("recusals", []), "total_votes": v.get("total_votes", 0)})
    return {"name": NAMES["maui"], "source": "Maui County minutes via CivicClerk (votes_watch.py)",
            "votes_structured": True,
            "meetings": meetings, "officials": officials,
            "meetings_total": len(vi),
            "votes": sum(o["total_votes"] for o in officials),
            "recusals": sum(len(o["recusals"]) for o in officials),
            "decisions": sum(len(m["items"]) for m in meetings),
            "note": "Real per-member roll-call (AYE/NO/recused) parsed from the County's official minutes by votes_watch.py — %d meetings on file." % len(vi)}

# ── other tenants: minutes/materials links from the verified discovery workflow ─────────────
def ingest_archive(tid, a, g):
    meetings = []
    for p in (a.get("recent_past") or []):
        meetings.append({"date": p.get("date", ""), "body": p.get("body", ""),
                         "minutes_url": p.get("minutes_url", ""), "materials_url": p.get("materials_url", ""),
                         "items": [], "recusals": []})
    return {"name": NAMES.get(tid, tid),
            "source": a.get("past_url") or g.get("source_url") or "",
            "votes_structured": bool(a.get("votes_structured")),
            "meetings": meetings, "officials": [],
            "meetings_total": len(meetings), "votes": 0, "recusals": 0, "decisions": 0,
            "minutes_available": bool(a.get("minutes_available")),
            "supplemental_available": bool(a.get("supplemental_available")),
            "votes_how": a.get("votes_how", ""),
            "note": (a.get("note") or "")[:380] or "Minutes/materials links pending the archive discovery pass."}

def build_corpus():
    arch = {a["tenant_id"]: a for a in load(ARCHIVE, {}).get("archive", [])}
    agen = {s["tenant_id"]: s for s in load(AGENDA, {}).get("sources", [])}
    tenants = {}
    for tid in NAMES:
        if tid == "maui":
            tenants[tid] = ingest_maui()
        else:
            tenants[tid] = ingest_archive(tid, arch.get(tid, {}), agen.get(tid, {}))
    return {"generated": now_hst().strftime("%Y-%m-%d %H:%M HST"), "tenants": tenants}

# ── rendering ───────────────────────────────────────────────────────────────────────────────
CSS = """<style>
 body{margin:0;background:#0c100e;color:#e8e4d8;font-family:Georgia,'Iowan Old Style',serif;line-height:1.6}
 .wrap{max-width:980px;margin:0 auto;padding:30px 22px 70px}
 .eyebrow{font-family:Consolas,monospace;font-size:11px;letter-spacing:1.4px;color:#d9b24c;text-transform:uppercase}
 h1{font-size:27px;font-weight:600;margin:8px 0 4px} h2{font-size:17px;margin:24px 0 6px;color:#f0ead8}
 .lead{font-size:14px;color:#cfc9b6;max-width:80ch}
 .meta{font-family:Consolas,monospace;font-size:11px;color:#9a957f;margin:8px 0}
 .kpis{display:flex;gap:10px;flex-wrap:wrap;margin:12px 0}
 .kpi{border:1px solid rgba(255,255,255,.1);border-radius:11px;padding:10px 14px;background:rgba(255,255,255,.02)}
 .kpv{font-family:Consolas,monospace;font-size:22px;font-weight:700;color:#d9b24c} .kpl{font-size:11px;color:#9a957f}
 table{width:100%;border-collapse:collapse;margin:8px 0;font-size:12.5px}
 th,td{text-align:left;padding:6px 8px;border-bottom:1px solid rgba(255,255,255,.08)} th{color:#9a957f;font-family:Consolas,monospace;font-size:10.5px;text-transform:uppercase;letter-spacing:.5px}
 .num{font-family:Consolas,monospace;text-align:right} .recuse{color:#e06a4a;font-weight:600}
 .mtg{border:1px solid rgba(255,255,255,.1);border-radius:12px;padding:12px 15px;margin:9px 0;background:rgba(255,255,255,.02)}
 .mh{display:flex;justify-content:space-between;gap:10px;align-items:baseline;flex-wrap:wrap}
 .md{font-family:Consolas,monospace;font-size:12px;color:#d9b24c} .mb{font-size:14px;font-weight:600}
 .mo{font-family:Consolas,monospace;font-size:11px;color:#9a957f;margin-top:3px} .mo a{color:#9fd9bf}
 .none{font-size:13px;color:#9a957f;font-style:italic} a{color:#d9b24c}
 .disc{font-size:12px;color:#9a957f;font-style:italic;border-left:2px solid rgba(217,178,76,.4);padding:7px 12px;margin:14px 0}
 .jrow{display:flex;justify-content:space-between;gap:10px;align-items:baseline;text-decoration:none;color:inherit;border-bottom:1px solid rgba(255,255,255,.08);padding:10px 4px}
 .jrow:hover{background:rgba(217,178,76,.05)} .jn{font-size:15px;font-weight:600} .js{font-family:Consolas,monospace;font-size:11px;color:#9a957f}
 footer{margin-top:30px;border-top:1px solid rgba(255,255,255,.1);padding-top:12px;font-family:Consolas,monospace;font-size:10.5px;color:#9a957f}
</style>"""

def officials_table(officials):
    if not officials: return ""
    rows = "".join('<tr><td>%s</td><td class="num">%d</td><td class="num">%d</td><td class="num">%d</td><td class="num %s">%d</td></tr>' % (
        esc(o["name"]), o["meetings"], o["ayes"], o["noes"], ("recuse" if o["recused"] else ""), o["recused"]) for o in officials)
    return ('<h2>Members — recorded roll-call</h2><table><tr><th>Member</th><th>Mtgs</th><th>Ayes</th><th>Noes</th><th>Recused</th></tr>%s</table>' % rows)

def meeting_html(m):
    links = ""
    if m.get("minutes_url"):   links += '<a href="%s" target="_blank" rel="noopener">minutes &#8599;</a> ' % esc(m["minutes_url"])
    if m.get("materials_url"): links += '<a href="%s" target="_blank" rel="noopener">materials &#8599;</a> ' % esc(m["materials_url"])
    # note: m["report"] is an internal votes/*.html artifact not published to the site — do not link it
    n_items = len(m.get("items", []))
    oc = []
    if m.get("carried"): oc.append("%d carried" % m["carried"])
    if m.get("failed"):  oc.append("%d failed" % m["failed"])
    if n_items:          oc.append("%d items" % n_items)
    rec = (' &middot; <span class="recuse">recused: %s</span>' % esc(", ".join(m["recusals"]))) if m.get("recusals") else ""
    return '<div class="mtg"><div class="mh"><span class="mb">%s</span><span class="md">%s</span></div><div class="mo">%s%s<br>%s</div></div>' % (
        esc(m.get("body") or "Meeting"), esc(m.get("date") or ""), " &middot; ".join(oc) or "record", rec,
        links or '<span class="none">link pending</span>')

def xnav(tid):
    out = []
    for pat, lbl in [("crosswalk_%s.html","charter ⇄ law"), ("agendas_%s.html","agendas"), ("money_%s.html","money"), ("parity_%s.html","parity")]:
        if os.path.exists(os.path.join(MAUIOS, pat % tid)): out.append('<a href="%s">%s</a>' % (pat % tid, lbl))
    out.append('<a href="n53_engine.html">N53 engine</a>'); out.append('<a href="jurisdictions.html">all jurisdictions</a>')
    return " &middot; ".join(out)

def archive_page(tid, e):
    nm = e["name"]; g = now_hst().strftime("%Y-%m-%d %H:%M HST")
    mts = "".join(meeting_html(m) for m in e["meetings"]) or '<div class="none">No past meetings captured yet — source identified, ingestion pending.</div>'
    badge = "live roll-call (parsed minutes)" if e["votes_structured"] and e["votes"] else ("minutes/materials links" if e["meetings"] else "source pending")
    extra = ""
    if e.get("meetings_total", 0) > len(e["meetings"]):
        extra = '<div class="meta">showing the %d most recent of %d meetings on file.</div>' % (len(e["meetings"]), e["meetings_total"])
    return """<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Archive — %s — N53 · Kilo Aupuni</title>%s</head><body><div class="wrap">
<div class="eyebrow">12 Stones Global &middot; Kilo Aupuni &middot; N53 Ka Luna Kiaʻi &middot; %s</div>
<h1>Past record &mdash; %s</h1>
<p class="lead">The minutes, supplemental materials, and roll-call votes the N53 integrity engine reads &mdash;
the actual record of what was decided and who voted. Every item links to its source; nothing is inferred.</p>
<div class="kpis"><div class="kpi"><div class="kpv">%d</div><div class="kpl">meetings ingested</div></div>
<div class="kpi"><div class="kpv">%s</div><div class="kpl">roll-call votes</div></div>
<div class="kpi"><div class="kpv">%d</div><div class="kpl">recusals (conflict signal)</div></div></div>
<div class="meta">mode: %s &middot; source: %s</div>%s
<!-- src -->
<div class="disc">%s</div>
%s
<h2>Meetings</h2>%s
<p style="margin-top:14px">%s</p>
<footer>generated %s &middot; n53-ingest v2 &middot; minutes/votes from the official record &middot; Kilo Aupuni &middot; aloha &middot; pono</footer>
</div></body></html>""" % (esc(nm), CSS, esc(nm), esc(nm), len(e["meetings"]),
        ("{:,}".format(e["votes"]) if e["votes"] else "—"), e["recusals"], esc(badge),
        (('<a href="%s" target="_blank" rel="noopener">%s</a>' % (esc(e["source"]), esc(e["source"])))
         if str(e.get("source", "")).startswith("http") else (esc(e["source"]) or "—")),
        extra, esc(e["note"]), officials_table(e.get("officials", [])), mts, xnav(tid), g)

def index_page(corpus):
    g = corpus["generated"]; rows = ""
    for tid, e in corpus["tenants"].items():
        tag = ("%s votes · %d recusals" % ("{:,}".format(e["votes"]), e["recusals"])) if e["votes"] else ("%d meetings" % len(e["meetings"]) if e["meetings"] else "pending")
        rows += '<a class="jrow" href="archive_%s.html"><span class="jn">%s</span><span class="js">%s</span></a>' % (tid, esc(e["name"]), esc(tag))
    return """<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>N53 — the past record, every tenant</title>%s</head><body><div class="wrap">
<div class="eyebrow">12 Stones Global &middot; Kilo Aupuni &middot; N53 Ka Luna Kiaʻi</div>
<h1>N53 &mdash; the integrity engine's record</h1>
<p class="lead">Ka Luna Kiaʻi, the Overseer, reads the actual minutes and roll-call votes to test parity &mdash;
a vote that doesn't answer its district, a contract that doesn't answer its donor. The corpus per tenant:</p>
<div style="margin-top:12px">%s</div>
<p style="margin-top:16px"><a href="n53_engine.html">the N53 engine &rarr;</a> &middot; <a href="parity_check.html">parity — pairs that no longer answer</a> &middot; <a href="jurisdictions.html">all jurisdictions</a></p>
<footer>generated %s &middot; n53-ingest index &middot; Kilo Aupuni</footer></div></body></html>""" % (CSS, rows, g)

def engine_page(corpus):
    g = corpus["generated"]; T = corpus["tenants"]
    tot_v = sum(e["votes"] for e in T.values()); tot_r = sum(e["recusals"] for e in T.values())
    tot_m = sum(e.get("meetings_total", len(e["meetings"])) for e in T.values())
    live = [e["name"] for e in T.values() if e["votes_structured"] and e["votes"]]
    recs = ""
    for tid, e in T.items():
        for m in e["meetings"]:
            if m.get("recusals"):
                recs += '<div class="mtg"><div class="mo"><b>%s</b> &middot; %s &middot; <span class="recuse">recused: %s</span> %s</div></div>' % (
                    esc(e["name"]), esc(m["date"]), esc(", ".join(m["recusals"])),
                    ('<a href="%s" target="_blank" rel="noopener">minutes &#8599;</a>' % esc(m["minutes_url"])) if m.get("minutes_url") else "")
    recs = recs or '<div class="none">No recusals in the currently-ingested window.</div>'
    return """<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>N53 — Ka Luna Kiaʻi, the integrity engine</title>%s</head><body><div class="wrap">
<div class="eyebrow">12 Stones Global &middot; Kilo Aupuni &middot; N53 &middot; aloha &middot; pono</div>
<h1>N53 &mdash; Ka Luna Kia&#699;i, the Overseer</h1>
<p class="lead">The integrity engine reads the real record to find a <b>broken pair</b> &mdash; an output that no
longer answers its input. Its money side is CSC donations &times; HANDS contracts; its <b>votes side</b> is the
roll-call + recusals ingested from official minutes. A recusal is the cleanest signal: a member formally
declaring a conflict on a specific money item.</p>
<div class="kpis"><div class="kpi"><div class="kpv">%d</div><div class="kpl">meetings on file</div></div>
<div class="kpi"><div class="kpv">%s</div><div class="kpl">roll-call votes</div></div>
<div class="kpi"><div class="kpv">%d</div><div class="kpl">recusals</div></div></div>
<div class="meta">live roll-call tenants: %s</div>
<h2>Recusals — declared conflicts (the cleanest broken-pair signal)</h2>
%s
<div class="disc">Every datum links to its source minutes; recusals and votes are facts, and any money&times;vote
correlation is posed as a QUESTION for further reporting, never an accusation. The corpus grows each day the
checker runs. Where roll-call is locked inside PDF prose or a non-English record, the minutes link is captured
and structured parsing is marked pending &mdash; never invented.</div>
<p style="margin-top:10px"><a href="archive.html">browse every tenant's past record &rarr;</a> &middot;
<a href="parity_check.html">parity — pairs that no longer answer</a></p>
<footer>generated %s &middot; N53 Ka Luna Kiaʻi &middot; corpus: n53_corpus.json &middot; Kilo Aupuni &middot; aloha &middot; pono</footer>
</div></body></html>""" % (CSS, tot_m, "{:,}".format(tot_v), tot_r, esc(", ".join(live) or "(none this run)"), recs, g)

def main():
    os.makedirs(MAUIOS, exist_ok=True)
    corpus = build_corpus()
    open(CORPUS, "w", encoding="utf-8", newline="\n").write(json.dumps(corpus, ensure_ascii=False, indent=1))
    for tid, e in corpus["tenants"].items():
        open(os.path.join(MAUIOS, "archive_%s.html" % tid), "w", encoding="utf-8", newline="\n").write(archive_page(tid, e))
    open(os.path.join(MAUIOS, "archive.html"), "w", encoding="utf-8", newline="\n").write(index_page(corpus))
    open(os.path.join(MAUIOS, "n53_engine.html"), "w", encoding="utf-8", newline="\n").write(engine_page(corpus))
    tv = sum(e["votes"] for e in corpus["tenants"].values()); tr = sum(e["recusals"] for e in corpus["tenants"].values())
    print("n53-ingest: %d tenants; %s roll-call votes, %d recusals in corpus; archive+engine written"
          % (len(corpus["tenants"]), "{:,}".format(tv), tr))
    return 0

if __name__ == "__main__":
    import sys; sys.exit(main())
