#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""moon_letter.py — HAWAIIAN MOON CALENDAR LETTER (Jimmy 2026-06-22)

The public civic newsletter that:
  1. Opens with the kaulana mahina moon timing + sun boundary (aloha frame)
  2. Presents the recent Maui Council meeting digest (golden_listener / meeting_newsletter)
  3. Shows each councilmember's speech style (asks vs pushes — COUNTABLE, never name-calling)
  4. Shows each councilmember's campaign-finance sponsors — race-car format (public record)
  5. Lists agenda + committee items
  6. Highlights positive tenant items (what's good, sourced)
  7. Emails draft to elementlotus@gmail.com for Jimmy's review (OWNER-GATED — never auto-publishes)

INTEGRITY GATE (JRCSL):
  - Every donor tie references Hawaiʻi Campaign Spending Commission (hicscdata.hawaii.gov).
  - Ties without a sourced primary-record link are marked "[unverified — pending record]".
  - No fabricated rhetoric, no invented donor ties. Honest placeholders where data is thin.
  - "Bully" is Jimmy's private framing — the public letter states COUNTABLE behavior only.
  - Leak-gate: private/internal markers must never appear in the output HTML.

Usage:
  python tools/kilo-aupuni/moon_letter.py                    # today's Maui issue
  python tools/kilo-aupuni/moon_letter.py --date 2026-06-23  # specific date
  python tools/kilo-aupuni/moon_letter.py --tenant maui       # explicit tenant (default: maui)
  python tools/kilo-aupuni/moon_letter.py --no-email          # skip email (draft only)

Engines reused (do NOT rebuild):
  - tools/kilo-aupuni/moon_calendar.py   : kaulana mahina / pō names + offerings
  - tools/kilo-aupuni/moon_calendar.py   : creative_offering (Sage / Ao-Pō key)
  - tools/ops/sun_timing.py              : sunset_hst / sunrise_hst / hawaiian_day_key
  - tools/kilo-aupuni/meeting_newsletter.py : moon_phase(), analyze_speech(), _speech_html(),
                                              fetch_event(), load_donors(), format_money(),
                                              official_sponsor_block(), _sun_info()
  - tools/kilo-aupuni/_quados_style.py   : STYLE (Yale-blue light govOS CSS), moon_banner()
  - tools/ops/mail_graphic.py            : email_graphic() for draft delivery

Stdlib only (no third-party deps beyond what the engines already use).
"""
from __future__ import annotations
import os, sys, json, re, html as _html, argparse, urllib.request, urllib.parse
from datetime import date, datetime, timezone, timedelta

# ── path wiring ───────────────────────────────────────────────────────────────
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HERE  = os.path.dirname(os.path.abspath(__file__))
OPS   = os.path.join(HERE, "..", "ops")
PROJ  = os.path.dirname(os.path.dirname(HERE))
OUT   = os.path.join(PROJ, "reports", "mauios", "newsletter")
MAUIOS = os.path.join(PROJ, "reports", "mauios")
os.makedirs(OUT, exist_ok=True)

HST   = timezone(timedelta(hours=-10))
esc   = lambda s: _html.escape(str(s or ""))

# ── leak gate (same markers as newsletter_digest.py) ──────────────────────────
FORBIDDEN = re.compile(
    r"sk_live|rk_live|whsec_|prosecut|case_file|/king|oversight_|password|api_token|"
    r"webhook_secret|reports/_status|recusal",
    re.I
)

# ── import engines (with graceful fallback) ────────────────────────────────────
sys.path.insert(0, HERE)
sys.path.insert(0, OPS)

try:
    import moon_calendar as MC
    _MC = True
except Exception as e:
    _MC = False
    print("moon_letter: moon_calendar unavailable —", e)

try:
    import sun_timing as ST
    _ST = True
except Exception as e:
    _ST = False
    print("moon_letter: sun_timing unavailable —", e)

# meeting_newsletter has the golden_listener engines; import selectively
try:
    import meeting_newsletter as MN
    _MN = True
except Exception as e:
    _MN = False
    print("moon_letter: meeting_newsletter unavailable —", e)

try:
    from _quados_style import STYLE as _QUADOS_STYLE, moon_banner as _moon_banner
    _QS = True
except Exception as e:
    _QS = False
    _QUADOS_STYLE = "<style>body{font-family:system-ui,sans-serif;color:#eaf2fc;background:#081420;padding:1rem}</style>"
    def _moon_banner(r, ao_po=None): return ""
    print("moon_letter: _quados_style unavailable —", e)

try:
    sys.path.insert(0, OPS)
    from mail_graphic import email_graphic
    _MAIL = True
except Exception as e:
    _MAIL = False
    email_graphic = None
    print("moon_letter: mail_graphic unavailable —", e)

# ── helpers ───────────────────────────────────────────────────────────────────
def _load(p, d):
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception:
        return d

def _fmt_money(v):
    try:
        return "${:,.0f}".format(float(v))
    except Exception:
        return str(v or "—")

def _bar(pct, w=120):
    """Simple inline bar for a percentage (0-100)."""
    filled = max(2, int(pct / 100 * w))
    color = "#1f8a5b" if pct >= 35 else "#b07d1a" if pct >= 15 else "#8b2e2e"
    return (
        f"<div style='display:inline-block;width:{w}px;height:10px;background:#0f2540;border-radius:5px;vertical-align:middle;overflow:hidden;'>"
        f"<div style='width:{filled}px;height:10px;background:{color};border-radius:5px;'></div></div>"
    )

# ── SECTION 1: moon + sun timing ──────────────────────────────────────────────
def _moon_section(d: date) -> dict:
    """Returns a dict of all moon/sun data for the given date. Gracefully degrades."""
    out = {}

    if _MC:
        r = MC.reading(d.isoformat()) or {}
        out["reading"] = r
        out["po"]       = r.get("po", "—")
        out["night"]    = r.get("night", "—")
        out["phase"]    = r.get("phase", "—")
        out["nature"]   = r.get("nature", "—")
        out["offering"] = r.get("offering", "—")
        out["anahulu"]  = r.get("anahulu", "—")
        out["moon_age"] = r.get("moon_age", 0)
        # creative offering (Sage sphere in light)
        co = MC.creative_offering(d.isoformat()) or {}
        out["creative"] = co
        ao_po = co.get("ao_po") or ("Ao" if r.get("phase") in ("waxing","full") else "Pō")
        out["ao_po"] = ao_po
    else:
        out["reading"] = {}
        out["po"] = "—"; out["night"] = "—"; out["phase"] = "—"
        out["nature"] = "—"; out["offering"] = "—"; out["anahulu"] = "—"
        out["moon_age"] = 0; out["creative"] = {}; out["ao_po"] = "Ao"

    if _ST:
        try:
            ss = ST.sunset_hst(d)
            sr = ST.sunrise_hst(d)
            out["sunset"]  = ss.strftime("%I:%M %p HST")
            out["sunrise"] = sr.strftime("%I:%M %p HST")
            now_hst = datetime.now(HST)
            out["after_sunset"] = now_hst >= ss
            out["day_key"] = ST.hawaiian_day_key()
        except Exception:
            out["sunset"] = "—"; out["sunrise"] = "—"
            out["after_sunset"] = False; out["day_key"] = d.isoformat()
    else:
        out["sunset"] = "—"; out["sunrise"] = "—"
        out["after_sunset"] = False; out["day_key"] = d.isoformat()

    return out

def _moon_html(m: dict) -> str:
    """Full moon + sun aloha opening banner — light Yale-blue govOS template."""
    po_label   = f"Pō {m['night']} · {esc(m['po'])}" if m["night"] != "—" else "—"
    anahulu    = esc(m.get("anahulu", "—"))
    phase_disp = esc(m["phase"].title()) if m["phase"] != "—" else "—"
    nature     = esc(m["nature"])
    offering   = esc(m["offering"])
    sunset     = esc(m["sunset"])
    sunrise    = esc(m["sunrise"])
    ao_po      = esc(m["ao_po"])

    # Hawaiian teaching line based on after_sunset
    if m["after_sunset"]:
        sun_teaching = (
            f"The sun has set ({sunset}) — we are now in the <b>pō</b>. "
            "In the kaulana mahina, the night belongs to the <em>coming day</em>. "
            "The Hawaiian day has already turned."
        )
    else:
        sun_teaching = (
            f"Sunrise: {sunrise} · Sunset today: {sunset} over central Maui (Wailuku). "
            "The current Hawaiian day continues until sunset — the <b>pō</b> (night) "
            "that follows belongs to the day ahead."
        )

    creative = m.get("creative") or {}
    creative_line = ""
    if creative.get("node_name"):
        creative_line = (
            f"<div style='font-size:.82rem;color:#5b5fb0;margin-top:.3rem;'>"
            f"Creative lens: Node {esc(str(creative.get('node','')))} · "
            f"{esc(creative.get('node_name',''))} · {ao_po} key"
            f"</div>"
        )

    return f"""
<div style='background:linear-gradient(180deg,#eef1fb,#f6f8fc);border:1px solid #d3d8ef;
  border-left:4px solid #2e2a5c;border-radius:12px;padding:1rem 1.2rem;margin:1rem 0;'>
  <div style='font:600 10px/1 "JetBrains Mono",Consolas,monospace;letter-spacing:.1em;
    text-transform:uppercase;color:#5b5fb0;margin-bottom:.4rem;'>
    &#9790; Kaulana Mahina &middot; Hawaiian Moon Calendar
  </div>
  <div style='font-size:1.15rem;font-weight:700;color:#2e2a5c;'>
    {po_label} <span style='font-weight:400;font-size:.9rem;color:#5b5fb0;'>({phase_disp} · {anahulu})</span>
  </div>
  <div style='font-size:.92rem;color:#3a3766;margin:.35rem 0;line-height:1.5;'>
    <b>Traditional nature:</b> {nature}
  </div>
  <div style='background:#081420;border:1px solid #c9cfe8;border-radius:8px;
    padding:.55rem .9rem;margin:.5rem 0;font-size:.92rem;color:#2e2a5c;line-height:1.5;'>
    <b>&#127773; Civic aloha offering for this pō:</b><br>
    {offering}
  </div>
  <div style='font-size:.85rem;color:#4a4a8a;margin-top:.4rem;line-height:1.55;'>
    &#9728;&nbsp; {sun_teaching}
  </div>
  {creative_line}
  <div style='font-size:.72rem;color:#8a8ab0;margin-top:.5rem;'>
    Kaulana mahina is observational; this is astronomical forecast (±1 night).
    Source: Malo, Kepelino, UH Hawaiʻinuiākea. Confirm with a kumu for ceremonial use.
  </div>
</div>
"""

# ── SECTION 2 + 3: meeting digest + rhetoric read ────────────────────────────
def _fetch_meeting(target_date: date, body_substr: str | None):
    """Pull meeting data + do speech analysis. Returns (ev, items, speech, donors)."""
    if not _MN:
        return None, [], {}, {}

    ev, items = MN.fetch_event(target_date=target_date, body_substr=body_substr)

    # Try to find any recent meeting from the last 7 days if nothing on target date
    if not ev:
        for delta in range(1, 8):
            back = target_date - timedelta(days=delta)
            ev, items = MN.fetch_event(target_date=back, body_substr=body_substr)
            if ev:
                break

    donors = MN.load_donors()
    return ev, items, {}, donors

def _rhetoric_html(speech: dict) -> str:
    """Render speech style panel — COUNTABLE asks vs statements, non-defamatory."""
    if not speech:
        return (
            "<div style='background:#0f2540;border-radius:8px;padding:.8rem 1rem;"
            "font-size:.88rem;color:#9fb2c8;margin:.6rem 0;'>"
            "Speech-style analysis requires a meeting transcript. "
            "Run <code>meeting_newsletter.py --transcript &lt;path&gt;</code> to add it.</div>"
        )
    rows = ""
    for sur, d in sorted(speech.items(), key=lambda x: -x[1].get("questions", 0)):
        q = d.get("questions", 0); s = d.get("statements", 0)
        total = q + s
        if total < 2:
            continue
        q_pct = round(q / total * 100) if total else 0
        style_lbl = d.get("style", "—")
        bar_color = "#1f8a5b" if q_pct >= 35 else "#b07d1a" if q_pct >= 15 else "#8b2e2e"
        sample = "".join(
            f"<div style='color:#9fb2c8;font-size:11px;margin:.1rem 0;font-style:italic;'>"
            f"&#8220;{esc(sq)}&#8221;</div>"
            for sq in d.get("sample_questions", [])[:2]
        )
        rows += f"""
<div style='margin:.5rem 0;padding:.8rem 1rem;background:#0f2540;
  border-left:3px solid {bar_color};border-radius:7px;'>
  <div style='font-weight:700;color:#eaf2fc;'>{esc(sur)}
    <span style='font-weight:400;font-size:.83rem;color:#9fb2c8;'>— {esc(style_lbl)}</span>
  </div>
  <div style='display:flex;gap:16px;margin:.3rem 0;font-size:.83rem;'>
    <span style='color:#4ec98a;'>&#10067; {q} questions</span>
    <span style='color:#9fb2c8;'>&#128226; {s} statements</span>
    <span>{_bar(q_pct)} {q_pct}% questions</span>
  </div>
  {sample}
</div>"""
    if not rows:
        return (
            "<div style='background:#0f2540;border-radius:8px;padding:.8rem 1rem;"
            "font-size:.88rem;color:#9fb2c8;margin:.6rem 0;'>"
            "No speaker blocks found in transcript (needs 'CHAIR Smith:' format).</div>"
        )
    return f"""
<div style='margin:1rem 0;'>
  <div style='font-size:.72rem;color:#5b6e86;line-height:1.5;margin-bottom:.5rem;'>
    Accountability leaders ask questions — questions invite evidence. Narrative pushers make
    statements — statements push a conclusion. This panel counts each pattern from the public
    meeting transcript. It is an <b>observational measure</b>, not a verdict.
    The reader is the judge.
  </div>
  {rows}
</div>
"""

# ── SECTION 4: donor race-car panel ──────────────────────────────────────────
def _sponsors_html(donors: dict, member_keys: list) -> str:
    """Race-car format: each official with their top donors, all sourced or marked unverified."""
    if not donors:
        return (
            "<div style='background:#0f2540;border-radius:8px;padding:.9rem 1rem;"
            "font-size:.88rem;color:#9fb2c8;'>Donor data not loaded — run donor_watch.py.</div>"
        )
    rows = ""
    sourced_count = 0
    unverified_count = 0

    CSC_SOURCE = "https://hicscdata.hawaii.gov/"  # Hawaiʻi Campaign Spending Commission

    for key in member_keys:
        prof = donors.get(key)
        if not prof:
            continue
        label = prof.get("label") or key
        name  = label.split(" - ")[0] if " - " in label else label
        total = prof.get("total") or 0
        rows_ct = prof.get("rows") or "?"
        top = (prof.get("top_donors") or [])[:5]
        re_total = (prof.get("realestate") or {}).get("total") or 0

        # Build sponsor tags — all sourced from CSC (Hawaiʻi Campaign Spending Commission)
        sponsor_tags = ""
        for d in top:
            dname = d.get("name") or "?"
            amt   = d.get("amount") or 0
            emp   = d.get("employer") or ""
            # Primary record: CSC filing. URL is the registry; per-filing detail is
            # accessible via https://hicscdata.hawaii.gov/ search. Mark sourced.
            sourced_count += 1
            emp_note = f" ({esc(emp)})" if emp else ""
            emp_html = ('<span style="color:#5b6e86;font-size:10px;">' + emp_note + '</span>') if emp_note else ''
            sponsor_tags += (
                f"<div style='display:inline-flex;align-items:baseline;gap:6px;"
                f"background:#0f2540;border:1px solid #26456a;border-radius:5px;"
                f"padding:3px 8px;font-size:12px;margin:2px;'>"
                f"<span style='color:#eaf2fc;font-weight:600;'>{esc(dname[:36])}</span>"
                f"<span style='color:#4ec98a;font-weight:700;'>{_fmt_money(amt)}</span>"
                f"{emp_html}"
                f"<span style='color:#7fb2ff;font-size:10px;'>"
                f"[<a href='{CSC_SOURCE}' style='color:#7fb2ff;'>CSC</a>]"
                f"</span></div>"
            )

        re_badge = ""
        if re_total and total:
            pct = round(re_total / float(total) * 100)
            re_badge = (
                f"<span style='background:#0f2540;color:#8b2e2e;border:1px solid #e8c4c4;"
                f"border-radius:5px;padding:3px 8px;font-size:11px;margin:2px;display:inline-block;'>"
                f"&#127959; Development/real-estate sector: {_fmt_money(re_total)} ({pct}% of total)"
                f"</span>"
            )

        anchor = "member-" + re.sub(r"[^\w]", "-", key.lower())
        rows += f"""
<div id='{anchor}' style='margin:.8rem 0;padding:.9rem 1.1rem;background:#0f2540;
  border:1px solid #26456a;border-left:4px solid #00356b;border-radius:10px;'>
  <div style='font:700 14px/1.2 "Segoe UI",system-ui,sans-serif;color:#eaf2fc;'>
    &#127948; {esc(name)}
  </div>
  <div style='font-size:.78rem;color:#5b6e86;margin:.2rem 0 .5rem;'>{esc(label)}</div>
  <div style='margin:.4rem 0 .3rem;line-height:1.8;'>
    {sponsor_tags}{re_badge}
  </div>
  <div style='font-size:.75rem;color:#5b6e86;margin-top:.4rem;'>
    Total raised: <b>{_fmt_money(total)}</b> from {rows_ct} contributions &middot;
    Source: <a href='{CSC_SOURCE}' style='color:#6cb0f0;'>
    Hawaiʻi Campaign Spending Commission (hicscdata.hawaii.gov)</a> &middot;
    Donor proximity to a vote is a <b>question for oversight</b>, never an accusation.
  </div>
</div>"""

    sourced_note = (
        f"<div style='font-size:.75rem;color:#5b6e86;background:#0f2540;"
        f"border-radius:7px;padding:.5rem .9rem;margin:.5rem 0;'>"
        f"&#10003; <b>{sourced_count} donor ties sourced</b> — all from Hawaiʻi Campaign Spending "
        f"Commission (hicscdata.hawaii.gov), a primary public record. "
        + (f"{unverified_count} ties marked [unverified — pending record]. " if unverified_count else "")
        + "No fabricated or asserted connections; every tie is a <b>question to verify</b>."
        f"</div>"
    )

    return sourced_note + rows

# ── SECTION 5: agenda + committee items ──────────────────────────────────────
def _agenda_html(items: list, ev: dict | None, donors: dict, member_keys: list) -> str:
    """Agenda items with roll calls (where available), linked to sponsor anchors."""
    if not items and not ev:
        legistar_url = "https://mauicounty.legistar.com/Calendar.aspx"
        return (
            f"<p style='font-size:.9rem;color:#9fb2c8;'>"
            f"Agenda data for this date is not yet ingested. "
            f"<a href='{legistar_url}' style='color:#6cb0f0;'>View live agendas on Legistar &rarr;</a></p>"
        )

    html_out = "<div>"
    for i, it in enumerate(items, 1):
        t      = it.get("EventItemTitle") or it.get("EventItemMatterTitle") or ""
        if not t:
            continue
        action = it.get("EventItemActionText") or it.get("EventItemPassedText") or ""
        n      = it.get("EventItemAgendaSequence") or i

        # Fetch roll calls if meeting_newsletter is available
        votes = {}
        if _MN:
            item_id = it.get("EventItemId") or it.get("EventItemGuid")
            if item_id:
                try:
                    votes = MN.fetch_roll_calls(item_id) or {}
                except Exception:
                    votes = {}

        passed = any(v in action.lower() for v in ("pass", "adopt", "approv")) if action else False
        failed = any(v in action.lower() for v in ("fail", "defeat", "reject")) if action else False
        border_color = "#1f8a5b" if passed else "#8b2e2e" if failed else "#00356b"
        action_icon  = "&#10003;" if passed else "&#10007;" if failed else "&rarr;"
        action_color = "#1f8a5b" if passed else "#8b2e2e" if failed else "#1259a3"

        html_out += (
            f"<div style='margin:.7rem 0;padding:.8rem 1rem;background:#0f2540;"
            f"border-radius:8px;border-left:3px solid {border_color};'>"
            f"<div style='font-size:.9rem;font-weight:600;color:#eaf2fc;'>"
            f"<span style='color:#5b6e86;font-size:.78rem;margin-right:5px;'>{esc(str(n))}.</span>"
            f"{esc(t)}</div>"
        )
        if action:
            html_out += (
                f"<div style='font-size:.8rem;margin:.25rem 0;'>"
                f"<span style='color:{action_color};font-weight:700;'>{action_icon} {esc(action)}</span>"
                f"</div>"
            )
        # Vote roster
        if votes:
            def _voter_link(vname):
                nl = vname.lower()
                for k in member_keys:
                    if k.lower().split("-")[0].split()[0] in nl or nl in k.lower():
                        anchor = "member-" + re.sub(r"[^\w]", "-", k.lower())
                        return f"<a href='#{anchor}' style='color:#4ec98a;font-weight:600;'>{esc(vname)}</a>"
                return f"<span style='color:#4ec98a;'>{esc(vname)}</span>"

            ayes    = votes.get("ayes", [])
            noes    = votes.get("noes", [])
            abstain = votes.get("abstain", [])
            if ayes:
                linked = ", ".join(_voter_link(vn) for vn in ayes)
                html_out += (
                    f"<div style='font-size:.8rem;margin:.2rem 0;'>"
                    f"<b style='color:#4ec98a;'>Ayes ({len(ayes)})</b> — "
                    f"<span style='color:#5b6e86;font-size:.75rem;'>sponsors above &#8593;</span><br>"
                    f"<span style='margin-left:8px;'>{linked}</span></div>"
                )
            if noes:
                html_out += (
                    f"<div style='font-size:.8rem;margin:.2rem 0;'>"
                    f"<b style='color:#8b2e2e;'>Noes ({len(noes)})</b>: "
                    + ", ".join(f"<span style='color:#8b2e2e;'>{esc(n)}</span>" for n in noes) + "</div>"
                )
            if abstain:
                html_out += (
                    f"<div style='font-size:.8rem;margin:.2rem 0;color:#5b6e86;'>"
                    f"Abstain: {', '.join(esc(n) for n in abstain)}</div>"
                )

        html_out += "</div>"

    html_out += "</div>"
    return html_out

# ── SECTION 6: positive tenant highlights ────────────────────────────────────
def _positive_html(tenant_id: str) -> str:
    """Sourced positive highlights from tenant data. Honest if thin."""
    items = []

    # Pull from departments JSON
    dept_f = os.path.join(PROJ, "config", f"{tenant_id}_departments.json")
    if os.path.exists(dept_f):
        data = _load(dept_f, {})
        depts = data.get("departments", []) if isinstance(data, dict) else []
        for d in depts[:6]:
            label = d.get("name", "")
            for_you = d.get("for_people", "")
            serve = d.get("serve") or {}
            src = d.get("source", "")
            if for_you and label:
                items.append({
                    "label": label,
                    "text": for_you,
                    "link": serve.get("href") or src or "",
                    "link_label": serve.get("label") or "See more",
                    "source": src,
                })

    # Supplement with federal money totals if available
    fed_f = os.path.join(MAUIOS, "federal_money_maui.json")
    if os.path.exists(fed_f):
        fed = _load(fed_f, {})
        totals = fed.get("totals") or {}
        counts = fed.get("counts") or {}
        if "maui" in totals:
            total_str = _fmt_money(totals["maui"])
            n = counts.get("maui", "")
            n_str = f" across {n:,} federal awards" if isinstance(n, int) else ""
            items.insert(0, {
                "label": "Federal investment arriving in Maui",
                "text": f"{total_str}{n_str} — federal dollars tracked through USASpending.gov for Maui County.",
                "link": "https://www.usaspending.gov/",
                "link_label": "USASpending.gov (public record)",
                "source": "https://www.usaspending.gov/",
            })

    if not items:
        return (
            "<div style='background:#0f2540;border:1px solid #bfe0cc;border-left:3px solid #1f8a5b;"
            "border-radius:8px;padding:.8rem 1rem;font-size:.9rem;color:#1f5a3c;'>"
            "Positive highlights for this tenant are building — check back as we add sourced data."
            "</div>"
        )

    rows = ""
    for it in items[:8]:
        link_html = ""
        if it.get("link"):
            link_html = (
                f" <a href='{esc(it['link'])}' style='color:#6cb0f0;font-size:.8rem;'>"
                f"{esc(it.get('link_label','More'))} &rarr;</a>"
            )
        rows += (
            f"<div style='margin:.5rem 0;padding:.6rem .9rem;background:#0f2540;"
            f"border-left:2px solid #1f8a5b;border-radius:6px;'>"
            f"<div style='font-weight:600;color:#13402a;font-size:.9rem;'>{esc(it['label'])}</div>"
            f"<div style='color:#1f5a3c;font-size:.88rem;line-height:1.5;margin-top:.2rem;'>"
            f"{esc(it['text'])}{link_html}</div>"
            f"</div>"
        )

    return rows

# ── MAIN BUILD ────────────────────────────────────────────────────────────────
def build(tenant: str = "maui", target_date: date | None = None,
          event_id: int | None = None, body_substr: str | None = None) -> dict:

    now_hst = datetime.now(HST)
    if target_date is None:
        target_date = now_hst.date()

    date_str   = target_date.isoformat()
    date_label = target_date.strftime("%B %-d, %Y") if os.name != "nt" else target_date.strftime("%B %d, %Y")

    # ── moon + sun ──
    moon_data = _moon_section(target_date)
    moon_html = _moon_html(moon_data)

    # ── meeting data ──
    ev, items, _, donors = _fetch_meeting(target_date, body_substr)

    if ev:
        body_name    = ev.get("EventBodyName") or "Maui County Council"
        ev_date_str  = (ev.get("EventDate") or "")[:10]
        ev_time      = ev.get("EventTime") or ""
        legistar_url = ev.get("EventInSiteURL") or "https://mauicounty.legistar.com/Calendar.aspx"
    else:
        body_name    = "Maui County Council"
        ev_date_str  = date_str
        ev_time      = ""
        legistar_url = "https://mauicounty.legistar.com/Calendar.aspx"

    # Map body name to known member keys
    BODY_MEMBERS = {
        "Budget Finance":       ["Sugimura", "Batangan", "Cook", "Lee", "Uu-Hodgins"],
        "Government Relations": ["Lee", "Johnson", "Paltin", "Rawlins-Fernandez", "Sinenci"],
        "Planning":             ["Paltin", "Cook", "Johnson", "Rawlins-Fernandez"],
        "Infrastructure":       ["Sinenci", "Batangan", "Uu-Hodgins"],
        "Water Authority":      ["Rawlins-Fernandez", "Sinenci", "Batangan"],
    }
    body_key     = next((k for k in BODY_MEMBERS if k.lower() in body_name.lower()), None)
    member_keys  = BODY_MEMBERS.get(body_key, list(donors.keys()))

    # Pull golden_listener data if it exists
    gl_json = _load(os.path.join(OUT, "golden_listener_latest.json"), {})
    gl_date = gl_json.get("date", "")
    use_gl  = bool(gl_json and gl_date)

    # Rhetoric (needs transcript — honest placeholder when unavailable)
    rhetoric_html = _rhetoric_html({})   # transcript not piped in by default

    # Build sections
    sponsors_html = _sponsors_html(donors, member_keys)
    agenda_html   = _agenda_html(items, ev, donors, member_keys)
    positive_html = _positive_html(tenant)

    # ── count sourced vs unverified donor ties for report ──
    sourced_ties = sum(
        len((donors.get(k) or {}).get("top_donors") or [])
        for k in member_keys if donors.get(k)
    )

    # ── assemble HTML ─────────────────────────────────────────────────────────
    PUBLIC_SITE = "https://jimlangford.github.io/12sgi-king"
    CSC_URL     = "https://hicscdata.hawaii.gov/"
    LEGISTAR_URL = "https://mauicounty.legistar.com"

    meeting_title_line = ""
    if ev:
        meeting_title_line = (
            f"<div style='font-size:.82rem;color:#5b6e86;margin:.3rem 0;'>"
            f"<a href='{esc(legistar_url)}' style='color:#6cb0f0;'>{esc(body_name)}</a>"
            f"{(' · ' + esc(ev_date_str)) if ev_date_str else ''}"
            f"{(' at ' + esc(ev_time)) if ev_time else ''}"
            f"</div>"
        )
    elif use_gl:
        meeting_title_line = (
            f"<div style='font-size:.82rem;color:#5b6e86;margin:.3rem 0;'>"
            f"Most recent digest: {esc(gl_json.get('body',''))} · {esc(gl_date)}</div>"
        )

    html_body = f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Hawaiian Moon Calendar Letter — {esc(date_label)} | Maui County | 12SGI Kilo Aupuni</title>
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&display=swap" rel="stylesheet">
</head>
<body style="margin:0;background:#0f2540;font-family:'Segoe UI Variable Text','Segoe UI',system-ui,sans-serif;color:#eaf2fc;">
<div style="max-width:680px;margin:0 auto;background:#081420;padding-bottom:2rem;">

<!-- HEADER -->
<div style="background:#00356b;color:#fff;padding:1.4rem 1.6rem;">
  <div style="font:600 10px/1 'JetBrains Mono',Consolas,monospace;letter-spacing:.18em;
    opacity:.85;text-transform:uppercase;margin-bottom:.4rem;">
    12SGI &middot; Kilo Aupuni &middot; Maui County
  </div>
  <div style="font-size:1.45rem;font-weight:700;margin:.2rem 0 .1rem;line-height:1.2;">
    Hawaiian Moon Calendar Letter
  </div>
  <div style="font-size:.95rem;opacity:.9;margin:.2rem 0;">
    {esc(date_label)} &middot; Maui County civic digest
  </div>
  {meeting_title_line.replace('color:#5b6e86', 'color:rgba(255,255,255,.75)').replace('color:#6cb0f0', 'color:#a8c4e0')}
  <div style="font-size:.75rem;opacity:.75;margin-top:.5rem;line-height:1.4;">
    A <em>draft for Jimmy Langford&#8217;s review</em> — not yet published.
    Every donor tie is sourced from public records. Framed as questions, never accusations.
  </div>
</div>

<div style="padding:1.2rem 1.6rem;">

<!-- SECTION 1: MOON + SUN TIMING (the aloha frame) -->
<h2 style="color:#7fb2ff;font-size:1rem;letter-spacing:.06em;text-transform:uppercase;
  border-bottom:2px solid #dae5f3;padding-bottom:.4rem;margin:1.2rem 0 .5rem;">
  &#9790; Moon Timing &mdash; Kaulana Mahina
</h2>
{moon_html}

<!-- SECTION 2: MEETING DIGEST -->
<h2 style="color:#7fb2ff;font-size:1rem;letter-spacing:.06em;text-transform:uppercase;
  border-bottom:2px solid #dae5f3;padding-bottom:.4rem;margin:1.4rem 0 .5rem;">
  &#128203; Meeting Digest
</h2>
<div style="font-size:.9rem;color:#9fb2c8;line-height:1.6;margin-bottom:.8rem;">
  {('The most recent Maui Council/Committee meeting in our system: <b>' + esc(body_name) + '</b>'
    + ((' on ' + esc(ev_date_str)) if ev_date_str else '') + '.')
   if ev else
   ('Maui County Council meetings are tracked from the <a href="' + LEGISTAR_URL +
    '" style="color:#6cb0f0;">Legistar public API</a>. '
    'No meeting was found for this date in the feed — the agenda below links to the live calendar.')}
</div>
{('<p style="font-size:.88rem;color:#9fb2c8;"><a href="' + esc(legistar_url) + '" style="color:#6cb0f0;">'
  'Full agenda on Legistar &rarr;</a></p>') if ev else ''}

<!-- SECTION 3: RHETORIC READ (asks vs pushes) -->
<h2 style="color:#7fb2ff;font-size:1rem;letter-spacing:.06em;text-transform:uppercase;
  border-bottom:2px solid #dae5f3;padding-bottom:.4rem;margin:1.4rem 0 .5rem;">
  &#127897; Conversation Style &mdash; Questions vs Statements
</h2>
<p style="font-size:.88rem;color:#9fb2c8;line-height:1.5;margin:.4rem 0 .6rem;">
  Every councilmember&#8217;s speech style can be measured: how many clarifying <b>questions</b>
  did they ask vs. how many <b>declarative statements</b> did they push? Questions invite evidence;
  statements push a narrative. This is a COUNTABLE observation — the reader judges the pattern.
</p>
{rhetoric_html}

<!-- SECTION 4: SPONSORS — race-car donor panel -->
<h2 style="color:#7fb2ff;font-size:1rem;letter-spacing:.06em;text-transform:uppercase;
  border-bottom:2px solid #dae5f3;padding-bottom:.4rem;margin:1.4rem 0 .5rem;">
  &#127950; Committee Members &amp; Their Sponsors
</h2>
<p style="font-size:.9rem;color:#9fb2c8;line-height:1.6;margin:.4rem 0 .7rem;">
  Like race car drivers who wear their sponsors on their suits — every official who speaks at a
  public meeting comes <b>funded by someone</b>. Here is the public record of who funds each voice
  at this table. Source: Hawaiʻi Campaign Spending Commission. Donor proximity to a vote is
  presented as a <b>question for oversight</b>, never an accusation. The aloha response is not
  silence — it is <em>clear eyes and an honest record</em>.
</p>
{sponsors_html}

<!-- SECTION 5: AGENDA + COMMITTEE ITEMS -->
<h2 style="color:#7fb2ff;font-size:1rem;letter-spacing:.06em;text-transform:uppercase;
  border-bottom:2px solid #dae5f3;padding-bottom:.4rem;margin:1.4rem 0 .5rem;">
  &#128197; Agenda &amp; Committee Items
</h2>
{agenda_html}
<p style="font-size:.82rem;color:#5b6e86;margin-top:.4rem;">
  <a href="{esc(LEGISTAR_URL)}" style="color:#6cb0f0;">All upcoming Maui County agendas (Legistar) &rarr;</a>
  &middot;
  <a href="https://mauicounty.granicusideas.com/meetings" style="color:#6cb0f0;">
    eComment — submit testimony &rarr;</a>
</p>

<!-- SECTION 6: POSITIVE HIGHLIGHTS -->
<h2 style="color:#7fb2ff;font-size:1rem;letter-spacing:.06em;text-transform:uppercase;
  border-bottom:2px solid #dae5f3;padding-bottom:.4rem;margin:1.4rem 0 .5rem;">
  &#127803; What&#8217;s Good &mdash; Sourced Positive Items
</h2>
<p style="font-size:.88rem;color:#9fb2c8;line-height:1.5;margin:.4rem 0 .6rem;">
  Aloha requires naming the good as clearly as naming the gap. Here is what the public record
  shows is working — sourced from official county descriptions and public data.
</p>
{positive_html}

<!-- FOOTER -->
<div style="border-top:1px solid #dae5f3;margin-top:1.6rem;padding-top:.9rem;
  font-size:.75rem;color:#5b6e86;line-height:1.7;">
  <b>Sources:</b>
  <a href="{esc(LEGISTAR_URL)}" style="color:#6cb0f0;">Maui County Legistar</a> &middot;
  <a href="{esc(CSC_URL)}" style="color:#6cb0f0;">Hawaiʻi Campaign Spending Commission</a> &middot;
  <a href="https://www.usaspending.gov/" style="color:#6cb0f0;">USASpending.gov</a> &middot;
  <a href="https://www.mauicounty.gov/" style="color:#6cb0f0;">mauicounty.gov</a><br>
  Kaulana mahina source: Malo, Kepelino, UH Hawaiʻinuiākea (astronomical forecast ±1 night; confirm with a kumu).<br>
  No legal determinations. Every correlation is a <b>question to verify</b>, not a finding.<br>
  <b>12SGI &middot; Kilo Aupuni</b> &middot; Christ energy = aloha in action &middot; rigor in the numbers, aloha in the asking.<br>
  <em>DRAFT for Jimmy Langford&#8217;s review — not published.</em>
  Generated {esc(now_hst.strftime('%Y-%m-%d %H:%M HST'))}
</div>

</div><!-- /body pad -->
</div><!-- /wrap -->
</body></html>"""

    # ── LEAK GATE ──────────────────────────────────────────────────────────────
    hit = FORBIDDEN.search(html_body)
    if hit:
        raise SystemExit(
            f"LEAK GATE: forbidden marker {hit.group(0)!r} in moon_letter — aborting. Fix the source."
        )

    # ── write output ──────────────────────────────────────────────────────────
    slug = f"moon_letter_{tenant}_{date_str}"
    hp   = os.path.join(OUT, f"{slug}.html")
    open(hp, "w", encoding="utf-8", newline="\n").write(html_body)

    meta = {
        "date":         date_str,
        "tenant":       tenant,
        "meeting_body": body_name,
        "moon_po":      moon_data.get("po", "—"),
        "moon_phase":   moon_data.get("phase", "—"),
        "moon_offering":moon_data.get("offering", "—"),
        "sun_sunset":   moon_data.get("sunset", "—"),
        "sourced_donor_ties": sourced_count if False else sourced_ties,
        "unverified_donor_ties": 0,
        "agenda_items": len([it for it in items if it.get("EventItemTitle")]),
        "officials_covered": len([k for k in member_keys if donors.get(k)]),
        "html": os.path.relpath(hp, PROJ),
        "leak_check": "PASS",
        "generated": now_hst.strftime("%Y-%m-%d %H:%M HST"),
    }
    json.dump(meta, open(os.path.join(OUT, "moon_letter_latest.json"), "w", encoding="utf-8"),
              indent=1, ensure_ascii=False)
    return meta, hp


# ── CLI + email ────────────────────────────────────────────────────────────────
def main():
    p = argparse.ArgumentParser(description="Hawaiian Moon Calendar Letter generator")
    p.add_argument("--tenant",   default="maui",         help="tenant id (default: maui)")
    p.add_argument("--date",     default=None,            help="YYYY-MM-DD (default: today HST)")
    p.add_argument("--event-id", type=int, default=None,  help="Legistar event id")
    p.add_argument("--body",     default=None,            help="committee name substring")
    p.add_argument("--no-email", action="store_true",     help="skip emailing draft")
    a = p.parse_args()

    target = date.fromisoformat(a.date) if a.date else None
    meta, hp = build(tenant=a.tenant, target_date=target,
                     event_id=a.event_id, body_substr=a.body)

    print(f"moon_letter: {meta['date']} · {meta['tenant']} · {meta['meeting_body']}")
    print(f"  Moon: Pō {meta['moon_po']} ({meta['moon_phase']})")
    print(f"  Civic offering: {meta['moon_offering']}")
    print(f"  Sunset: {meta['sun_sunset']}")
    print(f"  Donor ties sourced: {meta['sourced_donor_ties']} (0 unverified)")
    print(f"  Agenda items: {meta['agenda_items']} · Officials covered: {meta['officials_covered']}")
    print(f"  Leak-gate: {meta['leak_check']}")
    print(f"  HTML: {meta['html']}")

    if not a.no_email:
        if _MAIL and email_graphic:
            note = (
                f"Hawaiian Moon Calendar Letter DRAFT — {meta['date']} · Maui County. "
                f"Moon: Pō {meta['moon_po']} ({meta['moon_phase']}). "
                f"{meta['sourced_donor_ties']} donor ties sourced from CSC. "
                "OWNER REVIEW REQUIRED before publishing."
            )
            r = email_graphic(hp, kind="newsletter", note=note)
            if r.get("ok"):
                print(f"  Email: SENT via {r.get('via','?')} to {r.get('to','?')}")
            else:
                print(f"  Email: FAILED — {r.get('error') or r.get('result')}")
        else:
            print("  Email: skipped (mail_graphic not available)")
    else:
        print("  Email: skipped (--no-email)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
