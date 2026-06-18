#!/usr/bin/env python3
# nay_narratives.py - the NAY NARRATIVES on "who governs" (Jimmy 2026-06-17: "show the committee votes on the
# who governs so we see the nay narratives"). votes_watch.py reads the live CivicClerk window and counts ayes/
# noes; this mines the FULL local minutes corpus (every ingested Maui meeting, the whole history) for the moments
# the council SPLIT — every recorded NO vote — and captures, for each: the item/motion, the aye/no roster (incl.
# FORMER members the current-roster parser would drop), and the NARRATIVE: the discussion around the vote and the
# dissenter's own recorded words (the "why"). Dissent is the record of conscience — honored, framed as a question
# ("what did the majority approve, and why did these members say no?"), never an accusation. Public record; links
# to source. Output: public council_votes_maui.html (Yale-blue, moon + curse-breaker) + PRIVATE nay_narratives.json.
import os, sys, re, json
HERE=os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path: sys.path.insert(0, HERE)
import moon_calendar as mc
from _quados_style import STYLE, moon_banner
try: from votes_watch import ROSTER
except Exception: ROSTER={}
from datetime import datetime, timedelta, timezone
HST=timezone(timedelta(hours=-10))
HOME=os.path.expanduser("~"); PROJ=os.path.join(HOME,"Documents","Claude","Projects","Video System elementLOTUS")
TXT=os.path.join(PROJ,"reports","minutes_text","hi-maui"); M=os.path.join(PROJ,"reports","mauios")
ST=os.path.join(PROJ,"reports","_status")
def esc(s): return str(s if s is not None else "").replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")

# member surnames are explicitly labelled in the vote roster lines; connector/role/non-member words to drop
_ROLE={"COUNCILMEMBER","COUNCILMEMBERS","COUNCIL","MEMBER","MEMBERS","VICE","CHAIR","VICECHAIR","VICE-CHAIR",
       "AND","THE","PRESIDING","OFFICER","PRO","TEM","MAYOR","NONE","NOES","AYES","EXCUSED","ABSENT","ABSTAIN",
       "DEPUTY","COUNTY","CLERK","CORPORATION","COUNSEL","DIRECTOR","NOT","PRESENT","MOTION","CARRIES","CARRIED"}
NAME_TOK=re.compile(r"[A-Z][A-Z'’\-]{2,}")
# the vote-tally header: "NOES:" (require the S and the colon — a bare "No" in dialogue is NOT a roll call)
NOES_HDR=re.compile(r"\bNOES\s*:",re.I)
AYES_HDR=re.compile(r"\bAYES\s*:",re.I)
ITEM_RE=re.compile(r"(Bill\s+No\.?\s*\d+|Bill\s+\d+|Resolution\s+No\.?\s*[\d-]+|Committee Report\s+No\.?\s*[\d-]+|"
                   r"County Communication\s+No\.?\s*[\d-]+|Ordinance\s+No\.?\s*[\d-]+|CC\s?\d{2}-\d+)",re.I)
TALLY_RE=re.compile(r"(\w+)\s+\"?ayes?\"?\s+and\s+(\w+)\s+\"?noes?\"?",re.I)
SPEAK_RE=lambda sur: re.compile(r"(?:COUNCIL ?MEMBER|CHAIR|VICE[- ]?CHAIR|MR\.?|MS\.?)\s+%s\s*:?\s*(.{0,360}?)(?=\n[A-Z][A-Z .]{3,}:|$)"%re.escape(sur),re.I|re.S)

def _members(seg):
    """surnames named in a vote-roster segment (caps tokens minus role/connector words)."""
    out=[]
    for t in NAME_TOK.findall(seg or ""):
        tt=t.replace("’","'")
        if tt.upper() in _ROLE: continue
        if tt not in out: out.append(tt)
    return out

