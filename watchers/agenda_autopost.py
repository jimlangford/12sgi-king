#!/usr/bin/env python3
"""agenda_autopost.py — the LIVE auto-publisher for civic agenda reels.

James PRE-APPROVED live auto-publishing (2026-06-16): no per-item human sign-off is required.
What replaces human review is an AUTOMATED, ALWAYS-ON content-safety gate — every reel is
re-checked by agenda_safety.check_reel() immediately before it posts, and anything that reads
as an accusation/guilt claim about a named real person is HARD-BLOCKED (logged, never posted).
That keeps it neutral, sourced, public-record — "all aloha" and defamation-safe.

Controls (NOT human-approval gates — operational switches James owns):
  - MASTER SWITCH: config/agenda_autopost.ENABLED. Its contents set privacy:
        PRIVATE (default) | UNLISTED | PUBLIC. Delete the file to stop everything instantly.
  - PRIVACY: --unlisted forces unlisted (used for the very first reel so James can watch the
        exact artifact); otherwise the gate-file mode wins; PUBLIC requires the flag to say PUBLIC.
  - CADENCE: --max N posts at most N reels per run (drip, no spam burst). Default 2.

Reuses the EXISTING uploader (app/server/youtube_api.YouTubeClient — OAuth self-heal, defaults
PRIVATE). It stores/handles NO secrets itself. YouTube is wired live. TikTok/IG have no API
token on file, so each posted reel is also dripped into config/tiktok_queue.json (the existing
manual/assisted TikTok lane) — it does not auto-post to TikTok.

USAGE:
  python tools/kilo-aupuni/agenda_autopost.py --status            # gate + safety + queue state
  python tools/kilo-aupuni/agenda_autopost.py --unlisted --max 1  # post the first reel UNLISTED
  python tools/kilo-aupuni/agenda_autopost.py --max 2             # drip 2 (privacy per gate file)
"""
import os, sys, json, glob, argparse

HOME    = os.path.expanduser("~")
PROJECT = os.path.join(HOME, "Documents", "Claude", "Projects", "Video System elementLOTUS")
SHORTS  = os.path.join(PROJECT, "finals", "shorts")
CONFIG  = os.path.join(PROJECT, "config")
GATE    = os.path.join(CONFIG, "agenda_autopost.ENABLED")


def _reels():
    return sorted(glob.glob(os.path.join(SHORTS, "agenda_*")) + glob.glob(os.path.join(SHORTS, "moon_*")))

def _meta(slug_dir):
    f = os.path.join(slug_dir, "clip_00.json")
    try: return json.load(open(f, encoding="utf-8"))
    except Exception: return {}

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import agenda_safety as SAFETY               # always-on neutral-framing / defamation gate
import civic_post_gate as COMPLY             # HRS 92 (Sunshine) + HRS 92F (UIPA) compliance gate (Jimmy 2026-07-03)
BUNDLE  = os.path.join(PROJECT, "reports", "_status", "agenda_reels")
TIKTOK_Q = os.path.join(CONFIG, "tiktok_queue.json")
BLOCKED  = os.path.join(BUNDLE, "_blocked.jsonl")

def _gate():
    """(enabled, mode) — mode in {PRIVATE, UNLISTED, PUBLIC}. Master on/off + privacy."""
    if not os.path.exists(GATE): return False, ""
    mode = open(GATE, encoding="utf-8").read().strip().upper() or "PRIVATE"
    return True, mode

def _full_meta(slug):
    """Read the full per-platform bundle metadata (+ storyboard text) for the safety check."""
    d = os.path.join(BUNDLE, slug)
    meta = {}
    try: meta = json.load(open(os.path.join(d, "metadata.json"), encoding="utf-8"))
    except Exception: pass
    sbt = ""
    try:
        sb = json.load(open(os.path.join(d, "storyboard.json"), encoding="utf-8"))
        sbt = " ".join((b.get("big", "") + " " + b.get("body", "")) for b in sb.get("beats", []))
    except Exception: pass
    return meta, sbt

def _is_past(date_str):
    """Don't post 'testify before the vote' reels after the meeting already happened."""
    import datetime as _dt
    try:
        d = _dt.datetime.strptime((date_str or "")[:10], "%Y-%m-%d").date()
        today = (_dt.datetime.utcnow() - _dt.timedelta(hours=10)).date()   # HST
        return d < today
    except Exception:
        return False

def _log_blocked(slug, verdict):
    os.makedirs(BUNDLE, exist_ok=True)
    with open(BLOCKED, "a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": "post", "slug": slug, "hits": verdict.get("hits", []),
                            "reasons": verdict.get("reasons", [])}, ensure_ascii=False) + "\n")

def _feed_tiktok(slug, meta):
    """Drip the reel into the EXISTING tiktok_queue.json (the manual/assisted TikTok lane).
    No TikTok API token is on file, so this stages the caption+tags for the existing flow;
    it does not auto-post to TikTok."""
    try:
        q = json.load(open(TIKTOK_Q, encoding="utf-8")) if os.path.exists(TIKTOK_Q) else []
        if any(e.get("slug") == slug for e in q): return
        tk = meta.get("tiktok", {})
        q.append({"n": len(q) + 1, "type": "civic", "slug": slug,
                  "caption": tk.get("caption", ""),
                  "tags": [t.lstrip("#") for t in tk.get("hashtags", "").split() if t.startswith("#")][:6],
                  "video": os.path.join("finals", "shorts", slug, "clip_00.mp4"),
                  "min60": False, "posted": None, "skipped": None})
        json.dump(q, open(TIKTOK_Q, "w", encoding="utf-8"), indent=1)
    except Exception:
        pass

