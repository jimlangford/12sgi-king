#!/usr/bin/env python3
"""civic_outreach.py -- hardened private civic letter system (Jimmy 2026-07-01
"I need my own private system to do that for the rest of them and harden all these skills").

Generates the FULL outreach package for any Maui County Council member, committee, or agency:
  - Personalized civic finding letter (sourced, allegation-framed, question-only)
  - ADA accommodation notice (clinical anxiety, Title II -- permanently baked in)
  - Sunshine Law deadlines (HRS 92F-15: ack 5 biz days, full 10 biz days -- auto-calculated)
  - Song lyric crosswalk (civic->creative arc, plain English per theme)
  - WordPress HTML (staged for deliberate posting, NEVER auto-posted)
  - Gmail HTML body (staged for deliberate draft creation, NEVER auto-sent)
  - Outbox queue entry with deadline tracking

CLI:
  python civic_outreach.py --target Lee          # one council member (roster key)
  python civic_outreach.py --target GREAT        # a committee abbreviation
  python civic_outreach.py --all                 # all council seats
  python civic_outreach.py --list                # show staged packages + deadlines
  python civic_outreach.py --wp-stage Lee        # print WP HTML to stdout
  python civic_outreach.py --gmail-stage Lee     # print Gmail HTML to stdout

PRIVATE: output -> reports/_status/civic_outreach/  Never auto-published.
NEVER SENDS. Owner reviews staged packages and sends deliberately.
Integrity: framed as questions answered by named public records -- never verdicts.
Stdlib only.
"""
import os, sys, json, secrets, re
from datetime import date, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(os.path.dirname(HERE))
if HERE not in sys.path: sys.path.insert(0, HERE)
from votes_watch import ROSTER

OUT = os.path.join(PROJ, "reports", "_status", "civic_outreach")
REPLY_EMAIL = "elementlotus@gmail.com"
REQUESTER = "Jimmy Langford"
WP_SITE = "elementlotus.com"
CLERK = "county.clerk@mauicounty.us"

# ---------------------------------------------------------------------------
# COMMITTEES (abbreviation -> full name + member filter keyword)
# ---------------------------------------------------------------------------
COMMITTEES = {
    "GET":  {"name": "Government Relations, Ethics & Transparency", "abbr": "GET"},
    "GREAT":{"name": "Government Relations, Ethics & Transparency", "abbr": "GET"},
    "BFED": {"name": "Budget, Finance & Economic Development", "abbr": "BFED"},
    "HLU":  {"name": "Housing & Land Use", "abbr": "HLU"},
    "WIT":  {"name": "Water, Infrastructure & Transportation", "abbr": "WIT"},
    "DRR":  {"name": "Disaster, Resilience & Recovery", "abbr": "DRR"},
    "APT":  {"name": "Agriculture, Environment & Public Trust", "abbr": "APT"},
    "HCC":  {"name": "Human Concerns & Culture", "abbr": "HCC"},
}

# ---------------------------------------------------------------------------
# ADA NOTICE -- permanently baked in (Jimmy 2026-07-01)
# ---------------------------------------------------------------------------
ADA_NOTICE_TEXT = (
    "I have a documented disability -- clinical anxiety -- protected under Title II of the "
    "Americans with Disabilities Act (42 U.S.C. S 12132) and the Rehabilitation Act of 1973. "
    "I am requesting reasonable accommodation in the form of a written, dated response to this "
    "correspondence within the standard statutory window. This letter is part of my public record "
    "as a constituent with a disability exercising oversight rights."
)
ADA_NOTICE_HTML = (
    "I have a documented disability — clinical anxiety — protected under Title II of the "
    "Americans with Disabilities Act (42 U.S.C. § 12132) and the Rehabilitation Act of 1973. "
    "I am requesting reasonable accommodation in the form of a written, dated response to this "
    "correspondence within the standard statutory window. This letter is part of my public record "
    "as a constituent with a disability exercising oversight rights."
)

