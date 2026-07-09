#!/usr/bin/env python3
"""link_check.py — no link on the built PUBLIC site may 404 ("the actual links must work").

Companion to orphan_check.py. Where orphan_check finds built pages that nothing links TO
(unreachable), link_check finds the opposite failure: a page that links to a target that
DOES NOT EXIST — a dead/broken link a real visitor would hit as a 404.

It walks every published page in REPO/site, extracts every INTERNAL reference (href, src,
data-src, action, poster, <option value=...>, AND .html/.css/.js/.json/asset tokens inside
inline JS + url(...) in inline CSS), resolves each the way GitHub Pages serves it
(/12sgi-king/ prefix, root-absolute, page-relative; a dir resolves to its index.html), and
reports any whose target file is missing on disk.

Output: a clear, ACTIONABLE list — {from_page, target, raw, kind} — not just a count, so the
exact broken link and the page it lives on are both named. Writes
reports/_status/broken_links.json + a public-safe site/broken_links.html dashboard panel.

Importable: `from link_check import find_broken_links`. Stdlib only; never fails a build by
itself — it reports, the operator (and selfheal/completeness_guard) gate on it.
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

# Pages we DON'T scan as link SOURCES (preview/temp artifacts). Their own links aren't shipped.
SKIP_SOURCE_BASENAME_PREFIX = ("_",)

# Internal references with these prefixes are external / non-file — never a broken-file case.
EXTERNAL_PREFIX = ("http://", "https://", "//", "mailto:", "tel:", "data:", "javascript:", "#")

# SEVERITY. A reference rendered by the browser into a real element (an <a href>, <link>, <img/script
# src>, <form action>, <option value>, CSS url()) that points to a missing file is a HARD 404 a visitor
# hits — that FAILS the gate. A bare quoted file token inside inline JS is SOFT: it may be a guarded
# fetch (r.ok?...:null), a server-routed path (king_serve.py serves /king/x.html dynamically), or an
# optional asset that degrades — reported for review but it does NOT fail the gate by itself.
HARD_KINDS = {"attr", "option", "css-url"}

# Verified-intentional / guarded / server-routed targets — never a real break, so excluded even from the
# SOFT review list (keeps the report trustworthy instead of crying wolf). Matched as a path SUBSTRING.
# - onboarding/tutorial.mp4 : optional tour video; the <video onerror> degrades to "tour video coming soon".
# - quadrant_progress.json  : optional data fetch in go.html, guarded `r.ok?r.json():null` (the .html page exists).
# - king/watcher.html / watcher.html : served dynamically by king_serve.py routing, not a static file.
EXEMPT_TARGET_SUBSTR = ("assets/onboarding/tutorial.mp4", "quadrant_progress.json",
                        "king/watcher.html", "watcher.html")

# Reference extractors (kind -> compiled regex returning the URL in group 1).
_ATTR = re.compile(r'(?:href|src|data-src|action|poster)\s*=\s*["\']([^"\'<>]+)["\']', re.I)
_OPTION = re.compile(r'<option[^>]*\bvalue\s*=\s*["\']([^"\']+\.html[^"\']*)["\']', re.I)
_CSSURL = re.compile(r'url\(\s*["\']?([^"\')]+)["\']?\s*\)', re.I)
# a real file-ish asset reference ends in a known asset/page extension (filters JS url()/mime
# types like image/png, blob:, a.href that aren't files — kills css-url false positives).
_ASSET_EXT = re.compile(r'\.(?:html?|css|js|json|png|jpe?g|svg|webp|gif|ico|woff2?|ttf|otf|eot|mp4|webm|pdf)(?:[?#].*)?$', re.I)
# quoted file-ish tokens inside inline JS (route tables, fetch(), location=) for the asset
# types that 404 as real pages/resources. Kept conservative to avoid false positives.
_JSTOK = re.compile(r'["\']([A-Za-z0-9_%.\-/]+\.(?:html|htm|css|js|json|png|jpg|jpeg|svg|webp|gif|ico|mp4|webm|pdf))(?:\?[^"\']*)?["\']', re.I)

def _resolve(tok, page_dir):
    """Resolve an internal reference to an absolute on-disk path the way GitHub Pages serves
    REPO/site. Returns None for external / template / non-resolvable tokens."""
    h = unquote(tok.split("?")[0].split("#")[0].strip())
    if not h:
        return None
    if h.lower().startswith(EXTERNAL_PREFIX):
        return None
    if "{{" in h or "}}" in h or "${" in h or "<" in h or ">" in h:   # template / JS expression, not a literal URL
        return None
    if h.startswith("/12sgi-king/"): base, rel = SITE, h[len("/12sgi-king/"):]
    elif h.startswith("/"):          base, rel = SITE, h.lstrip("/")
    else:                            base, rel = page_dir, h
    tgt = os.path.normpath(os.path.join(base, rel))
    return tgt

def _exists(tgt):
    if os.path.isfile(tgt):
        return True
    if os.path.isdir(tgt) and os.path.isfile(os.path.join(tgt, "index.html")):
        return True
    return False

def _refs(txt):
    """Yield (raw_token, kind) for every internal reference in a page's text."""
    for m in _ATTR.findall(txt):      yield m, "attr"
    for m in _OPTION.findall(txt):    yield m, "option"
    for m in _CSSURL.findall(txt):
        if _ASSET_EXT.search(m.split("#")[0]): yield m, "css-url"   # skip JS url()/mime non-files
    for m in _JSTOK.findall(txt):     yield m, "js-token"

