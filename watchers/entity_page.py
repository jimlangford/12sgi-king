#!/usr/bin/env python3
# entity_page.py - DEEP per-organization dossiers (Jimmy 2026-06-16: "deepen a specific top organization into its
# own page — every meeting date + the bills it touched + its officers + its giving timeline"). For the top donor
# organizations it builds entity_<slug>.html: the giving timeline (every contribution: date/amount/office, from
# the CSC dataset), the property transacted (RE report), the officers/executives, and EVERY meeting of the public
# record where its name appears WITH the bill/topic context snippet from the minutes. Public record; questions,
# not findings; curse-breaker. Yale-blue. entity_index.html ties them together.
import os, sys, re, json, urllib.request, urllib.parse
HERE=os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path: sys.path.insert(0, HERE)
import moon_calendar as mc
from _quados_style import STYLE, moon_banner
from datetime import datetime, timedelta, timezone
HST=timezone(timedelta(hours=-10))
HOME=os.path.expanduser("~"); PROJ=os.path.join(HOME,"Documents","Claude","Projects","Video System elementLOTUS")
M=os.path.join(PROJ,"reports","mauios"); ST=os.path.join(PROJ,"reports","_status"); TXT=os.path.join(PROJ,"reports","minutes_text")
CSC="https://hicscdata.hawaii.gov/resource/jexd-xbcg.json"; UA="Mozilla/5.0 (compatible; KiloAupuni/1.0)"
def esc(s): return str(s if s is not None else "").replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
def usd(n): return "{:,.0f}".format(int(n or 0))
def slugify(s): return re.sub(r"[^a-z0-9]+","_",s.lower()).strip("_")[:48]
_STOP={"hawaii","hawai","maui","oahu","kauai","honolulu","county","council","state","general","the","and","of"}
TNAME={"hi-maui":"Maui","hi-honolulu":"Honolulu","hi-hawaii":"Hawaiʻi County","hi-kauai":"Kauaʻi","hi-state":"State"}

def org_tokens(nm): return [w.upper() for w in re.findall(r"[A-Za-z]{4,}",nm) if w.lower() not in _STOP]

def load_blob():
    blob=[]
    for root,_d,fs in os.walk(TXT):
        for f in fs:
            if f.endswith(".txt"):
                p=os.path.join(root,f)
                try: head="".join(open(p,encoding="utf-8").readlines()[:2])
                except Exception: continue
                mm=re.search(r"MINUTES \| (\S+) \| (.*?) \| (.*)",head)
                tid=mm.group(1) if mm else "?"; date=(mm.group(3).strip() if mm else "")
                blob.append((tid,date,open(p,encoding="utf-8",errors="replace").read()))
    return blob

def context_hits(tokens, blob, cap=40):
    """meetings where ALL tokens appear + a topic snippet around the first mention."""
    up=[t for t in tokens]; out=[]
    key=max(up,key=len)   # search on the most distinctive token, then confirm all
    for tid,date,text in blob:
        U=text.upper()
        if not all(t in U for t in up): continue
        i=U.find(key); a=max(0,i-160); b=min(len(text),i+160)
        snip=re.sub(r"\s+"," ",text[a:b]).strip()
        out.append({"tenant":tid,"date":date,"snippet":snip})
    out.sort(key=lambda x:x["date"],reverse=True)
    return out[:cap], len(out)

def giving(nm):
    """Contributions where this org is the contributor OR the employer (the timeline)."""
    tok=org_tokens(nm)
    if not tok: return [],0
    like=tok[0]   # distinctive token for a LIKE filter
    q={"$select":"date,amount,office,candidate_name,contributor_name,employer",
       "$where":"upper(contributor_name) like '%%%s%%' or upper(employer) like '%%%s%%'"%(like,like),
       "$order":"date desc","$limit":"400"}
    try:
        rows=json.load(urllib.request.urlopen(urllib.request.Request(CSC+"?"+urllib.parse.urlencode(q),headers={"User-Agent":UA}),timeout=60))
    except Exception: return [],0
    # keep rows where ALL tokens appear in contributor or employer (precise)
    keep=[]
    for r in rows:
        blobf=((r.get("contributor_name") or "")+" "+(r.get("employer") or "")).upper()
        if all(t in blobf for t in tok):
            try: amt=float(r.get("amount") or 0)
            except: amt=0
            keep.append({"date":(r.get("date") or "")[:10],"amount":amt,"office":r.get("office"),"to":r.get("candidate_name")})
    return keep, sum(x["amount"] for x in keep)

def officers(nm):
    try:
        pt=json.load(open(os.path.join(ST,"people_trace.json"),encoding="utf-8"))
        for tid,d in pt.get("tenants",{}).items():
            for o in d.get("orgs",[]):
                if o["name"].upper()==nm.upper(): return o.get("officers",[])
    except Exception: pass
    return []

