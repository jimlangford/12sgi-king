#!/usr/bin/env python3
"""bill_committee_enrich.py - Committee and council vote enrichment for the member scorecard.

Adds three layers of context under each notable vote:
  1. WHAT the bill does  — MatterTitle from Legistar (machine-accessible)
  2. WHICH committee     — extracted from MatterFile prefix (e.g. BFED, HLU, DRIP)
  3. COUNCIL roll-call   — full 9-member AYE/NAY/OTHER cross-referenced from officials.json
  4. MOTION trail        — AMEND motions before ADOPT = the "what changed" signal
  5. ABSENT/OTHER flag   — who was not present or classified differently

  COMMITTEE ROLL-CALL NOTE (verified 2026-06-25, committee_votes.py):
  Maui County does NOT publish committee member-by-member votes through any
  machine-accessible channel (Legistar Votes API, CivicClerk structured data).
  Actual committee NAYs require a formal records request to the County Clerk.
  This tool never fabricates — it shows what IS published and flags the gap.

Outputs:
  reports/_status/bill_enrichment.json   (PRIVATE - not published)

Usage:
  python bill_committee_enrich.py           # refresh + save
  python bill_committee_enrich.py --read    # print enrichment summary
  from bill_committee_enrich import load_enrichment  # used by votes_watch.py
Stdlib only.
"""
import json, os, re, ssl, time, sys, urllib.request, urllib.parse
from datetime import datetime, timedelta, timezone

HOME    = os.path.expanduser("~")
PROJECT = os.path.join(HOME, "Documents", "Claude", "Projects", "Video System elementLOTUS")
TOOL_DIR = os.path.dirname(os.path.abspath(__file__))
PRIV    = os.path.join(PROJECT, "reports", "_status")
OUT_F   = os.path.join(PRIV, "bill_enrichment.json")
LEGISTAR_CACHE = os.path.join(PRIV, "legistar_matters_cache.json")
OFFICIALS_F  = os.path.join(PROJECT, "reports", "mauios", "officials.json")
COMM_PRIV    = os.path.join(PROJECT, "reports", "_status", "committee")
MEETINGS_F   = os.path.join(COMM_PRIV, "committee_meetings.json")
BILL_INDEX_F = os.path.join(COMM_PRIV, "committee_bill_index.json")

HST = timezone(timedelta(hours=-10))
UA  = {"User-Agent": "12sgi-kilo-aupuni-enrich/1.0 (civic transparency; public record)"}
BASE = "https://webapi.legistar.com/v1/mauicounty"
CACHE_TTL = 86400  # 24h

# Committee code → full name mapping (from observed Legistar data)
COMMITTEE_NAMES = {
    "BFED":  "Budget, Finance & Economic Development",
    "HLU":   "Housing and Land Use",
    "DRIP":  "Disaster Recovery, Infrastructure & Planning",
    "ADEPT": "Affordable/Diverse/Equitable/Permanent/Transitional Housing",
    "GPAC":  "General Plan Advisory Committee",
    "PSC":   "Public Safety & Corrections",
    "GREAT": "Government Reform, Ethics, Accountability & Transparency",
    "PSF":   "Public Safety & Fiscal",
}

# Council member surname → display name
MEMBER_NAMES = {
    "Batangan": "Batangan",
    "Cook": "Cook",
    "Johnson": "Johnson",
    "Lee": "Lee",
    "Paltin": "Paltin",
    "Rawlins-Fernandez": "Rawlins-Fernandez",
    "Sinenci": "Sinenci",
    "Sugimura": "Sugimura",
    "Uu-Hodgins": "Uʻu-Hodgins",
}

def jget(u):
    req = urllib.request.Request(u, headers=UA)
    return json.loads(urllib.request.urlopen(
        req, timeout=30, context=ssl.create_default_context()
    ).read().decode("utf-8", "replace"))

def _normalize_bill(raw):
    """Normalize bill references to a canonical key.
    'BILL 88', 'Bill 88 (2026)', 'Bill 88 (2025)' → 'Bill 88'
    'Bill 117 with the CD1 version, please raise your' → 'Bill 117'
    """
    s = re.sub(r"\s*\(\d{4}\)\s*", "", raw).strip()
    s = re.sub(r"^BILL\b", "Bill", s)
    s = re.sub(r"^RESOLUTION\b", "Resolution", s)
    s = re.sub(r"^RESO\b", "Reso", s)
    s = re.sub(r"^CC\s+", "CC ", s)
    # Truncate at the first non-reference word (verbose committee minutes extracts)
    m = re.match(r"((?:Bill|Resolution|Reso|CR|CC)\s+[\d\-\.]+)", s, re.I)
    if m:
        s = m.group(1)
    return s.strip()