def cmd_status():
    en, mode = _gate()
    print("agenda_autopost STATUS")
    print("  enable gate:", ("LIVE (%s)" % mode) if en else "OFF (no config/agenda_autopost.ENABLED)")
    print("  safety gate: ALWAYS ON (agenda_safety.check_reel re-runs before every post)")
    for d in _reels():
        slug = os.path.basename(d)
        up = os.path.exists(os.path.join(d, "_uploaded.json"))
        meta, sbt = _full_meta(slug)
        safe = SAFETY.check_reel(meta, sbt)["ok"] if meta else None
        print("   - %s | uploaded=%s | safe=%s" % (slug, up, safe))
    return 0

def cmd_approve(slug):  # optional manual marker; no longer a gate (James pre-approved)
    f = os.path.join(SHORTS, slug, "clip_00.json")
    if not os.path.exists(f): print("approve: no such staged reel:", slug); return 2
    m = json.load(open(f, encoding="utf-8")); m["reviewed"] = True
    json.dump(m, open(f, "w", encoding="utf-8"), indent=2)
    print("marked reviewed (optional):", slug); return 0

def cmd_post(public, max_n, force_unlisted):
    en, mode = _gate()
    if not en:
        print("agenda_autopost: OFF — no config/agenda_autopost.ENABLED. Nothing posted."); return 0
    # privacy resolution: --unlisted wins; else gate mode; PUBLIC only if flag says PUBLIC.
    if force_unlisted:                 privacy = "unlisted"
    elif mode == "PUBLIC":             privacy = "public"
    elif mode == "UNLISTED":           privacy = "unlisted"
    else:                              privacy = "private"
    if public and privacy != "public":
        print("agenda_autopost: --public asked but gate flag is '%s'; staying %s." % (mode, privacy))
    sys.path.insert(0, os.path.join(PROJECT, "app", "server"))
    try:
        from youtube_api import YouTubeClient
        yt = YouTubeClient(interactive=False)        # headless: never pops a browser
    except Exception as e:
        print("agenda_autopost: YouTube API not ready (%s). Nothing posted." % e); return 1
    posted = 0
    for d in _reels():
        if posted >= max_n: break                    # drip cadence — no spam burst
        slug = os.path.basename(d)
        rec_f = os.path.join(d, "_uploaded.json")
        rec = json.load(open(rec_f, encoding="utf-8")) if os.path.exists(rec_f) else {}
        mp4 = os.path.join(d, "clip_00.mp4")
        if "clip_00.mp4" in rec or not os.path.exists(mp4):
            continue                                 # already up / no file
        meta, sbt = _full_meta(slug); m = _meta(d)
        if _is_past(meta.get("date")):               # meeting already happened — stale, skip
            print("  skip %s (meeting date passed)" % slug); continue
        # ── ALWAYS-ON CONTENT SAFETY GATE — re-checked here, immediately before posting ──
        verdict = SAFETY.check_reel(meta, sbt) if meta else SAFETY.check(
            (m.get("title", "") + " " + m.get("description", "")))
        if not verdict["ok"]:
            _log_blocked(slug, verdict)
            print("  ! BLOCKED (safety): %s -> %s" % (slug, "; ".join(verdict["reasons"])[:140]))
            continue
        # ── HRS 92 (Sunshine) + HRS 92F (UIPA) CIVIC-POST COMPLIANCE GATE (Jimmy 2026-07-03, signed) ──
        import datetime as _dt
        desc = m.get("description", "")
        official = meta.get("agenda_url") or meta.get("source_url") or meta.get("url") or ""
        ok, missing = COMPLY.check(desc, is_agenda_mirror=True, official_link=official)
        if not ok and all(x.split()[0] in ("R1", "R2", "R3", "R4") for x in missing):
            # auto-remediate the fixable ones: attach official-posting link + retrieval date + unofficial-mirror disclaimer
            footer = "\n\n" + (("Official posting: %s\n" % official) if official else "") \
                     + ("Retrieved %s.\n" % _dt.date.today().isoformat()) + COMPLY.DISCLAIMER
            desc = (desc + footer); m["description"] = desc
            ok, missing = COMPLY.check(desc, is_agenda_mirror=True, official_link=official)
        if not ok:
            _log_blocked(slug, {"ok": False, "reasons": ["HRS92/92F compliance: " + ", ".join(missing)]})
            print("  ! BLOCKED (civic-compliance): %s -> %s" % (slug, ", ".join(missing)))
            continue
        try:
            vid = yt.upload_video(mp4, title=m.get("title", slug), description=m.get("description", ""),
                                  tags=m.get("tags", []), privacy=privacy, category_id="25")
            rec["clip_00.mp4"] = vid; json.dump(rec, open(rec_f, "w", encoding="utf-8"), indent=2)
            _feed_tiktok(slug, meta)
            print("  + %s -> https://youtu.be/%s  [%s]" % (slug, vid, privacy)); posted += 1
        except Exception as e:
            print("  x %s failed: %s" % (slug, e))
    print("\nagenda_autopost: posted %d reel(s) as %s (max %d). "
          "TikTok/IG staged into tiktok_queue.json (manual lane; no API token on file)." % (posted, privacy, max_n))
    return 0

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--approve", metavar="SLUG")
    ap.add_argument("--public", action="store_true", help="force public (needs gate flag == PUBLIC)")
    ap.add_argument("--unlisted", action="store_true", help="force UNLISTED (e.g. the first reel)")
    ap.add_argument("--max", type=int, default=2, help="max reels to post this run (drip cadence)")
    args = ap.parse_args()
    if sys.platform == "win32":
        import io; sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    if args.status:  return cmd_status()
    if args.approve: return cmd_approve(args.approve)
    return cmd_post(args.public, args.max, args.unlisted)

if __name__ == "__main__":
    sys.exit(main())
