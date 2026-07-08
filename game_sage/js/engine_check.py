#!/usr/bin/env python3
# engine_check.py - static contract check for sage_engine.js (node not guaranteed).
# Loads the JS as TEXT and asserts every ENGINE CONTRACT symbol exists, the
# window.SageEngine + module.exports attachments are present, and the file is
# non-trivial (Windows truncation defense). Exit 0 = pass.
import io, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
JS = os.path.join(HERE, "sage_engine.js")

CONTRACT = [
    "init", "roundPy", "moonWindow", "nodeKpis", "kpisAll", "kpisPlanted",
    "selftest", "newGame", "draw", "canPlay", "play", "malama", "discardCard",
    "endMoon", "score", "serialize", "deserialize", "mulberry32",
]
ATTACH = ["window.SageEngine", "module.exports"]
STATE_KEYS = ["seed", "moon", "cycle", "deck", "hand", "discard", "planted",
              "waterCapacity", "waterUsed", "season", "crisisArmed", "won", "log",
              "discardsUsed"]

def main():
    if not os.path.exists(JS):
        print("FAIL: missing " + JS); return 1
    size = os.path.getsize(JS)
    if size < 8000:
        print("FAIL: sage_engine.js suspiciously small (%d bytes) - truncation?" % size)
        return 1
    text = io.open(JS, encoding="utf-8").read()
    bad = []
    for name in CONTRACT:
        # must exist as a function definition AND be exported on the api object
        if not re.search(r"\bfunction\s+" + name + r"\b", text):
            bad.append("no function " + name)
        if not re.search(r"\b" + name + r"\s*:\s*" + name + r"\b", text):
            bad.append("not exported: " + name)
    for s in ATTACH:
        if s not in text:
            bad.append("no attach: " + s)
    for k in STATE_KEYS:
        if not re.search(r"\b" + k + r"\s*:", text):
            bad.append("state key missing: " + k)
    if text.count("{") != text.count("}"):
        bad.append("unbalanced braces {%d vs %d}" % (text.count("{"), text.count("}")))
    if bad:
        print("FAIL (%d bytes):" % size)
        for b in bad:
            print("  - " + b)
        return 1
    print("PASS: sage_engine.js %d bytes | %d contract symbols + %d attachments + %d state keys verified"
          % (size, len(CONTRACT), len(ATTACH), len(STATE_KEYS)))
    return 0

if __name__ == "__main__":
    sys.exit(main())
