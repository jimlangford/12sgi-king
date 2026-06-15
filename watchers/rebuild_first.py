#!/usr/bin/env python3
"""rebuild_first.py — "Who Rebuilt First" — the Lahaina/Kula disaster-recovery permit line.

Practical influence made visible: after the 2023 fire, WHO reached the front of the rebuild-permit
line? Built from the Maui County EnerGov permit record (mapps_watch.py → permits_index.jsonl). Each
permit is public record; the page orders the fire-recovery permits by application date and shows
status (Issued vs still In Review) — so a reader can see who got through, and who is waiting.

HONEST LIMITS (stated on the page, never hidden):
  - The permit INDEX is a recent snapshot window, not the full since-2023 history — so this shows the
    current rebuild pipeline, not the complete first-to-last ordering. (Deeper history = a fuller pull.)
  - The index carries the OWNER / project, not the CONTRACTOR / architect — those live in each permit's
    detail page (a deeper pull). So contractor-level "who builds" is marked pending, not guessed.
Front end = factual + a question, never an accusation. Output: reports/mauios/rebuild_first.html
"""
import os, json, re, html
from datetime import datetime, timezone, timedelta

HOME    = os.path.expanduser("~")
PROJECT = os.path.join(HOME, "Documents", "Claude", "Projects", "Video System elementLOTUS")
MAUIOS  = os.path.join(PROJECT, "reports", "mauios")
IDX     = os.path.join(MAUIOS, "permits_index.jsonl")
OUT     = os.path.join(MAUIOS, "rebuild_first.html")
HST     = timezone(timedelta(hours=-10))
esc     = lambda s: html.escape(str(s or ""))
def now_hst(): return datetime.now(HST)

def area(a):
    a = (a or "").upper()
    return "Lahaina" if "LAHAINA" in a else ("Kula" if "KULA" in a else None)
def owner(desc):
    d = re.sub(r"\(2023 FIRE\)\s*", "", desc or "").strip()
    return d[:70]
ISSUED = {"issued", "inspections authorized", "payment received", "waiting for payment", "co issued"}

