#!/usr/bin/env python3
"""charter_crosswalk.py — the 12 Stones Sovereign Charter crosswalked against a tenant's
ENTIRE legal hierarchy, up through the Holy See.

Model (generalizes the Maui-only charter_law_map.py to every tenant):
  ROWS  = governance FUNCTIONS, each anchored to a real 12 Stones Sovereign Charter (SSC v5)
          article (the spec / overlay — constant across all tenants).
  COLS  = the law bodies in this tenant's hierarchy, bottom to apex:
            local (this tenant's charter + code) -> state -> United States -> International ->
            ICC -> ICJ -> Holy See.
          The apex spine (US..Holy See) is UNIVERSAL and shared by every tenant. The state layer
          is inherited (HI counties reuse the State of Hawaiʻi corpus; NYC/Liverpool reuse NY State).
          Only the LOCAL layer is genuinely per-tenant — that is the variable column the fan-out builds.
  CELL  = the REAL, citable instrument in that layer which already mirrors the same outcome,
          OR an honest "pending verification" marker naming the corpus to check. NEVER invented.

A roadmap of lawful CORRESPONDENCE — "the law that already exists to reach the same end" —
framed as a map/question, never an accusation against any person.

Per-tenant LOCAL layers are loaded from crosswalk_local.json (produced by the verified fan-out
workflow); the State of Hawaiʻi proof tenant is built in. Stdlib only. No subprocess.
Output: reports/mauios/crosswalk_<id>.html
"""
import os, json, html
from datetime import datetime, timezone, timedelta

HOME    = os.path.expanduser("~")
TOOL_DIR= os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.join(HOME, "Documents", "Claude", "Projects", "Video System elementLOTUS")
MAUIOS  = os.path.join(PROJECT, "reports", "mauios")
LOCAL_JSON = os.path.join(TOOL_DIR, "crosswalk_local.json")   # extra tenants from the fan-out
HST     = timezone(timedelta(hours=-10))
esc     = lambda s: html.escape(str(s or ""))
def now_hst(): return datetime.now(HST)

def C(layer, cite, note, conf="v"):
    return {"layer": layer, "cite": cite, "note": note, "conf": conf}

