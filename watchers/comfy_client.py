#!/usr/bin/env python3
"""comfy_client.py — a managed ComfyUI render-hub client for the PAID studio-civic render path
(Jimmy 2026-06-18; codifies the ComfyUI-as-a-service best practices researched this session).

This is the LOCAL `RenderBackend` the civic_fulfill dispatcher uses to talk to ComfyUI on :8000 when
the GPU is free (it never interrupts an active render — pick_backend enforces that). The cloud backend
is a sibling impl (fal / RunComfy / Comfy Deploy) wired separately and gated on keys.

Best-practice contract (from the official ComfyUI API + ViewComfy/9elements/Runflow production guides):
  • submit:    POST /prompt {prompt:<API-FORMAT json>, client_id, [extra_data], [front:true]} -> {prompt_id, number}
  • track:     completion is the WS sentinel `executing` with node==None for THIS prompt_id — NOT `executed`.
               We also support a stdlib POLLING tracker (/queue position + /history presence) when the
               optional `websocket-client` package isn't installed. Either way: read outputs ONLY from /history.
  • outputs:   GET /history/{prompt_id} -> outputs.<node_id>.images|gifs|videos[] -> GET /view?filename=...
  • recover:   POST /free {unload_models:true, free_memory:true} to release VRAM; NEVER /interrupt a job we don't own.
  • gate:      GET /system_stats for free VRAM; require free >= job peak (the GPU_BUSY_MIB co-tenant rule) before submit.
  • expedite:  `front:true` jumps the queue — the paid expedite tier.
The ComfyUI queue is IN-MEMORY: callers MUST keep a durable job ledger and re-enqueue on restart.
Stdlib only (urllib); live per-step progress is an optional upgrade when `websocket` is importable.
"""
import os, sys, json, time, uuid, urllib.request, urllib.parse

HOST = os.environ.get("COMFY_HOST", "127.0.0.1:8000")
BASE = "http://%s" % HOST


def _get(path, timeout=15):
    with urllib.request.urlopen(BASE + path, timeout=timeout) as r:
        return json.load(r)


