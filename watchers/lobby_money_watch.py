#!/usr/bin/env python3
"""lobby_money_watch.py — Kilo Aupuni: the LOBBY + MONEY overlap.
Pulls the Hawaiʻi State Ethics Commission lobbyist-registration open data (public), and finds
the entities that BOTH register to lobby the State AND donate to the tracked Maui officials —
a double channel of influence. Public records, framed as documented facts + open questions,
never accusations. Output: reports/mauios/lobby_money_watch.{json,html}.
Source: opendata.hawaii.gov (Hawaii State Ethics Commission lobbyist registration statements).
"""
import os, json, csv, re, ssl, io, urllib.request
from datetime import datetime, timezone, timedelta

HOME = os.path.expanduser("~")
PROJECT = os.path.join(HOME, "Documents", "Claude", "Projects", "Video System elementLOTUS")
MAUIOS = os.path.join(PROJECT, "reports", "mauios")
DONORS = os.path.join(MAUIOS, "donor_profiles.json")
CACHE = os.path.join(MAUIOS, "_lobby_src", "lob_reg.csv")
OUT_JSON = os.path.join(MAUIOS, "lobby_money_watch.json")
OUT_HTML = os.path.join(MAUIOS, "lobby_money_watch.html")
CSV_URL = ("https://opendata.hawaii.gov/dataset/9f4e6414-dd04-40bf-88d2-31b5b8b6e8d3/resource/"
           "f186ec29-a1c8-4985-b92e-870b19db8211/download/socrata_-lobbyist-registration-statements.csv")
