import subprocess, re, os

# king-reason: rebase from qwen3:1.7b -> qwen3:4b
# king-web: rebase from gemma3 -> qwen3:4b
# king-workboard: scrub the Tailscale hostname from system prompt

QWEN4B_BLOB = "sha256-3e4cb14174460404e7a233e531675303b2fbf7749c02f91864fe311ab6344e4f"
GEMMA3_BLOB = "sha256-aeda25e63ebd698fab8638ffb778e68bed908b960d39d0becc650fa981609d25"
QWEN17B_BLOB = "sha256-3d0b790534fe4b79525fc3692950408dca41171676ed7e21db57af5c65ef6ab6"

QWEN4B_FROM = r"FROM C:\Users\12sgi\.ollama\models\blobs\" + QWEN4B_BLOB

# qwen3:4b uses different stop tokens and template than gemma3
QWEN4B_STOPS = """PARAMETER stop <|im_start|>
PARAMETER stop <|im_end|>"""
GEMMA3_STOPS = """PARAMETER stop <end_of_turn>"""

def rebuild(model, new_mf):
    short = model.replace(":latest", "")
    path = f"_mf_{short}.tmp"
    with open(path, "w", encoding="utf-8") as f:
        f.write(new_mf)
    r = subprocess.run(["ollama", "create", short, "-f", path],
                       capture_output=True, text=True, timeout=60)
    os.remove(path)
    status = "OK" if r.returncode == 0 else f"FAIL: {r.stderr[:60]}"
    print(f"  {status}: {model}")

# ── king-reason: rebase to qwen3:4b ─────────────────────────────────────────
r = subprocess.run(["ollama","show","--modelfile","king-reason:latest"],
                   capture_output=True, text=True, timeout=15)
mf = r.stdout
mf = re.sub(r"FROM [^\n]+", lambda m: QWEN4B_FROM, mf, count=1)
# swap gemma3 stop for qwen3 stop if present
mf = mf.replace(GEMMA3_STOPS, QWEN4B_STOPS)
if QWEN4B_STOPS not in mf:
    mf = mf.rstrip() + "\n" + QWEN4B_STOPS + "\n"
rebuild("king-reason:latest", mf)

# ── king-web: rebase to qwen3:4b ─────────────────────────────────────────────
r = subprocess.run(["ollama","show","--modelfile","king-web:latest"],
                   capture_output=True, text=True, timeout=15)
mf = r.stdout
mf = re.sub(r"FROM [^\n]+", QWEN4B_FROM, mf, count=1)
mf = mf.replace(GEMMA3_STOPS, QWEN4B_STOPS)
if QWEN4B_STOPS not in mf:
    mf = mf.rstrip() + "\n" + QWEN4B_STOPS + "\n"
rebuild("king-web:latest", mf)

# ── king-workboard: scrub Tailscale hostname from system prompt ───────────────
r = subprocess.run(["ollama","show","--modelfile","king-workboard:latest"],
                   capture_output=True, text=True, timeout=15)
mf = r.stdout
# remove any .ts.net hostnames (they appear in the system prompt as examples)
mf_clean = re.sub(r'\b\w+\.tail\w+\.ts\.net\b', '[PRIVATE-TAILSCALE-HOST]', mf)
if mf_clean != mf:
    print("  Scrubbed Tailscale hostname from king-workboard system prompt")
rebuild("king-workboard:latest", mf_clean)

print("\nDone.")
