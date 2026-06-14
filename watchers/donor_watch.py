#!/usr/bin/env python3
# donor_watch.py - Kilo Aupuni watcher #6: campaign finance -> "reconnect to money choices".
#
# Pulls contributions to each tracked Maui official from the Hawaii Campaign Spending
# Commission public dataset (Socrata SODA API, resource jexd-xbcg on hicscdata.hawaii.gov),
# builds donor profiles, FLAGS real-estate / development-sector donors (the link to housing,
# STR/Bill 9, and permit votes), and cross-references each official's RECUSALS (from
# votes-watch officials.json) so donors and conflicts sit side by side.
#
# INTEGRITY: 100% public records, every figure traceable to the CSC dataset. Donor->vote
# proximity is presented as a QUESTION to investigate, never as proof of a quid pro quo.
#
# Stdlib only. No subprocesses -> no console popups, ever.
import json, os, re, ssl, sys, time, urllib.request, urllib.parse
from datetime import datetime, timedelta, timezone

HOME      = os.path.expanduser("~")
TOOL_DIR  = os.path.dirname(os.path.abspath(__file__))
PROJECT   = os.path.join(HOME, "Documents", "Claude", "Projects", "Video System elementLOTUS")
OUT_DIR   = os.path.join(PROJECT, "reports", "mauios", "donors")
PROFILES_F= os.path.join(PROJECT, "reports", "mauios", "donor_profiles.json")
PAGE_F    = os.path.join(PROJECT, "reports", "mauios", "money_behind_officials.html")
OFFICIALS_F = os.path.join(PROJECT, "reports", "mauios", "officials.json")  # from votes-watch
DISPATCH  = os.path.join(PROJECT, ".dispatch_log.jsonl")
SODA      = "https://hicscdata.hawaii.gov/resource/jexd-xbcg.json"
HST       = timezone(timedelta(hours=-10))

# tracked officials -> the candidate_name LIKE pattern in the CSC dataset
OFFICIALS = [
    ("Bissen",   "BISSEN",            "Richard Bissen - Mayor (incumbent), former judge"),
    ("Sugimura", "SUGIMURA",          "Yuki Lei Sugimura - Council Vice-Chair, BFED Chair; mayoral candidate"),
    ("Lee",      "LEE, ALICE",        "Alice L. Lee - Council Chair"),
    ("Cook",     "COOK, THOMAS",      "Tom Cook - Councilmember, South Maui"),
    ("Johnson",  "JOHNSON, GABRIEL",  "Gabe Johnson - Councilmember"),
    ("Paltin",   "PALTIN",            "Tamara Paltin - Councilmember, West Maui"),
    ("Rawlins-Fernandez", "RAWLINS",  "Keani Rawlins-Fernandez - Councilmember, Molokai"),
    ("Sinenci",  "SINENCI",           "Shane Sinenci - Councilmember, East Maui"),
    ("Uu-Hodgins","HODGINS",          "Nohelani Uʻu-Hodgins - Councilmember"),
    ("Batangan", "BATANGAN",          "Kauanoe Batangan - Councilmember, Kahului"),
]

# employer/occupation signals that tie a donor to land-use / housing / STR money
REALESTATE_KW = ["real estate", "realtor", "realty", "broker", "brokerage", "developer",
                 "development", "property", "properties", "construction", "contractor",
                 "homebuilder", "home builder", "land ", "realtors", "sotheby", "coldwell",
                 "keller williams", "compass", "hawaii life", "berkshire", "remax", "re/max",
                 "vacation rental", "short-term rental", "resort", "hotel", "hospitality"]

def now_hst(): return datetime.now(HST)

def soda(params):
    url = SODA + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "12sgi-kilo-aupuni/1.0 (civic transparency)"})
    with urllib.request.urlopen(req, timeout=90, context=ssl.create_default_context()) as r:
        return json.loads(r.read().decode("utf-8", "replace"))