def _post(path, obj, timeout=30):
    data = json.dumps(obj).encode()
    req = urllib.request.Request(BASE + path, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        body = r.read()
        return json.loads(body) if body else {}


# ---- health / readiness / VRAM gate -------------------------------------------------------------
def ready():
    """ComfyUI READINESS = /system_stats 200 (not port-open). Cold-start grace is the caller's job."""
    try:
        _get("/system_stats", timeout=6); return True
    except Exception:
        return False


def system_stats():
    try:
        return _get("/system_stats", timeout=8)
    except Exception:
        return {}


def vram_free_mib():
    """Free VRAM on the first CUDA device, in MiB (-1 if unknown). Use to gate submits."""
    st = system_stats()
    for d in (st.get("devices") or []):
        if "cuda" in str(d.get("type", "")).lower() or d.get("index") == 0:
            free = d.get("vram_free")
            if isinstance(free, (int, float)):
                return int(free / (1024 * 1024))
    return -1


def can_submit(job_peak_mib):
    """True if free VRAM covers the job's measured peak. Honest: unknown VRAM -> let the caller decide."""
    free = vram_free_mib()
    if free < 0:
        return None, "VRAM unknown"
    return (free >= job_peak_mib), "free=%dMiB need=%dMiB" % (free, job_peak_mib)


# ---- queue ------------------------------------------------------------------------------------
def queue_state():
    """{'running':[prompt_id...], 'pending':[prompt_id...]} — for 'N ahead of you' UX + never-interrupt checks."""
    try:
        q = _get("/queue", timeout=8)
    except Exception:
        return {"running": [], "pending": []}
    def _ids(items):
        out = []
        for it in items or []:
            # queue entries are [number, prompt_id, prompt, extra, outputs]
            if isinstance(it, list) and len(it) >= 2:
                out.append(it[1])
        return out
    return {"running": _ids(q.get("queue_running")), "pending": _ids(q.get("queue_pending"))}


def position(prompt_id):
    """How many jobs are ahead of this one (0 = running/next). None if not found in the queue."""
    qs = queue_state()
    if prompt_id in qs["running"]:
        return 0
    if prompt_id in qs["pending"]:
        return 1 + qs["pending"].index(prompt_id)
    return None


# ---- submit -----------------------------------------------------------------------------------
def submit(workflow_api, client_id=None, front=False, extra_data=None):
    """Queue an API-FORMAT workflow. Returns (prompt_id, client_id) or raises on validation error.
    workflow_api MUST be the API-format graph (node-id -> {class_type, inputs}), NOT the UI export."""
    client_id = client_id or uuid.uuid4().hex
    payload = {"prompt": workflow_api, "client_id": client_id}
    if front:
        payload["front"] = True                 # paid expedite: jump the queue
    if extra_data:
        payload["extra_data"] = extra_data
    resp = _post("/prompt", payload)             # 400 -> urllib raises HTTPError with node_errors body
    pid = resp.get("prompt_id")
    if not pid:
        raise RuntimeError("no prompt_id returned: %s" % json.dumps(resp)[:200])
    return pid, client_id


# ---- track (poll; WS upgrade if available) ----------------------------------------------------
def _history_entry(prompt_id):
    try:
        h = _get("/history/%s" % urllib.parse.quote(prompt_id), timeout=10)
        return h.get(prompt_id)
    except Exception:
        return None


def track(prompt_id, client_id=None, on_progress=None, budget_s=1800, poll_s=3):
    """Block until the job finishes. Returns {'status': 'completed'|'error'|'timeout', 'detail':...}.

    Completion is detected from /history (the durable record): the entry appears with a status once the
    prompt has run. /queue gives live position. If `websocket` is installed we also stream real progress
    (sampler step %, node) via the official WS sentinel; otherwise we poll. Either path reads outputs from /history."""
    t0 = time.time()
    # Optional: live progress over the official WS (executing node==None for our prompt_id = done)
    try:
        import websocket  # type: ignore  (websocket-client) — optional
        ws = websocket.create_connection("ws://%s/ws?clientId=%s" % (HOST, client_id or ""), timeout=10)
        try:
            while time.time() - t0 < budget_s:
                msg = ws.recv()
                if isinstance(msg, (bytes, bytearray)):
                    continue                      # binary preview frame — skip
                ev = json.loads(msg); typ = ev.get("type"); data = ev.get("data", {})
                if data.get("prompt_id") not in (None, prompt_id):
                    continue
                if typ == "progress" and on_progress:
                    on_progress(data.get("value", 0), data.get("max", 1), data.get("node"))
                elif typ == "execution_error":
                    return {"status": "error", "detail": str(data.get("exception_message", ""))[:200]}
                elif typ == "executing" and data.get("node") is None and data.get("prompt_id") == prompt_id:
                    return {"status": "completed", "detail": "ws sentinel"}
        finally:
            ws.close()
    except ImportError:
        pass                                      # no websocket-client -> fall through to polling
    except Exception:
        pass                                      # WS hiccup -> polling is the safety net
    # Polling tracker (stdlib): position for UX, /history for completion.
    while time.time() - t0 < budget_s:
        entry = _history_entry(prompt_id)
        if entry is not None:
            st = (entry.get("status") or {})
            if st.get("status_str") == "error" or st.get("completed") is False and st.get("messages"):
                # inspect messages for an execution_error
                for m in st.get("messages", []):
                    if isinstance(m, list) and m and m[0] == "execution_error":
                        return {"status": "error", "detail": str(m[1])[:200] if len(m) > 1 else "execution_error"}
            return {"status": "completed", "detail": "history present"}
        if on_progress:
            p = position(prompt_id)
            if p is not None:
                on_progress(0, 1, "queued:pos=%s" % p)
        time.sleep(poll_s)
    return {"status": "timeout", "detail": "no completion within %ds" % budget_s}


# ---- outputs / download -----------------------------------------------------------------------
def outputs(prompt_id):
    """List output files from /history: [{filename, subfolder, type, kind}] (kind=images|gifs|videos)."""
    entry = _history_entry(prompt_id) or {}
    files = []
    for node_id, out in (entry.get("outputs") or {}).items():
        for kind in ("images", "gifs", "videos"):
            for f in (out.get(kind) or []):
                files.append({"filename": f.get("filename"), "subfolder": f.get("subfolder", ""),
                              "type": f.get("type", "output"), "kind": kind, "node": node_id})
    return files


def download(filerec, dst_path):
    """Fetch one output file's bytes to dst_path via /view. Returns dst_path or None."""
    q = urllib.parse.urlencode({"filename": filerec["filename"], "subfolder": filerec.get("subfolder", ""),
                                "type": filerec.get("type", "output")})
    try:
        with urllib.request.urlopen(BASE + "/view?" + q, timeout=60) as r:
            data = r.read()
        os.makedirs(os.path.dirname(dst_path), exist_ok=True)
        open(dst_path, "wb").write(data)
        return dst_path if os.path.getsize(dst_path) > 0 else None
    except Exception:
        return None


# ---- recover ----------------------------------------------------------------------------------
def free(unload_models=True, free_memory=True):
    """Release VRAM between heavy jobs / before a co-tenant needs the card. NEVER /interrupt a foreign job."""
    try:
        _post("/free", {"unload_models": unload_models, "free_memory": free_memory}, timeout=20)
        return True
    except Exception:
        return False


def main():
    import argparse
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="print readiness + VRAM + queue")
    a = ap.parse_args()
    if a.check or len(sys.argv) == 1:
        print("ComfyUI %s  ready=%s  vram_free=%sMiB" % (BASE, ready(), vram_free_mib()))
        print("queue:", json.dumps(queue_state()))
    return 0


if __name__ == "__main__":
    if sys.platform == "win32":
        import io; sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(main())
