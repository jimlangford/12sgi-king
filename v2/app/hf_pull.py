"""
hf_pull.py — pull a Hugging Face model into the local models/ volume.

Reads the HF token from the Docker secret at /run/secrets/hf_token.
Reads the model ID from the HF_MODEL_ID environment variable.

Usage (inside the running app container):
    docker compose exec app python /workspace/app/hf_pull.py

Or as a one-off:
    docker compose run --rm app python /workspace/app/hf_pull.py
"""
from huggingface_hub import snapshot_download
from pathlib import Path
import os
import sys


def read_secret(path: str) -> str | None:
    p = Path(path)
    if p.exists():
        val = p.read_text().strip()
        return val or None
    return None


HF_TOKEN  = read_secret("/run/secrets/hf_token")
MODEL_ID  = os.getenv("HF_MODEL_ID", "Qwen/Qwen2.5-Coder-7B-Instruct")
MODEL_DIR = os.getenv("MODEL_DIR", "/workspace/models")

if not HF_TOKEN:
    print("WARNING: /run/secrets/hf_token not found — proceeding without auth "
          "(public models only).")

safe_name  = MODEL_ID.replace("/", "__")
local_dir  = os.path.join(MODEL_DIR, safe_name)

print(f"Pulling model: {MODEL_ID}")
print(f"Destination:   {local_dir}")

try:
    snapshot_download(
        repo_id=MODEL_ID,
        local_dir=local_dir,
        token=HF_TOKEN,
        local_dir_use_symlinks=False,
    )
    print("Model pull complete.")
except Exception as e:
    print(f"ERROR: model pull failed: {e}", file=sys.stderr)
    sys.exit(1)
