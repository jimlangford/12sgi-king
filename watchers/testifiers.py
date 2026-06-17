#!/usr/bin/env python3
# testifiers.py - the TESTIFIER trace (Jimmy 2026-06-17: "also the testifiers et al"). Closes the loop the other
# way: the donors/contractors/RE pages show who gives & owns; the minutes show who SHOWS UP to testify on the
# bills. This walks the ingested minutes (.txt) corpus, extracts every named public testifier and the item(s)
# they testified on (+ the affiliation they named), aggregates per person, and CROSS-REFERENCES each testifier
# against the money record — donors (people_trace) and the RE entities (maui_re_report). The question that
# closes the loop: did the people who testify on a matter also fund the seat that decides it, or hold a
# contract/parcel interest in it? Public record on both sides; a QUESTION to verify, never an accusation.
#
# Output: public testifiers_<tenant>.html (Yale-blue, moon + curse-breaker) + PRIVATE testifiers.json
# (full per-person meeting/item/context for the prosecutor) + a PRIVATE searchable testifiers_index.txt.
import os, sys, re, json
HERE=os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path: sys.path.insert(0, HERE)
import moon_calendar as mc
from _quados_style import STYLE, moon_banner
from datetime import datetime, timedelta, timezone
HST=timezone(timedelta(hours=-10))
HOME=os.path.expanduser("~"); PROJ=os.path.join(HOME,"Documents","Claude","Projects","Video System elementLOTUS")
TXT=os.path.join(PROJ,"reports","minutes_text"); M=os.path.join(PROJ,"reports","mauios")
ST=os.path.join(PROJ,"reports","_status")
def esc(s): return str(s if s is not None else "").replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")

TENANTS=[("maui","Maui County","hi-maui"),("honolulu","City & County of Honolulu","hi-honolulu"),
         ("hawaii","Hawaiʻi County","hi-hawaii"),("kauai","Kauaʻi County","hi-kauai")]

# --- testifier line: TITLE NAME [. AFFILIATION] (testifying on ITEM...) ; OCR garbles "testifying"->testifvina etc.
TITLE=r"(?:MR|MS|MRS|MISS|DR|MAYOR|COUNCIL ?MEMBER|REP|SEN|REPRESENTATIVE|SENATOR)"
# trigger = optional "(" or stray OCR "f", then test... then "on/in" — tolerant of OCR (testifvina/testifvinq/etc.)
TRIG=re.compile(r"[\(\[]?\s*f?test[a-z]*v?[a-z]*\s+(?:on|in)\b",re.I)
LINE=re.compile(r"^\s*(%s)\b\.?\s+([A-Z][A-Z0-9'’.\- ]{2,60}?)(?=\s*[\(\[]|\s+f?test|\s*\.\s+[A-Z]{2}|$)"%TITLE)
ITEM=re.compile(r"\b(\d{2}-\d{2,4})\b")
ITEMKIND=re.compile(r"(County Communication|General Communication|Committee Report|Bill|Resolution|Ordinance)",re.I)
_STOP_NAME={"THE","AND","OF","FOR","ON","TO","NO","NOS","AN","A","ITEM","ITEMS","PHONE","ONLINE","VIA",
            "WHO","WAS","WHAT","WERE","ALSO","THEN","TESTIFYING","TESTIFIED","TESTIMONY","SPOKE","STATED"}
# generic org words that must NOT be the sole basis for an affiliation->donor-org match (kills "international"/
# "management"/"community" false positives). A real match needs >=2 shared DISTINCTIVE tokens.
_ORG_GENERIC={"the","and","of","llc","inc","corp","ltd","llp","co","company","group","holdings","properties",
              "realty","associates","association","partners","enterprises","development","management","services",
              "international","community","foundation","program","planner","redevelopment","department","dept",
              "hawaii","hawai","maui","oahu","kauai","honolulu","county","state","city","council","office","center",
              "fund","trust","investments","investment","capital","property","ohana","aloha","island","pacific"}

def _norm_name(raw):
    """A testifier prefix -> (Given Surname display, given_lc, surname_lc) or None. Strict: 2-4 alpha tokens,
    each >=2 chars, all-caps (the formal roster form — skips lowercased dialogue like 'Mr. Morris. What item…')."""
    raw=raw.strip().rstrip(".,").strip()
    toks=[t for t in re.split(r"[ .]+",raw) if t]
    toks=[t for t in toks if re.fullmatch(r"[A-Z'’\-]{2,}",t) and t not in _STOP_NAME]
    if not (2<=len(toks)<=4): return None
    given=toks[0]; surname=toks[-1]
    if len(given)<2 or len(surname)<3: return None
    disp=" ".join(w.capitalize() for w in toks)
    return disp, given.lower(), surname.lower()