def find_broken_links():
    """(hard[list], soft[list], checked_refs, pages) or None if site/ not built.

    Each broken entry = {from, target, raw, kind, severity}. HARD = a rendered ref (href/src/
    action/option/css url) that 404s for a visitor — these FAIL the gate. SOFT = a js-token ref
    that may be guarded/server-routed — reported for review, does not fail the gate. Verified-
    intentional targets (EXEMPT_TARGET_SUBSTR) are dropped entirely. `from`/`target` are
    site-relative (forward-slash). Dedup is on (from, resolved-target)."""
    if not os.path.isdir(SITE):
        return None
    hard, soft, checked, pages, seen = [], [], 0, 0, set()
    for root, _d, files in os.walk(SITE):
        for fn in files:
            if not fn.lower().endswith((".html", ".htm")):
                continue
            if fn.startswith(SKIP_SOURCE_BASENAME_PREFIX):
                continue
            src = os.path.normpath(os.path.join(root, fn))
            try:
                txt = open(src, encoding="utf-8", errors="ignore").read()
            except Exception:
                continue
            pages += 1
            src_rel = os.path.relpath(src, SITE).replace("\\", "/")
            for raw, kind in _refs(txt):
                tgt = _resolve(raw, root)
                if tgt is None:
                    continue
                checked += 1
                key = (src_rel, tgt)
                if key in seen:
                    continue
                seen.add(key)
                if _exists(tgt):
                    continue
                tgt_rel = os.path.relpath(tgt, SITE).replace("\\", "/")
                if any(x in tgt_rel for x in EXEMPT_TARGET_SUBSTR):
                    continue   # verified-intentional / guarded / server-routed — not a real break
                sev = "HARD" if kind in HARD_KINDS else "SOFT"
                rec = {"from": src_rel, "target": tgt_rel, "raw": raw[:200], "kind": kind, "severity": sev}
                (hard if sev == "HARD" else soft).append(rec)
    hard.sort(key=lambda b: (b["from"], b["target"]))
    soft.sort(key=lambda b: (b["from"], b["target"]))
    return hard, soft, checked, pages

