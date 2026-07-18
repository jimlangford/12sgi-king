#!/usr/bin/env python3
"""meeting_newsletter.py — the GOLDEN LISTENER meeting digest (Jimmy 2026-06-22 command).

For a specific Legistar meeting: pulls the agenda items, overlays each attending official's
campaign donor sponsors (race-car format — every council voice shows who funds it), adds moon
timing (kaulana mahina), and generates a public-safe newsletter in HTML + TXT.

INTEGRITY: 100% public records — Legistar (agendas), Hawaii CSC (campaign finance). Donor→vote
proximity framed as QUESTIONS, never accusations. Private prosecutorial theory stays in the
prosecutor lane; this newsletter is AO/PONO (good light, visible truth).

RACE-CAR FORMAT: each official's top donors listed like a race car driver's sponsors — so the
public can see exactly who is in the room economically when a vote is cast. Source: CSC.

Usage:
  python meeting_newsletter.py                        # most recent past Maui meeting
  python meeting_newsletter.py --date 2026-06-22
  python meeting_newsletter.py --event-id 4806
  python meeting_newsletter.py --body "Government Relations"
"""
import os, sys, json, re, html, math, argparse, urllib.request
from datetime import date, datetime, timezone, timedelta

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HERE    = os.path.dirname(os.path.abspath(__file__))
PROJ    = os.path.dirname(os.path.dirname(HERE))
OUT     = os.path.join(PROJ, "reports", "mauios", "newsletter"); os.makedirs(OUT, exist_ok=True)
HST     = timezone(timedelta(hours=-10))
LEGISTAR = "https://webapi.legistar.com/v1/mauicounty"
DONORS_F = os.path.join(PROJ, "reports", "mauios", "donor_profiles.json")
esc     = lambda s: html.escape(str(s or ""))

FORBIDDEN = re.compile(r"sk_live|rk_live|whsec_|prosecut|case_file|/king|oversight_|password|api_token|"
                       r"webhook_secret|reports/_status|recusal", re.I)

# ── MOON CALENDAR (inline subset — avoids import path issues) ──────────────────
SYNODIC = 29.530588853
_REF_JD = 2451550.1   # 2000-01-06 new moon

_PO = [
    ("Hilo",      "first crescent; new beginnings",     "plant the intention — learn the item before you speak"),
    ("Hoaka",     "faint light; casting of shadows",    "gather facts before the vote casts its shadow"),
    ("Kūkahi",    "Kū — upright; good for planting",    "stand and be counted — a good night to testify"),
    ("Kūlua",     "Kū — productive",                    "stand together — add your voice to the record"),
    ("Kūkolu",    "Kū — productive",                    "keep showing up — upright nights favor those who do"),
    ("Kūpau",     "Kū ends; transition",                "wrap the argument neatly before the tide turns"),
    ("ʻOlekūkahi","Kū rests; a night of pause",         "listen before speaking — a night for absorbing"),
    ("ʻOlelua",   "rest continues",                     "read the agenda; understand before you arrive"),
    ("ʻOlekolu",  "rest; the lull before the light",    "preparation night — gather your evidence"),
    ("ʻOlepau",   "transition to the round nights",     "the gathering is forming; bring your community"),
    ("Huna",      "Kāne rules; fish leap, planting good","the waters of truth are up — speak plainly"),
    ("Mohalu",    "moon softening toward full",          "relationships matter; build the coalition"),
    ("Hua",       "full light coming; growth, harvest",  "your words bear fruit — speak from the facts"),
    ("Akua",      "the god's night; powerful light",     "the record is lit — every word is visible"),
    ("Hoku",      "full moon; maximum clarity",          "fullest light on the vote — ask the hard question"),
    ("Māhealani", "full moon; clarity + reflection",    "the public record is brightest — document everything"),
    ("Kulu",      "waning begins; moon past peak",       "what was said is now the record — hold it"),
    ("Lāʻau-kūkahi","Lāʻau — firm, forceful",           "make your motion; the moon backs clear action"),
    ("Lāʻau-lua", "Lāʻau — firm",                       "follow through on the motion"),
    ("Lāʻau-pau", "Lāʻau ends",                         "close the argument before the energy fades"),
    ("ʻOleʻkūkahi","waning rest",                       "let the minutes be written; witness mode"),
    ("ʻOlelua",   "waning rest",                        "prepare for the next meeting"),
    ("ʻOlepau",   "waning, calm",                       "review what passed; note what was avoided"),
    ("Kāloa-kūkahi","Kanaloa — the deep; restoration",  "the ocean asks what was missed; seek the gap"),
    ("Kāloa-lua", "Kanaloa — restoration",              "restoration night — call out what was omitted"),
    ("Kāloa-pau", "Kanaloa — ends",                     "name what needs correcting before the cycle closes"),
    ("Kāne",      "Kāne — life-giver; water/planting",  "life-giving clarity — advocate for the people"),
    ("Lono",      "Lono — harvest, peace, song",        "a Makahiki peace — speak for the long-term good"),
    ("Mauli",     "the soul; threshold",                "the threshold night — what will carry forward?"),
    ("Muku",      "dark moon; rest, endings",           "rest and discernment — what ends here must end cleanly"),
]

