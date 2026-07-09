#!/usr/bin/env python3
# committee_minutes.py - THE committee dissent harvester (Jimmy 2026-06-16). Breakthrough: Maui committee
#   minutes ARE reachable over plain HTTP after all -
#     1. Legistar API -> committee Events (+ EventInSiteURL)
#     2. fetch the meeting-detail page -> scrape the View.ashx?M=M (MINUTES) link  [absent on upcoming mtgs;
#        present once finalized]  3. fetch that minutes PDF -> pypdf text
#     4. parse the formal roll-call blocks:  AYES: <names>. NOES: <names>. ABSTAIN/ABSENT/EXC.: <names>.
#   Captures every motion where NOES != None = the DISSENT, with the bill/item + a CROSS-DISTRICT flag
#   (member voting on a matter outside their own district = the question). PRIVATE/owner-only, sourced,
#   question-framed, NEVER published, NEVER invented. Supersedes the "records request required" conclusion.
#   Stdlib + pypdf. Usage: python committee_minutes.py [committee_substr] [max_meetings]
import os, sys, json, ssl, io, re, urllib.request, urllib.parse
from datetime import datetime, timedelta, timezone

HOME = os.path.expanduser("~")
PROJECT = os.path.join(HOME, "Documents", "Claude", "Projects", "Video System elementLOTUS")
PRIV = os.path.join(PROJECT, "reports", "_status", "committee")
HST = timezone(timedelta(hours=-10))
UA = {"User-Agent": "Mozilla/5.0 12sgi-kilo-aupuni/1.0 (civic transparency; public record)"}
BASE = "https://webapi.legistar.com/v1/mauicounty"

SURNAMES = {"Batangan": r"Batangan", "Cook": r"\bCook\b", "Johnson": r"Johnson", "Lee": r"\bLee\b",
            "Paltin": r"Paltin", "Rawlins-Fernandez": r"Fernandez", "Sinenci": r"Sinenci",
            "Sugimura": r"Sugimura", "Uu-Hodgins": r"Hodgins"}
DISTRICT = {"Batangan":"Kahului","Cook":"South Maui","Johnson":"Lanai","Lee":"Wailuku","Paltin":"West Maui",
            "Rawlins-Fernandez":"Molokai","Sinenci":"East Maui","Sugimura":"Upcountry","Uu-Hodgins":"South Maui/at-large"}
PLACES = {"lipoa":"South Maui","kihei":"South Maui","wailea":"South Maui","makena":"South Maui",
          "lahaina":"West Maui","kaanapali":"West Maui","napili":"West Maui","wailuku":"Wailuku","kahului":"Kahului",
          "hana":"East Maui","haiku":"East Maui","makawao":"Upcountry","kula":"Upcountry","pukalani":"Upcountry",
          "lanai":"Lanai","molokai":"Molokai"}

def gt(u, b=False):
    r = urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=60, context=ssl.create_default_context()).read()
    return r if b else r.decode("utf-8", "replace")
def jj(u): return json.loads(gt(u))

def members_in(s):
    if not s or re.match(r"\s*none\b", s, re.I): return []
    return sorted({k for k, tok in SURNAMES.items() if re.search(tok, s)})

# a roll-call block: AYES: ... NOES: ... [ABSTAIN: ...] [ABSENT: ...] EXC.: ...
ROLL = re.compile(r"AYES:\s*(.*?)\s*NOES:\s*(.*?)(?:\s*ABSTAIN:\s*(.*?))?(?:\s*ABSENT:\s*(.*?))?\s*EXC\.?:?\s*(.*?)(?:\n|\.\s|$)",
                  re.I | re.S)
# Capture bill/resolution number with optional year paren: "Bill 83 (2026)" or "Bill 83"
# Deliberately narrow — don't capture trailing motion text ("Bill 117 with the CD1...")
ITEM = re.compile(r"(Bill\s+\d+(?:\s*\([^\)]{0,8}\))?|CR\s*\d+[\-\d]*|Reso(?:lution)?\s+[\d\-]+(?:\s*\([^\)]{0,8}\))?|County\s+Communication\s+\d+[\-\d]*)", re.I)

def parse_minutes(txt):
    txt = re.sub(r"[ \t]+", " ", txt)
    motions = []
    for m in ROLL.finditer(txt):
        ayes, noes, abst, absent, exc = (m.group(i) or "" for i in range(1, 6))
        noes_m = members_in(noes)
        # only keep real recorded roll calls (have ayes), flag dissent when noes present
        ay = members_in(ayes)
        if not ay and not noes_m: continue
        pre = txt[max(0, m.start() - 700): m.start()]
        item = ITEM.findall(pre)
        subject = re.sub(r"\s+", " ", item[-1]).strip()[:60] if item else None
        # cross-district: which place is named near the item, vs the dissenter's district
        win = (pre[-400:] + " " + (subject or "")).lower()
        place = next((d for k, d in PLACES.items() if re.search(r"\b" + k, win)), None)
        flags = []
        for nm in noes_m:
            if place and place.split("/")[0].lower() not in DISTRICT[nm].lower():
                flags.append("%s (NO, %s) voted on a %s matter — outside their district" % (nm, DISTRICT[nm], place))
        motions.append({"item": subject, "place": place, "ayes": ay, "noes": noes_m,
                        "abstain": members_in(abst), "excused": members_in(exc),
                        "dissent": bool(noes_m), "cross_district_questions": flags})
    return motions

