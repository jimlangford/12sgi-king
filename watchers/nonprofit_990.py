#!/usr/bin/env python3
# nonprofit_990.py - Kilo Aupuni Maui NONPROFIT (IRS 990) watcher.
#   Pulls Maui County nonprofits + their latest Form 990 financials from the
#   ProPublica Nonprofit Explorer API v2 (FREE, no key). This is the "who runs
#   the money on the nonprofit side of Maui" AUDIT lens: revenue, expenses,
#   net assets, and top-officer compensation - each linked to the public filing.
#
# Sources (public, no key):
#   search: https://projects.propublica.org/nonprofits/api/v2/search.json?q=<term>&state[id]=HI
#   detail: https://projects.propublica.org/nonprofits/api/v2/organizations/{ein}.json
#           -> filings_with_data[] carries 990 financials + pdf_url per filing.
#
# Integrity (same standard as the rest of Kilo Aupuni): facts + sourced links only.
# A nonprofit's size, spending, or officer pay is a QUESTION for the public to weigh
# ("who is served, who is paid, does the mission match the money?"), NEVER an accusation.
# Officers named on a 990 and the org itself are public record (IRS-published). We do not
# invent a number, a name, or a statute. Where a value is unknown, we say so.
#
# PROVENANCE: every record carries source_type = "sourced" (these come straight from the
# IRS-published 990 filing via ProPublica) and renders a small visible badge. There is no
# transcription here - nothing is derived from audio/video - so "sourced" is correct for all.
#
# PRIVATE by location: writes only into reports/mauios (the civic tree). Never published
# by this tool; publishing stays owner-gated.
#
# Stdlib + urllib ONLY (no pip). Windowless-safe (every print guarded by `if sys.stdout`).
import argparse, json, os, sys, time, unicodedata, urllib.parse, urllib.request
from datetime import datetime, timedelta, timezone

# --- UTF-8 everywhere (okina/kahako safe) ---
try:
    if sys.stdout and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HOME    = os.path.expanduser("~")
PROJECT = os.path.join(HOME, "Documents", "Claude", "Projects", "Video System elementLOTUS")
OUT_DIR = os.path.join(PROJECT, "reports", "mauios")
JSON_F  = os.path.join(OUT_DIR, "nonprofits_maui.json")
HTML_F  = os.path.join(OUT_DIR, "nonprofits_maui.html")
STATE_F = os.path.join(os.path.dirname(os.path.abspath(__file__)), "nonprofit_990_state.json")
DISPATCH= os.path.join(PROJECT, ".dispatch_log.jsonl")

SEARCH_API = "https://projects.propublica.org/nonprofits/api/v2/search.json"
ORG_API    = "https://projects.propublica.org/nonprofits/api/v2/organizations/%s.json"
ORG_PAGE   = "https://projects.propublica.org/nonprofits/organizations/%s"   # human-readable public page
UA         = "kilo-aupuni/1.0 (civic-transparency; Maui govOS; sourced-only)"
HST        = timezone(timedelta(hours=-10))

# Maui County towns (the task list) + unambiguous Maui-County localities, normalized (no okina/accents,
# lowercase) so a filing's mailing city can be matched. ProPublica's `city` is the org's mailing city;
# matching to this set is how we keep the record to MAUI COUNTY and not the whole state.
MAUI_TOWNS_DISPLAY = ["Wailuku", "Kahului", "Lahaina", "Kihei", "Makawao", "Hana",
                      "Paia", "Kula", "Pukalani", "Haiku", "Lanai City", "Kaunakakai"]
# search terms (task: "also try q per town to widen coverage") + the county name itself
SEARCH_TERMS = MAUI_TOWNS_DISPLAY + ["Maui", "Molokai", "Lanai"]
# accepted mailing cities (superset of the search terms - every one sits in Maui County: Maui island,
# Molokaʻi, and Lānaʻi are the three inhabited islands of Maui County)
MAUI_CITIES = {
    "wailuku", "kahului", "lahaina", "kihei", "makawao", "hana", "paia", "kula",
    "pukalani", "haiku", "lanai city", "kaunakakai", "wailea", "kaanapali", "napili",
    "kapalua", "olowalu", "waihee", "waikapu", "spreckelsville", "haiku-pauwela",
    "puunene", "maalaea", "hoolehua", "kualapuu", "maunaloa", "kilohana", "kihei-wailea",
    "lanai", "molokai", "napili-honokowai",
}

