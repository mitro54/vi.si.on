"""
Factory for creating the appropriate LLM streaming worker.
"""

from __future__ import annotations

from typing import Any, Optional

from ..config import ProviderConfig
from .base import BaseLLMWorker
from .litellm_client import LiteLLMWorker
from .ollama_client import OllamaWorker


def create_llm_worker(provider_config: ProviderConfig, parent: Optional[Any] = None) -> BaseLLMWorker:
    """Returns an active LLM worker configured for the specified provider."""
    if provider_config.type == "litellm":
        return LiteLLMWorker(provider_config, parent=parent)
    return OllamaWorker(provider_config, parent=parent)
