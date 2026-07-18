#!/usr/bin/env python3
"""list_controls.py — ONE reusable search + sort toolbar for civic LIST pages (Jimmy 2026-06-19:
"add sort to navigation … add search feature to classes like this too … have the richness sort too").

Proven first on nay_narratives (council_votes_maui.html). Any generator that renders a vertical list of
"card" elements can add a live SEARCH box + a SORT select (newest / oldest / most-detail) in two lines —
no page-specific JS. Pure client-side (no data leaves the page), namespaced `lc-`, works after build_site's
recolor/nav/font passes (it only touches its own toolbar + the cards' display order).

USAGE in a generator:
    from list_controls import controls_css, toolbar, sortjs, card_attrs
    # 1) give each card a stable wrapper carrying its sort keys:
    #    '<div class="dv"%s>…</div>' % card_attrs(date=e["date"], rich=score)
    # 2) put the cards inside ONE container id and bracket them with the toolbar + script:
    #    html = ... + controls_css() + toolbar(noun="split votes")
    #              + '<div id="lc-list">' + cards + '</div>' + sortjs()
The container id is always `lc-list`; the toolbar/script find it by that id. Date is an ISO 'YYYY-MM-DD'
string (lexical sort == chronological); rich is any integer (higher = more detail). Stdlib only.
"""
import html as _html


def card_attrs(date="", rich=0):
    """Return the ` data-date="…" data-rich="N"` attribute string to drop into a card's opening tag."""
    return ' data-date="%s" data-rich="%d"' % (_html.escape(str(date or "")), int(rich or 0))


def controls_css():
    return ("<style>"
            ".lc-bar{display:flex;align-items:center;gap:9px;margin:.7rem 0 .3rem;flex-wrap:wrap}"
            ".lc-bar input[type=search]{flex:1 1 220px;min-width:160px;font:inherit;font-size:.92rem;"
            "color:var(--ink,#13243d);background:#fff;border:1px solid var(--line,#26456a);border-radius:9px;padding:.45rem .7rem}"
            ".lc-bar input[type=search]:focus{outline:0;border-color:var(--accent2,#1259a3);box-shadow:0 0 0 3px rgba(18,89,163,.12)}"
            ".lc-bar .lc-lbl{font-family:'JetBrains Mono',Consolas,monospace;font-size:10px;letter-spacing:1px;"
            "text-transform:uppercase;color:var(--faint,#5b6e86)}"
            ".lc-btns{display:flex;gap:5px;flex-wrap:wrap}"
            ".lc-sb{font:inherit;font-size:.82rem;font-weight:600;padding:.3rem .7rem;border-radius:20px;"
            "border:1px solid var(--line,#26456a);background:#fff;color:var(--accent,#00356b);"
            "cursor:pointer;white-space:nowrap;display:inline-flex;align-items:center;gap:4px;"
            "line-height:1.2;transition:background .1s,color .1s}"
            ".lc-sb:hover{background:var(--panel,#e7eef8)}"
            ".lc-sb.on{background:var(--accent,#00356b);color:#fff;border-color:var(--accent,#00356b)}"
            ".lc-bar .lc-n{font-family:'JetBrains Mono',Consolas,monospace;font-size:11px;color:var(--faint,#5b6e86);white-space:nowrap}"
            "</style>")


def toolbar(noun="items", placeholder=None, with_rich=True):
    """The search input + sort emoji pill buttons. `noun` is what the counter says ("80 split votes")."""
    ph = placeholder or ("Search %s…" % noun)
    rich_btn = ("<button class=lc-sb id=lcs-rich onclick=\"lcSort('rich')\" aria-label='Most detail first'>"
                "⭐ Detail</button>") if with_rich else ""
    return ("<div class=lc-bar>"
            "<input id=lc-search type=search placeholder='%s' aria-label='Search %s' oninput='lcFilter(this.value)'>"
            "<div class=lc-btns>"
            "<button class='lc-sb on' id=lcs-new onclick=\"lcSort('new')\" aria-label='Newest first'>\U0001f4c5 Newest</button>"
            "<button class=lc-sb id=lcs-old onclick=\"lcSort('old')\" aria-label='Oldest first'>\U0001f553 Oldest</button>"
            "%s</div>"
            "<span class=lc-n id=lc-n></span></div>") % (_html.escape(ph), _html.escape(noun), rich_btn)


def sortjs(noun="items"):
    """The client-side filter+sort over `#lc-list` children. Newest-first on load."""
    return ("<script>(function(){var box=document.getElementById('lc-list');if(!box)return;"
            "var cards=[].slice.call(box.children);cards.forEach(function(c){c.__t=(c.textContent||'').toLowerCase();});"
            "var q='',nEl=document.getElementById('lc-n');var NOUN=%r;"
            "function apply(){var s=0;cards.forEach(function(c){var ok=!q||c.__t.indexOf(q)>-1;"
            "c.style.display=ok?'':'none';if(ok)s++;});if(nEl)nEl.textContent=s+(q?' of '+cards.length:'')+' '+NOUN;}"
            "window.lcFilter=function(v){q=(v||'').trim().toLowerCase();apply();};"
            "function setActive(m){'new old rich'.split(' ').forEach(function(id){"
            "var el=document.getElementById('lcs-'+id);"
            "if(el)el.className='lc-sb'+(m===id?' on':'');});}"
            "window.lcSort=function(m){setActive(m);var a=cards.slice();a.sort(function(x,y){"
            "var dx=x.getAttribute('data-date')||'',dy=y.getAttribute('data-date')||'',"
            "rx=+(x.getAttribute('data-rich')||0),ry=+(y.getAttribute('data-rich')||0);"
            "if(m==='old')return dx<dy?-1:dx>dy?1:ry-rx;"
            "if(m==='rich')return (ry-rx)||(dx<dy?1:dx>dy?-1:0);"
            "return dx<dy?1:dx>dy?-1:ry-rx;});a.forEach(function(c){box.appendChild(c);});apply();};"
            "apply();})();</script>") % noun
