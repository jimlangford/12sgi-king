#!/usr/bin/env python3
"""selfheal.py — the system re-asserts its own truth on every build.

Every clarification we reached on this journey becomes an INVARIANT checked here, so the system catches
its own drift instead of waiting for a human to notice. Run it locally (full picture) or on CI (checks
what's present). Writes a public-safe integrity summary (reports/mauios/selfheal.html) + a detailed
local JSON. PASS/WARN/FAIL per check. See docs/SAGE_REALM_MODEL.md §2 (self-healing principle).

Stdlib only. Never fails the build by itself — it reports; the operator decides.
"""
import os, re, json, html
from urllib.parse import unquote
from datetime import datetime, timezone, timedelta

HERE   = os.path.dirname(os.path.abspath(__file__))
PROJ   = os.path.abspath(os.path.join(HERE, "..", ".."))
MAUIOS = os.path.join(PROJ, "reports", "mauios")
HOME   = os.path.expanduser("~")
HST    = timezone(timedelta(hours=-10))
def esc(s): return html.escape(str(s or ""))

# Find the publish repo (local desktop path, else CI checkout = cwd).
def _repo():
    for c in (os.path.join(HOME, "Documents", "Claude", "12sgi-king"), os.getcwd()):
        if os.path.isdir(os.path.join(c, "watchers")) or os.path.isfile(os.path.join(c, "build_site.py")):
            return c
    return os.getcwd()
REPO = _repo()

PRIVATE_NAMES = ("prosecutor.py", "case_files.html")          # owner-only back end — must never publish

def _known_secrets():
    """The ACTUAL secret VALUES, read at runtime from the local key files — NEVER hard-coded here
    (this file is published to the public watchers/, so it must contain no secret literal). On CI the
    keys are written to config/*.txt from Actions secrets; on a fresh clone there are none and we fall
    back to the filename check only."""
    vals = set()
    cfg = os.path.join(HOME, "Documents", "Claude", "Projects", "Video System elementLOTUS", "config")
    for fn in ("nysenate_key.txt", "legiscan_key.txt"):
        p = os.path.join(cfg, fn)
        try:
            v = open(p, encoding="utf-8", errors="ignore").read().strip()
            if len(v) >= 12:
                vals.add(v)
        except Exception:
            pass
    return vals

def chk_no_leak():
    """No private back-end file or secret key may exist anywhere in the publish repo tree."""
    hits = []
    secrets = _known_secrets()
    for root, dirs, files in os.walk(REPO):
        if ".git" in dirs: dirs.remove(".git")
        for fn in files:
            if fn in PRIVATE_NAMES or (fn.endswith(".txt") and "key" in fn.lower()):
                hits.append(os.path.relpath(os.path.join(root, fn), REPO))
            elif secrets and fn.endswith((".py", ".html", ".json", ".txt", ".md")):
                try:
                    body = open(os.path.join(root, fn), encoding="utf-8", errors="ignore").read()
                    if any(s in body for s in secrets):
                        hits.append(os.path.relpath(os.path.join(root, fn), REPO) + " (secret value)")
                except Exception:
                    pass
    if hits:
        return "FAIL", "private/secret artifacts in publish repo: " + ", ".join(hits[:5])
    return "PASS", "no private back-end files or secret keys in the publish repo"

def chk_links():
    """Internal links in the built site resolve the way GitHub Pages serves (%20 + /12sgi-king/)."""
    site = os.path.join(REPO, "site")
    if not os.path.isdir(site):
        return "WARN", "site/ not built yet (run build_site.py) — skipped"
    href_re = re.compile(r'(?:href|src)\s*=\s*["\']([^"\'#]+)["\']', re.I)
    broken = total = 0
    for root, _d, files in os.walk(site):
        for fn in files:
            if not fn.lower().endswith((".html", ".htm")): continue
            txt = open(os.path.join(root, fn), encoding="utf-8", errors="ignore").read()
            for href in href_re.findall(txt):
                h = href.split("?")[0].split("#")[0].strip()
                if not h or h.startswith(("http://","https://","mailto:","tel:","data:","javascript:","//")): continue
                if "{{" in h or "}}" in h: continue
                total += 1; h = unquote(h)
                if h.startswith("/12sgi-king/"): base, rel = site, h[len("/12sgi-king/"):]
                elif h.startswith("/"): base, rel = site, h.lstrip("/")
                else: base, rel = root, h
                tgt = os.path.normpath(os.path.join(base, rel))
                if not (os.path.exists(tgt) or os.path.exists(os.path.join(tgt, "index.html"))):
                    broken += 1
    return ("PASS" if broken == 0 else "FAIL"), f"{broken} broken of {total} internal links"

def _has(fn, needle):
    p = os.path.join(MAUIOS, fn)
    if not os.path.exists(p): return None
    return needle in open(p, encoding="utf-8", errors="ignore").read()

def chk_moon():
    """The moon dimension is live on both the civic cards and the Sage board."""
    a, s = _has("agenda_explainer.html", "🌙"), _has("sage_bridge.html", "🌙")
    if a is None or s is None: return "WARN", "agenda_explainer/sage_bridge not generated yet — skipped"
    return ("PASS" if (a and s) else "FAIL"), f"moon on agenda_explainer={bool(a)} sage_bridge={bool(s)}"

