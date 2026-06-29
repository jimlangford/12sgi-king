#!/usr/bin/env python3
"""Fix split article titles in charter-explainer.html.

Many articles have their title split: first part in <h2>, continuation as
the first line of article-body. This merges them back into the <h2>.
"""
import re, shutil, sys
from pathlib import Path

SRC = Path(__file__).parent.parent / "king_public_src" / "charter-explainer.html"

txt = SRC.read_text(encoding="utf-8")
original = txt

def fix(h2_end, body_start):
    """Remove 'body_start\n' from article-body and append it to the h2."""
    old = f'{h2_end}</h2>\n<div class="article-body">{body_start}\n'
    new = f'{h2_end} {body_start}</h2>\n<div class="article-body">\n'
    return old, new

replacements = [
    fix("ARTICLE VI – FIDUCIARY TRUST AND",     "TRANSPARENCY"),
    fix("ARTICLE VII – PUBLIC HEALTH AND WELLNESS", "STEWARDSHIP"),
    fix("ARTICLE VIII – EDUCATION AND CULTURAL",  "LEARNING SYSTEMS"),
    fix("ARTICLE IX – PROTECTION OF YOUTH AND FUTURE", "GENERATIONS"),
    fix("ARTICLE XI – SPIRIT CONTRACT AND CREATOR'S", "OATH"),
    fix("ARTICLE XII – PUBLIC TRUST INFRASTRUCTURE AND", "SACRED SYSTEMS"),
    fix("ARTICLE XIII – ENFORCEMENT, TRIBUNALS, AND", "13TH PROTOCOL IMPLEMENTATION"),
    fix("ARTICLE XIV – BACKEND PROTOCOLS, RAIS",  "LEDGER, AND DATA SOVEREIGNTY SYSTEMS"),
    fix("ARTICLE XV – SACRED SITES AND BURIAL GROUNDS", "PROTECTION"),
    fix("ARTICLE XVII – INDIGENOUS DIPLOMACY AND", "FOREIGN RELATIONS"),
    fix("ARTICLE XVIII – TREASURY AND FINANCIAL",  "SYSTEM SOVEREIGNTY"),
    fix("ARTICLE XIX – RESTITUTION AND ECONOMIC",  "JUSTICE TRIBUNAL"),
    fix("ARTICLE XX – GLOBAL SOVEREIGN BANKING",  "INTEGRATION"),
    fix("ARTICLE XXI – SOVEREIGN PERSONNEL AND PUBLIC", "OFFICE CODE"),
    fix("ARTICLE XXIV – HR AND COMMUNITY AGREEMENTS", "CODE"),
    fix("ARTICLE XXV – DIASPORA AND EXILE RETURN",  "PROTOCOLS"),
    fix("ARTICLE XXVI – SACRED TECHNOLOGY AND AI",  "GOVERNANCE"),
    fix("ARTICLE XXVII – CRISIS RECOVERY AND DISASTER", "RESILIENCE"),
    fix("ARTICLE XXVIII – THE 14TH STONE: INTANGIBLE", "GUARDIAN ALGORITHM"),
]

count = 0
for old, new in replacements:
    if old in txt:
        txt = txt.replace(old, new)
        count += 1
    else:
        print(f"  NOT FOUND: {old[:60]!r}")

if count:
    shutil.copy2(SRC, str(SRC) + ".bak")
    SRC.write_text(txt, encoding="utf-8")
    print(f"Fixed {count}/{len(replacements)} article titles in {SRC.name}")
    print(f"Backup: {SRC}.bak")
else:
    print("Nothing changed (may already be fixed).")
