"""
SearXNG-based Web Search Tool with JSON format support.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from ..config import WebSearchConfig

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str


def is_searxng_healthy(url: str, timeout: float = 1.5) -> bool:
    """Performs a quick HTTP check to determine if SearXNG is reachable."""
    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.get(url.rstrip("/") + "/search", params={"q": "test", "format": "json"})
            return resp.status_code == 200
    except (httpx.HTTPError, OSError):
        return False


def ensure_searxng_container(config: WebSearchConfig, non_blocking: bool = True) -> bool:
    """Automatically starts the SearXNG Docker container if configured for localhost and not running."""
    if not config.enabled:
        return False

    url = (config.searxng_url or "").lower()
    is_local = "localhost" in url or "127.0.0.1" in url or "0.0.0.0" in url
    if not is_local:
        return True

    if is_searxng_healthy(config.searxng_url):
        return True

    if not shutil.which("docker"):
        logger.warning("[SearXNG] Docker is not installed or not in PATH; cannot auto-start SearXNG.")
        return False

    repo_dir = Path(__file__).resolve().parent.parent.parent.parent
    compose_file = repo_dir / "docker-compose.searxng.yml"
    if not compose_file.exists():
        return False

    # Ensure default settings.yml exists
    settings_dir = repo_dir / "searxng-data"
    settings_file = settings_dir / "settings.yml"
    if not settings_file.exists():
        settings_dir.mkdir(parents=True, exist_ok=True)
        default_settings = """# SearXNG configuration for vi.si.on
use_default_settings: true

server:
  secret_key: "vi_si_on_ambient_ai_searxng_secret_key"
  limiter: false
  image_proxy: false

search:
  safe_search: 0
  autocomplete: ""
  formats:
    - html
    - json
"""
        settings_file.write_text(default_settings, encoding="utf-8")

    def _start():
        try:
            cmd = ["docker", "compose", "-f", str(compose_file), "up", "-d"]
            res = subprocess.run(cmd, cwd=str(repo_dir), capture_output=True, text=True, timeout=35, check=False)
            if res.returncode == 0:
                logger.info("[SearXNG] Container started successfully.")
            else:
                logger.warning("[SearXNG] Docker compose error: %s", res.stderr)
        except (subprocess.SubprocessError, OSError) as e:
            logger.warning("[SearXNG] Failed to start container: %s", e)

    if non_blocking:
        t = threading.Thread(target=_start, daemon=True)
        t.start()
        return True
    else:
        _start()
        for _ in range(12):
            if is_searxng_healthy(config.searxng_url, timeout=1.0):
                return True
            time.sleep(0.5)
        return False


class SearXNGSearch:
    """Queries SearXNG JSON API for real-time web intelligence."""

    def __init__(self, config: WebSearchConfig):
        self.config = config
        if self.config.enabled:
            ensure_searxng_container(self.config, non_blocking=True)

    def search(self, query: str) -> list[SearchResult]:
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
                results: list[SearchResult] = []
                for r in raw_results[: self.config.max_results]:
                    results.append(
                        SearchResult(
                            title=r.get("title", "Untitled"),
                            url=r.get("url", ""),
                            snippet=r.get("content", "") or r.get("snippet", ""),
                        )
                    )
                return results

        except (httpx.HTTPError, OSError) as e:
            # If failed to connect, try auto-starting container and retry search once
            if ensure_searxng_container(self.config, non_blocking=False):
                try:
                    with httpx.Client(timeout=10.0) as client:
                        response = client.get(endpoint, params=params)
                        if response.status_code == 200:
                            data = response.json()
                            raw_results = data.get("results", [])
                            results = []
                            for r in raw_results[: self.config.max_results]:
                                results.append(
                                    SearchResult(
                                        title=r.get("title", "Untitled"),
                                        url=r.get("url", ""),
                                        snippet=r.get("content", "") or r.get("snippet", ""),
                                    )
                                )
                            return results
                except (httpx.HTTPError, OSError):
                    pass

            return [
                SearchResult(
                    title="Search Exception",
                    url="",
                    snippet=f"Failed to connect to SearXNG ({base_url}): {e}",
                )
            ]

    def format_results_for_llm(self, results: list[SearchResult]) -> str:
        """Formats list of search results as a readable markdown string."""
        if not results:
            return "No web results found for this query."
        lines = []
        for i, res in enumerate(results, 1):
            lines.append(f"[{i}] {res.title}\nURL: {res.url}\nSummary: {res.snippet}\n")
        return "\n".join(lines)

    @staticmethod
    def get_tool_schema() -> dict[str, Any]:
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