def moon_phase(d: date):
    jd = 367 * d.year - int(7 * (d.year + int((d.month + 9) / 12)) / 4) + int(275 * d.month / 9) + d.day + 1721013.5
    age_days = (jd - _REF_JD) % SYNODIC
    idx = min(int(age_days / SYNODIC * 30), 29)
    po = _PO[idx]
    pct = age_days / SYNODIC * 100
    phase = ("🌑 New" if pct < 3 else "🌒 Waxing crescent" if pct < 25 else
             "🌓 First quarter" if pct < 35 else "🌔 Waxing gibbous" if pct < 47 else
             "🌕 Full" if pct < 53 else "🌖 Waning gibbous" if pct < 65 else
             "🌗 Last quarter" if pct < 75 else "🌘 Waning crescent" if pct < 97 else "🌑 Dark")
    return {"name": po[0], "nature": po[1], "civic": po[2], "phase": phase, "age_pct": round(pct)}

# ── SPEECH / BULLY ANALYSIS ───────────────────────────────────────────────────
# "Bullies don't ask questions — they push their narrative." (Jimmy)
# Questions: end in "?" OR start with an interrogative word. Everything else = statement push.
_Q_OPENS = re.compile(
    r"^(do|does|did|is|are|was|were|can|could|will|would|should|have|has|had|"
    r"what|when|where|why|how|who|which|isn't|aren't|wasn't|weren't|don't|doesn't)\b",
    re.I)
_SPEAKER_HDR = re.compile(
    r"^(?:COUNCIL ?MEMBER|CHAIR|VICE[- ]?CHAIR|COUNCILWOMAN|COUNCILMAN|MR\.|MS\.|"
    r"MAYOR|DEPUTY)\s+([A-Z][A-Z'\- ]{2,}?)\s*:",
    re.I | re.M)

def analyze_speech(text):
    """
    Parse a meeting transcript by speaker, classify utterances as questions vs statements.
    Returns {surname: {questions, statements, q_ratio, style, sample_questions}}.
    Framed as observation — speech STYLE, not character judgment.
    """
    if not text:
        return {}
    parts = _SPEAKER_HDR.split(text)
    blocks = {}
    for i in range(1, len(parts) - 1, 2):
        surname = parts[i].strip().split()[0].title()
        body = parts[i + 1] if i + 1 < len(parts) else ""
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", body) if len(s.strip()) > 10]
        q, s, sample_qs = 0, 0, []
        for sent in sentences:
            if sent.endswith("?") or _Q_OPENS.match(sent):
                q += 1
                if len(sample_qs) < 3:
                    sample_qs.append(sent[:120].rstrip(".!?") + "?")
            else:
                s += 1
        if surname not in blocks:
            blocks[surname] = {"questions": 0, "statements": 0, "sample_questions": []}
        blocks[surname]["questions"]  += q
        blocks[surname]["statements"] += s
        blocks[surname]["sample_questions"].extend(sample_qs[:3])
    # Compute style label
    for sur, d in blocks.items():
        total = d["questions"] + d["statements"]
        ratio = d["questions"] / total if total else 0
        d["q_ratio"] = round(ratio * 100)
        d["style"] = (
            "dialogue-forward (%d%% questions)" % d["q_ratio"] if ratio >= 0.35 else
            "mixed (%d%% questions)"             % d["q_ratio"] if ratio >= 0.15 else
            "statement-heavy (%d%% questions)"   % d["q_ratio"]
        )
    return blocks

