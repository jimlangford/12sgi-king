#!/usr/bin/env python3
# beta_portal.py - govOS BETA request portal (Jimmy 2026-06-17). "Build it with your council": Maui County
# Council members verify (Stripe IDENTITY — free, no charge) and request software features, GUIDED BY the
# constituents who sign up in their district. Two doors on one public page:
#   1) CONSTITUENTS — sign up by district + say what they want built (this is the guidance signal).
#   2) COUNCIL MEMBERS — verify identity with Stripe (free), then request features, seeing their district's asks.
#
# HOSTING (Jimmy's choice): Stripe-hosted verification LINK + a hosted form service (no custom backend). This
# generator reads PUBLIC-SAFE links from config/beta.json (gitignored) — a Stripe Identity verification URL and
# form endpoints. NO secret key ever touches this page (the leak gate enforces it). Where a link isn't wired yet
# the section shows a dignified "opening soon" — the page still explains the program. The council gate is a
# client-side beta convenience (reveals the request form after Stripe returns success); true server-side
# enforcement would need the backend option, deliberately not taken for the beta. Stdlib only.
import os, sys, json
HERE=os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path: sys.path.insert(0, HERE)
from votes_watch import ROSTER
from datetime import datetime, timedelta, timezone
HST=timezone(timedelta(hours=-10))
HOME=os.path.expanduser("~"); PROJ=os.path.join(HOME,"Documents","Claude","Projects","Video System elementLOTUS")
M=os.path.join(PROJ,"reports","mauios"); CFG=os.path.join(PROJ,"config","beta.json")
def esc(s): return str(s if s is not None else "").replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")

# the 9 Maui Council seats (district pulled from the roster label) — Bissen is the mayor, not a district seat
def _districts():
    out=[]
    for k,full in ROSTER.items():
        if k=="Bissen": continue
        name=full.split(" - ")[0].strip()
        dist=(full.split(" - ",1)[1].split(",")[0].strip() if " - " in full else "")
        out.append((name,dist or "Maui County"))
    return out

def _cfg():
    try: c=json.load(open(CFG,encoding="utf-8"))
    except Exception: c={}
    def ok(v): return bool(v) and not str(v).startswith("PASTE_")
    return {
        "verify_url": c.get("stripe_identity_url") if ok(c.get("stripe_identity_url")) else "",
        "constituent_form": c.get("constituent_form_url") if ok(c.get("constituent_form_url")) else "",
        "council_form": c.get("council_form_url") if ok(c.get("council_form_url")) else "",
        "district_asks": c.get("district_asks") or {},   # {district: ["ask", ...]} — fills as constituents sign up
    }

