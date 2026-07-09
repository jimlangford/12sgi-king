#!/usr/bin/env python3
# vendor_donor_join.py - Kilo Aupuni: the CONTRACTS x DONORS join, public-records only.
#
# Sets two public datasets side by side, NO records request needed:
#   1. Maui County contract AWARDS (hands_maui_awards.json, from HANDS) - who the county pays.
#   2. Campaign CONTRIBUTIONS to tracked Maui officials (HI Campaign Spending Commission) - who funds them.
# It name-matches the two and surfaces entities that BOTH won county contracts AND gave to officials.
#
# INTEGRITY (non-negotiable): a name match is a QUESTION, not proof. Donating and
# contracting are both lawful. Names are matched mechanically and EVERY hit is labelled
# "name match - verify identity" - it is a lead for reporting, never an allegation of
# quid pro quo. Conservative matching (distinctive core tokens) to minimise false hits.
# Stdlib only, no popups.
import json, os, re, ssl, sys, time, urllib.request, urllib.parse
from datetime import datetime, timedelta, timezone

HOME     = os.path.expanduser("~")
PROJECT  = os.path.join(HOME, "Documents", "Claude", "Projects", "Video System elementLOTUS")
AWARDS_F = os.path.join(PROJECT, "reports", "mauios", "hands_maui_awards.json")
OUT_JSON = os.path.join(PROJECT, "reports", "mauios", "vendor_donor_join.json")
OUT_HTML = os.path.join(PROJECT, "reports", "mauios", "contracts_x_donors.html")
DISPATCH = os.path.join(PROJECT, ".dispatch_log.jsonl")
SODA     = "https://hicscdata.hawaii.gov/resource/jexd-xbcg.json"
HST      = timezone(timedelta(hours=-10))

# tracked officials -> CSC candidate_name LIKE pattern (kept in sync with donor_watch.py)
OFFICIALS = [
    ("Bissen",   "BISSEN",            "Richard Bissen - Mayor"),
    ("Sugimura", "SUGIMURA",          "Yuki Lei Sugimura - Council Vice-Chair, BFED Chair"),
    ("Lee",      "LEE, ALICE",        "Alice L. Lee - Council Chair"),
    ("Cook",     "COOK, THOMAS",      "Tom Cook - Councilmember, South Maui"),
    ("Johnson",  "JOHNSON, GABRIEL",  "Gabe Johnson - Councilmember"),
    ("Paltin",   "PALTIN",            "Tamara Paltin - Councilmember, West Maui"),
    ("Rawlins-Fernandez", "RAWLINS",  "Keani Rawlins-Fernandez - Councilmember, Molokai"),
    ("Sinenci",  "SINENCI",           "Shane Sinenci - Councilmember, East Maui"),
    ("Uu-Hodgins","HODGINS",          "Nohelani Uu-Hodgins - Councilmember"),
    ("Batangan", "BATANGAN",          "Kauanoe Batangan - Councilmember, Kahului"),
]

# words stripped before matching: corporate suffixes + generic industry/geo tokens
STOP = set("""INC INCORPORATED LLC LLP LP PC CO CORP CORPORATION COMPANY LTD LIMITED
ASSOCIATES ASSOC ASSOCIATION CONSULTANTS CONSULTANT CONSULTING ENGINEERING ENGINEERS
ENGINEER ARCHITECTS ARCHITECT ARCHITECTURE GROUP INTERNATIONAL INTL HAWAII HAWAIIAN
AND OF THE SUBS SUB DBA AIA PLLC SERVICES SERVICE SOLUTIONS PARTNERS PARTNERSHIP
SURVEYING DESIGN PLANNING CONSTRUCTION BUILDERS CONTRACTING CONTRACTORS ENTERPRISES
SYSTEMS TECHNOLOGIES TECHNOLOGY MANAGEMENT DEVELOPMENT PACIFIC ISLAND ISLANDS USA US
NETWORK ARCHITECTURAL GENERAL NATIONAL GLOBAL PROFESSIONAL ENVIRONMENTAL CIVIL STRUCTURAL
ELECTRIC ELECTRICAL MECHANICAL INDUSTRIES INDUSTRIAL HOLDINGS VENTURES PROPERTIES REALTY
REAL ESTATE LAND WATER ENERGY POWER UNION LOCAL PAC COMMITTEE FUND""".split())

