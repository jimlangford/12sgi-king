#!/usr/bin/env python3
"""testimony_watch.py — extract NAMED public testifiers from Maui committee minutes, then link
them (and their organizations) to the money. The verbal-testimony → influence → money layer.

Source (the one Jimmy found): Maui County COMMITTEE minutes are full verbatim transcripts on
Legistar — https://mauicounty.legistar.com/View.ashx?M=M&ID=<id> — and they NAME testifiers, with
their stated position (support/oppose) and affiliation. (The CivicClerk council minutes that
votes_watch parses are vote-records only; these committee transcripts are the testimony record.)

Pipeline:
  1. Enumerate the year's minutes from Calendar.aspx?Mode=<year> (the View.ashx?M=M&ID= links).
  2. Parse each transcript: drop councilmembers + introduced department staff; capture turns where a
     speaker SELF-IDENTIFIES as a member of the public ("my name is …" / "I'd like to testify …"),
     with position (support/oppose) and organization ("on behalf of …", "representing …", "… LLC").
  3. Link each testifier + org to public money records (CSC donor_profiles, HANDS vendors, HSEC
     lobby orgs) — framed as a PUBLIC-RECORD QUESTION, never an accusation.

High precision over recall: only self-identified public testimony is captured (never invented); a
speaker we can't classify is skipped, not guessed. Stdlib + pypdf. Output: testimony_record.json.
"""
import os, re, ssl, io, json, urllib.request, urllib.parse, html
from datetime import datetime, timezone, timedelta
try: import pypdf
except Exception: import PyPDF2 as pypdf

HOME    = os.path.expanduser("~")
PROJECT = os.path.join(HOME, "Documents", "Claude", "Projects", "Video System elementLOTUS")
MAUIOS  = os.path.join(PROJECT, "reports", "mauios")
DONORS  = os.path.join(MAUIOS, "donor_profiles.json")
VDJ     = os.path.join(MAUIOS, "vendor_donor_join.json")
LOBBY   = os.path.join(MAUIOS, "lobby_money_watch.json")
OUT     = os.path.join(MAUIOS, "testimony_record.json")
LEG     = "https://mauicounty.legistar.com/"
HST     = timezone(timedelta(hours=-10))
UA      = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) 12sgi-kilo"}
MAXMTG  = 56   # full year's committee minutes
esc     = lambda s: html.escape(str(s or ""))
def now_hst(): return datetime.now(HST)

def get(u, raw=False, t=70):
    d = urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=t, context=ssl.create_default_context()).read()
    return d if raw else d.decode("utf-8", "replace")

def load(p, d):
    try: return json.load(open(p, encoding="utf-8"))
    except Exception: return d

# ── 1. enumerate minutes documents for a year ───────────────────────────────────────────────
def enumerate_minutes(year):
    h = get(LEG + "Calendar.aspx?Mode=%d" % year)
    seen, out = set(), []
    for mid, guid in re.findall(r'View\.ashx\?M=M&amp;ID=(\d+)&amp;GUID=([A-F0-9\-]+)', h):
        if mid in seen: continue
        seen.add(mid)
        out.append((mid, guid))
    return out

# ── 2. parse a transcript for self-identified public testifiers ─────────────────────────────
STAFF_TITLES = re.compile(r"\b(Director|Deputy|Corporation Counsel|Planning|Budget Director|"
                          r"Administrator|Officer|Department of|Staff|Clerk|Supervising|First Deputy)\b", re.I)
ORG_RE = re.compile(r"(?:on behalf of|representing|(?:here )?with the|with|from the|for the|president of|director of|executive director of|work for)\s+(?:the\s+)?"
                    r"([A-Z][A-Za-zʻ'&.\- ]{3,52}?(?:Association|Assn|Hui|Coalition|Foundation|Council|Union|"
                    r"Chamber|Alliance|Society|Partners|Partnership|Group|LLC|L\.L\.C\.|Inc|Company|Corporation|Corp|Ltd|"
                    r"Trust|Department|Realtors|Realty|Properties|Bureau|Club|Institute|Fund|Ohana|Board))")
