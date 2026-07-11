import os


COMMIT_SHA = os.environ.get("COMMIT_SHA", "").strip() or "unknown"
BUILD_TIMESTAMP = os.environ.get("BUILD_TIMESTAMP", "").strip() or "unknown"
ENVIRONMENT = os.environ.get("ENVIRONMENT", "").strip() or "development"
# Platform-level release identifier shared across all V2 services.
# Injected as PLATFORM_VERSION by docker-compose.v2.yml and the deploy workflow.
# Falls back to "unknown" when running outside of the managed stack.
PLATFORM_VERSION = os.environ.get("PLATFORM_VERSION", "").strip() or "unknown"


def service_metadata(service: str, version: str) -> dict[str, str]:
    return {
        "service": service,
        "platform_version": PLATFORM_VERSION,
        "service_version": version,
        # Keep "version" for backward-compat with callers that already read it
        "version": version,
        "commit_sha": COMMIT_SHA,
        "build_timestamp": BUILD_TIMESTAMP,
        "environment": ENVIRONMENT,
    }


def with_service_metadata(payload: dict, service: str, version: str) -> dict:
    return {**payload, **service_metadata(service, version)}
