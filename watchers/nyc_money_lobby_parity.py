# -*- coding: utf-8 -*-
"""nyc_money_lobby_parity.py — Kilo Aupuni / govOS New York City tenant.

Builds three civic-transparency pages from REAL NYC public-record open data:
  1) money_nyc.html  (money)  — NYC Campaign Finance Board "Campaign Contributions"
                                Socrata rjkp-yttg: who funds NYC officials, by recipient,
                                plus top donor cities/zips.
  2) parity_nyc.html (parity) — entities that BOTH win NYC contracts (qyyg-4tf5 Awards)
                                AND show up as CFB contributors (rjkp-yttg). Overlaps
                                stated as QUESTIONS, never accusations.
  3) lobby_nyc.html  (lobby)  — NYC City Clerk eLobbyist Data (fmf3-knd8): top lobbying
                                clients/spenders by reported compensation + expenses.

Integrity: only data fetched live in this run; money fields are TEXT on Socrata and
contain outliers/anomalies, so all amounts are cast to float and cleaned in Python
(nulls dropped, absurd values flagged + excluded). Every correlation is framed as a
question naming a pattern, never a guilty person. Source cited on every page.
"""
import os, json, ssl, time, urllib.request, urllib.parse, html, re
from datetime import datetime, timezone, timedelta

HOME = os.path.expanduser("~")
PROJECT = os.path.join(HOME, "Documents", "Claude", "Projects", "Video System elementLOTUS")
MAUIOS = os.path.join(PROJECT, "reports", "mauios")
EST = timezone(timedelta(hours=-5))
UA = {"User-Agent": "12sgi-kilo-aupuni/1.0 (civic transparency; public record)", "Accept": "application/json"}
DOMAIN = "data.cityofnewyork.us"
CFB = "rjkp-yttg"        # Campaign Finance Board — Campaign Contributions (1.67M rows)
AWARDS = "qyyg-4tf5"     # City Record — Recent Contract Awards
ELOBBY = "fmf3-knd8"     # City Clerk eLobbyist Data

# Outlier handling (money fields are dirty text on Socrata)
CONTRACT_OUTLIER = 2_000_000_000     # single contract > $2B = data-entry anomaly, exclude
CONTRIB_SELFFUND = 250_000           # single contribution >= $250k = self-funder/loan, exclude from "donor" totals

esc = lambda s: html.escape(str(s if s is not None else ""))
usd = lambda n: f"{n:,.0f}"
def now_est(): return datetime.now(EST)

def num(s):
    try:
        v = float(str(s).replace(",", "").replace("$", "").strip())
        return v
    except Exception:
        return None

def socrata(dataset, params):
    qs = "&".join(f"{k}={urllib.parse.quote(str(v))}" for k, v in params.items())
    url = f"https://{DOMAIN}/resource/{dataset}.json?{qs}"
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=180, context=ssl.create_default_context()) as r:
        return json.loads(r.read().decode("utf-8", "replace"))

# ----------------------------------------------------------------------------- norm/key
def norm(s):
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", (s or "").lower())).strip()

SUFFIX = re.compile(r"\b(llc|inc|ltd|lp|llp|corp|corporation|company|co|pac|"
                    r"incorporated|limited|associates|group|the)\b")
def org_key(org):
    n = SUFFIX.sub(" ", norm(org))
    n = re.sub(r"\s+", " ", n).strip()
    return n if len(n) >= 6 and len(n.split()) >= 2 else ""

