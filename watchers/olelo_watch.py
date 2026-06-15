#!/usr/bin/env python3
"""olelo_watch.py — every Hawaiian word/concept the system uses, held with humility.

Extracts each ʻŌlelo Hawaiʻi term in use across the civic site + the Sage realm data, publishes a
PUBLIC glossary that states plainly the words are under ʻŌiwi community review, and prepares the body of
a weekly verification email to ʻŌiwi resources at Maui County. Jimmy reviews + sends the Gmail draft;
this script NEVER sends anything. The on-site notice makes the review visible to the public.

Grounding: definitions here are plain working glosses, every one marked review-pending. We do not assert
authority over ʻōlelo — we ask. Stdlib only. Outputs into reports/mauios/ so build_site publishes them.
"""
import os, re, json, html
from datetime import datetime, timezone, timedelta

HERE   = os.path.dirname(os.path.abspath(__file__))
PROJ   = os.path.abspath(os.path.join(HERE, "..", ".."))
MAUIOS = os.path.join(PROJ, "reports", "mauios")
HST    = timezone(timedelta(hours=-10))
def esc(s): return html.escape(str(s or ""))

# Department of ʻŌiwi Resources, County of Maui — the verification recipient (Jimmy reviews + sends).
OIWI_EMAIL = "oiwi@mauicounty.gov"
OIWI_NAME  = "Department of ʻŌiwi Resources, County of Maui"
OIWI_PHONE = "808-270-1719"

# Curated core lexicon: term -> (plain working gloss, kind). EVERY gloss is review-pending by design.
# These are the words we actually surface; ʻŌiwi resources confirm/correct them.
LEXICON = {
    "aloha": ("love, compassion, the breath of life shared — for us, Christ-energy in action", "concept"),
    "pono": ("rightness, balance, things in their proper order", "concept"),
    "hewa": ("a wrong, an imbalance — a pair that does not answer", "concept"),
    "kaulana mahina": ("the Hawaiian moon calendar — the named nights of the month", "concept"),
    "anahulu": ("a 10-night period; the month has three (waxing, full, waning)", "concept"),
    "pō": ("night; also the deep dark from which life unfolds (Kumulipo)", "concept"),
    "ao": ("light, day; the world of form and the living", "concept"),
    "akua": ("god, deity, elemental source-energy", "concept"),
    "kapu": ("sacred, set-apart, restricted", "concept"),
    "mana": ("spiritual power, life-force", "concept"),
    "ʻāina": ("land; that which feeds", "concept"),
    "mauka": ("toward the mountain, inland / upland", "place"),
    "makai": ("toward the sea", "place"),
    "ahupuaʻa": ("a land division running mountain-to-sea", "place"),
    "kumulipo": ("the Hawaiian cosmogonic genealogy chant of creation", "source"),
    "wā": ("an era / epoch — the Kumulipo unfolds in wā", "source"),
    "ʻōiwi": ("native, of the bone — Native Hawaiian", "people"),
    "ʻōlelo hawaiʻi": ("the Hawaiian language", "concept"),
    "lawaiʻa": ("fisherman; the practice of fishing", "practice"),
    "hukilau": ("communal net-fishing, all hands pulling together", "practice"),
    "makahiki": ("the season sacred to Lono — harvest, peace, no war", "concept"),
    "pele": ("akua of fire and volcano", "akua"),
    "kāne": ("akua of fresh water, sunlight, life", "akua"),
    "lono": ("akua of rain, harvest, peace, Makahiki", "akua"),
    "kanaloa": ("akua of the deep ocean", "akua"),
    "kū": ("akua of the upright, of standing, of work", "akua"),
    "ʻōhiʻa": ("the native ʻōhiʻa lehua tree", "plant"),
    "kilo": ("to observe closely; a watcher / observer", "practice"),
    "aupuni": ("nation, government, dominion", "concept"),
    "kilo aupuni": ("watching the nation — the civic-observer engine", "concept"),
    "māhealani": ("the full-moon night — abundance, clarity", "moon"),
    "muku": ("the dark-moon night — rest, the close before renewal", "moon"),
    "hilo": ("the first thin-crescent night — beginnings", "moon"),
    "hoku": ("a near-full night — fullness, peak", "moon"),
    "lāʻau": ("medicine; the medicine nights of the moon", "moon"),
    "kāloa": ("the Kanaloa (ocean) nights of the waning moon", "moon"),
}

