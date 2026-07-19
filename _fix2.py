import re, subprocess, os

QWEN4B_BLOB = "sha256-3e4cb14174460404e7a233e531675303b2fbf7749c02f91864fe311ab6344e4f"
QWEN4B_FROM = "FROM C:\\Users\\12sgi\\.ollama\\models\\blobs\\" + QWEN4B_BLOB
QWEN4B_STOPS = "PARAMETER stop <|im_start|>\nPARAMETER stop <|im_end|>"
GEMMA3_STOPS = "PARAMETER stop <end_of_turn>"

def rebuild(model, mf):
    short = model.replace(":latest", "")
    path = "_mf_" + short + ".tmp"
    with open(path, "w", encoding="utf-8") as f:
        f.write(mf)
    r = subprocess.run(["ollama", "create", short, "-f", path],
                       capture_output=True, text=True, timeout=60)
    os.remove(path)
    status = "OK" if r.returncode == 0 else ("FAIL: " + r.stderr[:60])
    print("  " + status + ": " + model)

# Rebase king-reason and king-web to qwen3:4b
for model in ["king-reason:latest", "king-web:latest"]:
    r = subprocess.run(["ollama", "show", "--modelfile", model],
                       capture_output=True, text=True, timeout=15)
    mf = r.stdout
    mf = re.sub(r"FROM [^\n]+", lambda _: QWEN4B_FROM, mf, count=1)
    mf = mf.replace(GEMMA3_STOPS, QWEN4B_STOPS)
    if "<|im_start|>" not in mf:
        mf = mf.rstrip() + "\n" + QWEN4B_STOPS + "\n"
    rebuild(model, mf)

# Scrub Tailscale hostname from king-workboard
r = subprocess.run(["ollama", "show", "--modelfile", "king-workboard:latest"],
                   capture_output=True, text=True, timeout=15)
mf = r.stdout
cleaned = re.sub(r"\w+\.tail\w+\.ts\.net", "[PRIVATE-TAILSCALE-HOST]", mf)
if cleaned != mf:
    print("  Scrubbed Tailscale hostname from king-workboard system prompt")
rebuild("king-workboard:latest", cleaned)
print("Done.")
