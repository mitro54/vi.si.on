"""
Unit tests for tools: SearXNG formatter, ChromaDB knowledge base, and ToolRegistry.
"""

from pathlib import Path

from desktop_ambient_ai.config import AppConfig, KnowledgeBaseConfig, WebSearchConfig
from desktop_ambient_ai.tools.knowledge_base import KnowledgeBase
from desktop_ambient_ai.tools.tool_registry import ToolRegistry
from desktop_ambient_ai.tools.web_search import SearchResult, SearXNGSearch


def test_searxng_formatting_and_schema():
    searcher = SearXNGSearch(WebSearchConfig(enabled=True, searxng_url="http://localhost:8888"))
    results = [
        SearchResult(title="PyQt6 Guide", url="https://pyqt.org", snippet="PyQt6 is a set of Python bindings..."),
        SearchResult(title="OpenCV Docs", url="https://opencv.org", snippet="OpenCV is a computer vision library..."),
    ]
    formatted = searcher.format_results_for_llm(results)
    assert "PyQt6 Guide" in formatted
    assert "https://opencv.org" in formatted

    schema = SearXNGSearch.get_tool_schema()
    assert schema["type"] == "function"
    assert schema["function"]["name"] == "web_search"
    assert "query" in schema["function"]["parameters"]["properties"]


def test_knowledge_base_ingestion(tmp_path: Path):
    persist_dir = tmp_path / "chroma"
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()

    # Create test markdown file
    doc_file = docs_dir / "architecture.md"
    doc_file.write_text(
        "# System Architecture\nThis service uses ChromaDB and 2D integral box convolutions for clutter detection.",
        encoding="utf-8",
    )

    kb_cfg = KnowledgeBaseConfig(
        enabled=True,
        watch_directory=str(docs_dir),
        persist_directory=str(persist_dir),
        top_k=2,
    )

    kb = KnowledgeBase(kb_cfg)
    kb.ingest_directory(docs_dir)

    results = kb.query("integral box convolutions")
    assert len(results) >= 1
    assert "integral box convolutions" in results[0].content

    context_str = kb.format_context_for_prompt("What does the service use for clutter?")
    assert "Relevant Context from User Knowledge Base" in context_str
    kb.stop_watcher()


def test_tool_registry():
    cfg = AppConfig(web_search=WebSearchConfig(enabled=True))
    searcher = SearXNGSearch(cfg.web_search)
    registry = ToolRegistry(config=cfg, web_search=searcher)

    tool_defs = registry.get_tool_definitions()
    assert len(tool_defs) >= 1
    assert any(t["function"]["name"] == "web_search" for t in tool_defs)
