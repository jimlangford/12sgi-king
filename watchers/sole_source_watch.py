#!/usr/bin/env python3
# sole_source_watch.py - Kilo Aupuni: the SOLE-SOURCE / procurement-exemption watch.
# Motivated by the Stewart Stant conviction (Maui Dept. of Environmental Management
# director, 10 yrs federal prison for steering >$19M in SOLE-SOURCE contracts to
# Milton Choy). Sole-source = awarded WITHOUT competition (HRS 103D-102 exemption) -
# the exact mechanism. This watch ingests what Maui actually POSTS, and honestly
# names the gap where the dangerous awards hide + the lawful unlock. Stdlib only.
import json, os, re, ssl, time, urllib.request
from datetime import datetime, timezone, timedelta

HOME    = os.path.expanduser("~")
PROJECT = os.path.join(HOME, "Documents", "Claude", "Projects", "Video System elementLOTUS")
MAUIOS  = os.path.join(PROJECT, "reports", "mauios")
OUT     = os.path.join(MAUIOS, "sole_source_watch.html")
DISPATCH= os.path.join(PROJECT, ".dispatch_log.jsonl")
HST     = timezone(timedelta(hours=-10))
SRC     = "https://mauicounty.us/procurements/"
UA      = {"User-Agent": "12sgi-kilo-aupuni/1.0 (public procurement transparency)"}
KW      = re.compile(r"sole[\s-]?source|exemption|103D|3-122|3-120|contract|procure|award", re.I)


def now_hst(): return datetime.now(HST)
def esc(s): return str(s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def dispatch(tag, msg):
    try:
        with open(DISPATCH, "a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": int(time.time()), "iso": now_hst().strftime("%Y-%m-%d %H:%M:%S"),
                                "source": "kilo-aupuni", "event": f"{tag}: {msg}"}, ensure_ascii=False) + "\n")
    except Exception:
        pass


