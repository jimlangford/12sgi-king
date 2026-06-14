#!/usr/bin/env python3
# accountability_watch.py - Kilo Aupuni: the Accountability Record.
# Renders accountability_inputs.json (public record: rankings + FEDERAL convictions
# + the 2022 Standards-of-Conduct reforms + the lawful path) into a sourced,
# disclaimered HTML page. Facts + sources only. Named individuals = court outcomes,
# never allegations. Stdlib only. No popups.
import json, os, time
from datetime import datetime, timezone, timedelta

HOME    = os.path.expanduser("~")
PROJECT = os.path.join(HOME, "Documents", "Claude", "Projects", "Video System elementLOTUS")
HERE    = os.path.dirname(os.path.abspath(__file__))
INP     = os.path.join(HERE, "accountability_inputs.json")
MAUIOS  = os.path.join(PROJECT, "reports", "mauios")
OUT     = os.path.join(MAUIOS, "accountability_record.html")
DISPATCH= os.path.join(PROJECT, ".dispatch_log.jsonl")
HST     = timezone(timedelta(hours=-10))


def esc(s):
    return str(s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def src(o):
    if o.get("url"):
        return f'<a class="src" href="{esc(o["url"])}" target="_blank" rel="noopener">{esc(o.get("source","source"))} &#8599;</a>'
    return f'<span class="src">{esc(o.get("source",""))}</span>'


def dispatch(tag, msg):
    try:
        with open(DISPATCH, "a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": int(time.time()),
                                "iso": datetime.now(HST).strftime("%Y-%m-%d %H:%M:%S"),
                                "source": "kilo-aupuni", "event": f"{tag}: {msg}"}, ensure_ascii=False) + "\n")
    except Exception:
        pass


def main():
    d = json.load(open(INP, encoding="utf-8"))
    g = datetime.now(HST).strftime("%Y-%m-%d %H:%M HST")

    rankings = "".join(
        f'<div class="row"><div class="claim">{esc(r["claim"])}</div><div class="meta">{src(r)}</div></div>'
        for r in d.get("rankings", []))

    def conv(c):
        return (f'<div class="conv"><div class="chd"><span class="who">{esc(c["who"])}</span>'
                f'<span class="lvl">{esc(c.get("level",""))}</span></div>'
                f'<div class="role">{esc(c.get("role",""))}</div>'
                f'<div class="what">{esc(c.get("what",""))}</div>'
                f'<div class="outcome">&#9878; {esc(c.get("outcome",""))}</div>'
                f'<div class="meta">{src(c)}</div></div>')
    convictions = "".join(conv(c) for c in d.get("convictions", []))

    def invc(c):
        facts = "".join(f'<div class="what">&bull; {esc(x.get("f",""))} {src(x)}</div>' for x in c.get("facts", []))
        resp = ""
        if c.get("response"):
            ro = {"source": c.get("response_source", ""), "url": c.get("response_url", "")}
            resp = f'<div class="resp"><b>Her response:</b> {esc(c["response"])} {src(ro)}</div>'
        return (f'<div class="inv"><div class="chd"><span class="who">{esc(c["who"])}</span>'
                f'<span class="lvlw">UNDER INVESTIGATION</span></div>'
                f'<div class="role">{esc(c.get("role",""))}</div>'
                f'<div class="banner">&#9888; {esc(c.get("banner",""))}</div>'
                f'{facts}{resp}</div>')
    investigations = "".join(invc(c) for c in d.get("investigations", []))

    def reform(r):
        st = esc(r.get("status", ""))
        cls = "done" if st.upper().startswith("ENACTED") else ("rep" if "RECOMMEND" in st.upper() or "PROPOS" in st.upper() else "rep")
        return (f'<div class="row"><div class="claim">{esc(r["item"])} '
                f'<span class="badge {cls}">{st}</span></div><div class="meta">{src(r)}</div></div>')
    reforms = "".join(reform(r) for r in d.get("reforms", []))

    watch = "".join(f"<li>{esc(w)}</li>" for w in d.get("why_we_watch", []))
    active = d.get("still_active", {})
    active_html = (f'<div class="active">&#128308; {esc(active.get("note",""))} {src(active)}</div>'
                   if active else "")

    html = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Accountability Record - Hawai'i &amp; Maui County - 12 Stones</title>