def _files(tenant):
    d=os.path.join(TXT,tenant)
    if not os.path.isdir(d): return
    for f in sorted(os.listdir(d)):
        if f.endswith(".txt"): yield os.path.join(d,f)

def _meta(path):
    try:
        head="".join(open(path,encoding="utf-8",errors="replace").readlines()[:3])
        m=re.search(r"MINUTES \| (\S+) \| (.*?) \| (.*)",head); src=re.search(r"SOURCE: (\S+)",head)
        return ((m.group(1),m.group(2).strip(),m.group(3).strip()) if m else ("?","",""),(src.group(1) if src else ""))
    except Exception: return ("?","",""),""

def extract(tenant):
    """people: surname_lc|given_lc -> {disp, count, dates:set, items:set, affil:set, ctx:[(date,item,url)]}"""
    people={}
    for p in _files(tenant):
        txt=open(p,encoding="utf-8",errors="replace").read()
        (tid,body,date),url=_meta(p)
        for ln in txt.splitlines():
            if not TRIG.search(ln): continue
            m=LINE.match(ln)
            if not m: continue
            tg=TRIG.search(ln); prefix=ln[m.start(2):tg.start()]
            # prefix may be "NAME" or "NAME. AFFILIATION" — split affiliation off the first interior period
            affil=""
            if ". " in prefix:
                nm_part, aff_part = prefix.split(". ",1)
                if re.search(r"[A-Za-z]",aff_part) and len(aff_part.strip())>3: affil=aff_part.strip().rstrip(".,")
                prefix=nm_part
            nn=_norm_name(prefix)
            if not nn: continue
            disp, g, s = nn
            suffix=ln[tg.end():]
            items=set(ITEM.findall(suffix))
            key="%s|%s"%(s,g)
            e=people.setdefault(key,{"disp":disp,"count":0,"dates":set(),"items":set(),"affil":set(),"ctx":[]})
            e["count"]+=1;
            if date: e["dates"].add(date)
            e["items"]|=items
            if affil and len(affil)<=60: e["affil"].add(affil.title())
            e["ctx"].append({"date":date,"items":sorted(items),"body":body,"url":url})
    return people

# ---- the money record, normalized for matching ----
def _toks(s): return [w for w in re.findall(r"[A-Za-z]{3,}",(s or "").lower())]
def load_donors(tid):
    """surname_lc -> set(given_first3) from people_trace people ('Last, First'), per tenant."""
    idx={}
    try: d=json.load(open(os.path.join(ST,"people_trace.json"),encoding="utf-8"))
    except Exception: return idx, set()
    orgnames=set()
    for o in d.get("tenants",{}).get(tid,{}).get("orgs",[]):
        orgnames.add(o.get("name",""))
        for nm in o.get("people",[]):
            if "," not in nm: continue
            sur=_toks(nm.split(",")[0]); giv=_toks(nm.split(",",1)[1])
            if sur and giv: idx.setdefault(sur[0],set()).add(giv[0][:3])
    return idx, orgnames
def load_re():
    """surname_lc->set(given3) and a list of org token-sets, from the Maui RE entities ('SURNAME, GIVEN' / org)."""
    persons={}; orgs=[]
    try: d=json.load(open(os.path.join(ST,"maui_re_report.json"),encoding="utf-8"))
    except Exception: return persons, orgs
    for e in d.get("entities",[]):
        nm=e.get("entity","")
        if "," in nm:
            sur=_toks(nm.split(",")[0]); giv=_toks(nm.split(",",1)[1])
            if sur and giv: persons.setdefault(sur[0],set()).add(giv[0][:3])
        else:
            t=set(w for w in _toks(nm) if w not in {"llc","inc","corp","ltd","the","company","group","hawaii","maui"})
            if len(t)>=1: orgs.append((nm,t))
    return persons, orgs

def donor_hit(s,g,idx):  return s in idx and g[:3] in idx[s]
def org_hit(affils, orgnames, re_orgs):
    """Affiliation named in testimony matches a money-record org ONLY on >=2 shared DISTINCTIVE tokens — generic
    words (management/international/community/foundation…) never carry a match alone. Returns matched org name."""
    def dist(s): return set(w for w in _toks(s) if w not in _ORG_GENERIC and len(w)>=3)
    for af in affils:
        at=dist(af)
        if len(at)<1: continue
        for on in list(orgnames)+[nm for nm,_ in re_orgs]:
            ot=dist(on)
            if len(ot)<1: continue
            shared=at & ot
            # strong: >=2 shared distinctive tokens, OR one side fully contained and that side has >=2 tokens
            if len(shared)>=2 or (shared and (at<=ot or ot<=at) and min(len(at),len(ot))>=2):
                return on
    return None

