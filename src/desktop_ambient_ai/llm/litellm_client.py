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

    def _resolve_model(self) -> Optional[str]:
        """Resolves configured cloud model."""
        if self._mode == "conversation":
            return (
                self.provider_config.litellm_model_conversation
                or self.provider_config.litellm_model
            )
        return (
            self.provider_config.litellm_model_quick
            or self.provider_config.litellm_model
        )

    def is_vision_capable(self, model: Optional[str] = None) -> bool:
        """Checks if configured cloud model supports multimodal vision via LiteLLM."""
        if not model:
            model = self.provider_config.litellm_model_vision or self._resolve_model()
        if not model:
            return False
        try:
            if litellm.supports_vision(model):
                return True
        except Exception:
            pass
        lower = str(model).lower()
        return any(k in lower for k in ("vision", "vl", "multimodal", "4o", "claude-3", "gemini"))

    def run(self) -> None:
        self._setup_api_keys()
        model = self._resolve_model()
        if self._images and self.provider_config.litellm_model_vision:
            model = self.provider_config.litellm_model_vision

        if not model:
            self.stream_error.emit("No Cloud/LiteLLM model configured. Please specify a model in settings.")
            return

        try:
            formatted_messages = []
            for m in self._messages:
                msg_copy = dict(m)
                if self._images and msg_copy.get("role") == "user" and m == self._messages[-1]:
                    content_text = str(msg_copy.get("content", ""))
                    parts: List[Dict[str, Any]] = [{"type": "text", "text": content_text}]
                    for img_b64 in self._images:
                        parts.append({
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{img_b64}"}
                        })
                    msg_copy["content"] = parts
                formatted_messages.append(msg_copy)

            kwargs: Dict[str, Any] = {
                "model": model,
                "messages": formatted_messages,
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
