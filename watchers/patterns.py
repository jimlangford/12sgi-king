#!/usr/bin/env python3
# patterns.py - Kilo Aupuni: the two cross-jurisdiction PATTERN joins.
#   (A) Legislators: real-estate/developer money received  vs  dissents on housing/STR/RE/
#       water/budget bills (lege_legiscan votes x CSC money) - who votes the development
#       line, and who is funded by it. Correlation = a QUESTION, never proof.
#   (B) Cross-jurisdiction donors: contributors funding the most distinct office-types
#       (Gov + State House/Senate + multiple county Councils + Mayors) - the influence web.
# All public record. Stdlib only. No popups.
import json, os, re, ssl, time, urllib.request, urllib.parse
from datetime import datetime, timedelta, timezone

HOME    = os.path.expanduser("~")
PROJECT = os.path.join(HOME, "Documents", "Claude", "Projects", "Video System elementLOTUS")
MAUIOS  = os.path.join(PROJECT, "reports", "mauios")
LEG_F   = os.path.join(MAUIOS, "lege", "legislators.json")
OFFICIALS_F = os.path.join(MAUIOS, "officials.json")        # county council votes/recusals (votes-watch)
DONORS_F    = os.path.join(MAUIOS, "donor_profiles.json")   # county campaign money (donor-watch)
OUT_F   = os.path.join(MAUIOS, "patterns_money_x_votes.html")
DISPATCH= os.path.join(PROJECT, ".dispatch_log.jsonl")
SODA    = "https://hicscdata.hawaii.gov/resource/jexd-xbcg.json"
HST     = timezone(timedelta(hours=-10))
RE_WHERE= ("upper(occupation) like '%REAL ESTATE%' or upper(occupation) like '%REALTOR%' or "
           "upper(occupation) like '%DEVELOP%' or upper(occupation) like '%BROKER%' or "
           "upper(employer) like '%REALTY%' or upper(employer) like '%DEVELOPMENT%' or "
           "upper(employer) like '%PROPERTIES%' or upper(contributor_name) like '%REALTOR%' or "
           "upper(contributor_name) like '%DEVELOP%'")

def now_hst(): return datetime.now(HST)
def esc(s): return str(s).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
def usd(x):
    try: return f"${float(x):,.0f}"
    except Exception: return "$0"
def dispatch(tag,msg):
    try:
        with open(DISPATCH,"a",encoding="utf-8") as f:
            f.write(json.dumps({"ts":int(time.time()),"iso":now_hst().strftime("%Y-%m-%d %H:%M:%S"),
                                "source":"kilo-aupuni","event":f"{tag}: {msg}"},ensure_ascii=False)+"\n")
    except Exception: pass
def soda(params):
    url=SODA+"?"+urllib.parse.urlencode(params)
    req=urllib.request.Request(url, headers={"User-Agent":"12sgi-kilo-aupuni/1.0 (civic transparency)"})
    with urllib.request.urlopen(req,timeout=120,context=ssl.create_default_context()) as r:
        return json.loads(r.read().decode("utf-8","replace"))
def fnum(x):
    try: return float(x or 0)
    except Exception: return 0.0

def nkey(name):
    name=(name or "").strip()
    if "," in name: last, first = name.split(",",1)
    else:
        p=name.split(); first=p[0] if p else ""; last=p[-1] if p else ""
    last=re.sub(r"[^a-z]","",last.lower()); fi=(first.strip()[:1].lower())
    return last+"|"+fi

def re_money_by_candidate():
    rows=soda({"$select":"candidate_name, sum(amount) as re_total","$where":RE_WHERE,
               "$group":"candidate_name","$order":"re_total DESC","$limit":"5000"})
    m={}
    for r in rows:
        k=nkey(r.get("candidate_name")); m[k]=m.get(k,0.0)+fnum(r.get("re_total"))
    return m, {nkey(r.get("candidate_name")): r.get("candidate_name") for r in rows}

def cross_jurisdiction_donors():
    rows=soda({"$select":"contributor_name, count(distinct office) as offices, count(distinct candidate_name) as cands, sum(amount) as total",
               "$group":"contributor_name","$having":"count(distinct office) >= 4","$order":"total DESC","$limit":"40"})
    return [{"name":r.get("contributor_name"),"offices":int(float(r.get("offices",0))),
             "cands":int(float(r.get("cands",0))),"total":fnum(r.get("total"))} for r in rows if r.get("contributor_name")]

