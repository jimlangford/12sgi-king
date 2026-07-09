#!/usr/bin/env python3
"""case_document.py — TENANT-LEVEL case documents, governed by the AUDIT WISDOM.
   (Jimmy 2026-06-18: "prosecutor features handled by the audit wisdom … write up actual
   tenant-level documents to have approve and send to court if necessary.")

WHAT THIS IS — and is NOT.
  This turns the prosecutorial back end (prosecutor.py) into a FORMAL, per-tenant DRAFT document a
  human can read, APPROVE, and — only if counsel agrees — route to the lawful channel. It is
  prosecutorial WORK PRODUCT: allegations to be PROVEN by named public records, never established
  guilt; every fact is sourced + dated; nothing is fabricated. It is NOT a filed pleading and it
  does not file anything — routing to Corporation Counsel / Board of Ethics / OIP / the Prosecuting
  Attorney / a court is Jimmy's decision with a licensed attorney.

THE AUDIT WISDOM (the integrity gate every document passes through — christ-aloha: rigor + aloha):
  1. SOURCED — every factual assertion traces to a named public record (HANDS, CSC, HSEC, county
     minutes, EnerGov, qPublic) WITH the record named. Unsourced assertion → not stated as fact.
  2. ALLEGATION, NOT VERDICT — conclusions are framed as questions / theories to be proven.
  3. RECORD-HONEST — where the record is insufficient, the document says so and lists the UIPA
     requests to file FIRST, instead of overclaiming. A thin tenant gets a record-building plan,
     not a manufactured case.
  4. PRIVATE — written to reports/_status/case_documents/ (owner-only; the _status dir is never in
     the public publish path; leak-gate enforces it). Never committed, never published.
  5. APPROVABLE — each document carries an explicit approval + counsel sign-off block, so nothing
     advances to a lawful channel without a human (and a lawyer) signing.

Sources reused: prosecutor.build_cases() (Maui, the richest record) + each tenant's connected data
(orgs_<t>, realestate_<t>, money_<t> — people_trace / realestate_county / statewide_money output).
"""
import os, sys, json, html
from datetime import datetime, timezone, timedelta

HOME    = os.path.expanduser("~")
PROJECT = os.path.join(HOME, "Documents", "Claude", "Projects", "Video System elementLOTUS")
MAUIOS  = os.path.join(PROJECT, "reports", "mauios")
OUT_DIR = os.path.join(PROJECT, "reports", "_status", "case_documents")   # PRIVATE — never published
HST     = timezone(timedelta(hours=-10))
TOOL_DIR = os.path.dirname(os.path.abspath(__file__))
if TOOL_DIR not in sys.path: sys.path.insert(0, TOOL_DIR)
esc = lambda s: html.escape(str(s or ""))
def now_hst(): return datetime.now(HST)
def load(p, d):
    try: return json.load(open(p, encoding="utf-8"))
    except Exception: return d

# Tenants (the governments). Maui = the proof tenant with the deepest record; the others are at the
# record-building stage and get an honest UIPA-first plan rather than a manufactured case.
TENANTS = [
    {"id": "hi-maui",     "name": "Maui County",                 "channel_local": "Maui County Department of the Corporation Counsel + Maui Board of Ethics", "rich": True},
    {"id": "hi-honolulu", "name": "City & County of Honolulu",   "channel_local": "Honolulu Department of the Corporation Counsel + Honolulu Ethics Commission", "rich": False},
    {"id": "hi-hawaii",   "name": "Hawaiʻi County",              "channel_local": "Hawaiʻi County Office of the Corporation Counsel + Board of Ethics", "rich": False},
    {"id": "hi-kauai",    "name": "Kauaʻi County",               "channel_local": "Kauaʻi County Office of the County Attorney + Board of Ethics", "rich": False},
    {"id": "hi-state",    "name": "State of Hawaiʻi",            "channel_local": "Hawaiʻi State Ethics Commission + Office of Information Practices (OIP)", "rich": False},
]
# The lawful escalation ladder — the same for every tenant; a matter climbs only as the record warrants.
ESCALATION = [
    "Internal review by the member/agency (disclose · recuse · decide in the open)",
    "{channel_local} — request review under the county/state ethics code",
    "Office of Information Practices (OIP) — UIPA records requests to close every evidence gap",
    "Hawaiʻi State Ethics Commission / County Prosecuting Attorney — if the records sustain the elements",
    "State Attorney General / a court of competent jurisdiction — only on counsel's advice, if warranted",
]

