#!/usr/bin/env python3
"""tribute_all.py — Generate tributes for all 28 Hawaiian predecessors using local king AI.

Zero Claude tokens. Reads docs/community/HAWAIIAN_PREDECESSORS.json, calls king-jrcsl
via Ollama for each person, saves to docs/community/tributes/<id>_<slug>.md.

Time: ~30-45s per tribute; 28 total = ~14-20 minutes.
Run overnight or during a GPU-idle window.

Usage:
  python tools/kilo-aupuni/tribute_all.py           # all 28
  python tools/kilo-aupuni/tribute_all.py --id 1   # single by id
  python tools/kilo-aupuni/tribute_all.py --pillar food_aina  # one pillar (7)
  python tools/kilo-aupuni/tribute_all.py --dry     # print prompts only, no Ollama
"""
import os, sys, json, subprocess, argparse, time, urllib.request, urllib.error

HERE   = os.path.dirname(os.path.abspath(__file__))
ROOT   = os.path.dirname(os.path.dirname(HERE))
CATALOG = os.path.join(ROOT, "docs", "community", "HAWAIIAN_PREDECESSORS.json")
OUT    = os.path.join(ROOT, "docs", "community", "tributes")
DISPATCH = os.path.join(ROOT, "app", "server", "dispatch.py")
PY = sys.executable

OLLAMA_MODEL = "king-jrcsl"
FALLBACK     = "king-civic"


OLLAMA_HTTP = "http://127.0.0.1:11434/api/generate"