# former Maui councilmembers who appear in the historical record but aren't on the current roster (no money profile)
_FORMER={"hokama":"Hokama","kama":"Kama","molina":"Molina","king":"King","carroll":"Carroll","crivello":"Crivello",
         "white":"White","guzman":"Guzman","cochran":"Cochran","atay":"Atay","victorino":"Victorino","hokama":"Hokama"}
def _short(full): return full.split(" - ")[0].strip()
def _disp(sur):
    """Canonical short name (First Last) — roster + former-member + OCR-tolerant, so 'Fernandez'/'Sinenc' don't
    split into phantom members. Falls back to Title-cased surname for anyone unrecognized."""
    s=sur.lower().replace("'","").replace("’","").replace("ʻ","")
    ss=s.replace("-","")
    if "fernandez" in s or s.startswith("rawlins"): return _short(ROSTER.get("Rawlins-Fernandez","Rawlins-Fernandez"))
    if "hodgins" in s: return _short(ROSTER.get("Uu-Hodgins","Uʻu-Hodgins"))
    for k,full in ROSTER.items():
        kk=k.lower().replace("-","").replace("ʻ","")
        if ss==kk or (len(ss)>=4 and kk.startswith(ss)) or (len(ss)>=5 and ss in kk): return _short(full)
    for fk,fv in _FORMER.items():
        if s==fk or (len(s)>=4 and s.startswith(fk[:4]) and fk.startswith(s[:4])): return fv
    return sur.title()

_PROFILES=None
def _profiles():
    """surname_lower -> {total, top, label} from donor_profiles.json (the money behind each current seat)."""
    global _PROFILES
    if _PROFILES is not None: return _PROFILES
    _PROFILES={}
    try:
        for p in json.load(open(os.path.join(M,"donor_profiles.json"),encoding="utf-8")):
            td=p.get("top_donors") or []
            _PROFILES[p["key"].lower()]={"total":p.get("total",0),
                "top":(td[0]["name"] if td else None),"label":p.get("label","")}
    except Exception: pass
    return _PROFILES
def _money_for(display):
    """campaign-money profile for a member display name (last-token surname, OCR/roster-tolerant)."""
    profs=_profiles(); sur=display.lower().split()[-1].replace("ʻ","").replace("'","")
    if "fernandez" in sur or "rawlins" in display.lower(): sur="rawlins-fernandez"
    if "hodgins" in sur: sur="uu-hodgins"
    if sur in profs: return profs[sur]
    for pk,v in profs.items():
        if sur==pk or (len(sur)>=4 and pk.startswith(sur)) or (len(sur)>=5 and sur in pk): return v
    return None

def _meta(path):
    head="".join(open(path,encoding="utf-8",errors="replace").readlines()[:3])
    m=re.search(r"MINUTES \| (\S+) \| (.*?) \| (.*)",head); src=re.search(r"SOURCE: (\S+)",head)
    return ((m.group(2).strip(),m.group(3).strip()) if m else ("","")),(src.group(1) if src else "")

def _seg_after(txt,pos,limit=170):
    """roster text after a header pos, across line wraps, up to the terminating period / next vote marker."""
    s=txt[pos:pos+limit].replace("\n"," ")
    # stop at the first period, or any following section marker (no newline required — OCR runs them together)
    s=re.split(r"\.\s|\b(?:AYES|NOES|EXCUSED|ABSENT|ABSTAIN|MOTION|COMMITTEE|MADAM|DEPUTY|RECUS)",s,1,re.I)[0]
    return re.sub(r"[ \t]+"," ",s).strip()

# OCR injects page headers/footers mid-sentence — strip them so narrative + quotes read as real speech
_BOILER=re.compile(r"(?:Regular|Special|Budget|Committee)?\s*Meeting\s*of[A-Za-z ]{0,45}Maui|"  # OCR joins words: "Councilofthe County of Maui"
                   r"Page\s+\d+\b|\b(?:January|February|March|April|May|June|July|August|September|October|November|"
                   r"December)\s+\d{1,2},?\s+\d{4}\b",re.I)
