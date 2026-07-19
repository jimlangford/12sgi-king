#!/usr/bin/env python3
# connections.py - SURFACE THE LOOP (Jimmy 2026-06-16): the public "on the record" page. For each tenant it
# joins the donor ORGANIZATIONS to (a) what they gave the council, (b) what they transact in property / hold in
# contracts, (c) their officers/executives, and (d) the MEETINGS of the public record where their name appears
# (from the 2,293-meeting minutes corpus). Deep, clear, Yale-blue, mobile-first. Every line a QUESTION to verify,
# never a finding; the curse-breaker offers the pono path. Public record only.
#
# Output: connections_<tenant>.html (public) + reports/_status/connections.json (private working data).
import os, sys, re, json
HERE=os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path: sys.path.insert(0, HERE)
import moon_calendar as mc
from _quados_style import STYLE, moon_banner
from datetime import datetime, timedelta, timezone
HST=timezone(timedelta(hours=-10))
HOME=os.path.expanduser("~"); PROJ=os.path.join(HOME,"Documents","Claude","Projects","Video System elementLOTUS")
M=os.path.join(PROJ,"reports","mauios"); ST=os.path.join(PROJ,"reports","_status"); TXT=os.path.join(PROJ,"reports","minutes_text")
def esc(s): return str(s if s is not None else "").replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
def slugify(s): return re.sub(r"[^a-z0-9]+","_",s.lower()).strip("_")[:48]
def dossier_link(name):
    fn="entity_%s.html"%slugify(name)
    return (" &middot; <a href='%s'><b>full dossier &rarr;</b></a>"%fn) if os.path.exists(os.path.join(M,fn)) else ""
def usd(n): return "{:,.0f}".format(int(n or 0))
_NS_STOP={"hawaii","hawai","maui","oahu","kauai","honolulu","county","council","state","general","public",
          "department","office","committee","meeting","member","members","chair"}
ENT=re.compile(r"\b(llc|lp|inc|corp|co|company|ltd|llp|lllp|pac|assoc|association|ranch|farms?|development|"
               r"resort|properties|realty|holdings|group|trust|partners|bank|hotel|enterprises|builders|construction|brothers|bros)\b",re.I)
TEN=[("maui","Maui County","hi-maui","Maui Council"),("honolulu","City & County of Honolulu","hi-honolulu","Honolulu Council"),
     ("hawaii","Hawaiʻi County","hi-hawaii","Hawaii Council"),("kauai","Kauaʻi County","hi-kauai","Kauai Council")]

def _meta(path):
    try:
        head="".join(open(path,encoding="utf-8").readlines()[:2])
        m=re.search(r"MINUTES \| (\S+) \| (.*?) \| (.*)",head)
        return (m.group(1),m.group(3).strip()) if m else ("?","")
    except Exception: return ("?","")

def matchers():
    prof=json.load(open(os.path.join(M,"donor_profiles.json"),encoding="utf-8"))
    if isinstance(prof,dict): prof=list(prof.values())
    out={}
    for p in prof:
        for d in (p.get("realestate",{}) or {}).get("donors",[]):
            nm=(d.get("name") or "").strip()
            if not nm: continue
            if ENT.search(nm):
                toks=[w.upper() for w in re.findall(r"[A-Za-z]{4,}",nm) if w.lower() not in _NS_STOP]
                if len(toks)>=2: out[nm]=("org",toks)
            elif "," in nm:
                sur=re.findall(r"[A-Za-z]{3,}",nm.split(",")[0]); giv=re.findall(r"[A-Za-z]{3,}",nm.split(",",1)[1])
                if sur and giv:
                    s=re.escape(sur[0].upper()); g=re.escape(giv[0].upper())
                    out[nm]=("person",re.compile(r"\b%s\b[ .A-Z]{0,8}\b%s\b|\b%s,?\s+%s\b"%(g,s,s,g)))
    return out

