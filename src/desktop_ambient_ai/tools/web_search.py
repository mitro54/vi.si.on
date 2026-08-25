"""
SearXNG-based Web Search Tool with JSON format support.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import httpx

from ..config import WebSearchConfig


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str


class SearXNGSearch:
    """Queries SearXNG JSON API for real-time web intelligence."""

    def __init__(self, config: WebSearchConfig):
        self.config = config

    def search(self, query: str) -> List[SearchResult]:
        """Executes search query against configured SearXNG instance."""
        if not self.config.searxng_url:
            return []

        base_url = self.config.searxng_url.rstrip("/")
        endpoint = f"{base_url}/search"
        params = {
            "q": query,
            "format": "json",
            "categories": "general",
        }

        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.get(endpoint, params=params)
                if response.status_code != 200:
                    return [
                        SearchResult(
                            title="Search Error",
                            url="",
                            snippet=f"SearXNG returned HTTP status {response.status_code}",
                        )
                    ]

                data = response.json()
                raw_results = data.get("results", [])
                results: List[SearchResult] = []
                for r in raw_results[: self.config.max_results]:
                    results.append(
                        SearchResult(
                            title=r.get("title", "Untitled"),
                            url=r.get("url", ""),
                            snippet=r.get("content", "") or r.get("snippet", ""),
                        )
                    )
                return results

        except Exception as e:
            return [
                SearchResult(
                    title="Search Exception",
                    url="",
                    snippet=f"Failed to connect to SearXNG ({base_url}): {e}",
                )
            ]

    def format_results_for_llm(self, results: List[SearchResult]) -> str:
        """Formats list of search results as a readable markdown string."""
        if not results:
            return "No web results found for this query."
        lines = []
        for i, res in enumerate(results, 1):
            lines.append(f"[{i}] {res.title}\nURL: {res.url}\nSummary: {res.snippet}\n")
        return "\n".join(lines)

    @staticmethod
    def get_tool_schema() -> Dict[str, Any]:
        """Returns standard tool definition for function calling."""
        return {
            "type": "function",
            "function": {
                "name": "web_search",
                "description": (
                    "Search the live web for current, up-to-date information, news, documentation, "
                    "or events that may have occurred after model training cutoff."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The search query keywords",
                        }
                    },
                    "required": ["query"],
                },
            },
        }
