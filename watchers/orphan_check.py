#!/usr/bin/env python3
"""orphan_check.py — no useful built surface stays unreachable ("check for heal").

Crawls the built PUBLIC site (REPO/site) from the front door + the injected nav, follows
every reference to another built page (anchors, iframe src, <select> option values, and
.html tokens in inline JS — so the tenant-switcher pulldown and go.html maps count as
reachable), and flags any built .html that is NOT reachable from anywhere navigable: an
ORPHAN. Built-but-useful work that isn't wired into nav or a tenant gets caught here (red)
until it's integrated.

Writes reports/_status/orphans.json + a public-safe site/orphans.html dashboard panel.
Importable: `from orphan_check import find_orphans`. Stdlib only; never fails a build by
itself — it reports, the operator (and selfheal) decide.
"""
import os, re, json, html
from urllib.parse import unquote
from datetime import datetime, timezone, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.abspath(os.path.join(HERE, "..", ".."))
HOME = os.path.expanduser("~")
HST  = timezone(timedelta(hours=-10))
def esc(s): return html.escape(str(s or ""))

def _repo():
    for c in (os.path.join(HOME, "Documents", "Claude", "12sgi-king"), os.getcwd()):
        if os.path.isfile(os.path.join(c, "build_site.py")):
            return c
    return os.getcwd()
REPO = _repo()
SITE = os.path.join(REPO, "site")

# Entry points the crawl seeds from (a visitor can always reach these directly).
SEEDS = ["index.html", "reports.html", "go.html", "jurisdictions.html", "reports_hub.html",
         "king/index.html", "king/app.html", "take_action.html", "testify.html",
         "king/govos_signup.html",   # still a public civic entry point even though the site root is now studio-first
         # HEAL-FORWARD (Jimmy 2026-07-01/02): real, sourced, standalone destinations that aren't woven
         # into a per-tenant nav — same category as take_action.html/testify.html above. blog.html's
         # own posts self-link once wired (see blog_engine.py static=True), so seeding blog.html here
         # pulls all of them in too. Re-applied 2026-07-02 after this file reverted to an older version
         # once already tonight -- see dispatch FINDING about tools/kilo-aupuni vs 12sgi-king/watchers
         # canonical-source confusion.
         "blog.html", "grants.html", "king/aupuni.html",
         # officials_maui.html: real, sourced "who governs" roster, superseded as the CANONICAL Maui
         # governance page by officials_scorecard.html (confirmed in tenant_registry.json) but not
         # garbage -- seeded rather than deleted; a content call on whether to keep both stays Jimmy's.
         "officials_maui.html",
         # tenant_coverage.html: the 9x16 coverage heatmap (dashboard redesign 2026-07-01) -- a
         # standalone destination, same category as datasets.html's Open Data page.
         "tenant_coverage.html",
         # great_mahele_overlay.html: the Great Mahele overlay (2026-07-02) -- standalone, same category.
         "great_mahele_overlay.html"]

# Built html that is intentionally NOT a navigable destination — never an orphan.
EXEMPT_EXACT = {"404.html", "go.html", "selfheal.html", "orphans.html", "navmap.html", "external_links.html"}
# Whole subtrees that are data/feed/embed partials, not pages.
EXEMPT_PREFIX = ("king/civic/templates/_feed/",)
# Suffixes that mark a fragment/component, not a standalone page:
#   *.dc.html — DataComponent shells the King app (app.html) imports + renders internally
#   via its dc-import router; they are never navigated to directly.
EXEMPT_SUFFIX = (".dc.html",)

# any path-ish token ending in .html (anchors, option values, JS string literals, iframe src)
TOK = re.compile(r'[A-Za-z0-9_%.\-/]+?\.html', re.I)

def _resolve(tok, root):
    h = unquote(tok.split("?")[0].split("#")[0].strip())
    if not h or "{{" in h or "}}" in h:
        return None
    if h.startswith(("http://", "https://", "//", "mailto:", "tel:", "data:", "javascript:")):
        return None
    if h.startswith("/12sgi-king/"): base, rel = SITE, h[len("/12sgi-king/"):]
    elif h.startswith("/"):          base, rel = SITE, h.lstrip("/")
    else:                            base, rel = root, h
    tgt = os.path.normpath(os.path.join(base, rel))
    if os.path.isdir(tgt):
        tgt = os.path.join(tgt, "index.html")
    return tgt

