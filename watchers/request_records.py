#!/usr/bin/env python3
"""request_records.py — "Request the Record", TENANT-AWARE.

Every tenant has its OWN access-to-information regime and its OWN records office — a Maui UIPA
request is useless in London or Hong Kong. This builds request_records.html with: the hot topic
drafts (Lahaina rebuild permits, FEMA housing rates), a per-tenant card for each of the 16 govOS
tenants (the real law + citation + requesting authority + portal + local circumstances + a copy-ready
request templated to that law), and a form to send the records back to govOS.

Every regime named is a real, flagship public-records law; the SPECIFIC office/portal can move, so
each card says "verify the current office/portal." Where a jurisdiction has NO general access law
(Singapore; the Holy See), it says so honestly rather than inventing a process.
Output: reports/mauios/request_records.html
"""
import os, html
from datetime import datetime, timezone, timedelta

HOME    = os.path.expanduser("~")
PROJECT = os.path.join(HOME, "Documents", "Claude", "Projects", "Video System elementLOTUS")
MAUIOS  = os.path.join(PROJECT, "reports", "mauios")
OUT     = os.path.join(MAUIOS, "request_records.html")
HST     = timezone(timedelta(hours=-10))
esc     = lambda s: html.escape(str(s or ""))
def now_hst(): return datetime.now(HST)

