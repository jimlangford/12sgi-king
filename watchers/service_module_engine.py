#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
County Service Module Engine
============================
Turns a *config + sourced-content drop* into a standard, Yale-blue,
iPhone-15/iPad plain-language county-service page in the SAME shape as the
live Title 19 service (king_public_src/civic/templates/title19-service/).

Goal: adding a new MCC title or county service = author a `<id>.config.json`
+ drop sourced content -> run this engine -> get the page. No bespoke HTML.

Layer separation (guardrails baked in):
  A. CONTENT  (sourced)   -> process/tables/enforcement blocks carry a `source`
  B. ANALYSIS (labeled)   -> charter-lens / who-pays / analysis blocks render a
                             persistent "analysis, not law" label
  C. TRANSACTION (gated)  -> MAPPS deep-links (shared adapter) + verification
                             tier box; NO Stripe keys (env-ref only)

Shared components (build once, every module reuses):
  - parcel lookup (Hawaiʻi Statewide GIS) + MAPPS deep-link adapter
  - process / permit tracker (.steps)
  - fee / who-pays + tables
  - charter-lens (.pos)  [Maui County Charter  vs  Sovereign Charter]
  - citation / "expanding" / "sourced" / "dated-opinion" badges
  - Tier-1-free / Tier-3-verified gate box (Stripe = env-ref only)

Usage:
  python tools/service_module_engine.py <config.json> [--out <path>] [--check]

