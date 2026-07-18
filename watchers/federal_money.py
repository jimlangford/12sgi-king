#!/usr/bin/env python3
# federal_money.py - Kilo Aupuni FEDERAL-dollars watcher.
#   Pulls federal awards (contracts + grants) whose PLACE OF PERFORMANCE is in
#   Hawaii, tagging the Maui County (FIPS 15009) subset, from USASpending.gov.
#   This is the "federal dollars into Maui + State of Hawaii" AUDIT lens (elections).
#
# Source: USASpending.gov public API (no key):
#   POST https://api.usaspending.gov/api/v2/search/spending_by_award/
#
# Integrity (same standard as the rest of Kilo Aupuni): facts + sourced links only.
# Federal $ landing in a place is a QUESTION ("who received it, who decided, who
# benefits?"), never an accusation. The recipient list feeds the money x votes join
# (federal_donor_join) so we can ASK whether federal contractors also fund local
# deciders - but that join labels every hit "name match - verify identity".
#
# Stdlib only. No window. Windowless by design (no-popup policy).
import json, os, re, sys, time, urllib.request
from datetime import datetime, timedelta, timezone

HOME    = os.path.expanduser("~")
PROJECT = os.path.join(HOME, "Documents", "Claude", "Projects", "Video System elementLOTUS")
OUT_DIR = os.path.join(PROJECT, "reports", "mauios")
JSON_F  = os.path.join(OUT_DIR, "federal_money_maui.json")
HTML_F  = os.path.join(OUT_DIR, "federal_money.html")
STATE_F = os.path.join(os.path.dirname(os.path.abspath(__file__)), "federal_state.json")
DISPATCH= os.path.join(PROJECT, ".dispatch_log.jsonl")
API     = "https://api.usaspending.gov/api/v2/search/spending_by_award/"
HST     = timezone(timedelta(hours=-10))

# Federal fiscal-year window. Default = the four FYs that include the Aug-2023 Lahaina
# fire and the federal disaster response (the most election-relevant Maui federal money).
START   = os.environ.get("KA_FED_START", "2021-10-01")
END     = os.environ.get("KA_FED_END",   "2026-09-30")
MAX_PAGES = int(os.environ.get("KA_FED_PAGES", "8"))     # 8 x 100 = top 800 per category
PAGE_LIMIT = 100

# award_type_codes groups (USASpending)
GROUPS = {
    "contracts": ["A", "B", "C", "D"],
    "grants":    ["02", "03", "04", "05"],
    "direct":    ["06", "10"],
}
# Hawaii place-of-performance. county "009" = Maui (FIPS 15009). State-only filter (no
# county) captures all of Hawaii; we tag the Maui subset from each award's county.
HI_STATE = {"country": "USA", "state": "HI"}
HI_MAUI  = {"country": "USA", "state": "HI", "county": "009"}   # Maui FIPS 15009
MAUI_COUNTY = "009"

FIELDS = ["Award ID", "Recipient Name", "Award Amount", "Awarding Agency",
          "Awarding Sub Agency", "Award Type", "Start Date", "End Date",
          "Place of Performance State Code", "Place of Performance County Code",
          "Description", "generated_internal_id"]


def now_hst(): return datetime.now(HST)

def dispatch(tag, msg):
    line = {"ts": int(time.time()), "iso": now_hst().strftime("%Y-%m-%d %H:%M:%S"),
            "source": "kilo-aupuni", "event": f"{tag}: {msg}"}
    try:
        with open(DISPATCH, "a", encoding="utf-8") as f:
            f.write(json.dumps(line, ensure_ascii=False) + "\n")
    except Exception:
        pass

def esc(s): return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

# Yale-blue industry/agency % breakdown bars (Jimmy 2026-06-16: "% breakdowns of industry especially federal
# at the top, correct yale-blue"). .ind CSS carries no literal % so it embeds safely in %-format style strings.
_IND_CSS = (".ind{margin:.5rem 0 1.1rem}.ind .ih{font-size:.78rem;letter-spacing:.04em;text-transform:uppercase;"
    "color:#6d7f97;font-weight:600;margin-bottom:.45rem}.ind .row{display:grid;grid-template-columns:210px 1fr 58px;"
    "gap:10px;align-items:center;margin:.3rem 0;font-size:.86rem}.ind .nm{color:#13243d;overflow:hidden;"
    "text-overflow:ellipsis;white-space:nowrap}.ind .tr{background:#dae5f3;border-radius:99px;height:13px;overflow:hidden}"
    ".ind .tr i{display:block;height:13px;border-radius:99px;background:linear-gradient(90deg,#00356b,#1259a3)}"
    ".ind .pc{font-family:Consolas,monospace;font-weight:700;color:#00356b;text-align:right}"
    "@media(max-width:560px){.ind .row{grid-template-columns:130px 1fr 48px}}")
