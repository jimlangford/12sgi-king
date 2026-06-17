#!/usr/bin/env python3
# realestate_county.py - per-tenant REAL-ESTATE × MONEY pages for the non-Maui tenants (Jimmy 2026-06-16:
# "do the rest of hawaii and other tenants with the realestate/contracts/donor data until complete").
# Maui has the full giving×property-sales loop (maui_re_report.py, realestate_maui.html). The others get the
# same FRAME from the data that exists today — real RE-donor money to the council (statewide_money
# realestate_by_office), the contracts lens where it's published, the money×votes parity where it exists —
# and an HONEST status for the property-sales loop (each county's RPT/RPAD sales extract is sourced as we go;
# Maui's is in hand). Public, Yale-blue, moon + curse-breaker + pono. Sourced-only; never invented.
import os, sys, json
from datetime import datetime, timedelta, timezone
HERE=os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path: sys.path.insert(0, HERE)
import moon_calendar as mc
from _quados_style import STYLE, moon_banner
HST=timezone(timedelta(hours=-10))
HOME=os.path.expanduser("~"); PROJ=os.path.join(HOME,"Documents","Claude","Projects","Video System elementLOTUS")
M=os.path.join(PROJ,"reports","mauios")
def esc(s): return str(s if s is not None else "").replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
def usd(n): return "{:,.0f}".format(int(n or 0))

# slug -> (display, tenant_id, [RE office key(s)], contracts_file, parity_file, property_status)
TENANTS=[
 ("honolulu","City & County of Honolulu","hi-honolulu",["Honolulu Council"],"contracts_honolulu.html","parity_honolulu.html",
  "Honolulu publishes parcel/assessment data (RPAD + Oʻahu open-geo); its recorded-sales extract is being sourced — when it lands, the giving×property loop completes here as it does for Maui."),
 ("hawaii","Hawaiʻi County","hi-hawaii",["Hawaii Council"],"contracts_hawaii.html",None,
  "Hawaiʻi County contract awards are not yet in the open-data feed, and its sales extract is being sourced. The donor side is real and shown; the loop completes as the county's records open."),
 ("kauai","Kauaʻi County","hi-kauai",["Kauai Council"],"contracts_kauai.html",None,
  "Kauaʻi County contract awards are near-absent from open data and its sales extract is being sourced. The donor side is real and shown; the loop completes as the records open."),
 ("state","State of Hawaiʻi","hi-state",["House","Senate","Governor","Lt. Governor"],"contracts_state.html","parity_state.html",
  "Statewide property transactions span all four counties; the per-island sales extracts are sourced county by county (Maui in hand). The statewide giving and contracts are shown."),
]

def _office(rows,keys):
    tot=0.0;n=0
    for r in rows:
        if r.get("office") in keys: tot+=r.get("total",0) or 0; n+=r.get("n",0) or 0
    return tot,n

def page(slug,disp,tid,keys,contracts,parity,prop_status,sm,gen,mr,ao_po):
    rbo=sm.get("realestate_by_office",[]); bo=sm.get("by_office",[])
    re_tot,re_n=_office(rbo,keys); raised,_=_office(bo,keys)
    share=(100.0*re_tot/raised) if raised else 0.0
    links=[]
    if os.path.exists(os.path.join(M,contracts)): links.append("<a href='%s'>contracts &amp; spending</a>"%contracts)
    if parity and os.path.exists(os.path.join(M,parity)): links.append("<a href='%s'>money &times; votes (parity)</a>"%parity)
    money_pg="money_%s.html"%slug
    if os.path.exists(os.path.join(M,money_pg)): links.append("<a href='%s'>who funds the council</a>"%money_pg)
    links.append("<a href='tenant_%s.html'>%s overview</a>"%(tid,esc(disp)))
    linkrow=" &middot; ".join(links)
    cb=("<div class=cb>&#9790;&#9728; <b>Curse-breaker.</b> Under tonight's %s, the path to pono is the same on every "
        "island: the official can <b>disclose</b> real-estate giving before a land-use or budget vote, <b>recuse</b> where "
        "the interest is direct, or <b>decide in the open</b>; the interest can <b>say plainly what it seeks</b>. Aloha is "
        "the ask — the record is the light.</div>")%(esc(mr.get("po","") or "moon"))
    head=("<!doctype html><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'>"
          "<title>%s — real estate, money &amp; the questions | govOS</title>"%esc(disp))+STYLE
    body=("<div class=wrap><div class=sub style='letter-spacing:.1em;text-transform:uppercase;color:var(--accent2);font-weight:600'>"
          "govOS &middot; %s &middot; asked in aloha</div><h1>Real estate, the money, and the questions</h1>"%esc(disp)
          +moon_banner(mr,ao_po)
          +("<div class=kpis>"
            "<div class=kp><div class=kv>$%s</div><div class=kl>real-estate money to the council</div></div>"
            "<div class=kp><div class=kv>%s</div><div class=kl>RE contributions</div></div>"
            "<div class=kp><div class=kv>%.0f%%</div><div class=kl>of all giving</div></div></div>")%(usd(re_tot),"{:,}".format(re_n),share)
          +("<div class=pono>The real-estate interests that fund <b>%s</b> also build and sell land here. Set the giving "
            "beside the votes and the contracts and read it as a <b>question</b>, never an accusation. Where land-use sits "
            "before an office, the money is the slice to watch.</div>"%esc(disp))
          +("<div class=e><div class=eh><h2>The property-sales loop</h2><span class=kpi>status</span></div>"
            "<div class=q>%s</div></div>"%prop_status)
          +cb
          +("<p class=sub style='margin-top:1rem'>%s &middot; <a href='realestate_maui.html'>Maui (full loop)</a> &middot; "
            "<a href='tenants_hub.html'>all governments</a></p>"%linkrow)
          +("<div class=foot>Source: Hawaiʻi Campaign Spending Commission (giving, office filter) + county records as they open. "
            "Public record; questions, not findings · generated %s.</div></div>"%esc(gen)))
    fn="realestate_%s.html"%slug
    with open(os.path.join(M,fn),"w",encoding="utf-8",newline="\n") as f: f.write(head+body)
    return fn,re_tot

def main():
    sm=json.load(open(os.path.join(M,"statewide_money.json"),encoding="utf-8"))
    gen=datetime.now(HST).strftime("%Y-%m-%d %H:%M HST")
    today=datetime.now(HST).date().isoformat()
    mr=mc.reading(today) or {}; co=mc.creative_offering(today) or {}
    ao_po=co.get("ao_po") or ("Ao" if mr.get("phase") in ("waxing","full") else "Pō")
    print("realestate_county: per-tenant RE×money pages")
    for slug,disp,tid,keys,contracts,parity,prop,*_ in TENANTS:
        fn,re_tot=page(slug,disp,tid,keys,contracts,parity,prop,sm,gen,mr,ao_po)
        print("  %-9s $%s RE money -> %s"%(slug,usd(re_tot),fn))
    return 0

if __name__=="__main__":
    if sys.platform=="win32":
        import io; sys.stdout=io.TextIOWrapper(sys.stdout.buffer,encoding="utf-8",errors="replace")
    sys.exit(main())
