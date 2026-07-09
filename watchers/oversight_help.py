#!/usr/bin/env python3
"""oversight_help.py — the PUBLIC plain-language guide for the tenant oversight pages.

Jimmy 2026-06-20 ("user guides that need to be uploaded today, reasonably"): the oversight pages went
live this morning with no explainer. This is the citizen-facing help page — what "Questions for oversight"
means, why findings are framed as questions, that every claim is sourced, what an empty page means, and
that the people's records are always free. Public, leak-clean, aloha. Reuses the one civic stylesheet.

  python tools/kilo-aupuni/oversight_help.py     # writes reports/mauios/oversight_help.html
"""
import os, sys
from datetime import datetime, timezone, timedelta

TOOL_DIR = os.path.dirname(os.path.abspath(__file__))
if TOOL_DIR not in sys.path: sys.path.insert(0, TOOL_DIR)
import tenant_pages as TP          # the one Yale-blue civic stylesheet + esc (single source of truth)

HST = timezone(timedelta(hours=-10))
M = TP.M

# Plain-language, aloha sections. Each is a titled card the reader can scan.
SECTIONS = [
    ("Why every finding is a question",
     "The public record can show a pattern — a vote, a donation, a contract — but a pattern is not a verdict. "
     "So we ask the question and invite the government to show the record, rather than assume the answer. "
     "Every item on an oversight page is a question for the people and the officials alike — never an accusation."),
    ("Everything is sourced",
     "Each question names the public record behind it: campaign-spending filings, county contract awards, "
     "council minutes, committee testimony, permits. If a claim cannot be traced to a named public record, "
     "we do not show it. You can follow every link back to the source and see it for yourself."),
    ("When it says “the record is still being gathered”",
     "Some governments have a deeper public record than others. An empty page does not mean nothing is "
     "happening — it means no finding has yet met the bar to be shown publicly. We request the missing "
     "records (a UIPA request under Hawaiʻi’s open-records law) and they appear here as they come back. "
     "We never fill a gap with a guess, and never with another government’s data."),
    ("The people’s records are free",
     "Reading your government’s record always costs nothing. That is the covenant we hold ourselves to — "
     "serve equals charge: we never charge for what the public is already owed. Paid tools are only the "
     "extra help (drafting, analysis, oversight assistance); the record itself is, and stays, free."),
    ("What stays private",
     "The deeper working files — the prosecutorial preparation behind a question — stay private and are "
     "never published. Only sourced questions that clear an integrity review reach this public page. The "
     "same standard we hold the government to, we hold ourselves to."),
    ("How to use it",
     "1. Pick your government on the home page.  2. Open its dashboard.  3. Open “Questions for oversight.”  "
     "4. Read each question and follow the links to the public records behind it. After that, explore any "
     "part of the record freely — agendas, money, contracts, federal dollars, minutes."),
]


def render():
    g = datetime.now(HST).strftime("%Y-%m-%d %H:%M HST")
    css = TP.CSS + (
        ".card2{border:1px solid var(--line);border-left:3px solid var(--accent);border-radius:14px;"
        "padding:1rem 1.1rem;margin:.8rem 0;background:var(--panel)}"
        ".card2 h2{font-size:1.08rem;color:var(--ink);margin:0 0 .35rem;font-weight:650}"
        ".card2 p{color:var(--dim);font-size:.95rem;line-height:1.5;margin:0}")
    cards = "".join("<div class=card2><h2>%s</h2><p>%s</p></div>" % (TP.esc(t), TP.esc(b)) for t, b in SECTIONS)
    return ("<!doctype html><meta charset=utf-8>"
            "<meta name=viewport content='width=device-width,initial-scale=1,viewport-fit=cover'>"
            "<meta name=theme-color content='#00356b'>"
            "<title>How to read your government’s record | govOS</title><style>%s</style>"
            "<div class=eyebrow><a href='tenants_hub.html'>govOS</a> · Kilo Aupuni</div>"
            "<h1>How to read your government’s record</h1>"
            "<div class=sub>This is the public record of your government, organized around the questions that "
            "matter most — who governs, where the money comes from, who gets the contracts. We ask the record; "
            "we do not accuse. Here is how to read it.</div>"
            "%s"
            "<p class=sub style='margin-top:1.2rem'><a href='tenants_hub.html'>← pick your government</a></p>"
            "<p class=sub style='color:var(--faint);font-size:.85rem'>Public record · sourced · framed as "
            "questions, never accusations · the people’s records stay free · generated %s · aloha · pono</p>"
            % (css, cards, g))


def main():
    os.makedirs(M, exist_ok=True)
    out = os.path.join(M, "oversight_help.html")
    open(out, "w", encoding="utf-8", newline="\n").write(render())
    print("oversight_help: wrote %s" % out)
    return 0


if __name__ == "__main__":
    if sys.platform == "win32":
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(main())
