# -*- coding: utf-8 -*-
"""
news_record_page.py  —  kilo-aupuni  (the Herald)

Renders config/news_records.json into the public "News vs Record" page:
  reports/mauios/news_record.html

Each record is a BALANCING PAIR laid side by side:
    THEIR ANGLE (outlet framing, labeled — never fact)
        <=>
    OUR TRUTH (primary-sourced facts + 12 Stones position, labeled analysis — never law)

Our truth LEADS (left-to-read priority / sourced first); the outlet's angle is
tracked alongside as labeled secondary. The Kumulipo checksum (pair_answers:
ANSWERS=Pono / PARTIAL / HEWA) is shown so the public can SEE whether the
frame and the record agree.

Sourced-only - framing != fact - position != law - leak-gate clean.

Run:  python -X utf8 tools/kilo-aupuni/news_record_page.py
"""
import os, json, html, datetime

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA = os.path.join(ROOT, "config", "news_records.json")
OUT  = os.path.join(ROOT, "reports", "mauios", "news_record.html")

VDATE = datetime.date.today().isoformat()  # cache-bust token


def esc(s):
    return html.escape(str(s if s is not None else ""))


def pair_badge(pa):
    """pair_answers -> (css-class, short-label)."""
    head = (pa or "").strip().upper()
    if head.startswith("ANSWERS"):
        return "ans", "ANSWERS &middot; Pono"
    if head.startswith("PARTIAL"):
        return "part", "PARTIAL"
    if head.startswith("HEWA"):
        return "hewa", "HEWA &middot; tilts"
    return "part", esc(head.split(" ")[0] or "PAIR")


def li(items):
    return "".join("<li>%s</li>" % esc(x) for x in (items or []))


def src_links(sources):
    out = []
    for s in (sources or []):
        if isinstance(s, dict):
            label = s.get("label") or s.get("title") or s.get("url") or "source"
            url = s.get("url")
        else:
            label, url = s, None
        if url and str(url).startswith("http"):
            out.append('<a class="src" href="%s" target="_blank" rel="noopener">%s &#8599;</a>'
                       % (esc(url), esc(label)))
        else:
            out.append('<span class="src nolink">%s</span>' % esc(label))
    return "".join('<div class="srcrow">%s</div>' % x for x in out)


def cross_links(links):
    """cross_links: list of {label, href, note} -> internal cross-reference chips."""
    if not links:
        return ""
    chips = []
    for l in links:
        label = l.get("label", "link")
        href = l.get("href", "#")
        note = l.get("note", "")
        chips.append(
            '<a class="xlink" href="%s">%s</a>%s'
            % (esc(href), esc(label),
               (' <span class="xnote">%s</span>' % esc(note)) if note else "")
        )
    return ('<div class="xwrap"><div class="xhd">Cross-linked to the record</div>%s</div>'
            % "".join('<div class="xrow">%s</div>' % c for c in chips))


def testimony_block(t):
    if not t:
        return ""
    def names(lst, key):
        return ", ".join(esc(x.get("name", "")) for x in (lst or []))
    sup = names(t.get("support"), "for")
    opp = names(t.get("oppose"), "against")
    rows = ""
    if sup:
        rows += '<div class="tst"><span class="tlab sup">testified for</span> %s</div>' % sup
    if opp:
        rows += '<div class="tst"><span class="tlab opp">testified against</span> %s</div>' % opp
    return rows


