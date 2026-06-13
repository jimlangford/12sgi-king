#!/usr/bin/env python3
# council_watch.py — 12 Stones Maui County Council agenda watcher (v2)
#
# Modes:
#   (no args)                 daily watch: events -7d..+21d, new agendas only
#   --backfill START END      one-time corpus build, e.g. 2026-01-01 2026-07-31
#                             (monthly windows, polite 1.5s pacing)
#   --digest                  rebuild the Financial Motivations digest only
#
# Every run ends by regenerating the digest from reports/council/index.jsonl,
# so momentum accrues automatically: per-meeting 12 Stones lens reports +
# one rolling "Financial Motivations — Maui County 2026" page that aggregates
# dollar mentions, lens activity by month and by body, and the FY2027 arc.
#
# Stdlib-only network (urllib). No subprocesses -> no console popups, ever.
import json, os, re, ssl, sys, time, urllib.request
from datetime import datetime, timedelta, timezone

HOME      = os.path.expanduser("~")
TOOL_DIR  = os.path.dirname(os.path.abspath(__file__))
PROJECT   = os.path.join(HOME, "Documents", "Claude", "Projects", "Video System elementLOTUS")
REPORTS   = os.path.join(PROJECT, "reports", "council")
INDEX_F   = os.path.join(REPORTS, "index.jsonl")
DIGEST_F  = os.path.join(REPORTS, "Financial Motivations — Maui County 2026.html")
DISPATCH  = os.path.join(PROJECT, ".dispatch_log.jsonl")
STATE_F   = os.path.join(TOOL_DIR, "state.json")
API       = "https://mauicounty.api.civicclerk.com/v1"
PORTAL    = "https://mauicounty.portal.civicclerk.com"
UA        = {"User-Agent": "12sgi-council-watch/2.0 (civic transparency; mauicounty resident tooling)"}
HST       = timezone(timedelta(hours=-10))

LENSES = [
    ("Art.X · Budget",        ["budget", "appropriation", "bill 55", "bill 56", "real property tax",
                               "fiscal year 2027", "general fund", "bond"]),
    ("Title 19 · Land use",   ["zoning", "title 19", "land use", "community plan", "district boundary",
                               "special use permit", "subdivision"]),
    ("Water · Kane/Kanaloa",  ["water supply", "water authority", "stream", "watershed", "wells",
                               "irrigation", "water rights"]),
    ("Housing · Hale",        ["affordable housing", "201h", "housing project", "rental", "houseless",
                               "homeless", "safe parking"]),
    ("Recovery · Lahaina",    ["lahaina", "wildfire", "disaster recovery", "burn", "rebuild", "fema"]),
    ("ʻĀina · Agriculture",   ["agriculture", "ag park", "farm", "feral animal", "invasive"]),
    ("Charter · Governance",  ["charter amendment", "county manager", "charter commission", "ordinance amending"]),
]
FY27_ORDINANCE = re.compile(r"fiscal year 2027 budget", re.I)
ITEM_RE   = re.compile(r"^\s{0,8}((?:CC|CR|BFED|HHC|WAI|DRT|ADEPT|GREAT|PSLU|EACP)[- ]?\d{2}-\d+|[A-Z]{2,6}-\d+|\d+\.\s+[A-Z].{8,})", re.M)
DOLLAR_RE = re.compile(r"\$\s?[\d][\d,]*(?:\.\d+)?(?:\s?(?:million|billion))?", re.I)

def now_hst(): return datetime.now(HST)

def http_json(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60, context=ssl.create_default_context()) as r:
        return json.loads(r.read().decode("utf-8", "replace"))

def http_bytes(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=120, context=ssl.create_default_context()) as r:
        return r.read()

def dispatch(tag, msg):
    line = {"ts": int(time.time()), "iso": now_hst().strftime("%Y-%m-%d %H:%M:%S"),
            "source": "council-watch", "event": f"{tag}: {msg}"}
    os.makedirs(os.path.dirname(DISPATCH), exist_ok=True)
    with open(DISPATCH, "a", encoding="utf-8") as f:
        f.write(json.dumps(line, ensure_ascii=False) + "\n")

def load_state():
    try:
        with open(STATE_F, encoding="utf-8") as f: return json.load(f)
    except Exception:
        return {"seen_files": {}, "fy27_ordinance_flagged": False, "last_error": ""}

def save_state(st):
    with open(STATE_F, "w", encoding="utf-8") as f: json.dump(st, f, indent=1)

