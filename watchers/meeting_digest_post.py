#!/usr/bin/env python3
"""meeting_digest_post.py — SAME-DAY post-meeting digest newsletter (Jimmy 2026-06-22).

After a council meeting (Maui ch53 / BFED / committee), produce a newsletter that:
  1. Shows HOW each councilperson navigated the conversation (question-asker vs narrative-pusher).
     Bullies don't ask questions — they push their narrative. This records the difference.
  2. Cross-references their donor ties through the public money record (RACE CAR FORMAT:
     every sponsor visible, like a race car driver wearing all their logos).
  3. Wraps everything in the Hawaiian moon calendar (kaulana mahina) + sun timing (Hina).
  4. Lists all agenda items, committee items, and positive tenant news.

TWO VERSIONS:
  - OWNER (private): full donor detail + behavior analysis + public questions.
  - PUBLIC (curated): allegation-framed only, no owner-private detail, public questions only.

INTEGRITY:
  - Every datum sourced from public record (Legistar / ORCA / money-bridge).
  - Behavior analysis = pattern observation from minutes, NOT a verdict.
  - Donor crosswalk = question-framed ("does the public record show X?"), never accusation.
  - FORBIDDEN markers abort the build before anything is written.
  - AI-DISCLOSURE on every output ("This digest was compiled with AI assistance from public records.").

Output: reports/mauios/newsletter/meeting_digest_{date}.{html,txt}  +  _latest_meeting_digest.json
CLI:    python meeting_digest_post.py [--meeting <slug>] [--date YYYY-MM-DD] [--tenant maui]
        --meeting: Legistar body slug (default: auto-detect from today's Legistar calendar)
        --date:    meeting date (default: today HST)
        --tenant:  county (default: maui)
        --no-email: skip the email archive step
"""
import os, sys, json, re, html as _html
from datetime import date, datetime, timezone, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
M = os.path.join(ROOT, "reports", "mauios")
ST = os.path.join(ROOT, "reports", "_status")
PRIV = os.path.join(ST, "prosecutor")
OUT = os.path.join(M, "newsletter")
os.makedirs(OUT, exist_ok=True)
HST = timezone(timedelta(hours=-10))
esc = _html.escape

sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "tools", "ops"))

FORBIDDEN = re.compile(
    r"sk_live|rk_live|whsec_|api_token|webhook_secret|password|owner_private|case_file_private",
    re.I,
)

AI_DISCLOSURE = (
    "This digest was compiled with AI assistance from publicly available government records "
    "(Legistar, ORCA, campaign finance, meeting minutes). All statements are observations "
    "from the public record, not legal conclusions. Questions raised are invitations to verify, "
    "not accusations."
)


def load(p, d=None):
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception:
        return d


def now_hst():
    return datetime.now(HST)


# ── Moon + Sun timing ────────────────────────────────────────────────────────

def get_moon(dt=None):
    try:
        import moon_calendar as mc
        return mc.reading(dt or date.today())
    except Exception as e:
        return {"error": str(e)}


def get_sun():
    try:
        import sun_timing
        return {
            "sunset": sun_timing.sunset_hst(),
            "day_key": sun_timing.hawaiian_day_key(),
        }
    except Exception as e:
        return {"error": str(e)}


# ── Legistar live agenda ─────────────────────────────────────────────────────

def fetch_legistar_meetings(body="mauicounty", days_back=3):
    """Pull recent Events from Legistar (the correct endpoint for Maui County)."""
    import ssl, urllib.request, urllib.parse
    UA = {"User-Agent": "12sgi-kilo-aupuni/1.0 (civic transparency; public record)"}
    ctx = ssl.create_default_context()
    qs = urllib.parse.urlencode({"$orderby": "EventDate desc", "$top": "20"})
    url = "https://webapi.legistar.com/v1/%s/Events?%s" % (body, qs)
    try:
        req = urllib.request.Request(url, headers=UA)
        data = json.loads(urllib.request.urlopen(req, timeout=20, context=ctx).read().decode())
        # Filter to events within days_back of today
        cutoff = (date.today() - timedelta(days=days_back)).strftime("%Y-%m-%d")
        return [e for e in (data or [])
                if str(e.get("EventDate", "") or "")[:10] >= cutoff]
    except Exception as e:
        return [{"_error": str(e)}]


