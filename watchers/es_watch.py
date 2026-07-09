#!/usr/bin/env python3
"""es_watch.py - EXECUTIVE SESSION watch (Jimmy 2026-06-20: "when they go into executive session that is a
HUGE indicator of crime").

Disciplined framing: an executive (closed) meeting is LAWFUL only for the enumerated purposes in HRS 92-5,
and only after a recorded 2/3 vote with the purpose stated (HRS 92-4). So an executive session is not crime
by itself - it is a HIGH-VALUE Sunshine-Law RED FLAG. The questions for oversight:
  - was a permitted HRS 92-5 purpose STATED?            (missing/vague purpose = flag)
  - was the 2/3 recorded vote to close taken?           (no recorded vote = flag)
  - was ACTION taken behind the door that should be public?
  - how OFTEN does this body close its doors?           (frequency = pattern)

This SCANS the actual minutes text (reusing committee_minutes.py's Legistar fetch) for executive sessions,
extracts the context, cross-checks against the HRS 92-5 permitted-purpose list, and writes each as a
SOURCED QUESTION - never a verdict, never fabricated. Where full minutes text is not available it says so
honestly (NEEDS-RECORD) rather than inventing.

Source of law: HRS 92-5 (capitol.hawaii.gov/hrscurrent/Vol02_Ch0046-0115/HRS0092/HRS_0092-0005.htm).
PRIVATE / owner-only. Output: reports/_status/prosecutor/es_findings.json. Stdlib + pypdf.
Usage: python es_watch.py [max_meetings]
"""
import os, sys, json, re, io
from datetime import datetime, timezone, timedelta

HST = timezone(timedelta(hours=-10))
HOME = os.path.expanduser("~")
PROJ = os.path.join(HOME, "Documents", "Claude", "Projects", "Video System elementLOTUS")
OUT = os.path.join(PROJ, "reports", "_status", "prosecutor")
HRS_92_5_URL = "https://www.capitol.hawaii.gov/hrscurrent/Vol02_Ch0046-0115/HRS0092/HRS_0092-0005.htm"

# HRS 92-5(a) permitted purposes (verbatim-grounded from capitol.hawaii.gov; the statute list continues at
# the URL above - keep this as the cross-check vocabulary, cite the source, never assert beyond it).
PERMITTED = {
    "personnel": r"\b(hire|hiring|evaluat\w+|dismiss\w+|disciplin\w+|charges?|personnel|officer or employee)\b",
    "licensing": r"\b(licens\w+|section 26-9)\b",
    "negotiations": r"\b(labor negotiat\w+|collective bargain\w+|acquisition of public property|negotiate)\b",
    "attorney_consult": r"\b(consult\w* with .{0,20}attorney|powers, duties|privileges,? immunities|liabilit\w+|litigation|pending (?:suit|claim)|lawsuit)\b",
    "criminal_investigation": r"\b(investigate proceedings|criminal misconduct)\b",
    "confidential_law": r"\b(section 92F|chapter 92F|confidential\w*|required by .{0,15}law)\b",
}
ES_RX = re.compile(r"executive (?:session|meeting)", re.I)
VOTE_RX = re.compile(r"\b(two-?thirds|2/3|moved? .{0,40}executive|to (?:go|enter|convene) .{0,15}executive)\b", re.I)
PURSUANT_RX = re.compile(r"\b(pursuant to|under) .{0,20}(92-?5|92-?4|HRS 92)", re.I)


def load_cm():
    sys.path.insert(0, os.path.join(PROJ, "tools", "kilo-aupuni"))
    import committee_minutes as cm
    return cm


def events(cm, top=120):
    try:
        return cm.jj("%s/Events?$orderby=EventDate+desc&$top=%d" % (cm.BASE, top))
    except Exception:
        return []


def minutes_text(cm, ev):
    try:
        url = cm.minutes_url_for(ev)
        if not url:
            return None
        import pypdf
        raw = cm.gt(url, b=True)
        txt = "\n".join((p.extract_text() or "") for p in pypdf.PdfReader(io.BytesIO(raw)).pages)
        # VP LISTENER: persist the minutes VERBATIM into the truth-store (always-being-truth)
        if txt and txt.strip():
            try:
                import record_store
                record_store.put(source="legistar_minutes", tenant="hi-maui",
                                 doc_id="maui_%s" % (ev.get("EventId") or "unknown"),
                                 text=txt, url=url, tier="primary", doc_type="minutes",
                                 title="%s %s" % ((ev.get("EventDate") or "")[:10], ev.get("EventBodyName") or ""),
                                 fetch_tool="es_watch")
            except Exception:
                pass
        return txt
    except Exception:
        return None


