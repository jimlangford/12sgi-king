#!/usr/bin/env python3
# people_trace.py - the NEXT TRACE past real estate (Jimmy 2026-06-16): the PEOPLE and ORGANIZATIONS behind the
# money. From the Hawaiʻi Campaign Spending Commission contribution dataset (Socrata jexd-xbcg) we group every
# council contribution by EMPLOYER -> the organization behind the giving, and the executives/employees who give
# under it (contributor names + occupations). This widens the loop beyond real estate to ALL the money:
# contractors, ranches, hotels/tourism, unions, banks. (Board-of-directors/officers from the State business
# registry (BREG) is the next source after this — noted; this trace is the executives/employees who self-report
# their employer on the public record.)
#
# Output: public "organizations behind the money" page per tenant (Yale-blue, questions + curse-breaker) +
# a PRIVATE prosecutor JSON (org -> people, cross-referenced with the RE entities). Sourced; questions, not findings.
import os, sys, re, json, urllib.request, urllib.parse
HERE=os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path: sys.path.insert(0, HERE)
import moon_calendar as mc
from _quados_style import STYLE, moon_banner
from datetime import datetime, timedelta, timezone
HST=timezone(timedelta(hours=-10))
HOME=os.path.expanduser("~"); PROJ=os.path.join(HOME,"Documents","Claude","Projects","Video System elementLOTUS")
M=os.path.join(PROJ,"reports","mauios"); ST=os.path.join(PROJ,"reports","_status")
KING=[os.path.join(HOME,"AppData","Local","king-extract","deploy","king-local"),os.path.join(PROJ,"king-local")]
CSC="https://hicscdata.hawaii.gov/resource/jexd-xbcg.json"
UA="Mozilla/5.0 (compatible; KiloAupuni/1.0)"
def esc(s): return str(s if s is not None else "").replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
def usd(n): return "{:,.0f}".format(int(n or 0))
GEN={"retired","self-employed","self employed","self","none","n/a","na","not employed","not applicable",
     "homemaker","unemployed","","student","disabled","information requested","requested","none requested"}
GOV={"state of hawaii","county of maui","city and county of honolulu","county of hawaii","county of kauai",
     "state of hawaii judiciary","united states government","federal government"}
def core(n): return set(w for w in re.findall(r"[a-z0-9]+",(n or "").lower()) if len(w)>2 and w not in
                        {"the","and","of","llc","lp","inc","co","corp","ltd","company","group","hawaii","maui"})
# officer/executive titles in the CSC occupation field — the board/exec layer from the public record (BREG's
# own officer search is reCAPTCHA-gated, which we do NOT bypass; this is the self-reported executive who gives).
OFFICER_RX=re.compile(r"\b(president|owner|ceo|cfo|coo|chief|vice[ -]?president|vp|principal|partner|director|"
                      r"managing|manager|chair|founder|officer|executive|proprietor|broker[ -]?in[ -]?charge|"
                      r"principal broker)\b",re.I)

_OC=None
def oc_officers(name):
    """Registered officers (state registry via OpenCorporates) for an org, if oc_officers.py has run. Empty until."""
    global _OC
    if _OC is None:
        try: _OC=json.load(open(os.path.join(ST,"oc_officers.json"),encoding="utf-8")).get("orgs",{})
        except Exception: _OC={}
    return (_OC.get(name) or _OC.get(name.upper()) or {}).get("officers",[])

TENANTS=[("maui","Maui County","hi-maui",["Maui Council"]),
         ("honolulu","City & County of Honolulu","hi-honolulu",["Honolulu Council"]),
         ("hawaii","Hawaiʻi County","hi-hawaii",["Hawaii Council"]),
         ("kauai","Kauaʻi County","hi-kauai",["Kauai Council"])]

def fetch_office(office, limit=8000):
    q={"$select":"contributor_name,employer,occupation,amount","$where":"office='%s'"%office.replace("'","''"),
       "$limit":str(limit)}
    url=CSC+"?"+urllib.parse.urlencode(q)
    try:
        return json.load(urllib.request.urlopen(urllib.request.Request(url,headers={"User-Agent":UA}),timeout=90))
    except Exception as e:
        print("  fetch fail %s: %s"%(office,str(e)[:70])); return []

