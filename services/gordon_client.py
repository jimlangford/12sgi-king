"""
Gordon Client Library for Local AI Systems
Provides uniform access to Gordon admin endpoints for LOTUS, King-Server, Naga, etc.
"""

import os
import json
from typing import Optional, Dict, Any, Literal
import httpx
from enum import Enum

# Gordon endpoint configuration
GORDON_HOST = os.getenv("GORDON_HOST", "localhost")
GORDON_PORT = int(os.getenv("GORDON_PORT", "8504"))
GORDON_OWNER_EMAILS = {
    "jimlangford@me.com",
    "elementlotus@gmail.com",
    "jimmylangford@elementlotus.com",
    "JRCSL@12sgi.com"
}
GORDON_API_KEY = os.getenv("GORDON_API_KEY", "")  # For local dev


class GordonAction(str, Enum):
    QUERY = "query"
    REDESIGN = "redesign"
    MODIFY = "modify"


class GordonClient:
    """
    Client for interacting with Gordon admin backend.
    Used by LOTUS, King-Server, Naga, and other local AI systems.
    """

    def __init__(
        self,
        host: str = GORDON_HOST,
        port: int = GORDON_PORT,
        api_key: Optional[str] = None,
        system_name: str = "local-ai"
    ):
        """
        Initialize Gordon client.

        Args:
            host: Gordon API host
            port: Gordon API port
            api_key: Optional API key for local dev (uses Tailscale auth in production)
            system_name: Name of calling system (LOTUS, King-Server, Naga, etc.)
        """
        self.base_url = f"http://{host}:{port}"
        self.api_key = api_key or GORDON_API_KEY
        self.system_name = system_name
        self.client = httpx.Client(timeout=30.0)

    def _make_request(
        self,
        method: str,
        endpoint: str,
        json_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Make HTTP request to Gordon with authentication."""
        url = f"{self.base_url}{endpoint}"
        headers = {}

        # Add API key if available (for local dev)
        if self.api_key:
            headers["X-API-Key"] = self.api_key

        try:
            if method == "POST":
                response = self.client.post(url, json=json_data, headers=headers)
            else:
                response = self.client.get(url, headers=headers)

            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            return {
                "error": str(e),
                "status_code": e.response.status_code,
                "detail": e.response.text
            }
        except Exception as e:
            return {"error": f"Request failed: {str(e)}"}

    def check_status(self) -> Dict[str, Any]:
        """Check if Gordon is accessible and authenticated."""
        result = self._make_request("GET", "/admin/gordon/status")
        result["system"] = self.system_name
        return result

    def query(self, text: str) -> Dict[str, Any]:
        """Ask Gordon for advice or information."""
        return self._make_request(
            "POST",
            "/admin/gordon",
            {"text": text, "action": GordonAction.QUERY}
        )

    def redesign(self, text: str) -> Dict[str, Any]:
        """Request Gordon to redesign backend pages or components."""
        return self._make_request(
            "POST",
            "/admin/gordon",
            {"text": text, "action": GordonAction.REDESIGN}
        )

    def modify(self, text: str) -> Dict[str, Any]:
        """Request Gordon to modify backend files."""
        return self._make_request(
            "POST",
            "/admin/gordon",
            {"text": text, "action": GordonAction.MODIFY}
        )

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.client.close()


# Convenience functions for quick access
def check_gordon_status(system_name: str = "local-ai") -> Dict[str, Any]:
    """Check if Gordon is available."""
    with GordonClient(system_name=system_name) as client:
        return client.check_status()


def ask_gordon(question: str, system_name: str = "local-ai") -> Dict[str, Any]:
    """Ask Gordon for advice."""
    with GordonClient(system_name=system_name) as client:
        return client.query(question)


def gordon_redesign(request: str, system_name: str = "local-ai") -> Dict[str, Any]:
    """Request Gordon redesign."""
    with GordonClient(system_name=system_name) as client:
        return client.redesign(request)


def gordon_modify(request: str, system_name: str = "local-ai") -> Dict[str, Any]:
    """Request Gordon file modification."""
    with GordonClient(system_name=system_name) as client:
        return client.modify(request)