def dispatch(tag, msg):
    line = {"ts": int(time.time()), "iso": now_hst().strftime("%Y-%m-%d %H:%M:%S"),
            "source": "kilo-aupuni", "event": f"{tag}: {msg}"}
    try:
        with open(DISPATCH, "a", encoding="utf-8") as f:
            f.write(json.dumps(line, ensure_ascii=False) + "\n")
    except Exception:
        pass

def esc(s): return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def usd(x):
    try: return f"{float(x):,.0f}"
    except Exception: return "0"

def fnum(x):
    try: return float(str(x).replace(",", "").strip() or 0)
    except Exception: return 0.0

def is_realestate(row):
    blob = " ".join(str(row.get(k, "")) for k in ("employer", "occupation", "contributor_name")).lower()
    return any(k in blob for k in REALESTATE_KW)

def fetch_contributions(pattern):
    rows = soda({"$where": f"upper(candidate_name) like '%{pattern}%'",
                 "$order": "date DESC", "$limit": "50000"})
    return rows

def profile(key, pattern, label, recusals):
    rows = fetch_contributions(pattern)
    if not rows:
        return {"key": key, "label": label, "rows": 0, "total": 0.0, "candidate_names": [],
                "top_donors": [], "by_type": {}, "realestate": {"count": 0, "total": 0.0, "donors": []},
                "out_of_state_pct": 0, "recusals": recusals}
    cand_names = sorted({r.get("candidate_name", "") for r in rows})
    total = sum(fnum(r.get("amount")) for r in rows)
    by_type = {}; donors = {}; re_rows = []; oos = 0
    for r in rows:
        t = r.get("contributor_type", "?"); by_type[t] = by_type.get(t, 0.0) + fnum(r.get("amount"))
        nm = r.get("contributor_name", "?")
        d = donors.setdefault(nm, {"name": nm, "amount": 0.0, "n": 0,
                                   "employer": r.get("employer", ""), "occupation": r.get("occupation", "")})
        d["amount"] += fnum(r.get("amount")); d["n"] += 1
        if (r.get("non_resident_yes_or_no_") or "").upper().startswith("Y") or (r.get("inoutstate") or "").upper() == "OUT":
            oos += 1
        if is_realestate(r):
            re_rows.append(r)
    top = sorted(donors.values(), key=lambda d: -d["amount"])[:15]
    re_donors = {}
    for r in re_rows:
        nm = r.get("contributor_name", "?")
        rd = re_donors.setdefault(nm, {"name": nm, "amount": 0.0,
                                       "employer": r.get("employer", ""), "occupation": r.get("occupation", "")})
        rd["amount"] += fnum(r.get("amount"))
    re_total = sum(fnum(r.get("amount")) for r in re_rows)
    return {"key": key, "label": label, "rows": len(rows), "total": round(total, 2),
            "candidate_names": cand_names, "top_donors": top, "by_type": by_type,
            "realestate": {"count": len(re_rows), "total": round(re_total, 2),
                           "donors": sorted(re_donors.values(), key=lambda d: -d["amount"])[:12]},
            "out_of_state_pct": round(100 * oos / len(rows)) if rows else 0,
            "recusals": recusals}

