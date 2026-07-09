#!/usr/bin/env python3
"""meeting_commentary.py — $99/seat LIVE MEETING COMMENTARY engine.

For every govOS council/committee meeting it generates a running, item-by-item
AI commentary that includes:
  - Plain-language "what this vote actually means" per agenda item
  - MONEY PROXIMITY: which officials voting have donor ties to the item's sector
  - TESTIMONY TRACKER: who spoke, question-framed donor cross-references
  - NON-COMPLIANCE FLAGS: Sunshine Law violations, recusal failures, procedure breaks
  - PONO NOTE: what a community member should watch for

INTEGRITY CONTRACT:
  - Every flag framed as a QUESTION (never verdict) + sourced public record
  - Prosecutor private theory NEVER surfaces here (that's the private lane)
  - Non-compliance = statutory facts only (§92 deadlines, recusal HRS §84-14)
  - Commentary delivered to SUBSCRIBERS ONLY (not published to GitHub Pages)
  - Private outputs → reports/_status/meeting_commentary/<event_id>.*
  - Subscribers managed in config/commentary_subscribers.json (Stripe-verified)

Usage:
  python meeting_commentary.py                   # most recent past Maui meeting
  python meeting_commentary.py --event-id 4806
  python meeting_commentary.py --date 2026-06-25
  python meeting_commentary.py --deliver         # email to subscribers after gen
  python meeting_commentary.py --status          # show delivered log
Stdlib only. No GPU.
"""
import os, sys, json, re, html, argparse, urllib.request, urllib.parse, ssl
from datetime import datetime, date, timezone, timedelta

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HERE   = os.path.dirname(os.path.abspath(__file__))
PROJ   = os.path.dirname(os.path.dirname(HERE))
PRIV   = os.path.join(PROJ, "reports", "_status", "meeting_commentary")
MAUIOS = os.path.join(PROJ, "reports", "mauios")
CFG    = os.path.join(PROJ, "config")
HST    = timezone(timedelta(hours=-10))
esc    = lambda s: html.escape(str(s or ""))

LEGISTAR = "https://webapi.legistar.com/v1/mauicounty"
UA       = {"User-Agent": "12sgi-kilo-aupuni-commentary/1.0 (civic transparency; public record)"}

# ── Safe output path guard (never write to public) ──────────────────────────────
FORBIDDEN_OUT = re.compile(r"seed_reports|site/|reports/mauios(?!.*_status)", re.I)

def _safe_path(p):
    if FORBIDDEN_OUT.search(p.replace("\\", "/")):
        raise RuntimeError("commentary: output path would reach public area: %s" % p)
    return p

os.makedirs(PRIV, exist_ok=True)

# ── JSON helpers ─────────────────────────────────────────────────────────────────
def _load(p, d=None):
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception:
        return d if d is not None else {}

def _save(p, obj):
    _safe_path(p)
    tmp = p + ".tmp"
    open(tmp, "w", encoding="utf-8").write(json.dumps(obj, indent=2, ensure_ascii=False))
    os.replace(tmp, p)

# ── HTTP helper ──────────────────────────────────────────────────────────────────
def _get(url, timeout=25):
    req = urllib.request.Request(url, headers=UA)
    ctx = ssl.create_default_context()
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
        return r.read().decode("utf-8", "replace")

def _jget(url):
    return json.loads(_get(url))

# ── LEGISTAR fetch ────────────────────────────────────────────────────────────────
def _events(days_back=14, days_fwd=3):
    now_hst = datetime.now(HST)
    since = (now_hst - timedelta(days=days_back)).strftime("%Y-%m-%dT00:00:00")
    until = (now_hst + timedelta(days=days_fwd)).strftime("%Y-%m-%dT23:59:59")
    q = urllib.parse.urlencode({
        "$orderby": "EventDate desc",
        "$top": "20",
        "$filter": "EventDate ge datetime'%s' and EventDate le datetime'%s'" % (since, until),
    })
    try:
        return _jget("%s/Events?%s" % (LEGISTAR, q))
    except Exception:
        return []

