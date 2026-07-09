#!/usr/bin/env python3
"""testimony_crosscheck.py - "Cross-checked testimony: real estate, construction, et al."

Jimmy 2026-06-18: "build in all cross checked testimony from real estate construction et al."

WHAT IT HONESTLY IS: it takes the industry advocacy that is ALREADY on the public record - the
real-estate / short-term-rental testimony on Bill 9 (bill9_index.jsonl, sourced packet scans) and the
construction/engineering contractors on record - and CROSS-CHECKS each industry against TWO other
independent public records:
  1. campaign money to the deciders  - donor_profiles.json (the RE donations bucket per official)
  2. county contracts + their donations - vendor_donor_join.json (contractor awards x contributions)
A linkage is "cross-checked" only when it is corroborated by >= 2 independent public sources (the
testimony record AND a campaign-finance / contracts record). Each is written as a PUBLIC-RECORD
QUESTION, never an accusation.

WHAT IT IS NOT: it does not conclude anyone conspired or broke the law. Industries lobbying the
Council is lawful. Where the record holds genuine antitrust/licensing signals, bill9_testimony.py
already routes them to the bodies that can act (AG antitrust, DCCA/RICO, Real Estate Commission).
No testifier name is invented - Maui publishes no named citizen roster, so only the genuinely public
industry/lobbyist/contractor records are used.

Stdlib only. Reads reports/mauios/{donor_profiles,vendor_donor_join}.json + bill9/bill9_index.jsonl.
Writes reports/mauios/testimony_crosscheck.{json,html}.
"""
import os, sys, json, re, html, glob
from datetime import datetime, timezone, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(os.path.dirname(HERE))
M = os.path.join(PROJ, "reports", "mauios")          # inputs (public data) read from here
ST = os.path.join(PROJ, "reports", "_status")        # OUTPUT goes here — PRIVATE (names officials; publish-confirm gated)
HST = timezone(timedelta(hours=-10))
esc = lambda s: html.escape(str(s if s is not None else ""))


def load(p, d):
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception:
        return d


def load_jsonl(p):
    out = []
    try:
        for ln in open(p, encoding="utf-8"):
            ln = ln.strip()
            if ln:
                try: out.append(json.loads(ln))
                except Exception: pass
    except Exception:
        pass
    return out


# industry classifiers - real estate, construction, et al. Each maps a name/employer -> industry.
INDUSTRY = {
    "real_estate": ["realtor", "real estate", "realty", "brokerage", "broker", "vacation rental",
                    "short-term rental", "short term rental", "property management", "rental", "mls",
                    "coldwell", "keller williams", "sotheby", "compass real", "hawaii life", "remax",
                    "re/max", "development", "developer", "land &", "land and", "properties", "pineapple",
                    "ledcor", "alexander & baldwin", "a&b", "hoaloha", "kaanapali", "ranch"],
    "construction": ["construction", "contractor", "contracting", "engineering", "engineers", "builder",
                     "building", "paving", "excavat", "concrete", "general contractor", "grading",
                     "fukumoto", "goodfellow", "dorvin", "maui paving", "isemoto", "hawaiian dredging"],
}
GENERIC = {"the", "inc", "llc", "ltd", "co", "company", "corp", "corporation", "of", "and", "hawaii",
           "hawaiʻi", "maui", "county", "group", "trust", "lp", "llp", "dba"}


def industry_of(name, employer=""):
    s = (str(name or "") + " " + str(employer or "")).lower()
    for ind, kws in INDUSTRY.items():
        if any(k in s for k in kws):
            return ind
    return None


def collect_testimony():
    """Industry advocacy already on the public record. Bill 9 (STR phase-out) = the RE/realtor industry
    front; each meeting carries its sourced packet URL + the count of industry hits."""
    rows = []
    for r in load_jsonl(os.path.join(M, "bill9", "bill9_index.jsonl")):
        if (r.get("industry_hits") or 0) <= 0:
            continue
        rows.append({"industry": "real_estate", "matter": "Bill 9 (short-term-rental phase-out)",
                     "date": r.get("date"), "meeting": r.get("meeting"),
                     "industry_hits": r.get("industry_hits"), "price_hits": r.get("price_hits", 0),
                     "source": r.get("url")})
    rows.sort(key=lambda x: x.get("date") or "", reverse=True)
    return rows


