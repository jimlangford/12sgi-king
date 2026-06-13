#!/usr/bin/env python3
# mapps_watch.py - Kilo Aupuni watcher #3: Maui County permits/planning (MAPPS).
# Source: Tyler EnerGov Self Service JSON API behind mapps2.co.maui.hi.us.
#   POST /EnerGov_Prod/SelfService/api/energov/search/search
# The working request shape (headers + body template) was captured from a live
# browser session 2026-06-11 (the SPA's own search call) and frozen into
# energov_permit_template.json. Verified replicating headlessly from Python.
# Required headers were the catch: tenantId=1, tenantName/Tyler-TenantUrl=
# MauiCountyHIProd, Tyler-Tenant-Culture=en-US; PermitType/StatusId must be "none".
#
# Stdlib only. No subprocesses -> no console popups, ever.
import json, os, re, ssl, sys, time, urllib.request
from datetime import datetime, timedelta, timezone

HOME      = os.path.expanduser("~")
TOOL_DIR  = os.path.dirname(os.path.abspath(__file__))
PROJECT   = os.path.join(HOME, "Documents", "Claude", "Projects", "Video System elementLOTUS")
OUT_DIR   = os.path.join(PROJECT, "reports", "mauios", "permits")
INDEX_F   = os.path.join(PROJECT, "reports", "mauios", "permits_index.jsonl")
DISPATCH  = os.path.join(PROJECT, ".dispatch_log.jsonl")
STATE_F   = os.path.join(TOOL_DIR, "mapps_state.json")
TMPL_F    = os.path.join(TOOL_DIR, "energov_permit_template.json")
API       = "https://mapps2.co.maui.hi.us/EnerGov_Prod/SelfService/api/energov/search/search"
HEADERS   = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/plain, */*",
    "tenantId": "1", "tenantName": "MauiCountyHIProd",
    "Tyler-TenantUrl": "MauiCountyHIProd", "Tyler-Tenant-Culture": "en-US",
    "User-Agent": "Mozilla/5.0 12sgi-kilo-aupuni/1.0 (civic transparency; mauicounty resident tooling)",
}
HST       = timezone(timedelta(hours=-10))

LENSES = [
    ("Recovery / Lahaina",   ["lahaina", "wildfire", "rebuild", "burn", "fire damage", "disaster"]),
    ("Title 19 / Land use",  ["subdivision", "grading", "grubbing", "zoning", "shoreline", "sma", "variance", "use permit"]),
    ("Housing / Hale",       ["dwelling", "ohana", "adu", "accessory dwelling", "affordable", "multi-family", "apartment"]),
    ("Water / Kane-Kanaloa", ["water", "wastewater", "cesspool", "septic", "drywell", "well", "injection"]),
    ("Aina / Agriculture",   ["agricultural", "farm", "ag ", "solar", "photovoltaic", "grading"]),
    ("Commercial / Build",   ["commercial", "retail", "hotel", "resort", "tvr", "transient", "demolition", "new construction"]),
]

def now_hst(): return datetime.now(HST)

def http_post_json(url, body):
    req = urllib.request.Request(url, data=body.encode("utf-8"), headers=HEADERS, method="POST")
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

def load_state():
    try:
        with open(STATE_F, encoding="utf-8") as f: return json.load(f)
    except Exception:
        return {"seen": {}, "last_error": ""}

def save_state(st):
    with open(STATE_F, "w", encoding="utf-8") as f: json.dump(st, f, indent=1)

def esc(s): return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def build_body(date_from, date_to, page, size=50):
    tmpl = open(TMPL_F, encoding="utf-8").read()
    return (tmpl.replace('"__FROM__"', json.dumps(date_from))
                .replace('"__TO__"', json.dumps(date_to))
                .replace('"__PN__"', str(page))
                .replace('"__PS__"', str(size)))

def analyze(rec):
    blob = " ".join(str(rec.get(k, "")) for k in
                    ("CaseType", "CaseWorkclass", "Description", "ProjectName", "Address", "AddressDisplay")).lower()
    hits = [(lens, sorted({k.strip() for k in kws if k in blob})) for lens, kws in LENSES]
    return [(l, f) for l, f in hits if f]

def report_html(rec, hits):
    num = esc(rec.get("CaseNumber") or "permit")
    fields = [("Type", rec.get("CaseType")), ("Work class", rec.get("CaseWorkclass")),
              ("Status", rec.get("CaseStatus")), ("Project", rec.get("ProjectName")),
              ("Applied", rec.get("ApplyDate")), ("Issued", rec.get("IssueDate")),
              ("Address", rec.get("AddressDisplay") or rec.get("Address")),
              ("Parcel (TMK)", rec.get("MainParcel"))]
    fld = "".join(f'<div class="m"><span class="a">{esc(k)}</span><span class="c">{esc(v)}</span></div>'
                  for k, v in fields if v)
    lens_html = "".join(
        f'<div class="lens"><div class="l">{esc(l)}</div><div class="k">{esc(" / ".join(f))}</div></div>'
        for l, f in hits) or '<div class="lens"><div class="l">No 12 Stones lens hits</div></div>'
    g = now_hst().strftime("%Y-%m-%d %H:%M HST")
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>12 Stones permit report - {num}</title>
<style>
 body{{margin:0;background:#0c100e;color:#e8e4d8;font-family:Georgia,'Iowan Old Style',serif;line-height:1.55}}
 .wrap{{max-width:840px;margin:0 auto;padding:34px 24px 60px}}
 .eyebrow{{font-family:Consolas,monospace;font-size:11px;letter-spacing:1.2px;color:#d9b24c;text-transform:uppercase}}
 h1{{font-size:23px;font-weight:600;margin:8px 0 2px}}
 .sect{{font-family:Consolas,monospace;font-size:11px;letter-spacing:1px;color:#d9b24c;text-transform:uppercase;
        border-bottom:1px solid rgba(217,178,76,.25);padding-bottom:6px;margin:28px 0 12px}}
 .lens{{border:1px solid rgba(217,178,76,.3);border-radius:10px;padding:10px 14px;margin-bottom:8px;background:rgba(217,178,76,.05)}}
 .lens .l{{font-weight:600;font-size:15px}} .lens .k{{font-family:Consolas,monospace;font-size:11px;color:#9a957f;margin-top:3px}}
 .m{{display:flex;gap:12px;align-items:baseline;border-bottom:1px solid rgba(255,255,255,.06);padding:7px 0}}
 .m .a{{font-family:Consolas,monospace;font-size:12.5px;color:#d9b24c;white-space:nowrap;min-width:130px}}
 .m .c{{font-size:12.5px;color:#bdb8a4}}
 footer{{margin-top:40px;border-top:1px solid rgba(255,255,255,.1);padding-top:12px;
        font-family:Consolas,monospace;font-size:10.5px;color:#9a957f;letter-spacing:.4px}}
</style></head><body><div class="wrap">
<div class="eyebrow">12 Stones Global / Kilo Aupuni / MAPPS permit watch / {num}</div>
<h1>{esc(rec.get("CaseType") or "Permit")} - {num}</h1>
<div class="sect">Record</div>
{fld}
<div class="sect">12 Stones lenses</div>
{lens_html}
<footer>generated {g} / mapps-watch v1 (EnerGov API) / Kilo Aupuni / MauiOS / aloha in action</footer>
</div></body></html>"""

def harvest_window(st, date_from, date_to, max_pages=400, page_size=50):
    new = []
    page = 1
    while page <= max_pages:
        try:
            data = http_post_json(API, build_body(date_from, date_to, page, page_size))
        except Exception as e:
            dispatch("FINDING", f"mapps-watch page {page} fetch failed: {e}")
            break
        res = (data or {}).get("Result") or {}
        ents = res.get("EntityResults") or []
        total_pages = res.get("TotalPages") or 1
        if not ents:
            break
        for rec in ents:
            num = rec.get("CaseNumber")
            if not num or num in st["seen"]:
                continue
            hits = analyze(rec)
            safe = re.sub(r"[^A-Za-z0-9 _-]", "", str(num))[:50].strip()
            out = os.path.join(OUT_DIR, f"{safe}.html")
            with open(out, "w", encoding="utf-8") as f:
                f.write(report_html(rec, hits))
            with open(INDEX_F, "a", encoding="utf-8") as f:
                f.write(json.dumps({"permit": num, "type": rec.get("CaseType"),
                                    "status": rec.get("CaseStatus"), "applied": rec.get("ApplyDate"),
                                    "address": rec.get("AddressDisplay") or rec.get("Address"),
                                    "parcel": rec.get("MainParcel"),
                                    "desc": (rec.get("Description") or "")[:200],
                                    "lenses": [l for l, _ in hits], "seen": now_hst().strftime("%Y-%m-%d"),
                                    "report": os.path.basename(out)}, ensure_ascii=False) + "\n")
            st["seen"][num] = now_hst().strftime("%Y-%m-%d")
            new.append(num)
            if len(new) % 50 == 0:
                save_state(st)
        if page >= total_pages:
            break
        page += 1
        time.sleep(0.6)  # polite pacing
    return new

def main():
    st = load_state()
    os.makedirs(OUT_DIR, exist_ok=True)
    args = sys.argv[1:]
    try:
        if args[:1] == ["--backfill"] and len(args) == 3:
            a, b = args[1], args[2]
        else:
            # default watch: applied in the last 30 days
            a = (now_hst() - timedelta(days=30)).strftime("%Y-%m-%dT10:00:00.000Z")
            b = (now_hst() + timedelta(days=1)).strftime("%Y-%m-%dT10:00:00.000Z")
        new = harvest_window(st, a, b)
        if st.get("last_error"): st["last_error"] = ""
        save_state(st)
        if new:
            dispatch("SHIPPED", f"mapps-watch ingested {len(new)} permit case(s) -> reports/mauios/permits/ "
                     f"(window {a[:10]}..{b[:10]})")
        return 0
    except Exception as e:
        msg = f"mapps-watch run failed: {e}"
        if st.get("last_error") != msg:
            dispatch("FINDING", msg); st["last_error"] = msg; save_state(st)
        return 1

if __name__ == "__main__":
    sys.exit(main())
