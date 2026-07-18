#!/usr/bin/env python3
"""chain_link.py -- Kilo Aupuni money-chain join for Maui County.

Reads the sourced datasets the other Kilo Aupuni tools already produced and joins them
into ONE up-and-down-the-chain view:

    FUNDER (federal / state / county)  ->  PRIME (nonprofit or vendor)  ->  SUBCONTRACTOR

...and cross-links any entity that appears in more than one layer -- e.g. a 990 nonprofit
that is ALSO a federal subrecipient, or a county-contract vendor that is ALSO a campaign
donor to an official (via the existing vendor<->donor join).

Civic discipline (non-negotiable, same as county_awards.py / federal_money.py):
  * SOURCED-ONLY. Every edge carries its public source link + a source_type badge.
  * Overlaps are framed as QUESTIONS to verify -- a name match is NOT proof of identity,
    and receiving public money and donating are both lawful. Never an accusation.
  * PROVENANCE. Each edge/role carries source_type = "sourced" (official document / API
    filing) or "transcribed" (derived from a meeting transcript). Default = "sourced";
    the value is inherited from each underlying record where it records its own.
  * Never invent a link the data does not support -- edges come only from real records,
    cross-links only from a normalized-name match, and the match is flagged for verify.

Inputs (all already in reports/mauios/, all sourced):
  nonprofits_maui.json     -- ProPublica 990 nonprofits (Maui)
  subcontracts_maui.json   -- USASpending federal subawards (prime -> sub)
  hands_maui_awards.json   -- HANDS county contract awards (Maui County -> vendor)
  federal_money_maui.json  -- USASpending federal awards (agency -> recipient)
  vendor_donor_join.json   -- Kilo Aupuni vendor<->donor name-match (vendor -> official)

Output: reports/mauios/money_chain_maui.html + money_chain_maui.json
Stdlib only (no pip). Windowless-safe (every print guarded by `if sys.stdout`). UTF-8.
"""
import os, sys, json, re, argparse
from datetime import datetime, timezone, timedelta

if sys.platform == "win32":
    try:
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    except Exception:
        pass

HOME = os.path.expanduser("~")
PROJECT = os.path.join(HOME, "Documents", "Claude", "Projects", "Video System elementLOTUS")
MAUIOS = os.path.join(PROJECT, "reports", "mauios")
HST = timezone(timedelta(hours=-10))

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    import civic_shell            # shared Yale-blue chrome (header/footer/tokens)
except Exception:
    civic_shell = None

USASPEND_AWARD = "https://www.usaspending.gov/award/"
HANDS_URL = "https://hands.ehawaii.gov/hands/awards"
PROPUBLICA = "https://projects.propublica.org/nonprofits/"
CSC_JOIN_PAGE = "contracts_x_donors.html"   # local sourced vendor<->donor report


# ---------------------------------------------------------------- helpers
def out(*a):
    if sys.stdout:
        try:
            print(*a)
        except Exception:
            pass

def now_hst():
    return datetime.now(HST)