# NTEE major-group letter -> plain-language category (IRS classification). First letter of ntee_code.
NTEE_MAJOR = {
    "A": "Arts, Culture & Humanities", "B": "Education", "C": "Environment",
    "D": "Animal-Related", "E": "Health Care", "F": "Mental Health & Crisis",
    "G": "Diseases & Medical Disciplines", "H": "Medical Research", "I": "Crime & Legal",
    "J": "Employment", "K": "Food, Agriculture & Nutrition", "L": "Housing & Shelter",
    "M": "Public Safety & Disaster Relief", "N": "Recreation & Sports", "O": "Youth Development",
    "P": "Human Services", "Q": "International & Foreign Affairs", "R": "Civil Rights & Advocacy",
    "S": "Community Improvement", "T": "Philanthropy & Grantmaking", "U": "Science & Technology",
    "V": "Social Science", "W": "Public & Societal Benefit", "X": "Religion-Related",
    "Y": "Mutual & Membership Benefit", "Z": "Unknown",
}
# IRS 990 form-type codes returned by ProPublica (formtype)
FORM_TYPE = {0: "990", 1: "990-EZ", 2: "990-PF"}


def now_hst(): return datetime.now(HST)

def say(*a):
    if sys.stdout:
        try: print(*a)
        except Exception: pass

def dispatch(tag, msg):
    line = {"ts": int(time.time()), "iso": now_hst().strftime("%Y-%m-%d %H:%M:%S"),
            "source": "kilo-aupuni", "event": f"{tag}: {msg}"}
    try:
        with open(DISPATCH, "a", encoding="utf-8") as f:
            f.write(json.dumps(line, ensure_ascii=False) + "\n")
    except Exception:
        pass

def esc(s):
    return (str(s if s is not None else "")
            .replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))

def norm_city(s):
    if not s: return ""
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(c for c in s if not unicodedata.combining(c))  # strip kahako/accents
    return s.replace("ʻ", "").replace("'", "").replace("`", "").strip().lower()

def _num(v):
    try:
        if v is None or v == "": return None
        return float(v)
    except Exception:
        return None

def get_json(url, timeout=45):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def search_term(term, max_pages, sleep):
    """Page a single search term (state=HI), returning raw org rows (statewide fuzzy match)."""
    rows, page = [], 0            # ProPublica pages are 0-indexed (cur_page starts at 0)
    while page < max_pages:
        qs = urllib.parse.urlencode({"q": term, "state[id]": "HI", "page": page})
        url = SEARCH_API + "?" + qs
        try:
            d = get_json(url)
        except Exception as e:
            dispatch("FINDING", f"nonprofit_990 search '{term}' page {page} failed: {e}")
            break
        got = d.get("organizations", []) or []
        rows.extend(got)
        num_pages = d.get("num_pages", 1) or 1
        if page >= num_pages - 1 or not got:
            break
        page += 1
        time.sleep(sleep)
    return rows


def latest_filing(det):
    """Return the most-recent filing WITH structured financial data, or None."""
    fwd = det.get("filings_with_data", []) or []
    if not fwd:
        return None
    return max(fwd, key=lambda f: (f.get("tax_prd_yr") or 0, f.get("tax_prd") or 0))


def build_record(org_row, det):
    """Merge a search row + the org-detail response into one sourced civic record."""
    ein = org_row.get("ein")
    o = det.get("organization", {}) if det else {}
    ntee = (org_row.get("ntee_code") or o.get("ntee_code") or "").strip()
    category = NTEE_MAJOR.get(ntee[:1].upper(), "Uncategorized") if ntee else "Uncategorized"
    rec = {
        "ein": ein,
        "strein": org_row.get("strein") or o.get("ein"),
        "name": (org_row.get("name") or o.get("name") or "UNKNOWN").strip(),
        "city": (org_row.get("city") or o.get("city") or "").strip(),
        "state": org_row.get("state") or o.get("state") or "HI",
        "ntee_code": ntee, "category": category,
        "subsection": org_row.get("subseccd") or o.get("subsection_code"),
        # financials (latest 990 with data) - null where unknown, never invented
        "fiscal_year": None, "form_type": None,
        "revenue": None, "expenses": None, "net_assets": None,
        "total_assets": None, "total_liabilities": None, "officer_comp": None,
        "has_financials": False,
        # sourced links
        "source_url": ORG_PAGE % ein if ein is not None else None,   # public ProPublica org page
        "filing_pdf_url": None,
        "source_type": "sourced",                                    # IRS-published 990 via ProPublica
        "note": None,
    }
    f = latest_filing(det) if det else None
    if f:
        na = _num(f.get("totnetassetend"))
        if na is None:
            ta, tl = _num(f.get("totassetsend")), _num(f.get("totliabend"))
            if ta is not None:
                na = ta - (tl or 0.0)
        rec.update({
            "fiscal_year": f.get("tax_prd_yr"),
            "form_type": FORM_TYPE.get(f.get("formtype"), str(f.get("formtype"))),
            "revenue": _num(f.get("totrevenue")),
            "expenses": _num(f.get("totfuncexpns")),
            "net_assets": na,
            "total_assets": _num(f.get("totassetsend")),
            "total_liabilities": _num(f.get("totliabend")),
            "officer_comp": _num(f.get("compnsatncurrofcr")),
            "has_financials": True,
            "filing_pdf_url": f.get("pdf_url"),
        })
    else:
        rec["note"] = ("No structured 990 financial extract is published for this org yet; "
                       "the ProPublica page lists any filings on record.")
    return rec