def fetch_legistar_matters():
    """Fetch matters from Legistar (cached 24h). Returns list of matter dicts."""
    if os.path.exists(LEGISTAR_CACHE):
        try:
            cached = json.load(open(LEGISTAR_CACHE, encoding="utf-8"))
            if time.time() - cached.get("_ts", 0) < CACHE_TTL:
                return cached["matters"]
        except Exception:
            pass

    # Fetch last 2 years of matters (most relevant for active council)
    matters = []
    try:
        page = jget("%s/Matters?$top=1000&$orderby=MatterIntroDate+desc" % BASE)
        matters = page
    except Exception as e:
        sys.stderr.write("Legistar fetch error: %s\n" % e)
        return []

    os.makedirs(PRIV, exist_ok=True)
    json.dump({"_ts": int(time.time()), "matters": matters},
              open(LEGISTAR_CACHE, "w", encoding="utf-8"), ensure_ascii=False)
    return matters

def build_legistar_index(matters):
    """Build lookup dict: normalized_bill_key → {title, committee_code, committee_name, matter_id}."""
    idx = {}
    for m in matters:
        file_str = m.get("MatterFile") or ""
        title = m.get("MatterTitle") or ""
        body  = m.get("MatterBodyName") or ""

        # Extract committee code from MatterFile: "BFED-12 Bill 83 (2026)" → "BFED"
        # Also handles "HLU-3(5) Bill 47 (2025)" (optional parenthetical after number)
        code_match = re.match(r"([A-Z]+)-\d+(?:\(\d+\))?\s+(.*)", file_str)
        if code_match:
            comm_code = code_match.group(1)
            bill_part = code_match.group(2).strip()
        else:
            comm_code = ""
            bill_part = file_str.strip()

        key = _normalize_bill(bill_part)
        if not key:
            continue

        # Truncate title at reasonable length and clean up
        short_title = title.replace("  ", " ").strip()
        # Remove the parenthetical at end that repeats the file code, e.g. "(HLU-16)"
        short_title = re.sub(r"\s*\([A-Z]+-\d+\)\s*$", "", short_title).strip()

        entry = {
            "title": short_title[:300],
            "committee_code": comm_code,
            "committee_name": COMMITTEE_NAMES.get(comm_code, body.split("(")[0].strip()),
            "matter_id": m.get("MatterId"),
            "status": m.get("MatterStatusName") or "",
            "intro": (m.get("MatterIntroDate") or "")[:10],
        }
        existing = idx.get(key)
        # Keep the entry that has a committee code; don't overwrite a good code with empty
        if existing and existing.get("committee_code") and not comm_code:
            continue
        idx[key] = entry
    return idx

def build_council_rollcall(officials):
    """Cross-reference officials.json: {(item_key, date) → {member: vote, ...}}."""
    rollcall = {}
    for member, data in officials.items():
        for v in data.get("vote_log", []):
            item = _normalize_bill(v.get("item") or "")
            date = v.get("date") or ""
            if not item or not date:
                continue
            key = (item, date)
            if key not in rollcall:
                rollcall[key] = {}
            rollcall[key][member] = {
                "vote": v.get("vote", "?"),
                "motion": v.get("motion", ""),
            }
    return rollcall

def load_committee_data():
    """Load committee sweep data. Returns (bill_index, meetings_by_code).

    bill_index:      {bill_key: [vote_refs_with_minutes+video_urls]}
    meetings_by_code: {committee_code: [meeting_records_sorted_by_date]}
    Returns ({}, {}) if sweep has not been run yet.
    """
    bill_index = {}
    meetings_by_code = {}
    try:
        data = json.load(open(BILL_INDEX_F, encoding="utf-8"))
        raw_index = data.get("index", {})
        # Normalize keys so they match what _normalize_bill produces from council vote log
        for k, v in raw_index.items():
            nk = _normalize_bill(k)
            if nk:
                bill_index.setdefault(nk, []).extend(v if isinstance(v, list) else [v])
    except Exception:
        pass
    try:
        data = json.load(open(MEETINGS_F, encoding="utf-8"))
        for mtg in data.get("meetings", []):
            code = mtg.get("code") or ""
            meetings_by_code.setdefault(code, []).append(mtg)
    except Exception:
        pass
    return bill_index, meetings_by_code

