#!/usr/bin/env python3
# fix_link_prefixes.py — deploy-time link-prefix normalizer for the built site/ tree.
# Repo-root civic pages are authored with a `site/…` href/src prefix so they resolve when previewed
# from the repo root; once copied INTO site/ that prefix double-points (site/site/…) and 404s. This
# strips it, generalizing the one-off fix build_site already applied to education.html so it can NEVER
# recur for any page. Bounded to href/src ATTRIBUTES only (never touches text/JS/`${...}`).
# Idempotent + safe to run every build. Returns the number of substitutions made.
import os, re

# strip one-or-more leading ../ from a href/src on a SITE-ROOT page (root has no parent, so any
# ../ escapes the site and 404s). Bounded to the attribute value's leading segments only.
_UP_RE = re.compile(r'((?:href|src)\s*=\s*["\'])((?:\.\./)+)(?=[^"\']*["\'])', re.I)

def _fix_text(t, in_king):
    n = 0
    if not in_king:
        # root pages: drop leading ../ (but never touch protocol-relative // or absolute /)
        def _strip(m):
            return m.group(1)
        t, k = _UP_RE.subn(_strip, t)
        n += k
    if in_king:
        # served at site/king/ — site-root siblings are one level up
        pairs = [('href="../site/', 'href="../'), ("href='../site/", "href='../"),
                 ('src="../site/', 'src="../'), ("src='../site/", "src='../"),
                 ('href="site/', 'href="../'), ("href='site/", "href='../"),
                 ('src="site/', 'src="../'), ("src='site/", "src='../")]
    else:
        # served at site/ root — site-root siblings are same dir
        pairs = [('href="site/', 'href="'), ("href='site/", "href='"),
                 ('src="site/', 'src="'), ("src='site/", "src='"),
                 ('href="../site/', 'href="../'), ("href='../site/", "href='../"),
                 ('src="../site/', 'src="../'), ("src='../site/", "src='../")]
    for a, b in pairs:
        c = t.count(a)
        if c:
            t = t.replace(a, b); n += c
    return t, n

# Owner-only backend routes have NO public page. build_site's privacy-sanitize rewrites the tailnet
# host -> 12sgi.com on public pages, turning these into 12sgi.com/board etc. (404). The owner's private
# king-local build keeps the real tailnet links; on the PUBLIC mirror, send these to the public King
# landing that DOES exist (/king/). Bounded to href/src attribute values only.
_OWNER_RE = re.compile(
    r'((?:href|src)\s*=\s*["\'])https://12sgi\.com/'
    r'(?:board(?:/[a-z0-9-]+)?/?|king/dispatch/?|king/quados/?|king/system_status\.html|owner_jobs\.html)'
    r'(["\'])', re.I)

def _fix_owner(t):
    return _OWNER_RE.subn(lambda m: m.group(1) + "https://12sgi.com/king/" + m.group(2), t)

def fix_site(site_dir):
    total = 0; files = 0
    for dp, dn, fn in os.walk(site_dir):
        rel = os.path.relpath(dp, site_dir)
        depth = 0 if rel == "." else rel.count(os.sep) + 1
        in_king = (rel == "king") or rel.startswith("king" + os.sep)
        # only fix root-level and king/ pages (that's where the repo-root/king_public_src authoring lands)
        if not (rel == "." or in_king):
            continue
        for f in fn:
            if not f.lower().endswith((".html", ".htm")) or f.lower().endswith(".dc.html"):
                continue
            p = os.path.join(dp, f)
            try:
                t = open(p, encoding="utf-8", errors="replace").read()
            except Exception:
                continue
            t2, n = _fix_text(t, in_king)
            t2, k = _fix_owner(t2)
            n += k
            if in_king:
                # king/index.html links a bare king_bridge.html that has no public page -> King landing
                c = t2.count('href="king_bridge.html"')
                if c:
                    t2 = t2.replace('href="king_bridge.html"', 'href="./"'); n += c
            if n:
                open(p, "w", encoding="utf-8", newline="\n").write(t2)
                total += n; files += 1
    return total, files

if __name__ == "__main__":
    SITE = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "site"))
    t, f = fix_site(SITE)
    print("fix_link_prefixes: %d substitutions across %d files in %s" % (t, f, SITE))