def normalize_bill(raw):
    """Normalize bill references to a canonical key (same logic as bill_committee_enrich).
    'BILL 88', 'Bill 88 (2026)' → 'Bill 88'; 'Resolution 25-142 (2025)' → 'Resolution 25-142'
    """
    import re as _re
    s = _re.sub(r"\s*\(\d{4}\)\s*", "", raw).strip()
    s = _re.sub(r"^BILL\b", "Bill", s)
    s = _re.sub(r"^RESOLUTION\b", "Resolution", s)
    s = _re.sub(r"^RESO\b", "Reso", s)
    s = _re.sub(r"^CC\s+", "CC ", s)
    m = _re.match(r"((?:Bill|Resolution|Reso|CR|CC)\s+[\d\-\.]+)", s, _re.I)
    if m:
        s = m.group(1)
    return s.strip()

def minutes_and_video_for(event):
    """Returns (minutes_url, video_url) from the InSite meeting page. video_url may be None."""
    insite = event.get("EventInSiteURL")
    if not insite: return None, None
    try:
        html = gt(insite)
    except Exception:
        return None, None
    mm = re.search(r'View\.ashx\?M=M&[^"\'<> ]+', html)
    minutes = ("https://mauicounty.legistar.com/" + mm.group(0).replace("&amp;", "&")) if mm else None
    # Granicus player is embedded as an iframe src or direct link
    gm = re.search(r'(https?://[^"\'<>\s]*granicus\.com/[^"\'<>\s]+)', html, re.I)
    video = gm.group(1) if gm else None
    return minutes, video

def minutes_url_for(event):
    minutes, _ = minutes_and_video_for(event)
    return minutes

def main():
    substr = sys.argv[1] if len(sys.argv) > 1 else "budget"
    cap = int(sys.argv[2]) if len(sys.argv) > 2 else 20
    rows = jj("%s/Events?%s" % (BASE, urllib.parse.urlencode({"$orderby": "EventDate desc", "$top": "300"})))
    evs = [r for r in rows if substr.lower() in (r.get("EventBodyName") or "").lower()
           and r.get("EventMinutesStatusName") == "Final" and r.get("EventInSiteURL")]
    print("Final '%s' meetings to scan: %d (cap %d)" % (substr, len(evs), cap))
    meetings, n_motions, n_dissent, dissents = 0, 0, 0, []
    for e in evs[:cap]:
        url, video_url = minutes_and_video_for(e)
        if not url: continue
        try:
            import pypdf
            txt = "\n".join((p.extract_text() or "") for p in pypdf.PdfReader(io.BytesIO(gt(url, b=True))).pages)
        except Exception:
            continue
        ms = parse_minutes(txt)
        if not ms: continue
        meetings += 1
        date = str(e.get("EventDate"))[:10]
        for mo in ms:
            n_motions += 1
            if mo["dissent"]:
                n_dissent += 1
                rec = {"date": date, "body": e.get("EventBodyName"), "minutes": url, **mo}
                if video_url:
                    rec["video_url"] = video_url
                dissents.append(rec)
    os.makedirs(PRIV, exist_ok=True)
    with open(os.path.join(PRIV, "committee_dissent.jsonl"), "w", encoding="utf-8") as f:
        for d in dissents:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")
    json.dump({"generated": datetime.now(HST).strftime("%Y-%m-%d %H:%M HST"), "PRIVACY": "OWNER-ONLY - never publish",
               "committee_filter": substr, "meetings_parsed": meetings, "motions": n_motions, "dissent_motions": n_dissent,
               "note": "Real committee roll-calls from Legistar minutes PDFs (M=M). NOES != None = recorded dissent. "
               "cross_district_questions flag a NO cast on a matter outside the member's district. Sourced, never invented."},
              open(os.path.join(PRIV, "committee_dissent_summary.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print("committee_minutes (%s):" % substr)
    print("  meetings with parsed roll-calls:", meetings)
    print("  motions parsed                 :", n_motions)
    print("  motions WITH dissent (NOES)    :", n_dissent)
    for d in dissents[:10]:
        print("   * %s  NO: %s  on %s%s" % (d["date"], ", ".join(d["noes"]), d.get("item") or "(item?)",
              ("  [%s]" % d["cross_district_questions"][0]) if d["cross_district_questions"] else ""))
    print("  -> PRIVATE reports/_status/committee/committee_dissent.jsonl")
    return 0

if __name__ == "__main__":
    if sys.platform == "win32":
        import io as _io; sys.stdout = _io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(main())