def main():
    res = find_broken_links()
    now = datetime.now(HST)
    status_dir = os.path.join(PROJ, "reports", "_status")
    os.makedirs(status_dir, exist_ok=True)
    if res is None:
        print("link_check: site/ not built — run build_site.py first")
        return
    hard, soft, checked, pages = res
    out = {"generated": now.isoformat(), "pages": pages, "refs_checked": checked,
           "hard_count": len(hard), "soft_count": len(soft),
           "broken_count": len(hard),          # the GATE number = hard 404s only
           "broken": hard, "soft": soft}
    with open(os.path.join(status_dir, "broken_links.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    # public-safe dashboard panel (mirrors orphans.html styling) — gate on HARD
    ok = (len(hard) == 0)
    rows = "".join(
        "<tr><td style='font-family:Consolas,monospace;font-size:12.5px'>%s</td>"
        "<td style='font-family:Consolas,monospace;font-size:12.5px;color:#c0322c'>%s</td>"
        "<td style='color:#5b6e86;font-size:12px'>%s</td>"
        "<td style='color:#c0322c;font-weight:700'>BROKEN</td></tr>"
        % (esc(b["from"]), esc(b["target"]), esc(b["kind"])) for b in hard
    ) or "<tr><td colspan=4 style='color:#1f8a5b;font-weight:700'>None — every rendered internal link resolves &#10003;</td></tr>"
    page = (
        "<!DOCTYPE html><html lang=en><head><meta charset=UTF-8>"
        "<meta name=viewport content='width=device-width,initial-scale=1'>"
        "<title>Link check &middot; govOS self-heal</title><style>"
        "body{margin:0;background:#fff;color:#13243d;font-family:'Segoe UI',system-ui,sans-serif;line-height:1.5}"
        ".wrap{max-width:980px;margin:0 auto;padding:18px 16px 70px}"
        "h1{font-size:22px;margin:6px 0}.eyebrow{font-family:Consolas,monospace;font-size:11px;"
        "letter-spacing:1.5px;color:#00356b;text-transform:uppercase}"
        ".badge{display:inline-block;font-weight:700;border-radius:8px;padding:4px 12px;color:#fff;background:%s}"
        "table{width:100%%;border-collapse:collapse;margin-top:14px;font-size:14px}"
        "th,td{text-align:left;padding:8px 10px;border-bottom:1px solid #bacde6;vertical-align:top}"
        "th{font-family:Consolas,monospace;font-size:11px;text-transform:uppercase;color:#5b6e86}"
        ".note{font-size:12.5px;color:#5b6e86;margin-top:10px}</style></head><body><div class=wrap>"
        "<div class=eyebrow>govOS &middot; Kilo Aupuni &middot; self-heal</div>"
        "<h1>Link check <span class=badge>%s</span></h1>"
        "<p class=note>Every internal link on a built page must resolve to a real file. "
        "%d references across %d pages checked. Broken links below 404 for a real visitor until fixed.</p>"
        "<table><thead><tr><th>On page</th><th>Broken target</th><th>Kind</th><th>Status</th></tr></thead>"
        "<tbody>%s</tbody></table>"
        "<p class=note>Generated %s &middot; the continuous dead-link guard (companion to the orphan check).</p>"
        "</div></body></html>"
    ) % (("#1f8a5b" if ok else "#c0322c"),
         ("CLEAN" if ok else ("%d BROKEN" % len(hard))),
         checked, pages, rows, esc(now.strftime("%Y-%m-%d %H:%M HST")))
    if os.path.isdir(SITE):
        with open(os.path.join(SITE, "broken_links.html"), "w", encoding="utf-8", newline="\n") as f:
            f.write(page)
    print("link_check: %d refs / %d pages — %d HARD broken, %d soft (review)" % (
        checked, pages, len(hard), len(soft)))
    for b in hard[:40]:
        print("  HARD [%s] %s -> %s" % (b["kind"], b["from"], b["target"]))
    for b in soft[:20]:
        print("  soft [%s] %s -> %s" % (b["kind"], b["from"], b["target"]))

if __name__ == "__main__":
    main()
