#!/usr/bin/env python3
"""trend_aloha.py — sunrise/sunset aloha messages keyed to what's SALIENT across the tenants (Jimmy 2026-06-18).

"Perhaps the server can understand who/what is trending around the world of all tenants and send aloha
messages hourly or at sunrise/sunset each day." This composes a warm, curse-breaking aloha message per
tenant, tying together three honest, SOURCED signals:
  • the MOON — today's kaulana mahina reading + its civic offering (moon_calendar),
  • the SALIENT civic item — the nearest UPCOMING agenda / recent council item we already track (never invented),
  • the SOLAR MOMENT — local sunrise or sunset, computed on-box (NOAA almanac algorithm, no API/key).
"World of all tenants" = a one-line pulse aggregating each tenant's salient item ("what's moving across the
islands") — sourced from our own civic record, framed as a gentle invitation to show up, never an accusation.

Publish posture: this STAGES messages (reports/_status/aloha/). Aloha/moon is an allowlisted publish class,
but actual posting still goes through the existing gated lane (upload_shorts allowlist + Sunshine cadence) —
this never auto-posts. Default cadence = sunrise + sunset per tenant; hourly is opt-in. Stdlib only.

CLI:  python trend_aloha.py --tenant hi-maui --moment sunrise --date 2026-06-19
      python trend_aloha.py --all            # every tenant, both moments for today -> staged JSON
"""
import os, sys, json, math, glob, argparse
from datetime import date as _date, datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
try:
    import moon_calendar as mc
except Exception:
    mc = None

# Civic tenants with public coordinates + UTC offset (HST=-10 no DST; NY=-4 DST summer).
TENANT_GEO = {
    "hi-maui":     (20.80, -156.33, -10, "Maui"),
    "hi-honolulu": (21.31, -157.86, -10, "Honolulu"),
    "hi-hawaii":   (19.70, -155.08, -10, "Hawaiʻi County"),
    "hi-kauai":    (22.08, -159.32, -10, "Kauaʻi"),
    "hi-state":    (21.31, -157.86, -10, "State of Hawaiʻi"),
    "ny":          (40.71,  -74.01,  -4, "New York"),
}