def main():
    rows = []
    try:
        for l in open(IDX, encoding="utf-8"):
            if l.strip(): rows.append(json.loads(l))
    except Exception:
        rows = []
    def isfire(r):
        t = (r.get("type", "") or "").lower()
        return "(2023 fire)" in json.dumps(r, ensure_ascii=False).lower() or "disaster recovery" in t
    fire = [r for r in rows if isfire(r) and area(r.get("address", ""))]
    fire.sort(key=lambda r: (r.get("applied", "") or ""))
    g = now_hst().strftime("%Y-%m-%d %H:%M HST")
    n_iss = sum(1 for r in fire if (r.get("status", "") or "").lower() in ISSUED)
    rng = ((fire[0].get("applied", "") or "")[:10] + " → " + (fire[-1].get("applied", "") or "")[:10]) if fire else "—"
    def row(r):
        st = (r.get("status", "") or "")
        cls = "iss" if st.lower() in ISSUED else "rev"
        return ('<div class="p"><span class="pd">%s</span><span class="pa">%s</span>'
                '<span class="ps %s">%s</span><span class="po">%s</span>'
                '<span class="paddr">%s · %s</span></div>') % (
            esc((r.get("applied", "") or "")[:10]), esc(area(r.get("address", ""))), cls, esc(st),
            esc(owner(r.get("desc", ""))), esc((r.get("type", "") or "")[:34]), esc((r.get("address", "") or "")[:36]))
    body = "".join(row(r) for r in fire) or '<div class="none">No fire-recovery permits in the current index window.</div>'
    CSS = ("<style> body{margin:0;background:#0c100e;color:#e8e4d8;font-family:Georgia,serif;line-height:1.6}"
           " .wrap{max-width:960px;margin:0 auto;padding:30px 22px 70px}"
           " .eyebrow{font-family:Consolas,monospace;font-size:11px;letter-spacing:1.4px;color:#d9b24c;text-transform:uppercase}"
           " h1{font-size:27px;font-weight:600;margin:8px 0 4px} h2{font-size:16px;margin:22px 0 6px;color:#f0ead8}"
           " .lead{font-size:14px;color:#cfc9b6;max-width:80ch}"
           " .kpis{display:flex;gap:10px;flex-wrap:wrap;margin:12px 0}"
           " .kpi{border:1px solid rgba(255,255,255,.1);border-radius:11px;padding:10px 14px;background:rgba(255,255,255,.02)}"
           " .kpv{font-family:Consolas,monospace;font-size:21px;font-weight:700;color:#d9b24c} .kpl{font-size:11px;color:#9a957f}"
           " .p{display:flex;gap:10px;align-items:baseline;flex-wrap:wrap;padding:7px 2px;border-bottom:1px solid rgba(255,255,255,.07);font-size:13px}"
           " .pd{font-family:Consolas,monospace;font-size:12px;color:#d9b24c;min-width:84px} .pa{font-size:11px;color:#9fd9bf;min-width:58px}"
           " .ps{font-family:Consolas,monospace;font-size:10px;padding:1px 7px;border-radius:7px;min-width:80px}"
           " .ps.iss{background:rgba(86,192,138,.16);color:#56c08a} .ps.rev{background:rgba(224,106,74,.14);color:#e06a4a}"
           " .po{font-weight:600;color:#e8e4d8;flex:1;min-width:180px} .paddr{font-size:11px;color:#9a957f;width:100%}"
           " .q{font-size:13px;color:#bdb8a4;background:rgba(217,178,76,.06);border-radius:8px;padding:10px 13px;margin:14px 0}"
           " .disc{font-size:12px;color:#9a957f;font-style:italic;border-left:2px solid rgba(217,178,76,.4);padding:7px 12px;margin:14px 0}"
           " a{color:#d9b24c} .none{font-size:13px;color:#9a957f;font-style:italic}"
           " footer{margin-top:28px;border-top:1px solid rgba(255,255,255,.1);padding-top:12px;font-family:Consolas,monospace;font-size:10.5px;color:#9a957f}"
           "</style>")
    page = ("<!DOCTYPE html><html lang=\"en\"><head><meta charset=\"UTF-8\">"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
        "<title>Who Rebuilt First — Lahaina &amp; Kula — govOS · Kilo Aupuni</title>" + CSS +
        "</head><body><div class=\"wrap\">"
        "<div class=\"eyebrow\">12 Stones Global · Kilo Aupuni · Maui County · aloha · pono</div>"
        "<h1>Who Rebuilt First — Lahaina &amp; Kula</h1>"
        "<p class=\"lead\">After the 2023 fire, who reached the front of the rebuild line? Every building permit is "
        "public record. Here the fire-recovery permits are ordered by the date applied, with status shown — so the "
        "order of the rebuild is visible: who is <b>Issued</b> and building, and who is still <b>In Review</b> and waiting.</p>"
        "<div class=\"kpis\">"
        "<div class=\"kpi\"><div class=\"kpv\">" + str(len(fire)) + "</div><div class=\"kpl\">fire-recovery permits (this window)</div></div>"
        "<div class=\"kpi\"><div class=\"kpv\">" + str(n_iss) + "</div><div class=\"kpl\">cleared to build / paying</div></div>"
        "<div class=\"kpi\"><div class=\"kpv\">" + esc(rng) + "</div><div class=\"kpl\">applied-date range</div></div></div>"
        "<div class=\"q\"><b>The question for the record:</b> when a commercial entity&rsquo;s rebuild permit issues "
        "while homeowners&rsquo; applications sit in review, does the rebuild line answer the greatest need — or the "
        "greatest reach? A question grounded in the public permit record, for reporting and verification — not a "
        "finding against any applicant.</div>"
        "<h2>The rebuild line — earliest application first</h2>" + body +
        "<div class=\"disc\">Source: Maui County EnerGov permit record (mapps_watch). HONEST LIMITS: this is a recent "
        "index window, not the full since-2023 history (deeper history = a fuller pull); and the index carries the "
        "OWNER / project, not the CONTRACTOR / architect — contractor-level &ldquo;who builds&rdquo; lives in each "
        "permit&rsquo;s detail page and is a deeper pull, marked pending rather than guessed. "
        "<b><a href=\"request_records.html#county-permits\">→ Request this record (and send it back)</a></b> — "
        "a ready-to-file UIPA request for the contractor &amp; architect on every rebuild permit.</div>"
        "<p style=\"margin-top:8px\"><a href=\"wildfire_recovery_watch.html\">wildfire recovery money</a> · "
        "<a href=\"contracts_x_donors.html\">contracts × donors</a> · <a href=\"testimony_record.html\">who testified</a> · "
        "<a href=\"jurisdictions.html\">all jurisdictions</a></p>"
        "<footer>generated " + g + " · rebuild-first v1 · source: Maui County EnerGov permits (public record) · "
        "Kilo Aupuni · aloha · pono</footer></div></body></html>")
    open(OUT, "w", encoding="utf-8", newline="\n").write(page)
    print("rebuild-first: %d fire-recovery permits (Lahaina/Kula), %d issued/paying; range %s" % (len(fire), n_iss, rng))
    return 0

if __name__ == "__main__":
    import sys; sys.exit(main())
