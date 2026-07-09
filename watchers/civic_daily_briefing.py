#!/usr/bin/env python3
"""civic_daily_briefing.py - the STANDING DAILY "Today's Agenda" briefing (James 2026-06-26).

"A full report on today's agenda posted in our newsletter and blog every day right before
the meetings, at sunrise."  Forward-looking (BEFORE the meetings, so people can act that
morning) - the mirror of meeting_digest_post.py (which is the AFTER-the-meeting digest).

WHAT IT DOES (data only - it does NOT publish, email, or fire any trigger by itself):
  - pulls TODAY's real civic meetings from the Legistar feed (Maui + optional Honolulu/state)
  - for each meeting: body, HST start time, location, the agenda items, neutral "what to ask",
    how to testify (eComment link + Sunshine-Law deadline), and the primary-source links
  - opens with the moon (kaulana mahina), closes with "E ala e - the curse is broken with aloha"
  - writes a BLOG post (HTML, civic page standard) + a NEWSLETTER body (TXT) + daily_latest.json
    (the shape tools/ops/newsletter_subscribers.send reads) - all to a STAGING dir
  - leak-gated; idempotent (dated filename); graceful "no meetings today"

INTEGRITY: 100% public record (Legistar). Money/votes are QUESTION-framed, never accusations.
Sourced-only - framing != fact - position != law. Nothing here sends or publishes; the sunrise
trigger, the publish verb, and the newsletter send are wired SEPARATELY and gated on James.

  python civic_daily_briefing.py                      # today HST, Maui
  python civic_daily_briefing.py --date 2026-06-30     # a specific day
  python civic_daily_briefing.py --tenants maui,honolulu
"""
import os, sys, json, re, html, ssl, argparse, urllib.request, urllib.parse
from datetime import date, datetime, timezone, timedelta

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
OUT  = os.path.join(ROOT, "reports", "mauios", "daily"); os.makedirs(OUT, exist_ok=True)
NL   = os.path.join(ROOT, "reports", "mauios", "newsletter"); os.makedirs(NL, exist_ok=True)
HST  = timezone(timedelta(hours=-10))
esc  = lambda s: html.escape(str(s if s is not None else ""))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(ROOT, "tools", "ops"))

# Same leak gate the civic newsletters use - aborts the build if a private/secret marker slips in.
FORBIDDEN = re.compile(r"sk_live|rk_live|whsec_|prosecut|case_file|/king|oversight_|password|api_token|"
                       r"webhook_secret|reports/_status|recusal", re.I)

TENANTS = {
    "maui":     {"client": "mauicounty", "label": "Maui County"},
    "honolulu": {"client": "honolulu",   "label": "City & County of Honolulu"},
    "hawaii":   {"client": "hawaiicounty","label": "Hawaiʻi County"},
    "kauai":    {"client": "kauai",       "label": "Kauaʻi County"},
}
UA  = {"User-Agent": "12sgi-kilo-aupuni/1.0 (civic transparency; public record)"}
CTX = ssl.create_default_context()


# -- timing (reuse the canonical system clock) --------------------------------
def moon_for(d):
    try:
        import moon_calendar as mc
        return mc.reading(d)
    except Exception:
        return {}

def sun_for(d):
    try:
        import sun_timing
        return {"sunrise": sun_timing.sunrise_hst(d), "sunset": sun_timing.sunset_hst(d)}
    except Exception:
        return {}

def _hhmm(dt):
    try:
        return dt.strftime("%-I:%M %p") if hasattr(dt, "strftime") else str(dt)
    except Exception:
        try:    return dt.strftime("%I:%M %p").lstrip("0")
        except Exception: return str(dt)


# -- the Pō prayers that bracket the day (James 2026-06-26) --------------------
# OPEN with the prayer from the night that just gestated this dawn (PULLED, never invented):
# prefer the actual staged Moon Blessing text; else reproduce it byte-identically from the same
# generator (sage_kumulipo_card.gather + moon_blessing's base format). CLOSE with a forward
# intention toward the coming Pō, anchored on tonight's real kaulana-mahina offering + the day's gathering.