def build_orgs(rows):
    orgs={}
    for r in rows:
        emp=(r.get("employer") or "").strip()
        if not emp or emp.lower() in GEN: continue
        try: amt=float(r.get("amount") or 0)
        except: amt=0
        nm=(r.get("contributor_name") or "").strip(); occ=(r.get("occupation") or "").strip()
        key=emp.upper()
        o=orgs.setdefault(key,{"name":emp,"total":0.0,"people":{},"occ":{},"officers":{}})
        o["total"]+=amt
        if nm: o["people"][nm]=o["people"].get(nm,0)+amt
        if occ and occ.lower() not in GEN: o["occ"][occ]=o["occ"].get(occ,0)+1
        if nm and occ and OFFICER_RX.search(occ):           # an officer/executive of this org, on the record
            o["officers"][nm]=occ
    return orgs

def re_entities():
    try:
        d=json.load(open(os.path.join(ST,"maui_re_report.json"),encoding="utf-8"))
        return set(core(e.get("entity","")) and frozenset(core(e.get("entity",""))) for e in d.get("entities",[]))
    except Exception: return set()

def page(slug,disp,tid,orgs,gen,mr,ao_po):
    ranked=sorted(orgs.values(),key=lambda o:-o["total"])
    nongov=[o for o in ranked if o["name"].lower() not in GOV][:25]
    rows=""
    for o in nongov:
        ppl=sorted(o["people"].items(),key=lambda x:-x[1])
        off=o.get("officers",{})
        off_line=("<div class=ofx><b>Officers &amp; executives on the record:</b> "+
                  ", ".join("%s <span class=ti>(%s)</span>"%(esc(n),esc(t)) for n,t in sorted(off.items())[:8])+"</div>") if off else ""
        reg=oc_officers(o["name"])
        if reg:
            off_line+=("<div class=ofx style='background:#0f2540;border-color:#1f3d5f'>"
                       "<b>Registered officers (state registry):</b> "+
                       ", ".join("%s <span class=ti>(%s)</span>"%(esc(r.get('name')),esc(r.get('position') or 'officer')) for r in reg[:10])+"</div>")
        names=", ".join(esc(n) for n,_ in ppl[:6])+(" +%d more"%(len(ppl)-6) if len(ppl)>6 else "")
        rows+=("<div class=org><div class=oh><b>%s</b><span class=ot>$%s &middot; %d giver(s) &middot; %d officer(s)</span></div>"
               "%s<div class=op>givers incl.: %s</div></div>")%(esc(o["name"]),usd(o["total"]),len(o["people"]),len(off),off_line,names)
    total_orgs=len([o for o in ranked if o["name"].lower() not in GOV])
    sup=("<style>.org{border:1px solid var(--line);border-radius:12px;padding:.7rem 1rem;margin:.5rem 0;background:var(--panel)}"
         ".org .oh{display:flex;justify-content:space-between;gap:10px;flex-wrap:wrap;align-items:baseline}"
         ".org .oh b{color:var(--accent);font-size:1.02rem}.org .ot{font:600 12px/1 'JetBrains Mono',Consolas,monospace;color:var(--accent2)}"
         ".org .op{color:var(--dim);font-size:.9rem;margin-top:.35rem;line-height:1.45}"
         ".org .ofx{font-size:.9rem;color:#13243d;background:#0f2540;border:1px solid #bfe0cc;border-radius:8px;padding:.45rem .7rem;margin:.4rem 0;line-height:1.5}"
         ".org .ofx .ti{color:#1f5a3c;font-family:Consolas,monospace;font-size:.8rem}</style>")
    cb=("<div class=cb>&#9790;&#9728; <b>Curse-breaker.</b> Under tonight's %s, an organization&rsquo;s people giving "
        "together is lawful and ordinary &mdash; the question is only whether a later decision answers the public or "
        "the people who funded the seat. The official can <b>disclose, recuse, or decide in the open</b>; the "
        "organization can <b>say plainly what it seeks</b>. Aloha is the ask.</div>")%(esc(mr.get("po","") or "moon"))
    head="<!doctype html><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'><title>%s — the organizations behind the money | govOS</title>"%esc(disp)
    intro=("<div class=wrap><div class=sub style='letter-spacing:.1em;text-transform:uppercase;color:var(--accent2);font-weight:600'>"
           "govOS &middot; %s &middot; asked in aloha</div><h1>The organizations behind the money</h1>")%esc(disp)
    pono=("<div class=pono>Past the individual checks: who do the givers <b>work for</b>? Grouping every contribution to "
          "this council by the donor&rsquo;s <b>employer</b> shows the organizations &mdash; developers, contractors, "
          "ranches, hotels, unions, banks &mdash; and the executives &amp; employees who give under each. Public record; "
          "a <b>question to verify</b>, never a finding. (Boards &amp; officers from the State business registry are the next trace.)</div>")
    h2="<h2>Top organizations by combined giving (%d in all)</h2>"%total_orgs
    _tf=(" &middot; <a href='testifiers_%s.html'>who testifies &times; money</a>"%slug) if slug=="maui" else ""
    nav=("<p class=sub style='margin-top:1rem'><a href='realestate_%s.html'>money &times; votes (overview)</a>%s &middot; "
         "<a href='tenant_%s.html'>%s overview</a> &middot; <a href='tenants_hub.html'>all governments</a></p>")%(slug,_tf,tid,esc(disp))
    foot=("<div class=foot>Source: Hawaiʻi Campaign Spending Commission (hicscdata jexd-xbcg), grouped by donor-reported "
          "employer; generic/retired/government-payroll employers set aside. Public record; questions, not findings &middot; "
          "generated %s.</div></div>")%esc(gen)
    html=head+STYLE+sup+intro+moon_banner(mr,ao_po)+pono+h2+rows+cb+nav+foot
    fn="orgs_%s.html"%slug
    open(os.path.join(M,fn),"w",encoding="utf-8",newline="\n").write(html)
    return fn,nongov

