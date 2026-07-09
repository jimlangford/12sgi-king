#!/usr/bin/env python3
"""meeting_watch.py — animated character "WATCH OUT" + moon-aware meeting reminders for the upcoming
agendas (Jimmy 2026-06-18: "animated character watch out and meeting reminders with moon for all the
work you just did on agendas and upcoming meetings").

For each UPCOMING council meeting (live Legistar), it builds:
  1. a MOON-AWARE MEETING REMINDER card (PNG) — body, date/time, the kaulana-mahina moon (phase + nature +
     aloha offering for that night), and the watch-out questions to bring — get ahead of hewa, in time.
  2. an ANIMATED CHARACTER "WATCH OUT" reel (9:16 mp4) — the civic narrator (POLYNESIAN_STANDARD, a
     FICTIONAL/GENERIC face — never a real official or the hero) delivering the watch-out across a few
     PIL beats, assembled by ffmpeg. PURE CPU (no GPU talking-head) so it never touches a render.

INTEGRITY: the watch-out is the worked hewa_watchlist (money signals pointed forward) matched onto the
real agenda items — every flag a QUESTION for pono, never an accusation; evidence stays private. AI-
DISCLOSURE badge on every frame; STAGE-ONLY (reports/_status/meeting_watch/, never auto-published; the
publish-allowlist still governs what goes out). Reuses agenda_reel's CPU frame/ffmpeg helpers.

Output per meeting: reports/_status/meeting_watch/<slug>/{reminder.png, watchout.mp4, frames/*.png, meeting.json}
CLI: python meeting_watch.py [--days 14] [--narrator POLYNESIAN_STANDARD] [--no-reel]
"""
import os, sys, json, re, ssl, glob, subprocess, urllib.request, urllib.parse
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(PROJ, "reports", "_status", "meeting_watch")
HST = timezone(timedelta(hours=-10))
C = "mauicounty"
UA = {"User-Agent": "12sgi-kilo-aupuni/1.0 (civic transparency; public record)"}
sys.path.insert(0, HERE)
import moon_calendar as mc
import bfed_today as bt            # jj, load_watchlist, watchlist_hit, _norm
try:
    import explainer_character as ec
except Exception:
    ec = None
from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1920
BG_TOP, BG_BOT = (12, 28, 50), (6, 14, 28)
GOLD, INK, MUTE, ALOHA = (224, 178, 92), (236, 240, 245), (150, 165, 180), (95, 200, 140)


def jj(u):
    return json.loads(urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=40,
                      context=ssl.create_default_context()).read().decode("utf-8", "replace"))


def F(size, bold=False):
    for p in ([r"C:\Windows\Fonts\seguisb.ttf", r"C:\Windows\Fonts\segoeui.ttf"] if bold else
              [r"C:\Windows\Fonts\segoeui.ttf"]):
        try: return ImageFont.truetype(p, size)
        except Exception: pass
    return ImageFont.load_default()


def wrap(draw, text, font, maxw):
    out, line = [], ""
    for w in str(text).split():
        t = (line + " " + w).strip()
        if draw.textlength(t, font=font) <= maxw:
            line = t
        else:
            if line: out.append(line)
            line = w
    if line: out.append(line)
    return out


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", str(s).lower()).strip("-")[:48] or "meeting"


def gradient_bg():
    img = Image.new("RGB", (W, H), BG_TOP); px = img.load()
    for y in range(H):
        t = y / H
        px_row = (int(BG_TOP[0] + (BG_BOT[0] - BG_TOP[0]) * t),
                  int(BG_TOP[1] + (BG_BOT[1] - BG_TOP[1]) * t),
                  int(BG_TOP[2] + (BG_BOT[2] - BG_TOP[2]) * t))
        for x in range(W):
            px[x, y] = px_row
    return img


def narrator_still():
    if not ec:
        return None
    try:
        for n in ec.narrators():
            if n.get("id") == "POLYNESIAN_STANDARD" and n.get("still") and os.path.exists(n["still"]):
                return n["still"]
        for n in ec.narrators():
            if n.get("still") and os.path.exists(n["still"]):
                return n["still"]
    except Exception:
        pass
    return None


def paste_character(img, still, box=(W - 360, H - 470, 320, 320)):
    """Composite the civic narrator still as a rounded portrait — the 'character' giving the watch-out."""
    if not still:
        return
    try:
        x, y, w, h = box
        c = Image.open(still).convert("RGB").resize((w, h))
        mask = Image.new("L", (w, h), 0); md = ImageDraw.Draw(mask)
        md.rounded_rectangle([0, 0, w, h], radius=40, fill=255)
        img.paste(c, (x, y), mask)
        d = ImageDraw.Draw(img)
        d.rounded_rectangle([x, y, x + w, y + h], radius=40, outline=GOLD, width=4)
    except Exception:
        pass


