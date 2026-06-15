#!/usr/bin/env python3
"""moon_calendar.py — kaulana mahina (Hawaiian moon calendar) as the timing dimension that links a
real agenda DATE to the Sage node's moon, and offers an aloha suggestion grounded in the moon.

For a date it computes the lunation age (astronomical) → the night of the 30-pō Hawaiian moon month
→ the documented general nature of that night → a gentle CIVIC offering (when to stand and testify,
when to listen, when a night is sacred to collective good). This is what lets the Sage twin suggest
*from the moon dimension* and bring aloha to the agendas.

GROUNDING (honors SAGE_GROUNDING_POLICY): the 30 pō names + their broad traditional associations are
DOCUMENTED public kaulana mahina (Malo; Kepelino; Bishop Museum; UH Hawaiʻinuiākea). The moon-AGE is
real astronomy (±1 night vs observed — the true kaulana mahina is OBSERVED, so this is a forecast to
confirm). Offerings are framed as "traditionally a night for…", never directives, and the specific
node↔pō sacred binding stays kumu-validation-pending — no fabricated sacred protocol, reverent only.
Stdlib only.
"""
import math
from datetime import date, datetime

SYNODIC = 29.530588853                 # mean lunation, days
_REF_NEWMOON_JD = 2451550.1            # 2000-01-06 ~18:14 UTC, a known new moon

# The 30 nights, in 3 anahulu (10-night groups): Hoʻonui (waxing) · Poepoe (full/round) · Hoʻēmi (waning).
# (name, anahulu, broad documented nature, CIVIC aloha offering tied to that nature)
PO = [
 ("Hilo","Hoʻonui","first thin crescent; new beginnings, planting","a night of beginnings — plant the intention; learn the item before you speak"),
 ("Hoaka","Hoʻonui","faint light; casting of shadows, caution","go gently — gather the facts before the vote casts its shadow"),
 ("Kūkahi","Hoʻonui","Kū — upright, standing; good for planting & work","stand and be counted — a good night to testify"),
 ("Kūlua","Hoʻonui","Kū — upright, productive","stand together — add your voice to the record"),
 ("Kūkolu","Hoʻonui","Kū — upright, productive","keep standing — the upright nights favor those who show up"),
 ("Kūpau","Hoʻonui","Kū — the last of the upright nights","finish what you stood for — submit the testimony"),
 ("ʻOlekūkahi","Hoʻonui","ʻOle — 'nothing'; low tides, rest, not for forcing","a night to listen, not force — read the agenda, ready the question"),
 ("ʻOlekūlua","Hoʻonui","ʻOle — rest, weeding, clearing","clear the noise — separate the money from the merit"),
 ("ʻOlekūkolu","Hoʻonui","ʻOle — rest, low productivity","patience — let the record speak before you do"),
 ("ʻOlepau","Hoʻonui","ʻOle — the last quiet night","rest closes; tomorrow the light grows — prepare to act"),
 ("Huna","Poepoe","hidden; root crops, the unseen made ready","look for what's hidden in the item — the unanswered pair"),
 ("Mōhalu","Poepoe","unfolding; flowers, fruit set","let your testimony unfold — name the question plainly"),
 ("Hua","Poepoe","fruit, seed, abundance begins","the fruit forms — this is when showing up bears the most"),
 ("Akua","Poepoe","sacred to the akua; ceremony, reverence","a sacred night — bring reverence, not contention, to the chamber"),
 ("Hoku","Poepoe","near-full; fullness, peak fishing & planting","the people's voice is near its fullest — gather the neighbors"),
 ("Māhealani","Poepoe","FULL MOON; abundance, clarity, everything thrives","full light — testify in the open; nothing hidden answers best now"),
 ("Kulu","Poepoe","the moon 'drips'/begins to wane; release","release what's settled; carry forward what still needs answering"),
 ("Lāʻaukūkahi","Poepoe","Lāʻau — medicine, healing herbs","a healing night — frame the testimony to restore, not to wound"),
 ("Lāʻaukūlua","Poepoe","Lāʻau — medicine, gathering of cures","gather the remedy — the law that already answers the wrong"),
 ("Lāʻaupau","Poepoe","Lāʻau — the last medicine night","apply the cure — the records request, the testimony, the vote"),
 ("ʻOlekūkahi","Hoʻēmi","ʻOle — rest returns, low tides","rest and watch — not every night is for forcing the hand"),
 ("ʻOlekūlua","Hoʻēmi","ʻOle — quiet, weeding","weed the agenda — which items truly serve the people?"),
 ("ʻOlepau","Hoʻēmi","ʻOle — the last quiet of the waning","stillness before the sacred nights — listen for the broken pair"),
 ("Kāloakūkahi","Hoʻēmi","Kāloa — sacred to Kanaloa (ocean); long crops, fishing","the ocean's nights — think of the makai, the ʻāina, the long horizon"),
 ("Kāloakūlua","Hoʻēmi","Kāloa — Kanaloa; deep waters, endurance","endure — the long crops and long fights both reward patience"),
 ("Kāloapau","Hoʻēmi","Kāloa — the last of Kanaloa's nights","close the deep work — what did the vote answer to?"),
 ("Kāne","Hoʻēmi","KAPU to Kāne — fresh water, sun, life; ceremony, no contention","sacred to Kāne — a night for collective good and clean water, not quarrel"),
 ("Lono","Hoʻēmi","KAPU to Lono — rain, harvest, peace; Makahiki spirit","sacred to Lono — bring the harvest spirit: shared abundance, not capture"),
 ("Mauli","Hoʻēmi","last sliver, 'last breath' of the moon; reflection","reflect — what pair still does not answer? mark it for the next light"),
 ("Muku","Hoʻēmi","dark moon, 'cut off'; rest, the close before renewal","the dark before renewal — rest, then begin the cycle in pono"),
]

def _jd(d):
    y, m, dd = d.year, d.month, d.day
    if m <= 2: y -= 1; m += 12
    a = y // 100; b = 2 - a + a // 4
    return int(365.25 * (y + 4716)) + int(30.6001 * (m + 1)) + dd + b - 1524.5

def moon_age(d):
    """days into the current lunation (0..~29.53)."""
    return (_jd(d) - _REF_NEWMOON_JD) % SYNODIC

def parse(s):
    for f in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%B %d, %Y"):
        try: return datetime.strptime(str(s)[:19] if "T" in str(s) else str(s), f).date()
        except Exception: pass
    return None

def reading(s):
    """Date string -> kaulana mahina reading (the moon timing for an agenda date)."""
    d = parse(s)
    if not d: return None
    age = moon_age(d)
    night = min(29, int(age))                      # 0..29 index -> pō list
    nm, anahulu, nature, offering = PO[night]
    phase = "new/dark" if age < 1.5 or age > 28 else ("full" if 13.5 <= age <= 16.5 else ("waxing" if age < 14.76 else "waning"))
    return {"date": d.isoformat(), "night": night + 1, "po": nm, "anahulu": anahulu,
            "phase": phase, "nature": nature, "offering": offering, "moon_age": round(age, 1),
            "note": "kaulana mahina — forecast from lunation; the true reckoning is observed. Offering, not directive; confirm with a kumu."}

if __name__ == "__main__":
    import sys
    for s in (sys.argv[1:] or ["2026-06-15", "2026-06-17", "2026-07-09"]):
        r = reading(s)
        print(f"{s}: pō {r['night']} {r['po']} ({r['anahulu']}, {r['phase']}) — {r['nature']}\n   offering: {r['offering']}")
