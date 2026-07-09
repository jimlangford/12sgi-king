#!/usr/bin/env python3
"""testimony_realtime.py — real-time testimony monitor for ACTIVE Maui County committee meetings.

Called every 2 minutes by the supervisor tick (or via CLI) during meeting hours. Polls:
  1. The Legistar meeting page for eComment submissions.
  2. Audio segments in reports/_status/meeting_watch/<slug>/audio/ — new .wav files are
     transcribed with faster_whisper (tiny/cpu/int8) and parsed for self-identified testifiers
     using the same high-precision patterns as testimony_watch.py.

Each new testifier is cross-referenced against donor_profiles.json (by name and organization).
Findings are written to reports/_status/testimony_live_feed.json and appended to
reports/_status/testifiers_index.txt.

INTEGRITY: only self-identified speakers are captured, never invented. Strength 4-5 donor-linked
entries are marked public_safe: false and stay private.

Stdlib only + faster_whisper (optional — transcription skipped if unavailable).
CLI: python testimony_realtime.py [--force]   (--force skips the 8am-6pm HST time gate)
"""
import os, re, ssl, json, glob, urllib.request, html
from datetime import datetime, timezone, timedelta

try:
    from faster_whisper import WhisperModel
    _WHISPER_OK = True
except Exception:
    _WHISPER_OK = False

HOME    = os.path.expanduser("~")
PROJECT = os.path.join(HOME, "Documents", "Claude", "Projects", "Video System elementLOTUS")
MAUIOS  = os.path.join(PROJECT, "reports", "mauios")
STATUS  = os.path.join(PROJECT, "reports", "_status")
MTG_DIR = os.path.join(STATUS, "meeting_watch")
DONORS  = os.path.join(MAUIOS, "donor_profiles.json")
FEED    = os.path.join(STATUS, "testimony_live_feed.json")
IDX     = os.path.join(STATUS, "testifiers_index.txt")
LEG     = "https://mauicounty.legistar.com/"
HST     = timezone(timedelta(hours=-10))
UA      = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) 12sgi-kilo"}

# Meeting hours gate (HST)
MTG_START_HR = 8
MTG_END_HR   = 18

# ── shared patterns from testimony_watch.py ─────────────────────────────────────────────────
STAFF_TITLES = re.compile(
    r"\b(Director|Deputy|Corporation Counsel|Planning|Budget Director|"
    r"Administrator|Officer|Department of|Staff|Clerk|Supervising|First Deputy)\b", re.I)
ORG_RE = re.compile(
    r"(?:on behalf of|representing|(?:here )?with the|with|from the|for the|"
    r"president of|director of|executive director of|work for)\s+(?:the\s+)?"
    r"([A-Z][A-Za-zʻ'&.\- ]{3,52}?(?:Association|Assn|Hui|Coalition|Foundation|Council|Union|"
    r"Chamber|Alliance|Society|Partners|Partnership|Group|LLC|L\.L\.C\.|Inc|Company|Corporation|"
    r"Corp|Ltd|Trust|Department|Realtors|Realty|Properties|Bureau|Club|Institute|Fund|Ohana|Board))")
NAME_RE  = re.compile(r"[Mm]y name is\s+([A-Z][A-Za-zʻ'\-]+(?:\s+[A-Z][A-Za-zʻ'\-]+){0,2})")
CLAIM_RE = re.compile(
    r"\b(treble damages|damages|injunction|cease and desist|violation|negligence|"
    r"misappropriation|fraud|class action|settlement|compensation|restitution|"
    r"lawsuit|litigation|complaint|appeal)\b", re.I)
ITEM_RE  = re.compile(r"\b(BFED|PA|LU|HH|TC|ECON|GO|ACC|PSM)-\d+\b|\bBill\s+\d+\b|\bResolution\s+\d+\b", re.I)
SELF_ID  = re.compile(
    r"my name is|i would like to testify|like to testify|i'm here to testify|"
    r"i am here to testify|testifying on behalf|i am testifying|i'm testifying", re.I)
POS_SUPP = re.compile(r"\bin support\b|support of\b|favor of\b", re.I)
POS_OPP  = re.compile(r"\boppos|against\b|urge .* oppose", re.I)


def now_hst():
    return datetime.now(HST)


def _get(url, timeout=30):
    ctx = ssl.create_default_context()
    req = urllib.request.Request(url, headers=UA)
    return urllib.request.urlopen(req, timeout=timeout, context=ctx).read().decode("utf-8", "replace")


