"""
LiteLLM unified streaming worker for paid/cloud providers.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

import litellm

from ..config import ProviderConfig
from .base import BaseLLMWorker


class LiteLLMWorker(BaseLLMWorker):
    """Executes cloud LLM inferences via LiteLLM with streaming and tool support."""

    def __init__(self, provider_config: ProviderConfig, parent: Optional[Any] = None):
        super().__init__(parent)
        self.provider_config = provider_config

    def _setup_api_keys(self) -> None:
        """Applies configured API keys to environment variables."""
        for key, val in self.provider_config.api_keys.items():
            if val:
                os.environ[key] = val

    def run(self) -> None:
        self._setup_api_keys()
        if self._mode == "conversation":
            model = (
                self.provider_config.litellm_model_conversation
                or self.provider_config.litellm_model
                or "gpt-4o-mini"
            )
        else:
            model = (
                self.provider_config.litellm_model_quick
                or self.provider_config.litellm_model
                or "gpt-4o-mini"
            )

        try:
            kwargs: Dict[str, Any] = {
                "model": model,
                "messages": self._messages,
                "stream": True,
                "timeout": self.provider_config.request_timeout_seconds,
            }
            if self._tools:
                kwargs["tools"] = self._tools

            response = litellm.completion(**kwargs)

            accumulated_tool_calls: List[Dict[str, Any]] = []

            for chunk in response:
                if self.is_cancelled():
                    break

                choices = chunk.get("choices", [])
                if not choices:
                    continue

                delta = choices[0].get("delta", {})
                content = delta.get("content")
                if content:
                    self.token_received.emit(content)

                tool_calls = delta.get("tool_calls", [])
                if tool_calls:
                    for tc in tool_calls:
                        fn = tc.get("function", {})
                        fn_name = fn.get("name", "")
                        fn_args = fn.get("arguments", {})
                        if isinstance(fn_args, str):
                            try:
                                fn_args = json.loads(fn_args)
                            except Exception:
                                pass
                        accumulated_tool_calls.append({
                            "name": fn_name,
                            "arguments": fn_args
                        })

            if accumulated_tool_calls and not self.is_cancelled():
                self.tool_call_requested.emit(accumulated_tool_calls)
            else:
                self.stream_complete.emit()

        except Exception as e:
            if not self.is_cancelled():
                self.stream_error.emit(str(e))
