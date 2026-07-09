#!/usr/bin/env python3
"""feature_requests.py — let the public REQUEST how the government software should work (Jimmy 2026-06-18).

Two tiers, one engine. Both sit behind a Stripe signup (so a request has a real, verified person behind it):
  • FREE / PUBLIC  — after a free Stripe Identity signup (no charge), anyone can submit a request AND
    publicly VOTE on others'. The board is sorted by AI into DEPARTMENT + AGENDA priority from the existing
    government side (the real Maui County Council committees), so the loudest idea isn't the only one heard.
  • PAID / PRIVATE — county / government users pay for PRIVATE access to build out their operations software
    privately (their build requests stay owner+requester only — never on the public board, leak-gate enforced).

This is the engine: data model + AI department classification (local Ollama :11434, keyword fallback) +
agenda-priority weighting + one-vote-per-verified-voter + tiered board output. The Stripe gate + the board
page consume it. Sourced/honest: departments + priorities come from the real committee structure, not invented.
Stdlib only (+ urllib for the local Ollama probe). Public store is publishable; PRIVATE store NEVER publishes.

API:
  submit(author, title, desc, tier, tenant, department=None) -> record
  vote(request_id, voter_id)                                  -> {ok, votes}
  classify(text)                                              -> department id          (AI or keyword)
  board(tenant)         -> {departments:[{id,label,priority,requests:[...sorted]}], generated}
  private_list(tenant)  -> [ ...paid/private build requests ]  (owner-side only)
CLI: python feature_requests.py --demo   |   --board [--tenant hi-maui]
"""
import os, sys, re, json, time, hashlib, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(os.path.dirname(HERE))
PUB_STORE = os.path.join(PROJ, "reports", "feature_requests", "requests_public.jsonl")     # publishable (sanitized)
PRIV_STORE = os.path.join(PROJ, "reports", "_status", "feature_requests_private.jsonl")     # NEVER published
VOTES = os.path.join(PROJ, "reports", "feature_requests", "votes.json")

# DEPARTMENTS = the real Maui County Council committees (the gov-side priority structure) + core ops depts.
# Each carries the keywords that route a free-text request to it when the local AI is unavailable.
DEPARTMENTS = [
    ("budget_finance",   "Budget, Finance & Economic Development", ["budget", "finance", "tax", "fee", "economic", "procurement", "contract", "grant", "fund", "revenue", "audit"]),
    ("housing_land",     "Housing & Land Use",                     ["housing", "land", "zoning", "permit", "build", "development", "rent", "affordable", "parcel", "tmk", "subdivision"]),
    ("water_parks",      "Water Authority, Social Services & Parks", ["water", "park", "social service", "recreation", "beach", "irrigation", "well", "wastewater", "sewer", "homeless"]),
    ("disaster_intl",    "Disaster Recovery & International Affairs", ["disaster", "fire", "recovery", "rebuild", "lahaina", "emergency", "hazard", "resilience", "wildfire", "relief"]),
    ("govrel_ethics",    "Government Relations, Ethics & Transparency", ["ethics", "transparency", "open data", "records", "disclosure", "lobby", "conflict", "recusal", "sunshine", "testify", "vote"]),
    ("public_works",     "Public Works & Infrastructure",          ["road", "infrastructure", "traffic", "bridge", "drainage", "sidewalk", "transit", "bus", "pothole", "street"]),
    ("planning_permit",  "Planning & Permitting",                  ["planning", "permitting", "inspection", "plan review", "code enforcement", "violation", "shoreline"]),
    ("clerk_elections",  "County Clerk & Elections",               ["election", "ballot", "voter registration", "clerk", "agenda", "minutes", "meeting"]),
    ("ops_it",           "Operations & Technology",                ["software", "system", "app", "online", "portal", "digital", "automate", "dashboard", "data", "api", "website", "form"]),
]
_DEPT_IDS = [d[0] for d in DEPARTMENTS]
_DEPT_LABEL = {d[0]: d[1] for d in DEPARTMENTS}
_DEPT_KW = {d[0]: d[2] for d in DEPARTMENTS}


def _now():
    return int(time.time())


def _rid(author, title):
    return "fr_" + hashlib.sha1(("%s|%s|%s" % (author, title, _now())).encode()).hexdigest()[:12]


def _read_jsonl(path):
    out = []
    if os.path.exists(path):
        for line in open(path, encoding="utf-8"):
            line = line.strip()
            if line:
                try: out.append(json.loads(line))
                except Exception: pass
    return out


def _append_jsonl(path, rec):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


# ── AI / keyword department classification ──────────────────────────────────────────────────
def _ollama_classify(text):
    try:
        prompt = ("Classify this resident request into ONE government department id from this list "
                  "%s. Reply with ONLY the id, nothing else. Request: %r" % (json.dumps(_DEPT_IDS), text[:400]))
        body = json.dumps({"model": __import__("os").environ.get("OLLAMA_MODEL","llama3.1:8b"), "prompt": prompt, "stream": False,
                           "think": False, "options": {"temperature": 0, "num_gpu": 0}}).encode()
        req = urllib.request.Request("http://127.0.0.1:11434/api/generate", data=body,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=20) as r:
            _d = json.loads(r.read().decode())
            resp = _d.get("response") or _d.get("thinking") or ""
        for did in _DEPT_IDS:
            if did in resp:
                return did
    except Exception:
        pass
    return None


def _keyword_classify(text):
    t = (text or "").lower()
    best, score = "ops_it", 0
    for did, kws in _DEPT_KW.items():
        s = sum(1 for k in kws if k in t)
        if s > score:
            best, score = did, s
    return best


def classify(text):
    """Free text -> department id. Local AI (Ollama) first, keyword fallback (default ops_it)."""
    return _ollama_classify(text) or _keyword_classify(text)