def _clean(s): return re.sub(r"\s+"," ",_BOILER.sub(" ",str(s or ""))).strip()
def _is_speech(q):
    """real recorded statement, not OCR debris: substantial, has sentence-like lowercase words, not header junk."""
    q=q.strip().lstrip(".,;:- ").strip()
    if len(q)<55: return False
    if len(re.findall(r"\b[a-z]{3,}\b",q))<7: return False     # needs real words, not all-caps fragments
    return True

def extract():
    """list of dissent events (each NOES with names), most-narrative-rich first."""
    events=[]
    for fn in sorted(os.listdir(TXT)):
        if not fn.endswith(".txt"): continue
        p=os.path.join(TXT,fn); txt=open(p,encoding="utf-8",errors="replace").read()
        (body,date),url=_meta(p)
        for nm in NOES_HDR.finditer(txt):
            seg=_seg_after(txt,nm.end())
            if "COUNCIL" not in seg.upper(): continue   # a real roll call names "COUNCILMEMBER(S) X"; skips "NOES: NONE"
            noes=_members(seg)
            if not noes: continue                       # "NOES: NONE" / empty -> not a split
            # AYES: nearest preceding within 900 chars
            ayes=[]; pre=txt[max(0,nm.start()-900):nm.start()]; ah=None
            for am in AYES_HDR.finditer(pre): ah=am
            if ah: ayes=_members(_seg_after(pre,ah.end()))
            # item: nearest ITEM_RE within +/-1400 chars (prefer closest)
            lo=max(0,nm.start()-1400); win=txt[lo:nm.start()+1400]; rel=nm.start()-lo
            its=[(abs(mm.start()-rel),_clean(mm.group(1))) for mm in ITEM_RE.finditer(win)]
            item=sorted(its)[0][1] if its else None
            # tally phrase ("seven ayes and two noes")
            tal=TALLY_RE.search(txt[nm.start():nm.start()+260])
            if tal: tally="%s ayes / %s noes"%(tal.group(1),tal.group(2))
            elif ayes: tally="%d aye / %d no"%(len(ayes),len(noes))
            else: tally="%d no (full count in source)"%len(noes)
            # narrative: discussion window before the vote
            narr=_clean(txt[max(0,nm.start()-650):nm.start()])[-460:]
            # the dissenter's OWN recorded words near the vote (strongest "why")
            quotes=[]
            for sur in noes[:3]:
                preq=txt[max(0,nm.start()-2600):nm.start()]
                for mq in reversed(list(SPEAK_RE(sur).finditer(preq))):
                    q=_clean(mq.group(1)).lstrip(".,;:- ").strip()
                    if _is_speech(q): quotes.append((_disp(sur),q[:300])); break
            events.append({"date":date,"body":body,"url":url,"item":item,"motion_narrative":narr,
                           "ayes":[_disp(a) for a in ayes],"noes":[_disp(n) for n in noes],
                           "tally":tally,"quotes":quotes,"file":fn})
    # richest first (has item + has a quote), then by date desc
    events.sort(key=lambda e:(bool(e["quotes"]),bool(e["item"]),e["date"] or ""),reverse=True)
    return events

