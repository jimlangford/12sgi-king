#!/usr/bin/env python3
"""agenda_reel.py — turn each upcoming civic Agenda Explainer fact-card into a 9:16
short-form VIDEO reel (the "phase 2 narrated-video lane" agenda_explainer.py promised).

DESIGN: this EXTENDS the existing civic pipeline, it does not fork it.
  - DATA: reuses agenda_explainer.py as a library (NAMES / ORDER / links_for /
    how_to_testify / moon offering) so the reel is driven by the SAME live agenda feed
    (agenda_sources.json) the share-cards use. One source of truth.
  - RENDER: pure CPU — PIL draws six 1080x1920 beat frames, ffmpeg assembles them with
    fades into an MP4. NO GPU, NO ComfyUI — it can run while the 12 STONES render holds
    the card; it is a polite co-tenant by construction (it never asks for VRAM).
  - PUBLISH: writes the reel in the EXISTING finals/shorts/<slug>/clip_00.mp4 + clip_00.json
    format that batch/upload_shorts.py already uploads (PRIVATE by default, OAuth self-heal
    in app/server/youtube_api.py). This script NEVER posts. It only builds drafts.

STORYBOARD (6 beats, the fact-card arc): hook -> what -> law -> money -> deadline -> how-to-testify.

NEUTRAL / SOURCED: every reel is framed as a question and a civic invitation ("know the law,
follow the money, testify before the vote") — never an accusation. Public-record only; each
reel carries its official source link. Tone matches the civic surfaces.

OUTPUT (draft bundle, per reel):
  reports/_status/agenda_reels/<slug>/reel.mp4         the 9:16 video
  reports/_status/agenda_reels/<slug>/frames/*.png     the six beat frames
  reports/_status/agenda_reels/<slug>/metadata.json    per-platform titles/desc/hashtags
  reports/_status/agenda_reels/<slug>/marketing.md     human-review sheet
  finals/shorts/<slug>/clip_00.mp4 + clip_00.json      the uploader-ready copy (for when Jimmy says go)
  reports/_status/agenda_reels/index.html              review gallery

USAGE:
  python tools/kilo-aupuni/agenda_reel.py                      # DRAFT: 2 sample Maui reels
  python tools/kilo-aupuni/agenda_reel.py --tenant maui --limit 6
  python tools/kilo-aupuni/agenda_reel.py --all-tenants --limit 1
  (there is intentionally NO --post flag here; live posting stays in upload_shorts.py, gated.)
"""
import os, sys, re, json, glob, subprocess, argparse
from datetime import datetime, date
# the ʻŌlelo chant voice (local, CPU) — muxed into the reel as the audio track; safe-optional
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    import olelo_voice as _olelo
except Exception:
    _olelo = None
# a traditional sunrise oli as the default chant intro (correct, dignified); a storyboard may override
DEFAULT_OLI = "E ala ē, ka lā i ka hikina"

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import agenda_explainer as AX          # reuse the civic data layer (NAMES, ORDER, links_for, ...)
import agenda_safety as SAFETY         # always-on neutral-framing / defamation gate
try:
    from PIL import Image, ImageDraw, ImageFont
except Exception as e:
    print("agenda_reel: Pillow required (pip install pillow):", e); sys.exit(1)

PROJECT  = AX.PROJECT
MAUIOS   = AX.MAUIOS
REELDIR  = os.path.join(PROJECT, "reports", "_status", "agenda_reels")
SHORTS   = os.path.join(PROJECT, "finals", "shorts")
NW       = 0x08000000 if os.name == "nt" else 0

# ── brand palette (the civic Yale-blue system) ───────────────────────────────
BG_TOP, BG_BOT = (255, 255, 255), (238, 244, 252)   # white -> pale blue
INK      = (19, 36, 61)      # #13243d
BLUE     = (0, 53, 107)      # #00356b  Yale blue
GREEN    = (31, 138, 91)     # #1f8a5b
RED      = (192, 50, 44)     # #c0322c
GOLD     = (160, 120, 30)    # money accent
PURPLE   = (91, 95, 176)     # moon
MUTE     = (109, 127, 151)   # #6d7f97
W, H     = 1080, 1920

def _font(names, size):
    for n in names:
        for p in (n, os.path.join(r"C:\Windows\Fonts", n)):
            try: return ImageFont.truetype(p, size)
            except Exception: pass
    return ImageFont.load_default()

def F(size, bold=False, mono=False):
    if mono: return _font(["consolab.ttf" if bold else "consola.ttf"], size)
    return _font(["segoeuib.ttf"] if bold else ["segoeui.ttf"], size)