# ---------------------------------------------------------------------------
# SONG CROSSWALK -- civic theme -> songs with plain-English explanation
# Updated here; never guess from outside the catalog.
# ---------------------------------------------------------------------------
SONG_CROSSWALK = {
    "contractor_donor": [
        {
            "title": "Mana Shark Flash",
            "search": "Mana Shark Flash Jimmy Langford",
            "lyric": ('"Shark flash, teeth made of flame... spark with a silence... '
                      'stomping by reef-borne feet"'),
            "plain": (
                "Mana (Hawaiian: spiritual power/authority) wielded like a shark -- sudden, silent, "
                "predatory. This song is about what happens when institutional power moves without "
                "announcement, without apology, without a paper trail the public can read. When a "
                "contract goes to a firm whose principals donated to the decision-makers, that is the "
                "shark moving."
            ),
        },
        {
            "title": "Maui Courts (Criminal Logic Pattern)",
            "search": "Maui Courts Jimmy Langford",
            "lyric": None,
            "plain": (
                "What is the 'criminal logic pattern' embedded in Maui's civic infrastructure? Not an "
                "accusation -- a question. When a contract goes to a firm whose principals gave to "
                "elected decision-makers, what is the pattern? This song names that question out loud."
            ),
        },
    ],
    "database_removal": [
        {
            "title": "Ashes of Trust",
            "search": "Ashes of Trust Jimmy Langford",
            "lyric": None,
            "plain": (
                "When public records disappear without notice -- contracts removed from a state database "
                "in 48 hours with no public explanation -- what's left is ash. The public's trust in "
                "those records is the thing that burned. This song is about institutional fire."
            ),
        },
        {
            "title": "Promised and Betrayed",
            "search": "Promised and Betrayed Jimmy Langford",
            "lyric": None,
            "plain": (
                "The promise of transparent government, and what happens when the database underneath "
                "the assessment quietly changes while the assessment is happening. Promised transparency; "
                "the ground shifted."
            ),
        },
    ],
    "governance": [
        {
            "title": "AN ON Y MO US",
            "search": "Anonymous Jimmy Langford elementLOTUS",
            "lyric": None,
            "plain": (
                "The central Joker node of Jimmy's 54-song civic arc. Anonymity as power -- the faceless "
                "force that moves contracts, removes records, and leaves no fingerprints. Who ordered it, "
                "and why? The song asks it. So does this letter."
            ),
        },
    ],
    "recovery": [
        {
            "title": "He Lei no Lahaina",
            "search": "He Lei no Lahaina Jimmy Langford",
            "lyric": None,
            "plain": (
                "A lei for Lahaina -- a song of grief and love for what was lost. Recovery promises are "
                "civic promises. When Lahaina-recovery contract records change in a public database without "
                "explanation, this song is the reckoning."
            ),
        },
    ],
    "land_water": [
        {
            "title": "REEF",
            "search": "Reef Jimmy Langford elementLOTUS",
            "lyric": None,
            "plain": (
                "The reef is the boundary -- coastal decisions affect the whole system. Permits, coastal "
                "erosion, water rights: the civic decisions that determine what the coast looks like for "
                "the next generation."
            ),
        },
    ],
}

# ---------------------------------------------------------------------------
# BUSINESS DAY CALCULATOR (HRS 92F-15)
# ---------------------------------------------------------------------------
def _biz_date(n):
    d = date.today()
    count = 0
    while count < n:
        d += timedelta(days=1)
        if d.weekday() < 5:
            count += 1
    return d.strftime("%B %d, %Y")

def _today_str():
    return date.today().strftime("%B %d, %Y")

def _iso_today():
    return date.today().isoformat()

# ---------------------------------------------------------------------------
# LOAD CIVIC FINDINGS
# ---------------------------------------------------------------------------
def _load_json(path, default):
    try:
        return json.load(open(path, encoding="utf-8"))
    except Exception:
        return default