def property_tx(nm):
    try:
        rr=json.load(open(os.path.join(ST,"maui_re_report.json"),encoding="utf-8"))
        for e in rr.get("entities",[]):
            if nm.upper() in e["entity"].upper() or e["entity"].upper() in nm.upper():
                return {"transacted":e.get("tx_value",0),"parcels":e.get("parcels",0),"role":e.get("role")}
    except Exception: pass
    return None

def dossier(nm, blob, mr, ao_po, gen):
    tok=org_tokens(nm)
    meets,total_m=context_hits(tok,blob)
    gives,total_g=giving(nm)
    offs=officers(nm); prop=property_tx(nm)
    # giving timeline by year
    by_year={}
    for g in gives: by_year[g["date"][:4]]=by_year.get(g["date"][:4],0)+g["amount"]
    yrs=sorted(by_year)
    tl="".join("<div class=tl><span class=ty>%s</span><span class=tb><i style='width:%d%%'></i></span><span class=tv>$%s</span></div>"%(
        esc(y),int(100*by_year[y]/max(by_year.values()) if by_year else 0),usd(by_year[y])) for y in yrs) if by_year else ""
    offline=("<div class=card><h2>Officers &amp; executives</h2><div class=op>"+
             ", ".join("%s <span class=ti>(%s)</span>"%(esc(o.get('name')),esc(o.get('position') or o.get('title') or 'officer')) for o in offs[:12])+
             "</div></div>") if offs else ""
    propline=("<div class=card><h2>Property</h2><div class=q>$%s in recorded Maui property transactions across %d parcel(s)%s. "
              "(See <a href='realestate_maui.html'>the deep real-estate loop</a>.)</div></div>")%(
              usd(prop["transacted"]),prop.get("parcels",0),(" — role: "+esc(prop.get("role"))) if prop.get("role") else "") if prop else ""
    mrows="".join("<div class=mtg><div class=mh><b>%s</b> &middot; %s</div><div class=ms>&hellip;%s&hellip;</div></div>"%(
        esc(TNAME.get(x["tenant"],x["tenant"])),esc(x["date"] or "?"),esc(x["snippet"])) for x in meets)
    head="<!doctype html><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'><title>%s — dossier | govOS</title>"%esc(nm)
    sup=("<style>.tl{display:grid;grid-template-columns:54px 1fr 92px;gap:10px;align-items:center;margin:.25rem 0;font-size:.85rem}"
         ".tl .ty{font-family:Consolas,monospace;color:var(--dim)}.tl .tb{background:var(--panel2);border-radius:99px;height:12px;overflow:hidden}"
         ".tl .tb i{display:block;height:12px;border-radius:99px;background:linear-gradient(90deg,var(--accent),var(--accent2))}"
         ".tl .tv{font-family:Consolas,monospace;color:var(--accent);text-align:right;font-size:.8rem}"
         ".card{border:1px solid var(--line);border-radius:12px;padding:.8rem 1rem;margin:.7rem 0;background:var(--panel)}"
         ".op{color:var(--dim);font-size:.92rem;line-height:1.5}.ti{color:#1f5a3c;font-family:Consolas,monospace;font-size:.8rem}"
         ".mtg{border-left:3px solid var(--accent);background:#0f2540;border-radius:8px;padding:.5rem .8rem;margin:.4rem 0}"
         ".mtg .mh{font-size:.92rem;color:var(--accent)}.mtg .ms{color:var(--dim);font-size:.84rem;font-style:italic;margin-top:.2rem;line-height:1.5}</style>")
    body=("<div class=wrap><div class=sub style='letter-spacing:.1em;text-transform:uppercase;color:var(--accent2);font-weight:600'>"
          "govOS &middot; dossier &middot; asked in aloha</div><h1>%s</h1>"%esc(nm)
          +moon_banner(mr,ao_po)
          +("<div class=kpis>"
            "<div class=kp><div class=kv>$%s</div><div class=kl>total contributed</div></div>"
            "<div class=kp><div class=kv>%d</div><div class=kl>contributions</div></div>"
            "<div class=kp><div class=kv>%d</div><div class=kl>meetings on the record</div></div>"
            +("<div class=kp><div class=kv>$%s</div><div class=kl>property transacted</div></div>"%usd(prop["transacted"]) if prop else "")
            +"</div>")%(usd(total_g),len(gives),total_m)
          +("<div class=pono>This is the public-record picture of <b>%s</b> — its giving, its property, its people, and "
            "every meeting of the council record where its name appears. Read it as a <b>question to verify</b> (name "
            "match), never a finding. The curse-breaker: the official can <b>disclose, recuse, or decide in the open</b>; "
            "the interest can <b>say plainly what it seeks</b>. Aloha is the ask.</div>"%esc(nm))
          +(("<div class=card><h2>Giving timeline</h2>%s</div>"%tl) if tl else "")
          +offline+propline
          +("<div class=card><h2>On the public record — %d meeting(s)%s</h2>%s</div>"%(
            total_m,(" (showing %d most recent)"%len(meets)) if total_m>len(meets) else "",mrows or "<div class=q>No minutes mentions found.</div>"))
          +("<p class=sub style='margin-top:1rem'><a href='entity_index.html'>&larr; all dossiers</a> &middot; "
            "<a href='connections_maui.html'>the loop, on the record</a> &middot; <a href='tenants_hub.html'>all governments</a></p>")
          +("<div class=foot>Sources: Hawaiʻi Campaign Spending Commission (giving) + council minutes (mentions) + Maui "
            "County records (property). Name match = a question to verify identity. Public record; questions, not findings "
            "&middot; generated %s.</div></div>"%esc(gen)))
    fn="entity_%s.html"%slugify(nm)
    open(os.path.join(M,fn),"w",encoding="utf-8",newline="\n").write(head+STYLE+sup+body)
    return fn,{"name":nm,"file":fn,"given":round(total_g),"contributions":len(gives),"meetings":total_m,
               "transacted":round(prop["transacted"]) if prop else 0,"officers":len(offs)}

