#!/usr/bin/env python3
# money_county.py - county campaign-money pages (the 'who funds the council' lens) for the Hawaiʻi county
# tenants, built from the SOURCED statewide CSC dataset (reports/mauios/statewide_money.json by_office +
# realestate_by_office). Honest-by-construction: shows the real money raised by each county council and the
# real-estate-interest slice (the prosecutorial angle), and states plainly WHERE the contract-side parity is
# blocked — Hawaiʻi County + Kauaʻi publish ~no contract awards to the HANDS open-data feed, so contracts×donors
# cannot be computed for them yet. That opacity is itself the finding. Facts + source; nothing invented.
# Stdlib only. Yale-blue govOS style to match officials_county.py.
import os, sys, json
from datetime import datetime, timedelta, timezone
HST=timezone(timedelta(hours=-10))
HOME=os.path.expanduser("~"); PROJ=os.path.join(HOME,"Documents","Claude","Projects","Video System elementLOTUS")
M=os.path.join(PROJ,"reports","mauios")
SM=os.path.join(M,"statewide_money.json")
HANDS=os.path.join(M,"_hands_statewide.json")
def esc(s): return str(s if s is not None else "").replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
def usd(n): return "{:,.0f}".format(n or 0)

# slug -> (council office key in by_office, display name, tenant id, HANDS jurisdiction names for contracts)
COUNTIES={
 "hawaii": ("Hawaii Council","Hawaiʻi County Council","hi-hawaii",
            {"County of Hawaii","County of Hawaiʻi","Hawaii County"}),
 "kauai":  ("Kauai Council","Kauaʻi County Council","hi-kauai",
            {"County of Kauai","County of Kauaʻi","Kauai County","Kauai County - Department of Water Supply"}),
}

def _office(rows, key):
    for r in rows:
        if r.get("office")==key: return r
    return {"total":0.0,"n":0}

def _contracts_count(jurs):
    try:
        rows=json.load(open(HANDS,encoding="utf-8")).get("rows",[])
    except Exception:
        return None
    return sum(1 for r in rows if (r.get("jurisdiction") or "") in jurs)

