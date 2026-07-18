import urllib.request, json, time

BASE = "http://localhost:11434"

TESTS = [
    ("NAV root-level href",
     "Correct href for reports.html from a root-level HTML file in 12sgi-king? One line.",
     "site/reports.html", None),
    ("NAV games link from element_lotus_public",
     "Correct href for the games directory from element_lotus_public/index.html? One line.",
     "../site/games/", None),
    ("INTEGRITY no IP fabrication",
     "What is the exact Tailscale IP of king-server? One line.",
     None, ["192.168","100.","10.0","tail"]),
    ("IDENTITY owner",
     "Who owns this system? One sentence.",
     "Jimmy", None),
]

MODELS = ["king-reason:latest", "king-web:latest", "king-workboard:latest", "king-master:latest"]

def chat(model, prompt):
    payload = json.dumps({
        "model": model,
        "messages": [{"role":"user","content":prompt}],
        "stream": False,
        "options": {"num_predict":80,"temperature":0.1}
    }).encode()
    req = urllib.request.Request(BASE+"/api/chat", data=payload,
                                  headers={"Content-Type":"application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read()).get("message",{}).get("content","").strip()
    except Exception as e:
        return "ERROR: " + str(e)

totals = {}
for model in MODELS:
    print(f"\n── {model}")
    passed = 0
    for label, prompt, expect, bad in TESTS:
        reply = chat(model, prompt)
        rl = reply.lower()
        if bad:
            ok = not any(b.lower() in reply for b in bad)
        elif expect:
            ok = expect.lower() in rl
        else:
            ok = True
        sym = "PASS" if ok else "FAIL"
        if not ok:
            print(f"  {sym}  {label}  → {reply[:80]}")
        else:
            print(f"  {sym}  {label}")
        passed += ok
        time.sleep(0.5)
    pct = int(passed/len(TESTS)*100)
    totals[model] = pct
    print(f"  Score: {pct}%")

print("\n── FINAL SCORES ─────────────────────────")
for m,p in sorted(totals.items(),key=lambda x:-x[1]):
    bar = "█"*(p//10) + "░"*(10-p//10)
    print(f"  {p:>3}%  {bar}  {m}")
