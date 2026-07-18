#!/usr/bin/env python3
"""govos_audit.py - the per-tenant govOS Audit dashboard (Jimmy 2026-06-20, "option 2 + call it govOS audit").

ONE page per tenant that puts the whole oversight picture in a single view:
  1. FUNDERS         - who put money into each tracked official (HI Campaign Spending Commission)
  2. VOTES/DECISIONS - how those officials voted / recused, and the money on the agenda (CivicClerk/Legistar)
  3. CONTRACTS       - donors who ALSO got paid by this government (HANDS awards x CSC donors)
  4. THE QUESTIONS   - the overlaps, each a sourced question (never an accusation)

Replaces the spread-out + dark legacy "money x votes" pages with one light govOS-template page per tenant.
Composes already-generated data; honest-empty for tenants with no sourced officials yet (NEEDS-RECORD).
Public / leak-safe: aggregates + public-record links only; private prosecutor case detail stays behind the gate.

CLI:  python govos_audit.py [--tenant maui|hi-honolulu|hi-hawaii|hi-kauai|hi-state|ny|all]
Out:  reports/mauios/govos_audit_<tenant>.html
"""
import os, sys, json, html, time

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.abspath(os.path.join(HERE, "..", ".."))
MAUIOS = os.path.join(PROJECT, "reports", "mauios")

# tenant -> (label, donor_profiles file, vendor_donor_join file, votes_index file)
# Maui uses the canonical unsuffixed files; other tenants use suffixed files that only
# exist once their officials are sourced (until then -> honest empty).
# keyed by canonical tenant id (matches tenants.json + tenant_<id>.html). Maui uses the canonical
# unsuffixed data files; other tenants use suffixed files that only exist once their officials are
# sourced (until then -> honest empty).
TENANTS = {
    "hi-maui":     ("Maui County",              "donor_profiles.json",             "vendor_donor_join.json",             "votes_index.jsonl"),
    "hi-honolulu": ("City & County of Honolulu","donor_profiles_hi-honolulu.json", "vendor_donor_join_hi-honolulu.json", "votes_index_hi-honolulu.jsonl"),
    "hi-hawaii":   ("Hawaii County",            "donor_profiles_hi-hawaii.json",   "vendor_donor_join_hi-hawaii.json",   "votes_index_hi-hawaii.jsonl"),
    "hi-kauai":    ("Kauai County",             "donor_profiles_hi-kauai.json",    "vendor_donor_join_hi-kauai.json",    "votes_index_hi-kauai.jsonl"),
    "hi-state":    ("State of Hawaii",          "donor_profiles_hi-state.json",    "vendor_donor_join_hi-state.json",    "votes_index_hi-state.jsonl"),
    "ny":          ("New York",                 "donor_profiles_ny.json",          "vendor_donor_join_ny.json",          "votes_index_ny.jsonl"),
}


def esc(s):
    return html.escape(str(s if s is not None else ""))


def money(n):
    try:
        return "${:,.0f}".format(float(n))
    except Exception:
        return "$0"