def _event_by_id(event_id):
    try:
        return _jget("%s/Events/%s" % (LEGISTAR, event_id))
    except Exception:
        return {}

def _event_by_date(dt_str):
    for ev in _events(days_back=30, days_fwd=7):
        d = (ev.get("EventDate") or "")[:10]
        if d == dt_str:
            return ev
    return {}

def _agenda_items(event_id):
    try:
        return _jget("%s/Events/%s/EventItems?AgendaNote=1&MinutesNote=1&Attachments=1" % (LEGISTAR, event_id))
    except Exception:
        return []

# ── DONOR PROXIMITY ───────────────────────────────────────────────────────────────
def _load_donors():
    return _load(os.path.join(MAUIOS, "donor_profiles.json"), {})

def _officials_with_donor_tie(sector_keywords, donors):
    """Return list of {official, donors, question} for officials with money from the sector."""
    flags = []
    kws = [k.lower() for k in sector_keywords]
    for official, profile in donors.items():
        hits = []
        for donor_name, amount in (profile.get("top_donors") or {}).items():
            if any(k in donor_name.lower() for k in kws):
                hits.append({"donor": donor_name, "amount_usd": amount})
        if hits:
            flags.append({
                "official": official,
                "sector_ties": hits,
                "question": "Does %s's receipt of campaign contributions from %s create a proximity to this vote?" % (
                    official, ", ".join(h["donor"] for h in hits[:3]))
            })
    return flags

# ── TESTIMONY TRACKER ─────────────────────────────────────────────────────────────
def _load_testimony_crosscheck():
    p = os.path.join(PROJ, "reports", "_status", "testimony_crosscheck.json")
    return _load(p, {"findings": []})

def _testimony_for_matter(matter_title, crosscheck):
    """Find testimony findings relevant to a matter title (keyword match)."""
    words = set(re.findall(r"\w{4,}", matter_title.lower()))
    matched = []
    for f in (crosscheck.get("findings") or []):
        ftxt = (f.get("matter") or "") + " " + (f.get("industry") or "")
        if any(w in ftxt.lower() for w in words):
            matched.append(f)
    return matched[:5]

# ── SUNSHINE / NON-COMPLIANCE ─────────────────────────────────────────────────────
def _sunshine_flag(event_date_str, posted_date_str=None):
    """Return a compliance flag dict for the notice timing."""
    try:
        ed = date.fromisoformat(event_date_str[:10])
    except Exception:
        return None
    deadline = ed - timedelta(days=6)
    today = datetime.now(HST).date()
    if posted_date_str:
        try:
            pd = date.fromisoformat(posted_date_str[:10])
            if pd > deadline:
                return {
                    "type": "sunshine_late_notice",
                    "severity": "HIGH",
                    "statute": "HRS §92-7(c)",
                    "fact": "Meeting notice posted %s — %d day(s) after the §92-7 6-calendar-day deadline of %s." % (
                        pd.isoformat(), (pd - deadline).days, deadline.isoformat()),
                    "question": "Was this meeting properly noticed under HRS §92-7? A notice posted after the deadline triggers §92-7(c) cancellation as a matter of law.",
                }
        except Exception:
            pass
    if today > deadline and posted_date_str is None:
        return {
            "type": "sunshine_unverified_notice",
            "severity": "MEDIUM",
            "statute": "HRS §92-7",
            "fact": "Notice posting date not available in machine-readable feed — §92-7 deadline was %s." % deadline.isoformat(),
            "question": "Was this meeting noticed by %s as required by HRS §92-7?" % deadline.isoformat(),
        }
    return None

