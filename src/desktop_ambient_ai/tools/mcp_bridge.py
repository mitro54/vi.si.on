"""
Model Context Protocol (MCP) Client Bridge.
"""

from __future__ import annotations

import asyncio
import json
import threading
from typing import Any, Dict, List, Optional

from ..config import MCPServerConfig


class MCPBridge:
    """Manages MCP server processes and converts tools to OpenAI function calling format."""

    def __init__(self, server_configs: List[MCPServerConfig]):
        self.server_configs = server_configs
        self._tools_cache: List[Dict[str, Any]] = []
        self._server_tool_map: Dict[str, MCPServerConfig] = {}

    def discover_tools_sync(self) -> List[Dict[str, Any]]:
        """Synchronously discovers tools from configured MCP servers."""
        if not self.server_configs:
            return []

        try:
            return asyncio.run(self.discover_tools())
        except Exception:
            return []

    async def discover_tools(self) -> List[Dict[str, Any]]:
        """Connects to MCP servers and loads available tool schemas."""
        tools_list: List[Dict[str, Any]] = []
        for server in self.server_configs:
            if server.transport == "stdio" and server.command:
                try:
                    from mcp import Client
                    from mcp.client.stdio import StdioServerParameters, stdio_client

                    server_params = StdioServerParameters(
                        command=server.command,
                        args=server.args,
                        env=server.env if server.env else None,
                    )

                    async with stdio_client(server_params) as (read, write):
                        async with Client(read, write) as client:
                            await client.initialize()
                            server_tools = await client.list_tools()
                            for t in server_tools:
                                tool_name = getattr(t, "name", "") or t.get("name", "")
                                desc = getattr(t, "description", "") or t.get("description", "")
                                schema = getattr(t, "inputSchema", None) or t.get("inputSchema", {})

                                namespaced_name = f"mcp__{server.name}__{tool_name}"
                                self._server_tool_map[namespaced_name] = server

                                tools_list.append({
                                    "type": "function",
                                    "function": {
                                        "name": namespaced_name,
                                        "description": f"[{server.name}] {desc}",
                                        "parameters": schema or {"type": "object", "properties": {}},
                                    },
                                })
                except Exception as e:
                    print(f"[MCP] Failed to connect to server {server.name}: {e}")

        self._tools_cache = tools_list
        return tools_list

    def execute_tool_sync(self, namespaced_name: str, arguments: Dict[str, Any]) -> str:
        """Synchronously invokes an MCP tool."""
        try:
            return asyncio.run(self.execute_tool(namespaced_name, arguments))
        except Exception as e:
            return f"Error executing MCP tool {namespaced_name}: {e}"

    async def execute_tool(self, namespaced_name: str, arguments: Dict[str, Any]) -> str:
        """Invokes a specific MCP tool and returns string result."""
        server = self._server_tool_map.get(namespaced_name)
        if not server:
            return f"Unknown MCP tool: {namespaced_name}"

        # Unpack original name: mcp__<server>__<tool>
        parts = namespaced_name.split("__")
        original_name = parts[-1] if len(parts) >= 3 else namespaced_name

        try:
            from mcp import Client
            from mcp.client.stdio import StdioServerParameters, stdio_client

            server_params = StdioServerParameters(
                command=server.command or "",
                args=server.args,
                env=server.env if server.env else None,
            )

            async with stdio_client(server_params) as (read, write):
                async with Client(read, write) as client:
                    await client.initialize()
                    result = await client.call_tool(original_name, arguments)
                    content = getattr(result, "content", [])
                    if isinstance(content, list):
                        text_parts = [getattr(c, "text", str(c)) for c in content]
                        return "\n".join(text_parts)
                    return str(result)
        except Exception as e:
            return f"MCP tool execution failed ({namespaced_name}): {e}"