def collect(args):
    """Search every term, filter to Maui-County mailing cities, dedupe by EIN, then fetch
    detail for up to max_detail candidates. Returns (records, stats) with NO silent truncation."""
    candidates, seen = [], set()
    per_term = {}
    for term in SEARCH_TERMS:
        rows = search_term(term, args.pages, args.sleep)
        kept = 0
        for r in rows:
            if norm_city(r.get("city")) not in MAUI_CITIES:
                continue
            ein = r.get("ein")
            if ein is None or ein in seen:
                continue
            seen.add(ein)
            candidates.append(r)
            kept += 1
        per_term[term] = {"scanned": len(rows), "new_maui": kept}
        say(f"  search '{term}': {len(rows)} scanned, {kept} new Maui candidate(s)")
        time.sleep(args.sleep)

    n_candidates = len(candidates)
    to_detail = candidates[:args.max_detail]
    n_skipped = n_candidates - len(to_detail)   # capped, not fetched (reported honestly)

    records, n_with_fin = [], 0
    for i, r in enumerate(to_detail, 1):
        ein = r.get("ein")
        det = None
        try:
            det = get_json(ORG_API % ein)
        except Exception as e:
            dispatch("FINDING", f"nonprofit_990 detail EIN {ein} failed: {e}")
        rec = build_record(r, det)
        if rec["has_financials"]:
            n_with_fin += 1
        records.append(rec)
        if i % 25 == 0:
            say(f"  ... detailed {i}/{len(to_detail)} orgs")
        time.sleep(args.sleep)

    records.sort(key=lambda x: (x.get("revenue") or -1), reverse=True)
    stats = {
        "candidates_found": n_candidates,
        "detailed": len(records),
        "skipped_over_cap": n_skipped,
        "with_financials": n_with_fin,
        "without_financials": len(records) - n_with_fin,
        "per_term": per_term,
    }
    return records, stats


# ----------------------------- rendering -----------------------------

def money(v):
    return "$" + "{:,.0f}".format(v) if isinstance(v, (int, float)) else "—"

def prov_badge(source_type):
    """Small visible provenance badge. sourced = green, transcribed = amber (Jimmy's ask)."""
    if source_type == "transcribed":
        return ('<span class="prov prov-t" title="Derived from a meeting audio/video transcription">'
                'transcribed</span>')
    return ('<span class="prov prov-s" title="From an official IRS-published Form 990 filing '
            '(via ProPublica)">sourced</span>')


def render_html(records, stats, payload):
    g = payload["generated"]
    tot_rev = sum(r["revenue"] for r in records if isinstance(r.get("revenue"), (int, float)))
    tot_exp = sum(r["expenses"] for r in records if isinstance(r.get("expenses"), (int, float)))
    towns = ", ".join(MAUI_TOWNS_DISPLAY)

    rows = []
    for r in records:
        pdf = (f' &middot; <a href="{esc(r["filing_pdf_url"])}" rel="nofollow noopener">990 PDF</a>'
               if r.get("filing_pdf_url") else "")
        fy = r.get("fiscal_year") or "—"
        cat = esc(r.get("category") or "")
        ntee = esc(r.get("ntee_code") or "")
        src = esc(r.get("source_url") or "#")
        rows.append(
            "<tr>"
            f'<td class=nm><a href="{src}" rel="nofollow noopener">{esc(r["name"])}</a>'
            f'<span class=e>EIN {esc(r.get("strein") or r.get("ein"))} {prov_badge(r.get("source_type"))}</span></td>'
            f'<td class=ct>{esc(r.get("city"))}</td>'
            f'<td class=cat>{cat}{(" &middot; " + ntee) if ntee else ""}</td>'
            f'<td class=yr>{esc(fy)}</td>'
            f'<td class=amt>{money(r.get("revenue"))}</td>'
            f'<td class=amt>{money(r.get("expenses"))}</td>'
            f'<td class=amt>{money(r.get("net_assets"))}</td>'
            f'<td class=amt>{money(r.get("officer_comp"))}</td>'
            f'<td class=lk>{esc(r.get("form_type") or "—")}{pdf}</td>'
            "</tr>")
    if not rows:
        rows = ['<tr><td colspan=9 class=ct>No Maui-County nonprofits were captured in this window. '
                'The record fills as filings post.</td></tr>']

    body = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="theme-color" content="#00356b">
