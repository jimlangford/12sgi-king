# -*- coding: utf-8 -*-
"""
collusion_graph.py — the donor-BLOC network across the Maui Council, in Neo4j + a graphic console page.

Jimmy 2026-07-08: "run neo4j on all of that data and location data to show how votes are stolen with
collusion et al." Built HONESTLY: the vote record itself is near-UNANIMOUS on almost every joint bill
(verified: 34 joint-vote bills, essentially 100% AYE together — see officials.json vote_log) — so "did two
reps vote the same way" is not a real signal here, it is the near-universal default. The REAL, sourced,
graphable pattern is the DONOR-BLOC NETWORK: which donor/vendor entities fund MULTIPLE council members
SIMULTANEOUSLY, at what dollar scale, and where (real parcels via Hawaii statewide GIS). That is a
structural fact, not proof any one vote was "stolen" — presented here as a sourced pattern to question,
never a verdict. No fabricated coordination is claimed.

ADDITIVE to Neo4j — never wipes chain_to_graph.py's existing money_chain_maui.json graph (distinct labels:
Representative/Donor/Vendor/Parcel, property layer='silencing_audit').

  python tools/kilo-aupuni/collusion_graph.py            # compute + load Neo4j + render the console page
"""
import io, json, os, re, sys, urllib.error, urllib.parse, urllib.request
from datetime import datetime, timezone, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(os.path.dirname(HERE))
MAUIOS = os.path.join(PROJ, "reports", "mauios")
NEO = os.environ.get("NEO4J_HTTP", "http://127.0.0.1:7474/db/neo4j/tx/commit")
HST = timezone(timedelta(hours=-10))
sys.path.insert(0, HERE)
import testimony_effect_map as tem  # reuse the REAL GIS TMK/centroid lookup — never duplicate it


def _load(path, default=None):
    try:
        return json.load(open(path, encoding="utf-8"))
    except Exception:
        return default


def _esc(s):
    import html
    return html.escape(str(s if s is not None else ""))