def chk_watcher_parity():
    """The generators' shared dependency (moon_calendar.py) is mirrored beside them for the cron path."""
    w = os.path.join(REPO, "watchers")
    if not os.path.isdir(w): return "WARN", "no watchers/ (not the publish repo) — skipped"
    need = ["moon_calendar.py", "sage_bridge.py", "agenda_explainer.py", "olelo_watch.py"]
    miss = [n for n in need if not os.path.exists(os.path.join(w, n))]
    return ("PASS" if not miss else "FAIL"), ("all key generators mirrored" if not miss else "missing in watchers: " + ", ".join(miss))

def chk_olelo():
    """ʻŌlelo Hawaiʻi is published under a visible community-review notice."""
    ok = _has("olelo_glossary.html", "under community review")
    if ok is None: return "WARN", "olelo_glossary not generated yet — run olelo_watch.py"
    return ("PASS" if ok else "FAIL"), "ʻŌlelo glossary carries the community-review notice"

def chk_bats_ascii():
    """.bat files stay pure ASCII (a stray non-ASCII byte breaks cmd parsing)."""
    bad = []
    for rel in ("12sgi-king/sync_watchers.bat", "dispatch.bat"):
        p = os.path.join(HOME, "Documents", "Claude", rel)
        if os.path.exists(p):
            try: open(p, encoding="ascii").read()
            except UnicodeDecodeError: bad.append(rel)
    return ("PASS" if not bad else "FAIL"), ("bats pure ASCII" if not bad else "non-ASCII in: " + ", ".join(bad))

CHECKS = [
    ("Private back end stays private", chk_no_leak),
    ("Links resolve like GitHub Pages", chk_links),
    ("Moon dimension is live",         chk_moon),
    ("Generators share their deps",    chk_watcher_parity),
    ("ʻŌlelo held under review",       chk_olelo),
    ("Batch files pure ASCII",         chk_bats_ascii),
]

def run():
    now = datetime.now(HST)
    results = []
    for name, fn in CHECKS:
        try: status, detail = fn()
        except Exception as e: status, detail = "FAIL", "check errored: %s" % e
        results.append({"check": name, "status": status, "detail": detail})
    summary = {s: sum(1 for r in results if r["status"] == s) for s in ("PASS", "WARN", "FAIL")}
    os.makedirs(MAUIOS, exist_ok=True)
    with open(os.path.join(MAUIOS, "selfheal.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump({"generated": now.isoformat(), "summary": summary, "results": results}, f, ensure_ascii=False, indent=1)

    color = {"PASS": "#4ade80", "WARN": "#d9b24c", "FAIL": "#e06a4a"}
    rows = "".join(
        '<tr><td>%s</td><td style="color:%s;font-weight:700">%s</td><td class="d">%s</td></tr>' % (
            esc(r["check"]), color.get(r["status"], "#999"), r["status"], esc(r["detail"])) for r in results)
    overall = "FAIL" if summary["FAIL"] else ("WARN" if summary["WARN"] else "PASS")
    page = (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<title>System integrity — govOS self-check</title><style>"
        "body{margin:0;background:#0e1311;color:#e8e4d6;font-family:-apple-system,Segoe UI,Roboto,sans-serif;line-height:1.5}"
        ".wrap{max-width:900px;margin:0 auto;padding:26px 18px 60px}h1{font-size:23px;margin:.2em 0}"
        ".sub{color:#9a957f;font-size:14px;margin-bottom:18px}"
        ".badge{display:inline-block;padding:3px 12px;border-radius:20px;font-weight:700;font-size:13px}"
        "table{width:100%;border-collapse:collapse;font-size:14px;margin-top:16px}"
        "td{padding:9px 10px;border-bottom:1px solid rgba(255,255,255,.07);vertical-align:top}"
        ".d{color:#9a957f;font-size:13px}footer{margin-top:22px;color:#9a957f;font-size:12px}</style></head>"
        "<body><div class='wrap'><h1>govOS system integrity — self-check</h1>"
        "<div class='sub'>The system re-checks its own promises on every build · " + esc(now.strftime("%Y-%m-%d %H:%M HST")) + "</div>"
        "<span class='badge' style='background:" + color[overall] + ";color:#0e1311'>" + overall +
        "</span> &nbsp;<span style='color:#9a957f'>" + str(summary["PASS"]) + " pass · " + str(summary["WARN"]) +
        " warn · " + str(summary["FAIL"]) + " fail</span>"
        "<table><tbody>" + rows + "</tbody></table>"
        "<footer>Private records are kept private; public records are kept public; the words are held under "
        "community review. This page proves we hold ourselves to that. · Kilo Aupuni</footer>"
        "</div></body></html>")
    with open(os.path.join(MAUIOS, "selfheal.html"), "w", encoding="utf-8", newline="\n") as f:
        f.write(page)
    print("selfheal: %s — %d pass / %d warn / %d fail" % (overall, summary["PASS"], summary["WARN"], summary["FAIL"]))
    for r in results:
        print("  [%s] %s — %s" % (r["status"], r["check"], r["detail"]))
    return overall

if __name__ == "__main__":
    run()