def _badges(e,slug,re_persons,donors,orgnames,re_orgs):
    nn=_norm_name(e["disp"].upper()); b=""
    if nn:
        _,g,s=nn
        if donor_hit(s,g,donors): b+="<a class=bdg bd-d href='orgs_%s.html'>also in the donor record</a>"%slug
        if slug=="maui" and s in re_persons and g[:3] in re_persons[s]:
            b+="<a class=bdg bd-r href='realestate_maui.html'>also in the real-estate record</a>"
    oh=org_hit(e["affil"],orgnames,re_orgs)
    if oh: b+="<a class=bdg bd-o href='orgs_%s.html'>stated org gives: %s</a>"%(slug,esc(oh[:30]))
    return b
def _card(e,badges):
    af=(" &middot; <span class=af>%s</span>"%esc(", ".join(sorted(e["affil"])[:2]))) if e["affil"] else ""
    items=", ".join(sorted(e["items"])[:8]); itx=(" +%d"%(len(e["items"])-8)) if len(e["items"])>8 else ""
    return ("<div class=tf><div class=th><b>%s</b>%s<span class=tc>%d appearance(s) &middot; %d item(s)</span></div>"
            "%s<div class=ti>items: %s%s</div></div>")%(esc(e["disp"]),af,e["count"],len(e["items"]),
            ("<div class=bds>"+badges+"</div>") if badges else "", items or "—", itx)
def page(slug,disp,tid,people,gen,mr,ao_po,re_persons,re_orgs,donors,orgnames):
    ranked=sorted(people.values(),key=lambda e:(-e["count"],-len(e["items"])))
    # the loop FIRST: testifiers who also appear in the money record (any frequency), then the frequent civic voices
    loop=[];
    for e in ranked:
        b=_badges(e,slug,re_persons,donors,orgnames,re_orgs)
        if b: loop.append((e,b))
    matched=len(loop)
    loop_rows="".join(_card(e,b) for e,b in loop) or ("<div class=tf><div class=ti>No top testifier in the available "
        "minutes also surfaces in the money record yet — the people who show up most are community voices. The full "
        "record keeps filling as more minutes are ingested.</div></div>")
    freq_rows="".join(_card(e,_badges(e,slug,re_persons,donors,orgnames,re_orgs)) for e in ranked[:40])
    rows=("<h2>The loop, on the record — testifiers who also appear in the money record (%d)</h2>%s"
          "<h2>Most frequent testifiers (top %d of %d) — who shows up</h2>%s")%(
          matched,loop_rows,min(40,len(ranked)),len(people),freq_rows)
    total=len(people)
    sup=("<style>.tf{border:1px solid var(--line);border-radius:12px;padding:.65rem 1rem;margin:.5rem 0;background:var(--panel)}"
         ".tf .th{display:flex;justify-content:space-between;gap:8px;flex-wrap:wrap;align-items:baseline}"
         ".tf .th b{color:var(--accent);font-size:1.02rem}.tf .tc{font:600 12px/1 'JetBrains Mono',Consolas,monospace;color:var(--accent2);white-space:nowrap}"
         ".tf .af{color:var(--accent2);font-size:.85rem}.tf .ti{color:var(--dim);font-size:.84rem;margin-top:.3rem;font-family:Consolas,monospace}"
         ".tf .bds{margin:.4rem 0 .1rem;display:flex;flex-wrap:wrap;gap:6px}"
         ".bdg{display:inline-block;font-size:.74rem;font-weight:600;text-decoration:none;border-radius:99px;padding:.18rem .6rem;border:1px solid}"
         ".bd-d{background:#fbf6ea;color:#5a4a16;border-color:#e6d8a8}.bd-r{background:#eef6f0;color:#1f5a3c;border-color:#bfe0cc}"
         ".bd-o{background:#eef2f7;color:#00356b;border-color:#bacde6}</style>")
    cb=("<div class=cb>&#9790;&#9728; <b>Curse-breaker.</b> Showing up to testify is the most ordinary, honorable "
        "civic act there is &mdash; a neighbor speaking to their government in the open. The only question this page "
        "asks is the narrow one: when a testifier <i>also</i> funds the seat or holds an interest in the matter, the "
        "decider can <b>disclose and recuse</b>, and the testifier can <b>say plainly whom they speak for</b>. Named in "
        "aloha, under tonight&rsquo;s %s &mdash; the record simply made legible, never an accusation.</div>")%esc(mr.get("po","") or "moon")
    head=("<!doctype html><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'>"
          "<title>%s — who testifies, and the money record | govOS</title>")%esc(disp)
    intro=("<div class=wrap><div class=sub style='letter-spacing:.1em;text-transform:uppercase;color:var(--accent2);font-weight:600'>"
           "govOS &middot; %s &middot; asked in aloha</div><h1>Who shows up to testify</h1>")%esc(disp)
    pono=("<div class=pono>From the public minutes: every named testifier and the item(s) they testified on, with the "
          "affiliation they stated. Each name is then checked against the public money record &mdash; campaign donors "
          "(<a href='orgs_%s.html'>organizations behind the money</a>)%s. A badge means the same name appears on both "
          "sides; that is a <b>question to verify</b> &mdash; identity and intent are for you to confirm &mdash; never a "
          "finding &mdash; identity and intent are for you to confirm. <b>%d</b> distinct testifiers found; "
          "<b>%d</b> also appear in the money record.</div>")%(
          slug,(" and the <a href='realestate_maui.html'>real-estate record</a>" if slug=="maui" else ""),
          total,matched)
    nav=("<p class=sub style='margin-top:1rem'><a href='orgs_%s.html'>organizations behind the money</a> &middot; "
         "<a href='realestate_%s.html'>money &times; votes</a> &middot; <a href='connections_%s.html'>the loop, on the record</a> "
         "&middot; <a href='tenant_%s.html'>%s overview</a> &middot; <a href='tenants_hub.html'>all governments</a></p>")%(
         slug,slug,slug,tid,esc(disp))
    foot=("<div class=foot>Source: official council/committee minutes (Granicus/CivicClerk), named public testimony; "
          "cross-referenced to Hawaiʻi Campaign Spending Commission donor data and county real-property records. "
          "Public record on every side; questions, not findings &middot; generated %s.</div></div>")%esc(gen)
    html=head+STYLE+sup+intro+moon_banner(mr,ao_po)+pono+rows+cb+nav+foot
    fn="testifiers_%s.html"%slug
    open(os.path.join(M,fn),"w",encoding="utf-8",newline="\n").write(html)
    return fn, matched, total