def svg_bar_chart(rows, label_fn, value_fn, color="#d9b24c", max_items=10, unit_fn=None):
    """HIDDEN-DATA REDESIGN (Jimmy 2026-07-01): inline SVG, no CDN/JS dependency (leak-gate/offline-safe
    on the public govOS site) -- the underlying money figures already existed as flat table rows; this
    renders the same public-safe numbers as an actual bar chart above the table, not instead of it."""
    top = rows[:max_items]
    if not top:
        return ""
    maxv = max((value_fn(r) or 0) for r in top) or 1
    bar_h, gap, label_w, chart_w = 18, 8, 190, 420
    lines = []
    for i, r in enumerate(top):
        v = value_fn(r) or 0
        w = round((v / maxv) * chart_w)
        y = i * (bar_h + gap)
        lbl = esc(label_fn(r))[:26]
        val_txt = esc(unit_fn(v)) if unit_fn else esc(str(v))
        lines.append(
            f'<text x="0" y="{y+bar_h-5}" font-size="11" fill="#bdb8a4" font-family="Consolas,monospace">{lbl}</text>'
            f'<rect x="{label_w}" y="{y}" width="{w}" height="{bar_h}" rx="3" fill="{color}"/>'
            f'<text x="{label_w+w+6}" y="{y+bar_h-5}" font-size="11" fill="{color}" font-family="Consolas,monospace">{val_txt}</text>'
        )
    total_h = len(top) * (bar_h + gap)
    return (f'<svg viewBox="0 0 {label_w+chart_w+90} {total_h}" width="100%" height="{total_h}" '
            f'style="margin:10px 0" role="img" aria-label="bar chart">{"".join(lines)}</svg>')


def county_money_votes():
    """Maui County: join each official's campaign money (donor-watch) to their
    council votes/recusals (votes-watch). Money + recusals are QUESTIONS, never proof."""
    try: off = json.load(open(OFFICIALS_F, encoding="utf-8"))
    except Exception: off = {}
    try: dp = json.load(open(DONORS_F, encoding="utf-8"))
    except Exception: dp = []
    rows = []
    for p in (dp if isinstance(dp, list) else []):
        key = p.get("key", "")
        re = (p.get("realestate") or {}).get("total", 0.0)
        re_ct = (p.get("realestate") or {}).get("count", 0)
        o = off.get(key, {})
        rows.append({"name": p.get("label") or key, "re": re, "re_ct": re_ct,
                     "raised": p.get("total", 0.0), "recused": o.get("recused", 0),
                     "ayes": o.get("ayes", 0), "noes": o.get("noes", 0),
                     "meetings": o.get("meetings", 0), "is_council": bool(o)})
    rows.sort(key=lambda r: -r["re"])
    return rows


def main():
    os.makedirs(MAUIOS, exist_ok=True)
    leg = json.load(open(LEG_F, encoding="utf-8")).get("legislators", {})
    re_money, re_disp = re_money_by_candidate()
    crossd = cross_jurisdiction_donors()
    # (A) join legislators -> RE money + lens-dissents
    rowsA=[]
    for name, o in leg.items():
        diss=len(o.get("dissents",[]));
        rm=re_money.get(nkey(name), 0.0)
        if diss==0 and rm==0: continue
        rowsA.append({"name":name,"party":o.get("party"),"role":o.get("role"),
                      "dissents":diss,"nay":o.get("nay",0),"re":rm,
                      "matched":re_disp.get(nkey(name),"")})
    rowsA.sort(key=lambda r: (-(r["re"]), -r["dissents"]))
    def rowA(r):
        return (f'<div class="m"><span class="a">{usd(r["re"])}</span>'
                f'<span class="d">{r["dissents"]}</span>'
                f'<span class="c">{esc(r["name"])} <span class="role">({esc(r["party"] or "?")})</span>'
                f'{(" — CSC: " + esc(r["matched"])) if r["matched"] else " — no RE money matched"}</span></div>')
    a_html="".join(rowA(r) for r in rowsA[:40])
    cross_html="".join(
        f'<div class="m"><span class="a">{usd(d["total"])}</span><span class="d">{d["offices"]}</span>'
        f'<span class="c">{esc(d["name"])} &mdash; funds {d["cands"]} candidates across <b>{d["offices"]} office-types</b></span></div>'
        for d in crossd)
    county = county_money_votes()
    def rowCo(r):
        vote = (f'{r["ayes"]} aye / {r["noes"]} no over {r["meetings"]} mtgs' if r["is_council"]
                else 'Mayor &mdash; executive (no council vote)')
        donors = (f' &middot; {r["re_ct"]} RE/dev donors' if r["re_ct"] else '')
        return (f'<div class="m"><span class="a">{usd(r["re"])}</span>'
                f'<span class="d">{r["recused"]}</span>'
                f'<span class="c">{esc(r["name"])} &mdash; {vote}{donors}</span></div>')
    county_html="".join(rowCo(r) for r in county)
    county_chart = svg_bar_chart(sorted(county, key=lambda r: -r["re"]), lambda r: r["name"], lambda r: r["re"], "#d9b24c", unit_fn=usd)
    legis_chart = svg_bar_chart(rowsA, lambda r: r["name"], lambda r: r["re"], "#e06a4a", unit_fn=usd)
    cross_chart = svg_bar_chart(crossd, lambda r: r["name"], lambda r: r["total"], "#6a9ad9", unit_fn=usd)
    g=now_hst().strftime("%Y-%m-%d %H:%M HST")
    html=f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Patterns: Money x Votes - 12 Stones</title>
