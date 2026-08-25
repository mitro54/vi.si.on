"""
Ollama streaming client running on a dedicated QThread.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

import ollama

from ..config import ProviderConfig
from .base import BaseLLMWorker


class OllamaWorker(BaseLLMWorker):
    """Executes Ollama streaming inferences with tool call support."""

    def __init__(self, provider_config: ProviderConfig, parent: Optional[Any] = None):
        super().__init__(parent)
        self.provider_config = provider_config
        self.client = ollama.Client(host=provider_config.ollama_host)

    @staticmethod
    def list_models(host: str = "http://localhost:11434") -> List[Dict[str, Any]]:
        """Queries Ollama API for available local models."""
        try:
            client = ollama.Client(host=host)
            response = client.list()
            # In latest ollama python package, response is a ListResponse object with .models
            models_list = []
            models_raw = getattr(response, "models", None) or response.get("models", [])
            for m in models_raw:
                if hasattr(m, "model"):
                    name = m.model
                    size = getattr(m, "size", 0)
                    details = getattr(m, "details", None)
                    param_size = getattr(details, "parameter_size", "") if details else ""
                elif isinstance(m, dict):
                    name = m.get("model") or m.get("name", "")
                    size = m.get("size", 0)
                    details = m.get("details", {})
                    param_size = details.get("parameter_size", "") if isinstance(details, dict) else ""
                else:
                    name = str(m)
                    size = 0
                    param_size = ""

                # Format readable size (GB/MB)
                size_str = f"{size / (1024 ** 3):.1f} GB" if size > 1024 ** 3 else f"{size / (1024 ** 2):.0f} MB"
                models_list.append({
                    "name": name,
                    "size": size_str,
                    "param_size": param_size
                })
            return models_list
        except Exception as e:
            return []

    @staticmethod
    def get_running_models(host: str = "http://localhost:11434") -> List[str]:
        """Returns the list of model names currently loaded in memory/VRAM ('hot')."""
        try:
            client = ollama.Client(host=host, timeout=3)
            res = client.ps()
            running: List[str] = []
            models_raw = getattr(res, "models", None) or (res.get("models", []) if isinstance(res, dict) else [])
            for m in models_raw:
                name = getattr(m, "model", None) or (m.get("model") if isinstance(m, dict) else str(m))
                if name:
                    running.append(name)
            return running
        except Exception:
            return []

    def run(self) -> None:
        # Select model based on mode (quick chat vs memorized conversation)
        if self._mode == "conversation":
            model = self.provider_config.model_conversation or self.provider_config.model or "llama3.2:latest"
        else:
            model = self.provider_config.model_quick or self.provider_config.model or "llama3.2:latest"

        try:
            client = ollama.Client(
                host=self.provider_config.ollama_host,
                timeout=self.provider_config.request_timeout_seconds,
            )

            # Check if there is already a hot model loaded in memory matching the requested model
            try:
                running_models = self.get_running_models(self.provider_config.ollama_host)
                if running_models:
                    # If exact or prefix match exists in hot models, prioritize the hot model name
                    for rm in running_models:
                        if model == rm or model in rm or rm in model:
                            model = rm
                            break
            except Exception:
                pass

            # Select context window size based on query mode (16k quick, 64k conversation)
            num_ctx = (
                self.provider_config.num_ctx_conversation
                if self._mode == "conversation"
                else self.provider_config.num_ctx_quick
            )

            # Select keep_alive window: 10m for conversations, 3m for quick one-off queries
            keep_alive = (
                self.provider_config.keep_alive_conversation
                if self._mode == "conversation"
                else self.provider_config.keep_alive_quick
            )

            kwargs: Dict[str, Any] = {
                "model": model,
                "messages": self._messages,
                "stream": True,
                "keep_alive": keep_alive,  # Resets the in-memory retention timer with every query
                "options": {
                    "num_ctx": num_ctx,
                },
            }
            if self._tools:
                kwargs["tools"] = self._tools

            response_stream = client.chat(**kwargs)

            accumulated_tool_calls: List[Dict[str, Any]] = []

            for chunk in response_stream:
                if self.is_cancelled():
                    break

                # Support dict or object chunk
                msg = getattr(chunk, "message", None) or chunk.get("message", {})
                content = getattr(msg, "content", None) if hasattr(msg, "content") else msg.get("content", "")
                tool_calls = getattr(msg, "tool_calls", None) if hasattr(msg, "tool_calls") else msg.get("tool_calls", [])

                if content:
                    self.token_received.emit(content)

                if tool_calls:
                    for tc in tool_calls:
                        # Extract tool call structure
                        fn = getattr(tc, "function", None) or tc.get("function", {})
                        fn_name = getattr(fn, "name", "") if hasattr(fn, "name") else fn.get("name", "")
                        fn_args = getattr(fn, "arguments", {}) if hasattr(fn, "arguments") else fn.get("arguments", {})
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
