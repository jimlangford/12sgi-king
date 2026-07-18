#!/usr/bin/env python3
# link_audit.py — crawl the BUILT static site (site/) and report every broken INTERNAL link/asset.
# Resolves a/href, link/href, img/src, script/src against the site tree; handles #anchors, ?query,
# root-relative, https://12sgi.com absolute, directory/index.html. External http(s) links are listed
# separately (not failed). Also verifies #fragment targets exist as id=/name= on the destination page.
import os, re, sys, html
from urllib.parse import urlsplit, unquote

SITE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "site")
SITE = os.path.abspath(SITE)
SITE_HOSTS = ("12sgi.com", "www.12sgi.com")

def all_pages():
    out = []
    for dp, dn, fn in os.walk(SITE):
        for f in fn:
            # .dc.html are un-rendered templates (Handlebars/JS placeholders) — not shipped as-is
            if f.lower().endswith((".html", ".htm")) and not f.lower().endswith(".dc.html"):
                out.append(os.path.join(dp, f))
    return out

ATTR_RE = re.compile(r'(?:href|src)\s*=\s*["\']([^"\']+)["\']', re.I)
ID_RE   = re.compile(r'\b(?:id|name)\s*=\s*["\']([^"\']+)["\']', re.I)

def page_ids(path, cache):
    if path in cache: return cache[path]
    try:
        t = open(path, encoding="utf-8", errors="replace").read()
        ids = set(m.group(1) for m in ID_RE.finditer(t))
    except Exception:
        ids = set()
    cache[path] = ids
    return ids

def resolve(target, page):
    """Return ('ok'|'broken'|'external'|'skip', resolved_path_or_url, frag)."""
    t = target.strip()
    if not t or t.startswith(("mailto:", "tel:", "javascript:", "data:", "#")):
        return ("skip", t, "")
    # template placeholders rendered at build/runtime (Handlebars {{..}}, JS `${..}`) — not real hrefs
    if "{{" in t or "${" in t or "}}" in t or "<%" in t:
        return ("skip", t, "")
    sp = urlsplit(t)
    frag = sp.fragment
    if sp.scheme in ("http", "https"):
        if sp.netloc.lower() in SITE_HOSTS:
            rel = sp.path
        else:
            return ("external", t, frag)
    elif sp.scheme:
        return ("skip", t, "")
    else:
        rel = sp.path  # relative or root-relative
    if rel == "":
        return ("ok", page, frag)  # same-page anchor
    rel = unquote(rel)
    # /king/ prefix on tailnet maps to site root when served at 12sgi.com root
    if rel.startswith("/king/"): rel = rel[len("/king"):]
    if rel.startswith("/"):
        cand = os.path.join(SITE, rel.lstrip("/"))
    else:
        cand = os.path.join(os.path.dirname(page), rel)
    cand = os.path.normpath(cand)
    tries = [cand]
    if cand.endswith(("/", os.sep)) or os.path.isdir(cand):
        tries.append(os.path.join(cand, "index.html"))
    if not os.path.splitext(cand)[1]:
        tries += [cand + ".html", os.path.join(cand, "index.html")]
    for c in tries:
        if os.path.isfile(c):
            return ("ok", c, frag)
    return ("broken", cand, frag)

def main():
    if not os.path.isdir(SITE):
        print("NO site/ dir at", SITE); return 2
    pages = all_pages()
    idcache = {}
    broken, badfrag, external = [], [], set()
    total_links = 0
    for p in pages:
        rel_p = os.path.relpath(p, SITE)
        try:
            t = open(p, encoding="utf-8", errors="replace").read()
        except Exception:
            continue
        for m in ATTR_RE.finditer(t):
            raw = html.unescape(m.group(1))
            total_links += 1
            status, resolved, frag = resolve(raw, p)
            if status == "broken":
                broken.append((rel_p, raw))
            elif status == "external":
                external.add(urlsplit(raw).netloc)
            elif status == "ok" and frag:
                ids = page_ids(resolved, idcache)
                if frag not in ids and frag.lower() != "top":
                    badfrag.append((rel_p, raw))
    print("=== LINK AUDIT ===")
    print("pages: %d | links scanned: %d" % (len(pages), total_links))
    print("BROKEN internal links: %d" % len(broken))
    for pg, lnk in sorted(set(broken)):
        print("  [%s]  ->  %s" % (pg, lnk))
    print("BROKEN #anchors: %d" % len(badfrag))
    for pg, lnk in sorted(set(badfrag))[:60]:
        print("  [%s]  ->  %s" % (pg, lnk))
    print("external domains linked: %d -> %s" % (len(external), ", ".join(sorted(external))[:400]))
    return 0 if not broken else 1

if __name__ == "__main__":
    sys.exit(main())
