"""Unified Pages API — Clean wiring for all go/ pages

Simple endpoint that returns page structure and status for any access method.
Works identically on localhost and Tailscale.

Endpoints:
  GET /api/pages              - All pages
  GET /api/pages/category/:cat - Pages in category
  GET /api/pages/:id          - Specific page
  GET /api/dashboard          - Summary for dashboard

Usage: included in board_api.main
"""

from fastapi import APIRouter, HTTPException
from typing import Optional

from services.backend_model import BackendModel

router = APIRouter(prefix="/api", tags=["pages"])

# Global backend model
backend = BackendModel()

# Initialize schema
try:
    backend.initialize_schema()
except Exception:
    pass  # Neo4j may not be available


@router.on_event("startup")
async def startup():
    """Initialize pages on startup."""
    # Register all go/ pages
    pages = [
        ("docker", "Docker", "monitoring", "/go/docker.html", "Container status"),
        ("ollama", "Ollama", "ai", "/go/ollama.html", "LLM server status"),
        ("system", "System", "monitoring", "/go/system.html", "Hardware health"),
        ("github", "GitHub", "ci-cd", "/go/github.html", "CI status"),
        ("llm-watch", "LLM Watch", "ai", "/go/llm-watch.html", "Request monitor"),
        ("logs", "Logs", "monitoring", "/go/logs.html", "System log viewer"),
        ("comfyui", "ComfyUI", "rendering", "/go/comfyui.html", "Diffusion queue"),
        ("healing", "Healing", "ai", "/go/healing.html", "Self-healing system"),
    ]
    
    for page_id, title, category, path, desc in pages:
        try:
            backend.register_page(page_id, title, category, path, desc)
        except Exception:
            pass  # Neo4j may not be available


@router.get("/pages")
async def get_all_pages():
    """Get all available pages."""
    pages = backend.get_all_pages()
    return {
        "total": len(pages),
        "pages": pages,
        "categories": list(set(p.get("category") for p in pages))
    }


@router.get("/pages/category/{category}")
async def get_pages_by_category(category: str):
    """Get pages in a specific category."""
    pages = backend.get_pages_by_category(category)
    return {
        "category": category,
        "total": len(pages),
        "pages": pages
    }


@router.get("/pages/{page_id}")
async def get_page(page_id: str):
    """Get a specific page."""
    # Try Neo4j first
    try:
        page = backend.get_tenant_pages(page_id)  # Fallback to mock if needed
        if page:
            backend.record_page_access(page_id)
            return {"page": page[0] if page else None}
    except Exception:
        pass
    
    # Fallback to mock
    mock_pages = {
        "docker": {"id": "docker", "title": "Docker", "category": "monitoring", "path": "/go/docker.html"},
        "ollama": {"id": "ollama", "title": "Ollama", "category": "ai", "path": "/go/ollama.html"},
        "system": {"id": "system", "title": "System", "category": "monitoring", "path": "/go/system.html"},
        "github": {"id": "github", "title": "GitHub", "category": "ci-cd", "path": "/go/github.html"},
        "llm-watch": {"id": "llm-watch", "title": "LLM Watch", "category": "ai", "path": "/go/llm-watch.html"},
        "logs": {"id": "logs", "title": "Logs", "category": "monitoring", "path": "/go/logs.html"},
        "comfyui": {"id": "comfyui", "title": "ComfyUI", "category": "rendering", "path": "/go/comfyui.html"},
        "healing": {"id": "healing", "title": "Healing", "category": "ai", "path": "/go/healing.html"},
    }
    
    page = mock_pages.get(page_id)
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")
    
    return {"page": page}


@router.get("/dashboard")
async def get_dashboard():
    """Get unified dashboard summary."""
    summary = backend.get_dashboard_summary()
    
    # Fallback if Neo4j not available
    if not summary:
        summary = {
            "pages": {
                "total": 8,
                "by_category": [
                    {"category": "monitoring", "count": 3},
                    {"category": "ai", "count": 3},
                    {"category": "ci-cd", "count": 1},
                    {"category": "rendering", "count": 1},
                ]
            },
            "tenants": {
                "total": 0,
                "by_status": [],
                "avg_health": 100
            }
        }
    
    return summary