# id -> (display, access law + citation, requesting authority/office, portal/tool, local-circumstance note)
TENANTS = [
 ("state","State of Hawaiʻi","UIPA — Uniform Information Practices Act, HRS Chapter 92F","the agency's records officer; oversight by the Office of Information Practices (OIP)","oip.hawaii.gov","Strong open-records law; agencies must respond within ~10 business days. Campaign finance is separately public via the Campaign Spending Commission."),
 ("maui","Maui County","UIPA, HRS Chapter 92F","Office of the County Clerk / the relevant department (e.g. Public Works for permits)","mauicounty.gov · oip.hawaii.gov","Committee/Council agendas + minutes are already public on Legistar; permit CONTACTS (contractor/architect) need a UIPA request — they aren't in the public portal."),
 ("honolulu","City & County of Honolulu","UIPA, HRS Chapter 92F","Office of the City Clerk / the relevant department","honolulu.gov · oip.hawaii.gov","Same State UIPA; records via the department holding them."),
 ("hawaii","Hawaiʻi County","UIPA, HRS Chapter 92F","County of Hawaiʻi — the department/Clerk holding the record","hawaiicounty.gov · oip.hawaii.gov","County procurement is posted on the county's own site, not the State HANDS system — request it from the county directly."),
 ("kauai","Kauaʻi County","UIPA, HRS Chapter 92F","County of Kauaʻi — the department/Clerk","kauai.gov · oip.hawaii.gov","Kauaʻi files little to the State HANDS system; county contract records must come from the county itself."),
 ("nys","State of New York","FOIL — Freedom of Information Law, NY Public Officers Law Art. 6 (§§84–90)","the agency's Records Access Officer; guidance from the Committee on Open Government","dos.ny.gov/committee-open-government","Agencies must acknowledge within 5 business days. Roll-call votes are also live via the Open Legislation API (key)."),
 ("nyc","New York City","FOIL (NY Public Officers Law Art. 6)","the agency's Records Access Officer via the NYC OpenRecords portal","a836-openrecords.nyc.gov","NYC has a central OpenRecords portal — file once, route to any agency. Council legislation/votes are on Legistar."),
 ("liverpool","Village of Liverpool, NY","FOIL (NY Public Officers Law Art. 6)","the Village Clerk / Records Access Officer","villageofliverpool.org","Small village — records via the Village Clerk; NY FOIL's 5-business-day acknowledgment applies."),
 ("london","City of London / Greater London","UK Freedom of Information Act 2000","the body's Information Governance / FOI team (City of London Corporation; or the GLA)","cityoflondon.gov.uk · london.gov.uk · whatdotheyknow.com","20-working-day response. WhatDoTheyKnow.com files + publishes UK FOI requests for you."),
 ("tokyo","Tokyo Metropolis","Tokyo Metropolitan Information Disclosure Ordinance (+ Japan's Act on Access to Information Held by Administrative Organs)","the Tokyo Metropolitan Government disclosure counter (Japanese)","www.metro.tokyo.lg.jp","Requests are made in Japanese; non-residents may request. The TMG has a formal disclosure-request procedure."),
 ("hongkong","Hong Kong SAR","Code on Access to Information (administrative code)","the department's Access to Information Officer","access.gov.hk","Not a statutory FOI act but an administrative Code; departments designate an Access to Information Officer. LegCo voting results are already public (VRDB)."),
 ("singapore","Singapore","No general Freedom-of-Information Act","the specific agency (disclosure is statute-specific / discretionary)","gov.sg","HONEST NOTE: Singapore has no general public-records access law; data comes from what agencies choose to publish (e.g. Hansard, data.gov.sg) and statute-specific mechanisms."),
 ("zurich","Zürich (Switzerland)","Federal Act on Freedom of Information (BGÖ) + Canton Zürich Information & Data-Protection Act (IDG)","the federal/cantonal authority's information officer; oversight by the EDÖB (federal)","edoeb.admin.ch · zh.ch","Switzerland presumes access since 2006; cantonal IDG covers Zürich's own bodies."),
 ("frankfurt","Frankfurt am Main (Germany)","Informationsfreiheitsgesetz (IFG, federal) + Hessen IFG","the authority holding the record","fragdenstaat.de","FragDenStaat.de files + publishes German FOI requests for you; Hesse has its own IFG for Land/municipal bodies."),
 ("paris","Paris (France)","Loi CADA (loi du 17 juillet 1978; Code des relations entre le public et l'administration)","the administration's PRADA (records officer); appeal to the CADA","cada.fr","France presumes access to administrative documents; if refused, the CADA reviews. Conseil de Paris deliberations are published."),
 ("dubai","Dubai (UAE) + DIFC","No comprehensive federal access-to-information statute (UAE)","the specific Dubai/UAE authority; DIFC bodies operate separately","dubai.gov.ae · difc.ae","HONEST NOTE: the UAE has no general right-to-information law; access is largely discretionary or sector-specific. The DIFC financial free zone runs under its own common-law framework + data-protection law. Open data via Dubai Pulse / Bayanat."),
 ("holysee","Holy See / Vatican City State","No public freedom-of-information regime","— (financial reports are published voluntarily)","vatican.va","HONEST NOTE: there is no FOI law; the Holy See publishes audited accounts voluntarily via the Secretariat for the Economy (the figures govOS already shows)."),
]
US_FEMA = ("FOIA — Freedom of Information Act, 5 U.S.C. §552", "the agency's FOIA officer (e.g. FEMA-FOIA@fema.dhs.gov)", "foia.gov")

def draft_for(label, law, cite_hint):
    return ("Re: %s request — [the records you seek]\n\n"
            "Pursuant to %s, I request the following public records held by %s:\n"
            "1. [Describe the record — e.g. the contract/permit/vote log, with names, dates, dollar amounts].\n"
            "2. [Any related criteria, correspondence, or rate schedules].\n\n"
            "Electronic form preferred. If any portion is withheld, please cite the specific exemption and "
            "release the rest. I am happy to narrow the request to reduce any fee." ) % (law.split("—")[0].strip(), law, label)