# ── governance FUNCTIONS (rows) + the SHARED APEX SPINE (US -> Holy See, universal). ─────────
FUNCTIONS = [
    {"key": "transparency", "title": "Transparency — every public dollar posted & traceable",
     "ssc": ("Art. VI §6.2 — Fiduciary Trust",
             "All budgets, fund allocations, and project expenses must be posted publicly via the RAIS system and linked to each Steward and Peacekeeper."),
     "spine": [
        C("United States", "5 U.S.C. §552 — Freedom of Information Act", "Federal public right of access to agency records."),
        C("International", "UN Convention against Corruption (UNCAC, 2003), Art. 10 & 13", "Public reporting and access to information on public administration."),
        C("Holy See", "Code of Canon Law (1983), c. 1287 §2", "Administrators of ecclesiastical goods must render a public account of offerings to the faithful."),
     ]},
    {"key": "conflict", "title": "Conflict of interest — no private funder steers a public decision",
     "ssc": ("Art. IV §4.3 — Custodianship of Resources",
             "No private industry or outside funder may influence Custodian decisions without full glyph-based transparency."),
     "spine": [
        C("United States", "18 U.S.C. §208 — Acts affecting a personal financial interest", "Criminal conflict-of-interest bar on federal officials."),
        C("International", "UNCAC (2003), Art. 7(4) & 8", "Systems to prevent conflicts of interest; codes of conduct for public officials."),
        C("Holy See", "Code of Canon Law (1983), c. 1298", "Caution against alienation of Church goods to administrators or their relatives.", "p"),
     ]},
    {"key": "sunshine", "title": "Open meetings & the people's voice in every decision",
     "ssc": ("Art. III §3.5 — Council of Stewards",
             "Governance decisions are made in the open, with the people's right to be heard before action."),
     "spine": [
        C("United States", "Government in the Sunshine Act — 5 U.S.C. §552b", "Open-meeting requirement for federal multi-member agencies."),
        C("International", "ICCPR (1966), Art. 25; UDHR Art. 21", "Right to take part in the conduct of public affairs."),
        C("Holy See", "Code of Canon Law (1983), c. 212 §3", "The faithful have the right to make their views on the good of the Church known."),
     ]},
    {"key": "fiduciary", "title": "Public-trust stewardship of land, water & resources",
     "ssc": ("Art. VI + Art. IV — Fiduciary Trust & Custodianship",
             "Resources are held in trust for the people and future generations, not for private extraction."),
     "spine": [
        C("United States", "Public-trust doctrine — PPL Montana, LLC v. Montana, 565 U.S. 576 (2012)", "Sovereign holds navigable waters/beds in trust for the public."),
        C("International", "Rio Declaration (1992), Principles 1–4; UN SDGs (2015)", "Sustainable stewardship for present and future generations."),
        C("Holy See", "Laudato Si' (2015) encyclical; Code of Canon Law c. 1254", "Care for the common home; Church goods held for sacred and just purposes."),
     ]},
    {"key": "sacred", "title": "Sacred sites & burial grounds — protected, repatriated",
     "ssc": ("Art. XV — Sacred Sites and Burial Grounds",
             "Burial grounds and sacred sites are inviolable; disturbance triggers lineage review and ceremonial protection."),
     "spine": [
        C("United States", "NAGPRA, 25 U.S.C. §3001 et seq.; NHPA, 54 U.S.C. §300101", "Repatriation of remains; protection of historic & cultural properties."),
        C("International", "UN Declaration on the Rights of Indigenous Peoples (UNDRIP, 2007), Arts. 11–12", "Rights to cultural/spiritual sites and to repatriation of remains."),
        C("Holy See", "Code of Canon Law (1983), cc. 1205–1213", "Sacred places: their dedication, protection, and the loss of that character only by decree."),
     ]},
    {"key": "enforcement", "title": "Enforcement, remedy & tribunals",
     "ssc": ("Art. XIII — Enforcement, Tribunals",
             "Violations of the public trust are heard; remedy and, where warranted, ceremonial removal follow."),
     "spine": [
        C("United States", "42 U.S.C. §1983 (deprivation of rights); §1985 (conspiracy)", "Civil action against officials who deprive rights under color of law — cited in the Charter itself."),
        C("International", "ICCPR (1966), Art. 2(3)", "Right to an effective remedy for violations."),
        C("ICC", "Rome Statute (2002), Arts. 5 & 17", "Jurisdiction over the gravest crimes; complementarity to national courts."),
        C("ICJ", "Statute of the International Court of Justice, Art. 36", "Jurisdiction over legal disputes between states."),
        C("Holy See", "Code of Canon Law (1983), Book VII (Processes), cc. 1400+; c. 1311", "The Church's own forum and its inherent right to penal coercion."),
     ]},
    {"key": "culture", "title": "Cultural & lineage integrity — language, education, heritage",
     "ssc": ("Art. V — Cultural and Lineage Integrity",
             "Language, lineage, and cultural transmission are protected as the living spine of governance."),
     "spine": [
        C("United States", "Native American Languages Act, 25 U.S.C. §2901; Apology Resolution, Pub. L. 103-150 (1993)", "Federal policy to preserve Native languages; acknowledgment of the 1893 overthrow."),
        C("International", "UNDRIP (2007), Arts. 13–14; ICESCR Art. 15", "Rights to language, culturally appropriate education, and cultural life."),
        C("Holy See", "Vatican II, Sacrosanctum Concilium (1963) — inculturation/vernacular", "Magisterial principle of honoring a people's language and culture.", "p"),
     ]},
    {"key": "selfdet", "title": "Foundation & self-determination of the people",
     "ssc": ("Art. I — Foundation",
             "The Charter rests on the people's inherent right to self-governance (referencing the 1864 Constitution Preamble)."),
     "spine": [
        C("United States", "Apology Resolution, Pub. L. 103-150 (1993)", "Congress acknowledges the illegal overthrow of the Kingdom of Hawaiʻi and the unrelinquished claims of Native Hawaiians."),
        C("International", "UN Charter Art. 1(2); ICCPR/ICESCR common Art. 1; UNGA Res. 1514 (1960)", "Self-determination of peoples as a foundational principle of international law."),
        C("ICJ", "Western Sahara, Advisory Opinion (1975); Chagos, Advisory Opinion (2019)", "Self-determination affirmed as an erga omnes obligation."),
        C("Holy See", "Pacem in Terris (1963) encyclical", "The rights of peoples and nations to existence and self-development.", "p"),
     ]},
]
FUNC_BY_KEY = {f["key"]: f for f in FUNCTIONS}

