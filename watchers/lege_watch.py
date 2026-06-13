#!/usr/bin/env python3
# lege_watch.py - Kilo Aupuni: State Legislature votes (KEYLESS - capitol.hawaii.gov).
#
# No API key. Scrapes the Legislature's own public measure-status pages
# (measure_indiv.aspx), which are keyless and NOT bot-gated. Structured vote data
# goes back to ~2009. Vote format records the AYE COUNT + the NAMES of dissents
# ("Noes, N (Reps. X, Y)") and excused - i.e. WHO broke ranks, the accountability signal.
#
#   python lege_watch.py                         # the seeded high-relevance bills
#   python lege_watch.py --bills HB300:2025,SB1:2025
#   python lege_watch.py --scan HB 2025 1 400    # polite range scan (capped), keyless
#
# Honest limits: keyless ~2009+ (not 2000); captures aye COUNT + NO/excused NAMES
# (per-member aye roster isn't printed on these pages). Bulk enumeration of ALL bills
# needs the JS list endpoint (not cracked) - so this is seeded/targeted + extensible.
# Dissent names join to statewide_money.py donor data (votes x money at the state level).
import json, os, re, ssl, sys, time, urllib.request
from datetime import datetime, timedelta, timezone

HOME    = os.path.expanduser("~")
TOOL_DIR= os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.join(HOME, "Documents", "Claude", "Projects", "Video System elementLOTUS")
MAUIOS  = os.path.join(PROJECT, "reports", "mauios")
OUT_DIR = os.path.join(MAUIOS, "lege")
INDEX_F = os.path.join(MAUIOS, "lege_index.jsonl")
DISPATCH= os.path.join(PROJECT, ".dispatch_log.jsonl")
BASE    = "https://www.capitol.hawaii.gov/session/measure_indiv.aspx?billtype={bt}&billnumber={n}&year={y}"
UA      = {"User-Agent": "Mozilla/5.0 12sgi-kilo-aupuni/1.0 (civic transparency; resident tooling)"}
HST     = timezone(timedelta(hours=-10))

# seed: high-relevance statewide measures (housing / STR / land-water / budget).
# Edit freely; --bills/--scan extend it. (year, billtype, number)
SEED = [("HB", "300", "2025"), ("SB", "1", "2025"), ("HB", "1", "2025")]

LENSES = [
    ("Housing / Hale",      ["housing", "affordable", "ohana", "adu", "rental", "kauhale", "homeless", "201h"]),
    ("Short-term rental",   ["transient", "short-term rental", "short term rental", "vacation rental", "tvr", "transient accommodation"]),
    ("Real estate / land",  ["real estate", "real property", "land use", "zoning", "conveyance", "broker", "subdivision"]),
    ("Water / Aina",        ["water", "stream", "watershed", "agricultur", "aina", "conservation"]),
    ("Budget / Tax",        ["budget", "appropriat", "general excise", "tax", "fund", "tat", "transient accommodations tax"]),
]

def now_hst(): return datetime.now(HST)
def esc(s): return str(s).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
def dispatch(tag,msg):
    try:
        with open(DISPATCH,"a",encoding="utf-8") as f:
            f.write(json.dumps({"ts":int(time.time()),"iso":now_hst().strftime("%Y-%m-%d %H:%M:%S"),
                                "source":"kilo-aupuni","event":f"{tag}: {msg}"},ensure_ascii=False)+"\n")
    except Exception: pass

def get(u):
    return urllib.request.urlopen(urllib.request.Request(u,headers=UA),timeout=50,
                                  context=ssl.create_default_context()).read().decode("utf-8","replace")
def strip(h): return re.sub(r"\s+"," ", re.sub(r"<[^>]+>"," ", h))