# ── text helpers ─────────────────────────────────────────────────────────────
def wrap(draw, text, font, maxw):
    out, line = [], ""
    for word in (text or "").split():
        t = (line + " " + word).strip()
        if line and draw.textlength(t, font=font) > maxw:
            out.append(line); line = word
        else:
            line = t
    if line: out.append(line)
    return out

def slugify(s):
    return re.sub(r"[^0-9a-z]+", "-", (s or "").lower()).strip("-")[:40].strip("-")


# ── storyboard: the six neutral, sourced beats ───────────────────────────────
def storyboard(tid, m):
    """Build the 6-beat arc for one meeting. Pure data — auditable for neutrality."""
    nm    = AX.NAMES.get(tid, tid)
    body  = m.get("body", "Meeting"); title = m.get("title", ""); dt = m.get("date", "")
    src   = m.get("url", ""); tip, _ = AX.how_to_testify(tid)
    L     = AX.links_for(tid)
    mr    = AX.moon_calendar.reading(dt) if (AX.moon_calendar and dt) else None
    has_law, has_money = bool(L.get("law")), bool(L.get("money") or tid == "maui")
    pretty = pretty_date(dt)
    beats = [
        {"kind": "hook", "accent": BLUE, "eyebrow": "GET AHEAD OF THE VOTE",
         "big": pretty, "body": nm,
         "foot": "what's on the table -- before the vote"},
        {"kind": "what", "accent": BLUE, "eyebrow": "WHAT'S BEING DECIDED",
         "big": body[:90], "body": title,
         "foot": "this is on the official agenda — public record"},
        {"kind": "law", "accent": BLUE, "eyebrow": "KNOW THE LAW",
         "big": "Which rules govern this?",
         "body": ("See how this body's powers map to the charter and the law — so you "
                  "know what they can and can't decide."),
         "foot": "law and charter crosswalk -- on the record"},
        {"kind": "money", "accent": GOLD, "eyebrow": "FOLLOW THE MONEY",
         "big": "Who funds the deciders?",
         "body": ("Public campaign-finance records show who backs the people at this table. "
                  "Worth asking before the vote."),
         "foot": ("from public campaign-finance records" if has_money else "public records")},
        {"kind": "deadline", "accent": RED, "eyebrow": "THE DEADLINE",
         "big": "Testify BEFORE the vote",
         "body": "Once they vote, it's decided. Your testimony counts most beforehand — on " + pretty + ".",
         "foot": "meeting date: " + pretty},
        {"kind": "testify", "accent": GREEN, "eyebrow": "HOW TO TESTIFY",
         "big": "Your voice, on the record",
         "body": tip,
         "foot": "12 Stones  /  Kilo Aupuni  /  the people's record"},
    ]
    if mr:
        beats[-1]["moon"] = "%s moon · po %s — %s" % (mr["po"], mr["night"], mr["offering"])
    # ALOHA FACT — the ho'oponopono balance: pairs the accountability beats with reconciliation
    # so every reel stays PONO (hold the office accountable, with aloha for the person).
    af = aloha_fact(body + dt)
    beats.append({"kind": "aloha", "accent": GREEN, "eyebrow": "ALOHA · KEEP IT PONO",
                  "big": af["term"], "body": af["fact"],
                  "foot": "follow the money to ASK, not accuse -- accountability + aloha"})
    return {"tid": tid, "tenant": nm, "body": body, "title": title, "date": dt,
            "pretty": pretty, "src": src, "beats": beats, "aloha": af}

_AF_CACHE = {}
def aloha_fact(seed):
    """Pick one aloha/ho'oponopono fact deterministically per reel (the pono balance)."""
    if not _AF_CACHE:
        try: _AF_CACHE["list"] = json.load(open(os.path.join(PROJECT, "config", "aloha_facts.json"),
                                                 encoding="utf-8")).get("facts", [])
        except Exception: _AF_CACHE["list"] = []
    facts = _AF_CACHE.get("list") or [{"term": "Pono", "fact": "Accountability and aloha, together.", "source": ""}]
    return facts[sum(ord(c) for c in (seed or "x")) % len(facts)]

def pretty_date(dt):
    try:
        d = datetime.strptime((dt or "")[:10], "%Y-%m-%d")
        return d.strftime("%b %-d, %Y") if os.name != "nt" else d.strftime("%b %#d, %Y")
    except Exception:
        return dt or ""


# ── frame renderer (PIL, CPU) ────────────────────────────────────────────────
def gradient_bg():
    img = Image.new("RGB", (W, H), BG_TOP); px = img.load()
    for y in range(H):
        t = y / (H - 1)
        px_row = tuple(int(BG_TOP[i] + (BG_BOT[i] - BG_TOP[i]) * t) for i in range(3))
        for x in range(W): px[x, y] = px_row
    return img