def find_orphans():
    """(orphans[rel], reachable_count, total_count) or None if site/ not built."""
    if not os.path.isdir(SITE):
        return None
    universe = set()
    for root, _d, files in os.walk(SITE):
        for fn in files:
            if fn.lower().endswith((".html", ".htm")):
                universe.add(os.path.normpath(os.path.join(root, fn)))
    seen, queue = set(), []
    for s in SEEDS:
        p = os.path.normpath(os.path.join(SITE, s))
        if os.path.exists(p) and p not in seen:
            seen.add(p); queue.append(p)
    while queue:
        cur = queue.pop()
        try:
            txt = open(cur, encoding="utf-8", errors="ignore").read()
        except Exception:
            continue
        root = os.path.dirname(cur)
        for tok in TOK.findall(txt):
            tgt = _resolve(tok, root)
            if tgt and tgt.lower().endswith((".html", ".htm")) and tgt in universe and tgt not in seen:
                seen.add(tgt); queue.append(tgt)
    orphans = []
    for p in sorted(universe):
        if p in seen:
            continue
        rel = os.path.relpath(p, SITE).replace("\\", "/")
        if rel in EXEMPT_EXACT or any(rel.startswith(x) for x in EXEMPT_PREFIX) \
           or any(rel.endswith(x) for x in EXEMPT_SUFFIX):
            continue
        orphans.append(rel)
    return orphans, len(seen), len(universe)

def main():
    res = find_orphans()
    now = datetime.now(HST)
    status_dir = os.path.join(PROJ, "reports", "_status")
    os.makedirs(status_dir, exist_ok=True)
    if res is None:
        print("orphan_check: site/ not built — run build_site.py first")
        return
    orphans, reach, total = res
    out = {"generated": now.isoformat(), "reachable": reach, "total": total,
           "orphans": orphans, "orphan_count": len(orphans)}
    with open(os.path.join(status_dir, "orphans.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    # public-safe dashboard panel
    ok = (len(orphans) == 0)
    rows = "".join(
        "<tr><td style='font-family:Consolas,monospace;font-size:12.5px'>%s</td>"
        "<td style='color:#c0322c;font-weight:700'>ORPHAN</td></tr>" % esc(o) for o in orphans
    ) or "<tr><td colspan=2 style='color:#4ec98a;font-weight:700'>None — every built page is reachable ✓</td></tr>"
    page = (
        "<!DOCTYPE html><html lang=en><head><meta charset=UTF-8>"
        "<meta name=viewport content='width=device-width,initial-scale=1'>"
        "<title>Orphan check · govOS self-heal</title><style>"
        "body{margin:0;background:#081420;color:#eaf2fc;font-family:'Segoe UI',system-ui,sans-serif;line-height:1.5}"
        ".wrap{max-width:860px;margin:0 auto;padding:18px 16px 70px}"
        "h1{font-size:22px;margin:6px 0}.eyebrow{font-family:Consolas,monospace;font-size:11px;"
        "letter-spacing:1.5px;color:#7fb2ff;text-transform:uppercase}"
        ".badge{display:inline-block;font-weight:700;border-radius:8px;padding:4px 12px;color:#fff;background:%s}"
        "table{width:100%%;border-collapse:collapse;margin-top:14px;font-size:14px}"
        "th,td{text-align:left;padding:8px 10px;border-bottom:1px solid #26456a}"
        "th{font-family:Consolas,monospace;font-size:11px;text-transform:uppercase;color:#8ea3ba}"
        ".note{font-size:12.5px;color:#8ea3ba;margin-top:10px}</style></head><body><div class=wrap>"
        "<div class=eyebrow>govOS · Kilo Aupuni · self-heal</div>"
        "<h1>Orphan check <span class=badge>%s</span></h1>"
        "<p class=note>Every built public page should be reachable from the nav or a tenant. "
        "%d of %d pages reachable. Orphans below stay flagged until they're wired in.</p>"
        "<table><thead><tr><th>Built page</th><th>Status</th></tr></thead><tbody>%s</tbody></table>"
        "<p class=note>Generated %s · the continuous &quot;check for heal&quot; orphan guard.</p>"
        "</div></body></html>"
    ) % (("#1f8a5b" if ok else "#c0322c"),
         ("CLEAN" if ok else ("%d ORPHAN%s" % (len(orphans), "" if len(orphans) == 1 else "S"))),
         reach, total, rows, esc(now.strftime("%Y-%m-%d %H:%M HST")))
    if os.path.isdir(SITE):
        with open(os.path.join(SITE, "orphans.html"), "w", encoding="utf-8", newline="\n") as f:
            f.write(page)
    print("orphan_check: %d/%d reachable · %d orphan(s)" % (reach, total, len(orphans)))
    for o in orphans:
        print("  ORPHAN:", o)

if __name__ == "__main__":
    main()
