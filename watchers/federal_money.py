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
    _write_html(payload)
    dispatch("SHIPPED", f"federal_money: HI ${totals['hawaii']:,.0f} ({counts['hawaii']} awards), "
                        f"Maui ${totals['maui']:,.0f} ({counts['maui']}), {len(recips)} recipients")
    print(f"federal_money: Hawaii ${totals['hawaii']:,.0f} / Maui ${totals['maui']:,.0f} "
          f"across {len(awards)} awards, {len(recips)} recipients -> {JSON_F}")
    return 0

def _write_html(p):
    t = p["totals"]; c = p["counts"]
    rows = "".join(
        f"<tr><td>{esc(r['recipient'])}</td><td class=n>${r['total']:,.0f}</td>"
        f"<td class=n>${r['maui_total']:,.0f}</td><td class=n>{r['count']}</td>"
        f"<td>{esc(', '.join(r['agencies'][:3]))}</td></tr>"
        for r in p["recipients"][:120])
    html = f"""<!doctype html><meta charset=utf-8>
<title>Federal Dollars - Maui & State of Hawaii | Kilo Aupuni</title>
<style>body{{font-family:system-ui,Segoe UI,sans-serif;max-width:1100px;margin:2rem auto;padding:0 1rem;color:#1a1a1a}}
h1{{font-size:1.5rem}} .sub{{color:#555}} table{{border-collapse:collapse;width:100%;margin-top:1rem;font-size:.92rem}}
th,td{{border-bottom:1px solid #e3e3e3;padding:.45rem .6rem;text-align:left}} th{{background:#f4f6f8}}
.n{{text-align:right;font-variant-numeric:tabular-nums}} .kpi{{display:flex;gap:2rem;margin:1rem 0}}
.kpi div{{background:#f4f6f8;border-radius:10px;padding:.8rem 1.2rem}} .kpi b{{font-size:1.3rem;display:block}}
.note{{background:#fff8e6;border-left:4px solid #e0b400;padding:.7rem 1rem;margin:1rem 0;font-size:.9rem}}</style>
<h1>Federal Dollars into Maui &amp; the State of Hawai&#699;i</h1>
<div class=sub>In plain words: this is federal money (contracts + grants) recorded as being spent in
Hawai&#699;i, with the Maui County share called out. It is published so anyone can ask the oversight
questions: who received it, which agency awarded it, what was it for, and did the people who decide
local matters benefit. Source: USASpending.gov. Window {esc(p['window']['start'])} to {esc(p['window']['end'])}.
Generated {esc(p['generated'])}.</div>
<div class=kpi>
 <div>State of Hawai&#699;i<b>${t['hawaii']:,.0f}</b>{c['hawaii']} awards</div>
 <div>Maui County<b>${t['maui']:,.0f}</b>{c['maui']} awards</div>
 <div>Recipients<b>{p['n_recipients']}</b>distinct</div>
</div>
<div class=note>{esc(p['note'])}</div>
<table><thead><tr><th>Recipient</th><th class=n>Total (HI)</th><th class=n>Maui</th>
<th class=n>Awards</th><th>Top agencies</th></tr></thead><tbody>{rows}</tbody></table>
<p class=sub style=margin-top:1rem>Showing top 120 recipients by total. Full data in
<code>federal_money_maui.json</code>. This is a records-awareness tool; lawful action
(records requests, reporting, voting) is the endpoint.</p>"""
    tmp = HTML_F + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(html)
    os.replace(tmp, HTML_F)

if __name__ == "__main__":
    sys.exit(main())