def load_findings(target_key):
    """Return findings dict relevant to target_key (seat key OR committee abbr)."""
    f = {"contractor_donor": [], "database_removal": [], "themes": set()}

    # vendor-donor join
    vdj = _load_json(
        os.path.join(PROJ, "seed_reports", "mauios", "vendor_donor_join.json"), {})
    for m in vdj.get("matches", []):
        raw = json.dumps(m)
        if target_key.lower() in raw.lower():
            f["contractor_donor"].append(m)
    if f["contractor_donor"]:
        f["themes"].add("contractor_donor")
        f["themes"].add("governance")

    # HANDS corrections
    hands = _load_json(
        os.path.join(PROJ, "seed_reports", "mauios", "hands_maui_awards.json"), {})
    for c in hands.get("corrections", []):
        if c.get("removed") or c.get("added"):
            f["database_removal"].append(c)
    if f["database_removal"]:
        f["themes"].add("database_removal")
        f["themes"].add("governance")

    f["themes"] = sorted(f["themes"])
    return f

# ---------------------------------------------------------------------------
# SONG SECTION BUILDER
# ---------------------------------------------------------------------------
def _songs_for_findings(findings):
    """Return list of song dicts relevant to the finding themes."""
    songs = []
    seen = set()
    for theme in findings.get("themes", []):
        for s in SONG_CROSSWALK.get(theme, []):
            if s["title"] not in seen:
                seen.add(s["title"])
                songs.append(s)
    return songs

# ---------------------------------------------------------------------------
# TARGET RESOLUTION
# ---------------------------------------------------------------------------
def resolve_target(key):
    """Return (type, label, full_name, to_addr) for a council seat or committee key."""
    # Committee?
    if key.upper() in COMMITTEES:
        c = COMMITTEES[key.upper()]
        return ("committee", key.upper(), c["name"],
                CLERK, "the Chair and Vice-Chair of the %s Committee" % c["name"])
    # Council seat?
    full = ROSTER.get(key) or ROSTER.get(key.capitalize())
    if full:
        name = full.split(" - ")[0].strip()
        district = full.split(" - ", 1)[1].strip() if " - " in full else "Maui County"
        email_guess = "%s.%s@mauicounty.gov" % (
            name.split()[0].lower(),
            name.split()[-1].lower().replace("'", "").replace("ʻ", ""))
        return ("member", key, full, email_guess, "Councilmember %s" % name.split()[0])
    return None

# ---------------------------------------------------------------------------
# LETTER CONTENT BUILDERS
# ---------------------------------------------------------------------------
def _finding_text_blocks(findings):
    blocks = []
    if findings["contractor_donor"]:
        for m in findings["contractor_donor"][:3]:  # cap at 3 per letter
            vendor = m.get("vendor", "Unknown Vendor")
            award = m.get("award_total") or m.get("amount") or 0
            contrib = m.get("contrib_total") or m.get("contrib") or 0
            blocks.append(
                "Finding: %s holds $%s in county awards (HANDS, hands.ehawaii.gov) and appears in "
                "campaign-finance records with $%s associated with officials on this committee "
                "(HI-CAMS). Every item above is a sourced question, not a conclusion."
                % (vendor, "{:,.0f}".format(float(award)),
                   "{:,.0f}".format(float(contrib))))
    if findings["database_removal"]:
        c = findings["database_removal"][0]
        removed = c.get("removed", [])
        delta = abs(float(c.get("delta_dollars") or 0))
        if removed and delta:
            blocks.append(
                "Finding: A comparison of consecutive HANDS database pulls shows $%s across %d records "
                "removed or corrected at the source with no public notice (run: %s). When contract records "
                "in a public database change silently during a Fraud Risk Assessment, the assessment is "
                "only as strong as the database's own integrity controls."
                % ("{:,.0f}".format(delta), len(removed), c.get("run", _iso_today())[:10]))
    return blocks