def draw_beat(beat, sb, idx, total):
    img = gradient_bg(); d = ImageDraw.Draw(img)
    accent = beat["accent"]
    d.rectangle([22, 22, W - 22, H - 22], outline=BLUE, width=5)   # civic border
    pad = 96; maxw = W - pad * 2
    # progress pips
    for i in range(total):
        cx = pad + i * 46
        d.ellipse([cx, 120, cx + 26, 146], fill=(accent if i == idx else (206, 217, 230)))
    # pre-measure the content block so we can vertically center it
    big_f, body_f, eye_f = F(96, bold=True), F(52), F(40, mono=True)
    big_lines = wrap(d, beat["big"], big_f, maxw)[:4]
    body_lines = wrap(d, beat.get("body", ""), body_f, maxw - 36)[:7]
    moon_lines = wrap(d, beat["moon"], F(46), maxw - 36)[:3] if beat.get("moon") else []
    block_h = 96 + len(big_lines) * 112 + 26
    if body_lines: block_h += len(body_lines) * 70 + 40 + 44
    if moon_lines: block_h += len(moon_lines) * 60 + 36
    y = max(250, (H - block_h) // 2 - 80)
    # eyebrow
    d.text((pad, y), beat["eyebrow"], font=eye_f, fill=accent); y += 96
    # big headline
    for ln in big_lines:
        d.text((pad, y), ln, font=big_f, fill=INK); y += 112
    y += 26
    # body band (accent left bar)
    if body_lines:
        bh = len(body_lines) * 70 + 40
        d.rounded_rectangle([pad - 18, y - 16, W - pad + 18, y - 16 + bh], radius=18, fill=(238, 244, 252))
        d.rectangle([pad - 18, y - 16, pad - 8, y - 16 + bh], fill=accent)
        for ln in body_lines:
            d.text((pad, y), ln, font=body_f, fill=INK); y += 70
        y += 44
    # optional moon offering band
    if moon_lines:
        mh = len(moon_lines) * 60 + 36
        d.rounded_rectangle([pad - 18, y - 14, W - pad + 18, y - 14 + mh], radius=18, fill=(241, 238, 251))
        d.rectangle([pad - 18, y - 14, pad - 8, y - 14 + mh], fill=PURPLE)
        for ln in moon_lines:
            d.text((pad, y), ln, font=F(46), fill=(46, 42, 92)); y += 60
    # footer — wrapped, never overflows
    foot_f = F(30, mono=True)
    fl = wrap(d, beat.get("foot", ""), foot_f, maxw)
    fy = H - 110 - (len(fl) - 1) * 40
    for ln in fl:
        d.text((W / 2, fy), ln, font=foot_f, fill=MUTE, anchor="ma"); fy += 40
    d.text((W / 2, H - 64), "govOS  /  jimlangford.github.io/12sgi-king", font=F(26, mono=True),
           fill=MUTE, anchor="ma")
    return img


# ── marketing metadata (neutral, sourced, per-platform) ──────────────────────
HASHTAG_LIB = os.path.join(PROJECT, "config", "hashtag_library.json")
PEOPLE_ON   = os.path.join(PROJECT, "config", "hashtag_people.ON")
_LIB_CACHE  = {}

def _library():
    if not _LIB_CACHE:
        try: _LIB_CACHE.update(json.load(open(HASHTAG_LIB, encoding="utf-8")))
        except Exception: _LIB_CACHE["_missing"] = True
    return _LIB_CACHE

def tenant_tag(tid, nm):
    base = {"maui": "Maui", "honolulu": "Honolulu", "hawaii": "HawaiiCounty",
            "state": "Hawaii", "kauai": "Kauai", "nyc": "NYC", "nys": "NewYork"}.get(tid)
    return base or re.sub(r"[^0-9A-Za-z]+", "", nm)

def load_hashtags(tid, slug=""):
    """Build (yt_tags, hashtag_string, people) from config/hashtag_library.json.
    Auto categories + the tenant's location set feed every reel (reach). People tags
    (sourced council/candidates) ride along only when config/hashtag_people.ON exists."""
    lib = _library()
    if lib.get("_missing"):                       # graceful fallback if the file is gone
        base = ["govOS", "KiloAupuni", "Maui", "Hawaii", "civictech", "transparency",
                "accountability", "followthemoney", "testify", "Aloha"]
        return base[:15], " ".join("#" + t for t in (["Shorts"] + base[:8])), []
    reach, rotated = [], []
    for key, cat in lib.items():
        if key.startswith("_") or not isinstance(cat, dict) or "tags" not in cat: continue
        if not (cat.get("auto") or cat.get("tenant") == tid): continue
        tags = list(cat.get("tags", []))
        r = cat.get("rotate")
        if r and tags:                               # influencer set: a deterministic few per reel
            start = sum(ord(c) for c in (slug or key)) % len(tags)
            rotated += [tags[(start + i) % len(tags)] for i in range(min(int(r), len(tags)))]
        elif not r:
            reach += tags
    # de-dupe, keep order, civic identity first
    seen, ordered = set(), []
    for t in [tenant_tag(tid, "")] + reach:
        k = t.lower()
        if t and k not in seen: seen.add(k); ordered.append(t)
    infl = [t for t in dict.fromkeys(rotated) if t.lower() not in seen]   # rotating influencer tags
    # people tags (sourced) — council attaches to its own county; candidates when populated
    people = []
    if tid == "maui":
        people += [{"name": m["name"], "tag": m["tag"]} for m in
                   lib.get("maui_council", {}).get("members", [])]
    people += [{"name": m.get("name", ""), "tag": m.get("tag", "")} for m in
               lib.get("candidates_2026", {}).get("members", []) if m.get("tag")]
    if os.path.exists(PEOPLE_ON):                   # opt-in: reserve room so people tags land
        ptags = [p["tag"] for p in people][:9]
        yt_tags = (ordered[:13] + ptags)[:22]      # YouTube allows ~500 chars of tags
        ht_tokens = ["Shorts"] + ordered[:8] + infl + ptags
    else:
        yt_tags = (ordered + infl)[:18]
        ht_tokens = ["Shorts"] + ordered[:9] + infl
    hashtags = " ".join("#" + t for t in dict.fromkeys(ht_tokens))
    return yt_tags, hashtags, people

CROSSWALK = os.path.join(PROJECT, "config", "influencer_crosswalk.json")
_XW_CACHE = {}

def crosswalk_tags(body, title):
    """Map the reel's topic -> the interest hashtags that audience already follows
    (the influencer crosswalk). Returns up to 4 matched topic tags."""
    if not _XW_CACHE:
        try: _XW_CACHE.update(json.load(open(CROSSWALK, encoding="utf-8")))
        except Exception: _XW_CACHE["_missing"] = True
    ti = _XW_CACHE.get("topic_interests", {})
    text = ((body or "") + " " + (title or "")).lower()
    out = []
    for keys, tags in ti.items():
        if any(k.strip() in text for k in keys.split("|")):
            out += tags
    return list(dict.fromkeys(out))[:4]

def metadata(sb):
    tid, nm, dt = sb["tid"], sb["tenant"], sb["pretty"]
    body = sb["body"]; src = sb["src"]
    ttag = tenant_tag(tid, nm)
    tags, hashtags, people = load_hashtags(tid, sb.get("slug", ""))
    # crosswalk: tag the topic-interest streams matched to THIS reel's subject
    xw = crosswalk_tags(body, sb.get("title", ""))
    if xw:
        tags = list(dict.fromkeys(tags + xw))[:24]
        hashtags = hashtags + " " + " ".join("#" + t for t in xw)
    # YouTube title <= 100 chars (word-safe; never cut mid-word)
    SUFFIX = " #Shorts"
    core = "%s: %s meets %s — testify before the vote" % (ttag, _short_body(body, 38), dt)
    title = _wordcap(core, 100 - len(SUFFIX)) + SUFFIX
    desc = (
        "%s has a public meeting coming up on %s: %s.\n\n"
        "Before the vote, it's worth knowing three things:\n"
        "  • The LAW — what this body can and can't decide.\n"
        "  • The MONEY — who funds the people at the table (public campaign-finance records).\n"
        "  • The DEADLINE — testimony counts most before they vote.\n\n"
        "This is a neutral civic reminder built from public records. We don't tell you how to "
        "think — we help you get ahead of the vote and testify in your own words.\n\n"
        "Official agenda source: %s\n"
        "More: https://jimlangford.github.io/12sgi-king/agenda_explainer.html\n\n%s"
    ) % (nm, dt, _short_body(body), src or "see the county agenda portal", hashtags)
    tiktok_cap = ("%s meets %s. Know the law, follow the money, testify BEFORE the vote. "
                  "Public records only. %s") % (nm, dt, hashtags)
    ig_cap = ("Get ahead of the vote: %s, %s. The law, the money, and how to testify — "
              "all from public record. %s") % (nm, dt, hashtags)
    return {
        "slug": sb["slug"], "tenant": nm, "tenant_id": tid, "date": sb["date"], "pretty": dt,
        "source": src,
        "youtube": {"title": title, "description": desc, "tags": tags, "category_id": "25",
                    "privacy_default": "private"},
        "tiktok":  {"caption": tiktok_cap, "hashtags": hashtags},
        "instagram_reels": {"caption": ig_cap, "hashtags": hashtags},
        "canvas":  {"caption": tiktok_cap},   # the share-card lane in agenda_explainer.py
        "people_tags": people,                # sourced council/candidate tags (auto only if hashtag_people.ON)
        "people_auto": os.path.exists(PEOPLE_ON),
        "marketing": {
            "hook": "%s votes soon — here's how to be heard before they do." % nm,
            "best_post_window": "1-3 days before the meeting date (%s)" % dt,
            "framing": "neutral civic reminder; question, not accusation; public-record only",
        },
    }

def _short_body(body, cap=60):
    b = re.sub(r"\s*\(20\d\d-20\d\d\)\s*$", "", body or "").strip()
    b = re.sub(r"\s+Committee$", "", b)
    return _wordcap(b, cap)

def _wordcap(s, n):
    """Truncate to <= n chars on a word boundary (no dangling fragments)."""
    s = (s or "").strip()
    if len(s) <= n: return s
    cut = s[:n].rsplit(" ", 1)[0].rstrip(" ,-—")
    return cut or s[:n]


# ── assembly (ffmpeg, CPU) ───────────────────────────────────────────────────
def build_reel(sb, hold=4.2, fade=0.5, fps=30):
    """Render the 6 beats and concat them into a 9:16 mp4 with fades + silent audio."""
    slug = sb["slug"]
    d_draft = os.path.join(REELDIR, slug); d_frames = os.path.join(d_draft, "frames")
    os.makedirs(d_frames, exist_ok=True)
    frames = []
    total = len(sb["beats"])
    for i, beat in enumerate(sb["beats"]):
        fp = os.path.join(d_frames, "beat_%02d.png" % i)
        draw_beat(beat, sb, i, total).save(fp)
        frames.append(fp)
    out_mp4 = os.path.join(d_draft, "reel.mp4")
    # ʻŌlelo chant intro (local CPU voice) → muxed as the reel's audio; falls back to silent if unavailable
    chant_wav = None
    chant_text = sb.get("chant") or sb.get("oli") or sb.get("olelo") or DEFAULT_OLI
    if _olelo and chant_text:
        try:
            cw = os.path.join(d_draft, "chant.wav")
            _olelo.synth(chant_text, cw)
            if os.path.exists(cw) and os.path.getsize(cw) > 1000:
                chant_wav = cw
        except Exception as e:
            sys.stderr.write("olelo chant skipped (%s) — reel renders silent\n" % str(e)[:120])
    # English plain-language NARRATION (CPU SAPI, new studio recipe) of the agenda + moon, layered after the oli
    narr_wav = None
    if _olelo:
        try:
            script = _narration_script(sb)
            if script:
                nw = os.path.join(d_draft, "narration.wav")
                # the KIND voiceover (Jimmy 2026-06-18): default to the WARM cloned voice whenever the model
                # is ready (cached); opt out with CIVIC_WARM_VOICE=0 for a fast SAPI pass. Graceful fallback either way.
                warm = (os.environ.get("CIVIC_WARM_VOICE", "1") != "0" and hasattr(_olelo, "clone")
                        and getattr(_olelo, "clone_available", lambda: False)())
                if warm and _olelo.clone(script, nw):
                    narr_wav = nw
                elif hasattr(_olelo, "narrate") and _olelo.narrate(script, nw):
                    narr_wav = nw
        except Exception as e:
            sys.stderr.write("narration skipped (%s)\n" % str(e)[:120])
    audio_wav = _combine_audio(d_draft, chant_wav, narr_wav)
    # stretch the per-beat hold so the FULL chant+narration is heard (video length >= audio); also gives reading time
    if audio_wav and os.path.exists(audio_wav):
        try:
            dur = float(subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", audio_wav],
                capture_output=True, text=True, timeout=30, creationflags=NW).stdout.strip() or 0)
            need = (dur + 0.6) / max(1, len(frames))
            if need > hold:
                hold = round(min(need, 9.0), 2)   # cap a single beat at 9s so it never drags absurdly
        except Exception:
            pass
    ok = _ffmpeg_concat(frames, out_mp4, hold=hold, fade=fade, fps=fps, chant_wav=audio_wav)
    return out_mp4 if ok else None