def load_json(fn):
    p = os.path.join(MAUIOS, fn)
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def load_jsonl(fn):
    p = os.path.join(MAUIOS, fn)
    rows = []
    try:
        with open(p, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        rows.append(json.loads(line))
                    except Exception:
                        pass
    except Exception:
        return []
    return rows


CSS = """<style>:root{--bg:#081420;--panel:#0f2540;--line:#26456a;--ink:#eaf2fc;--dim:#9fb2c8;--faint:#7f93aa;--accent:#4a9eff;--accent2:#6cb0f0;--ok:#1f8a5b;--ask:#b8860b}
*{box-sizing:border-box}body{font-family:'Segoe UI Variable Text','Segoe UI',system-ui,sans-serif;max-width:920px;margin:0 auto;padding:18px 16px 48px;color:var(--ink);background:var(--bg);font-size:16px;line-height:1.55}
a{color:var(--accent2)}h1{font-size:1.55rem;margin:.3rem 0}h2{color:var(--accent);font-size:1.08rem;margin:1.6rem 0 .5rem;border-top:1px solid var(--line);padding-top:1rem}
.sub{color:var(--dim);font-size:.95rem;line-height:1.55}
.eyebrow{letter-spacing:.1em;text-transform:uppercase;color:var(--accent2);font-weight:600;font-size:.8rem}
.kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin:1.1rem 0}@media(max-width:620px){.kpis{grid-template-columns:repeat(2,1fr)}}
.kp{background:var(--panel);border:1px solid var(--line);border-radius:11px;padding:.7rem .85rem}.kv{font:700 17px/1.1 'JetBrains Mono',Consolas,monospace;color:var(--accent)}.kl{font-size:11px;color:var(--faint);text-transform:uppercase;letter-spacing:.4px;margin-top:4px}
.note{background:#241d0e;border:1px solid #5c4a1e;border-left:3px solid var(--ask);border-radius:10px;padding:.7rem 1rem;margin:.9rem 0;font-size:.9rem;color:#e3c98a;line-height:1.5}
.empty{background:#0f2540;border:1px dashed var(--line);border-radius:10px;padding:1rem 1.1rem;margin:.9rem 0;color:var(--dim);font-size:.92rem;line-height:1.55}
.row{display:flex;justify-content:space-between;gap:12px;align-items:baseline;border-bottom:1px solid #e3e9f1;padding:.5rem .1rem;font-size:.92rem}
.row .nm{color:var(--ink);min-width:0;overflow-wrap:anywhere;flex:1}.row .amt{font-family:Consolas,monospace;color:var(--accent);text-align:right;flex-shrink:0}.row .rd{color:var(--faint);font-size:.78rem}
.bars{margin:.6rem 0 1rem}.bar{display:grid;grid-template-columns:250px 1fr 96px;gap:10px;align-items:center;margin:.42rem 0;font-size:.88rem}.bar .bn{color:var(--ink);line-height:1.22;overflow:hidden}.bar .bn .nL{display:block;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.bar .bn .sL{display:block;font-size:.72rem;color:var(--faint)}.bar .bn .sL .re{color:var(--ask)}.bar .bn .sL .rcz{color:#f0b0b0}.bar .bt{background:#0f2540;border-radius:99px;height:14px;overflow:hidden}.bar .bt i{display:block;height:14px;border-radius:99px;background:linear-gradient(90deg,#00356b,#1259a3)}.bar .bt i.warm{background:linear-gradient(90deg,#b8860b,#d9a93a)}.bar .bv{font-family:Consolas,monospace;font-weight:700;color:var(--accent);text-align:right}@media(max-width:560px){.bar{grid-template-columns:140px 1fr 78px}}
.q{background:#fff;border:1px solid var(--line);border-left:3px solid var(--accent2);border-radius:10px;padding:.7rem .95rem;margin:.6rem 0;font-size:.92rem;line-height:1.5}
.q .qh{font-weight:600;color:var(--accent)}.q .qs{color:var(--faint);font-size:.8rem;margin-top:.35rem}
.tag{display:inline-block;background:#2a1416;color:#f0b0b0;border:1px solid #6a3030;border-radius:99px;font-size:.72rem;padding:.05rem .5rem;margin-left:.4rem;vertical-align:middle}
.lnk{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:.6rem .9rem;margin:1rem 0;font-size:.9rem;line-height:1.9}
footer{margin-top:36px;border-top:1px solid var(--line);padding-top:12px;font-size:11px;color:var(--faint);line-height:1.6}</style>"""


def footer(tenant, label, sourced):
    g = time.strftime("%Y-%m-%d %H:%M HST")
    if sourced:
        src = ("sources: HI Campaign Spending Commission (campaign money) + HANDS award notices (contracts) + "
               "CivicClerk/Legistar minutes (votes/recusals) &middot; all public record")
    else:
        src = "no tenant data sourced yet &middot; honest-empty by design"
    return ("<footer>govOS Audit &middot; %s &middot; generated %s &middot; %s &middot; "
            "questions, not accusations &middot; private case files stay behind the auth gate. "
            "This is a records-awareness tool; lawful action (records requests, reporting, voting) is the endpoint.</footer>"
            % (esc(label), g, src))


def build(tenant):
    label, df_f, vdj_f, votes_f = TENANTS[tenant]
    profiles = load_json(df_f)            # list of officials w/ funding
    vdj = load_json(vdj_f)                # contracts x donors join
    votes = load_jsonl(votes_f)           # meeting/vote index
    sourced = bool(profiles)

    P = []
    P.append("<!doctype html><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1,viewport-fit=cover'><meta name=theme-color content='#00356b'>")
    P.append("<title>govOS Audit &mdash; %s</title>" % esc(label))
    P.append(CSS)
    P.append("<div class=eyebrow>govOS &middot; %s &middot; asked in aloha</div>" % esc(label))
    P.append("<h1>govOS Audit &mdash; %s</h1>" % esc(label))
    P.append("<div class=sub>One page, the whole oversight picture for <b>%s</b>: who funds the officials, how they vote, "
             "and who the government pays &mdash; with the overlaps surfaced as <b>questions to verify, never accusations</b>. "
             "Every figure links back to the public record.</div>" % esc(label))

    if not sourced:
        P.append("<div class=empty><b>Record still being requested.</b> No officials have been sourced for %s yet, "
                 "so this audit is intentionally empty rather than showing another tenant&rsquo;s data. "
                 "When this tenant&rsquo;s officials + campaign-finance pattern are filled in "
                 "(<code>config/tenant_officials.json</code>) and its award notices pulled, the four sections below populate from the public record."
                 "<br><br>The four sections this page will hold: <b>1.</b> Funders &middot; <b>2.</b> Votes &amp; decisions &middot; "
                 "<b>3.</b> Contracts &times; donors &middot; <b>4.</b> The questions.</div>" % esc(label))
        P.append(footer(tenant, label, sourced=False))
        return "\n".join(P)

    # ---- KPIs ----
    n_officials = len(profiles)
    money_tracked = sum(float(o.get("total", 0) or 0) for o in profiles)
    n_matches = vdj.get("matches", 0) if isinstance(vdj, dict) else 0
    n_meetings = len(votes)
    P.append("<div class=kpis>")
    P.append("<div class=kp><div class=kv>%s</div><div class=kl>Campaign money tracked</div></div>" % money(money_tracked))
    P.append("<div class=kp><div class=kv>%d</div><div class=kl>Officials watched</div></div>" % n_officials)
    P.append("<div class=kp><div class=kv>%d</div><div class=kl>Donor&times;contract matches</div></div>" % n_matches)
    P.append("<div class=kp><div class=kv>%d</div><div class=kl>Meetings on record</div></div>" % n_meetings)
    P.append("</div>")
    P.append("<div class=note>A funder, a vote, and a contract lining up is a <b>question for oversight</b> &mdash; "
             "who gave, who decided, who benefited &mdash; never a finding. The endpoint is lawful action: a records request, a report, a vote.</div>")

    # per-official recusal record (last-name match between donor_profiles key and the votes-index recusals)
    rec_by_off = {}
    for mtg in votes:
        for r in (mtg.get("recusals") or []):
            rec_by_off.setdefault(r, []).append(mtg)
    maxtot = max((float(o.get("total", 0) or 0) for o in profiles), default=0) or 1.0

    # ---- 1. FUNDERS (bar chart) ----
    P.append("<h2>1. Funders &mdash; who puts money into each official</h2>")
    P.append("<div class=sub>Campaign money on record per official (bar = share of the most-funded). The "
             "<span style='color:var(--ask)'>real-estate / development</span> share is called out &mdash; those interests are most often "
             "before a county on permits, zoning, and contracts. Source: HI Campaign Spending Commission.</div>")
    P.append("<div class=bars>")
    for o in sorted(profiles, key=lambda x: float(x.get("total", 0) or 0), reverse=True):
        tot = float(o.get("total", 0) or 0)
        key = o.get("key", "")
        re_ = o.get("realestate", {}) or {}
        re_total = float(re_.get("total", 0) or 0)
        pct = int(round(100.0 * tot / maxtot))
        warm = " warm" if (tot and re_total / tot >= 0.25) else ""   # >=25% real-estate funded -> amber bar
        sub = []
        if re_total > 0:
            sub.append("<span class=re>RE/dev %s</span>" % money(re_total))
        nrec = len(rec_by_off.get(key, []))
        if nrec:
            sub.append("<span class=rcz>%d recusal%s on record</span>" % (nrec, "s" if nrec != 1 else ""))
        sub.append("%d gifts" % (o.get("rows", 0)))
        P.append("<div class=bar><span class=bn><span class=nL>%s</span><span class=sL>%s</span></span>"
                 "<span class=bt><i class='%s' style='width:%d%%'></i></span><span class=bv>%s</span></div>"
                 % (esc(o.get("label", key)), " &middot; ".join(sub), warm.strip(), pct, money(tot)))
    P.append("</div>")

    # ---- 2. VOTES / DECISIONS (per-official, then recent meetings) ----
    P.append("<h2>2. Votes &amp; decisions &mdash; the same officials, on the record</h2>")
    P.append("<div class=sub>For each official above: how often the public record shows them <b>stepping back (recusing)</b> from a "
             "matter &mdash; a recusal is itself part of the record, and the question is always <i>which</i> matters. "
             "Source: CivicClerk / Legistar minutes.</div>")
    P.append("<div class=bars>")
    maxrec = max((len(v) for v in rec_by_off.values()), default=0) or 1
    for o in sorted(profiles, key=lambda x: len(rec_by_off.get(x.get("key", ""), [])), reverse=True):
        key = o.get("key", "")
        recs = rec_by_off.get(key, [])
        n = len(recs)
        when = ", ".join(sorted({r.get("date", "") for r in recs})[:4]) if recs else "none on record in this window"
        pct = int(round(100.0 * n / maxrec))
        P.append("<div class=bar><span class=bn><span class=nL>%s</span><span class=sL>%s</span></span>"
                 "<span class=bt><i class='warm' style='width:%d%%'></i></span><span class=bv>%d</span></div>"
                 % (esc(o.get("label", key)), esc(when), pct, n))
    P.append("</div>")
    P.append("<div class=sub style='margin-top:1rem'>Recent meetings on record &mdash; recusals flagged, biggest dollar item shown:</div>")
    shown = 0
    for m in sorted(votes, key=lambda x: x.get("date", ""), reverse=True):
        if shown >= 10:
            break
        rec = m.get("recusals") or []
        rectag = (" <span class=tag>recusal: %s</span>" % esc(", ".join(rec))) if rec else ""
        amts = m.get("agenda_money") or []
        big = ""
        try:
            nums = sorted({float(str(a).replace("$", "").replace(",", "").rstrip(",")) for a in amts
                           if str(a).replace("$", "").replace(",", "").rstrip(",").replace(".", "", 1).isdigit()}, reverse=True)
            if nums:
                big = " &middot; top item " + money(nums[0])
        except Exception:
            pass
        url = m.get("url", "")
        name = esc(m.get("meeting", "Meeting"))
        link = ("<a href='%s'>%s</a>" % (esc(url), name)) if url else name
        P.append("<div class=row><span class=nm>%s &middot; %s%s</span><span class=amt><span class=rd>%d items%s</span></span></div>"
                 % (esc(m.get("date", "")), link, rectag, len(m.get("items") or []), big))
        shown += 1

    # ---- 3. CONTRACTS x DONORS ----
    P.append("<h2>3. Contracts &times; donors &mdash; who got paid <i>and</i> gave</h2>")
    P.append("<div class=sub>Firms that received government awards AND show up as campaign donors to the officials above, "
             "name-matched from two public datasets (no records request needed). Source: HANDS award notices &times; HI Campaign Spending Commission.</div>")
    matched = vdj.get("matched", []) if isinstance(vdj, dict) else []
    for mm in sorted(matched, key=lambda x: float(x.get("award_total", 0) or 0), reverse=True):
        hits = mm.get("hits", []) or []
        whoto = ", ".join(sorted({h.get("official", "") for h in hits if h.get("official")}))
        contrib = sum(float(h.get("amount", 0) or 0) for h in hits)
        P.append("<div class=row><span class=nm>%s<span class=rd> &middot; gave %s to %s</span></span><span class=amt>%s<span class=rd> &middot; %d awards</span></span></div>"
                 % (esc(mm.get("vendor", "")), money(contrib), esc(whoto or "&mdash;"), money(mm.get("award_total", 0)), mm.get("award_count", 0)))

    # ---- 4. THE QUESTIONS ----
    P.append("<h2>4. The questions &mdash; where the money, the vote, and the contract meet</h2>")
    P.append("<div class=sub>Each overlap below is phrased as a question for the public record to answer.</div>")
    qn = 0
    for mm in sorted(matched, key=lambda x: float(x.get("award_total", 0) or 0), reverse=True):
        for h in (mm.get("hits", []) or []):
            off = h.get("official_label") or h.get("official") or ""
            okey = h.get("official", "")
            nrec = len(rec_by_off.get(okey, []))
            recctx = ""
            if nrec:
                recctx = (" The record already shows %d recusal%s by this official in this window &mdash; do any touch this firm?"
                          % (nrec, "s" if nrec != 1 else ""))
            P.append("<div class=q><div class=qh>%s received %s in government awards and contributed %s to %s.</div>"
                     "<div class=qs>Does the record show whether %s disclosed or recused on matters touching this firm?%s "
                     "&mdash; sourced to HANDS award notices + the Campaign Spending Commission filing. A question, not a finding.</div></div>"
                     % (esc(mm.get("vendor", "")), money(mm.get("award_total", 0)), money(h.get("amount", 0)),
                        esc(okey), esc(off), recctx))
            qn += 1
            if qn >= 25:
                break
        if qn >= 25:
            break
    if qn == 0:
        P.append("<div class=empty>No funder&times;contract overlaps surfaced in the current data &mdash; that absence is also on the record.</div>")

    P.append("<div class=lnk><b>Drill in:</b> <a href='money_behind_officials.html'>who funds the officials</a> &middot; "
             "<a href='contracts_x_donors.html'>contracts &times; donors</a> &middot; "
             "<a href='council_votes_maui.html'>council votes</a> &middot; "
             "<a href='federal_money.html'>federal dollars</a></div>")
    P.append(footer(tenant, label, sourced=True))
    return "\n".join(P)


def write(tenant):
    out = os.path.join(MAUIOS, "govos_audit_%s.html" % tenant)
    htmltext = build(tenant)
    tmp = out + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(htmltext)
    os.replace(tmp, out)
    return out, len(htmltext)


def main():
    args = sys.argv[1:]
    tenant = "all"
    if "--tenant" in args:
        i = args.index("--tenant")
        if i + 1 < len(args):
            tenant = args[i + 1]
    targets = list(TENANTS) if tenant == "all" else [tenant]
    for t in targets:
        if t not in TENANTS:
            print("unknown tenant:", t)
            continue
        out, n = write(t)
        print("wrote %s (%d bytes)" % (out, n))


if __name__ == "__main__":
    main()