# The national layer was historically baked into each function's spine as a "United States" cell.
# Lift it into NATIONS so the layer can vary by country (UK, Japan, Switzerland, ...). What remains
# of the spine — International -> ICC -> ICJ -> Holy See — is universal and shared by every tenant.
NATIONS = {"us": {"label": "United States",
                  "layer": {fn["key"]: next((c for c in fn["spine"] if c["layer"] == "United States"), None) for fn in FUNCTIONS}}}
def apex_spine(fn): return [c for c in fn["spine"] if c["layer"] != "United States"]

# ── built-in proof tenant: State of Hawaiʻi (it IS the parent corpus -> no state_parent) ─────
TENANTS = {
    "state": {
        "id": "HI-000", "name": "State of Hawaiʻi", "seat": "Honolulu", "state_parent": None,
        "tagline": "The parent corpus — Constitution + Hawaiʻi Revised Statutes — that every county charter and code lays on top of.",
        "local_label": "State of Hawaiʻi (Constitution + HRS)",
        "local": {
            "transparency": C("State of Hawaiʻi", "HRS Ch. 92F (UIPA); HRS Ch. 11, Pt. XIII (Campaign Finance)", "Open-records right + every campaign contribution made public record via the Campaign Spending Commission."),
            "conflict":     C("State of Hawaiʻi", "HRS Ch. 84 — State Ethics Code (Standards of Conduct)", "Conflict-of-interest disclosure and recusal; enforced by the State Ethics Commission."),
            "sunshine":     C("State of Hawaiʻi", "HRS Ch. 92 — Sunshine Law (open meetings)", "Public's right to open meetings and to testify before any board acts."),
            "fiduciary":    C("State of Hawaiʻi", "Haw. Const. Art. XI §1 (public trust); Public Land Trust, HRS Ch. 171", "Natural resources held in trust for the benefit of the people."),
            "sacred":       C("State of Hawaiʻi", "HRS Ch. 6E — Historic Preservation; §6E-43 (burial sites) + Island Burial Councils", "State protection of burial sites and historic/cultural properties."),
            "enforcement":  C("State of Hawaiʻi", "Haw. Const. Art. VI (Judiciary); HRS Title 32 (Courts)", "The state forum for remedy and adjudication."),
            "culture":      C("State of Hawaiʻi", "Haw. Const. Art. XV §4 (Hawaiian + English official); Art. X §4 (Hawaiian education); Art. XII (OHA / Hawaiian Affairs)", "Hawaiian as an official language; constitutional Hawaiian-education and Hawaiian-affairs mandates."),
            "selfdet":      C("State of Hawaiʻi", "Haw. Const. Preamble & Art. XII; 1978 Con-Con Hawaiian provisions", "Constitutional recognition of Native Hawaiian rights and trust obligations."),
        },
    },
    # The APEX tenant — the Holy See is the top of every tenant's hierarchy, so it has no
    # downward spine; it crosswalks the SSC to its OWN law (Code of Canon Law + the Fundamental
    # Law of Vatican City State) and to the financial-governance body that administers it.
    "holysee": {
        "id": "VAT-HS", "name": "Holy See / Vatican City State", "seat": "Vatican City",
        "apex": True, "state_parent": None,
        "tagline": "The apex of the hierarchy. Where every tenant's crosswalk terminates — here it is the subject: the Holy See's own law and the financial-governance bodies that administer it.",
        "local_label": "Holy See (Canon Law + Fundamental Law of Vatican City State)",
        "local": {
            "transparency": C("Holy See — law", "Code of Canon Law (1983), c. 1287 §2", "Administrators of ecclesiastical goods must render a public account of offerings to the faithful."),
            "conflict":     C("Holy See — law", "Code of Canon Law (1983), c. 1298", "Caution against alienation of Church goods to administrators or their relatives.", "p"),
            "sunshine":     C("Holy See — law", "Code of Canon Law (1983), c. 212 §3", "The faithful have the right, even the duty, to make their views on the good of the Church known."),
            "fiduciary":    C("Holy See — law", "Code of Canon Law (1983), c. 1254; Laudato Si' (2015)", "Church goods are held for sacred purposes and the care of the common home, not private gain."),
            "sacred":       C("Holy See — law", "Code of Canon Law (1983), cc. 1205–1213", "Sacred places: their dedication, protection, and the loss of that character only by decree."),
            "enforcement":  C("Holy See — law", "Code of Canon Law (1983), Book VII (Processes), cc. 1400+; Fundamental Law of Vatican City State (2023), judicial order", "The Church's canonical forum and the Vatican City State penal jurisdiction."),
            "culture":      C("Holy See — law", "Vatican II, Sacrosanctum Concilium (1963) — inculturation/vernacular", "Magisterial principle of honoring a people's language and culture.", "p"),
            "selfdet":      C("Holy See — law", "Lateran Treaty (1929); Fundamental Law of Vatican City State (2023)", "Established Vatican City State sovereignty and the Holy See's international legal personality."),
        },
        "gov": {
            "transparency": C("Holy See — governance", "Secretariat for the Economy (2014); Office of the Auditor General (2014)", "Publishes the annual Consolidated Financial Statement; independent audit of Holy See entities."),
            "conflict":     C("Holy See — governance", "Council for the Economy (2014); financial-reform motu proprios", "Sets economic policy and oversight across all Holy See and Vatican City State entities."),
            "sunshine":     C("Holy See — governance", "Praedicate Evangelium (2022) — apostolic constitution on the Roman Curia", "Reorganized the Curia and its consultative/accountability structures.", "p"),
            "fiduciary":    C("Holy See — governance", "APSA — Administration of the Patrimony of the Apostolic See", "Manages the Holy See's patrimony, real estate, and investments; reports net results annually."),
            "sacred":       C("Holy See — governance", "Fabric of St. Peter; Pontifical Commission for Sacred Archaeology", "Custody and conservation of sacred sites and the catacombs.", "p"),
            "enforcement":  C("Holy See — governance", "Vatican City State Tribunal + Office of the Promoter of Justice", "The court that in Dec. 2023 convicted a cardinal of embezzlement in the London-property case (on appeal)."),
            "culture":      C("Holy See — governance", "Dicastery for Culture and Education (Praedicate Evangelium, 2022)", "Curial body for culture, education, and heritage."),
            "selfdet":      C("Holy See — governance", "Secretariat of State; Vatican UN Permanent Observer Mission", "Conducts the Holy See's diplomacy and its standing in international law."),
        },
    },
}