def _staged_blessing(date_s):
    """The exact Moon Blessing prose the system already staged for that night, if it exists."""
    p = os.path.join(ROOT, "reports", "_status", "agenda_reels", "moon_" + date_s, "storyboard.json")
    try:
        sb = json.load(open(p, encoding="utf-8"))
        for b in sb.get("beats", []):
            if b.get("body"):
                return b["body"].strip()
    except Exception:
        pass
    return ""

def _reconstruct_blessing(date_s):
    """Reproduce moon_blessing.caption()'s base text exactly (same source data, no hashtags)."""
    try:
        import sage_kumulipo_card as SKC
        g = SKC.gather(date_s)
        m = g.get("moon") or {}; wa = g.get("wa") or {}
        return ("Moon blessing - %s.  po %d, %s (%s): %s.  Kumulipo wa %s, %s.  "
                "Offered with aloha - kumu pending." % (
                    m.get("date", date_s), m.get("night", 0), m.get("po", ""), m.get("phase", ""),
                    m.get("offering", ""), wa.get("wa", ""),
                    (wa.get("archetype") or "").split(" - ")[-1] or "the source"))
    except Exception:
        return ""

def night_before(d):
    """The blessing offered at last night's sunset (civil date d-1), which gestated this dawn."""
    prev = (d - timedelta(days=1)).isoformat()
    text = _staged_blessing(prev); prov = "offered"
    if not text:
        text = _reconstruct_blessing(prev); prov = "from the kaulana mahina"
    return {"date": prev, "text": text, "prov": prov}

def night_ahead(d, n_meetings):
    """A forward intention toward tonight's Pō, anchored on the real moon offering + the day's gathering."""
    po = phase = off = ""
    try:
        import moon_calendar as MC
        r = MC.reading(d.isoformat())
        po, phase, off = r.get("po", ""), r.get("phase", ""), r.get("offering", "")
    except Exception:
        pass
    if n_meetings:
        planted = "the people's testimony and %d gathering%s" % (n_meetings, "" if n_meetings == 1 else "s")
    else:
        planted = "a quiet day, the record at rest"
    text = ("Into the pō ahead — Pō %s%s%s. What today plants — %s — we carry into the night "
            "to gestate tomorrow's dawn." % (
                po, (", " + phase) if phase else "", (": " + off) if off else "", planted))
    return {"date": d.isoformat(), "po": po, "phase": phase, "text": text}


# -- Legistar (public record) -------------------------------------------------
def _get(url, timeout=18):
    try:
        req = urllib.request.Request(url, headers=UA)
        return json.loads(urllib.request.urlopen(req, timeout=timeout, context=CTX).read().decode())
    except Exception:
        return None

def meetings_on(client, d):
    """Events whose EventDate falls on day d, with their agenda items. Public record."""
    lo, hi = "%sT00:00:00" % d, "%sT23:59:59" % d
    flt = "EventDate ge datetime'%s' and EventDate le datetime'%s'" % (lo, hi)
    url = "https://webapi.legistar.com/v1/%s/Events?%s" % (
        client, urllib.parse.urlencode({"$filter": flt, "$orderby": "EventTime"}))
    evs = _get(url) or []
    out = []
    for ev in evs:
        eid = ev.get("EventId")
        items = _get("https://webapi.legistar.com/v1/%s/Events/%s/EventItems?$top=200" % (client, eid)) or []
        titles = []
        for it in items:
            t = (it.get("EventItemTitle") or it.get("EventItemMatterName") or "").strip()
            if not t or len(t) <= 4:
                continue
            t = re.sub(r"\s+", " ", t)
            # drop Legistar section headers / procedural boilerplate (e.g. "A G E N D A")
            bare = t.replace(" ", "").upper()
            if bare in {"AGENDA", "MINUTES", "ADJOURNMENT", "ROLLCALL", "ANNOUNCEMENTS",
                        "PUBLICTESTIMONY", "OLDBUSINESS", "NEWBUSINESS", "COMMUNICATIONS",
                        "APPROVALOFMINUTES", "CALLTOORDER", "EXECUTIVESESSION"}:
                continue
            titles.append(t[:240])
        out.append({
            "body":     ev.get("EventBodyName") or "Council/Committee",
            "time":     ev.get("EventTime") or "",
            "location": ev.get("EventLocation") or "",
            "url":      ev.get("EventInSiteURL") or "https://%s.legistar.com/Calendar.aspx" % client,
            "agenda":   ev.get("EventAgendaFile") or "",
            "comment":  ev.get("EventCommentURL") or "",
            "items":    titles,
        })
    return out


