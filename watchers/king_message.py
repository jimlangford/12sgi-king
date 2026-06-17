#!/usr/bin/env python3
# king_message.py - the daily KING MESSAGE OF ALOHA + the CURSE-BREAKER kindness (Jimmy 2026-06-16).
#
# Two readings of one balance, every day, for every tenant:
#   * SUN (Ao / logic)  - what the public record shows: the prosecutor's "reasonable awareness" for an office
#                         (real-estate money carried, a money->contract loop edge). The number, plainly.
#   * MOON (Pō / aloha) - today's kaulana mahina (moon_calendar): the night, its nature, its civic offering.
# When the two meet - when the prosecutor finds reasonable awareness AND the moon gives its timing - the King
# speaks a message of aloha: it shows the number, then offers the CURSE-BREAKER - kindness to consider, a pono
# path to restore balance (disclose · recuse · return · decide for the public). Never an accusation; an invitation.
# That is the skill: the truth told in light (sun), the path offered in aloha (moon), so the curse - the quiet
# erosion of trust when money sits too close to a vote - is broken by a choice, not a condemnation.
#
# HOLD (Jimmy 2026-06-16): the PUBLIC real-estate report waits on real property-transaction data. So the full
# numbers render PRIVATE (king-local owner-only) now; the PUBLIC daily message carries the moon + the curse-breaker
# kindness + the QUESTION, WITHOUT the held dollar figures. When the public RE report ships, flip PUBLISH_NUMBERS.
# Stdlib only (+ local moon_calendar).
import os, sys, json
from datetime import datetime, timedelta, timezone
HERE=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import moon_calendar as mc
HST=timezone(timedelta(hours=-10))
HOME=os.path.expanduser("~"); PROJ=os.path.join(HOME,"Documents","Claude","Projects","Video System elementLOTUS")
M=os.path.join(PROJ,"reports","mauios"); ST=os.path.join(PROJ,"reports","_status")
KING_DIRS=[os.path.join(HOME,"AppData","Local","king-extract","deploy","king-local"),os.path.join(PROJ,"king-local")]
PUBLISH_NUMBERS=False   # flip to True only when the public RE report ships (transactions real)
AWARE_RE=25000          # RE money at/above this = "reasonable awareness" even without a closed loop edge
def L(p,d=None):
    try: return json.load(open(p,encoding="utf-8"))
    except Exception: return d
def esc(s): return str(s if s is not None else "").replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
def usd(n): return "{:,.0f}".format(int(n or 0))

# every civic tenant gets a daily message; the prosecutor signal (ram_loop) is Maui-deep today
TENANTS=[("hi-maui","Maui County"),("hi-honolulu","Honolulu"),("hi-hawaii","Hawaiʻi County"),
         ("hi-kauai","Kauaʻi County"),("hi-state","State of Hawaiʻi"),("ny","New York")]

def curse_breaker(office, re_total, closed):
    """The kindness offered: a pono path to break the curse (money sitting too close to a vote)."""
    if closed:
        deed=("a real-estate donor to this office also holds county contracts")
    elif re_total>=AWARE_RE:
        deed=("real-estate interests are among the larger funders of this office")
    else:
        deed=None
    if not deed: return None
    return ("Aloha to %s. The record shows %s — a question, never a finding. The curse is not the money; it is "
            "the doubt it plants in the people. To break it, kindness offers a choice, not a charge: <b>disclose</b> "
            "the tie before the vote, <b>recuse</b> where the interest is direct, <b>return</b> what clouds the seat, "
            "or simply <b>decide for the public</b> in the open. Any one restores the balance. That is pono — and it "
            "is yours to choose.")%(esc(office),deed)