def render_record(r):
    ta = r.get("their_angle", {})
    ot = r.get("our_truth", {})
    cls, blab = pair_badge(r.get("pair_answers", ""))

    angle_emph = li(ta.get("emphasis"))
    angle_omit = li(ta.get("underweighted_or_omitted"))

    facts = li(ot.get("primary_facts"))
    pos = ot.get("our_position", "")
    kl = ot.get("kumulipo_link", "")

    article_url = ta.get("url", "")
    article_link = (
        '<a class="src" href="%s" target="_blank" rel="noopener">read the article &#8599;</a>'
        % esc(article_url) if str(article_url).startswith("http") else ""
    )

    return """
<section class="rec">
  <div class="rhd">
    <div>
      <div class="issue">{issue}</div>
      <div class="rmeta">{tenant} &middot; event {event} &middot; {status}</div>
    </div>
    <span class="pa {cls}">{blab}</span>
  </div>

  <div class="cols">
    <div class="col truth">
      <div class=" chl">OUR TRUTH <span class="lbl">primary-sourced fact + 12 Stones position (analysis, not law)</span></div>
      <ul class="facts">{facts}</ul>
      {testimony}
      <div class="position"><span class="ptag">12 Stones position</span> {pos}</div>
      <div class="srcs"><div class="srchd">Primary sources</div>{psrc}</div>
    </div>

    <div class="col angle">
      <div class="chl angleh">THEIR ANGLE <span class="lbl">outlet framing — how the news told it, not fact</span></div>
      <div class="outlet">{outlet}{author}</div>
      <div class="hl">&ldquo;{headline}&rdquo;</div>
      <div class="frame">{framing}</div>
      <div class="mini"><div class="minihd">emphasized</div><ul>{emph}</ul></div>
      <div class="mini"><div class="minihd">underweighted / omitted</div><ul class="omit">{omit}</ul></div>
      <div class="srcrow">{article}</div>
    </div>
  </div>

  <div class="check"><span class="cklab">Kumulipo checksum</span> {pair}</div>
  {kumi}
  {xlinks}
</section>""".format(
        issue=esc(r.get("issue", "")),
        tenant=esc(r.get("tenant", "")),
        event=esc(r.get("event_date", "")),
        status=esc(r.get("status", "")),
        cls=cls, blab=blab,
        facts=facts,
        testimony=testimony_block(ot.get("testimony")),
        pos=esc(pos),
        psrc=src_links(ot.get("primary_sources")),
        outlet=esc(ta.get("outlet", "")),
        author=(' &middot; %s' % esc(ta.get("author"))) if ta.get("author") else "",
        headline=esc(ta.get("headline", "")),
        framing=esc(ta.get("framing", "")),
        emph=angle_emph, omit=angle_omit,
        article=article_link,
        pair=esc(r.get("pair_answers", "")),
        kumi=('<div class="kumi"><span class="klab">Kumulipo</span> %s</div>' % esc(kl)) if kl else "",
        xlinks=cross_links(r.get("cross_links")),
    )