def _narration_script(sb):
    """A concise spoken summary of the agenda + moon, in plain words — voiced after the oli chant."""
    p = []
    nm = sb.get("tenant", ""); pretty = sb.get("pretty", ""); body = sb.get("body", ""); title = sb.get("title", "")
    if nm: p.append("%s." % nm)
    if pretty: p.append("%s." % pretty)
    if body: p.append("On the agenda: %s." % re.sub(r"\s+", " ", body).strip()[:160])
    if title: p.append(re.sub(r"\s+", " ", title).strip()[:160] + ".")
    p.append("Know the law. Follow the money — who funds the deciders. Testify before the vote; your voice counts most beforehand.")
    moon = next((b.get("moon") for b in reversed(sb.get("beats", [])) if b.get("moon")), "")
    if moon:
        p.append(re.sub(r"[·—]", ".", moon).strip(". ") + ".")
    p.append("Keep it pono. Aloha.")
    return " ".join(p)

def _combine_audio(d, a, b):
    """oli chant first, a short breath, then the spoken summary — one audio track. Falls back gracefully."""
    a = a if (a and os.path.exists(a)) else None
    b = b if (b and os.path.exists(b)) else None
    if a and b:
        out = os.path.join(d, "audio.wav")
        fc = "[0:a]apad=pad_dur=0.4[o];[o][1:a]concat=n=2:v=0:a=1[a]"
        try:
            pr = subprocess.run(["ffmpeg", "-y", "-i", a, "-i", b, "-filter_complex", fc, "-map", "[a]", out],
                                capture_output=True, timeout=120, creationflags=NW)
            if pr.returncode == 0 and os.path.exists(out):
                return out
        except Exception:
            pass
        return a
    return a or b