NAMES_RE = re.compile(r"\(([^)]*\b(?:Rep|Sen|Representative|Senator)[^)]*)\)", re.I)
def _names(blob):
    out=[]
    for m in NAMES_RE.finditer(blob or ""):
        inner = re.sub(r"(Reps?\.|Sens?\.|Representatives?|Senators?)", "", m.group(1))
        for nm in re.split(r",|\band\b|;", inner):
            nm = re.sub(r"[^A-Za-z'\- ʻ]", "", nm).strip()
            if len(nm) >= 3 and nm.lower() != "none":   # real surname, not a fragment
                out.append(nm)
    return sorted(set(out))

def parse_measure(bt, n, y):
    html = get(BASE.format(bt=bt, n=n, y=y))
    if "Final Reading" not in html and "Introduced" not in strip(html):
        return None
    t = strip(html)
    title = ""
    mt = re.search(r"(Report Title|Measure Title)\s*:?\s*(.+?)\s*(Description|Companion|Status Text|Introducer)", t, re.I)
    if mt: title = mt.group(2).strip()[:240]
    votes=[]; seen=set()
    # find each Final Reading action and read the vote tally in the window AFTER it
    # (don't stop at periods). Chamber inferred from total: House=51 seats, Senate=25.
    for fm in re.finditer(r"Final Reading", t):
        seg = t[fm.start(): fm.start()+520]
        ay = re.search(r"Ayes?,?\s*(\d+)", seg)
        if not ay: continue
        no = re.search(r"Noes?,?\s*(\d+)\s*(\([^)]*\))?", seg)
        ex = re.search(r"Excused,?\s*(\d+)\s*(\([^)]*\))?", seg)
        ayes = int(ay.group(1)); noes = int(no.group(1)) if no else 0
        exc = int(ex.group(1)) if ex else 0
        total = ayes + noes + exc
        chamber = "House" if total >= 30 else ("Senate" if total > 0 else "?")
        sig = (chamber, ayes, noes, exc)
        if sig in seen: continue
        seen.add(sig)
        votes.append({"chamber": chamber, "ayes": ayes, "noes": noes,
                      "noes_names": _names(no.group(2) or "") if no else [],
                      "excused_names": _names(ex.group(2) or "") if ex else []})
    low = (title + " " + t[:1500]).lower()
    lenses = [L for L, kws in LENSES if any(k in low for k in kws)]
    became_act = bool(re.search(r"\bAct\s+\d+\b", t))
    return {"bill": f"{bt}{n}", "year": y, "title": title or "(title not parsed)",
            "url": BASE.format(bt=bt, n=n, y=y), "votes": votes, "lenses": lenses,
            "became_act": became_act,
            "dissenters": sorted({nm for v in votes for nm in v["noes_names"]})}