def _load_json(path, default):
    try:
        return json.load(open(path, encoding="utf-8"))
    except Exception:
        return default


def _dump_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


# ── 1. find today's active meeting ──────────────────────────────────────────────────────────
def find_active_meeting():
    """Scan meeting_watch/<slug>/meeting.json files for one scheduled today.
    Returns dict with keys: body, date, legid, slug — or None if no match."""
    today = now_hst().date().isoformat()
    if not os.path.isdir(MTG_DIR):
        return None
    for slug_dir in sorted(os.listdir(MTG_DIR)):
        mjson = os.path.join(MTG_DIR, slug_dir, "meeting.json")
        if not os.path.exists(mjson):
            continue
        try:
            m = json.load(open(mjson, encoding="utf-8"))
            # date may be "June 24, 2026" or "2026-06-24"; normalise to ISO
            raw_date = str(m.get("date", ""))
            try:
                parsed = datetime.strptime(raw_date, "%B %d, %Y").date().isoformat()
            except ValueError:
                parsed = raw_date[:10]
            if parsed == today:
                return {
                    "body":  m.get("body", slug_dir),
                    "date":  raw_date,
                    "legid": str(m.get("legid", m.get("id", ""))),
                    "slug":  slug_dir,
                }
        except Exception:
            continue
    return None


# ── 2. eComment scrape ───────────────────────────────────────────────────────────────────────
def _scrape_ecomments(legid):
    """Fetch the Legistar meeting detail page and extract eComment submitter lines.
    Returns list of raw text snippets (best-effort; page format may vary)."""
    url = LEG + "MeetingDetail.aspx?LEGID=" + legid
    try:
        page = _get(url, timeout=40)
    except Exception:
        return []
    # eComment submissions appear as rows in a table classed "rgMasterTable"
    # Each row has a speaker name column. Extract all non-empty cell text.
    rows = re.findall(r'<tr[^>]*>(.*?)</tr>', page, re.S | re.I)
    snippets = []
    for row in rows:
        cells = re.findall(r'<td[^>]*>(.*?)</td>', row, re.S | re.I)
        cells_text = [re.sub(r'<[^>]+>', '', c).strip() for c in cells]
        cells_text = [html.unescape(c) for c in cells_text if c]
        if len(cells_text) >= 2:
            merged = " | ".join(cells_text)
            snippets.append(merged)
    return snippets


def _parse_ecomment_testifier(snippet, timestamp_hst):
    """Try to extract a testifier record from a single eComment table row text."""
    low = snippet.lower()
    if not SELF_ID.search(low) and "public comment" not in low and "testif" not in low:
        # eComment rows may not always contain self-ID phrases; capture if name-like anyway
        # by checking for a name pattern
        if not NAME_RE.search(snippet):
            return None
    nm = NAME_RE.search(snippet)
    name = nm.group(1).strip() if nm else ""
    if not name:
        # fallback: first two Title-cased words
        words = [w for w in snippet.split() if w and w[0].isupper() and len(w) > 1]
        if len(words) >= 2:
            name = " ".join(words[:2])
        else:
            return None
    org_m = ORG_RE.search(snippet)
    org = re.sub(r"\s+", " ", org_m.group(1)).strip(" .") if org_m else ""
    item_m = ITEM_RE.search(snippet)
    item = item_m.group(0).upper() if item_m else ""
    claim_m = CLAIM_RE.search(snippet)
    claim = claim_m.group(1) if claim_m else ""
    pos = ("support" if POS_SUPP.search(snippet)
           else "oppose" if POS_OPP.search(snippet) else "comment")
    return {"name": name, "org": org, "item": item, "position": pos, "claim": claim,
            "timestamp": timestamp_hst, "source": "ecomment"}


# ── 3. audio transcription ───────────────────────────────────────────────────────────────────
_whisper_model = None

def _get_whisper():
    global _whisper_model
    if not _WHISPER_OK:
        return None
    if _whisper_model is None:
        try:
            _whisper_model = WhisperModel("tiny", device="cpu", compute_type="int8")
        except Exception:
            return None
    return _whisper_model


def transcribe_segment(wav_path):
    """Transcribe a .wav segment; returns plain text or empty string."""
    m = _get_whisper()
    if m is None:
        return ""
    try:
        segments, _ = m.transcribe(wav_path, language="en")
        return " ".join(s.text.strip() for s in segments).strip()
    except Exception:
        return ""


