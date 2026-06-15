# -*- coding: utf-8 -*-
"""Build Honolulu money + parity pages from cached real public-record data."""
import json, re
from collections import defaultdict
from datetime import datetime, timezone, timedelta

HST = timezone(timedelta(hours=-10))
g = datetime.now(HST).strftime("%Y-%m-%d %H:%M HST")
MAUIOS = r"C:\Users\12sgi\Documents\Claude\Projects\Video System elementLOTUS\reports\mauios"
esc = lambda s: str(s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
usd = lambda n: f"{n:,.0f}"

money = json.load(open(MAUIOS + r"\_hon_money_tmp.json", encoding="utf-8"))
matches = json.load(open(MAUIOS + r"\_hon_matches_tmp.json", encoding="utf-8"))
hands = json.load(open(MAUIOS + r"\_hands_statewide.json", encoding="utf-8"))["rows"]


def num(s):
    try:
        return float(re.sub(r"[^0-9.]", "", str(s)))
    except Exception:
        return None


HONJUR = {"City and County of Honolulu", "Honolulu Authority for Rapid Transit",
          "City & County of Honolulu - City Council"}
OUTLIER = 500_000_000
vend = defaultdict(lambda: {"t": 0.0, "n": 0, "jur": ""})
outliers, nullc = [], 0
for r in hands:
    if r.get("jurisdiction") not in HONJUR:
        continue
    a = num(r.get("amount"))
    v = (r.get("vendorName") or "").strip()
    if not a or a <= 0:
        nullc += 1
        continue
    if a >= OUTLIER:
        outliers.append({"vendor": v, "amt": a, "title": r.get("title"), "jur": r.get("jurisdiction")})
        continue
    if not v:
        continue
    vend[v]["t"] += a
    vend[v]["n"] += 1
    vend[v]["jur"] = r.get("jurisdiction")
vend_list = sorted(([k, v] for k, v in vend.items()), key=lambda x: -x[1]["t"])
clean_total = sum(v["t"] for v in vend.values())
n_clean = sum(v["n"] for v in vend.values())
outlier_sum = sum(o["amt"] for o in outliers)

# ---------------- PAGE 1: MONEY ----------------
rec_rows = "".join(
    f'<div class="m"><span class="a">${usd(r["total"])}</span><span class="n">{r["n"]}</span>'
    f'<span class="c">{esc(r["name"])}</span></div>' for r in money["recipients"])
don_rows = "".join(
    f'<div class="m"><span class="a">${usd(r["total"])}</span><span class="n">{r["n"]}</span>'
    f'<span class="c">{esc(r["name"])}</span></div>' for r in money["donors"])

money_html = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>Honolulu Council — Campaign Money - Kilo Aupuni</title>
<style>
 body{{margin:0;background:#0c100e;color:#e8e4d8;font-family:Georgia,'Iowan Old Style',serif;line-height:1.55}}
 .wrap{{max-width:940px;margin:0 auto;padding:34px 24px calc(env(safe-area-inset-bottom,0px) + 70px)}}
 .eyebrow{{font-family:Consolas,monospace;font-size:11px;letter-spacing:1.2px;color:#d9b24c;text-transform:uppercase}}
 h1{{font-size:27px;font-weight:600;margin:8px 0 2px}} h2{{font-size:18px;margin:30px 0 6px;font-weight:600}}
 .lead{{font-size:13.5px;color:#bdb8a4;max-width:84ch}}
 .kpi{{display:flex;flex-wrap:wrap;gap:26px;margin:16px 0}}
 .kpi .n{{font-family:Consolas,monospace;font-size:22px;color:#d9b24c}}
 .kpi .l{{font-family:Consolas,monospace;font-size:11px;color:#9a957f;text-transform:uppercase}}
 .disc{{font-size:12px;color:#9a957f;font-style:italic;border-left:2px solid rgba(217,178,76,.4);padding:7px 12px;margin:14px 0}}
 .m{{display:grid;grid-template-columns:140px 50px 1fr;gap:12px;align-items:baseline;padding:6px 0;border-bottom:1px solid rgba(255,255,255,.06)}}
 .m .a{{font-family:Consolas,monospace;font-size:12.5px;color:#d9b24c;text-align:right}}
 .m .n{{font-family:Consolas,monospace;font-size:12px;color:#9a957f;text-align:center}}
 .m .c{{font-size:13px;color:#e8e4d8}}
 .hd{{font-family:Consolas,monospace;font-size:10.5px;color:#756b56;text-transform:uppercase}}
 .q{{background:rgba(217,178,76,.05);border:1px solid rgba(217,178,76,.25);border-radius:10px;padding:12px 15px;margin:18px 0;font-size:13px;color:#cfc9b6}}
 .q b{{color:#e8e4d8}} a{{color:#d9b24c}}
 footer{{margin-top:34px;border-top:1px solid rgba(255,255,255,.1);padding-top:12px;font-family:Consolas,monospace;font-size:10.5px;color:#9a957f}}
</style></head><body><div class="wrap">
<div class="eyebrow">12 Stones Global · Kilo Aupuni · City &amp; County of Honolulu · who funds the deciders</div>
<h1>Honolulu City Council — the Campaign Money</h1>
<p class="lead">Every campaign contribution reported to candidates for the <b>Honolulu City Council</b>, from the
Hawaiʻi Campaign Spending Commission public dataset. Who raises it (the deciders) and who gives it (the funders).
Donating is lawful — this maps the money so it can be read beside the votes and the contracts.</p>
<div class="kpi">
 <div><div class="n">${usd(money['total'])}</div><div class="l">total to Honolulu Council</div></div>
 <div><div class="n">{money['n']:,}</div><div class="l">contributions</div></div>
 <div><div class="n">{money['n_recipients']}</div><div class="l">candidates</div></div>
 <div><div class="n">{money['n_donors']:,}</div><div class="l">distinct donors</div></div>
</div>
<div class="disc">Source: Hawaiʻi Campaign Spending Commission — “Campaign Contributions Received By Hawaii State
and County Candidates” (hicscdata.hawaii.gov, dataset jexd-xbcg), filtered to office = “Honolulu Council.”
Amount fields are stored as text; cleaned and summed in Python. The county <b>Mayor</b> office is not separable
by county in this dataset (“Mayor” pools all counties statewide), so it is omitted here rather than guessed.
Documented facts and open questions, not findings of wrongdoing.</div>
<div class="q"><b>The question.</b> Money is the input to a campaign; a vote is the output of the office. When the
biggest donors to the Council are the same interests that hold business before it — trade unions, developers,
banks, real estate — the question is whether each later decision answers the public, or the people who funded the seat.</div>
<h2>Top recipients — candidates by money raised</h2>
<div class="m hd"><span style="text-align:right">raised</span><span style="text-align:center">#</span><span>candidate</span></div>
{rec_rows}
<h2>Top donors — who funds the Council</h2>
<div class="m hd"><span style="text-align:right">given</span><span style="text-align:center">#</span><span>contributor</span></div>
{don_rows}
<p style="margin-top:20px"><a href="parity_honolulu.html">→ Honolulu contracts × donors (parity)</a>
 · <a href="jurisdictions.html">all govOS jurisdictions</a></p>
<footer>generated {g} · honolulu-money v1 · source: HI Campaign Spending Commission (hicscdata.hawaii.gov jexd-xbcg, public record) · Kilo Aupuni · govOS</footer>
</div></body></html>"""
open(MAUIOS + r"\money_honolulu.html", "w", encoding="utf-8", newline="\n").write(money_html)
print("WROTE money_honolulu.html  total ${:,.0f}".format(money["total"]))

# ---------------- PAGE 2: PARITY ----------------
DONOR_DETAIL = {
    "PROMETHEUS CONSTRUCTION": [("Kiaaina, Esther", 4000.0)],
    "FIRST HAWAIIAN BANK": [("Menor, Ron", 750.0), ("Fukunaga, Carol", 250.0), ("Manahan, Joey", 250.0)],
}
prows = ""
tot_award = tot_contrib = 0.0
for m in sorted(matches, key=lambda x: -(x["award"] / x["contrib"] if x["contrib"] else 0)):
    v, award, contrib = m["vendor"], m["award"], m["contrib"]
    lev = award / contrib if contrib else 0
    tot_award += award
    tot_contrib += contrib
    dd = DONOR_DETAIL.get(v.upper(), [])
    offs = ", ".join(d[0] for d in dd) or "Honolulu Council candidate(s)"
    q = (f"Does {esc(v)}'s ${usd(award)} in Honolulu government awards answer the public, "
         f"or the ${usd(contrib)} given to {esc(offs)} who sit on the Council? "
         f"(public records — a correlation to verify, not a finding)")
    prows += (f'<div class="row"><span class="a">{lev:,.0f}x</span><span class="c"><b>{esc(v)}</b> — '
              f'${usd(award)} in Honolulu awards ({m["awn"]}) / ${usd(contrib)} to {esc(offs)}. '
              f'<span style="color:#9a957f">{q}</span></span></div>')
agg_lev = tot_award / tot_contrib if tot_contrib else 0

vend_rows = "".join(
    f'<div class="m"><span class="a">${usd(v[1]["t"])}</span><span class="n">{v[1]["n"]}</span>'
    f'<span class="c">{esc(v[0])} <span style="color:#756b56">· {esc(v[1]["jur"])}</span></span></div>'
    for v in vend_list[:15])
outlier_note = "; ".join(
    f'{esc(o["vendor"])} ${usd(o["amt"])} ({esc(o["title"])[:60]})' for o in outliers)

parity_html = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>Honolulu — Contracts × Donors (Parity) - Kilo Aupuni</title>
<style>
 body{{margin:0;background:#0c100e;color:#e8e4d8;font-family:Georgia,'Iowan Old Style',serif;line-height:1.55}}
 .wrap{{max-width:960px;margin:0 auto;padding:34px 24px calc(env(safe-area-inset-bottom,0px) + 80px)}}
 .eyebrow{{font-family:Consolas,monospace;font-size:11px;letter-spacing:1.2px;color:#d9b24c;text-transform:uppercase}}
 h1{{font-size:27px;font-weight:600;margin:8px 0 2px}} h2{{font-size:18px;margin:28px 0 6px;font-weight:600}}
 .lead{{font-size:13.5px;color:#bdb8a4;max-width:84ch}}
 .disc{{font-size:12px;color:#9a957f;font-style:italic;border-left:2px solid rgba(217,178,76,.4);padding:6px 12px;margin:14px 0}}
 .kps{{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin:16px 0 6px}}
 @media (max-width:620px){{.kps{{grid-template-columns:repeat(2,1fr)}}}}
 .kp{{background:rgba(255,255,255,.03);border:1px solid rgba(255,255,255,.08);border-radius:10px;padding:11px 13px}}
 .kv{{font-family:Consolas,monospace;font-size:20px;font-weight:700}} .kl{{font-size:10.5px;color:#9a957f;margin-top:2px}}
 .row{{display:flex;gap:12px;align-items:baseline;border-bottom:1px solid rgba(255,255,255,.06);padding:8px 0}}
 .row .a{{font-family:Consolas,monospace;font-size:12.5px;color:#e06a4a;white-space:nowrap;min-width:78px;text-align:right}}
 .row .c{{font-size:12.5px;color:#bdb8a4}}
 .m{{display:grid;grid-template-columns:160px 44px 1fr;gap:12px;align-items:baseline;padding:6px 0;border-bottom:1px solid rgba(255,255,255,.06)}}
 .m .a{{font-family:Consolas,monospace;font-size:12.5px;color:#d9b24c;text-align:right}}
 .m .n{{font-family:Consolas,monospace;font-size:12px;color:#9a957f;text-align:center}} .m .c{{font-size:12.5px;color:#bdb8a4}}
 .q{{background:rgba(217,178,76,.05);border:1px solid rgba(217,178,76,.25);border-radius:10px;padding:12px 15px;margin:16px 0;font-size:13px;color:#cfc9b6}}
 .q b{{color:#e8e4d8}} a{{color:#d9b24c}}
 footer{{margin-top:36px;border-top:1px solid rgba(255,255,255,.1);padding-top:12px;font-family:Consolas,monospace;font-size:10.5px;color:#9a957f}}
</style></head><body><div class="wrap">
<div class="eyebrow">12 Stones Global · Kilo Aupuni · City &amp; County of Honolulu · the pair that answers</div>
<h1>Honolulu — Contracts beside Donors</h1>
<p class="lead">Two public ledgers set side by side: who the City &amp; County of Honolulu (and the Honolulu
Authority for Rapid Transit) <b>pays</b> to build, and who <b>funds</b> the Honolulu City Council that approves
the budgets. Where the same name appears in both, it is placed here as a <b>question</b> — never an accusation.</p>
<div class="disc">Sources: HANDS contract awards (Hawaiʻi awards feed) filtered to Honolulu jurisdictions ×
Hawaiʻi Campaign Spending Commission donors (hicscdata.hawaii.gov jexd-xbcg, office = “Honolulu Council”).
Amounts cleaned/cast in Python. A ${usd(OUTLIER)}+ single award (the HART rail line) is shown separately as a
megacontract, not blended into the vendor ranking. Matching is on entity name with generic tokens stoplisted —
treat every pair as a lead to verify in the full record.</div>

<h2>Honolulu’s largest contract vendors</h2>
<div class="m"><span style="text-align:right">awarded</span><span style="text-align:center">#</span><span>vendor · jurisdiction</span></div>
{vend_rows}
<p style="font-size:11.5px;color:#756b56;margin-top:8px">Megacontract shown separately: {outlier_note}.</p>

<h2>The pairs to read together</h2>
<div class="kps">
 <div class="kp"><div class="kv" style="color:#e06a4a">{len(matches)}</div><div class="kl">vendor–donor name overlaps</div></div>
 <div class="kp"><div class="kv" style="color:#e06a4a">${usd(tot_award)}</div><div class="kl">awards in those pairs</div></div>
 <div class="kp"><div class="kv" style="color:#d9b24c">${usd(tot_contrib)}</div><div class="kl">donations to the Council</div></div>
 <div class="kp"><div class="kv" style="color:#e06a4a">{agg_lev:,.0f}x</div><div class="kl">aggregate leverage</div></div>
</div>
<p style="font-size:12.5px;color:#bdb8a4;margin:6px 0 12px">A small donation beside a large award is the pair that
asks the loudest question: does the contract answer the public, or the contribution? Sorted by leverage.</p>
{prows}
<div class="q"><b>An honest, narrow result.</b> Of {len(vend)} cleaned Honolulu vendors set against {money['n_donors']:,}
Council donors, only <b>{len(matches)}</b> names match in both ledgers. That narrowness is itself a finding: most
Honolulu contractors do <i>not</i> appear as Council donors in this dataset — and the biggest gap is structural.
The <b>HART rail megacontract</b> and most large builders sit outside the Council-donor list, and <b>subcontractor</b>
and <b>sole-source</b> detail is not in open data at all. The two clean pairs above are leads to verify, not verdicts.</div>
<p style="margin-top:18px"><a href="money_honolulu.html">← Honolulu campaign money</a>
 · <a href="jurisdictions.html">all govOS jurisdictions</a></p>
<footer>generated {g} · honolulu-parity v1 · source: HANDS awards (Honolulu jurisdictions) × HI Campaign Spending Commission (hicscdata jexd-xbcg) · public record · Kilo Aupuni · govOS</footer>
</div></body></html>"""
open(MAUIOS + r"\parity_honolulu.html", "w", encoding="utf-8", newline="\n").write(parity_html)
print("WROTE parity_honolulu.html  pairs={} award_in_pairs=${:,.0f} contrib=${:,.0f} agg_lev={:.0f}x".format(
    len(matches), tot_award, tot_contrib, agg_lev))
print("clean vendor total ${:,.0f} over {} awards / {} vendors; outliers={} (${:,.0f})".format(
    clean_total, n_clean, len(vend), len(outliers), outlier_sum))
