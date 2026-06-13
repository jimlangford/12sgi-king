#!/usr/bin/env python3
# votes_watch.py - Kilo Aupuni watcher #4: council VOTES + recusals, follow-the-money.
#
# Ingests Maui County meeting MINUTES (CivicClerk, PDF -> pypdf), and extracts the
# accountability facts that hold up:
#   - RECUSALS  ("CM <name> Recused")  -> a member formally declaring a conflict of
#                interest on a specific item. The strongest, cleanest signal.
#   - MOTIONS / VOTES (carried/failed, vote totals, members recorded) linked to the
#                item/bill and the dollar figures in or near it.
#   - per-official SCORECARDS: participation, recusals (with the money item + source),
#                items chaired/championed.
#
# INTEGRITY STANDARD (enforced in the output): facts + source links only. Conflicts and
# correlations are presented as QUESTIONS for further reporting, never as accusations of
# corruption. Every datum links to the source minutes PDF so a human can verify.
#
# Stdlib + pypdf. No subprocesses -> no console popups, ever.
import io, json, os, re, ssl, sys, time, urllib.request
from datetime import datetime, timedelta, timezone

HOME      = os.path.expanduser("~")
TOOL_DIR  = os.path.dirname(os.path.abspath(__file__))
PROJECT   = os.path.join(HOME, "Documents", "Claude", "Projects", "Video System elementLOTUS")
OUT_DIR   = os.path.join(PROJECT, "reports", "mauios", "votes")
INDEX_F   = os.path.join(PROJECT, "reports", "mauios", "votes_index.jsonl")
OFFICIALS_F = os.path.join(PROJECT, "reports", "mauios", "officials.json")
SCORECARD_F = os.path.join(PROJECT, "reports", "mauios", "officials_scorecard.html")
COUNCIL_INDEX = os.path.join(PROJECT, "reports", "council", "index.jsonl")
DISPATCH  = os.path.join(PROJECT, ".dispatch_log.jsonl")
STATE_F   = os.path.join(TOOL_DIR, "votes_state.json")
API       = "https://mauicounty.api.civicclerk.com/v1"
PORTAL    = "https://mauicounty.portal.civicclerk.com"
UA        = {"User-Agent": "12sgi-kilo-aupuni/1.0 (civic transparency; mauicounty resident tooling)"}
HST       = timezone(timedelta(hours=-10))

# Verified current Maui County Council roster (9 members) + the mayor. Attribution is
# restricted to this roster so the scorecard stays factual (no prose false-positives).
# Source: mauicounty.us/councilmembers/ (verified 2026-06-11).
ROSTER = {
    "Batangan": "Kauanoe Batangan - Kahului",
    "Cook": "Tom Cook - South Maui",
    "Johnson": "Gabe Johnson - Lanai",
    "Lee": "Alice L. Lee - Council Chair, Wailuku",
    "Paltin": "Tamara Paltin - West Maui",
    "Rawlins-Fernandez": "Keani Rawlins-Fernandez - Molokai",
    "Sinenci": "Shane Sinenci - East Maui",
    "Sugimura": "Yuki Lei Sugimura - Council Vice-Chair, BFED Chair; 2026 mayoral candidate",
    "Uu-Hodgins": "Nohelani Uʻu-Hodgins",
    "Bissen": "Richard Bissen - Mayor (executive; budget proposer/vetoes), former judge; 2026 incumbent",
}
# people of interest get highlighted (still facts-only)
WATCH_OFFICIALS = {
    "Sugimura": ROSTER["Sugimura"], "Lee": ROSTER["Lee"], "Bissen": ROSTER["Bissen"],
}

def canon(name):
    """Map a raw captured surname to a canonical roster key, or None if not a known official."""
    n = (name or "").strip().replace("ʻ", "").replace("‘", "").replace("'", "")
    low = n.lower()
    if low.startswith("rawlins"): return "Rawlins-Fernandez"
    if low.startswith("uu") or low.startswith("u-hodgins") or "hodgins" in low: return "Uu-Hodgins"
    for k in ROSTER:
        kk = k.replace("-", "").replace("ʻ", "").lower()
        if low == kk or low == k.lower(): return k
    return None