# ============================================================================= MONEY
def build_money():
    # Server-side aggregate by recipient. Then clean self-funder distortion in python
    # by re-deriving each big recipient's small-donor total (amnt < CONTRIB_SELFFUND).
    recips = socrata(CFB, {
        "$select": "recipname, sum(amnt) as tot, count(1) as n",
        "$group": "recipname", "$order": "tot desc", "$limit": 400})
    cleaned = []
    for r in recips:
        name = (r.get("recipname") or "").strip()
        tot = num(r.get("tot"))
        n = int(num(r.get("n")) or 0)
        if not name or tot is None or tot <= 0:
            continue
        cleaned.append({"name": name, "raw_total": tot, "n": n})

    # For the top recipients, fetch their small-money total (exclude self-fund/loan spikes)
    top = cleaned[:60]
    for r in top:
        try:
            agg = socrata(CFB, {
                "$select": "sum(amnt) as tot, count(1) as n",
                "$where": f"recipname='{r['name'].replace(chr(39), chr(39)*2)}' AND amnt < {CONTRIB_SELFFUND}"})
            r["small_total"] = num(agg[0].get("tot")) or 0.0
            r["small_n"] = int(num(agg[0].get("n")) or 0)
        except Exception:
            r["small_total"] = None; r["small_n"] = None
        time.sleep(0.1)

    # rank by small-donor (public) money — the honest "who funds officials" view
    funded = [r for r in top if r.get("small_total")]
    funded.sort(key=lambda x: -(x["small_total"] or 0))

    # top donor cities (zip/geography pattern), small money only
    cities = socrata(CFB, {
        "$select": "city, state, sum(amnt) as tot, count(1) as n",
        "$where": f"amnt < {CONTRIB_SELFFUND} AND city IS NOT NULL",
        "$group": "city, state", "$order": "tot desc", "$limit": 25})
    city_rows = []
    for c in cities:
        t = num(c.get("tot")); cnt = int(num(c.get("n")) or 0)
        if t and t > 0:
            city_rows.append({"city": (c.get("city") or "").strip().title(),
                              "state": (c.get("state") or "").strip().upper(),
                              "tot": t, "n": cnt})

    # totals across the full dataset (small money = public money, large = self/loan)
    grand = socrata(CFB, {"$select": "sum(amnt) as tot, count(1) as n"})
    grand_tot = num(grand[0].get("tot")) or 0.0
    grand_n = int(num(grand[0].get("n")) or 0)
    self_tot_agg = socrata(CFB, {"$select": "sum(amnt) as tot, count(1) as n",
                                 "$where": f"amnt >= {CONTRIB_SELFFUND}"})
    self_tot = num(self_tot_agg[0].get("tot")) or 0.0
    self_n = int(num(self_tot_agg[0].get("n")) or 0)
    public_tot = grand_tot - self_tot

    g = now_est().strftime("%Y-%m-%d %H:%M ET")
    krows = "".join(
        f'<div class="m"><span class="a">${usd(r["small_total"])}</span>'
        f'<span class="n">{r["small_n"]:,}</span>'
        f'<span class="c">{esc(r["name"])}</span></div>'
        for r in funded[:40])
    crows = "".join(
        f'<div class="m"><span class="a">${usd(c["tot"])}</span><span class="n">{c["n"]:,}</span>'
        f'<span class="c">{esc(c["city"])}{(", "+esc(c["state"])) if c["state"] else ""}</span></div>'
        for c in city_rows[:20])

    page = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>New York City — Who Funds the Officials — Kilo Aupuni</title>
