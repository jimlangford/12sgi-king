# -*- coding: utf-8 -*-
"""
parity_check.py - the Kumulipo Corruption Mechanic, made real.

"The math is the ledger": in the Kumulipo every birth must ANSWER its pair. Civic
parity is the same - a contract (output) must answer the PUBLIC (its input), not a
private donor. When an award answers a donation routed through the deciding
official, the pair no longer answers: that is HEWA, and it is detectable.

This reads the real Kilo Aupuni money x votes flags (reports/mauios/
vendor_donor_join.json) and measures each broken pair as a LEVERAGE imbalance:
    leverage = award_total / contribution_total
A tiny input shadowing a huge output = the pair that does not answer. Every line
is a QUESTION against public records (HI Campaign Spending Commission + HANDS
contract awards), never an accusation. Output feeds the Overseer Joker (N53,
Ka Luna Kiaʻi), who voices each cited pair back toward Pono.

  python tools/kilo-aupuni/parity_check.py
"""
import os, json, time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC  = os.path.join(ROOT, "reports", "mauios", "vendor_donor_join.json")
OUT  = os.path.join(ROOT, "reports", "mauios", "parity_check.json")
HTML = os.path.join(ROOT, "reports", "mauios", "parity_check.html")

def esc(s):
    return (str(s or "")).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def build_html(r):
    h = r["hewa"]
    kp = (f'<div class="kp"><div class="kv" style="color:#e06a4a">{h["n_broken_pairs"]}</div>'
          f'<div class="kl">pairs that no longer answer</div></div>'
          f'<div class="kp"><div class="kv" style="color:#e06a4a">${h["total_award_in_broken_pairs"]:,.0f}</div>'
          f'<div class="kl">county awards shadowed</div></div>'
          f'<div class="kp"><div class="kv" style="color:#d9b24c">${h["total_contrib_in_broken_pairs"]:,.0f}</div>'
          f'<div class="kl">in donations to deciders</div></div>'
          f'<div class="kp"><div class="kv" style="color:#e06a4a">{h["aggregate_leverage"]:,.0f}x</div>'
          f'<div class="kl">aggregate leverage</div></div>')
    rows = ""
    for p in h["pairs"]:
        lv = f'{p["leverage"]:,.0f}x' if p["leverage"] else "n/a"
        rows += (f'<div class="row"><span class="a">{lv}</span><span class="c"><b>{esc(p["vendor"])}</b> — '
                 f'${p["award_total"]:,.0f} in awards / ${p["contrib_total"]:,.0f} to '
                 f'{esc(", ".join(p["officials"]))}. <span style="color:#9a957f">{esc(p["question"])}</span></span></div>')
    offs = ""
    for o, v in r["by_official"].items():
        offs += (f'<div class="row"><span class="a">${v["award_shadowed"]:,.0f}</span>'
                 f'<span class="c">{esc(v["label"])} — received ${v["contrib_received"]:,.0f} from '
                 f'{v["n_vendors"]} contracted vendor(s)</span></div>')
    ov = r["overseer"]
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>Pairs That No Longer Answer - Kumulipo Parity - 12 Stones</title>
<style>
 body{{margin:0;background:#0c100e;color:#e8e4d8;font-family:Georgia,'Iowan Old Style',serif;line-height:1.55}}
 .wrap{{max-width:960px;margin:0 auto;padding:34px 24px calc(env(safe-area-inset-bottom,0px) + 80px)}}
 .eyebrow{{font-family:Consolas,monospace;font-size:11px;letter-spacing:1.2px;color:#d9b24c;text-transform:uppercase}}
 h1{{font-size:27px;font-weight:600;margin:8px 0 2px}}
 .lead{{font-size:13.5px;color:#bdb8a4;max-width:82ch}}
 .disc{{font-size:12px;color:#9a957f;font-style:italic;border-left:2px solid rgba(217,178,76,.4);padding:6px 12px;margin:14px 0}}
 .dash{{border:1px solid rgba(217,178,76,.25);border-radius:14px;padding:18px 20px;margin:18px 0 26px;background:rgba(217,178,76,.03)}}
 .sec{{font-family:Consolas,monospace;font-size:11px;letter-spacing:1.5px;text-transform:uppercase;color:#d9b24c;border-bottom:1px solid rgba(217,178,76,.2);padding-bottom:6px;margin:22px 0 11px}}
 .dash .sec:first-child{{margin-top:0}}
 .note{{font-size:12.5px;color:#bdb8a4;margin:0 0 12px;line-height:1.6}}
 .kps{{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-bottom:6px}}
 @media (max-width:620px){{.kps{{grid-template-columns:repeat(2,1fr)}}}}
 .kp{{background:rgba(255,255,255,.03);border:1px solid rgba(255,255,255,.08);border-radius:10px;padding:11px 13px}}
 .kv{{font-family:Consolas,monospace;font-size:20px;font-weight:700}} .kl{{font-size:10.5px;color:#9a957f;margin-top:2px}}
 .row{{display:flex;gap:12px;align-items:baseline;border-bottom:1px solid rgba(255,255,255,.06);padding:7px 0}}
 .row .a{{font-family:Consolas,monospace;font-size:12.5px;color:#e06a4a;white-space:nowrap;min-width:78px;text-align:right}}
 .row .c{{font-size:12.5px;color:#bdb8a4}}
 .oracle{{border:1px solid rgba(217,178,76,.35);border-radius:12px;padding:15px 18px;margin:16px 0;background:rgba(217,178,76,.05)}}
 .oracle .t{{font-size:16px;font-weight:600;color:#f0cf7a}} .oracle .b{{font-size:13px;color:#bdb8a4;margin-top:6px}}
 a{{color:#d9b24c}}
 footer{{margin-top:40px;border-top:1px solid rgba(255,255,255,.1);padding-top:12px;font-family:Consolas,monospace;font-size:10.5px;color:#9a957f}}
</style></head><body><div class="wrap">
<div class="eyebrow">12 Stones Global · Kilo Aupuni · Kumulipo parity</div>
<h1>The Pairs That No Longer Answer</h1>
<p class="lead">In the Kumulipo every birth answers its pair. Civic parity is the same law: a county
contract (the output) must answer the <b>public</b> (its input) — not a private donor. When an award is
shadowed by a donation routed through the official who decides it, the pair no longer answers. That is the
imbalance this page measures: <b>leverage = award ÷ contribution</b>.</p>
<div class="disc">All figures are public record (Hawaiʻi Campaign Spending Commission × HANDS contract awards).
Contributions and contracts are lawful. Every line is a <b>question for verification</b> — a correlation in
the record, never an allegation against any person.</div>
<div class="dash"><h2 class="sec">The imbalance — what the ledger shows</h2><div class="kps">{kp}</div>
<h2 class="sec">Pairs that no longer answer — sorted by leverage</h2>
<p class="note">A tiny input shadowing a huge output is the pair that does not answer. The question, each time:
does the award answer the public, or the donation?</p>{rows}
<h2 class="sec">By decider — awards shadowed via their donors</h2>{offs}</div>
<div class="oracle"><div class="t">N53 · Ka Luna Kiaʻi — the Overseer</div>
<div class="b">{esc(ov["charge"])} <br><br><i>{esc(r["pono_restoration"])}</i></div></div>
<footer>generated {r["generated"]} HST · parity-check · Kumulipo corruption mechanic · source: CSC × HANDS · govOS · aloha in action</footer>
</div></body></html>"""

def main():
    d = json.load(open(SRC, encoding="utf-8"))
    matches = d.get("matched") or d.get("matches") or []
    pairs = []
    for m in matches:
        award = float(m.get("award_total") or 0)
        contrib = float(m.get("contrib_total") or 0)
        lev = round(award / contrib, 1) if contrib > 0 else None
        offs = m.get("officials") or []
        pairs.append({
            "vendor": m.get("vendor"),
            "award_total": award, "award_count": m.get("award_count"),
            "contrib_total": contrib, "leverage": lev,
            "officials": offs,
            "hits": m.get("hits", []),
            # the pair, stated as a question (public records; correlation, not proof)
            "question": (f"Does {m.get('vendor')}'s ${award:,.0f} in county awards "
                         f"answer the public, or the ${contrib:,.0f} given to "
                         f"{', '.join(offs) or 'deciding officials'} who decide them? "
                         f"(public records - a correlation to verify, not a finding)"),
            "status": "PAIR_DOES_NOT_ANSWER",
        })
    pairs.sort(key=lambda p: (p["leverage"] or 0), reverse=True)

    # per-official imbalance (award $ shadowed via their donors)
    by_off = {}
    for m in matches:
        award = float(m.get("award_total") or 0)
        for h in m.get("hits", []):
            o = h.get("official"); lab = h.get("official_label", o)
            r = by_off.setdefault(o, {"label": lab, "award_shadowed": 0.0,
                                      "contrib_received": 0.0, "vendors": set()})
            r["contrib_received"] += float(h.get("amount") or 0)
            r["vendors"].add(m.get("vendor"))
        # attribute the award once per official named on the match
        for o in (m.get("officials") or []):
            by_off.setdefault(o, {"label": o, "award_shadowed": 0.0,
                                  "contrib_received": 0.0, "vendors": set()})["award_shadowed"] += award
    for o in by_off:
        by_off[o]["vendors"] = sorted(by_off[o]["vendors"])
        by_off[o]["n_vendors"] = len(by_off[o]["vendors"])

    total_award = sum(p["award_total"] for p in pairs)
    total_contrib = sum(p["contrib_total"] for p in pairs)
    report = {
        "generated": time.strftime("%Y-%m-%d %H:%M:%S"),
        "source": "reports/mauios/vendor_donor_join.json (CSC donors x HANDS awards, public records)",
        "method": "Kumulipo parity: a pair that does not answer = output (award) shadowed by private input (donation). leverage = award/contrib. Correlations as QUESTIONS, never accusations; names a broken pair, not a guilty person.",
        "hewa": {
            "n_broken_pairs": len(pairs),
            "vendors_scanned": d.get("maui_vendors_scanned"),
            "total_award_in_broken_pairs": round(total_award, 2),
            "total_contrib_in_broken_pairs": round(total_contrib, 2),
            "aggregate_leverage": round(total_award / total_contrib, 1) if total_contrib else None,
            "pairs": pairs,
        },
        "by_official": dict(sorted(by_off.items(), key=lambda kv: -kv[1]["award_shadowed"])),
        "overseer": {
            "node": 53, "name": "Ka Luna Kiaʻi (the Overseer Joker)",
            "broken_pairs": len(pairs),
            "charge": (f"{len(pairs)} pairs no longer answer (${total_award:,.0f} in awards shadowed by "
                       f"${total_contrib:,.0f} in donations). The Overseer voices each cited pair - "
                       "naming the award and the donation together - calling it back toward Pono."),
        },
        "pono_restoration": "Each award answers the public record, voiced as its pair. The remedy is disclosure sung, not accusation.",
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    open(OUT, "w", encoding="utf-8", newline="\n").write(json.dumps(report, ensure_ascii=False, indent=1))
    open(HTML, "w", encoding="utf-8", newline="\n").write(build_html(report))

    print("=== PARITY CHECK — pairs that no longer answer (public records, as questions) ===")
    print(f"broken pairs: {len(pairs)} | award shadowed ${total_award:,.0f} | by ${total_contrib:,.0f} | aggregate leverage {report['hewa']['aggregate_leverage']:,}x")
    print("\ntop by leverage (tiny donation, large award):")
    for p in pairs[:8]:
        lv = f"{p['leverage']:,}x" if p["leverage"] else "n/a"
        print(f"  {lv:>10}  {p['vendor'][:34]:34s}  ${p['award_total']:>12,.0f} / ${p['contrib_total']:>7,.0f}  -> {', '.join(p['officials'])}")
    print(f"\nOverseer (N53): {report['overseer']['broken_pairs']} pairs to voice.")
    print(f"wrote {os.path.relpath(OUT, ROOT)}")

if __name__ == "__main__":
    main()