def sweep():
    """org/person -> {tenant -> [dates]} across the whole minutes corpus."""
    mts=matchers(); blob=[]
    for root,_d,fs in os.walk(TXT):
        for f in fs:
            if f.endswith(".txt"):
                p=os.path.join(root,f); tid,date=_meta(p)
                blob.append((tid,date,open(p,encoding="utf-8",errors="replace").read().upper()))
    hits={}
    for nm,(kind,m) in mts.items():
        per={}
        for tid,date,txt in blob:
            ok=all(tok in txt for tok in m) if kind=="org" else bool(m.search(txt))
            if ok: per.setdefault(tid,[]).append(date or "?")
        if per: hits[nm]={"kind":kind,"by_tenant":{t:sorted(set(ds),reverse=True) for t,ds in per.items()}}
    return hits

def load_money():
    giving={}  # org_upper -> {total, officers, tenants}
    try:
        pt=json.load(open(os.path.join(ST,"people_trace.json"),encoding="utf-8"))
        for tid,d in pt.get("tenants",{}).items():
            for o in d.get("orgs",[]):
                giving.setdefault(o["name"].upper(),{"total":0,"officers":[],"name":o["name"]})
                g=giving[o["name"].upper()]; g["total"]=max(g["total"],o.get("total",0)); g["officers"]=o.get("officers",[]) or g["officers"]
    except Exception: pass
    tx={}      # entity_upper -> {transacted, role}
    try:
        rr=json.load(open(os.path.join(ST,"maui_re_report.json"),encoding="utf-8"))
        for e in rr.get("entities",[]):
            tx[e["entity"].upper()]={"transacted":e.get("tx_value",0),"role":e.get("role"),"donated":e.get("donated",0)}
    except Exception: pass
    return giving,tx

def card(name,kind,dates,mr,giving,tx):
    gv=giving.get(name.upper(),{}); txe=None
    for k,v in tx.items():
        if name.upper() in k or k in name.upper(): txe=v; break
    given=gv.get("total",0) or (txe or {}).get("donated",0)
    transacted=(txe or {}).get("transacted",0); role=(txe or {}).get("role")
    officers=gv.get("officers",[])[:5]
    n=len(dates); recent=", ".join(esc(d) for d in dates[:8] if d and d!="?")
    kpis=("<div class=kpis style='margin:.5rem 0'>"
          "<div class=kp><div class=kv>%d</div><div class=kl>meetings on the record</div></div>"
          +("<div class=kp><div class=kv>$%s</div><div class=kl>given to the council</div></div>"%usd(given) if given else "")
          +("<div class=kp><div class=kv>$%s</div><div class=kl>property transacted</div></div>"%usd(transacted) if transacted else "")
          +"</div>")
    offline=("<div class=op><b>Officers/execs:</b> "+", ".join("%s (%s)"%(esc(o.get('name')),esc(o.get('position') or o.get('title') or 'officer')) for o in officers)+"</div>") if officers else ""
    q=("<b>%s</b>%s gave to this council and its name appears in <b>%d meeting(s)</b> of the public record%s. "
       "Does each decision answer the public, or the giving? A <b>question to verify</b> — never a finding.%s")%(
       esc(name),(" (role: %s)"%esc(role)) if role else "",n,(", incl. "+recent) if recent else "",dossier_link(name))
    cb=("<div class=cb>&#9790;&#9728; Under tonight's %s, the pono path: the official can <b>disclose, recuse, or "
        "decide in the open</b>; the interest can <b>say plainly what it seeks</b>. Aloha is the ask.</div>")%(esc(mr.get("po","") or "moon"))
    return "<section class=e><div class=eh><h2>%s</h2><span class=role>%s</span></div>%s<div class=q>%s</div>%s%s</section>"%(
        esc(name),esc(role or ("PAC/Assoc" if "PAC" in name.upper() or "ASSOC" in name.upper() else "organization")),kpis,q,offline,cb)

