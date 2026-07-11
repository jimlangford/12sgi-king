#!/usr/bin/env python3
"""sage_bridge.py — the CLOUD BRIDGE between worlds: the live civic record (govOS cloud) projected
onto the 54-node Sage Game digital twin, so the twin breathes from real data.

Sage is the interactive digital twin tuned to the Kumulipo's paired parity (Pono = the pair answers;
Hewa = a broken pair the Overseer/N53 voices back to balance). This bridge maps each node by its
governance_role onto the live civic state:
  - HEWA   — a real broken pair touches this node's domain (parity_check.json hewa) → the twin reads imbalance.
  - OPPORTUNITY — an UPCOMING agenda item touches this node's domain → a live chance to breathe balance
                  in (testify before the vote; the Voice-the-Pono moment).
  - PONO   — balanced; no live break, no pending decision.

Output is a PUBLIC cloud channel (sage_bridge.json) the studio Sage Game pulls to animate the twin,
plus a public balance-board view (sage_bridge.html). The narrated VIDEO / cut scenes stay studio-side
(per Jimmy) — this bridge carries DATA, not video.

INTEGRITY / SAGE_GROUNDING: nodes are mapped by GOVERNANCE ROLE (functional, real). The sacred wā per
node is the APPROVED node_map value; the wā<->civic-Hewa sacred binding stays "voiced by N53, cultural
review pending" where not attested — never an automated sacred guess. Hewa is real public-record data.
"""
import os, json, re, html
from datetime import datetime, timezone, timedelta
try:
    import moon_calendar          # kaulana mahina: agenda date -> pō night + aloha offering
except Exception:
    moon_calendar = None

HOME    = os.path.expanduser("~")
TOOL_DIR= os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.join(HOME, "Documents", "Claude", "Projects", "Video System elementLOTUS")
MAUIOS  = os.path.join(PROJECT, "reports", "mauios")
CARDS   = os.path.join(PROJECT, "config", "sage_deck_cards.json")
PARITY  = os.path.join(MAUIOS, "parity_check.json")
AGENDA  = os.path.join(TOOL_DIR, "agenda_sources.json")
OUTJ    = os.path.join(MAUIOS, "sage_bridge.json")
OUTH    = os.path.join(MAUIOS, "sage_bridge.html")
HST     = timezone(timedelta(hours=-10))
esc     = lambda s: html.escape(str(s or ""))
def now_hst(): return datetime.now(HST)
def load(p, d):
    try: return json.load(open(p, encoding="utf-8"))
    except Exception: return d

STOP = {"the","of","and","a","for","to","in","lead","officer","council","committee","county","maui",
        "management","services","affairs","resilience","relations","economic","development","general",
        "2025-2027","2025","2027","planning","authority","social"}
def toks(s):
    return {w for w in re.split(r"[^a-z0-9ʻ]+", (s or "").lower()) if w and w not in STOP and len(w) > 2}

def hewa_list(p):
    h = p.get("hewa")
    if isinstance(h, dict): h = list(h.values())
    return h if isinstance(h, list) else []

def _build_moon_grid(ag):
    """Build the 30-pō lunation grid for the current moon month.

    Each cell contains: the pō night data + any upcoming civic meetings that
    fall on a day whose kaulana mahina night lands on that pō index.
    This is what the MoonCal panel and moon_cal.html game page render.
    """
    if not moon_calendar:
        return []
    # pre-compute pō index for each agenda meeting (cached)
    meeting_by_po = {}  # po_index (1..30) -> list of meeting dicts
    for a in ag:
        r = moon_calendar.reading(a["date"])
        if not r:
            continue
        po_n = r["night"]  # 1..30
        meeting_by_po.setdefault(po_n, []).append({
            "tenant": a["tenant"],
            "date": a["date"],
            "body": a["body"],
            "url": a["url"],
            "po": r["po"],
            "phase": r["phase"],
            "offering": r["offering"],
        })
    grid = []
    for i, (nm, anahulu, nature, offering) in enumerate(moon_calendar.PO):
        po_night = i + 1
        # game-turn frame label
        if "Kū" in nm and "Kā" not in nm:
            game_frame = "stand-testify"
        elif nm == "Māhealani":
            game_frame = "full-light"
        elif "ʻOle" in nm:
            game_frame = "listen-hold"
        elif nm in ("Kāne", "Lono", "Akua"):
            game_frame = "sacred"
        else:
            game_frame = "flow"
        grid.append({
            "po_index": po_night,
            "po": nm,
            "anahulu": anahulu,
            "nature": nature,
            "offering": offering,
            "game_frame": game_frame,
            "meetings": meeting_by_po.get(po_night, []),
        })
    return grid


