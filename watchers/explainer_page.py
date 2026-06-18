#!/usr/bin/env python3
"""explainer_page.py — the public EXPLAINER GENERATE page (Jimmy 2026-06-18).

A beautiful, aloha-framed page where anyone can ask our AI to explain any part of Maui County
government — focused on the Title-system software (Title 19 et al). It carries:
  • the Hawaiian MOON (kaulana mahina) + the SUN (Ao/Pō) timing for any date you pick
  • the UPCOMING AGENDA — pick/post a date and see that date's agenda data
  • the AI question → CHECKBOX aspects (Title features first), driving a quote + ETA
  • a curse-breaker animation: relationships + recusals explored gracefully, with aloha not accusation

Static page: embeds a moon table (next ~120 days), the upcoming agenda, and the aspect catalog, so the
date picker + intake work client-side. The quote/checkout call the deployed backend (verify_api_base in
config/beta.json) when present; until then the price area shows "opening soon" (gating intact). CPU/stdlib.
Writes reports/mauios/explainer.html.
"""
import os, sys, json
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path: sys.path.insert(0, HERE)
import moon_calendar as mc
import explainer_intake as ei
from datetime import datetime, timedelta, timezone
HST = timezone(timedelta(hours=-10))
PROJ = os.path.abspath(os.path.join(HERE, "..", ".."))
M = os.path.join(PROJ, "reports", "mauios")
COUNCIL = os.path.join(PROJ, "reports", "council", "index.jsonl")

def _moon_table(days=120):
    out = {}
    d0 = datetime.now(HST).date()
    for i in range(days):
        ds = (d0 + timedelta(days=i)).isoformat()
        r = mc.reading(ds) or {}
        try: co = mc.creative_offering(ds) or {}
        except Exception: co = {}
        out[ds] = {"po": r.get("po", ""), "night": r.get("night"), "phase": r.get("phase", ""),
                   "anahulu": r.get("anahulu", ""), "offering": r.get("offering", ""),
                   "ao_po": co.get("ao_po", ""), "zone": co.get("zone", ""), "hex": co.get("frame_hex", "#00356b")}
    return out

def _agenda(cap=16):
    out = []
    try:
        for ln in open(COUNCIL, encoding="utf-8", errors="replace").read().splitlines():
            try: r = json.loads(ln)
            except Exception: continue
            if not r.get("date"): continue
            out.append({"date": r.get("date"), "body": (r.get("body") or "Meeting")[:80],
                        "items": (r.get("items") or [])[:3],
                        "dollars": [d.get("amt") for d in (r.get("dollars") or [])][:3],
                        "url": r.get("url", "")})
    except Exception:
        pass
    out.sort(key=lambda x: x["date"], reverse=True)
    # keep the most recent + any future, capped
    return out[:cap]

def _verify_base():
    try:
        c = json.load(open(os.path.join(PROJ, "config", "beta.json"), encoding="utf-8"))
        v = (c.get("verify_api_base") or "").rstrip("/")
        return v if v and not v.startswith("PASTE_") else ""
    except Exception:
        return ""