NAME_RE = re.compile(r"[Mm]y name is\s+([A-Z][A-Za-zʻ'\-]+(?:\s+[A-Z][A-Za-zʻ'\-]+){0,2})")
# real-estate / disaster-housing affiliation — the Bill 9 (short-term rental) follow-the-money angle
REALTOR_RE = re.compile(r"\b(realtor|real estate|real-estate|broker|realty|property manager|"
                        r"vacation rental|short-term rental|transient (?:vacation|accommodation)|"
                        r"rental (?:owner|manager)|lodging|hotel|resort)\b", re.I)
BILL9_RE   = re.compile(r"\bBill\s*9\b|short-term rental|transient vacation|\bTVR\b|\bMinatoya\b|phase[- ]?out|"
                        r"\bSTR\b|vacation rental", re.I)
FEMA_RE    = re.compile(r"\bFEMA\b|disaster (?:housing|recovery)|emergency housing|displaced|wildfire (?:housing|survivors)", re.I)

def meeting_header(t):
    m = re.search(r"([A-Z][A-Z ,’'&]+COMMITTEE|COUNCIL[A-Z ]*)\s+MINUTES", t)
    body = (m.group(1).title().strip() if m else "Committee")
    d = re.search(r"\b([A-Z][a-z]+ \d{1,2}, 20\d\d)\b", t)
    return body, (d.group(1) if d else "")

def councilmember_surnames(t):
    pres = re.search(r"PRESENT:(.*?)(?:EXCUSED|STAFF|ALSO PRESENT|CONVENE|APPROVAL|$)", t, re.S)
    block = pres.group(1) if pres else ""
    sn = set()
    for full in re.findall(r"Councilmember\s+([A-Z][\wʻ.\-]+(?:\s+[A-Z][\wʻ.\-]+){0,2})", block):
        sn.add(full.split()[-1].upper().strip(".’'"))
    sn |= {"PALTIN","LEE","SUGIMURA","COOK","JOHNSON","SINENCI","BATANGAN","HODGINS",
           "RAWLINS-FERNANDEZ","KAMA","UU-HODGINS","U‘U-HODGINS"}
    return sn

def parse_testifiers(t):
    t = re.sub(r"\n\s*-\s*\d+\s*-\s*\n", " ", t)        # strip "- 4 -" page breaks
    t = re.sub(r"[ \t]+", " ", t)
    cms = councilmember_surnames(t)
    turns = re.split(r"\n([A-Z][A-Zʻ'’.\- ]{2,42}):", "\n" + t)
    # turns = ['', LABEL1, BODY1, LABEL2, BODY2, ...]
    out = []
    for i in range(1, len(turns) - 1, 2):
        label = turns[i].strip(); body = turns[i + 1].strip()
        sur = re.sub(r"^(MR|MS|MRS|DR)\.?\s+", "", label).split()[-1].upper().strip(".’'") if label else ""
        if label.startswith(("COUNCILMEMBER","CHAIR","VICE-CHAIR","PRESIDING","VICE CHAIR")): continue
        if sur in cms: continue
        low = body.lower()
        # require a SELF-IDENTIFIED public-testimony marker (high precision)
        if not ("my name is" in low or "i would like to testify" in low or "like to testify" in low
                or "i'm here to testify" in low or "i am here to testify" in low or "testifying" in low):
            continue
        if STAFF_TITLES.search(body[:120]) and "my name is" not in low:   # skip dept staff briefings
            continue
        nm = NAME_RE.search(body)
        name = (nm.group(1).strip() if nm else label.title().strip())
        pos = ("support" if re.search(r"\bin support\b|support of\b|favor of\b", low)
               else "oppose" if re.search(r"\boppos|against\b|urge .* oppose", low) else "comment")
        org = ""
        om = ORG_RE.search(body)
        if om: org = re.sub(r"\s+", " ", om.group(1)).strip(" .")
        bill = ""
        bm = re.search(r"\b(Bill No\.?\s*\d+|Bill\s+\d+|Resolution\s+\d+\-\d+|Reso\.?\s*\d+\-\d+)", body)
        if bm: bill = bm.group(1)
        out.append({"name": name, "org": org, "position": pos, "bill": bill,
                    "realtor": bool(REALTOR_RE.search(body)),
                    "bill9": bool(BILL9_RE.search(body)),
                    "fema": bool(FEMA_RE.search(body)),
                    "quote": re.sub(r"\s+", " ", body)[:240]})
    # de-dup by (name,bill,position)
    seen, dedup = set(), []
    for r in out:
        k = (r["name"].lower(), r["bill"], r["position"])
        if k in seen: continue
        seen.add(k); dedup.append(r)
    return dedup

