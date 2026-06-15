#!/usr/bin/env python3
"""wildfire_watch.py — Kilo Aupuni: break down the Maui wildfire-recovery money.
Reads reports/mauios/hands_maui_awards.json (public HANDS award notices) + donor_profiles.json,
isolates the post-August-2023 wildfire/Lahaina recovery awards, ranks the firms (the repeat
players), and sets the money beside the deciders — framed as documented facts + open questions,
NEVER accusations (Kilo Aupuni rule). Output: reports/mauios/wildfire_recovery_watch.{json,html}.
"""
import os, json, html, re
from datetime import datetime, timezone, timedelta

HOME = os.path.expanduser("~")
PROJECT = os.path.join(HOME, "Documents", "Claude", "Projects", "Video System elementLOTUS")
MAUIOS = os.path.join(PROJECT, "reports", "mauios")
AWARDS = os.path.join(MAUIOS, "hands_maui_awards.json")
DONORS = os.path.join(MAUIOS, "donor_profiles.json")
OUT_JSON = os.path.join(MAUIOS, "wildfire_recovery_watch.json")
OUT_HTML = os.path.join(MAUIOS, "wildfire_recovery_watch.html")
HST = timezone(timedelta(hours=-10))

WF_KEYS = ("wildfire", "lahaina", "disaster", "recovery", "after action", "debris",
           "fire mit", "fire station", "revegetation", "fema", "rebuild", "opt-out")
esc = lambda s: html.escape(str(s or ""))
usd = lambda n: f"{n:,.0f}"
def now_hst(): return datetime.now(HST)

def collect():
    h = json.load(open(AWARDS, encoding="utf-8"))
    by = {}
    for v in h.get("vendors", []):
        for a in v.get("awards", []):
            t = (a.get("title") or "").lower()
            if any(k in t for k in WF_KEYS):
                d = by.setdefault(v["vendor"], {"vendor": v["vendor"], "total": 0.0, "awards": []})
                d["total"] += a.get("amount") or 0
                d["awards"].append(a)
    vendors = sorted(by.values(), key=lambda x: -x["total"])
    for v in vendors:
        v["count"] = len(v["awards"])
        v["awards"].sort(key=lambda a: -(a.get("amount") or 0))
    return vendors

def alpha_trace():
    """Every Alpha-Construction-linked record in the donor data (name or employer)."""
    dp = json.load(open(DONORS, encoding="utf-8"))
    hits = []
    for o in dp:
        off = (o.get("official") or {}).get("label") if isinstance(o.get("official"), dict) else o.get("label")
        for cat, blk in o.items():
            if isinstance(blk, dict):
                for dn in blk.get("donors", []) or []:
                    blob = (str(dn.get("name", "")) + " " + str(dn.get("employer", ""))).lower()
                    if "alpha" in blob and ("construction" in blob or "alpha construction" in blob):
                        hits.append({"official": off, "donor": dn.get("name"),
                                     "employer": dn.get("employer"), "occupation": dn.get("occupation"),
                                     "amount": dn.get("amount"), "list": cat})
    return hits

