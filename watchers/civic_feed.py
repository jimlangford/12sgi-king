#!/usr/bin/env python3
"""civic_feed.py — the PUBLIC-SAFE feed that lets WordPress (12sgi.com) consume the civic system
(Jimmy 2026-06-18: "how can we use the civic system on that site and flourish").

The civic engine produces fresh, sourced content daily; this exposes the PUBLIC-SAFE slice of it as a
clean JSON + RSS feed any WordPress can pull (WP RSS import, a feed widget, or the REST API) — so the
site auto-fills with civic-transparency content with zero manual posting.

WHAT GOES IN (public-safe, leak-gated): the weekly newsletter issue, the upcoming-meeting reminders (the
body + date + kaulana-mahina moon + the aloha 'show up' invitation), and links to the live public reports.
WHAT NEVER GOES IN: the money lens / casework / hewa watchlist / any official-naming analysis (those stay
private until publish-confirm). A FORBIDDEN sweep aborts if a private/secret marker slips in.

Output: reports/mauios/civic_feed.json + reports/mauios/civic_feed.xml (RSS 2.0). Stdlib only.
"""
import os, sys, json, re, glob, html
from datetime import datetime, timezone, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(os.path.dirname(HERE))
M = os.path.join(PROJ, "reports", "mauios")
STMW = os.path.join(PROJ, "reports", "_status", "meeting_watch")
HST = timezone(timedelta(hours=-10))
PUBLIC = "https://jimlangford.github.io/12sgi-king"     # until 12sgi.com fronts it; then swap to https://12sgi.com
esc = lambda s: html.escape(str(s if s is not None else ""))
FORBIDDEN = re.compile(r"sk_live|rk_live|whsec_|prosecut|case_file|/king|oversight_|hewa_watchlist|"
                       r"EXAMINE|same_entity|recus|money.lens|casework", re.I)


def load(p, d):
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception:
        return d


def items():
    out = []
    # 1) the weekly newsletter issue (public-safe digest)
    nl = load(os.path.join(M, "newsletter", "latest.json"), {})
    if nl.get("subject"):
        fig = "; ".join("%s: %s" % (a, b) for a, b in (nl.get("figures") or [])[:4])
        out.append({"kind": "newsletter", "title": nl["subject"],
                    "summary": "This week on the public record. " + fig,
                    "link": "%s/newsletter.html" % PUBLIC, "date": nl.get("date", "")})
    # 2) upcoming-meeting reminders (PUBLIC parts only: body + date + moon + the aloha invitation)
    for mj in sorted(glob.glob(os.path.join(STMW, "*", "meeting.json")), reverse=True)[:8]:
        m = load(mj, {})
        if not m.get("body"):
            continue
        moon = m.get("moon") or {}
        moonline = ("Moon: %s, %s — %s. %s" % (moon.get("po", ""), moon.get("phase", ""),
                    moon.get("nature", ""), moon.get("offering", ""))).strip(" .—")
        out.append({"kind": "meeting", "title": "Watch out: %s — %s" % (m["body"], m.get("when", m.get("date", ""))),
                    "summary": ("An upcoming decision — be there in time. %s. A question for pono, never an "
                                "accusation; show up, testify, make the answer visible." % moonline),
                    "link": "%s/agenda_explainer.html" % PUBLIC, "date": m.get("date", "")})
    # 3) standing links to the live public reports (the data anyone can open)
    for label, page in (("Follow every dollar & vote", "reports.html"),
                        ("Explain your government — upcoming agendas", "agenda_explainer.html"),
                        ("Build our government software", "feature_board.html")):
        out.append({"kind": "report", "title": label, "summary": "Live public-records view, updated daily.",
                    "link": "%s/%s" % (PUBLIC, page), "date": ""})
    return out


def build():
    now = datetime.now(HST)
    its = items()
    feed = {"site": "12SGI Kilo Aupuni — civic transparency",
            "generated": now.strftime("%Y-%m-%d %H:%M:%S HST"),
            "note": "Public-safe civic feed for WordPress/any consumer. Sourced; questions for pono, never accusations.",
            "items": its}
    blob = json.dumps(feed, ensure_ascii=False)
    hit = FORBIDDEN.search(blob)
    if hit:
        raise SystemExit("LEAK GATE: forbidden marker %r in civic_feed — aborting." % hit.group(0))
    json.dump(feed, open(os.path.join(M, "civic_feed.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    # RSS 2.0 (WordPress imports this directly)
    rss = ['<?xml version="1.0" encoding="UTF-8"?>', '<rss version="2.0"><channel>',
           "<title>12SGI Kilo Aupuni — civic transparency</title>",
           "<link>%s</link>" % PUBLIC,
           "<description>Get ahead of the agenda: upcoming meetings, the money, the moon — sourced, in aloha.</description>"]
    for it in its:
        rss.append("<item><title>%s</title><link>%s</link><description>%s</description></item>"
                   % (esc(it["title"]), esc(it["link"]), esc(it["summary"])))
    rss.append("</channel></rss>")
    open(os.path.join(M, "civic_feed.xml"), "w", encoding="utf-8", newline="\n").write("\n".join(rss))
    return feed


def main():
    f = build()
    print("civic_feed: %d public-safe items (leak-gate PASS) -> civic_feed.{json,xml}" % len(f["items"]))
    for it in f["items"][:6]:
        print("  [%s] %s" % (it["kind"], it["title"][:70]))
    return 0


if __name__ == "__main__":
    if sys.platform == "win32":
        import io; sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(main())
