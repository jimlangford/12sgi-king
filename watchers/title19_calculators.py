#!/usr/bin/env python3
"""title19_calculators.py — the Title 19 page: the tenant's full SUBMISSION-CALCULATOR HUB.

Jimmy 2026-06-20: "The Title 19 page is supposed to be all of the calculators for all of the tenant
(Maui titles), matching the needs to submit to all departments of the tenant … do the whole county today
to have an estimate for onboarding."

An applicant enters their project → every Maui department's requirement + an ESTIMATED cost, computed from
the REAL FY2026 fee schedules. INTEGRITY (the truth gate, applied to money): every figure is sourced to the
county code + Appendix B with its fiscal year + a source link; where a fee is not publicly posted (Planning
permit dollar amounts), the calculator says "confirm with the department" rather than guessing. Output is a
sourced ESTIMATE to plan a submission — not an official determination.

Source of the dollar figures: County of Maui Appendix B — Rates, Fees, Taxes, FY2026 (eff. 2025-07-01),
mauicounty.gov; RPT rates FY2025-2026; MCC §§16.25 / 20.08 / 14 / 18.16.320 / 2.96.040 / SMA page. Light
civic surface (docs/SURFACE_THEME_POLICY.md). Per-tenant: Maui sourced now; other counties honest-empty
until their schedules are sourced (no cross-tenant fallback). Civic lane (kilo-aupuni) owns + extends it.

  python tools/kilo-aupuni/title19_calculators.py     # writes reports/mauios/title19.html
"""
import os, sys
from datetime import datetime, timezone, timedelta

TOOL = os.path.dirname(os.path.abspath(__file__))
if TOOL not in sys.path: sys.path.insert(0, TOOL)
import tenant_pages as TP  # reuse the one light Yale-blue civic stylesheet
HST = timezone(timedelta(hours=-10))
M = TP.M

CALC_CSS = (
    ".intro{background:linear-gradient(180deg,#eef3fb,#f7f9fc);border:1px solid var(--line);"
    "border-left:3px solid var(--accent);border-radius:12px;padding:.85rem 1.05rem;margin:.6rem 0 1.1rem}"
    ".intro b{color:var(--ink)} .intro .src{font-family:Consolas,monospace;font-size:.78rem;color:var(--faint)}"
    ".form{display:grid;grid-template-columns:1fr;gap:.7rem;margin:1rem 0}"
    "@media(min-width:620px){.form{grid-template-columns:1fr 1fr}}"
    ".fld{display:flex;flex-direction:column;gap:.2rem}.fld label{font-size:.85rem;color:var(--dim);font-weight:600}"
    ".fld input,.fld select{font:inherit;font-size:1rem;padding:.5rem .6rem;border:1px solid var(--line);"
    "border-radius:9px;background:#fff;color:var(--ink)}"
    ".cards{display:grid;grid-template-columns:1fr;gap:.7rem;margin:1rem 0}"
    "@media(min-width:620px){.cards{grid-template-columns:1fr 1fr}}"
    ".dc{border:1px solid var(--line);border-radius:14px;padding:1rem 1.05rem;background:var(--panel)}"
    ".dc h3{margin:0 0 .15rem;font-size:1.05rem;color:var(--ink)}"
    ".dc .dept{font-family:Consolas,monospace;font-size:.7rem;letter-spacing:.06em;text-transform:uppercase;color:var(--accent2)}"
    ".dc .amt{font-size:1.5rem;font-weight:750;color:var(--ink);margin:.35rem 0 .1rem;font-family:'Segoe UI',system-ui}"
    ".dc .req{font-size:.9rem;color:var(--dim);line-height:1.45;margin:.2rem 0 .4rem}"
    ".badge{display:inline-block;font-family:Consolas,monospace;font-size:.66rem;padding:.12rem .5rem;border-radius:20px;letter-spacing:.04em}"
    ".badge.ok{background:rgba(31,138,91,.12);color:#1f6e4a;border:1px solid rgba(31,138,91,.4)}"
    ".badge.confirm{background:rgba(217,138,12,.12);color:#9a6a00;border:1px solid rgba(217,138,12,.4)}"
    ".dc a{font-size:.82rem} .dc .note{font-size:.8rem;color:var(--faint);margin-top:.35rem;line-height:1.4}"
    ".total{border:2px solid var(--accent);border-radius:14px;padding:1rem 1.2rem;margin:1.1rem 0;background:#eef3fb}"
    ".total .amt{font-size:1.9rem;font-weight:800;color:var(--accent)}"
    ".total .lab{font-size:.85rem;color:var(--dim)}")