def _ffmpeg_concat(frames, out_mp4, hold, fade, fps, chant_wav=None):
    # Build a filtergraph: each still -> a clip of `hold` s with fade-in/out, then concat.
    n = len(frames)
    cmd = ["ffmpeg", "-y"]
    for fp in frames:
        cmd += ["-loop", "1", "-t", str(hold), "-i", fp]
    # audio track: the ʻŌlelo chant (played once, then padded with silence to the reel length);
    # falls back to a silent source if no chant was generated (TikTok/IG prefer an audio track present)
    if chant_wav:
        cmd += ["-i", chant_wav]
    else:
        cmd += ["-f", "lavfi", "-t", str(hold * n), "-i", "anullsrc=r=44100:cl=stereo"]
    parts, labels = [], []
    for i in range(n):
        parts.append(
            "[%d:v]scale=%d:%d:force_original_aspect_ratio=decrease,"
            "pad=%d:%d:(ow-iw)/2:(oh-ih)/2:color=white,setsar=1,fps=%d,"
            "fade=t=in:st=0:d=%s,fade=t=out:st=%s:d=%s[v%d]"
            % (i, W, H, W, H, fps, fade, round(hold - fade, 2), fade, i))
        labels.append("[v%d]" % i)
    fc = ";".join(parts) + ";" + "".join(labels) + "concat=n=%d:v=1:a=0[vout]" % n
    if chant_wav:
        fc += ";[%d:a]apad[aout]" % n      # pad the chant with trailing silence; -shortest trims to the video
        amap = "[aout]"
    else:
        amap = "%d:a" % n
    cmd += ["-filter_complex", fc, "-map", "[vout]", "-map", amap,
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(fps),
            "-c:a", "aac", "-b:a", "96k", "-shortest", "-movflags", "+faststart", out_mp4]
    try:
        p = subprocess.run(cmd, capture_output=True, timeout=300, creationflags=NW)
        if p.returncode != 0:
            sys.stderr.write(p.stderr.decode("utf-8", "ignore")[-1500:] + "\n")
            return False
        return os.path.exists(out_mp4)
    except Exception as e:
        sys.stderr.write("ffmpeg failed: %s\n" % e); return False


