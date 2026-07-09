# -*- coding: utf-8 -*-
"""sage_kumulipo_card.py — the reverent animated Sage-Kumulipo card for an agenda day.

For a date it blends FOUR threads that your system already aligns, and lets them sit together
quietly (not fancy — honoring):
  1. the SAGE CARD for that date (moon_calendar.creative_offering): zone color, akua, wa archetype
  2. the MOON message (kaulana mahina): the po-night + its civic offering
  3. the KUMULIPO wa the node is bound to: the real, cited Hawaiian chant line(s)
     (Kalakaua 1889 text, in node_map/kumulipo_wa_text.json) in the tradition of Queen
     Lili'uokalani's 1897 English translation
  4. what the AGENDA weighs that day (agenda_sources.json)

It renders three slow movements (the moon · the chant · the day) and crossfades them into a
9:16 reel with ffmpeg. CPU only — no GPU, no ComfyUI; it never touches the card that the films
hold. Restrained palette, serif type, a few still stars. Honoring, not performing.

ATTRIBUTION + HUMILITY (honors moon_calendar's SAGE_GROUNDING_POLICY): the Hawaiian is cited
(Kalakaua text); the English lineage is Queen Lili'uokalani's 1897 translation; the archetype/
'developmental reading' is the project's own gloss, labeled as such — never put in the Queen's
mouth. Offered with aloha; node<->wa sacred binding is kumu-validation-pending.

USAGE:
  python tools/kilo-aupuni/sage_kumulipo_card.py 2026-06-17        # one day's card
  python tools/kilo-aupuni/sage_kumulipo_card.py                   # today (HST)
Output: reports/_status/agenda_reels/kumulipo/<date>/card.mp4 (+ movement_*.png)
"""
import os, sys, json, subprocess, datetime as dt
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import moon_calendar as M
try:
    from PIL import Image, ImageDraw, ImageFont
except Exception as e:
    print("Pillow required:", e); sys.exit(1)

PROJ = os.path.join(os.path.expanduser("~"), "Documents", "Claude", "Projects", "Video System elementLOTUS")
WA_TEXT = os.path.join(PROJ, "node_map", "kumulipo_wa_text.json")
NODE_MAP = os.path.join(PROJ, "node_map", "node_map_canonical.json")
AGENDA = os.path.join(HERE, "agenda_sources.json")
OUTROOT = os.path.join(PROJ, "reports", "_status", "agenda_reels", "kumulipo")
NW = 0x08000000 if os.name == "nt" else 0
W, H = 1080, 1920

# Queen Lili'uokalani's 1897 English translation — the universal creation opening (wa 1),
# public domain. Quoted verbatim, attributed; used as the anchoring epigraph. (Other wa show the
# cited Hawaiian + the project's labeled reading rather than unverified English.)
LILIU_WA1 = ["At the time when the earth became hot",
             "At the time when the heavens turned about",
             "At the time when the sun was darkened",
             "To cause the moon to shine",
             "The slime, this was the source of the earth",
             "The source of the night that made night",
             "Nothing but night."]

def _font(names, size):
    for n in names:
        for p in (n, os.path.join(r"C:\Windows\Fonts", n)):
            try: return ImageFont.truetype(p, size)
            except Exception: pass
    return ImageFont.load_default()
def SER(sz, bold=False): return _font(["georgiab.ttf"] if bold else ["georgia.ttf", "times.ttf"], sz)
def MON(sz): return _font(["consola.ttf"], sz)

def hexrgb(h, default=(56, 189, 248)):
    try: h = h.lstrip("#"); return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))
    except Exception: return default

def wrap(d, text, font, maxw):
    out, line = [], ""
    for w in (text or "").split():
        t = (line + " " + w).strip()
        if line and d.textlength(t, font=font) > maxw: out.append(line); line = w
        else: line = t
    if line: out.append(line)
    return out

# ── gather the four threads (all sourced) ────────────────────────────────────
def gather(date_s):
    r = M.reading(date_s); co = M.creative_offering(date_s)
    wa = (co or {}).get("node") and _node_wa(co["node"])
    wa_text = _wa_lines(wa.get("wa")) if wa else None
    agenda = _agenda_for(date_s)
    return {"date": date_s, "moon": r, "card": co, "wa": wa, "wa_text": wa_text, "agenda": agenda}