# ── 3. link testifiers/orgs to public money ─────────────────────────────────────────────────
GEN = {"the","of","and","hawaii","hawaiʻi","maui","county","association","department","group",
       "inc","llc","ltd","co","company","corporation","council","trust"}
def toks(s): return {w for w in re.split(r"[^a-z0-9ʻ]+", (s or "").lower()) if w and w not in GEN and len(w) > 2}

def money_index():
    donors = {}
    for blk in load(DONORS, []):
        for d in blk.get("donors", []) or []:
            donors.setdefault(d.get("name","").lower(), []).append(blk.get("label","").split(" -")[0])
    vendors = [(m.get("vendor"), toks(m.get("vendor"))) for m in (load(VDJ, {}).get("matched") or [])]
    lobby = [(e.get("org"), toks(e.get("org"))) for e in (load(LOBBY, {}).get("lobby_and_donate") or [])]
    return donors, vendors, lobby

def link_money(rec, idx):
    donors, vendors, lobby = idx
    hits = []
    nm = rec["name"].lower()
    if nm in donors:
        hits.append({"kind":"donor","detail":"a donor by this name funded %s (CSC public record)" % ", ".join(sorted(set(donors[nm]))[:4])})
    target = rec["org"] or rec["name"]
    tt = toks(target)
    if tt:
        for v, vt in vendors:
            if tt & vt: hits.append({"kind":"contract","detail":"name overlaps County contract winner %s (HANDS)" % v}); break
        for o, ot in lobby:
            if tt & ot: hits.append({"kind":"lobby","detail":"name overlaps a registered lobbying org %s (HSEC)" % o}); break
    return hits

CSS = """<style>
 body{margin:0;background:#0c100e;color:#e8e4d8;font-family:Georgia,'Iowan Old Style',serif;line-height:1.6}
 .wrap{max-width:980px;margin:0 auto;padding:30px 22px 70px}
 .eyebrow{font-family:Consolas,monospace;font-size:11px;letter-spacing:1.4px;color:#d9b24c;text-transform:uppercase}
 h1{font-size:27px;font-weight:600;margin:8px 0 4px} h2{font-size:17px;margin:22px 0 6px;color:#f0ead8}
 .lead{font-size:14px;color:#cfc9b6;max-width:80ch}
 .kpis{display:flex;gap:10px;flex-wrap:wrap;margin:12px 0}
 .kpi{border:1px solid rgba(255,255,255,.1);border-radius:11px;padding:10px 14px;background:rgba(255,255,255,.02)}
 .kpv{font-family:Consolas,monospace;font-size:22px;font-weight:700;color:#d9b24c} .kpl{font-size:11px;color:#9a957f}
 .money{border:1px solid rgba(224,106,74,.35);border-radius:12px;padding:13px 16px;margin:10px 0;background:rgba(224,106,74,.06)}
 .mtg{border:1px solid rgba(255,255,255,.1);border-radius:12px;padding:12px 15px;margin:9px 0;background:rgba(255,255,255,.02)}
 .mh{display:flex;justify-content:space-between;gap:10px;align-items:baseline;flex-wrap:wrap}
 .md{font-family:Consolas,monospace;font-size:12px;color:#d9b24c} .mb{font-size:14px;font-weight:600}
 .t{font-size:13px;padding:4px 0;border-bottom:1px solid rgba(255,255,255,.06)}
 .pos{font-family:Consolas,monospace;font-size:10px;padding:1px 6px;border-radius:7px;margin-right:6px}
 .support{background:rgba(86,192,138,.16);color:#56c08a} .oppose{background:rgba(224,106,74,.16);color:#e06a4a} .comment{background:rgba(154,149,127,.16);color:#bdb8a4}
 .moneytag{color:#e9b48a;font-size:11.5px} .org{color:#9fd9bf;font-size:12px}
 .disc{font-size:12px;color:#9a957f;font-style:italic;border-left:2px solid rgba(217,178,76,.4);padding:7px 12px;margin:14px 0}
 a{color:#d9b24c} .none{font-size:13px;color:#9a957f;font-style:italic}
 footer{margin-top:30px;border-top:1px solid rgba(255,255,255,.1);padding-top:12px;font-family:Consolas,monospace;font-size:10.5px;color:#9a957f}
</style>"""