def now_hst(): return datetime.now(HST)

def soda(params):
    url = SODA + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "12sgi-kilo-aupuni/1.0 (civic transparency)"})
    with urllib.request.urlopen(req, timeout=90, context=ssl.create_default_context()) as r:
        return json.loads(r.read().decode("utf-8", "replace"))

def dispatch(tag, msg):
    line = {"ts": int(time.time()), "iso": now_hst().strftime("%Y-%m-%d %H:%M:%S"),
            "source": "kilo-aupuni", "event": f"{tag}: {msg}"}
    try:
        with open(DISPATCH, "a", encoding="utf-8") as f:
            f.write(json.dumps(line, ensure_ascii=False) + "\n")
    except Exception:
        pass

def esc(s): return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
def usd(x):
    try: return f"{float(x):,.0f}"
    except Exception: return "0"
def fnum(x):
    try: return float(str(x).replace(",", "").strip() or 0)
    except Exception: return 0.0

def core_tokens(name):
    """Distinctive uppercase tokens of an entity name, suffixes/generics removed."""
    up = re.sub(r"[^A-Z0-9 ]", " ", str(name).upper())
    toks = [t for t in up.split() if t not in STOP and len(t) >= 3 and not t.isdigit()]
    return toks

def vendor_key(name):
    toks = core_tokens(name)
    # keep the most distinctive 1-2 tokens (longest), preserve order
    if not toks: return []
    ranked = sorted(toks, key=lambda t: -len(t))[:2]
    return [t for t in toks if t in ranked]

def fetch_contributors(pattern):
    """contributor_name -> {amount,n} for one official."""
    try:
        rows = soda({"$select": "contributor_name, sum(amount) as amt, count(*) as n",
                     "$where": f"upper(candidate_name) like '%{pattern}%'",
                     "$group": "contributor_name", "$order": "amt DESC", "$limit": "50000"})
    except Exception as e:
        dispatch("FINDING", f"vendor-donor: contributor pull failed for {pattern}: {e}")
        return {}
    out = {}
    for r in rows:
        nm = (r.get("contributor_name") or "").strip()
        if nm:
            out[nm] = {"amount": fnum(r.get("amt")), "n": int(fnum(r.get("n")))}
    return out

def match(vendor_toks, contributor_norm_set):
    """True if every distinctive vendor token appears as a whole word in the contributor name."""
    if not vendor_toks: return False
    return all(t in contributor_norm_set for t in vendor_toks)