# ── the audit-wisdom integrity gate ──────────────────────────────────────────
def gate(case):
    """Return (verdict, reasons). REVIEW-READY only if it is sourced, allegation-framed, and names the
    next record. Otherwise NEEDS-RECORD: route to UIPA first; do not advance it as fact."""
    reasons = []
    # A NAMED public record — case-insensitive. Includes committee transcripts/testimony, the official
    # Legistar agenda/minutes system, and a direct URL to a public record (http...), all of which are
    # public records the gate must credit (discernment hardened 2026-06-18 — was a false-negative that
    # held genuinely-sourced matters at NEEDS-RECORD).
    _SRC = ("hands","csc","hsec","officials.json","minutes","energov","public record","qpublic","cfb",
            "boe","transcript","testimony","legistar","council meeting","recused","http")
    sourced = any(e.get("v") and any(t in str(e["v"]).lower() for t in _SRC) for e in case.get("evidence", []))
    if not sourced: reasons.append("no named public-record source in the evidence chain")
    has_next = bool(case.get("next"))
    if not has_next: reasons.append("no next-record (UIPA) named to close the gap")
    theory = (case.get("theory","") + " " + case.get("question","")).lower()
    verdicty = [w for w in ("is guilty","proven that","established that","conclusively","clearly broke the law") if w in theory]
    if verdicty: reasons.append("verdict-style language (must be framed as an allegation/question): " + ", ".join(verdicty))
    framed_q = "?" in case.get("question","")
    if not framed_q: reasons.append("front-end question not framed as a question")
    ready = sourced and has_next and not verdicty and framed_q and (case.get("strength",0) >= 3)
    if case.get("strength",0) < 3: reasons.append("evidence strength < 3 — preliminary, build the record")
    return ("REVIEW-READY" if ready else "NEEDS-RECORD"), reasons

# ── per-tenant connected-data summary (for tenants still building the record) ──
def tenant_connections(tid):
    """Honest read of what is already CONNECTED for a tenant (no fabrication) from the public pages'
    backing data — the 'keep connecting the data' layer, surfaced for the record-building plan."""
    out = []
    vdj = load(os.path.join(MAUIOS, "vendor_donor_join.json"), {})
    if tid == "hi-maui" and (vdj.get("matched")):
        out.append("%d contract×donor overlaps joined (HANDS awards × CSC donors)" % len(vdj["matched"]))
    par = load(os.path.join(MAUIOS, "parity_check.json"), {})
    if par.get("open"):
        out.append("%s money×votes pair(s) flagged open to examine (parity_check)" % par.get("open"))
    # realtor names + profits since 2000 (the RE money trace) — report presence, never invent figures
    re_html = os.path.join(MAUIOS, "realestate_%s.html" % tid.replace("hi-",""))
    if os.path.exists(re_html):
        out.append("real-estate × giving page present (realestate_%s) — donor↔recorded-property trace" % tid.replace("hi-",""))
    org_html = os.path.join(MAUIOS, "orgs_%s.html" % tid.replace("hi-",""))
    if os.path.exists(org_html):
        out.append("donor-employer org groupings present (orgs_%s) — officers/execs on the record" % tid.replace("hi-",""))
    return out

usd = lambda n: "{:,.0f}".format(n or 0)

