"""Unified Backend Model — Neo4j Graph for Page & Tenant Organization

Simplifies all page wiring and backend relationships using Neo4j.
One source of truth for:
  - Page structure (go/ pages)
  - Tenant relationships
  - Health status
  - Task tracking

Usage:
  from services.backend_model import BackendModel
  model = BackendModel()
  pages = model.get_all_pages()
"""

import os
from typing import Optional
from neo4j import GraphDatabase
from datetime import datetime, timezone


class BackendModel:
    """Unified Neo4j backend for all pages and tenants."""
    
    def __init__(self, uri: str = None, user: str = None, password: str = None):
        self.uri = uri or os.environ.get("NEO4J_URI", "bolt://localhost:7687")
        self.user = user or os.environ.get("NEO4J_USER", "neo4j")
        self.password = password or os.environ.get("NEO4J_PASSWORD", "password")
        
        try:
            self.driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))
            self._verify_connection()
        except Exception as e:
            print(f"⚠ Neo4j connection failed (running in fallback mode): {e}")
            self.driver = None
    
    def _verify_connection(self):
        """Test Neo4j connection."""
        with self.driver.session() as session:
            result = session.run("RETURN 1")
            result.consume()
    
    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()
    
    def initialize_schema(self):
        """Create Neo4j indexes and constraints."""
        if not self.driver:
            return
        
        queries = [
            "CREATE CONSTRAINT unique_page_id IF NOT EXISTS FOR (p:Page) REQUIRE p.id IS UNIQUE",
            "CREATE CONSTRAINT unique_tenant_id IF NOT EXISTS FOR (t:Tenant) REQUIRE t.id IS UNIQUE",
            "CREATE INDEX page_category IF NOT EXISTS FOR (p:Page) ON (p.category)",
            "CREATE INDEX tenant_status IF NOT EXISTS FOR (t:Tenant) ON (t.status)",
        ]
        
        with self.driver.session() as session:
            for query in queries:
                try:
                    session.run(query)
                except Exception:
                    pass  # Constraint/index may already exist
    
    def register_page(self, page_id: str, title: str, category: str, path: str, 
                     description: str = "", enabled: bool = True) -> dict:
        """Register a go/ page in the backend."""
        if not self.driver:
            return self._mock_page(page_id, title, category, path)
        
        query = """
        MERGE (p:Page {id: $id})
        SET p.title = $title,
            p.category = $category,
            p.path = $path,
            p.description = $description,
            p.enabled = $enabled,
            p.updated_at = $now
        RETURN p
        """
        
        with self.driver.session() as session:
            result = session.run(query, {
                "id": page_id,
                "title": title,
                "category": category,
                "path": path,
                "description": description,
                "enabled": enabled,
                "now": self._now()
            })
            record = result.single()
            if record:
                return dict(record["p"])
        
        return {}
    
    def get_all_pages(self) -> list:
        """Get all registered pages."""
        if not self.driver:
            return self._mock_all_pages()
        
        query = "MATCH (p:Page) WHERE p.enabled = true RETURN p ORDER BY p.category, p.title"
        
        with self.driver.session() as session:
            result = session.run(query)
            return [dict(record["p"]) for record in result]
    
    def get_pages_by_category(self, category: str) -> list:
        """Get pages in a specific category."""
        if not self.driver:
            return self._mock_pages_by_category(category)
        
        query = "MATCH (p:Page) WHERE p.category = $cat AND p.enabled = true RETURN p"
        
        with self.driver.session() as session:
            result = session.run(query, {"cat": category})
            return [dict(record["p"]) for record in result]
    
    def register_tenant(self, tenant_id: str, owner: str = "", 
                       status: str = "active") -> dict:
        """Register a tenant."""
        if not self.driver:
            return self._mock_tenant(tenant_id, owner, status)
        
        query = """
        MERGE (t:Tenant {id: $id})
        SET t.owner = $owner,
            t.status = $status,
            t.created_at = COALESCE(t.created_at, $now),
            t.updated_at = $now,
            t.health_score = 100
        RETURN t
        """
        
        with self.driver.session() as session:
            result = session.run(query, {
                "id": tenant_id,
                "owner": owner,
                "status": status,
                "now": self._now()
            })
            record = result.single()
            if record:
                return dict(record["t"])
        
        return {}
    
    def update_tenant_health(self, tenant_id: str, health_score: int, 
                            status: str) -> dict:
        """Update tenant health and status."""
        if not self.driver:
            return self._mock_tenant(tenant_id, "", status)
        
        query = """
        MATCH (t:Tenant {id: $id})
        SET t.health_score = $score,
            t.status = $status,
            t.updated_at = $now
        RETURN t
        """
        
        with self.driver.session() as session:
            result = session.run(query, {
                "id": tenant_id,
                "score": health_score,
                "status": status,
                "now": self._now()
            })
            record = result.single()
            if record:
                return dict(record["t"])
        
        return {}
    
    def get_tenant(self, tenant_id: str) -> dict:
        """Get a specific tenant."""
        if not self.driver:
            return self._mock_tenant(tenant_id, "", "active")
        
        query = "MATCH (t:Tenant {id: $id}) RETURN t"
        
        with self.driver.session() as session:
            result = session.run(query, {"id": tenant_id})
            record = result.single()
            if record:
                return dict(record["t"])
        
        return {}
    
    def get_all_tenants(self) -> list:
        """Get all tenants."""
        if not self.driver:
            return []
        
        query = "MATCH (t:Tenant) RETURN t ORDER BY t.updated_at DESC"
        
        with self.driver.session() as session:
            result = session.run(query)
            return [dict(record["t"]) for record in result]
    
    def link_page_to_tenant(self, page_id: str, tenant_id: str) -> dict:
        """Link a page to a tenant (for multi-tenant pages)."""
        if not self.driver:
            return {"status": "ok"}
        
        query = """
        MATCH (p:Page {id: $page_id}), (t:Tenant {id: $tenant_id})
        MERGE (t)-[r:USES_PAGE]->(p)
        SET r.accessed_at = $now
        RETURN {page: p.id, tenant: t.id}
        """
        
        with self.driver.session() as session:
            result = session.run(query, {
                "page_id": page_id,
                "tenant_id": tenant_id,
                "now": self._now()
            })
            record = result.single()
            if record:
                return dict(record[0])
        
        return {}
    
    def get_tenant_pages(self, tenant_id: str) -> list:
        """Get all pages accessible to a tenant."""
        if not self.driver:
            return self._mock_all_pages()
        
        query = """
        MATCH (t:Tenant {id: $id})-[r:USES_PAGE]->(p:Page)
        RETURN p ORDER BY p.category
        """
        
        with self.driver.session() as session:
            result = session.run(query, {"id": tenant_id})
            pages = [dict(record["p"]) for record in result]
            if pages:
                return pages
        
        # Fallback: return all pages if no specific links
        return self.get_all_pages()
    
    def record_page_access(self, page_id: str, tenant_id: str = None) -> dict:
        """Log page access."""
        if not self.driver:
            return {"recorded": True}
        
        query = """
        MATCH (p:Page {id: $page_id})
        SET p.last_accessed = $now,
            p.access_count = COALESCE(p.access_count, 0) + 1
        RETURN p
        """
        
        with self.driver.session() as session:
            session.run(query, {
                "page_id": page_id,
                "now": self._now()
            })
        
        return {"recorded": True}
    
    def get_dashboard_summary(self) -> dict:
        """Get summary of all pages and tenants for dashboard."""
        if not self.driver:
            return self._mock_dashboard()
        
        query = """
        RETURN {
            pages: {
                total: size([(p:Page) WHERE p.enabled = true | p]),
                by_category: [(p:Page) WHERE p.enabled = true WITH p.category as cat RETURN {category: cat, count: count(p)})
            },
            tenants: {
                total: size([(t:Tenant) | t]),
                by_status: [(t:Tenant) WITH t.status as status RETURN {status: status, count: count(t)}),
                avg_health: avg([(t:Tenant) | t.health_score])
            }
        } as summary RETURN summary
        """
        
        with self.driver.session() as session:
            result = session.run(query)
            record = result.single()
            if record:
                return dict(record["summary"])
        
        return {}
    
    def close(self):
        """Close Neo4j driver."""
        if self.driver:
            self.driver.close()
    
    # ── FALLBACK MOCK DATA ────────────────────────────────────────────────────────
    
    def _mock_page(self, page_id: str, title: str, category: str, path: str) -> dict:
        return {
            "id": page_id,
            "title": title,
            "category": category,
            "path": path,
            "enabled": True,
            "updated_at": self._now()
        }
    
    def _mock_all_pages(self) -> list:
        return [
            self._mock_page("docker", "Docker", "monitoring", "/go/docker.html"),
            self._mock_page("ollama", "Ollama", "ai", "/go/ollama.html"),
            self._mock_page("system", "System", "monitoring", "/go/system.html"),
            self._mock_page("github", "GitHub", "ci-cd", "/go/github.html"),
            self._mock_page("llm-watch", "LLM Watch", "ai", "/go/llm-watch.html"),
            self._mock_page("logs", "Logs", "monitoring", "/go/logs.html"),
            self._mock_page("comfyui", "ComfyUI", "rendering", "/go/comfyui.html"),
            self._mock_page("healing", "Healing", "ai", "/go/healing.html"),
        ]
    
    def _mock_pages_by_category(self, category: str) -> list:
        return [p for p in self._mock_all_pages() if p["category"] == category]
    
    def _mock_tenant(self, tenant_id: str, owner: str, status: str) -> dict:
        return {
            "id": tenant_id,
            "owner": owner,
            "status": status,
            "health_score": 100,
            "created_at": self._now(),
            "updated_at": self._now()
        }
    
    def _mock_dashboard(self) -> dict:
        pages = self._mock_all_pages()
        categories = {}
        for p in pages:
            cat = p["category"]
            categories[cat] = categories.get(cat, 0) + 1
        
        return {
            "pages": {
                "total": len(pages),
                "by_category": [{"category": cat, "count": cnt} for cat, cnt in categories.items()]
            },
            "tenants": {
                "total": 0,
                "by_status": [],
                "avg_health": 100
            }
        }