def report_html(records):
    blocks=""
    for r in records:
        vh="".join(
            f'<div class="m"><span class="a">{esc(v["chamber"])}</span>'
            f'<span class="c">Ayes {v["ayes"]} &middot; <b style="color:{"#e06a4a" if v["noes"] else "#6abf86"}">Noes {v["noes"]}</b>'
            f'{(" — " + esc(", ".join(v["noes_names"]))) if v["noes_names"] else ""}'
            f'{(" · excused: " + esc(", ".join(v["excused_names"]))) if v["excused_names"] else ""}</span></div>'
            for v in r["votes"]) or '<div class="m"><span class="c" style="color:#9a957f">no final-reading vote parsed</span></div>'
        blocks += (f'<div class="ev"><h2>{esc(r["bill"])} ({esc(r["year"])}){" · became law" if r["became_act"] else ""}</h2>'
                   f'<div class="when"><a href="{esc(r["url"])}">source</a> · lenses: {esc(", ".join(r["lenses"]) or "none")}</div>'
                   f'<div class="ti">{esc(r["title"])}</div>{vh}'
                   + (f'<div class="q">Dissenters to cross-check against donors: {esc(", ".join(r["dissenters"]))}</div>' if r["dissenters"] else "")
                   + '</div>')
    g = now_hst().strftime("%Y-%m-%d %H:%M HST")
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>State Legislature Votes - 12 Stones</title>
<style>
 body{{margin:0;background:#0c100e;color:#e8e4d8;font-family:Georgia,serif;line-height:1.5}}
 .wrap{{max-width:900px;margin:0 auto;padding:32px 22px 60px}}
 .eyebrow{{font-family:Consolas,monospace;font-size:11px;letter-spacing:1.2px;color:#d9b24c;text-transform:uppercase}}
 h1{{font-size:25px;margin:8px 0 2px}} h2{{font-size:17px;margin:0}}
 .disc{{font-size:12px;color:#9a957f;font-style:italic;border-left:2px solid rgba(217,178,76,.4);padding:6px 12px;margin:12px 0}}
 .ev{{border:1px solid rgba(255,255,255,.1);border-radius:12px;padding:13px 16px;margin:12px 0;background:rgba(255,255,255,.02)}}
 .when{{font-family:Consolas,monospace;font-size:11px;color:#9a957f;margin:3px 0}} .ti{{font-size:13px;color:#bdb8a4;margin:4px 0 8px}}
 .m{{display:flex;gap:12px;border-bottom:1px solid rgba(255,255,255,.06);padding:5px 0}} .m .a{{font-family:Consolas,monospace;font-size:12px;color:#d9b24c;min-width:70px}} .m .c{{font-size:12.5px;color:#bdb8a4}}
 .q{{font-size:12.5px;color:#e8d9a8;background:rgba(224,106,74,.07);border-radius:8px;padding:8px 11px;margin-top:8px}}
 footer{{margin-top:36px;border-top:1px solid rgba(255,255,255,.1);padding-top:12px;font-family:Consolas,monospace;font-size:10.5px;color:#9a957f}}
</style></head><body><div class="wrap">
<div class="eyebrow">12 Stones Global · Kilo Aupuni · State Legislature votes (keyless)</div>
<h1>Hawaii Legislature — Final-Reading Votes</h1>
<div class="disc">Keyless, from capitol.hawaii.gov (~2009+). Captures aye COUNT + the NAMES of dissenters /
excused (who broke ranks). Cross-check dissenters against the statewide money map. Public record; questions, not accusations.</div>
{blocks}
<footer>generated {g} · lege-watch v1 (keyless) · source: capitol.hawaii.gov measure status · MauiOS</footer>
</div></body></html>"""

def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    bills = list(SEED)
    if "--bills" in sys.argv:
        spec = sys.argv[sys.argv.index("--bills")+1]
        for b in spec.split(","):
            m = re.match(r"([A-Za-z]+)(\d+):(\d{4})", b.strip())
            if m: bills.append((m.group(1).upper(), m.group(2), m.group(3)))
    if "--scan" in sys.argv:
        i=sys.argv.index("--scan"); bt=sys.argv[i+1].upper(); y=sys.argv[i+2]
        lo=int(sys.argv[i+3]); hi=min(int(sys.argv[i+4]), lo+600)  # cap 600 polite
        bills += [(bt, str(k), y) for k in range(lo, hi+1)]
    records=[]
    bills = list(dict.fromkeys(bills))   # dedup (seed + --bills overlap)
    for bt, n, y in bills:
        try:
            time.sleep(0.5)
            r = parse_measure(bt, n, y)
        except Exception as e:
            dispatch("FINDING", f"lege-watch {bt}{n}/{y} fetch failed: {e}"); continue
        if not r or not r["votes"]:
            continue
        records.append(r)
        with open(INDEX_F,"a",encoding="utf-8") as f:
            f.write(json.dumps(r, ensure_ascii=False)+"\n")
    if records:
        with open(os.path.join(OUT_DIR,"lege_votes.html"),"w",encoding="utf-8") as f:
            f.write(report_html(records))
        diss = sum(len(r["dissenters"]) for r in records)
        dispatch("SHIPPED", f"lege-watch (keyless): {len(records)} state measures w/ final-reading votes parsed, "
                 f"{diss} dissenter-names captured -> reports/mauios/lege/lege_votes.html")
    else:
        dispatch("FINDING", "lege-watch: no final-reading votes parsed from the seed/scan this run.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