def main():
    today=datetime.now(HST).date().isoformat()
    r=mc.reading(today) or {}
    co=mc.creative_offering(today) or {}
    ao_po=co.get("ao_po") or ("Ao" if r.get("phase") in ("waxing","full") else "Pō")
    ram=L(os.path.join(ST,"ram_loop.json"),{}) or {}
    loops=ram.get("loops",[])
    gen=datetime.now(HST).strftime("%Y-%m-%d %H:%M HST")

    # build per-tenant daily message + (for tenants with a prosecutor signal) king messages
    out={"generated":gen,"date":today,"moon":r,"ao_po":ao_po,"tenants":{}}
    for tid,name in TENANTS:
        daily=("Aloha, %s. Tonight is pō %s %s — %s. The moon's offering for those who govern and those who "
               "watch: %s. Sun and moon held together: lead in the light, decide in aloha.")%(
               esc(name),r.get("night","?"),esc(r.get("po","")),esc(r.get("nature","")),esc(r.get("offering","")))
        kings=[]
        if tid=="hi-maui":   # the prosecutor's reasonable-awareness signal is Maui-deep today
            for l in loops:
                re_total=l.get("re_total",0) or 0; closed=l.get("closed") or []
                if closed or re_total>=AWARE_RE:
                    cb=curse_breaker(l.get("official",""),re_total,bool(closed))
                    if cb:
                        kings.append({"office":l.get("official",""),"re_total":re_total,
                                      "closed_edges":len(closed),"aware":"loop" if closed else "re-money",
                                      "curse_breaker":cb})
        out["tenants"][tid]={"name":name,"daily":daily,"king_messages":kings}

    os.makedirs(ST,exist_ok=True)
    json.dump(out,open(os.path.join(ST,"king_messages.json"),"w",encoding="utf-8"),indent=1,ensure_ascii=False)

    # ---- PUBLIC-SAFE daily aloha (moon line per tenant ONLY — no held numbers, no king curse-breaker) ----
    # This is what build_site may publish + inject into each public tenant page: the moon's daily offering, pure aloha.
    pub={"generated":gen,"date":today,
         "moon":{"night":r.get("night"),"po":r.get("po"),"anahulu":r.get("anahulu"),
                 "phase":r.get("phase"),"nature":r.get("nature"),"offering":r.get("offering"),"ao_po":ao_po},
         "tenants":{tid:{"name":out["tenants"][tid]["name"],"daily":out["tenants"][tid]["daily"]} for tid,_ in TENANTS}}
    json.dump(pub,open(os.path.join(M,"daily_aloha.json"),"w",encoding="utf-8"),indent=1,ensure_ascii=False)

    # ---- PRIVATE owner-only render: full numbers + curse-breaker (respects the HOLD) ----
    def kingbox(k):
        num=("<span class=num>$%s real-estate money%s</span>"%(usd(k["re_total"]),
             (" · <b>%d loop edge(s) closed</b>"%k["closed_edges"]) if k["closed_edges"] else "")) if PUBLISH_NUMBERS or True else ""
        return ("<div class=king><div class=kh>⚖ + ☾ &nbsp; King message of aloha — %s</div>"
                "<div class=knum>%s</div><div class=kcb>%s</div></div>")%(esc(k["office"]),num,k["curse_breaker"])
    cards=""
    for tid,name in TENANTS:
        t=out["tenants"][tid]
        kings="".join(kingbox(k) for k in t["king_messages"]) or "<div class=none>No reasonable-awareness signal today — the daily aloha stands on its own.</div>"
        cards+=("<section class=t><h2>%s</h2><div class=daily>%s</div>%s</section>")%(esc(name),t["daily"],kings)
    moon_line=("Tonight — pō %s <b>%s</b> (%s, %s); %s key. %s"%(
        r.get("night","?"),esc(r.get("po","")),esc(r.get("anahulu","")),esc(r.get("phase","")),ao_po,esc(r.get("nature",""))))
    html=("<!doctype html><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'>"
      "<title>King message of aloha — daily | PRIVATE owner only</title><style>"
      "body{margin:0;background:#0b0f12;color:#e8e4d8;font-family:Georgia,serif;line-height:1.55;padding:22px}"
      ".wrap{max-width:880px;margin:0 auto}h1{color:#f0cf7a;font-size:22px;margin:.2rem 0}"
      ".priv{display:inline-block;font-family:Consolas,monospace;font-size:10.5px;letter-spacing:1px;text-transform:uppercase;color:#e06c6c;border:1px solid #4a2222;border-radius:6px;padding:2px 8px;margin-left:8px}"
      ".moon{background:#0e1622;border:1px solid #213049;border-radius:10px;padding:.7rem 1rem;color:#bcd0ea;font-size:.92rem;margin:.7rem 0}"
      ".t{background:#11160f;border:1px solid #243029;border-radius:12px;padding:.7rem 1rem;margin:.8rem 0}.t h2{font-size:1.05rem;color:#e8e4d8;margin:.2rem 0}"
      ".daily{color:#cfe0c9;font-size:.95rem;font-style:italic;margin:.3rem 0 .5rem}"
      ".king{background:#1a130d;border:1px solid #5a3a1a;border-radius:10px;padding:.6rem .9rem;margin:.5rem 0}"
      ".kh{font-family:Consolas,monospace;font-size:11px;letter-spacing:.5px;color:#e0a45a;text-transform:uppercase}"
      ".knum{font-family:Consolas,monospace;font-size:12.5px;color:#d9b24c;margin:.25rem 0}.num{color:#d9b24c}"
      ".kcb{font-size:.92rem;color:#e8e4d8;margin-top:.25rem}.none{color:#7f8a78;font-size:.88rem;font-style:italic}"
      ".pono{background:#11160f;border:1px solid #2a3a22;border-radius:10px;padding:.7rem 1rem;color:#8fae7e;font-size:.86rem;margin:.8rem 0}</style>"
      "<div class=wrap><h1>King message of aloha — daily<span class=priv>private · numbers owner-only until RE report ships</span></h1>"
      "<div class=moon>☾ %s</div>"
      "<div class=pono>The skill: tell the truth in light (the sun/Ao — the number), offer the path in aloha (the moon/Pō — "
      "the kindness). The curse-breaker is an <b>invitation to pono</b>, never an accusation. Public record only; every "
      "number is a <b>question to verify</b>. Generated %s.</div>%s"
      "<div class=pono style='margin-top:1rem'>PUBLIC face today carries the moon + the curse-breaker kindness + the question — "
      "WITHOUT the held dollar figures (the public RE report waits on real property-transaction data). Flip PUBLISH_NUMBERS "
      "when it ships. &copy; 2026 James RCS Langford · 12 Stones Global · PRIVATE owner-only.</div></div>")%(
      moon_line,esc(gen),cards)
    posted=[]
    try: open(os.path.join(ST,"king_message.html"),"w",encoding="utf-8").write(html)
    except Exception: pass
    for kd in KING_DIRS:
        try:
            if os.path.isdir(kd): open(os.path.join(kd,"king_message.html"),"w",encoding="utf-8").write(html); posted.append(kd)
        except Exception: pass
    n_king=sum(len(out["tenants"][t]["king_messages"]) for t,_ in TENANTS)
    print("king_message: moon pō %s %s (%s, %s key); %d king message(s) of aloha across %d tenants"%(
        r.get("night","?"),r.get("po",""),r.get("phase",""),ao_po,n_king,len(TENANTS)))
    print("  -> PRIVATE king_message.html on the King:", posted or "(king-local not found; json in reports/_status)")
    return 0

if __name__=="__main__":
    if sys.platform=="win32":
        import io; sys.stdout=io.TextIOWrapper(sys.stdout.buffer,encoding="utf-8",errors="replace")
    sys.exit(main())
