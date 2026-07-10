import os


COMMIT_SHA = os.environ.get("COMMIT_SHA", "").strip() or "unknown"
BUILD_TIMESTAMP = os.environ.get("BUILD_TIMESTAMP", "").strip() or "unknown"
ENVIRONMENT = os.environ.get("ENVIRONMENT", "").strip() or "development"


def service_metadata(service: str, version: str) -> dict[str, str]:
    return {
        "service": service,
        "version": version,
        "commit_sha": COMMIT_SHA,
        "build_timestamp": BUILD_TIMESTAMP,
        "environment": ENVIRONMENT,
    }


def with_service_metadata(payload: dict, service: str, version: str) -> dict:
    return {**payload, **service_metadata(service, version)}
