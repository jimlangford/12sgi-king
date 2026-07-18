import subprocess, re

for model in ["king-reason:latest", "king-workboard:latest", "king-web:latest"]:
    r = subprocess.run(["ollama","show","--modelfile",model], capture_output=True, text=True, timeout=15)
    text = r.stdout
    nav_found = "NAVIGATION CANON" in text
    # count SYSTEM blocks
    sys_blocks = len(re.findall(r'SYSTEM\s+"""', text))
    # find where nav is (or isn't)
    idx = text.find("NAVIGATION CANON")
    # show tail of system block
    m = re.search(r'SYSTEM\s+"""(.*?)"""', text, re.DOTALL)
    tail = m.group(1)[-200:] if m else "(no match)"
    print(f"\n{'='*60}")
    print(f"Model: {model}")
    print(f"  Nav canon present: {nav_found} (at char {idx})")
    print(f"  SYSTEM blocks: {sys_blocks}")
    print(f"  Total Modelfile length: {len(text)}")
    print(f"  System block tail: {repr(tail)}")