STYLE = """<style>
:root{--bg:#fff;--panel:#e7eef8;--line:#bacde6;--ink:#13243d;--dim:#41536b;--faint:#6d7f97;--accent:#00356b;--accent2:#1259a3;--ok:#1f8a5b;--gold:#b8860b}
*{box-sizing:border-box}body{font-family:'Segoe UI Variable Text','Segoe UI',system-ui,sans-serif;max-width:840px;margin:0 auto;padding:0 16px 48px;color:var(--ink);background:var(--bg);font-size:16px;line-height:1.55}
a{color:var(--accent2)}h1{font-size:1.7rem;margin:.2rem 0}h2{color:var(--accent);font-size:1.12rem;margin:1.4rem 0 .5rem}
.eyebrow{letter-spacing:.12em;text-transform:uppercase;color:var(--accent2);font-weight:600;font-size:.78rem}
.sub{color:var(--dim);font-size:.95rem}
/* curse-breaker hero: the moon wanes to dark, then the sun (Ao) breaks over it — light, not accusation */
.sky{position:relative;height:140px;border-radius:16px;overflow:hidden;margin:.8rem 0;
 background:linear-gradient(180deg,#0b1733 0%,#16306b 45%,#3f6bb0 75%,#cfe0f4 100%)}
.moon{position:absolute;left:18%;top:30px;width:54px;height:54px;border-radius:50%;background:#eef3fb;
 box-shadow:inset -16px -4px 0 0 #16306b,0 0 22px rgba(238,243,251,.7);animation:wax 9s ease-in-out infinite}
@keyframes wax{0%{box-shadow:inset -16px -4px 0 0 #16306b,0 0 12px rgba(238,243,251,.4)}
 50%{box-shadow:inset 0 0 0 0 #16306b,0 0 26px rgba(255,247,224,.9)}
 100%{box-shadow:inset -16px -4px 0 0 #16306b,0 0 12px rgba(238,243,251,.4)}}
.sun{position:absolute;right:16%;bottom:-40px;width:96px;height:96px;border-radius:50%;
 background:radial-gradient(circle,#fff7e0 0%,#f4c95d 55%,#e0a45a 100%);filter:blur(.3px);
 box-shadow:0 0 60px 20px rgba(244,201,93,.55);animation:rise 9s ease-in-out infinite}
@keyframes rise{0%{bottom:-70px;opacity:.2}55%{bottom:-10px;opacity:1}100%{bottom:-70px;opacity:.2}}
.threads{position:absolute;inset:0;opacity:.5}
.cap{position:absolute;left:14px;bottom:10px;color:#eef3fb;font-size:.8rem;text-shadow:0 1px 4px rgba(0,0,0,.5)}
.card{background:var(--panel);border:1px solid var(--line);border-radius:13px;padding:.85rem 1rem;margin:.7rem 0}
.row{display:flex;gap:14px;flex-wrap:wrap;align-items:center}
input,textarea,select{font:inherit;color:var(--ink);background:#fff;border:1px solid var(--line);border-radius:9px;padding:.5rem .6rem;width:100%}
.moonpanel{display:flex;gap:14px;align-items:center;flex-wrap:wrap}
.mdisc{width:46px;height:46px;border-radius:50%;background:#eef3fb;box-shadow:inset -12px -3px 0 0 #16306b;flex:0 0 auto}
.tag{display:inline-block;font-size:.74rem;font-weight:600;border-radius:99px;padding:.16rem .6rem;border:1px solid var(--line);background:#fff;color:var(--accent)}
.asp{display:flex;gap:10px;align-items:flex-start;border-bottom:1px solid #dbe5f1;padding:.5rem .1rem}
.asp input{width:auto;margin-top:.25rem}.asp .l{font-weight:600;color:var(--ink)}.asp .d{color:var(--dim);font-size:.85rem}
.feat{background:#fbf6ea;border-color:#e6d8a8}
.btn{display:inline-block;background:var(--accent);color:#fff;text-decoration:none;font-weight:600;border:0;border-radius:10px;padding:.6rem 1.1rem;font-size:.95rem;cursor:pointer}
.btn:hover{background:var(--accent2)}.muted{color:var(--faint);font-size:.85rem}
.cb{background:var(--panel);border:1px solid var(--line);border-left:3px solid var(--gold);border-radius:11px;padding:.8rem 1rem;margin:1rem 0;color:var(--dim);line-height:1.55;font-size:.92rem}
.quote{background:#eef6f0;border:1px solid #bfe0cc;border-radius:11px;padding:.7rem 1rem;margin:.6rem 0;color:#1f5a3c;font-size:.95rem}
.foot{margin-top:1.6rem;border-top:1px solid var(--line);padding-top:.7rem;color:var(--faint);font-size:.78rem}
</style>"""

