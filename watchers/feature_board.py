#!/usr/bin/env python3
"""feature_board.py — the PUBLIC "Build Our Government Software" board (Jimmy 2026-06-18).

Renders the free/public tier of feature_requests.py: residents (after a FREE Stripe Identity signup) submit
how they want the software to work and publicly VOTE; the board is AI-sorted by DEPARTMENT + AGENDA priority
from the real government side. Also explains the PAID/PRIVATE tier (county/gov build their ops software
privately). Honest + gated: it reads PUBLIC-SAFE signup links from config/beta.json (no secret key ever here —
the leak gate enforces it); where a link isn't wired the action shows a dignified "opening soon" but the board
still renders. Vote/submit POST to the deployed gate (verify_api_base) when present. Private requests NEVER appear.

Writes:  reports/mauios/feature_board.html  (-> build_site EXTRA_PAGES, public + Naga)
         reports/mauios/feature_board.json  (-> site/data/, the board data the page renders)
Stdlib only.
"""
import os, sys, json
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import feature_requests as FR
PROJ = os.path.dirname(os.path.dirname(HERE))
M = os.path.join(PROJ, "reports", "mauios")
CFG = os.path.join(PROJ, "config", "beta.json")


def esc(s):
    return str(s if s is not None else "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _cfg():
    try: c = json.load(open(CFG, encoding="utf-8"))
    except Exception: c = {}
    def ok(v): return bool(v) and not str(v).startswith("PASTE_")
    return {"verify_url": c.get("stripe_identity_url") if ok(c.get("stripe_identity_url")) else "",
            "api_base": (c.get("verify_api_base") or "").rstrip("/") if ok(c.get("verify_api_base")) else ""}


def _tier_ladder_html():
    """Render the CANONICAL tier ladder from config/plans.json (Jimmy 2026-06-18: keep studio names + live
    Stripe). Council Pro carries its live payment link so visitors can buy now."""
    try:
        plans = json.load(open(os.path.join(PROJ, "config", "plans.json"), encoding="utf-8")).get("plans", [])
    except Exception:
        return ""
    cards = []
    for p in plans:
        if not p.get("public", True):
            continue
        cents = p.get("price_month", p.get("price_each", 0)) or 0
        if p.get("id") == "free":
            price = "Free"
        elif p.get("billing") == "one_time":
            price = "$%d" % (cents / 100)
        else:
            price = "$%d/mo" % (cents / 100)
        delivers = "".join("<li>%s</li>" % esc(d) for d in (p.get("features") or [])[:4])
        link = p.get("payment_link_month") or p.get("payment_link") or ""
        nm = esc(p.get("name", p.get("id")))
        if link:
            nm = '<a href="%s" style="color:inherit;text-decoration:none">%s · buy &rarr;</a>' % (esc(link), nm)
        cards.append('<div class=tier><div class=th>%s</div><div class=price>%s</div>'
                     '<ul class=tl>%s</ul></div>' % (nm, price, delivers))
    return '<div class=tiers>%s</div>' % "".join(cards)


def _author_label(a):
    """Never expose a raw id. 'verified:...' -> 'Verified resident'; 'county:...' -> the county user (private only)."""
    a = str(a or "")
    if a.startswith("county:"): return "County user"
    return "Verified resident"


def build(tenant="hi-maui"):
    b = FR.board(tenant)
    json.dump(b, open(os.path.join(M, "feature_board.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    cfg = _cfg()
    # the free-signup-to-participate CTA (gated: real link or honest "opening soon")
    if cfg["verify_url"]:
        signup = ('<a class="btn" href="%s">Free signup to vote &amp; request &rarr;</a>'
                  '<div class=fine>Free Stripe Identity check (no charge) — so every request has a real person behind it.</div>'
                  % esc(cfg["verify_url"]))
    else:
        signup = ('<div class=warn><b>Public voting opens soon.</b> A free identity signup (no charge) is being '
                  'wired so each vote is one real person. The board below is live; voting switches on when it is.</div>')
    # render the AI-sorted board
    secs = []
    for g in b["departments"]:
        pri = ' <span class=pill>agenda priority</span>' if g["priority"] else ''
        items = "".join(
            '<li><div class=rt>%s</div><div class=rd>%s</div>'
            '<div class=rm>%s &middot; %d vote%s</div></li>'
            % (esc(r["title"]), esc(r["desc"][:200]), _author_label(r["author"]),
               r["votes"], "" if r["votes"] == 1 else "s")
            for r in g["requests"])
        secs.append('<div class=dept><div class=dh><b>%s</b>%s</div><ul class=reqs>%s</ul></div>'
                    % (esc(g["label"]), pri, items or "<li class=fine>No requests yet — be the first.</li>"))
    board_html = "".join(secs) or "<div class=fine>No public requests yet.</div>"
    body = (
        '<div style="max-width:880px;margin:0 auto;padding:1.2rem 1rem">'
        '<h1 style="color:#0e4a84">Build Our Government Software</h1>'
        '<p class=lead>Tell us how you want the county\'s software to work — then vote on what others ask for. '
        'Requests are sorted by the real council departments and by what\'s coming up on the agenda, so the best '
        'ideas rise on merit, not volume. This is a request board; it informs the work, it doesn\'t bind the county.</p>'
        + signup +
        '<h2 style="color:#0e4a84;margin-top:1.2rem">Membership</h2>'
        '<p class=fine>Free to request + vote. Members get private reports + AI advice on all public data; '
        'Builders stand up their own county tenant. Read access on public records — confirm every figure at its source.</p>'
        + _tier_ladder_html() +
        '<h2 style="color:#0e4a84;margin-top:1.3rem">The board</h2>'
        '<style>.dept{border:1px solid #d6e2f0;border-radius:10px;padding:.6rem .9rem;margin:.6rem 0;background:#081420}'
        '.dh{font-weight:700;color:#0e4a84;margin-bottom:.3rem}.reqs{list-style:none;padding:0;margin:0}'
        '.reqs li{border-top:1px solid #eef3f9;padding:.45rem 0}.rt{font-weight:600}.rd{font-size:.9rem;color:#33414f}'
        '.rm{font-size:.78rem;color:#5a6b7b;margin-top:.15rem}.pill{background:#eaf2fb;color:#0e4a84;border-radius:20px;'
        'padding:.05rem .5rem;font-size:.7rem;margin-left:.4rem}.tiers{display:flex;gap:.8rem;flex-wrap:wrap;margin:.8rem 0}'
        '.tier{flex:1;min-width:230px;border:1px solid #d6e2f0;border-radius:10px;padding:.6rem .8rem;background:#fbfdff}'
        '.th{font-weight:700;color:#0e4a84}.price{font-weight:700;color:#1f6f54;margin:.2rem 0}'
        '.tl{font-size:.8rem;color:#33414f;margin:.3rem 0 0;padding-left:1.1rem}.tl li{margin:.1rem 0}'
        '.btn{display:inline-block;background:#0e4a84;color:#fff;font-weight:700;'
        'border-radius:9px;padding:.6rem 1.1rem;text-decoration:none;margin:.5rem 0}'
        '.warn{background:#fff6e0;border-left:3px solid #d9a400;padding:.6rem .9rem;border-radius:8px;margin:.6rem 0}'
        '.fine{color:#5a6b7b;font-size:.84rem;margin-top:.3rem}</style>'
        + board_html +
        '<div class=fine style="margin-top:1rem">Sourced + honest: departments and priorities come from the real '
        'Maui County Council committee structure. Requests are public; paid build requests stay private. '
        'A request is a question to the county, never a claim about it.</div>'
        # ROSCA / FTC auto-renewal + cancellation disclosure at the offer (required before charging)
        '<div class=fine style="margin-top:.8rem;border-top:1px solid #eef3f9;padding-top:.6rem">'
        '<b>Billing:</b> identity verification is free. Paid plans are subscriptions billed in advance that '
        '<b>auto-renew monthly or annually until you cancel</b>; the price + cycle shown at checkout are what you pay. '
        '<b>Cancel anytime</b> in your account or by email — you won\'t be billed again, and access continues through '
        'the period you paid for. Nothing is charged until you complete Stripe checkout. '
        '<a href="refunds.html">Billing &amp; Refunds</a> &middot; <a href="terms.html">Terms</a> &middot; '
        '<a href="privacy.html">Privacy</a></div></div>')
    html = ("<!doctype html><html lang=en><head><meta charset=utf-8>"
            "<meta name=viewport content=\"width=device-width,initial-scale=1\">"
            "<title>Build Our Government Software — govOS</title></head><body>" + body + "</body></html>")
    open(os.path.join(M, "feature_board.html"), "w", encoding="utf-8", newline="\n").write(html)
    return b


def main():
    import argparse
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--tenant", default="hi-maui")
    a = ap.parse_args()
    b = build(a.tenant)
    print("feature_board: %d public requests across %d departments -> feature_board.html + .json"
          % (b["total"], len(b["departments"])))
    return 0


if __name__ == "__main__":
    if sys.platform == "win32":
        import io; sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(main())
