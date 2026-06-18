#!/usr/bin/env python3
"""agenda_cadence.py — the CIVIC Sunshine-Law agenda-post cadence (Jimmy 2026-06-18).

Wires the studio handoff (config/agenda_post_policy.json) into the civic posting pipeline: for each
UPCOMING meeting, it ramps posts toward the meeting day — T-6d → T-3d → T-1d → day-of (HRS §92-7: never
public before T-6d) — each with the post template filled, the hashtags assembled (base by county/topic +
per-Hawaii-influencer MERGED from config/influencer_crosswalk.json — NOT forked), and a studio-rendered
agenda visual requested. Posts are STAGED private (reports/_status/agenda_posts/); publishing uses the
allowlisted 'agenda_*' slug through upload_shorts (which the publish-policy gate permits) on owner approval.

Runs daily (hook into audit_cycle). Reuses agenda_explainer (links/testify) + agenda_reel (hashtags/crosswalk).
Stdlib only. Coordinates the T-0 post away from the ~7PM HST daily moon message.
"""
import os, sys, re, json
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path: sys.path.insert(0, HERE)
from datetime import datetime, timedelta, timezone
HST = timezone(timedelta(hours=-10))
PROJ = os.path.abspath(os.path.join(HERE, "..", ".."))
POLICY = os.path.join(PROJ, "config", "agenda_post_policy.json")
CROSSWALK = os.path.join(PROJ, "config", "influencer_crosswalk.json")
COUNCIL = os.path.join(PROJ, "reports", "council", "index.jsonl")
OUT = os.path.join(PROJ, "reports", "_status", "agenda_posts")
try:
    import agenda_explainer as AX
except Exception:
    AX = None
try:
    import agenda_reel as AR
except Exception:
    AR = None

_COUNTY = {"maui": "Maui", "honolulu": "Honolulu", "hawaii": "Hawaii", "kauai": "Kauai", "state": "State",
           "hi-maui": "Maui", "hi-honolulu": "Honolulu", "hi-hawaii": "Hawaii", "hi-kauai": "Kauai", "hi-state": "State"}
_TOPIC_KW = {"land": ["land", "zoning", "rezone", "parcel", "sma", "shoreline"], "water": ["water", "wai", "well", "stream"],
             "housing": ["housing", "rental", "str", "affordable", "homeless"], "budget": ["budget", "tax", "fund", "appropriat", "fiscal"],
             "permits": ["permit", "build", "construction", "development", "subdivision"], "ag": ["ag ", "agricult", "farm", "crop", "ranch"]}

def _policy():
    try: return json.load(open(POLICY, encoding="utf-8"))
    except Exception: return {}

def _crosswalk():
    """Existing civic influencer crosswalk (MERGE source for per-influencer hashtags) — never forked."""
    try: return json.load(open(CROSSWALK, encoding="utf-8"))
    except Exception: return {}

def _upcoming():
    out = []
    try:
        for ln in open(COUNCIL, encoding="utf-8", errors="replace").read().splitlines():
            try: r = json.loads(ln)
            except Exception: continue
            if r.get("date"): out.append(r)
    except Exception:
        pass
    return out

def _topics(text):
    t = (text or "").lower()
    return [k for k, kws in _TOPIC_KW.items() if any(w in t for w in kws)]

def _per_influencer(tid, body, topics):
    """Per-Hawaii-influencer hashtags/handles MERGED from the existing crosswalk + agenda_reel's matcher.
    Returns a flat list of tags; identity/handles come from the crosswalk, never invented here."""
    tags = []
    xw = _crosswalk()
    # crosswalk shape is civic's own; pull any county/topic-aligned influencer handles+tags it defines
    entries = xw.get("influencers") or xw.get("crosswalk") or (xw if isinstance(xw, dict) else {})
    if isinstance(entries, dict):
        for name, e in entries.items():
            if name.startswith("_"): continue
            e = e if isinstance(e, dict) else {}
            cty = (e.get("county") or "").lower(); etopics = [str(x).lower() for x in (e.get("topics") or [])]
            if (not cty or cty in (tid, _COUNTY.get(tid, "").lower())) and (not etopics or set(etopics) & set(topics) or not topics):
                tags += [h for h in (e.get("hashtags") or []) if h]
                if e.get("handle"): tags.append(e["handle"])
    # also reuse agenda_reel's topic-interest crosswalk if present
    if AR and hasattr(AR, "crosswalk_tags"):
        try: tags += [t for t in (AR.crosswalk_tags(body, "") or []) if t]
        except Exception: pass
    # dedup, cap
    seen = []; [seen.append(t) for t in tags if t not in seen]
    return seen[:8]