# ── agenda priority (depts with a near upcoming agenda rank higher) ──────────────────────────
_COMMITTEE_DEPT = {
    "budget-finance": "budget_finance", "housing-and-land": "housing_land",
    "water-authority": "water_parks", "disaster-recovery": "disaster_intl",
    "government-relations": "govrel_ethics",
}

def _agenda_priority():
    """{dept_id: weight} — a small boost for departments whose committee has an upcoming/recent agenda."""
    pri = {}
    import glob
    for p in glob.glob(os.path.join(PROJ, "reports", "_status", "agenda_reels", "agenda_maui_*")):
        leaf = os.path.basename(p)
        for frag, did in _COMMITTEE_DEPT.items():
            if frag in leaf:
                pri[did] = pri.get(did, 0) + 1
    for p in glob.glob(os.path.join(PROJ, "reports", "_status", "agenda_posts", "agenda_*.json")):
        try:
            j = json.load(open(p, encoding="utf-8"))
            board = (j.get("board") or "").lower()
            for frag, did in _COMMITTEE_DEPT.items():
                if frag.split("-")[0] in board:
                    pri[did] = pri.get(did, 0) + 2     # an actual upcoming post weighs more
        except Exception:
            pass
    return pri


# ── submit / vote ────────────────────────────────────────────────────────────────────────────
def submit(author, title, desc, tier="free_public", tenant="hi-maui", department=None):
    """Record a request. tier 'free_public' (votable board) or 'paid_private' (owner-side build request)."""
    dept = department or classify("%s. %s" % (title, desc))
    rec = {"id": _rid(author, title), "author": author, "title": str(title)[:140],
           "desc": str(desc)[:2000], "tier": tier, "tenant": tenant, "department": dept,
           "department_label": _DEPT_LABEL.get(dept, dept), "status": "open",
           "votes": 0, "created": _now()}
    _append_jsonl(PRIV_STORE if tier == "paid_private" else PUB_STORE, rec)
    return rec


def vote(request_id, voter_id):
    """One vote per verified voter on a PUBLIC request. Returns {ok, votes}."""
    os.makedirs(os.path.dirname(VOTES), exist_ok=True)
    try: v = json.load(open(VOTES, encoding="utf-8"))
    except Exception: v = {}
    voters = set(v.get(request_id, []))
    if voter_id in voters:
        return {"ok": False, "votes": len(voters), "reason": "already voted"}
    voters.add(voter_id)
    v[request_id] = sorted(voters)
    tmp = VOTES + ".tmp"; json.dump(v, open(tmp, "w", encoding="utf-8")); os.replace(tmp, VOTES)
    return {"ok": True, "votes": len(voters)}


def _vote_counts():
    try: v = json.load(open(VOTES, encoding="utf-8"))
    except Exception: v = {}
    return {rid: len(voters) for rid, voters in v.items()}


# ── boards ─────────────────────────────────────────────────────────────────────────────────
def board(tenant="hi-maui"):
    """Public board: requests grouped by DEPARTMENT, departments ordered by agenda priority, requests
    within a department ranked by live votes. This is the AI-sorted, agenda+department-prioritized view."""
    reqs = [r for r in _read_jsonl(PUB_STORE) if r.get("tenant", tenant) == tenant and r.get("tier") == "free_public"]
    counts = _vote_counts(); pri = _agenda_priority()
    for r in reqs:
        r["votes"] = counts.get(r["id"], r.get("votes", 0))
    groups = {}
    for r in reqs:
        groups.setdefault(r["department"], []).append(r)
    out = []
    for did, label, _kw in DEPARTMENTS:
        rs = sorted(groups.get(did, []), key=lambda x: -x["votes"])
        if rs:
            out.append({"id": did, "label": label, "priority": pri.get(did, 0), "requests": rs})
    out.sort(key=lambda g: (-g["priority"], -sum(r["votes"] for r in g["requests"])))
    return {"tenant": tenant, "generated": _now(), "departments": out,
            "total": len(reqs), "note": "Sorted by department + agenda priority from the government side; ranked by public votes."}


def private_list(tenant="hi-maui"):
    """Paid/private build requests — owner + requesting county user only. NEVER published."""
    return [r for r in _read_jsonl(PRIV_STORE) if r.get("tenant", tenant) == tenant]


def main():
    import argparse
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--board", action="store_true")
    ap.add_argument("--tenant", default="hi-maui")
    a = ap.parse_args()
    if a.demo:
        for au, ti, de, tier in [
            ("verified:resident1", "Online permit status tracker", "Let me check my building permit status online without calling.", "free_public"),
            ("verified:resident2", "Lahaina rebuild dashboard", "One place to see fire-recovery permit progress and timelines.", "free_public"),
            ("verified:resident3", "Searchable budget by department", "Download the budget data behind the charts.", "free_public"),
            ("county:planning_dept", "Internal plan-review queue tool", "Private workflow tool for our plan reviewers.", "paid_private")]:
            r = submit(au, ti, de, tier); print("submitted [%s] %s -> %s" % (tier, ti, r["department_label"]))
        vote(_read_jsonl(PUB_STORE)[-1]["id"], "verified:resident9")
    if a.board or a.demo:
        b = board(a.tenant)
        print("\nPUBLIC BOARD (%s) — %d requests" % (a.tenant, b["total"]))
        for g in b["departments"]:
            print("  [%s pri=%d] %s" % (g["id"], g["priority"], g["label"]))
            for r in g["requests"]:
                print("      %3d votes  %s" % (r["votes"], r["title"]))
        print("\nPRIVATE build requests (owner-side, never public): %d" % len(private_list(a.tenant)))
    return 0


if __name__ == "__main__":
    if sys.platform == "win32":
        import io; sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(main())