<title>Maui nonprofits — the 990 record | govOS</title>
<style>:root{{--bg:#fff;--panel:#e7eef8;--line:#bacde6;--ink:#13243d;--dim:#41536b;--faint:#6d7f97;--accent:#00356b;--accent2:#1259a3;--ok:#1f8a5b;--gold:#b8860b}}
*{{box-sizing:border-box}}body{{font-family:'Segoe UI Variable Text','Segoe UI',system-ui,sans-serif;max-width:1080px;margin:0 auto;padding:18px 16px 44px;color:var(--ink);background:var(--bg);font-size:16px;line-height:1.55}}
a{{color:var(--accent2)}}h1{{font-size:1.5rem;margin:.3rem 0}}h2{{color:var(--accent);font-size:1.05rem;margin:1.2rem 0 .4rem}}
.sub{{color:var(--dim);font-size:.95rem;line-height:1.55}}
.kpis{{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin:1rem 0}}@media(max-width:640px){{.kpis{{grid-template-columns:1fr 1fr}}}}
.kp{{background:var(--panel);border:1px solid var(--line);border-radius:11px;padding:.7rem .85rem}}.kv{{font:700 18px/1.1 'JetBrains Mono',Consolas,monospace;color:var(--accent)}}.kl{{font-size:11px;color:var(--faint);text-transform:uppercase;letter-spacing:.4px;margin-top:4px}}
.note{{background:#fbf6ea;border:1px solid #e6d8a8;border-left:3px solid var(--gold);border-radius:10px;padding:.7rem 1rem;margin:.9rem 0;font-size:.9rem;color:#5a4a16;line-height:1.5}}
.prov{{display:inline-block;font:600 10px/1 'JetBrains Mono',Consolas,monospace;text-transform:uppercase;letter-spacing:.4px;padding:2px 6px;border-radius:99px;margin-left:6px;vertical-align:middle}}
.prov-s{{background:#e2f3ea;color:var(--ok);border:1px solid #a9dcc2}}
.prov-t{{background:#fbf1dd;color:var(--gold);border:1px solid #e6d3a3}}
table{{border-collapse:collapse;width:100%;font-size:.85rem;margin-top:.4rem}}
td,th{{padding:.45rem .5rem;border-bottom:1px solid #e3e9f1;text-align:left;vertical-align:top}}
th{{font-size:.7rem;text-transform:uppercase;letter-spacing:.4px;color:var(--faint);font-weight:700}}
.nm{{max-width:280px;overflow-wrap:anywhere}}.nm .e{{display:block;color:var(--faint);font-size:.72rem;font-family:Consolas,monospace;margin-top:2px}}
.ct{{color:var(--dim);white-space:nowrap}}.cat{{color:var(--faint);font-size:.8rem}}.yr{{font-family:Consolas,monospace;color:var(--dim)}}
.amt{{font-family:Consolas,monospace;color:var(--accent);white-space:nowrap;text-align:right}}
.lk{{font-size:.78rem;white-space:nowrap}}
.tablewrap{{overflow-x:auto;-webkit-overflow-scrolling:touch}}
</style></head><body>
<div class=sub style="letter-spacing:.1em;text-transform:uppercase;color:var(--accent2);font-weight:600">govOS &middot; Maui County &middot; asked in aloha</div>
<h1>Maui nonprofits — the Form 990 record</h1>
<div class=sub>Maui-County tax-exempt organizations and their most recent IRS <b>Form 990</b> — revenue, expenses,
net assets, and top-officer compensation — so anyone can ask the plain questions: who is served, who is paid,
and does the mission match the money? A record to weigh, never a finding. Source:
<a href="https://projects.propublica.org/nonprofits/" rel="nofollow noopener">ProPublica Nonprofit Explorer</a>
(IRS 990 data) &middot; towns: {esc(towns)} &middot; generated {esc(g)}.</div>
<div class=kpis>
 <div class=kp><div class=kv>{stats['detailed']}</div><div class=kl>orgs detailed</div></div>
 <div class=kp><div class=kv>{stats['with_financials']}</div><div class=kl>with 990 financials</div></div>
 <div class=kp><div class=kv>{money(tot_rev)}</div><div class=kl>total revenue (latest 990s)</div></div>
 <div class=kp><div class=kv>{money(tot_exp)}</div><div class=kl>total expenses (latest 990s)</div></div>
</div>
<div class=note>Every figure is the organization's own IRS-published Form 990. A nonprofit's size, spending, or
officer pay is a <b>question for the public to weigh</b> — who is served, who is paid, does the mission match the
money — never an accusation. Each row links back to the public filing so you can verify it yourself. Coverage this
run: {stats['candidates_found']} Maui candidates found, {stats['detailed']} detailed
({stats['skipped_over_cap']} beyond the run cap, not yet fetched — no silent truncation).</div>
<div class=tablewrap><table>
<thead><tr><th>organization</th><th>city</th><th>category</th><th>FY</th><th>revenue</th><th>expenses</th>
<th>net assets</th><th>officer comp</th><th>form</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table></div>
<p class=sub style="margin-top:1rem">Full data in <code>nonprofits_maui.json</code>. This is a records-awareness
tool; lawful action (records requests, reporting, giving, board service) is the endpoint. Officers listed on a 990
are public record; private individuals are not named here.</p>
</body></html>"""

    # unify with the shared civic chrome if the module is present (never fatal if absent)
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import civic_shell
        body = civic_shell.wrap_html(body)
    except Exception:
        pass

    tmp = HTML_F + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(body)
    os.replace(tmp, HTML_F)


# ----------------------------- main -----------------------------

def main(argv=None):
    ap = argparse.ArgumentParser(description="Maui nonprofit (IRS 990) watcher — ProPublica Nonprofit Explorer.")
    ap.add_argument("--pages", type=int, default=int(os.environ.get("KA_NP_PAGES", "4")),
                    help="max search pages per term (25 orgs/page). Default 4.")
    ap.add_argument("--max-detail", type=int, default=int(os.environ.get("KA_NP_MAXDETAIL", "160")),
                    help="max org-detail fetches (keeps runtime to a few min). Default 160.")
    ap.add_argument("--sleep", type=float, default=float(os.environ.get("KA_NP_SLEEP", "0.34")),
                    help="seconds between API calls (be polite). Default 0.34.")
    args = ap.parse_args(argv)

    os.makedirs(OUT_DIR, exist_ok=True)
    say(f"nonprofit_990: Maui County · pages/term={args.pages} · max_detail={args.max_detail}")
    records, stats = collect(args)

    payload = {
        "generated": now_hst().strftime("%Y-%m-%d %H:%M:%S HST"),
        "source": "ProPublica Nonprofit Explorer API v2 (IRS Form 990 data)",
        "source_url": "https://projects.propublica.org/nonprofits/",
        "target": {"county": "Maui County", "state": "HI",
                   "towns": MAUI_TOWNS_DISPLAY, "search_terms": SEARCH_TERMS},
        "source_type_default": "sourced",
        "coverage": stats,
        "count": len(records),
        "records": records,
        "note": ("Maui-County tax-exempt orgs + latest 990 financials. Facts + sourced links only; "
                 "a nonprofit's finances are a question for the public to weigh, never an accusation. "
                 "source_type='sourced' for all rows (IRS-published 990 via ProPublica)."),
    }
    tmp = JSON_F + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)
    os.replace(tmp, JSON_F)

    render_html(records, stats, payload)

    with open(STATE_F, "w", encoding="utf-8") as f:
        json.dump({"last_run": payload["generated"], "count": len(records),
                   "with_financials": stats["with_financials"],
                   "candidates_found": stats["candidates_found"],
                   "skipped_over_cap": stats["skipped_over_cap"]}, f, indent=1)

    dispatch("SHIPPED", f"nonprofit_990: Maui {len(records)} orgs "
                        f"({stats['with_financials']} with 990 financials, "
                        f"{stats['candidates_found']} candidates, {stats['skipped_over_cap']} over cap) -> "
                        f"nonprofits_maui.html/.json")
    say(f"nonprofit_990: {len(records)} Maui orgs detailed "
        f"({stats['with_financials']} with financials) of {stats['candidates_found']} candidates; "
        f"{stats['skipped_over_cap']} beyond cap")
    say(f"  -> {JSON_F}")
    say(f"  -> {HTML_F}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