# ── publish-staging (DRAFT ONLY — writes files; never posts) ─────────────────
def stage_for_upload(slug, mp4, meta):
    """Write the reel into the finals/shorts/<slug>/ format upload_shorts.py expects,
    plus a PRIVATE-by-default marker. This does NOT upload — a human runs upload_shorts.py
    when Jimmy confirms. We DELIBERATELY do not write _uploaded.json."""
    d = os.path.join(SHORTS, slug); os.makedirs(d, exist_ok=True)
    dst = os.path.join(d, "clip_00.mp4")
    try:
        import shutil; shutil.copy2(mp4, dst)
    except Exception as e:
        return None
    yt = meta["youtube"]
    json.dump({"title": yt["title"], "description": yt["description"], "tags": yt["tags"],
               "_privacy_default": "private", "_status": "DRAFT_REVIEW",
               "_note": "Built by agenda_reel.py. Upload is gated: requires Jimmy's go + "
                        "`python batch/upload_shorts.py --slug %s` (private). --public only after review." % slug},
              open(os.path.join(d, "clip_00.json"), "w", encoding="utf-8"), indent=2)
    return dst


def _log_blocked(sb, verdict):
    """Record a safety-gate block so a human can see what was withheld (never silently dropped)."""
    os.makedirs(REELDIR, exist_ok=True)
    line = json.dumps({"ts": AX.now_hst().strftime("%Y-%m-%d %H:%M HST"), "slug": sb["slug"],
                       "tenant": sb["tenant"], "date": sb["date"], "hits": verdict["hits"],
                       "reasons": verdict["reasons"]}, ensure_ascii=False)
    with open(os.path.join(REELDIR, "_blocked.jsonl"), "a", encoding="utf-8") as f:
        f.write(line + "\n")