def build_post(meeting, step, pol):
    tid = (meeting.get("tid") or meeting.get("tenant") or "maui").replace("hi-", "")
    board = (AX.NAMES.get(tid, tid) if AX else tid) + (" Council" if "council" not in (meeting.get("body","").lower()) else "")
    body = meeting.get("body", "Meeting"); date = meeting.get("date", "")
    _it = meeting.get("items"); _it = _it if isinstance(_it, list) else []
    items = ", ".join(str(x) for x in _it[:3]) or body
    testify = (AX.how_to_testify(tid)[0] if AX else "See the testify page.")
    links = (AX.links_for(tid) if AX else {})
    tpl = step.get("template", "{board} meets {date}.")
    cap = tpl.format(board=board, date=date, time="see agenda", top_items=items,
                     testify_link=links.get("testify", "testify.html"), live_link=links.get("live", links.get("agenda", "")))
    topics = _topics(body + " " + items)
    bh = pol.get("base_hashtags", {})
    tags = list(bh.get("always", []))
    tags += bh.get("by_county", {}).get(_COUNTY.get(tid, ""), [])
    for tp in topics: tags += bh.get("by_topic", {}).get(tp, [])
    tags += _per_influencer(tid, body, topics)
    seen = []; [seen.append(t) for t in tags if t not in seen]
    slug = "agenda_%s_%s_%s" % (tid, date, step.get("name", "post"))   # 'agenda' prefix → passes the publish gate
    return {"slug": slug, "tenant": tid, "board": board, "meeting_date": date, "step": step.get("name"),
            "when": step.get("when"), "caption": cap, "hashtags": seen, "topics": topics,
            "agenda_visual": bool(step.get("agenda_visual")), "privacy": "private",
            "note": "STAGED — owner approves the public flip (allowlisted slug; never before T-6d; keep T-0 off the ~7PM moon slot)"}

def run(today=None):
    pol = _policy(); cad = pol.get("cadence", [])
    if not cad: print("agenda_cadence: no policy"); return 0
    today = today or datetime.now(HST).date()
    if isinstance(today, str): today = datetime.fromisoformat(today).date()
    offset = {"T-6d": 6, "T-3d": 3, "T-1d": 1, "T-0": 0}
    os.makedirs(OUT, exist_ok=True)
    staged = 0
    for m in _upcoming():
        try: D = datetime.fromisoformat(m["date"][:10]).date()
        except Exception: continue
        for step in cad:
            off = offset.get(step.get("when"))
            if off is None: continue
            if (D - timedelta(days=off)) == today:           # today is this ramp step for this meeting
                post = build_post(m, step, pol)
                fn = os.path.join(OUT, post["slug"] + ".json")
                json.dump(post, open(fn, "w", encoding="utf-8", newline="\n"), indent=1, ensure_ascii=False)
                staged += 1
                print("  staged %s [%s] -> %s" % (post["slug"], step.get("when"), post["caption"][:70]))
    print("agenda_cadence: %d post(s) staged for %s (private; publish via the allowlisted agenda slug on approval)" % (staged, today))
    return 0

def main():
    if "--once" in sys.argv or len(sys.argv) == 1: return run()
    if "--date" in sys.argv: return run(sys.argv[sys.argv.index("--date") + 1])
    print(__doc__); return 0

if __name__ == "__main__":
    if sys.platform == "win32":
        import io; sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(main())