The engine is intentionally dependency-free (stdlib only) and CPU/web only;
it never touches GPU/ASHES/mesh and writes no secrets.
"""
import os, re, json, sys, html, datetime

# --------------------------------------------------------------------------
# SHARED THEME (the design system): Yale-blue, serif body, iPhone-15 @430,
# iPad max-width 980. Lifted verbatim from the live Title 19 service so every
# generated module is visually consistent with the proven page.
# --------------------------------------------------------------------------
THEME_CSS = """ :root{--bg:#ffffff;--panel:#e7eef8;--panel2:#dae5f3;--line:#bacde6;--ink:#13243d;--ink-dim:#41536b;
   --ink-faint:#6d7f97;--accent:#00356b;--accent2:#1259a3;--ok:#1f8a5b;--warn:#b07d1a;--err:#c0322c;--lahaina:#b3541e;}
 *{box-sizing:border-box} body{margin:0;background:var(--bg);color:var(--ink);font-family:Georgia,'Iowan Old Style',serif;line-height:1.6}
 .wrap{max-width:980px;margin:0 auto;padding:18px 16px 80px}
 .top{display:flex;gap:10px;align-items:center;flex-wrap:wrap;font-family:Consolas,monospace;font-size:11.5px}
 .top a{color:var(--accent2);text-decoration:none;border:1px solid var(--line);border-radius:7px;padding:5px 10px}
 .eyebrow{font-family:Consolas,monospace;font-size:11px;letter-spacing:1.5px;color:var(--accent);text-transform:uppercase;margin-top:12px}
 h1{font-size:28px;font-weight:600;margin:6px 0 4px;line-height:1.15}
 .lead{font-size:15.5px;color:var(--ink-dim);max-width:80ch}
 .free{display:inline-block;background:var(--ok);color:#fff;font-family:Consolas,monospace;font-size:11px;font-weight:700;letter-spacing:.5px;padding:3px 10px;border-radius:6px;text-transform:uppercase}
 h2{font-size:13px;font-family:Consolas,monospace;letter-spacing:1px;text-transform:uppercase;color:var(--ink-faint);margin:30px 0 8px;border-bottom:1px solid var(--line);padding-bottom:6px}
 h3{font-size:18px;font-weight:600;margin:16px 0 4px}
 .src{font-family:Consolas,monospace;font-size:11.5px;color:var(--ink-faint)} .src a{color:var(--accent2)}
 .src::before{content:"Source: ";font-weight:700;color:var(--ink-dim)}
 .exp{display:inline-block;font-family:Consolas,monospace;font-size:10px;font-weight:700;letter-spacing:.5px;text-transform:uppercase;color:var(--warn);border:1px solid var(--warn);border-radius:9px;padding:1px 8px;margin-left:6px}
 .pos{font-size:13.5px;color:var(--accent);background:rgba(0,53,107,.06);border-left:3px solid var(--accent);border-radius:8px;padding:9px 13px;margin:8px 0}
 .pos b{color:var(--accent)} .pos .b{font-family:Consolas,monospace;font-size:10px;letter-spacing:.5px;text-transform:uppercase;color:var(--warn);display:block;margin-bottom:2px}
 .lens{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin:8px 0}
 .lens .col{border:1px solid var(--line);border-radius:9px;padding:9px 12px;background:#fbfdff;font-size:13.5px}
 .lens .col .h{font-family:Consolas,monospace;font-size:10px;letter-spacing:.5px;text-transform:uppercase;color:var(--ink-faint);display:block;margin-bottom:3px}
 @media(max-width:560px){.lens{grid-template-columns:1fr}}
 .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(210px,1fr));gap:11px;margin-top:10px}
 .card{display:block;border:1px solid var(--line);border-radius:11px;background:var(--panel);padding:13px 15px;text-decoration:none;color:inherit}
 .card.lah{border-color:var(--lahaina);background:#fbf2ec;border-width:2px}
 .card .t{font-weight:600;font-size:15.5px;color:var(--ink)} .card.lah .t{color:var(--lahaina)}
 .card .b{font-size:12.5px;color:var(--ink-dim);margin-top:3px}
 table{width:100%;border-collapse:collapse;font-size:13.5px;margin-top:8px;display:block;overflow-x:auto}
 th,td{text-align:left;padding:8px 10px;border-bottom:1px solid var(--line);white-space:nowrap} th{font-family:Consolas,monospace;font-size:11px;text-transform:uppercase;letter-spacing:.5px;color:var(--ink-faint)}
 .y{color:var(--ok);font-weight:700}.c{color:var(--warn);font-weight:700}.n{color:var(--err);font-weight:700}
 .steps{counter-reset:s;padding:0;margin:10px 0;list-style:none}
 .steps li{position:relative;padding:10px 12px 10px 46px;border:1px solid var(--line);border-radius:10px;background:#fbfdff;margin-bottom:8px}
 .steps li::before{counter-increment:s;content:counter(s);position:absolute;left:11px;top:11px;width:26px;height:26px;border-radius:50%;background:var(--accent);color:#fff;font-family:Consolas,monospace;font-weight:700;display:flex;align-items:center;justify-content:center;font-size:13px}
 .steps .w{font-size:12.5px;color:var(--ink-dim);margin-top:3px} .steps .pay{font-family:Consolas,monospace;font-size:11.5px;color:var(--accent2);margin-top:3px}
 .tier3{border:1px dashed var(--accent);border-radius:10px;background:rgba(0,53,107,.04);padding:11px 14px;margin-top:10px;font-size:13px;color:var(--ink-dim)}
 .note{font-size:12.5px;color:var(--ink-faint);font-style:italic;margin:6px 0}
 svg{max-width:100%;height:auto} a{color:var(--accent2)}
 .tool{border:1px solid var(--accent);border-radius:12px;background:rgba(0,53,107,.04);padding:14px 16px;margin:10px 0}
 .tool .r{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin:8px 0 4px}
 .tool input{flex:1;min-width:170px;font:inherit;font-size:16px;padding:10px 12px;border:1px solid var(--line);border-radius:9px;background:#fff;color:var(--ink)}
 .tool button{font:inherit;font-size:14px;font-weight:700;padding:10px 18px;border-radius:9px;border:1px solid var(--accent);background:var(--accent);color:#fff;cursor:pointer;min-height:44px}
 .tool button:disabled{opacity:.5}
 .res{margin-top:8px} .res dl{display:grid;grid-template-columns:max-content 1fr;gap:5px 14px;margin:0;font-size:14px}
 .res dt{font-family:Consolas,monospace;font-size:11px;text-transform:uppercase;letter-spacing:.5px;color:var(--ink-faint);padding-top:2px}
 .res dd{margin:0;font-weight:600;color:var(--ink)}
 .res .out{display:flex;gap:8px;flex-wrap:wrap;margin-top:10px}
 .res .out a{font-family:Consolas,monospace;font-size:12px;border:1px solid var(--line);border-radius:7px;padding:6px 10px;text-decoration:none}
 .live{display:inline-block;font-family:Consolas,monospace;font-size:10px;font-weight:700;letter-spacing:.5px;text-transform:uppercase;color:var(--ok);border:1px solid var(--ok);border-radius:9px;padding:1px 8px;margin-left:6px;vertical-align:middle}
 .model{border:1px dashed var(--warn);border-radius:10px;background:rgba(176,125,26,.06);padding:6px 12px;font-size:12.5px;color:var(--ink-dim);margin:7px 0}
 .model b{color:var(--warn)}
 .answers td{white-space:normal}
 footer{font-family:Consolas,monospace;font-size:10.5px;color:var(--ink-faint);margin-top:30px;border-top:1px solid var(--line);padding-top:12px}
 @media(max-width:430px){ h1{font-size:23px} .wrap{padding:14px 12px 70px} .res dl{grid-template-columns:1fr} .res dt{padding-top:8px} }"""

# Shared MAPPS adapter — the county's live self-service transaction system.
# The digital twin is a LAYER OVER the code that HANDS OFF here at the
# money/identity step; it is not a replacement for the official record.
MAPPS_SELF_SERVICE = "https://mapps2.co.maui.hi.us/EnerGov_Prod/SelfService"

def esc(s):
    return html.escape(str(s if s is not None else ""), quote=True)

def _src(source):
    """Render a Source: line. `source` = {text, html?} ; may carry inline <a>."""
    if not source:
        return ""
    if isinstance(source, str):
        return '<p class="src">%s</p>' % source
    body = source.get("html") or esc(source.get("text", ""))
    badge = ' <span class="exp">%s</span>' % esc(source["expanding"]) if source.get("expanding") else ""
    return '<p class="src">%s%s</p>' % (body, badge)

def _badge(b):
    if not b:
        return ""
    kind = b.get("kind", "exp")
    cls = {"exp": "exp", "live": "live"}.get(kind, "exp")
    return ' <span class="%s">%s</span>' % (cls, esc(b.get("text", "")))

# --------------------------------------------------------------------------
# SECTION RENDERERS (each consumes a typed block from config["sections"])
# --------------------------------------------------------------------------
def r_prose(b):
    out = ['<h2>%s%s</h2>' % (esc(b["title"]), _badge(b.get("badge")))]
    if b.get("note"):
        out.append('<p class="note">%s</p>' % b["note"])
    if b.get("html"):
        out.append(b["html"])
    out.append(_src(b.get("source")))
    return "\n".join(out)

def r_cards(b):
    out = ['<h2>%s%s</h2>' % (esc(b["title"]), _badge(b.get("badge")))]
    if b.get("note"):
        out.append('<p class="note">%s</p>' % b["note"])
    out.append('<div class="grid">')
    for c in b.get("cards", []):
        cls = "card lah" if c.get("lahaina") else "card"
        flag = ' <span class="exp">%s</span>' % esc(c["flag"]) if c.get("flag") else ""
        out.append('<a class="%s" href="%s" target="_blank" rel="noopener"><div class="t">%s</div><div class="b">%s%s</div></a>'
                   % (cls, esc(c["href"]), esc(c["title"]), esc(c.get("body", "")), flag))
    out.append('</div>')
    out.append(_src(b.get("source")))
    return "\n".join(out)

def r_table(b):
    out = ['<h2>%s%s</h2>' % (esc(b["title"]), _badge(b.get("badge")))]
    if b.get("note"):
        out.append('<p class="note">%s</p>' % b["note"])
    out.append('<table><thead><tr>%s</tr></thead><tbody>'
               % "".join("<th>%s</th>" % esc(c) for c in b["columns"]))
    for row in b["rows"]:
        cells = []
        for cell in row:
            if isinstance(cell, dict):  # {v, cls?, html?}
                inner = cell.get("html") or esc(cell.get("v", ""))
                cls = ' class="%s"' % esc(cell["cls"]) if cell.get("cls") else ""
                cells.append("<td%s>%s</td>" % (cls, inner))
            else:
                cells.append("<td>%s</td>" % esc(cell))
        out.append("<tr>%s</tr>" % "".join(cells))
    out.append('</tbody></table>')
    out.append(_src(b.get("source")))
    return "\n".join(out)

def r_process(b):
    out = ['<h2>%s%s</h2>' % (esc(b["title"]), _badge(b.get("badge")))]
    if b.get("note"):
        out.append('<p class="note">%s</p>' % b["note"])
    out.append('<ol class="steps">')
    for s in b["steps"]:
        w = '<div class="w">%s</div>' % s["what"] if s.get("what") else ""
        pay = '<div class="pay">%s</div>' % esc(s["pay"]) if s.get("pay") else ""
        out.append('<li><b>%s</b>%s%s</li>' % (s["name"], w, pay))
    out.append('</ol>')
    if b.get("charterLens"):
        out.append(r_charter_lens(b["charterLens"], standalone=False))
    out.append(_src(b.get("source")))
    return "\n".join(out)

def r_charter_lens(b, standalone=True):
    """LAYER B — dual-charter lens, always labeled analysis (not law)."""
    blocks = []
    if standalone and b.get("title"):
        blocks.append('<h2>%s <span class="exp">analysis</span></h2>' % esc(b["title"]))
    if b.get("note"):
        blocks.append('<p class="note">%s</p>' % b["note"])
    maui = b.get("mauiCharter")
    sov = b.get("sovereignCharter")
    if maui or sov:
        blocks.append('<div class="lens">'
            '<div class="col"><span class="h">Maui County Charter — lens</span>%s</div>'
            '<div class="col"><span class="h">Sovereign Charter (12 Stones) — lens</span>%s</div>'
            '</div>' % (maui or "&mdash;", sov or "&mdash;"))
    if b.get("position"):
        p = b["position"]
        blocks.append('<div class="pos"><span class="b">%s</span>%s</div>'
                      % (esc(p.get("label", "⚖️ Position — analysis, not law")), p["text"]))
    if b.get("source"):
        blocks.append(_src(b["source"]))
    return "\n".join(blocks)

def r_analysis_list(b):
    out = ['<h2>%s <span class="exp">analysis</span></h2>' % esc(b["title"])]
    out.append('<div class="pos"><span class="b">⚖️ Analysis / position — not law</span>%s</div>' % b.get("intro", ""))
    out.append('<ul style="font-size:14.5px;padding-left:18px">')
    for it in b["items"]:
        out.append("<li>%s</li>" % it)
    out.append('</ul>')
    out.append(_src(b.get("source")))
    return "\n".join(out)

def r_model(b):
    """A labeled 'proposed model / dated opinion' block (Layer B)."""
    out = ['<h2>%s%s</h2>' % (esc(b["title"]), _badge(b.get("badge")))]
    out.append('<div class="model"><b>%s</b> %s</div>' % (esc(b.get("label", "PROPOSED MODEL — not adopted law.")), b.get("text", "")))
    if b.get("html"):
        out.append(b["html"])
    out.append(_src(b.get("source")))
    return "\n".join(out)

def r_tier_gate(b):
    return '<div class="tier3">%s</div>' % b["text"]

def r_raw(b):
    return b.get("html", "")

def r_parcel_lookup(b):
    """Shared LOOKUP component: live Hawaiʻi Statewide GIS designations +
    MAPPS deep-link for this parcel's permits. No parcel data stored."""
    title = b.get("title", "★ Parcel lookup")
    note = b.get("note", "")
    return (
      '<h2>%s <span class="live">live data</span></h2>\n'
      '<p class="note">%s</p>\n'
      '<div class="tool">\n'
      ' <div class="r"><input id="tmk" type="text" inputmode="numeric" placeholder="TMK digits — e.g. 211001001" aria-label="Tax Map Key"><button id="plk" onclick="lookupTMK()">Look up</button></div>\n'
      ' <div class="res" id="pres"><p class="note">Tip: type the digits of your TMK (zone-section-plat-parcel). Don\'t know it? Open the <a href="https://experience.arcgis.com/experience/d91bec49db3a4ef9b52f497a136562e6" target="_blank" rel="noopener">State Land Use Viewer ↗</a> to find it on a map.</p></div>\n'
      '</div>\n'
      '%s' % (title, note, _src(b.get("source")))
    )

SECTION_RENDERERS = {
    "prose": r_prose, "cards": r_cards, "table": r_table, "process": r_process,
    "charter-lens": r_charter_lens, "analysis-list": r_analysis_list,
    "model": r_model, "tier-gate": r_tier_gate, "parcel-lookup": r_parcel_lookup,
    "raw": r_raw,
}

# --------------------------------------------------------------------------
# Shared parcel-lookup JS (GIS + MAPPS adapter), parameterized per module.
# --------------------------------------------------------------------------
def parcel_js(cfg):
    pl = cfg.get("parcelLookup", {})
    mapps_permit = pl.get("mappsPermitUrl", MAPPS_SELF_SERVICE)
    muni = pl.get("codeUrl", "https://library.municode.com/hi/county_of_maui/codes/code_of_ordinances")
    code_label = pl.get("codeRowLabel", "Code chapter")
    code_link_label = pl.get("codeLinkLabel", "Code chapter (Municode) ↗")
    permit_link_label = pl.get("permitLinkLabel", "Permits &amp; entitlements (MAPPS) ↗")
    return """<script>
(function(){
 var BASE="https://geodata.hawaii.gov/arcgis/rest/services/ParcelsZoning/MapServer", SR=102202;
 var LUV="https://experience.arcgis.com/experience/d91bec49db3a4ef9b52f497a136562e6";
 var MAPPS=%(mapps)s;
 var MUNI=%(muni)s;
 var SLU={U:"Urban",A:"Agricultural",R:"Rural",C:"Conservation"};
 function J(u){return fetch(u).then(function(r){return r.json();});}
 function esc(s){return (s==null?"":String(s)).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/"/g,"&quot;");}
 function ptQ(id,x,y,out){var g=encodeURIComponent(JSON.stringify({x:x,y:y,spatialReference:{wkid:SR}}));
  return J(BASE+"/"+id+"/query?geometry="+g+"&geometryType=esriGeometryPoint&inSR="+SR+"&spatialRel=esriSpatialRelIntersects&outFields="+out+"&returnGeometry=false&f=json")
   .then(function(d){return (d&&d.features&&d.features[0])?d.features[0].attributes:null;}).catch(function(){return null;});}
 window.lookupTMK=function(){
  var raw=((document.getElementById("tmk").value)||"").replace(/\\D/g,"");
  var box=document.getElementById("pres"), btn=document.getElementById("plk");
  if(raw.length<7){box.innerHTML='<p class="note">Enter your full TMK digits (e.g. 211001001).</p>';return;}
  btn.disabled=true; box.innerHTML='<p class="note">Looking up parcel '+esc(raw)+' in the Hawaiʻi Statewide GIS…</p>';
  J(BASE+"/30/query?where="+encodeURIComponent("tmk_txt='"+raw+"'")+"&outFields=tmk_txt,qpub_link,taxacres&returnGeometry=true&f=json").then(function(d){
   var f=d&&d.features&&d.features[0];
   if(!f){box.innerHTML='<p class="note">No parcel matched <b>'+esc(raw)+'</b>. Check the digits, or find it on the <a href="'+LUV+'" target="_blank" rel="noopener">State Land Use Viewer ↗</a>.</p>';btn.disabled=false;return;}
   var a=f.attributes, ring=f.geometry.rings[0], sx=0, sy=0, i;
   for(i=0;i<ring.length;i++){sx+=ring[i][0];sy+=ring[i][1];}
   var x=sx/ring.length, y=sy/ring.length;
   Promise.all([ptQ(33,x,y,"zone_code,zone_dist,cp_area"),ptQ(10,x,y,"designations,cp_year"),ptQ(20,x,y,"ludcode"),ptQ(21,x,y,"smarea"),ptQ(4,x,y,"docket_no")]).then(function(r){
    var z=r[0]||{},c=r[1]||{},slu=r[2]||{},sma=r[3],ial=r[4], qp=a.qpub_link||"";
    box.innerHTML='<dl>'+
     '<dt>TMK</dt><dd>'+esc(a.tmk_txt)+'</dd>'+
     '<dt>County zoning</dt><dd>'+esc(z.zone_dist||"—")+(z.zone_code?' <span class="src" style="border:0">['+esc(z.zone_code)+']</span>':'')+'</dd>'+
     '<dt>Community plan</dt><dd>'+esc(c.designations||z.cp_area||"—")+(c.cp_year?' ('+esc(c.cp_year)+')':'')+'</dd>'+
     '<dt>State land use</dt><dd>'+esc(SLU[slu.ludcode]||slu.ludcode||"—")+'</dd>'+
     '<dt>SMA</dt><dd>'+(sma?'Within a Special Management Area — extra building review':'Not in mapped SMA')+'</dd>'+
     '<dt>Important Ag Land</dt><dd>'+(ial?('Yes — docket '+esc(ial.docket_no)):'Not mapped as IAL')+'</dd>'+
     '<dt>Parcel size</dt><dd>'+esc(a.taxacres!=null?(a.taxacres+" ac (tax)"):"—")+'</dd>'+
     '</dl><div class="out">'+
      (qp?'<a href="'+esc(qp)+'" target="_blank" rel="noopener">Real-property record (qPublic) ↗</a>':'')+
      '<a href="'+MAPPS+'" target="_blank" rel="noopener">%(permit_label)s</a>'+
      '<a href="'+MUNI+'" target="_blank" rel="noopener">%(code_link_label)s</a>'+
     '</div><p class="note">Designations are live from the Hawaiʻi Statewide GIS (Parcels &amp; Zoning). <b>Permits, entitlements, and inspection history are not in GIS</b> — use the MAPPS link for this parcel. Designations are at the parcel\\'s approximate center; confirm boundary-edge cases with the County.</p>';
    btn.disabled=false;
   });
  }).catch(function(){box.innerHTML='<p class="note">GIS lookup is unavailable right now. Open the <a href="'+LUV+'" target="_blank" rel="noopener">State Land Use Viewer ↗</a> or <a href="'+MAPPS+'" target="_blank" rel="noopener">MAPPS ↗</a>.</p>';btn.disabled=false;});
 };
 var t=document.getElementById("tmk"); if(t){t.addEventListener("keydown",function(e){if(e.key==="Enter")window.lookupTMK();});}
})();
</script>""" % {
        "mapps": json.dumps(mapps_permit), "muni": json.dumps(muni),
        "permit_label": permit_link_label, "code_link_label": code_link_label,
    }

# --------------------------------------------------------------------------
# PAGE ASSEMBLY
# --------------------------------------------------------------------------
def render(cfg):
    m = cfg["meta"]
    top = "".join(
        '<a href="%s"%s>%s</a>' % (esc(l["href"]),
            ' target="_blank" rel="noopener"' if l.get("ext") else "", esc(l["label"]))
        for l in cfg.get("topnav", []))
    free = ' <span class="free">%s</span>' % esc(m["freeBadge"]) if m.get("freeBadge") else ""
    body = []
    for b in cfg["sections"]:
        fn = SECTION_RENDERERS.get(b["type"])
        if not fn:
            raise SystemExit("Unknown section type: %s" % b["type"])
        body.append(fn(b))
    scripts = parcel_js(cfg) if cfg.get("parcelLookup") else ""
    tmpl = ('<!-- @template name="%(tname)s" description="%(desc)s" -->\n'
        '<!-- generated by tools/service_module_engine.py — edit %(id)s.config.json, not this file -->\n'
        '<!DOCTYPE html>\n<html lang="en"><head><meta charset="UTF-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
        '<title>%(title)s</title>\n'
        '<link rel="stylesheet" href="../../styles.css?v=%(ver)s">\n'
        '<style>\n%(css)s\n</style></head><body><div class="wrap">\n'
        ' <div class="top">%(top)s</div>\n'
        ' <div class="eyebrow">%(eyebrow)s</div>\n'
        ' <h1>%(h1)s%(free)s</h1>\n'
        ' <p class="lead">%(lead)s</p>\n\n'
        '%(body)s\n\n'
        ' <footer>%(footer)s</footer>\n'
        '</div>\n%(scripts)s\n</body></html>\n')
    return tmpl % {
        "tname": esc(m["templateName"]), "desc": esc(m.get("description", "")),
        "id": esc(m["id"]), "title": esc(m["pageTitle"]), "ver": esc(m.get("version", datetime.date.today().isoformat())),
        "css": THEME_CSS, "top": top, "eyebrow": esc(m["eyebrow"]),
        "h1": m["h1"], "free": free, "lead": cfg["hero"]["lead"],
        "body": "\n\n".join(body), "footer": cfg["footer"], "scripts": scripts,
    }

# --------------------------------------------------------------------------
# GUARDRAIL CHECK: no Stripe secret keys; every content (Layer A) section that
# asserts law carries a source; analysis blocks are labeled (by construction).
# --------------------------------------------------------------------------
SECRET_RE = re.compile(r"sk_(live|test)_[0-9A-Za-z]{6,}")
def guardrail_check(cfg, out_html):
    problems = []
    if SECRET_RE.search(out_html):
        problems.append("FAIL: a Stripe secret key is present — env refs only.")
    LAW_TYPES = {"process", "table"}
    for b in cfg["sections"]:
        if b.get("type") in LAW_TYPES and b.get("law", True) and not b.get("source"):
            problems.append("WARN: %s section '%s' asserts code content but has no source." %
                            (b["type"], b.get("title", "?")))
    return problems

def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    flags = [a for a in sys.argv[1:] if a.startswith("--")]
    if not args:
        raise SystemExit("usage: service_module_engine.py <config.json> [--out PATH] [--check]")
    cfg_path = args[0]
    cfg = json.load(open(cfg_path, encoding="utf-8"))
    out_html = render(cfg)
    problems = guardrail_check(cfg, out_html)
    for p in problems:
        print("  " + p)
    if any(p.startswith("FAIL") for p in problems):
        raise SystemExit("guardrail FAIL — not writing output.")
    if "--check" in flags:
        print("check OK: %s sections render; no FAIL." % len(cfg["sections"]))
        return
    out = None
    if "--out" in flags:
        out = args[1] if len(args) > 1 else None
        # allow --out=PATH
    for f in flags:
        if f.startswith("--out="):
            out = f.split("=", 1)[1]
    if not out:
        m = cfg["meta"]
        out = os.path.join(os.path.dirname(os.path.abspath(cfg_path)), m["outFile"])
    with open(out, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(out_html)
    print("wrote %s (%d bytes, %d sections)" % (out, len(out_html), len(cfg["sections"])))

if __name__ == "__main__":
    main()
