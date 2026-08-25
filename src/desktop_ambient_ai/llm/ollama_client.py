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
    def is_model_vision_capable(host: str, model_name: str) -> bool:
        """Dynamically inspects Ollama model metadata to determine if it has vision capabilities."""
        try:
            client = ollama.Client(host=host, timeout=4)
            info = client.show(model_name)
            caps = getattr(info, "capabilities", []) or (info.get("capabilities", []) if isinstance(info, dict) else [])
            if "vision" in caps:
                return True
            details = getattr(info, "details", None) or (info.get("details", {}) if isinstance(info, dict) else {})
            families = getattr(details, "families", []) if hasattr(details, "families") else (details.get("families", []) if isinstance(details, dict) else [])
            if any("clip" in str(f).lower() or "mllama" in str(f).lower() or "vision" in str(f).lower() or "vl" in str(f).lower() for f in families):
                return True
            model_info = getattr(info, "model_info", {}) or (info.get("model_info", {}) if isinstance(info, dict) else {})
            if any("vision" in str(k).lower() or "clip" in str(k).lower() or "mllama" in str(k).lower() for k in model_info.keys()):
                return True
        except Exception:
            pass
        return False

    @staticmethod
    def find_vision_models(host: str = "http://127.0.0.1:11434") -> List[str]:
        """Discovers any vision-capable models currently installed in Ollama."""
        vision_models: List[str] = []
        try:
            models = OllamaWorker.list_models(host=host)
            for m in models:
                name = m.get("name", "")
                if name and OllamaWorker.is_model_vision_capable(host, name):
                    vision_models.append(name)
        except Exception:
            pass
        return vision_models

    def _resolve_model(self) -> Optional[str]:
        """Dynamically determines the model to use from configuration, hot memory, or installed models."""
        if self._mode == "conversation":
            model = self.provider_config.model_conversation or self.provider_config.model
        else:
            model = self.provider_config.model_quick or self.provider_config.model

        if model:
            return model

        # Check models currently resident in VRAM
        running = self.get_running_models(self.provider_config.ollama_host)
        if running:
            return running[0]

        # Check installed models in Ollama
        installed = self.list_models(self.provider_config.ollama_host)
        if installed:
            return installed[0].get("name")

        return None

    def is_vision_capable(self, model: Optional[str] = None) -> bool:
        """Checks if current active model or specified model supports vision."""
        if not model:
            model = self._resolve_model()
        if not model:
            return False
        return self.is_model_vision_capable(self.provider_config.ollama_host, model)

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
        model = self._resolve_model()

        # If image payload is attached, check vision routing
        if self._images:
            if self.provider_config.model_vision:
                model = self.provider_config.model_vision
            elif not model or not self.is_model_vision_capable(self.provider_config.ollama_host, model):
                # Search for any installed vision model in Ollama
                vision_models = self.find_vision_models(self.provider_config.ollama_host)
                if vision_models:
                    model = vision_models[0]
                else:
                    self.stream_error.emit(
                        f"The active model does not support image inputs, and no vision-capable model was found in Ollama.\n"
                        "Please pull a vision-capable model in Ollama to enable screen region analysis."
                    )
                    return

        if not model:
            self.stream_error.emit(
                "No local model configured or found in Ollama.\n"
                "Please install a model using 'ollama pull <model>'."
            )
            return

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

            # Format messages with image payload if present
            formatted_messages = [dict(m) for m in self._messages]
            if self._images and formatted_messages:
                for i in range(len(formatted_messages) - 1, -1, -1):
                    if formatted_messages[i].get("role") == "user":
                        formatted_messages[i]["images"] = self._images
                        break

            kwargs: Dict[str, Any] = {
                "model": model,
                "messages": formatted_messages,
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
                self.stream_error.emit(f"Ollama streaming failed: {str(e)}")
