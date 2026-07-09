# -*- coding: utf-8 -*-
"""
crosswalk_build.py - ALIGN the public-record civic datasets into ONE entity graph
(nodes + sourced edges) for the accountability crosswalk surface.

STRICT FRAME (non-negotiable): public records only; every edge carries its SOURCE +
a NEUTRAL "what to ask" question; NO accusations, NO guilt conclusions, NO inferred
crimes, NO private personal info. The system DOCUMENTS and ASKS; it does not convict.
Mirrors the existing vendor_donor_join / parity_check framing ("every hit is a QUESTION
to verify, not proof").

Output: reports/mauios/crosswalk_graph.json   (meta, nodes[], edges[])
"""
import json, os, re, datetime

MAU = r"C:\Users\12sgi\Documents\Claude\Projects\Video System elementLOTUS\reports\mauios"
def load(rel):
    p = os.path.join(MAU, rel)
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else None

def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")

def norm_vendor(s):
    s = (s or "").lower()
    s = re.sub(r"\b(inc|llc|ltd|corp|co|incorporated|company|consulting|group|associates|architects|engineers|engineering)\b", "", s)
    return re.sub(r"[^a-z0-9]+", "", s)

def usd(x):
    return "${:,.0f}".format(x or 0)

officials = load("officials.json") or {}
money     = load("statewide_money.json") or {}
vdj       = load("vendor_donor_join.json") or {}
hands     = load("hands_maui_awards.json") or {}
profiles  = load("donor_profiles.json") or []
parity    = load("parity_check.json") or {}

nodes = {}
edges = []
def node(nid, **kw):
    if nid not in nodes:
        nodes[nid] = {"id": nid, **kw}
    else:
        nodes[nid].update({k: v for k, v in kw.items() if v not in (None, "", 0)})
    return nid

# ---- OFFICIAL nodes (Maui Council, from the public vote/recusal record) ----
label_by_off = {}
for m in vdj.get("matched", []):
    for h in m.get("hits", []):
        if h.get("official") and h.get("official_label"):
            label_by_off[h["official"]] = h["official_label"]
for name, rec in officials.items():
    node("off:" + slug(name), type="official", name=name,
         label=label_by_off.get(name, name + " - Maui County Council"),
         votes=rec.get("total_votes", 0), recused=rec.get("recused", 0),
         drill="officials_scorecard.html")
for p in profiles:
    if "Mayor" in (p.get("label", "")):
        node("off:" + slug(p.get("key", "mayor")), type="official", name=p.get("key"),
             label=p.get("label"), office="Mayor", drill="money_behind_officials.html")

# ---- County office + VENDOR nodes + CONTRACT edges (HANDS public awards) ----
node("office:maui-county", type="office", name="County of Maui", drill="county_dashboard.html")
hands_src = hands.get("source", "HANDS hands.ehawaii.gov")
for v in hands.get("vendors", []):
    vid = "ven:" + norm_vendor(v.get("vendor"))
    node(vid, type="vendor", name=v.get("vendor"), award_total=v.get("total", 0),
         award_count=v.get("count", 0), drill="maui_contract_awards.html")
    edges.append({
        "src": vid, "dst": "office:maui-county", "kind": "contract",
        "amount": v.get("total", 0), "count": v.get("count", 0),
        "detail": "%d county awards totaling %s" % (v.get("count", 0), usd(v.get("total", 0))),
        "source": hands_src + " (public Notice of Award)",
        "ask": "Were these awards competitively bid and documented in the public record?",
    })

# ---- MONEY x CONTRACT edges (vendor_donor_join - already sourced matches) ----
match_method = vdj.get("method", "name match - a question to verify")
for m in vdj.get("matched", []):
    vid = "ven:" + norm_vendor(m.get("vendor"))
    node(vid, type="vendor", name=m.get("vendor"), award_total=m.get("award_total", 0),
         award_count=m.get("award_count", 0), drill="maui_contract_awards.html")
    for h in m.get("hits", []):
        off = h.get("official")
        if not off:
            continue
        oid = "off:" + slug(off)
        node(oid, type="official", name=off, label=h.get("official_label", off),
             drill="money_behind_officials.html")
        person = (h.get("official_label", off).split(" - ")[0])
        edges.append({
            "src": vid, "dst": oid, "kind": "money_x_contract",
            "amount": h.get("amount", 0), "award": m.get("award_total", 0),
            "contributor": h.get("contributor"), "basis": h.get("basis"),
            "detail": "%s in contributions from %s (%s), set beside %s in county awards to the firm" % (
                usd(h.get("amount", 0)), h.get("contributor", "?"), h.get("basis", "?"), usd(m.get("award_total", 0))),
            "source": "HI Campaign Spending Commission (contributions) x %s (awards); %s" % (hands_src, match_method),
            "ask": "Did %s disclose this relationship and recuse where required when %s's matters came before the body?" % (
                person, m.get("vendor")),
        })