def official_report(p):
    def donor_row(d, label_fallback=""):
        meta = d.get("occupation") or d.get("employer") or label_fallback
        meta_html = (" &mdash; " + esc(meta)) if meta else ""
        nx = f' ({d["n"]}x)' if d.get("n") else ""
        return ('<div class="m"><span class="a">$' + usd(d["amount"]) + '</span>'
                '<span class="c">' + esc(d["name"]) + meta_html + nx + '</span></div>')
    top = "".join(donor_row(d) for d in p["top_donors"])
    re_html = "".join(donor_row(d, "real-estate sector") for d in p["realestate"]["donors"]) \
              or '<div class="m"><span class="c">no real-estate-sector donors flagged</span></div>'
    rec_html = "".join(
        f'<div class="m"><span class="a">{esc(r.get("date"))}</span>'
        f'<span class="c">recused on {esc(r.get("item") or "an item")}{(" ($" + esc(", ".join(r.get("dollars") or [])) + ")") if r.get("dollars") else ""} '
        f'&middot; <a href="{esc(r.get("url"))}">minutes</a></span></div>'
        for r in p["recusals"]) or '<div class="m"><span class="c">no recusals recorded</span></div>'
    g = now_hst().strftime("%Y-%m-%d %H:%M HST")
    re_q = (f'<div class="q">Question to investigate: ${p["realestate"]["total"]:,.0f} from real-estate / '
            f'development donors. Cross-check against this official\'s votes on Bill 9 (STR phase-out), '
            f'housing measures, permits, and zoning. Donor money is lawful; the question is whether the '
            f'voting pattern tracks it.</div>') if p["realestate"]["total"] else ""
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Money profile - {esc(p["label"])}</title>
<style>
 body{{margin:0;background:#0c100e;color:#e8e4d8;font-family:Georgia,'Iowan Old Style',serif;line-height:1.55}}
 .wrap{{max-width:880px;margin:0 auto;padding:34px 24px 60px}}
 .eyebrow{{font-family:Consolas,monospace;font-size:11px;letter-spacing:1.2px;color:#d9b24c;text-transform:uppercase}}
 h1{{font-size:23px;font-weight:600;margin:8px 0 2px}}
 .kpi{{display:flex;gap:26px;margin:10px 0}} .kpi .n{{font-family:Consolas,monospace;font-size:22px;color:#d9b24c}}
 .kpi .l{{font-family:Consolas,monospace;font-size:11px;color:#9a957f;text-transform:uppercase}}
 .sect{{font-family:Consolas,monospace;font-size:11px;letter-spacing:1px;color:#d9b24c;text-transform:uppercase;
        border-bottom:1px solid rgba(217,178,76,.25);padding-bottom:6px;margin:28px 0 12px}}
 .m{{display:flex;gap:12px;align-items:baseline;border-bottom:1px solid rgba(255,255,255,.06);padding:6px 0}}
 .m .a{{font-family:Consolas,monospace;font-size:12.5px;color:#d9b24c;white-space:nowrap;min-width:90px;text-align:right}}
 .m .c{{font-size:12.5px;color:#bdb8a4}}
 .q{{font-size:13px;color:#e8d9a8;background:rgba(224,106,74,.07);border-radius:8px;padding:9px 12px;margin-top:10px}}
 a{{color:#d9b24c}}
 footer{{margin-top:40px;border-top:1px solid rgba(255,255,255,.1);padding-top:12px;
        font-family:Consolas,monospace;font-size:10.5px;color:#9a957f;letter-spacing:.4px}}
</style></head><body><div class="wrap">
<div class="eyebrow">12 Stones Global · Kilo Aupuni · money behind officials · follow the money</div>
<h1>{esc(p["label"])}</h1>
<div class="kpi">
 <div><div class="n">${esc(f"{p['total']:,.0f}")}</div><div class="l">total raised (CSC record)</div></div>
 <div><div class="n">{p["rows"]}</div><div class="l">contributions</div></div>
 <div><div class="n">${esc(f"{p['realestate']['total']:,.0f}")}</div><div class="l">real-estate sector</div></div>
 <div><div class="n">{p["out_of_state_pct"]}%</div><div class="l">out-of-state</div></div>
</div>
<div class="sect">Real-estate / development donors &mdash; the housing &amp; STR money</div>
{re_html}
{re_q}
<div class="sect">Recusals (from meeting minutes) &mdash; the conflict trail</div>
{rec_html}
<div class="sect">Top donors overall</div>
{top}
<footer>generated {g} · donor-watch v1 · source: Hawaii Campaign Spending Commission (jexd-xbcg) · facts + questions, not accusations · govOS</footer>
</div></body></html>"""

def build_page(profiles):
    rows = sorted(profiles, key=lambda p: -p["realestate"]["total"])
    cards = ""
    for p in rows:
        cards += (f'<div class="card"><div class="nm">{esc(p["label"])}</div>'
                  f'<div class="stat">${p["total"]:,.0f} raised · {p["rows"]} gifts · '
                  f'<b style="color:#e06a4a">${p["realestate"]["total"]:,.0f} real-estate</b> · '
                  f'{len(p["recusals"])} recusal(s) · {p["out_of_state_pct"]}% out-of-state · '
                  f'<a href="donors/{esc(p["key"])}.html">full profile &rarr;</a></div></div>')
    g = now_hst().strftime("%Y-%m-%d %H:%M HST")
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>The Money Behind Maui's Officials - 12 Stones</title>
<style>
 body{{margin:0;background:#0c100e;color:#e8e4d8;font-family:Georgia,'Iowan Old Style',serif;line-height:1.55}}
 .wrap{{max-width:920px;margin:0 auto;padding:34px 24px 60px}}
 .eyebrow{{font-family:Consolas,monospace;font-size:11px;letter-spacing:1.2px;color:#d9b24c;text-transform:uppercase}}
 h1{{font-size:27px;font-weight:600;margin:8px 0 2px}}
 .lead{{font-size:13.5px;color:#bdb8a4;max-width:80ch}}
 .disc{{font-size:12px;color:#9a957f;font-style:italic;border-left:2px solid rgba(217,178,76,.4);padding:6px 12px;margin:14px 0}}
 .card{{border:1px solid rgba(255,255,255,.1);border-radius:12px;padding:13px 16px;margin:10px 0;background:rgba(255,255,255,.02)}}
 .nm{{font-size:16px;font-weight:600}} .stat{{font-family:Consolas,monospace;font-size:12px;color:#9a957f;margin-top:5px}}
 a{{color:#d9b24c}}
 footer{{margin-top:40px;border-top:1px solid rgba(255,255,255,.1);padding-top:12px;
        font-family:Consolas,monospace;font-size:10.5px;color:#9a957f;letter-spacing:.4px}}
</style></head><body><div class="wrap">
<div class="eyebrow">12 Stones Global · Kilo Aupuni · money behind officials</div>
<h1>The Money Behind Maui's Officials</h1>
<p class="lead">Campaign contributions to each tracked official, from the Hawaii Campaign Spending
Commission public record, with real-estate / development donors flagged and recusals attached.
Sorted by real-estate-sector money — the dollars closest to housing, STR (Bill 9), and permit votes.</p>
<div class="disc">All figures are public record (CSC dataset jexd-xbcg). Contributions are lawful.
The point is the <b>map</b>: who funds whom, and whether votes track the money. Every claim here is a
question for reporting and verification — not an allegation against any donor or official.</div>
{cards}
<footer>generated {g} · donor-watch v1 · source: Hawaii Campaign Spending Commission · govOS · aloha in action</footer>
</div></body></html>"""

def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    officials = {}
    if os.path.exists(OFFICIALS_F):
        try: officials = json.load(open(OFFICIALS_F, encoding="utf-8"))
        except Exception: officials = {}
    try:
        profiles = []
        for key, pattern, label in OFFICIALS:
            recusals = officials.get(key, {}).get("recusals", [])
            try:
                time.sleep(0.5)
                p = profile(key, pattern, label, recusals)
            except Exception as e:
                dispatch("FINDING", f"donor-watch failed for {key}: {e}")
                continue
            profiles.append(p)
            with open(os.path.join(OUT_DIR, f"{key}.html"), "w", encoding="utf-8") as f:
                f.write(official_report(p))
        # serializable profiles (drop heavy nested for the json)
        slim = [{k: v for k, v in p.items() if k != "top_donors"} | {"top_donors": p["top_donors"][:8]}
                for p in profiles]
        json.dump(slim, open(PROFILES_F, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
        with open(PAGE_F, "w", encoding="utf-8") as f:
            f.write(build_page(profiles))
        re_total = sum(p["realestate"]["total"] for p in profiles)
        dispatch("SHIPPED", f"donor-watch profiled {len(profiles)} officials from HI Campaign Spending Commission; "
                 f"${re_total:,.0f} in real-estate/development money flagged across them "
                 f"-> reports/mauios/money_behind_officials.html")
        return 0
    except Exception as e:
        dispatch("FINDING", f"donor-watch run failed: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