RECUSE_RE = re.compile(r"(?:CM|Council ?member|Chair|Vice[- ]?Chair|Member|Mayor)\s+([A-Z][A-Za-zʻ‘'\-ūō]+)\s+Recused", re.I)
MEMBER_RE = re.compile(r"(?:CM|Council ?member|Chair|Vice[- ]?Chair|Pres(?:ider)?|Member)\s+([A-Z][A-Za-zʻ‘'\-ūō]+)")
ITEM_RE   = re.compile(r"(Bill\s+No\.?\s*\d+|Bill\s+\d+|Resolution\s+No\.?\s*\d+|CC\s?\d{2}-\d+|County Communication\s+No\.?\s*[\d-]+|Committee Report\s+No\.?\s*[\d-]+)", re.I)
DOLLAR_RE = re.compile(r"\$\s?[\d][\d,]*(?:\.\d+)?(?:\s?(?:million|billion))?", re.I)
CARRIED_RE= re.compile(r"\b(carried|adopted|passed|unanimous|FAILED|defeated)\b", re.I)

def now_hst(): return datetime.now(HST)

def http_json(url):
    return json.loads(urllib.request.urlopen(urllib.request.Request(url, headers=UA),
                      timeout=60, context=ssl.create_default_context()).read().decode("utf-8", "replace"))

def http_bytes(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA),
                                  timeout=120, context=ssl.create_default_context()).read()

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

def minutes_text(fid):
    raw = http_bytes(f"{API}/Meetings/GetMeetingFileStream(fileId={fid},plainText=true)")
    txt = raw.decode("utf-8", "replace")
    if len(txt.strip()) > 200 and "%PDF" not in txt[:8]:
        return txt
    raw = http_bytes(f"{API}/Meetings/GetMeetingFileStream(fileId={fid},plainText=false)")
    import pypdf
    rd = pypdf.PdfReader(io.BytesIO(raw))
    return "\n".join((p.extract_text() or "") for p in rd.pages)

def money_for_meeting(date):
    """Pull dollar context from the matching agenda (council-watch index) for the same date."""
    out = []
    try:
        with open(COUNCIL_INDEX, encoding="utf-8") as f:
            for ln in f:
                try: r = json.loads(ln)
                except Exception: continue
                if r.get("date") == date:
                    out += [d.get("amt") for d in r.get("dollars", [])][:8]
    except FileNotFoundError:
        pass
    return out

SURNAME_TOKENS = {  # roster key -> regex token that identifies the member in minutes text
    "Batangan": r"Batangan", "Cook": r"\bCook\b", "Johnson": r"Johnson",
    "Lee": r"\bLee\b", "Paltin": r"Paltin", "Rawlins-Fernandez": r"Fernandez",
    "Sinenci": r"Sinenci", "Sugimura": r"Sugimura", "Uu-Hodgins": r"Hodgins",
}

def roster_present(txt):
    return sorted({k for k, tok in SURNAME_TOKENS.items() if re.search(tok, txt)})

# --- roll-call vote parser (real Maui minutes format) -------------------------
# Minutes record each motion as a flattened 2-column table that pypdf renders as:
#   "CM Cook √   VC Sugimura √ ... Chair Lee √   Maker Sugimura  Seconder Lee
#    TOTAL VOTES 9 MOTION PASSED".  A name followed by √/✓ = AYE; "Recused"/"Excused"
#   /"No" after the name set those states.  Each motion block ends at "TOTAL VOTES n
#   MOTION <result>".  We anchor on that and read the preceding window as the roll call.
VOTE_MARK    = re.compile(r"[√✓✔]")   # √ ✓ ✔
MOTION_ANCHOR= re.compile(r"TOTAL\s+VOTES\s+(\d+)\s+MOTION\s+([A-Z][A-Za-z]+)", re.I)
MAKER_RE     = re.compile(r"Maker\s+([A-Z][A-Za-zʻ'\-ūō]+)")
SECOND_RE    = re.compile(r"Seconder\s+([A-Z][A-Za-zʻ'\-ūō]+)")
MOTIONTXT_RE = re.compile(r"Motion\s+(ADOPT|AMEND|DEFER|FILE|PASS|RECEIVE|REFER|POSTPONE|APPROVE|RECONSIDER|TABLE|WAIVE)[^\n]{0,70}", re.I)

