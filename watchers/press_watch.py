#!/usr/bin/env python3
"""press_watch.py — THE SKILL, run daily (Jimmy 2026-06-18 "learn this skill daily or more"): read the
county's own press releases, get AHEAD of the big land-use/money matters they announce, and turn each into
an aloha question with the money lens — before the vote.

WHAT IT DOES each run:
  1. Pull the Maui County press-release feed (mauicounty.us/press-release/) — the county's own words.
  2. Dedup vs a state file; classify each (housing / zoning / development / entitlement / contract / permit
     = GET-AHEAD priority; the rest = noted).
  3. MONEY LENS: scan each release's title for any entity already on our worked watchlist / donor data
     (e.g. a developer or landowner who funds the deciders) -> flag a sourced QUESTION, never an accusation.
  4. Write a dignified get-ahead board (public-safe) + a private state, and log a dispatch FINDING for each
     NEW priority release so the system (and Jimmy) gets ahead in time.

Honest + sourced: every item links to the county's release; the developer/landowner is named only from the
public record; affordable housing is a GOOD for the people — the questions are about transparency, who
benefits, and due process, never opposition. Stdlib only.
Output: reports/mauios/press_watch.html + reports/_status/press_watch.json
"""
import os, sys, json, re, ssl, html, urllib.request
from datetime import datetime, timezone, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(os.path.dirname(HERE))
M = os.path.join(PROJ, "reports", "mauios")
ST = os.path.join(PROJ, "reports", "_status")
STATE = os.path.join(ST, "press_watch_state.json")
HST = timezone(timedelta(hours=-10))
FEED = "https://www.mauicounty.us/press-release/"
UA = {"User-Agent": "12sgi-kilo-aupuni/1.0 (civic transparency; public record)"}
esc = lambda s: html.escape(str(s if s is not None else ""))

PRIORITY = re.compile(r"housing|affordable|zoning|rezone|district boundary|community plan|island plan|"
                      r"entitlement|development|subdivision|201h|permit|contract|award|bid|lease|tax|bond|"
                      r"general plan|land use|mixed.use", re.I)
TINY = {"THE", "AND", "OF", "INC", "LLC", "LP", "DBA", "A"}


def _get(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=40,
                                  context=ssl.create_default_context()).read().decode("utf-8", "replace")


def load(p, d):
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception:
        return d


def watch_names():
    """Entity names already worked (watchlist + donor profiles) -> distinctive token sets, for the money lens."""
    out = []
    w = load(os.path.join(ST, "hewa_watchlist_maui.json"), {})
    for e in w.get("entities", []):
        toks = {t for t in re.sub(r"[^A-Z0-9 ]", " ", (e.get("entity") or "").upper()).split() if len(t) >= 4 and t not in TINY}
        if toks:
            out.append((toks, e.get("entity"), e.get("officials", []), "watchlist"))
    dp = load(os.path.join(M, "donor_profiles.json"), [])
    for prof in (dp if isinstance(dp, list) else []):
        for don in ((prof.get("realestate") or {}).get("donors") or [])[:40]:
            nm = don.get("name") or ""
            toks = {t for t in re.sub(r"[^A-Z0-9 ]", " ", nm.upper()).split() if len(t) >= 4 and t not in TINY}
            if toks:
                out.append((toks, nm, [prof.get("label") or prof.get("key")], "donor"))
    return out


def money_lens(title, names):
    tn = {t for t in re.sub(r"[^A-Z0-9 ]", " ", title.upper()).split() if len(t) >= 4}
    for toks, name, offs, src in names:
        if toks and toks <= tn:
            return {"entity": name, "officials": offs, "source": src}
    return None


def parse_feed(htmltext):
    """Pull (title, url, date?) for each press release on the listing page. Robust to theme markup."""
    items = []
    seen = set()
    for m in re.finditer(r'href="(https?://[^"]*?/press-release/[^"]+?)"[^>]*>([^<]{8,140})<', htmltext):
        url, title = m.group(1), html.unescape(m.group(2)).strip()
        if url.rstrip("/").endswith("/press-release") or url in seen or not title:
            continue
        seen.add(url)
        items.append({"title": title, "url": url})
    return items[:30]