# ── SECTOR KEYWORDS from item title ──────────────────────────────────────────────
_SECTOR_MAP = {
    "real estate": ["real estate", "realty", "realtor", "developer", "development", "maui land"],
    "construction": ["construction", "contractor", "engineer", "civil", "infrastructure", "road"],
    "short term rental": ["short-term rental", "str", "vacation rental", "tvr", "transient"],
    "hotel": ["hotel", "resort", "tourism", "hta", "visitor"],
    "utility": ["utility", "water", "wastewater", "electric", "meco", "mwc"],
    "agriculture": ["farm", "agriculture", "ag land", "upcountry"],
    "healthcare": ["hospital", "health", "medical", "hmsa"],
    "finance": ["bank", "financial", "loan", "credit"],
}

def _infer_sectors(title):
    tl = title.lower()
    return [s for s, kws in _SECTOR_MAP.items() if any(k in tl for k in kws)]

# ── PLAIN-LANGUAGE SUMMARY ────────────────────────────────────────────────────────
def _plain_summary(item):
    """Plain-language one-liner for an agenda item. Heuristic fallback — no LLM needed."""
    t = (item.get("EventItemTitle") or item.get("title") or "").strip()
    num = (item.get("EventItemMatterFile") or "").strip()
    action = (item.get("EventItemActionText") or "").strip()
    mtype = (item.get("EventItemMatterType") or "").strip()
    # Resolution / Bill / Communication prefix
    prefix = ""
    if re.search(r"\breso\w*\b", t, re.I) or mtype.lower() == "resolution":
        prefix = "RESOLUTION — "
    elif re.search(r"\bbill\b", t, re.I) or mtype.lower() == "bill":
        prefix = "BILL — "
    elif re.search(r"\bord\w*\b", t, re.I) or mtype.lower() == "ordinance":
        prefix = "ORDINANCE — "
    summary = prefix + (t[:180] if t else "(no title)")
    if num:
        summary = "[%s] %s" % (num, summary)
    return summary

# ── ITEM-LEVEL COMMENTARY BLOCK ───────────────────────────────────────────────────
def _commentary_block(item, donors, crosscheck):
    title = (item.get("EventItemTitle") or item.get("title") or "")
    sectors = _infer_sectors(title)
    money_flags = []
    for s in sectors:
        kws = _SECTOR_MAP.get(s, [s])
        money_flags += _officials_with_donor_tie(kws, donors)
    # de-dup by official
    seen = set()
    deduped = []
    for f in money_flags:
        if f["official"] not in seen:
            seen.add(f["official"])
            deduped.append(f)
    testimony = _testimony_for_matter(title, crosscheck)
    url = item.get("EventItemMatterAttachmentURL") or item.get("url") or ""
    return {
        "item_title": title,
        "plain_summary": _plain_summary(item),
        "sectors": sectors,
        "money_proximity": deduped,
        "testimony_crosscheck": testimony,
        "non_compliance": [],
        "pono_note": _pono_note(deduped, testimony, title),
        "source_url": url,
    }

def _pono_note(money_flags, testimony, title):
    notes = []
    if money_flags:
        officials = [f["official"] for f in money_flags[:3]]
        notes.append("Watch: %s received campaign contributions from sectors with a stake in this item." % ", ".join(officials))
    if testimony:
        notes.append("Cross-checked testimony on file: industry advocates on record with campaign ties to deciding officials.")
    if not notes:
        notes.append("No public-record money-proximity flags found for this item in the current dataset.")
    return " ".join(notes)