def _trow(r, url):
    org = (' <span class="org">&middot; %s</span>' % esc(r["org"])) if r["org"] else ""
    bill = (' &middot; %s' % esc(r["bill"])) if r["bill"] else ""
    money = (' <span class="moneytag">&#9888; %s</span>' % esc("; ".join(h["detail"] for h in r["money"]))) if r.get("money") else ""
    return '<div class="t"><span class="pos %s">%s</span><b>%s</b>%s%s%s</div>' % (
        r["position"], r["position"], esc(r["name"]), org, bill, money)

def build_html(out):
    g = out["generated"]
    linked = [(m, r) for m in out["meetings"] for r in m["testifiers"] if r.get("money")]
    money_html = "".join('<div class="money">%s<div style="font-size:11px;color:#9a957f;margin-top:4px">%s &middot; %s &middot; <a href="%s" target="_blank" rel="noopener">minutes &#8599;</a></div></div>'
                         % (_trow(r, m["url"]), esc(m["date"]), esc(m["body"]), esc(m["url"])) for m, r in linked) \
                 or '<div class="none">No testifier in the scanned window matches a public donation/contract/lobby record. Most public testifiers are private citizens with no money footprint — which is the honest result.</div>'
    # front-end Bill 9 insight — the QUESTION (aloha + factual), with the precision caveat
    allt = [r for m in out["meetings"] for r in m["testifiers"]]
    re_b9 = [r for r in allt if r.get("realtor") and r.get("bill9")]
    fema_n = sum(1 for r in allt if r.get("fema"))
    bill9_html = ""
    if re_b9 or fema_n:
        bill9_html = ('<h2>A question on Bill 9 (short-term rentals)</h2>'
          '<div class="money"><b>%d</b> real-estate / rental-affiliated voices appear in the Bill 9 / short-term-rental '
          'testimony, and <b>%d</b> testimony segments invoke FEMA or disaster housing in the same record. '
          '<div style="font-size:12.5px;color:#bdb8a4;margin-top:8px"><b>The question for the record:</b> where an industry '
          'compensated on rental and property values helps shape the bill that sets those values &mdash; and where some of '
          'those interests also hold disaster-housing exposure or fund the deciders &mdash; does the vote answer the displaced, '
          'or the portfolio? A question grounded in the public testimony, for reporting and verification &mdash; not a finding '
          'against any person.</div>'
          '<div style="font-size:11px;color:#9a957f;margin-top:6px;font-style:italic">Precision note: the real-estate flag is '
          'keyword-based on the transcript; confirm each speaker&rsquo;s actual affiliation in the linked minutes before relying on it.</div></div>')
    mtgs = ""
    for m in out["meetings"]:
        if not m["testifiers"]: continue
        rows = "".join(_trow(r, m["url"]) for r in m["testifiers"])
        mtgs += '<div class="mtg"><div class="mh"><span class="mb">%s</span><span class="md">%s &middot; <a href="%s" target="_blank" rel="noopener">minutes &#8599;</a></span></div>%s</div>' % (
            esc(m["body"]), esc(m["date"]), esc(m["url"]), rows)
    return """<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Who Testified — the public record — govOS · Kilo Aupuni</title>%s</head><body><div class="wrap">
<div class="eyebrow">12 Stones Global &middot; Kilo Aupuni &middot; Maui County &middot; aloha &middot; pono</div>
<h1>Who Testified &mdash; and who, if anyone, the money follows</h1>
<p class="lead">The other half of the record: not just how members <b>voted</b>, but who <b>testified</b> and what
they urged. Named public testifiers parsed from Maui County <b>committee minutes</b> (Legistar verbatim
transcripts), with position and any organization. Where a testifier or org also appears in a public
donation, contract, or lobbying record, it is flagged &mdash; as a question for further reporting, never an accusation.</p>
<div class="kpis">
 <div class="kpi"><div class="kpv">%d</div><div class="kpl">named testifiers</div></div>
 <div class="kpi"><div class="kpv">%d</div><div class="kpl">meetings scanned</div></div>
 <div class="kpi"><div class="kpv">%d</div><div class="kpl">with a public money link</div></div></div>
<h2>Testimony the money may follow</h2>
%s
%s
<h2>The full testimony record (by meeting)</h2>
%s
<div class="disc">Source: Maui County committee minutes, the verbatim Legistar transcripts (View.ashx?M=M).
Only testifiers who self-identify ("my name is…", "I'd like to testify…") are captured — high precision over
recall; a speaker we cannot classify is skipped, never guessed. These names are already public record in the
minutes. The vast majority of testifiers are private citizens with no money footprint; the money-flag appears
only on a public-records match and is posed as a question. (Correction to an earlier note: testifier names ARE
available — in the committee transcripts, though not in the council vote-minutes or eComment.)</div>
<p style="margin-top:10px"><a href="testimony_money.html">professional advocacy &times; money</a> &middot;
<a href="n53_engine.html">N53 — the votes side</a> &middot; <a href="agendas_maui.html">upcoming agendas</a> &middot;
<a href="jurisdictions.html">all jurisdictions</a></p>
<footer>generated %s &middot; testimony-watch v1 &middot; source: Maui County committee minutes (Legistar) &times; CSC/HANDS/HSEC public records &middot; Kilo Aupuni &middot; aloha &middot; pono</footer>
</div></body></html>""" % (CSS, out["testifiers"], out["minutes_scanned"], out["money_links"], money_html, bill9_html, mtgs, g)