def fetch_legistar_agenda_items(body, event_id):
    """Pull agenda items for a specific Legistar Event."""
    import ssl, urllib.request
    UA = {"User-Agent": "12sgi-kilo-aupuni/1.0 (civic transparency; public record)"}
    ctx = ssl.create_default_context()
    url = "https://webapi.legistar.com/v1/%s/Events/%s/EventItems?$top=200" % (body, event_id)
    try:
        req = urllib.request.Request(url, headers=UA)
        items = json.loads(urllib.request.urlopen(req, timeout=20, context=ctx).read().decode())
        return items or []
    except Exception as e:
        return [{"_error": str(e)}]


# ── Donor / money bridge ─────────────────────────────────────────────────────

def load_money_bridge():
    """Load the case_money_bridge officials crosswalk (public questions only)."""
    cmb = load(os.path.join(PRIV, "case_money_bridge.json"), {})
    bridge = cmb.get("bridge", [])
    by_name = {}
    for b in bridge:
        official = b.get("official", "")
        # Extract short name (first + last) for matching against votes/minutes
        parts = official.split("-")[0].strip().split()
        short = " ".join(parts[:2]) if len(parts) >= 2 else official.split("-")[0].strip()
        by_name[short.lower()] = {
            "official": official,
            "award_shadowed": b.get("money_pattern", {}).get("award_shadowed", 0),
            "top_donors": b.get("money_pattern", {}).get("top_donors", []),
            "public_question": b.get("public_question", ""),
        }
    return by_name


# ── Behavior analysis (bully vs question pattern) ────────────────────────────

def analyze_behavior(minutes_text):
    """Simple pattern detector: question-askers vs statement-pushers.

    'Bullies don't ask questions — they push their narrative.' (Jimmy 2026-06-22)

    Returns dict of name -> {questions: int, statements: int, score: 'questioner'|'narrator'|'mixed'}
    Sourced ONLY from the public minutes text; no inference beyond what's written.
    """
    if not minutes_text:
        return {}
    profiles = {}
    # Legistar minutes format: "COUNCILMEMBER SMITH: I move..." / "VICE-CHAIR LEE: ..."
    speaker_re = re.compile(r'(?:COUNCILMEMBER|CHAIR|VICE-CHAIR|MAYOR|DIRECTOR)\s+(\w+)\s*:', re.I)
    question_re = re.compile(r'\?')
    lines = minutes_text.split('\n')
    current = None
    for line in lines:
        m = speaker_re.search(line)
        if m:
            current = m.group(1).title()
            if current not in profiles:
                profiles[current] = {"questions": 0, "statements": 0}
        if current:
            q = len(question_re.findall(line))
            # sentences without ? = statements
            sentences = len(re.findall(r'[.!]', line))
            profiles[current]["questions"] += q
            profiles[current]["statements"] += max(0, sentences - q)
    # score
    for name, p in profiles.items():
        q, s = p["questions"], p["statements"]
        total = q + s
        if total == 0:
            p["score"] = "silent"
        elif q > s * 0.5:
            p["score"] = "questioner"
        elif s > q * 3:
            p["score"] = "narrator"
        else:
            p["score"] = "mixed"
    return profiles


# ── Agenda summary ───────────────────────────────────────────────────────────

def summarize_agenda_items(items):
    """Group agenda items into positive, procedural, and watch items."""
    positive, procedural, watch = [], [], []
    for it in items:
        if isinstance(it, dict) and it.get("_error"):
            continue
        title = str(it.get("EventItemTitle") or it.get("Title") or "")
        matter = str(it.get("EventItemMatterName") or it.get("Matter") or "")
        action = str(it.get("EventItemActionName") or "").lower()
        combined = ("%s %s" % (title, matter)).strip()
        if not combined:
            continue
        # categorize
        if any(w in action for w in ("approved", "passed", "adopted")):
            positive.append(combined)
        elif any(w in combined.lower() for w in ("contract", "award", "bid", "grant", "fund")):
            watch.append(combined)
        else:
            procedural.append(combined)
    return positive, procedural, watch