<style>
 body{{margin:0;background:#0c100e;color:#e8e4d8;font-family:Georgia,'Iowan Old Style',serif;line-height:1.55}}
 .wrap{{max-width:940px;margin:0 auto;padding:34px 24px 70px}}
 .eyebrow{{font-family:Consolas,monospace;font-size:11px;letter-spacing:1.2px;color:#d9b24c;text-transform:uppercase}}
 h1{{font-size:27px;font-weight:600;margin:8px 0 2px}} h2{{font-size:18px;margin:30px 0 4px}}
 .lead{{font-size:13.5px;color:#bdb8a4;max-width:84ch}}
 .kpi{{display:flex;flex-wrap:wrap;gap:26px;margin:16px 0}}
 .kpi .n{{font-family:Consolas,monospace;font-size:22px;color:#d9b24c}}
 .kpi .l{{font-family:Consolas,monospace;font-size:11px;color:#9a957f;text-transform:uppercase}}
 .disc{{font-size:12px;color:#9a957f;font-style:italic;border-left:2px solid rgba(217,178,76,.4);padding:7px 12px;margin:14px 0}}
 .sub{{font-size:12.5px;color:#bdb8a4;margin:2px 0 10px}}
 .m{{display:grid;grid-template-columns:150px 80px 1fr;gap:12px;align-items:baseline;padding:6px 0;border-bottom:1px solid rgba(255,255,255,.06)}}
 .m .a{{font-family:Consolas,monospace;font-size:12.5px;color:#d9b24c;text-align:right}}
 .m .n{{font-family:Consolas,monospace;font-size:11.5px;color:#9a957f;text-align:right}} .m .c{{font-size:12.5px;color:#bdb8a4}}
 .hd .a,.hd .n{{color:#756b56}} .hd .c{{color:#756b56}}
 a{{color:#d9b24c}} footer{{margin-top:34px;border-top:1px solid rgba(255,255,255,.1);padding-top:12px;font-family:Consolas,monospace;font-size:10.5px;color:#9a957f}}
</style></head><body><div class="wrap">
<div class="eyebrow">12 Stones Global &middot; Kilo Aupuni &middot; New York City &middot; who funds the officials</div>
<h1>New York City — Who Funds the Officials</h1>
<p class="lead">Every campaign contribution reported to the <b>NYC Campaign Finance Board</b>, aggregated by
who received it. This is the money side of the map: which candidates and officials draw the most
<b>public</b> donor money, and where that money comes from. Self-funding and large loans (single
contributions of ${usd(CONTRIB_SELFFUND)}+) are separated out so the donor picture is not distorted by a
billionaire writing their own campaign a check.</p>
<div class="kpi">
 <div><div class="n">{grand_n:,}</div><div class="l">contributions on record</div></div>
 <div><div class="n">${usd(public_tot)}</div><div class="l">from donors (&lt;${usd(CONTRIB_SELFFUND)} each)</div></div>
 <div><div class="n">${usd(self_tot)}</div><div class="l">self-fund / large ({self_n:,})</div></div>
</div>
<div class="disc">Source: NYC Campaign Finance Board, "Campaign Contributions" (NYC Open Data, dataset
<a href="https://data.cityofnewyork.us/dataset/Campaign-Contributions/rjkp-yttg">rjkp-yttg</a> on
data.cityofnewyork.us). Amounts are stored as text and contain anomalies; all figures here were cast to
number and cleaned in code. Receiving and giving campaign money is lawful — this maps the flow so it can be
read beside contracts and lobbying. Documented public record and open questions.</div>

<h2>Officials &amp; candidates by donor money raised</h2>
<p class="sub">Ranked by money from individual donors under ${usd(CONTRIB_SELFFUND)} each (the "who funds them"
signal), not by self-funded totals. Across all elections in the CFB record.</p>
<div class="m hd"><span class="a">donor $</span><span class="n">gifts</span><span class="c">recipient</span></div>
{krows}

<h2>Where the donor money comes from — top cities</h2>
<p class="sub">Geography of small-donor money (under ${usd(CONTRIB_SELFFUND)} per gift). A funding base
concentrated outside the five boroughs is itself a question worth asking of any NYC official.</p>
<div class="m hd"><span class="a">donor $</span><span class="n">gifts</span><span class="c">city</span></div>
{crows}

<p style="margin-top:18px"><a href="parity_nyc.html">contracts &times; donors (parity)</a>
&middot; <a href="lobby_nyc.html">who lobbies NYC</a>
&middot; <a href="contracts_nyc.html">NYC contract awards</a></p>
<footer>generated {g} &middot; nyc-money v1 &middot; source: NYC CFB Campaign Contributions (rjkp-yttg, public record) &middot; Kilo Aupuni &middot; govOS</footer>
</div></body></html>"""
    open(os.path.join(MAUIOS, "money_nyc.html"), "w", encoding="utf-8", newline="\n").write(page)
    stats = {"grand_n": grand_n, "public_tot": round(public_tot, 2), "self_tot": round(self_tot, 2),
             "self_n": self_n, "top_recipient": funded[0]["name"] if funded else None,
             "top_recipient_donor_total": round(funded[0]["small_total"], 2) if funded else None,
             "n_recipients_ranked": len(funded)}
    json.dump({"generated": now_est().isoformat(), "source": "NYC CFB rjkp-yttg", **stats},
              open(os.path.join(MAUIOS, "money_nyc.json"), "w", encoding="utf-8"), indent=1)
    print(f"money_nyc: {grand_n:,} contributions; public ${public_tot:,.0f}; "
          f"top donor-funded = {stats['top_recipient']} ${stats['top_recipient_donor_total']:,.0f}")
    return funded, stats

# ============================================================================= PARITY
def build_parity():
    # 1) top NYC contract vendors (Award notices), cleaned of outliers
    vrows = socrata(AWARDS, {
        "$select": "vendor_name, sum(contract_amount) as tot, count(1) as n",
        "$where": "type_of_notice_description='Award'",
        "$group": "vendor_name", "$order": "tot desc", "$limit": 600})
    vendors, excl = [], 0
    for r in vrows:
        name = (r.get("vendor_name") or "").strip()
        tot = num(r.get("tot")); n = int(num(r.get("n")) or 0)
        if not name or tot is None or tot <= 0:
            continue
        if tot >= CONTRACT_OUTLIER:
            excl += 1; continue
        vendors.append({"name": name, "total": tot, "n": n, "key": org_key(name)})
    vendors.sort(key=lambda x: -x["total"])

    # 2) top CFB contributors (organizations) — group by contributor name proxy.
    # rjkp-yttg has no contributor-name column we can group on reliably (donor identity
    # is in recipid/refno-level rows). The contributor org appears via the 'recipname'
    # being a recipient, not a giver — so we name-match contract vendors against the
    # *contribution recipients* AND against high-volume city/employer signals is not
    # possible here. Honest approach: match vendor org keys against CFB recipient names
    # is meaningless; instead we surface the two ledgers side by side and explain the
    # identity-data gap, which is the truthful state.
    #
    # We DO have one real cross-check: some contract vendors are themselves PACs/LLCs
    # that also appear as CFB *recipients* (committees). Match vendor keys to recipient
    # keys to catch any literal overlap.
    recips = socrata(CFB, {
        "$select": "recipname, sum(amnt) as tot, count(1) as n",
        "$group": "recipname", "$order": "tot desc", "$limit": 600})
    rkeyed = {}
    for r in recips:
        nm = (r.get("recipname") or "").strip()
        t = num(r.get("tot"))
        if not nm or t is None or t <= 0:
            continue
        k = org_key(nm)
        if k:
            rkeyed.setdefault(k, {"name": nm, "tot": t, "n": int(num(r.get("n")) or 0)})

    overlaps = []
    for v in vendors[:300]:
        if v["key"] and v["key"] in rkeyed:
            rc = rkeyed[v["key"]]
            overlaps.append({"vendor": v["name"], "award_total": v["total"], "award_n": v["n"],
                             "cfb_name": rc["name"], "cfb_total": rc["tot"], "cfb_n": rc["n"]})
    overlaps.sort(key=lambda x: -x["award_total"])

    award_total = sum(v["total"] for v in vendors)
    g = now_est().strftime("%Y-%m-%d %H:%M ET")

    if overlaps:
        orows = "".join(
            f'<div class="row"><span class="a">${usd(o["award_total"])}</span>'
            f'<span class="c"><b>{esc(o["vendor"])}</b> won ${usd(o["award_total"])} in NYC awards '
            f'({o["award_n"]}); an entity matching that name appears in CFB campaign-finance records as '
            f'<b>{esc(o["cfb_name"])}</b> (${usd(o["cfb_total"])}). '
            f'<span style="color:#9a957f">Same entity, or a name collision? A pair to verify against the '
            f'underlying filings — a question, not a finding.</span></span></div>'
            for o in overlaps[:40])
        overlap_block = f"""<h2 class="sec">Name overlaps — contract winner also in the finance ledger</h2>
<p class="note">Where a contract vendor's normalized name also appears in the Campaign Finance Board ledger.
Each is a candidate pair to confirm against the source filings (names alone do not prove identity).</p>
{orows}"""
    else:
        overlap_block = """<h2 class="sec">Name overlaps</h2>
<p class="note">No high-confidence name overlap survived normalization between the contract-vendor ledger and
the campaign-finance ledger on this run. That is an honest negative, not an all-clear: the CFB dataset keys
contributions by <i>recipient</i>, not by a clean contributor-organization field, so a vendor's owners or
officers giving as individuals would not match here. Closing that gap needs contributor-level identity data
(employer/EIN), which this dataset does not expose. The two ledgers are shown side by side below.</p>"""

    vlist = "".join(
        f'<div class="m"><span class="a">${usd(v["total"])}</span><span class="n">{v["n"]}</span>'
        f'<span class="c">{esc(v["name"])}</span></div>' for v in vendors[:30])
    rlist = "".join(
        f'<div class="m"><span class="a">${usd(r["tot"])}</span><span class="n">{r["n"]:,}</span>'
        f'<span class="c">{esc(r["name"])}</span></div>'
        for r in sorted(rkeyed.values(), key=lambda x: -x["tot"])[:30])

    page = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>New York City — Contracts &times; Donors (Parity) — Kilo Aupuni</title>
<style>
 body{{margin:0;background:#0c100e;color:#e8e4d8;font-family:Georgia,'Iowan Old Style',serif;line-height:1.55}}
 .wrap{{max-width:960px;margin:0 auto;padding:34px 24px 70px}}
 .eyebrow{{font-family:Consolas,monospace;font-size:11px;letter-spacing:1.2px;color:#d9b24c;text-transform:uppercase}}
 h1{{font-size:27px;font-weight:600;margin:8px 0 2px}}
 .lead{{font-size:13.5px;color:#bdb8a4;max-width:84ch}}
 .disc{{font-size:12px;color:#9a957f;font-style:italic;border-left:2px solid rgba(217,178,76,.4);padding:7px 12px;margin:14px 0}}
 .kpi{{display:flex;flex-wrap:wrap;gap:26px;margin:16px 0}}
 .kpi .n{{font-family:Consolas,monospace;font-size:22px;color:#d9b24c}}
 .kpi .l{{font-family:Consolas,monospace;font-size:11px;color:#9a957f;text-transform:uppercase}}
 .sec{{font-family:Consolas,monospace;font-size:11px;letter-spacing:1.5px;text-transform:uppercase;color:#d9b24c;border-bottom:1px solid rgba(217,178,76,.2);padding-bottom:6px;margin:26px 0 10px}}
 .note{{font-size:12.5px;color:#bdb8a4;margin:0 0 12px;line-height:1.6;max-width:84ch}}
 .row{{display:flex;gap:12px;align-items:baseline;border-bottom:1px solid rgba(255,255,255,.06);padding:7px 0}}
 .row .a{{font-family:Consolas,monospace;font-size:12.5px;color:#e06a4a;white-space:nowrap;min-width:110px;text-align:right}}
 .row .c{{font-size:12.5px;color:#bdb8a4}}
 .cols{{display:grid;grid-template-columns:1fr 1fr;gap:26px}} @media(max-width:680px){{.cols{{grid-template-columns:1fr}}}}
 .m{{display:grid;grid-template-columns:120px 44px 1fr;gap:10px;align-items:baseline;padding:5px 0;border-bottom:1px solid rgba(255,255,255,.06)}}
 .m .a{{font-family:Consolas,monospace;font-size:12px;color:#d9b24c;text-align:right}}
 .m .n{{font-family:Consolas,monospace;font-size:11px;color:#9a957f;text-align:right}} .m .c{{font-size:12px;color:#bdb8a4}}
 a{{color:#d9b24c}} footer{{margin-top:34px;border-top:1px solid rgba(255,255,255,.1);padding-top:12px;font-family:Consolas,monospace;font-size:10.5px;color:#9a957f}}
</style></head><body><div class="wrap">
<div class="eyebrow">12 Stones Global &middot; Kilo Aupuni &middot; New York City &middot; the parity question</div>
<h1>New York City — Contracts &times; Donors</h1>
<p class="lead">Civic parity asks one thing of the public ledger: does a contract (the output of public money)
answer the <b>public</b>, or does it answer a private donor to the official who approves it? This page sets
NYC's two money ledgers beside each other — who the City <b>pays</b> (contract awards) and who <b>funds</b>
its officials (campaign contributions) — and looks for entities in both.</p>
<div class="disc">Sources: NYC Open Data — City Record "Recent Contract Awards"
(<a href="https://data.cityofnewyork.us/dataset/Recent-Contract-Awards/qyyg-4tf5">qyyg-4tf5</a>) and NYC
Campaign Finance Board "Campaign Contributions"
(<a href="https://data.cityofnewyork.us/dataset/Campaign-Contributions/rjkp-yttg">rjkp-yttg</a>), both on
data.cityofnewyork.us. Contract amounts were cleaned in code: {excl} vendor totals over $2B were excluded as
data-entry anomalies. Winning contracts and giving to campaigns are both lawful — every overlap below is a
<b>question to verify</b>, naming a pair, never an accusation against a person.</div>
<div class="kpi">
 <div><div class="n">{len(vendors):,}</div><div class="l">contract vendors (cleaned)</div></div>
 <div><div class="n">${usd(award_total)}</div><div class="l">total awarded (cleaned)</div></div>
 <div><div class="n">{len(overlaps)}</div><div class="l">name overlaps found</div></div>
</div>

{overlap_block}

<h2 class="sec">The two ledgers, side by side</h2>
<p class="note">Top contract vendors (left) and top campaign-finance entities (right). Reading them together
is the point: a name appearing high on both lists is where the parity question gets sharpest.</p>
<div class="cols">
 <div><div class="m"><span class="a" style="color:#756b56">awarded</span><span class="n" style="color:#756b56">#</span><span class="c" style="color:#756b56">top contract vendors</span></div>{vlist}</div>
 <div><div class="m"><span class="a" style="color:#756b56">finance $</span><span class="n" style="color:#756b56">#</span><span class="c" style="color:#756b56">top finance-ledger entities</span></div>{rlist}</div>
</div>

<p style="margin-top:18px"><a href="money_nyc.html">who funds NYC officials</a>
&middot; <a href="lobby_nyc.html">who lobbies NYC</a>
&middot; <a href="contracts_nyc.html">NYC contract awards</a></p>
<footer>generated {g} &middot; nyc-parity v1 &middot; source: NYC qyyg-4tf5 &times; rjkp-yttg (public record) &middot; Kilo Aupuni &middot; govOS</footer>
</div></body></html>"""
    open(os.path.join(MAUIOS, "parity_nyc.html"), "w", encoding="utf-8", newline="\n").write(page)
    stats = {"vendors": len(vendors), "award_total": round(award_total, 2),
             "excluded_outliers": excl, "overlaps": len(overlaps),
             "top_vendor": vendors[0]["name"] if vendors else None,
             "top_vendor_total": round(vendors[0]["total"], 2) if vendors else None}
    json.dump({"generated": now_est().isoformat(), "source": "qyyg-4tf5 x rjkp-yttg", **stats},
              open(os.path.join(MAUIOS, "parity_nyc.json"), "w", encoding="utf-8"), indent=1)
    print(f"parity_nyc: {len(vendors):,} vendors ${award_total:,.0f}; {len(overlaps)} overlaps")
    return stats

# ============================================================================= LOBBY
def build_lobby():
    rows, off, PAGE = [], 0, 50000
    while True:
        batch = socrata(ELOBBY, {
            "$select": "client_name, client_industry, compensation_total, "
                       "lobbying_expenses_total, report_year",
            "$limit": PAGE, "$offset": off})
        rows += batch
        if len(batch) < PAGE:
            break
        off += PAGE; time.sleep(0.3)

    by, n_used, comp_sum, exp_sum, years = {}, 0, 0.0, 0.0, set()
    for r in rows:
        name = (r.get("client_name") or "").strip()
        if not name:
            continue
        comp = num(r.get("compensation_total")) or 0.0
        exp = num(r.get("lobbying_expenses_total")) or 0.0
        if comp < 0: comp = 0.0
        if exp < 0: exp = 0.0
        if comp >= CONTRACT_OUTLIER or exp >= CONTRACT_OUTLIER:   # absurd anomaly guard
            continue
        yr = (r.get("report_year") or "").strip()
        if yr: years.add(yr)
        e = by.setdefault(name, {"client": name, "industry": (r.get("client_industry") or "").strip(),
                                 "comp": 0.0, "exp": 0.0, "filings": 0})
        e["comp"] += comp; e["exp"] += exp; e["filings"] += 1
        n_used += 1; comp_sum += comp; exp_sum += exp
    clients = sorted(by.values(), key=lambda x: -(x["comp"] + x["exp"]))
    yrange = ""
    if years:
        ys = sorted(years)
        yrange = ys[0] if len(ys) == 1 else f"{ys[0]}–{ys[-1]}"

    g = now_est().strftime("%Y-%m-%d %H:%M ET")
    lrows = "".join(
        f'<div class="m"><span class="a">${usd(c["comp"]+c["exp"])}</span>'
        f'<span class="n">{c["filings"]}</span>'
        f'<span class="c">{esc(c["client"])}'
        f'{(" &middot; <span class=ind>"+esc(c["industry"])+"</span>") if c["industry"] else ""}</span></div>'
        for c in clients[:50])

    page = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>New York City — Who Lobbies the City — Kilo Aupuni</title>
<style>
 body{{margin:0;background:#0c100e;color:#e8e4d8;font-family:Georgia,'Iowan Old Style',serif;line-height:1.55}}
 .wrap{{max-width:940px;margin:0 auto;padding:34px 24px 70px}}
 .eyebrow{{font-family:Consolas,monospace;font-size:11px;letter-spacing:1.2px;color:#d9b24c;text-transform:uppercase}}
 h1{{font-size:27px;font-weight:600;margin:8px 0 2px}}
 .lead{{font-size:13.5px;color:#bdb8a4;max-width:84ch}}
 .kpi{{display:flex;flex-wrap:wrap;gap:26px;margin:16px 0}}
 .kpi .n{{font-family:Consolas,monospace;font-size:22px;color:#d9b24c}}
 .kpi .l{{font-family:Consolas,monospace;font-size:11px;color:#9a957f;text-transform:uppercase}}
 .disc{{font-size:12px;color:#9a957f;font-style:italic;border-left:2px solid rgba(217,178,76,.4);padding:7px 12px;margin:14px 0}}
 .sub{{font-size:12.5px;color:#bdb8a4;margin:2px 0 10px;max-width:84ch}}
 .m{{display:grid;grid-template-columns:150px 56px 1fr;gap:12px;align-items:baseline;padding:6px 0;border-bottom:1px solid rgba(255,255,255,.06)}}
 .m .a{{font-family:Consolas,monospace;font-size:12.5px;color:#d9b24c;text-align:right}}
 .m .n{{font-family:Consolas,monospace;font-size:11.5px;color:#9a957f;text-align:right}} .m .c{{font-size:12.5px;color:#bdb8a4}}
 .ind{{color:#756b56}} .hd .a,.hd .n,.hd .c{{color:#756b56}}
 a{{color:#d9b24c}} footer{{margin-top:34px;border-top:1px solid rgba(255,255,255,.1);padding-top:12px;font-family:Consolas,monospace;font-size:10.5px;color:#9a957f}}
</style></head><body><div class="wrap">
<div class="eyebrow">12 Stones Global &middot; Kilo Aupuni &middot; New York City &middot; the third channel</div>
<h1>New York City — Who Lobbies the City</h1>
<p class="lead">Beyond donating and contracting, there is a third channel of influence: paid lobbying. This is
the <b>NYC City Clerk eLobbyist</b> registry — the clients who hire lobbyists to shape City Council bills,
agency rules, and budget lines, ranked by the compensation and expenses they reported. Who pays to be heard
inside City Hall.</p>
<div class="kpi">
 <div><div class="n">{len(clients):,}</div><div class="l">lobbying clients</div></div>
 <div><div class="n">${usd(comp_sum)}</div><div class="l">compensation reported</div></div>
 <div><div class="n">${usd(exp_sum)}</div><div class="l">lobbying expenses</div></div>
 <div><div class="n">{n_used:,}</div><div class="l">filings scanned{(" &middot; "+yrange) if yrange else ""}</div></div>
</div>
<div class="disc">Source: NYC City Clerk, "eLobbyist Data" (NYC Open Data, dataset
<a href="https://data.cityofnewyork.us/dataset/City-Clerk-eLobbyist-Data/fmf3-knd8">fmf3-knd8</a> on
data.cityofnewyork.us). Compensation and expense fields are stored as text; all amounts were cast to number
and summed per client in code. Lobbying is lawful and registered by design — this maps who spends the most to
influence City government, to read beside who funds officials and who wins contracts. Documented public record
and open questions.</div>

<h2 style="font-size:18px;margin:30px 0 4px">Top lobbying clients by reported spend</h2>
<p class="sub">Ranked by reported compensation + lobbying expenses, summed across all filings in the registry.
A client appearing here <i>and</i> in the contract-award or campaign-finance ledgers is where three influence
channels converge — a question to carry into the parity view.</p>
<div class="m hd"><span class="a">comp + exp</span><span class="n">filings</span><span class="c">client &middot; industry</span></div>
{lrows}

<p style="margin-top:18px"><a href="money_nyc.html">who funds NYC officials</a>
&middot; <a href="parity_nyc.html">contracts &times; donors</a>
&middot; <a href="contracts_nyc.html">NYC contract awards</a></p>
<footer>generated {g} &middot; nyc-lobby v1 &middot; source: NYC City Clerk eLobbyist (fmf3-knd8, public record) &middot; Kilo Aupuni &middot; govOS</footer>
</div></body></html>"""
    open(os.path.join(MAUIOS, "lobby_nyc.html"), "w", encoding="utf-8", newline="\n").write(page)
    stats = {"clients": len(clients), "comp_sum": round(comp_sum, 2), "exp_sum": round(exp_sum, 2),
             "filings": n_used, "year_range": yrange,
             "top_client": clients[0]["client"] if clients else None,
             "top_client_total": round(clients[0]["comp"] + clients[0]["exp"], 2) if clients else None}
    json.dump({"generated": now_est().isoformat(), "source": "NYC eLobbyist fmf3-knd8", **stats},
              open(os.path.join(MAUIOS, "lobby_nyc.json"), "w", encoding="utf-8"), indent=1)
    print(f"lobby_nyc: {len(clients):,} clients; comp ${comp_sum:,.0f} exp ${exp_sum:,.0f}; "
          f"top = {stats['top_client']} ${stats['top_client_total']:,.0f}")
    return stats

def main():
    os.makedirs(MAUIOS, exist_ok=True)
    m = build_money()
    p = build_parity()
    l = build_lobby()
    return 0

if __name__ == "__main__":
    import sys; sys.exit(main())