def ollama_query(model, prompt, system=None, timeout=120):
    """Query Ollama via its HTTP API (NOT the `ollama run` CLI subprocess).
    HEAL-FORWARD (2026-07-02, audit-quad-os): the CLI path streams to a TTY and, when captured via
    subprocess with a non-tty stdout, `ollama run` still emits raw CSI cursor-control sequences
    (\\x1b[<n>D\\x1b[K — cursor-back + erase-line, from its line-wrap redraw) INTO stdout itself, not
    just stderr. Captured verbatim this corrupts every line into a repeated-partial-word mess (each
    line ends mid-word, next line repeats the tail). Reproduced directly against `king-civic`/`king-jrcsl`
    on this machine — not a one-off fluke. The HTTP API (`/api/generate`, stream:false) returns clean
    JSON with no terminal artifacts and is the correct non-interactive path. Never route AI-generated
    published content through the CLI subprocess again."""
    full = f"{system}\n\n{prompt}" if system else prompt
    payload = {"model": model, "prompt": full, "stream": False}
    try:
        req = urllib.request.Request(
            OLLAMA_HTTP, data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            r = json.loads(resp.read().decode("utf-8"))
        text = (r.get("response") or "").strip()
        if text:
            return text
        if model != FALLBACK:
            return ollama_query(FALLBACK, prompt, system, timeout)
        return None
    except Exception as e:
        print(f"  [tribute-all] Ollama error ({model}): {e}", flush=True)
        if model != FALLBACK:
            return ollama_query(FALLBACK, prompt, system, timeout)
        return None


def dispatch_log(msg):
    if os.path.exists(DISPATCH):
        subprocess.run([PY, "-X", "utf8", DISPATCH, ROOT,
                        "--log-event", msg, "--source", "audit-quad-os"],
                       capture_output=True, cwd=ROOT)


def build_context(person):
    """Build a compact context string for the AI prompt."""
    lines = [
        f"Honoree: {person['name']} ({person['years']})",
        f"Role: {person['role']}",
        f"Pillar: {person['pillar']}",
        f"Work: {person['work']}",
        f"Civic parallel: {person['civic_parallel']}",
    ]
    if person.get("tmk") and person.get("tmk") != "null":
        lines.append(f"Land (TMK): {person['tmk']} — {person.get('tmk_note', '')}")
    wa = person.get("wa")
    stone = person.get("stone")
    if wa:
        lines.append(f"Kumulipo Wā: {wa} (cosmological resonance — the epoch this work belongs to)")
    if stone:
        lines.append(f"Levi Breastplate Stone: {stone} (12 Stones charter alignment)")
    return "\n".join(lines)


def generate_tribute(person, dry=False):
    context = build_context(person)
    system = (
        "You are the voice of Jimmy Langford (elementLOTUS, 12sgi). "
        "Your voice is Christ-aloha: warm, humble, direct, grateful, truth-grounded. "
        "You write as a Hawaiian sovereign rights artist who sees community service as sacred. "
        "You never boast. You witness clearly and offer gratitude plainly. "
        "Reference specific work by name. Connect their labor to aloha as love in action. "
        "Connect to the Kumulipo wā as cosmological resonance — not genealogical claim. "
        "Keep it under 500 words. No hashtags. No hollow praise. Real witness."
    )
    prompt = (
        f"Write a personal tribute letter from Jimmy Langford to {person['name']}. "
        f"This is a spiritual thank-you — an offering of gratitude for their service to Hawaii. "
        f"Reference their specific work listed below. "
        f"Connect their labor to the {person['pillar'].replace('_',' ').title()} pillar of Jimmy's 12 Stones chart. "
        f"If the Kumulipo wā is listed, reference it lightly as the epoch their work belongs to — "
        f"'your work belongs to the same wā as [what that wā represents]' — not a genealogical claim. "
        f"Mention PULSE (N54 — Universal Synergy) as the heartbeat that their work continues to feed. "
        f"Close with 'Me ke aloha pumehana, Jimmy Langford / elementLOTUS'.\n\n"
        f"CONTEXT:\n{context}"
    )
    if dry:
        print(f"\n{'='*60}")
        print(f"[DRY] Tribute for: {person['name']}")
        print(f"SYSTEM: {system[:100]}...")
        print(f"PROMPT:\n{prompt[:300]}...")
        return "[DRY RUN — no Ollama call]"
    return ollama_query(OLLAMA_MODEL, prompt, system)


def save_tribute(person, text):
    os.makedirs(OUT, exist_ok=True)
    slug = person["name"].lower()
    for ch in " .,'āāēēīīōōūūʻ":
        slug = slug.replace(ch, "_" if ch == " " else "")
    slug = "".join(c for c in slug if c.isalnum() or c == "_")
    fname = f"{person['id']:02d}_{slug}.md"
    outfile = os.path.join(OUT, fname)
    pillar_label = person.get("pillar", "").replace("_", " ").title()
    with open(outfile, "w", encoding="utf-8") as f:
        f.write(f"# Tribute: {person['name']}\n")
        f.write(f"# ID: {person['id']} / Pillar: {pillar_label} / Wā: {person.get('wa')} / Stone: {person.get('stone')}\n")
        f.write(f"# Generated by {OLLAMA_MODEL} (local AI, zero Claude tokens)\n")
        f.write(f"# DRAFT — Jimmy review before any public release\n")
        f.write(f"# Kumulipo resonance: Wā {person.get('wa')} — cosmological framing, NOT genealogical claim\n")
        f.write(f"# TMK: {person.get('tmk', 'see catalog')} ({person.get('tmk_note', '')})\n\n")
        f.write(text)
        f.write(f"\n\n---\n")
        f.write(f"**Public record**: {person.get('public_record', 'see HAWAIIAN_PREDECESSORS.json')}\n")
        if person.get("verify"):
            f.write(f"\n**⚠ VERIFY**: Some details in this entry need local/kumu confirmation before publication.\n")
    print(f"  → saved: {fname}", flush=True)
    return outfile


def main():
    ap = argparse.ArgumentParser(description="Generate tributes for all 28 Hawaiian predecessors")
    ap.add_argument("--id",     type=int,  help="Only generate tribute for this person ID (1-28)")
    ap.add_argument("--pillar", type=str,  help="Only generate for this pillar (food_aina|sage_education|luna_truth|charter_sovereignty)")
    ap.add_argument("--dry",    action="store_true", help="Print prompts only, no Ollama")
    args = ap.parse_args()

    if not os.path.exists(CATALOG):
        print(f"[tribute-all] Catalog not found: {CATALOG}", flush=True)
        return 1

    with open(CATALOG, encoding="utf-8") as f:
        data = json.load(f)
    people = data.get("predecessors", [])

    # Filter
    if args.id:
        people = [p for p in people if p["id"] == args.id]
    elif args.pillar:
        people = [p for p in people if p["pillar"] == args.pillar]

    if not people:
        print("[tribute-all] No people matched filter.", flush=True)
        return 1

    print(f"[tribute-all] Generating {len(people)} tributes via {OLLAMA_MODEL}...", flush=True)
    print(f"[tribute-all] Estimated time: {len(people)*40//60} min {len(people)*40%60}s", flush=True)

    done, failed = [], []
    for i, person in enumerate(people, 1):
        name = person["name"]
        print(f"\n[{i}/{len(people)}] {name} (Wā {person.get('wa')}, Stone {person.get('stone')})", flush=True)
        t0 = time.time()
        text = generate_tribute(person, dry=args.dry)
        elapsed = time.time() - t0
        if text and not args.dry:
            path = save_tribute(person, text)
            done.append(name)
            print(f"  Done in {elapsed:.0f}s", flush=True)
        elif args.dry:
            done.append(name)
        else:
            print(f"  FAILED after {elapsed:.0f}s", flush=True)
            failed.append(name)

    print(f"\n[tribute-all] Complete: {len(done)} done, {len(failed)} failed", flush=True)
    if failed:
        print(f"[tribute-all] Failed: {failed}", flush=True)

    if not args.dry and done:
        dispatch_log(
            f"SHIPPED: tribute_all.py generated {len(done)} tributes for Hawaiian predecessors "
            f"(local king AI, zero Claude tokens) → docs/community/tributes/ "
            f"Pillars: food/sage/luna/charter × 7 each = 28. "
            f"Kumulipo wā + 12 Stones connected. TMK parcel references included."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
