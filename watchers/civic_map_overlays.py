#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""civic_map_overlays.py — generate the toggleable OVERLAY data for the Maui civic map canvas.

James 2026-07-02: the Maui tenant map is the central canvas; every feature ties in as a toggleable
overlay. This builds the overlay DATA files the map loads. STRICT data-discipline labels on every file:

  FACT / SOURCED   — the record (federal spend). Amounts real + cited; geographic precision stated.
  OUR MODEL        — 12 Stones projection + the cost/quote. Clearly labeled, never the county's numbers, never law.

Never fabricates county cost figures — the quote uses OUR OWN published rate card (an assumption shown),
projected across the county's ACTUAL upcoming agenda workload to the Hawaiʻi fiscal calendar (Jul 1–Jun 30).

Output: reports/mauios/overlays/{money_concentration,wealth_model,cost_quote}.json
Run:    python -X utf8 tools/kilo-aupuni/civic_map_overlays.py
"""
import os, json, re, datetime

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
M    = os.path.join(ROOT, "reports", "mauios")
OUT  = os.path.join(M, "overlays"); os.makedirs(OUT, exist_ok=True)
ST   = os.path.join(ROOT, "reports", "_status")

# Real, public Maui town coordinates (well-known; not fabricated placement of money —
# used only to anchor a town bubble WHEN an award's text names that town).
TOWNS = {
    "Wailuku":  (20.8893, -156.5040), "Kahului": (20.8893, -156.4729),
    "Lahaina":  (20.8783, -156.6825), "Kihei":   (20.7644, -156.4450),
    "Kīhei":    (20.7644, -156.4450), "Makawao": (20.8570, -156.3120),
    "Hana":     (20.7580, -156.0140), "Hāna":    (20.7580, -156.0140),
    "Kula":     (20.7500, -156.3300), "Paia":    (20.9030, -156.3730),
    "Pāʻia":    (20.9030, -156.3730),  "Wailea":  (20.6900, -156.4420),
    "Pukalani": (20.8380, -156.3390), "Napili":  (20.9940, -156.6660),
    "Kaanapali":(20.9200, -156.6940), "Haiku":   (20.9160, -156.3210),
}
COUNTYWIDE = (20.8300, -156.3300)  # island interior anchor for county-level (place-of-performance) spend


def load(p, d=None):
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception:
        return d


def money_concentration():
    """SOURCED overlay: real federal spend landing in Maui, aggregated to town where the award names one,
    else Countywide (place-of-performance = Maui County). Shows concentration; amounts cited to USAspending."""
    d = load(os.path.join(M, "federal_money_maui.json"), {}) or {}
    awards = d.get("awards") or []
    recips = d.get("recipients") or []
    maui_total = float((d.get("totals") or {}).get("maui") or 0)

    # DATA DISCIPLINE: award 'amount' is the FULL award (often multi-county/statewide) — summing it per town
    # over-counts and would contradict the sourced Maui total. Federal place-of-performance is COUNTY-LEVEL,
    # so we anchor ONE honest bubble = the sourced Maui-attributed total ($8.24B), and let the SOURCED
    # recipient breakdown carry the concentration story. No fabricated per-town money splits.
    n_awards = len([a for a in awards if float(a.get("amount") or 0) > 0])
    points = [{"place": "Maui County — federal (place of performance)", "lat": COUNTYWIDE[0],
               "lon": COUNTYWIDE[1], "amount": round(maui_total, 2), "count": n_awards, "county_level": True}]

    # the sourced concentration headline: share held by the top recipients
    rs = sorted(recips, key=lambda r: -float(r.get("maui_total") or 0))
    top10 = rs[:10]
    top10_sum = sum(float(r.get("maui_total") or 0) for r in top10)
    ratio = (top10_sum / maui_total) if maui_total else 0
    top_list = [{"recipient": r.get("recipient"), "maui_total": round(float(r.get("maui_total") or 0), 2)}
                for r in rs[:8]]

    return {
        "_label": "FACT / SOURCED — federal award amounts are the public record; cited.",
        "_source": d.get("source") or "USASpending.gov /api/v2/search/spending_by_award (place of performance = Hawaiʻi/Maui)",
        "_geo_note": "Federal place-of-performance is COUNTY-LEVEL. Town bubbles reflect awards whose text names a town; "
                     "the rest is shown as one 'Countywide' mass — which is itself the concentration: the money lands "
                     "in a few large county-level awards, not distributed across the towns where people live.",
        "maui_total": round(maui_total, 2),
        "top10_share": round(ratio, 4),
        "top10_share_pct": round(ratio * 100, 1),
        "top_recipients": top_list,
        "points": points,
        "generated": datetime.datetime.utcnow().strftime("%Y-%m-%d"),
    }


def wealth_model():
    """OUR MODEL overlay: 12 Stones generational-wealth distribution — reach spread EVENLY to every town
    (the projection of wealth reaching everybody). Labeled as our model/projection, NOT current fact."""
    towns = ["Wailuku", "Kahului", "Lahaina", "Kihei", "Makawao", "Hana", "Kula", "Paia",
             "Wailea", "Pukalani", "Napili", "Haiku"]
    pts = [{"place": t, "lat": TOWNS[t][0], "lon": TOWNS[t][1], "reach": 1.0} for t in towns]
    return {
        "_label": "OUR MODEL / PROJECTION — the 12 Stones generational-wealth distribution. "
                  "NOT current fact, NOT the county's numbers, NOT law.",
        "_basis": "12 Stones Global distributive model: value reaches every community on the island (even reach), "
                  "the deliberate inverse of concentration. Illustrative even weighting across Maui towns.",
        "points": pts,
        "generated": datetime.datetime.utcnow().strftime("%Y-%m-%d"),
    }


def cost_quote():
    """OUR MODEL overlay/panel: a live quote to run the civic software, projected across the county's ACTUAL
    upcoming agenda workload to the Hawaiʻi fiscal calendar (Jul 1–Jun 30). Uses OUR published rate card
    (assumption shown). Does NOT invent the county's own cost."""
    ai = load(os.path.join(ST, "agenda_intel_maui.json"), {}) or {}
    meetings = ai.get("meetings") or []
    upcoming_items = sum(len(m.get("items") or []) for m in meetings) or len(meetings)

    # Fiscal calendar (Hawaiʻi county FY = Jul 1 – Jun 30). Stamp passed in for determinism-free run.
    today = datetime.date(2026, 7, 2)
    fy_end = datetime.date(today.year + (1 if today.month >= 7 else 0), 6, 30)
    fy_start = datetime.date(fy_end.year - 1, 7, 1)
    months_left = max(1, (fy_end.year - today.year) * 12 + (fy_end.month - today.month))

    # OUR RATE CARD (assumption — our published tiers; transparent, not the county's figures)
    RATE = {
        "council_pro_dept_month": 999.0,   # per department / month (Council Pro tier)
        "per_seat_month": 29.0,            # per staff seat / month (Pro tier)
        "per_agenda_item_processed": 12.0, # per agenda item run through the pipeline (modeled unit)
    }
    DEPARTMENTS = 12   # modeled Maui County operating departments (assumption; refine from org chart)
    SEATS = 60         # modeled staff seats using the software (assumption)

    monthly = DEPARTMENTS * RATE["council_pro_dept_month"] + SEATS * RATE["per_seat_month"]
    items_month = max(upcoming_items, 1)
    monthly_items = items_month * RATE["per_agenda_item_processed"]
    monthly_total = monthly + monthly_items
    fy_total = monthly_total * months_left

    return {
        "_label": "OUR MODEL / LIVE QUOTE — 12 Stones govOS pricing applied to the county's actual upcoming "
                  "workload. NOT the county's official budget, NOT law. Rates are OUR published tiers (shown).",
        "_assumptions": {
            "rate_card": RATE, "departments_modeled": DEPARTMENTS, "seats_modeled": SEATS,
            "note": "Departments/seats are modeled assumptions — refine from the county org chart. "
                    "Agenda-item volume is SOURCED from agenda_intel_maui.json.",
        },
        "fiscal_year": {"start": fy_start.isoformat(), "end": fy_end.isoformat(),
                        "months_remaining": months_left, "as_of": today.isoformat()},
        "upcoming_agenda_items_sourced": upcoming_items,
        "monthly_quote": round(monthly_total, 2),
        "fiscal_year_quote": round(fy_total, 2),
        "breakdown": {
            "departments": round(DEPARTMENTS * RATE["council_pro_dept_month"], 2),
            "seats": round(SEATS * RATE["per_seat_month"], 2),
            "agenda_items_month": round(monthly_items, 2),
        },
        "generated": datetime.datetime.utcnow().strftime("%Y-%m-%d"),
    }


