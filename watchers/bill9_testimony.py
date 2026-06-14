#!/usr/bin/env python3
# bill9_testimony.py - Kilo Aupuni: Bill 9 (STR phase-out) testimony scanner.
#
# WHAT IT HONESTLY IS: a bounded scanner over the public Bill 9 hearing packets that
# (a) finds the meetings where Bill 9 was heard, (b) flags testimony from the
# real-estate / realtor / vacation-rental industry, and (c) pulls VERBATIM any language
# about prices, commissions, competition, or collusion - each with its source link.
#
# WHAT IT IS NOT: it does not conclude that anyone "conspired" or broke licensing law.
# Bill 9 is the short-term-rental phase-out; the real-estate industry lobbied against it,
# which is lawful. IF the public record contains genuine antitrust / licensing signals,
# this surfaces them as REFERABLE items for the bodies that can actually act:
#   - Hawaii Dept. of the Attorney General (antitrust)
#   - DCCA / Regulated Industries Complaints Office (RICO) + the Real Estate Commission
#   - (federal) the NAR commission-antitrust matter is separate from Bill 9.
#
# Stdlib + pypdf. Bounded page reads so giant packets don't hang. No popups.
import io, json, os, re, ssl, sys, time, urllib.request
from datetime import datetime, timedelta, timezone

HOME      = os.path.expanduser("~")
TOOL_DIR  = os.path.dirname(os.path.abspath(__file__))
PROJECT   = os.path.join(HOME, "Documents", "Claude", "Projects", "Video System elementLOTUS")
OUT_DIR   = os.path.join(PROJECT, "reports", "mauios", "bill9")
REPORT_F  = os.path.join(OUT_DIR, "bill9_testimony_scan.html")
INDEX_F   = os.path.join(OUT_DIR, "bill9_index.jsonl")
DISPATCH  = os.path.join(PROJECT, ".dispatch_log.jsonl")
STATE_F   = os.path.join(TOOL_DIR, "bill9_state.json")
API       = "https://mauicounty.api.civicclerk.com/v1"
PORTAL    = "https://mauicounty.portal.civicclerk.com"
UA        = {"User-Agent": "12sgi-kilo-aupuni/1.0 (civic transparency; mauicounty resident tooling)"}
HST       = timezone(timedelta(hours=-10))
MAX_PAGES = 220   # bound per packet so a giant testimony PDF cannot hang the run

INDUSTRY_KW = ["realtor", "realtors association", "ram ", "real estate", "realty", "brokerage",
               "broker", "vacation rental", "short-term rental", "short term rental", "property management",
               "rentals association", "rboaa", "hawaii association of realtors", "nar ", "mls",
               "coldwell", "keller williams", "sotheby", "compass real", "hawaii life", "remax", "re/max"]
PRICE_KW = re.compile(r"(price[- ]?fix\w*|fix\w* (?:the )?price|collud\w+|conspir\w+|anti[- ]?competitive|"
                      r"restrain\w* (?:of )?trade|commission rate|inflat\w+ (?:the )?price|drive up (?:the )?price|"
                      r"raise (?:the )?price|cartel|antitrust|sherman act|licens\w+ (?:violation|agreement|board))", re.I)
BILL9_RE = re.compile(r"\bBill\s+9\b", re.I)

def now_hst(): return datetime.now(HST)

def http_json(url):
    return json.loads(urllib.request.urlopen(urllib.request.Request(url, headers=UA),
                      timeout=60, context=ssl.create_default_context()).read().decode("utf-8", "replace"))

def http_bytes(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA),
                                  timeout=180, context=ssl.create_default_context()).read()

def dispatch(tag, msg):
    line = {"ts": int(time.time()), "iso": now_hst().strftime("%Y-%m-%d %H:%M:%S"),
            "source": "kilo-aupuni", "event": f"{tag}: {msg}"}
    try:
        with open(DISPATCH, "a", encoding="utf-8") as f:
            f.write(json.dumps(line, ensure_ascii=False) + "\n")
    except Exception:
        pass

def esc(s): return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def file_text(fid, max_pages=MAX_PAGES):
    raw = http_bytes(f"{API}/Meetings/GetMeetingFileStream(fileId={fid},plainText=true)")
    txt = raw.decode("utf-8", "replace")
    if len(txt.strip()) > 200 and "%PDF" not in txt[:8]:
        return txt
    raw = http_bytes(f"{API}/Meetings/GetMeetingFileStream(fileId={fid},plainText=false)")
    import pypdf
    rd = pypdf.PdfReader(io.BytesIO(raw))
    n = min(len(rd.pages), max_pages)
    return "\n".join((rd.pages[i].extract_text() or "") for i in range(n)), len(rd.pages), n

