import json
import os
from functools import lru_cache
from pathlib import Path


COMMIT_SHA = os.environ.get("COMMIT_SHA", "").strip() or "unknown"
BUILD_TIMESTAMP = os.environ.get("BUILD_TIMESTAMP", "").strip() or "unknown"
ENVIRONMENT = os.environ.get("ENVIRONMENT", "").strip() or "development"
_ENV_PLATFORM_VERSION = os.environ.get("PLATFORM_VERSION", "").strip()
_DEFAULT_PLATFORM_MANIFEST = Path(__file__).resolve().parents[1] / "config" / "platform_version.json"
PLATFORM_MANIFEST_FILE = Path(
    os.environ.get("PLATFORM_VERSION_FILE", str(_DEFAULT_PLATFORM_MANIFEST))
).resolve()


@lru_cache(maxsize=1)
def platform_manifest() -> dict:
    try:
        data = json.loads(PLATFORM_MANIFEST_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def manifest_platform_version() -> str:
    value = platform_manifest().get("platform_version")
    if isinstance(value, str) and value.strip():
        return value.strip()
    return "unknown"


def platform_version() -> str:
    return _ENV_PLATFORM_VERSION or manifest_platform_version()


def platform_version_disagreement() -> bool:
    return bool(
        _ENV_PLATFORM_VERSION
        and manifest_platform_version() != "unknown"
        and _ENV_PLATFORM_VERSION != manifest_platform_version()
    )


def service_metadata(service: str, version: str) -> dict[str, str | bool]:
    manifest = platform_manifest()
    return {
        "service": service,
        "platform_version": platform_version(),
        "platform_version_manifest": manifest_platform_version(),
        "platform_manifest_version": str(manifest.get("manifest_version") or "unknown"),
        "platform_version_mismatch": platform_version_disagreement(),
        "service_version": version,
        # Keep "version" for backward-compat with callers that already read it
        "version": version,
        "commit_sha": COMMIT_SHA,
        "build_timestamp": BUILD_TIMESTAMP,
        "environment": ENVIRONMENT,
    }


def with_service_metadata(payload: dict, service: str, version: str) -> dict:
    return {**payload, **service_metadata(service, version)}