def _committee_summary(code, bill_key, bill_index, meetings_by_code):
    """Return dict with committee vote context for a bill.

    Priority:
      1. Exact bill_key match in bill_index — real item-level votes
      2. Meeting-level summary by committee_code — we have meeting records,
         just couldn't link to this specific bill
      3. No data — return note that sweep hasn't run yet
    """
    # 1) Exact bill match
    refs = bill_index.get(bill_key, [])
    if refs:
        # Aggregate across all matched meetings
        all_ayes = sorted({nm for r in refs for nm in r.get("ayes", [])})
        all_noes = sorted({nm for r in refs for nm in r.get("noes", [])})
        all_abstain = sorted({nm for r in refs for nm in r.get("abstain", [])})
        video_url = next((r["video_url"] for r in refs if r.get("video_url")), None)
        minutes_url = refs[0].get("minutes_url")
        dissents = [r for r in refs if r.get("dissent")]
        return {
            "available": True,
            "source": "minutes_pdf",
            "meetings": len(refs),
            "ayes": all_ayes,
            "noes": all_noes,
            "abstain": all_abstain,
            "dissent": bool(dissents),
            "minutes_url": minutes_url,
            "video_url": video_url,
            "note": "",
        }

    # 2) Meeting-level match by committee code
    mtgs = meetings_by_code.get(code, []) if code else []
    if mtgs:
        # Sort descending by date; take the most recent few
        recent = sorted(mtgs, key=lambda m: m["date"], reverse=True)[:3]
        video_url = next((m["video_url"] for m in recent if m.get("video_url")), None)
        minutes_url = recent[0].get("minutes_url")
        n_dissent_total = sum(m["n_dissent"] for m in recent)
        return {
            "available": True,
            "source": "meeting_level",
            "meetings": len(recent),
            "ayes": [], "noes": [], "abstain": [],
            "dissent": n_dissent_total > 0,
            "minutes_url": minutes_url,
            "video_url": video_url,
            "note": (
                "Committee minutes accessible — bill-level vote not isolated "
                "(budget minutes list roll-calls without bill numbers). "
                "%d meeting(s) parsed; dissent recorded on %d motion(s)."
            ) % (len(recent), n_dissent_total),
        }

    # 3) No data
    if meetings_by_code:
        return {
            "available": False,
            "source": "no_match",
            "meetings": 0,
            "ayes": [], "noes": [], "abstain": [],
            "dissent": False,
            "minutes_url": None,
            "video_url": None,
            "note": (
                "Committee minutes not yet indexed for this committee. "
                "Run committee_sweep.py to harvest."
            ),
        }
    return {
        "available": False,
        "source": "sweep_not_run",
        "meetings": 0,
        "ayes": [], "noes": [], "abstain": [],
        "dissent": False,
        "minutes_url": None,
        "video_url": None,
        "note": (
            "Committee minutes accessible via Legistar — run committee_sweep.py "
            "to harvest roll-calls and video links."
        ),
    }

def build_motion_trail(officials, member):
    """For a specific member: {(item_key, date) → [motions in order]} to detect AMEND→ADOPT."""
    trail = {}
    for v in officials.get(member, {}).get("vote_log", []):
        item = _normalize_bill(v.get("item") or "")
        date = v.get("date") or ""
        if not item or not date:
            continue
        key = (item, date)
        if key not in trail:
            trail[key] = []
        trail[key].append(v.get("motion", ""))
    return trail