def main():
    if not os.path.exists(AWARDS_F):
        dispatch("FINDING", "vendor-donor: hands_maui_awards.json missing - run hands_awards.py first")
        return 1
    awards = json.load(open(AWARDS_F, encoding="utf-8"))
    vendors = awards.get("vendors", [])

    # build contributor index per official (contributor_name -> {amount,n}); also a global map
    by_official = {}
    contrib_index = {}   # normalized-token-set keyed by contributor display name
    for key, pat, label in OFFICIALS:
        time.sleep(0.4)
        cs = fetch_contributors(pat)
        by_official[key] = {"label": label, "contribs": cs}
        for nm in cs:
            if nm not in contrib_index:
                contrib_index[nm] = set(core_tokens(nm))

    matches = []
    for v in vendors:
        vk = vendor_key(v["vendor"])
        if not vk:
            continue
        hits = []
        for key, od in by_official.items():
            for nm, info in od["contribs"].items():
                if match(vk, contrib_index.get(nm, set())):
                    up = nm.upper()
                    is_firm = any(s in up.split() or s in re.sub(r"[^A-Z ]"," ",up).split()
                                  for s in ("INC", "LLC", "LTD", "CORP", "CO", "LLP", "GROUP",
                                            "ASSOCIATES", "TRUST", "COMPANY", "PARTNERS"))
                    hits.append({"official": key, "official_label": od["label"],
                                 "contributor": nm, "amount": info["amount"], "n": info["n"],
                                 "basis": "firm" if is_firm else "individual"})
        if hits:
            gave = sum(h["amount"] for h in hits)
            offs = sorted({h["official"] for h in hits})
            matches.append({"vendor": v["vendor"], "award_total": v["total"],
                            "award_count": v["count"], "contrib_total": round(gave, 2),
                            "officials": offs, "hits": sorted(hits, key=lambda h: -h["amount"])})
    matches.sort(key=lambda m: -m["award_total"])

    out = {"generated": now_hst().isoformat(),
           "method": "mechanical name match on distinctive entity tokens; every hit is a QUESTION to verify, not proof",
           "maui_vendors_scanned": len(vendors), "matches": len(matches),
           "matched": matches}
    # ATOMIC WRITE (Jimmy 2026-07-02 heal-forward): reports/mauios/contracts_x_donors.html deployed
    # STALE twice in one session -- a manual run's fully-rendered output (incl. the svg_network chart)
    # got clobbered by a concurrent process writing the same path before the seed-sync copy happened.
    # Writing to a temp file then os.replace() makes every write instantaneous+atomic from any reader's
    # view (never a half-written or "whoever-finished-last-wins mid-render" state); doesn't eliminate a
    # genuinely concurrent SECOND full run racing this one, but removes the torn-write failure mode.
    tmp_json = OUT_JSON + ".tmp"
    json.dump(out, open(tmp_json, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    os.replace(tmp_json, OUT_JSON)
    tmp_html = OUT_HTML + ".tmp"
    with open(tmp_html, "w", encoding="utf-8") as f:
        f.write(build_page(matches, len(vendors)))
    os.replace(tmp_html, OUT_HTML)
    dispatch("SHIPPED", f"vendor-donor join: {len(matches)} of {len(vendors)} Maui vendors name-match a "
             f"campaign donor to a tracked official (public records, framed as questions) "
             f"-> reports/mauios/contracts_x_donors.html")
    return 0

def svg_network(matches, max_vendors=12):
    """HIDDEN-DATA REDESIGN (Jimmy 2026-07-01): a bipartite vendor<->official diagram, inline SVG, no
    CDN/JS dependency. The richest 'money network' data in the system had zero graph visualization --
    it was a flat card list. Vendors on the left, officials on the right, line weight = $ given."""
    top = matches[:max_vendors]
    if not top:
        return ""
    officials = []
    for m in top:
        for o in m["officials"]:
            if o not in officials:
                officials.append(o)
    v_n, o_n = len(top), len(officials)
    row_h, width, left_x, right_x = 34, 640, 170, 470
    height = max(v_n, o_n) * row_h + 20
    max_award = max((m["award_total"] or 0) for m in top) or 1
    lines = []
    v_y = {m["vendor"]: 10 + i * row_h + row_h / 2 for i, m in enumerate(top)}
    o_y = {o: 10 + i * row_h + row_h / 2 for i, o in enumerate(officials)}
    for m in top:
        for o in m["officials"]:
            oy = o_y.get(o)
            vy = v_y[m["vendor"]]
            if oy is None:
                continue
            w = 1 + min(6, (m["contrib_total"] or 0) / 2000)
            lines.append(f'<line x1="{left_x}" y1="{vy}" x2="{right_x}" y2="{oy}" stroke="#e06a4a" stroke-width="{w:.1f}" opacity="0.55"/>')
    for m in top:
        y = v_y[m["vendor"]]
        r = 4 + min(10, (m["award_total"] or 0) / max_award * 10)
        lines.append(f'<circle cx="{left_x}" cy="{y}" r="{r:.1f}" fill="#d9b24c"/>')
        lines.append(f'<text x="{left_x-10}" y="{y+4}" font-size="11" fill="#bdb8a4" text-anchor="end" font-family="Consolas,monospace">{esc(m["vendor"])[:28]}</text>')
    for o in officials:
        y = o_y[o]
        lines.append(f'<circle cx="{right_x}" cy="{y}" r="6" fill="#1259a3"/>')
        lines.append(f'<text x="{right_x+12}" y="{y+4}" font-size="11" fill="#bdb8a4" font-family="Consolas,monospace">{esc(o)[:30]}</text>')
    return (f'<svg viewBox="0 0 {width} {height}" width="100%" height="{height}" style="margin:12px 0" '
            f'role="img" aria-label="vendor to official money network">{"".join(lines)}</svg>'
            f'<div style="font-size:11px;color:#9a957f;font-family:Consolas,monospace">'
            f'<span style="color:#d9b24c">&#9679;</span> vendor (size = award $) &nbsp; '
            f'<span style="color:#1259a3">&#9679;</span> official &nbsp; '
            f'<span style="color:#e06a4a">&mdash;</span> line weight = $ contributed</div>')


def build_page(matches, nv):
    g = now_hst().strftime("%Y-%m-%d %H:%M HST")
    network = svg_network(matches)
    rows = ""
    for m in matches:
        who = ", ".join(m["officials"])
        hitlines = "".join(
            f'<div class="hit">${usd(h["amount"])} &middot; {esc(h["contributor"])} '
            f'<span class="b">[{h.get("basis","?")}]</span> &rarr; {esc(h["official"])} ({h["n"]}x)</div>'
            for h in m["hits"][:6])
        rows += (f'<div class="m"><div class="top"><span class="a">${usd(m["award_total"])}</span>'
                 f'<span class="c"><b>{esc(m["vendor"])}</b> &mdash; {m["award_count"]} county award(s) '
                 f'&middot; also gave ${usd(m["contrib_total"])} to {esc(who)}</span></div>'
                 f'<div class="q">Name match &mdash; verify identity. Public question: does this vendor\'s '
                 f'county work track its giving? Both are lawful; the match is a lead, not a finding.</div>'
                 f'{hitlines}</div>')
    body = rows or '<div class="m"><span class="c">No vendor names matched a tracked official\'s donors under the conservative rule.</span></div>'
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Contracts x Donors - Maui - 12 Stones</title>
<style>
 body{{margin:0;background:#0c100e;color:#e8e4d8;font-family:Georgia,'Iowan Old Style',serif;line-height:1.55}}
 .wrap{{max-width:920px;margin:0 auto;padding:34px 24px 60px}}
 .eyebrow{{font-family:Consolas,monospace;font-size:11px;letter-spacing:1.2px;color:#d9b24c;text-transform:uppercase}}
 h1{{font-size:26px;font-weight:600;margin:8px 0 2px}}
 .lead{{font-size:13.5px;color:#bdb8a4;max-width:82ch}}
 .disc{{font-size:12px;color:#e8d9a8;font-style:italic;border-left:2px solid rgba(224,106,74,.5);padding:8px 12px;margin:14px 0;background:rgba(224,106,74,.06)}}
 .m{{border:1px solid rgba(255,255,255,.1);border-radius:11px;padding:12px 15px;margin:11px 0;background:rgba(255,255,255,.02)}}
 .m .top{{display:flex;gap:13px;align-items:baseline}}
 .m .a{{font-family:Consolas,monospace;font-size:14px;color:#d9b24c;white-space:nowrap}}
 .m .c{{font-size:13.5px;color:#e8e4d8}}
 .q{{font-size:12px;color:#e8d9a8;margin:7px 0 6px}}
 .hit{{font-family:Consolas,monospace;font-size:11.5px;color:#9a957f;padding:2px 0}}
 footer{{margin-top:34px;border-top:1px solid rgba(255,255,255,.1);padding-top:12px;font-family:Consolas,monospace;font-size:10.5px;color:#9a957f}}
</style></head><body><div class="wrap">
<div class="eyebrow">12 Stones Global &middot; Kilo Aupuni &middot; contracts &times; donors &middot; follow the money</div>
<h1>Contracts &times; Donors &mdash; the public join</h1>
<p class="lead">Maui County contract awardees (HANDS public record) name-matched against campaign
contributors to tracked Maui officials (Campaign Spending Commission public record). Where a county
vendor also funds an official, it is set here as a <b>question for reporting</b> &mdash; built entirely
from public records, no information request required.</p>
<div class="disc"><b>Read this first.</b> A name match is mechanical and is a QUESTION, never proof.
Winning county contracts and donating to campaigns are both lawful and ordinary. Verify each identity
before relying on it. Correlations are questions, never accusations &mdash; the 12 Stones integrity rule.</div>
<p class="lead" style="font-family:Consolas,monospace;font-size:12px;color:#9a957f">{len(matches)} of {nv} Maui vendors name-match a donor to a tracked official.</p>
{network}
{body}
<footer>generated {g} &middot; vendor-donor-join v1 &middot; sources: HANDS award notices + HI Campaign Spending Commission &middot; public records &middot; questions, not accusations &middot; govOS</footer>
</div></body></html>"""

if __name__ == "__main__":
    sys.exit(main())