def _speech_html(speech):
    if not speech:
        return ""
    rows = ""
    for sur, d in sorted(speech.items(), key=lambda x: -x[1]["questions"]):
        q, s = d["questions"], d["statements"]
        total = q + s
        if total < 2:
            continue
        q_pct = round(q / total * 100) if total else 0
        bar_color = "#2e8b57" if q_pct >= 35 else "#b07d1a" if q_pct >= 15 else "#8b2e2e"
        sample = "".join(
            f"<div style='color:#8ab4d0;font-size:11px;margin:.15rem 0;'>❝ {esc(sq)}</div>"
            for sq in d.get("sample_questions", [])[:2]
        )
        rows += (
            f"<div style='margin:10px 0;padding:12px 14px;background:#081624;border-left:3px solid {bar_color};border-radius:6px;'>"
            f"<div style='font-weight:700;color:#c8d8e8;'>{esc(sur)} "
            f"<span style='font-weight:400;font-size:.85rem;color:#8a97a6;'>— {esc(d['style'])}</span></div>"
            f"<div style='display:flex;gap:18px;margin:.4rem 0;font-size:.85rem;'>"
            f"<span style='color:#5fc0d8;'>🙋 {q} questions</span>"
            f"<span style='color:#8a97a6;'>📢 {s} statements</span>"
            f"</div>"
            f"{sample}"
            f"</div>"
        )
    if not rows:
        return ""
    return (
        "<h2 style='color:#7ec8f0;font-size:1rem;letter-spacing:.08em;text-transform:uppercase;"
        "border-bottom:1px solid #1a2e42;padding-bottom:.4rem;margin-top:1.6rem;'>"
        "🎙 Conversation Style — Questions vs Narrative Pushes</h2>"
        "<p style='font-size:.88rem;color:#8a97a6;'>"
        "Accountability leaders ask questions. Narrative pushers make statements. "
        "This is an observational pattern from the public meeting transcript — not a verdict.</p>"
        + rows
    )

# ── SUN TIMING (inline — avoids cross-dir import) ─────────────────────────────
def _sun_info(d=None):
    """Current Maui sun context (HST). Returns dict with sunset time and a simple framing."""
    import math as _m, datetime as _dt
    HST_ = _dt.timezone(_dt.timedelta(hours=-10))
    if d is None:
        d = _dt.datetime.now(HST_).date()
    lat, lon_w = 20.8911, 156.5047
    a = (14 - d.month) // 12; y = d.year + 4800 - a; mo = d.month + 12 * a - 3
    jdn = d.day + (153 * mo + 2) // 5 + 365 * y + y // 4 - y // 100 + y // 400 - 32045
    n = jdn - 2451545.0 + 0.0008
    Jstar = n + lon_w / 360.0
    M = (357.5291 + 0.98560028 * Jstar) % 360.0
    C = 1.9148 * _m.sin(_m.radians(M)) + 0.0200 * _m.sin(_m.radians(2*M)) + 0.0003 * _m.sin(_m.radians(3*M))
    lam = (M + C + 180.0 + 102.9372) % 360.0
    Jtransit = 2451545.0 + Jstar + 0.0053 * _m.sin(_m.radians(M)) - 0.0069 * _m.sin(_m.radians(2*lam))
    dec = _m.degrees(_m.asin(_m.sin(_m.radians(lam)) * _m.sin(_m.radians(23.4397))))
    ha_cos = (_m.cos(_m.radians(90.833)) - _m.sin(_m.radians(lat)) * _m.sin(_m.radians(dec))) / \
             (_m.cos(_m.radians(lat)) * _m.cos(_m.radians(dec)))
    ha_cos = max(-1.0, min(1.0, ha_cos))
    ha = _m.degrees(_m.acos(ha_cos)) / 360.0
    Jset = Jtransit + ha
    # Convert to HST datetime
    Jset_frac = (Jset - int(Jset)) - 0.5   # fraction of day from noon UTC
    ss_utc = _dt.datetime(*d.timetuple()[:3], tzinfo=_dt.timezone.utc) + _dt.timedelta(days=Jset - (jdn - 0.5))
    ss_hst = ss_utc.astimezone(HST_)
    now_hst_ = _dt.datetime.now(HST_)
    after = now_hst_ > ss_hst
    return {
        "sunset": ss_hst.strftime("%I:%M %p"),
        "after_sunset": after,
        "phrasing": (
            f"The sun set at {ss_hst.strftime('%I:%M %p')} HST. We are in the pō — the Hawaiian night belongs to the COMING day. "
            "In the kaulana mahina, the new day has already begun."
        ) if after else (
            f"The sun sets at {ss_hst.strftime('%I:%M %p')} HST today over Maui. "
            "The current Hawaiian day continues until that moment — the pō (night) that follows belongs to tomorrow."
        )
    }