def _member_vote(block, tok):
    m = re.search(tok, block)
    if not m: return None
    tail = block[m.end(): m.end()+18]
    if re.match(r"[\s:]*Recus", tail, re.I):  return "RECUSED"
    if re.match(r"[\s:]*(Excus|Absent)", tail, re.I): return "EXCUSED"
    if VOTE_MARK.search(tail[:7]):            return "AYE"
    if re.match(r"[\s:]*No\b", tail):         return "NO"
    return None   # present but mark unclear -> do NOT guess (integrity)

def motions_in(txt):
    out = []
    for am in MOTION_ANCHOR.finditer(txt):
        win = txt[max(0, am.start()-850): am.end()]
        votes = {k: v for k, tok in SURNAME_TOKENS.items() if (v := _member_vote(win, tok))}
        if not votes: continue
        mk = MAKER_RE.search(win); sc = SECOND_RE.search(win); mt = MOTIONTXT_RE.search(win)
        it = ITEM_RE.search(txt[am.start(): am.start()+260]) or ITEM_RE.search(win[-500:])
        out.append({"result": am.group(2).upper(), "total": int(am.group(1)),
                    "maker": (canon(mk.group(1)) if mk else None),
                    "seconder": (canon(sc.group(1)) if sc else None),
                    "motion": (re.sub(r"\s+", " ", mt.group(0)).strip()[:90] if mt else None),
                    "item": (re.sub(r"\s+", " ", it.group(1)).strip() if it else None),
                    "votes": votes})
    return out

def analyze(txt, date):
    recusals = sorted({c for m in RECUSE_RE.finditer(txt) if (c := canon(m.group(1)))})
    members  = roster_present(txt)
    items    = sorted({re.sub(r"\s+", " ", m.group(1)).strip() for m in ITEM_RE.finditer(txt)})[:40]
    # recusal -> nearby item/dollar context (the conflict question)
    recusal_ctx = []
    for m in RECUSE_RE.finditer(txt):
        name = canon(m.group(1))
        if not name: continue
        s = max(0, m.start() - 400); e = min(len(txt), m.end() + 200)
        win = txt[s:e]
        near_item = ITEM_RE.search(win)
        near_dollar = DOLLAR_RE.findall(win)
        recusal_ctx.append({"member": name,
                            "item": (re.sub(r"\s+", " ", near_item.group(1)).strip() if near_item else None),
                            "dollars": near_dollar[:4],
                            "snippet": re.sub(r"\s+", " ", win).strip()[:300]})
    outcomes = {"carried": len(re.findall(r"\b(carried|adopted|passed|unanimous)\b", txt, re.I)),
                "failed":  len(re.findall(r"\b(FAILED|defeated)\b", txt))}
    motions = motions_in(txt)
    agenda_money = money_for_meeting(date)
    return {"recusals": recusals, "recusal_ctx": recusal_ctx, "members": members,
            "items": items, "outcomes": outcomes, "agenda_money": agenda_money, "motions": motions}

