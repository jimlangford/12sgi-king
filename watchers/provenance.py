#!/usr/bin/env python3
# provenance.py - the ONE provenance convention for the whole Kilo Aupuni civic chain.
#
# Jimmy's ask ("put the other stuff saying transcribed"): every civic record must declare
# WHERE it came from, so a reader can tell an official filing apart from something we
# derived from a meeting's audio/video transcript. This is a civic-discipline primitive,
# not a data tool: it fabricates nothing, it only LABELS provenance that the caller already
# knows.
#
#   source_type = "sourced"      -> official document / API filing (a posted minutes or
#                                   agenda PDF, a Legistar/CivicClerk record, a gov API row).
#                                   THIS IS THE DEFAULT.
#   source_type = "transcribed"  -> derived from audio/video meeting transcription (only
#                                   where the content truly came from a transcript).
#
# Small green 'sourced' / amber 'transcribed' badge renders inline on any civic page. The
# span is fully self-contained (inline styles) so it needs no external CSS, and every color
# matches the shared civic palette (green = --cs-ok #1f8a5b, amber = --cs-gold #b8860b).
#
# Stdlib only. UTF-8. Import from any sibling tool: `import provenance`.

SOURCE_TYPES = ("sourced", "transcribed")
DEFAULT_SOURCE_TYPE = "sourced"

# palette (shared with civic_shell / the Yale-blue civic pages)
_COLORS = {
    "sourced":     {"fg": "#0f6b45", "bg": "#e4f4ec", "bd": "#1f8a5b", "label": "sourced"},
    "transcribed": {"fg": "#7a5a08", "bg": "#fbf3dd", "bd": "#b8860b", "label": "transcribed"},
}


def normalize(source_type):
    """Return a valid source_type, defaulting to 'sourced'.

    Accepts None / unknown / mixed-case / stray whitespace and never raises -
    an unknown or empty value normalizes to the safe default ('sourced'), because
    the civic default is that a record is an official filing unless we KNOW it was
    derived from a transcript.
    """
    if not source_type:
        return DEFAULT_SOURCE_TYPE
    s = str(source_type).strip().lower()
    if s in ("transcribed", "transcript", "transcription"):
        return "transcribed"
    if s in ("sourced", "source", "official", "document", "filing", "api"):
        return "sourced"
    return DEFAULT_SOURCE_TYPE


def badge_html(source_type):
    """Return a small labeled <span> badge: green 'sourced', amber 'transcribed'.

    Self-contained inline styles (no external CSS required). Safe to drop straight
    into any civic HTML page next to a record.
    """
    st = normalize(source_type)
    c = _COLORS[st]
    style = (
        "display:inline-block;padding:1px 7px;border-radius:99px;"
        "font:600 10.5px/1.5 'JetBrains Mono',Consolas,monospace;"
        "letter-spacing:.03em;text-transform:uppercase;white-space:nowrap;"
        "color:%s;background:%s;border:1px solid %s" % (c["fg"], c["bg"], c["bd"])
    )
    return '<span class="prov-badge prov-%s" title="provenance: %s" style="%s">%s</span>' % (
        st, st, style, c["label"])


def classify(status=None, url=None, note=None):
    """Convenience: infer source_type from a record's status/url/note strings.

    Conservative on purpose - returns 'transcribed' ONLY when a signal explicitly
    says the content came from audio/video transcription; everything else (posted
    minutes/agenda PDFs, portal API PDFs, HTML docs) is an official filing = 'sourced'.
    This keeps us honest: we never mislabel an official document as a transcript, and
    we never claim 'sourced' for something we actually transcribed.
    """
    blob = " ".join(str(x) for x in (status, url, note) if x).lower()
    if any(k in blob for k in ("transcript", "transcrib", "captions", "closed-caption",
                               "audio-derived", "video-derived", "whisper", "otter",
                               "asr")):
        return "transcribed"
    return "sourced"


if __name__ == "__main__":
    import sys
    if sys.platform == "win32" and sys.stdout:
        import io as _io
        sys.stdout = _io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    if sys.stdout:
        print("SOURCE_TYPES =", SOURCE_TYPES)
        for s in (None, "sourced", "TRANSCRIBED", "transcript", "official", "weird"):
            print("  normalize(%-12r) -> %-11s  %s" % (s, normalize(s), badge_html(s)))
        print("  classify(status='civicclerk-pdf')          ->", classify(status="civicclerk-pdf"))
        print("  classify(status='granicus video transcript') ->", classify(status="granicus video transcript"))
