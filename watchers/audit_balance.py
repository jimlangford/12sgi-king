#!/usr/bin/env python3
# audit_balance.py - Kilo Aupuni "BALANCE THE EQUATION" scorecard.
#   Reads every money/votes/contracts/federal lens and reports COVERAGE + OPEN ITEMS,
#   then a single "balanced" verdict. This is the completion target for the recurring
#   audit: keep ingesting tenant minutes + contracts + federal + filling the
#   prosecutorial inputs UNTIL coverage is complete and every flagged money x votes
#   pair has been examined (pono restoration). Focus tenants: Maui (001) + State (000).
#
# The "equation": money IN (donations + county contracts + federal awards) reconciled
# against VOTES / decisions. Imbalances (hewa) are the open items; the audit is
# "balanced" when coverage is complete and each imbalance has been examined/explained.
#
# Integrity: counts + coverage only here (public-safe). The prosecutorial *content*
# stays private (case_files.html, king-local). Stdlib only. Windowless.
import json, os, sys, time
from datetime import datetime, timedelta, timezone

HOME    = os.path.expanduser("~")
PROJECT = os.path.join(HOME, "Documents", "Claude", "Projects", "Video System elementLOTUS")
M       = os.path.join(PROJECT, "reports", "mauios")
JSON_F  = os.path.join(M, "audit_balance.json")
HTML_F  = os.path.join(M, "audit_balance.html")
DISPATCH= os.path.join(PROJECT, ".dispatch_log.jsonl")
HST     = timezone(timedelta(hours=-10))

def now_hst(): return datetime.now(HST)
def esc(s): return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def dispatch(tag, msg):
    try:
        with open(DISPATCH, "a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": int(time.time()),
                "iso": now_hst().strftime("%Y-%m-%d %H:%M:%S"),
                "source": "kilo-aupuni", "event": f"{tag}: {msg}"}, ensure_ascii=False) + "\n")
    except Exception: pass

def load(name):
    p = os.path.join(M, name)
    try:
        with open(p, encoding="utf-8") as f: return json.load(f)
    except Exception: return None

def n_of(x):
    """Count a field that might be an int, a list, or a dict."""
    if x is None: return 0
    if isinstance(x, (int, float)): return int(x)
    if isinstance(x, (list, dict)): return len(x)
    return 0

def pct(a, b): return round(100.0 * a / b, 1) if b else None

