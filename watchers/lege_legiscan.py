#!/usr/bin/env python3
# lege_legiscan.py - Kilo Aupuni: HI State Legislature PER-MEMBER votes via LegiScan.
#
# Uses the LegiScan API (key in config/legiscan_key.txt - a SECRET, never logged/committed).
# LegiScan session DATASETS bundle every bill + roll-call + legislator for a session in one
# download, so we get COMPLETE per-member yea/nay (what capitol.hawaii.gov flat text couldn't).
# HI coverage: 2010 -> now (24 sessions). This is the real 15-year legislative pattern layer.
#
#   python lege_legiscan.py                 # recent sessions (default)
#   python lege_legiscan.py --years 2010 2026   # full history backfill
#
# Builds a per-legislator scorecard (party, yea/nay, dissents on housing/STR/RE/water/budget
# lens bills) joinable to statewide_money.py (votes x money at the state level).
# Integrity: public record; dissents/patterns are questions, not accusations.
import base64, io, json, os, re, ssl, sys, time, urllib.request, zipfile
from datetime import datetime, timedelta, timezone

HOME    = os.path.expanduser("~")
TOOL_DIR= os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.join(HOME, "Documents", "Claude", "Projects", "Video System elementLOTUS")
MAUIOS  = os.path.join(PROJECT, "reports", "mauios")
OUT_F   = os.path.join(MAUIOS, "lege", "legislator_scorecard.html")
DATA_F  = os.path.join(MAUIOS, "lege", "legislators.json")
KEY_F   = os.path.join(PROJECT, "config", "legiscan_key.txt")
DISPATCH= os.path.join(PROJECT, ".dispatch_log.jsonl")
HST     = timezone(timedelta(hours=-10))

LENSES = [
    ("Housing", ["housing","affordable","ohana","accessory dwelling","rental","kauhale","homeless","201h","leasehold"]),
    ("Short-term rental", ["transient accommodation","short-term rental","vacation rental","transient vacation"]),
    ("Real estate / land", ["real estate","real property","land use","zoning","conveyance","condominium","subdivision"]),
    ("Water / Aina", ["water","stream","watershed","agricultur","conservation district"]),
    ("Budget / Tax", ["appropriat","state budget","general excise","income tax","transient accommodations tax","relating to taxation"]),
]

def now_hst(): return datetime.now(HST)
def esc(s): return str(s).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
def dispatch(tag,msg):
    try:
        with open(DISPATCH,"a",encoding="utf-8") as f:
            f.write(json.dumps({"ts":int(time.time()),"iso":now_hst().strftime("%Y-%m-%d %H:%M:%S"),
                                "source":"kilo-aupuni","event":f"{tag}: {msg}"},ensure_ascii=False)+"\n")
    except Exception: pass

KEY = open(KEY_F, encoding="utf-8").read().strip()
def api(op, **kw):
    u = "https://api.legiscan.com/?key=%s&op=%s" % (KEY, op) + "".join(f"&{k}={v}" for k, v in kw.items())
    return json.loads(urllib.request.urlopen(u, timeout=90, context=ssl.create_default_context()).read().decode("utf-8","replace"))

def lens_of(title):
    low = (title or "").lower()
    return [L for L, kws in LENSES if any(k in low for k in kws)]

def process_session(sess_id, access_key, year, leg):
    """Download a session dataset ZIP, tally per-member votes; mutate leg dict."""
    d = api("getDataset", id=sess_id, access_key=access_key)
    ds = d.get("dataset") or {}
    zb = ds.get("zip")
    if not zb:
        dispatch("FINDING", f"lege-legiscan: no zip for session {sess_id} ({year})"); return 0, 0
    z = zipfile.ZipFile(io.BytesIO(base64.b64decode(zb)))
    people, bills, votes = {}, {}, []
    for name in z.namelist():
        if not name.endswith(".json"): continue
        try: obj = json.loads(z.read(name).decode("utf-8","replace"))
        except Exception: continue
        if "person" in obj:
            p = obj["person"]; people[p.get("people_id")] = {"name": p.get("name"), "party": p.get("party"), "role": p.get("role")}
        elif "bill" in obj:
            b = obj["bill"]; bills[b.get("bill_id")] = {"number": b.get("bill_number"), "title": b.get("title","")}
        elif "roll_call" in obj:
            votes.append(obj["roll_call"])   # a roll call (LegiScan wraps as 'roll_call')
    nbills = 0; nvotes = 0
    for rc in votes:
        b = bills.get(rc.get("bill_id")) or {}
        lenses = lens_of(b.get("title"))
        relevant = bool(lenses)
        if relevant: nbills += 1
        for v in rc.get("votes", []):
            pid = v.get("people_id"); vt = (v.get("vote_text") or "").strip()
            person = people.get(pid)
            if not person: continue
            key = person["name"]
            o = leg.setdefault(key, {"party": person.get("party"), "role": person.get("role"),
                                     "yea": 0, "nay": 0, "other": 0, "dissents": []})
            if vt == "Yea": o["yea"] += 1
            elif vt == "Nay": o["nay"] += 1
            else: o["other"] += 1
            nvotes += 1
            if vt == "Nay" and relevant:   # the dissent signal on money/housing bills
                o["dissents"].append({"year": year, "bill": b.get("number"),
                                      "title": (b.get("title") or "")[:90], "lens": lenses})
    return nbills, nvotes

