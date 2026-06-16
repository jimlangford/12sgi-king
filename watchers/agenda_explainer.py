#!/usr/bin/env python3
"""agenda_explainer.py — "Forecast -> fact -> publish": turn each upcoming agenda item into a
shareable fact-card so the community can get ahead of the vote.

Data-driven from the live agenda feed (agenda_sources.json). For each upcoming meeting it builds a
vertical 9:16 fact-card — WHAT is being decided, WHEN, the testify DEADLINE, the LAW (the tenant's
charter<->law crosswalk), the MONEY (who funds the deciders), and HOW TO TESTIFY — plus a ready-to-
paste caption + hashtags and a share sheet.

EXPORT (honest): the Web Share API opens the phone's native share sheet to ANY app — TikTok, Instagram,
Facebook, X — with the caption + link; for the visual, screenshot/download the 9:16 card. (No platform
login and no auto-posting: publishing is the user's tap. A narrated-VIDEO render lane is phase 2.)
Output: reports/mauios/agenda_explainer.html
"""
import os, json, html
from datetime import datetime, timezone, timedelta
try:
    import moon_calendar          # kaulana mahina: the meeting date's pō + aloha offering on each card
except Exception:
    moon_calendar = None

HOME    = os.path.expanduser("~")
PROJECT = os.path.join(HOME, "Documents", "Claude", "Projects", "Video System elementLOTUS")
MAUIOS  = os.path.join(PROJECT, "reports", "mauios")
AGENDA  = os.path.join(os.path.dirname(os.path.abspath(__file__)), "agenda_sources.json")
OUT     = os.path.join(MAUIOS, "agenda_explainer.html")
HST     = timezone(timedelta(hours=-10))
esc     = lambda s: html.escape(str(s or ""))
ja      = lambda s: (str(s or "")).replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")
def now_hst(): return datetime.now(HST)

NAMES = {"state":"State of Hawaiʻi","maui":"Maui County","honolulu":"City & County of Honolulu",
         "hawaii":"Hawaiʻi County","kauai":"Kauaʻi County","nyc":"New York City","nys":"New York State",
         "liverpool":"Village of Liverpool","london":"City of London","tokyo":"Tokyo Metropolis",
         "hongkong":"Hong Kong SAR","singapore":"Singapore","zurich":"Zürich","frankfurt":"Frankfurt",
         "paris":"Paris","dubai":"Dubai"}
ORDER = ["maui","honolulu","state","hawaii","kauai","nyc","nys","liverpool","london","hongkong",
         "tokyo","singapore","zurich","frankfurt","paris","dubai"]

def links_for(tid):
    out = {}
    for key, pat in (("law","crosswalk_%s.html"),("money","money_%s.html"),("parity","parity_%s.html"),("agendas","agendas_%s.html")):
        fn = pat % tid
        if os.path.exists(os.path.join(MAUIOS, fn)): out[key] = fn
    if tid == "maui":
        out["money"] = "money_behind_officials.html"; out["testify"] = "testify.html"
    out["request"] = "request_records.html#" + tid
    return out

def how_to_testify(tid):
    if tid == "maui":
        return ("Testify before the vote — email the County Clerk (Council) or use eComment (committee). "
                "govOS makes it one tap.", "testify.html")
    return ("Submit testimony before the meeting through this government's process.", "request_records.html#" + tid)