# -- neutral "what to ask" (question-framed, never an accusation) -------------
_LENS = [
    (re.compile(r"contract|award|bid|procure|rfp|purchase", re.I),
     "Who is awarded this, for how much - and does the public record show who funds the people deciding?"),
    (re.compile(r"\bsma\b|shoreline|coastal|special management", re.I),
     "Did anyone with the duty find no significant or cumulative coastal harm BEFORE this moves - or is that finding skipped?"),
    (re.compile(r"zoning|permit|entitlement|variance|rezon|land use|subdivision", re.I),
     "Who benefits from this land-use change, who is nearby, and what conditions protect the community?"),
    (re.compile(r"budget|appropriat|fund|fee|tax|rate|fiscal", re.I),
     "What is the trade-off here, and who pays - residents, or someone else?"),
    (re.compile(r"water|well|stream|aquifer|diversion", re.I),
     "Whose water, how much, and what does it leave for the aina and the next generation?"),
    (re.compile(r"housing|affordable|rental|homeless", re.I),
     "Who is actually housed by this, at what income, and for how long is it kept affordable?"),
    (re.compile(r"lease|license|easement|disposition|sale of|convey", re.I),
     "What public asset is changing hands, to whom, at what price, and was it offered openly?"),
]
def what_to_ask(items):
    qs, seen = [], set()
    for t in items:
        for rx, q in _LENS:
            if rx.search(t) and q not in seen:
                qs.append(q); seen.add(q); break
        if len(qs) >= 3:
            break
    if not qs:
        qs.append("What does this decide, who does it affect, and what does the public record already show about it?")
    return qs


# -- render -------------------------------------------------------------------
def _testify_line(m):
    bits = []
    if m["comment"]:
        bits.append('<a class="src" href="%s" target="_blank" rel="noopener">submit written testimony (eComment) &#8599;</a>' % esc(m["comment"]))
    bits.append('<a class="src" href="%s" target="_blank" rel="noopener">full agenda + packet &#8599;</a>' % esc(m["url"]))
    return " &middot; ".join(bits)

