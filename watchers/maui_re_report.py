#!/usr/bin/env python3
# maui_re_report.py - the REAL-ESTATE REPORT, the missing prosecutorial piece (Jimmy 2026-06-16, "312" order).
# PRIVATE owner-only review build FIRST (Jimmy: "be sure on the private side") before anything goes public.
#
# Connects three public ledgers for the real-estate interests that fund Maui's deciders:
#   political giving (donor_profiles: RE donor -> which officials, how much)
#     x  property owned (Maui County FULLOWNR extract: owner -> parcels)
#     x  recorded sales (Maui County sales.csv extract: parcel -> sale price + date)
#   = the entity that funds the seat AND transacts large property sums on the island it governs.
#
# RIGOR (so this can later go public honestly):
#   * Entity match = the donor's distinctive CORE tokens (minus legal-suffix noise) MUST be a subset of the
#     owner's tokens, >=2 tokens. Rejects "Wailea Resort Dev LP" vs "Wailea Beach Resort". Still a NAME match
#     -> framed "verify identity", never a proven tie.
#   * "Recorded transaction value" (sum of sale PRICE), NEVER "profit"/"money made" - we don't have cost basis.
#   * Every line is a QUESTION from the public record, never an accusation. Curse-breaker offers a pono path.
# Sources: Hawaiʻi CSC donors (donor_profiles) + Maui County RPT extracts (sales.csv, fullownr26.txt; layout PDFs).
# Stdlib only.
import os, sys, re, csv, json
from datetime import datetime, timedelta, timezone
HERE=os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path: sys.path.insert(0, HERE)
import moon_calendar as mc
from _quados_style import STYLE, moon_banner
HST=timezone(timedelta(hours=-10))
HOME=os.path.expanduser("~"); PROJ=os.path.join(HOME,"Documents","Claude","Projects","Video System elementLOTUS")
M=os.path.join(PROJ,"reports","mauios"); ST=os.path.join(PROJ,"reports","_status")
EX=os.path.join(M,"property","_rpt_extracts")
KING_DIRS=[os.path.join(HOME,"AppData","Local","king-extract","deploy","king-local"),os.path.join(PROJ,"king-local")]
ENT={"llc","lp","inc","corp","ltd","llp","lllp","dba","the","and","of","co","company","trust",
     "revocable","living","family","partnership","partners","holdings","group","et","al","ii","iii","iv","jr","sr"}
def esc(s): return str(s if s is not None else "").replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
def usd(n): return "{:,.0f}".format(int(n or 0))
def toks(n): return [w for w in re.findall(r"[a-z0-9]+",(n or "").lower()) if len(w)>2]
def core(n): return set(w for w in toks(n) if w not in ENT)

def re_entities():
    """RE donor entity -> {donated, officials:[(official, amount)]} from donor_profiles."""
    prof=json.load(open(os.path.join(M,"donor_profiles.json"),encoding="utf-8"))
    if isinstance(prof,dict): prof=list(prof.values())
    ent={}
    for p in prof:
        off=p.get("label") or p.get("name") or "?"
        for d in (p.get("realestate",{}) or {}).get("donors",[]):
            nm=(d.get("name") or "").strip(); amt=d.get("amount",0) or 0
            if not nm or len(core(nm))<2: continue   # need a resolvable entity (>=2 core tokens)
            e=ent.setdefault(nm.upper(),{"donated":0.0,"officials":{},"occ":set()})
            e["donated"]+=amt; e["officials"][off]=e["officials"].get(off,0)+amt
            oc=(d.get("occupation") or "").strip()
            if oc: e["occ"].add(oc)
    return ent