def page(slug, gen, sm):
    office_key, name, tenant, jurs = COUNTIES[slug]
    money=_office(sm.get("by_office",[]), office_key)
    re_money=_office(sm.get("realestate_by_office",[]), office_key)
    n_contracts=_contracts_count(jurs)
    re_pct = (100.0*re_money["total"]/money["total"]) if money["total"] else 0.0
    # honest contract-gap sentence
    if n_contracts is None:
        gapline="Contract-award open data could not be read this build."
    elif n_contracts==0:
        gapline=("<b>No</b> contract awards for this county appear in the State's HANDS open-data awards feed — so "
                 "contracts&times;donors parity cannot be computed here yet. That the county's spending is not in open "
                 "data is itself the question worth pressing.")
    else:
        gapline=("Only <b>%d</b> award(s) for this county appear in the HANDS open-data feed — too thin for an honest "
                 "contracts&times;donors parity. The gap is the county's, not the record's." % n_contracts)
    html=("<!doctype html><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'>"
      "<title>%s — who funds the council | govOS</title><style>"
      "body{font-family:'Segoe UI',system-ui,sans-serif;max-width:900px;margin:1.3rem auto;padding:0 1rem;color:#eaf2fc;background:#081420}"
      "h1{font-size:1.5rem;margin:.3rem 0}h2{font-size:1.05rem;color:#7fb2ff;margin:1.3rem 0 .3rem}"
      ".sub{color:#9fb2c8;font-size:.9rem;line-height:1.5}"
      ".kpi{display:flex;flex-wrap:wrap;gap:1.4rem;margin:1rem 0}"
      ".kpi .n{font-family:Consolas,monospace;font-size:1.5rem;color:#7fb2ff;font-weight:700}"
      ".kpi .l{font-size:.72rem;letter-spacing:.4px;text-transform:uppercase;color:#8ea3ba}"
      ".disc{background:#0f2540;border:1px solid #1f3d5f;border-radius:10px;padding:.7rem 1rem;color:#9fb2c8;font-size:.85rem;margin:.8rem 0;line-height:1.5}"
      ".q{background:#241d0e;border:1px solid #5c4a1e;border-radius:10px;padding:.7rem 1rem;color:#e3c98a;font-size:.86rem;margin:.9rem 0;line-height:1.5}"
      ".re{background:#2a1416;border:1px solid #6a3030;border-radius:10px;padding:.7rem 1rem;color:#f0b0b0;font-size:.86rem;margin:.9rem 0;line-height:1.5}"
      "a{color:#6cb0f0}</style>"
      "<h1>%s — who funds the council</h1>"
      "<div class=sub>Every campaign contribution reported to candidates for the <b>%s</b>, from the Hawaiʻi Campaign "
      "Spending Commission public dataset. Giving is lawful — this maps the money so it can be read beside the votes.</div>"
      "<div class=kpi>"
      "<div><div class=n>$%s</div><div class=l>raised by the council</div></div>"
      "<div><div class=n>%s</div><div class=l>contributions</div></div>"
      "<div><div class=n>$%s</div><div class=l>from real-estate interests</div></div>"
      "<div><div class=n>%.0f%%</div><div class=l>real-estate share</div></div>"
      "</div>"
      "<div class=re><b>The real-estate slice.</b> Of the money raised, <b>$%s</b> across <b>%s</b> contributions came "
      "from real-estate interests (developers, brokerages, land holders). Where land-use and zoning sit before a "
      "council, that is the slice to watch — placed here as a question to verify, never an accusation.</div>"
      "<h2>Why there is no contracts&times;donors page here — yet</h2>"
      "<div class=disc>%s</div>"
      "<div class=q><b>The question.</b> Money is the input to a campaign; a vote is the output of the office. When a "
      "council's contracts are not published to open data, the public cannot set the two ledgers side by side — and "
      "the harder it is to read the money beside the votes, the more it matters that someone does.</div>"
      "<div class=disc>Source: Hawaiʻi Campaign Spending Commission — “Campaign Contributions Received By Hawaii State "
      "and County Candidates” (hicscdata.hawaii.gov, dataset jexd-xbcg), office = “%s”. Amounts cleaned and summed in "
      "Python. Real-estate slice from the same dataset, donor-employer/industry tagged. Documented facts and open "
      "questions, not findings of wrongdoing · generated %s.</div>"
      "<p class=sub style='margin-top:1rem'><a href='officials_%s.html'>who governs (%s roster)</a> &middot; "
      "<a href='tenant_%s.html'>%s overview</a> &middot; <a href='statewide_money_patterns.html'>statewide money patterns</a> "
      "&middot; <a href='tenants_hub.html'>all governments</a></p>")%(
      esc(name),esc(name),esc(name),usd(money["total"]),"{:,}".format(money["n"]),usd(re_money["total"]),re_pct,
      usd(re_money["total"]),"{:,}".format(re_money["n"]),gapline,esc(office_key),esc(gen),
      slug,esc(name),esc(tenant),esc(name),)
    fn="money_%s.html"%slug
    with open(os.path.join(M,fn),"w",encoding="utf-8",newline="\n") as f: f.write(html)
    return fn, money["total"], re_money["total"], n_contracts

def main():
    sm=json.load(open(SM,encoding="utf-8"))
    gen=datetime.now(HST).strftime("%Y-%m-%d %H:%M HST")
    print("money_county: building honest county campaign-money pages")
    for slug in COUNTIES:
        fn,tot,re_t,nc=page(slug,gen,sm)
        print("  %-8s $%s raised  $%s real-estate  contracts_in_opendata=%s -> %s"%(
            slug,usd(tot),usd(re_t),nc,fn))
    return 0

if __name__=="__main__":
    if sys.platform=="win32":
        import io; sys.stdout=io.TextIOWrapper(sys.stdout.buffer,encoding="utf-8",errors="replace")
    sys.exit(main())
