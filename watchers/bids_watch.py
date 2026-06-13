#!/usr/bin/env python3
# bids_watch.py - Kilo Aupuni watcher #2: Maui County procurement (Bids/RFPs).
# Source: https://www.mauicounty.gov/Bids.aspx (CivicEngage, plain HTML - verified
# parseable 2026-06-11, no API; stdlib fetch is sufficient, no Playwright needed).
#
# Follow-the-money lane: every posted bid/RFP is where budgeted dollars actually
# leave the building. New bids get a 12 Stones lens report + an index line that
# the Kilo Aupuni dashboard rolls up.
#
# Stdlib only. No subprocesses -> no console popups, ever.
import json, os, re, ssl, sys, time, urllib.request
from datetime import datetime, timedelta, timezone
from html import unescape

HOME      = os.path.expanduser("~")
TOOL_DIR  = os.path.dirname(os.path.abspath(__file__))
PROJECT   = os.path.join(HOME, "Documents", "Claude", "Projects", "Video System elementLOTUS")
OUT_DIR   = os.path.join(PROJECT, "reports", "mauios", "bids")
INDEX_F   = os.path.join(PROJECT, "reports", "mauios", "bids_index.jsonl")
DISPATCH  = os.path.join(PROJECT, ".dispatch_log.jsonl")
STATE_F   = os.path.join(TOOL_DIR, "bids_state.json")
LIST_URL  = "https://www.mauicounty.gov/Bids.aspx?showAllBids=on"
BID_URL   = "https://www.mauicounty.gov/bids.aspx?bidID={bid}"
UA        = {"User-Agent": "12sgi-kilo-aupuni/1.0 (civic transparency; mauicounty resident tooling)"}
HST       = timezone(timedelta(hours=-10))

LENSES = [
    ("Art.X / Budget",       ["appropriation", "general fund", "bond", "cip", "fiscal year"]),
    ("Title 19 / Land use",  ["zoning", "land use", "subdivision", "grading", "grubbing"]),
    ("Water / Kane-Kanaloa", ["water", "wastewater", "wwrf", "sewer", "well", "reservoir", "irrigation"]),
    ("Housing / Hale",       ["housing", "affordable", "201h", "rental", "houseless", "homeless"]),
    ("Recovery / Lahaina",   ["lahaina", "wildfire", "disaster", "rebuild", "fema", "debris"]),
    ("Aina / Agriculture",   ["agriculture", "ag park", "farm", "invasive", "landfill", "compost", "recycling"]),
    ("Infrastructure",       ["road", "highway", "bridge", "pavement", "drainage", "roofing", "facility",
                              "improvements", "construction", "renovation"]),
    ("Services / Consultants",["consultant", "professional services", "design services", "study",
                              "engineering services", "planning services"]),
]
DOLLAR_RE = re.compile(r"\$\s?[\d][\d,]*(?:\.\d+)?(?:\s?(?:million|billion))?", re.I)
TAG_RE    = re.compile(r"<[^>]+>")

def now_hst(): return datetime.now(HST)

def http_text(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60, context=ssl.create_default_context()) as r:
        return r.read().decode("utf-8", "replace")

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
        return {"seen_bids": {}, "last_error": ""}

def save_state(st):
    with open(STATE_F, "w", encoding="utf-8") as f: json.dump(st, f, indent=1)

def esc(s): return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def list_bids():
    """Return {bid_id: title} from the listing page."""
    html = http_text(LIST_URL)
    out = {}
    for m in re.finditer(r'href="bids\.aspx\?bidID=(\d+)"[^>]*>([^<]+)', html, re.I):
        bid, title = m.group(1), unescape(m.group(2)).strip()
        if title.lower().replace("\xa0", " ") in ("read on", "read more"): continue
        if bid not in out or len(title) > len(out[bid]):
            out[bid] = title
    return out

def fetch_bid(bid):
    """Fetch a bid detail page -> (plain_text, fields dict)."""
    html = http_text(BID_URL.format(bid=bid))
    core = html
    m = re.search(r"(?is)<div[^>]*class=\"[^\"]*bid[^\"]*\".*?</form>", html)
    if m: core = m.group(0)
    text = unescape(TAG_RE.sub(" ", core))
    text = re.sub(r"\s+", " ", text).strip()
    fields = {}
    for label in ("Bid Number", "Bid Title", "Category", "Status", "Publication Date",
                  "Closing Date", "Pre-bid Meeting", "Contact Person", "Department"):
        fm = re.search(re.escape(label) + r"\s*:?\s*([^|]{2,120}?)(?=  |$)", text)
        if fm: fields[label] = fm.group(1).strip()[:120]
    return text, fields

def analyze(text):
    low = text.lower()
    hits = [(lens, sorted({k for k in kws if k in low})) for lens, kws in LENSES]
    hits = [(l, f) for l, f in hits if f]
    dollars = []
    for m in DOLLAR_RE.finditer(text):
        s = max(0, m.start() - 80); e = min(len(text), m.end() + 80)
        dollars.append({"amt": m.group(0), "ctx": text[s:e].strip()[:180]})
        if len(dollars) >= 20: break
    return hits, dollars

