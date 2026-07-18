#!/usr/bin/env python3
"""sunshine_board.py — the council/clerk Sunshine-compliance dashboard (Jimmy 2026-06-18).

Built into the agenda flow: for each upcoming meeting it shows the HRS §92-7 deadline COUNTDOWN, the
required-elements check, the ready-to-file notice, and ONE-CLICK distribution buttons — a prefilled
`mailto:` to the newspaper legal-notices desk ("send to newspaper") and to the notification list. The
buttons open the user's own mail client with everything filled in; a HUMAN clicks send (this tool never
auto-sends). This is the OWNER/clerk-facing private surface (Naga / king-local) — it speeds compliance,
it does not perform the county's official calendar/clerk filing.

HONESTY: newspaper publication is NOT a §92 requirement (OIP) — it's matter-specific (rezoning §46-4,
budget/charter hearings). The board labels it as opt-in. The §92 controlling act is the county-calendar
electronic posting + clerk filing, which remain the county's to perform; we hand them a validated package.

Writes: reports/_status/sunshine/board.html  (private; served on Naga, never on the public site).
Stdlib only.
"""
import os, sys, json, glob, urllib.parse
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path: sys.path.insert(0, HERE)
import sunshine_compliance as SC
PROJ = os.path.dirname(os.path.dirname(HERE))
POSTS = os.path.join(PROJ, "reports", "_status", "agenda_posts")
OUT = os.path.join(PROJ, "reports", "_status", "sunshine")


def esc(s):
    return str(s if s is not None else "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _upcoming():
    out = []
    for p in sorted(glob.glob(os.path.join(POSTS, "agenda_*.json"))):
        try:
            j = json.load(open(p, encoding="utf-8"))
        except Exception:
            continue
        md = j.get("meeting_date") or j.get("date")
        if md:
            out.append({"board": j.get("board") or j.get("committee") or "County Council",
                        "meeting_date": md, "items": j.get("topics") or j.get("items") or []})
    # de-dupe by (board, date)
    seen, uniq = set(), []
    for m in out:
        k = (m["board"], m["meeting_date"])
        if k not in seen:
            seen.add(k); uniq.append(m)
    return uniq


def _mailto(to, subject, body):
    q = urllib.parse.urlencode({"subject": subject, "body": body})
    return "mailto:%s?%s" % (urllib.parse.quote(to or ""), q)


_STATUS_COLOR = {"on_track": "#1f8a5b", "post_now": "#d9a400", "LATE": "#c0392b", "past": "#5a6b7b"}


def build():
    os.makedirs(OUT, exist_ok=True)
    meetings = _upcoming()
    cards = []
    for m in meetings:
        st = SC.status(m); dl = st["deadline"]; el = st["elements"]
        color = _STATUS_COLOR.get(dl.get("status"), "#5a6b7b")
        risk = ' <b style="color:#c0392b">AUTO-CANCEL RISK</b>' if dl.get("auto_cancel_risk") else ""
        miss = (" — missing: " + ", ".join(esc(x) for x in el["missing"])) if el["missing"] else " — all present"
        notice = SC.notice_text(m)
        nem = SC.notification_email(m); npk = SC.newspaper_package(m)
        # one-click buttons (prefilled mailto: a HUMAN sends; never auto-sent)
        news_btn = ('<a class="btn" href="%s">Send to newspaper &rarr;</a>' % esc(_mailto(npk["to"], "Public notice — %s, %s" % (m["board"], dl.get("meeting_date")), npk["legal_notice"]))) \
            if npk["sendable"] else '<span class=fine>Set config/newspaper.json to enable "send to newspaper".</span>'
        notif_btn = '<a class="btn alt" href="%s">Email the notification list &rarr;</a>' % esc(_mailto("", nem["subject"], nem["body"]))
        cards.append(
            '<div class=mtg><div class=mh><b>%s</b> &middot; meeting %s</div>'
            '<div class=cd style="color:%s">Notice deadline <b>%s</b> (post by %s) &middot; %s &middot; %d day(s) to deadline%s</div>'
            '<div class=fine>Required elements%s</div>'
            '<details><summary>Ready-to-file notice (HRS §92-7)</summary><pre class=notice>%s</pre></details>'
            '<div class=btns>%s %s</div>'
            '<div class=fine>Newspaper is opt-in / matter-specific (rezoning, budget, charter hearings) — '
            'NOT a §92 meeting requirement. The §92 act = county-calendar posting + clerk filing (the county performs these).</div>'
            '</div>'
            % (esc(m["board"]), esc(dl.get("meeting_date")), color, esc(dl.get("notice_deadline")),
               esc(dl.get("recommended_post_by")), esc(dl.get("status")), dl.get("days_to_deadline", 0), risk,
               esc(miss), esc(notice), news_btn, notif_btn))
    body = (
        '<div style="max-width:900px;margin:0 auto;padding:1.2rem 1rem">'
        '<h1 style="color:#0e4a84">Sunshine compliance &amp; distribution</h1>'
        '<p class=lead>Speed HRS §92 compliance: every upcoming meeting with its 6-day notice deadline, the '
        'required-elements check, the ready-to-file notice, and one-click distribution. The buttons open your '
        'mail client with everything filled in — you click send. This tool prepares; the County Clerk performs '
        'the official county-calendar posting + filing.</p>'
        '<style>.mtg{border:1px solid #d6e2f0;border-radius:10px;padding:.7rem .9rem;margin:.7rem 0;background:#081420}'
        '.mh{font-weight:700;color:#0e4a84}.cd{font-size:.92rem;margin:.3rem 0}.fine{color:#5a6b7b;font-size:.82rem;margin:.25rem 0}'
        '.notice{white-space:pre-wrap;background:#f6f9fc;border:1px solid #1f3d5f;border-radius:8px;padding:.6rem;font-size:.8rem;overflow:auto}'
        '.btns{margin:.5rem 0}.btn{display:inline-block;background:#0e4a84;color:#fff;font-weight:700;border-radius:8px;'
        'padding:.5rem .9rem;text-decoration:none;margin:.2rem .4rem .2rem 0}.btn.alt{background:#1f6f54}'
        'details summary{cursor:pointer;color:#0e4a84;font-size:.85rem;margin:.3rem 0}</style>'
        + ("".join(cards) or "<div class=fine>No upcoming meetings staged.</div>") +
        '<div class=fine style="margin-top:1rem">Assist only — confirm with the County Clerk / Corporation '
        'Counsel; OIP Attorney of the Day (808) 586-1400 for edge cases. Calendar days; meeting day excluded; '
        'late electronic posting cancels the meeting as a matter of law (§92-7(c)).</div></div>')
    html = ("<!doctype html><html lang=en><head><meta charset=utf-8>"
            "<meta name=viewport content=\"width=device-width,initial-scale=1\">"
            "<title>Sunshine Compliance — govOS (private)</title></head><body>" + body + "</body></html>")
    open(os.path.join(OUT, "board.html"), "w", encoding="utf-8", newline="\n").write(html)
    return {"meetings": len(meetings), "out": os.path.join(OUT, "board.html")}


def main():
    r = build()
    print("sunshine_board: %d upcoming meeting(s) -> %s" % (r["meetings"], r["out"]))
    return 0


if __name__ == "__main__":
    if sys.platform == "win32":
        import io; sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(main())