def main():
    gen=datetime.now(HST).strftime("%Y-%m-%d %H:%M HST")
    today=datetime.now(HST).date().isoformat()
    mr=mc.reading(today) or {}; co=mc.creative_offering(today) or {}
    ao_po=co.get("ao_po") or ("Ao" if mr.get("phase") in ("waxing","full") else "Pō")
    priv={"generated":gen,"tenants":{}}
    for slug,disp,tid,offices in TENANTS:
        rows=[]
        for off in offices: rows+=fetch_office(off)
        orgs=build_orgs(rows)
        fn,top=page(slug,disp,tid,orgs,gen,mr,ao_po)
        priv["tenants"][tid]={"orgs":[{"name":o["name"],"total":round(o["total"]),"n_people":len(o["people"]),
                              "officers":[{"name":n,"title":t} for n,t in sorted(o.get("officers",{}).items())],
                              "people":sorted(o["people"],key=lambda n:-o["people"][n])[:20],
                              "occupations":sorted(o["occ"],key=lambda k:-o["occ"][k])[:5]} for o in
                              sorted(orgs.values(),key=lambda x:-x["total"])[:60]]}
        print("  %-9s %d orgs (non-generic), top: %s"%(slug,len(orgs),
              ", ".join("%s $%s"%(o["name"][:18],usd(o["total"])) for o in top[:3])))
    os.makedirs(ST,exist_ok=True)
    json.dump(priv,open(os.path.join(ST,"people_trace.json"),"w",encoding="utf-8"),indent=1,ensure_ascii=False)
    print("people_trace: public orgs_<tenant>.html + PRIVATE people_trace.json (org->people)")
    return 0

if __name__=="__main__":
    if sys.platform=="win32":
        import io; sys.stdout=io.TextIOWrapper(sys.stdout.buffer,encoding="utf-8",errors="replace")
    sys.exit(main())
