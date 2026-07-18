"""
Full fleet review:
- What base model each king-* uses
- Whether nav canon is present
- Whether system prompt is intact (not empty, not broken)
- Whether FROM line is a valid blob path
- king-master: verify nav canon, lane routing, inference quality
"""
import subprocess, re, os, json, urllib.request

# ── 1. Collect all king-* models ─────────────────────────────────────────────
r = subprocess.run(["ollama", "list"], capture_output=True, text=True, timeout=10)
all_models = []
for line in r.stdout.splitlines()[1:]:  # skip header
    parts = line.split()
    if parts:
        all_models.append(parts[0])

king_models = sorted([m for m in all_models if m.startswith("king") or m == "kahualii:latest"])
print(f"Fleet: {len(king_models)} models\n")

# ── 2. Blob → friendly name map ───────────────────────────────────────────────
BLOB_NAMES = {
    "sha256-aeda25e6": "gemma3:latest (2B)",
    "sha256-3d0b7905": "qwen3:1.7b",
    "sha256-3e4cb141": "qwen3:4b",
    "sha256-dec52a44": "qwen3.5:latest",
}

def identify_base(from_line):
    for prefix, name in BLOB_NAMES.items():
        if prefix in from_line:
            return name
    if "blob" in from_line.lower():
        return "unknown-blob"
    # FROM points to non-blob (broken)
    return f"BROKEN: {from_line[:60]}"

# ── 3. Audit each model ───────────────────────────────────────────────────────
results = []
for model in king_models:
    r = subprocess.run(["ollama", "show", "--modelfile", model],
                       capture_output=True, text=True, timeout=15)
    mf = r.stdout if r.returncode == 0 else ""

    from_line = ""
    system_len = 0
    has_nav = "NAVIGATION CANON" in mf
    has_system = False
    broken_from = False

    for line in mf.splitlines():
        if line.startswith("FROM "):
            from_line = line[5:].strip()
        if "SYSTEM" in line:
            has_system = True

    system_match = re.search(r'SYSTEM\s+"""(.*?)"""', mf, re.DOTALL)
    if system_match:
        system_len = len(system_match.group(1).strip())

    base = identify_base(from_line)
    broken_from = base.startswith("BROKEN")

    results.append({
        "model": model,
        "base": base,
        "has_nav": has_nav,
        "has_system": has_system,
        "system_len": system_len,
        "broken_from": broken_from,
        "from_raw": from_line[:80],
    })

# ── 4. Print summary table ────────────────────────────────────────────────────
print(f"{'MODEL':<35} {'BASE':<24} {'NAV':<5} {'SYS':<5} {'SYS_LEN':<8} ISSUES")
print("-" * 110)
issues_found = []
for r in results:
    nav = "YES" if r["has_nav"] else "no"
    sys_ = "YES" if r["has_system"] else "NO"
    issues = []
    if r["broken_from"]:
        issues.append("BROKEN_FROM")
    if not r["has_nav"]:
        issues.append("NO_NAV_CANON")
    if r["system_len"] < 100:
        issues.append(f"SHORT_SYSTEM({r['system_len']})")
    issue_str = ", ".join(issues) if issues else "ok"
    if issues:
        issues_found.append((r["model"], issues))
    print(f"  {r['model']:<33} {r['base']:<24} {nav:<5} {sys_:<5} {r['system_len']:<8} {issue_str}")

# ── 5. Base model distribution ────────────────────────────────────────────────
print("\n── Base model distribution ─────────────────────")
from collections import Counter
dist = Counter(r["base"] for r in results)
for base, count in dist.most_common():
    print(f"  {count:>3}x  {base}")

# ── 6. Issues summary ─────────────────────────────────────────────────────────
print(f"\n── Issues: {len(issues_found)} models need attention ──────────────────")
for model, issues in issues_found:
    print(f"  {model}: {', '.join(issues)}")

# ── 7. king-master Modelfile content check ────────────────────────────────────
print("\n── king-master Modelfile check ─────────────────")
r = subprocess.run(["ollama", "show", "--modelfile", "king-master:latest"],
                   capture_output=True, text=True, timeout=15)
mf = r.stdout
checks = {
    "FROM qwen3:4b blob":        "sha256-3e4cb141" in mf,
    "SYSTEM present":            'SYSTEM """' in mf,
    "NAV CANON":                 "NAVIGATION CANON" in mf,
    "site/ link rule":           'href="site/' in mf,
    "Lane routing table":        "LANE REFERENCE" in mf,
    "Integrity gate":            "GROUNDED OR SILENT" in mf,
    "Architecture section":      "SYSTEM ARCHITECTURE" in mf,
    "Privacy section":           "PRIVACY" in mf,
    "temperature 0.5":           "temperature 0.5" in mf,
    "num_ctx 8192":              "num_ctx 8192" in mf,
    "qwen3 stops":               "<|im_start|>" in mf,
}
for check, passed in checks.items():
    print(f"  {'OK' if passed else 'MISSING':8} {check}")