def main():
    gen=datetime.now(HST).strftime("%Y-%m-%d %H:%M HST")
    today=datetime.now(HST).date().isoformat()
    mr=mc.reading(today) or {}; co=mc.creative_offering(today) or {}
    ao_po=co.get("ao_po") or ("Ao" if mr.get("phase") in ("waxing","full") else "Pō")
    hits=sweep(); giving,tx=load_money()
    json.dump({"generated":gen,"hits":{k:v["by_tenant"] for k,v in hits.items()}},
              open(os.path.join(ST,"connections.json"),"w",encoding="utf-8"),indent=1,ensure_ascii=False)
    sup="<style>.e .role{font:600 10.5px/1 Consolas,monospace;letter-spacing:.04em;text-transform:uppercase;color:#1f5a3c;background:#0f2540;border:1px solid #bfe0cc;border-radius:99px;padding:3px 9px}.op{color:var(--dim);font-size:.9rem;margin:.3rem 0;line-height:1.45}</style>"
    made=[]
    for slug,disp,tid,office in TEN:
        # orgs/persons whose name appears in THIS tenant's minutes, ranked by meeting count
        rows=[]
        ents=[(nm,h) for nm,h in hits.items() if tid in h["by_tenant"]]
        ents.sort(key=lambda x:-len(x[1]["by_tenant"][tid]))
        for nm,h in ents[:30]:
            rows.append(card(nm,h["kind"],h["by_tenant"][tid],mr,giving,tx))
        head="<!doctype html><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'><title>%s — the loop, on the record | govOS</title>"%esc(disp)
        body=("<div class=wrap><div class=sub style='letter-spacing:.1em;text-transform:uppercase;color:var(--accent2);font-weight:600'>"
              "govOS &middot; %s &middot; asked in aloha</div><h1>The loop, on the record</h1>"%esc(disp)
              +moon_banner(mr,ao_po)
              +("<div class=pono>The interests that <b>fund</b> the council and <b>transact</b> here also appear in its "
                "<b>meeting record</b>. Below: each organization, what it gave, what it transacts, who its officers are, "
                "and the <b>%d-meeting</b> public record where its name shows up. Every line is a <b>question to verify</b> "
                "(name match &mdash; confirm identity), never a finding. Source: council minutes + Hawaiʻi Campaign "
                "Spending Commission + Maui County records.</div>"%len([1 for nm,h in ents]))
              +("<h2>Donor organizations in %s&rsquo;s record (%d found)</h2>"%(esc(disp),len(ents)))
              +("".join(rows) or "<div class=pono>No donor-organization name matches in this tenant's ingested minutes yet.</div>")
              +("<p class=sub style='margin-top:1rem'><a href='entity_index.html'>deep dossiers &rarr;</a> &middot; "
                "<a href='realestate_%s.html'>money &times; votes</a> &middot; "
                "<a href='orgs_%s.html'>organizations behind the money</a> &middot; "
                "%s<a href='tenant_%s.html'>%s overview</a> &middot; "
                "<a href='tenants_hub.html'>all governments</a></p>"%(slug,slug,
                ("<a href='testifiers_maui.html'>who testifies &times; money</a> &middot; " if slug=="maui" else ""),
                tid,esc(disp)))
              +("<div class=foot>Name matches are questions to verify (org = full name; person = adjacent name-phrase). "
                "Public record; questions, not findings &middot; generated %s.</div></div>"%esc(gen)))
        fn="connections_%s.html"%slug
        open(os.path.join(M,fn),"w",encoding="utf-8",newline="\n").write(head+STYLE+sup+body)
        made.append((slug,len(ents)))
    print("connections: per-tenant 'on the record' pages")
    for s,n in made: print("  connections_%s.html — %d donor entities on the record"%(s,n))
    return 0

if __name__=="__main__":
    if sys.platform=="win32":
        import io; sys.stdout=io.TextIOWrapper(sys.stdout.buffer,encoding="utf-8",errors="replace")
    sys.exit(main())
