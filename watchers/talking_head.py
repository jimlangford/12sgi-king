#!/usr/bin/env python3
"""talking_head.py — GATED lip-synced talking head for the civic narrator (Jimmy 2026-06-18 "yes wire it").

The premium tier above meeting_watch's voiced reel: the narrator's MOUTH actually moves, lip-synced to the
warm cloned voice. Uses the no-download LatentSync ComfyUI wrapper (GeekyLatentSyncNode, vram_usage="low")
— it runs INSIDE ComfyUI as a queued prompt, so it NEVER stops the studio (unlike the EchoMimic path) and
queues behind any live render rather than interrupting it.

PIPELINE: narrator still -> ffmpeg loop into a 512 face video (length = audio) -> LatentSync drives the
mouth to the voice wav -> mux the voice back on -> talking_head.mp4.

GUARDRAILS (same as explainer_character): GPU-GATED + NEVER-INTERRUPT (defers when <6 GB free = a render
is active); FICTIONAL narrator only; AI-DISCLOSED; STAGE-ONLY. Returns {ok|deferred|error, media}.

API: make(still_png, audio_wav, out_mp4, prefix="MEETING_WATCH", seconds_cap=40) -> dict
Stdlib only.
"""
import os, sys, json, glob, time, shutil, subprocess, urllib.request

COMFY = "http://127.0.0.1:8000"
CIN = r"C:\Users\12sgi\Documents\ComfyUI\input"
COUT = r"C:\Users\12sgi\Documents\ComfyUI\output"
NW = 0x08000000 if os.name == "nt" else 0
DISCLOSURE = "AI-generated · fictional civic narrator · lip-synced (LatentSync)"


def _free_mib():
    try:
        r = subprocess.run(["nvidia-smi", "--query-gpu=memory.free", "--format=csv,noheader,nounits"],
                           capture_output=True, text=True, timeout=15, creationflags=NW)
        return int(r.stdout.strip().splitlines()[0])
    except Exception:
        return -1


def gpu_busy():
    """True if a studio render is active (defer — never interrupt). <6 GB free = a render holds the card."""
    f = _free_mib()
    return 0 <= f < 6000


def _wav_dur(wav):
    try:
        import wave
        w = wave.open(wav); d = w.getnframes() / float(w.getframerate()); w.close(); return d
    except Exception:
        return None


def _post(path, obj):
    data = json.dumps(obj).encode()
    r = urllib.request.urlopen(urllib.request.Request(COMFY + path, data=data,
                              headers={"Content-Type": "application/json"}), timeout=30)
    return json.loads(r.read())


def _get(path):
    return json.loads(urllib.request.urlopen(COMFY + path, timeout=30).read())