def build():
    with open(DATA, "r", encoding="utf-8") as f:
        data = json.load(f)
    records = data.get("records", [])
    # newest event first
    records = sorted(records, key=lambda r: r.get("event_date", ""), reverse=True)
    body = "\n".join(render_record(r) for r in records)

    page = """<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>News vs Record - 12 Stones Global - Kilo Aupuni</title>
<style>
 body{{margin:0;background:#0c100e;color:#e8e4d8;font-family:Georgia,serif;line-height:1.55}}
 .wrap{{max-width:1040px;margin:0 auto;padding:34px 22px 70px}}
 .eyebrow{{font-family:Consolas,monospace;font-size:11px;letter-spacing:1.3px;color:#d9b24c;text-transform:uppercase}}
 h1{{font-size:27px;margin:8px 0 4px}}
 .lead{{font-size:14px;color:#bdb8a4;max-width:84ch}}
 .disc{{font-size:12px;color:#9a957f;font-style:italic;border-left:2px solid rgba(224,106,74,.55);padding:9px 13px;margin:16px 0;background:rgba(224,106,74,.05)}}
 .rec{{border:1px solid rgba(255,255,255,.09);border-radius:13px;padding:17px 18px;margin:22px 0;background:rgba(255,255,255,.012)}}
 .rhd{{display:flex;align-items:flex-start;justify-content:space-between;gap:12px;border-bottom:1px solid rgba(255,255,255,.08);padding-bottom:10px;margin-bottom:13px}}
 .issue{{font-size:19px;font-weight:700;color:#f0cf7a}}
 .rmeta{{font-family:Consolas,monospace;font-size:10.5px;color:#9a957f;margin-top:3px;text-transform:uppercase;letter-spacing:.6px}}
 .pa{{font-family:Consolas,monospace;font-size:10px;letter-spacing:.7px;padding:4px 10px;border-radius:11px;white-space:nowrap;font-weight:700}}
 .pa.ans{{background:rgba(86,192,138,.16);color:#6fd29b}}
 .pa.part{{background:rgba(217,178,76,.15);color:#e3c161}}
 .pa.hewa{{background:rgba(224,106,74,.16);color:#ef8a6c}}
 .cols{{display:grid;grid-template-columns:1.15fr 1fr;gap:16px}}
 @media(max-width:760px){{.cols{{grid-template-columns:1fr}}}}
 .col{{border-radius:10px;padding:13px 14px}}
 .truth{{background:rgba(86,192,138,.05);border:1px solid rgba(86,192,138,.22)}}
 .angle{{background:rgba(224,106,74,.045);border:1px solid rgba(224,106,74,.20)}}
 .chl{{font-family:Consolas,monospace;font-size:12px;font-weight:700;letter-spacing:.8px;color:#6fd29b;margin-bottom:9px}}
 .angleh{{color:#ef8a6c}}
 .lbl{{display:block;font-weight:400;font-size:9.5px;letter-spacing:.3px;color:#9a957f;text-transform:none;margin-top:2px;font-style:italic}}
 ul.facts{{margin:6px 0;padding-left:18px;font-size:13px;color:#dcd7c8}} ul.facts li{{margin:6px 0}}
 .tst{{font-size:12px;color:#cfc9ba;margin:4px 0}}
 .tlab{{font-family:Consolas,monospace;font-size:9.5px;letter-spacing:.5px;padding:1px 6px;border-radius:7px;margin-right:6px}}
 .tlab.sup{{background:rgba(86,192,138,.15);color:#6fd29b}} .tlab.opp{{background:rgba(224,106,74,.15);color:#ef8a6c}}
 .position{{font-size:12.5px;color:#e3dfd2;margin-top:11px;border-top:1px dashed rgba(255,255,255,.13);padding-top:9px}}
 .ptag{{font-family:Consolas,monospace;font-size:9.5px;letter-spacing:.6px;color:#d9b24c;display:block;margin-bottom:3px;text-transform:uppercase}}
 .srcs{{margin-top:10px}} .srchd,.minihd{{font-family:Consolas,monospace;font-size:9.5px;letter-spacing:.6px;color:#9a957f;text-transform:uppercase;margin:7px 0 4px}}
 .srcrow{{margin:3px 0}}
 .src{{font-family:Consolas,monospace;font-size:10.5px;color:#d9b24c;text-decoration:none}} .src:hover{{text-decoration:underline}}
 .src.nolink{{color:#a59e86}}
 .outlet{{font-size:12.5px;color:#cfc9ba;font-weight:600}}
 .hl{{font-size:13.5px;color:#e8e4d8;font-style:italic;margin:6px 0}}
 .frame{{font-size:12px;color:#bdb8a4;margin:5px 0 9px}}
 .mini ul{{margin:3px 0 8px;padding-left:17px;font-size:11.5px;color:#bdb8a4}} .mini li{{margin:3px 0}}
 .mini ul.omit li{{color:#cfa18f}}
 .check{{margin-top:13px;font-size:12px;color:#dcd7c8;background:rgba(217,178,76,.06);border:1px solid rgba(217,178,76,.18);border-radius:9px;padding:9px 12px}}
 .cklab{{font-family:Consolas,monospace;font-size:9.5px;letter-spacing:.7px;color:#d9b24c;text-transform:uppercase;margin-right:7px}}
 .kumi{{margin-top:9px;font-size:12px;color:#b9c8bd;font-style:italic;border-left:2px solid rgba(86,192,138,.4);padding:6px 12px;background:rgba(86,192,138,.04)}}
 .klab{{font-family:Consolas,monospace;font-style:normal;font-size:9.5px;letter-spacing:.7px;color:#6fd29b;text-transform:uppercase;margin-right:7px}}
 .xwrap{{margin-top:11px;border-top:1px solid rgba(255,255,255,.08);padding-top:9px}}
 .xhd{{font-family:Consolas,monospace;font-size:9.5px;letter-spacing:.6px;color:#9a957f;text-transform:uppercase;margin-bottom:5px}}
 .xrow{{margin:3px 0}}
 .xlink{{font-family:Consolas,monospace;font-size:11px;color:#8fc7e8;text-decoration:none;border-bottom:1px dotted rgba(143,199,232,.4)}}
 .xlink:hover{{color:#bfe0f5}}
 .xnote{{font-size:11px;color:#9a957f;font-family:Georgia,serif;font-style:italic}}
 footer{{margin-top:38px;border-top:1px solid rgba(255,255,255,.1);padding-top:13px;font-family:Consolas,monospace;font-size:10.5px;color:#9a957f}}
</style></head><body><div class="wrap">
<div class="eyebrow">12 Stones Global &middot; Kilo Aupuni &middot; news vs record</div>
<h1>News &amp; the Record &mdash; the balancing pair</h1>
<p class="lead">Every story sits as a pair: <b>our truth</b> &mdash; the primary record, sourced and cited &mdash;
laid beside <b>their angle</b>, the outlet's framing, captured and <i>labeled</i>. The sourced facts lead;
the framing is tracked alongside, never presented as fact. The Kumulipo checksum tells you whether the
two agree (<b>Pono</b>) or the frame tilts past the record (<b>Hewa</b>) &mdash; and you can see it, because both sit side by side.</p>
<div class="disc">Outlet framing is labeled &ldquo;how the news told it &mdash; not fact.&rdquo; The 12 Stones read is labeled
&ldquo;position / analysis &mdash; not law.&rdquo; Sourced-only. Lead with the primary source.</div>
{body}
<footer>12 Stones Global &middot; kilo-aupuni &middot; generated {vdate} &middot; sourced-only &middot; framing &#8800; fact &middot; position &#8800; law</footer>
</div></body></html>""".format(body=body, vdate=VDATE)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(page)
    return OUT, len(records)


if __name__ == "__main__":
    path, n = build()
    print("BUILT", path, "(%d records)" % n)