def _agency_bars(awards, total, label="Where the federal money comes from — by awarding agency (share of $)"):
    from collections import defaultdict
    agg = defaultdict(float)
    for a in awards:
        agg[(a.get("agency") or "Other").strip() or "Other"] += a.get("amount", 0) or 0
    tot = total or sum(agg.values()) or 1
    top = sorted(agg.items(), key=lambda x: -x[1])[:8]
    body = "".join(
        '<div class=row><span class=nm>%s</span><span class=tr><i style="width:%.1f%%"></i></span><span class=pc>%d%%</span></div>'
        % (esc(n), min(100.0, 100.0 * v / tot), round(100 * v / tot)) for n, v in top)
    return '<div class=ind><div class=ih>%s</div>%s</div>' % (esc(label), body)

def post(body):
    req = urllib.request.Request(API, data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "User-Agent": "kilo-aupuni/1.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode())

def fetch_group(codes, location):
    """Page through one award-type group for a given place-of-performance location
    (state-wide HI, or Maui county 009 explicitly — the per-award county field is
    unreliable when querying state-wide, so we query Maui directly)."""
    out, page = [], 1
    while page <= MAX_PAGES:
        body = {
            "filters": {
                "time_period": [{"start_date": START, "end_date": END}],
                "place_of_performance_locations": [location],
                "award_type_codes": codes,
            },
            "fields": FIELDS, "page": page, "limit": PAGE_LIMIT,
            "sort": "Award Amount", "order": "desc",
        }
        try:
            d = post(body)
        except Exception as e:
            dispatch("FINDING", f"federal_money group page {page} failed: {e}")
            break
        rows = d.get("results", [])
        out.extend(rows)
        if not d.get("page_metadata", {}).get("hasNext"):
            break
        page += 1
        time.sleep(0.4)          # be gentle to the public API
    return out

def amt(r):
    try: return float(r.get("Award Amount") or 0)
    except Exception: return 0.0

# Hawaii county FIPS subsets — so EACH county tenant gets its real federal slice (Jimmy 2026-06-16).
# USASpending "Place of Performance County Code" is the 3-digit within state FIPS 15.
COUNTY_NAMES = {"001": "Hawaiʻi County", "003": "Honolulu", "007": "Kauaʻi", "009": "Maui County"}
COUNTY_PAGE  = {"001": "federal_money_hawaii.html", "003": "federal_money_honolulu.html",
                "007": "federal_money_kauai.html",  "009": "federal_money.html"}

def _write_county_pages(by_county, payload):
    """One dignified, sourced federal page per Hawaii county (Maui keeps federal_money.html)."""
    for code, c in by_county.items():
        if code == "009":      # Maui already served by the main federal_money.html
            continue
        page = COUNTY_PAGE.get(code)
        if not page: continue
        aws = sorted(c["awards"], key=lambda x: -x["amount"])[:120]
        rows = "".join(
            "<tr><td class=amt>$%s</td><td>%s</td><td class=ag>%s</td><td class=ds>%s</td></tr>" % (
                "{:,.0f}".format(x["amount"]), esc(x["recipient"]), esc(x.get("agency") or ""),
                esc((x.get("desc") or "")[:120]))
            for x in aws) or ("<tr><td colspan=4 class=ds>No federal awards with place of performance in this "
                              "county were found in the window. The record fills as USASpending posts them.</td></tr>")
        html = ("<!doctype html><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'>"
            "<title>%s — Federal dollars | govOS</title><style>"
            "body{font-family:'Segoe UI',system-ui,sans-serif;max-width:1000px;margin:1.3rem auto;padding:0 1rem;color:#13243d;background:#fff}"
            "h1{font-size:1.5rem;margin:.3rem 0}.sub{color:#41536b;font-size:.9rem}.kpi{font-family:Consolas,monospace;color:#00356b;font-weight:700;font-size:1.1rem;margin:.6rem 0}"
            ".disc{background:#0f2540;border:1px solid #1f3d5f;border-radius:10px;padding:.7rem 1rem;color:#41536b;font-size:.85rem;margin:.8rem 0}"
            "table{border-collapse:collapse;width:100%%;font-size:.85rem}td,th{padding:.4rem .5rem;border-bottom:1px solid #e3e9f1;text-align:left;vertical-align:top}"
            ".amt{font-family:Consolas,monospace;color:#00356b;white-space:nowrap}.ag{color:#41536b}.ds{color:#6d7f97;font-size:.8rem}a{color:#1259a3}"
            +_IND_CSS+"</style>"
            "<h1>%s — federal dollars</h1>"
            "<div class=sub>Federal awards (contracts + grants) with place of performance in %s. "
            "Source: <a href='https://www.usaspending.gov/'>USASpending.gov</a> · window %s–%s · generated %s.</div>"
            "<div class=kpi>$%s across %d awards</div>%s"
            "<div class=disc>Federal money landing in a place is a <b>question for oversight</b> — who received it, "
            "who decided, who benefits — never an accusation. Every recipient links back to the public record.</div>"
            "<table><thead><tr><th>amount</th><th>recipient</th><th>awarding agency</th><th>description</th></tr></thead>"
            "<tbody>%s</tbody></table>"
            "<p class=sub style='margin-top:1rem'><a href='tenant_hi-%s.html'>← overview</a> · "
            "<a href='federal_money.html'>Maui federal</a> · <a href='tenants_hub.html'>all governments</a></p>") % (
            esc(c["name"]), esc(c["name"]), esc(c["name"]),
            payload["window"]["start"], payload["window"]["end"], payload["generated"],
            "{:,.0f}".format(c["total"]), c["count"],
            _agency_bars(c["awards"], c["total"], "Where %s's federal money comes from — by awarding agency (share of $)" % esc(c["name"])),
            rows, COUNTY_TID.get(code, ""))
        with open(os.path.join(OUT_DIR, page), "w", encoding="utf-8", newline="\n") as f:
            f.write(html)

COUNTY_TID = {"001": "hawaii", "003": "honolulu", "007": "kauai", "009": "maui"}

def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    by_recipient, awards = {}, []
    totals = {"hawaii": 0.0, "maui": 0.0}
    counts = {"hawaii": 0, "maui": 0}
    # Build (row, group, is_maui) records: Maui (county 009) query FIRST so every Maui
    # award is captured + summed exactly, then the state-wide superset (deduped by id).
    seen = set()
    records = []
    for group, codes in GROUPS.items():
        for r in fetch_group(codes, HI_MAUI):
            i = r.get("Award ID") or r.get("generated_internal_id")
            if i and i in seen: continue
            if i: seen.add(i)
            records.append((r, group, True))
    for group, codes in GROUPS.items():
        for r in fetch_group(codes, HI_STATE):
            i = r.get("Award ID") or r.get("generated_internal_id")
            if i and i in seen: continue
            if i: seen.add(i)
            records.append((r, group, False))
    for r, group, maui in records:
            a = amt(r)
            rec = (r.get("Recipient Name") or "UNKNOWN").strip()
            awards.append({
                "id": r.get("Award ID"), "recipient": rec, "amount": a,
                "agency": r.get("Awarding Agency"), "sub_agency": r.get("Awarding Sub Agency"),
                "type": group, "award_type": r.get("Award Type"),
                "start": r.get("Start Date"), "end": r.get("End Date"),
                "county": r.get("Place of Performance County Code"),
                "maui": maui, "desc": (r.get("Description") or "")[:240],
                "gid": r.get("generated_internal_id"),
            })
            totals["hawaii"] += a; counts["hawaii"] += 1
            if maui: totals["maui"] += a; counts["maui"] += 1
            b = by_recipient.setdefault(rec, {"recipient": rec, "total": 0.0, "maui_total": 0.0,
                                              "count": 0, "agencies": set(), "types": set()})
            b["total"] += a; b["count"] += 1
            b["agencies"].add(r.get("Awarding Agency") or "")
            b["types"].add(group)
            if maui: b["maui_total"] += a
    recips = sorted(by_recipient.values(), key=lambda x: -x["total"])
    for b in recips:
        b["agencies"] = sorted(a for a in b["agencies"] if a)
        b["types"] = sorted(b["types"])
    # per-county federal slice: the per-award county field is unreliable, so query each county EXPLICITLY
    # (same proven pattern as the Maui-009 query). Maui (009) is already captured above.
    by_county = {"009": {"name": COUNTY_NAMES["009"], "total": totals["maui"], "count": counts["maui"],
                         "awards": [a for a in awards if a.get("maui")]}}
    for code in ("001", "003", "007"):
        loc = {"country": "USA", "state": "HI", "county": code}
        bc = by_county.setdefault(code, {"name": COUNTY_NAMES[code], "total": 0.0, "count": 0, "awards": []})
        cseen = set()
        for group, codes in GROUPS.items():
            for r in fetch_group(codes, loc):
                i = r.get("Award ID") or r.get("generated_internal_id")
                if i and i in cseen: continue
                if i: cseen.add(i)
                a = amt(r)
                bc["total"] += a; bc["count"] += 1
                bc["awards"].append({"recipient": (r.get("Recipient Name") or "UNKNOWN").strip(),
                                     "amount": a, "agency": r.get("Awarding Agency"),
                                     "desc": (r.get("Description") or "")[:240]})
    payload = {
        "generated": now_hst().strftime("%Y-%m-%d %H:%M:%S HST"),
        "window": {"start": START, "end": END},
        "source": "USASpending.gov /api/v2/search/spending_by_award/ (place of performance = Hawaii)",
        "totals": totals, "counts": counts,
        "n_recipients": len(recips),
        "recipients": recips[:400],
        "awards": sorted(awards, key=lambda x: -x["amount"])[:600],
        "note": "Federal dollars landing in Hawaii (Maui subset by FIPS 15009). Facts only; "
                "presence of federal money is a question for oversight, never an accusation.",
    }
    tmp = JSON_F + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)
    os.replace(tmp, JSON_F)
    with open(STATE_F, "w", encoding="utf-8") as f:
        json.dump({"last_run": payload["generated"], "n_awards": len(awards),
                   "maui_total": totals["maui"], "hawaii_total": totals["hawaii"]}, f, indent=1)
    payload["by_county"] = {code: {"name": c["name"], "total": c["total"], "count": c["count"]}
                            for code, c in by_county.items()}
    _write_html(payload)
    _write_county_pages(by_county, payload)
    _cty = " · ".join("%s $%s" % (c["name"], "{:,.0f}".format(c["total"])) for c in by_county.values() if c["count"])
    print("  per-county: " + _cty)
    dispatch("SHIPPED", f"federal_money: HI ${totals['hawaii']:,.0f} ({counts['hawaii']} awards), "
                        f"Maui ${totals['maui']:,.0f} ({counts['maui']}), {len(recips)} recipients")
    print(f"federal_money: Hawaii ${totals['hawaii']:,.0f} / Maui ${totals['maui']:,.0f} "
          f"across {len(awards)} awards, {len(recips)} recipients -> {JSON_F}")
    return 0