def build():
    gen = datetime.now(HST).strftime("%Y-%m-%d %H:%M HST")
    moon = _moon_table(); agenda = _agenda()
    cat = ei.catalog("hi-maui")
    cat_js = [{"id": a["id"], "label": a["label"], "desc": a["desc"], "featured": a.get("featured", False),
               "kw": ei._KW.get(a["id"], [])} for a in cat]
    today = datetime.now(HST).date().isoformat()
    vbase = _verify_base()
    data = ("<script>const MOON=%s;const AGENDA=%s;const CATALOG=%s;const TODAY=%s;const VBASE=%s;</script>"
            % (json.dumps(moon), json.dumps(agenda), json.dumps(cat_js), json.dumps(today), json.dumps(vbase)))

    head = ("<!doctype html><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1,viewport-fit=cover'>"
            "<meta name=theme-color content='#00356b'><title>Explain your government — govOS · Maui County</title>")
    hero = ("<div class=eyebrow>govOS &middot; Maui County &middot; made in aloha</div>"
            "<h1>Explain your government</h1>"
            "<p class=sub>Ask for any part of Maui County government explained &mdash; the Title&nbsp;19 system, a permit, "
            "a parcel, who funds a seat, how they voted &mdash; and get a shareable explainer, timed to the Hawaiian moon. "
            "The hard questions (relationships, recusals) are explored <b>gracefully</b>: light, not accusation.</p>"
            "<div class=sky><div class=moon></div><div class=sun></div>"
            "<div class=cap>&#9790; the moon wanes &middot; &#9728; the sun breaks &mdash; the curse is broken with aloha</div></div>")
    datepick = ("<h2>1 &middot; Pick a date &mdash; the moon, the sun, the agenda</h2>"
            "<div class=card><div class=row><label class=muted>Date &nbsp;<input type=date id=dt></label>"
            "<span class=tag id=suntag>&#9728;</span></div>"
            "<div class=moonpanel style='margin-top:.6rem'><div class=mdisc id=mdisc></div>"
            "<div><div id=moontxt style='font-weight:600;color:var(--accent)'></div>"
            "<div class=muted id=offer></div></div></div>"
            "<div id=agbox style='margin-top:.6rem'></div></div>")
    intake = ("<h2>2 &middot; What would you like explained?</h2>"
            "<div class=card><textarea id=ask rows=2 placeholder=\"e.g. can I build an ADU on my parcel, and who funds the council deciding it?\"></textarea>"
            "<div style='margin:.5rem 0'><button class=btn type=button onclick='suggest()'>Ask &mdash; tick the aspects &rarr;</button> "
            "<span class=muted id=engine></span></div><div id=aspects></div></div>")
    pricebox = ("<h2>3 &middot; Your explainer</h2>"
            "<div class=card><div class=row><label class=muted>Length &nbsp;<select id=tier>"
            "<option value=premium_reel>Reel (animated, chant + narration)</option>"
            "<option value=premium_card>Single card (image)</option>"
            "<option value=free_cpu>Free preview (our standard reel)</option></select></label>"
            "<label class=muted>&nbsp;<input type=checkbox id=prio> priority (render now)</label></div>"
            "<div class=quote id=quote>Pick aspects above for an estimate.</div>"
            "<button class=btn type=button onclick='order()' id=gobtn>Generate &amp; share</button>"
            "<div class=muted id=gonote style='margin-top:.4rem'></div></div>")
    cb = ("<div class=cb>&#9790;&#9728; <b>The curse-breaker.</b> Where a relationship or a recusal touches a decision, we "
          "name it as a <b>question</b>, never an accusation &mdash; the official can disclose, recuse, or decide in the open; "
          "the public can simply see clearly. Beauty over blame; aloha over contention. Every explainer carries the day's "
          "moon offering, so the work stays pono.</div>")
    nav = ("<p class=sub style='margin-top:1rem'><a href='reports.html'>&larr; govOS home</a> &middot; "
           "<a href='king/civic/templates/title19-system/Title19%20System.html'>the Title 19 System</a> &middot; "
           "<a href='testifiers_maui.html'>who testifies</a> &middot; <a href='council_votes_maui.html'>council votes</a></p>"
           "<div class=foot>govOS explainer &middot; moon: kaulana mahina &middot; sourced public record, framed as questions &middot; "
           "premium renders are buyer-funded; the free preview is our standard local reel &middot; generated " + gen + "</div>")
    html = head + STYLE + hero + datepick + intake + pricebox + cb + nav + data + _SCRIPT
    open(os.path.join(M, "explainer.html"), "w", encoding="utf-8", newline="\n").write(html)
    print("explainer_page: explainer.html (%d moon days, %d agenda, %d aspects, backend=%s)"
          % (len(moon), len(agenda), len(cat_js), "wired" if vbase else "opening-soon"))
    return 0