def build_scorecard(leg, sessions_done):
    rows = sorted(leg.items(), key=lambda kv: (-(kv[1]["nay"]), -(kv[1]["yea"])))
    cards = ""
    for name, o in rows:
        diss = o["dissents"][-12:]
        dh = "".join(
            f'<div class="rr"><span class="rd">{esc(str(d["year"]))}</span>'
            f'<span class="ri"><b style="color:#e06a4a">NAY</b> on {esc(d["bill"])} ({esc(", ".join(d["lens"]))}) &mdash; {esc(d["title"])}</span></div>'
            for d in diss) or '<div class="rr"><span class="ri" style="color:#9a957f">no dissents on lens bills</span></div>'
        cards += (f'<div class="card"><div class="nm">{esc(name)} <span class="role">({esc(o.get("party") or "?")}, {esc(o.get("role") or "")})</span></div>'
                  f'<div class="stat">{o["yea"]} yea · {o["nay"]} nay · {o["other"]} other · {len(o["dissents"])} dissents on housing/STR/RE/water/budget bills</div>'
                  + dh + '</div>')
    g = now_hst().strftime("%Y-%m-%d %H:%M HST")
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>HI Legislator Scorecard - 12 Stones</title>
<style>
 body{{margin:0;background:#0c100e;color:#e8e4d8;font-family:Georgia,serif;line-height:1.5}}
 .wrap{{max-width:940px;margin:0 auto;padding:32px 22px 60px}}
 .eyebrow{{font-family:Consolas,monospace;font-size:11px;letter-spacing:1.2px;color:#d9b24c;text-transform:uppercase}}
 h1{{font-size:25px;margin:8px 0 2px}}
 .disc{{font-size:12px;color:#9a957f;font-style:italic;border-left:2px solid rgba(217,178,76,.4);padding:6px 12px;margin:12px 0}}
 .card{{border:1px solid rgba(255,255,255,.1);border-radius:12px;padding:12px 15px;margin:10px 0;background:rgba(255,255,255,.02)}}
 .nm{{font-size:15px;font-weight:600}} .role{{font-family:Consolas,monospace;font-size:11px;color:#d9b24c}}
 .stat{{font-family:Consolas,monospace;font-size:11.5px;color:#9a957f;margin:4px 0 8px}}
 .rr{{display:grid;grid-template-columns:60px 1fr;gap:10px;border-bottom:1px solid rgba(255,255,255,.06);padding:4px 0;font-size:12.5px}}
 .rd{{font-family:Consolas,monospace;color:#e06a4a}} .ri{{color:#bdb8a4}}
 footer{{margin-top:36px;border-top:1px solid rgba(255,255,255,.1);padding-top:12px;font-family:Consolas,monospace;font-size:10.5px;color:#9a957f}}
</style></head><body><div class="wrap">
<div class="eyebrow">12 Stones Global · Kilo Aupuni · HI legislator scorecard</div>
<h1>Hawaii Legislators — Per-Member Votes ({esc(sessions_done)})</h1>
<div class="disc">Complete per-member roll-call votes via LegiScan. Dissents shown are NAY votes on
housing / short-term-rental / real-estate / water / budget bills — cross-check against the statewide
money map. Public record; questions, not accusations.</div>
{cards}
<footer>generated {g} · lege-legiscan v1 · source: LegiScan (HI 2010+) · per-member roll calls · govOS</footer>
</div></body></html>"""

def main():
    os.makedirs(os.path.dirname(OUT_F), exist_ok=True)
    dl = api("getDatasetList", state="HI").get("datasetlist", [])
    by_id = {d.get("session_id"): d for d in dl}
    years = (2024, 2027)
    if "--years" in sys.argv:
        i = sys.argv.index("--years"); years = (int(sys.argv[i+1]), int(sys.argv[i+2]))
    want = [d for d in dl if years[0] <= int(d.get("year_start") or d.get("year") or 0) <= years[1]]
    leg = {}; done = []
    tot_bills = tot_votes = 0
    for d in sorted(want, key=lambda x: x.get("session_id", 0)):
        sid = d.get("session_id"); ak = d.get("access_key"); yr = d.get("year_start") or d.get("year")
        if not (sid and ak): continue
        try:
            time.sleep(1.0)
            nb, nv = process_session(sid, ak, yr, leg)
            tot_bills += nb; tot_votes += nv; done.append(str(yr))
        except Exception as e:
            dispatch("FINDING", f"lege-legiscan session {sid} ({yr}) failed: {e}")
    json.dump({"asOf": now_hst().strftime("%Y-%m-%d %H:%M HST"), "sessions": done,
               "legislators": leg}, open(DATA_F, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    with open(OUT_F, "w", encoding="utf-8") as f:
        f.write(build_scorecard(leg, ", ".join(done)))
    dispatch("SHIPPED", f"lege-legiscan: {len(leg)} legislators, {tot_votes} per-member votes across sessions "
             f"{', '.join(done)} ({tot_bills} lens-relevant roll calls) -> reports/mauios/lege/legislator_scorecard.html")
    return 0

if __name__ == "__main__":
    sys.exit(main())
