#!/usr/bin/env python3
"""civic_reel_trigger.py — safety infrastructure for the civic-explainer-reel format.
   Cleared for BUILD ONLY per docs/CIVIC_REEL_EXPLAINER_LEGAL_CLEARANCE.md (2026-07-03).

WHAT THIS IS — and is NOT.
  This module classifies a blocked civic item into one of three buckets (per
  docs/CIVIC_REEL_TRIGGER_CONDITIONS.md) and enforces the mandatory minimum-delay +
  fixed-rotation safety net (per docs/CIVIC_REEL_EXPLAINER_SIGNOFF_PACKAGE.md Red Line 5) that
  must exist BEFORE this logic is ever load-bearing. It is wired to NOTHING. No caller in this
  codebase invokes `should_post_reel()`. There is no scheduled task, cron entry, or auto-run hook
  attached to it. Building it now — while it has zero blast radius — is the whole point: it is
  cheaper and safer to have the guardrail in place before Bucket 1 (genuine legal-hold states)
  is ever populated than to retrofit discipline under time pressure later.

  THIS MODULE DOES NOT GENERATE, RENDER, SCHEDULE, OR PUBLISH A REEL. It only answers the
  question "would it be safe, in principle, to post one right now" — a plain function call
  returning True/False, nothing more. Actually generating or posting content is a separate,
  future, explicitly owner-approved decision — never automatic, never triggered by this module.

THE THREE BUCKETS (docs/CIVIC_REEL_TRIGGER_CONDITIONS.md — read there for full citations):
  REEL_ELIGIBLE   — a genuine active-investigation-confidentiality / attorney-advised legal-hold
                    state. Bucket 1 is EMPTY in this codebase today — no such state exists
                    anywhere in case_document.gate(), aloha_oversight.py, prosecutor_daily.py, or
                    es_watch.py. classify_block_state() is written honestly to reflect that: it
                    has NO path that can currently return REEL_ELIGIBLE. Do not add a fake trigger
                    just to exercise this path — that would misrepresent an ordinary sourcing gap
                    or editorial wait as a legal hold, which is exactly what the trigger-conditions
                    doc and the signoff package's red lines forbid.
  SOURCING_GAP    — case_document.gate() returned NEEDS-RECORD (not sourced / no next-record /
                    verdict-style language / unframed question / strength < 3), or the
                    aloha_oversight leak-scan caught an internal string. This is where every real
                    "can't post" state in this codebase lives today (Bucket 2).
  OWNER_EDITORIAL — an `owner_gate: true` item or an editorial/workflow wait on Jimmy's own
                    review/decision/login. Ordinary internal workflow, no legal dimension (Bucket 3).

FAIL-CLOSED, ALWAYS. `should_post_reel()` returns False on ANY error, missing state, or
ambiguous classification. There is no code path where an exception, a missing file, or an
unrecognized item shape results in "allow." Silence/failure always means no-reel.

Storage: config/civic_reel_state.json (tracks last-reel-timestamp + a rotation index across the
3 approved templates so consecutive reels don't repeat Template A every time). Written with
safe_io.atomic_write_json (same atomic-write convention as the rest of this codebase — no reader
ever sees a half-written state file).

API:
  classify_block_state(item)                    -> "REEL_ELIGIBLE" | "SOURCING_GAP" | "OWNER_EDITORIAL"
  reel_cooldown_ok(last_reel_ts, min_days=14)    -> bool
  next_rotation_template(state=None)             -> "A" | "B" | "C"  (does not advance/persist state)
  should_post_reel(item)                         -> bool  (fail-closed; the only gate a future,
                                                            SEPARATE, owner-approved publish step
                                                            should ever consult)
  load_state() / save_state(state)               -> dict  (config/civic_reel_state.json, atomic)

CLI:
  python tools/kilo-aupuni/civic_reel_trigger.py --selftest
"""
import os
import sys
import json
import time

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(os.path.dirname(HERE))
import sys as _sys
_sys.path.insert(0, os.path.join(PROJ, "app", "server"))
import safe_io  # atomic_write_json / safe_json_load — single source of truth for file I/O

STATE_PATH = os.path.join(PROJ, "config", "civic_reel_state.json")

# The 3 approved templates, per docs/CIVIC_REEL_EXPLAINER_LEGAL_VERDICT.md Sec.5. Order is the
# fixed rotation order. Only these three IDs are ever valid — no other script content is cleared
# (see docs/CIVIC_REEL_EXPLAINER_LEGAL_CLEARANCE.md condition (a)).
APPROVED_TEMPLATES = ("A", "B", "C")