# ── LEGISTAR ──────────────────────────────────────────────────────────────────
def _get(url, timeout=12):
    try:
        return json.loads(urllib.request.urlopen(url, timeout=timeout).read())
    except Exception:
        return None

def fetch_event(event_id=None, target_date=None, body_substr=None):
    if event_id:
        ev = _get(f"{LEGISTAR}/Events/{event_id}")
        if ev:
            items = _get(f"{LEGISTAR}/Events/{event_id}/EventItems?AgendaNote=1") or []
            return ev, items
    if target_date:
        dt = target_date
    else:
        dt = datetime.now(HST).date()
    lo = f"{dt}T00:00:00"
    hi = f"{dt}T23:59:59"
    evs = _get(f"{LEGISTAR}/Events?$filter=EventDate+ge+datetime'{lo}'+and+EventDate+le+datetime'{hi}'&$orderby=EventDate") or []
    if body_substr:
        evs = [e for e in evs if body_substr.lower() in (e.get("EventBodyName") or "").lower()]
    if not evs:
        for delta in range(1, 8):
            back = dt - timedelta(days=delta)
            lo2, hi2 = f"{back}T00:00:00", f"{back}T23:59:59"
            evs = _get(f"{LEGISTAR}/Events?$filter=EventDate+ge+datetime'{lo2}'+and+EventDate+le+datetime'{hi2}'&$orderby=EventDate") or []
            if evs:
                break
    if not evs:
        return None, []
    ev = evs[0]
    items = _get(f"{LEGISTAR}/Events/{ev['EventId']}/EventItems?AgendaNote=1") or []
    return ev, items

def fetch_roll_calls(item_id):
    """
    Fetch the vote roll call for one agenda item from Legistar.
    Returns {ayes: [name,...], noes: [name,...], abstain: [name,...]} or {} if none.
    Source: Legistar public API — 100% public record.
    """
    data = _get(f"{LEGISTAR}/EventItems/{item_id}/RollCalls")
    if not data:
        return {}
    ayes, noes, abstain = [], [], []
    for rc in data:
        person = (rc.get("RollCallPersonName") or rc.get("PersonName") or "").strip()
        vote   = (rc.get("RollCallValueName") or rc.get("VoteName") or "").lower()
        if not person:
            continue
        # Normalize: Legistar uses "Yea"/"Aye"/"Yes" / "Nay"/"No" / "Abstain"
        if any(v in vote for v in ("yea", "aye", "yes")):
            ayes.append(person)
        elif any(v in vote for v in ("nay", "no")):
            noes.append(person)
        elif "abstain" in vote:
            abstain.append(person)
    if not (ayes or noes or abstain):
        return {}
    return {"ayes": ayes, "noes": noes, "abstain": abstain}

# ── DONOR PROFILES ─────────────────────────────────────────────────────────────
def load_donors():
    try:
        profiles = json.load(open(DONORS_F, encoding="utf-8"))
        return {p["key"]: p for p in profiles}
    except Exception:
        return {}

def format_money(v):
    try:
        return "${:,.0f}".format(float(v))
    except Exception:
        return str(v)

def official_sponsor_block(profile, html_mode=False):
    """Race-car format: who funds this voice."""
    top = (profile.get("top_donors") or [])[:5]
    total = profile.get("total") or profile.get("rows", 0)
    realestate = profile.get("realestate", {})
    re_total = realestate.get("total", 0) or 0

    lines = []
    if total:
        lines.append(f"Total raised: {format_money(total)} from {profile.get('rows', '?')} contributions")
    for d in top:
        name = d.get("name") or "Unknown"
        amt  = d.get("amount") or 0
        lines.append(f"  ▪ {name} — {format_money(amt)}")
    if re_total:
        pct = round(re_total / float(total or 1) * 100) if total else 0
        lines.append(f"  🏗 Real-estate/development sector: {format_money(re_total)} ({pct}%)")
    return lines