def load_extra_tenants():
    """Merge fan-out tenants from crosswalk_local.json. Each entry supplies the LOCAL layer
    (8 cells); the cell `layer` label is stamped from `local_jur`. Verified upstream."""
    if not os.path.exists(LOCAL_JSON):
        return
    try:
        data = json.load(open(LOCAL_JSON, encoding="utf-8"))
    except Exception as e:
        print("  ! crosswalk_local.json unreadable:", e); return
    # per-country national layers (UK, Japan, ...) used by the world-city tenants
    for ncode, nobj in data.get("nations", {}).items():
        lbl = nobj.get("label", ncode)
        NATIONS[ncode] = {"label": lbl,
                          "layer": {k: C(lbl, c.get("cite", ""), c.get("note", ""), c.get("conf", "p"))
                                    for k, c in nobj.get("layer", {}).items()}}
    for t in data.get("tenants", []):
        tid = t["id"]
        local = {}
        for k, cell in t.get("local", {}).items():
            local[k] = C(t.get("local_jur", t.get("local_label", t["name"])),
                         cell.get("cite", ""), cell.get("note", ""), cell.get("conf", "p"))
        TENANTS[tid] = {"id": t.get("code", tid), "name": t["name"], "seat": t.get("seat", ""),
                        "state_parent": t.get("state_parent"), "nation": t.get("nation", "us"),
                        "tagline": t.get("tagline", ""),
                        "local_label": t.get("local_label", t["name"]), "local": local}

CONF_TAG = {"v": '<span class="cf v">cited</span>', "p": '<span class="cf p">§ pending verification</span>'}