def _case(cid, title, theory, question, elements, evidence, strength, nxt):
    return {"id": cid, "title": title, "theory": theory, "question": question,
            "elements": elements, "evidence": evidence, "strength": strength, "next": nxt}

def org_matters(tenant):
    """Tenant-level matters built from people_trace.json — the sourced (CSC) donor-employer org
    groupings. PRELIMINARY by design: framed as a question, every figure sourced, but strength 2 so
    the gate holds them NEEDS-RECORD until the votes/contracts touching the org are joined. This is
    how Honolulu/Hawaiʻi/Kauaʻi get REAL matters (not '0') without fabricating a verdict."""
    pt = load(os.path.join(PROJECT, "reports", "_status", "people_trace.json"), {})
    orgs = ((pt.get("tenants", {}) or {}).get(tenant["id"], {}) or {}).get("orgs", [])
    matters = []
    for o in sorted(orgs, key=lambda x: -(x.get("total") or 0))[:6]:
        name = o.get("name") or "org"; total = o.get("total") or 0; npl = o.get("n_people") or 0
        offs = o.get("officers", [])[:5]
        off_str = ", ".join("%s (%s)" % (x.get("name"), x.get("title")) for x in offs if x.get("name"))
        ev = [{"k": "money", "v": "%s — $%s in contributions to this council through %d giver(s) (Hawaiʻi Campaign Spending Commission, public record)" % (name, usd(total), npl)}]
        if off_str: ev.append({"k": "context", "v": "officers/executives on the record (CSC employer field): %s" % off_str})
        matters.append(_case(
            "ORG-" + name[:22], "Concentrated giving — %s" % name,
            "An employer's people gave $%s to this council through %d giver(s), several of them officers. Theory to PROVE (not yet established): a later council decision — a contract, permit, land-use entitlement, or appointment — answered the organization's interest rather than the public's, and a funded member did not disclose or recuse." % (usd(total), npl),
            "When an organization's people fund a council together, does a later decision answer the organization — or the public?",
            ["The org's combined giving + the officers who gave (CSC)",
             "A specific council decision touching the org's interest (vote / contract / permit / land use)",
             "Whether the funded member disclosed or recused",
             "The outcome vs. the public interest"],
            ev, 2,
            "UIPA: this council's roll-call votes + any contract/permit/land-use action touching %s; cross the action dates to the giving dates; financial-disclosure statements of the deciding members." % name))
    return matters

def tenant_cases(tenant, maui_cases):
    """Per-tenant case list. Maui = the rich prosecutor logic + its org matters; the other HI
    counties = org matters from people_trace (real, sourced, preliminary). Tenants with neither
    return [] and the document honestly becomes a record-building plan."""
    cases = list(maui_cases) if tenant["id"] == "hi-maui" else []
    cases += org_matters(tenant)
    return cases