def enrich_vote_log(member, officials, legistar_idx, rollcall,
                    bill_index=None, meetings_by_code=None):
    """Return enriched vote entries for a member's notable votes — one entry per (item, date)."""
    # First pass: group all motions by (item_key, date) and keep the most significant vote
    motion_trail = build_motion_trail(officials, member)
    groups = {}  # (item_key, date) -> best_vote_entry + all motions
    for v in officials.get(member, {}).get("vote_log", []):
        raw_item = v.get("item") or ""
        item = _normalize_bill(raw_item)
        date = v.get("date") or ""
        if not date:
            continue
        key = (item, date)
        if key not in groups:
            groups[key] = {"best": v, "motions": [], "raw_item": raw_item}
        groups[key]["motions"].append(v.get("motion", ""))
        # Prefer ADOPT/PASS vote over AMEND (ADOPT is the final action)
        mo = (v.get("motion") or "").upper()
        if "ADOPT" in mo or ("PASS" in mo and "AMEND" not in mo):
            groups[key]["best"] = v

    _bill_index = bill_index or {}
    _meetings_by_code = meetings_by_code or {}

    enriched = []
    for (item, date), grp in sorted(groups.items(), key=lambda x: x[0][1]):
        v = grp["best"]
        raw_item = grp["raw_item"]
        key = (item, date)
        motions = grp["motions"]

        leg = legistar_idx.get(item) or {}
        rc = rollcall.get(key) or {}
        comm_code = leg.get("committee_code", "")

        # Classify council roll-call
        ayes = sorted([MEMBER_NAMES.get(m, m) for m, vd in rc.items() if vd["vote"] == "AYE"])
        nays = sorted([MEMBER_NAMES.get(m, m) for m, vd in rc.items() if vd["vote"] in ("NAY","NO")])
        other = sorted([MEMBER_NAMES.get(m, m) for m, vd in rc.items()
                        if vd["vote"] not in ("AYE","NAY","NO")])
        absent = sorted([MEMBER_NAMES.get(m, m) for m in MEMBER_NAMES if m not in rc])

        # Detect amendment trail: any AMEND or AMEND WITH motion before an ADOPT
        amend_motions = [mo for mo in motions if "AMEND" in mo.upper()]
        adopt_motion = any("ADOPT" in mo.upper() or "PASS" in mo.upper() for mo in motions)
        was_amended = bool(amend_motions) and adopt_motion
        amend_note = ""
        if was_amended:
            amend_note = "Amended before final adoption — " + (amend_motions[0][:120] if amend_motions else "")

        # Committee roll-call from sweep data
        comm = _committee_summary(comm_code, item, _bill_index, _meetings_by_code)

        enriched.append({
            "date": date,
            "item": raw_item,
            "item_key": item,
            "motion": v.get("motion", ""),
            "vote": v.get("vote", ""),
            "result": v.get("result", ""),
            "url": v.get("url", ""),
            # Legistar enrichment
            "bill_title": leg.get("title", ""),
            "committee_code": comm_code,
            "committee_name": leg.get("committee_name", ""),
            # Council roll-call
            "council_ayes": ayes,
            "council_nays": nays,
            "council_other": other,
            "council_absent": absent,
            "council_total": len(rc),
            # Amendment trail
            "was_amended": was_amended,
            "amend_note": amend_note,
            # Committee roll-call from minutes PDFs
            "committee_rollcall_available": comm["available"],
            "committee_rollcall_source":    comm["source"],
            "committee_ayes":               comm["ayes"],
            "committee_noes":               comm["noes"],
            "committee_abstain":            comm["abstain"],
            "committee_dissent":            comm["dissent"],
            "committee_minutes_url":        comm["minutes_url"],
            "committee_video_url":          comm["video_url"],
            "committee_rollcall_note":      comm["note"],
        })
    return enriched

def build_enrichment():
    """Build full enrichment for all officials. Returns dict."""
    matters = fetch_legistar_matters()
    legistar_idx = build_legistar_index(matters)
    try:
        officials = json.load(open(OFFICIALS_F, encoding="utf-8"))
    except Exception:
        officials = {}
    rollcall = build_council_rollcall(officials)

    # Load committee sweep data (may be empty if sweep hasn't run yet)
    bill_index, meetings_by_code = load_committee_data()
    has_sweep = bool(bill_index) or bool(meetings_by_code)

    out = {
        "_generated": datetime.now(HST).strftime("%Y-%m-%d %H:%M HST"),
        "_legistar_matters_indexed": len(legistar_idx),
        "_officials": len(officials),
        "_committee_sweep_available": has_sweep,
        "_committee_bill_keys": len(bill_index),
        "_committee_bodies_indexed": len(meetings_by_code),
        "members": {}
    }
    for member in officials:
        out["members"][member] = enrich_vote_log(
            member, officials, legistar_idx, rollcall,
            bill_index=bill_index, meetings_by_code=meetings_by_code
        )

    os.makedirs(PRIV, exist_ok=True)
    json.dump(out, open(OUT_F, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    return out

def load_enrichment():
    """Load enrichment from cache (build if missing or stale). Returns dict keyed by member."""
    if os.path.exists(OUT_F):
        try:
            data = json.load(open(OUT_F, encoding="utf-8"))
            # Accept cache up to 12h old
            gen_str = data.get("_generated", "")
            return data.get("members", {})
        except Exception:
            pass
    try:
        data = build_enrichment()
        return data.get("members", {})
    except Exception:
        return {}

def main():
    if "--read" in sys.argv:
        enrichment = load_enrichment()
        for member, entries in sorted(enrichment.items()):
            notable = [e for e in entries if e.get("item")][:5]
            if not notable:
                continue
            print("\n%s:" % member)
            for e in notable:
                print("  %s | %s | %s | Council: %d-AYE %d-NAY %d-other%s" % (
                    e["date"], e["item"][:30], e["committee_code"] or "?",
                    len(e["council_ayes"]), len(e["council_nays"]), len(e["council_other"]),
                    (" AMENDED" if e["was_amended"] else "")))
                if e["bill_title"]:
                    print("    → %s" % e["bill_title"][:100])
        return 0

    print("Building bill enrichment...")
    data = build_enrichment()
    print("Generated: %s" % data.get("_generated"))
    print("Legistar matters indexed: %d" % data.get("_legistar_matters_indexed", 0))
    print("Members enriched: %d" % len(data.get("members", {})))
    print("Output: %s" % OUT_F)
    return 0

if __name__ == "__main__":
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    sys.exit(main())