def cell_html(c):
    return ('<div class="cell %s"><div class="cl">%s</div><div class="ci">%s %s</div><div class="cn">%s</div></div>') % (
        "pend" if c["conf"] == "p" else "", esc(c["layer"]), esc(c["cite"]), CONF_TAG[c["conf"]], esc(c["note"]))

def layers_for(fn, t):
    """local -> (inherited state) -> shared apex spine. The apex tenant (Holy See) has no
    downward spine: it shows its own law + its governing body."""
    out = []
    loc = t["local"].get(fn["key"])
    if loc: out.append(loc)
    if t.get("apex"):
        gov = t.get("gov", {}).get(fn["key"])
        if gov: out.append(gov)
        return out
    sp = t.get("state_parent")
    if sp and sp in TENANTS:
        st = TENANTS[sp]["local"].get(fn["key"])
        if st: out.append(st)
    nat = NATIONS.get(t.get("nation", "us"))
    if nat:
        nc = nat["layer"].get(fn["key"])
        if nc: out.append(nc)
    out.extend(apex_spine(fn))
    return out

def row_card(fn, t):
    art, text = fn["ssc"]
    layers = layers_for(fn, t)
    npend = sum(1 for c in layers if c["conf"] == "p")
    return """<div class="fn">
  <div class="fn-hd"><span class="fn-t">%s</span><span class="fn-ladder">%d law bodies%s</span></div>
  <div class="ssc"><span class="ssc-k">12 Stones Sovereign Charter &middot; %s</span><span class="ssc-x">&ldquo;%s&rdquo;</span></div>
  <div class="cells">%s</div>
</div>""" % (esc(fn["title"]), len(layers), (" &middot; %d pending" % npend) if npend else "",
             esc(art), esc(text), "".join(cell_html(c) for c in layers))

def hierarchy_line(t):
    if t.get("apex"):
        return ("<b>%s</b> &mdash; the apex every other tenant&rsquo;s crosswalk answers up to "
                "(no layer sits above it).") % esc(t["local_label"])
    chain = [t["local_label"]]
    sp = t.get("state_parent")
    if sp and sp in TENANTS: chain.append(TENANTS[sp]["name"])
    nat = NATIONS.get(t.get("nation", "us"))
    if nat: chain.append(nat["label"])
    chain += ["International", "ICC", "ICJ", "Holy See"]
    return " &rarr; ".join("<b>%s</b>" % esc(x) for x in chain)