CSS = ("<style> body{margin:0;background:#0c100e;color:#e8e4d8;font-family:Georgia,serif;line-height:1.6}"
 " .wrap{max-width:860px;margin:0 auto;padding:30px 22px calc(env(safe-area-inset-bottom,0px) + 80px)}"
 " .eyebrow{font-family:Consolas,monospace;font-size:11px;letter-spacing:1.3px;color:#d9b24c;text-transform:uppercase}"
 " h1{font-size:27px;margin:8px 0 6px} h2{font-size:18px;margin:26px 0 8px;color:#f0ead8} h3{font-size:14px;margin:0 0 2px;color:#f0ead8}"
 " .lead{font-size:14px;color:#cfc9b6;max-width:74ch}"
 " .req,.ten{border:1px solid #243029;border-radius:13px;padding:14px 16px;margin:12px 0;background:#151d19}"
 " .ten{scroll-margin-top:70px} .who{font-family:Consolas,monospace;font-size:11px;color:#9fd9bf;margin:3px 0}"
 " .law{font-size:13px;color:#e8e4d8} .port{font-family:Consolas,monospace;font-size:11px;color:#d9b24c} .circ{font-size:12px;color:#9a957f;font-style:italic;margin-top:5px}"
 " textarea{width:100%;background:#0e1411;color:#e8e4d8;border:1px solid #243029;border-radius:9px;padding:11px 12px;font-family:Consolas,monospace;font-size:12px;min-height:120px;resize:vertical}"
 " .btns{display:flex;gap:9px;flex-wrap:wrap;margin:9px 0 2px}"
 " .btn{font-family:Consolas,monospace;font-size:12px;padding:8px 14px;border-radius:9px;border:1px solid #d9b24c;color:#d9b24c;background:rgba(217,178,76,.06);cursor:pointer;text-decoration:none}"
 " .btn.primary{background:#d9b24c;color:#0c100e;font-weight:700} .btn:hover{background:rgba(217,178,76,.16)}"
 " label{display:block;font-size:11.5px;color:#9a957f;font-family:Consolas,monospace;text-transform:uppercase;letter-spacing:.5px;margin:12px 0 4px}"
 " input,select{width:100%;background:#0e1411;color:#e8e4d8;border:1px solid #243029;border-radius:9px;padding:11px 12px;font-family:inherit;font-size:14px}"
 " .row2{display:flex;gap:12px;flex-wrap:wrap}.row2>div{flex:1;min-width:180px}"
 " .note{font-size:11.5px;color:#9a957f;font-style:italic;margin-top:8px} #msg{font-family:Consolas,monospace;font-size:13px;margin:8px 0} .okmsg{color:#56c08a} .errmsg{color:#e06a4a}"
 " .aloha{font-size:13px;color:#9fd9bf;border-left:3px solid #2a6b4e;padding:9px 13px;margin:18px 0;line-height:1.65}"
 " .jump{font-size:12px;color:#cfc9b6} .jump a{color:#d9b24c;font-family:Consolas,monospace;font-size:11px}"
 " a{color:#d9b24c} footer{margin-top:30px;border-top:1px solid #243029;padding-top:12px;font-family:Consolas,monospace;font-size:10.5px;color:#9a957f}</style>")

def ten_card(i, t):
    tid, name, law, who, port, circ = t
    no_law = "No general" in law or "No public" in law
    draft = "" if no_law else (
        '<textarea id="t%d" readonly>%s</textarea>'
        '<div class="btns"><button class="btn primary" data-copy="t%d">Copy a starter request</button>'
        '%s</div>' % (i, esc(draft_for(who, law, "")), i,
                      ('<a class="btn" href="https://%s" target="_blank" rel="noopener">records portal ↗</a>' % esc(port.split(" ")[0]))))
    return ('<div class="ten" id="%s"><h3>%s</h3>'
            '<div class="law"><b>%s</b></div>'
            '<div class="who">file with: %s</div>'
            '<div class="port">%s</div>'
            '<div class="circ">%s%s</div>%s</div>') % (
        esc(tid), esc(name), esc(law), esc(who), esc(port), esc(circ),
        " — verify the current office/portal before filing." , draft)