def cypher(statements, timeout=90):
    body = json.dumps({"statements": statements}).encode("utf-8")
    req = urllib.request.Request(NEO, data=body, headers={"Content-Type": "application/json", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8", "replace"))
    except urllib.error.URLError as e:
        print("Neo4j not reachable at %s (%s)" % (NEO, str(e)[:140]))
        return None


def _rows(out, i=0):
    if not out or not out.get("results"):
        return []
    return [row.get("row", []) for row in out["results"][i].get("data", [])]


# ---------- 1) compute the donor-bloc network from sourced data (pure Python, no invention) ----------
def build_network():
    officials = _load(os.path.join(MAUIOS, "officials.json"), {}) or {}
    donor_profiles = _load(os.path.join(MAUIOS, "donor_profiles.json"), []) or []
    vdj = _load(os.path.join(MAUIOS, "vendor_donor_join.json"), {}) or {}

    reps, donors, edges = {}, {}, []  # donors[name] = {"total":$, "reps":{rep:$}, "kind":"realestate"|"vendor"}

    dp_by_key = {d.get("key"): d for d in donor_profiles}
    for rep, d in officials.items():
        reps[rep] = {"total_votes": d.get("total_votes", 0), "noes": d.get("noes", 0), "recused": d.get("recused", 0)}
        prof = dp_by_key.get(rep) or {}
        for don in (prof.get("realestate") or {}).get("donors", []):
            nm = re.sub(r"\s+", " ", (don.get("name") or "").strip())
            if not nm:
                continue
            key = nm.upper()
            donors.setdefault(key, {"name": nm, "reps": {}, "kind": "realestate_donor", "employer": don.get("employer", "")})
            donors[key]["reps"][rep] = donors[key]["reps"].get(rep, 0) + float(don.get("amount", 0) or 0)

    # vendor-tied money (vendor_donor_join hits) — same donor-entity may recur here under contributor name
    for m in vdj.get("matched", []):
        for h in m.get("hits", []):
            nm = re.sub(r"\s+", " ", (h.get("contributor") or "").strip())
            if not nm:
                continue
            key = nm.upper()
            donors.setdefault(key, {"name": nm, "reps": {}, "kind": "vendor_tied_donor", "vendor": m.get("vendor"),
                                     "award_total": m.get("award_total", 0)})
            donors[key]["reps"][h["official"]] = donors[key]["reps"].get(h["official"], 0) + float(h.get("amount", 0) or 0)

    # THE BLOC: donor entities funding 2+ of the 9 current reps
    bloc = []
    for key, d in donors.items():
        if len(d["reps"]) >= 2:
            bloc.append({"donor": d["name"], "kind": d["kind"], "n_reps": len(d["reps"]),
                         "reps": d["reps"], "total": round(sum(d["reps"].values()), 2),
                         "vendor": d.get("vendor"), "award_total": d.get("award_total")})
    bloc.sort(key=lambda x: (-x["n_reps"], -x["total"]))
    return reps, donors, bloc


# ---------- 2) real location data for the bloc's top entities (reuses the existing GIS lookup) ----------
def bloc_locations(bloc, top_n=8):
    names = [b["donor"] for b in bloc[:top_n]]
    try:
        tmk_by_entity = tem.find_tmks_for_entity(names)
        all_tmks = sorted({t for v in tmk_by_entity.values() for t in v})
        centroids = tem.fetch_centroids(all_tmks) if all_tmks else {}
    except Exception as e:
        print("  GIS lookup unavailable (%s) — location layer skipped, honest-empty" % str(e)[:120])
        return {}, {}
    return tmk_by_entity, centroids


# ---------- 3) load into Neo4j, ADDITIVE (own labels, never touches the existing money-chain graph) ----------
def load_neo4j(reps, bloc, tmk_by_entity, centroids):
    if cypher([{"statement": "MATCH (n {layer:'silencing_audit'}) DETACH DELETE n"}]) is None:  # only OUR prior layer
        return False
    cypher([{"statement": "CREATE CONSTRAINT rep_id IF NOT EXISTS FOR (x:Representative) REQUIRE x.id IS UNIQUE"}])
    cypher([{"statement": "CREATE CONSTRAINT donor_id IF NOT EXISTS FOR (x:Donor) REQUIRE x.id IS UNIQUE"}])

    rep_rows = [{"id": "rep:" + k, "name": k, "total_votes": v["total_votes"], "noes": v["noes"],
                 "recused": v["recused"], "layer": "silencing_audit"} for k, v in reps.items()]
    cypher([{"statement": "UNWIND $rows AS n MERGE (x:Representative {id:n.id}) SET x += n",
             "parameters": {"rows": rep_rows}}])

    donor_rows, fund_rows, parcel_rows, own_rows = [], [], [], []
    for b in bloc:
        did = "donor:" + b["donor"].upper()
        donor_rows.append({"id": did, "name": b["donor"], "kind": b["kind"], "n_reps": b["n_reps"],
                           "total": b["total"], "layer": "silencing_audit"})
        for rep, amt in b["reps"].items():
            fund_rows.append({"donor": did, "rep": "rep:" + rep, "amount": amt})
        for tmk in tmk_by_entity.get(b["donor"], []):
            c = centroids.get(tmk)  # (x, y) tuple, Hawaii State Plane projected coords — see fetch_centroids docstring
            if c:
                pid = "parcel:" + tmk
                parcel_rows.append({"id": pid, "tmk": tmk, "x": c[0], "y": c[1], "layer": "silencing_audit"})
                own_rows.append({"donor": did, "parcel": pid})
    cypher([{"statement": "UNWIND $rows AS n MERGE (x:Donor {id:n.id}) SET x += n", "parameters": {"rows": donor_rows}}])
    cypher([{"statement": "UNWIND $rows AS e MATCH (d:Donor {id:e.donor}) MATCH (r:Representative {id:e.rep}) "
                          "MERGE (d)-[f:FUNDED]->(r) SET f.amount=e.amount, f.source='HI Campaign Spending Commission'",
             "parameters": {"rows": fund_rows}}])
    if parcel_rows:
        cypher([{"statement": "UNWIND $rows AS n MERGE (x:Parcel {id:n.id}) SET x += n", "parameters": {"rows": parcel_rows}}])
        cypher([{"statement": "UNWIND $rows AS e MATCH (d:Donor {id:e.donor}) MATCH (p:Parcel {id:e.parcel}) "
                              "MERGE (d)-[:OWNS_NEAR {source:'Hawaii Statewide GIS ParcelsZoning'}]->(p)",
                 "parameters": {"rows": parcel_rows and own_rows}}])
    v = cypher([{"statement": "MATCH (n {layer:'silencing_audit'}) RETURN count(n)"},
                {"statement": "MATCH ()-[r:FUNDED]->() RETURN count(r)"}])
    if v:
        print("  Neo4j LOADED (additive): %s silencing_audit nodes, %s FUNDED edges — live at http://127.0.0.1:7474"
              % (_rows(v, 0)[0][0] if _rows(v, 0) else "?", _rows(v, 1)[0][0] if _rows(v, 1) else "?"))
    return True


def cypher_bloc_query():
    """The actual pattern Neo4j answers that flat JSON can't: multi-hop donor-bloc discovery."""
    out = cypher([{"statement":
                   "MATCH (d:Donor {layer:'silencing_audit'})-[f:FUNDED]->(r:Representative) "
                   "WITH d, count(DISTINCT r) AS n_reps, collect(r.name) AS reps, sum(f.amount) AS total "
                   "WHERE n_reps >= 2 RETURN d.name, n_reps, reps, total ORDER BY n_reps DESC, total DESC LIMIT 15"}])
    return _rows(out, 0)


# ---------- 4) the graphic console page (self-contained SVG network + real-parcel map, CSP-safe) ----------
def svg_network(bloc, top_n=10):
    import math
    top = bloc[:top_n]
    all_reps = sorted({r for b in top for r in b["reps"]})
    W, H = 780, 520
    cx_d, cy_d, R_d = W * 0.32, H / 2, 190   # donors ring (left)
    cx_r, cy_r, R_r = W * 0.78, H / 2, 170   # reps ring (right)
    dpos, rpos = {}, {}
    for i, b in enumerate(top):
        a = 2 * math.pi * i / max(1, len(top)) - math.pi / 2
        dpos[b["donor"]] = (cx_d + R_d * math.cos(a) * 0.55, cy_d + R_d * math.sin(a))
    for i, rep in enumerate(all_reps):
        a = 2 * math.pi * i / max(1, len(all_reps)) - math.pi / 2
        rpos[rep] = (cx_r + R_r * math.cos(a) * 0.55, cy_r + R_r * math.sin(a))

    parts = ['<svg viewBox="0 0 %d %d" width="100%%" style="max-width:%dpx;display:block;margin:0 auto" '
             'xmlns="http://www.w3.org/2000/svg" role="img" aria-label="donor-bloc network">' % (W, H, W)]
    for b in top:
        x1, y1 = dpos[b["donor"]]
        for rep, amt in b["reps"].items():
            if rep not in rpos:
                continue
            x2, y2 = rpos[rep]
            w = max(0.8, min(4.5, amt / 800.0))
            parts.append('<line x1="%.0f" y1="%.0f" x2="%.0f" y2="%.0f" stroke="#c9760f" stroke-opacity=".45" stroke-width="%.1f"/>'
                         % (x1, y1, x2, y2, w))
    for rep, (x, y) in rpos.items():
        parts.append('<circle cx="%.0f" cy="%.0f" r="9" fill="#e3ad33"/>'
                     '<text x="%.0f" y="%.0f" fill="#f3d589" font-size="11" text-anchor="start" font-family="system-ui">%s</text>'
                     % (x, y, x + 12, y + 4, _esc(rep)))
    for b in top:
        x, y = dpos[b["donor"]]
        r = 5 + min(9, b["n_reps"] * 1.6)
        parts.append('<circle cx="%.0f" cy="%.0f" r="%.0f" fill="#5fc0d8"/>'
                     '<text x="%.0f" y="%.0f" fill="#9fd4e6" font-size="9.5" text-anchor="end" font-family="system-ui">%s (%d)</text>'
                     % (x, y, r, x - r - 6, y + 3, _esc(b["donor"][:26]), b["n_reps"]))
    parts.append('</svg>')
    return "".join(parts)


def svg_map(centroids, tmk_by_entity, width=560, height=380):
    # centroids: {tmk: (x, y)} in Hawaii State Plane projected coords (see fetch_centroids docstring) —
    # a relative in-house map, not tied to a lat/lon basemap, so raw projected x/y is the honest unit.
    pts = []
    for entity, tmks in tmk_by_entity.items():
        for t in tmks:
            c = centroids.get(t)
            if c:
                pts.append((c[0], c[1], entity))
    if not pts:
        return '<p style="color:#8a7c60;font-style:italic;text-align:center">No parcel locations resolved for this bloc (honest-empty — GIS lookup returned none).</p>'
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    minx, maxx, miny, maxy = min(xs), max(xs), min(ys), max(ys)
    pad = 30
    def proj(px, py):
        x = pad + (px - minx) / max(1e-6, (maxx - minx)) * (width - 2 * pad)
        y = height - pad - (py - miny) / max(1e-6, (maxy - miny)) * (height - 2 * pad)
        return x, y
    parts = ['<svg viewBox="0 0 %d %d" width="100%%" style="max-width:%dpx;display:block;margin:0 auto;background:#100d09;'
             'border-radius:10px" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="donor parcel map">' % (width, height, width)]
    for px, py, entity in pts:
        x, y = proj(px, py)
        parts.append('<circle cx="%.0f" cy="%.0f" r="4.5" fill="#e0872f" fill-opacity=".85"><title>%s</title></circle>'
                     % (x, y, _esc(entity)))
    parts.append('</svg>')
    return "".join(parts)


def render_page(reps, bloc, tmk_by_entity, centroids):
    css = (":root{--bg:#0d0b08;--pan:#16130d;--ln:#2a241a;--ink:#efe9da;--mut:#b3a98f;--fn:#8a7c60;"
           "--gold:#e3ad33;--g2:#f3d589;--sea:#5fc0d8;--amb:#e0872f}"
           "*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);"
           "font-family:'Segoe UI',system-ui,sans-serif;line-height:1.55}"
           ".wrap{max-width:960px;margin:0 auto;padding:24px 20px 70px}"
           ".hd{border-bottom:1px solid rgba(227,173,51,.25);padding-bottom:16px;margin-bottom:20px}"
           ".hd h1{margin:0 0 6px;font-size:clamp(24px,4.6vw,34px);color:var(--g2)}"
           ".hd p{color:var(--mut);max-width:70ch;margin:8px 0 0}"
           ".honest{background:rgba(95,192,216,.07);border:1px solid #2a3f47;border-radius:10px;padding:14px 16px;"
           "margin:16px 0;font-size:14px;color:var(--mut)}.honest b{color:var(--sea)}"
           "h2{font-size:14px;letter-spacing:.06em;text-transform:uppercase;color:var(--gold);margin:30px 0 12px}"
           ".gr{background:var(--pan);border:1px solid var(--ln);border-radius:12px;padding:18px 10px;text-align:center}"
           "table{width:100%;border-collapse:collapse;font-size:14px;margin-top:10px}"
           "th{text-align:left;color:var(--fn);font:600 11px/1 Consolas,monospace;letter-spacing:.05em;"
           "text-transform:uppercase;padding:8px 10px;border-bottom:1px solid var(--ln)}"
           "td{padding:10px;border-bottom:1px solid rgba(255,255,255,.05);vertical-align:top}"
           ".mono{font-family:Consolas,monospace;color:var(--g2)}"
           ".reps{color:var(--mut);font-size:12.5px}"
           ".foot{color:var(--fn);font-size:12px;margin-top:34px;padding-top:16px;border-top:1px solid var(--ln)}"
           ".legend{display:flex;gap:18px;justify-content:center;font-size:12px;color:var(--fn);margin-top:8px}"
           ".legend span{display:inline-flex;align-items:center;gap:5px}"
           ".dot{width:9px;height:9px;border-radius:50%}")

    rows = ""
    for b in bloc[:20]:
        rep_list = ", ".join(sorted(b["reps"].keys()))
        rows += ('<tr><td>%s<div class="reps">%s</div></td><td class="mono">%d</td><td class="mono">$%s</td>'
                 '<td>%s</td></tr>'
                 % (_esc(b["donor"]), _esc(rep_list), b["n_reps"], "{:,.0f}".format(b["total"]),
                    _esc((b.get("vendor") or "").title() or "&mdash;")))

    body = ('<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>The donor bloc &mdash; who funds the whole Council | govOS</title><style>%s</style></head>'
            '<body><div class="wrap">'
            '<div class="hd"><h1>The donor bloc</h1>'
            '<p>Which donor and vendor entities fund <b style="color:var(--ink)">multiple</b> Maui Council members '
            'at once &mdash; the network structure behind the money, built as a graph (Neo4j) and mapped to real '
            'parcel locations where the donor entities hold recorded land (Hawaiʻi Statewide GIS).</p></div>'
            '<div class="honest"><b>Read this honestly &mdash;</b> across 34 joint-vote bills in the record, council '
            'votes are recorded as AYE together almost every time (near-unanimous is the structural norm on Maui, '
            'independent of money). So shared voting is NOT the signal here. What IS sourced and graphable is the '
            '<b style="color:var(--ink)">donor network itself</b>: the same small set of entities funding a majority '
            'of the body simultaneously. That is a structural pattern worth asking about &mdash; not proof any single '
            'vote was bought or "stolen." Follow the graph; draw your own conclusion; verify with the source links.</div>'
            '<h2>The network</h2><div class="gr">%s'
            '<div class="legend"><span><i class="dot" style="background:#e3ad33"></i>council member</span>'
            '<span><i class="dot" style="background:#5fc0d8"></i>donor/vendor (size = # members funded)</span>'
            '<span>line width = $ given</span></div></div>'
            '<h2>Where the bloc holds land</h2><div class="gr">%s'
            '<p style="color:var(--fn);font-size:12px;margin:10px 0 0">Real parcels (TMK) matched to the top bloc '
            'entities via Hawaiʻi Statewide GIS ParcelsZoning &mdash; a name match, not proof of a specific '
            'transaction; verify each parcel independently.</p></div>'
            '<h2>The bloc, ranked</h2>'
            '<table><thead><tr><th>Donor / vendor entity</th><th>Members funded</th><th>Total $</th><th>County vendor tie</th></tr></thead>'
            '<tbody>%s</tbody></table>'
            '<div class="foot">Sourced: Hawaiʻi Campaign Spending Commission (donations) &middot; HANDS Notice-of-'
            'Award (contracts) &middot; Hawaiʻi Statewide GIS ParcelsZoning (parcel locations) &middot; Maui County '
            'CivicClerk (vote record, 34 joint bills reviewed). Loaded into a graph database for multi-hop query '
            '(internal analysis tool, not publicly hosted). Framed as a sourced pattern, never a verdict.</div>'
            '</div></body></html>'
            % (css, svg_network(bloc), svg_map(centroids, tmk_by_entity), rows))
    out_path = os.path.join(MAUIOS, "donor_bloc.html")
    with open(out_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(body)
    return out_path


# ---------- 5) machine-readable output (Jimmy 2026-07-10: "use the graphing system to relearn our skills
#    on the local AI") — until now build_network()'s bloc list only ever reached a human via donor_bloc.html
#    prose; graph_vectors.py's gather_docs() (the embedding layer that lets the local Ollama-backed semantic
#    search "learn" the civic corpus) had nothing structured to read for this feature and so never embedded
#    it. This writes the SAME computed bloc (+ the parcel matches already resolved by bloc_locations()) as
#    donor_bloc.json, sitting next to donor_bloc.html — graph_vectors.gather_docs() picks it up from there.
def write_bloc_json(bloc, tmk_by_entity, centroids):
    rows = []
    for b in bloc:
        rows.append({
            "donor": b["donor"], "kind": b["kind"], "n_reps": b["n_reps"],
            "reps": b["reps"], "total": b["total"],
            "vendor": b.get("vendor"), "award_total": b.get("award_total"),
            "tmks": sorted(tmk_by_entity.get(b["donor"], [])),
        })
    payload = {
        "generated": datetime.now(HST).strftime("%Y-%m-%d %H:%M HST"),
        "note": "Donor/vendor entities that fund 2+ of the 9 current Maui Council members simultaneously. "
                "A structural pattern to question, never proof any vote was bought or coordinated — see "
                "donor_bloc.html for the full honest framing. Same computation as the Neo4j load in this "
                "module (load_neo4j); this file exists so downstream tools (e.g. graph_vectors.py's local "
                "semantic-search embedding layer) have a structured artifact to read, not just prose.",
            "sources": ["Hawaii Campaign Spending Commission (donations)", "HANDS Notice-of-Award (contracts)",
                    "Hawaii Statewide GIS ParcelsZoning (parcel locations)",
                    "Maui County CivicClerk (vote record, 34 joint bills reviewed)"],
        "bloc": rows,
    }
    out_path = os.path.join(MAUIOS, "donor_bloc.json")
    tmp = out_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)
    os.replace(tmp, out_path)
    return out_path


def main():
    print("computing the donor-bloc network from sourced data...")
    reps, donors, bloc = build_network()
    print("  %d donor/vendor entities fund 2+ of the 9 current members" % len(bloc))
    for b in bloc[:8]:
        print("   %-38s %d members  $%s  %s" % (b["donor"][:38], b["n_reps"], "{:,.0f}".format(b["total"]), sorted(b["reps"].keys())))

    print("\nresolving real parcel locations for the top bloc entities (Hawaii Statewide GIS)...")
    tmk_by_entity, centroids = bloc_locations(bloc)
    print("  %d entities matched to %d parcels" % (len(tmk_by_entity), len(centroids)))

    print("\nloading into Neo4j (additive, own labels)...")
    load_neo4j(reps, bloc, tmk_by_entity, centroids)

    print("\nmulti-hop Cypher query result (the graph answering what flat JSON can't):")
    for row in cypher_bloc_query()[:8]:
        print("   %-38s reps=%-2d $%-10s %s" % (str(row[0])[:38], row[1], "{:,.0f}".format(row[3] or 0), row[2]))

    print("\nrendering the graphic console page...")
    out = render_page(reps, bloc, tmk_by_entity, centroids)
    print("wrote", out)

    print("\nwriting the structured artifact (so the local vector layer can learn it too)...")
    jout = write_bloc_json(bloc, tmk_by_entity, centroids)
    print("wrote", jout, "— run graph_vectors.py --build to embed it")


if __name__ == "__main__":
    main()