def build(tid):
    t = TENANTS[tid]
    g = now_hst().strftime("%Y-%m-%d %H:%M HST")
    cards = "".join(row_card(fn, t) for fn in FUNCTIONS)
    tot = sum(len(layers_for(fn, t)) for fn in FUNCTIONS)
    pend = sum(1 for fn in FUNCTIONS for c in layers_for(fn, t) if c["conf"] == "p")
    return """<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Charter Crosswalk — %s — govOS · Kilo Aupuni</title>
<style>
 body{margin:0;background:#0c100e;color:#e8e4d8;font-family:Georgia,'Iowan Old Style',serif;line-height:1.6}
 .wrap{max-width:1100px;margin:0 auto;padding:30px 22px 70px}
 .eyebrow{font-family:Consolas,monospace;font-size:11px;letter-spacing:1.4px;color:#d9b24c;text-transform:uppercase}
 h1{font-size:27px;font-weight:600;margin:8px 0 4px}
 .lead{font-size:14px;color:#cfc9b6;max-width:80ch}
 .spine{font-family:Consolas,monospace;font-size:11px;color:#9fd9bf;margin:12px 0 4px;letter-spacing:.4px}
 .spine b{color:#d9e9df}
 .disc{font-size:12px;color:#9a957f;font-style:italic;border-left:2px solid rgba(217,178,76,.4);padding:7px 12px;margin:14px 0}
 .fn{border:1px solid rgba(255,255,255,.1);border-radius:14px;padding:16px 18px;margin:14px 0;background:rgba(255,255,255,.02)}
 .fn-hd{display:flex;justify-content:space-between;gap:12px;align-items:baseline;flex-wrap:wrap}
 .fn-t{font-size:17px;font-weight:600;color:#f0ead8} .fn-ladder{font-family:Consolas,monospace;font-size:11px;color:#9a957f}
 .ssc{margin:9px 0 12px;font-size:13px;color:#cfc9b6;background:rgba(217,178,76,.05);border-radius:8px;padding:9px 12px}
 .ssc-k{display:block;font-family:Consolas,monospace;font-size:11px;color:#d9b24c;letter-spacing:.5px;margin-bottom:3px}
 .ssc-x{font-style:italic}
 .cells{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:9px}
 .cell{border:1px solid rgba(255,255,255,.08);border-radius:10px;padding:9px 11px;background:rgba(255,255,255,.015)}
 .cell.pend{border-color:rgba(224,106,74,.35);border-style:dashed}
 .cl{font-family:Consolas,monospace;font-size:10px;letter-spacing:.6px;text-transform:uppercase;color:#9fd9bf;margin-bottom:3px}
 .ci{font-size:12.5px;color:#e8e4d8;font-weight:600}
 .cn{font-size:11.5px;color:#bdb8a4;margin-top:3px}
 .cf{font-family:Consolas,monospace;font-size:9px;letter-spacing:.4px;padding:1px 6px;border-radius:8px;vertical-align:middle;white-space:nowrap}
 .cf.v{background:rgba(86,192,138,.14);color:#56c08a} .cf.p{background:rgba(224,106,74,.14);color:#e06a4a}
 a{color:#d9b24c}
 footer{margin-top:34px;border-top:1px solid rgba(255,255,255,.1);padding-top:12px;font-family:Consolas,monospace;font-size:10.5px;color:#9a957f}
</style></head><body><div class="wrap">
<div class="eyebrow">12 Stones Global &middot; Kilo Aupuni &middot; %s &middot; seat: %s</div>
<h1>Charter &#8644; Law Crosswalk &mdash; %s</h1>
<p class="lead">The <b>12 Stones Sovereign Charter</b> is the spec. Each governance function below is
traced from the Charter article that prescribes it, down to the <b>real, enforceable law that already
exists to reach the same outcome</b> &mdash; through this tenant&rsquo;s own corpus and up the full
hierarchy. A roadmap of lawful correspondence, framed as a map &mdash; never an accusation.</p>
<div class="spine">Hierarchy &middot; %s</div>
<div class="disc">Integrity: every cell names a real instrument. A solid flagship citation is tagged
<b>cited</b>; where the exact section is still being verified the cell is tagged <b>§ pending verification</b>
and shown dashed &mdash; named, never invented. %d law-body cells across %d functions, %d pending verification.</div>
%s
<p style="margin-top:18px"><a href="jurisdictions.html">all govOS jurisdictions</a>
&middot; <a href="charter_application.html">Charter &rarr; Law &rarr; live evidence (Maui)</a>
&middot; <a href="parity_check.html">parity — pairs that no longer answer</a></p>
<footer>generated %s &middot; charter-crosswalk v2 &middot; SSC v5 &times; %s &middot; sources: local charter/code, HRS/NY law, U.S. Code, UN/UNCAC/ICCPR/UNDRIP, Rome &amp; ICJ Statutes, Code of Canon Law (1983) &middot; Kilo Aupuni &middot; aloha &middot; pono</footer>
</div></body></html>""" % (
        esc(t["name"]), esc(t["name"]), esc(t["seat"]), esc(t["name"]),
        hierarchy_line(t), tot, len(FUNCTIONS), pend, cards, g, esc(t["name"]))

def main():
    os.makedirs(MAUIOS, exist_ok=True)
    load_extra_tenants()
    for tid in TENANTS:
        out = os.path.join(MAUIOS, "crosswalk_%s.html" % tid)
        open(out, "w", encoding="utf-8", newline="\n").write(build(tid))
        t = TENANTS[tid]
        tot = sum(len(layers_for(fn, t)) for fn in FUNCTIONS)
        pend = sum(1 for fn in FUNCTIONS for c in layers_for(fn, t) if c["conf"] == "p")
        print("crosswalk_%s.html  %-22s %d functions  %d cells  %d pending" % (tid, t["name"], len(FUNCTIONS), tot, pend))
    return 0

if __name__ == "__main__":
    import sys; sys.exit(main())