def build():
    now = datetime.now(HST)
    try:
        items = parse_feed(_get(FEED))
    except Exception as e:
        return {"ok": False, "error": str(e)[:120]}
    # MANUAL SEED merge: releases Jimmy (or any thread) spots directly — e.g. on Facebook — when the
    # county listing page only surfaces the latest. Each seed flows through the SAME priority + money-lens
    # + finding pipeline as a scraped item, so nothing important is missed. config/press_seed.json = a list
    # of {title, url}. Self-heal: the feed scrape is best-effort; the seed is the backstop.
    seed = load(os.path.join(PROJ, "config", "press_seed.json"), [])
    have = {it["url"] for it in items}
    for s in (seed if isinstance(seed, list) else []):
        u, t = (s.get("url") or "").strip(), (s.get("title") or "").strip()
        if u and t and u not in have:
            items.insert(0, {"title": t, "url": u}); have.add(u)
    state = load(STATE, {"seen": []})
    seen = set(state.get("seen", []))
    names = watch_names()
    new_priority = []
    rows = []
    for it in items:
        pri = bool(PRIORITY.search(it["title"]))
        lens = money_lens(it["title"], names) if pri else None
        is_new = it["url"] not in seen
        it.update({"priority": pri, "money_lens": lens, "new": is_new})
        rows.append(it)
        if is_new and pri:
            new_priority.append(it)
    # persist seen
    state["seen"] = sorted(seen | {it["url"] for it in items})
    state["checked"] = now.strftime("%Y-%m-%d %H:%M:%S HST")
    json.dump(state, open(STATE, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    out = {"checked": state["checked"], "total": len(rows), "priority": sum(1 for r in rows if r["priority"]),
           "new_priority": len(new_priority), "items": rows}
    json.dump(out, open(os.path.join(ST, "press_watch.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    _html(out)
    # log a FINDING for each NEW priority release (get ahead, in time)
    for it in new_priority:
        msg = ("FINDING (get ahead): Maui County announced \"%s\". A get-ahead question for pono — what is "
               "being decided, who benefits, and is the public hearing/process open? %s%s"
               % (it["title"][:120],
                  ("MONEY LENS: the public record shows %s (a decider-funder) — a question to verify at the "
                   "source. " % it["money_lens"]["entity"]) if it["money_lens"] else "",
                  it["url"]))
        _dispatch(msg)
    return out


def _dispatch(msg):
    try:
        import subprocess
        subprocess.run([sys.executable, os.path.join(PROJ, "app", "server", "dispatch.py"), PROJ,
                        "--log-event", msg, "--source", "kilo-aupuni"],
                       capture_output=True, timeout=30, creationflags=(0x08000000 if os.name == "nt" else 0))
    except Exception:
        pass


def _html(out):
    def row(it):
        badge = "<span class=pri>get ahead</span>" if it["priority"] else ""
        lens = ("<div class=lens>Money lens: the public record shows <b>%s</b> in the donor data — a question "
                "to verify at the source, never a claim.</div>" % esc(it["money_lens"]["entity"])) if it["money_lens"] else ""
        return ("<div class=item><div class=t><a href='%s'>%s</a> %s</div>%s</div>"
                % (esc(it["url"]), esc(it["title"]), badge, lens))
    body = "".join(row(it) for it in out["items"]) or "<div class=fine>No releases parsed this run.</div>"
    doc = ("<!doctype html><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'>"
           "<title>Press watch — get ahead | govOS</title>"
           "<style>body{font-family:system-ui,Segoe UI,sans-serif;max-width:880px;margin:1.4rem auto;padding:0 1rem;color:#1f2d3a}"
           "h1{color:#7fb2ff;font-size:1.3rem}.lead{color:#33414f}.item{border-bottom:1px solid #eef3f9;padding:.6rem 0}"
           ".t{font-weight:600}a{color:#0b6bcb;text-decoration:none}.pri{background:#241d0e;border:1px solid #5c4a1e;"
           "color:#e3c98a;border-radius:99px;padding:.05rem .55rem;font-size:.72rem;margin-left:.4rem}"
           ".lens{font-size:.86rem;color:#1f6f54;margin-top:.25rem}.fine{color:#5a6b7b}</style>"
           "<h1>Press watch — getting ahead of the agenda</h1>"
           "<p class=lead>The county's own announcements, read early so the people can be there in time. Every "
           "item links to the source; each is a question for pono, never an accusation. Affordable housing and "
           "public projects are a good — the questions are about transparency, who benefits, and open process.</p>"
           "%s<p class=fine>Checked %s · source: Maui County press releases.</p>" % (body, esc(out["checked"])))
    open(os.path.join(ST, "press_watch.html"), "w", encoding="utf-8", newline="\n").write(doc)  # PRIVATE (money lens names entities)


def main():
    out = build()
    if not out.get("ok", True) and out.get("error"):
        print("press_watch: feed error:", out["error"]); return 1
    print("press_watch: %d releases, %d get-ahead priority, %d NEW priority -> press_watch.{html,json}"
          % (out["total"], out["priority"], out["new_priority"]))
    for it in out["items"]:
        if it["priority"]:
            print("  %s%s %s" % ("[NEW] " if it["new"] else "      ",
                                 ("$lens:" + it["money_lens"]["entity"]) if it["money_lens"] else "", it["title"][:80]))
    return 0


if __name__ == "__main__":
    if sys.platform == "win32":
        import io; sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(main())