def main():
    yr = now_hst().year
    mins = []
    try: mins = enumerate_minutes(yr)
    except Exception as e: print("enumerate err:", e)
    if not mins:
        try: mins = enumerate_minutes(yr - 1)
        except Exception: pass
    idx = money_index()
    meetings, n_test, n_link = [], 0, 0
    for mid, guid in mins[:MAXMTG]:
        try:
            data = get(LEG + "View.ashx?M=M&ID=%s&GUID=%s" % (mid, guid), raw=True)
            t = "\n".join((p.extract_text() or "") for p in pypdf.PdfReader(io.BytesIO(data)).pages)
        except Exception:
            continue
        body, date = meeting_header(t)
        tests = parse_testifiers(t)
        for r in tests:
            r["money"] = link_money(r, idx)
            n_link += 1 if r["money"] else 0
        n_test += len(tests)
        meetings.append({"minutes_id": mid, "url": LEG + "View.ashx?M=M&ID=%s&GUID=%s" % (mid, guid),
                         "body": body, "date": date, "testifiers": tests})
    out = {"generated": now_hst().strftime("%Y-%m-%d %H:%M HST"), "source": "Maui County committee minutes (Legistar View.ashx?M=M)",
           "minutes_scanned": len(meetings), "minutes_available": len(mins),
           "testifiers": n_test, "money_links": n_link, "meetings": meetings}
    open(OUT, "w", encoding="utf-8", newline="\n").write(json.dumps(out, ensure_ascii=False, indent=1))
    open(os.path.join(MAUIOS, "testimony_record.html"), "w", encoding="utf-8", newline="\n").write(build_html(out))
    print("testimony-watch: scanned %d/%d minutes, %d named testifiers, %d with a public money link"
          % (len(meetings), len(mins), n_test, n_link))
    for m in meetings:
        if m["testifiers"]:
            print("  %s %s: %d testifiers" % (m["date"], m["body"][:34], len(m["testifiers"])))
    return 0

if __name__ == "__main__":
    import sys; sys.exit(main())