def fetch_posted():
    """Pull the sole-source / exemption notices Maui actually posts (HTML + PDF links)."""
    try:
        req = urllib.request.Request(SRC, headers=UA)
        with urllib.request.urlopen(req, timeout=60, context=ssl.create_default_context()) as r:
            html = r.read().decode("utf-8", "replace")
    except Exception as e:
        return [], str(e)
    rows, seen = [], set()
    for m in re.finditer(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', html, re.I | re.S):
        href, text = m.group(1), re.sub(r"<[^>]+>", "", m.group(2)).strip()
        if not text or len(text) < 6:
            continue
        if KW.search(text) or KW.search(href):
            if href.startswith("/"):
                href = "https://mauicounty.us" + href
            key = (text[:90], href)
            if key in seen:
                continue
            seen.add(key)
            rows.append({"text": text[:160], "href": href})
    return rows[:60], None


def main():
    posted, err = fetch_posted()
    rows = "".join(
        f'<div class="m"><a class="c" href="{esc(p["href"])}" target="_blank" rel="noopener">{esc(p["text"])}</a></div>'
        for p in posted)
    g = now_hst().strftime("%Y-%m-%d %H:%M HST")
    err_html = f'<div class="disc">Live fetch note: {esc(err)}</div>' if err else ""
    html = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Sole-Source Watch - Maui County - 12 Stones</title>
<style>
 body{{margin:0;background:#0c100e;color:#e8e4d8;font-family:Georgia,serif;line-height:1.55}}
 .wrap{{max-width:960px;margin:0 auto;padding:34px 22px 70px}}
 .eyebrow{{font-family:Consolas,monospace;font-size:11px;letter-spacing:1.3px;color:#d9b24c;text-transform:uppercase}}
 h1{{font-size:26px;margin:8px 0 4px}} h2{{font-size:18px;margin:28px 0 6px}}
 .lead{{font-size:14px;color:#bdb8a4;max-width:82ch}}
 .disc{{font-size:12px;color:#9a957f;font-style:italic;border-left:2px solid rgba(217,178,76,.5);padding:9px 13px;margin:14px 0;background:rgba(217,178,76,.05)}}
 .warn{{font-size:13px;color:#e3dfd2;border:1px solid rgba(224,106,74,.35);border-radius:11px;padding:13px 15px;margin:14px 0;background:rgba(224,106,74,.06)}}
 .m{{border-bottom:1px solid rgba(255,255,255,.07);padding:8px 0}}
 a.c{{font-size:13px;color:#e3dfd2;text-decoration:none}} a.c:hover{{color:#d9b24c}}
 a.src{{color:#d9b24c;font-family:Consolas,monospace;font-size:11px}}
 ul{{font-size:13px;color:#bdb8a4}} li{{margin:5px 0}}
 footer{{margin-top:36px;border-top:1px solid rgba(255,255,255,.1);padding-top:13px;font-family:Consolas,monospace;font-size:10.5px;color:#9a957f}}
</style></head><body><div class="wrap">
<div class="eyebrow">12 Stones Global &middot; Kilo Aupuni &middot; sole-source watch</div>
<h1>Sole-Source &amp; Procurement-Exemption Watch &mdash; Maui County</h1>
<p class="lead">Sole-source means a contract awarded <b>without competition</b> (a HRS 103D-102 exemption).
It is legal when justified &mdash; and it is exactly the mechanism a Maui official used to steal.</p>

<div class="warn">&#9888; <b>Why this watch exists.</b> Stewart Stant, former director of Maui County&#8217;s Dept. of
Environmental Management, was sentenced to <b>10 years in federal prison</b> for taking ~$2M in bribes to steer
<b>more than $19,000,000 in sole-source contracts and purchase orders</b> to Milton Choy&#8217;s H2O Process Systems
(U.S. DOJ). Competition is the safeguard sole-source removes &mdash; so sole-source awards are where the risk concentrates.
<a class="src" href="https://www.justice.gov/usao-hi/pr/former-maui-county-official-sentenced-ten-years-federal-prison-honest-services-wire" target="_blank" rel="noopener">DOJ &#8599;</a></div>

<h2>Posted sole-source / exemption notices</h2>
<div class="disc">Pulled live from the County&#8217;s public procurements page. This is what is voluntarily posted &mdash;
mostly the Council/legislative branch, often without dollar amounts.</div>
{err_html}
{rows or '<div class="m">No posted notices matched on this fetch - see the source page directly.</div>'}
<p style="margin-top:8px"><a class="src" href="{SRC}" target="_blank" rel="noopener">source: mauicounty.us/procurements &#8599;</a></p>

<h2>The gap &mdash; and the lawful way to close it</h2>
<div class="disc">The dangerous awards (the kind in the Stant case) were <b>executive-branch</b> sole-source contracts &mdash;
those are <b>not</b> published in any clean, machine-readable county feed. That opacity is the finding. There is a lawful path to the full record:</div>
<ul>
 <li><b>HANDS</b> &mdash; Hawai&#699;i Awards &amp; Notices Data System (state awards/exemptions): hands.ehawaii.gov</li>
 <li><b>State Procurement Office</b> exemption + sole-source reports (SPO-001 / SPO-007), HAR 3-120 Exhibit A</li>
 <li><b>UIPA request</b> (HRS 92F) for the County&#8217;s full sole-source / 103D-102 exemption log with vendors, amounts, and dates &mdash; public record. Drop the returned data at reports/mauios/sole_source/ and it joins to donor-watch (contract &rarr; donor).</li>
</ul>
<div class="disc">Integrity: a sole-source award is <b>not</b> evidence of wrongdoing. This watch shows <b>where to look</b> &mdash;
facts and the lawful records path, framed as questions, never accusations.</div>
<footer>generated {g} &middot; sole-source watch &middot; sources: mauicounty.us/procurements &middot; U.S. DOJ &middot; HI SPO / HANDS &middot; HRS 103D &middot; public record</footer>
</div></body></html>"""
    os.makedirs(MAUIOS, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(html)
    dispatch("SHIPPED", f"sole_source_watch: {len(posted)} posted notices ingested + executive-branch gap + UIPA unlock + Stant tie -> reports/mauios/sole_source_watch.html")
    print(f"built sole_source_watch.html: {len(posted)} posted notices" + (f" (fetch note: {err})" if err else ""))
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
