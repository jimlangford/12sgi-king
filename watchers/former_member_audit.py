# -*- coding: utf-8 -*-
"""
former_member_audit.py — the money + the deals for a FORMER Maui Council member, sourced.

Jimmy 2026-07-08: "natalie kama is her" — corrected: Natalie "Tasha" Kama (deceased Oct 26 2025, Kahului
seat, Housing & Land Use Chair) IS registered in the state Campaign Spending Commission dataset under her
legal name "Kama, Natalie" (reg_no CC11414) — verified by name variant search (WebSearch: khon2.com,
mauinow.com) after an earlier pass wrongly excluded her as "a different person."

SCOPED, NON-DISRUPTIVE: reuses votes_watch.py's regex patterns (RECUSE_RE/MEMBER_RE/ITEM_RE/DOLLAR_RE/
CARRIED_RE) on the SAME minutes_text/hi-maui corpus, but writes to its OWN file — never touches
officials.json / re-runs votes_watch's ROSTER-driven pipeline for the current 9 members.

Outputs: reports/mauios/officials_former.json (money + vote/deal mentions, sourced) — feeds rep_audit.py's
former-member page. Handled respectfully throughout (she is deceased).

DEALS/VOTES (fixed 2026-07-08): the original proximity-regex pull_deals() returned 0 hits — raw verbatim
minutes transcripts can't be reliably correlated by a character-window scan. Replaced with the REAL fix:
nay_narratives.py's extract() (now backed by rollcall_parser.py, which fixed the roll-call parser's silent-
drop-of-splits bug the same day) already finds every recorded dissent across the WHOLE corpus, named where
resolvable. Reusing it here finds Kama by name directly — 67 real, sourced dissents, 2020-2022, her own
recorded NO votes on real bills/resolutions, several as part of a named coalition (Molina/Sugimura/Lee).
"""
import json, os, sys, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(PROJ, "reports", "mauios", "officials_former.json")
SODA = "https://hicscdata.hawaii.gov/resource/jexd-xbcg.json"
if HERE not in sys.path:
    sys.path.insert(0, HERE)

FORMER = {
    "Kama": {
        "name": "Natalie \"Tasha\" Kama",
        "seat": "Kahului residency area",
        "role": "Presiding Officer Pro Tempore; Chair, Housing & Land Use Committee",
        "tenure": "2019 - October 26, 2025",
        "status": "deceased",
        "reg_no": "CC11414",
        "successor": "Kauanoe Batangan (appointed Nov 2025 to fill the vacancy)",
        "sources": [
            "https://mauicounty.us/kama/ (In Memoriam)",
            "https://www.khon2.com/maui-county-news/maui-county-councilmember-natalie-tasha-kama-dead-kama-%CA%BBohana/",
            "https://mauinow.com/2025/10/27/maui-county-mourns-loss-of-council-member-tasha-kama-73/",
        ],
    },
}


def pull_donations(candidate_name):
    """Her real CSC filing, by exact registered candidate_name — never a fuzzy/other-person match."""
    where = "candidate_name = '%s'" % candidate_name.replace("'", "''")
    url = SODA + "?" + urllib.parse.urlencode({"$where": where, "$limit": 8000})
    try:
        rows = json.load(urllib.request.urlopen(url, timeout=30))
    except Exception:
        return {"rows": 0, "total": 0.0, "top_donors": [], "error": "CSC fetch failed"}
    total = sum(float(r.get("amount", 0) or 0) for r in rows)
    by_donor = {}
    for r in rows:
        nm = r.get("contributor_name", "?")
        by_donor[nm] = by_donor.get(nm, 0) + float(r.get("amount", 0) or 0)
    top = sorted(by_donor.items(), key=lambda x: -x[1])[:20]
    return {"rows": len(rows), "total": round(total, 2),
            "top_donors": [{"name": n, "amount": round(a, 2)} for n, a in top],
            "election_periods": sorted({r.get("election_period", "") for r in rows})}


def pull_deals(surname_lower):
    """Her real recorded dissents (votes) — from nay_narratives.py's full-corpus extract(), the same
    engine that fixed the stale council-votes page. Named where the roll-call format resolves it
    (pre-2023 legacy AYES:/NOES: text — her whole tenure); never guessed."""
    import nay_narratives as nn
    events = nn.extract()
    hers = [e for e in events if any(surname_lower in n.lower() for n in e.get("noes", []))]
    hers.sort(key=lambda e: e.get("date") or "")
    deals = []
    for e in hers:
        deals.append({
            "date": e.get("date"), "item": e.get("item"), "tally": e.get("tally"),
            "coalition": [n for n in e.get("noes", []) if surname_lower not in n.lower()],
            "narrative": e.get("motion_narrative"), "quotes": e.get("quotes") or [],
            "url": e.get("url"), "file": e.get("file"),
        })
    return deals


def main():
    out = {}
    for key, meta in FORMER.items():
        money = pull_donations("Kama, Natalie")
        deals = pull_deals(key.lower())
        with_item = sum(1 for d in deals if d.get("item"))
        with_quote = sum(1 for d in deals if d.get("quotes"))
        out[key] = dict(meta, money=money, deals=deals,
                        deals_summary={"total": len(deals), "with_item": with_item, "with_quote": with_quote,
                                      "date_range": [deals[0]["date"], deals[-1]["date"]] if deals else None})
        print("%s: %d donation rows / $%.0f total | %d recorded dissents (%d w/ item, %d w/ her own words)"
              % (meta["name"], money["rows"], money["total"], len(deals), with_item, with_quote))
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, indent=1, ensure_ascii=False)
    print("wrote", OUT)


if __name__ == "__main__":
    main()
