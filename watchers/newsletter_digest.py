#!/usr/bin/env python3
"""newsletter_digest.py — the WEEKLY civic newsletter, auto-populated from the work we do (Jimmy 2026-06-18:
"this type of information we wanna put in our newsletter ... have the work that we do populated").

LANE: CIVIC (content). This builds the ISSUE only — public-safe, leak-gated, question-framed. The
subscriber list + delivery are the SERVER lane (tools/ops/newsletter_subscribers.py); this hands them a
finished issue. Sending is gated on Jimmy + a delivery key — this module never sends.

PUBLIC-SAFE ONLY: pulls headline figures + live public links from the already-public civic data
(federal money totals, the audit scorecard, agendas, dashboards). It NEVER includes the private
prosecutorial cross-check (testimony_crosscheck is owner-held), case files, oversight, donor-by-name
detail, or anything under reports/_status. A leak check aborts the build if a private/secret marker slips in.

Output: reports/mauios/newsletter/issue_<YYYY-MM-DD>.{html,txt} + latest.json (what the sender reads).
Stdlib only. Run weekly (audit_cycle / a scheduled tick).
"""
import os, sys, json, re, html
from datetime import datetime, timezone, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(os.path.dirname(HERE))
M = os.path.join(PROJ, "reports", "mauios")
OUT = os.path.join(M, "newsletter"); os.makedirs(OUT, exist_ok=True)
HST = timezone(timedelta(hours=-10))
PUBLIC = "https://jimlangford.github.io/12sgi-king"      # the public site (curated subset)
esc = lambda s: html.escape(str(s if s is not None else ""))

# markers that must NEVER appear in a public newsletter (leak gate)
FORBIDDEN = re.compile(r"sk_live|rk_live|whsec_|prosecut|case_file|/king|oversight_|password|api_token|"
                       r"webhook_secret|reports/_status|recusal", re.I)


def load(p, d):
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception:
        return d


def _money(v):
    try:
        return "$%s" % "{:,.0f}".format(float(v))
    except Exception:
        return None


def gather_figures():
    """Public-safe headline numbers. Each is a fact + framed as a question, never an accusation."""
    figs = []
    fed = load(os.path.join(M, "federal_money_maui.json"), {})
    totals = fed.get("totals") or {}
    counts = fed.get("counts") or {}
    # render whatever HI/Maui dollar totals exist (keys vary; pick the biggest two)
    for key in ("hawaii", "hi", "state", "maui"):
        if key in totals and _money(totals[key]):
            n = counts.get(key)
            figs.append(("Federal dollars landing in %s" % ("Hawaiʻi" if key in ("hawaii", "hi", "state") else "Maui"),
                         _money(totals[key]) + (" across %s awards" % "{:,}".format(n) if isinstance(n, (int, float)) else "")))
    ab = load(os.path.join(M, "audit_balance.json"), {})
    if isinstance(ab.get("open_total"), int):
        figs.append(("Money-and-votes pairs we're examining", "%d open questions on the public record" % ab["open_total"]))
    # dashboard counts (agendas / permits / bids) if the dashboard json is present + public-safe
    dash = load(os.path.join(M, "dashboard.json"), {}) or load(os.path.join(M, "kilo_dashboard.json"), {})
    for label, keys in (("Public agendas tracked", ("agendas", "agenda_count")),
                        ("County permits indexed", ("permits", "permit_count")),
                        ("Bids & contracts watched", ("bids", "bid_count"))):
        for k in keys:
            if isinstance(dash.get(k), (int, float)):
                figs.append((label, "{:,}".format(dash[k]))); break
    return figs[:6]


def gather_watching():
    """This week's public agendas + the live pages a reader can open. Public links only."""
    items = [
        ("See every dollar &amp; vote", "%s/reports.html" % PUBLIC),
        ("Explain your government — agendas &amp; what's being decided", "%s/explainer.html" % PUBLIC),
        ("Build our government software (vote &amp; request)", "%s/feature_board.html" % PUBLIC),
    ]
    return items