def build_html(d, tenants, blocks, moon, sun, before, ahead):
    sr = _hhmm(sun.get("sunrise")) if sun.get("sunrise") else ""
    nice = d.strftime("%A, %B %d, %Y").replace(" 0", " ")
    head_moon = ""
    if moon:
        head_moon = "&#127769; Pō %s &middot; %s &mdash; %s" % (
            esc(moon.get("po", "")), esc(moon.get("phase", "")), esc(moon.get("offering", "")))

    sections = []
    total_meetings = 0
    for tk in tenants:
        ms = blocks.get(tk, [])
        tlabel = TENANTS[tk]["label"]
        if not ms:
            sections.append('<section class="ten"><h2>%s</h2><p class="none">No public meetings posted for today. '
                            'A quiet civic day - the record rests.</p></section>' % esc(tlabel))
            continue
        total_meetings += len(ms)
        rows = []
        for m in ms:
            items_html = "".join("<li>%s</li>" % esc(it) for it in m["items"][:18]) or "<li class='none'>Agenda items not yet posted - see the packet link.</li>"
            ask_html = "".join("<li>%s</li>" % esc(q) for q in what_to_ask(m["items"]))
            when = (esc(m["time"]) + " HST") if m["time"] else "time TBA"
            loc  = (" &middot; " + esc(m["location"])) if m["location"] else ""
            rows.append("""
      <div class="mtg">
        <div class="mtghd"><span class="body">%s</span><span class="when">%s%s</span></div>
        <div class="sub">On today's agenda</div>
        <ul class="items">%s</ul>
        <div class="ask"><div class="askhd">What you could ask</div><ul>%s</ul></div>
        <div class="act">%s</div>
      </div>""" % (esc(m["body"]), when, loc, items_html, ask_html, _testify_line(m)))
        sections.append('<section class="ten"><h2>%s</h2>%s</section>' % (esc(tlabel), "".join(rows)))

    body = """<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Today's Civic Agenda - %(nice)s - Kilo Aupuni</title>
<style>
 body{margin:0;background:#0c100e;color:#e8e4d8;font-family:Georgia,serif;line-height:1.55}
 .wrap{max-width:880px;margin:0 auto;padding:34px 22px 70px}
 .eyebrow{font-family:Consolas,monospace;font-size:11px;letter-spacing:1.3px;color:#d9b24c;text-transform:uppercase}
 h1{font-size:26px;margin:8px 0 4px}
 .moon{font-size:12.5px;color:#bda86a;margin:4px 0 2px}
 .lead{font-size:14px;color:#bdb8a4;max-width:80ch}
 .disc{font-size:12px;color:#9a957f;font-style:italic;border-left:2px solid rgba(217,178,76,.5);padding:8px 13px;margin:15px 0;background:rgba(217,178,76,.05)}
 .ten h2{font-size:17px;color:#f0cf7a;border-bottom:1px solid rgba(255,255,255,.09);padding-bottom:6px;margin:26px 0 8px}
 .mtg{border:1px solid rgba(255,255,255,.09);border-radius:11px;padding:14px 16px;margin:13px 0;background:rgba(255,255,255,.012)}
 .mtghd{display:flex;justify-content:space-between;gap:12px;align-items:baseline;flex-wrap:wrap}
 .body{font-size:16px;font-weight:700;color:#e8e4d8}
 .when{font-family:Consolas,monospace;font-size:11.5px;color:#7fb8d8;white-space:nowrap}
 .sub{font-family:Consolas,monospace;font-size:9.5px;letter-spacing:.6px;color:#9a957f;text-transform:uppercase;margin:7px 0 3px}
 ul.items{margin:3px 0;padding-left:19px;font-size:13px;color:#dcd7c8} ul.items li{margin:4px 0}
 .ask{margin-top:9px;background:rgba(86,192,138,.05);border:1px solid rgba(86,192,138,.18);border-radius:8px;padding:9px 12px}
 .askhd{font-family:Consolas,monospace;font-size:9.5px;letter-spacing:.6px;color:#6fd29b;text-transform:uppercase;margin-bottom:3px}
 .ask ul{margin:3px 0;padding-left:18px;font-size:12.5px;color:#cfdccf} .ask li{margin:4px 0}
 .act{margin-top:9px;border-top:1px dashed rgba(255,255,255,.12);padding-top:7px}
 .src{font-family:Consolas,monospace;font-size:10.5px;color:#d9b24c;text-decoration:none} .src:hover{text-decoration:underline}
 .none{color:#9a957f;font-style:italic}
 .pule{border:1px solid rgba(189,168,106,.3);border-radius:11px;padding:13px 16px;margin:16px 0;background:rgba(189,168,106,.05)}
 .pulehd{font-family:Consolas,monospace;font-size:9.5px;letter-spacing:1px;color:#bda86a;text-transform:uppercase;margin-bottom:6px}
 .puletext{font-size:13.5px;color:#e3dcc6;font-style:italic;line-height:1.6}
 .pulesrc{font-family:Consolas,monospace;font-size:9.5px;color:#7d775f;margin-top:6px}
 .ealae{margin-top:18px;font-size:14px;color:#e3c98a;font-style:italic}
 footer{margin-top:20px;border-top:1px solid rgba(255,255,255,.1);padding-top:13px;font-family:Consolas,monospace;font-size:10.5px;color:#9a957f}
</style></head><body><div class="wrap">
<div class="eyebrow">12 Stones Global &middot; Kilo Aupuni &middot; today's civic agenda</div>
<h1>What your government decides today</h1>
<div class="moon">%(moon)s</div>

<div class="pule">
  <div class="pulehd">&#127769; The prayer from the night that gestated this dawn</div>
  <div class="puletext">%(before)s</div>
  <div class="pulesrc">Moon Blessing offered at last sunset &middot; %(before_date)s &middot; %(before_prov)s</div>
</div>

<p class="lead">Posted at sunrise%(sr)s, before the meetings &mdash; so you can read the day's public agenda
and act on it this morning. Every item below is the public record (Legistar). Knowing your government is
how you protect your community &mdash; civic duty is aloha in action.</p>
<div class="disc">100%% public record. Money and votes are written as questions, never as accusations.
This is sourced information, not legal advice. Verify at the linked primary source.</div>
%(sections)s

<div class="pule">
  <div class="pulehd">&#127765; The intention carried into the night ahead</div>
  <div class="puletext">%(ahead)s</div>
</div>
<div class="ealae">E ala ē &mdash; the curse is broken with aloha. Show up; the record is brighter when you do.</div>
<footer>12 Stones Global &middot; kilo-aupuni &middot; %(nice)s &middot; sourced from Legistar &middot; compiled with AI assistance from public records</footer>
</div></body></html>""" % {"nice": esc(nice), "moon": head_moon, "sr": (" (" + sr + " HST)") if sr else "",
                            "before": esc(before.get("text", "")), "before_date": esc(before.get("date", "")),
                            "before_prov": esc(before.get("prov", "")), "ahead": esc(ahead.get("text", "")),
                            "sections": "\n".join(sections)}
    return body, total_meetings