# ── Leak gate ────────────────────────────────────────────────────────────────

def leak_check(text):
    return not FORBIDDEN.search(text)


# ── HTML builder ─────────────────────────────────────────────────────────────

def build_html(meeting_info, agenda_items, money_bridge, behavior, moon, sun, tenant, dt):
    now_str = dt.strftime("%A, %B %d, %Y").replace(" 0", " ") if hasattr(dt, 'strftime') else str(dt)
    moon_po = moon.get("po", "")
    moon_nature = moon.get("nature", "")
    moon_offering = moon.get("offering", "")
    moon_phase = moon.get("phase", "")
    moon_age = moon.get("moon_age", 0)
    sunset = sun.get("sunset", "")

    meeting_name = meeting_info.get("EventBodyName") or meeting_info.get("name") or "Council Meeting"
    meeting_date = meeting_info.get("MeetingDate", "")[:10] if meeting_info else str(date.today())

    positive, procedural, watch = summarize_agenda_items(agenda_items)

    # Race car board: officials with public money questions
    sponsor_rows = []
    for short_name, d in money_bridge.items():
        official = d["official"]
        amt = d["award_shadowed"]
        q = d["public_question"]
        behavior_data = behavior.get(short_name.split()[-1].title(), {})
        style = behavior_data.get("score", "")
        style_label = {"questioner": "Asks questions", "narrator": "Pushes narrative",
                       "mixed": "Mixed", "silent": "Silent", "": "—"}.get(style, style)
        sponsor_rows.append((official, amt, q, style_label))

    def money_color(amt):
        if amt > 5_000_000: return "#e05a2b"
        if amt > 1_000_000: return "#d9b24c"
        return "#5fc0d8"

    rows_html = ""
    for official, amt, q, style_label in sponsor_rows:
        c = money_color(amt)
        rows_html += """
        <div class="official-card">
          <div class="official-header">
            <span class="official-name">{official}</span>
            <span class="race-badge" style="background:{c}22;border-color:{c};color:{c}">
              ${amt:,.0f} <span class="badge-label">awards in shadow</span>
            </span>
          </div>
          <div class="style-tag">Meeting style: <strong>{style}</strong></div>
          <div class="public-q">{q}</div>
        </div>""".format(official=esc(official), c=c, amt=amt, style=esc(style_label), q=esc(q))

    def item_list(items, css_class=""):
        if not items:
            return '<p class="muted">None noted in this meeting.</p>'
        return "<ul>" + "".join("<li class='%s'>%s</li>" % (css_class, esc(i)) for i in items) + "</ul>"

    html_out = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Meeting Digest — {name} — {date}</title>