def main():
    cards = (load(CARDS, {}) or {}).get("cards", [])
    # the Sage 13-moon binding per node (Moon N of 13) — the studio-node side of the moon link
    NMOON = {}
    for n in (load(os.path.join(PROJECT, "node_map", "node_map_canonical.json"), {}) or {}).get("nodes", []):
        mb = n.get("moon_binding") or {}
        NMOON[n.get("id")] = mb.get("moon")
    par = load(PARITY, {})
    hewa = hewa_list(par)
    hewa_txt = [(json.dumps(x, ensure_ascii=False).lower(), x) for x in hewa]
    # upcoming agendas (Maui = the rooted twin; include all tenants' items as live signal)
    ag = []
    for s in (load(AGENDA, {}).get("sources", [])):
        for m in (s.get("upcoming") or []):
            ag.append({"tenant": s["tenant_id"], "date": m.get("date",""), "body": m.get("body",""),
                       "title": m.get("title",""), "url": m.get("url",""), "tok": toks(m.get("body","")+" "+m.get("title",""))})
    nodes = []
    for c in cards:
        role = c.get("governance_role",""); realm = c.get("realm",""); dom = toks(role + " " + realm)
        # HEWA: a live broken pair touching this node's domain
        hv = None
        for txt, x in hewa_txt:
            if dom and any(t in txt for t in dom):
                if isinstance(x, dict):
                    hv = x.get("vendor") or x.get("official") or x.get("question") or "broken pair"
                else:
                    hv = re.sub(r'[\["\]{}]', "", txt)[:70]
                break
        # OPPORTUNITY: an upcoming agenda touching this node's domain
        opps = [a for a in ag if dom & a["tok"]][:4]
        balance = "hewa" if hv else ("opportunity" if opps else "pono")
        opp_out = []
        for o in opps:
            mr = moon_calendar.reading(o["date"]) if moon_calendar else None
            opp_out.append({"tenant": o["tenant"], "date": o["date"], "body": o["body"], "url": o["url"],
                            "moon": ({"night": mr["night"], "po": mr["po"], "phase": mr["phase"],
                                      "offering": mr["offering"]} if mr else None)})
        nodes.append({"node": c.get("node"), "name": c.get("realm") or c.get("card_name"),
                      "role": role, "zone": c.get("zone"), "akua": c.get("akua"),
                      "wa": c.get("wa"), "phase": c.get("wa_phase"), "frame": c.get("frame_hex","#9a957f"),
                      "moon13": NMOON.get(c.get("node")),     # Sage 13-moon binding (Moon N of 13)
                      "balance": balance, "hewa_evidence": hv, "opportunities": opp_out})
    summary = {"pono": sum(1 for n in nodes if n["balance"]=="pono"),
               "opportunity": sum(1 for n in nodes if n["balance"]=="opportunity"),
               "hewa": sum(1 for n in nodes if n["balance"]=="hewa")}
    # the sun(Ao)<->moon(Po) OVERLAP for today: one date, two readings of one balance —
    # the civic pō-offering AND the creative sphere "in light" (the creative lane, surfaced with humility).
    today = now_hst().strftime("%Y-%m-%d")
    co = moon_calendar.creative_offering(today) if moon_calendar else None
    today_overlap = ({"date": today, "moon_of_year": co["moon_of_year"], "ao_po": co["ao_po"],
                      "node": co["node"], "node_name": co["node_name"], "akua": co["akua"],
                      "po": co["po"], "po_night": co["po_night"],
                      "civic_offering": co["civic_offering"], "creative_offering": co["creative_offering"]}
                     if co else None)
    bridge = {"generated": now_hst().strftime("%Y-%m-%d %H:%M HST"),
              "what": "Cloud bridge: the live govOS civic record projected onto the 54-node Sage twin (Kumulipo parity).",
              "summary": summary, "overseer": par.get("overseer"), "today": today_overlap, "nodes": nodes,
              "moon_grid": _build_moon_grid(ag)}
    open(OUTJ, "w", encoding="utf-8", newline="\n").write(json.dumps(bridge, ensure_ascii=False, indent=1))
    open(OUTH, "w", encoding="utf-8", newline="\n").write(render(bridge))
    print("sage-bridge: 54 nodes · pono %d / opportunity %d / hewa %d · %d live agenda signals"
          % (summary["pono"], summary["opportunity"], summary["hewa"], len(ag)))
    return 0

