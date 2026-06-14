# Link-integrity audit: crawl site/ and report every internal href/src that 404s.
import os, re
SITE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "site")
href_re = re.compile(r'(?:href|src)\s*=\s*["\\\']([^"\\\'#]+)["\\\']', re.I)
broken, total = [], 0
for root, dirs, files in os.walk(SITE):
    for fn in files:
        if not fn.lower().endswith((".html", ".htm")):
            continue
        p = os.path.join(root, fn)
        txt = open(p, encoding="utf-8", errors="ignore").read()
        for href in href_re.findall(txt):
            h = href.split("?")[0].split("#")[0].strip()
            if not h or h.startswith(("http://", "https://", "mailto:", "tel:", "data:", "javascript:", "//")):
                continue
            if "{{" in h or "}}" in h:  # DC template binding resolved in-browser, not a real href
                continue
            total += 1
            tgt = os.path.normpath(os.path.join(root, h))
            ok = os.path.exists(tgt) or (os.path.isdir(tgt) and os.path.exists(os.path.join(tgt, "index.html"))) \
                 or os.path.exists(os.path.join(tgt, "index.html"))
            if not ok:
                broken.append((os.path.relpath(p, SITE), href))
print(f"checked {total} internal links; BROKEN: {len(broken)}")
seen = set()
for sf, href in broken:
    key = (sf, href)
    if key in seen:
        continue
    seen.add(key)
    print(f"  [{sf}]  ->  {href}")