# ── solar (NOAA / Almanac for Computers sunrise-sunset algorithm; local math, no network) ──
def _sun(lat, lon, d, tz, rising):
    ZEN = 90.833                                   # official zenith incl. refraction
    D2R, R2D = math.pi / 180.0, 180.0 / math.pi
    N = d.timetuple().tm_yday
    lngHour = lon / 15.0
    t = N + (((6 if rising else 18) - lngHour) / 24.0)
    M = (0.9856 * t) - 3.289
    L = M + (1.916 * math.sin(M * D2R)) + (0.020 * math.sin(2 * M * D2R)) + 282.634
    L %= 360.0
    RA = R2D * math.atan(0.91764 * math.tan(L * D2R))
    RA %= 360.0
    RA += ((L // 90) * 90) - ((RA // 90) * 90)     # same quadrant as L
    RA /= 15.0
    sinDec = 0.39782 * math.sin(L * D2R)
    cosDec = math.cos(math.asin(sinDec))
    cosH = (math.cos(ZEN * D2R) - (sinDec * math.sin(lat * D2R))) / (cosDec * math.cos(lat * D2R))
    if cosH > 1 or cosH < -1:
        return None                                # sun never rises/sets that day at this latitude
    H = (360 - R2D * math.acos(cosH)) if rising else (R2D * math.acos(cosH))
    H /= 15.0
    T = H + RA - (0.06571 * t) - 6.622
    UT = (T - lngHour) % 24.0
    local = (UT + tz) % 24.0
    hh = int(local); mm = int(round((local - hh) * 60))
    if mm == 60: hh, mm = (hh + 1) % 24, 0
    return "%02d:%02d" % (hh, mm)


def sun_times(tenant, d=None):
    g = TENANT_GEO.get(tenant)
    if not g: return (None, None)
    lat, lon, tz, _ = g
    d = d or _date.today()
    return (_sun(lat, lon, d, tz, True), _sun(lat, lon, d, tz, False))


# ── salient signal (sourced — what's upcoming / on the record; never invented) ──
def _short_tid(tenant):
    return tenant.replace("hi-", "")


def salient(tenant, d=None):
    """The nearest upcoming agenda item (or a recent council item) for this tenant. None if nothing tracked."""
    d = d or _date.today()
    tid = _short_tid(tenant)
    # 1) upcoming agenda posts we already stage
    best = None
    for p in glob.glob(os.path.join(PROJ, "reports", "_status", "agenda_posts", "agenda_%s_*.json" % tid)):
        try:
            j = json.load(open(p, encoding="utf-8"))
        except Exception:
            continue
        dt = j.get("meeting_date") or j.get("date") or ""
        title = j.get("board") or j.get("title") or j.get("body") or j.get("committee") or ""
        if dt and title and dt >= d.isoformat():
            if best is None or dt < best[0]:
                best = (dt, str(title)[:120])
    if best:
        return {"kind": "agenda", "when": best[0], "what": best[1]}
    # 2) most recent council item on the record (the council index is Maui's CivicClerk record)
    idx = os.path.join(PROJ, "reports", "council", "index.jsonl")
    if os.path.exists(idx) and tid == "maui":
        last = None
        try:
            for line in open(idx, encoding="utf-8"):
                line = line.strip()
                if not line: continue
                last = json.loads(line)        # last non-empty line = most recent
        except Exception:
            last = None
        if last:
            return {"kind": "council", "when": last.get("date", ""),
                    "what": str(last.get("event") or last.get("title") or "a recent decision")[:120]}
    return None


def world_pulse(d=None):
    """One-line cross-tenant pulse: what's moving across the islands (sourced from each tenant's salient item)."""
    d = d or _date.today()
    bits = []
    for t in TENANT_GEO:
        s = salient(t, d)
        if s:
            bits.append("%s (%s)" % (TENANT_GEO[t][3], s["what"][:40].rstrip()))
    if not bits:
        return "Across the islands, a quiet day on the public record — a good day to listen."
    return "Moving across the tenants today: " + "; ".join(bits[:4]) + "."


# ── compose the aloha message (curse-breaker tone: aloha + facts, an invitation never an accusation) ──
_RISE = "E ala ē — rise with the light."
_SET = "As the sun sets, rest in gratitude; tomorrow we serve again."


def aloha_message(tenant, moment="sunrise", d=None):
    d = d or _date.today()
    g = TENANT_GEO.get(tenant)
    place = g[3] if g else tenant
    rise, set_ = sun_times(tenant, d)
    when = rise if moment == "sunrise" else set_
    moon = (mc.reading(d.isoformat()) if mc else None) or {}
    offering = moon.get("offering") or moon.get("creative_offering") or ""
    po = moon.get("po") or ""
    sal = salient(tenant, d)
    open_line = (_RISE if moment == "sunrise" else _SET)
    parts = ["Aloha, %s." % place, open_line]
    if po:
        parts.append("Tonight is %s." % po)
    if offering:
        parts.append(offering.rstrip(". ") + ".")
    if sal:
        lead = ("Coming up: " if sal["kind"] == "agenda" else "On the record: ")
        tail = (" — your voice on the record before the vote means the most." if sal["kind"] == "agenda" else "")
        parts.append(lead + sal["what"].rstrip(". ") + (" (%s)" % sal["when"] if sal["when"] else "") + "." + tail)
    parts.append("Keep it pono. With aloha.")
    text = " ".join(parts)
    return {"tenant": tenant, "place": place, "moment": moment, "date": d.isoformat(),
            "local_time": when, "moon_po": po, "salient": sal, "text": text,
            "publish_class": "aloha", "staged": True,
            "note": "Sourced civic content; an invitation, never an accusation. Staging only — posting stays gated."}


# ── stage (never auto-post; the gated lane handles publishing per the allowlist) ──
def stage(msg):
    d = os.path.join(PROJ, "reports", "_status", "aloha")
    os.makedirs(d, exist_ok=True)
    fn = "aloha_%s_%s_%s.json" % (msg["tenant"], msg["date"], msg["moment"])
    path = os.path.join(d, fn)
    json.dump(msg, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return path


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tenant", default="hi-maui")
    ap.add_argument("--moment", default="sunrise", choices=["sunrise", "sunset"])
    ap.add_argument("--date", default=None)
    ap.add_argument("--all", action="store_true", help="every tenant, both moments, today -> staged")
    a = ap.parse_args()
    d = mc.parse(a.date) if (a.date and mc) else (datetime.strptime(a.date, "%Y-%m-%d").date() if a.date else _date.today())
    if a.all:
        print("World pulse:", world_pulse(d))
        for t in TENANT_GEO:
            r, s = sun_times(t, d)
            for moment in ("sunrise", "sunset"):
                m = aloha_message(t, moment, d)
                p = stage(m)
                print("  staged %-12s %-7s %s -> %s" % (t, moment, m["local_time"], os.path.basename(p)))
        return 0
    m = aloha_message(a.tenant, a.moment, d)
    print("World pulse:", world_pulse(d))
    print("\n[%s · %s · local %s]\n%s" % (m["place"], a.moment, m["local_time"], m["text"]))
    print("\nstaged ->", stage(m))
    return 0


if __name__ == "__main__":
    if sys.platform == "win32":
        import io; sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(main())