def write_bundle(sb, mp4, meta):
    d = os.path.join(REELDIR, sb["slug"])
    json.dump(meta, open(os.path.join(d, "metadata.json"), "w", encoding="utf-8"), indent=2)
    json.dump({k: sb[k] for k in ("tid", "tenant", "body", "title", "date", "src")} |
              {"beats": [{"kind": b["kind"], "eyebrow": b["eyebrow"], "big": b["big"],
                          "body": b.get("body", "")} for b in sb["beats"]]},
              open(os.path.join(d, "storyboard.json"), "w", encoding="utf-8"), indent=2)
    yt = meta["youtube"]
    md = [
        "# Agenda reel — review sheet", "",
        "**Tenant:** %s  " % meta["tenant"], "**Meeting:** %s  " % sb["body"],
        "**Date:** %s  " % meta["pretty"], "**Source:** %s  " % (meta["source"] or "(county portal)"),
        "**Reel:** `%s`  " % os.path.join("reports", "_status", "agenda_reels", sb["slug"], "reel.mp4"),
        "**Upload-staged copy:** `%s`" % os.path.join("finals", "shorts", sb["slug"], "clip_00.mp4"),
        "", "**Status:** DRAFT — NOT POSTED. Live posting is gated on Jimmy's confirmation.",
        "", "---", "", "## YouTube Shorts", "",
        "**Title:** %s" % yt["title"], "", "**Description:**", "", "```", yt["description"], "```",
        "", "**Tags:** %s" % ", ".join(yt["tags"]), "",
        "## TikTok", "", meta["tiktok"]["caption"], "",
        "## Instagram Reels", "", meta["instagram_reels"]["caption"], "",
        "## Marketing", "",
        "- **Hook:** %s" % meta["marketing"]["hook"],
        "- **Best post window:** %s" % meta["marketing"]["best_post_window"],
        "- **Framing:** %s" % meta["marketing"]["framing"],
        "",
        "## People tags (sourced council; %s)" % ("AUTO-ON" if meta.get("people_auto") else "available, off by default"),
        "_Neutral civic engagement; create config/hashtag_people.ON to auto-attach. Candidates pending official filings._",
        "",
        " ".join("#" + p["tag"] for p in meta.get("people_tags", [])) or "_(none for this tenant yet)_",
    ]
    open(os.path.join(d, "marketing.md"), "w", encoding="utf-8").write("\n".join(md))


def write_index(built):
    os.makedirs(REELDIR, exist_ok=True)
    rows = ""
    for b in built:
        m = b["meta"]
        rows += (
            "<div class='card'>"
            "<video src='%s/reel.mp4' controls muted playsinline></video>"
            "<div class='meta'><div class='t'>%s</div><div class='d'>%s &middot; %s</div>"
            "<div class='yt'>%s</div>"
            "<div class='tags'>%s</div>"
            "<a href='%s/marketing.md'>marketing.md</a> &middot; <a href='%s' target='_blank'>source &#8599;</a>"
            "</div></div>"
            % (b["slug"], AX.esc(m["tenant"]), AX.esc(m["pretty"]),
               AX.esc(b["sb"]["body"][:60]), AX.esc(m["youtube"]["title"]),
               AX.esc(" ".join("#" + t for t in m["youtube"]["tags"][:8])),
               b["slug"], AX.esc(m["source"] or "#"))
        )
    g = AX.now_hst().strftime("%Y-%m-%d %H:%M HST")
    html = (
        "<!DOCTYPE html><html lang='en'><head><meta charset='UTF-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>"
        "<title>Agenda Reels — draft review | govOS</title><style>"
        "body{margin:0;background:#081420;color:#eaf2fc;font-family:Georgia,serif;padding:28px}"
        "h1{font-size:26px;margin:0 0 4px} .lead{color:#9fb2c8;font-size:14px;max-width:80ch}"
        ".banner{background:#241d0e;border:1px solid #5c4a1e;border-radius:10px;padding:12px 16px;margin:16px 0;font-size:13px;color:#e3c98a}"
        ".grid{display:flex;flex-wrap:wrap;gap:22px;margin-top:18px}"
        ".card{width:300px;border:1px solid #26456a;border-radius:14px;overflow:hidden;background:#0f2540}"
        "video{width:300px;height:533px;object-fit:cover;background:#000;display:block}"
        ".meta{padding:12px 14px} .t{font-weight:700} .d{font-size:12px;color:#8ea3ba;font-family:Consolas,monospace}"
        ".yt{font-size:13px;margin:8px 0;color:#eaf2fc} .tags{font-family:Consolas,monospace;font-size:11px;color:#7fb2ff;margin-bottom:8px}"
        "a{color:#6cb0f0;font-family:Consolas,monospace;font-size:11px}"
        "footer{margin-top:26px;border-top:1px solid #26456a;padding-top:12px;color:#8ea3ba;font-family:Consolas,monospace;font-size:11px}"
        "</style></head><body>"
        "<h1>Agenda Reels &mdash; draft review</h1>"
        "<p class='lead'>Each upcoming agenda item rendered as a 9:16 short-form reel: "
        "hook &rarr; what &rarr; law &rarr; money &rarr; deadline &rarr; how-to-testify. "
        "Built from the live agenda feed; neutral, public-record only.</p>"
        "<div class='banner'>&#9989; LIVE &mdash; James pre-approved auto-publish. YouTube posts on a "
        "daily drip (max 2/run); every reel is re-checked by the always-on neutral-framing safety gate "
        "before it posts. TikTok/IG are staged into the manual queue. Delete config/agenda_autopost.ENABLED to stop.</div>"
        "<div class='grid'>" + (rows or "<i>No reels built.</i>") + "</div>"
        "<footer>generated " + g + " &middot; agenda-reel v1 &middot; CPU render (no GPU) &middot; "
        "draft-only &middot; Kilo Aupuni &middot; aloha &middot; pono</footer></body></html>"
    )
    open(os.path.join(REELDIR, "index.html"), "w", encoding="utf-8", newline="\n").write(html)