def build():
    g = now_hst().strftime("%Y-%m-%d %H:%M HST")
    jump = " · ".join('<a href="#%s">%s</a>' % (esc(t[0]), esc(t[1].split("(")[0].split("/")[0].strip())) for t in TENANTS)
    cards = "".join(ten_card(i, t) for i, t in enumerate(TENANTS))
    # the hot topic drafts keep their existing anchors so the inline gap-links still resolve
    maui_draft = ("Re: Uniform Information Practices Act (HRS §92F-11) request — disaster-recovery building permits, Lahaina & Kula\n\n"
      "Pursuant to HRS Chapter 92F, I request: (1) all fire-rebuild building permits for parcels in LAHAINA and KULA from "
      "August 8, 2023 to present — permit number; application date; ISSUE date; status; parcel/TMK; address; owner/applicant; "
      "the GENERAL CONTRACTOR of record; and the ARCHITECT/ENGINEER of record; (2) any expedited/priority-review criteria and "
      "which permits received it; (3) which were commercial vs. residential, and the order issued. Electronic (CSV/Excel) preferred.")
    fema_draft = ("Re: FOIA request (5 U.S.C. §552) — Maui (DR-4724-HI) disaster-housing contracts & rates\n\n"
      "For the August 2023 Hawaiʻi wildfires (DR-4724-HI, Maui), I request: (1) all Direct Housing / Direct Lease / rental-assistance "
      "contracts, task orders, and RATE schedules — vendor names, award amounts, per-unit/per-night rates; (2) records identifying any "
      "contractor/lessor also licensed in Hawaiʻi as a real-estate broker; (3) rates paid relative to fair-market rent. Public-interest fee waiver requested.")
    return ("<!DOCTYPE html><html lang=\"en\"><head><meta charset=\"UTF-8\">"
      "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1, viewport-fit=cover\">"
      "<title>Request the Record — every tenant's own process | Kilo Aupuni</title>" + CSS + "</head><body><div class=\"wrap\">"
      "<div class=\"eyebrow\">12 Stones Global · Kilo Aupuni · request the record</div>"
      "<h1>Request the Record — and send it back to build govOS</h1>"
      "<p class=\"lead\">Some of the most important data isn't online yet — but it is <b>public record</b>, and you can request it. "
      "Every government has its OWN access law and records office, so the right request is below <b>per tenant</b>. Copy one, file it, "
      "and when the records come back, <b>send them here</b> so they join the public map.</p>"
      "<div class=\"jump\">Jump to your jurisdiction: " + jump + "</div>"
      "<h2 id=\"county-permits\">Featured: Lahaina &amp; Kula rebuild permits — contractor &amp; architect names</h2>"
      "<div class=\"req\"><div class=\"who\">file with: County of Maui (UIPA, HRS §92F) — Clerk / Public Works · mauicounty.gov</div>"
      "<textarea id=\"r1\" readonly>" + esc(maui_draft) + "</textarea>"
      "<div class=\"btns\"><button class=\"btn primary\" data-copy=\"r1\">Copy this request</button></div></div>"
      "<h2 id=\"fema\">Featured: FEMA disaster-housing rates &amp; contractors (DR-4724-HI)</h2>"
      "<div class=\"req\"><div class=\"who\">file with: FEMA FOIA Office — FEMA-FOIA@fema.dhs.gov (5 U.S.C. §552)</div>"
      "<textarea id=\"r2\" readonly>" + esc(fema_draft) + "</textarea>"
      "<div class=\"btns\"><button class=\"btn primary\" data-copy=\"r2\">Copy this request</button>"
      "<a class=\"btn\" href=\"mailto:FEMA-FOIA@fema.dhs.gov?subject=FOIA%20request%20DR-4724-HI\" target=\"_blank\" rel=\"noopener\">Email FEMA FOIA ↗</a></div></div>"
      "<h2>Your jurisdiction's records office</h2>"
      "<p class=\"lead\">Each govOS tenant, its real access law, and where to file. (US federal records, like FEMA: " + esc(US_FEMA[0]) + ".)</p>"
      + cards +
      "<h2>Got records back? Send them here →</h2>"
      "<form id=\"rec\" method=\"POST\" action=\"https://formspree.io/f/xzdqydpe\">"
      "<label>Which tenant / record is this?</label><input name=\"record\" id=\"f_rec\" placeholder=\"e.g. Maui rebuild permits · NYC FOIL · London FOIA\">"
      "<label>Paste the agency response (or key facts)</label>"
      "<textarea name=\"response\" id=\"f_resp\" style=\"min-height:110px;font-family:inherit;font-size:14px\" placeholder=\"names, dates, dollar amounts…\"></textarea>"
      "<label>Link to the files (Google Drive / Dropbox — for PDFs &amp; spreadsheets)</label>"
      "<input name=\"files_link\" id=\"f_link\" placeholder=\"https://… shareable link\">"
      "<div class=\"row2\"><div><label>Your name (optional)</label><input name=\"name\" id=\"f_name\"></div>"
      "<div><label>Your email</label><input name=\"email\" id=\"f_email\" type=\"email\"></div></div>"
      "<input type=\"hidden\" name=\"_subject\" value=\"govOS — public records received from the community\">"
      "<div class=\"btns\"><button class=\"btn primary\" type=\"submit\">Send the records to govOS →</button>"
      "<a class=\"btn\" id=\"mailbtn\" target=\"_blank\" rel=\"noopener\">…or email them</a></div><div id=\"msg\" role=\"status\"></div>"
      "<p class=\"note\">Big files? Put them in a Drive/Dropbox folder and paste the link — the originals reach the public map.</p></form>"
      "<div class=\"aloha\">Aloha. The record belongs to the people; sometimes it just has to be asked for — in the right office, "
      "under the right law. When you request a record and send it back, a “pending” becomes a fact on the ledger. Mahalo for carrying a stone.</div>"
      "<footer>generated " + g + " · request-records v2 (tenant-aware) · UIPA · FOIL · FOIA · UK FOIA · CADA · IFG · BGÖ · Code on Access · public records by the people · aloha · pono</footer>"
      "<script>"
      "document.querySelectorAll('button[data-copy]').forEach(function(b){b.addEventListener('click',function(){var t=document.getElementById(b.getAttribute('data-copy'));t.select();try{document.execCommand('copy');}catch(e){}if(navigator.clipboard)navigator.clipboard.writeText(t.value);var o=b.textContent;b.textContent='Copied ✓';setTimeout(function(){b.textContent=o;},1500);});});"
      "(function(){var f=document.getElementById('rec'),msg=document.getElementById('msg'),mail=document.getElementById('mailbtn');"
      "function r(){var b='Record: '+(document.getElementById('f_rec').value||'')+'\\n\\n'+(document.getElementById('f_resp').value||'')+'\\n\\nFiles: '+(document.getElementById('f_link').value||'(attached)');mail.href='mailto:?subject='+encodeURIComponent('govOS — public records')+'&body='+encodeURIComponent(b);}"
      "['input','change'].forEach(function(e){f.addEventListener(e,r);});r();"
      "f.addEventListener('submit',function(e){e.preventDefault();var fd=new FormData(f);if(document.getElementById('f_email').value)fd.append('_replyto',document.getElementById('f_email').value);var btn=f.querySelector('button[type=submit]'),l=btn.textContent;btn.disabled=true;btn.textContent='Sending…';fetch(f.action,{method:'POST',body:fd,headers:{'Accept':'application/json'}}).then(function(x){if(x.ok){msg.className='okmsg';msg.textContent='Mahalo — the records reached govOS.';f.querySelectorAll('input,select,textarea,.btns').forEach(function(el){el.style.display='none';});}else{return x.json().then(function(d){throw new Error((d.errors&&d.errors.map(function(y){return y.message;}).join(', '))||'error');});}}).catch(function(err){btn.disabled=false;btn.textContent=l;msg.className='errmsg';msg.textContent='Could not send ('+err.message+'). Use the email button.';});});})();"
      "</script></div></body></html>")

def main():
    os.makedirs(MAUIOS, exist_ok=True)
    open(OUT, "w", encoding="utf-8", newline="\n").write(build())
    print("request-records: tenant-aware page built — %d tenant records-offices + Maui/FEMA featured drafts" % len(TENANTS))
    return 0

if __name__ == "__main__":
    import sys; sys.exit(main())