def _overlap_panel(t):
    """The sun(Ao)<->moon(Po) overlap for today: civic offering AND creative sphere-in-light, with humility."""
    if not t:
        return ""
    return (
        '<div class="overlap"><div class="ot">🌙 today · the sun↔moon overlap · ' + esc(t["date"]) +
        ' · moon ' + esc(t["moon_of_year"]) + '/13 · ' + esc(t["ao_po"]) + ' key</div>'
        '<div class="oc"><b>Civic (pō ' + esc(t["po_night"]) + ' ' + esc(t["po"]) + '):</b> ' + esc(t["civic_offering"]) +
        '<br><b>Creative (sphere in light):</b> ' + esc(t["creative_offering"]) + '</div>'
        '<div class="ohum">One date, two readings of one balance — the civic ledger and the creative realm drawn from '
        'the same source. The sacred binding of node to night is offered with humility and stays kumu-validation-pending.</div></div>')

def render(b):
    s = b["summary"]
    def tile(n):
        col = {"pono":"#56c08a","opportunity":"#d9b24c","hewa":"#e06a4a"}[n["balance"]]
        glyph = {"pono":"●","opportunity":"◆","hewa":"⚠"}[n["balance"]]
        opp = ""
        if n["opportunities"]:
            o = n["opportunities"][0]
            mo = o.get("moon") or {}
            moonline = (' <div class="moon">🌙 pō ' + esc(mo.get("po","")) + ' — ' + esc(mo.get("offering","")) + '</div>') if mo else ""
            opp = ('<div class="opp">live: ' + esc(o["body"][:40]) + ' · ' + esc(o["date"]) +
                   ' <a href="agenda_explainer.html">act ↗</a></div>' + moonline)
        elif n["balance"] == "hewa":
            opp = '<div class="opp hw">broken pair — ' + esc(str(n["hewa_evidence"])[:46]) + ' · <a href="parity_check.html">N53 ↗</a></div>'
        return ('<div class="nd" style="border-color:' + col + '44">'
                '<div class="nh"><span class="ng" style="color:' + col + '">' + glyph + '</span>'
                '<span class="nn">' + esc(n["name"]) + '</span><span class="nw">wā ' + esc(n["wa"]) + ' · ' + esc(n["phase"]) + (' · moon ' + esc(n["moon13"]) + '/13' if n.get("moon13") else '') + '</span></div>'
                '<div class="nr">' + esc(n["role"]) + ' · ' + esc(n["akua"]) + '</div>' + opp + '</div>')
    tiles = "".join(tile(n) for n in b["nodes"])
    CSS = ("<style> body{margin:0;background:#0c100e;color:#e8e4d8;font-family:Georgia,serif;line-height:1.55}"
     " .wrap{max-width:1100px;margin:0 auto;padding:30px 22px 70px}"
     " .eyebrow{font-family:Consolas,monospace;font-size:11px;letter-spacing:1.4px;color:#d9b24c;text-transform:uppercase}"
     " h1{font-size:27px;font-weight:600;margin:8px 0 4px} .lead{font-size:14px;color:#cfc9b6;max-width:80ch}"
     " .bal{display:flex;gap:10px;flex-wrap:wrap;margin:14px 0;font-family:Consolas,monospace;font-size:12px}"
     " .bp{padding:6px 12px;border-radius:20px;border:1px solid #243029} .bp.p{color:#56c08a} .bp.o{color:#d9b24c} .bp.h{color:#e06a4a}"
     " .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:9px;margin-top:14px}"
     " .nd{border:1px solid #243029;border-radius:11px;padding:10px 12px;background:rgba(255,255,255,.02)}"
     " .nh{display:flex;gap:6px;align-items:baseline;flex-wrap:wrap} .ng{font-size:14px} .nn{font-size:14px;font-weight:600;color:#f0ead8;flex:1}"
     " .nw{font-family:Consolas,monospace;font-size:9.5px;color:#9a957f} .nr{font-size:11.5px;color:#9a957f;margin:2px 0}"
     " .opp{font-size:11.5px;color:#cfc9b6;margin-top:5px} .opp.hw{color:#e9b48a} .opp a{color:#d9b24c}"
     " .moon{font-size:11px;color:#9fd9bf;margin-top:4px;font-style:italic}"
     " a{color:#d9b24c} .aloha{font-size:13px;color:#9fd9bf;border-left:3px solid #2a6b4e;padding:9px 13px;margin:18px 0;line-height:1.6}"
     " .overlap{margin:16px 0;padding:14px 16px;border:1px solid rgba(205,180,240,.3);border-radius:12px;background:rgba(205,180,240,.05)}"
     " .overlap .ot{font-family:Consolas,monospace;font-size:11px;letter-spacing:1.2px;color:#cdb4f0;text-transform:uppercase}"
     " .overlap .oc{font-size:13.5px;color:#e8e4d8;margin-top:6px;line-height:1.6} .overlap .oc b{color:#9fd9bf}"
     " .overlap .ohum{font-size:11px;color:#9a957f;font-style:italic;margin-top:7px}"
     " footer{margin-top:26px;border-top:1px solid #243029;padding-top:12px;font-family:Consolas,monospace;font-size:10.5px;color:#9a957f}</style>")
    return ("<!DOCTYPE html><html lang=\"en\"><head><meta charset=\"UTF-8\"><meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
      "<title>Sage — the living twin | govOS · Kilo Aupuni</title>" + CSS + "</head><body><div class=\"wrap\">"
      "<div class=\"eyebrow\">12 Stones Global · Kilo Aupuni · the cloud bridge · Kumulipo parity</div>"
      "<h1>Sage — the living twin</h1>"
      "<p class=\"lead\">The Sage Game's 54 nodes, breathing from the live civic record. Each node is a strand of the "
      "system's parity: <b>Pono</b> when the pair answers, <b>Hewa</b> when a pair is broken (the Overseer N53 voices it "
      "back), and an <b>opportunity</b> when an upcoming agenda is the live chance to restore balance — testify before the "
      "vote. This is the bridge between worlds: the cloud's record animates the twin.</p>"
      "<div class=\"bal\"><span class=\"bp p\">● Pono " + str(s["pono"]) + "</span>"
      "<span class=\"bp o\">◆ Opportunity " + str(s["opportunity"]) + "</span>"
      "<span class=\"bp h\">⚠ Hewa " + str(s["hewa"]) + "</span></div>"
      + _overlap_panel(b.get("today")) +
      "<div class=\"grid\">" + tiles + "</div>"
      "<div class=\"aloha\">Aloha. The twin does not invent the world — it listens to it. Where the record shows a pair no "
      "longer answering, the node dims to Hewa; where an agenda opens, it glows gold — your chance to breathe the balance back. "
      "Pono is not filed; it is voiced, and it is lived.</div>"
      "<p><a href=\"agenda_explainer.html\">the agenda opportunities</a> · <a href=\"parity_check.html\">the broken pairs (N53)</a> · "
      "<a href=\"jurisdictions.html\">all jurisdictions</a></p>"
      "<footer>generated " + b["generated"] + " · sage-bridge v1 · cloud→twin data channel (sage_bridge.json) · video/cut-scenes stay studio-side · Kilo Aupuni · aloha · pono</footer>"
      "</div></body></html>")

if __name__ == "__main__":
    import sys; sys.exit(main())