def build_body_text(target_info, findings):
    ttype, key, full_name, to_addr, salutation = target_info
    blocks = _finding_text_blocks(findings)
    ack = _biz_date(5)
    full_d = _biz_date(10)
    lines = [
        "Aloha %s," % salutation,
        "",
        "My name is Jimmy Langford. I am a Maui resident and I follow the public record through "
        "Kilo Aupuni, a civic transparency project. I am writing with sourced questions from the "
        "public record for your consideration.",
        "",
        "ADA ACCOMMODATION NOTICE:",
        ADA_NOTICE_TEXT,
        "",
    ]
    if blocks:
        lines.append("PUBLIC RECORD QUESTIONS (sourced -- every item is a question, not an accusation):")
        for b in blocks:
            lines.append("")
            lines.append(b)
    lines += [
        "",
        "SUNSHINE LAW RESPONSE NOTICE (HRS S92F-15):",
        "Acknowledgment due within 5 business days (by %s)." % ack,
        "Full response due within 10 business days (by %s)." % full_d,
        "",
        "This letter and any response received will be posted publicly at elementlotus.com "
        "as part of my Sunshine Law tracking record.",
        "",
        "I offer these questions not as accusations but as sourced items from a Maui resident "
        "who believes your committee is the right body to receive them. All data is drawn from "
        "public records. I am glad to share the underlying dataset in any format useful to you.",
        "",
        "Me ke aloha pumehana,",
        "",
        "%s" % REQUESTER,
        "Maui resident / Kilo Aupuni civic transparency project / elementLOTUS",
        REPLY_EMAIL,
        "ADA-protected constituent / clinical anxiety / Title II, 42 U.S.C. S 12132",
        "",
        "Sources: HANDS (hands.ehawaii.gov), Hawaii Campaign Spending Commission (HI-CAMS), "
        "Maui County Legistar (mauicounty.legistar.com).",
    ]
    return "\n".join(lines)

def build_wp_html(target_info, findings, songs, date_str=None):
    ttype, key, full_name, to_addr, salutation = target_info
    date_str = date_str or _today_str()
    ack = _biz_date(5)
    full_d = _biz_date(10)
    blocks = _finding_text_blocks(findings)
    label = ("Committee: %s" % full_name) if ttype == "committee" else full_name

    html_findings = ""
    for i, b in enumerate(blocks, 1):
        html_findings += "<p><strong>Finding %d:</strong> %s</p>\n" % (i, b)

    html_songs = ""
    for s in songs:
        lyric_line = ("<p><em>%s</em></p>\n" % s["lyric"]) if s.get("lyric") else ""
        html_songs += (
            "<h3>%s</h3>\n%s<p>%s</p>\n"
            "<p>\U0001f3b5 Search <strong>%s</strong> on Spotify / Apple Music &middot; "
            "<a href=\"https://elementlotus.com\">elementlotus.com</a></p>\n"
        ) % (s["title"], lyric_line, s["plain"], s["search"])

    return (
        "<!-- wp:paragraph -->\n"
        "<p><strong>Sent:</strong> {date} &nbsp;|&nbsp; "
        "<strong>To:</strong> {label} &nbsp;|&nbsp; "
        "<strong>From:</strong> {requester}, Maui resident / Kilo Aupuni</p>\n"
        "<!-- /wp:paragraph -->\n\n"
        "<!-- wp:paragraph -->\n"
        "<p><strong>Sunshine Law (HRS &sect;92F-15):</strong> "
        "Acknowledgment due by <strong>{ack}</strong> &middot; "
        "Full response due by <strong>{full_d}</strong></p>\n"
        "<!-- /wp:paragraph -->\n\n"
        "<!-- wp:separator --><hr/><!-- /wp:separator -->\n\n"
        "<!-- wp:heading {{\"level\":2}} --><h2>The Letter</h2><!-- /wp:heading -->\n\n"
        "<!-- wp:paragraph -->\n"
        "<p><strong>ADA Accommodation Notice:</strong> {ada}</p>\n"
        "<!-- /wp:paragraph -->\n\n"
        "{findings}"
        "<!-- wp:separator --><hr/><!-- /wp:separator -->\n\n"
        "<!-- wp:heading {{\"level\":2}} -->"
        "<h2>Songs From the Catalog &mdash; Lyric Overlaps in Plain English</h2>"
        "<!-- /wp:heading -->\n\n"
        "{songs}"
        "<!-- wp:separator --><hr/><!-- /wp:separator -->\n\n"
        "<!-- wp:paragraph -->\n"
        "<p><em>All findings drawn from public records: HANDS (hands.ehawaii.gov), "
        "HI-CAMS, Maui County Legistar. Framed as questions -- not legal advice, not a "
        "conclusion. Kilo Aupuni &middot; 12 Stones Global &middot; {date}.</em></p>\n"
        "<!-- /wp:paragraph -->\n\n"
        "<!-- wp:paragraph -->\n"
        "<p><strong>Me ke aloha pumehana,</strong><br>{requester}<br>"
        "<em>ADA-protected &middot; clinical anxiety &middot; Title II, 42 U.S.C. &sect; 12132</em></p>\n"
        "<!-- /wp:paragraph -->"
    ).format(
        date=date_str, label=label, requester=REQUESTER,
        ack=ack, full_d=full_d, ada=ADA_NOTICE_HTML,
        findings=html_findings, songs=html_songs,
    )