def _scan_usage():
    """Count occurrences of each term across the published civic HTML (case-insensitive)."""
    usage = {t: 0 for t in LEXICON}
    pages = {t: set() for t in LEXICON}
    if not os.path.isdir(MAUIOS):
        return usage, pages
    for fn in os.listdir(MAUIOS):
        if not fn.lower().endswith((".html", ".htm")):
            continue
        try:
            txt = open(os.path.join(MAUIOS, fn), encoding="utf-8", errors="ignore").read().lower()
        except Exception:
            continue
        for t in LEXICON:
            n = txt.count(t.lower())
            if n:
                usage[t] += n
                pages[t].add(fn)
    return usage, pages

def _realm_terms():
    """Pull living Hawaiian terms from the Sage realm data (lineage names + akua)."""
    found = set()
    for rel in (("node_map", "node_map_canonical.json"), ("config", "sage_deck_cards.json")):
        p = os.path.join(PROJ, *rel)
        try:
            blob = open(p, encoding="utf-8", errors="ignore").read().lower()
        except Exception:
            continue
        for t in LEXICON:
            if t.lower() in blob:
                found.add(t)
    return found

def build():
    usage, pages = _scan_usage()
    realm = _realm_terms()
    now = datetime.now(HST)
    # terms in actual use anywhere (site or realm data)
    live = sorted([t for t in LEXICON if usage[t] > 0 or t in realm],
                  key=lambda t: (-usage[t], t))
    os.makedirs(MAUIOS, exist_ok=True)

    # ---- public glossary page (states the community-review posture plainly) ----
    rows = []
    for t in live:
        gloss, kind = LEXICON[t]
        where = ", ".join(sorted(p.replace(".html", "") for p in pages[t])[:6]) or "Sage realm data"
        rows.append(
            '<tr><td class="t">%s</td><td class="k">%s</td><td class="g">%s</td>'
            '<td class="u">%d</td><td class="w">%s</td></tr>' % (
                esc(t), esc(kind), esc(gloss), usage[t], esc(where)))
    notice = (
        '<div class="olelo-notice">🌺 <b>ʻŌlelo Hawaiʻi here is under community review.</b> '
        'Every Hawaiian word and concept we use is sent each week to ʻŌiwi resources at Maui County for '
        'verification. These are working glosses offered with humility, not authority — if a word is '
        'wrong, we will fix it. Offerings tied to the moon are "traditionally a night for…", never '
        'directives; the sacred bindings stay kumu-validation-pending.</div>')
    page = (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<title>ʻŌlelo Hawaiʻi — words under community review · govOS</title><style>"
        "body{margin:0;background:#0e1311;color:#e8e4d6;font-family:-apple-system,Segoe UI,Roboto,sans-serif;line-height:1.55}"
        ".wrap{max-width:1000px;margin:0 auto;padding:26px 18px 60px}"
        "h1{font-size:24px;margin:.2em 0}.sub{color:#9a957f;font-size:14px;margin-bottom:18px}"
        ".olelo-notice{background:rgba(217,178,76,.07);border:1px solid rgba(217,178,76,.4);border-radius:12px;"
        "padding:14px 16px;font-size:14px;color:#e7dcc0;margin:14px 0 22px}"
        "table{width:100%;border-collapse:collapse;font-size:14px}"
        "th,td{text-align:left;padding:8px 10px;border-bottom:1px solid rgba(255,255,255,.07);vertical-align:top}"
        "th{color:#9fd9bf;font-size:12px;text-transform:uppercase;letter-spacing:.04em}"
        ".t{font-weight:700;color:#cdb4f0;white-space:nowrap}.k{color:#9a957f;font-size:12px}"
        ".g{color:#e8e4d6}.u{color:#9fd9bf;text-align:right}.w{color:#9a957f;font-size:12px}"
        "footer{margin-top:24px;color:#9a957f;font-size:12px}</style></head><body><div class='wrap'>"
        "<h1>ʻŌlelo Hawaiʻi — words we use, held with humility</h1>"
        "<div class='sub'>" + str(len(live)) + " terms in use across govOS + the Sage realm · "
        + esc(now.strftime("%Y-%m-%d %H:%M HST")) + "</div>"
        + notice +
        "<table><thead><tr><th>Term</th><th>Kind</th><th>Working gloss (review-pending)</th>"
        "<th>Used</th><th>Where</th></tr></thead><tbody>" + "".join(rows) + "</tbody></table>"
        "<footer>Sent weekly to the County of Maui Department of ʻŌiwi Resources (" + esc(OIWI_EMAIL) +
        ") for verification · a working glossary, corrected by community guidance · Kilo Aupuni</footer>"
        "</div></body></html>")
    with open(os.path.join(MAUIOS, "olelo_glossary.html"), "w", encoding="utf-8", newline="\n") as f:
        f.write(page)

    # ---- weekly email body (Jimmy reviews + sends as a Gmail draft; never auto-sent) ----
    lines = [
        "To: %s <%s>" % (OIWI_NAME, OIWI_EMAIL),
        "Subject: ʻŌlelo Hawaiʻi verification — govOS / Kilo Aupuni (%s)" % now.strftime("%Y-%m-%d"),
        "",
        "Aloha kākou,",
        "",
        "Mahalo for helping us hold ʻŌlelo Hawaiʻi with care. The govOS / Kilo Aupuni civic-transparency",
        "site uses the Hawaiian words and concepts listed below. We offer working glosses with humility and",
        "ask for your verification or correction — if any word, meaning, or usage is wrong, we will fix it.",
        "",
        "Words and concepts currently in use (" + str(len(live)) + "), with our working gloss:",
        "",
    ]
    for t in live:
        gloss, kind = LEXICON[t]
        lines.append("  - %s (%s): %s" % (t, kind, gloss))
    lines += [
        "",
        "We also bind some words to the kaulana mahina (moon) nights as gentle civic 'offerings'",
        "(e.g. a night to stand and testify, a night to listen). These are framed 'traditionally a night",
        "for…', never as directives, and we mark every sacred binding as pending your guidance.",
        "",
        "If you would prefer we remove or rephrase anything, please tell us and it is done.",
        "",
        "Me ke aloha,",
        "Jimmy Langford · 12 Stones / Kilo Aupuni",
        "https://jimlangford.github.io/12sgi-king/olelo_glossary.html",
    ]
    digest = "\n".join(lines)
    with open(os.path.join(MAUIOS, "olelo_digest.txt"), "w", encoding="utf-8", newline="\n") as f:
        f.write(digest)

    # ---- machine data ----
    data = {
        "generated": now.isoformat(),
        "subject": "ʻŌlelo Hawaiʻi verification — govOS / Kilo Aupuni (%s)" % now.strftime("%Y-%m-%d"),
        "terms": [{"term": t, "kind": LEXICON[t][1], "gloss": LEXICON[t][0],
                   "used": usage[t], "pages": sorted(pages[t])} for t in live],
        "recipient": OIWI_EMAIL, "recipient_name": OIWI_NAME, "recipient_phone": OIWI_PHONE,
        "note": "working glosses, community-review pending; Gmail draft is reviewable — never auto-sent",
    }
    with open(os.path.join(MAUIOS, "olelo_terms.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)

    print("olelo-watch: %d terms in use -> glossary + weekly digest draft (review-pending, not sent)" % len(live))
    return data

if __name__ == "__main__":
    build()
