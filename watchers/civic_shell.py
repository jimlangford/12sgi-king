#!/usr/bin/env python3
"""civic_shell.py — ONE shared chrome for every civic page, extracted verbatim from the 12sgi home page
(site/index.html, "the lovely one" — Jimmy 2026-06-19: "Can we have the site be like that").

THE UNIFY: the home page's design language = Yale-blue CSS-variable palette + JetBrains Mono machine values +
the ⚖ seal header + a clean footer. This module hands every generator (and a build-time wrap pass) that exact
header + footer + token stylesheet so the whole site matches the home page BY CONSTRUCTION instead of page by
page (JRCSL HIGH: unify, never fragment).

Everything here is NAMESPACED `cs-` so it injects alongside a page's own CSS without collisions. `wrap_html()`
takes a finished page's HTML and returns it with the shell tokens + header injected after <body> and the footer
before </body>, leaving the page's own body content untouched. Stdlib only. Color-only/markup-only — never
touches data or scripts.
"""
import os, re

# --- the home page's design tokens (verbatim from site/index.html :root) ---
TOKENS = (":root{--cs-bg:#ffffff;--cs-panel:#e7eef8;--cs-panel2:#dae5f3;--cs-line:#26456a;--cs-ink:#13243d;"
          "--cs-ink-dim:#41536b;--cs-ink-faint:#5b6e86;--cs-accent:#00356b;--cs-accent2:#1259a3;--cs-gold:#b8860b;"
          "--cs-ok:#1f8a5b;--cs-mono:'JetBrains Mono',Consolas,monospace}")

# --- header + footer CSS, namespaced so it never clashes with a report page's own classes ---
CHROME_CSS = (
    ".cs-top{max-width:1040px;margin:0 auto;padding:14px 20px;display:flex;align-items:center;gap:11px;"
    "font-family:'Segoe UI Variable Text','Segoe UI',system-ui,sans-serif}"
    ".cs-seal{width:34px;height:34px;border-radius:9px;background:var(--cs-accent);color:#fff;display:flex;"
    "align-items:center;justify-content:center;font-size:17px;flex:none;text-decoration:none}"
    ".cs-brand{font-weight:800;font-size:17px;color:var(--cs-ink);line-height:1.1}"
    ".cs-brand span{display:block;color:var(--cs-ink-faint);font-weight:600;font-size:11px;font-family:var(--cs-mono)}"
    ".cs-nav{margin-left:auto;display:flex;gap:16px;flex-wrap:wrap;font-size:13.5px;font-weight:600}"
    ".cs-nav a{color:var(--cs-accent2);text-decoration:none}.cs-nav a:hover{text-decoration:underline}"
    ".cs-bar{border-bottom:1px solid var(--cs-line);background:linear-gradient(180deg,rgba(0,53,107,.04),transparent)}"
    ".cs-foot{max-width:1040px;margin:40px auto 0;font-family:var(--cs-mono);font-size:11px;color:var(--cs-ink-faint);"
    "text-align:center;border-top:1px solid var(--cs-line);padding:24px 20px 38px;line-height:1.8}"
    "@media(max-width:560px){.cs-nav{gap:11px;font-size:12px}}")

NAV = [("reports.html", "dashboards"), ("jurisdictions.html", "jurisdictions"),
       ("datasets.html", "open data"), ("testify.html", "testify")]


def header_html(home="index.html"):
    nav = "".join('<a href="%s">%s</a>' % (h, l) for h, l in NAV)
    return ('<div class="cs-bar"><div class="cs-top">'
            '<a class="cs-seal" href="%s">⚖</a>'
            '<div class="cs-brand">govOS<span>by 12 Stones Global · the public record, in the open</span></div>'
            '<nav class="cs-nav">%s</nav></div></div>') % (home, nav)


def footer_html():
    return ('<footer class="cs-foot">govOS · 12 Stones Global &nbsp;·&nbsp; christ-aloha, solution-side '
            '&nbsp;·&nbsp; the public record, free for the people<br>'
            '&copy; 2026 James RCS Langford · all rights reserved</footer>')


def style_block():
    return "<style>%s %s</style>" % (TOKENS, CHROME_CSS)


def wrap_html(html, home="index.html"):
    """Inject the shared shell into a finished page: tokens+chrome CSS into <head>, header after <body>,
    footer before </body>. Idempotent (skips if already shelled). Body content is left untouched."""
    if "cs-foot" in html or 'class="cs-top"' in html:
        return html  # already shelled
    sb = style_block()
    # CSS: prefer right before </head>; fall back to right after <body>; else prepend.
    if re.search(r"</head>", html, re.I):
        html = re.sub(r"</head>", sb + "</head>", html, count=1, flags=re.I)
        css_done = True
    else:
        css_done = False
    m = re.search(r"<body[^>]*>", html, re.I)
    hdr = header_html(home)
    if m:
        ins = (("" if css_done else sb) + hdr)
        html = html[:m.end()] + ins + html[m.end():]
    else:
        html = (sb if not css_done else "") + hdr + html
    if re.search(r"</body>", html, re.I):
        html = re.sub(r"</body>", footer_html() + "</body>", html, count=1, flags=re.I)
    else:
        html = html + footer_html()
    return html


def wrap_file(path, home="index.html"):
    with open(path, encoding="utf-8") as f:
        html = f.read()
    out = wrap_html(html, home)
    if out != html:
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(out)
        return True
    return False


if __name__ == "__main__":
    import sys
    if sys.platform == "win32":
        import io; sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    # demo: wrap a copy of a sample page to *_shell.html so nothing canonical is mutated
    here = os.path.dirname(os.path.abspath(__file__))
    proj = os.path.dirname(os.path.dirname(here))
    sample = os.path.join(proj, "reports", "mauios", sys.argv[1] if len(sys.argv) > 1 else "money_kauai.html")
    with open(sample, encoding="utf-8") as f:
        html = f.read()
    out = wrap_html(html)
    dst = sample.replace(".html", "_shell.html")
    open(dst, "w", encoding="utf-8", newline="\n").write(out)
    print("wrapped %s -> %s (%d -> %d bytes); header=%s footer=%s" % (
        os.path.basename(sample), os.path.basename(dst), len(html), len(out),
        'class="cs-top"' in out, "cs-foot" in out))