def card(tid, m, idx):
    nm = NAMES.get(tid, tid); L = links_for(tid)
    body = m.get("body", "Meeting"); title = m.get("title", ""); date = m.get("date", "")
    src = m.get("url", ""); tip, tlink = how_to_testify(tid)
    mr = moon_calendar.reading(date) if (moon_calendar and date) else None
    moon_cap = (" 🌙 %s moon (pō %d) — %s." % (mr["po"], mr["night"], mr["offering"])) if mr else ""
    caption = ("⚖ %s — %s%s on %s. Know the law, follow the money, and testify BEFORE the vote. "
               "This is how we get ahead of it.%s #govOS #FollowTheMoney #%s #KiloAupuni #Aloha" % (
                 nm, body, (" — " + title) if title else "", date, moon_cap, tid))
    share_url = "https://jimlangford.github.io/12sgi-king/agenda_explainer.html"
    chips = ""
    for k, lbl in (("law","the law ⇄"),("money","the money"),("parity","the pairs"),("agendas","full agenda")):
        if L.get(k): chips += '<a class="chip" href="%s">%s</a>' % (esc(L[k]), lbl)
    chips += '<a class="chip act" href="' + esc(tlink) + '">how to testify</a>'
    src_btn = ('<a class="sb" href="' + esc(src) + '" target="_blank" rel="noopener">source ↗</a>') if src else ""
    sub = esc(body) + ((" — " + esc(title)) if title else "") + " · " + esc(date)
    title_text = body[:80] + ((" — " + title) if title else "")
    moon_text = (mr["po"] + " moon · pō " + str(mr["night"]) + " — " + mr["offering"]) if mr else ""
    return ('<div class="ex" data-cap="' + ja(caption) + '" data-url="' + ja(share_url) + '"'
      ' data-date="' + ja(date) + '" data-tenant="' + ja(nm) + '" data-title="' + ja(title_text) + '"'
      ' data-cta="' + ja(tip) + '" data-moon="' + ja(moon_text) + '">'
      '<div class="card9"><div class="c9-top"><span class="c9-eye">govOS · get ahead of the vote</span></div>'
      '<div class="c9-body"><div class="c9-when">' + esc(date) + '</div>'
      '<div class="c9-what">' + esc(nm) + '</div>'
      '<div class="c9-title">' + esc(body[:80]) + ((" — " + esc(title)) if title else "") + '</div>'
      '<div class="c9-deadline">&#9201; Testify BEFORE the vote</div>'
      '<div class="c9-cta">' + esc(tip) + '</div>'
      + (('<div class="c9-moon">🌙 ' + esc(mr["po"]) + ' moon · pō ' + str(mr["night"])
          + ' — ' + esc(mr["offering"]) + '</div>') if mr else '') + '</div>'
      '<div class="c9-foot">⚖ 12 Stones · Kilo Aupuni · the people&rsquo;s record</div></div>'
      '<div class="ex-side"><div class="ex-h">' + esc(nm) + '</div><div class="ex-sub">' + sub + '</div>'
      '<div class="chips">' + chips + '</div>'
      '<div class="cap">' + esc(caption) + '</div>'
      '<div class="sbtns">'
      '<button class="sb primary" data-share>&#128228; Share graphic</button>'
      '<button class="sb" data-save>&#11015; Save card (.png)</button>'
      '<button class="sb" data-copy>Copy caption</button>'
      '<a class="sb" data-x target="_blank" rel="noopener">Post to X</a>'
      '<a class="sb" data-fb target="_blank" rel="noopener">Facebook</a>' + src_btn + '</div>'
      '<div class="hint">&#128228; Share graphic sends the card <b>image</b> itself (with the date in its title) straight to TikTok / IG / FB / X via your share sheet. No share sheet? It saves the .png and copies the caption.</div>'
      '</div></div>')