def build_gmail_html(target_info, findings, songs, wp_url=None):
    ttype, key, full_name, to_addr, salutation = target_info
    ack = _biz_date(5)
    full_d = _biz_date(10)
    blocks = _finding_text_blocks(findings)
    wp_block = ""
    if wp_url:
        wp_block = (
            "<p><strong>PUBLIC RECORD:</strong> This letter will be posted at: "
            "<a href=\"{u}\">{u}</a></p><hr/>\n"
        ).format(u=wp_url)

    findings_html = ""
    for i, b in enumerate(blocks, 1):
        findings_html += "<p><strong>Finding %d:</strong> %s</p>\n" % (i, b)

    songs_html = ""
    for s in songs:
        lyric_line = ("<em>%s</em><br>" % s["lyric"]) if s.get("lyric") else ""
        songs_html += (
            "<p><strong>%s</strong><br>%s%s<br>"
            "\U0001f3b5 Search <strong>%s</strong> on Spotify / Apple Music &middot; "
            "<a href=\"https://elementlotus.com\">elementlotus.com</a></p>\n"
        ) % (s["title"], lyric_line, s["plain"], s["search"])

    return (
        "{wp_block}"
        "<p>Aloha {salutation},</p>\n"
        "<p>My name is {requester}. I am a Maui resident and I follow the public record through "
        "Kilo Aupuni, a civic transparency project.</p>\n"
        "<p><strong>ADA Accommodation Notice:</strong> {ada}</p><hr/>\n"
        "{findings}"
        "<p><strong>FROM THE ARTIST'S CATALOG &mdash; Songs Whose Lyrics Speak to This Record</strong></p>\n"
        "{songs}"
        "<hr/>\n"
        "<p><strong>Sunshine Law (HRS &sect;92F-15):</strong> "
        "Acknowledgment due <strong>{ack}</strong> &middot; "
        "Full response due <strong>{full_d}</strong></p>\n"
        "<p>This letter and any response will be posted publicly at elementlotus.com.</p>\n"
        "<hr/>\n"
        "<p>Me ke aloha pumehana,</p>\n"
        "<p><strong>{requester}</strong><br>Maui resident / Kilo Aupuni / elementLOTUS<br>"
        "{email}<br>"
        "<em>ADA-protected constituent &middot; clinical anxiety &middot; "
        "Title II, 42 U.S.C. &sect; 12132</em></p>\n"
        "<p><small><em>All findings from public records: HANDS (hands.ehawaii.gov), HI-CAMS, "
        "Maui County Legistar. Framed as questions -- not legal advice, not a conclusion. "
        "Kilo Aupuni &middot; 12 Stones Global &middot; {date}.</em></small></p>"
    ).format(
        wp_block=wp_block, salutation=salutation,
        requester=REQUESTER, ada=ADA_NOTICE_HTML,
        findings=findings_html, songs=songs_html,
        ack=ack, full_d=full_d, email=REPLY_EMAIL, date=_today_str(),
    )