def ai_badge(d):
    t = "AI-GENERATED · civic narrator (fictional)"
    f = F(26)
    d.rounded_rectangle([40, H - 78, 40 + d.textlength(t, font=f) + 36, H - 30], radius=22, fill=(40, 30, 10))
    d.text((58, H - 70), t, font=f, fill=GOLD)


def draw_beat(headline, lines, still=True, eyebrow="12SGI · KILO AUPUNI"):
    img = gradient_bg(); d = ImageDraw.Draw(img)
    d.text((64, 120), eyebrow, font=F(30, True), fill=GOLD)
    y = 230
    for ln in wrap(d, headline, F(82, True), W - 128):
        d.text((64, y), ln, font=F(82, True), fill=INK); y += 96
    y += 30
    for kind, txt in lines:
        col = {"q": ALOHA, "m": GOLD, "b": INK, "mute": MUTE}.get(kind, INK)
        f = F(46) if kind != "b" else F(52, True)
        for ln in wrap(d, txt, f, W - 128 - (360 if still else 0)):
            d.text((64, y), ln, font=f, fill=col); y += 60
        y += 14
    return img, d


def draw_talking_card(body, when, moon):
    """A WATCH-OUT card with a CENTER framed box where the lip-synced talking face is composited — so the
    talking head looks like the cards, not a bare floating face. Returns (image, portrait box)."""
    img = gradient_bg(); d = ImageDraw.Draw(img)
    d.text((64, 110), "12SGI · KILO AUPUNI", font=F(30, True), fill=GOLD)
    y = 196
    d.text((64, y), "WATCH OUT", font=F(104, True), fill=INK); y += 128
    for ln in wrap(d, body, F(48, True), W - 128):
        d.text((64, y), ln, font=F(48, True), fill=GOLD); y += 58
    d.text((64, y + 6), when, font=F(40), fill=MUTE)
    bw = bh = 540; bx = (W - bw) // 2; by = 660            # the talking portrait region
    d.rounded_rectangle([bx, by, bx + bw, by + bh], radius=48, outline=GOLD, width=5)
    my = by + bh + 44
    if moon:
        for ln in wrap(d, "%s, %s — %s" % (moon.get("po", ""), moon.get("phase", ""), moon.get("nature", "")), F(42), W - 128):
            d.text((64, my), ln, font=F(42), fill=GOLD); my += 52
        for ln in wrap(d, moon.get("offering", ""), F(40), W - 128):
            d.text((64, my), ln, font=F(40), fill=ALOHA); my += 50
    ai_badge(d)
    return img, (bx, by, bw, bh)


def moon_for(date):
    try:
        return mc.reading(date)
    except Exception:
        return {}


def meeting_watchouts(eid, wl):
    outs = []
    try:
        items = jj("https://webapi.legistar.com/v1/%s/Events/%s/EventItems?$top=200" % (C, eid))
    except Exception:
        items = []
    for it in items:
        t = (it.get("EventItemTitle") or it.get("EventItemMatterName") or "").strip()
        if not t:
            continue
        hit = bt.watchlist_hit(t, wl)
        if hit:
            outs.append({"entity": hit["entity"], "why": (hit.get("why") or [""])[0],
                         "officials": hit.get("officials", []), "item": t[:140]})
    return outs


def upcoming(days):
    today = datetime.now(HST).strftime("%Y-%m-%d")
    horizon = (datetime.now(HST) + timedelta(days=days)).strftime("%Y-%m-%d")
    # desc = newest + UPCOMING first (asc would return the oldest 200 and miss upcoming past the cap)
    rows = jj("https://webapi.legistar.com/v1/%s/Events?%s" % (
        C, urllib.parse.urlencode({"$orderby": "EventDate desc", "$top": "120"})))
    up = [r for r in rows if today <= str(r.get("EventDate"))[:10] <= horizon and r.get("EventBodyName")]
    return sorted(up, key=lambda r: str(r.get("EventDate"))[:10])   # chronological for the reminders


def pretty(d):
    try:
        return datetime.strptime(d[:10], "%Y-%m-%d").strftime("%A, %B %d")
    except Exception:
        return d