def build():
    try:
        srcs = {s["tenant_id"]: s for s in json.load(open(AGENDA, encoding="utf-8")).get("sources", [])}
    except Exception:
        srcs = {}
    g = now_hst().strftime("%Y-%m-%d %H:%M HST")
    # each tenant gets its OWN card section (anchored #<tenant>) + a jump-nav
    sections, jump, n = "", [], 0
    for tid in ORDER:
        s = srcs.get(tid)
        if not s: continue
        items = (s.get("upcoming") or [])[:3]
        if not items: continue
        nm = NAMES.get(tid, tid)
        tcards = "".join(card(tid, m, n + i) for i, m in enumerate(items)); n += len(items)
        ag = ('<a class="tlink" href="agendas_%s.html">full agenda feed ↗</a>' % tid) if os.path.exists(os.path.join(MAUIOS, "agendas_%s.html" % tid)) else ""
        sections += ('<h2 class="tsec" id="%s">%s — %d card%s %s</h2>%s' % (
            tid, esc(nm), len(items), "" if len(items) == 1 else "s", ag, tcards))
        jump.append('<a href="#%s">%s</a>' % (tid, esc(nm)))
    cards = sections or '<div class="none">No upcoming meetings in the current feed — check back as agendas post.</div>'
    jumpnav = ('<div class="jump">Each government&rsquo;s cards: ' + " · ".join(jump) + '</div>') if jump else ""
    CSS = ("<style> body{margin:0;background:#0c100e;color:#e8e4d8;font-family:Georgia,serif;line-height:1.6}"
     " .wrap{max-width:1040px;margin:0 auto;padding:30px 22px 70px}"
     " .eyebrow{font-family:Consolas,monospace;font-size:11px;letter-spacing:1.4px;color:#d9b24c;text-transform:uppercase}"
     " h1{font-size:27px;font-weight:600;margin:8px 0 4px} .lead{font-size:14px;color:#cfc9b6;max-width:80ch}"
     " .ex{display:flex;gap:16px;flex-wrap:wrap;align-items:flex-start;border-top:1px solid rgba(255,255,255,.08);padding:18px 0}"
     " .card9{width:288px;min-width:288px;aspect-ratio:9/16;border-radius:16px;background:linear-gradient(160deg,#10231b,#0c100e 70%);"
     "   border:1px solid #2a6b4e;display:flex;flex-direction:column;justify-content:space-between;padding:18px 16px;box-shadow:0 6px 26px rgba(0,0,0,.4)}"
     " .c9-eye{font-family:Consolas,monospace;font-size:10px;letter-spacing:1px;color:#9fd9bf;text-transform:uppercase}"
     " .c9-when{font-family:Consolas,monospace;font-size:13px;color:#d9b24c;margin-bottom:8px}"
     " .c9-what{font-size:21px;font-weight:700;color:#f0ead8;line-height:1.2}"
     " .c9-title{font-size:16.5px;font-weight:600;color:#f4eeda;margin-top:9px;background:rgba(255,255,255,.06);border-left:3px solid #d9b24c;border-radius:8px;padding:8px 10px;line-height:1.3}"
     " .c9-deadline{font-family:Consolas,monospace;font-size:12px;color:#e06a4a;margin-top:14px}"
     " .c9-cta{font-size:13px;color:#9fd9bf;margin-top:6px}"
     " .c9-moon{font-size:14.5px;font-weight:600;color:#ecdfff;margin-top:12px;background:rgba(205,180,240,.16);border-left:3px solid #cdb4f0;border-radius:9px;padding:9px 11px;line-height:1.45}"
     " .c9-foot{font-family:Consolas,monospace;font-size:10px;color:#9a957f;text-align:center}"
     " .ex-side{flex:1;min-width:260px} .ex-h{font-size:17px;font-weight:600;color:#f0ead8} .ex-sub{font-size:12.5px;color:#9a957f;margin-bottom:8px}"
     " .chips{display:flex;flex-wrap:wrap;gap:7px;margin:6px 0 10px} .chip{font-family:Consolas,monospace;font-size:11px;text-decoration:none;color:#d9b24c;border:1px solid #243029;border-radius:8px;padding:5px 9px} .chip.act{color:#9fd9bf;border-color:#2a6b4e} .chip:hover{background:rgba(217,178,76,.1)}"
     " .cap{font-size:12.5px;color:#cfc9b6;background:#151d19;border:1px solid #243029;border-radius:9px;padding:10px 12px;margin:6px 0}"
     " .sbtns{display:flex;flex-wrap:wrap;gap:8px;margin:8px 0} .sb{font-family:Consolas,monospace;font-size:12px;padding:8px 13px;border-radius:9px;border:1px solid #d9b24c;color:#d9b24c;background:rgba(217,178,76,.06);cursor:pointer;text-decoration:none} .sb.primary{background:#d9b24c;color:#0c100e;font-weight:700} .sb:hover{background:rgba(217,178,76,.16)}"
     " .hint{font-size:11px;color:#9a957f;font-style:italic;margin-top:6px} .none{font-size:14px;color:#9a957f;font-style:italic}"
     " .tsec{font-size:16px;color:#f0ead8;margin:28px 0 2px;border-bottom:1px solid #243029;padding-bottom:6px;scroll-margin-top:60px} .tlink{font-family:Consolas,monospace;font-size:11px;margin-left:8px;font-weight:400} .jump{font-size:12px;color:#cfc9b6;margin:12px 0} .jump a{color:#d9b24c;font-family:Consolas,monospace;font-size:11px}"
     " a{color:#d9b24c} footer{margin-top:28px;border-top:1px solid #243029;padding-top:12px;font-family:Consolas,monospace;font-size:10.5px;color:#9a957f}</style>")
    JS = r"""<script>
(function(){
 var SANS="-apple-system,'Segoe UI',Roboto,Helvetica,Arial,sans-serif",MONO="'Consolas','SF Mono','Menlo',monospace";
 function wrap(x,text,maxw){var w=(text||'').split(/\s+/),L=[],c='';for(var i=0;i<w.length;i++){var t=c?c+' '+w[i]:w[i];if(c&&x.measureText(t).width>maxw){L.push(c);c=w[i];}else{c=t;}}if(c)L.push(c);return L;}
 function rr(x,X,Y,W,H,r){x.beginPath();x.moveTo(X+r,Y);x.arcTo(X+W,Y,X+W,Y+H,r);x.arcTo(X+W,Y+H,X,Y+H,r);x.arcTo(X,Y+H,X,Y,r);x.arcTo(X,Y,X+W,Y,r);x.closePath();}
 function band(x,lines,X,y,maxw,lineH,bg,bar,fg){var H=lines.length*lineH+24;x.fillStyle=bg;rr(x,X-18,y-14,maxw+36,H,14);x.fill();x.fillStyle=bar;x.fillRect(X-18,y-14,6,H);x.fillStyle=fg;lines.forEach(function(l){x.fillText(l,X,y);y+=lineH;});return y+18;}
 function drawCard(ex){
  var W=1080,H=1920,pad=84,maxw=W-pad*2,cv=document.createElement('canvas');cv.width=W;cv.height=H;var x=cv.getContext('2d');
  var g=x.createLinearGradient(0,0,W,H);g.addColorStop(0,'#10231b');g.addColorStop(.65,'#0c100e');g.addColorStop(1,'#0c100e');
  x.fillStyle=g;x.fillRect(0,0,W,H);
  x.strokeStyle='#2a6b4e';x.lineWidth=5;x.strokeRect(22,22,W-44,H-44);
  x.textBaseline='top';x.textAlign='left';
  var date=ex.getAttribute('data-date')||'',tenant=ex.getAttribute('data-tenant')||'',title=ex.getAttribute('data-title')||'',cta=ex.getAttribute('data-cta')||'',moon=ex.getAttribute('data-moon')||'';
  var y=150;
  x.fillStyle='#9fd9bf';x.font='600 30px '+MONO;x.fillText('govOS · GET AHEAD OF THE VOTE',pad,y);y+=78;
  x.fillStyle='#d9b24c';x.font='bold 60px '+MONO;x.fillText(date,pad,y);y+=104;        // date is the headline
  x.fillStyle='#f0ead8';x.font='bold 64px '+SANS;wrap(x,tenant,maxw).slice(0,3).forEach(function(l){x.fillText(l,pad,y);y+=78;});y+=22;
  x.font='600 50px '+SANS;y=band(x,wrap(x,title,maxw).slice(0,6),pad,y,maxw,62,'rgba(255,255,255,.07)','#d9b24c','#f6f0dc'); // meeting title — larger + highlight
  y+=14;x.fillStyle='#e06a4a';x.font='36px '+MONO;x.fillText('⏱ Testify BEFORE the vote',pad,y);y+=62;
  x.fillStyle='#9fd9bf';x.font='38px '+SANS;wrap(x,cta,maxw).slice(0,3).forEach(function(l){x.fillText(l,pad,y);y+=50;});
  if(moon){y+=24;x.font='600 44px '+SANS;y=band(x,wrap(x,'🌙 '+moon,maxw).slice(0,3),pad,y,maxw,56,'rgba(205,180,240,.18)','#cdb4f0','#efe4ff');} // moon offering — larger purple highlight
  x.fillStyle='#9a957f';x.font='28px '+MONO;x.textAlign='center';x.fillText('⚖ 12 Stones · Kilo Aupuni · the people’s record',W/2,H-96);
  return cv;
 }
 function fname(ex){var d=(ex.getAttribute('data-date')||'agenda').replace(/[^0-9A-Za-z-]/g,'');var t=(ex.getAttribute('data-tenant')||'card').replace(/[^0-9A-Za-z]+/g,'-').replace(/(^-|-$)/g,'');return 'govOS_'+d+'_'+t+'.png';}
 try{window.govosDrawCard=drawCard;}catch(e){}   // exposed for verification + future batch export
 function toPng(ex,cb){drawCard(ex).toBlob(function(b){cb(b);},'image/png');}
 function dl(blob,name){var a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download=name;document.body.appendChild(a);a.click();a.remove();setTimeout(function(){URL.revokeObjectURL(a.href);},4000);}
 document.querySelectorAll('.ex').forEach(function(ex){
  var cap=ex.getAttribute('data-cap'),url=ex.getAttribute('data-url');
  var ttl='govOS agenda — '+(ex.getAttribute('data-tenant')||'')+' — '+(ex.getAttribute('data-date')||'');
  var xb=ex.querySelector('[data-x]');if(xb)xb.href='https://twitter.com/intent/tweet?text='+encodeURIComponent(cap)+'&url='+encodeURIComponent(url);
  var fb=ex.querySelector('[data-fb]');if(fb)fb.href='https://www.facebook.com/sharer/sharer.php?u='+encodeURIComponent(url)+'&quote='+encodeURIComponent(cap);
  var sh=ex.querySelector('[data-share]');if(sh)sh.addEventListener('click',function(){var o=sh.textContent;sh.textContent='Rendering…';toPng(ex,function(blob){
    var file=new File([blob],fname(ex),{type:'image/png'});
    if(navigator.canShare&&navigator.canShare({files:[file]})){navigator.share({files:[file],title:ttl,text:cap}).then(function(){sh.textContent=o;}).catch(function(){sh.textContent=o;});}
    else{dl(blob,fname(ex));if(navigator.clipboard)navigator.clipboard.writeText(cap+' '+url);sh.textContent='Saved .png + caption copied';setTimeout(function(){sh.textContent=o;},2600);}
  });});
  var sv=ex.querySelector('[data-save]');if(sv)sv.addEventListener('click',function(){var o=sv.textContent;sv.textContent='Rendering…';toPng(ex,function(blob){dl(blob,fname(ex));sv.textContent='Saved ✓';setTimeout(function(){sv.textContent=o;},1800);});});
  var cp=ex.querySelector('[data-copy]');if(cp)cp.addEventListener('click',function(){if(navigator.clipboard)navigator.clipboard.writeText(cap+' '+url);var o=cp.textContent;cp.textContent='Copied ✓';setTimeout(function(){cp.textContent=o;},1500);});
 });
})();
</script>"""
    return ("<!DOCTYPE html><html lang=\"en\"><head><meta charset=\"UTF-8\">"
      "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1, viewport-fit=cover\">"
      "<title>Agenda Explainer — get ahead of the vote | govOS</title>" + CSS + "</head><body><div class=\"wrap\">"
      "<div class=\"eyebrow\">12 Stones Global · Kilo Aupuni · forecast → fact → publish</div>"
      "<h1>Agenda Explainer — get ahead of the vote</h1>"
      "<p class=\"lead\">Every upcoming meeting becomes a shareable fact-card: what's being decided, the law that "
      "governs it, the money behind the deciders, and how to testify <b>before</b> the vote. Tap <b>Share graphic</b> to send "
      "the 9:16 card <b>image</b> (with the date in its title) straight to TikTok / Instagram / Facebook / X with the caption — "
      "or <b>Save card</b> to download the .png. Each government has its own cards below.</p>" + jumpnav + cards +
      "<footer>generated " + g + " · agenda-explainer v1 · live from the daily agenda feed · share opens your own apps — no auto-posting · Kilo Aupuni · aloha · pono</footer>"
      + JS + "</div></body></html>")

def main():
    os.makedirs(MAUIOS, exist_ok=True)
    open(OUT, "w", encoding="utf-8", newline="\n").write(build())
    print("agenda-explainer: shareable fact-cards built from the live agenda feed")
    return 0

if __name__ == "__main__":
    import sys; sys.exit(main())
