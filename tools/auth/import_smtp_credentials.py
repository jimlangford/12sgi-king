#!/usr/bin/env python3
"""Import an existing mailroom SMTP JSON file into a gitignored env file."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

try:
    from .import_google_credentials import _atomic_write, _replace_env_values
except ImportError:  # Direct script execution adds this directory, not the repo root, to sys.path.
    from import_google_credentials import _atomic_write, _replace_env_values


def import_smtp_credentials(credentials_path: Path, env_path: Path) -> None:
    payload = json.loads(credentials_path.read_text(encoding="utf-8"))
    host = str(payload.get("host") or "").strip()
    port = str(payload.get("port") or "").strip()
    user = str(payload.get("user") or payload.get("username") or "").strip()
    password = str(payload.get("password") or "")
    sender = str(payload.get("from") or user).strip()
    if not host or not port.isdigit() or not user or not password or not sender:
        raise ValueError("SMTP credentials require host, numeric port, user, password, and from")
    if password.upper().startswith("PASTE_"):
        raise ValueError("SMTP credentials still contain a placeholder password")

    current = env_path.read_text(encoding="utf-8") if env_path.exists() else ""
    updated = _replace_env_values(
        current,
        {
            "SMTP_HOST": host,
            "SMTP_PORT": port,
            "SMTP_USER": user,
            "SMTP_PASS": password,
            "SMTP_FROM": sender,
            "SMTP_STARTTLS": "false" if port == "465" else "true",
            "SMTP_ALLOW_UNAUTHENTICATED": "false",
        },
    )
    _atomic_write(env_path, updated)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("credentials", type=Path, help="Existing mailroom SMTP JSON file")
    parser.add_argument("--env-file", type=Path, default=Path(".env.v2"))
    args = parser.parse_args()
    import_smtp_credentials(args.credentials, args.env_file)
    print(f"Configured SMTP in {args.env_file}; no credential values were printed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
