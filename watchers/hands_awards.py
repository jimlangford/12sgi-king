#!/usr/bin/env python3
# hands_awards.py - Kilo Aupuni watcher: Maui County CONTRACT AWARDS from HANDS.
#
# HANDS = Hawaii Awards & Notices Data System (hands.ehawaii.gov). Its Angular UI
# is backed by a JSON API at POST /hands/api/contract-awards (size+page+sort query
# params, empty JSON body returns everything). 10,609 award notices statewide; we
# page through (size cap = 2000) and keep the ones whose `jurisdiction` is a Maui
# county entity. These are the public "Notice of Award" records - the VENDOR side
# of the money map, with NO records request needed.
#
# Output: reports/mauios/hands_maui_awards.json (vendor -> total awarded $, count,
# the awards) + a human page. Feeds the vendor<->donor join (vendor_donor_join.py).
#
# INTEGRITY: 100% public award notices. A vendor receiving county contracts is
# normal and lawful; the file is the MAP, not an allegation. Stdlib only, no popups.
import json, os, re, ssl, sys, time, urllib.request
from datetime import datetime, timedelta, timezone

HOME     = os.path.expanduser("~")
PROJECT  = os.path.join(HOME, "Documents", "Claude", "Projects", "Video System elementLOTUS")
OUT_JSON = os.path.join(PROJECT, "reports", "mauios", "hands_maui_awards.json")
OUT_HTML = os.path.join(PROJECT, "reports", "mauios", "maui_contract_awards.html")
DISPATCH = os.path.join(PROJECT, ".dispatch_log.jsonl")
API      = "https://hands.ehawaii.gov/hands/api/contract-awards"
HST      = timezone(timedelta(hours=-10))
PAGE_SZ  = 2000   # server cap

def now_hst(): return datetime.now(HST)

def fetch_page(page):
    url = f"{API}?size={PAGE_SZ}&page={page}&sort=award_date_dt,desc"
    req = urllib.request.Request(url, data=b"{}", method="POST",
                                 headers={"Content-Type": "application/json",
                                          "Accept": "application/json",
                                          "User-Agent": "12sgi-kilo-aupuni/1.0 (civic transparency)"})
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

def money(s):
    try: return float(re.sub(r"[^0-9.]", "", str(s)) or 0)
    except Exception: return 0.0

def usd(x):
    try: return f"{float(x):,.0f}"
    except Exception: return "0"

def pull_all():
    first = fetch_page(0)
    total = int(first.get("data", {}).get("total", 0) or 0)
    rows  = list(first.get("data", {}).get("searchResult", {}).get("content", []) or [])
    pages = (total + PAGE_SZ - 1) // PAGE_SZ
    for p in range(1, pages):
        time.sleep(0.4)
        try:
            d = fetch_page(p)
            rows += d.get("data", {}).get("searchResult", {}).get("content", []) or []
        except Exception as e:
            dispatch("FINDING", f"hands-awards page {p} failed: {e}")
    return rows, total

def is_maui(r):
    j = (r.get("jurisdiction") or "")
    d = (r.get("department") or "")
    return ("maui" in j.lower()) or ("maui" in d.lower())

def build_vendors(maui):
    v = {}
    for r in maui:
        name = (r.get("vendorName") or "").strip()
        if not name:
            continue
        amt = money(r.get("amount"))
        e = v.setdefault(name, {"vendor": name, "total": 0.0, "count": 0, "awards": []})
        e["total"] += amt; e["count"] += 1
        e["awards"].append({"amount": amt, "date": r.get("awardDate"),
                            "title": r.get("title"), "dept": r.get("department"),
                            "category": r.get("category"), "sol": r.get("solicitionNo")})
    return sorted(v.values(), key=lambda x: -x["total"])