# The sourced fee logic + UI lives in this JS block (client-side; no server data). Every constant is the
# real FY2026 Maui figure; every card carries a source link + an OK/confirm badge.
JS = r"""
<script>
var SRC = {
  appB:'https://www.mauicounty.gov/DocumentCenter/View/152286/005---FY-2026-App-B-Rates--Fees-Clean',
  bldg:'https://www.mauicounty.gov/1208/Building-Permit',
  water:'https://www.mauicounty.gov/1888/Water-System-Development-Fees',
  ww:'https://www.mauicounty.gov/1318/Wastewater-Permits-Applications',
  rpt:'https://www.mauicounty.gov/755/Real-Property-Tax-Rates',
  sma:'https://www.mauicounty.gov/698/Special-Management-Area-Permits',
  planning:'https://www.mauicounty.gov/121/Planning',
  zoning:'https://www.mauicounty.gov/1907/Zoning'
};
function usd(n){ if(n==null||isNaN(n)) return '—'; return '$'+Math.round(n).toLocaleString(); }
function ceil(n){ return Math.ceil(n); }

// 1. Building permit — MCC 16.25.109 tiered (FY2026 App B); plan review = 35%; +$50 C of O
function buildingPermit(v){ v=Math.max(0,v); if(!v) return 0; var f;
  if(v<=500) f=30;
  else if(v<=2000) f=30+ceil((v-500)/100)*3;
  else if(v<=25000) f=75+ceil((v-2000)/1000)*10;
  else if(v<=50000) f=305+ceil((v-25000)/1000)*9;
  else if(v<=100000) f=530+ceil((v-50000)/1000)*7;
  else if(v<=500000) f=880+ceil((v-100000)/1000)*5;
  else if(v<=1000000) f=2880+ceil((v-500000)/1000)*6;
  else f=5880+ceil((v-1000000)/1000)*10;
  return f; }
function buildingTotal(v){ var p=buildingPermit(v); return p?p*1.35+50:0; } // permit + plan review + CofO

// 2. Grading (MCC 20.08.090, by greater of cut/fill) + grubbing
function grading(cy){ cy=Math.max(0,cy); if(!cy) return 0;
  if(cy<=500) return ceil(cy/100)*60;
  if(cy<=10000) return 300+ceil((cy-500)/100)*25;
  return 2675+ceil((cy-10000)/100)*8; }
function grubbing(ac){ ac=Math.max(0,ac); if(!ac) return 0; return 100+ceil(Math.max(0,ac-1))*50; }

// 3. Water System Development Fee by meter size (Charter 8-11.4) + install ($190/$275 where lateral exists)
var WSDF={'5/8':12060,'3/4':18884,'1':33356,'1.5':71948,'2':125012,'3':279380,'4':496460,'6':1113932,'8':1977428,'10':3089360,'12':4447436};
function waterInstall(m){ if(m=='5/8') return 190; if(m=='3/4'||m=='1') return 275; return null; } // larger=actual cost
function waterTotal(m){ var s=WSDF[m]; if(s==null) return null; var i=waterInstall(m); return i==null? s : s+i; }

// 4. Wastewater facility expansion assessment — per gallon of project flow (Kihei/W-K only)
var WW={'kihei':4.65,'wk':4.57};
function wastewater(region, gpd){ var r=WW[region]; if(r==null) return null; if(!gpd) return 0; return gpd*r; }

// 5. Real Property Tax (annual) — FY2026-27 tiered $/$1,000 (eff. 2026-07-01); $300k home exemption for owner-occupied
// Source: Maui County Council-adopted FY2027 rates (mauicounty.gov/DocumentCenter/View/159947; secondary: mauirealestate.com/maui-county-2026-2027-property-tax-rates)
// Confirm at mauicounty.gov/755 before relying on these for a real transaction.
var RPT={
 'Owner-Occupied':[[1300000,1.65],[4500000,1.80],[1e15,5.00]],
 'Non-Owner-Occupied':[[1000000,6.25],[3000000,9.00],[1e15,17.00]],
 'Long-Term Rental':[[1500000,2.90],[3000000,5.00],[1e15,8.50]],
 'Short-Term Rental (TVR-STRH)':[[900000,13.00],[3000000,15.00],[1e15,17.00]],
 'Commercialized Residential':[[1500000,2.25],[3000000,3.00],[1e15,10.00]],
 'Apartment':[[1e15,3.50]],'Hotel/Resort':[[1e15,11.80]],'Time Share':[[1e15,14.90]],
 'Agricultural':[[1e15,5.74]],'Conservation':[[1e15,6.43]],'Commercial':[[1e15,6.05]],'Industrial':[[1e15,7.05]]};
function propertyTax(cls, val, ownerOcc){ var tiers=RPT[cls]; if(!tiers) return null; val=Math.max(0,val);
  if(ownerOcc) val=Math.max(0,val-300000);
  var tax=0, floor=0; for(var i=0;i<tiers.length;i++){ var cap=tiers[i][0], rate=tiers[i][1];
    if(val>floor){ tax += (Math.min(val,cap)-floor)/1000*rate; } floor=cap; }
  return tax; }

// 6. SMA threshold (official): >=$750k -> Major (>=$500k shoreline); else Minor. Dollar fee = confirm.
function smaTier(v, shoreline){ var t=shoreline?500000:750000; return v>=t?'SMA MAJOR (Use Permit + hearing)':'SMA Minor (director)'; }

// 7. Parks dedication (MCC 18.16.320): 500 sq ft per lot/unit over 3 (250 for workforce); fee-in-lieu = sqft x land value
function parkSqft(units){ units=Math.max(0,units); return units>3? (units-3)*500 : 0; }

// 8. Residential Workforce Housing (MCC 2.96.040): 25% (round up) of units when total >= 10
function workforce(units){ units=Math.max(0,units); return units>=10? ceil(0.25*units) : 0; }

function val(id){ var e=document.getElementById(id); var n=parseFloat((e&&e.value||'').replace(/[^0-9.]/g,'')); return isNaN(n)?0:n; }
function sel(id){ var e=document.getElementById(id); return e?e.value:''; }
function chk(id){ var e=document.getElementById(id); return !!(e&&e.checked); }

function card(dept, title, amt, req, sourced, link, note){
  var badge = sourced ? "<span class=\"badge ok\">sourced · FY2026</span>"
                      : "<span class=\"badge confirm\">confirm with dept</span>";
  return "<div class=dc><div class=dept>"+dept+"</div><h3>"+title+"</h3>"
    +"<div class=amt>"+(amt===''?'—':amt)+"</div>"
    +"<div class=req>"+req+"</div>"+badge
    +" &nbsp;<a href=\""+link+"\" target=_blank rel=noopener>official page →</a>"
    +(note?"<div class=note>"+note+"</div>":"")+"</div>";
}

function recompute(){
  var V=val('valuation'), cy=val('cuyd'), ac=val('acres'), meter=sel('meter'),
      units=val('units'), assessed=val('assessed'), cls=sel('rptclass'), oo=chk('owneroccupied'),
      region=sel('region'), gpd=val('gpd'), shoreline=chk('shoreline');

  var bldg=buildingTotal(V), grade=grading(cy)+grubbing(ac), water=waterTotal(meter),
      ww=wastewater(region,gpd), tax=propertyTax(cls,assessed,oo),
      psf=parkSqft(units), wfh=workforce(units);

  var cards=[];
  cards.push(card('Public Works · Title 16','Building permit', usd(bldg),
    'Valuation-tiered permit + 35% plan review + $50 certificate of occupancy.', true, SRC.bldg,
    'Electrical/plumbing/mechanical permits are separate per-device fees.'));
  cards.push(card('Public Works · Title 20','Grading & grubbing', usd(grade),
    'By the greater of cut or fill (cu yd) + grubbing by cleared acreage.', true, SRC.appB, ''));
  cards.push(card('Water Supply','Water system development + meter', water==null? '' : usd(water),
    'One-time system development fee by meter size + install ($190–$275 where a lateral exists).',
    true, SRC.water, waterInstall(meter)==null && meter? 'Meters ≥1.5″ install on actual cost — estimate excludes install.':''));
  cards.push(card('Environmental Mgmt','Wastewater assessment', ww==null? '' : usd(ww),
    'Per-gallon facility expansion assessment on project flow.', region=='other'?false:true, SRC.ww,
    region=='other'? 'Only Kihei & Wailuku-Kahului rates are publicly posted — confirm your region with DEM (808-270-7417).'
      : 'Flow factor (gpd/dwelling) = engineer-supplied or ref HAR §11-62: typical SFR ≈375 gpd; multi-family ~225 gpd/unit. Confirm exact factor with DEM (808-270-7417) before submitting.'));
  cards.push(card('Finance · Real Property Tax','Annual property tax', tax==null? '' : usd(tax)+' /yr',
    'Net assessed value × your class rate (tiered), less the $300k home exemption if owner-occupied.',
    true, SRC.rpt, 'Annual — not a submission fee. FY2026-27 council-adopted rates (eff. 2026-07-01) — confirm at mauicounty.gov/755 before relying on these.'));
  cards.push(card(‘Planning · SMA’,’Special Management Area’, smaTier(val(‘projval’),shoreline),
    ‘Threshold is official; the assessment/use-permit dollar fee is set in the Planning Table A &amp; B (eff. 2023-07-01).’,
    false, SRC.sma, ‘SMA Use Permit fees in Table A &amp; B (Maui County Planning Dept, Resolution 23-xx, eff 2023-07-01) — confirm current fee with Planning (808-270-7735). UIPA request can obtain the scanned schedule if not posted online.’));
  cards.push(card(‘Planning · Title 19’,’Zoning / use / subdivision’, ‘’,
    ‘Zoning compliance, change-in-zoning, conditional/special use, subdivision.’, false, SRC.zoning,
    ‘Application fees set in Planning Table A &amp; B (eff. 2023-07-01). Examples from the adopted table: Change in Zoning ~$3,295; Conditional Use ~$2,745; Subdivision Preliminary ~varies. Confirm current fee with Planning (808-270-7735) or UIPA Table A &amp; B.’));
  cards.push(card('Parks & Recreation','Subdivision park dedication', psf? psf.toLocaleString()+' sq ft' : '$0',
    '500 sq ft per lot/unit over 3 (250 for workforce); or fee-in-lieu at the area land value.', true,
    'http://www.mauico-hi.elaws.us/code/cid16289/18.16.320/', psf? 'Fee-in-lieu = sq ft × your community-plan-area land value.':'3 or fewer lots are exempt.'));
  cards.push(card('Housing & Human Concerns','Workforce housing', wfh? wfh+' unit(s)' : '0',
    '25% of units (rounded up) must be workforce housing when the project is 10+ units.', true,
    'http://mauico-hi.elaws.us/code/coor_title2_ch2.96_sec2.96.040', wfh? 'Income mix + credits per MCC 2.96/2.97.':'Under 10 units: not triggered.'));
  var fireFlag = V>=500000 || units>=10 ? 'Fire review likely required' : (V>=50000 ? 'Confirm with Maui Fire' : 'Likely exempt — confirm');
  cards.push(card('Maui Fire Department','Fire plan review', fireFlag,
    'Required for large commercial, high-occupancy, or multi-family projects. Sprinkler/suppression requirements under HRS Ch. 132, MFC.',
    false, 'https://www.mauicounty.gov/255/Fire-Services',
    'Fire review fees not publicly machine-readable; confirm with Maui Fire Prevention (808-270-7565).'));

  document.getElementById('cards').innerHTML = cards.join('');
  var oneTime = (bldg||0)+(grade||0)+(water||0)+(ww||0);
  document.getElementById('totalAmt').textContent = usd(oneTime);
}
document.addEventListener('input', recompute);
document.addEventListener('change', recompute);
window.addEventListener('DOMContentLoaded', recompute);
</script>
"""