def main():
    gen=datetime.now(HST).strftime("%Y-%m-%d %H:%M HST")
    today=datetime.now(HST).date().isoformat()
    mr=mc.reading(today) or {}; co=mc.creative_offering(today) or {}
    ao_po=co.get("ao_po") or ("Ao" if mr.get("phase") in ("waxing","full") else "Pō")
    re_persons,re_orgs=load_re()
    priv={"generated":gen,"tenants":{}}; idx_lines=["TESTIFIERS — cross-referenced to the money record (PRIVATE). %s"%gen,""]
    for slug,disp,tid in TENANTS:
        people=extract(tid)
        if not people:
            print("  %-9s no named testifiers parsed (corpus thin)"%slug); continue
        donors,orgnames=load_donors(tid)
        fn,matched,total=page(slug,disp,tid,people,gen,mr,ao_po,re_persons,re_orgs,donors,orgnames)
        # private prosecutor record (every appearance + overlap flag)
        recs=[]
        for key,e in sorted(people.items(),key=lambda kv:-kv[1]["count"]):
            s,g=key.split("|")
            flags=[]
            if donor_hit(s,g,donors): flags.append("donor")
            if slug=="maui" and s in re_persons and g[:3] in re_persons[s]: flags.append("realestate")
            oh=org_hit(e["affil"],orgnames,re_orgs)
            if oh: flags.append("org:"+oh)
            recs.append({"name":e["disp"],"count":e["count"],"items":sorted(e["items"]),
                         "dates":sorted(e["dates"]),"affiliations":sorted(e["affil"]),"flags":flags,
                         "appearances":e["ctx"][:40]})
            if flags:
                idx_lines.append("%-26s x%-3d items:%s flags:%s%s"%(
                    e["disp"],e["count"],",".join(sorted(e["items"])[:6]) or "-",";".join(flags),
                    (" affil:"+", ".join(sorted(e["affil"])[:2])) if e["affil"] else ""))
        priv["tenants"][tid]={"file":fn,"n_testifiers":total,"n_matched":matched,"testifiers":recs[:400]}
        print("  %-9s %d testifiers, %d also in the money record -> %s"%(slug,total,matched,fn))
    os.makedirs(ST,exist_ok=True)
    json.dump(priv,open(os.path.join(ST,"testifiers.json"),"w",encoding="utf-8"),indent=1,ensure_ascii=False)
    open(os.path.join(ST,"testifiers_index.txt"),"w",encoding="utf-8",newline="\n").write("\n".join(idx_lines)+"\n")
    print("testifiers: public testifiers_<tenant>.html + PRIVATE testifiers.json + testifiers_index.txt")
    return 0

if __name__=="__main__":
    if sys.platform=="win32":
        import io; sys.stdout=io.TextIOWrapper(sys.stdout.buffer,encoding="utf-8",errors="replace")
    sys.exit(main())