def fetch_events(a_iso, b_iso):
    q = (f"{API}/Events?$filter=startDateTime+ge+{a_iso}+and+startDateTime+le+{b_iso}"
         f"&$orderby=startDateTime+asc&$top=200")
    data = http_json(q)
    return data.get("value", data if isinstance(data, list) else [])

def agenda_files(ev):
    out = []
    for f in (ev.get("publishedFiles") or []):
        ftype = (f.get("type") or f.get("fileType") or "").lower()
        fid = f.get("fileId") or f.get("id")
        if fid and ("agenda" in ftype or "packet" in ftype):
            out.append((int(fid), f.get("name") or ftype or "agenda"))
    return out

def fetch_file_text(fid):
    try:
        raw = http_bytes(f"{API}/Meetings/GetMeetingFileStream(fileId={fid},plainText=true)")
        txt = raw.decode("utf-8", "replace")
        if len(txt.strip()) > 200 and "%PDF" not in txt[:8]:
            return txt
    except Exception:
        pass
    raw = http_bytes(f"{API}/Meetings/GetMeetingFileStream(fileId={fid},plainText=false)")
    try:
        import pypdf, io
        rd = pypdf.PdfReader(io.BytesIO(raw))
        return "\n".join((p.extract_text() or "") for p in rd.pages)
    except Exception as e:
        raise RuntimeError(f"file {fid}: no plain text and pypdf unavailable/failed ({e}); "
                           f"fix: pip install pypdf") from e

def analyze(text):
    low = text.lower()
    hits = []
    for lens, kws in LENSES:
        found = sorted({k for k in kws if k in low})
        if found: hits.append((lens, found))
    items = [m.group(1).strip()[:160] for m in ITEM_RE.finditer(text)][:60]
    dollars = []                      # (amount_text, context line) — money trail
    for m in DOLLAR_RE.finditer(text):
        s = max(0, m.start() - 90); e = min(len(text), m.end() + 90)
        ctx = re.sub(r"\s+", " ", text[s:e]).strip()
        dollars.append({"amt": m.group(0), "ctx": ctx[:200]})
        if len(dollars) >= 40: break
    return hits, items, dollars

def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def dollars_to_float(amt):
    t = amt.lower().replace("$", "").replace(",", "").strip()
    mult = 1_000_000 if "million" in t else 1_000_000_000 if "billion" in t else 1
    try: return float(re.sub(r"[a-z\s]", "", t)) * mult
    except Exception: return 0.0