# ── document render ───────────────────────────────────────────────────────────
def document(tenant, cases):
    g = now_hst().strftime("%Y-%m-%d %H:%M HST")
    ready = [c for c in cases if c["_verdict"] == "REVIEW-READY"]
    prelim = [c for c in cases if c["_verdict"] != "REVIEW-READY"]
    esc_ladder = [step.format(channel_local=tenant["channel_local"]) for step in ESCALATION]

    def case_block(c, n):
        ev = "".join("<li><span class=ek>%s</span> %s</li>" % (esc(e.get("k","")), esc(e.get("v",""))) for e in c.get("evidence",[]))
        el = "".join("<li>%s</li>" % esc(x) for x in c.get("elements",[]))
        gate_reasons = (" · ".join(c["_reasons"])) if c["_reasons"] else "meets the integrity bar"
        return """<div class="matter">
  <div class="mh"><span class="mid">Matter %d · %s</span><span class="badge %s">%s · strength %d</span></div>
  <div class="mt">%s</div>
  <div class="sec"><span class="lab">Nature of the matter (allegation to be proven — not a finding)</span><p>%s</p></div>
  <div class="sec"><span class="lab">The question for the lawful channel</span><p class="q">&ldquo;%s&rdquo;</p></div>
  <div class="sec"><span class="lab">Elements to establish</span><ul>%s</ul></div>
  <div class="sec"><span class="lab">Statement of facts — each on the public record</span><ul class="ev">%s</ul></div>
  <div class="sec"><span class="lab">Records still required to close the gap (file these first)</span><p>%s</p></div>
  <div class="sec gatel"><span class="lab">Audit-wisdom gate</span><p>%s — <b>%s</b></p></div>
</div>""" % (n, esc(c["id"]), "ready" if c["_verdict"]=="REVIEW-READY" else "prelim", esc(c["_verdict"]),
            c.get("strength",0), esc(c["title"]), esc(c["theory"]), esc(c["question"]),
            el, ev, esc(c.get("next","")), esc(c["_verdict"]), esc(gate_reasons))

    matters = "".join(case_block(c, i+1) for i, c in enumerate(ready + prelim))
    conns = tenant_connections(tenant["id"])
    conn_html = ("<ul>" + "".join("<li>%s</li>" % esc(x) for x in conns) + "</ul>") if conns else \
                "<p>No tenant-level joins connected yet — the record-building UIPA requests below come first.</p>"
    ladder = "".join("<li>%s</li>" % esc(s) for s in esc_ladder)

    return """<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Case Document — %s — OWNER ONLY / DRAFT</title><style>
 body{margin:0;background:#0a0c10;color:#e8e4d8;font-family:Georgia,'Iowan Old Style',serif;line-height:1.6}
 .wrap{max-width:980px;margin:0 auto;padding:26px 22px 70px}
 .owner{background:rgba(224,106,74,.12);border:1px solid rgba(224,106,74,.4);border-radius:10px;padding:11px 14px;
   font-family:Consolas,monospace;font-size:12px;color:#e9b48a;margin-bottom:14px}
 .eyebrow{font-family:Consolas,monospace;font-size:11px;letter-spacing:1.4px;color:#d9b24c;text-transform:uppercase}
 h1{font-size:26px;font-weight:600;margin:7px 0 3px} h2{font-size:15px;color:#9fd9bf;margin:22px 0 6px;
   font-family:Consolas,monospace;letter-spacing:.5px;text-transform:uppercase}
 .lead{font-size:14px;color:#cfc9b6;max-width:82ch}
 .matter{border:1px solid rgba(255,255,255,.12);border-radius:13px;padding:15px 18px;margin:12px 0;background:rgba(255,255,255,.02)}
 .mh{display:flex;justify-content:space-between;align-items:baseline;gap:10px}
 .mid{font-family:Consolas,monospace;font-size:11px;color:#9a957f}
 .badge{font-family:Consolas,monospace;font-size:10px;padding:2px 7px;border-radius:20px}
 .badge.ready{background:rgba(63,157,85,.18);color:#86e0a6;border:1px solid rgba(63,157,85,.5)}
 .badge.prelim{background:rgba(217,178,76,.12);color:#e6cf86;border:1px solid rgba(217,178,76,.45)}
 .mt{font-size:17px;font-weight:600;color:#f0ead8;margin:4px 0 8px}
 .lab{display:block;font-family:Consolas,monospace;font-size:10px;letter-spacing:.6px;text-transform:uppercase;color:#9fd9bf;margin:9px 0 2px}
 .q{color:#9fd9bf;font-style:italic;border-left:3px solid #2a6b4e;padding:5px 12px}
 ul{margin:3px 0;padding-left:18px} li{font-size:13px;color:#cfc9b6;margin:2px 0}
 .ev .ek{font-family:Consolas,monospace;font-size:9.5px;color:#9a957f;text-transform:uppercase;margin-right:4px}
 .gatel p{font-size:12px;color:#bdb8a4}
 .ladder li{margin:4px 0} .approve{border:1px dashed rgba(159,217,191,.5);border-radius:10px;padding:14px 16px;margin-top:10px;background:rgba(159,217,191,.04)}
 .approve .row{display:flex;gap:18px;flex-wrap:wrap;font-family:Consolas,monospace;font-size:12px;color:#cfc9b6;margin:7px 0}
 .approve .row span{border-bottom:1px solid rgba(255,255,255,.25);min-width:210px;padding-bottom:2px}
 footer{margin-top:28px;border-top:1px solid rgba(255,255,255,.1);padding-top:12px;font-family:Consolas,monospace;font-size:10.5px;color:#9a957f}
</style></head><body><div class="wrap">
<div class="owner">🔒 OWNER ONLY · DRAFT WORK PRODUCT · private King (Tailscale) — NOT published, NOT filed.
Allegations to be PROVEN by the named public records, not established findings. This document does not file
anything; routing to a lawful channel is the owner's decision with a licensed attorney.</div>
<div class="eyebrow">12 Stones Global · Kilo Aupuni · tenant case document</div>
<h1>%s — Case Document</h1>
<p class="lead">A formal, sourced compilation of the public-record patterns concerning %s, prepared for
review and, if counsel agrees, lawful action. Every fact below traces to a public record and is named.
%d matter(s) meet the review bar; %d remain at the record-building stage (UIPA first).</p>

<h2>What is already connected (public record)</h2>
%s

<h2>Matters</h2>
%s

<h2>Lawful escalation path</h2>
<p class="lead">A matter advances one rung only as the record sustains the elements — disclosure and recusal
resolve most; the courts are the last rung, on counsel's advice.</p>
<ol class="ladder">%s</ol>

<h2>Approval — required before any routing</h2>
<div class="approve">
  <div class="row">Reviewed by (owner): <span>&nbsp;</span> Date: <span>&nbsp;</span></div>
  <div class="row">Licensed-counsel sign-off: <span>&nbsp;</span> Bar no.: <span>&nbsp;</span> Date: <span>&nbsp;</span></div>
  <div class="row">Approved to route to: <span>&nbsp;</span></div>
  <div class="row">Withheld / needs more record: <span>&nbsp;</span></div>
</div>

<footer>generated %s · case_document v1 · OWNER ONLY · sources: HANDS · CSC · HSEC · county minutes · EnerGov ·
qPublic (all public record) · integrity: allegations to be proven, sourced, private · Kilo Aupuni · aloha · pono</footer>
</div></body></html>""" % (esc(tenant["name"]), esc(tenant["name"]), esc(tenant["name"]),
        len(ready), len(prelim), conn_html, matters, ladder, g)

def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    # Maui = the rich tenant: reuse prosecutor's verified case logic.
    maui_cases = []
    try:
        import prosecutor
        maui_cases = prosecutor.build_cases()
    except Exception as e:
        print("case_document: prosecutor.build_cases unavailable (%s) — Maui doc will be record-building only" % e)
    summary = []
    for t in TENANTS:
        cases = tenant_cases(t, maui_cases)
        for c in cases:
            v, r = gate(c); c["_verdict"] = v; c["_reasons"] = r
        ready = sum(1 for c in cases if c["_verdict"] == "REVIEW-READY")
        out = os.path.join(OUT_DIR, "case_%s.html" % t["id"])
        open(out, "w", encoding="utf-8", newline="\n").write(document(t, cases))
        summary.append((t["name"], len(cases), ready))
        print("  + %-26s %d matter(s), %d review-ready -> %s" % (t["name"], len(cases), ready, os.path.basename(out)))
    print("case_document: %d tenant document(s) written to reports/_status/case_documents/ (OWNER ONLY, never published)"
          % len(TENANTS))
    return 0

if __name__ == "__main__":
    sys.exit(main())