def main():
    gen=datetime.now(HST).strftime("%Y-%m-%d %H:%M HST")
    today=datetime.now(HST).date().isoformat()
    mr=mc.reading(today) or {}; co=mc.creative_offering(today) or {}
    ao_po=co.get("ao_po") or ("Ao" if mr.get("phase") in ("waxing","full") else "Pō")
    # top orgs = donor orgs with the most meetings on the record (connections.json), organizations only
    try: conn=json.load(open(os.path.join(ST,"connections.json"),encoding="utf-8")).get("hits",{})
    except Exception: conn={}
    ENT=re.compile(r"\b(llc|lp|inc|corp|co|company|pac|assoc|association|ranch|farms?|development|resort|properties|realty|holdings|group|hotel|brothers|bros|construction)\b",re.I)
    orgs=[(nm,sum(len(v) for v in bt.values())) for nm,bt in conn.items() if ENT.search(nm)]
    orgs.sort(key=lambda x:-x[1])
    # dedupe near-identical names (keep the first/longest-meeting variant)
    seen=set(); picked=[]
    for nm,n in orgs:
        k=tuple(sorted(org_tokens(nm)))
        if k in seen: continue
        seen.add(k); picked.append(nm)
        if len(picked)>=14: break
    blob=load_blob()
    idx=[]
    for nm in picked:
        fn,meta=dossier(nm,blob,mr,ao_po,gen); idx.append(meta)
        print("  %-32s give $%-9s %4d mtgs %s -> %s"%(nm[:32],usd(meta["given"]),meta["meetings"],
              ("$%s prop"%usd(meta["transacted"])) if meta["transacted"] else "",fn))
    # index page
    rows="".join("<a class=q href='%s'><div class=ql>%s</div><div class=qd>$%s given &middot; %d meetings on the record%s</div>"
                 "<div class=go>open dossier &rarr;</div></a>"%(esc(m["file"]),esc(m["name"]),usd(m["given"]),m["meetings"],
                 (" &middot; $%s property"%usd(m["transacted"])) if m["transacted"] else "") for m in idx)
    ih=("<!doctype html><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'><title>Dossiers — the organizations | govOS</title>"
        +STYLE+"<style>.qs{display:grid;grid-template-columns:1fr;gap:.7rem;margin:1rem 0}@media(min-width:620px){.qs{grid-template-columns:1fr 1fr}}"
        ".q{display:block;border:1px solid var(--line);border-radius:14px;padding:1rem;background:var(--panel);text-decoration:none}"
        ".q:hover{border-color:var(--accent)}.ql{font-weight:650;color:var(--ink);font-size:1.05rem}.qd{color:var(--dim);font-size:.9rem;margin:.25rem 0 .5rem}.go{color:var(--accent2);font-weight:600;font-size:.9rem}</style>"
        "<div class=wrap><div class=sub style='letter-spacing:.1em;text-transform:uppercase;color:var(--accent2);font-weight:600'>govOS &middot; asked in aloha</div>"
        "<h1>Dossiers — the organizations behind the money</h1>"+moon_banner(mr,ao_po)+
        "<div class=pono>A deep, public-record file on each top donor organization: its giving timeline, its property, "
        "its officers, and every meeting of the council record where its name appears. Questions to verify, never findings.</div>"
        "<div class=qs>"+rows+"</div>"
        "<p class=sub><a href='tenants_hub.html'>all governments</a> &middot; <a href='connections_maui.html'>the loop, on the record</a></p>"
        "<div class=foot>Public record; questions, not findings &middot; generated "+esc(gen)+"</div></div>")
    open(os.path.join(M,"entity_index.html"),"w",encoding="utf-8",newline="\n").write(ih)
    json.dump({"generated":gen,"dossiers":idx},open(os.path.join(ST,"entity_dossiers.json"),"w",encoding="utf-8"),indent=1,ensure_ascii=False)
    print("entity_page: %d dossiers + entity_index.html"%len(idx))
    return 0

if __name__=="__main__":
    if sys.platform=="win32":
        import io; sys.stdout=io.TextIOWrapper(sys.stdout.buffer,encoding="utf-8",errors="replace")
    sys.exit(main())