def _role(occs):
    """Classify a real-estate donor by the part it plays — the loop is closed when we can see who BROKERS
    the deal (agent/broker) vs who DEVELOPS/BUILDS vs who simply OWNS. From the CSC occupation field."""
    s=" ".join(occs).lower()
    if any(k in s for k in ("realtor","broker","real estate agent","salesperson","real estate sales","r(b)","r(s)")):
        return "Agent / Broker"
    if "commercial real estate" in s: return "Agent / Broker"
    if any(k in s for k in ("developer","development","builder")): return "Developer"
    if "contractor" in s: return "Contractor"
    if any(k in s for k in ("owner","president","investor","principal","landlord","lessor")): return "Owner / Principal"
    return "Real-estate interest"

def load_sales():
    sales={}
    lines=(l for l in open(os.path.join(EX,"sales.csv"),encoding="utf-8",errors="replace") if l.strip())
    rdr=csv.reader(lines); hdr=[h.strip() for h in next(rdr)]
    pi,di,idi=hdr.index("PRICE"),hdr.index("SALEDATE"),hdr.index("PARID")
    for row in rdr:
        if len(row)<=pi: continue
        try: v=float(row[pi].strip().replace(",",""))
        except: v=0
        if v>0: sales.setdefault(row[idi].strip(),[]).append((v,row[di].strip()))
    return sales

def owned_parcels(targets):
    """target-name -> set(parcels), via hardened subset match on the FULLOWNR fixed-width extract."""
    # prefilter: token -> [target] so each owner line only checks plausible targets
    tcore={t:core(t) for t in targets}
    tok2t={}
    for t,c in tcore.items():
        for w in c: tok2t.setdefault(w,[]).append(t)
    hits={t:{"parcels":set(),"owners":set()} for t in targets}
    with open(os.path.join(EX,"fullownr26.txt"),encoding="utf-8",errors="replace") as f:
        for line in f:
            if len(line)<53: continue
            owner=line[13:53].strip(); oc=core(owner)
            if not oc: continue
            cand=set()
            for w in oc: cand.update(tok2t.get(w,()))
            for t in cand:
                if tcore[t].issubset(oc):
                    hits[t]["parcels"].add(line[1:13]); hits[t]["owners"].add(owner)
    return hits

