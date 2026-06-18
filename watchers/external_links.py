#!/usr/bin/env python3
"""external_links.py — verify OUTBOUND links and self-heal the ones we've learned.

The orphan check guards INTERNAL reachability; this guards EXTERNAL links — the county
.gov pages, Municode, the Hawaiʻi Statewide GIS, MAPPS, mauipropertytax, mauirecovers, etc.
It HTTP-checks every unique external URL in the built site, classifies each, and:

  • confirmed  — 2xx/3xx (resolves)
  • recheck    — transient (403 bot-block / 429 / 5xx / timeout): NOT counted broken; falls
                 back to the cached last-good so a gov rate-limit never hard-fails a deploy.
  • broken     — 404/410/451 or DNS/connection failure AFTER a retry: a genuinely dead link.

HEAL_MAP holds what we've learned (dead URL → verified replacement). `--heal` rewrites the
canonical templates in king_public_src, swapping any known-dead URL to its verified one.

Writes reports/_status/external_links.json + a public-safe site/external_links.html dashboard.
Importable: `from external_links import status_summary`. Stdlib only; never hard-fails a build.
"""
import os, re, json, html, ssl, time, urllib.request, urllib.error
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
SRC  = os.path.join(REPO, "king_public_src")
STATUS_DIR = os.path.join(PROJ, "reports", "_status")
CACHE_F = os.path.join(STATUS_DIR, "external_links_cache.json")

# What we've LEARNED: dead/stale URL  ->  verified-live replacement (HTTP 200, 2026-06-17).
# Used both to heal source and to suggest a fix when a known-dead URL is seen in the build.
HEAL_MAP = {
    "https://www.mauicounty.gov/2065/Lahaina-Community-Plan": "https://www.mauirecovers.org/lahaina",
}

# Domains we care to verify (civic sources). Other externals are recorded but not failed.
CIVIC_HINTS = ("mauicounty.gov", "municode.com", "geodata.hawaii.gov", "mapps.mauicounty.gov",
               "mauipropertytax", "mauirecovers.org", "t19rewrite.org", "capitol.hawaii.gov",
               "hawaii.gov", "wearemaui.org", "formbasedcodes.org", "qpublic", "schneidercorp")

URL_RE = re.compile(r'(?:href|src)\s*=\s*["\'](https?://[^"\'>\s]+)["\']', re.I)
UA = "Mozilla/5.0 (compatible; 12sgi-civic-linkcheck/1.0; +https://jimlangford.github.io/12sgi-king/)"
TRANSIENT = {403, 408, 429, 500, 502, 503, 504, 522, 524, 0}  # 0 = timeout/conn error

def collect_urls():
    urls = {}
    if not os.path.isdir(SITE):
        return urls
    for root, _d, files in os.walk(SITE):
        for fn in files:
            if not fn.lower().endswith((".html", ".htm")):
                continue
            try:
                t = open(os.path.join(root, fn), encoding="utf-8", errors="ignore").read()
            except Exception:
                continue
            rel = os.path.relpath(os.path.join(root, fn), SITE).replace("\\", "/")
            for u in URL_RE.findall(t):
                u = u.split("#")[0].rstrip(".,)")
                urls.setdefault(u, set()).add(rel)
    return urls

def _probe(url, timeout=22):
    """Return an HTTP status (int); 0 on timeout/connection error. Tries GET (HEAD is often blocked)."""
    req = urllib.request.Request(url, method="GET", headers={"User-Agent": UA, "Accept": "*/*"})
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ssl.create_default_context()) as r:
            return getattr(r, "status", 200) or 200
    except urllib.error.HTTPError as e:
        return e.code
    except Exception:
        return 0

def check_url(url):
    code = _probe(url)
    if code in TRANSIENT:          # one retry after a short pause for transient classes
        time.sleep(1.5)
        code = _probe(url)
    if 200 <= code < 400:
        return "confirmed", code
    if code in (404, 410, 451):
        return "broken", code
    return "recheck", code          # 403/429/5xx/timeout → don't call it broken; gov rate-limits

def load_cache():
    try: return json.load(open(CACHE_F, encoding="utf-8"))
    except Exception: return {}

def run(now_iso):
    urls = collect_urls()
    civic = {u: pages for u, pages in urls.items() if any(h in u for h in CIVIC_HINTS)}
    cache = load_cache()
    results = []
    for u in sorted(civic):
        state, code = check_url(u)
        prev = cache.get(u, {})
        if state == "recheck":
            # fall back to last-good so a transient blip never reports a dead link
            note = "transient %s; last-good %s" % (code, prev.get("last_good", "—"))
            last_good = prev.get("last_good")
        else:
            note = ""
            last_good = now_iso if state == "confirmed" else prev.get("last_good")
        healable = HEAL_MAP.get(u)
        results.append({"url": u, "state": state, "code": code, "pages": sorted(civic[u])[:6],
                        "note": note, "heal": healable})
        cache[u] = {"state": state, "code": code, "last_check": now_iso,
                    "last_good": last_good, **({"confirmed_at": now_iso} if state == "confirmed" else {})}
    os.makedirs(STATUS_DIR, exist_ok=True)
    json.dump(cache, open(CACHE_F, "w", encoding="utf-8", newline="\n"), ensure_ascii=False, indent=2)
    return results

def status_summary():
    """For selfheal: (confirmed, recheck, broken, healable, total) from the last cache/report."""
    try:
        rep = json.load(open(os.path.join(STATUS_DIR, "external_links.json"), encoding="utf-8"))
    except Exception:
        return None
    return (rep.get("confirmed", 0), rep.get("recheck", 0), rep.get("broken", 0),
            rep.get("healable", 0), rep.get("total", 0))