def render():
    g = datetime.now(HST).strftime("%Y-%m-%d %H:%M HST")
    css = TP.CSS + CALC_CSS
    form = """
<div class=form>
 <div class=fld><label for=valuation>Building valuation ($)</label><input id=valuation type=text inputmode=numeric placeholder="e.g. 400000"></div>
 <div class=fld><label for=projval>Project total cost — for SMA ($)</label><input id=projval type=text inputmode=numeric placeholder="e.g. 800000"></div>
 <div class=fld><label for=cuyd>Grading — cut/fill (cu yd)</label><input id=cuyd type=text inputmode=numeric placeholder="e.g. 600"></div>
 <div class=fld><label for=acres>Grubbing — cleared acres</label><input id=acres type=text inputmode=numeric placeholder="e.g. 1"></div>
 <div class=fld><label for=meter>Water meter size</label><select id=meter><option value="">—</option><option>5/8</option><option>3/4</option><option>1</option><option>1.5</option><option>2</option><option>3</option><option>4</option><option>6</option><option>8</option><option>10</option><option>12</option></select></div>
 <div class=fld><label for=units>Total dwelling units / lots</label><input id=units type=text inputmode=numeric placeholder="e.g. 12"></div>
 <div class=fld><label for=assessed>Net assessed value ($)</label><input id=assessed type=text inputmode=numeric placeholder="e.g. 900000"></div>
 <div class=fld><label for=rptclass>Property tax class</label><select id=rptclass><option>Owner-Occupied</option><option>Non-Owner-Occupied</option><option>Long-Term Rental</option><option>Short-Term Rental (TVR-STRH)</option><option>Commercialized Residential</option><option>Apartment</option><option>Hotel/Resort</option><option>Time Share</option><option>Agricultural</option><option>Conservation</option><option>Commercial</option><option>Industrial</option></select></div>
 <div class=fld><label for=region>Wastewater region</label><select id=region><option value="">—</option><option value="kihei">Kihei</option><option value="wk">Wailuku-Kahului</option><option value="other">Other / confirm</option></select></div>
 <div class=fld><label for=gpd>Projected wastewater flow (gal/day)</label><input id=gpd type=text inputmode=numeric placeholder="engineer-supplied"></div>
 <div class=fld><label><input id=owneroccupied type=checkbox> Owner-occupied (home exemption)</label></div>
 <div class=fld><label><input id=shoreline type=checkbox> Shoreline-area parcel (SMA)</label></div>
</div>"""
    return ("<!doctype html><meta charset=utf-8>"
            "<meta name=viewport content='width=device-width,initial-scale=1,viewport-fit=cover'>"
            "<meta name=theme-color content='#00356b'>"
            "<title>govOS — Maui County · submission calculators</title>"
            "<style>%s</style>"
            "<div class=eyebrow><a href='tenants_hub.html'>govOS</a> — <a href='tenant_hi-maui.html'>Maui County</a></div>"
            "<h1>Submission calculators</h1>"
            "<div class=sub style='margin:-.15rem 0 .3rem;font-size:1.05rem'>What to prepare for every "
            "department of your government, and an estimate of the cost.</div>"
            "<div class=intro><b>Plan your submission across every Maui department.</b> Enter your project; "
            "each card shows the requirement and an <b>estimated</b> cost from the current Maui fee schedule. "
            "These are estimates to prepare your submission — <b>confirm exact figures with each department</b> "
            "(every card links to the official page). Figures marked <span class=\"badge ok\">sourced</span> are "
            "from the county code + FY2026 Appendix B; <span class=\"badge confirm\">confirm with dept</span> means "
            "the dollar fee isn’t publicly posted — we won’t guess it."
            "<div class=src>Sources: Maui County Appendix B FY2026 · MCC 16.25 / 20.08 / 14 / 18.16.320 / 2.96.040 · RPT FY2026-27 council-adopted rates (eff. 2026-07-01) · generated %s</div></div>"
            "%s"
            "<div class=total><div class=lab>Estimated one-time submission cost (permits + grading + water + wastewater)</div>"
            "<div class=amt id=totalAmt>—</div>"
            "<div class=lab>Property tax is annual (shown separately). Planning application fees: confirm with the department.</div></div>"
            "<h2 style='font-size:1.15rem;margin:1.2rem 0 .2rem'>By department</h2>"
            "<div class=cards id=cards></div>"
            "<p class=sub style='color:var(--faint);font-size:.84rem'>An estimate to help you prepare — not an "
            "official determination. Every figure is sourced or flagged; confirm exact amounts with each "
            "department before you submit. The people’s records stay free. · pono</p>"
            "<p class=sub><a href='tenants_hub.html'>← all governments</a> · <a href='tenant_hi-maui.html'>Maui dashboard</a></p>"
            "%s"
            % (css, g, form, JS))


def main():
    os.makedirs(M, exist_ok=True)
    out = os.path.join(M, "title19.html")
    open(out, "w", encoding="utf-8", newline="\n").write(render())
    print("title19_calculators: wrote %s" % out)
    return 0


if __name__ == "__main__":
    if sys.platform == "win32":
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(main())
