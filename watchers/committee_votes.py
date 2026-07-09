#!/usr/bin/env python3
# committee_votes.py - BFED (Budget, Finance & Economic Development) committee decision spine + the
#   dissent-data REALITY (Jimmy 2026-06-16 "yes BFED": see what members vote NO on + the changes that
#   flipped them to YES, then how the money speaks). GROUNDED FINDING (verified this build):
#     Maui does NOT publish committee ROLL-CALL VOTES anywhere machine-accessible:
#       - CivicClerk has no standing committee events (full Council only)
#       - Legistar EventMinutesFile = empty for all 170+ Final BFED meetings
#       - Legistar Votes API (EventItems/Votes) returns 0 vote rows for Maui
#       - the Legistar InSite meeting page exposes only the AGENDA (View.ashx?M=A), no minutes link
#     => the NAYs require a formal RECORDS REQUEST to the County Clerk (flagged below), OR appear only
#        inside committee minutes the county hasn't posted. We NEVER fabricate a vote.
#   What IS accessible (and built here): the committee DECISION UNIVERSE via Legistar EventItems —
#   each meeting's matters, incl. the CD (Committee Draft) version bumps that ARE the "change to flip"
#   signal. This is the private spine the prosecutorial engine crosses with money; votes slot in if/when
#   the county publishes them or a records request returns them. Stdlib only.
import os, sys, json, ssl, urllib.request, urllib.parse, re
from datetime import datetime, timedelta, timezone

HOME = os.path.expanduser("~")
PROJECT = os.path.join(HOME, "Documents", "Claude", "Projects", "Video System elementLOTUS")
PRIV = os.path.join(PROJECT, "reports", "_status", "committee")
HST = timezone(timedelta(hours=-10))
UA = {"User-Agent": "12sgi-kilo-aupuni-committee/1.0 (civic transparency; public record)"}
CLIENT = "mauicounty"
BASE = "https://webapi.legistar.com/v1/%s" % CLIENT

def jget(u):
    return json.loads(urllib.request.urlopen(urllib.request.Request(u, headers=UA),
                      timeout=60, context=ssl.create_default_context()).read().decode("utf-8", "replace"))

def events(body_substr, top=400):
    qs = urllib.parse.urlencode({"$orderby": "EventDate desc", "$top": str(top)})
    rows = jget("%s/Events?%s" % (BASE, qs))
    return [r for r in rows if body_substr.lower() in (r.get("EventBodyName") or "").lower()]

CD_RE = re.compile(r"\b(CD\d|SD\d|HD\d|PROPOSED|DRAFT\s*\d|AS\s+AMENDED)\b", re.I)

def harvest_bfed(limit_meetings=60):
    evs = [e for e in events("budget") if e.get("EventMinutesStatusName") == "Final"]
    meetings, matters_total, amended = [], 0, 0
    votes_found = 0
    for e in evs[:limit_meetings]:
        eid = e.get("EventId")
        try:
            items = jget("%s/Events/%s/EventItems?$top=300" % (BASE, eid))
        except Exception:
            items = []
        matters = []
        for it in items:
            if not it.get("EventItemMatterId"):
                continue
            name = (it.get("EventItemTitle") or it.get("EventItemMatterName") or "").strip()
            cd = bool(CD_RE.search(name))
            if cd: amended += 1
            # probe the structured vote API (confirmed empty for Maui, but check so it self-heals if they enable it)
            roll = []
            try:
                vs = jget("%s/EventItems/%s/Votes" % (BASE, it.get("EventItemId")))
                roll = [{"member": v.get("VotePersonName"), "vote": v.get("VoteValueName")} for v in vs]
            except Exception:
                roll = []
            if roll: votes_found += 1
            matters.append({"matter": name[:160], "matter_id": it.get("EventItemMatterId"),
                            "draft_revision": cd, "action": it.get("EventItemActionName"),
                            "passed": it.get("EventItemPassedFlagName"), "roll_call": roll})
            matters_total += 1
        meetings.append({"date": str(e.get("EventDate"))[:10], "body": e.get("EventBodyName"),
                         "minutes_status": e.get("EventMinutesStatusName"),
                         "source": e.get("EventInSiteURL"), "matters": matters})
    return meetings, {"meetings": len(meetings), "matters": matters_total,
                      "draft_revisions": amended, "items_with_rollcall": votes_found}

def main():
    os.makedirs(PRIV, exist_ok=True)
    try:
        meetings, stats = harvest_bfed()
    except Exception as e:
        print("committee_votes: Legistar fetch failed:", str(e)[:120]); return 1
    votes_published = stats["items_with_rollcall"] > 0
    out = {"generated": datetime.now(HST).strftime("%Y-%m-%d %H:%M HST"), "committee": "BFED (Budget, Finance & Economic Development)",
           "stats": stats, "votes_published_by_county": votes_published,
           "dissent_access": ("structured roll-call available via Legistar Votes API" if votes_published else
               "NOT machine-accessible — county publishes agendas + matters but not committee roll-call votes; "
               "the NAYs require a RECORDS REQUEST to the Maui County Clerk (or appear only in unposted committee minutes). "
               "Never fabricate — this is a transparency GAP to pursue, not data to invent."),
           "meetings": meetings}
    # PRIVATE spine — the prosecutorial engine crosses these matters (esp. draft_revisions) with money.
    json.dump(out, open(os.path.join(PRIV, "bfed_index.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    with open(os.path.join(PRIV, "bfed_matters.jsonl"), "w", encoding="utf-8") as f:
        for mt in meetings:
            for m in mt["matters"]:
                f.write(json.dumps({**m, "date": mt["date"], "source": mt["source"]}, ensure_ascii=False) + "\n")
    print("committee_votes (BFED):")
    print("  Final meetings indexed : %d" % stats["meetings"])
    print("  matters (decisions)    : %d" % stats["matters"])
    print("  draft-revision matters : %d  (CD/SD/'as amended' = the change-to-flip signal)" % stats["draft_revisions"])
    print("  items w/ roll-call vote: %d" % stats["items_with_rollcall"])
    print("  -> dissent (NAYs): %s" % ("PUBLISHED — harvesting" if votes_published else "NOT published by county (records request required)"))
    print("  spine -> reports/_status/committee/bfed_matters.jsonl (PRIVATE)")
    return 0

if __name__ == "__main__":
    if sys.platform == "win32":
        import io; sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(main())