def _parse_audio_testifier(text, wav_basename, timestamp_hst):
    """Parse a transcript chunk for self-identified testifiers; same logic as testimony_watch."""
    low = text.lower()
    if not SELF_ID.search(low):
        return None
    if STAFF_TITLES.search(text[:120]) and "my name is" not in low:
        return None
    nm = NAME_RE.search(text)
    name = nm.group(1).strip() if nm else ""
    if not name:
        # label fallback: can't identify speaker
        return None
    org_m = ORG_RE.search(text)
    org = re.sub(r"\s+", " ", org_m.group(1)).strip(" .") if org_m else ""
    item_m = ITEM_RE.search(text)
    item = item_m.group(0).upper() if item_m else ""
    claim_m = CLAIM_RE.search(text)
    claim = claim_m.group(1) if claim_m else ""
    pos = ("support" if POS_SUPP.search(text)
           else "oppose" if POS_OPP.search(text) else "comment")
    return {"name": name, "org": org, "item": item, "position": pos, "claim": claim,
            "timestamp": timestamp_hst, "source": "audio_transcript",
            "_wav": wav_basename}


# ── 4. donor cross-reference ─────────────────────────────────────────────────────────────────
_donor_cache = None

def _donors():
    global _donor_cache
    if _donor_cache is None:
        _donor_cache = _load_json(DONORS, [])
    return _donor_cache


def _name_tokens(s):
    return set(re.findall(r"[A-Za-zʻ']{2,}", s.lower()))


def donor_cross_ref(name, org):
    """Check name and org against donor_profiles.json. Returns (flagged, detail_str)."""
    profiles = _donors()
    if not profiles:
        return False, ""
    name_tok = _name_tokens(name)
    org_tok  = _name_tokens(org) if org else set()
    for profile in profiles:
        # profile keys: key, label, rows, total, candidate_names, realestate.donors[]
        cand_label = profile.get("label", "")
        rows_total  = profile.get("total", 0)
        # scan individual donor rows
        for bucket_key in ("realestate",):
            bucket = profile.get(bucket_key) or {}
            for donor in bucket.get("donors", []):
                dname = donor.get("name", "")
                damt  = donor.get("amount", 0)
                dtok  = _name_tokens(dname)
                # name overlap (at least 2 tokens match) or org overlap
                name_hit = len(name_tok & dtok) >= 2 if len(name_tok) >= 2 else name_tok == dtok
                org_hit  = (len(org_tok) >= 2 and len(org_tok & dtok) >= 2)
                if name_hit or org_hit:
                    candidate = re.match(r"([^(]+)", cand_label)
                    cand_name = candidate.group(1).strip() if candidate else cand_label
                    detail = "%s gave $%.0f to %s" % (dname, damt, cand_name)
                    return True, detail
        # also scan top-level candidate_names for name/org in label
        label_low = cand_label.lower()
        if name_tok and any(tok in label_low for tok in name_tok if len(tok) > 3):
            detail = "appears in donor record for %s (total $%.0f)" % (
                cand_label.split("(")[0].strip(), rows_total)
            return True, detail
    return False, ""


# ── 5. strength scoring ──────────────────────────────────────────────────────────────────────
def score_strength(t):
    """Score a testifier record 1-5. 4-5 = private."""
    s = 1
    if t.get("donor_flag"):
        s += 2
    if t.get("org"):
        s += 1
    if t.get("claim"):
        s += 1
    if t.get("position") == "oppose":
        s = min(s + 1, 5)
    return min(s, 5)