<style>
 body{{margin:0;background:#0c100e;color:#e8e4d8;font-family:Georgia,serif;line-height:1.5}}
 .wrap{{max-width:960px;margin:0 auto;padding:32px 22px 60px}}
 .eyebrow{{font-family:Consolas,monospace;font-size:11px;letter-spacing:1.2px;color:#d9b24c;text-transform:uppercase}}
 h1{{font-size:25px;margin:8px 0 2px}} h2{{font-size:18px;margin:22px 0 2px}}
 .disc{{font-size:12px;color:#9a957f;font-style:italic;border-left:2px solid rgba(224,106,74,.5);padding:7px 12px;margin:12px 0;background:rgba(224,106,74,.05)}}
 .hd{{display:grid;grid-template-columns:120px 60px 1fr;gap:12px;font-family:Consolas,monospace;font-size:10.5px;color:#9a957f;text-transform:uppercase;border-bottom:1px solid rgba(217,178,76,.25);padding-bottom:5px;margin-top:8px}}
 .m{{display:grid;grid-template-columns:120px 60px 1fr;gap:12px;align-items:baseline;border-bottom:1px solid rgba(255,255,255,.06);padding:5px 0}}
 .m .a{{font-family:Consolas,monospace;font-size:12.5px;color:#d9b24c;text-align:right}}
 .m .d{{font-family:Consolas,monospace;font-size:12.5px;color:#e06a4a;text-align:center}}
 .m .c{{font-size:12.5px;color:#bdb8a4}} .m .c b{{color:#e8e4d8}} .role{{color:#9a957f;font-family:Consolas,monospace;font-size:10.5px}}
 footer{{margin-top:36px;border-top:1px solid rgba(255,255,255,.1);padding-top:12px;font-family:Consolas,monospace;font-size:10.5px;color:#9a957f}}
</style></head><body><div class="wrap">
<div class="eyebrow">12 Stones Global · Kilo Aupuni · patterns · money x votes</div>
<h1>The Patterns — Money × Votes (joined)</h1>
<div class="disc">Three public-record joins across <b>Maui County and the State of Hawai&#699;i</b>. Correlation is a
<b>question for investigation</b>, not proof of a quid pro quo. Campaign money received next to recusals
(county) or dissents (state) on housing/STR/RE/water/budget matters shows where to look; it does not
establish why anyone voted as they did. Verify before asserting anything about anyone.</div>
<h2>A. Maui County — campaign money received vs. recusals &amp; council votes</h2>
{county_chart}
<div class="hd"><span style="text-align:right">RE/dev $ (2008+)</span><span style="text-align:center">recusals</span><span>county official (votes from the minutes)</span></div>
{county_html or '<div class="m"><span class="c">no data yet</span></div>'}
<h2>B. Hawai&#699;i Legislature — real-estate/developer money received vs. lens-bill dissents</h2>
{legis_chart}
<div class="hd"><span style="text-align:right">RE $ (2008+)</span><span style="text-align:center">dissents</span><span>legislator (2010-2026 votes)</span></div>
{a_html or '<div class="m"><span class="c">no matches</span></div>'}
<h2>C. Cross-jurisdiction donors — funding the most distinct office-types</h2>
{cross_chart}
<div class="hd"><span style="text-align:right">total</span><span style="text-align:center">offices</span><span>donor (the influence web)</span></div>
{cross_html or '<div class="m"><span class="c">none</span></div>'}
<footer>generated {g} · patterns v2 · sources: CivicClerk council minutes (county votes/recusals) + LegiScan (state votes 2010+) + HI Campaign Spending Commission (money 2008+) · public record · govOS</footer>
</div></body></html>"""
    # ATOMIC WRITE (Jimmy 2026-07-02 heal-forward): same torn-write class as contracts_x_donors.html --
    # tmp+os.replace so a reader (incl. the seed-sync copy step) never sees a partial/mid-render file.
    _tmp = OUT_F + ".tmp"
    with open(_tmp,"w",encoding="utf-8") as f: f.write(html)
    os.replace(_tmp, OUT_F)
    matched=sum(1 for r in rowsA if r["re"]>0)
    dispatch("SHIPPED", f"patterns money x votes v2: {len(county)} Maui County officials + {len(rowsA)} legislators "
             f"({matched} w/ RE money matched) + {len(crossd)} cross-jurisdiction donors -> reports/mauios/patterns_money_x_votes.html")
    return 0

if __name__ == "__main__":
    import sys; sys.exit(main())