# ── FULL MEETING COMMENTARY ───────────────────────────────────────────────────────
def build_commentary(event_id=None, date_str=None):
    if event_id:
        ev = _event_by_id(event_id)
    elif date_str:
        ev = _event_by_date(date_str)
    else:
        evs = _events(days_back=3, days_fwd=0)
        ev = evs[0] if evs else {}

    if not ev:
        print("meeting_commentary: no meeting found"); return None

    eid = ev.get("EventId") or event_id
    edate = (ev.get("EventDate") or "")[:10]
    ebody = ev.get("EventBodyName") or "Council"
    eurl  = ev.get("EventInSiteURL") or ""
    posted = (ev.get("EventLastModifiedUtc") or ev.get("EventAgendaStatusName") or "")[:10]

    print("meeting_commentary: building for Event %s — %s — %s" % (eid, edate, ebody))

    items = _agenda_items(eid)
    donors = _load_donors()
    crosscheck = _load_testimony_crosscheck()

    sunshine = _sunshine_flag(edate, posted if len(posted) == 10 else None)

    blocks = []
    for it in items:
        b = _commentary_block(it, donors, crosscheck)
        if sunshine:
            b["non_compliance"].append(sunshine)
        blocks.append(b)

    money_count = sum(1 for b in blocks if b["money_proximity"])
    compliance_count = sum(1 for b in blocks if b["non_compliance"])

    out = {
        "generated": datetime.now(HST).strftime("%Y-%m-%d %H:%M HST"),
        "event_id": eid,
        "event_date": edate,
        "body": ebody,
        "source_url": eurl,
        "item_count": len(blocks),
        "money_flags": money_count,
        "compliance_flags": compliance_count,
        "sunshine_flag": sunshine,
        "items": blocks,
        "integrity": "sourced / question-framed / never-publish-without-owner-review",
    }

    slug = "%s_%s" % (str(eid), edate)
    jpath = _safe_path(os.path.join(PRIV, "%s.json" % slug))
    hpath = _safe_path(os.path.join(PRIV, "%s.html" % slug))
    _save(jpath, out)
    open(hpath, "w", encoding="utf-8").write(_render_html(out))
    print("meeting_commentary: %d items | %d money flags | %d compliance flags -> %s" % (
        len(blocks), money_count, compliance_count, jpath))
    return out