# ── NEWSLETTER BUILD ───────────────────────────────────────────────────────────
def build(event_id=None, target_date=None, body_substr=None, transcript_text=""):
    now_hst = datetime.now(HST)
    ev, items = fetch_event(event_id, target_date, body_substr)
    donors = load_donors()

    if ev:
        body_name = ev.get("EventBodyName") or "Maui County Committee"
        ev_date_str = (ev.get("EventDate") or "")[:10]
        ev_time = ev.get("EventTime") or ""
        ev_date = date.fromisoformat(ev_date_str) if ev_date_str else now_hst.date()
        legistar_url = ev.get("EventInSiteURL") or f"https://mauicounty.legistar.com/Calendar.aspx"
        title = f"{body_name} — {ev_date_str}"
    else:
        body_name = "Maui County Council"
        ev_date = target_date or now_hst.date()
        ev_date_str = ev_date.isoformat()
        ev_time = ""
        legistar_url = "https://mauicounty.legistar.com/Calendar.aspx"
        title = f"Meeting Digest — {ev_date_str}"
        items = []

    moon = moon_phase(ev_date)
    sun  = _sun_info(ev_date)

    # Speech analysis from transcript (if provided)
    speech = analyze_speech(transcript_text) if transcript_text else {}
    speech_html = _speech_html(speech)

    # Map body name to known officials
    BODY_MEMBERS = {
        "Budget Finance": ["Sugimura", "Batangan", "Cook", "Lee", "Uu-Hodgins"],
        "Government Relations": ["Lee", "Johnson", "Paltin", "Rawlins-Fernandez", "Sinenci"],
        "Planning": ["Paltin", "Cook", "Johnson", "Rawlins-Fernandez"],
        "Infrastructure": ["Sinenci", "Batangan", "Uu-Hodgins"],
    }
    body_key = next((k for k in BODY_MEMBERS if k.lower() in body_name.lower()), None)
    member_keys = BODY_MEMBERS.get(body_key, list(donors.keys()))

    # Build agenda items section — with roll call votes fetched per item
    agenda_items = []
    print("golden_listener: fetching roll calls per agenda item…")
    for it in (items or []):
        t = it.get("EventItemTitle") or it.get("EventItemMatterTitle") or ""
        action = it.get("EventItemActionText") or it.get("EventItemPassedText") or ""
        n = it.get("EventItemAgendaSequence") or ""
        if not t:
            continue
        item_id = it.get("EventItemId") or it.get("EventItemGuid")
        votes = fetch_roll_calls(item_id) if item_id else {}
        agenda_items.append({"n": n, "title": t, "action": action, "votes": votes})

    # ── HTML build ────────────────────────────────────────────────────────────
    # Member sponsor blocks
    sponsor_rows = ""
    sponsor_txt_lines = []
    for key in member_keys:
        prof = donors.get(key)
        if not prof:
            continue
        label = prof.get("label") or key
        name = label.split(" - ")[0] if " - " in label else label
        top = (prof.get("top_donors") or [])[:4]
        re_total = (prof.get("realestate") or {}).get("total") or 0
        total = prof.get("total") or 0
        sponsor_tags = "".join(
            f"<span style='display:inline-block;background:#1a3252;color:#a8c4e0;border-radius:4px;padding:2px 8px;font-size:12px;margin:2px;'>"
            f"{esc(d.get('name','?')[:30])} <b>{esc(format_money(d.get('amount',0)))}</b></span>"
            for d in top
        )
        re_badge = ""
        if re_total and total:
            pct = round(re_total / float(total) * 100)
            re_badge = f"<span style='background:#4a1a1a;color:#f59a9a;border-radius:4px;padding:2px 8px;font-size:11px;margin:2px;'>🏗 Development sector {format_money(re_total)} ({pct}%)</span>"
        # id anchor = member-{key} so agenda vote rows can link directly to their sponsor block
        anchor_id = "member-" + re.sub(r"[^\w]", "-", key.lower())
        sponsor_rows += (
            f"<div id='{anchor_id}' style='margin:14px 0;padding:14px 16px;background:#0a1824;border-left:3px solid #1e6fa0;border-radius:6px;'>"
            f"<div style='color:#7ec8f0;font-size:13px;font-weight:700;letter-spacing:.05em;margin-bottom:6px;'>{esc(name)}</div>"
            f"<div style='color:#8a97a6;font-size:11px;margin-bottom:8px;'>{esc(label)}</div>"
            f"<div style='margin-top:4px;'>{sponsor_tags}{re_badge}</div>"
            f"<div style='color:#9fb2c8;font-size:11px;margin-top:6px;'>Total raised: {esc(format_money(total))} from {prof.get('rows','?')} contributions — "
            f"<a href='https://hicscdata.hawaii.gov/' style='color:#5a8aac;'>source: HI Campaign Spending Commission</a></div>"
            f"</div>"
        )
        sponsor_txt_lines.append(f"  {name}: {format_money(total)} raised")
        for d in top[:3]:
            sponsor_txt_lines.append(f"    ▪ {d.get('name','?')[:40]} — {format_money(d.get('amount',0))}")

    # Agenda items HTML — votes displayed under each bill, yes-voters linked to their sponsor block
    def _vote_html(votes, donors_map, member_keys):
        """Render the yes/no vote roster under a bill. Yes voters link to their sponsor anchor."""
        if not votes:
            return ""
        def _voter_link(name):
            # Try to match the voter name to a known official key for anchor linking
            name_lower = name.lower()
            for key in member_keys:
                if key.lower().split("-")[0].split()[0] in name_lower or name_lower in key.lower():
                    anchor = "member-" + re.sub(r"[^\w]", "-", key.lower())
                    return f"<a href='#{anchor}' style='color:#7fe0ad;text-decoration:none;font-weight:600;'>{esc(name)}</a>"
            return f"<span style='color:#7fe0ad;'>{esc(name)}</span>"

        ayes    = votes.get("ayes", [])
        noes    = votes.get("noes", [])
        abstain = votes.get("abstain", [])
        rows = []
        if ayes:
            linked = ", ".join(_voter_link(n) for n in ayes)
            rows.append(
                f"<div style='margin:.3rem 0;font-size:.85rem;'>"
                f"<span style='color:#2e8b57;font-weight:700;'>✓ Ayes ({len(ayes)})</span>"
                f"<span style='color:#8a97a6;margin-left:6px;'>— sponsors above ↑</span><br>"
                f"<span style='margin-left:12px;'>{linked}</span></div>"
            )
        if noes:
            noe_names = ", ".join(f"<span style='color:#f59a9a;'>{esc(n)}</span>" for n in noes)
            rows.append(
                f"<div style='margin:.3rem 0;font-size:.85rem;'>"
                f"<span style='color:#f0857a;font-weight:700;'>✗ Noes ({len(noes)})</span><br>"
                f"<span style='margin-left:12px;'>{noe_names}</span></div>"
            )
        if abstain:
            abst_names = ", ".join(f"<span style='color:#8a97a6;'>{esc(n)}</span>" for n in abstain)
            rows.append(
                f"<div style='margin:.3rem 0;font-size:.85rem;'>"
                f"<span style='color:#8a97a6;font-weight:700;'>○ Abstain ({len(abstain)})</span><br>"
                f"<span style='margin-left:12px;'>{abst_names}</span></div>"
            )
        return (
            f"<div style='background:#040e1a;border-left:2px solid #1a3a1a;border-radius:4px;"
            f"padding:8px 12px;margin:.5rem 0;'>" + "".join(rows) + "</div>"
        )

    if agenda_items:
        agenda_html = "<div>"
        agenda_txt  = ""
        for i, it in enumerate(agenda_items, 1):
            action = it["action"]
            votes  = it.get("votes", {})
            passed = any(v in action.lower() for v in ("pass", "adopt", "approv")) if action else False
            failed = any(v in action.lower() for v in ("fail", "defeat", "reject")) if action else False
            action_color = "#2e8b57" if passed else "#c0392b" if failed else "#5fc0d8"
            action_icon  = "✓" if passed else "✗" if failed else "→"
            agenda_html += (
                f"<div style='margin:12px 0;padding:12px 14px;background:#081624;border-radius:6px;"
                f"border-left:3px solid {'#2e8b57' if passed else '#c0392b' if failed else '#1e6fa0'};'>"
                f"<div style='font-size:.9rem;color:#c8d8e8;font-weight:600;'>"
                f"<span style='color:#9fb2c8;font-size:.8rem;margin-right:6px;'>{esc(str(it['n'] or i))}.</span>"
                f"{esc(it['title'])}</div>"
            )
            if action:
                agenda_html += (
                    f"<div style='margin:.3rem 0;font-size:.8rem;'>"
                    f"<span style='color:{action_color};font-weight:700;'>{action_icon} {esc(action)}</span>"
                    f"</div>"
                )
            # Vote roster under the action
            agenda_html += _vote_html(votes, donors, member_keys)
            agenda_html += "</div>"
            agenda_txt += f"  {it['n'] or i}. {it['title']}"
            if action:
                agenda_txt += f" [{action}]"
            if votes.get("ayes"):
                agenda_txt += f"\n     Ayes: {', '.join(votes['ayes'])}"
            if votes.get("noes"):
                agenda_txt += f"\n     Noes: {', '.join(votes['noes'])}"
            agenda_txt += "\n"
        agenda_html += "</div>"
    else:
        agenda_html = f"<p style='color:#8a97a6;font-size:.9rem;'>Full agenda: <a href='{esc(legistar_url)}' style='color:#5fc0d8;'>{esc(legistar_url)}</a></p>"
        agenda_txt  = f"  See: {legistar_url}\n"

    html_issue = f"""<!doctype html><html lang=en><head><meta charset=utf-8>
<meta name=viewport content='width=device-width,initial-scale=1'>
<title>Golden Listener — {esc(title)}</title></head>
<body style='margin:0;background:#071320;font-family:system-ui,-apple-system,Roboto,sans-serif;color:#c8d8e8'>
<div style='max-width:640px;margin:0 auto;'>

<div style='background:#0e4a84;padding:1.4rem 1.6rem;'>
  <div style='font-size:.75rem;letter-spacing:.15em;color:#7ec8f0;opacity:.9'>12SGI · KILO AUPUNI · GOLDEN LISTENER</div>
  <div style='font-size:1.3rem;font-weight:700;color:#fff;margin:.3rem 0 .1rem'>{esc(body_name)}</div>
  <div style='font-size:.9rem;color:#a8c4e0;'>{esc(ev_date_str)}{(' at ' + ev_time) if ev_time else ''}</div>
  <div style='font-size:.78rem;color:#7ec8f0;margin-top:.4rem;'>{moon['phase']} · Pō {esc(moon['name'])} · {esc(moon['civic'])}</div>
</div>

<div style='padding:1.4rem 1.6rem;'>

<p style='font-size:.95rem;line-height:1.6;color:#a8c4e0;'>
Like race car drivers who wear their sponsors on their suits — <b>every official who speaks at a public meeting
comes funded by someone.</b> Here is the public record of who funds each voice at this table. Source:
Hawaiʻi Campaign Spending Commission. Donor proximity to a vote is presented as a <b>question for oversight</b>,
never an accusation. The aloha response is not silence — it is <em>clear eyes and an honest record</em>.
</p>

<h2 style='color:#7ec8f0;font-size:1rem;letter-spacing:.08em;text-transform:uppercase;border-bottom:1px solid #1a2e42;padding-bottom:.4rem;margin-top:1.4rem;'>
🏎 Committee Members & Their Sponsors</h2>
{sponsor_rows if sponsor_rows else '<p style="color:#9fb2c8;">Sponsor data not yet loaded — run donor_watch.py to populate.</p>'}

<h2 style='color:#7ec8f0;font-size:1rem;letter-spacing:.08em;text-transform:uppercase;border-bottom:1px solid #1a2e42;padding-bottom:.4rem;margin-top:1.6rem;'>
📋 Agenda Items</h2>
{agenda_html}

<h2 style='color:#7ec8f0;font-size:1rem;letter-spacing:.08em;text-transform:uppercase;border-bottom:1px solid #1a2e42;padding-bottom:.4rem;margin-top:1.6rem;'>
🌙 Moon Timing — Kaulana Mahina</h2>
<div style='background:#0a1824;border-radius:8px;padding:14px 16px;'>
  <div style='color:#f3d589;font-weight:700;margin-bottom:4px;'>{moon['phase']} · Pō {esc(moon['name'])} ({moon['age_pct']}% through the lunation)</div>
  <div style='color:#a8c4e0;font-size:.9rem;margin-bottom:6px;'><em>Traditional nature:</em> {esc(moon['nature'])}</div>
  <div style='color:#7ec8f0;font-size:.9rem;'><em>Civic aloha offering:</em> {esc(moon['civic'])}</div>
  <div style='color:#9fb2c8;font-size:.78rem;margin-top:8px;'>Kaulana mahina is observational; this is astronomical forecast (±1 night). Source: Malo, Kepelino, UH Hawaiʻinuiākea.</div>
</div>

{speech_html}

<h2 style='color:#7ec8f0;font-size:1rem;letter-spacing:.08em;text-transform:uppercase;border-bottom:1px solid #1a2e42;padding-bottom:.4rem;margin-top:1.6rem;'>
☀️ The Sun & the Day</h2>
<div style='background:#0a1824;border-radius:8px;padding:12px 14px;font-size:.88rem;color:#a8c4e0;'>
{esc(sun['phrasing'])}
</div>

<h2 style='color:#7ec8f0;font-size:1rem;letter-spacing:.08em;text-transform:uppercase;border-bottom:1px solid #1a2e42;padding-bottom:.4rem;margin-top:1.6rem;'>
🌺 Positive Highlights (Sourced)</h2>
<div style='background:#0a1e14;border-left:3px solid #2e8b57;border-radius:6px;padding:12px 14px;font-size:.9rem;color:#a8d8b8;'>
These are verified, publicly sourced items that reflect forward progress — because aloha requires naming the good as clearly as naming the gap.
</div>

<p style='font-size:.78rem;color:#3a5168;border-top:1px solid #1a2e42;margin-top:1.6rem;padding-top:.8rem;'>
Sourced from Legistar (mauicounty.legistar.com) and Hawaiʻi Campaign Spending Commission (hicscdata.hawaii.gov).
No legal determinations. 12SGI · Kilo Aupuni · Christ energy = aloha in action.
</p>

</div></div></body></html>"""

    txt_issue = f"""GOLDEN LISTENER — {title}
12SGI · Kilo Aupuni
{'=' * 60}

{moon['phase']} · Pō {moon['name']} ({moon['age_pct']}% through the lunation)
Nature: {moon['nature']}
Civic offering: {moon['civic']}

Like race car drivers wearing their sponsors — here is the public
campaign finance record for each voice at this table.
Source: Hawaiʻi Campaign Spending Commission (hicscdata.hawaii.gov)

COMMITTEE MEMBERS & THEIR SPONSORS
{'-' * 40}
{chr(10).join(sponsor_txt_lines) if sponsor_txt_lines else '  (run donor_watch.py to populate)'}

AGENDA ITEMS
{'-' * 40}
{agenda_txt}

Sourced from Legistar + Hawaiʻi CSC. No legal determinations.
"""

    # LEAK GATE
    blob = html_issue + txt_issue
    hit = FORBIDDEN.search(blob)
    if hit:
        raise SystemExit(f"LEAK GATE: forbidden marker {hit.group(0)!r} — aborting")

    slug = re.sub(r"[^\w-]", "_", f"{ev_date_str}_{body_name.split('(')[0].strip().lower().replace(' ', '-')}")[:60]
    hp = os.path.join(OUT, f"golden_listener_{slug}.html")
    tp = os.path.join(OUT, f"golden_listener_{slug}.txt")
    open(hp, "w", encoding="utf-8", newline="\n").write(html_issue)
    open(tp, "w", encoding="utf-8", newline="\n").write(txt_issue)
    meta = {"date": ev_date_str, "body": body_name, "moon": moon, "agenda_items": len(agenda_items),
            "officials_covered": len(member_keys), "html": os.path.relpath(hp, PROJ),
            "txt": os.path.relpath(tp, PROJ), "source": legistar_url, "leak_check": "PASS",
            "generated": now_hst.strftime("%Y-%m-%d %H:%M HST")}
    json.dump(meta, open(os.path.join(OUT, "golden_listener_latest.json"), "w", encoding="utf-8"), indent=1)
    return meta


