#!/usr/bin/env python3
"""open_golive.py — open the go-live pages Jimmy must COMPLETE, in Chrome, and bring to front (Jimmy 2026-06-18).

"Open the pages in chrome that I need to complete + bring to front when I need to authorize logins." This
opens a named group from config/golive_pages.json in Chrome (falls back to the default browser), opening the
group's `primary` LAST so it lands front-most for sign-in. Claude NEVER enters credentials — Jimmy authorizes
each login himself; this only opens + surfaces the page. (The Chrome MCP blocks financial dashboards by design,
so we open through the OS.) Stdlib only; Windows.

CLI:  python open_golive.py stripe        # open the Stripe go-live tabs (products front)
      python open_golive.py --list        # show the groups + readiness
"""
import os, sys, json, time, shutil, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(os.path.dirname(HERE))
CFG = os.path.join(PROJ, "config", "golive_pages.json")
_CHROME_CANDIDATES = [
    os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"), "Google", "Chrome", "Application", "chrome.exe"),
    os.path.join(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"), "Google", "Chrome", "Application", "chrome.exe"),
    os.path.join(os.environ.get("LocalAppData", ""), "Google", "Chrome", "Application", "chrome.exe"),
]


def _cfg():
    try: return json.load(open(CFG, encoding="utf-8"))
    except Exception: return {"groups": {}}


def _chrome():
    p = shutil.which("chrome")
    if p: return p
    for c in _CHROME_CANDIDATES:
        if c and os.path.exists(c): return c
    return None


def open_group(name):
    g = _cfg().get("groups", {}).get(name)
    if not g:
        print("unknown group %r. groups: %s" % (name, ", ".join(_cfg().get("groups", {})))); return 2
    pages = list(g.get("pages", []))
    primary = g.get("primary")
    # open the primary LAST so it ends up front-most for sign-in
    ordered = [u for u in pages if u != primary] + ([primary] if primary in pages else [])
    chrome = _chrome()
    for u in ordered:
        try:
            if chrome:
                subprocess.Popen([chrome, u], close_fds=True)
            else:
                os.startfile(u)  # default browser
        except Exception as e:
            print("  open failed %s: %s" % (u, str(e)[:80]))
        time.sleep(0.6)
    print("opened group '%s' (%d tabs) -> %s front. %s" % (name, len(ordered), primary, g.get("why", "")))
    print("  Sign in yourself — Claude never enters credentials.")
    return 0


def main():
    if "--list" in sys.argv or len(sys.argv) == 1:
        for k, g in _cfg().get("groups", {}).items():
            print("  [%s] %-12s %s" % ("READY" if g.get("ready") else "later", k, g.get("title", "")))
        print("\nusage: python open_golive.py <group>   (e.g. stripe)")
        return 0
    return open_group(sys.argv[1])


if __name__ == "__main__":
    raise SystemExit(main())