def scan_packet(txt):
    industry = []  # (org/keyword, verbatim line)
    low = txt.lower()
    for kw in INDUSTRY_KW:
        idx = 0
        while True:
            j = low.find(kw, idx)
            if j < 0: break
            s = max(0, j - 90); e = min(len(txt), j + 130)
            industry.append({"kw": kw.strip(), "ctx": re.sub(r"\s+", " ", txt[s:e]).strip()[:240]})
            idx = j + len(kw)
            if len(industry) >= 60: break
        if len(industry) >= 60: break
    price = []
    for m in PRICE_KW.finditer(txt):
        s = max(0, m.start() - 160); e = min(len(txt), m.end() + 160)
        price.append({"hit": m.group(0), "ctx": re.sub(r"\s+", " ", txt[s:e]).strip()[:340]})
        if len(price) >= 40: break
    # dedupe industry by context
    seen = set(); ind2 = []
    for it in industry:
        k = it["ctx"][:80]
        if k in seen: continue
        seen.add(k); ind2.append(it)
    return ind2[:40], price

def build_report(events):
    blocks = ""
    for ev in events:
        ind, price = ev["industry"], ev["price"]
        price_html = "".join(
            f'<div class="pr"><div class="hit">{esc(p["hit"])}</div><div class="ctx">&hellip;{esc(p["ctx"])}&hellip;</div></div>'
            for p in price) or '<div class="pr"><div class="ctx" style="color:#9a957f">no price/competition/collusion language found in the scanned pages</div></div>'
        ind_html = "".join(
            f'<div class="m"><span class="a">{esc(i["kw"])}</span><span class="c">&hellip;{esc(i["ctx"])}&hellip;</span></div>'
            for i in ind) or '<div class="m"><span class="c">no real-estate-industry testimony flagged in scanned pages</span></div>'
        blocks += (f'<div class="ev"><h2>{esc(ev["name"])} &mdash; {esc(ev["date"])}</h2>'
                   f'<div class="when"><a href="{esc(ev["url"])}">source packet</a> &middot; scanned {ev["scanned"]}/{ev["pages"]} pages</div>'
                   f'<div class="sect">Pricing / competition / collusion language (verbatim)</div>{price_html}'
                   f'<div class="sect">Real-estate-industry testimony flagged</div>{ind_html}</div>')
    g = now_hst().strftime("%Y-%m-%d %H:%M HST")
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Bill 9 Testimony Scan - 12 Stones</title>
<style>
 body{{margin:0;background:#0c100e;color:#e8e4d8;font-family:Georgia,'Iowan Old Style',serif;line-height:1.55}}
 .wrap{{max-width:920px;margin:0 auto;padding:34px 24px 60px}}
 .eyebrow{{font-family:Consolas,monospace;font-size:11px;letter-spacing:1.2px;color:#d9b24c;text-transform:uppercase}}
 h1{{font-size:26px;font-weight:600;margin:8px 0 2px}} h2{{font-size:18px;margin:0}}
 .lead{{font-size:13.5px;color:#bdb8a4;max-width:82ch}}
 .disc{{font-size:12px;color:#9a957f;font-style:italic;border-left:2px solid rgba(224,106,74,.5);padding:8px 12px;margin:14px 0;background:rgba(224,106,74,.05)}}
 .ev{{border:1px solid rgba(255,255,255,.1);border-radius:12px;padding:14px 16px;margin:14px 0;background:rgba(255,255,255,.02)}}
 .when{{font-family:Consolas,monospace;font-size:11px;color:#9a957f;margin:3px 0 6px}}
 .sect{{font-family:Consolas,monospace;font-size:11px;letter-spacing:1px;color:#d9b24c;text-transform:uppercase;
        border-bottom:1px solid rgba(217,178,76,.25);padding-bottom:5px;margin:18px 0 10px}}
 .pr{{border-left:2px solid #e06a4a;padding:5px 0 5px 12px;margin-bottom:8px}}
 .pr .hit{{font-family:Consolas,monospace;font-size:12px;color:#e06a4a;font-weight:700}}
 .pr .ctx{{font-size:13px;color:#e8e4d8}}
 .m{{display:flex;gap:12px;align-items:baseline;border-bottom:1px solid rgba(255,255,255,.06);padding:5px 0}}
 .m .a{{font-family:Consolas,monospace;font-size:11.5px;color:#d9b24c;white-space:nowrap;min-width:150px}}
 .m .c{{font-size:12px;color:#bdb8a4}}
 a{{color:#d9b24c}}
 footer{{margin-top:40px;border-top:1px solid rgba(255,255,255,.1);padding-top:12px;
        font-family:Consolas,monospace;font-size:10.5px;color:#9a957f;letter-spacing:.4px}}
</style></head><body><div class="wrap">
<div class="eyebrow">12 Stones Global · Kilo Aupuni · Bill 9 testimony scan</div>
<h1>Bill 9 (STR phase-out) — Testimony Scan</h1>
<p class="lead">A bounded scan of the public Bill 9 hearing packets, flagging real-estate-industry
testimony and any verbatim language about prices, commissions, competition, or collusion.</p>
<div class="disc"><b>Read this first.</b> Bill 9 is the short-term-rental phase-out. The real-estate
industry lobbying against it is lawful. The excerpts below are RAW, machine-flagged, and may be quoted
out of context — they are leads to verify against the source packet, not findings. This tool does not
conclude that any person or firm conspired or violated licensing. If a genuine antitrust or licensing
signal is here, it is <b>referable</b> to: the Hawaii Attorney General (antitrust), DCCA/RICO + the Real
Estate Commission (licensing). Verify before asserting anything about anyone.</div>
{blocks or '<p class="lead">No Bill 9 hearing packets matched in the scanned window.</p>'}
<footer>generated {g} · bill9-testimony v1 · sources: CivicClerk packets · raw leads, not conclusions · govOS</footer>
</div></body></html>"""

def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    try:
        st = {}
        if os.path.exists(STATE_F):
            try: st = json.load(open(STATE_F, encoding="utf-8"))
            except Exception: st = {}
        seen = st.get("seen", {})
        args = sys.argv[1:]
        if len(args) == 2:
            a_iso = args[0] + "T00:00:00Z"; b_iso = args[1] + "T00:00:00Z"
        else:
            a_iso = "2025-09-01T00:00:00Z"; b_iso = "2026-02-28T00:00:00Z"
        evs = http_json(f"{API}/Events?$filter=startDateTime+ge+{a_iso}+and+startDateTime+le+{b_iso}"
                        f"&$orderby=startDateTime+desc&$top=200").get("value", [])
        out_events = []
        for ev in evs:
            date = (ev.get("startDateTime") or "")[:10]
            pkt = [f for f in (ev.get("publishedFiles") or []) if (f.get("type") or "") in ("Agenda Packet", "Agenda")]
            # cheap gate: does the agenda mention Bill 9?
            agenda = next((f for f in pkt if (f.get("type") == "Agenda")), None)
            if not agenda: continue
            try:
                a_txt = file_text(agenda.get("fileId"))
                a_txt = a_txt[0] if isinstance(a_txt, tuple) else a_txt
            except Exception:
                continue
            if not BILL9_RE.search(a_txt):
                continue
            packet = next((f for f in pkt if f.get("type") == "Agenda Packet"), agenda)
            pid = packet.get("fileId")
            if str(pid) in seen:
                continue
            url = f"{PORTAL}/event/{ev.get('id')}/files/agenda/{pid}"
            try:
                time.sleep(0.8)
                res = file_text(pid)
                txt, pages, scanned = res if isinstance(res, tuple) else (res, 1, 1)
            except Exception as e:
                dispatch("FINDING", f"bill9 packet {pid} read failed ({date}): {e}")
                seen[str(pid)] = "error"; continue
            ind, price = scan_packet(txt)
            rec = {"name": ev.get("eventName"), "date": date, "url": url, "fid": pid,
                   "pages": pages, "scanned": scanned, "industry": ind, "price": price}
            out_events.append(rec)
            with open(INDEX_F, "a", encoding="utf-8") as f:
                f.write(json.dumps({"date": date, "meeting": ev.get("eventName"), "fid": pid,
                                    "pages": pages, "scanned": scanned, "industry_hits": len(ind),
                                    "price_hits": len(price), "url": url}, ensure_ascii=False) + "\n")
            seen[str(pid)] = date
        if out_events:
            with open(REPORT_F, "w", encoding="utf-8") as f:
                f.write(build_report(out_events))
            tot_price = sum(len(e["price"]) for e in out_events)
            dispatch("SHIPPED", f"bill9-testimony scanned {len(out_events)} Bill 9 packet(s); "
                     f"{tot_price} pricing/competition language hit(s) flagged (raw leads) "
                     f"-> reports/mauios/bill9/bill9_testimony_scan.html")
        st["seen"] = seen
        json.dump(st, open(STATE_F, "w", encoding="utf-8"), indent=1)
        return 0
    except Exception as e:
        dispatch("FINDING", f"bill9-testimony run failed: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