def esc(s):
    return str(s if s is not None else "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def usd(n):
    try:
        return "{:,.0f}".format(float(n or 0))
    except Exception:
        return "0"

def load(fn):
    p = os.path.join(MAUIOS, fn)
    if not os.path.exists(p):
        out("  note: missing input", fn, "(skipped -- honest partial)")
        return None
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        out("  warn: could not read", fn, e)
        return None

# entity name -> normalized match key (drops corporate suffixes + punctuation, lowercases)
_SUFFIX = re.compile(
    r"\b(incorporated|inc|llc|ltd|limited|corporation|corp|company|co|lp|llp|pllc|pc|the)\b", re.I)
def normkey(name):
    s = (name or "").lower().replace("&", " and ")
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    s = _SUFFIX.sub(" ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

# layer category each role belongs to (for counting cross-LAYER overlaps, not just cross-role)
LAYER_OF = {"federal": "federal", "federal_prime": "federal", "subcontractor": "subaward",
            "county_vendor": "county", "nonprofit": "nonprofit", "donor": "donor"}
LAYER_LABEL = {"federal": "federal recipient", "subaward": "federal subrecipient",
               "county": "county-contract vendor", "nonprofit": "990 nonprofit",
               "donor": "campaign donor"}


# ---------------------------------------------------------------- graph model
class Graph:
    def __init__(self):
        self.ent = {}       # normkey -> entity dict (roles across layers)
        self.nodes = {}     # node id -> node dict
        self.edges = []     # edge dicts

    def entity(self, name):
        k = normkey(name)
        if not k:
            return None
        e = self.ent.get(k)
        if not e:
            e = {"key": k, "name": name, "roles": {}}
            self.ent[k] = e
        if len(name or "") > len(e["name"] or ""):
            e["name"] = name
        return e

    def add_role(self, ent, role, amount=0.0, source="", source_url="", source_type="sourced", **extra):
        r = ent["roles"].setdefault(role, {"amount": 0.0, "count": 0, "source": source,
                                           "source_url": source_url, "source_type": source_type})
        r["amount"] += float(amount or 0)
        r["count"] += 1
        r.update({k: v for k, v in extra.items() if v is not None})
        if source_url:
            r["source_url"] = source_url
        return r

    def node(self, nid, label, ntype, **extra):
        n = self.nodes.get(nid)
        if not n:
            n = {"id": nid, "label": label, "type": ntype}
            n.update(extra)
            self.nodes[nid] = n
        return n

    def edge(self, src, dst, kind, amount=0.0, label="", source="", source_url="",
             source_type="sourced", verify=False):
        self.edges.append({"src": src, "dst": dst, "kind": kind, "amount": float(amount or 0),
                           "label": label, "source": source, "source_url": source_url,
                           "source_type": source_type, "verify": bool(verify)})


def entity_nid(ent):
    return "e:" + ent["key"]


# ---------------------------------------------------------------- build
def build():
    g = Graph()
    stats = {"inputs": {}}

    # --- A. federal awards: agency -> recipient (Maui place-of-performance subset) -----
    fed = load("federal_money_maui.json")
    if fed:
        stats["inputs"]["federal_money_maui.json"] = len(fed.get("awards", []))
        for a in fed.get("awards", []):
            if not a.get("maui"):
                continue
            ent = g.entity(a.get("recipient"))
            if not ent:
                continue
            gid = a.get("gid") or a.get("id")
            surl = (USASPEND_AWARD + gid) if gid else "https://www.usaspending.gov/"
            g.add_role(ent, "federal", a.get("amount", 0), fed.get("source", ""), surl, "sourced")
            en = g.node(entity_nid(ent), ent["name"], "entity")
            agency = (a.get("agency") or "Federal agency").strip() or "Federal agency"
            fn = g.node("F:" + normkey(agency), agency, "funder", scope="federal")
            g.edge(fn["id"], en["id"], "federal_award", a.get("amount", 0),
                   label=(a.get("type") or ""), source="USASpending.gov (place of performance = Maui)",
                   source_url=surl, source_type="sourced")

    # --- B. federal subawards: agency -> prime -> subcontractor -----------------------
    sub = load("subcontracts_maui.json")
    if sub:
        stats["inputs"]["subcontracts_maui.json"] = len(sub.get("records", []))
        for r in sub.get("records", []):
            pri = g.entity(r.get("prime_name"))
            s = g.entity(r.get("sub_name"))
            if not (pri and s):
                continue
            st = r.get("source_type") or "sourced"
            pgid = r.get("prime_gid")
            purl = (USASPEND_AWARD + pgid) if pgid else (r.get("source_url") or "https://www.usaspending.gov/")
            g.add_role(pri, "federal_prime", 0, sub.get("source", ""), purl, st)
            g.add_role(s, "subcontractor", r.get("sub_amount", 0), sub.get("source", ""),
                       r.get("source_url", ""), st)
            pn = g.node(entity_nid(pri), pri["name"], "entity")
            sn = g.node(entity_nid(s), s["name"], "entity")
            agency = (r.get("agency") or "Federal agency").strip() or "Federal agency"
            fn = g.node("F:" + normkey(agency), agency, "funder", scope="federal")
            # funder -> prime (federal pass-through), sourced to the prime award
            g.edge(fn["id"], pn["id"], "federal_prime", 0, label=(r.get("group") or ""),
                   source="USASpending.gov prime award", source_url=purl, source_type=st)
            # prime -> subcontractor
            g.edge(pn["id"], sn["id"], "subcontract", r.get("sub_amount", 0),
                   label=(r.get("group") or ""), source="USASpending.gov subaward (SAM.gov/FSRS)",
                   source_url=r.get("source_url", ""), source_type=st)

    # --- C. county contracts: Maui County -> vendor ----------------------------------
    hands = load("hands_maui_awards.json")
    if hands:
        stats["inputs"]["hands_maui_awards.json"] = len(hands.get("vendors", []))
        county = g.node("county:maui", "Maui County", "funder", scope="county")
        for v in hands.get("vendors", []):
            ent = g.entity(v.get("vendor"))
            if not ent:
                continue
            aws = v.get("awards") or []
            dept = (aws[0].get("dept") if aws else "") or ""
            g.add_role(ent, "county_vendor", v.get("total", 0), hands.get("source", "HANDS"),
                       HANDS_URL, "sourced", county_count=v.get("count", 0), dept=dept)
            en = g.node(entity_nid(ent), ent["name"], "entity")
            g.edge(county["id"], en["id"], "county_award", v.get("total", 0), label=dept,
                   source="HANDS award notices (hands.ehawaii.gov)", source_url=HANDS_URL,
                   source_type="sourced")

    # --- D. 990 nonprofits: role attribute (enables the nonprofit cross-link) ---------
    npf = load("nonprofits_maui.json")
    if npf:
        stats["inputs"]["nonprofits_maui.json"] = len(npf.get("records", []))
        for n in npf.get("records", []):
            ent = g.entity(n.get("name"))
            if not ent:
                continue
            g.add_role(ent, "nonprofit", n.get("revenue", 0) or 0,
                       npf.get("source", "IRS Form 990 (ProPublica)"),
                       n.get("source_url") or PROPUBLICA, n.get("source_type") or "sourced",
                       category=n.get("category"), fiscal_year=n.get("fiscal_year"),
                       ein=n.get("strein"))

    # --- E. vendor<->donor: vendor -> official (campaign contribution) ----------------
    vdj = load("vendor_donor_join.json")
    if vdj:
        stats["inputs"]["vendor_donor_join.json"] = len(vdj.get("matched", []))
        for m in vdj.get("matched", []):
            ent = g.entity(m.get("vendor"))
            if not ent:
                continue
            g.add_role(ent, "donor", m.get("contrib_total", 0), "Hawaiʻi Campaign Spending Commission",
                       CSC_JOIN_PAGE, "sourced", officials=m.get("officials"))
            en = g.node(entity_nid(ent), ent["name"], "entity")
            for h in (m.get("hits") or []):
                lbl = h.get("official_label") or h.get("official") or "official"
                onid = "official:" + normkey(h.get("official") or lbl)
                on = g.node(onid, lbl, "official")
                g.edge(en["id"], on["id"], "campaign_contribution", h.get("amount", 0),
                       label=(h.get("contributor") or ""),
                       source="Hawaiʻi Campaign Spending Commission (via vendor<->donor name-match)",
                       source_url=CSC_JOIN_PAGE, source_type="sourced", verify=True)

    return g, stats


# ---------------------------------------------------------------- cross-links
def cross_links(g):
    """Entities whose roles span two or more LAYERS -> the questions to verify."""
    xs = []
    for e in g.ent.values():
        layers = {}
        for role, rd in e["roles"].items():
            lay = LAYER_OF.get(role, role)
            L = layers.setdefault(lay, {"amount": 0.0, "count": 0, "source_url": rd.get("source_url", ""),
                                        "source_type": rd.get("source_type", "sourced"),
                                        "extra": {k: v for k, v in rd.items()
                                                  if k not in ("amount", "count", "source", "source_url", "source_type")}})
            L["amount"] += rd.get("amount", 0)
            L["count"] += rd.get("count", 0)
        if len(layers) >= 2:
            xs.append({"name": e["name"], "key": e["key"], "layers": layers})
    # biggest-money overlaps first
    xs.sort(key=lambda x: -sum(l["amount"] for l in x["layers"].values()))
    return xs


def question_for(x):
    """A plain-language QUESTION (never a finding) for one cross-layer overlap."""
    labs = [LAYER_LABEL.get(k, k) for k in x["layers"].keys()]
    if len(labs) == 2:
        pair = "%s and a %s" % (labs[0], labs[1])
    else:
        pair = ", ".join(labs[:-1]) + ", and a " + labs[-1]
    return ("Is the entity recorded as a %s the same organization here? A name match across "
            "public records is a lead to verify -- not proof of identity, and each activity is "
            "lawful on its own. Confirm identity before drawing any conclusion." % pair)


# ---------------------------------------------------------------- chains
def build_chains(g):
    """Assemble FUNDER -> PRIME -> SUB chains from the subaward edges, annotating any
    other layer the prime or sub also appears in (the cross-link enrichment)."""
    # index funder->prime edges by prime node
    prime_funders = {}
    for ed in g.edges:
        if ed["kind"] == "federal_prime":
            prime_funders.setdefault(ed["dst"], []).append(ed)
    chains = []
    for ed in g.edges:
        if ed["kind"] != "subcontract":
            continue
        pn = g.nodes.get(ed["src"])
        sn = g.nodes.get(ed["dst"])
        if not (pn and sn):
            continue
        ff = prime_funders.get(ed["src"], [])
        funder_label = g.nodes[ff[0]["src"]]["label"] if ff else "Federal agency"
        # roles the sub ALSO carries (beyond subcontractor) -> the cross-link tags
        sub_ent = g.ent.get(sn["id"][2:]) if sn["id"].startswith("e:") else None
        sub_layers = []
        if sub_ent:
            seen = set()
            for role in sub_ent["roles"]:
                lay = LAYER_OF.get(role, role)
                if lay != "subaward" and lay not in seen:
                    seen.add(lay)
                    sub_layers.append(LAYER_LABEL.get(lay, lay))
        chains.append({
            "funder": funder_label, "prime": pn["label"], "sub": sn["label"],
            "amount": ed["amount"], "source_url": ed["source_url"], "source_type": ed["source_type"],
            "sub_also": sub_layers,
        })
    # prefer chains whose sub crosses into another layer, then by dollars
    chains.sort(key=lambda c: (-(1 if c["sub_also"] else 0), -c["amount"]))
    return chains


# ---------------------------------------------------------------- render
def badge(st):
    if st == "transcribed":
        return ('<span class="pv pv-t" title="Derived from an audio/video meeting transcript">'
                '&#9998; transcribed</span>')
    return ('<span class="pv pv-s" title="From an official document or API filing">'
            '&#10003; sourced</span>')

CSS = """
.wrapx{max-width:1000px;margin:0 auto;padding:6px 16px 40px;color:var(--cs-ink,#13243d);
 font-family:'Segoe UI Variable Text','Segoe UI',system-ui,sans-serif;line-height:1.55}
.eyebrow{letter-spacing:.1em;text-transform:uppercase;color:#6cb0f0;font-weight:600;font-size:.8rem}
h1{font-size:1.55rem;margin:.3rem 0}
h2{color:#7fb2ff;font-size:1.08rem;margin:1.6rem 0 .5rem;border-bottom:1px solid #26456a;padding-bottom:.3rem}
.sub{color:#9fb2c8;font-size:.95rem}
.kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin:1rem 0}
@media(max-width:640px){.kpis{grid-template-columns:1fr 1fr}}
.kp{background:#0f2540;border:1px solid #26456a;border-radius:11px;padding:.7rem .85rem}
.kv{font:700 18px/1.1 'JetBrains Mono',Consolas,monospace;color:#7fb2ff}
.kl{font-size:11px;color:#8ea3ba;text-transform:uppercase;letter-spacing:.4px;margin-top:4px}
.note{background:#241d0e;border:1px solid #5c4a1e;border-left:3px solid #b8860b;border-radius:10px;
 padding:.7rem 1rem;margin:.9rem 0;font-size:.9rem;color:#e3c98a;line-height:1.5}
.pv{font:600 10.5px/1 'JetBrains Mono',Consolas,monospace;padding:2px 7px;border-radius:99px;white-space:nowrap;margin-left:6px;vertical-align:middle}
.pv-s{background:#0f2540;color:#4ec98a;border:1px solid #b9dcc7}
.pv-t{background:#241d0e;color:#e3c98a;border:1px solid #5c4a1e}
.legend{font-size:.82rem;color:#9fb2c8;margin:.4rem 0 0}
.card{border:1px solid #26456a;border-radius:12px;padding:.85rem 1rem;margin:.7rem 0;background:#0f2540}
.card .nm{font-weight:700;color:#eaf2fc;font-size:1.02rem}
.chips{margin:.5rem 0 .35rem;display:flex;flex-wrap:wrap;gap:7px}
.chip{font-size:.82rem;background:#0f2540;border:1px solid #26456a;border-radius:9px;padding:.28rem .55rem;color:#eaf2fc}
.chip a{color:#6cb0f0;text-decoration:none}.chip a:hover{text-decoration:underline}
.chip .m{font-family:Consolas,monospace;color:#7fb2ff;font-weight:700}
.q{font-size:.86rem;color:#e3c98a;font-style:italic}
.chain{display:grid;grid-template-columns:1fr;gap:2px;border-bottom:1px solid #1f3d5f;padding:.6rem .1rem}
.chain .flow{font-size:.92rem}
.chain .a{color:#7fb2ff;font-weight:600}
.chain .arrow{color:#9fb4cf;font-family:Consolas,monospace;margin:0 6px}
.chain .m{font-family:Consolas,monospace;color:#7fb2ff}
.chain .tags{font-size:.78rem;color:#e3c98a;margin-top:2px}
.lnk{background:#0f2540;border:1px solid #26456a;border-radius:10px;padding:.6rem .9rem;margin:1rem 0;font-size:.92rem;line-height:1.9}
a{color:#6cb0f0}
"""

def render_html(g, xs, chains, stats, kind_sums):
    gts = now_hst().strftime("%Y-%m-%d %H:%M HST")
    n_ent = sum(1 for n in g.nodes.values() if n["type"] == "entity")
    n_fund = sum(1 for n in g.nodes.values() if n["type"] == "funder")
    n_off = sum(1 for n in g.nodes.values() if n["type"] == "official")

    # cross-link cards
    cards = []
    for x in xs[:60]:
        chips = []
        for lay, L in sorted(x["layers"].items(), key=lambda kv: -kv[1]["amount"]):
            lab = LAYER_LABEL.get(lay, lay)
            amt = "$%s" % usd(L["amount"]) if L["amount"] else ("%d record(s)" % L["count"])
            url = L.get("source_url") or ""
            inner = '<a href="%s">%s</a>' % (esc(url), esc(lab)) if url else esc(lab)
            chips.append('<span class="chip">%s &middot; <span class="m">%s</span> %s</span>'
                         % (inner, esc(amt), badge(L.get("source_type", "sourced"))))
        cards.append('<div class="card"><div class="nm">%s</div><div class="chips">%s</div>'
                     '<div class="q">%s</div></div>' % (esc(x["name"]), "".join(chips), esc(question_for(x))))
    cards_html = "".join(cards) or '<p class="sub">No cross-layer overlaps found in the current data.</p>'

    # chains
    crows = []
    for c in chains[:80]:
        tags = ""
        if c["sub_also"]:
            tags = '<div class="tags">the subrecipient here also appears as: %s &mdash; a question to verify</div>' % esc(", ".join(c["sub_also"]))
        crows.append(
            '<div class="chain"><div class="flow">'
            '<span class="a">%s</span><span class="arrow">&rarr;</span>'
            '<span class="a">%s</span><span class="arrow">&rarr;</span>'
            '<span class="a">%s</span> &nbsp;<span class="m">$%s</span> '
            '<a href="%s">source</a> %s</div>%s</div>'
            % (esc(c["funder"]), esc(c["prime"]), esc(c["sub"]), usd(c["amount"]),
               esc(c["source_url"] or "https://www.usaspending.gov/"),
               badge(c["source_type"]), tags))
    chains_html = "".join(crows) or '<p class="sub">No funder&rarr;prime&rarr;sub chains in the current data.</p>'

    # cross-links to sibling reports that exist
    sib = [("maui_contract_awards.html", "county contracts"),
           ("federal_money.html", "federal dollars"),
           ("subcontractors_maui.html", "subcontractors"),
           ("nonprofits_maui.html", "nonprofits (990)"),
           ("contracts_x_donors.html", "contracts &times; donors"),
           ("jurisdictions.html", "all jurisdictions")]
    linkrow = " &middot; ".join('<a href="%s">%s</a>' % (fn, lbl) for fn, lbl in sib
                                if os.path.exists(os.path.join(MAUIOS, fn)))

    body = """<div class="wrapx">
<div class="eyebrow">12 Stones Global &middot; Kilo Aupuni &middot; Maui County &middot; asked in aloha</div>
<h1>The money chain &mdash; funder &rarr; prime &rarr; subcontractor</h1>
<p class="sub">One joined view of Maui&rsquo;s public money, up and down the chain: who funds
(federal / state / county), who they pay (the prime &mdash; a nonprofit or a vendor), and who the
prime pays underneath (the subcontractor). Where one name turns up in more than one layer &mdash; a
990 nonprofit that is also a federal subrecipient, a county vendor that is also a campaign donor &mdash;
we surface it as a <b>question to verify</b>, never a finding. Every edge links to its public source
and carries a provenance badge. Generated %s.</p>

<div class="kpis">
 <div class="kp"><div class="kv">%d</div><div class="kl">entities in the chain</div></div>
 <div class="kp"><div class="kv">%d</div><div class="kl">money edges</div></div>
 <div class="kp"><div class="kv">%d</div><div class="kl">cross-layer overlaps</div></div>
 <div class="kp"><div class="kv">$%s</div><div class="kl">federal subawards traced</div></div>
</div>
<div class="kpis">
 <div class="kp"><div class="kv">$%s</div><div class="kl">county contracts (HANDS)</div></div>
 <div class="kp"><div class="kv">$%s</div><div class="kl">federal awards (Maui)</div></div>
 <div class="kp"><div class="kv">$%s</div><div class="kl">campaign contributions</div></div>
 <div class="kp"><div class="kv">%d</div><div class="kl">funders + %d officials</div></div>
</div>

<div class="note">Receiving public money is lawful and ordinary; so is donating to a campaign.
This page does not allege wrongdoing. It maps how the dollars connect so anyone can ask the
oversight questions &mdash; and every overlap below is a <b>name match to verify</b>, not proof that
two records are the same entity.</div>
<div class="legend">Provenance: %s = from an official document or API filing &nbsp; %s = derived from a
meeting transcript. Default is sourced.</div>

<h2>Where one name appears in more than one layer</h2>
<p class="sub">These entities show up across layers of the money chain. Each is a lead for oversight
&mdash; confirm identity against the linked source before concluding anything.</p>
%s

<h2>The chain, end to end &mdash; funder &rarr; prime &rarr; subcontractor</h2>
<p class="sub">Federal money flowing agency &rarr; prime &rarr; subrecipient, with Maui place of
performance. Where the subrecipient also appears elsewhere in the chain, it is tagged as a question.</p>
%s

<div class="lnk"><b>Follow it further:</b> %s</div>
<p class="sub" style="margin-top:1rem">Full node/edge data in <code>money_chain_maui.json</code>.
This is a records-awareness tool; lawful action (records requests, reporting, voting) is the endpoint.
Sources: USASpending.gov, HANDS (hands.ehawaii.gov), IRS Form 990 via ProPublica, Hawai&#699;i
Campaign Spending Commission.</p>
</div>""" % (
        esc(gts), n_ent, len(g.edges), len(xs), usd(kind_sums.get("subcontract", 0)),
        usd(kind_sums.get("county_award", 0)), usd(kind_sums.get("federal_award", 0)),
        usd(kind_sums.get("campaign_contribution", 0)), n_fund, n_off,
        badge("sourced"), badge("transcribed"),
        cards_html, chains_html, linkrow)

    html = ("<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
            "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1,viewport-fit=cover\">"
            "<meta name=\"theme-color\" content=\"#00356b\">"
            "<title>The money chain &mdash; Maui County | govOS</title>"
            "<style>body{margin:0;background:#081420}%s</style></head><body>%s</body></html>" % (CSS, body))
    if civic_shell:
        try:
            html = civic_shell.wrap_html(html)
        except Exception as e:
            out("  note: civic_shell wrap skipped:", e)
    return html


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description="Kilo Aupuni money-chain join (defaults to Maui County).")
    ap.add_argument("--county", default="maui", help="target county (only 'maui' wired; kept for parity)")
    args = ap.parse_args()
    if args.county.lower() != "maui":
        out("note: only Maui is wired in this build; proceeding with Maui.")

    os.makedirs(MAUIOS, exist_ok=True)
    g, stats = build()
    xs = cross_links(g)
    chains = build_chains(g)

    kind_sums = {}
    for e in g.edges:
        kind_sums[e["kind"]] = kind_sums.get(e["kind"], 0.0) + e["amount"]

    n_ent = sum(1 for n in g.nodes.values() if n["type"] == "entity")

    # ---- JSON dataset (so future joins can consume it) ----
    payload = {
        "generated": now_hst().strftime("%Y-%m-%d %H:%M:%S HST"),
        "target": {"county": "Maui County", "fips": "15009", "tenant": "hi-maui"},
        "source": "Join of Kilo Aupuni sourced datasets (USASpending, HANDS, IRS 990/ProPublica, HI CSC)",
        "inputs": stats["inputs"],
        "source_type_default": "sourced",
        "provenance_note": ("Every edge carries source_type ('sourced' = official document / API "
                            "filing; 'transcribed' = from a meeting transcript). Overlaps are name "
                            "matches framed as questions to verify, never findings or accusations."),
        "counts": {
            "nodes": len(g.nodes), "entities": n_ent, "edges": len(g.edges),
            "funders": sum(1 for n in g.nodes.values() if n["type"] == "funder"),
            "officials": sum(1 for n in g.nodes.values() if n["type"] == "official"),
            "cross_layer_overlaps": len(xs),
            "edge_kinds": {k: sum(1 for e in g.edges if e["kind"] == k)
                           for k in sorted({e["kind"] for e in g.edges})},
        },
        "dollars_by_edge_kind": {k: round(v, 2) for k, v in kind_sums.items()},
        "layer_labels": LAYER_LABEL,
        "cross_links": [
            {"name": x["name"], "key": x["key"],
             "layers": {lay: {"amount": round(L["amount"], 2), "count": L["count"],
                              "source_url": L.get("source_url", ""),
                              "source_type": L.get("source_type", "sourced")}
                        for lay, L in x["layers"].items()},
             "question": question_for(x)}
            for x in xs],
        "sample_chains": chains[:120],
        "nodes": list(g.nodes.values()),
        "edges": g.edges,
        "note": ("FUNDER -> PRIME -> SUBCONTRACTOR money chain for Maui County, cross-linked where "
                 "one entity appears in more than one layer. Sourced-only; questions, not findings."),
    }
    jpath = os.path.join(MAUIOS, "money_chain_maui.json")
    tmp = jpath + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)
    os.replace(tmp, jpath)

    # ---- HTML page ----
    html = render_html(g, xs, chains, stats, kind_sums)
    hpath = os.path.join(MAUIOS, "money_chain_maui.html")
    tmp = hpath + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(html)
    os.replace(tmp, hpath)

    out("chain_link: %d nodes (%d entities), %d edges, %d cross-layer overlaps"
        % (len(g.nodes), n_ent, len(g.edges), len(xs)))
    out("  edge kinds:", ", ".join("%s=%d" % (k, sum(1 for e in g.edges if e["kind"] == k))
                                    for k in sorted({e["kind"] for e in g.edges})))
    for i, c in enumerate(chains[:3], 1):
        also = (" [also: %s]" % ", ".join(c["sub_also"])) if c["sub_also"] else ""
        out("  chain %d: %s -> %s -> %s  $%s%s" % (i, c["funder"], c["prime"], c["sub"],
                                                   usd(c["amount"]), also))
    out("-> " + hpath)
    out("-> " + jpath)
    return 0


if __name__ == "__main__":
    sys.exit(main())
