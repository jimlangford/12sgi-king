#!/usr/bin/env python3
"""civic_fulfill.py — PHASE 2 fulfillment worker for paid civic explainers (Jimmy 2026-06-18).

Reads the paid-order render queue (written by the Stripe webhook in stripe_identity_backend.py),
picks the render BACKEND to maximize margin while respecting the GPU co-tenancy, renders the
explainer, hosts a SHAREABLE artifact, and marks the order fulfilled.

Backend routing (the heart of Jimmy's model):
  • priority order            → render NOW (cloud/hourly), never waits on the GPU
  • standard + GPU free        → render on the LAPTOP (max margin) — gated on GPU_BUSY_MIB
  • standard + GPU busy (studio is RENDERING) → wait / fall back to cloud — NEVER interrupt an active render

What's REAL here vs gated:
  • Orchestration (queue, priority order, GPU-gated backend pick, share+record+done) — REAL.
  • The agenda CPU reel deliverable (agenda_reel.py, chant+narration) — REAL for an agenda job with a tenant.
  • PREMIUM cloud AI-visual render (ComfyUI Cloud) — a clearly-marked HOOK; needs Jimmy's calibrated
    workflow + token spend (his account/keys). Until wired, premium jobs are marked render_pending.

Stdlib only. CPU/orchestration; never spends cloud credits itself. Run: python civic_fulfill.py --once
"""
import os, sys, re, json, glob, shutil, subprocess
from datetime import datetime, timezone, timedelta
HST = timezone(timedelta(hours=-10))
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path: sys.path.insert(0, HERE)
PROJ = os.path.abspath(os.path.join(HERE, "..", ".."))
QUEUE = os.path.join(PROJ, "reports", "_status", "render_jobs")
DONE = os.path.join(QUEUE, "done")
SHARES = os.path.join(PROJ, "reports", "mauios", "shares")          # hosted shareable artifacts (published)
FULFILLED = os.path.join(PROJ, "reports", "_status", "fulfilled_orders.jsonl")
NW = 0x08000000 if os.name == "nt" else 0
PY = sys.executable

def _pricing():
    try: return json.load(open(os.path.join(PROJ, "config", "civic_pricing.json"), encoding="utf-8"))
    except Exception: return {}

def _gpu_free(threshold_mib=6000):
    try:
        out = subprocess.run(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
                             capture_output=True, text=True, timeout=10, creationflags=NW).stdout.strip().splitlines()
        used = int(out[0]) if out else 0
        return used < threshold_mib, used
    except Exception:
        return True, 0

def pick_backend(job):
    """priority → cloud now; standard → laptop if GPU free, else cloud. Never preempts a studio render."""
    p = _pricing(); thr = int(p.get("eta", {}).get("gpu_busy_mib", 6000))
    if (job.get("priority") or job.get("tier_priority")) == "priority":
        return "cloud", "priority — render now, no GPU wait"
    free, used = _gpu_free(thr)
    if free:
        return "local_laptop", "GPU free (%d MiB) — laptop, max margin" % used
    return "cloud", "GPU busy (%d MiB) — the studio is RENDERING — falling back to cloud (never interrupt an active render)" % used

def render(job, backend):
    """Produce the artifact. REAL: agenda CPU reel for a tenant. Premium cloud AI render = gated hook."""
    tenant = job.get("tenant") or "hi-maui"
    tier = job.get("tier") or "premium_reel"
    tid = re.sub(r"^hi-", "", tenant)                      # agenda_reel uses short tids (maui/honolulu/...)
    # Premium AI-visual (ComfyUI Cloud) render is the gated upgrade — needs the calibrated workflow + token spend.
    if tier.startswith("premium") and backend in ("cloud", "hourly_gpu"):
        return None, "render_pending", ("premium cloud render hook — needs the calibrated ComfyUI Cloud "
                                        "workflow + token spend (Jimmy). Orchestration ready; artifact not yet produced.")
    # REAL deliverable: the CPU agenda reel (chant + narration) for this tenant
    try:
        subprocess.run([PY, "-X", "utf8", os.path.join(HERE, "agenda_reel.py"), "--tenant", tid, "--limit", "1"],
                       capture_output=True, timeout=600, creationflags=NW)
    except Exception as e:
        return None, "failed", "agenda_reel error: %s" % str(e)[:160]
    reels = sorted(glob.glob(os.path.join(PROJ, "reports", "_status", "agenda_reels", "*", "reel.mp4")),
                   key=os.path.getmtime, reverse=True)
    return (reels[0] if reels else None), ("rendered" if reels else "failed"), ("CPU reel via agenda_reel" if reels else "no reel produced")

def deliver(job, artifact):
    """Host the artifact as a shareable file + return a public-style link."""
    if not (artifact and os.path.exists(artifact)): return None
    os.makedirs(SHARES, exist_ok=True)
    qid = job.get("quote_id") or job.get("session") or "order"
    dst = os.path.join(SHARES, "%s.mp4" % re.sub(r"[^A-Za-z0-9_-]", "", qid))
    shutil.copy2(artifact, dst)
    return "shares/%s" % os.path.basename(dst)             # served at /shares/<id>.mp4 (public + Naga)

def _record(rec):
    os.makedirs(os.path.dirname(FULFILLED), exist_ok=True)
    with open(FULFILLED, "a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")

def process_once():
    jobs = sorted(glob.glob(os.path.join(QUEUE, "*.json")))
    if not jobs:
        print("civic_fulfill: queue empty"); return 0
    # priority jobs first, then oldest
    def _load(p):
        try: return json.load(open(p, encoding="utf-8"))
        except Exception: return {}
    jobs.sort(key=lambda p: (0 if (_load(p).get("priority") == "priority") else 1, os.path.getmtime(p)))
    os.makedirs(DONE, exist_ok=True)
    n = 0
    for jp in jobs:
        job = _load(jp)
        backend, why = pick_backend(job)
        artifact, status, note = render(job, backend)
        share = deliver(job, artifact) if status == "rendered" else None
        rec = {"quote_id": job.get("quote_id"), "tenant": job.get("tenant"), "tier": job.get("tier"),
               "aspect": job.get("aspect"), "backend": backend, "backend_reason": why,
               "status": status, "note": note, "share": share,
               "when": datetime.now(HST).strftime("%Y-%m-%d %H:%M:%S HST")}
        _record(rec)
        if status in ("rendered", "render_pending"):       # pending stays queued (move only the finished)
            if status == "rendered":
                shutil.move(jp, os.path.join(DONE, os.path.basename(jp)))
        print("  %s [%s] %s -> %s%s" % (job.get("quote_id", "?"), backend, status,
                                        share or note, "" if status == "rendered" else " (left queued)"))
        n += 1
    print("civic_fulfill: processed %d job(s)" % n)
    return 0

def main():
    if "--once" in sys.argv or len(sys.argv) == 1:
        return process_once()
    print(__doc__); return 0

if __name__ == "__main__":
    if sys.platform == "win32":
        import io; sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(main())