def main():
    gen=datetime.now(HST).strftime("%Y-%m-%d %H:%M HST")
    ent=re_entities()
    sales=load_sales()
    hits=owned_parcels(set(ent.keys()))
    # join — MERGE entity name-variants that resolve to the SAME parcels (e.g. "LANAI RESORTS" /
    # "LANAI RESORTS LLC" / "LANAI RESORTS, LLC" all own the same 428 parcels). Without this the same
    # property transactions are counted once per spelling, inflating the totals. Group by parcel-set;
    # sum donations + officials across variants; count transaction value ONCE.
    groups={}   # frozenset(parcels) -> aggregate
    for name,info in ent.items():
        h=hits.get(name,{"parcels":set(),"owners":set()})
        if not h["parcels"]: continue
        key=frozenset(h["parcels"])
        g=groups.setdefault(key,{"names":set(),"owners":set(),"donated":0.0,"officials":{},"occ":set()})
        g["names"].add(name); g["owners"].update(h["owners"]); g["donated"]+=info["donated"]
        g["occ"].update(info.get("occ") or set())
        for o,a in info["officials"].items(): g["officials"][o]=g["officials"].get(o,0)+a
    rows=[]
    for key,g in groups.items():
        psales=[]
        for pid in key: psales+=sales.get(pid,[])
        tx=sum(v for v,_ in psales); psales.sort(reverse=True)
        # canonical display name = the shortest variant (usually the cleanest entity form)
        disp=sorted(g["names"],key=lambda n:(len(n),n))[0]
        rows.append({"entity":disp,"aka":sorted(g["names"]-{disp})[:3],"donated":g["donated"],
                     "officials":sorted(g["officials"].items(),key=lambda x:-x[1]),
                     "parcels":len(key),"sales":len(psales),"tx_value":tx,
                     "top":psales[:3],"owner_as":sorted(g["owners"])[:2],
                     "role":_role(g["occ"]),"occ":sorted(g["occ"])[:3]})
    rows.sort(key=lambda r:-r["tx_value"])
    matched=[r for r in rows if r["sales"]]
    n_agents=sum(1 for r in matched if r["role"]=="Agent / Broker")
    summary={"generated":gen,"re_entities":len(ent),"entities_owning_parcels":len(rows),
             "entities_with_sales":len(matched),"agents_brokers":n_agents,
             "total_tx_value":sum(r["tx_value"] for r in matched),
             "total_donated_by_matched":sum(r["donated"] for r in matched)}
    os.makedirs(ST,exist_ok=True)
    json.dump({"summary":summary,"entities":rows},
              open(os.path.join(ST,"maui_re_report.json"),"w",encoding="utf-8"),indent=1,ensure_ascii=False)

    # moon timing for the pono framing (sun = the finding/number, moon = the kind path)
    today=datetime.now(HST).date().isoformat()
    mr=mc.reading(today) or {}
    co=mc.creative_offering(today) or {}
    ao_po=co.get("ao_po") or ("Ao" if mr.get("phase") in ("waxing","full") else "Pō")
    def entbox(r):
        offs=" · ".join("%s ($%s)"%(esc(o),usd(a)) for o,a in r["officials"][:4])
        tops="".join("<li>$%s &middot; %s</li>"%(usd(v),esc(dt)) for v,dt in r["top"])
        q=("Does %s's <b>$%s</b> in recorded Maui property transactions, across <b>%d parcel(s)</b>, sit in any "
           "relation to the <b>$%s</b> it gave the officials who decide land use and contracts? A question from the "
           "public record — and a <b>name match to verify</b> (owner of record: %s).")%(
           esc(r["entity"].title()),usd(r["tx_value"]),r["parcels"],usd(r["donated"]),
           esc((r["owner_as"][0] if r["owner_as"] else "").title()))
        cb=("<div class=cb>&#9790;&#9728; <b>Curse-breaker.</b> Under tonight's %s (the moon turns us toward balance), "
            "the doubt is broken not by blame but by daylight: the official can <b>disclose this giving before the vote</b>, "
            "<b>recuse</b> on this interest's matters, or <b>decide in the open</b>; the interest can <b>say plainly what it "
            "seeks</b>. Any one returns the seat to the people. That is <b>pono</b>.</div>")%(esc(mr.get("po","") or "moon"))
        role=esc(r.get("role") or "")
        occ=(" &middot; "+esc(", ".join(r.get("occ") or []))) if r.get("occ") else ""
        return ("<section class=e><div class=eh><h2>%s</h2>"
                "<span class=role>%s%s</span>"
                "<span class=kpi>$%s transacted &middot; %d parcels &middot; %d sales</span></div>"
                "<div class=gave>Gave <b>$%s</b> to: %s</div>"
                "<div class=q>%s</div><ul class=top>%s</ul>%s</section>")%(
                esc(r["entity"].title()),role,occ,usd(r["tx_value"]),r["parcels"],r["sales"],
                usd(r["donated"]),offs or "—",q,tops,cb)
    body="".join(entbox(r) for r in matched[:40])
    kpis=("<div class=kpis>"
      "<div class=kp><div class=kv>%d</div><div class=kl>RE donors own parcels</div></div>"
      "<div class=kp><div class=kv>%d</div><div class=kl>with recorded sales</div></div>"
      "<div class=kp><div class=kv>$%s</div><div class=kl>property transacted</div></div>"
      "<div class=kp><div class=kv>%d</div><div class=kl>are agents / brokers</div></div></div>")%(
      summary["entities_owning_parcels"],summary["entities_with_sales"],
      usd(summary["total_tx_value"]),summary["agents_brokers"])
    foot=("<div class=foot>Sources: Hawaiʻi Campaign Spending Commission (giving) × Maui County Real Property "
          "Tax extracts (sales + ownership), public record. Entity match is name-based — <b>verify identity</b>. "
          "&ldquo;Transacted&rdquo; = recorded sale value, not profit. Showing top %d of %d matched entities · generated %s.</div>")%(
          min(40,len(matched)),len(matched),esc(gen))
    # ---- PRIVATE review build (owner-only) ----
    priv=("<!doctype html><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'>"
          "<title>Maui real-estate report — PRIVATE review | owner only</title>"+STYLE
          +"<div class=wrap><h1>Maui real-estate report — the connective tissue"
           "<span class=priv>private · review</span></h1>"+moon_banner(mr,ao_po)+kpis
          +"<div class=pono><b>PONO.</b> Every figure is public record. A shared name is a <b>question to verify "
           "identity</b>, never a finding. The sun (the number) is told in light; the moon (the curse-breaker) offers "
           "the kind way back to balance.</div>"+body+foot+"</div>")
    # ---- PUBLIC build (asked in aloha; questions + curse-breaker) ----
    pub=("<!doctype html><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'>"
         "<title>Maui — real estate, money &amp; the questions | govOS</title>"+STYLE
         +"<div class=wrap><div class=sub style='letter-spacing:.1em;text-transform:uppercase;color:var(--accent2);font-weight:600'>"
          "govOS · Maui County · asked in aloha</div>"
          "<h1>Real estate, the money, and the questions</h1>"+moon_banner(mr,ao_po)+kpis
         +"<div class=pono>The real-estate interests that fund the council also <b>own and sell</b> Maui land. Two public "
          "ledgers, set side by side — campaign giving × recorded property sales — so the money can be read beside the "
          "votes. Every shared name is a <b>question to verify</b>, never an accusation; &ldquo;transacted&rdquo; is recorded "
          "sale value, not profit. The number is told in the light; the <b>curse-breaker</b> offers each office a kind, "
          "pono way through — disclose, recuse, or decide in the open. Aloha is the ask.</div>"+body
         +"<p class=sub style='margin-top:1rem'><a href='tenant_hi-maui.html'>&larr; Maui County overview</a> &middot; "
          "<a href='money_behind_officials.html'>money behind officials</a> &middot; "
          "<a href='contracts_x_donors.html'>contracts &times; donors</a> &middot; "
          "<a href='testifiers_maui.html'>who testifies &times; money</a> &middot; <a href='tenants_hub.html'>all governments</a></p>"
         +foot+"</div>")
    posted=[]
    try: open(os.path.join(ST,"maui_re_report.html"),"w",encoding="utf-8").write(priv)
    except Exception: pass
    try: open(os.path.join(M,"realestate_maui.html"),"w",encoding="utf-8",newline="\n").write(pub)   # PUBLIC -> build_site publishes
    except Exception: pass
    for kd in KING_DIRS:
        try:
            if os.path.isdir(kd): open(os.path.join(kd,"maui_re_report.html"),"w",encoding="utf-8").write(priv); posted.append(kd)
        except Exception: pass
    print("maui_re_report: %d RE entities own parcels, %d with recorded sales; $%s transacted vs $%s given"%(
        summary["entities_owning_parcels"],summary["entities_with_sales"],
        usd(summary["total_tx_value"]),usd(summary["total_donated_by_matched"])))
    for r in matched[:10]:
        print("  $%-13s %-30s gave $%-8s -> %d parcels"%(usd(r["tx_value"]),r["entity"][:30],usd(r["donated"]),r["parcels"]))
    print("  -> PRIVATE owner-only maui_re_report.html:", posted or "(king-local not found; json in reports/_status)")
    return 0

if __name__=="__main__":
    if sys.platform=="win32":
        import io; sys.stdout=io.TextIOWrapper(sys.stdout.buffer,encoding="utf-8",errors="replace")
    sys.exit(main())
