#!/usr/bin/env python3
# agenda_patterns.py - integrate the agenda WORK (conflict/eligibility scan) into the agenda explainer +
# calendar, walking meetings FORWARD first (upcoming) then BACKWARD (historical). Jimmy 2026-06-16:
# "as you work forwards and backwards patterns will emerge." Each meeting's agenda items are scanned for
# vendor<->donor recusal ties (sourced); the RECURRING ties accumulate into the emergent pattern. PUBLIC =
# aloha pattern questions; PRIVATE = the dollar evidence. Sourced-only, never invented. Stdlib only.
import os, sys, json, ssl, re, urllib.request, urllib.parse
from datetime import datetime, timedelta, timezone
from collections import Counter, defaultdict
HST=timezone(timedelta(hours=-10))
HOME=os.path.expanduser("~"); PROJ=os.path.join(HOME,"Documents","Claude","Projects","Video System elementLOTUS")
M=os.path.join(PROJ,"reports","mauios"); ST=os.path.join(PROJ,"reports","_status"); C="mauicounty"
UA={"User-Agent":"12sgi-kilo-aupuni/1.0 (civic transparency; public record)"}
def jj(u): return json.loads(urllib.request.urlopen(urllib.request.Request(u,headers=UA),timeout=45,context=ssl.create_default_context()).read().decode("utf-8","replace"))
def esc(s): return str(s or "").replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
def norm(s): return re.sub(r"\s+"," ", re.sub(r"[^A-Z0-9 ]"," ", str(s).upper())).strip()

def conflict_map():
    out={}
    try:
        d=json.load(open(os.path.join(M,"vendor_donor_join.json"),encoding="utf-8"))
        for mm in d.get("matched",[]):
            out[norm(mm["vendor"])[:22]]={"vendor":mm["vendor"],"members":sorted({h["official"] for h in mm.get("hits",[])}),
                                          "amt":{h["official"]:h["amount"] for h in mm.get("hits",[])}}
    except Exception: pass
    # broaden with the WORKED hewa watchlist (casework EXAMINE/NOTE + property/contract entities) so the
    # forward/backward walk catches the full money picture, not only the raw vendor↔donor matches. Full-name
    # key (>=12 chars) keeps it solid — never a generic-word hit. Officials become the members to watch.
    try:
        w=json.load(open(os.path.join(PROJ,"reports","_status","hewa_watchlist_maui.json"),encoding="utf-8"))
        for e in w.get("entities",[]):
            k=norm(e.get("entity",""))[:22]
            if len(k)>=12 and k not in out:
                out[k]={"vendor":e["entity"],"members":sorted(e.get("officials",[])),"amt":{}}
    except Exception: pass
    return out