# ---------------------------------------------------------------------------
# STAGE PACKAGE
# ---------------------------------------------------------------------------
def stage_package(key, verbose=True):
    """Generate and stage the full package for a target key. Returns manifest dict."""
    tinfo = resolve_target(key)
    if not tinfo:
        print("civic_outreach: unknown target %r -- valid keys: %s" % (
            key, ", ".join(list(ROSTER.keys()) + list(COMMITTEES.keys()))))
        return None
    ttype, rkey, full_name, to_addr, salutation = tinfo

    findings = load_findings(key)
    songs = _songs_for_findings(findings)

    body_text = build_body_text(tinfo, findings)
    subject = ("Public Record Questions & ADA Request -- %s -- Maui County Council %s %s"
               % (full_name if ttype == "committee" else rkey,
                  _today_str(), REPLY_EMAIL))
    wp_html = build_wp_html(tinfo, findings, songs)
    gmail_html = build_gmail_html(tinfo, findings, songs)

    # Stage directory
    slug = re.sub(r"[^a-z0-9]+", "_", key.lower()).strip("_")
    out_dir = os.path.join(OUT, slug)
    os.makedirs(out_dir, exist_ok=True)

    # Write files
    open(os.path.join(out_dir, "letter.txt"), "w", encoding="utf-8", newline="\n").write(body_text)
    open(os.path.join(out_dir, "wp_post.html"), "w", encoding="utf-8", newline="\n").write(wp_html)
    open(os.path.join(out_dir, "gmail_body.html"), "w", encoding="utf-8", newline="\n").write(gmail_html)

    manifest = {
        "target": key,
        "type": ttype,
        "full_name": full_name,
        "to_addr": to_addr,
        "subject": subject,
        "date": _iso_today(),
        "sunshine_ack_by": _biz_date(5),
        "sunshine_full_by": _biz_date(10),
        "ada_notice": "included",
        "songs_count": len(songs),
        "song_titles": [s["title"] for s in songs],
        "themes": findings.get("themes", []),
        "contractor_donor_matches": len(findings["contractor_donor"]),
        "database_corrections": len(findings["database_removal"]),
        "files": {
            "letter": "letter.txt",
            "wp_html": "wp_post.html",
            "gmail_html": "gmail_body.html",
        },
        "wp_posted": False,
        "gmail_draft_id": None,
        "outbox_id": None,
        "status": "STAGED -- owner reviews, posts WP + creates Gmail draft deliberately",
    }
    json.dump(manifest, open(os.path.join(out_dir, "manifest.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)

    # Queue in outbox
    try:
        sys.path.insert(0, HERE)
        import outbox
        item = outbox.enqueue(
            to=to_addr,
            subject=subject,
            body_text=body_text,
            body_html=gmail_html,
            source="civic_outreach",
            item_id="co-%s-%s" % (slug, _iso_today()),
        )
        # Patch outbox item with Sunshine Law deadline fields
        item["sunshine_ack_by"] = _biz_date(5)
        item["sunshine_full_by"] = _biz_date(10)
        item["ada_accommodation"] = True
        item["wp_staged"] = True
        item["songs"] = [s["title"] for s in songs]
        outbox._save(item)
        manifest["outbox_id"] = item["id"]
        json.dump(manifest, open(os.path.join(out_dir, "manifest.json"), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=2)
    except Exception as e:
        manifest["outbox_error"] = str(e)[:120]

    if verbose:
        print("civic_outreach: STAGED %s (%s)" % (key, ttype))
        print("  dir:       %s" % out_dir)
        print("  to:        %s" % to_addr)
        print("  songs:     %s" % ", ".join(s["title"] for s in songs))
        print("  themes:    %s" % ", ".join(findings.get("themes", [])))
        print("  ack by:    %s  (5 biz days, HRS 92F-15)" % manifest["sunshine_ack_by"])
        print("  full by:   %s  (10 biz days)" % manifest["sunshine_full_by"])
        print("  outbox:    %s" % manifest.get("outbox_id", "N/A"))
        print("  NEXT: post WP -> then create Gmail draft via MCP -> then enqueue outbox for approval")
    return manifest

# ---------------------------------------------------------------------------
# STAGE ALL COUNCIL SEATS
# ---------------------------------------------------------------------------
def stage_all(verbose=True):
    results = []
    for k in ROSTER:
        if k == "Bissen":
            continue
        m = stage_package(k, verbose=False)
        if m:
            results.append(m)
            if verbose:
                print("  staged %s (%s) -> outbox %s" % (
                    k, m["full_name"], m.get("outbox_id", "N/A")))
    if verbose:
        print("civic_outreach: staged %d packages -> %s" % (len(results), OUT))
    return results

# ---------------------------------------------------------------------------
# LIST STAGED PACKAGES
# ---------------------------------------------------------------------------
def list_staged():
    if not os.path.isdir(OUT):
        print("civic_outreach: no staged packages yet (run --all or --target <key>)")
        return
    found = 0
    for entry in sorted(os.listdir(OUT)):
        mpath = os.path.join(OUT, entry, "manifest.json")
        if not os.path.isfile(mpath):
            continue
        try:
            m = json.load(open(mpath, encoding="utf-8"))
        except Exception:
            continue
        found += 1
        wp = "WP:posted" if m.get("wp_posted") else "WP:staged"
        gm = "Gmail:%s" % m.get("gmail_draft_id", "pending")
        ob = "Outbox:%s" % (m.get("outbox_id") or "N/A")
        print("  [%s] %s | %s / %s / %s" % (
            m.get("status", "?")[:20], m.get("target","?"),
            wp, gm, ob))
        print("    to: %s" % m.get("to_addr","?"))
        print("    ack by: %s | full by: %s" % (
            m.get("sunshine_ack_by","?"), m.get("sunshine_full_by","?")))
        print("    songs: %s" % ", ".join(m.get("song_titles",[])))
    if not found:
        print("civic_outreach: no manifests found in %s" % OUT)

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    import argparse
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--target", default=None,
                    help="Council seat key (Lee, Cook, ...) or committee abbr (GREAT, BFED, ...)")
    ap.add_argument("--all", dest="all", action="store_true",
                    help="Stage packages for all council seats")
    ap.add_argument("--list", dest="list", action="store_true",
                    help="List staged packages and deadlines")
    ap.add_argument("--wp-stage", dest="wp_stage", metavar="KEY",
                    help="Print WP HTML for a target to stdout")
    ap.add_argument("--gmail-stage", dest="gmail_stage", metavar="KEY",
                    help="Print Gmail HTML for a target to stdout")
    a = ap.parse_args()

    if sys.platform == "win32":
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    if a.list:
        list_staged()
    elif a.wp_stage:
        tinfo = resolve_target(a.wp_stage)
        if not tinfo:
            print("unknown target:", a.wp_stage); return 1
        f = load_findings(a.wp_stage)
        s = _songs_for_findings(f)
        print(build_wp_html(tinfo, f, s))
    elif a.gmail_stage:
        tinfo = resolve_target(a.gmail_stage)
        if not tinfo:
            print("unknown target:", a.gmail_stage); return 1
        f = load_findings(a.gmail_stage)
        s = _songs_for_findings(f)
        print(build_gmail_html(tinfo, f, s))
    elif a.all:
        stage_all()
    elif a.target:
        stage_package(a.target)
    else:
        ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