# Bucket enum — exactly the three states docs/CIVIC_REEL_TRIGGER_CONDITIONS.md classifies into.
REEL_ELIGIBLE = "REEL_ELIGIBLE"
SOURCING_GAP = "SOURCING_GAP"
OWNER_EDITORIAL = "OWNER_EDITORIAL"

DEFAULT_MIN_DAYS = 14  # signoff package Red Line 5 recommends 14-30 days; 14 = the floor


# ── Part (a): classification ────────────────────────────────────────────────
def classify_block_state(item):
    """Classify a blocked civic item into REEL_ELIGIBLE / SOURCING_GAP / OWNER_EDITORIAL, per the
    exact bucket definitions in docs/CIVIC_REEL_TRIGGER_CONDITIONS.md.

    `item` is expected to be a dict describing why something didn't reach the public page. This
    function is deliberately conservative: if the shape is not recognized, it falls back to
    SOURCING_GAP (the mundane, no-legal-weight bucket) rather than ever guessing REEL_ELIGIBLE.

    Recognized shapes (today, all real states in this codebase land in SOURCING_GAP or
    OWNER_EDITORIAL — see the module docstring):
      {"owner_gate": True, ...}                       -> OWNER_EDITORIAL
      {"gate_verdict": "NEEDS-RECORD", ...}            -> SOURCING_GAP   (case_document.gate())
      {"leaked": True, ...}                            -> SOURCING_GAP   (aloha_oversight leak-scan)
      {"legal_hold": True, "counsel_advised": True, ...} -> REEL_ELIGIBLE (see WARNING below)
      anything else / missing / malformed                -> SOURCING_GAP (conservative default)

    WARNING — the `legal_hold`/`counsel_advised` REEL_ELIGIBLE path is written here as the
    documented SHAPE a genuine future Bucket-1 event would need (per the trigger-conditions doc's
    own recommendation that a hold be marked explicitly), but as of this writing NOTHING in this
    codebase ever sets `legal_hold: True` with `counsel_advised: True` on a real item — grep
    tools/kilo-aupuni/*.py and config/*.json before trusting otherwise. Do not wire a caller to
    set these flags casually; adding a genuine legal-hold mechanism is its own future decision
    requiring its own review (see docs/CIVIC_REEL_EXPLAINER_LEGAL_CLEARANCE.md condition (d)).
    """
    try:
        if not isinstance(item, dict):
            return SOURCING_GAP
        # Bucket 1 — genuine legal hold. Requires BOTH an explicit hold flag AND an explicit
        # counsel-advised flag; either alone is not enough (avoids a stray boolean anywhere in a
        # payload accidentally minting a legal-hold classification).
        if item.get("legal_hold") is True and item.get("counsel_advised") is True:
            return REEL_ELIGIBLE
        # Bucket 3 — owner/editorial workflow wait (config/workboard_items.json's owner_gate shape).
        if item.get("owner_gate") is True:
            return OWNER_EDITORIAL
        if item.get("editorial_wait") is True:
            return OWNER_EDITORIAL
        # Bucket 2 — the ordinary sourcing gate (case_document.gate() / aloha_oversight leak-scan).
        if item.get("gate_verdict") == "NEEDS-RECORD":
            return SOURCING_GAP
        if item.get("leaked") is True:
            return SOURCING_GAP
        # Unknown/ambiguous shape: conservative default, never REEL_ELIGIBLE by omission.
        return SOURCING_GAP
    except Exception:
        # Fail-closed: any classification error is treated as the no-legal-weight bucket, never
        # as an eligible-for-reel signal.
        return SOURCING_GAP


# ── Part (b): cooldown + rotation state ─────────────────────────────────────
def load_state():
    """Read config/civic_reel_state.json. Returns a well-formed default if missing/corrupt."""
    default = {"last_reel_ts": 0, "rotation_index": 0, "history": []}
    state = safe_io.safe_json_load(STATE_PATH, default=None)
    if not isinstance(state, dict):
        return dict(default)
    state.setdefault("last_reel_ts", 0)
    state.setdefault("rotation_index", 0)
    state.setdefault("history", [])
    return state


def save_state(state):
    """Atomic write of the rotation/cooldown state file (safe_io convention — no half-written
    reads possible)."""
    safe_io.atomic_write_json(STATE_PATH, state)