def main():
    today=datetime.now(HST).strftime("%Y-%m-%d")
    cmap=conflict_map()
    # BFED meetings, most-recent-first (forward window first, then walk back through history)
    rows=jj("https://webapi.legistar.com/v1/%s/Events?%s"%(C,urllib.parse.urlencode({"$orderby":"EventDate desc","$top":"60"})))
    bfed=[r for r in rows if "budget" in (r.get("EventBodyName") or "").lower()]
    fwd=[r for r in bfed if str(r.get("EventDate"))[:10]>=today]
    back=[r for r in bfed if str(r.get("EventDate"))[:10]<today]
    ordered=fwd+back            # FORWARD first, then historical
    tie_counts=Counter()        # (vendor, member) -> # of meetings it surfaced on
    mem_meetings=defaultdict(set)
    processed=[]; ev_priv=[]
    for e in ordered[:24]:      # bounded window; grows as run repeats forward+backward
        eid=e["EventId"]; date=str(e.get("EventDate"))[:10]
        try: items=jj("https://webapi.legistar.com/v1/%s/Events/%s/EventItems?$top=200"%(C,eid))
        except Exception: items=[]
        hits=[]
        for it in items:
            t=(it.get("EventItemTitle") or it.get("EventItemMatterName") or "")
            tn=norm(t)
            for key,info in cmap.items():
                if key and key in tn:
                    for mem in info["members"]:
                        tie_counts[(info["vendor"],mem)]+=1; mem_meetings[mem].add(date)
                        hits.append({"vendor":info["vendor"],"member":mem,"amount":info["amt"].get(mem),"item":t[:120],"date":date})
        processed.append({"date":date,"when":"upcoming" if date>=today else "historical","hits":len(hits)})
        ev_priv+=hits
    # emergent patterns: recurring ties (>=2 meetings) + per-member exposure
    recurring=sorted([(v,m,c) for (v,m),c in tie_counts.items() if c>=2], key=lambda x:-x[2])
    mem_rank=sorted(mem_meetings, key=lambda m:-len(mem_meetings[m]))
    gen=datetime.now(HST).strftime("%Y-%m-%d %H:%M HST")
    fwd_n=sum(1 for p in processed if p["when"]=="upcoming"); back_n=len(processed)-fwd_n
    # PUBLIC aloha pattern page (questions, no dollars)
    pat=""
    if recurring:
        pat="".join("<li><b>%s</b> appears with <b>%s</b> across <b>%d</b> meetings — a recurring pairing. A question for pono: when this vendor is a party, should this member recuse?</li>"%(esc(m),esc(v),c) for v,m,c in recurring[:12])
    else:
        pat="<li>No vendor↔member tie has recurred across the scanned window yet — patterns surface as more meetings (forward + back) are processed.</li>"
    rank="".join("<li>%s — touched %d scanned meetings with a donor-tied party</li>"%(esc(m),len(mem_meetings[m])) for m in mem_rank[:9])
    html=("<!doctype html><meta charset=utf-8><meta http-equiv=refresh content=600><title>Agenda patterns — forward & back | govOS</title>"
      "<style>body{font-family:system-ui,Segoe UI,sans-serif;max-width:920px;margin:2rem auto;padding:0 1.1rem;color:#eaf2fc}"
      "a{color:#5a97e6}h1{font-size:1.45rem;margin:.2rem 0}h2{font-size:1.05rem;color:#1f6b4a;margin:1.3rem 0 .3rem}"
      ".eyebrow{font-size:.72rem;letter-spacing:.16em;text-transform:uppercase;color:#6b7a89}.sub{color:#56646f;font-size:.9rem;margin:.3rem 0 1rem}"
      "li{margin:.3rem 0;font-size:.9rem;line-height:1.45}.meter{color:#8b99a6;font-size:.82rem}</style>"
      "<div class=eyebrow><a href='agenda_explainer.html'>govOS · agenda explainer</a> · <a href='meetings_calendar.html'>calendar</a></div>"
      "<h1>Agenda patterns — working forward &amp; back</h1>"
      "<div class=sub>We scan each meeting's agenda items for sourced donor↔member ties, starting with "
      "<b>upcoming</b> meetings and walking <b>back</b> through the record. As coverage grows both ways, the "
      "recurring pairings surface — offered as questions for pono, never accusations. Scanned this run: "
      "<b>%d upcoming + %d historical</b> meetings. Generated %s.</div>"
      "<h2>Recurring pairings (the emerging pattern)</h2><ul>%s</ul>"
      "<h2>Members most exposed to donor-tied agenda parties</h2><ul>%s</ul>"
      "<p class=sub>Method: each tie is a QUESTION for the Board of Ethics to verify (Maui Charter Art.10 / HRS 84). "
      "The dollar evidence is kept in the private record. Patterns strengthen as the window extends.</p>"
      %(fwd_n,back_n,esc(gen),pat,rank))
    os.makedirs(M,exist_ok=True); open(os.path.join(M,"agenda_patterns.html"),"w",encoding="utf-8").write(html)
    # PRIVATE evidence
    os.makedirs(os.path.join(ST,"leads"),exist_ok=True)
    json.dump({"generated":gen,"PRIVACY":"OWNER-ONLY","forward":fwd_n,"historical":back_n,
               "recurring_ties":[{"vendor":v,"member":m,"meetings":c} for v,m,c in recurring],"evidence":ev_priv},
              open(os.path.join(ST,"leads","agenda_patterns_evidence.json"),"w",encoding="utf-8"),indent=1,ensure_ascii=False)
    print("agenda_patterns: scanned %d meetings (%d upcoming + %d historical) · recurring ties: %d"%(len(processed),fwd_n,back_n,len(recurring)))
    for v,m,c in recurring[:8]: print("   %s <-> %s : %d meetings"%(m,v[:34],c))
    return 0

if __name__=="__main__":
    if sys.platform=="win32":
        import io; sys.stdout=io.TextIOWrapper(sys.stdout.buffer,encoding="utf-8",errors="replace")
    sys.exit(main())
