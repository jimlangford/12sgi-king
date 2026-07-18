#!/usr/bin/env python3
"""Import a Google OAuth web-client JSON file into a gitignored env file."""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path
from urllib.parse import urlsplit


DEFAULT_CALLBACK = "https://auth.12sgi.com/api/v2/auth/google/callback"


def _safe_env_value(value: object) -> str:
    text = str(value)
    if any(character in text for character in ("\r", "\n", "\0")):
        raise ValueError("Credential values cannot contain line breaks or NUL bytes")
    return text


def _replace_env_values(text: str, values: dict[str, str]) -> str:
    remaining = {key: _safe_env_value(value) for key, value in values.items()}
    output: list[str] = []
    for line in text.splitlines():
        key = line.split("=", 1)[0].strip() if "=" in line and not line.lstrip().startswith("#") else ""
        if key in remaining:
            output.append(f"{key}={remaining.pop(key)}")
        else:
            output.append(line)
    if remaining:
        if output and output[-1]:
            output.append("")
        output.extend(f"{key}={value}" for key, value in remaining.items())
    return "\n".join(output) + "\n"


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent, text=True)
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_name, path)
    except Exception:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise


def _env_value(text: str, name: str) -> str:
    for line in text.splitlines():
        if line.lstrip().startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip() == name:
            return value.strip()
    return ""


def _web_origins(values: object) -> list[str]:
    if not isinstance(values, list):
        return []
    origins: list[str] = []
    for value in values:
        raw = str(value or "").strip()
        parsed = urlsplit(raw)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.netloc
            or parsed.username
            or parsed.password
            or parsed.path not in {"", "/"}
            or parsed.query
            or parsed.fragment
        ):
            continue
        origin = f"{parsed.scheme}://{parsed.netloc}"
        if origin not in origins:
            origins.append(origin)
    return origins


def _merged_csv(current: str, additions: list[str]) -> str:
    values = [value.strip() for value in current.split(",") if value.strip()]
    for value in additions:
        if value not in values:
            values.append(value)
    return ",".join(values)


def import_credentials(credentials_path: Path, env_path: Path, callback_uri: str) -> bool:
    payload = json.loads(credentials_path.read_text(encoding="utf-8"))
    web = payload.get("web")
    if not isinstance(web, dict):
        raise ValueError("Google credentials must be an OAuth web application JSON file")
    client_id = str(web.get("client_id") or "").strip()
    client_secret = str(web.get("client_secret") or "").strip()
    if not client_id or not client_secret:
        raise ValueError("Google credentials are missing client_id or client_secret")

    current = env_path.read_text(encoding="utf-8") if env_path.exists() else ""
    values = {
        "GOOGLE_CLIENT_ID": client_id,
        "GOOGLE_CLIENT_SECRET": client_secret,
    }
    javascript_origins = _web_origins(web.get("javascript_origins"))
    if javascript_origins:
        values["CORS_ORIGINS"] = _merged_csv(
            _env_value(current, "CORS_ORIGINS"),
            javascript_origins,
        )
    updated = _replace_env_values(current, values)
    _atomic_write(env_path, updated)
    redirect_uris = {str(uri).strip() for uri in web.get("redirect_uris", []) if str(uri).strip()}
    return callback_uri in redirect_uris


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("credentials", type=Path, help="Downloaded Google OAuth credentials.json")
    parser.add_argument("--env-file", type=Path, default=Path(".env.v2"))
    parser.add_argument("--callback-uri", default=DEFAULT_CALLBACK)
    args = parser.parse_args()

    callback_registered = import_credentials(args.credentials, args.env_file, args.callback_uri)
    print(f"Configured Google OAuth in {args.env_file}; no credential values were printed.")
    if callback_registered:
        print(f"Callback registered in downloaded config: {args.callback_uri}")
        return 0
    print(f"ACTION REQUIRED in Google Cloud: add authorized redirect URI {args.callback_uri}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