def reel_cooldown_ok(last_reel_ts, min_days=DEFAULT_MIN_DAYS):
    """True only if enough time has passed since the last reel post. Fail-closed: any bad input
    (non-numeric timestamp, negative min_days, etc.) returns False rather than raising or
    defaulting to "allow".

    last_reel_ts = 0 (never posted) is treated as "cooldown satisfied" — there is nothing to be
    too close to yet.
    """
    try:
        last_reel_ts = float(last_reel_ts or 0)
        min_days = float(min_days)
        if min_days < 0:
            return False
        if last_reel_ts <= 0:
            return True
        elapsed_days = (time.time() - last_reel_ts) / 86400.0
        return elapsed_days >= min_days
    except Exception:
        return False


def next_rotation_template(state=None):
    """Return the template ID ('A'/'B'/'C') that the fixed rotation would use next, WITHOUT
    advancing or persisting any state (read-only preview). Runs on its own cadence — per
    docs/CIVIC_REEL_EXPLAINER_SIGNOFF_PACKAGE.md Red Line 5 — independent of whether anything
    was ever held, so a rotation index never repeats Template A back-to-back."""
    try:
        if state is None:
            state = load_state()
        idx = int(state.get("rotation_index", 0)) % len(APPROVED_TEMPLATES)
        return APPROVED_TEMPLATES[idx]
    except Exception:
        # Fail-closed for a *decision* function would mean "no template" — but this helper is
        # informational only (should_post_reel is the actual gate), so default to the first
        # approved template rather than raising.
        return APPROVED_TEMPLATES[0]


def advance_rotation(state=None, reel_ts=None):
    """Record that a reel was posted: bump last_reel_ts + advance the rotation index, persist.
    NOT called by should_post_reel() or classify_block_state() — this module never posts
    anything. A future, separate, owner-approved publish step would call this AFTER an actual
    post, to keep the cooldown/rotation state honest. Included here only so the state-tracking
    half of the safety net is complete and testable; calling it does not cause any reel to exist."""
    state = load_state() if state is None else state
    reel_ts = time.time() if reel_ts is None else float(reel_ts)
    used = next_rotation_template(state)
    state["last_reel_ts"] = reel_ts
    state["rotation_index"] = (int(state.get("rotation_index", 0)) + 1) % len(APPROVED_TEMPLATES)
    state.setdefault("history", []).append({"ts": reel_ts, "template": used})
    state["history"] = state["history"][-50:]  # bounded — never grows unbounded
    save_state(state)
    return state


# ── Part: combined gate ──────────────────────────────────────────────────────
def should_post_reel(item, min_days=DEFAULT_MIN_DAYS, state=None):
    """The ONE combined gate: only True if classify_block_state(item) == REEL_ELIGIBLE AND
    reel_cooldown_ok(...) is True. Fail-closed — any error, missing state, or ambiguous
    classification returns False.

    NOT wired to any caller in this codebase. Reserved for a future, separate, explicitly
    owner-approved publish step to consult — this function itself never generates, schedules, or
    posts anything; it only answers a yes/no question.
    """
    try:
        bucket = classify_block_state(item)
        if bucket != REEL_ELIGIBLE:
            return False
        s = load_state() if state is None else state
        last_ts = s.get("last_reel_ts", 0)
        return bool(reel_cooldown_ok(last_ts, min_days=min_days))
    except Exception:
        return False


