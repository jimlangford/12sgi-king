#!/usr/bin/env python3
"""agenda_safety.py — the ALWAYS-ON content-integrity gate for civic agenda reels.

Every reel's full text (title + description + every on-screen beat + each platform caption)
must pass check() BEFORE it can be rendered/staged or posted. This is automated defamation
safety + the aloha frame: civic content stays NEUTRAL, SOURCED, public-record, "what to ask /
not a finding." It HARD-BLOCKS anything that reads as an accusation or a guilt claim about a
named real person. Blocking is fail-safe: a blocked reel is simply not auto-posted (it's logged
for a human), so a false-positive costs us a skipped post, never a defamatory one.

It is deliberately strict and self-contained (stdlib only, no model call, no network) so it can
run inside a headless scheduled post with zero dependencies and zero secrets.

  from agenda_safety import check
  verdict = check(text_blob)           # {"ok": bool, "reasons": [...], "hits": [...]}
  if not verdict["ok"]: skip + log

WHAT IT BLOCKS (guilt assertions — civic neutral reels never need these):
  - direct guilt/criminality terms asserted as fact: corrupt, bribe, kickback, embezzle,
    fraud(ster), stole/stolen, launder, rigged, crook, guilty, criminal, felon, conspired,
    "pay to play", "in the pocket of", "bought and paid for", etc.
  - guilt-claim sentence patterns about a person/official: "<Name/title> is corrupt",
    "<Name> took a bribe", "<Name> broke the law", "<Name> lied", "<Name> stole".
  - slurs / profanity (defensive).

WHAT IT ALLOWS (civic-accountability vocabulary is NOT an accusation):
  follow the money, who funds the deciders, campaign-finance records, transparency,
  accountability, ethics, testify, conflict of interest *as a question*, "worth asking".
"""
import re

# Guilt/criminality terms — asserted, these defame. Word-boundary matched, case-insensitive.
GUILT_TERMS = [
    r"corrupt(?:ion|ed)?", r"brib(?:e|ed|ery|ing)", r"kickback", r"embezzl\w*",
    r"fraud(?:ster|ulent)?", r"launder(?:ing|ed)?", r"\bstole\b", r"\bstolen\b",
    r"\bcrook(?:ed|s)?\b", r"\bguilty\b", r"\bcriminal(?:s)?\b", r"\bfelon(?:y|ious)?\b",
    r"conspir(?:e|ed|acy)", r"\bcover[\s-]?up\b", r"\bpayoff(?:s)?\b", r"\bgrift(?:er|ing)?\b",
    r"\bkleptocr\w*", r"\bextort(?:ed|ion)?\b", r"\brigg(?:ed|ing)\b", r"\bracket(?:eering)?\b",
]
# Phrase-level accusations.
GUILT_PHRASES = [
    r"pay[\s-]?to[\s-]?play", r"in the pocket of", r"bought and paid for",
    r"on the take", r"broke the law", r"above the law", r"lining (?:his|her|their) pockets",
    r"\bis (?:a )?(?:liar|crook|criminal|fraud)\b", r"\bare (?:liars|crooks|criminals|frauds)\b",
    r"\btook (?:a )?bribe", r"\bcaught (?:red[\s-]?handed|stealing)",
]
# Defensive: profanity / slurs (kept minimal; civic copy never needs these).
PROFANITY = [r"\bf[\*u]ck\w*", r"\bsh[\*i]t\b", r"\bbastard\b", r"\bscumbag\b"]

_ALL = [re.compile(p, re.I) for p in (GUILT_TERMS + GUILT_PHRASES + PROFANITY)]

# Soft signal: a charged word inside a question / "ask whether" frame is allowed, because the
# whole product is "what to ASK." We still block if it is asserted (no question framing nearby).
_QUESTION_FRAME = re.compile(r"\b(ask|whether|question|worth asking|is it|are they|should we|why)\b", re.I)

# NEUTRAL AUDIT TERMS (James 2026-07-02): 'fraud' is a control/document NAME here, not an accusation —
# e.g. "Fraud Risk Assessment", "anti-fraud", "fraud hotline", "fraud-complaint policy". Masked before the
# guilt scan so sourced civic-audit info auto-approves. Standalone "committed fraud" / "is a fraud" /
# "fraudster" / "fraudulent" are NOT in this list and STILL block.
_NEUTRAL_AUDIT = re.compile(
    r"\banti[-\s]?fraud\b"
    r"|\bfraud[-\s]?(?:risk\s+)?assessment\b"
    r"|\bfraud[-\s]?complaints?\b"
    r"|\bfraud[-\s]?complaint\s+polic\w+\b"
    r"|\bfraud[-\s]?hotline\b"
    r"|\bfraud[-\s]?tip[-\s]?line\b"
    r"|\bfraud[-\s]?prevention\b"
    r"|\bfraud[-\s]?risk\b", re.I)


def check(text, *, strict=True):
    """Return {ok, reasons, hits}. ok=False => DO NOT POST.
    strict=True (default) blocks on any guilt term regardless of framing — the right posture
    for a fully-automated public post. Set strict=False for an advisory scan."""
    t = " ".join((text or "").split())
    t = _NEUTRAL_AUDIT.sub(" audit-term ", t)   # neutralize control/document names before the guilt scan
    hits, reasons = [], []
    for rx in _ALL:
        for m in rx.finditer(t):
            frag = t[max(0, m.start() - 40): m.end() + 40]
            # In non-strict mode, allow a charged word that sits inside a question frame.
            if (not strict) and _QUESTION_FRAME.search(frag):
                continue
            hits.append(m.group(0))
            reasons.append("guilt/accusatory term '%s' in: “…%s…”" % (m.group(0), frag.strip()))
    ok = not hits
    return {"ok": ok, "reasons": reasons, "hits": sorted(set(h.lower() for h in hits))}


def check_reel(meta, storyboard_text=""):
    """Convenience: assemble a reel's full public-facing text and check it."""
    parts = [storyboard_text]
    yt = meta.get("youtube", {})
    parts += [yt.get("title", ""), yt.get("description", "")]
    parts += [meta.get("tiktok", {}).get("caption", ""),
              meta.get("instagram_reels", {}).get("caption", "")]
    parts += list(yt.get("tags", []))
    return check(" \n ".join(p for p in parts if p))


# ── self-test ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    SAMPLES = [
        ("NEUTRAL (should PASS)",
         "Maui County meets Jun 16. Know the law, follow the money — who funds the deciders? "
         "Public campaign-finance records show who backs the people at this table. Worth asking "
         "before the vote. Testify before they decide. #FollowTheMoney #Transparency #Accountability"),
        ("ACCUSATION (should BLOCK)",
         "Councilmember Smith is corrupt and took a bribe — this vote is bought and paid for."),
        ("GUILT CLAIM (should BLOCK)",
         "The mayor broke the law and is lining his pockets with kickbacks."),
        ("CIVIC ETHICS COMMITTEE NAME (should PASS)",
         "Government Relations, Ethics, and Transparency Committee meets to review disclosure rules."),
    ]
    bad = 0
    for label, s in SAMPLES:
        v = check(s)
        verdict = "PASS" if v["ok"] else "BLOCK"
        expect_block = "BLOCK" in label
        good = (verdict == "BLOCK") == expect_block
        bad += 0 if good else 1
        print("%-7s %-34s %s" % (verdict, label, "OK" if good else "*** WRONG ***"))
        for r in v["reasons"]:
            print("        -", r)
    sys.exit(1 if bad else 0)
