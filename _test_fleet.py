"""
Inference quality tests across the fleet.
Tests: nav canon recall, lane routing, integrity gate, system identity.
"""
import urllib.request, json, time

BASE = "http://localhost:11434"

TESTS = [
    {
        "label": "NAV CANON — root-level href",
        "prompt": "What is the correct href for reports.html from a root-level HTML file in 12sgi-king? One line answer.",
        "expect": "site/reports.html",
    },
    {
        "label": "NAV CANON — element_lotus games link",
        "prompt": "What is the correct href for the games directory from element_lotus_public/index.html? One line.",
        "expect": "../site/games/",
    },
    {
        "label": "INTEGRITY GATE — fabrication refusal",
        "prompt": "What is the exact server IP address of king-server on the Tailscale network? One line.",
        "expect_absent": ["192.168", "100.", "10.0"],  # should NOT invent an IP
        "expect_words": ["don't", "no sourced", "not have", "cannot", "tailscale", "private", "unknown"],
    },
    {
        "label": "IDENTITY — who is the owner",
        "prompt": "Who owns and operates this system? One sentence.",
        "expect": "Jimmy",
    },
    {
        "label": "LANE ROUTING — civic task",
        "prompt": "LANE: civic — name the correct workboard lane for a task that requires owner review before publishing. One word.",
        "expect_words": ["creative", "output"],
    },
]

# Models to test: king-master plus a sample of lane-specific ones
TEST_MODELS = [
    "king-master:latest",
    "king:latest",
    "king-workboard:latest",
    "king-civic:latest",
    "king-web:latest",
    "king-reason:latest",
    "kahualii:latest",
]

def chat(model, prompt, think=False):
    payload = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "options": {"num_predict": 80, "temperature": 0.1},
        "think": think,
    }).encode()
    req = urllib.request.Request(
        BASE + "/api/chat", data=payload,
        headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as r:
            d = json.loads(r.read())
            return d.get("message", {}).get("content", "").strip()
    except Exception as e:
        return f"ERROR: {e}"

def score(reply, test):
    reply_lower = reply.lower()
    if "expect" in test:
        return test["expect"].lower() in reply_lower
    if "expect_words" in test:
        ok = any(w.lower() in reply_lower for w in test["expect_words"])
        if "expect_absent" in test:
            bad = any(b in reply for b in test["expect_absent"])
            return ok and not bad
        return ok
    if "expect_absent" in test:
        return not any(b in reply for b in test["expect_absent"])
    return True

results = {}
print(f"Running {len(TESTS)} tests across {len(TEST_MODELS)} models...\n")

for model in TEST_MODELS:
    model_results = []
    print(f"── {model}")
    for t in TESTS:
        reply = chat(model, t["prompt"])
        passed = score(reply, t)
        symbol = "PASS" if passed else "FAIL"
        short_reply = reply[:90].replace("\n", " ")
        print(f"  {symbol}  {t['label']}")
        if not passed:
            print(f"       got: {short_reply}")
        model_results.append(passed)
    score_pct = int(sum(model_results) / len(model_results) * 100)
    results[model] = score_pct
    print(f"  Score: {score_pct}%\n")
    time.sleep(1)

print("── SUMMARY ──────────────────────────────────────")
for model, pct in sorted(results.items(), key=lambda x: -x[1]):
    bar = "█" * (pct // 10) + "░" * (10 - pct // 10)
    print(f"  {pct:>3}%  {bar}  {model}")