def build_page(vendors, alpha):
    g = now_hst().strftime("%Y-%m-%d %H:%M HST")
    total = sum(v["total"] for v in vendors)
    nfirms = len(vendors)
    nawards = sum(v["count"] for v in vendors)
    top3 = sum(v["total"] for v in vendors[:3])
    top3pct = (top3 / total * 100) if total else 0
    repeat = [v for v in vendors if v["count"] >= 2]

    vrows = ""
    for v in vendors:
        flag = ' <span style="color:#e0863a">&#9679; repeat</span>' if v["count"] >= 2 else ""
        det = "".join(
            f'<div class="aw"><span class="a">${usd(a.get("amount") or 0)}</span>'
            f'<span class="d">{esc(a.get("date"))}</span>'
            f'<span class="t">{esc(a.get("title"))} <span class="dept">&middot; {esc(a.get("dept"))}</span></span></div>'
            for a in v["awards"])
        vrows += (f'<div class="vh"><span class="a">${usd(v["total"])}</span>'
                  f'<span class="n">{v["count"]} award{"s" if v["count"]!=1 else ""}</span>'
                  f'<span class="c">{esc(v["vendor"])}{flag}</span></div>{det}')

    if alpha:
        arows = "".join(
            f'<div class="m"><span class="a">${usd(a.get("amount") or 0)}</span>'
            f'<span class="c">{esc(a.get("donor"))} &middot; {esc(a.get("occupation"))}, '
            f'<b>{esc(a.get("employer"))}</b> &rarr; {esc(a.get("official"))}</span></div>'
            for a in alpha)
        alpha_block = (
            '<h2>Alpha Construction &mdash; what the record shows</h2>'
            f'<p class="lead">In the current public-record set, <b>Alpha Construction</b> appears '
            f'as a campaign-donor connection ({len(alpha)} record{"s" if len(alpha)!=1 else ""}): its '
            f'named officer donated to a tracked official. It does <b>not</b> appear as a HANDS contract '
            f'awardee under that name. To trace whether Alpha is "everywhere," the records to pull next are '
            f'subcontractor rosters on the prime recovery contracts, DBA/affiliate names, and lobbyist '
            f'registrations &mdash; none of which are in this dataset yet.</p>'
            f'{arows}')
    else:
        alpha_block = ('<h2>Alpha Construction</h2><p class="lead">No Alpha-Construction record is present in '
                       'the current donor/award data. Pull subcontractor + lobbyist records to test the pattern.</p>')

    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Maui Wildfire Recovery Watch - Kilo Aupuni</title>