def make(still_png, audio_wav, out_mp4, prefix="MEETING_WATCH", seconds_cap=8, poll_cap=1500,
         card_png=None, box=(270, 640, 540, 540)):
    """Lip-sync a SHORT spoken intro (default 8s). On the 8 GB card ComfyUI caps PyTorch to ~6 GiB, so a
    long clip OOMs — the talking head is a short greeting; the full watch-out stays the CPU voiced reel."""
    if not (still_png and os.path.exists(still_png) and audio_wav and os.path.exists(audio_wav)):
        return {"ok": False, "error": "missing still or audio", "stage_only": True}
    if gpu_busy():
        return {"ok": False, "deferred": True, "reason": "GPU busy with a render — deferring (never interrupt)."}
    try:
        os.makedirs(CIN, exist_ok=True)
        dur = min(_wav_dur(audio_wav) or 8.0, seconds_cap)
        src = os.path.join(CIN, "mw_src.mp4")
        a16 = os.path.join(CIN, "mw_audio.wav")
        # 1) still -> short 512 face video (the mouth LatentSync drives)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-loop", "1", "-i", still_png, "-t", "%.2f" % dur,
                        "-r", "25", "-vf", "scale=512:512:force_original_aspect_ratio=increase,crop=512:512",
                        "-pix_fmt", "yuv420p", src], timeout=120, creationflags=NW)
        # 2) trimmed mono 16k audio (short window = fits the 8 GB / 6 GiB-capped card)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", audio_wav, "-t", "%.2f" % dur,
                        "-ac", "1", "-ar", "16000", a16], timeout=60, creationflags=NW)
        audio_wav = a16   # mux the same trimmed window back on
        if not os.path.exists(src):
            return {"ok": False, "error": "base face video build failed"}
        # 3) the proven LatentSync graph (vram_usage low so it co-tenants the 8 GB card)
        graph = {
            "lv": {"class_type": "LoadVideo", "inputs": {"file": "mw_src.mp4"}},
            "gvc": {"class_type": "GetVideoComponents", "inputs": {"video": ["lv", 0]}},
            "la": {"class_type": "LoadAudio", "inputs": {"audio": "mw_audio.wav"}},
            "ls": {"class_type": "GeekyLatentSyncNode", "inputs": {
                "images": ["gvc", 0], "audio": ["la", 0], "seed": 1,
                "lips_expression": 1.5, "inference_steps": 20, "vram_usage": "low"}},
            "cv": {"class_type": "CreateVideo", "inputs": {"images": ["ls", 0], "fps": ["gvc", 2]}},
            "sv": {"class_type": "SaveVideo", "inputs": {"video": ["cv", 0],
                   "filename_prefix": "%s/talkinghead" % prefix, "format": "auto", "codec": "auto"}},
        }
        pid = _post("/prompt", {"prompt": graph, "client_id": "talking_head"}).get("prompt_id")
        if not pid:
            return {"ok": False, "error": "ComfyUI did not accept the prompt"}
        # 4) poll (queues behind a live render; gated so we only got here when free, but stay patient)
        saved, deadline = None, time.time() + poll_cap
        while time.time() < deadline:
            time.sleep(6)
            try:
                h = _get("/history/%s" % pid)
            except Exception:
                continue
            if pid not in h:
                continue
            ent = h[pid]; st = ent.get("status", {})
            if st.get("status_str") == "error":
                return {"ok": False, "error": "LatentSync graph error", "messages": st.get("messages", [])[:3]}
            outs = ent.get("outputs", {})
            if outs:
                for _, o in outs.items():
                    for key in ("video", "videos", "gifs", "images"):
                        for v in (o.get(key, []) or []):
                            fn = v.get("filename", "")
                            if fn.lower().endswith((".mp4", ".webm", ".mov")):
                                saved = os.path.join(COUT, v.get("subfolder", ""), fn)
                if not saved:
                    cand = sorted(glob.glob(os.path.join(COUT, prefix, "*.mp4")), key=os.path.getmtime)
                    saved = cand[-1] if cand else None
                if saved:
                    break
        if not saved or not os.path.exists(saved):
            return {"ok": False, "deferred": True, "reason": "no output yet (queued behind a render); re-run to collect."}
        # 5) COMPOSITE the talking face INTO the designed card (so it looks like the cards, not a bare face),
        #    then mux the warm voice. If no card given, fall back to the bare face + voice.
        os.makedirs(os.path.dirname(out_mp4) or ".", exist_ok=True)
        if card_png and os.path.exists(card_png):
            bx, by, bw, bh = box
            fc = ("[1:v]scale=%d:%d,format=yuv420p[f];[0:v][f]overlay=%d:%d:shortest=1,format=yuv420p[v]"
                  % (bw, bh, bx, by))
            cmd = ["ffmpeg", "-y", "-loglevel", "error", "-loop", "1", "-i", card_png, "-i", saved, "-i", audio_wav,
                   "-filter_complex", fc, "-map", "[v]", "-map", "2:a", "-t", "%.2f" % dur,
                   "-r", "25", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", out_mp4]
        else:
            cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", saved, "-i", audio_wav,
                   "-c:v", "copy", "-c:a", "aac", "-map", "0:v:0", "-map", "1:a:0", "-shortest", out_mp4]
        subprocess.run(cmd, timeout=180, creationflags=NW)
        ok = os.path.exists(out_mp4)
        return {"ok": ok, "media": out_mp4 if ok else None, "raw": saved, "carded": bool(card_png),
                "disclosure": DISCLOSURE, "stage_only": True}
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}


def main():
    import argparse
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--still", required=True)
    ap.add_argument("--audio", required=True)
    ap.add_argument("--out", required=True)
    a, _ = ap.parse_known_args()
    r = make(a.still, a.audio, a.out)
    print(json.dumps({k: v for k, v in r.items() if k != "messages"}, ensure_ascii=False))
    return 0 if r.get("ok") else (2 if r.get("deferred") else 1)


if __name__ == "__main__":
    if sys.platform == "win32":
        import io; sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(main())
