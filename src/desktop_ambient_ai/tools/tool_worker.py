"""
Background worker for asynchronous tool execution.
Prevents GUI thread blocking during network and tool IO.
"""

from __future__ import annotations

from typing import Any

from PyQt6.QtCore import QThread, pyqtSignal

from .tool_registry import ToolRegistry


class ToolExecutionWorker(QThread):
    """Executes tool calls asynchronously in a background QThread."""

    tool_results_ready = pyqtSignal(dict, list)  # (assistant_tool_msg, tool_results)
    tool_error = pyqtSignal(str)

    def __init__(self, tool_registry: ToolRegistry, parent=None):
        super().__init__(parent)
        self.tool_registry = tool_registry
        self._tool_calls: list[dict[str, Any]] = []

    def execute_async(self, tool_calls: list[dict[str, Any]]) -> None:
        """Starts asynchronous execution of requested tool calls."""
        if self.isRunning():
            self.wait(1500)
        self._tool_calls = tool_calls
        self.start()

    def run(self) -> None:
        """Runs tool invocations in background worker thread."""
        try:
            assistant_tool_msg = {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "function": {
                            "name": tc.get("name", ""),
                            "arguments": tc.get("arguments", {}),
                        }
                    }
                    for tc in self._tool_calls
                ],
            }

            tool_results = []
            for tc in self._tool_calls:
                name = tc.get("name", "")
                args = tc.get("arguments", {})
                result_str = self.tool_registry.execute(name, args)
                tool_results.append({
                    "role": "tool",
                    "name": name,
                    "content": result_str,
                })

            self.tool_results_ready.emit(assistant_tool_msg, tool_results)
        except (RuntimeError, ValueError, OSError, TimeoutError, KeyError) as e:
            self.tool_error.emit(f"Tool execution failed: {e}")
        except BaseException as e:  # noqa: BLE001
            self.tool_error.emit(f"Unexpected tool failure: {e}")

