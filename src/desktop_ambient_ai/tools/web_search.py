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


from concurrent.futures import ThreadPoolExecutor
from html.parser import HTMLParser


class CleanTextExtractor(HTMLParser):
    """Fast, lightweight HTML parser that extracts readable body text, ignoring scripts, styles, and chrome."""

    def __init__(self):
        super().__init__()
        self.text_parts: list[str] = []
        self.ignore_stack: list[str] = []
        self.ignored_tags = {"script", "style", "nav", "footer", "header", "noscript", "svg", "button", "input", "form"}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag_lower = tag.lower()
        if tag_lower in self.ignored_tags:
            self.ignore_stack.append(tag_lower)
        elif tag_lower in {"p", "br", "h1", "h2", "h3", "h4", "h5", "h6", "li", "tr", "article", "section"}:
            self.text_parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        tag_lower = tag.lower()
        if self.ignore_stack and self.ignore_stack[-1] == tag_lower:
            self.ignore_stack.pop()
        elif tag_lower in {"p", "h1", "h2", "h3", "h4", "h5", "h6", "li", "tr", "article", "section"}:
            self.text_parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self.ignore_stack:
            cleaned = data.strip()
            if cleaned:
                self.text_parts.append(cleaned + " ")

    def get_text(self, max_chars: int = 1500) -> str:
        raw = "".join(self.text_parts)
        cleaned = re.sub(r"[ \t]+", " ", raw)
        cleaned = re.sub(r"\n\s*\n+", "\n", cleaned).strip()
        if len(cleaned) > max_chars:
            return cleaned[:max_chars].rsplit(" ", 1)[0] + "..."
        return cleaned


def fetch_page_content(url: str, timeout: float = 1.2) -> str:
    """Streams the first 32KB of HTML from URL to rapidly extract top article text with minimal latency."""
    if not url.startswith(("http://", "https://")):
        return ""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9,fi;q=0.8",
    }
    try:
        with (
            httpx.Client(timeout=timeout, follow_redirects=True) as client,
            client.stream("GET", url, headers=headers) as response,
        ):
            if response.status_code == 200:
                chunks = []
                total = 0
                for chunk in response.iter_bytes(chunk_size=8192):
                    chunks.append(chunk)
                    total += len(chunk)
                    if total >= 32768:
                        break
                html_text = b"".join(chunks).decode("utf-8", errors="ignore")
                parser = CleanTextExtractor()
                parser.feed(html_text)
                return parser.get_text()
    except (httpx.HTTPError, OSError, ValueError, TimeoutError):
        pass

    return ""


class SearXNGSearch:
    """Queries SearXNG JSON API for real-time web intelligence."""

    def __init__(self, config: WebSearchConfig):
        self.config = config
        self._cache: dict[str, tuple[float, list[SearchResult]]] = {}
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
            with httpx.Client(timeout=2.5) as client:
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

    def _enrich_with_page_content(self, results: list[SearchResult], max_pages: int = 2) -> None:
        """Concurrently fetches live webpage bodies for the top search results to extract real article text."""
        targets = [r for r in results[:max_pages] if r.url and not r.url.startswith("https://wttr.in")]
        if not targets:
            return

        urls = [t.url for t in targets]
        try:
            with ThreadPoolExecutor(max_workers=len(urls)) as executor:
                page_texts = list(executor.map(fetch_page_content, urls))

            for item, p_text in zip(targets, page_texts):
                if p_text and len(p_text) > 40:
                    item.snippet = (item.snippet + f"\n\nLive Webpage Content:\n{p_text}").strip()
        except (httpx.HTTPError, OSError, ValueError, TimeoutError):
            pass

    def search(self, query: str) -> list[SearchResult]:
        """Executes fast search preferring Google/News with parallel fallback and caching."""
        if not self.config.searxng_url:
            return []

        # Return instant result from 5-minute in-memory cache if available
        now = time.monotonic()
        cache_key = query.strip().lower()
        if cache_key in self._cache:
            ts, cached_results = self._cache[cache_key]
            if now - ts < 300:
                return cached_results

        base_url = self.config.searxng_url.rstrip("/")
        endpoint = f"{base_url}/search"
        effective_query = self._clean_query(query)

        # Fast engine tiers
        fast_engines = "duckduckgo news,reuters,bing,mojeek,duckduckgo"

        def _do_request(request_params: dict[str, Any]) -> list[SearchResult]:
            with httpx.Client(timeout=3.5) as client:
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

        is_news = bool(re.search(r"\b(news|headlines?|uutiset|uutisia|breaking|events?|latest|politics|economy)\b", query, re.IGNORECASE))
        results: list[SearchResult] = []

        try:
            # 1. Query news category or fast engines directly
            if is_news:
                results = _do_request({"q": effective_query, "format": "json", "categories": "news"})
                if not results:
                    results = _do_request({"q": effective_query, "format": "json", "engines": "google news,google,reuters"})
            else:
                # Include Google and fast engines concurrently
                results = _do_request({"q": effective_query, "format": "json", "engines": f"google,{fast_engines}"})

            # 2. If still empty, broad query fallback
            if not results:
                results = _do_request({"q": effective_query, "format": "json"})

            # 3. Fast meteorological sensor lookup if weather query
            self._enrich_with_live_meteo(query, results)

            # 4. Stream top 2 page heads in parallel
            self._enrich_with_page_content(results, max_pages=2)

            if results:
                self._cache[cache_key] = (now, results)

            return results

        except (httpx.HTTPError, OSError) as e:
            if ensure_searxng_container(self.config, non_blocking=False):
                try:
                    results = _do_request({"q": effective_query, "format": "json", "engines": fast_engines})
                    if results:
                        self._enrich_with_live_meteo(query, results)
                        self._enrich_with_page_content(results, max_pages=2)
                        self._cache[cache_key] = (now, results)
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

