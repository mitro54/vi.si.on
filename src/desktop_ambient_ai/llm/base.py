"""
Abstract base class for streaming LLM workers.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from PyQt6.QtCore import QThread, pyqtSignal


class BaseLLMWorker(QThread):
    """Base QThread worker for streaming LLM responses without blocking the Qt event loop."""

    token_received = pyqtSignal(str)
    stream_complete = pyqtSignal()
    stream_error = pyqtSignal(str)
    tool_call_requested = pyqtSignal(list)  # List of dicts with {"id": ..., "name": ..., "arguments": ...}

    def __init__(self, parent: Optional[Any] = None):
        super().__init__(parent)
        self._is_cancelled = False
        self._messages: List[Dict[str, Any]] = []
        self._tools: Optional[List[Dict[str, Any]]] = None
        self._mode: str = "quick"

    def start_stream(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        mode: str = "quick",
    ) -> None:
        """Configures messages and starts the background execution thread."""
        self._is_cancelled = False
        self._messages = list(messages)
        self._tools = tools
        self._mode = mode
        self.start()

    def cancel(self) -> None:
        """Sets cancellation flag to interrupt streaming."""
        self._is_cancelled = True

    def is_cancelled(self) -> bool:
        return self._is_cancelled

    def run(self) -> None:
        """Override in subclasses."""
        raise NotImplementedError
