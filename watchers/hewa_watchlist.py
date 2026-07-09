#!/usr/bin/env python3
"""hewa_watchlist.py — the LENS that points the money work FORWARD at the agenda (Jimmy 2026-06-18:
"process agendas and minutes to audit the direction and get ahead of hewa ... money work is the focus
of the civic thread" — and the money×votes work is the supporting lens for it).

It distills the worked money signals (money_votes_casework EXAMINE/NOTE verdicts + testimony_crosscheck
property/contract entities) into ONE small watchlist of entities + officials. The agenda forward-scan
(bfed_today.py / agenda_patterns.py) reads this so that when one of these names appears on an UPCOMING
agenda item, it is flagged AHEAD of the vote — the whole point: get ahead of hewa, not report it after.

The watchlist says WHO to watch and WHY (the money reason) + the aloha QUESTION to raise if they surface
on the agenda. It is not a verdict on anyone — it is a question the public can carry to the meeting in time.
PRIVATE owner-side (it names officials). Tenant-parameterized: --tenant. Stdlib only.
Output: reports/_status/hewa_watchlist_<tenant>.json
"""
import os, sys, json, re
from datetime import datetime, timezone, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(os.path.dirname(HERE))
ST = os.path.join(PROJ, "reports", "_status")
M = os.path.join(PROJ, "reports", "mauios")
HST = timezone(timedelta(hours=-10))


def load(p, d):
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception:
        return d


def _official(s):
    return (s or "").split(" - ")[0].strip()


def build(tenant):
    watch = {}   # entity name (upper) -> record

    def add(name, strength, why, official, source):
        if not name:
            return
        k = name.upper().strip()
        r = watch.setdefault(k, {"entity": name, "strength": 0, "why": [], "officials": set(), "sources": set()})
        r["strength"] = max(r["strength"], strength)
        if why and why not in r["why"]:
            r["why"].append(why)
        if official:
            r["officials"].add(_official(official))
        if source:
            r["sources"].add(source)

    # 1) the worked casework — EXAMINE = strong watch, NOTE = medium
    cw = load(os.path.join(ST, "casework_%s.json" % tenant), {})
    for c in (cw.get("cases") or []):
        v = c.get("verdict")
        if v == "EXAMINE":
            add(c.get("vendor"), 3, "$%s in county awards + donated to a deciding member" %
                "{:,.0f}".format(c.get("award_total") or 0), c.get("official"), "money_votes_casework")
        elif v == "NOTE":
            add(c.get("vendor"), 2, "county awards + a donation to a member (worth a question)",
                c.get("official"), "money_votes_casework")

    # 2) the property + contract entities from the cross-check (heaviest money trail)
    xc = load(os.path.join(M, "testimony_crosscheck.json"), {})
    for blk in (xc.get("industries") or {}).values():
        for p in (blk.get("property") or [])[:12]:
            offs = "; ".join(o.get("official", "") for o in (p.get("officials") or [])[:2])
            tx = p.get("tx_value") or 0
            if tx >= 100_000_000:
                add(p.get("entity"), 3, "%s parcels / $%s in property transactions + donations to deciders" % (
                    "{:,}".format(p.get("parcels") or 0), "{:,.0f}".format(tx)),
                    offs, "testimony_crosscheck:property")
            elif tx > 0:
                add(p.get("entity"), 2, "$%s in property transactions on record" % "{:,.0f}".format(tx),
                    offs, "testimony_crosscheck:property")
        for c in (blk.get("contracts") or [])[:12]:
            add(c.get("vendor"), 2, "$%s in county contracts" % "{:,.0f}".format(c.get("award_total") or 0),
                "; ".join(c.get("officials") or [])[:60], "testimony_crosscheck:contracts")

    entities = []
    for r in watch.values():
        offs = sorted(o for o in r["officials"] if o)
        entities.append({
            "entity": r["entity"], "strength": r["strength"], "why": r["why"], "officials": offs,
            "sources": sorted(r["sources"]),
            "if_on_agenda": ("If this name appears on an upcoming agenda item, ask BEFORE the vote: does any "
                             "member who received this entity's money sit over this decision, and will they "
                             "disclose or recuse? (A question for pono, raised in time — never an accusation.)")})
    entities.sort(key=lambda e: (-e["strength"], e["entity"]))

    out = {"tenant": tenant, "generated": datetime.now(HST).strftime("%Y-%m-%d %H:%M:%S HST"),
           "purpose": ("Forward lens for the agenda scan: WHO to watch on upcoming agendas + WHY (the money) "
                       "+ the aloha question to raise ahead of the vote. Get ahead of hewa, do not report it after."),
           "privacy": "OWNER-ONLY (names officials) — the public side shows only the aloha question once an item is live.",
           "count": len(entities), "high_strength": sum(1 for e in entities if e["strength"] >= 3),
           "entities": entities}
    os.makedirs(ST, exist_ok=True)
    json.dump(out, open(os.path.join(ST, "hewa_watchlist_%s.json" % tenant), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    return out


def main():
    import argparse
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--tenant", default="maui")
    a, _ = ap.parse_known_args()
    out = build(a.tenant)
    print("hewa_watchlist[%s]: %d entities to watch on upcoming agendas (%d high-strength) -> hewa_watchlist_%s.json"
          % (a.tenant, out["count"], out["high_strength"], a.tenant))
    for e in out["entities"][:6]:
        print("  [%d] %s — %s%s" % (e["strength"], e["entity"], (e["why"][0] if e["why"] else ""),
                                    (" -> " + ", ".join(e["officials"]) if e["officials"] else "")))
    return 0


if __name__ == "__main__":
    if sys.platform == "win32":
        import io; sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(main())
