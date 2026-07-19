"""Owner authentication shared by Studio maintenance and project mutations."""

import os

from fastapi import Header

from services.authz import require_claims


REQUIRE_AUTH = os.environ.get("STUDIO_ASSETS_REQUIRE_AUTH", "0") == "1"
AUTH_INTROSPECTION_URL = os.environ.get(
    "AUTH_INTROSPECTION_URL", "http://host.docker.internal:8101/api/v2/auth/introspect"
)
AUTH_READY_URL = os.environ.get(
    "AUTH_READY_URL", "http://host.docker.internal:8101/api/v2/ready"
)
INTERNAL_SERVICE_TOKEN = os.environ.get("INTERNAL_SERVICE_TOKEN", "")
AUTH_REQUEST_TIMEOUT = float(os.environ.get("AUTH_REQUEST_TIMEOUT", "5"))


def require_studio_owner(authorization: str | None = Header(default=None)) -> dict | None:
    if not REQUIRE_AUTH:
        return None
    return require_claims(
        service_name="studio-assets",
        authorization=authorization,
        introspection_url=AUTH_INTROSPECTION_URL,
        internal_service_token=INTERNAL_SERVICE_TOKEN,
        request_timeout=AUTH_REQUEST_TIMEOUT,
        required_scopes={"ops:owner"},
    )