def _node_wa(node_id):
    try:
        nm = json.load(open(NODE_MAP, encoding="utf-8"))
        nodes = nm.get("nodes") or (list(nm.values()) if isinstance(nm, dict) else nm)
        for n in nodes:
            if isinstance(n, dict) and n.get("id") == node_id:
                return n.get("kumulipo") or {}
    except Exception: pass
    return {}

def _wa_lines(wa_num):
    if not wa_num: return None
    try:
        d = json.load(open(WA_TEXT, encoding="utf-8"))
        for w in d.get("wa", []):
            if w.get("wa") == wa_num:
                lines = [ln.get("text", "") for ln in w.get("lines", [])[:6] if ln.get("text")]
                return {"wa": wa_num, "name": w.get("hawaiian_name", ""), "phase": w.get("phase", ""),
                        "incipit": w.get("incipit", ""), "births": w.get("births", ""),
                        "lines": lines, "n_lines": w.get("n_lines")}
    except Exception: pass
    return None

def _agenda_for(date_s):
    try:
        srcs = {s["tenant_id"]: s for s in json.load(open(AGENDA, encoding="utf-8")).get("sources", [])}
        items = [m for m in (srcs.get("maui", {}).get("upcoming") or []) if (m.get("date") or "")[:10] == date_s]
        return {"tenant": "Maui County", "items": items}
    except Exception:
        return {"tenant": "Maui County", "items": []}

# ── the three movements ──────────────────────────────────────────────────────
def stars(d, seed, n=46):
    s = seed
    for _ in range(n):
        s = (s * 1103515245 + 12345) & 0x7fffffff; x = s % W
        s = (s * 1103515245 + 12345) & 0x7fffffff; y = s % H
        s = (s * 1103515245 + 12345) & 0x7fffffff; r = 1 + s % 2
        d.ellipse([x, y, x + r, y + r], fill=(210, 220, 240))

def ground(phase):
    # Po = the generative dark; Ao = dawn light. Restrained, not flashy.
    if phase == "Ao": top, bot = (28, 26, 40), (66, 54, 44)
    else: top, bot = (9, 11, 26), (20, 24, 52)
    img = Image.new("RGB", (W, H), top); px = img.load()
    for y in range(H):
        t = y / (H - 1); px_row = tuple(int(top[i] + (bot[i] - top[i]) * t) for i in range(3))
        for x in range(W): px[x, y] = px_row
    return img