def build_meeting(ev, wl, narrator_path, make_reel, mode="warm", talkinghead=False):
    body = ev.get("EventBodyName") or "Council meeting"
    date = str(ev.get("EventDate"))[:10]
    when = pretty(date) + ("  " + (ev.get("EventTime") or "")).rstrip()
    moon = moon_for(date)
    watchouts = meeting_watchouts(ev.get("EventId"), wl)
    src = ev.get("EventInSiteURL") or ""
    d = os.path.join(OUT, slug(body) + "-" + date); os.makedirs(os.path.join(d, "frames"), exist_ok=True)

    # ---- beats ----
    moon_line = (("%s (%s) — %s" % (moon.get("po", ""), moon.get("phase", ""), moon.get("nature", "")))
                 if moon else "")
    offering = moon.get("offering", "")
    wq = ([("q", "Watch for: %s" % w["entity"]) for w in watchouts[:3]] or
          [("mute", "No flagged name on this agenda — still, show up and watch the direction.")])
    beats = [
        ("WATCH OUT", [("b", body), ("m", when), ("mute", "An upcoming decision — be there in time.")]),
        ("The moon", [("m", moon_line), ("q", offering)] if moon else [("mute", "")]),
        ("Bring these questions", wq + [("mute", "A question for pono — never an accusation.")]),
        ("Show up", [("b", "Testify. Ask. Make the answer visible."),
                     ("mute", "Source: Maui County Legistar" + (" · " + src if src else ""))]),
    ]
    frames = []
    for i, (hl, lines) in enumerate(beats):
        img, dr = draw_beat(hl, lines, still=bool(narrator_path))
        paste_character(img, narrator_path)
        ai_badge(dr)
        fp = os.path.join(d, "frames", "beat_%02d.png" % i); img.save(fp); frames.append(fp)
    # the reminder card = the first beat (moon-aware reminder), saved standalone
    Image.open(frames[0]).save(os.path.join(d, "reminder.png"))

    meta = {"body": body, "date": date, "when": when, "moon": moon, "watchouts": watchouts,
            "source": src, "narrator": "POLYNESIAN_STANDARD" if narrator_path else None,
            "ai_disclosed": True, "stage_only": True,
            "generated": datetime.now(HST).strftime("%Y-%m-%d %H:%M:%S HST")}
    json.dump(meta, open(os.path.join(d, "meeting.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    # spoken narration — one line per beat; the civic narrator SPEAKS the watch-out (warm cloned voice)
    say_q = ("Watch for %s. A question for pono, never an accusation."
             % ", ".join(w["entity"].title() for w in watchouts[:2])) if watchouts \
            else "No flagged name on this agenda. Still — show up, and watch the direction."
    narration = [
        "Watch out. The %s meets %s. An upcoming decision — be there in time." % (body, pretty(date)),
        ("The moon is %s, %s. %s. %s." % (moon.get("po", ""), moon.get("phase", ""),
                                          moon.get("nature", ""), offering)) if moon else "",
        say_q,
        "Testify. Ask. Make the answer visible. This is your government.",
    ]
    meta["narration"] = narration
    json.dump(meta, open(os.path.join(d, "meeting.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    reel_ok = False
    if make_reel:
        reel_ok = voiced_reel(frames, narration, d, os.path.join(d, "watchout.mp4"), mode=mode)
    # PREMIUM (gated): GPU lip-synced talking head — narrator's mouth moves to the warm voice. Defers to renders.
    th = None
    if talkinghead and reel_ok and narrator_path:
        try:
            import wave as _wave, glob as _glob, talking_head as TH
            wavs = sorted(_glob.glob(os.path.join(d, "audio", "v_0*.wav")))
            narr = os.path.join(d, "audio", "narration_full.wav"); ww = None
            for p in wavs:
                r = _wave.open(p, "rb")
                if ww is None:
                    ww = _wave.open(narr, "wb"); ww.setparams(r.getparams())
                ww.writeframes(r.readframes(r.getnframes())); r.close()
            if ww:
                ww.close()
            if os.path.exists(narr):
                # build the designed WATCH-OUT card; the lip-synced face composites into its center box
                card_img, box = draw_talking_card(body, pretty(date), moon)
                card_bg = os.path.join(d, "frames", "talkcard.png"); card_img.save(card_bg)
                res = TH.make(narrator_path, narr, os.path.join(d, "talkinghead.mp4"), prefix="MEETING_WATCH",
                              card_png=card_bg, box=box)
                th = "yes" if res.get("ok") else ("deferred" if res.get("deferred") else "fail")
        except Exception:
            th = "error"
    return {"dir": d, "body": body, "date": date, "watchouts": len(watchouts), "reel": reel_ok, "talkinghead": th}


NW = 0x08000000 if os.name == "nt" else 0
def _wav_dur(wav):
    try:
        import wave
        f = wave.open(wav); d = f.getnframes() / float(f.getframerate()); f.close()
        return d
    except Exception:
        return None

def _voice(line, out_wav, mode="warm"):
    """Speak a beat. mode 'warm' = Jimmy's cloned voice (XTTS-v2, CPU, model cached); 'sapi' = instant
    Windows narration. Warm falls back to SAPI so the reel always gets a voice. Returns wav path or None."""
    try:
        import olelo_voice as ov
    except Exception:
        return None
    if mode == "warm":
        w = ov.clone(line, out_wav)
        if w:
            return w
    return ov.narrate(line, out_wav)

def voiced_reel(frames, lines, work, out_mp4, mode="warm", fps=30):
    """CPU 'character animation with voice': each beat is shown while its line is SPOKEN, then concatenated.
    Per-segment (image+audio -> mp4) is robust; no fragile xfade timing. Defensive: silent fallback per beat."""
    ff = "ffmpeg"; segs = []; adir = os.path.join(work, "audio"); os.makedirs(adir, exist_ok=True)
    try:
        for i, fp in enumerate(frames):
            seg = os.path.join(work, "seg_%02d.mp4" % i)
            wav = _voice(lines[i], os.path.join(adir, "v_%02d.wav" % i), mode) if i < len(lines) and lines[i] else None
            dur = (_wav_dur(wav) + 0.5) if wav else 3.2
            if wav:
                cmd = [ff, "-y", "-loop", "1", "-i", fp, "-i", wav, "-t", "%.2f" % dur,
                       "-vf", "scale=1080:1920,format=yuv420p", "-c:v", "libx264", "-r", str(fps),
                       "-c:a", "aac", "-ar", "44100", "-shortest", seg]
            else:
                cmd = [ff, "-y", "-loop", "1", "-i", fp, "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
                       "-t", "%.2f" % dur, "-vf", "scale=1080:1920,format=yuv420p", "-c:v", "libx264",
                       "-r", str(fps), "-c:a", "aac", "-shortest", seg]
            r = subprocess.run(cmd, capture_output=True, timeout=240, creationflags=NW)
            if r.returncode == 0 and os.path.exists(seg):
                segs.append(seg)
        if not segs:
            return False
        lst = os.path.join(work, "concat.txt")
        open(lst, "w", encoding="utf-8").write("".join("file '%s'\n" % os.path.abspath(s) for s in segs))
        r = subprocess.run([ff, "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", out_mp4],
                           capture_output=True, timeout=180, creationflags=NW)
        return r.returncode == 0 and os.path.exists(out_mp4)
    except Exception:
        return False


def main():
    import argparse
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--days", type=int, default=14)
    ap.add_argument("--no-reel", action="store_true")
    ap.add_argument("--voice", choices=["warm", "sapi"], default="warm",
                    help="warm = Jimmy's cloned voice (XTTS-v2, CPU, slower); sapi = instant Windows narration")
    ap.add_argument("--limit", type=int, default=8)
    ap.add_argument("--talkinghead", action="store_true",
                    help="ALSO render a GPU lip-synced talking head (LatentSync) — gated, defers to active renders")
    a, _ = ap.parse_known_args()
    if a.talkinghead:
        a.voice = "warm"   # the lip-sync should move the mouth to the WARM cloned voice
    os.makedirs(OUT, exist_ok=True)
    wl = bt.load_watchlist("maui")
    still = narrator_still()
    print("meeting_watch: narrator still=%s | watchlist=%d | horizon=%dd | voice=%s" % (bool(still), len(wl), a.days, a.voice))
    try:
        meetings = upcoming(a.days)
    except Exception as e:
        print("  Legistar fetch failed:", str(e)[:120]); return 1
    built = []
    for ev in meetings[:a.limit]:
        try:
            built.append(build_meeting(ev, wl, still, not a.no_reel, mode=a.voice, talkinghead=a.talkinghead))
            b = built[-1]
            print("  + %s %s | watch-outs:%d | reel:%s -> %s" % (
                b["date"], b["body"][:42], b["watchouts"], "yes" if b["reel"] else "no", os.path.relpath(b["dir"], PROJ)))
        except Exception as e:
            print("  x meeting build failed:", str(e)[:120])
    print("meeting_watch: built %d moon-aware reminders + watch-out reels (CPU, stage-only)" % len(built))
    return 0


if __name__ == "__main__":
    if sys.platform == "win32":
        import io; sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(main())