def collect_property():
    """The ingested property layer (qPublic server-side workaround -> maui_re_report.json): real-estate
    ENTITIES that own parcels + sell them AND donate to the deciders. The heaviest RE money trail -
    ownership + transactions cross-checked to campaign donations. Returns entities sorted by tx value."""
    d = load(os.path.join(PROJ, "reports", "_status", "maui_re_report.json"), {})
    out = []
    for e in (d.get("entities") or []):
        offs = []
        for o in (e.get("officials") or []):
            if isinstance(o, (list, tuple)) and len(o) >= 2:
                offs.append({"official": o[0], "amount": o[1]})
            elif isinstance(o, str):
                offs.append({"official": o, "amount": None})
        out.append({"entity": e.get("entity"), "parcels": e.get("parcels") or 0,
                    "sales": e.get("sales") or 0, "tx_value": e.get("tx_value") or 0,
                    "donated": e.get("donated") or 0, "officials": offs,
                    "record": "county property (qPublic) x campaign finance",
                    "source": "reports/mauios/maui_re_report.html (private: reports/_status/maui_re_report.json)"})
    out.sort(key=lambda x: x.get("tx_value") or 0, reverse=True)
    return out, (d.get("summary") or {})


def collect_money(industries):
    """Money to the deciders, classified by industry. Two independent public records:
       - donor_profiles.json: the RE donations bucket per official (campaign finance)
       - vendor_donor_join.json: county contractors who also donated (contracts + finance)."""
    money = {k: [] for k in industries}
    contracts = {k: [] for k in industries}

    dp = load(os.path.join(M, "donor_profiles.json"), [])
    for prof in (dp if isinstance(dp, list) else []):
        official = prof.get("label") or prof.get("key") or ""
        re_b = prof.get("realestate") or {}
        for don in (re_b.get("donors") or []):
            ind = industry_of(don.get("name"), don.get("employer")) or "real_estate"
            if ind in money:
                money[ind].append({"official": official, "funder": don.get("name"),
                                   "amount": don.get("amount") or 0, "employer": don.get("employer") or "",
                                   "record": "campaign finance (CSC donor_profiles)",
                                   "source": "reports/mauios/donor_profiles.html"})

    vdj = load(os.path.join(M, "vendor_donor_join.json"), {})
    for m in (vdj.get("matched") or vdj.get("matches") or []):
        ind = industry_of(m.get("vendor")) or "construction"
        if ind not in contracts:
            continue
        contracts[ind].append({"vendor": m.get("vendor"), "award_total": m.get("award_total") or 0,
                               "award_count": m.get("award_count") or 0,
                               "officials": m.get("officials") or [],
                               "contrib_total": m.get("contrib_total") or 0,
                               "record": "county contracts (HANDS) x campaign finance",
                               "source": "reports/mauios/vendor_donor_join.html"})
        for h in (m.get("hits") or []):
            if ind in money:
                money[ind].append({"official": h.get("official_label") or h.get("official"),
                                   "funder": h.get("contributor"), "amount": h.get("amount") or 0,
                                   "employer": m.get("vendor"),
                                   "record": "contractor donation (vendor_donor_join, basis=%s)" % h.get("basis", "?"),
                                   "source": "reports/mauios/vendor_donor_join.html"})
    return money, contracts


