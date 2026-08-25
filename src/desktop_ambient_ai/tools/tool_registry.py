"""
Unified Tool Registry for aggregating enabled tools and routing executions.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..config import AppConfig
from .knowledge_base import KnowledgeBase
from .mcp_bridge import MCPBridge
from .web_search import SearXNGSearch


class ToolRegistry:
    """Aggregates all enabled tools and dispatches execution requests."""

    def __init__(
        self,
        config: AppConfig,
        web_search: Optional[SearXNGSearch] = None,
        knowledge_base: Optional[KnowledgeBase] = None,
        mcp_bridge: Optional[MCPBridge] = None,
    ):
        self.config = config
        self.web_search = web_search
        self.knowledge_base = knowledge_base
        self.mcp_bridge = mcp_bridge

    def get_tool_definitions(self) -> List[Dict[str, Any]]:
        """Returns tool schema definitions for active tools."""
        tools: List[Dict[str, Any]] = []

        if self.config.web_search.enabled and self.web_search:
            tools.append(self.web_search.get_tool_schema())

        if self.config.knowledge_base.enabled and self.knowledge_base:
            tools.append(self.knowledge_base.get_tool_schema())

        if self.mcp_bridge:
            mcp_tools = self.mcp_bridge.discover_tools_sync()
            tools.extend(mcp_tools)

        return tools

    def execute(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        """Routes tool execution and returns text payload."""
        if tool_name == "web_search" and self.web_search:
            query = arguments.get("query", "")
            results = self.web_search.search(query)
            return self.web_search.format_results_for_llm(results)

        elif tool_name == "search_knowledge_base" and self.knowledge_base:
            query = arguments.get("query", "")
            chunks = self.knowledge_base.query(query)
            if not chunks:
                return "No matching local documents found."
            return "\n\n".join([f"[{c.source}]: {c.content}" for c in chunks])

        elif tool_name.startswith("mcp__") and self.mcp_bridge:
            return self.mcp_bridge.execute_tool_sync(tool_name, arguments)

        return f"Unknown tool: {tool_name}"