def build_page(vendors, total_awards, total_dollars):
    g = now_hst().strftime("%Y-%m-%d %H:%M HST")
    rows = ""
    for v in vendors:
        rows += (f'<div class="m"><span class="a">${usd(v["total"])}</span>'
                 f'<span class="n">{v["count"]}</span>'
                 f'<span class="c">{esc(v["vendor"])} &middot; '
                 f'{esc((v["awards"][0] or {}).get("dept",""))}</span></div>')
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Maui County Contract Awards - 12 Stones</title>
<style>
 body{{margin:0;background:#0c100e;color:#e8e4d8;font-family:Georgia,'Iowan Old Style',serif;line-height:1.55}}
 .wrap{{max-width:920px;margin:0 auto;padding:34px 24px 60px}}
 .eyebrow{{font-family:Consolas,monospace;font-size:11px;letter-spacing:1.2px;color:#d9b24c;text-transform:uppercase}}
 h1{{font-size:26px;font-weight:600;margin:8px 0 2px}}
 .lead{{font-size:13.5px;color:#bdb8a4;max-width:82ch}}
 .kpi{{display:flex;gap:28px;margin:14px 0}} .kpi .n{{font-family:Consolas,monospace;font-size:22px;color:#d9b24c}}
 .kpi .l{{font-family:Consolas,monospace;font-size:11px;color:#9a957f;text-transform:uppercase}}
 .disc{{font-size:12px;color:#9a957f;font-style:italic;border-left:2px solid rgba(217,178,76,.4);padding:7px 12px;margin:14px 0}}
 .hd,.m{{display:grid;grid-template-columns:130px 50px 1fr;gap:12px;align-items:baseline;padding:6px 0;border-bottom:1px solid rgba(255,255,255,.06)}}
 .hd{{font-family:Consolas,monospace;font-size:10px;letter-spacing:1px;color:#9a957f;text-transform:uppercase}}
 .m .a{{font-family:Consolas,monospace;font-size:12.5px;color:#d9b24c;text-align:right}}
 .m .n{{font-family:Consolas,monospace;font-size:12px;color:#9a957f;text-align:center}}
 .m .c{{font-size:12.5px;color:#bdb8a4}}
 a{{color:#d9b24c}}
 footer{{margin-top:34px;border-top:1px solid rgba(255,255,255,.1);padding-top:12px;font-family:Consolas,monospace;font-size:10.5px;color:#9a957f}}
</style></head><body><div class="wrap">
<div class="eyebrow">12 Stones Global &middot; Kilo Aupuni &middot; the vendor side of the money</div>
<h1>Maui County Contract Awards</h1>
<p class="lead">Every public Notice of Award to a Maui County jurisdiction, from the State's
Hawai&#699;i Awards &amp; Notices Data System (HANDS). This is the <b>vendor side</b> of the money map &mdash;
who the county pays. Cross-referenced against campaign donors in the money&times;votes patterns.</p>
<div class="kpi">
 <div><div class="n">{total_awards}</div><div class="l">Maui award notices</div></div>
 <div><div class="n">{len(vendors)}</div><div class="l">distinct vendors</div></div>
 <div><div class="n">${usd(total_dollars)}</div><div class="l">total awarded</div></div>
</div>
<div class="disc">Public award notices (HANDS). Receiving a county contract is lawful and normal &mdash;
this is the map of who is paid, so it can be set beside who funds the officials. Not an allegation.</div>
<div class="hd"><span style="text-align:right">awarded</span><span style="text-align:center">#</span><span>vendor &middot; department</span></div>
{rows}
<footer>generated {g} &middot; hands-awards v1 &middot; source: HANDS (hands.ehawaii.gov) award notices &middot; govOS &middot; aloha in action</footer>
</div></body></html>"""

def main():
    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    try:
        rows, total = pull_all()
    except Exception as e:
        dispatch("FINDING", f"hands-awards pull failed: {e}")
        return 1
    maui = [r for r in rows if is_maui(r)]
    vendors = build_vendors(maui)
    total_dollars = sum(v["total"] for v in vendors)
    out = {"generated": now_hst().isoformat(), "source": "HANDS hands.ehawaii.gov",
           "statewide_total": total, "maui_awards": len(maui),
           "maui_vendors": len(vendors), "maui_dollars": round(total_dollars, 2),
           "vendors": vendors}
    json.dump(out, open(OUT_JSON, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    with open(OUT_HTML, "w", encoding="utf-8") as f:
        f.write(build_page(vendors, len(maui), total_dollars))
    dispatch("SHIPPED", f"hands-awards: {len(maui)} Maui award notices, {len(vendors)} vendors, "
             f"${total_dollars:,.0f} from HANDS public record -> reports/mauios/maui_contract_awards.html")
    return 0

if __name__ == "__main__":
    sys.exit(main())