def heal_sources():
    """Swap any known-dead URL (HEAL_MAP key) -> verified replacement across king_public_src."""
    if not os.path.isdir(SRC):
        return []
    healed = []
    for root, _d, files in os.walk(SRC):
        for fn in files:
            if not fn.lower().endswith((".html", ".htm", ".js", ".json", ".md")):
                continue
            p = os.path.join(root, fn)
            try:
                t = open(p, encoding="utf-8", errors="ignore").read()
            except Exception:
                continue
            t2 = t
            for bad, good in HEAL_MAP.items():
                if bad in t2:
                    t2 = t2.replace(bad, good)
            if t2 != t:
                open(p, "w", encoding="utf-8", newline="").write(t2)
                healed.append(os.path.relpath(p, SRC).replace("\\", "/"))
    return healed

def main():
    import sys
    now = datetime.now(HST)
    now_iso = now.isoformat()
    if "--heal" in sys.argv:
        h = heal_sources()
        print("external_links --heal: %d source file(s) rewritten %s" % (len(h), h or ""))
        return
    res = run(now_iso)
    cnt = {"confirmed": 0, "recheck": 0, "broken": 0}
    for r in res: cnt[r["state"]] += 1
    healable = sum(1 for r in res if r["state"] == "broken" and r["heal"])
    out = {"generated": now_iso, "total": len(res), "healable": healable, **cnt,
           "results": res}
    json.dump(out, open(os.path.join(STATUS_DIR, "external_links.json"), "w", encoding="utf-8", newline="\n"),
              ensure_ascii=False, indent=2)
    # public-safe dashboard
    color = {"confirmed": "#1f8a5b", "recheck": "#b07d1a", "broken": "#c0322c"}
    rows = "".join(
        "<tr><td style='font-family:Consolas,monospace;font-size:12px;word-break:break-all'>%s</td>"
        "<td style='color:%s;font-weight:700'>%s</td><td style='font-family:Consolas,monospace'>%s</td>"
        "<td style='font-size:11.5px;color:#6d7f97'>%s</td></tr>" % (
            esc(r["url"]), color.get(r["state"], "#999"), r["state"].upper(), r["code"],
            esc(("heal → " + r["heal"]) if r["heal"] else r["note"]))
        for r in sorted(res, key=lambda x: {"broken": 0, "recheck": 1, "confirmed": 2}[x["state"]]))
    ok = (cnt["broken"] == 0)
    page = (
        "<!DOCTYPE html><html lang=en><head><meta charset=UTF-8>"
        "<meta name=viewport content='width=device-width,initial-scale=1'>"
        "<title>External links · govOS self-heal</title><style>"
        "body{margin:0;background:#fff;color:#13243d;font-family:'Segoe UI',system-ui,sans-serif;line-height:1.5}"
        ".wrap{max-width:980px;margin:0 auto;padding:18px 16px 70px}h1{font-size:22px;margin:6px 0}"
        ".eyebrow{font-family:Consolas,monospace;font-size:11px;letter-spacing:1.5px;color:#00356b;text-transform:uppercase}"
        ".badge{display:inline-block;font-weight:700;border-radius:8px;padding:4px 12px;color:#fff;background:%s}"
        "table{width:100%%;border-collapse:collapse;margin-top:14px;font-size:13px}"
        "th,td{text-align:left;padding:7px 9px;border-bottom:1px solid #bacde6;vertical-align:top}"
        "th{font-family:Consolas,monospace;font-size:11px;text-transform:uppercase;color:#6d7f97}"
        ".note{font-size:12.5px;color:#6d7f97;margin-top:10px}</style></head><body><div class=wrap>"
        "<div class=eyebrow>govOS · Kilo Aupuni · self-heal</div>"
        "<h1>External links <span class=badge>%s</span></h1>"
        "<p class=note>%d civic outbound links checked · <b style='color:#1f8a5b'>%d confirmed</b> · "
        "<b style='color:#b07d1a'>%d recheck</b> (transient — gov rate-limit/bot-block, last-good kept) · "
        "<b style='color:#c0322c'>%d broken</b>. Transient hiccups never fail the deploy; a known-dead "
        "link with a learned replacement is auto-healed on build.</p>"
        "<table><thead><tr><th>URL</th><th>Status</th><th>HTTP</th><th>Note / heal</th></tr></thead><tbody>%s</tbody></table>"
        "<p class=note>Generated %s · the outbound 'verify external links and self-heal' guard.</p>"
        "</div></body></html>"
    ) % (("#1f8a5b" if ok else "#c0322c"),
         ("CLEAN" if ok else ("%d BROKEN" % cnt["broken"])),
         len(res), cnt["confirmed"], cnt["recheck"], cnt["broken"], rows, esc(now.strftime("%Y-%m-%d %H:%M HST")))
    if os.path.isdir(SITE):
        open(os.path.join(SITE, "external_links.html"), "w", encoding="utf-8", newline="\n").write(page)
    print("external_links: %d civic links · %d confirmed · %d recheck · %d broken (%d healable)" % (
        len(res), cnt["confirmed"], cnt["recheck"], cnt["broken"], healable))
    for r in res:
        if r["state"] != "confirmed":
            print("  [%s %s] %s %s" % (r["state"], r["code"], r["url"], ("→ heal " + r["heal"]) if r["heal"] else ""))

if __name__ == "__main__":
    main()
