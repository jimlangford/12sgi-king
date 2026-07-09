# -*- coding: utf-8 -*-
"""
rollcall_parser.py — the shared CivicClerk roll-call/motion parser (real Maui minutes checkmark format).

EXTRACTED from votes_watch.py (2026-07-08) with a real bug fix, so votes_watch.py, nay_narratives.py, and any
historical (former-member) extraction all reuse ONE correct parser instead of drifting copies.

THE BUG (found via direct corpus inspection): the original MOTION_ANCHOR accepted exactly ONE digit-group
between "VOTES" and "MOTION" — `TOTAL\s+VOTES\s+(\d+)\s+MOTION`. Real minutes render the tally as 1-3
space-separated numbers (AYE [NO] [EXC]), e.g. "TOTAL VOTES 7  2 MOTION PASSED" (7 aye, 2 no) or
"TOTAL VOTES 4 5  MOTION FAILED". Scanned the full 2025-2026 corpus: 837 real "TOTAL VOTES...MOTION..."
occurrences exist; the old regex matched only 377 (45%) — EVERY sampled miss was a non-unanimous or FAILED
motion, i.e. it silently dropped almost every real dissent while still "working" on unanimous votes. Fixed
below to accept 1-3 numbers and parse them into total/noes_total/exc_total, giving a numeric ground-truth
to cross-check the per-name checkmark-column guess against (the column-ambiguity defect: an AYE-column vs
NO-column checkmark render as the same glyph, differentiated only by whitespace offset in flattened pypdf
text — unreliable on its own). Where the per-name AYE count doesn't match the tally's own aye total, the
motion is marked low_confidence rather than presented as a fact.

Minutes record each motion as a flattened checkmark table that pypdf renders as:
  "CM Cook √   VC Sugimura √ ... Chair Lee √   Maker Sugimura  Seconder Lee
   TOTAL VOTES 9 MOTION PASSED"  (unanimous)
  "CM Sinenci √ ... CM Batangan   √   Chair Lee √ ... TOTAL VOTES 7  2 MOTION PASSED"  (7-2 split — the
   dissenter's checkmark sits further right, in the NO column, only distinguishable by whitespace offset)
Each motion block ends at "TOTAL VOTES n [m] [k] MOTION <result>"; we anchor on that and read the preceding
window as the roll call.
"""
import re

VOTE_MARK = re.compile(r"[√✓✔]")   # √ ✓ ✔

# FIXED (was exactly one digit-group): 1-3 space-separated numbers = AYE [NO] [EXC]
MOTION_ANCHOR = re.compile(r"TOTAL\s+VOTES\s+((?:\d+\s+){1,3})MOTION\s+([A-Z][A-Za-z]+)", re.I)
MAKER_RE = re.compile(r"Maker\s+([A-Z][A-Za-zʻ'\-ūō]+)")
SECOND_RE = re.compile(r"Seconder\s+([A-Z][A-Za-zʻ'\-ūō]+)")
MOTIONTXT_RE = re.compile(r"Motion\s+(ADOPT|AMEND|DEFER|FILE|PASS|RECEIVE|REFER|POSTPONE|APPROVE|RECONSIDER|TABLE|WAIVE)[^\n]{0,70}", re.I)
NOES_BLOCK = re.compile(r"(?:NOES?|VOTING\s+NO|NO\s+VOTES?|OPPOSED)\s*[:\-–—]\s*([A-Z][^\n.;]{0,140})", re.I)
ABSTAIN_BLOCK = re.compile(r"(?:ABSTAIN(?:ED|ING)?|ABSTENTIONS?)\s*[:\-–—]\s*([A-Z][^\n.;]{0,140})", re.I)


def member_vote(block, tok):
    m = re.search(tok, block)
    if not m:
        return None
    tail = block[m.end(): m.end() + 18]
    if re.match(r"[\s:]*Recus", tail, re.I):
        return "RECUSED"
    if re.match(r"[\s:]*(Excus|Absent)", tail, re.I):
        return "EXCUSED"
    if re.match(r"[\s:]*Abstain", tail, re.I):
        return "ABSTAIN"
    if VOTE_MARK.search(tail[:7]):
        return "AYE"
    if re.match(r"[\s:]*No\b", tail):
        return "NO"
    return None   # present but mark unclear -> do NOT guess (integrity)


def apply_tally(win, votes, surname_tokens):
    """Overlay explicit NOES:/ABSTAIN: tally lines onto the per-name marks (tally wins — it's explicit)."""
    for rx, state in ((NOES_BLOCK, "NO"), (ABSTAIN_BLOCK, "ABSTAIN")):
        for mm in rx.finditer(win):
            names = mm.group(1)
            for k, tok in surname_tokens.items():
                if re.search(tok, names):
                    votes[k] = state
    return votes


def motions_in(txt, surname_tokens, item_re):
    """Every parseable motion in txt. surname_tokens: {roster_key: regex_token}. item_re: the caller's
    ITEM_RE (Bill/Resolution/CC/... pattern) — kept caller-supplied so votes_watch.py's existing pattern
    is reused unchanged. Returns dicts with 'pos' (match offset, for narrative/quote windowing by callers)
    and 'low_confidence' (per-name AYE count didn't match the tally's own aye total — don't over-trust it)."""
    out = []
    for am in MOTION_ANCHOR.finditer(txt):
        win = txt[max(0, am.start() - 850): am.end()]
        votes = {k: v for k, tok in surname_tokens.items() if (v := member_vote(win, tok))}
        votes = apply_tally(win, votes, surname_tokens)
        if not votes:
            continue
        nums = [int(x) for x in re.findall(r"\d+", am.group(1))]
        total = nums[0] if nums else 0
        noes_total = nums[1] if len(nums) > 1 else 0
        exc_total = nums[2] if len(nums) > 2 else 0
        aye_count = sum(1 for v in votes.values() if v == "AYE")
        mk = MAKER_RE.search(win)
        sc = SECOND_RE.search(win)
        mt = MOTIONTXT_RE.search(win)
        it = item_re.search(txt[am.start(): am.start() + 260]) or item_re.search(win[-500:])
        out.append({
            "result": am.group(2).upper(), "total": total, "noes_total": noes_total, "exc_total": exc_total,
            "maker_raw": (mk.group(1) if mk else None), "seconder_raw": (sc.group(1) if sc else None),
            "motion": (re.sub(r"\s+", " ", mt.group(0)).strip()[:90] if mt else None),
            "item": (re.sub(r"\s+", " ", it.group(1)).strip() if it else None),
            "votes": votes, "pos": am.start(),
            "low_confidence": (aye_count != total),
        })
    return out
