"""
SearXNG-based Web Search Tool with JSON format support.
"""

from __future__ import annotations

import logging
import re
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

    @staticmethod
    def _clean_query(query: str) -> str:
        """Strips conversational noise words and misleading keywords that pollute search index results."""
        q = re.sub(r"^(what is the|what is|tell me the|search for|find|check)\s+", "", query, flags=re.IGNORECASE).strip()
        q = re.sub(r"\b(current|live)\s+", "", q, flags=re.IGNORECASE).strip()
        return q or query

    @staticmethod
    def _extract_weather_location(query: str) -> str | None:
        """Dynamically extracts target location from weather query without hardcoded city lists."""
        if not re.search(r"\b(weather|temperature|forecast|rain|snow|humidity|climate|sää|keli)\b", query, re.IGNORECASE):
            return None

        # 1. Clean temporal phrases first (e.g. "for this week", "this week", "next 7 days", "today", "tomorrow", etc.)
        q_clean = re.sub(
            r"\b(?:for\s+)?(?:this|next)?\s*(?:week|weekend|month|year|today|tonight|tomorrow|now|days?|\d+\s*days?)\b",
            "",
            query,
            flags=re.IGNORECASE,
        ).strip()

        # 2. Try explicit prepositional match: "in <location>", "at <location>", "kohteessa <location>"
        prep_match = re.search(
            r"\b(?:in|at|near|around|city of|region of|town of|kohteessa|alueella)\s+([A-Za-z\u00C0-\u017E0-9\s-]+)",
            q_clean,
            re.IGNORECASE,
        )
        if prep_match:
            loc = prep_match.group(1).strip()
            loc = re.sub(r"^[^\w]+|[^\w]+$", "", loc).strip()
            if loc:
                return loc

        # 3. General fallback: strip weather keywords; remaining tokens form the location
        loc = re.sub(
            r"\b(weather|temperature|forecast|rain|snow|humidity|climate|sää|keli|current|live|what is the|what is|how is the|check)\b",
            "",
            q_clean,
            flags=re.IGNORECASE,
        ).strip()
        loc = re.sub(r"^[^\w]+|[^\w]+$", "", loc).strip()
        return loc if len(loc) >= 2 else None

    def _enrich_with_live_meteo(self, query: str, results: list[SearchResult]) -> None:
        """Injects direct real-time meteorological observations and multi-day forecast breakdown."""
        loc = self._extract_weather_location(query)
        if not loc:
            return

        try:
            with httpx.Client(timeout=4.0) as client:
                w_resp = client.get(f"https://wttr.in/{loc}?format=j1")
                if w_resp.status_code == 200:
                    w_data = w_resp.json()
                    curr = w_data.get("current_condition", [{}])[0]
                    temp_c = curr.get("temp_C", "")
                    desc = curr.get("weatherDesc", [{}])[0].get("value", "")
                    hum = curr.get("humidity", "")
                    wind = curr.get("windspeedKmph", "")

                    # Extract multi-day daily forecast breakdown
                    forecast_lines = []
                    for day in w_data.get("weather", []):
                        d_date = day.get("date", "")
                        d_max = day.get("maxtempC", "")
                        d_min = day.get("mintempC", "")
                        d_hourly = day.get("hourly", [])
                        d_mid = d_hourly[len(d_hourly) // 2] if d_hourly else {}
                        d_desc = d_mid.get("weatherDesc", [{}])[0].get("value", "")
                        d_rain = d_mid.get("chanceofrain", "0")
                        forecast_lines.append(
                            f"  * {d_date}: Min {d_min}°C, Max {d_max}°C, Condition: {d_desc}, Rain chance: {d_rain}%"
                        )

                    snippet_parts = []
                    if temp_c != "":
                        snippet_parts.append(
                            f"Current Observation: Temperature {temp_c}°C, Condition: {desc}, "
                            f"Humidity: {hum}%, Wind speed: {wind} km/h."
                        )
                    if forecast_lines:
                        snippet_parts.append(f"Multi-Day Outlook for {loc.title()}:\n" + "\n".join(forecast_lines))

                    if snippet_parts:
                        results.insert(
                            0,
                            SearchResult(
                                title=f"Live Meteorological & Forecast Report ({loc.title()})",
                                url=f"https://wttr.in/{loc}",
                                snippet="\n\n".join(snippet_parts),
                            ),
                        )
        except (httpx.HTTPError, OSError, ValueError):
            pass



    def search(self, query: str) -> list[SearchResult]:
        """Executes search query against configured SearXNG instance with resilient multi-engine fallback."""
        if not self.config.searxng_url:
            return []

        base_url = self.config.searxng_url.rstrip("/")
        endpoint = f"{base_url}/search"
        reliable_engines = "bing,yahoo,mojeek,wikipedia"
        effective_query = self._clean_query(query)

        def _do_request(request_params: dict[str, Any]) -> list[SearchResult]:
            with httpx.Client(timeout=4.0) as client:
                response = client.get(endpoint, params=request_params)
                if response.status_code != 200:
                    return []
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

        params = {
            "q": effective_query,
            "format": "json",
            "engines": reliable_engines,
        }

        try:
            results = _do_request(params)
            # If cleaned query returned 0 results, retry with raw query
            if not results and effective_query != query:
                results = _do_request({"q": query, "format": "json", "engines": reliable_engines})
            # If multi-engine returned 0 results, fallback to broad search without engine restrictions
            if not results:
                results = _do_request({"q": effective_query, "format": "json"})

            self._enrich_with_live_meteo(query, results)
            return results


        except (httpx.HTTPError, OSError) as e:
            # If failed to connect, try auto-starting container and retry search once
            if ensure_searxng_container(self.config, non_blocking=False):
                try:
                    results = _do_request(params)
                    if not results and effective_query != query:
                        results = _do_request({"q": query, "format": "json", "engines": reliable_engines})
                    if not results:
                        results = _do_request({"q": effective_query, "format": "json"})
                    if results:
                        self._enrich_with_live_meteo(query, results)
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