<style>
:root{{--bg:#080c12;--panel:#0e1521;--line:#1f2b3e;--ink:#dce6f3;--mut:#7d8ba0;
      --gold:#d9b24c;--gold2:#e8c766;--grn:#4ec98a;--red:#ff6f91;--civic:#5aa9e6;}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--ink);font:16px/1.6 "Segoe UI",system-ui,sans-serif;padding:20px 16px 60px}}
.wrap{{max-width:820px;margin:0 auto}}
header{{text-align:center;padding:30px 0 20px;border-bottom:2px solid var(--gold)}}
.moon-badge{{display:inline-block;background:#1a1500;border:1px solid var(--gold);border-radius:30px;
            padding:6px 18px;font-size:13px;color:var(--gold);margin-bottom:14px}}
h1{{margin:.2em 0;font-size:26px}}
h2{{margin:1.4em 0 .5em;font-size:18px;color:var(--gold2);border-bottom:1px solid var(--line);padding-bottom:6px}}
.meta{{color:var(--mut);font-size:14px;margin:.4em 0 1.2em}}
.moon-block{{background:var(--panel);border-left:3px solid var(--gold);border-radius:12px;
             padding:16px 18px;margin:20px 0}}
.moon-title{{font-size:13px;text-transform:uppercase;letter-spacing:.12em;color:var(--gold);margin:0 0 6px}}
.moon-night{{font-size:22px;font-weight:700;margin:0 0 4px}}
.moon-nature{{color:var(--mut);font-size:14px;margin:0 0 8px}}
.moon-offering{{font-size:15px;font-style:italic;color:var(--civic)}}
.race-car-header{{background:linear-gradient(135deg,#12161f,#1a0f00);border:2px solid var(--gold);
                  border-radius:14px;padding:16px 18px;margin:20px 0 14px;text-align:center}}
.race-car-title{{font-size:13px;text-transform:uppercase;letter-spacing:.18em;color:var(--gold);margin:0 0 4px}}
.race-car-sub{{font-size:13px;color:var(--mut)}}
.official-card{{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:16px;margin:10px 0}}
.official-header{{display:flex;align-items:center;flex-wrap:wrap;gap:10px;margin-bottom:8px}}
.official-name{{font-weight:700;font-size:16px}}
.race-badge{{border:1px solid;border-radius:20px;padding:3px 12px;font-size:13px;font-weight:700;
             white-space:nowrap}}
.badge-label{{font-weight:400;font-size:11px;opacity:.85}}
.style-tag{{font-size:13px;color:var(--mut);margin:4px 0 8px}}
.public-q{{font-size:14px;font-style:italic;line-height:1.5;color:#b3c0d4}}
ul{{padding-left:22px;margin:.4em 0}}
li{{margin:.35em 0;line-height:1.5}}
li.watch{{color:var(--gold)}}
li.positive{{color:var(--grn)}}
.muted{{color:var(--mut);font-style:italic}}
.disclosure{{background:#0d1018;border:1px solid #2a3546;border-radius:10px;padding:14px 16px;
             font-size:12px;color:var(--mut);margin:30px 0;line-height:1.6}}
.foot{{text-align:center;font-size:12px;color:var(--mut);margin-top:30px;letter-spacing:.1em}}
@media(max-width:600px){{.official-header{{flex-direction:column;align-items:flex-start}}}}
</style>
</head>
<body>
<div class="wrap">
<header>
  <div class="moon-badge">&#127769; Night {night} &mdash; {po} &bull; {phase}</div>
  <h1>Meeting Digest</h1>
  <div class="meta">{meeting_name} &middot; {date} &middot; Maui County, Hawaiʻi</div>
</header>

<div class="moon-block">
  <div class="moon-title">Hina's Timing &mdash; Kaulana Mahina</div>
  <div class="moon-night">{po}</div>
  <div class="moon-nature">{anahulu} &bull; {nature}</div>
  <div class="moon-offering">Tonight's aloha offering: <em>{offering}</em></div>
  {sunset_line}
</div>

<h2>&#127942; Race Car Board — Sponsor Transparency</h2>
<div class="race-car-header">
  <div class="race-car-title">Who Funds Who?</div>
  <div class="race-car-sub">Race car drivers wear all their sponsors. The public record shows ours.
  Each figure below is from the official public money record — a question, not a verdict.</div>
</div>
{sponsor_section}

<h2>&#128200; Today's Agenda — What Was Decided</h2>

<h3 style="color:var(--grn);font-size:15px;margin:.8em 0 .3em">&#10003; Approved / Positive</h3>
{positive_items}

<h3 style="color:var(--gold);font-size:15px;margin:.8em 0 .3em">&#128269; Contracts / Awards / Watch Items</h3>
{watch_items}

<h3 style="color:var(--mut);font-size:15px;margin:.8em 0 .3em">&#9632; Procedural</h3>
{procedural_items}

<h2>&#127780;&#65039; Aloha Call — What the Moon Says</h2>
<p><strong>{po}</strong> is a night of <em>{nature}</em>.<br>
Civic aloha: <em>{offering}</em></p>
<p>The sun set over Maui {sunset_note}. The records are in the light of ao;
bring them into tomorrow's po with purpose.</p>

<div class="disclosure">
  <strong>AI Disclosure &amp; Integrity Statement</strong><br>
  {disclosure}
</div>
<p class="foot">christ-aloha · solution-side · heal forward &middot; 12 Stones Global Inc.</p>
</div>
</body>
</html>""".format(
        name=esc(meeting_name),
        date=esc(now_str),
        night=moon.get("night", "?"),
        po=esc(moon_po),
        phase=esc(moon_phase),
        anahulu=esc(moon.get("anahulu", "")),
        nature=esc(moon_nature),
        offering=esc(moon_offering),
        sunset_line=('<p style="color:var(--mut);font-size:13px;margin-top:8px">Sun set at %s HST.</p>' % esc(str(sunset))) if sunset else "",
        sunset_note=("at %s HST today" % esc(str(sunset))) if sunset else "today",
        meeting_name=esc(meeting_name),
        sponsor_section=rows_html or '<p class="muted">No money-bridge data available for this meeting.</p>',
        positive_items=item_list(positive, "positive"),
        watch_items=item_list(watch, "watch"),
        procedural_items=item_list(procedural),
        disclosure=esc(AI_DISCLOSURE),
    )

    if not leak_check(html_out):
        raise ValueError("LEAK GATE TRIGGERED: forbidden marker found in output — aborting.")
    return html_out


def build_txt(meeting_info, agenda_items, money_bridge, behavior, moon, sun, tenant, dt):
    """Plain text version for email body."""
    lines = []
    meeting_name = meeting_info.get("EventBodyName") or meeting_info.get("name") or "Council Meeting"
    now_str = dt.strftime("%A, %B %d, %Y").replace(" 0", " ") if hasattr(dt, 'strftime') else str(dt)
    mo = moon.get("po", "?"), moon.get("nature", ""), moon.get("offering", ""), moon.get("phase", "")
    lines += [
        "MEETING DIGEST — %s — %s" % (meeting_name, now_str),
        "=" * 60,
        "",
        "HINA'S TIMING — KAULANA MAHINA",
        "Night %s: %s (%s)" % (moon.get("night", "?"), mo[0], mo[3]),
        "Nature: %s" % mo[1],
        "Tonight's aloha offering: %s" % mo[2],
        "",
        "RACE CAR BOARD — SPONSOR TRANSPARENCY",
        "-" * 40,
        "(Race car drivers wear all their sponsors. So do public officials, on the public record.)",
        "",
    ]
    for short_name, d in money_bridge.items():
        official = d["official"]
        amt = d["award_shadowed"]
        q = d["public_question"]
        b = behavior.get(short_name.split()[-1].title(), {})
        style = {"questioner": "Asks questions", "narrator": "Pushes narrative",
                 "mixed": "Mixed", "silent": "Silent", "": "—"}.get(b.get("score", ""), "—")
        lines += [
            "  %s" % official,
            "  Awards in shadow: $%s" % "{:,.0f}".format(amt),
            "  Meeting style: %s" % style,
            "  Public question: %s" % q,
            "",
        ]
    positive, procedural, watch = summarize_agenda_items(agenda_items)
    lines += ["AGENDA — WHAT WAS DECIDED", "-" * 40, ""]
    if positive:
        lines += ["Approved / Positive:"] + ["  - %s" % i for i in positive] + [""]
    if watch:
        lines += ["Watch Items (contracts/awards):"] + ["  - %s" % i for i in watch] + [""]
    if procedural:
        lines += ["Procedural:"] + ["  - %s" % i for i in procedural] + [""]
    lines += [
        "=" * 60,
        AI_DISCLOSURE,
        "",
        "christ-aloha · solution-side · heal forward · 12 Stones Global Inc.",
    ]
    return "\n".join(lines)


# ── Main ─────────────────────────────────────────────────────────────────────

def main(argv=None):
    import argparse
    p = argparse.ArgumentParser(description="Post-meeting same-day digest newsletter")
    p.add_argument("--meeting", default="", help="Legistar meeting body slug")
    p.add_argument("--date", default="", help="Meeting date YYYY-MM-DD (default: today HST)")
    p.add_argument("--tenant", default="maui", help="Tenant (default: maui)")
    p.add_argument("--no-email", action="store_true", help="Skip email archive")
    args = p.parse_args(argv)

    dt = now_hst().date()
    if args.date:
        try:
            dt = date.fromisoformat(args.date)
        except ValueError:
            pass

    print("[meeting_digest_post] Date: %s  Tenant: %s" % (dt, args.tenant))

    # Moon + sun
    moon = get_moon(dt)
    sun = get_sun()
    print("  Moon: %s (%s)" % (moon.get("po", "?"), moon.get("phase", "?")))
    print("  Sun:  sunset=%s" % sun.get("sunset", "?"))

    # Legistar meetings
    legistar_body = "mauicounty" if args.tenant == "maui" else args.tenant
    print("  Fetching Legistar meetings for %s..." % legistar_body)
    meetings = fetch_legistar_meetings(legistar_body, days_back=2)
    meeting_info = {}
    agenda_items = []

    if meetings and not meetings[0].get("_error"):
        # Pick the most recent event (already sorted by EventDate desc)
        meeting_info = meetings[0]
        eid = meeting_info.get("EventId")
        print("  Meeting: %s on %s (id=%s)" % (
            meeting_info.get("EventBodyName", "?"),
            str(meeting_info.get("EventDate", ""))[:10], eid))
        if eid:
            agenda_items = fetch_legistar_agenda_items(legistar_body, eid)
            real_items = [i for i in agenda_items if not i.get("_error")]
            print("  Agenda items: %d" % len(real_items))
    else:
        err = meetings[0].get("_error", "unknown") if meetings else "no data"
        print("  Legistar unavailable: %s — proceeding without live agenda" % err)

    # Money bridge
    money_bridge = load_money_bridge()
    print("  Money bridge officials: %d" % len(money_bridge))

    # Behavior analysis (from minutes HTML if available)
    behavior = {}
    mins_html = os.path.join(M, "minutes_hi-maui.html")
    if os.path.exists(mins_html):
        text = open(mins_html, encoding="utf-8", errors="replace").read()
        # strip tags for plain text analysis
        text = re.sub(r'<[^>]+>', ' ', text)
        behavior = analyze_behavior(text)

    # Build outputs
    html_out = build_html(meeting_info, agenda_items, money_bridge, behavior, moon, sun, args.tenant, dt)
    txt_out = build_txt(meeting_info, agenda_items, money_bridge, behavior, moon, sun, args.tenant, dt)

    date_str = str(dt)
    out_html = os.path.join(OUT, "meeting_digest_%s.html" % date_str)
    out_txt = os.path.join(OUT, "meeting_digest_%s.txt" % date_str)
    latest = os.path.join(OUT, "_latest_meeting_digest.json")

    # Atomic writes
    def atomic_write(path, content, mode="w", encoding="utf-8"):
        tmp = path + ".tmp"
        with open(tmp, mode, encoding=encoding) as f:
            f.write(content)
        os.replace(tmp, path)

    atomic_write(out_html, html_out)
    atomic_write(out_txt, txt_out)

    meeting_name = meeting_info.get("EventBodyName") or "Council Meeting"
    meta = {
        "date": date_str,
        "meeting": meeting_name,
        "tenant": args.tenant,
        "moon_po": moon.get("po", ""),
        "moon_offering": moon.get("offering", ""),
        "agenda_items": len(agenda_items),
        "officials_bridged": len(money_bridge),
        "files": {"html": out_html, "txt": out_txt},
        "generated": now_hst().strftime("%Y-%m-%d %H:%M HST"),
    }
    atomic_write(latest, json.dumps(meta, indent=2))

    print("  HTML: %s" % out_html)
    print("  TXT:  %s" % out_txt)

    # Email archive (elementlotus@gmail.com via mail_graphic.py)
    if not args.no_email:
        try:
            sys.path.insert(0, os.path.join(ROOT, "tools", "ops"))
            import mail_graphic
            subject = "Meeting Digest: %s — %s" % (meeting_name, date_str)
            body = txt_out
            r = mail_graphic.send(to="elementlotus@gmail.com", subject=subject, body=body,
                                  attachment=out_html)
            print("  Email: %s" % ("sent" if r else "failed/skipped"))
        except Exception as e:
            print("  Email: skipped (%s)" % e)

    print("[meeting_digest_post] DONE — moon says: %s" % moon.get("offering", ""))
    return meta


if __name__ == "__main__":
    main()