# ── 6. main monitor ──────────────────────────────────────────────────────────────────────────
def run(force=False):
    hst_now = now_hst()
    ts_label = hst_now.strftime("%Y-%m-%d %H:%M HST")

    # Time-of-day gate
    if not force:
        if not (MTG_START_HR <= hst_now.hour < MTG_END_HR):
            # Outside meeting hours — write or preserve feed with active=false
            feed = _load_json(FEED, {})
            if not feed.get("meeting_active"):
                # Already false, nothing to do
                return
            feed["meeting_active"] = False
            feed["updated"] = ts_label
            feed["meeting"] = {}
            _dump_json(FEED, feed)
            return

    # Find today's active meeting
    meeting = find_active_meeting()
    if meeting is None:
        _dump_json(FEED, {
            "updated": ts_label, "meeting_active": False, "meeting": {},
            "testifiers": [], "alerts": []
        })
        return

    # Load existing feed to track already-seen items
    feed = _load_json(FEED, {
        "updated": ts_label, "meeting_active": True, "meeting": meeting,
        "testifiers": [], "alerts": [], "_seen_wavs": [], "_seen_ecomment_names": []
    })
    seen_wavs    = set(feed.get("_seen_wavs", []))
    seen_ecomm   = set(feed.get("_seen_ecomment_names", []))
    testifiers   = list(feed.get("testifiers", []))
    new_items    = []

    # ── A. eComment scrape ──────────────────────────────────────────────────────
    legid = meeting.get("legid", "")
    if legid:
        snippets = _scrape_ecomments(legid)
        for snip in snippets:
            t = _parse_ecomment_testifier(snip, hst_now.strftime("%H:%M HST"))
            if t is None:
                continue
            key = (t["name"] + "|" + t.get("item", "")).lower()
            if key in seen_ecomm:
                continue
            seen_ecomm.add(key)
            flagged, detail = donor_cross_ref(t["name"], t.get("org", ""))
            t["donor_flag"]   = flagged
            t["donor_detail"] = detail
            t["strength"]     = score_strength(t)
            t["public_safe"]  = not (flagged and t["strength"] >= 4)
            new_items.append(t)

    # ── B. audio segment scan ───────────────────────────────────────────────────
    slug = meeting.get("slug", "")
    audio_dir = os.path.join(MTG_DIR, slug, "audio") if slug else ""
    if audio_dir and os.path.isdir(audio_dir):
        wavs = sorted(glob.glob(os.path.join(audio_dir, "*.wav")))
        for wav in wavs:
            basename = os.path.basename(wav)
            if basename in seen_wavs:
                continue
            seen_wavs.add(basename)
            text = transcribe_segment(wav)
            if not text:
                continue
            # A single .wav may contain multiple speakers; split on silence markers or
            # just process the whole chunk for self-ID patterns
            t = _parse_audio_testifier(text, basename, hst_now.strftime("%H:%M HST"))
            if t is None:
                continue
            flagged, detail = donor_cross_ref(t["name"], t.get("org", ""))
            t["donor_flag"]   = flagged
            t["donor_detail"] = detail
            t["strength"]     = score_strength(t)
            t["public_safe"]  = not (flagged and t["strength"] >= 4)
            new_items.append(t)

    # Merge new items into testifiers list (dedup by name+item)
    existing_keys = set(
        (x["name"] + "|" + x.get("item", "")).lower() for x in testifiers
    )
    for t in new_items:
        key = (t["name"] + "|" + t.get("item", "")).lower()
        if key not in existing_keys:
            testifiers.append(t)
            existing_keys.add(key)

    # Build alerts
    alerts = []
    for t in testifiers:
        if t.get("donor_flag") and t.get("item"):
            alerts.append({
                "level": "red",
                "msg": "Testifier with donor connections on %s" % t["item"]
            })
        elif t.get("org") and t.get("item"):
            alerts.append({
                "level": "orange",
                "msg": "Organizational testifier (%s) on %s" % (t["org"], t["item"])
            })

    # Deduplicate alerts
    seen_alert_msgs = set()
    deduped_alerts = []
    for a in alerts:
        if a["msg"] not in seen_alert_msgs:
            deduped_alerts.append(a)
            seen_alert_msgs.add(a["msg"])

    feed_out = {
        "updated":        ts_label,
        "meeting_active": True,
        "meeting":        meeting,
        "testifiers":     testifiers,
        "alerts":         deduped_alerts,
        "_seen_wavs":     sorted(seen_wavs),
        "_seen_ecomment_names": sorted(seen_ecomm),
    }
    _dump_json(FEED, feed_out)

    # ── C. append new testifiers to index ──────────────────────────────────────
    if new_items:
        os.makedirs(os.path.dirname(IDX), exist_ok=True)
        with open(IDX, "a", encoding="utf-8") as f:
            for t in new_items:
                flags = "donor" if t.get("donor_flag") else ""
                flag_str = ("flags:" + flags) if flags else ""
                items_str = ("items:" + t["item"]) if t.get("item") else ""
                parts = [t["name"], "x1"]
                if items_str: parts.append(items_str)
                if flag_str:  parts.append(flag_str)
                f.write("  ".join(parts) + "\n")

    print("testimony_realtime: %s | meeting=%s | new=%d | total=%d | alerts=%d" % (
        ts_label, meeting.get("body", "?"), len(new_items), len(testifiers), len(deduped_alerts)))


def main():
    import argparse
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--force", action="store_true",
                    help="Skip the 8am-6pm HST time gate (run even outside meeting hours)")
    a = ap.parse_args()
    run(force=a.force)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