MAP = os.path.join(M, "maui_parcel_map.html")


def inject_map(out):
    """Inline the overlay data into the map's #ovdata placeholder so the page is self-contained
    (no dependency on build_site copying data files). Idempotent."""
    try:
        html = open(MAP, encoding="utf-8").read()
    except Exception:
        return False
    blob = json.dumps({"money": out["money_concentration"], "wealth": out["wealth_model"],
                       "cost": out["cost_quote"]}, ensure_ascii=False)
    new = re.sub(r'(<script id="ovdata" type="application/json">).*?(</script>)',
                 lambda m: m.group(1) + blob + m.group(2), html, count=1, flags=re.S)
    if new != html:
        open(MAP, "w", encoding="utf-8", newline="\n").write(new)
        return True
    return False


def build():
    out = {"money_concentration": money_concentration(),
           "wealth_model": wealth_model(),
           "cost_quote": cost_quote()}
    for name, data in out.items():
        p = os.path.join(OUT, name + ".json")
        json.dump(data, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    injected = inject_map(out)
    out["_injected"] = injected
    return out


if __name__ == "__main__":
    o = build()
    print("civic_map_overlays built ->", OUT)
    mc = o["money_concentration"]
    print("  money: $%.0f Maui federal; top-10 recipients = %.1f%%; %d place-buckets"
          % (mc["maui_total"], mc["top10_share_pct"], len(mc["points"])))
    print("  wealth (OUR MODEL): %d towns even-reach" % len(o["wealth_model"]["points"]))
    cq = o["cost_quote"]
    print("  cost quote (OUR MODEL): $%.0f/mo -> $%.0f to FY end (%s), from %d sourced agenda items"
          % (cq["monthly_quote"], cq["fiscal_year_quote"], cq["fiscal_year"]["end"], cq["upcoming_agenda_items_sourced"]))
