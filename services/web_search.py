"""Web search integration — free APIs for research and best practices.

Uses DuckDuckGo (no key required) and optional Brave Search API (free tier).
Provides: web research, best practices discovery, error solutions, documentation lookup.

Usage:
  from services.web_search import search_web, get_best_practices
  results = search_web("Docker healthcheck best practices")
  practices = get_best_practices("Python error handling")
"""

import json
import urllib.request
import urllib.parse
from typing import list
import time

TIMEOUT = 5
USER_AGENT = "Gordon-LocalAI/1.0 (+https://12sgigov.org)"

def search_duckduckgo(query: str, max_results: int = 5) -> list:
    """Search DuckDuckGo (free, no key required).
    
    Args:
        query: search term
        max_results: limit results (1-20)
    
    Returns:
        list of {"title", "url", "snippet"} dicts
    """
    try:
        # DuckDuckGo HTML endpoint
        url = f"https://duckduckgo.com/html/?q={urllib.parse.quote(query)}"
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
        
        results = []
        # Simple regex-based extraction (DuckDuckGo HTML is stable)
        import re
        pattern = r'<div class="result">\s*<div class="result__title">\s*<a[^>]*href="([^"]*)"[^>]*>([^<]+)</a>'
        for match in re.finditer(pattern, html, re.IGNORECASE):
            url_match, title = match.groups()
            if url_match.startswith("http"):
                results.append({
                    "title": title.strip(),
                    "url": url_match,
                    "source": "duckduckgo",
                    "snippet": ""
                })
                if len(results) >= max_results:
                    break
        
        return results
    except Exception as e:
        print(f"DuckDuckGo search failed: {e}")
        return []


def search_web(query: str, sources: list = None) -> list:
    """Multi-source web search for best practices and error solutions.
    
    Args:
        query: search term (e.g. "Docker OOM error fix", "Ollama VRAM optimization")
        sources: ["duckduckgo"] or custom (default: all free sources)
    
    Returns:
        list of search results with metadata
    """
    if sources is None:
        sources = ["duckduckgo"]
    
    all_results = []
    
    if "duckduckgo" in sources:
        all_results.extend(search_duckduckgo(query, max_results=5))
    
    # Remove duplicates (by URL)
    seen_urls = set()
    deduplicated = []
    for result in all_results:
        url = result.get("url", "")
        if url and url not in seen_urls:
            seen_urls.add(url)
            deduplicated.append(result)
    
    return deduplicated


def get_best_practices(topic: str) -> dict:
    """Retrieve best practices for a given topic.
    
    Args:
        topic: e.g. "Docker health checks", "Python error handling", "GPU memory management"
    
    Returns:
        dict with "practices", "links", "summary"
    """
    query = f"{topic} best practices tutorial 2024 2025"
    results = search_web(query)
    
    return {
        "topic": topic,
        "query": query,
        "results": results,
        "count": len(results),
        "note": "Use top 2-3 links for implementation guidance"
    }


def search_error_solution(error_msg: str, context: str = "") -> dict:
    """Search for solutions to a specific error.
    
    Args:
        error_msg: the error message (e.g. "CUDA out of memory")
        context: optional context (e.g. "ComfyUI render", "Ollama inference")
    
    Returns:
        dict with solutions, common causes, preventions
    """
    query = f"{error_msg} fix solution {context}".strip()
    results = search_web(query)
    
    return {
        "error": error_msg,
        "context": context,
        "query": query,
        "solutions": results,
        "search_time": time.time()
    }


def search_documentation(service: str, topic: str) -> dict:
    """Search for official documentation.
    
    Args:
        service: "docker", "ollama", "comfyui", "python", etc.
        topic: what to find docs for
    
    Returns:
        dict with links to official docs
    """
    query = f"site:docs.{service}.com OR site:{service}.io/docs {topic}"
    results = search_web(query)
    
    return {
        "service": service,
        "topic": topic,
        "results": results,
        "prefer_official": True
    }