def main():
    gen=datetime.now(HST).strftime("%Y-%m-%d %H:%M HST")
    c=_cfg(); dists=_districts()
    # constituent door
    cf=c["constituent_form"]
    csignup=(("<a class=btn href='%s' target='_blank' rel='noopener'>Add your voice &mdash; sign up by district &rarr;</a>"%esc(cf))
             if cf else "<div class=soon>Constituent sign-up opens shortly. Your district&rsquo;s request board is being prepared.</div>")
    # per-district guidance cards
    dcards=""
    for name,dist in dists:
        asks=c["district_asks"].get(dist) or c["district_asks"].get(name) or []
        body=("".join("<li>%s</li>"%esc(a) for a in asks[:5]) if asks else
              "<li class=empty>Be the first &mdash; what should govOS build for %s? Your neighbors&rsquo; requests appear here.</li>"%esc(dist))
        dcards+=("<div class=dc><div class=dh><b>%s</b><span class=dr>%s</span></div><ul>%s</ul></div>")%(
                 esc(dist),esc(name),body)
    # council door — Stripe Identity verify (free) then reveal the request form
    vurl=c["verify_url"]; cform=c["council_form"]
    if vurl:
        verify=("<a class=btn id=verifybtn href='%s'>Verify with Stripe &mdash; free, identity only &rarr;</a>"
                "<div class=fine>Stripe Identity confirms you are a sitting Maui County Council member. "
                "No charge, no card. You return here to file requests.</div>")%esc(vurl)
    else:
        verify="<div class=soon>Council verification opens shortly (Stripe Identity &mdash; free, no charge).</div>"
    if cform:
        reqform=("<div id=council-gate class=gate><div class=glock>&#128274; Verify above to unlock the council request form.</div>"
                 "<a class=btn id=reqbtn href='%s' target='_blank' rel='noopener' style='display:none'>Open the feature-request form &rarr;</a></div>"
                 "<script>(function(){var ok=/[?&](verified|verification|success)=/.test(location.search)||location.hash.indexOf('verified')>=0;"
                 "if(ok){var g=document.getElementById('council-gate');var b=document.getElementById('reqbtn');"
                 "var l=document.querySelector('#council-gate .glock');if(l)l.innerHTML='&#9989; Verified. File your requests — guided by your district below.';if(b)b.style.display='inline-block';}})();</script>")%esc(cform)
    else:
        reqform="<div class=soon>The council request form opens with verification.</div>"

    style=("<style>:root{--bg:#081420;--panel:#0f2540;--line:#26456a;--ink:#eaf2fc;--dim:#9fb2c8;--faint:#6d7f97;--accent:#4a9eff;--accent2:#6cb0f0;--ok:#1f8a5b;--gold:#e3ad33}"
      "*{box-sizing:border-box}body{font-family:'Segoe UI Variable Text','Segoe UI',system-ui,sans-serif;max-width:920px;margin:0 auto;padding:18px 16px 46px;color:var(--ink);background:var(--bg);font-size:16px;line-height:1.55}"
      "a{color:var(--accent2)}h1{font-size:1.6rem;margin:.3rem 0}h2{color:var(--accent);font-size:1.12rem;margin:1.4rem 0 .5rem}.sub{color:var(--dim);font-size:.95rem;line-height:1.55}"
      ".eyebrow{letter-spacing:.1em;text-transform:uppercase;color:var(--accent2);font-weight:600;font-size:.8rem}"
      ".lane{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:1rem 1.1rem;margin:.9rem 0}"
      ".btn{display:inline-block;background:var(--accent);color:#fff;text-decoration:none;font-weight:600;border-radius:10px;padding:.6rem 1rem;margin:.5rem 0;font-size:.95rem}"
      ".btn:hover{background:var(--accent2)}.fine{color:var(--faint);font-size:.82rem;margin-top:.2rem}"
      ".soon{background:#fbf6ea;border:1px solid #e6d8a8;border-radius:10px;padding:.6rem .9rem;color:#5a4a16;font-size:.9rem}"
      ".grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:12px;margin:.6rem 0}"
      ".dc{border:1px solid var(--line);border-radius:11px;padding:.6rem .8rem;background:#fff}.dc .dh{display:flex;justify-content:space-between;gap:8px;align-items:baseline}"
      ".dc .dh b{color:var(--accent)}.dc .dr{color:var(--faint);font-size:.8rem;font-family:Consolas,monospace}.dc ul{margin:.4rem 0 0;padding-left:1.1rem;font-size:.86rem;color:var(--dim)}.dc .empty{color:var(--faint);font-style:italic;list-style:none;margin-left:-1.1rem}"
      ".gate{border:1px dashed var(--line);border-radius:10px;padding:.7rem .9rem;margin:.5rem 0}.glock{color:var(--dim);font-size:.92rem}"
      ".note{background:var(--panel);border:1px solid var(--line);border-left:3px solid var(--gold);border-radius:10px;padding:.7rem 1rem;margin:1rem 0;font-size:.88rem;color:var(--dim);line-height:1.5}"
      ".foot{margin-top:1.6rem;border-top:1px solid var(--line);padding-top:.7rem;color:var(--faint);font-size:.78rem}</style>")
    head=("<!doctype html><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1,viewport-fit=cover'>"
          "<meta name=theme-color content='#00356b'><title>govOS Beta — build it with your council | Maui County</title>")
    body=("<div class=eyebrow>govOS &middot; Maui County &middot; beta program</div>"
      "<h1>Build it with your council</h1>"
      "<p class=sub>govOS is the public-record engine for Maui &mdash; agendas, votes, the money behind the seats, "
      "who testifies, the nay narratives. This beta opens the build to the people it serves: <b>constituents say what "
      "they need</b>, and <b>council members request features guided by their own district</b>. Made in aloha; the "
      "record stays public, the asking stays pono.</p>"
      "<div class=lane><div class=eyebrow>For neighbors &amp; residents</div>"
      "<h2 style='margin-top:.3rem'>Tell your council what to build</h2>"
      "<p class=sub>Sign up by your district and add what govOS should build for your community &mdash; a report, a "
      "watch, a plain-language view. Your requests become the guidance your council member sees below.</p>"
      "%s</div>"
      "<h2>What each district is asking for</h2>"
      "<p class=sub>The constituent signal, by seat &mdash; this is what guides each member&rsquo;s requests.</p>"
      "<div class=grid>%s</div>"
      "<div class=lane><div class=eyebrow>For Maui County Council members</div>"
      "<h2 style='margin-top:.3rem'>Verify, then request &mdash; guided by your district</h2>"
      "<p class=sub>Confirm you hold the seat (Stripe Identity &mdash; free, no charge, no card), then file the "
      "features your office and your constituents need. Your district&rsquo;s requests are listed above to guide you.</p>"
      "%s%s</div>"
      "<div class=note><b>How this works &amp; what it isn&rsquo;t.</b> Verification is identity only (Stripe Identity) "
      "&mdash; there is no charge and no payment is taken. Constituent sign-ups and council requests are collected "
      "through a hosted form; nothing here moves money. govOS remains a public-record tool &mdash; requests shape the "
      "software, never the public record itself.</div>"
      "<p class=sub style='margin-top:1rem'><a href='reports.html'>&larr; govOS home</a> &middot; "
      "<a href='tenant_hi-maui.html'>Maui County overview</a> &middot; <a href='testifiers_maui.html'>who testifies</a> "
      "&middot; <a href='council_votes_maui.html'>council votes</a></p>"
      "<div class=foot>govOS beta &middot; identity verification by Stripe (no charge) &middot; aloha in action &middot; generated %s</div>")%(
      csignup,dcards,verify,reqform,esc(gen))
    html=head+style+body
    open(os.path.join(M,"beta_requests.html"),"w",encoding="utf-8",newline="\n").write(html)
    wired=sum(1 for x in (c["verify_url"],c["constituent_form"],c["council_form"]) if x)
    print("beta_portal: beta_requests.html written (%d/3 links wired; %d districts)"%(wired,len(dists)))
    if wired<3: print("  -> fill config/beta.json: stripe_identity_url, constituent_form_url, council_form_url (public links; NO secret key)")
    return 0

if __name__=="__main__":
    if sys.platform=="win32":
        import io; sys.stdout=io.TextIOWrapper(sys.stdout.buffer,encoding="utf-8",errors="replace")
    sys.exit(main())
