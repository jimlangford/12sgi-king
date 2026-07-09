# -*- coding: utf-8 -*-
"""moon_blessing.py — the DAILY MOON BLESSING (James 2026-06-17).

Every day, build the reverent Sage-Kumulipo moon card (LOCAL, CPU — no cloud credits) and stage
it for the cross-post lanes with the influencer-reach hashtags, so a moon blessing goes out at
the perfect time to reach the community + the creators' audiences.

  card (sage_kumulipo_card, local) -> blessing caption + reach hashtags (hashtag_library +
  influencer_crosswalk) -> staged into finals/shorts/moon_<date>/ + the bundle, which the
  existing YouTube/TikTok/Facebook lanes already post on their schedules.

NEUTRAL/REVERENT: it's a blessing, not a pitch. The always-on safety gate still runs. Civic-only,
local-only; the cloud is for film.

USAGE:
  python tools/kilo-aupuni/moon_blessing.py            # today (HST)
  python tools/kilo-aupuni/moon_blessing.py 2026-06-18 # a given day
"""
import os, sys, json, shutil, datetime as dt
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import moon_calendar as M
import sage_kumulipo_card as SKC
import agenda_reel as AR          # reuse hashtags (load_hashtags), crosswalk, safety gate
import agenda_safety as SAFETY

PROJ = SKC.PROJ
SHORTS = os.path.join(PROJ, "finals", "shorts")
BUNDLE = os.path.join(PROJ, "reports", "_status", "agenda_reels")


def caption(g):
    m = g["moon"]; wa = g["wa"] or {}; wt = g["wa_text"] or {}; card = g["card"] or {}
    base = ("Moon blessing - %s.  po %d, %s (%s): %s.  "
            "Kumulipo wa %s, %s.  Offered with aloha - kumu pending." % (
              m["date"], m["night"], m["po"], m["phase"], m["offering"],
              wa.get("wa", ""), (wa.get("archetype") or "").split(" - ")[-1] or "the source"))
    # reach: civic + location + influencer crosswalk (the audiences we want to bless/reach)
    _tags, hashtags, _people = AR.load_hashtags("maui", "moon_" + m["date"])
    xw = AR.crosswalk_tags((card.get("zone", "") + " " + (wa.get("archetype") or "")), "moon kumulipo")
    extra = " ".join("#" + t for t in (["MoonBlessing", "KaulanaMahina", "Kumulipo", "Liliuokalani"] + xw))
    yt_tags = list(dict.fromkeys((["MoonBlessing", "KaulanaMahina", "Kumulipo", "Maui", "Hawaii",
                                   "Liliuokalani", "Aloha"] + _tags)))[:18]
    return base, (base + "  " + extra + " " + hashtags), yt_tags


def run(date_s):
    g = SKC.gather(date_s)
    mp4, _ = SKC.build(date_s)
    if not mp4:
        print("moon_blessing: card render failed for", date_s); return 1
    base, full_caption, yt_tags = caption(g)
    # safety (reverent, but the gate is always on)
    v = SAFETY.check(full_caption)
    if not v["ok"]:
        print("moon_blessing: BLOCKED by safety gate ->", "; ".join(v["reasons"])[:140]); return 1
    slug = "moon_" + date_s
    title = ("Moon blessing - %s - po %d %s | kaulana mahina" % (date_s, g["moon"]["night"], g["moon"]["po"]))[:96] + " #Shorts"
    # stage for the YouTube/TikTok/FB lanes
    d = os.path.join(SHORTS, slug); os.makedirs(d, exist_ok=True)
    shutil.copy2(mp4, os.path.join(d, "clip_00.mp4"))
    json.dump({"title": title, "description": full_caption, "tags": yt_tags,
               "_kind": "moon_blessing", "_local_render": True},
              open(os.path.join(d, "clip_00.json"), "w", encoding="utf-8"), indent=2)
    # bundle (so fb_ops / tiktok / safety + date guard all read it)
    b = os.path.join(BUNDLE, slug); os.makedirs(b, exist_ok=True)
    json.dump({"slug": slug, "tenant": "Maui County", "tenant_id": "maui", "date": date_s,
               "pretty": g["moon"]["date"], "source": "https://jimlangford.github.io/12sgi-king/",
               "youtube": {"title": title, "description": full_caption, "tags": yt_tags, "category_id": "25"},
               "tiktok": {"caption": full_caption, "hashtags": ""},
               "instagram_reels": {"caption": full_caption, "hashtags": ""},
               "kind": "moon_blessing"},
              open(os.path.join(b, "metadata.json"), "w", encoding="utf-8"), indent=2)
    json.dump({"beats": [{"kind": "blessing", "big": "Moon blessing", "body": base}]},
              open(os.path.join(b, "storyboard.json"), "w", encoding="utf-8"), indent=2)
    print("moon_blessing staged:", slug)
    print("  ", base)
    print("   -> finals/shorts/%s/clip_00.mp4 (local render). Posting lanes pick it up on schedule." % slug)
    return 0


def main():
    if sys.platform == "win32":
        import io; sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    date_s = sys.argv[1] if len(sys.argv) > 1 else (dt.datetime.utcnow() - dt.timedelta(hours=10)).date().isoformat()
    return run(date_s)


if __name__ == "__main__":
    sys.exit(main())