def main():
    os.makedirs(M, exist_ok=True)
    hands = load("hands_maui_awards.json") or {}
    swide = load("hands_statewide_awards.json") or {}   # full learn-all retainer
    join  = load("vendor_donor_join.json") or {}
    parity= load("parity_check.json") or {}
    state = load("statewide_money.json") or {}
    lobby = load("lobby_money_watch.json") or {}
    testi = load("testimony_record.json") or {}
    fed   = load("federal_money_maui.json") or {}
    case_files = os.path.join(M, "case_files.html")

    # ---- COVERAGE (how much have we ingested) ----
    minutes_scanned = n_of(testi.get("minutes_scanned"))
    minutes_avail   = n_of(testi.get("minutes_available"))
    contracts_maui  = n_of(hands.get("maui_awards"))
    contracts_total = n_of(swide.get("statewide_total")) or n_of(hands.get("statewide_total"))
    contracts_learned = n_of(swide.get("learned_total"))           # full set retained
    contracts_state = n_of((swide.get("by_tenant_counts") or {}).get("state_hawaii"))
    fed_counts      = fed.get("counts") or {}
    coverage = {
        "tenant_minutes": {"scanned": minutes_scanned, "available": minutes_avail,
                           "pct": pct(minutes_scanned, minutes_avail)},
        "all_contracts_learned": {"learned": contracts_learned, "statewide_total": contracts_total,
                                  "pct": pct(contracts_learned, contracts_total)},
        "county_contracts": {"maui": contracts_maui, "state_of_hawaii": contracts_state,
                             "statewide_total": contracts_total},
        "federal_dollars": {"hawaii_awards": n_of(fed_counts.get("hawaii")),
                            "maui_awards": n_of(fed_counts.get("maui")),
                            "hawaii_total_$": (fed.get("totals") or {}).get("hawaii"),
                            "maui_total_$": (fed.get("totals") or {}).get("maui")},
        "campaign_money_$": state.get("grand_total"),
    }

    # ---- OPEN ITEMS (the imbalances still to examine) ----
    hewa = n_of(parity.get("hewa"))
    vd_matches = n_of(join.get("matches") if join.get("matches") is not None else join.get("matched"))
    lobby_donate = n_of(lobby.get("lobby_and_donate"))
    open_items = {
        "money_x_votes_hewa": hewa,             # broken/unexplained money<->vote pairs
        "vendor_donor_matches_to_verify": vd_matches,
        "lobby_and_donate_flags": lobby_donate,
    }
    open_total = hewa + vd_matches + lobby_donate

    # ---- WHAT'S STILL MISSING (drives the next cycle) ----
    todo = []
    if not hands: todo.append("ingest county contracts (hands_awards.py)")
    if contracts_total and contracts_learned < contracts_total:
        todo.append(f"learn remaining contracts ({contracts_total - contracts_learned} of {contracts_total} left) - hands_statewide.py")
    if not fed: todo.append("ingest federal dollars (federal_money.py)")
    if not join: todo.append("run vendor_donor_join (money x votes)")
    if not parity: todo.append("run parity_check (money x votes reconciliation)")
    if not os.path.exists(case_files): todo.append("build prosecutorial case files (prosecutor.py)")
    if minutes_avail and minutes_scanned < minutes_avail:
        todo.append(f"ingest remaining tenant minutes ({minutes_avail - minutes_scanned} left)")

    # ---- BALANCED? (the completion target) ----
    have_all_lenses = bool(hands and join and parity and fed and os.path.exists(case_files))
    minutes_complete = (minutes_avail > 0 and minutes_scanned >= minutes_avail) or minutes_avail == 0
    contracts_complete = (contracts_total > 0 and contracts_learned >= contracts_total)  # ALL learned
    examined = (open_total == 0)   # every imbalance resolved/explained
    balanced = bool(have_all_lenses and minutes_complete and contracts_complete and examined)

    payload = {
        "generated": now_hst().strftime("%Y-%m-%d %H:%M:%S HST"),
        "tenants": ["001 Maui", "000 State of Hawaii"],
        "focus": "Maui + State of Hawaii, county + federal dollars (elections audit)",
        "coverage": coverage, "open_items": open_items, "open_total": open_total,
        "prosecutorial_case_files": os.path.exists(case_files),
        "todo_next_cycle": todo,
        "balanced": balanced,
        "verdict": ("BALANCED - coverage complete and every flagged pair examined"
                    if balanced else
                    f"OPEN - {open_total} flagged pair(s) to examine; {len(todo)} ingest step(s) pending"),
    }
    with open(JSON_F + ".tmp", "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)
    os.replace(JSON_F + ".tmp", JSON_F)
    _html(payload)
    dispatch("FINDING" if not balanced else "SHIPPED",
             f"audit_balance: {payload['verdict']} | minutes {minutes_scanned}/{minutes_avail}, "
             f"contracts maui {contracts_maui}/{contracts_total}, federal Maui ${coverage['federal_dollars'].get('maui_total_$') or 0:,.0f}, "
             f"open {open_total}")
    print(payload["verdict"])
    print(json.dumps(payload["coverage"], indent=1, default=str))
    return 0

def _html(p):
    c = p["coverage"]; o = p["open_items"]
    def row(k, v): return f"<tr><td>{esc(k)}</td><td class=n>{esc(v)}</td></tr>"
    cov = "".join([
        row("Tenant minutes scanned", f"{c['tenant_minutes']['scanned']} / {c['tenant_minutes']['available']} ({c['tenant_minutes']['pct']}%)"),
        row("ALL contracts learned", f"{c['all_contracts_learned']['learned']} / {c['all_contracts_learned']['statewide_total']} ({c['all_contracts_learned']['pct']}%)"),
        row("Contracts (Maui / State of Hawaii)", f"{c['county_contracts']['maui']} / {c['county_contracts']['state_of_hawaii']}"),
        row("Federal awards (Hawaii / Maui)", f"{c['federal_dollars']['hawaii_awards']} / {c['federal_dollars']['maui_awards']}"),
        row("Federal $ to Maui", f"${(c['federal_dollars']['maui_total_$'] or 0):,.0f}"),
        row("Federal $ to State of Hawaii", f"${(c['federal_dollars']['hawaii_total_$'] or 0):,.0f}"),
        row("Campaign money tracked", f"${(c['campaign_money_$'] or 0):,.0f}" if c['campaign_money_$'] else "pending"),
    ])
    opn = "".join([row(k.replace("_", " "), v) for k, v in o.items()])
    todo = "".join(f"<li>{esc(t)}</li>" for t in p["todo_next_cycle"]) or "<li>none - all ingest steps current</li>"
    badge = "#1a8a3a" if p["balanced"] else "#c2410c"
    html = f"""<!doctype html><meta charset=utf-8>
<title>Audit Balance - Maui & State of Hawaii | Kilo Aupuni</title>
<style>body{{font-family:system-ui,Segoe UI,sans-serif;max-width:900px;margin:2rem auto;padding:0 1rem;color:#1a1a1a}}
h1{{font-size:1.5rem}} .sub{{color:#555}} table{{border-collapse:collapse;width:100%;margin:1rem 0}}
th,td{{border-bottom:1px solid #e3e3e3;padding:.45rem .6rem;text-align:left}} .n{{text-align:right;font-variant-numeric:tabular-nums}}
.verdict{{background:{badge};color:#fff;border-radius:10px;padding:.7rem 1.1rem;font-weight:600;margin:1rem 0}}
h2{{font-size:1.05rem;margin-top:1.4rem}} .note{{background:#fff8e6;border-left:4px solid #e0b400;padding:.6rem 1rem;font-size:.9rem}}</style>
<h1>Balance the Equation - Maui &amp; State of Hawai&#699;i</h1>
<div class=sub>In plain words: this tracks how much of the public record we have pulled in
(council minutes, county contracts, federal dollars, campaign money) and how many money&#8596;votes
questions are still open. The audit keeps running until coverage is complete and every flagged
pair has been examined. Generated {esc(p['generated'])}.</div>
<div class=verdict>{esc(p['verdict'])}</div>
<h2>Coverage</h2><table><tbody>{cov}</tbody></table>
<h2>Open items (money &#8596; votes to examine)</h2><table><tbody>{opn}</tbody></table>
<div class=note>Prosecutorial case files present: {p['prosecutorial_case_files']} (private; content is owner-only and never published). Every flagged pair is a QUESTION for oversight - "name match, verify identity" - never an accusation.</div>
<h2>Next cycle will</h2><ul>{todo}</ul>"""
    with open(HTML_F + ".tmp", "w", encoding="utf-8") as f:
        f.write(html)
    os.replace(HTML_F + ".tmp", HTML_F)

if __name__ == "__main__":
    sys.exit(main())