def report_html(ev, a, url):
    name = esc(ev.get("eventName") or "Meeting")
    when = esc((ev.get("startDateTime") or "")[:16].replace("T", " · "))
    rec_html = "".join(
        f'<div class="rec"><div class="who">{esc(r["member"])} &mdash; RECUSED</div>'
        f'<div class="q">Conflict question: why did {esc(r["member"])} recuse on '
        f'{esc(r["item"] or "this item")}{(" ($ " + esc(", ".join(r["dollars"])) + ")") if r["dollars"] else ""}? '
        f'What relationship triggered it?</div>'
        f'<div class="sn">{esc(r["snippet"])}</div></div>'
        for r in a["recusal_ctx"]) or '<div class="rec"><div class="q">No recusals recorded in these minutes.</div></div>'
    items_html = "".join(f"<li>{esc(i)}</li>" for i in a["items"]) or "<li>(no item numbers parsed — read source)</li>"
    money_html = " · ".join(esc(x) for x in a["agenda_money"]) or "no agenda dollars on record for this date"
    def vsumm(mo):
        ayes = [m for m, v in mo["votes"].items() if v == "AYE"]
        nos  = [m for m, v in mo["votes"].items() if v == "NO"]
        recs = [m for m, v in mo["votes"].items() if v == "RECUSED"]
        parts = [f'{len(ayes)} aye']
        if nos:  parts.append('<b style="color:#e06a4a">' + ", ".join(esc(n) for n in nos) + " NO</b>")
        if recs: parts.append('<b style="color:#e06a4a">' + ", ".join(esc(r) for r in recs) + " RECUSED</b>")
        return " · ".join(parts)
    motions_html = "".join(
        f'<div class="rec"><div class="who">{esc(mo["item"] or mo["motion"] or "Motion")} &mdash; {esc(mo["result"])}</div>'
        f'<div class="q">{vsumm(mo)}{(" · maker " + esc(mo["maker"])) if mo["maker"] else ""}'
        f'{(" · 2nd " + esc(mo["seconder"])) if mo["seconder"] else ""}</div></div>'
        for mo in a["motions"]) or '<div class="rec"><div class="q">No roll-call motions parsed in these minutes.</div></div>'
    g = now_hst().strftime("%Y-%m-%d %H:%M HST")
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>12 Stones votes report - {name}</title>
<style>
 body{{margin:0;background:#0c100e;color:#e8e4d8;font-family:Georgia,'Iowan Old Style',serif;line-height:1.55}}
 .wrap{{max-width:880px;margin:0 auto;padding:34px 24px 60px}}
 .eyebrow{{font-family:Consolas,monospace;font-size:11px;letter-spacing:1.2px;color:#d9b24c;text-transform:uppercase}}
 h1{{font-size:24px;font-weight:600;margin:8px 0 2px}}
 .when{{font-family:Consolas,monospace;font-size:12px;color:#9a957f}}
 .sect{{font-family:Consolas,monospace;font-size:11px;letter-spacing:1px;color:#d9b24c;text-transform:uppercase;
        border-bottom:1px solid rgba(217,178,76,.25);padding-bottom:6px;margin:28px 0 12px}}
 .rec{{border:1px solid rgba(224,106,74,.45);border-radius:10px;padding:11px 14px;margin-bottom:9px;background:rgba(224,106,74,.06)}}
 .rec .who{{font-family:Consolas,monospace;font-weight:700;color:#e06a4a;font-size:13px}}
 .rec .q{{font-size:13.5px;margin:5px 0;color:#e8e4d8}}
 .rec .sn{{font-family:Consolas,monospace;font-size:10.5px;color:#9a957f}}
 ul{{padding-left:20px;font-size:13px;color:#bdb8a4}} li{{margin-bottom:4px}}
 .note{{font-size:12px;color:#9a957f;font-style:italic}}
 a{{color:#d9b24c}}
 footer{{margin-top:40px;border-top:1px solid rgba(255,255,255,.1);padding-top:12px;
        font-family:Consolas,monospace;font-size:10.5px;color:#9a957f;letter-spacing:.4px}}
</style></head><body><div class="wrap">
<div class="eyebrow">12 Stones Global · Kilo Aupuni · votes & recusals · follow the money</div>
<h1>{name}</h1>
<div class="when">{when} · <a href="{esc(url)}">source minutes</a></div>
<div class="sect">Recusals — formal conflict-of-interest declarations</div>
{rec_html}
<div class="sect">Money on this date's agenda</div>
<div class="note">{money_html}</div>
<div class="sect">Motions &amp; roll-call votes ({len(a["motions"])})</div>
{motions_html}
<div class="sect">Members recorded · {len(a["members"])}</div>
<div class="note">{esc(", ".join(a["members"]))}</div>
<div class="sect">Items / bills / resolutions</div>
<ul>{items_html}</ul>
<footer>generated {g} · votes-watch v1 · facts + source link; conflicts are questions, not conclusions · MauiOS</footer>
</div></body></html>"""

def council_committee_events(a_iso, b_iso):
    q = (f"{API}/Events?$filter=startDateTime+ge+{a_iso}+and+startDateTime+le+{b_iso}"
         f"&$orderby=startDateTime+desc&$top=200")
    return http_json(q).get("value", [])

def _blank():
    return {"meetings": 0, "ayes": 0, "noes": 0, "recused": 0, "excused": 0,
            "total_votes": 0, "vote_log": [], "recusals": []}

def _norm(o):
    """Ensure an official dict has every current key (older officials.json may lack the vote fields)."""
    for k, v in _blank().items():
        o.setdefault(k, v if not isinstance(v, list) else list(v))
    return o

def update_officials(a, ev, url, off):
    date = (ev.get("startDateTime") or "")[:10]
    for mem in a["members"]:
        _norm(off.setdefault(mem, _blank()))["meetings"] += 1
    for mo in a["motions"]:
        for mem, v in mo["votes"].items():
            o = _norm(off.setdefault(mem, _blank()))
            if   v == "AYE":     o["ayes"] += 1; o["total_votes"] += 1
            elif v == "NO":      o["noes"] += 1; o["total_votes"] += 1
            elif v == "RECUSED": o["recused"] += 1
            elif v == "EXCUSED": o["excused"] += 1
            # log the consequential votes: anything on a named bill/item, or a NO/RECUSED
            if mo["item"] or v in ("NO", "RECUSED"):
                o["vote_log"].append({"date": date, "item": mo["item"], "motion": mo["motion"],
                                      "vote": v, "result": mo["result"], "url": url})
    for r in a["recusal_ctx"]:
        o = _norm(off.setdefault(r["member"], _blank()))
        o["recusals"].append({"date": date, "meeting": ev.get("eventName"),
                              "item": r["item"], "dollars": r["dollars"], "url": url})
    # keep file sane: cap vote_log to the most recent 80 per official
    for o in off.values():
        if isinstance(o.get("vote_log"), list) and len(o["vote_log"]) > 80:
            o["vote_log"] = o["vote_log"][-80:]

def build_scorecard(off):
    rows = sorted(off.items(), key=lambda kv: (-len(kv[1]["recusals"]), -kv[1]["meetings"]))
    cards = ""
    for name, o in rows:
        role = ROSTER.get(name)
        watch = name in WATCH_OFFICIALS
        rec = o.get("recusals", [])
        ay, no, rc, ex, tv = o.get("ayes",0), o.get("noes",0), o.get("recused",0), o.get("excused",0), o.get("total_votes",0)
        rec_html = "".join(
            f'<div class="rr"><span class="rd">{esc(r["date"])}</span>'
            f'<span class="ri">{esc(r["item"] or "item n/a")}{(" · $" + esc(", ".join(r["dollars"]))) if r["dollars"] else ""}</span>'
            f'<span class="rl"><a href="{esc(r["url"])}">minutes</a></span></div>'
            for r in rec) or '<div class="rr"><span class="ri" style="color:#9a957f">no recusals recorded</span></div>'
        # notable votes on named bills/items + every NO/RECUSED
        vl = [v for v in o.get("vote_log", []) if v.get("item") or v.get("vote") in ("NO","RECUSED")][-14:]
        vlog = "".join(
            f'<div class="rr"><span class="rd">{esc(v["date"])}</span>'
            f'<span class="ri"><b style="color:{"#e06a4a" if v["vote"] in ("NO","RECUSED") else "#6abf86"}">{esc(v["vote"])}</b> '
            f'on {esc(v["item"] or v["motion"] or "motion")} &middot; {esc(v["result"])}</span>'
            f'<span class="rl"><a href="{esc(v["url"])}">minutes</a></span></div>'
            for v in vl) or '<div class="rr"><span class="ri" style="color:#9a957f">no itemized votes parsed yet</span></div>'
        flag = f'<div class="qq">Conflict questions: each recusal means {esc(name)} had a financial/relational interest in that item. Map each to campaign donors, business ties, and contract beneficiaries.</div>' if rec else ""
        cards += (f'<div class="card{" watch" if watch else ""}">'
                  f'<div class="nm">{esc(role or name)}{" ★" if watch else ""}</div>'
                  + f'<div class="stat">{o.get("meetings",0)} meetings · {tv} recorded votes ({ay} aye / {no} no) · {rc} recused · {ex} excused</div>'
                  + '<div class="role">Recusals (conflict trail):</div>' + rec_html
                  + '<div class="role">Notable votes (bills + every No/Recuse):</div>' + vlog
                  + flag + '</div>')
    g = now_hst().strftime("%Y-%m-%d %H:%M HST")
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Officials Scorecard - Follow the Money - 12 Stones</title>
<style>
 body{{margin:0;background:#0c100e;color:#e8e4d8;font-family:Georgia,'Iowan Old Style',serif;line-height:1.55}}
 .wrap{{max-width:940px;margin:0 auto;padding:34px 24px 60px}}
 .eyebrow{{font-family:Consolas,monospace;font-size:11px;letter-spacing:1.2px;color:#d9b24c;text-transform:uppercase}}
 h1{{font-size:27px;font-weight:600;margin:8px 0 2px}}
 .lead{{font-size:13.5px;color:#bdb8a4;max-width:80ch}}
 .disc{{font-size:12px;color:#9a957f;font-style:italic;border-left:2px solid rgba(217,178,76,.4);padding:6px 12px;margin:14px 0}}
 .card{{border:1px solid rgba(255,255,255,.1);border-radius:12px;padding:14px 16px;margin:12px 0;background:rgba(255,255,255,.02)}}
 .card.watch{{border-color:rgba(217,178,76,.5);background:rgba(217,178,76,.05)}}
 .nm{{font-size:17px;font-weight:600}} .role{{font-family:Consolas,monospace;font-size:11px;color:#d9b24c;margin:2px 0 6px}}
 .stat{{font-family:Consolas,monospace;font-size:11.5px;color:#9a957f;margin-bottom:8px}}
 .rr{{display:grid;grid-template-columns:90px 1fr 70px;gap:10px;align-items:baseline;border-bottom:1px solid rgba(255,255,255,.06);padding:5px 0;font-size:12.5px}}
 .rd{{font-family:Consolas,monospace;color:#e06a4a}} .ri{{color:#e8e4d8}} .rl{{text-align:right;font-family:Consolas,monospace;font-size:11px}}
 .qq{{font-size:12.5px;color:#e8d9a8;margin-top:8px;background:rgba(224,106,74,.07);border-radius:8px;padding:8px 11px}}
 a{{color:#d9b24c}}
 footer{{margin-top:40px;border-top:1px solid rgba(255,255,255,.1);padding-top:12px;
        font-family:Consolas,monospace;font-size:10.5px;color:#9a957f;letter-spacing:.4px}}
</style></head><body><div class="wrap">
<div class="eyebrow">12 Stones Global · Kilo Aupuni · officials scorecard · follow the money</div>
<h1>Maui County Officials — Votes, Recusals &amp; the Money</h1>
<p class="lead">Built only from public meeting minutes. Recusals are formal conflict-of-interest
declarations — the cleanest paper trail of where an official has a financial or relational stake.</p>
<div class="disc">These are <b>documented facts and open questions</b>, not findings of wrongdoing.
A recusal is lawful and proper — it is also a roadmap of where to look. Every line links to the
source minutes. Verify before you assert anything about any person.</div>
{cards}
<footer>generated {g} · votes-watch v1 · sources: CivicClerk minutes · MauiOS · aloha in action</footer>
</div></body></html>"""

def main():
    st = load_state()
    os.makedirs(OUT_DIR, exist_ok=True)
    try:
        args = sys.argv[1:]
        backfill = args[:1] == ["--backfill"] and len(args) == 3
        if backfill:
            # authoritative rebuild: fresh officials, reprocess the whole window
            off = {}; st["seen"] = {}
            a_iso = args[1] + "T00:00:00Z"; b_iso = args[2] + "T00:00:00Z"
        else:
            off = {}
            if os.path.exists(OFFICIALS_F):
                try: off = json.load(open(OFFICIALS_F, encoding="utf-8"))
                except Exception: off = {}
            a_iso = (now_hst() - timedelta(days=45)).strftime("%Y-%m-%dT00:00:00Z")
            b_iso = (now_hst() + timedelta(days=1)).strftime("%Y-%m-%dT00:00:00Z")
        events = council_committee_events(a_iso, b_iso)
        new = []
        for ev in events:
            mins = [f for f in (ev.get("publishedFiles") or []) if (f.get("type") or "").lower() == "minutes"]
            for mf in mins:
                fid = mf.get("fileId") or mf.get("id")
                key = str(fid)
                if not fid or key in st["seen"]:
                    continue
                date = (ev.get("startDateTime") or "")[:10]
                url = f"{PORTAL}/event/{ev.get('id')}/files/minutes/{fid}"
                try:
                    time.sleep(0.8)
                    txt = minutes_text(fid)
                except Exception as e:
                    dispatch("FINDING", f"votes-watch could not read minutes {fid} ({ev.get('eventName','?')} {date}): {e}")
                    st["seen"][key] = "error"; continue
                a = analyze(txt, date)
                safe = re.sub(r"[^A-Za-z0-9 _-]", "", ev.get("eventName") or "meeting")[:55].strip()
                out = os.path.join(OUT_DIR, f"{date} {safe} (min {fid}).html")
                with open(out, "w", encoding="utf-8") as f:
                    f.write(report_html(ev, a, url))
                with open(INDEX_F, "a", encoding="utf-8") as f:
                    f.write(json.dumps({"date": date, "meeting": ev.get("eventName"), "fid": fid,
                                        "recusals": a["recusals"], "members": len(a["members"]),
                                        "motions": len(a["motions"]),
                                        "items": a["items"][:20], "outcomes": a["outcomes"],
                                        "agenda_money": a["agenda_money"], "url": url,
                                        "report": os.path.basename(out)}, ensure_ascii=False) + "\n")
                update_officials(a, ev, url, off)
                st["seen"][key] = date
                new.append(f"{date} {safe} [{len(a['motions'])} motions, {len(a['recusals'])} recusal(s)]")
                save_state(st)
        json.dump(off, open(OFFICIALS_F, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
        with open(SCORECARD_F, "w", encoding="utf-8") as f:
            f.write(build_scorecard(off))
        if st.get("last_error"): st["last_error"] = ""
        save_state(st)
        total_rec = sum(len(o.get("recusals", [])) for o in off.values())
        total_votes = sum(o.get("total_votes", 0) for o in off.values())
        if new:
            dispatch("SHIPPED", f"votes-watch ingested {len(new)} minutes set(s); scorecard rebuilt "
                     f"({len(off)} officials, {total_votes} roll-call votes parsed, {total_rec} recusals) "
                     f"-> reports/mauios/officials_scorecard.html")
        return 0
    except Exception as e:
        msg = f"votes-watch run failed: {e}"
        if st.get("last_error") != msg:
            dispatch("FINDING", msg); st["last_error"] = msg; save_state(st)
        return 1

if __name__ == "__main__":
    sys.exit(main())