_SCRIPT = r"""<script>
function $(i){return document.getElementById(i)}
function moonFor(d){return MOON[d]||null}
function fmt(n){return n.charAt(0).toUpperCase()+n.slice(1)}
function showDate(){
  var d=$('dt').value||TODAY; var m=moonFor(d);
  if(!m){$('moontxt').textContent='(beyond the 120-day moon table)';$('offer').textContent='';$('suntag').textContent='';return;}
  var sun=(m.ao_po==='Ao')?'☀ Ao — sun/day energy':'☾ Pō — night/reflective energy';
  $('suntag').textContent=sun;
  $('moontxt').textContent='☾ '+m.po+' · '+fmt(m.phase)+' moon · '+(m.anahulu||'')+(m.zone?(' · '+m.zone):'');
  $('offer').textContent=m.offering||'';
  var md=$('mdisc'); var lit={waxing:'-10px',full:'0px',waning:'10px'}[m.phase]||'-10px';
  md.style.boxShadow='inset '+lit+' -3px 0 0 #16306b';
  // agenda for/near this date
  var near=AGENDA.filter(function(a){return a.date===d});
  if(!near.length){var f=AGENDA.slice().sort(function(a,b){return a.date>b.date?1:-1});near=f.slice(0,2);}
  var h=near.length?('<div class=muted style="margin-top:.3rem">Agenda on the record:</div>'):'';
  near.forEach(function(a){h+='<div class=asp style="border:0"><div><span class=tag>'+a.date+'</span> <b>'+(a.body||'')+'</b>'+
    (a.items&&a.items.length?(' <span class=muted>'+a.items.join(', ')+'</span>'):'')+
    (a.url?(' · <a href="'+a.url+'">minutes</a>'):'')+'</div></div>';});
  $('agbox').innerHTML=h||'<div class=muted>No meeting on that exact date; nearest shown.</div>';
}
function renderAspects(checked){
  var h='';CATALOG.forEach(function(a){var on=checked.indexOf(a.id)>=0;
    h+='<label class="asp'+(a.featured?' feat':'')+'"><input type=checkbox value="'+a.id+'" '+(on?'checked':'')+' onchange="estimate()">'+
       '<span><span class=l>'+a.label+(a.featured?' ★':'')+'</span><div class=d>'+a.desc+'</div></span></label>';});
  $('aspects').innerHTML=h;estimate();
}
function suggest(){
  var t=($('ask').value||'').toLowerCase();var hit=[];
  CATALOG.forEach(function(a){if(a.kw.some(function(k){return t.indexOf(k)>=0})) hit.push(a.id);});
  if(!hit.length) hit=CATALOG.filter(function(a){return a.featured}).slice(0,2).map(function(a){return a.id});
  $('engine').textContent='('+(t?'matched your words':'showing the Title-system features')+')';
  renderAspects(hit);
}
function selected(){return [].slice.call(document.querySelectorAll('#aspects input:checked')).map(function(c){return c.value})}
function estimate(){
  var sel=selected();var tier=$('tier').value;
  if(tier==='free_cpu'){$('quote').textContent='Free preview — our standard local reel. $0.';return;}
  if(!sel.length){$('quote').textContent='Pick aspects above for an estimate.';return;}
  var secs=6+Math.round(sel.length*1.2*4);
  $('quote').innerHTML='<b>'+sel.length+' aspect(s)</b> · ~'+secs+'s '+(tier==='premium_card'?'image':'reel')+
    (($('prio')&&$('prio').checked)?' · <b>priority</b>':'')+
    ' — <span class=muted>exact price + ETA on Generate (pricing is being calibrated).</span>';
}
function order(){
  var sel=selected();var tier=$('tier').value;var pri=($('prio')&&$('prio').checked)?'priority':'standard';
  var aspect=(sel.join(', ')||'agenda explainer');
  if(!VBASE){$('gonote').textContent='The generator opens shortly — secure checkout is being finalized. Your selection is ready.';return;}
  $('gonote').textContent='Getting your quote…';
  fetch(VBASE+'/checkout/start',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({aspect:aspect,tier:tier,priority:pri,tenant:'hi-maui',seconds:6+sel.length*5})})
   .then(function(r){return r.json()}).then(function(j){
     if(j.checkout_url){location.href=j.checkout_url;}
     else if(j.free){$('gonote').textContent='Free preview — queued. You’ll get a shareable link.';}
     else if(j.provisional){$('gonote').textContent='Pricing is being calibrated — generation opens shortly.';}
     else{$('gonote').textContent=(j.message||'Could not start checkout — try again shortly.');}
   }).catch(function(){$('gonote').textContent='Could not reach the generator — try again shortly.';});
}
(function(){$('dt').value=TODAY;showDate();$('dt').addEventListener('change',showDate);suggest();})();
</script>"""

if __name__ == "__main__":
    if sys.platform == "win32":
        import io; sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(build())