# ── feed selection ───────────────────────────────────────────────────────────
def upcoming_for(tid, srcs, limit, today):
    s = srcs.get(tid)
    if not s: return []
    items = []
    for m in (s.get("upcoming") or []):
        dt = (m.get("date") or "")[:10]
        try:
            if datetime.strptime(dt, "%Y-%m-%d").date() < today: continue
        except Exception:
            pass
        items.append(m)
    return items[:limit]


def load_sources():
    try:
        return {s["tenant_id"]: s for s in json.load(open(AX.AGENDA, encoding="utf-8")).get("sources", [])}
    except Exception:
        return {}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tenant", default="maui", help="tenant_id (default maui)")
    ap.add_argument("--all-tenants", action="store_true", help="every tenant with upcoming items")
    ap.add_argument("--limit", type=int, default=2, help="max reels per tenant (default 2 = sample)")
    ap.add_argument("--hold", type=float, default=4.2, help="seconds per beat")
    ap.add_argument("--include-past", action="store_true", help="don't filter past-dated items")
    ap.add_argument("--force", action="store_true", help="re-render even if reel.mp4 exists")
    args = ap.parse_args()

    if sys.platform == "win32":
        import io; sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    srcs = load_sources()
    if not srcs:
        print("agenda_reel: no agenda sources found at", AX.AGENDA); return 1
    today = date.min if args.include_past else AX.now_hst().date()
    tids = AX.ORDER if args.all_tenants else [args.tenant]

    built, blocked = [], 0
    for tid in tids:
        for m in upcoming_for(tid, srcs, args.limit, today):
            sb = storyboard(tid, m)
            sb["slug"] = "agenda_%s_%s_%s" % (tid, (sb["date"] or "")[:10], slugify(sb["body"]))
            meta = metadata(sb)
            # ALWAYS-ON SAFETY GATE — neutral/sourced framing enforced before anything is staged.
            sb_text = " ".join(b.get("big", "") + " " + b.get("body", "") for b in sb["beats"])
            verdict = SAFETY.check_reel(meta, sb_text)
            if not verdict["ok"]:
                blocked += 1
                _log_blocked(sb, verdict)
                print("   ! BLOCKED by safety gate:", sb["slug"], "->", "; ".join(verdict["reasons"])[:160])
                continue
            mp4_path = os.path.join(REELDIR, sb["slug"], "reel.mp4")
            if os.path.exists(mp4_path) and not args.force:
                print("-> exists (skip render):", sb["slug"])
                mp4 = mp4_path
            else:
                print("-> building reel:", sb["slug"])
                mp4 = build_reel(sb, hold=args.hold)
                if not mp4:
                    print("   x render failed for", sb["slug"]); continue
            write_bundle(sb, mp4, meta)
            staged = stage_for_upload(sb["slug"], mp4, meta)
            built.append({"slug": sb["slug"], "sb": sb, "meta": meta, "mp4": mp4, "staged": staged})
            print("   + staged:", os.path.relpath(staged, PROJECT) if staged else "(stage failed)")

    write_index(built)
    print("\nagenda-reel: staged %d reel(s); safety gate BLOCKED %d. Gallery:" % (len(built), blocked))
    print("   ", os.path.join("reports", "_status", "agenda_reels", "index.html"))
    print("   Posting is handled separately by agenda_autopost.py (safety gate re-checks every post).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