def _write_html(p):
    t = p["totals"]; c = p["counts"]
    rows = "".join(
        f'<div class=rcp><span class=rn>{esc(r["recipient"])}</span>'
        f'<span class=ra>${r["total"]:,.0f}<span class=rd> &middot; Maui ${r["maui_total"]:,.0f} &middot; {r["count"]} awards</span></span></div>'
        for r in p["recipients"][:120])
    # cross-links into the money web — only the ones that exist as published Maui pages
    _links = [("money_behind_officials.html","who funds the officials"),
              ("contracts_x_donors.html","contracts &times; donors"),
              ("realestate_maui.html","real estate &times; money"),
              ("orgs_maui.html","organizations behind the money"),
              ("connections_maui.html","the loop, on the record"),
              ("tenant_hi-maui.html","Maui County overview")]
    _md = os.path.dirname(HTML_F)
    linkrow = " &middot; ".join(f'<a href="{fn}">{lbl}</a>' for fn, lbl in _links
                                if os.path.exists(os.path.join(_md, fn)))
    html = f"""<!doctype html><meta charset=utf-8><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><meta name="theme-color" content="#00356b">
<title>Federal dollars — Maui &amp; the State of Hawaiʻi | govOS</title>
<style>:root{{--bg:#081420;--panel:#0f2540;--line:#1f3d5f;--ink:#eaf2fc;--dim:#9fb2c8;--faint:#6d7f97;--accent:#4a9eff;--accent2:#6cb0f0;--ok:#1f8a5b}}
*{{box-sizing:border-box}}body{{font-family:'Segoe UI Variable Text','Segoe UI',system-ui,sans-serif;max-width:900px;margin:0 auto;padding:18px 16px 44px;color:var(--ink);background:var(--bg);font-size:16px;line-height:1.55}}
a{{color:var(--accent2)}}h1{{font-size:1.5rem;margin:.3rem 0}}h2{{color:var(--accent);font-size:1.05rem;margin:1.2rem 0 .4rem}}
.sub{{color:var(--dim);font-size:.95rem;line-height:1.55}}
.kpis{{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin:1rem 0}}@media(max-width:560px){{.kpis{{grid-template-columns:1fr}}}}
.kp{{background:var(--panel);border:1px solid var(--line);border-radius:11px;padding:.7rem .85rem}}.kv{{font:700 18px/1.1 'JetBrains Mono',Consolas,monospace;color:var(--accent)}}.kl{{font-size:11px;color:var(--faint);text-transform:uppercase;letter-spacing:.4px;margin-top:4px}}
.note{{background:#241d0e;border:1px solid #5c4a1e;border-left:3px solid #b8860b;border-radius:10px;padding:.7rem 1rem;margin:.9rem 0;font-size:.9rem;color:#e3c98a;line-height:1.5}}
.lnk{{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:.6rem .9rem;margin:.6rem 0;font-size:.92rem;line-height:1.9}}
.rcp{{display:flex;justify-content:space-between;gap:12px;align-items:baseline;border-bottom:1px solid #e3e9f1;padding:.5rem .1rem;font-size:.92rem}}
.rcp .rn{{color:var(--ink);min-width:0;overflow-wrap:anywhere;flex:1}}.rcp .ra{{font-family:Consolas,monospace;color:var(--accent);display:flex;flex-direction:column;align-items:flex-end;text-align:right;flex-shrink:0}}.rcp .rd{{color:var(--faint);font-size:.78rem;white-space:normal}}
{_IND_CSS}</style>
<div class=sub style="letter-spacing:.1em;text-transform:uppercase;color:var(--accent2);font-weight:600">govOS &middot; Maui County &middot; asked in aloha</div>
<h1>Federal dollars — Maui &amp; the State of Hawaiʻi</h1>
<div class=sub>Federal money (contracts + grants) recorded as spent in Hawaiʻi, with the Maui share called out — so anyone
can ask the oversight questions: who received it, which agency awarded it, and did the people who decide local matters
benefit. A question to verify, never a finding. Source: <a href="https://www.usaspending.gov/">USASpending.gov</a> &middot;
window {esc(p['window']['start'])}–{esc(p['window']['end'])} &middot; generated {esc(p['generated'])}.</div>
<div class=kpis>
 <div class=kp><div class=kv>${t['hawaii']:,.0f}</div><div class=kl>State of Hawaiʻi &middot; {c['hawaii']} awards</div></div>
 <div class=kp><div class=kv>${t['maui']:,.0f}</div><div class=kl>Maui County &middot; {c['maui']} awards</div></div>
 <div class=kp><div class=kv>{p['n_recipients']}</div><div class=kl>distinct recipients</div></div>
</div>
{_agency_bars(p['awards'], None, "Where Hawaiʻi’s federal money comes from — by awarding agency (share of recorded awards)")}
<div class=lnk><b>Follow it further:</b> {linkrow}</div>
<div class=note>Federal money landing in a place is a question for oversight — who received it, who decided, who benefits — never an accusation. Every recipient links back to the public record.</div>
<h2>Top recipients by total (HI)</h2>
{rows}
<p class=sub style="margin-top:1rem">Showing top 120 recipients. Full data in <code>federal_money_maui.json</code>.
This is a records-awareness tool; lawful action (records requests, reporting, voting) is the endpoint.</p>"""
    tmp = HTML_F + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(html)
    os.replace(tmp, HTML_F)

if __name__ == "__main__":
    sys.exit(main())