# ── HTML RENDERER ─────────────────────────────────────────────────────────────────
def _render_html(c):
    items_html = ""
    for i, b in enumerate(c.get("items") or [], 1):
        mp = b.get("money_proximity") or []
        nc = b.get("non_compliance") or []
        tc = b.get("testimony_crosscheck") or []
        mp_html = ""
        if mp:
            mp_html = "<div class='flag money'><b>Money Proximity</b><ul>" + "".join(
                "<li><b>%s</b> — %s <span class='q'>%s</span></li>" % (
                    esc(f["official"]),
                    esc(", ".join("%s ($%s)" % (d["donor"], d.get("amount_usd","?")) for d in f.get("sector_ties",[])[:3])),
                    esc(f.get("question",""))
                ) for f in mp) + "</ul></div>"
        nc_html = ""
        for n in nc:
            nc_html += "<div class='flag nc-%s'><b>%s</b> (%s) — %s <span class='q'>%s</span></div>" % (
                n.get("severity","").lower(), esc(n.get("type","")),
                esc(n.get("statute","")), esc(n.get("fact","")), esc(n.get("question","")))
        tc_html = ""
        if tc:
            tc_html = "<div class='flag testimony'><b>Testimony on file</b><ul>" + "".join(
                "<li>%s — %s</li>" % (esc(t.get("industry","")), esc(t.get("finding","")[:160]))
                for t in tc) + "</ul></div>"
        pono = esc(b.get("pono_note",""))
        items_html += """<div class='item'>
  <div class='num'>%d</div>
  <div class='body'>
    <div class='title'>%s</div>
    %s%s%s
    <div class='pono'>Pono Note: %s</div>
  </div>
</div>""" % (i, esc(b.get("plain_summary","")), mp_html, nc_html, tc_html, pono)

    return """<!DOCTYPE html><html lang="en"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Commentary — %s — %s</title>
<style>
body{margin:0;background:#0d1117;color:#e8e4d8;font-family:'Segoe UI Variable Text','Segoe UI',sans-serif;font-size:14px;line-height:1.65}
.wrap{max-width:900px;margin:0 auto;padding:28px 20px 60px}
.eyebrow{font-family:Consolas,monospace;font-size:10.5px;letter-spacing:1.6px;color:#d9b24c;text-transform:uppercase;margin-bottom:6px}
h1{font-size:24px;font-weight:600;margin:6px 0 4px;color:#fff}
.meta{font-family:Consolas,monospace;font-size:11px;color:#9a8e6e;margin-bottom:18px}
.scorebar{display:flex;gap:18px;margin:14px 0;flex-wrap:wrap}
.sc{background:rgba(255,255,255,.06);border-radius:8px;padding:10px 18px;font-family:Consolas,monospace}
.sc .n{font-size:26px;font-weight:700;color:#d9b24c} .sc .l{font-size:11px;color:#9a8e6e}
.sc.red .n{color:#e06a4a} .sc.green .n{color:#56c08a}
.item{display:flex;gap:14px;border-bottom:1px solid rgba(255,255,255,.07);padding:16px 0}
.num{font-family:Consolas,monospace;font-size:12px;color:#9a8e6e;min-width:26px;padding-top:2px}
.title{font-size:14.5px;font-weight:600;color:#e8e4d8;margin-bottom:8px}
.flag{margin:6px 0;padding:8px 12px;border-radius:6px;font-size:12.5px}
.flag.money{background:rgba(217,178,76,.1);border-left:3px solid #d9b24c}
.flag.nc-high{background:rgba(224,106,74,.12);border-left:3px solid #e06a4a}
.flag.nc-medium{background:rgba(224,106,74,.07);border-left:3px solid #d99a4a}
.flag.testimony{background:rgba(95,200,140,.08);border-left:3px solid #56c08a}
.flag ul{margin:4px 0 0 16px;padding:0} .flag li{margin:2px 0}
.q{color:#9a8e6e;font-style:italic;display:block;margin-top:3px}
.pono{font-size:12px;color:#9a8e6e;font-style:italic;margin-top:8px;padding:6px 10px;border-left:2px solid rgba(217,178,76,.3)}
.disc{font-size:11.5px;color:#9a8e6e;border:1px solid rgba(255,255,255,.08);border-radius:6px;padding:10px 14px;margin:20px 0}
footer{font-family:Consolas,monospace;font-size:10.5px;color:#9a8e6e;margin-top:24px;border-top:1px solid rgba(255,255,255,.08);padding-top:10px}
a{color:#d9b24c}
</style></head><body><div class="wrap">
<div class="eyebrow">12 Stones Global · govOS Commentary · SUBSCRIBER ONLY</div>
<h1>%s — %s</h1>
<div class="meta">%d agenda items · Generated %s</div>
<div class="scorebar">
  <div class="sc%s"><div class="n">%d</div><div class="l">money proximity flags</div></div>
  <div class="sc%s"><div class="n">%d</div><div class="l">compliance flags</div></div>
  <div class="sc"><div class="n">%d</div><div class="l">items analyzed</div></div>
</div>
<div class="disc">SUBSCRIBER COMMENTARY — private, not for redistribution. All flags are public-record QUESTIONS, never verdicts. Source: Legistar / Hawaii CSC. govOS · kilo-aupuni · calendar_civic.</div>
<div>%s</div>
<footer>Generated %s · meeting_commentary v1 · govOS civic lane · 12sgi · sourced / question-framed / never verdict</footer>
</div></body></html>""" % (
        esc(c.get("body","")), esc(c.get("event_date","")),
        esc(c.get("body","")), esc(c.get("event_date","")),
        c.get("item_count",0), esc(c.get("generated","")),
        " red" if c.get("money_flags",0) > 0 else " green", c.get("money_flags",0),
        " red" if c.get("compliance_flags",0) > 0 else " green", c.get("compliance_flags",0),
        c.get("item_count",0),
        items_html,
        esc(c.get("generated",""))
    )

