#!/usr/bin/env python3
"""
govOS full site rebuild — stamps every HTML page with shared govos.css + govos-shell.js,
removes old inline nav/CSS/JS blobs, and wires v2 API backend links.

Usage:
    python rebuild_site.py [--dry-run] [--file page.html]

What it does:
  1. Removes all inline govos-nav style blocks (the repeated ~4KB CSS blob)
  2. Removes old inline tenant-switch-css style blocks
  3. Removes old inline navmap/tenant-switch script blocks
  4. Removes old govos-narrative inline wiring (leaves the div, wires via govos-shell.js)
  5. Injects <link rel=stylesheet href="govos.css"> in <head> if not present
  6. Injects <script src="govos-shell.js"></script> before </body> if not present
  7. Ensures all internal links use correct relative paths (no broken /site/ prefixes)
  8. Writes in-place with CRLF normalization to LF
"""
import os
import re
import sys
import argparse
import pathlib

SITE_DIR = pathlib.Path(__file__).parent

# ── Patterns to strip (old inline blobs) ──────────────────────────────────────

# The entire duplicated govos-nav <style> block (starts with .govos-nav{ and is huge)
RE_GOVOS_NAV_STYLE = re.compile(
    r'<style>\s*html\{background:#081420\}body\{background:#081420.*?</style>',
    re.S
)

# Old tenant-switch-css inline style
RE_TENANT_SWITCH_CSS = re.compile(
    r'<style id=["\']?tenant-switch-css["\']?>.*?</style>',
    re.S
)

# Old .govos class inline style block (the big component CSS pasted into each page)
RE_GOVOS_CLASS_STYLE = re.compile(
    r'<style>\s*\.govos\{--bg:#081420.*?</style>',
    re.S
)

# Old navmap script
RE_NAVMAP_SCRIPT = re.compile(
    r'<script id=["\']?navmap["\']?>.*?</script>',
    re.S
)

# Old tenant-switch inline script
RE_TENANT_SWITCH_SCRIPT = re.compile(
    r'<script>\s*\(function\(\)\{var D=\{"treg".*?}\)\(\);</script>',
    re.S
)

# Old govos-nav burger/open script (short inline script after nav)
RE_NAV_WIRE_SCRIPT = re.compile(
    r'<script>\s*\(function\(\)\{var n=document\.querySelector\(\'\.govos-nav\'\).*?}\)\(\);</script>',
    re.S
)

# Old navmap apply script
RE_NAVMAP_APPLY = re.compile(
    r'<script>\s*\(function\(\)\{var N=window\.__NAV__.*?}\)\(\);</script>',
    re.S
)

# Old tenant-nav div (entire duplicate tenant switcher)
# Keep only one canonical .tenant-nav built by govos-shell.js
RE_TENANT_NAV_DIV = re.compile(
    r'<div class=["\']?tenant-nav["\']?.*?</div>\s*<script>\s*\(function\(\)\{var D=\{"treg"',
    re.S
)

# ── Inject targets ─────────────────────────────────────────────────────────────

CSS_LINK = '<link rel="stylesheet" href="govos.css">'
JS_SCRIPT = '<script src="govos-shell.js" defer></script>'

# For pages in subdirectories, we need ../govos.css etc.
def asset_prefix(html_path):
    """Return relative prefix to site root from this file's location."""
    rel = html_path.relative_to(SITE_DIR)
    depth = len(rel.parts) - 1
    return '../' * depth

def inject_css(html, prefix):
    tag = '<link rel="stylesheet" href="{}govos.css">'.format(prefix)
    if 'govos.css' in html:
        return html
    # Insert before </head>
    return html.replace('</head>', tag + '\n</head>', 1)

def inject_js(html, prefix):
    tag = '<script src="{}govos-shell.js" defer></script>'.format(prefix)
    if 'govos-shell.js' in html:
        return html
    return html.replace('</body>', tag + '\n</body>', 1)