# ---- PARITY edges (the "pair that does not answer" - recusal question, neutral) ----
for pr in parity.get("hewa", {}).get("pairs", []):
    vid = "ven:" + norm_vendor(pr.get("vendor"))
    for off in pr.get("officials", []):
        edges.append({
            "src": "off:" + slug(off), "dst": vid, "kind": "parity_question",
            "award": pr.get("award_total", 0), "contrib": pr.get("contrib_total", 0),
            "leverage": pr.get("leverage", 0),
            "detail": "%s in awards alongside %s in contributions" % (usd(pr.get("award_total", 0)), usd(pr.get("contrib_total", 0))),
            "source": "reports/mauios/vendor_donor_join.json (CSC x HANDS public records)",
            "ask": "Is there a recusal or disclosure in the minutes for this pair? If not, why not? (a question, not a finding)",
        })

# ---- REAL-ESTATE sector money -> office ----
node("sector:real-estate", type="sector", name="Real-estate / development donors",
     total=money.get("realestate_total", 0), drill="money_behind_officials.html")
for r in money.get("realestate_by_office", []):
    ooff = "office:" + slug(r.get("office"))
    node(ooff, type="office", name=r.get("office"), re_total=r.get("total", 0))
    edges.append({
        "src": "sector:real-estate", "dst": ooff, "kind": "sector_money",
        "amount": r.get("total", 0), "count": r.get("n", 0),
        "detail": "%s from real-estate / development donors (%d gifts)" % (usd(r.get("total", 0)), r.get("n", 0)),
        "source": "HI Campaign Spending Commission (donor occupation/employer = real-estate sector)",
        "ask": "How does this sector's giving line up with land-use and permitting decisions by this office?",
    })

# ---- TOP PAC donors -> the money supply ----
node("office:statewide", type="office", name="Statewide offices (HI)", drill="statewide_money_patterns.html")
for t in (money.get("top_donors", []) or [])[:12]:
    did = "don:" + slug(t.get("name"))
    node(did, type="donor", name=t.get("name"), total=t.get("total", 0),
         cands=t.get("cands", 0), drill="statewide_money_patterns.html")
    edges.append({
        "src": did, "dst": "office:statewide", "kind": "contributions",
        "amount": t.get("total", 0), "count": t.get("cands", 0),
        "detail": "%s across %d candidates" % (usd(t.get("total", 0)), t.get("cands", 0)),
        "source": "HI Campaign Spending Commission",
        "ask": "What did this donor's funded candidates decide on matters touching the donor's interests?",
    })

# ---- LEGISLATOR nodes (Maui delegation, public roll-call record) ----
lege = (load("lege/legislators.json") or {}).get("legislators", {})
for lname in list(lege.keys())[:12]:
    node("leg:" + slug(lname), type="legislator", name=lname,
         label=lname + " - HI Legislature", drill="lege_legislator_scorecard.html")

node_list = list(nodes.values())
meta = {
    "generated": datetime.datetime.now().isoformat(timespec="seconds"),
    "status": "DRAFT - owner review before any public publish",
    "frame": ("Public records only. Every edge is a SOURCED, documented connection shown with its citation "
              "and a NEUTRAL question. The system documents and asks; it does not convict. No accusations, "
              "no guilt, no private personal information."),
    "sources": ["HI Campaign Spending Commission", "HANDS hands.ehawaii.gov (Notices of Award)",
                "Maui County Council minutes (votes/recusals)", "HI State Legislature roll-calls"],
    "unsourced_or_gaps": [
        "Public EMPLOYEES / staff -> department roster is NOT in the current datasets (no source pulled). "
        "Only ELECTED officials + their public committee roles are represented; an org-chart / salary-commission "
        "public-records pull would be needed to add an employee->department layer. Not fabricated here.",
        "Vendor<->donor links are MECHANICAL NAME MATCHES (firm/individual token match), flagged as questions to "
        "verify against the underlying filings, never asserted as the same legal person without confirmation.",
    ],
    "counts": {
        "nodes": len(node_list),
        "officials": sum(1 for n in node_list if n["type"] == "official"),
        "vendors": sum(1 for n in node_list if n["type"] == "vendor"),
        "donors": sum(1 for n in node_list if n["type"] == "donor"),
        "legislators": sum(1 for n in node_list if n["type"] == "legislator"),
        "offices": sum(1 for n in node_list if n["type"] == "office"),
        "edges": len(edges),
        "money_x_contract_edges": sum(1 for e in edges if e["kind"] == "money_x_contract"),
        "parity_questions": sum(1 for e in edges if e["kind"] == "parity_question"),
    },
}
op = os.path.join(MAU, "crosswalk_graph.json")
with open(op, "w", encoding="utf-8", newline="\n") as f:
    json.dump({"meta": meta, "nodes": node_list, "edges": edges}, f, ensure_ascii=False, indent=1)
print("wrote", op, os.path.getsize(op), "bytes")
print(json.dumps(meta["counts"], indent=1))