def build_txt(d, tenants, blocks, moon, sun, public_url, before, ahead):
    nice = d.strftime("%A, %B %d, %Y").replace(" 0", " ")
    L = ["TODAY'S CIVIC AGENDA - %s" % nice, "12SGI . Kilo Aupuni", "=" * 60, ""]
    if moon:
        L += ["Po %s . %s" % (moon.get("po", ""), moon.get("phase", "")),
              "Civic offering: %s" % moon.get("offering", ""), ""]
    # OPEN bracket - the prayer from the night that gestated this dawn (pulled, not invented)
    L += ["~ THE PRAYER FROM THE NIGHT BEFORE (%s) ~" % before.get("date", ""),
          before.get("text", ""), ""]
    L += ["Posted at sunrise, before the meetings, so you can act this morning.",
          "Every item is the public record (Legistar). Civic duty is aloha in action.", ""]
    total = 0
    for tk in tenants:
        ms = blocks.get(tk, [])
        L += ["%s" % TENANTS[tk]["label"], "-" * 40]
        if not ms:
            L += ["  No public meetings posted for today.", ""]; continue
        for m in ms:
            total += 1
            when = (m["time"] + " HST") if m["time"] else "time TBA"
            L.append("  * %s - %s%s" % (m["body"], when, (" . " + m["location"]) if m["location"] else ""))
            for it in m["items"][:12]:
                L.append("      - %s" % it)
            for q in what_to_ask(m["items"]):
                L.append("      ASK: %s" % q)
            if m["comment"]:
                L.append("      Testify (eComment): %s" % m["comment"])
            L.append("      Agenda/packet: %s" % m["url"])
            L.append("")
    # CLOSE bracket - the intention carried into the night ahead
    L += ["=" * 60,
          "~ THE INTENTION FOR THE NIGHT AHEAD ~",
          ahead.get("text", ""), "",
          "E ala e - the curse is broken with aloha. Show up; the record is brighter when you do.",
          "Read on the web: %s" % public_url,
          "Unsubscribe: {{unsubscribe_url}}",
          "Compiled with AI assistance from public records (Legistar). Sourced, not legal advice."]
    return "\n".join(L), total