def page(events,gen,mr,ao_po):
    # per-member dissent counts
    by={}
    for e in events:
        for n in e["noes"]: by[n]=by.get(n,0)+1
    members=sorted(by.items(),key=lambda kv:-kv[1])
    def mrow(n,c):
        mp=_money_for(n)
        money=""
        if mp:
            top=(" &middot; top giver %s"%esc(mp["top"])) if mp.get("top") else ""
            money=("<div class=mm>raised $%s in campaign money%s &middot; "
                   "<a href='money_behind_officials.html'>who funds this seat &rarr;</a></div>")%(
                   "{:,.0f}".format(mp.get("total") or 0),top)
        else:
            money="<div class=mm class2=former>former member — outside the current campaign-finance profile set</div>"
        return ("<div class=mrow><div class=mh><span class=mn>%s</span><span class=mc>%d dissent vote(s)</span></div>%s</div>")%(
                esc(n),c,money)
    mrows="".join(mrow(n,c) for n,c in members)
    def card(e):
        noes="".join("<span class=no>%s</span>"%esc(n) for n in e["noes"])
        q="".join("<div class=qt><b>%s:</b> &ldquo;%s&hellip;&rdquo;</div>"%(esc(nm),esc(t)) for nm,t in e["quotes"])
        src=(" &middot; <a href='%s'>source minutes</a>"%esc(e["url"])) if e["url"] else ""
        return ("<div class=dv><div class=dh><b>%s</b><span class=dd>%s &middot; %s</span></div>"
                "<div class=spl>NO: %s <span class=tl>(%s)</span></div>%s"
                "<div class=nar>%s</div><div class=sub2>%s%s</div></div>")%(
                esc(e["item"] or "Motion (item not parsed — read source)"),esc(e["body"] or "Council"),esc(e["date"]),
                noes or "&mdash;",esc(e["tally"]),q,esc(e["motion_narrative"] or ""),
                ("%s"%esc(e["body"])) if not e["url"] else "",src)
    cards="".join(card(e) for e in events[:80]) or "<div class=dv><div class=nar>No split votes parsed yet.</div></div>"
    sup=("<style>.dv{border:1px solid var(--line);border-left:3px solid #b4242c;border-radius:11px;padding:.7rem 1rem;margin:.6rem 0;background:var(--panel)}"
         ".dv .dh{display:flex;justify-content:space-between;gap:8px;flex-wrap:wrap;align-items:baseline}"
         ".dv .dh b{color:var(--accent);font-size:1.0rem}.dv .dd{font:600 12px/1 'JetBrains Mono',Consolas,monospace;color:var(--accent2);white-space:nowrap}"
         ".dv .spl{margin:.4rem 0;font-size:.92rem}.dv .no{display:inline-block;background:#f6e4e4;color:#9a242c;border:1px solid #e3bcbc;border-radius:99px;padding:.12rem .55rem;margin:.1rem .25rem .1rem 0;font-size:.82rem;font-weight:600}"
         ".dv .tl{color:var(--faint);font-family:Consolas,monospace;font-size:.8rem}"
         ".dv .qt{background:#fbf6ea;border:1px solid #e6d8a8;border-radius:8px;padding:.4rem .7rem;margin:.35rem 0;font-size:.88rem;color:#5a4a16;line-height:1.5}"
         ".dv .nar{color:var(--dim);font-size:.82rem;line-height:1.5;margin:.35rem 0;font-style:italic;border-top:1px dashed var(--line);padding-top:.35rem}"
         ".dv .sub2{font-size:.78rem;color:var(--faint);margin-top:.2rem}"
         ".mrow{border-bottom:1px solid #e3e9f1;padding:.5rem .1rem}.mrow .mh{display:flex;justify-content:space-between;gap:8px;align-items:baseline}"
         ".mn{color:var(--ink);font-weight:600}.mc{font-family:Consolas,monospace;color:#9a242c;font-size:.82rem;white-space:nowrap}"
         ".mrow .mm{font-size:.82rem;color:var(--dim);margin-top:.2rem}.mrow .mm a{white-space:nowrap}</style>")
    cb=("<div class=cb>&#9790;&#9728; <b>Curse-breaker.</b> A NO vote is not obstruction &mdash; it is the record of "
        "conscience, the moment a representative tells the public <i>why</i> they could not agree. Under tonight&rsquo;s "
        "%s, this page honors the dissent and asks only the open question it raises: what did the majority approve, what "
        "did the dissenters foresee, and does the later record bear them out? Read the minutes; the people speak for "
        "themselves. Facts and questions, never a finding.</div>")%esc(mr.get("po","") or "moon")
    head=("<!doctype html><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'>"
          "<title>Maui County Council — votes &amp; the nay narratives | govOS</title>")
    intro=("<div class=wrap><div class=sub style='letter-spacing:.1em;text-transform:uppercase;color:var(--accent2);font-weight:600'>"
           "govOS &middot; Maui County &middot; who governs &middot; asked in aloha</div><h1>Council votes &mdash; the nay narratives</h1>")
    pono=("<div class=pono>From the full record of ingested Council minutes: every motion where the council <b>split</b> "
          "&mdash; each recorded NO vote, who cast it (current <i>and</i> former members), the aye/no count, the matter, "
          "and the discussion around it, with the dissenter&rsquo;s own words where the minutes capture them. "
          "Unanimous votes are not listed; <b>%d</b> split votes are. A <b>question to verify</b> against the source "
          "minutes &mdash; never a finding. <a href='officials_scorecard.html'>&larr; officials scorecard</a> &middot; "
          "<a href='money_behind_officials.html'>money behind the seats</a>.</div>")%len(events)
    h2a="<h2>Where the council split (most-documented first, top %d)</h2>"%min(80,len(events))
    h2b=("<h2>Dissent by member &mdash; who says no, and who funds the seat</h2>"
         "<div class=pono style='margin:.2rem 0 .6rem'>Each current member&rsquo;s dissent count beside the campaign money "
         "behind their seat &mdash; so the open question is visible: does the money track with where a member stands, or "
         "against it? A <b>question to verify</b>, never a finding. Former members predate this finance profile set.</div>")
    nav=("<p class=sub style='margin-top:1rem'><a href='officials_scorecard.html'>officials scorecard</a> &middot; "
         "<a href='money_behind_officials.html'>money behind officials</a> &middot; <a href='testifiers_maui.html'>who testifies</a> "
         "&middot; <a href='tenant_hi-maui.html'>Maui overview</a> &middot; <a href='tenants_hub.html'>all governments</a></p>")
    foot=("<div class=foot>Source: official Maui County Council/committee minutes (CivicClerk/Granicus), parsed for "
          "recorded roll-call dissent. Public record; questions, not findings &middot; generated %s.</div></div>")%esc(gen)
    html=head+STYLE+sup+intro+moon_banner(mr,ao_po)+pono+h2a+cards+("<div class=cb2></div>")+h2b+mrows+cb+nav+foot
    open(os.path.join(M,"council_votes_maui.html"),"w",encoding="utf-8",newline="\n").write(html)
    return "council_votes_maui.html",len(members)