def gather_dept_items(cat_path):
    """Pull department items from the newsletter catalog.
    ao_pono / gate=public → include as explainers (up to 3).
    ao_hewa / gate=gated_sourced_question → include as framed questions only if source_href present (up to 2).
    po_hewa / gate=owner_only → NEVER included here.
    """
    try:
        cat = load(cat_path, {})
    except Exception:
        return [], []
    public_items, gated_items = [], []
    for it in cat.get("department_items", []):
        gate = it.get("gate", "")
        src = it.get("source_href", "")
        headline = it.get("headline", "")
        angle = it.get("angle", "")
        if not headline:
            continue
        if gate == "public":
            public_items.append({"headline": headline, "angle": angle, "source_href": src,
                                  "dept": it.get("department_name", ""), "tenant": it.get("tenant", "")})
        elif gate == "gated_sourced_question" and src:
            gated_items.append({"headline": headline, "angle": angle, "source_href": src,
                                 "dept": it.get("department_name", ""), "tenant": it.get("tenant", "")})
    # cap so the digest stays focused
    return public_items[:3], gated_items[:2]


def build():
    now = datetime.now(HST)
    figs = gather_figures()
    watch = gather_watching()
    cat_path = os.path.join(PROJ, "config", "newsletter_catalog.json")
    pub_items, gated_items = gather_dept_items(cat_path)
    date = now.strftime("%Y-%m-%d")
    week = now.strftime("Week of %B %-d, %Y") if os.name != "nt" else now.strftime("Week of %B %d, %Y")

    fig_html = "".join("<tr><td class=l>%s</td><td class=v>%s</td></tr>" % (esc(a), esc(b)) for a, b in figs) \
        or "<tr><td class=fine colspan=2>This week's figures publish with the next audit cycle.</td></tr>"
    watch_html = "".join("<li><a href='%s'>%s</a></li>" % (esc(u), l) for l, u in watch)
    fig_txt = "\n".join("  - %s: %s" % (a, b) for a, b in figs) or "  (figures publish with the next audit cycle)"
    watch_txt = "\n".join("  - %s  %s" % (re.sub('&amp;', '&', l), u) for l, u in watch)

    # department explainers (ao_pono, public gate)
    dept_html = ""
    dept_txt = ""
    if pub_items or gated_items:
        dept_rows = ""
        dept_lines = []
        for it in pub_items:
            dept_rows += ("<div style='border-left:3px solid #1f6f54;padding:.5rem .8rem;margin:.6rem 0'>"
                          "<b style='font-size:.95rem'>%s</b>"
                          "<p style='font-size:.88rem;color:#9fb2c8;margin:.25rem 0 0'>%s</p>"
                          "%s</div>" % (
                          esc(it["headline"]), esc(it["angle"]),
                          ("<a href='%s' style='font-size:.8rem;color:#7fb2ff'>Source &#8599;</a>" % esc(it["source_href"])
                           if it.get("source_href") else "")))
            dept_lines.append("  %s\n    %s%s" % (it["headline"], it["angle"],
                               ("\n    Source: %s" % it["source_href"]) if it.get("source_href") else ""))
        for it in gated_items:
            dept_rows += ("<div style='border-left:3px solid #c07b2a;padding:.5rem .8rem;margin:.6rem 0'>"
                          "<b style='font-size:.95rem'>%s</b>"
                          "<p style='font-size:.88rem;color:#9fb2c8;margin:.25rem 0 0'>%s</p>"
                          "<span style='font-size:.78rem;color:#8a6020;font-style:italic'>Public question — "
                          "verify before relying on it.</span> "
                          "%s</div>" % (
                          esc(it["headline"]), esc(it["angle"]),
                          ("<a href='%s' style='font-size:.8rem;color:#7fb2ff'>Source &#8599;</a>" % esc(it["source_href"])
                           if it.get("source_href") else "")))
            dept_lines.append("  [public question] %s\n    %s%s" % (it["headline"], it["angle"],
                               ("\n    Source: %s" % it["source_href"]) if it.get("source_href") else ""))
        dept_html = ("<h2 style='color:#7fb2ff;font-size:1.05rem;margin-top:1.1rem'>"
                     "Know your government</h2>%s" % dept_rows)
        dept_txt = "KNOW YOUR GOVERNMENT\n%s\n\n" % "\n\n".join(dept_lines)

    html_issue = (
        "<!doctype html><html lang=en><head><meta charset=utf-8>"
        "<meta name=viewport content='width=device-width,initial-scale=1'>"
        "<title>12SGI Kilo Aupuni — %s</title></head>"
        "<body style='margin:0;background:#0f2540;font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;color:#1f2d3a'>"
        "<div style='max-width:600px;margin:0 auto;background:#fff'>"
        "<div style='background:#0e4a84;color:#fff;padding:1.2rem 1.4rem'>"
        "<div style='font-size:.8rem;letter-spacing:.12em;opacity:.85'>12SGI · KILO AUPUNI</div>"
        "<div style='font-size:1.35rem;font-weight:700;margin-top:.2rem'>The people's watch on the money &amp; the votes</div>"
        "<div style='font-size:.85rem;opacity:.9;margin-top:.3rem'>%s</div></div>"
        "<div style='padding:1.2rem 1.4rem'>"
        "<p style='font-size:1rem;line-height:1.5'>Here is what the public record showed this week — facts you can "
        "open and check yourself. Every figure is a <b>question for oversight</b>, never an accusation.</p>"
        "<h2 style='color:#7fb2ff;font-size:1.05rem'>By the numbers</h2>"
        "<table style='border-collapse:collapse;width:100%%;font-size:.92rem'>"
        "<style>.l{padding:.4rem .2rem;border-bottom:1px solid #eef3f9}.v{padding:.4rem .2rem;border-bottom:1px solid #eef3f9;"
        "text-align:right;font-weight:700;color:#1f6f54}.fine{color:#9fb2c8;font-size:.85rem;padding:.5rem .2rem}</style>%s</table>"
        "%s"
        "<h2 style='color:#7fb2ff;font-size:1.05rem;margin-top:1.1rem'>Dig in yourself</h2>"
        "<ul style='font-size:.95rem;line-height:1.7;padding-left:1.1rem'>%s</ul>"
        "<p style='font-size:.85rem;color:#9fb2c8;border-top:1px solid #eef3f9;padding-top:.8rem;margin-top:1.2rem'>"
        "Sourced from public records — Hawaiʻi Campaign Spending Commission, USASpending.gov, county agendas &amp; "
        "contracts. Christ energy = aloha in action; rigor in the numbers, aloha in the asking.</p>"
        "<p style='font-size:.78rem;color:#8a97a6'>You're receiving this because you signed up at the free level on "
        "12SGI. <a href='{{unsubscribe_url}}' style='color:#8a97a6'>Unsubscribe</a> anytime.</p>"
        "</div></div></body></html>"
        % (esc(week), esc(week), fig_html, dept_html, watch_html))

    txt_issue = (
        "12SGI · KILO AUPUNI — %s\n"
        "The people's watch on the money & the votes\n\n"
        "What the public record showed this week. Every figure is a question for oversight, never an accusation.\n\n"
        "BY THE NUMBERS\n%s\n\n"
        "%s"
        "DIG IN YOURSELF\n%s\n\n"
        "Sourced from public records (HI Campaign Spending Commission, USASpending.gov, county agendas & contracts).\n"
        "You signed up at the free level on 12SGI. Unsubscribe: {{unsubscribe_url}}\n"
        % (week, fig_txt, dept_txt, watch_txt))

    # LEAK GATE — never ship a private/secret marker to the public
    blob = html_issue + txt_issue
    hit = FORBIDDEN.search(blob)
    if hit:
        raise SystemExit("LEAK GATE: forbidden marker %r in newsletter issue — aborting (fix the source)." % hit.group(0))

    hp = os.path.join(OUT, "issue_%s.html" % date)
    tp = os.path.join(OUT, "issue_%s.txt" % date)
    open(hp, "w", encoding="utf-8", newline="\n").write(html_issue)
    open(tp, "w", encoding="utf-8", newline="\n").write(txt_issue)
    latest = {"date": date, "week": week, "subject": "12SGI Kilo Aupuni — %s" % week,
              "html_path": os.path.relpath(hp, PROJ), "txt_path": os.path.relpath(tp, PROJ),
              "figures": figs, "dept_public": len(pub_items), "dept_gated": len(gated_items),
              "generated": now.strftime("%Y-%m-%d %H:%M:%S HST"), "leak_check": "PASS"}
    json.dump(latest, open(os.path.join(OUT, "latest.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return latest


def main():
    L = build()
    print("newsletter_digest: built issue %s (%d figures, %d public dept + %d gated, leak-gate PASS) -> %s" % (
          L["date"], len(L["figures"]), L.get("dept_public", 0), L.get("dept_gated", 0), L["html_path"]))
    return 0


if __name__ == "__main__":
    if sys.platform == "win32":
        import io; sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(main())