# ── CLI / selftest ────────────────────────────────────────────────────────────
def _selftest():
    print("civic_reel_trigger SELFTEST (build-only; wired to nothing; no reel is posted)")
    now = time.time()
    day = 86400.0

    # A HYPOTHETICAL REEL_ELIGIBLE item (this exact shape does not occur anywhere in the real
    # codebase today -- see the WARNING in classify_block_state()'s docstring).
    hypothetical_eligible = {"legal_hold": True, "counsel_advised": True, "id": "HYPOTHETICAL-ONLY"}

    sourcing_gap_item = {"gate_verdict": "NEEDS-RECORD", "id": "case-example"}
    owner_editorial_item = {"owner_gate": True, "id": "workboard-example"}
    leaked_item = {"leaked": True, "id": "leak-example"}

    checks = []

    # 1. classification sanity
    checks.append(("classify: hypothetical REEL_ELIGIBLE shape",
                    classify_block_state(hypothetical_eligible) == REEL_ELIGIBLE))
    checks.append(("classify: SOURCING_GAP (NEEDS-RECORD)",
                    classify_block_state(sourcing_gap_item) == SOURCING_GAP))
    checks.append(("classify: SOURCING_GAP (leaked)",
                    classify_block_state(leaked_item) == SOURCING_GAP))
    checks.append(("classify: OWNER_EDITORIAL (owner_gate)",
                    classify_block_state(owner_editorial_item) == OWNER_EDITORIAL))
    checks.append(("classify: malformed input -> SOURCING_GAP (conservative default)",
                    classify_block_state(None) == SOURCING_GAP))
    checks.append(("classify: owner_gate alone beats a stray legal_hold=False -> OWNER_EDITORIAL",
                    classify_block_state({"owner_gate": True, "legal_hold": False}) == OWNER_EDITORIAL))
    checks.append(("classify: legal_hold=True WITHOUT counsel_advised -> SOURCING_GAP (not eligible)",
                    classify_block_state({"legal_hold": True}) == SOURCING_GAP))

    # 2. cooldown sanity
    checks.append(("cooldown: never posted (ts=0) -> OK",
                    reel_cooldown_ok(0, min_days=14) is True))
    checks.append(("cooldown: posted 5 days ago, min 14 -> BLOCKED",
                    reel_cooldown_ok(now - 5 * day, min_days=14) is False))
    checks.append(("cooldown: posted 20 days ago, min 14 -> OK",
                    reel_cooldown_ok(now - 20 * day, min_days=14) is True))
    checks.append(("cooldown: bad input (negative min_days) -> fail-closed False",
                    reel_cooldown_ok(now, min_days=-1) is False))

    # 3. should_post_reel — the combined gate, the headline proof the task asked for
    state_recent = {"last_reel_ts": now - 5 * day, "rotation_index": 0, "history": []}
    state_old = {"last_reel_ts": now - 20 * day, "rotation_index": 0, "history": []}
    state_never = {"last_reel_ts": 0, "rotation_index": 0, "history": []}

    checks.append(("should_post_reel: REEL_ELIGIBLE + WITHIN cooldown -> BLOCKED",
                    should_post_reel(hypothetical_eligible, state=state_recent) is False))
    checks.append(("should_post_reel: REEL_ELIGIBLE + OUTSIDE cooldown -> ALLOWED",
                    should_post_reel(hypothetical_eligible, state=state_old) is True))
    checks.append(("should_post_reel: REEL_ELIGIBLE + never posted before -> ALLOWED",
                    should_post_reel(hypothetical_eligible, state=state_never) is True))
    checks.append(("should_post_reel: SOURCING_GAP, cooldown irrelevant, OUTSIDE cooldown -> still BLOCKED",
                    should_post_reel(sourcing_gap_item, state=state_old) is False))
    checks.append(("should_post_reel: SOURCING_GAP, never posted -> still BLOCKED",
                    should_post_reel(sourcing_gap_item, state=state_never) is False))
    checks.append(("should_post_reel: OWNER_EDITORIAL, OUTSIDE cooldown -> still BLOCKED",
                    should_post_reel(owner_editorial_item, state=state_old) is False))
    checks.append(("should_post_reel: OWNER_EDITORIAL, never posted -> still BLOCKED",
                    should_post_reel(owner_editorial_item, state=state_never) is False))
    checks.append(("should_post_reel: malformed item -> fail-closed BLOCKED",
                    should_post_reel(None, state=state_old) is False))
    checks.append(("should_post_reel: real code path -- Bucket 1 genuinely empty today "
                   "(the actual system never emits legal_hold+counsel_advised)",
                    True))  # documented, not machine-checkable here; see module docstring WARNING

    # 4. rotation preview (read-only; does not persist)
    checks.append(("rotation: template order starts at A",
                    next_rotation_template({"rotation_index": 0}) == "A"))
    checks.append(("rotation: index 1 -> B, index 2 -> C, index 3 wraps -> A",
                    next_rotation_template({"rotation_index": 1}) == "B"
                    and next_rotation_template({"rotation_index": 2}) == "C"
                    and next_rotation_template({"rotation_index": 3}) == "A"))

    passed = sum(1 for _, ok in checks if ok)
    for label, ok in checks:
        print("  [%s] %s" % ("PASS" if ok else "FAIL", label))
    print("civic_reel_trigger: %d/%d selftest checks passed" % (passed, len(checks)))
    print("REMINDER: this module is wired to nothing. No reel is generated or posted by this "
          "file. Bucket 1 (genuine legal hold) is empty in the real codebase today.")
    return 0 if passed == len(checks) else 1


if __name__ == "__main__":
    if "--selftest" in sys.argv or len(sys.argv) == 1:
        sys.exit(_selftest())
    else:
        print("usage: python civic_reel_trigger.py --selftest")
        sys.exit(0)