def main():
    if not os.path.isdir(TXT): print("nay_narratives: no Maui minutes corpus"); return 1
    gen=datetime.now(HST).strftime("%Y-%m-%d %H:%M HST")
    today=datetime.now(HST).date().isoformat()
    mr=mc.reading(today) or {}; co=mc.creative_offering(today) or {}
    ao_po=co.get("ao_po") or ("Ao" if mr.get("phase") in ("waxing","full") else "Pō")
    events=extract()
    fn,nmem=page(events,gen,mr,ao_po)
    os.makedirs(ST,exist_ok=True)
    json.dump({"generated":gen,"n_dissent_votes":len(events),"n_members":nmem,"events":events[:400]},
              open(os.path.join(ST,"nay_narratives.json"),"w",encoding="utf-8"),indent=1,ensure_ascii=False)
    withq=sum(1 for e in events if e["quotes"]); withi=sum(1 for e in events if e["item"])
    print("nay_narratives: %d split votes (%d w/ item, %d w/ a dissenter quote), %d members -> %s"%(
          len(events),withi,withq,nmem,fn))
    return 0

if __name__=="__main__":
    if sys.platform=="win32":
        import io; sys.stdout=io.TextIOWrapper(sys.stdout.buffer,encoding="utf-8",errors="replace")
    sys.exit(main())