HST = timezone(timedelta(hours=-10))
UA = {"User-Agent": "Mozilla/5.0 (kilo-aupuni civic transparency; public record)"}
esc = lambda s: str(s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
usd = lambda n: f"{n:,.0f}"
def now_hst(): return datetime.now(HST)

def norm(s):
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", (s or "").lower())).strip()

# entity suffixes to peel so "Lanai Resorts, LLC dba Pulama Lanai" -> key "lanai resorts"
SUFFIX = re.compile(r"\b(llc|inc|ltd|lp|llp|corp|company|co|pac|political action committee|"
                    r"dba .*|incorporated|limited)\b.*$")
def org_key(org):
    n = norm(org)
    k = SUFFIX.sub("", n).strip()
    return k if len(k) >= 8 and len(k.split()) >= 2 else (n if len(n) >= 8 else "")

def load_registrations():
    if not os.path.exists(CACHE):
        os.makedirs(os.path.dirname(CACHE), exist_ok=True)
        req = urllib.request.Request(CSV_URL, headers=UA)
        data = urllib.request.urlopen(req, timeout=90, context=ssl.create_default_context()).read()
        open(CACHE, "wb").write(data)
    rows = list(csv.DictReader(open(CACHE, encoding="utf-8-sig", errors="replace")))
    orgs = {}
    for r in rows:
        o = (r.get("Organization") or "").strip()
        if not o:
            continue
        d = orgs.setdefault(o, {"org": o, "lobbyists": set(), "years": set()})
        if r.get("Full Name"):
            d["lobbyists"].add(r["Full Name"].strip())
        if r.get("Lobby Year"):
            d["years"].add(str(r["Lobby Year"]).strip())
    return rows, orgs

def donor_records():
    dp = json.load(open(DONORS, encoding="utf-8"))
    out = []
    for o in dp:
        off = (o.get("official") or {}).get("label") if isinstance(o.get("official"), dict) else o.get("label")
        for cat, blk in o.items():
            if isinstance(blk, dict):
                for d in blk.get("donors", []) or []:
                    blob = norm((d.get("name") or "") + " " + (d.get("employer") or ""))
                    out.append({"official": off, "name": d.get("name"), "employer": d.get("employer"),
                                "amount": d.get("amount") or 0, "blob": blob})
    return out

def build_overlap(orgs, donors):
    keyed = [(org_key(o), v) for o, v in orgs.items()]
    keyed = [(k, v) for k, v in keyed if k]
    overlap = {}
    for k, v in keyed:
        for d in donors:
            if k in d["blob"]:
                ent = overlap.setdefault(v["org"], {"org": v["org"], "lobby_years": sorted(v["years"]),
                                                    "lobbyists": sorted(v["lobbyists"]), "donations": []})
                ent["donations"].append({"official": d["official"], "donor": d["name"],
                                         "employer": d["employer"], "amount": d["amount"]})
    res = []
    for ent in overlap.values():
        offs = {x["official"] for x in ent["donations"]}
        ent["n_officials"] = len(offs)
        ent["total"] = round(sum(x["amount"] for x in ent["donations"]), 2)
        res.append(ent)
    res.sort(key=lambda e: (-e["n_officials"], -e["total"]))
    return res

def build_page(res, n_orgs, n_rows):
    g = now_hst().strftime("%Y-%m-%d %H:%M HST")
    tot = sum(e["total"] for e in res)
    rows = ""
    for e in res:
        dons = "".join(
            f'<div class="aw"><span class="a">${usd(x["amount"])}</span>'
            f'<span class="t">{esc(x["official"])} <span class="dept">&middot; as {esc(x["donor"])}'
            f'{(" / "+esc(x["employer"])) if x["employer"] and x["employer"]!=x["donor"] else ""}</span></span></div>'
            for x in sorted(e["donations"], key=lambda d: -d["amount"]))
        yrs = (e["lobby_years"][0] + "–" + e["lobby_years"][-1]) if len(e["lobby_years"]) > 1 else (e["lobby_years"][0] if e["lobby_years"] else "")
        rows += (f'<div class="vh"><span class="a">${usd(e["total"])}</span>'
                 f'<span class="n">{e["n_officials"]} official{"s" if e["n_officials"]!=1 else ""}</span>'
                 f'<span class="c">{esc(e["org"])} <span class="dept">&middot; registered lobbyist {esc(yrs)}</span></span></div>{dons}')
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Lobby + Money - Who Lobbies AND Pays the Deciders - Kilo Aupuni</title>
<style>
 body{{margin:0;background:#0c100e;color:#e8e4d8;font-family:Georgia,'Iowan Old Style',serif;line-height:1.55}}
 .wrap{{max-width:940px;margin:0 auto;padding:34px 24px 60px}}
 .eyebrow{{font-family:Consolas,monospace;font-size:11px;letter-spacing:1.2px;color:#d9b24c;text-transform:uppercase}}
 h1{{font-size:27px;font-weight:600;margin:8px 0 2px}} h2{{font-size:18px;margin:28px 0 6px}}
 .lead{{font-size:13.5px;color:#bdb8a4;max-width:84ch}}
 .kpi{{display:flex;flex-wrap:wrap;gap:26px;margin:16px 0}}
 .kpi .n{{font-family:Consolas,monospace;font-size:22px;color:#d9b24c}}
 .kpi .l{{font-family:Consolas,monospace;font-size:11px;color:#9a957f;text-transform:uppercase}}
 .disc{{font-size:12px;color:#9a957f;font-style:italic;border-left:2px solid rgba(217,178,76,.4);padding:7px 12px;margin:14px 0}}
 .vh{{display:grid;grid-template-columns:120px 92px 1fr;gap:12px;align-items:baseline;padding:11px 0 5px;border-top:1px solid rgba(217,178,76,.18);margin-top:8px}}
 .vh .a{{font-family:Consolas,monospace;font-size:14px;color:#d9b24c;text-align:right;font-weight:700}}
 .vh .n{{font-family:Consolas,monospace;font-size:11px;color:#e0863a;text-align:center}}
 .vh .c{{font-size:14px;color:#e8e4d8;font-weight:600}}
 .aw{{display:grid;grid-template-columns:120px 1fr;gap:12px;align-items:baseline;padding:2px 0;font-size:12px}}
 .aw .a{{font-family:Consolas,monospace;color:#9a957f;text-align:right}} .aw .t{{color:#bdb8a4}} .dept{{color:#756b56}}
 .q{{background:rgba(217,178,76,.05);border:1px solid rgba(217,178,76,.25);border-radius:10px;padding:12px 15px;margin:16px 0;font-size:13px;color:#cfc9b6}}
 .q b{{color:#e8e4d8}} a{{color:#d9b24c}}
 footer{{margin-top:34px;border-top:1px solid rgba(255,255,255,.1);padding-top:12px;font-family:Consolas,monospace;font-size:10.5px;color:#9a957f}}
</style></head><body><div class="wrap">
<div class="eyebrow">12 Stones Global &middot; Kilo Aupuni &middot; two channels of influence</div>
<h1>Lobby + Money &mdash; who lobbies <i>and</i> pays the deciders</h1>
<p class="lead">Entities that appear in <b>both</b> public records at once: registered to lobby the State of
Hawaiʻi (Ethics Commission) <b>and</b> a campaign donor to a tracked Maui official. Lobbying is lawful;
donating is lawful. Doing both is a <b>double channel</b> &mdash; so it belongs on the map, as a question.</p>
<div class="kpi">
 <div><div class="n">{len(res)}</div><div class="l">lobby+donate entities</div></div>
 <div><div class="n">${usd(tot)}</div><div class="l">their donations to deciders</div></div>
 <div><div class="n">{n_orgs:,}</div><div class="l">orgs in lobbyist registry</div></div>
 <div><div class="n">{n_rows:,}</div><div class="l">registration filings scanned</div></div>
</div>
<div class="disc">Sources: Hawaiʻi State Ethics Commission lobbyist registration statements (opendata.hawaii.gov)
&times; campaign-finance donor profiles (public record). Matched on entity name. Lawful activity &mdash; documented
facts and open questions, not findings of wrongdoing. NOTE: this is <b>State</b> lobbying; Maui County
contract awardees who lobby only at the county level (or not at all) will not appear here &mdash; that gap is
why the subcontractor + sole-source UIPA requests matter.</div>

<div class="q"><b>The question.</b> When the same entity both funds a council member's campaign and pays
lobbyists to shape the laws that member votes on, two influence channels converge on one decider. The
record below shows which entities do both, and on how many officials. Read it beside their votes and
recusals &mdash; that is where the question gets answered.</div>

<h2>Both lobbying &amp; donating &mdash; by reach</h2>
{rows or '<div class="aw"><span class="t">No overlap on this run.</span></div>'}

<p style="margin-top:22px"><a href="patterns_money_x_votes.html">money &times; votes patterns</a>
&middot; <a href="contracts_x_donors.html">contracts &times; donors</a>
&middot; <a href="wildfire_recovery_watch.html">wildfire recovery money</a>
&middot; <a href="take_action.html">&#9878; demand the county records</a></p>
<footer>generated {g} &middot; lobby-money v1 &middot; source: opendata.hawaii.gov (HSEC lobbyist registrations) + donor profiles &middot; Kilo Aupuni &middot; govOS</footer>
</div></body></html>"""

def main():
    os.makedirs(MAUIOS, exist_ok=True)
    rows, orgs = load_registrations()
    donors = donor_records()
    res = build_overlap(orgs, donors)
    out = {"generated": now_hst().isoformat(),
           "source": "opendata.hawaii.gov HSEC lobbyist registrations + donor_profiles (public record)",
           "registry_orgs": len(orgs), "filings_scanned": len(rows),
           "lobby_and_donate": res}
    json.dump(out, open(OUT_JSON, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    open(OUT_HTML, "w", encoding="utf-8").write(build_page(res, len(orgs), len(rows)))
    print(f"lobby-money: {len(orgs)} registry orgs, {len(rows)} filings; "
          f"{len(res)} entities lobby+donate -> reports/mauios/lobby_money_watch.html")
    for e in res[:8]:
        print(f"   {e['n_officials']}off ${e['total']:>8,.0f}  {e['org']}")
    return 0

if __name__ == "__main__":
    import sys; sys.exit(main())