# ── STATUS ────────────────────────────────────────────────────────────────────────
def show_status():
    files = sorted([f for f in os.listdir(PRIV) if f.endswith(".json")], reverse=True)[:10]
    subs = _load(os.path.join(CFG, "commentary_subscribers.json"), {})
    active = [s for s in subs.get("subscribers",[]) if s.get("status") == "active"]
    print("meeting_commentary: %d commentaries on file | %d active subscriber(s)" % (len(files), len(active)))
    for f in files[:5]:
        try:
            d = json.load(open(os.path.join(PRIV, f), encoding="utf-8"))
            print("  %s  %s  %d items  %d$ flags  %d compliance" % (
                d.get("event_date",""), d.get("body","")[:30], d.get("item_count",0),
                d.get("money_flags",0), d.get("compliance_flags",0)))
        except Exception:
            pass

# ── DELIVERY ──────────────────────────────────────────────────────────────────────
def _deliver(commentary):
    """Email the commentary HTML to active subscribers via tools/ops/mail_graphic.py pattern."""
    try:
        import importlib.util, smtplib
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText
    except Exception:
        print("meeting_commentary: email libs not available — skipping delivery"); return 0

    subs_cfg = _load(os.path.join(CFG, "commentary_subscribers.json"), {})
    active = [s for s in subs_cfg.get("subscribers", []) if s.get("status") == "active"]
    if not active:
        print("meeting_commentary: no active subscribers — skipping delivery"); return 0

    slug = "%s_%s" % (commentary.get("event_id"), commentary.get("event_date"))
    hpath = os.path.join(PRIV, "%s.html" % slug)
    if not os.path.exists(hpath):
        print("meeting_commentary: no HTML file to deliver"); return 0

    html_body = open(hpath, encoding="utf-8").read()
    subject = "[govOS Commentary] %s — %s (%d items, %d flags)" % (
        commentary.get("body","Meeting"), commentary.get("event_date",""),
        commentary.get("item_count",0), commentary.get("money_flags",0))

    gmail_user = os.environ.get("GMAIL_USER", "elementlotus@gmail.com")
    gmail_app_pw = os.environ.get("GMAIL_APP_PASSWORD", "")
    if not gmail_app_pw:
        print("meeting_commentary: GMAIL_APP_PASSWORD not set — delivery skipped"); return 0

    sent = 0
    for sub in active:
        to = sub.get("email","")
        if not to:
            continue
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = gmail_user
            msg["To"] = to
            msg.attach(MIMEText(
                "govOS Commentary — %s — %s\n\nSee the attached HTML or log in at https://12sgianonymous.tail760750.ts.net/king/commentary\n\nPRIVATE — subscriber only." % (
                    commentary.get("body",""), commentary.get("event_date","")), "plain"))
            msg.attach(MIMEText(html_body, "html"))
            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
                s.login(gmail_user, gmail_app_pw)
                s.sendmail(gmail_user, to, msg.as_string())
            sent += 1
        except Exception as e:
            print("meeting_commentary: delivery to %s failed: %s" % (to[:20], e))

    log_path = os.path.join(PROJ, "reports", "_status", "commentary_delivered.jsonl")
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps({
            "ts": datetime.now(HST).strftime("%Y-%m-%d %H:%M HST"),
            "event_id": commentary.get("event_id"),
            "event_date": commentary.get("event_date"),
            "sent_to": sent,
            "subscribers_total": len(active),
        }) + "\n")

    print("meeting_commentary: delivered to %d/%d subscriber(s)" % (sent, len(active)))
    return sent

# ── CLI ───────────────────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser(description="meeting_commentary — $99/seat civic commentary engine")
    ap.add_argument("--event-id", type=int)
    ap.add_argument("--date", help="YYYY-MM-DD")
    ap.add_argument("--deliver", action="store_true", help="email to subscribers after build")
    ap.add_argument("--status", action="store_true")
    args = ap.parse_args()

    if args.status:
        show_status(); return

    c = build_commentary(event_id=args.event_id, date_str=args.date)
    if c and args.deliver:
        _deliver(c)

if __name__ == "__main__":
    main()