def classify(window):
    purposes = [k for k, rx in PERMITTED.items() if re.search(rx, window, re.I)]
    cited = bool(PURSUANT_RX.search(window))
    voted = bool(VOTE_RX.search(window))
    flags = []
    if not purposes and not cited:
        flags.append("NO permitted HRS 92-5 purpose stated near the closure")
    if not voted:
        flags.append("NO recorded 2/3 vote to close found in the minutes text")
    return purposes, cited, voted, flags


def scan(max_meetings=40):
    cm = load_cm()
    evs = events(cm)
    finalized = [e for e in evs if (e.get("EventMinutesStatusName") == "Final") or cm.minutes_url_for(e)]
    findings, scanned, with_text = [], 0, 0
    for e in finalized[:max_meetings]:
        txt = minutes_text(cm, e)
        scanned += 1
        if not txt:
            continue
        with_text += 1
        for m in ES_RX.finditer(txt):
            a, b = max(0, m.start() - 400), min(len(txt), m.end() + 400)
            window = " ".join(txt[a:b].split())
            purposes, cited, voted, flags = classify(window)
            findings.append({
                "date": (e.get("EventDate") or "")[:10], "body": e.get("EventBodyName"),
                "minutes_url": cm.minutes_url_for(e),
                "stated_purposes": purposes, "cites_statute": cited, "recorded_vote_found": voted,
                "flags": flags,
                "question": ("On %s the %s went into executive session. Stated HRS 92-5 purpose: %s; "
                             "statute cited: %s; 2/3 recorded vote found in the minutes: %s. %s "
                             "Was the closure within a permitted HRS 92-5 purpose, and was the vote properly "
                             "recorded? (HRS 92-5: %s)"
                             % ((e.get("EventDate") or "")[:10], e.get("EventBodyName"),
                                ", ".join(purposes) or "NONE found in text", "yes" if cited else "no",
                                "yes" if voted else "no",
                                ("RED FLAGS: " + "; ".join(flags) + ".") if flags else "No obvious gap in the text.",
                                HRS_92_5_URL)),
            })
    return findings, scanned, with_text


def main():
    os.makedirs(OUT, exist_ok=True)
    try:
        findings, scanned, with_text = scan(int(sys.argv[1]) if len(sys.argv) > 1 else 40)
        note = None
    except Exception as e:
        findings, scanned, with_text = [], 0, 0
        note = "scan unavailable (%s)" % (str(e)[:120])
    # per-body frequency
    freq = {}
    for f in findings:
        freq[f["body"]] = freq.get(f["body"], 0) + 1
    flagged = [f for f in findings if f["flags"]]
    rep = {
        "generated": datetime.now(HST).strftime("%Y-%m-%d %H:%M HST"),
        "source_of_law": HRS_92_5_URL,
        "integrity": ("Executive session is LAWFUL only for HRS 92-5 purposes after a recorded 2/3 vote; "
                      "this is a RED-FLAG indicator framed as questions, never a verdict. Sourced from the "
                      "actual minutes text; nothing fabricated."),
        "meetings_scanned": scanned, "meetings_with_text": with_text,
        "executive_sessions_found": len(findings), "with_red_flags": len(flagged),
        "by_body_frequency": freq, "findings": findings,
    }
    if with_text == 0 and not findings:
        rep["NEEDS_RECORD"] = ("No full minutes TEXT was available to scan (we index minutes metadata, not "
                               "full text). ES detection needs the minutes PDFs / meeting transcripts ingested "
                               "- DELEGATE the full-text pipe to audio-quad-os (transcripts) + the civic minutes "
                               "ingest. The detector + HRS 92-5 cross-check are ready for when the text lands.")
    if note:
        rep["note"] = note
    open(os.path.join(OUT, "es_findings.json"), "w", encoding="utf-8", newline="\n").write(
        json.dumps(rep, ensure_ascii=False, indent=2))
    print("es_watch: scanned %d meetings (%d with text) | %d executive sessions | %d red-flagged%s"
          % (scanned, with_text, len(findings), len(flagged), " | " + rep.get("NEEDS_RECORD", "")[:60] if rep.get("NEEDS_RECORD") else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