<style>
 body{{margin:0;background:#0c100e;color:#e8e4d8;font-family:Georgia,serif;line-height:1.55}}
 .wrap{{max-width:980px;margin:0 auto;padding:34px 22px 70px}}
 .eyebrow{{font-family:Consolas,monospace;font-size:11px;letter-spacing:1.3px;color:#d9b24c;text-transform:uppercase}}
 h1{{font-size:27px;margin:8px 0 4px}} h2{{font-size:18px;margin:30px 0 6px;color:#e8e4d8}}
 .lead{{font-size:14px;color:#bdb8a4;max-width:82ch}}
 .disc{{font-size:12px;color:#9a957f;font-style:italic;border-left:2px solid rgba(224,106,74,.55);padding:9px 13px;margin:16px 0;background:rgba(224,106,74,.05)}}
 .row{{border-bottom:1px solid rgba(255,255,255,.07);padding:9px 0}}
 .claim{{font-size:13.5px;color:#e3dfd2}} .meta{{margin-top:3px}}
 .src{{font-family:Consolas,monospace;font-size:10.5px;color:#d9b24c;text-decoration:none}} .src:hover{{text-decoration:underline}}
 .conv{{border:1px solid rgba(224,106,74,.28);border-radius:11px;padding:13px 15px;margin:11px 0;background:rgba(224,106,74,.045)}}
 .chd{{display:flex;align-items:baseline;justify-content:space-between;gap:10px}}
 .who{{font-size:16px;font-weight:700;color:#f0cf7a}} .lvl{{font-family:Consolas,monospace;font-size:10px;letter-spacing:1px;text-transform:uppercase;color:#e06a4a}}
 .role{{font-size:12px;color:#9a957f;margin:2px 0 7px}} .what{{font-size:13px;color:#cfc9ba}}
 .outcome{{font-size:12.5px;color:#e8e4d8;margin-top:7px;font-weight:600}}
 .badge{{font-family:Consolas,monospace;font-size:9.5px;letter-spacing:.6px;padding:2px 7px;border-radius:9px;white-space:nowrap}}
 .badge.done{{background:rgba(86,192,138,.16);color:#56c08a}} .badge.rep{{background:rgba(217,178,76,.15);color:#d9b24c}}
 .active{{font-size:12.5px;color:#e3dfd2;border:1px solid rgba(224,106,74,.3);border-radius:10px;padding:10px 13px;margin:14px 0;background:rgba(224,106,74,.06)}}
 .inv{{border:1px solid rgba(217,178,76,.4);border-radius:11px;padding:13px 15px;margin:11px 0;background:rgba(217,178,76,.05)}}
 .lvlw{{font-family:Consolas,monospace;font-size:10px;letter-spacing:1px;color:#d9b24c}}
 .banner{{font-size:11.5px;color:#d9b24c;font-weight:600;margin:6px 0 9px}}
 .resp{{font-size:12.5px;color:#cfc9ba;margin-top:8px;border-top:1px dashed rgba(255,255,255,.13);padding-top:7px}}
 ul{{font-size:13px;color:#bdb8a4}} li{{margin:5px 0}}
 footer{{margin-top:38px;border-top:1px solid rgba(255,255,255,.1);padding-top:13px;font-family:Consolas,monospace;font-size:10.5px;color:#9a957f}}
</style></head><body><div class="wrap">
<div class="eyebrow">12 Stones Global &middot; Kilo Aupuni &middot; accountability record</div>
<h1>Accountability Record &mdash; Hawai&#699;i &amp; Maui County</h1>
<p class="lead">What the public record shows: independent corruption rankings, federal convictions of officials,
the State&#8217;s own reform commission, and the lawful tools that already exist. Every line links to its source.</p>
<div class="disc">{esc(d.get("updated_note",""))}</div>

<h2>What the studies say</h2>
{rankings}

<h2>The record &mdash; federal convictions (court outcomes)</h2>
{convictions}
{active_html}

<h2>Active investigations &mdash; not charged or convicted</h2>
<div class="disc" style="border-left-color:rgba(217,178,76,.7)">Presumption of innocence. The people below are the subject of an open investigation or official inquiry per public sources and official proceedings (e.g., a Campaign Spending Commission case, an Attorney General target letter). They have <b>not been charged or convicted</b>. Their own responses are included. These are documented facts about a process &mdash; not findings of guilt.</div>
{investigations}

<h2>The State&#8217;s own response &mdash; recommended vs. enacted</h2>
{reforms}

<h2>Why Kilo Aupuni watches what it watches</h2>
<ul>{watch}</ul>

<footer>generated {g} &middot; Accountability Record &middot; sources: U.S. DOJ &middot; Hawai&#699;i courts &middot; Standards of Conduct Commission &middot; Civil Beat / Star-Advertiser / HPR &middot; academic integrity studies &middot; all public record</footer>
</div></body></html>"""
    os.makedirs(MAUIOS, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(html)
    nconv = len(d.get("convictions", []))
    dispatch("SHIPPED", f"accountability_record: {nconv} federal convictions + {len(d.get('reforms',[]))} reform items, all sourced -> reports/mauios/accountability_record.html")
    print(f"built accountability_record.html: {nconv} convictions, {len(d.get('rankings',[]))} rankings, {len(d.get('reforms',[]))} reforms")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