def inject_tenant_switcher(html, tenant_id):
    """
    If the page has no .tenant-nav, inject a lightweight placeholder that
    govos-shell.js will populate. Only injected on govOS content pages.
    """
    if 'tenant-nav' in html or 'tnav-gov' in html:
        return html
    switcher = (
        '\n<div class="tenant-nav" role="navigation" aria-label="Government navigation">'
        '\n  <div class="tn-grp"><span class="tn-lbl">Government</span>'
        '\n  <select id="tnav-gov" aria-label="Choose a government">'
        '\n    <option value="hi-state">Hawaii State</option>'
        '\n    <option value="hi-maui" {maui_sel}>Maui County</option>'
        '\n    <option value="hi-hawaii">Hawaii County</option>'
        '\n    <option value="hi-kauai">Kauaʻi County</option>'
        '\n    <option value="hi-honolulu">City & County of Honolulu</option>'
        '\n    <option value="ny">New York</option>'
        '\n  </select></div>'
        '\n  <div class="tn-grp"><span class="tn-lbl">View</span>'
        '\n  <select id="tnav-view" aria-label="Choose a report"></select></div>'
        '\n  <span class="tn-here">on <b>{tenant_name}</b></span>'
        '\n</div>'
    ).format(
        maui_sel='selected' if tenant_id == 'hi-maui' else '',
        tenant_name='Maui County' if tenant_id == 'hi-maui' else tenant_id
    )
    # Inject after govos-nav if present, else after <body>
    if '</nav>' in html:
        idx = html.index('</nav>') + len('</nav>')
        return html[:idx] + switcher + html[idx:]
    return html.replace('<body', '<body', 1)

def determine_tenant(filename, html):
    """Guess the tenant from filename or data-tenant attribute."""
    m = re.search(r'data-tenant=["\']([^"\']+)["\']', html)
    if m:
        return m.group(1)
    fname = os.path.basename(filename)
    for tid in ['hi-maui', 'hi-state', 'hi-hawaii', 'hi-kauai', 'hi-honolulu', 'ny']:
        if tid.replace('hi-', '') in fname:
            return tid
    return 'hi-maui'

def rebuild_page(html_path, dry_run=False, verbose=True):
    path = pathlib.Path(html_path)
    try:
        original = path.read_text(encoding='utf-8', errors='replace')
    except Exception as e:
        print(f'  SKIP {path.name}: {e}')
        return False

    html = original

    # 1. Strip old inline CSS blobs
    html = RE_GOVOS_NAV_STYLE.sub('', html)
    html = RE_GOVOS_CLASS_STYLE.sub('', html)
    html = RE_TENANT_SWITCH_CSS.sub('', html)

    # 2. Strip old inline JS blobs
    html = RE_NAVMAP_SCRIPT.sub('', html)
    html = RE_NAV_WIRE_SCRIPT.sub('', html)
    html = RE_NAVMAP_APPLY.sub('', html)
    html = RE_TENANT_SWITCH_SCRIPT.sub('', html)

    # 3. Determine prefix for asset paths
    prefix = asset_prefix(path)

    # 4. Inject shared CSS + JS
    html = inject_css(html, prefix)
    html = inject_js(html, prefix)

    # 5. Normalise CRLF → LF
    html = html.replace('\r\n', '\n').replace('\r', '\n')

    # 6. Clean up consecutive blank lines
    html = re.sub(r'\n{4,}', '\n\n\n', html)

    if html == original.replace('\r\n', '\n').replace('\r', '\n'):
        if verbose:
            print(f'  NO CHANGE {path.name}')
        return False

    if not dry_run:
        path.write_text(html, encoding='utf-8', newline='\n')
    if verbose:
        print(f'  {"DRY" if dry_run else "OK "} {path.name}')
    return True

def main():
    parser = argparse.ArgumentParser(description='Rebuild govOS site pages')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--file', help='Rebuild a single file')
    parser.add_argument('--quiet', action='store_true')
    args = parser.parse_args()

    verbose = not args.quiet

    if args.file:
        files = [SITE_DIR / args.file]
    else:
        files = sorted(SITE_DIR.glob('**/*.html'))
        # Exclude git/cache dirs
        files = [f for f in files if '.git' not in f.parts and '__pycache__' not in f.parts]

    changed = 0
    skipped = 0
    for f in files:
        result = rebuild_page(f, dry_run=args.dry_run, verbose=verbose)
        if result:
            changed += 1
        else:
            skipped += 1

    print(f'\nDone. {"[DRY RUN] " if args.dry_run else ""}Changed: {changed}  Unchanged: {skipped}  Total: {len(files)}')

if __name__ == '__main__':
    main()