def build():
    industries = list(INDUSTRY.keys())
    testimony = collect_testimony()
    money, contracts = collect_money(industries)
    re_property, prop_summary = collect_property()   # ingested qPublic property layer (real_estate)

    # the CROSS-CHECK: an industry is corroborated when it BOTH advocates on the record AND funds the
    # deciders (>= 2 independent public sources). Each is a question for further public reporting.
    crosschecks = []
    test_by_ind = {}
    for t in testimony:
        test_by_ind.setdefault(t["industry"], []).append(t)
    for ind in industries:
        t_rows = test_by_ind.get(ind, [])
        m_rows = money.get(ind, [])
        c_rows = contracts.get(ind, [])
        if not (t_rows or m_rows or c_rows):
            continue
        money_total = round(sum(r.get("amount") or 0 for r in m_rows), 2)
        award_total = round(sum(r.get("award_total") or 0 for r in c_rows), 2)
        prop_rows = re_property if ind == "real_estate" else []
        prop_tx = round(sum(p.get("tx_value") or 0 for p in prop_rows), 2)
        prop_parcels = sum(p.get("parcels") or 0 for p in prop_rows)
        corroborated = bool(t_rows) and bool(m_rows or c_rows or prop_rows)
        label = ind.replace("_", " ").title()
        if corroborated:
            prop_clause = ("" if not prop_tx else
                           " The same industry owns %s parcels and moved $%s in property transactions on record." % (
                               "{:,}".format(prop_parcels), "{:,.0f}".format(prop_tx)))
            q = ("On the public record the %s industry both ADVOCATED to the Council (%d sourced "
                 "appearance%s) and FUNDED the deciders ($%s in tracked donations%s).%s A reader should "
                 "ask: did the members who received this money vote on the matters this industry "
                 "testified about, and was that disclosed?" % (
                     label.lower(), len(t_rows), "" if len(t_rows) == 1 else "s",
                     "{:,.0f}".format(money_total),
                     (" + $%s in county awards" % "{:,.0f}".format(award_total)) if award_total else "",
                     prop_clause))
        else:
            q = ("The %s industry appears in one public record here but not yet cross-corroborated by a "
                 "second; treat as a lead, not a link." % label.lower())
        crosschecks.append({"industry": ind, "label": label, "corroborated": corroborated,
                            "testimony_appearances": len(t_rows), "donations_total": money_total,
                            "awards_total": award_total, "property_tx": prop_tx, "property_parcels": prop_parcels,
                            "question": q})

    # the THIRD leg - did the funded members vote on the matter the industry testified about? Maui does
    # NOT publish committee roll-call votes machine-accessibly (committee_votes.py verified: 0/100 matters
    # carry a published roll-call). We do NOT invent votes. Instead the gap becomes a concrete accountability
    # ACTION: a UIPA records request for the roll-call - the honest way to complete the money x votes x
    # testimony triangle.
    rollcall_published = 0
    try:
        for ln in open(os.path.join(PROJ, "reports", "_status", "committee", "bfed_matters.jsonl"), encoding="utf-8"):
            ln = ln.strip()
            if ln and (json.loads(ln).get("roll_call") or []):
                rollcall_published += 1
    except Exception:
        pass
    actions = []
    for x in crosschecks:
        if x["corroborated"]:
            actions.append({
                "type": "UIPA records request",
                "to": "Maui County Clerk (council services)",
                "ask": ("The recorded roll-call vote (ayes/noes by member) on the matters the %s industry "
                        "testified about, so the public can see whether the members who received this "
                        "industry's money voted its way." % x["label"].lower()),
                "why": ("Maui publishes agendas + matters but NOT committee roll-call votes (%d of the matters "
                        "on file carry a published roll-call); the dissent is only obtainable by record request."
                        % rollcall_published),
                "basis": "HRS 92F (UIPA)"})

    out = {
        "generated": datetime.now(HST).strftime("%Y-%m-%d %H:%M:%S HST"),
        "source": "kilo-aupuni / testimony_crosscheck",
        "integrity": ("Cross-checked = corroborated by >= 2 independent PUBLIC records (testimony packet + "
                      "campaign-finance / contracts). Lawful advocacy; every linkage is a public-record "
                      "QUESTION, never an accusation. No testifier name is invented. The roll-call vote that "
                      "would complete the triangle is WITHHELD from machine access - requested by UIPA, never faked."),
        "vote_record": {"rollcall_published": rollcall_published,
                        "status": "machine-inaccessible (Maui publishes no committee roll-call)",
                        "remedy": "UIPA records request (see actions)"},
        "property_summary": prop_summary,
        "industries": {ind: {"testimony": test_by_ind.get(ind, []), "money_to_deciders": money.get(ind, []),
                             "contracts": contracts.get(ind, []),
                             "property": re_property if ind == "real_estate" else []} for ind in industries},
        "cross_checks": crosschecks,
        "actions": actions,
    }
    json.dump(out, open(os.path.join(ST, "testimony_crosscheck.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    write_html(out)
    return out


def write_html(out):
    def industry_block(ind, label):
        d = out["industries"][ind]
        t = d["testimony"]; mo = d["money_to_deciders"]; c = d["contracts"]
        trs = "".join("<tr><td>%s</td><td>%s</td><td>%s hits</td><td><a href='%s'>packet</a></td></tr>"
                      % (esc(r["date"]), esc(r["matter"]), esc(r["industry_hits"]), esc(r["source"]))
                      for r in t) or "<tr><td colspan=4 class=fine>No sourced industry testimony indexed yet.</td></tr>"
        # collapse money to top funders by official
        mo_s = sorted(mo, key=lambda r: r.get("amount") or 0, reverse=True)[:25]
        mrs = "".join("<tr><td>%s</td><td>%s</td><td>$%s</td><td class=fine>%s</td></tr>"
                      % (esc(r["official"]), esc(r["funder"]), "{:,.0f}".format(r.get("amount") or 0), esc(r["record"]))
                      for r in mo_s) or "<tr><td colspan=4 class=fine>No tracked industry donations to deciders.</td></tr>"
        crs = "".join("<tr><td>%s</td><td>$%s</td><td>%s</td><td>%s</td></tr>"
                      % (esc(r["vendor"]), "{:,.0f}".format(r.get("award_total") or 0), esc(r.get("award_count")),
                         esc(", ".join(r.get("officials") or []))) for r in c)
        ctab = ("<h4>County contracts &times; donations</h4><table><tr><th>Vendor</th><th>Awards</th>"
                "<th>#</th><th>Funded officials</th></tr>%s</table>" % crs) if c else ""
        # property layer (real estate): entities that own + sell parcels AND fund the deciders
        prop = d.get("property") or []
        if prop:
            prs = "".join(
                "<tr><td>%s</td><td>%s</td><td>$%s</td><td>$%s</td><td class=fine>%s</td></tr>" % (
                    esc(p["entity"]), "{:,}".format(p.get("parcels") or 0),
                    "{:,.0f}".format(p.get("tx_value") or 0), "{:,.0f}".format(p.get("donated") or 0),
                    esc("; ".join("%s ($%s)" % (o["official"], "{:,.0f}".format(o["amount"] or 0))
                                  for o in (p.get("officials") or [])[:3])))
                for p in prop[:20])
            ptab = ("<h4>Property holdings &times; donations &mdash; the heaviest RE money trail "
                    "(qPublic + campaign finance)</h4><table><tr><th>Entity</th><th>Parcels</th>"
                    "<th>Transactions</th><th>Donated</th><th>Funded deciders</th></tr>%s</table>" % prs)
        else:
            ptab = ""
        return ("<section class=ind><h3>%s</h3>"
                "<h4>On the record: industry testimony</h4>"
                "<table><tr><th>Date</th><th>Matter</th><th>Industry signal</th><th>Source</th></tr>%s</table>"
                "<h4>Money to the deciders</h4>"
                "<table><tr><th>Official</th><th>Funder</th><th>Amount</th><th>Record</th></tr>%s</table>"
                "%s%s</section>" % (esc(label), trs, mrs, ptab, ctab))

    cc = "".join(
        "<li class='%s'><b>%s</b> &mdash; %s</li>" % (
            "ok" if x["corroborated"] else "lead", esc(x["label"]), esc(x["question"]))
        for x in out["cross_checks"]) or "<li class=fine>No industries on record yet.</li>"
    blocks = "".join(industry_block(ind, ind.replace("_", " ").title()) for ind in out["industries"])
    body = (
        "<div style='max-width:920px;margin:0 auto;padding:1.2rem 1rem'>"
        "<h1 style='color:#0e4a84'>Cross-checked testimony &mdash; real estate, construction, et al.</h1>"
        "<p class=lead>Industry advocacy that is on the public record, cross-checked against the campaign "
        "money to the deciders and the county contracts &mdash; corroborated across at least two "
        "independent public sources. Every line is a question for further reporting, not a finding.</p>"
        "<div class=integrity>%s</div>"
        "<h2 style='color:#0e4a84'>The cross-checks</h2><ul class=cc>%s</ul>%s"
        "<p class=fine>Generated %s. Sources: Bill 9 packet scans (mauicounty.civicclerk), Hawaiʻi CSC "
        "campaign finance, HANDS county awards. Lawful advocacy &mdash; a question to the record, never a claim.</p>"
        "</div>" % (esc(out["integrity"]), cc, blocks, esc(out["generated"])))
    css = ("<style>body{font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;color:#1f2d3a;background:#fff}"
           ".lead{font-size:1.04rem;color:#33414f}.integrity{background:#eef5ff;border-left:3px solid #0e4a84;"
           "padding:.6rem .9rem;border-radius:8px;font-size:.9rem;margin:.6rem 0}"
           "table{border-collapse:collapse;width:100%;margin:.4rem 0 1rem;font-size:.86rem}"
           "th,td{border:1px solid #dce6f1;padding:.32rem .5rem;text-align:left;vertical-align:top}"
           "th{background:#f3f8ff;color:#0e4a84}.ind{border-top:2px solid #e3edf8;margin-top:1.2rem}"
           ".cc{padding-left:1.1rem}.cc li{margin:.35rem 0}.cc .ok{}.cc .lead{color:#5a6b7b}"
           ".fine{color:#5a6b7b;font-size:.82rem}h3{color:#0e4a84;margin-bottom:.2rem}h4{margin:.7rem 0 .2rem;color:#33414f}</style>")
    doc = ("<!doctype html><html lang=en><head><meta charset=utf-8>"
           "<meta name=viewport content='width=device-width,initial-scale=1'>"
           "<title>Cross-checked testimony &mdash; govOS</title>%s</head><body>%s</body></html>" % (css, body))
    open(os.path.join(ST, "testimony_crosscheck.html"), "w", encoding="utf-8", newline="\n").write(doc)


def main():
    out = build()
    n_corr = sum(1 for x in out["cross_checks"] if x["corroborated"])
    print("testimony_crosscheck: %d industries, %d corroborated cross-checks -> testimony_crosscheck.{json,html}"
          % (len(out["cross_checks"]), n_corr))
    for x in out["cross_checks"]:
        print("  [%s] %s: %d testimony, $%s donations, $%s awards" % (
            "CORROBORATED" if x["corroborated"] else "lead", x["label"],
            x["testimony_appearances"], "{:,.0f}".format(x["donations_total"]),
            "{:,.0f}".format(x["awards_total"])))
    return 0


if __name__ == "__main__":
    if sys.platform == "win32":
        import io; sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(main())