def frame_card(img, zc):
    d = ImageDraw.Draw(img)
    d.rectangle([46, 46, W - 46, H - 46], outline=zc, width=3)
    d.rectangle([60, 60, W - 60, H - 60], outline=(zc[0] // 2 + 40, zc[1] // 2 + 40, zc[2] // 2 + 40), width=1)
    return d

def movement(kind, g, idx):
    phase = (g["wa"] or {}).get("phase") or (g["card"] or {}).get("ao_po") or "Po"
    zc = hexrgb((g["card"] or {}).get("frame_hex"))
    img = ground(phase); d = ImageDraw.Draw(img); stars(d, 7 + idx * 31)
    frame_card(img, zc); pad = 116; maxw = W - pad * 2
    cream, soft, gold = (236, 232, 222), (170, 178, 198), (212, 175, 110)
    moon = g["moon"]; card = g["card"] or {}; wa = g["wa"] or {}; wt = g["wa_text"] or {}
    y = 250
    if kind == "moon":
        d.text((W/2, y), "KAULANA MAHINA", font=MON(34), fill=zc, anchor="ma"); y += 90
        d.text((W/2, y), "☾", font=SER(150), fill=cream, anchor="ma"); y += 220
        d.text((W/2, y), "po %d · %s" % (moon["night"], moon["po"]), font=SER(64, True), fill=cream, anchor="ma"); y += 96
        d.text((W/2, y), "(%s · %s)" % (moon["anahulu"], moon["phase"]), font=MON(30), fill=soft, anchor="ma"); y += 110
        for ln in wrap(d, moon["offering"], SER(44), maxw)[:4]:
            d.text((W/2, y), ln, font=SER(44), fill=gold, anchor="ma"); y += 64
    elif kind == "chant":
        d.text((W/2, y), "KUMULIPO · WĀ %s" % (wa.get("wa", "")), font=MON(34), fill=zc, anchor="ma"); y += 84
        if wt.get("name"): d.text((W/2, y), wt["name"], font=SER(46, True), fill=cream, anchor="ma"); y += 80
        if wa.get("archetype"):
            for ln in wrap(d, wa["archetype"], SER(40), maxw)[:2]:
                d.text((W/2, y), ln, font=SER(40), fill=soft, anchor="ma"); y += 56
        y += 36
        # the real, cited Hawaiian chant line(s)
        for ln in (wt.get("lines") or [wt.get("incipit", "")])[:3]:
            for w in wrap(d, ln, SER(50), maxw)[:2]:
                d.text((W/2, y), w, font=SER(50), fill=cream, anchor="ma"); y += 66
            y += 8
        y += 22
        eng = LILIU_WA1 if wa.get("wa") == 1 else None
        if eng:
            for ln in eng[:5]:
                d.text((W/2, y), ln, font=SER(36), fill=soft, anchor="ma"); y += 50
        elif wa.get("developmental_meaning"):
            d.text((W/2, y), "— a developmental reading —", font=MON(26), fill=(120,128,150), anchor="ma"); y += 50
            for ln in wrap(d, wa["developmental_meaning"], SER(38), maxw)[:3]:
                d.text((W/2, y), ln, font=SER(38), fill=soft, anchor="ma"); y += 52
    else:  # the day
        d.text((W/2, y), "AND TODAY, ON MAUI", font=MON(34), fill=zc, anchor="ma"); y += 96
        items = g["agenda"]["items"]
        if items:
            for m in items[:3]:
                body = (m.get("body", "") or "").replace(" (2025-2027)", "")
                for ln in wrap(d, body, SER(46, True), maxw)[:2]:
                    d.text((W/2, y), ln, font=SER(46, True), fill=cream, anchor="ma"); y += 62
                y += 14
        else:
            d.text((W/2, y), "the council weighs the people's work", font=SER(46), fill=cream, anchor="ma"); y += 80
        y += 30
        blend = ("As the wa turns — %s — the same questions meet us: the land, the water, "
                 "and who tends them. Know the law, follow the money, testify before the vote." %
                 ((wa.get("archetype") or "the source").split(" - ")[-1].lower()))
        for ln in wrap(d, blend, SER(40), maxw)[:6]:
            d.text((W/2, y), ln, font=SER(40), fill=gold, anchor="ma"); y += 58
    # footer — attribution + humility, every movement
    d.text((W/2, H-150), "Kumulipo · Hawaiian text Kalakaua 1889 · in the tradition of",
           font=MON(24), fill=(120,128,150), anchor="ma")
    d.text((W/2, H-118), "Queen Liliʻuokalani’s 1897 translation · offered with aloha, kumu pending",
           font=MON(24), fill=(120,128,150), anchor="ma")
    d.text((W/2, H-82), "12 Stones · Kilo Aupuni · the people’s record", font=MON(24), fill=zc, anchor="ma")
    return img

def overlay_text_png(g, path):
    """A distinct TEXT LAYER (transparent 9:16 PNG) composited OVER the moving background with a fade-in
    (Jimmy 2026-06-19: "overlay text layer + animation across the entire duration"). Carries the blessing
    line in the lower third on a soft scrim so it reads over the motion; reuses the card fonts (Hawaiian
    diacritics intact)."""
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    cream, gold = (238, 232, 214), (214, 178, 120)
    moon = g["moon"]
    d.rectangle([0, int(H * 0.64), W, int(H * 0.99)], fill=(8, 10, 22, 140))  # legibility scrim
    y = int(H * 0.68)
    d.text((W / 2, y), "moon blessing", font=MON(36), fill=gold, anchor="ma"); y += 84
    for ln in wrap(d, moon.get("offering", ""), SER(60, True), W - 150)[:3]:
        d.text((W / 2, y), ln, font=SER(60, True), fill=cream, anchor="ma"); y += 82
    d.text((W / 2, int(H * 0.945)), "%s · po %d %s" % (moon.get("phase", ""), moon["night"], moon["po"]),
           font=MON(32), fill=gold, anchor="ma")
    img.save(path)
    return path


def build(date_s, hold=6.0, fade=1.0, fps=30):
    g = gather(date_s)
    out = os.path.join(OUTROOT, date_s); os.makedirs(out, exist_ok=True)
    frames = []
    for i, kind in enumerate(("moon", "chant", "day")):
        fp = os.path.join(out, "movement_%d_%s.png" % (i, kind))
        movement(kind, g, i).save(fp); frames.append(fp)
    mp4 = os.path.join(out, "card.mp4")
    ov = overlay_text_png(g, os.path.join(out, "overlay_text.png"))   # the animated text LAYER
    total = hold * len(frames)
    cmd = ["ffmpeg", "-y"]
    for fp in frames: cmd += ["-loop", "1", "-t", str(hold), "-i", fp]
    cmd += ["-f", "lavfi", "-t", str(total), "-i", "anullsrc=r=44100:cl=stereo"]
    cmd += ["-loop", "1", "-t", str(total), "-i", ov]                # overlay text input
    ovi = len(frames) + 1
    parts, labels = [], []
    for i in range(len(frames)):
        # stronger CONTINUOUS Ken Burns (centered zoom 1.0->1.20 over the hold) so motion reads across the
        # WHOLE clip, not a static card; gentle in/out fades between movements.
        parts.append("[%d:v]scale=%d:%d,zoompan=z='min(zoom+0.0018,1.20)':x='iw/2-(iw/zoom/2)':"
                     "y='ih/2-(ih/zoom/2)':d=%d:s=%dx%d:fps=%d,"
                     "fade=t=in:st=0:d=%s,fade=t=out:st=%s:d=%s[v%d]"
                     % (i, W, H, int(hold*fps), W, H, fps, fade, round(hold-fade,2), fade, i))
        labels.append("[v%d]" % i)
    # background movements -> [vbg]; the text layer fades in and rides OVER the motion the whole duration
    fc = (";".join(parts) + ";" + "".join(labels) + "concat=n=%d:v=1:a=0[vbg];" % len(frames)
          + "[%d:v]format=rgba,fade=t=in:st=0.6:d=1.6:alpha=1[txt];" % ovi
          + "[vbg][txt]overlay=0:0[vo]")
    cmd += ["-filter_complex", fc, "-map", "[vo]", "-map", "%d:a" % len(frames),
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(fps), "-c:a", "aac",
            "-b:a", "96k", "-shortest", "-movflags", "+faststart", mp4]
    p = subprocess.run(cmd, capture_output=True, timeout=300, creationflags=NW)
    if p.returncode != 0:
        sys.stderr.write(p.stderr.decode("utf-8", "ignore")[-1200:]); return None, g
    return mp4, g

def main():
    if sys.platform == "win32":
        import io; sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    date_s = sys.argv[1] if len(sys.argv) > 1 else (dt.datetime.utcnow() - dt.timedelta(hours=10)).date().isoformat()
    mp4, g = build(date_s)
    m, wa = g["moon"], (g["wa"] or {})
    print("Sage-Kumulipo card for", date_s)
    print("  moon : po %d %s (%s) -> %s" % (m["night"], m["po"], m["phase"], m["offering"]))
    if g["card"]: print("  card : node %s %s | zone %s | akua %s | %s" % (
        g["card"]["node"], g["card"]["node_name"], g["card"]["zone"], g["card"]["akua"], g["card"].get("wa_archetype")))
    print("  wa   : %s %s (%s) %s" % (wa.get("wa",""), (g["wa_text"] or {}).get("name",""), wa.get("phase",""), wa.get("archetype","")))
    print("  ->", os.path.relpath(mp4, PROJ) if mp4 else "(render failed)")
    return 0 if mp4 else 1

if __name__ == "__main__":
    sys.exit(main())