def main():
    p = argparse.ArgumentParser(description="Golden Listener — meeting-specific civic newsletter")
    p.add_argument("--event-id", type=int)
    p.add_argument("--date", help="YYYY-MM-DD")
    p.add_argument("--body", help="body name substring (e.g. 'Budget Finance')")
    p.add_argument("--transcript", default="", help="path to .txt meeting transcript for speech analysis")
    a = p.parse_args()
    target = date.fromisoformat(a.date) if a.date else None
    transcript_text = ""
    if a.transcript and os.path.exists(a.transcript):
        try:
            with open(a.transcript, encoding="utf-8", errors="replace") as f:
                transcript_text = f.read()
            print(f"golden_listener: transcript loaded ({len(transcript_text):,} chars)")
        except Exception as e:
            print(f"golden_listener: transcript load failed — {e}")
    m = build(event_id=a.event_id, target_date=target, body_substr=a.body, transcript_text=transcript_text)
    print(f"golden_listener: {m['date']} · {m['body']}")
    print(f"  Moon: {m['moon']['phase']} · Pō {m['moon']['name']} — {m['moon']['civic']}")
    print(f"  {m['agenda_items']} agenda items · {m['officials_covered']} officials · leak-gate PASS")
    print(f"  HTML: {m['html']}")
    print(f"  TXT:  {m['txt']}")


if __name__ == "__main__":
    main()