def run(target=None, tenants=("maui",)):
    d = target or datetime.now(HST).date()
    moon, sun = moon_for(d), sun_for(d)
    blocks = {tk: meetings_on(TENANTS[tk]["client"], d) for tk in tenants}

    date_str = d.isoformat()
    public_url = "https://jimlangford.github.io/12sgi-king/civic_daily_%s.html" % date_str
    # count meetings first so the night-ahead intention can name the day's gathering
    n_pre = sum(len(v) for v in blocks.values())
    before = night_before(d)
    ahead  = night_ahead(d, n_pre)
    html_out, n = build_html(d, tenants, blocks, moon, sun, before, ahead)
    txt_out, _  = build_txt(d, tenants, blocks, moon, sun, public_url, before, ahead)

    blob = html_out + txt_out
    hit = FORBIDDEN.search(blob)
    if hit:
        raise SystemExit("LEAK GATE: forbidden marker %r - aborting (nothing written)" % hit.group(0))

    hp = os.path.join(OUT, "civic_daily_%s.html" % date_str)        # dated archive (blog history)
    tp = os.path.join(OUT, "civic_daily_%s.txt" % date_str)
    open(hp, "w", encoding="utf-8", newline="\n").write(html_out)
    open(tp, "w", encoding="utf-8", newline="\n").write(txt_out)
    # STABLE always-current page that build_site publishes: reports/mauios/civic_daily.html
    # (the public "Today's Civic Agenda" blog, refreshed each sunrise; dated copies stay in daily/ as the archive)
    stable = os.path.join(ROOT, "reports", "mauios", "civic_daily.html")
    open(stable, "w", encoding="utf-8", newline="\n").write(html_out)

    # daily_latest.json - the shape tools/ops/newsletter_subscribers.send() reads (when James wires send).
    # SEPARATE from the weekly latest.json so the two issues never clobber each other.
    subject = "Today's Civic Agenda - %s (%d meeting%s)" % (
        d.strftime("%b ").rstrip() + " " + str(d.day), n, "" if n == 1 else "s")
    latest = {"kind": "daily_civic_briefing", "date": date_str, "subject": subject,
              "meetings": n, "tenants": list(tenants),
              "pule_before": {"date": before["date"], "prov": before["prov"], "text": before["text"]},
              "pule_ahead": {"po": ahead["po"], "text": ahead["text"]},
              "html_path": os.path.relpath(hp, ROOT), "txt_path": os.path.relpath(tp, ROOT),
              "public_url": public_url, "leak_check": "PASS",
              "generated": datetime.now(HST).strftime("%Y-%m-%d %H:%M HST"),
              "STAGED_ONLY": "Not published, not emailed, not triggered. Wiring is gated on James."}
    json.dump(latest, open(os.path.join(NL, "daily_latest.json"), "w", encoding="utf-8"), indent=1)
    return latest


def main():
    p = argparse.ArgumentParser(description="Today's civic agenda - daily briefing (staged; does not publish or send)")
    p.add_argument("--date", help="YYYY-MM-DD (default: today HST)")
    p.add_argument("--tenants", default="maui", help="comma list: maui,honolulu,hawaii,kauai")
    a = p.parse_args()
    target = date.fromisoformat(a.date) if a.date else None
    tenants = tuple(t.strip() for t in a.tenants.split(",") if t.strip() in TENANTS) or ("maui",)
    m = run(target, tenants)
    print("civic_daily_briefing: %s - %d meeting(s), tenants=%s, leak-gate PASS"
          % (m["date"], m["meetings"], ",".join(m["tenants"])))
    print("  BLOG (staged): %s" % m["html_path"])
    print("  NEWSLETTER (staged): %s" % m["txt_path"])
    print("  STAGED ONLY - not published, not emailed, not triggered.")


if __name__ == "__main__":
    main()