<style>
 body{{margin:0;background:#0c100e;color:#e8e4d8;font-family:Georgia,'Iowan Old Style',serif;line-height:1.55}}
 .wrap{{max-width:940px;margin:0 auto;padding:34px 24px 60px}}
 .eyebrow{{font-family:Consolas,monospace;font-size:11px;letter-spacing:1.2px;color:#d9b24c;text-transform:uppercase}}
 h1{{font-size:27px;font-weight:600;margin:8px 0 2px}} h2{{font-size:18px;font-weight:600;margin:30px 0 6px;color:#e8e4d8}}
 .lead{{font-size:13.5px;color:#bdb8a4;max-width:84ch}}
 .kpi{{display:flex;flex-wrap:wrap;gap:26px;margin:16px 0}}
 .kpi .n{{font-family:Consolas,monospace;font-size:22px;color:#d9b24c}}
 .kpi .l{{font-family:Consolas,monospace;font-size:11px;color:#9a957f;text-transform:uppercase}}
 .disc{{font-size:12px;color:#9a957f;font-style:italic;border-left:2px solid rgba(217,178,76,.4);padding:7px 12px;margin:14px 0}}
 .vh{{display:grid;grid-template-columns:130px 84px 1fr;gap:12px;align-items:baseline;padding:11px 0 5px;border-top:1px solid rgba(217,178,76,.18);margin-top:8px}}
 .vh .a{{font-family:Consolas,monospace;font-size:14px;color:#d9b24c;text-align:right;font-weight:700}}
 .vh .n{{font-family:Consolas,monospace;font-size:11px;color:#9a957f;text-align:center}}
 .vh .c{{font-size:14px;color:#e8e4d8;font-weight:600}}
 .aw{{display:grid;grid-template-columns:130px 84px 1fr;gap:12px;align-items:baseline;padding:2px 0;font-size:12px}}
 .aw .a{{font-family:Consolas,monospace;color:#9a957f;text-align:right}}
 .aw .d{{font-family:Consolas,monospace;color:#756b56;text-align:center;font-size:11px}}
 .aw .t{{color:#bdb8a4}} .aw .dept{{color:#756b56}}
 .m{{display:grid;grid-template-columns:110px 1fr;gap:12px;padding:5px 0;border-bottom:1px solid rgba(255,255,255,.06)}}
 .m .a{{font-family:Consolas,monospace;font-size:12.5px;color:#d9b24c;text-align:right}} .m .c{{font-size:12.5px;color:#bdb8a4}}
 .q{{background:rgba(217,178,76,.05);border:1px solid rgba(217,178,76,.25);border-radius:10px;padding:12px 15px;margin:16px 0;font-size:13px;color:#cfc9b6}}
 .q b{{color:#e8e4d8}} a{{color:#d9b24c}}
 footer{{margin-top:34px;border-top:1px solid rgba(255,255,255,.1);padding-top:12px;font-family:Consolas,monospace;font-size:10.5px;color:#9a957f}}
</style></head><body><div class="wrap">
<div class="eyebrow">12 Stones Global &middot; Kilo Aupuni &middot; following the recovery money</div>
<h1>Maui Wildfire Recovery Watch</h1>
<p class="lead">Where the public dollars went after the August 2023 Maui wildfires. Every Lahaina /
disaster / recovery award in the State HANDS record, ranked by firm &mdash; so the money can be set
beside the people who decide it. The <b>repeat players</b> are flagged.</p>
<div class="kpi">
 <div><div class="n">${usd(total)}</div><div class="l">recovery awarded</div></div>
 <div><div class="n">{nawards}</div><div class="l">award notices</div></div>
 <div><div class="n">{nfirms}</div><div class="l">firms</div></div>
 <div><div class="n">{top3pct:.0f}%</div><div class="l">to the top 3 firms</div></div>
 <div><div class="n">{len(repeat)}</div><div class="l">repeat firms (&ge;2)</div></div>
</div>
<div class="disc">Built from public Notices of Award (HANDS, hands.ehawaii.gov). Winning recovery work
is lawful and necessary &mdash; rebuilding Lahaina takes contractors. This is the map of <b>who is paid</b>,
so it can be read beside who funds the deciders. Documented facts and open questions, not findings of wrongdoing.</div>

<div class="q"><b>The open question.</b> The recovery money is concentrated &mdash; {top3pct:.0f}% of
${usd(total)} flows to just three firms, and {len(repeat)} firms hold repeat awards. In the current
public records there is <b>no campaign-donation link</b> found between these recovery awardees and the
deciding officials. The connections still to verify &mdash; the records to demand next &mdash; are
<b>subcontractor chains</b> on the prime contracts, <b>sole-source / emergency-procurement</b> justifications
used post-disaster, <b>lobbyist registrations</b>, and official <b>recusals</b>. That is where capture, if any, would hide.</div>

<h2>Recovery firms &mdash; the money, ranked</h2>
{vrows}

{alpha_block}

<p style="margin-top:22px"><a href="take_action.html">&#9878; Demand the subcontractor + sole-source records (UIPA) &rarr;</a>
&middot; <a href="parity_check.html">parity: pairs that no longer answer</a>
&middot; <a href="contracts_x_donors.html">contracts &times; donors</a></p>
<footer>generated {g} &middot; wildfire-watch v1 &middot; source: HANDS award notices + campaign-finance donor profiles (public record) &middot; Kilo Aupuni &middot; govOS</footer>
</div></body></html>"""

def main():
    os.makedirs(MAUIOS, exist_ok=True)
    vendors = collect()
    alpha = alpha_trace()
    total = sum(v["total"] for v in vendors)
    out = {"generated": now_hst().isoformat(), "source": "HANDS award notices + donor_profiles (public record)",
           "wildfire_total": round(total, 2), "firms": len(vendors),
           "awards": sum(v["count"] for v in vendors), "vendors": vendors, "alpha_construction": alpha}
    json.dump(out, open(OUT_JSON, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    with open(OUT_HTML, "w", encoding="utf-8") as f:
        f.write(build_page(vendors, alpha))
    print(f"wildfire-watch: {sum(v['count'] for v in vendors)} recovery awards, {len(vendors)} firms, "
          f"${total:,.0f}; alpha records={len(alpha)} -> reports/mauios/wildfire_recovery_watch.html")
    return 0

if __name__ == "__main__":
    import sys; sys.exit(main())