def report_html(ev, fname, hits, items, dollars, agenda_url):
    name = esc(ev.get("eventName") or "Council meeting")
    when = esc((ev.get("startDateTime") or "")[:16].replace("T", " · "))
    lens_html = "".join(
        f'<div class="lens"><div class="l">{esc(l)}</div><div class="k">{esc(" · ".join(kws))}</div></div>'
        for l, kws in hits) or '<div class="lens"><div class="l">No 12 Stones lens hits</div><div class="k">informational meeting — archived for the record</div></div>'
    items_html = "".join(f"<li>{esc(i)}</li>" for i in items) or "<li>(item extraction found no matter lines — read the source agenda)</li>"
    money_html = "".join(
        f'<div class="m"><span class="a">{esc(d["amt"])}</span><span class="c">{esc(d["ctx"])}</span></div>'
        for d in dollars[:18]) or '<div class="m"><span class="c">no dollar figures in this agenda</span></div>'
    g = now_hst().strftime("%Y-%m-%d %H:%M HST")
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>12 Stones report — {name}</title>
<style>
 body{{margin:0;background:#0c100e;color:#e8e4d8;font-family:Georgia,'Iowan Old Style',serif;line-height:1.55}}
 .wrap{{max-width:880px;margin:0 auto;padding:34px 24px 60px}}
 .eyebrow{{font-family:Consolas,monospace;font-size:11px;letter-spacing:1.2px;color:#d9b24c;text-transform:uppercase}}
 h1{{font-size:26px;font-weight:600;margin:8px 0 2px}}
 .when{{font-family:Consolas,monospace;font-size:12px;color:#9a957f}}
 .sect{{font-family:Consolas,monospace;font-size:11px;letter-spacing:1px;color:#d9b24c;text-transform:uppercase;
        border-bottom:1px solid rgba(217,178,76,.25);padding-bottom:6px;margin:30px 0 12px}}
 .lens{{border:1px solid rgba(217,178,76,.3);border-radius:10px;padding:10px 14px;margin-bottom:8px;background:rgba(217,178,76,.05)}}
 .lens .l{{font-weight:600;font-size:15px}}
 .lens .k{{font-family:Consolas,monospace;font-size:11px;color:#9a957f;margin-top:3px}}
 .m{{display:flex;gap:12px;align-items:baseline;border-bottom:1px solid rgba(255,255,255,.06);padding:7px 0}}
 .m .a{{font-family:Consolas,monospace;font-size:13px;color:#d9b24c;white-space:nowrap;min-width:110px}}
 .m .c{{font-size:12.5px;color:#bdb8a4}}
 ul{{padding-left:20px;font-size:13.5px}} li{{margin-bottom:5px}}
 a{{color:#d9b24c}}
 footer{{margin-top:40px;border-top:1px solid rgba(255,255,255,.1);padding-top:12px;
        font-family:Consolas,monospace;font-size:10.5px;color:#9a957f;letter-spacing:.4px}}
</style></head><body><div class="wrap">
<div class="eyebrow">12 Stones Global · council watch · {esc(fname)}</div>
<h1>{name}</h1>
<div class="when">{when} · <a href="{esc(agenda_url)}">source agenda</a></div>
<div class="sect">12 Stones lenses</div>
{lens_html}
<div class="sect">Money trail — dollar figures in this agenda</div>
{money_html}
<div class="sect">Agenda matters detected</div>
<ul>{items_html}</ul>
<footer>generated {g} · council-watch v2 · MauiOS · aloha in action</footer>
</div></body></html>"""

# ---------------- digest: Financial Motivations — Maui County 2026 ----------------
def read_index():
    rows = []
    try:
        with open(INDEX_F, encoding="utf-8") as f:
            for ln in f:
                ln = ln.strip()
                if ln:
                    try: rows.append(json.loads(ln))
                    except Exception: pass
    except FileNotFoundError:
        pass
    return rows

def body_of(name):
    n = (name or "").lower()
    if "budget" in n or "bfed" in n: return "Budget/Finance/Econ Dev"
    if "council" in n and "committee" not in n: return "Full Council"
    if "land use" in n or "planning" in n: return "Planning & Land Use"
    if "water" in n: return "Water"
    if "housing" in n: return "Housing"
    if "disaster" in n or "recovery" in n: return "Recovery"
    if "agriculture" in n or "environment" in n or "transportation" in n: return "Ag/Env/Transport"
    if "government" in n or "relations" in n or "ethics" in n: return "Gov Relations/Ethics"
    return "Other committees"

def build_digest():
    rows = sorted(read_index(), key=lambda r: r.get("date", ""))
    if not rows: return False
    months = {}; bodies = {}; lens_tot = {}; big = []
    for r in rows:
        mo = (r.get("date") or "")[:7]
        months.setdefault(mo, {"meetings": 0, "lenses": {}})
        months[mo]["meetings"] += 1
        for l in r.get("lenses", []):
            months[mo]["lenses"][l] = months[mo]["lenses"].get(l, 0) + 1
            lens_tot[l] = lens_tot.get(l, 0) + 1
        b = body_of(r.get("event"))
        bodies.setdefault(b, {"meetings": 0, "dollar_lines": 0})
        bodies[b]["meetings"] += 1
        bodies[b]["dollar_lines"] += len(r.get("dollars", []))
        for d in r.get("dollars", []):
            v = dollars_to_float(d["amt"])
            if v >= 1_000_000:
                big.append({"v": v, "amt": d["amt"], "ctx": d["ctx"],
                            "date": r.get("date"), "event": r.get("event")})
    big.sort(key=lambda x: -x["v"]); big = big[:30]
    max_l = max(lens_tot.values()) if lens_tot else 1

    def bar(n, mx, color="rgba(217,178,76,.75)"):
        w = max(2, round(n / mx * 100))
        return (f'<span style="display:block;height:12px;border-radius:4px;width:{w}%;'
                f'background:linear-gradient(90deg,{color},rgba(217,178,76,.3))"></span>')

    lens_rows = "".join(
        f'<div class="lr"><span class="ln">{esc(l)}</span><span class="tr">{bar(n, max_l)}</span>'
        f'<span class="ct">{n}</span></div>'
        for l, n in sorted(lens_tot.items(), key=lambda kv: -kv[1]))
    mo_rows = ""
    for mo in sorted(months):
        m = months[mo]
        top = sorted(m["lenses"].items(), key=lambda kv: -kv[1])[:3]
        toptxt = " · ".join(f"{l.split(' · ')[1] if ' · ' in l else l} ×{n}" for l, n in top) or "—"
        mo_rows += (f'<div class="mr"><span class="mo">{esc(mo)}</span>'
                    f'<span class="mm">{m["meetings"]} meetings</span>'
                    f'<span class="mt">{esc(toptxt)}</span></div>')
    body_rows = "".join(
        f'<div class="mr"><span class="mo">{esc(b)}</span><span class="mm">{v["meetings"]} meetings</span>'
        f'<span class="mt">{v["dollar_lines"]} dollar lines</span></div>'
        for b, v in sorted(bodies.items(), key=lambda kv: -kv[1]["dollar_lines"]))
    big_rows = "".join(
        f'<div class="m"><span class="a">{esc(x["amt"])}</span>'
        f'<span class="c"><b>{esc(x["date"])} · {esc(x["event"])}</b> — {esc(x["ctx"])}</span></div>'
        for x in big)
    g = now_hst().strftime("%Y-%m-%d %H:%M HST")
    html = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Financial Motivations — Maui County 2026 · 12 Stones</title>
<style>
 body{{margin:0;background:#0c100e;color:#e8e4d8;font-family:Georgia,'Iowan Old Style',serif;line-height:1.55}}
 .wrap{{max-width:960px;margin:0 auto;padding:34px 24px 60px}}
 .eyebrow{{font-family:Consolas,monospace;font-size:11px;letter-spacing:1.2px;color:#d9b24c;text-transform:uppercase}}
 h1{{font-size:28px;font-weight:600;margin:8px 0 2px}}
 .when{{font-family:Consolas,monospace;font-size:12px;color:#9a957f}}
 .sect{{font-family:Consolas,monospace;font-size:11px;letter-spacing:1px;color:#d9b24c;text-transform:uppercase;
        border-bottom:1px solid rgba(217,178,76,.25);padding-bottom:6px;margin:30px 0 12px}}
 .arc p{{font-size:14px;color:#bdb8a4;max-width:78ch;margin:6px 0}}
 .lr{{display:grid;grid-template-columns:220px 1fr 44px;gap:12px;align-items:center;padding:6px 0}}
 .ln{{font-size:13.5px;font-weight:600}} .tr{{}} .ct{{font-family:Consolas,monospace;font-size:12px;color:#d9b24c;text-align:right}}
 .mr{{display:grid;grid-template-columns:220px 130px 1fr;gap:12px;align-items:baseline;
      border-bottom:1px solid rgba(255,255,255,.06);padding:7px 0}}
 .mo{{font-family:Consolas,monospace;font-size:12.5px;color:#d9b24c}}
 .mm{{font-family:Consolas,monospace;font-size:11.5px;color:#9a957f}}
 .mt{{font-size:12.5px;color:#bdb8a4}}
 .m{{display:flex;gap:12px;align-items:baseline;border-bottom:1px solid rgba(255,255,255,.06);padding:7px 0}}
 .m .a{{font-family:Consolas,monospace;font-size:13px;color:#d9b24c;white-space:nowrap;min-width:120px}}
 .m .c{{font-size:12.5px;color:#bdb8a4}} .m .c b{{color:#e8e4d8;font-weight:600}}
 footer{{margin-top:40px;border-top:1px solid rgba(255,255,255,.1);padding-top:12px;
        font-family:Consolas,monospace;font-size:10.5px;color:#9a957f;letter-spacing:.4px}}
</style></head><body><div class="wrap">
<div class="eyebrow">12 Stones Global · council watch · rolling digest</div>
<h1>Financial Motivations — Maui County 2026</h1>
<div class="when">computed from {len(rows)} ingested agendas · regenerates on every watch run</div>
<div class="sect">The FY2027 arc (context, fixed)</div>
<div class="arc">
<p>March: Mayor proposes $1.245B operating + $371.1M CIP. April: district budget sessions
(Makawao, Pāʻia, Hāna, Molokaʻi, Kīhei…). May: committee markup. June 5: Council passes
Bills 55–56 unanimously — $1.6B total, $351M CIP, an $8.4M trim that shifted weight from
capital to operations: housing, social services, disaster recovery. Effective July 1 on signature.
Everything below is what the agendas themselves say, aggregated.</p>
</div>
<div class="sect">Lens activity — what the county keeps touching</div>
{lens_rows}
<div class="sect">Month by month</div>
{mo_rows}
<div class="sect">Where the money talk happens</div>
{body_rows}
<div class="sect">Largest dollar figures on any agenda (top {len(big)})</div>
{big_rows}
<footer>generated {g} · council-watch v2 digest · sources: CivicClerk agenda texts · MauiOS · aloha in action</footer>
</div></body></html>"""
    with open(DIGEST_F, "w", encoding="utf-8") as f:
        f.write(html)
    return True

# ---------------- ingest ----------------
def ingest_window(st, a_iso, b_iso, pace=0.0):
    new_reports, fy27_hit = [], None
    events = fetch_events(a_iso, b_iso)
    for ev in events:
        eid = ev.get("id")
        date = (ev.get("startDateTime") or "")[:10]
        for fid, fname in agenda_files(ev):
            key = str(fid)
            if key in st["seen_files"]: continue
            agenda_url = f"{PORTAL}/event/{eid}/files/agenda/{fid}"
            try:
                if pace: time.sleep(pace)
                text = fetch_file_text(fid)
            except Exception as e:
                dispatch("FINDING", f"council-watch could not read agenda file {fid} "
                                    f"({ev.get('eventName','?')} {date}): {e}")
                st["seen_files"][key] = "error"; continue
            hits, items, dollars = analyze(text)
            safe = re.sub(r"[^A-Za-z0-9 _-]", "", ev.get("eventName") or "meeting")[:60].strip()
            out = os.path.join(REPORTS, f"{date} {safe} (file {fid}).html")
            with open(out, "w", encoding="utf-8") as f:
                f.write(report_html(ev, fname, hits, items, dollars, agenda_url))
            with open(INDEX_F, "a", encoding="utf-8") as f:
                f.write(json.dumps({"date": date, "event": ev.get("eventName"), "fid": fid,
                                    "lenses": [l for l, _ in hits], "items": len(items),
                                    "dollars": dollars, "url": agenda_url,
                                    "report": os.path.basename(out)}, ensure_ascii=False) + "\n")
            st["seen_files"][key] = date
            new_reports.append(f"{date} {safe} [{len(hits)} lens hits]")
            if (not st.get("fy27_ordinance_flagged")) and FY27_ORDINANCE.search(text) \
               and re.search(r"ordinance|second and final|cd1|fd1", text, re.I):
                fy27_hit = agenda_url
    return new_reports, fy27_hit

def main():
    st = load_state()
    os.makedirs(REPORTS, exist_ok=True)
    args = sys.argv[1:]
    try:
        if args[:1] == ["--digest"]:
            ok = build_digest()
            dispatch("SHIPPED" if ok else "FINDING",
                     "council-watch digest " + ("rebuilt" if ok else "skipped — no ingested agendas yet"))
            return 0
        if args[:1] == ["--backfill"] and len(args) == 3:
            a = datetime.fromisoformat(args[1]); b = datetime.fromisoformat(args[2])
            allnew, fy27 = [], None
            cur = a
            while cur < b:                      # monthly windows, polite pacing
                nxt = min(b, (cur.replace(day=1) + timedelta(days=32)).replace(day=1))
                n, f = ingest_window(st, cur.strftime("%Y-%m-%dT00:00:00Z"),
                                         nxt.strftime("%Y-%m-%dT00:00:00Z"), pace=1.5)
                allnew += n; fy27 = fy27 or f
                save_state(st); cur = nxt
            build_digest()
            dispatch("SHIPPED", f"council-watch BACKFILL {args[1]}..{args[2]} complete: "
                     f"{len(allnew)} agendas ingested -> reports/council/ + Financial Motivations digest rebuilt.")
            if fy27 and not st.get("fy27_ordinance_flagged"):
                st["fy27_ordinance_flagged"] = True
                dispatch("FINDING", "FY2027 BUDGET ORDINANCE TEXT detected during backfill — " + fy27 +
                         " — re-parse department appropriations to the penny on the Budget Transparency page.")
            save_state(st)
            return 0
        # daily watch
        a = (now_hst() - timedelta(days=7)).strftime("%Y-%m-%dT00:00:00Z")
        b = (now_hst() + timedelta(days=21)).strftime("%Y-%m-%dT00:00:00Z")
        new_reports, fy27_hit = ingest_window(st, a, b)
        if st.get("last_error"): st["last_error"] = ""
        if new_reports:
            build_digest()
            dispatch("SHIPPED", "council-watch report(s) generated in reports/council/: "
                     + "; ".join(new_reports) + " · digest refreshed")
        if fy27_hit:
            st["fy27_ordinance_flagged"] = True
            dispatch("FINDING", "FY2027 BUDGET ORDINANCE TEXT detected on a council agenda — "
                     f"{fy27_hit} — re-parse department appropriations to the penny and replace "
                     "the FY2026 baseline ledger on the Budget Transparency page.")
        save_state(st)
        return 0
    except Exception as e:
        msg = f"council-watch run failed: {e}"
        if st.get("last_error") != msg:
            dispatch("FINDING", msg)
            st["last_error"] = msg; save_state(st)
        return 1

if __name__ == "__main__":
    sys.exit(main())
