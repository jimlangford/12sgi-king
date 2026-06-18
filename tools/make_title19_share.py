# -*- coding: utf-8 -*-
# Yale-blue 1200x630 Facebook/OG share card for the Title 19 free public service.
# Neutral, aloha-framed. No private data. ASCII-only text to avoid font glitches.
import os
from PIL import Image, ImageDraw, ImageFont

W, H = 1200, 630
BG     = (255, 255, 255)
INK    = (19, 36, 61)
DIM    = (65, 83, 107)
ACCENT = (0, 53, 107)
ACC2   = (18, 89, 163)
OK     = (31, 138, 91)
PANEL  = (231, 238, 248)
LINE   = (186, 205, 230)

def font(sz, bold=False):
    names = ([r"C:\Windows\Fonts\segoeuib.ttf", r"C:\Windows\Fonts\seguisb.ttf"] if bold
             else [r"C:\Windows\Fonts\segoeui.ttf"])
    for n in names:
        if os.path.exists(n):
            return ImageFont.truetype(n, sz)
    return ImageFont.load_default()

img = Image.new("RGB", (W, H), BG)
d = ImageDraw.Draw(img)

d.rectangle([0, 0, 14, H], fill=ACCENT)
d.text((60, 54), "MAUI COUNTY  .  TITLE 19 ZONING  .  govOS", font=font(24, True), fill=ACCENT)
d.text((58, 104), "Title 19", font=font(104, True), fill=INK)
d.text((62, 222), "Plain-Language Service", font=font(56, True), fill=ACC2)

pill = "FREE  .  NO ACCOUNT  .  PUBLIC RECORDS"
pw = d.textlength(pill, font=font(25, True))
d.rounded_rectangle([60, 300, 60 + pw + 44, 346], radius=23, fill=PANEL, outline=LINE, width=2)
d.text((82, 310), pill, font=font(25, True), fill=ACCENT)

bullets = [
    "LIVE parcel lookup -- enter your TMK, see every designation",
    "Process navigator with who pays  .  Community Plans (incl. Lahaina)",
    "Agriculture & Rural zoning  .  Table of Uses  .  who decides",
    "Form-based code crosswalk -- a working model of the rewrite",
]
y = 378
for b in bullets:
    d.ellipse([62, y + 9, 76, y + 23], fill=OK)
    d.text((92, y), b, font=font(26), fill=DIM)
    y += 45

d.rectangle([0, H - 64, W, H], fill=ACCENT)
d.text((60, H - 50), "jimlangford.github.io/12sgi-king/king/civic/templates/title19-service/", font=font(24, True), fill=(255, 255, 255))
d.text((W - 320, H - 50), "first version - expanding", font=font(22), fill=(200, 216, 240))

out = r"C:\Users\12sgi\Documents\Claude\12sgi-king\tools\title19_share.png"
img.save(out, "PNG")
print("WROTE", out, os.path.getsize(out), "bytes")