def report_html(bid, title, fields, hits, dollars, url):
    lens_html = "".join(
        f'<div class="lens"><div class="l">{esc(l)}</div><div class="k">{esc(" / ".join(f))}</div></div>'
        for l, f in hits) or '<div class="lens"><div class="l">No 12 Stones lens hits</div></div>'
    fld_html = "".join(f'<div class="m"><span class="a">{esc(k)}</span><span class="c">{esc(v)}</span></div>'
                       for k, v in fields.items())
    money_html = "".join(
        f'<div class="m"><span class="a">{esc(d["amt"])}</span><span class="c">{esc(d["ctx"])}</span></div>'
        for d in dollars) or '<div class="m"><span class="c">no dollar figures on the posting page</span></div>'
    g = now_hst().strftime("%Y-%m-%d %H:%M HST")
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>12 Stones bid report - {esc(title)}</title>
<style>
 body{{margin:0;background:#0c100e;color:#e8e4d8;font-family:Georgia,'Iowan Old Style',serif;line-height:1.55}}
 .wrap{{max-width:880px;margin:0 auto;padding:34px 24px 60px}}
 .eyebrow{{font-family:Consolas,monospace;font-size:11px;letter-spacing:1.2px;color:#d9b24c;text-transform:uppercase}}
 h1{{font-size:24px;font-weight:600;margin:8px 0 2px}}
 .when{{font-family:Consolas,monospace;font-size:12px;color:#9a957f}}
 .sect{{font-family:Consolas,monospace;font-size:11px;letter-spacing:1px;color:#d9b24c;text-transform:uppercase;
        border-bottom:1px solid rgba(217,178,76,.25);padding-bottom:6px;margin:30px 0 12px}}
 .lens{{border:1px solid rgba(217,178,76,.3);border-radius:10px;padding:10px 14px;margin-bottom:8px;background:rgba(217,178,76,.05)}}
 .lens .l{{font-weight:600;font-size:15px}}
 .lens .k{{font-family:Consolas,monospace;font-size:11px;color:#9a957f;margin-top:3px}}
 .m{{display:flex;gap:12px;align-items:baseline;border-bottom:1px solid rgba(255,255,255,.06);padding:7px 0}}
 .m .a{{font-family:Consolas,monospace;font-size:12.5px;color:#d9b24c;white-space:nowrap;min-width:130px}}
 .m .c{{font-size:12.5px;color:#bdb8a4}}
 a{{color:#d9b24c}}
 footer{{margin-top:40px;border-top:1px solid rgba(255,255,255,.1);padding-top:12px;
        font-family:Consolas,monospace;font-size:10.5px;color:#9a957f;letter-spacing:.4px}}
</style></head><body><div class="wrap">
<div class="eyebrow">12 Stones Global / Kilo Aupuni / procurement watch / bid {esc(bid)}</div>
<h1>{esc(title)}</h1>
<div class="when"><a href="{esc(url)}">source posting</a></div>
<div class="sect">Posting details</div>
{fld_html or '<div class="m"><span class="c">details on the source page</span></div>'}
<div class="sect">12 Stones lenses</div>
{lens_html}
<div class="sect">Money trail</div>
{money_html}
<footer>generated {g} / bids-watch v1 / Kilo Aupuni / MauiOS / aloha in action</footer>
</div></body></html>"""

def main():
    st = load_state()
    os.makedirs(OUT_DIR, exist_ok=True)
    new = []
    try:
        bids = list_bids()
        for bid, title in sorted(bids.items(), key=lambda kv: -int(kv[0])):
            if bid in st["seen_bids"]: continue
            try:
                time.sleep(1.0)  # polite pacing
                text, fields = fetch_bid(bid)
            except Exception as e:
                dispatch("FINDING", f"bids-watch could not read bid {bid} ({title[:60]}): {e}")
                st["seen_bids"][bid] = "error"; continue
            hits, dollars = analyze(text)
            url = BID_URL.format(bid=bid)
            safe = re.sub(r"[^A-Za-z0-9 _-]", "", title)[:70].strip() or f"bid {bid}"
            out = os.path.join(OUT_DIR, f"bid {bid} {safe}.html")
            with open(out, "w", encoding="utf-8") as f:
                f.write(report_html(bid, title, fields, hits, dollars, url))
            with open(INDEX_F, "a", encoding="utf-8") as f:
                f.write(json.dumps({"bid": bid, "title": title, "fields": fields,
                                    "lenses": [l for l, _ in hits], "dollars": dollars,
                                    "url": url, "seen": now_hst().strftime("%Y-%m-%d"),
                                    "report": os.path.basename(out)}, ensure_ascii=False) + "\n")
            st["seen_bids"][bid] = now_hst().strftime("%Y-%m-%d")
            new.append(f"{bid}: {title[:70]}")
            if len(new) % 25 == 0:
                save_state(st)   # checkpoint: a long archive backfill survives interruption
        if st.get("last_error"): st["last_error"] = ""
        if new:
            dispatch("SHIPPED", f"bids-watch ingested {len(new)} procurement posting(s) -> reports/mauios/bids/: "
                     + "; ".join(new[:6]) + ("..." if len(new) > 6 else ""))
        save_state(st)
        return 0
    except Exception as e:
        msg = f"bids-watch run failed: {e}"
        if st.get("last_error") != msg:
            dispatch("FINDING", msg); st["last_error"] = msg; save_state(st)
        return 1

if __name__ == "__main__":
    sys.exit(main())
