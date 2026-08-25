"""
Configuration management with dataclasses, defaults, and disk persistence.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional


@dataclass
class HotkeyConfig:
    quick_chat: str = "<alt>+1"
    conversation: str = "<alt>+2"
    new_conversation: str = "<alt>+<shift>+2"
    ocr_selection: str = "<alt>+3"
    dismiss: str = "<esc>"


@dataclass
class ProviderConfig:
    type: Literal["ollama", "litellm"] = "ollama"
    model: Optional[str] = None
    model_quick: Optional[str] = None
    model_conversation: Optional[str] = None
    model_vision: Optional[str] = None
    ollama_host: str = "http://127.0.0.1:11434"
    litellm_model: Optional[str] = None
    litellm_model_quick: Optional[str] = None
    litellm_model_conversation: Optional[str] = None
    litellm_model_vision: Optional[str] = None
    api_keys: Dict[str, str] = field(default_factory=dict)
    num_ctx: int = 16384
    num_ctx_quick: int = 16384
    num_ctx_conversation: int = 65536
    request_timeout_seconds: int = 120
    keep_alive_quick: str = "3m"
    keep_alive_conversation: str = "10m"






@dataclass
class OverlayConfig:
    min_width: int = 400
    min_height: int = 280
    max_width: int = 620
    max_height: int = 520
    auto_close: Literal["timer", "immediate", "manual"] = "timer"
    auto_close_seconds: int = 15
    screen_target: Literal["same_screen", "alternate_screen"] = "same_screen"
    prompt_placement: Literal["cursor", "center"] = "cursor"
    answer_placement: Literal["clearest_area", "center", "cursor"] = "clearest_area"
    prefer_alternate_monitor: bool = False



@dataclass
class ConversationConfig:
    promotion_timeout_seconds: int = 60
    persist_to_disk: bool = True


@dataclass
class TypographyConfig:
    font_base_size: int = 15
    font_min_size: int = 13
    downscale_threshold: int = 350
    downscale_rate: int = 200


@dataclass
class WebSearchConfig:
    enabled: bool = False
    searxng_url: str = "http://localhost:8888"
    max_results: int = 5


@dataclass
class KnowledgeBaseConfig:
    enabled: bool = False
    watch_directory: Optional[str] = None
    persist_directory: Optional[str] = None
    top_k: int = 3


@dataclass
class MCPServerConfig:
    name: str
    transport: Literal["stdio", "sse", "http"] = "stdio"
    command: Optional[str] = None
    args: List[str] = field(default_factory=list)
    url: Optional[str] = None
    env: Dict[str, str] = field(default_factory=dict)


@dataclass
class AppConfig:
    hotkeys: HotkeyConfig = field(default_factory=HotkeyConfig)
    provider: ProviderConfig = field(default_factory=ProviderConfig)
    overlay: OverlayConfig = field(default_factory=OverlayConfig)
    conversation: ConversationConfig = field(default_factory=ConversationConfig)
    system_prompt: str = (
        "You are a precise, context-aware desktop assistant. Provide direct, accurate, "
        "and well-structured answers. Use code blocks for code. Prioritize correctness. "
        "When information may be outdated, indicate this. Format for quick scanning: "
        "bullets, bold key terms, concise headers."
    )
    typography: TypographyConfig = field(default_factory=TypographyConfig)
    web_search: WebSearchConfig = field(default_factory=WebSearchConfig)
    knowledge_base: KnowledgeBaseConfig = field(default_factory=KnowledgeBaseConfig)
    mcp_servers: List[MCPServerConfig] = field(default_factory=list)
    edge_density_fallback_threshold: float = 0.35
    setup_complete: bool = False


def get_default_config_dir() -> Path:
    """Returns platform-specific configuration directory."""
    if sys.platform == "win32":
        app_data = os.environ.get("APPDATA")
        base = Path(app_data) if app_data else Path.home() / "AppData" / "Roaming"
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        xdg = os.environ.get("XDG_CONFIG_HOME")
        base = Path(xdg) if xdg else Path.home() / ".config"
    return base / "vi.si.on"


def get_default_data_dir() -> Path:
    """Returns platform-specific data storage directory."""
    if sys.platform == "win32":
        local_app = os.environ.get("LOCALAPPDATA")
        base = Path(local_app) if local_app else Path.home() / "AppData" / "Local"
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        xdg = os.environ.get("XDG_DATA_HOME")
        base = Path(xdg) if xdg else Path.home() / ".local" / "share"
    return base / "vi.si.on"


def get_config_path(custom_path: Optional[str] = None) -> Path:
    """Resolves config file path."""
    if custom_path:
        return Path(custom_path).resolve()
    # Check current working directory first (for portable dev runs)
    local_cfg = Path("config.json").resolve()
    if local_cfg.exists():
        return local_cfg
    config_dir = get_default_config_dir()
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir / "config.json"


def _deep_update(target: Dict[str, Any], source: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively updates a nested dictionary."""
    for key, val in source.items():
        if isinstance(val, dict) and key in target and isinstance(target[key], dict):
            _deep_update(target[key], val)
        else:
            target[key] = val
    return target


def load_config(config_path: Optional[Path | str] = None) -> AppConfig:
    """Loads configuration from disk or returns default configuration."""
    path = get_config_path(str(config_path) if config_path else None)
    if not path.exists():
        cfg = AppConfig()
        save_config(cfg, path)
        return cfg

    try:
        with open(path, "r", encoding="utf-8") as f:
            raw_data = json.load(f)

        default_dict = asdict(AppConfig())
        merged = _deep_update(default_dict, raw_data)

        # Parse sub-dataclasses
        hotkeys = HotkeyConfig(**merged.get("hotkeys", {}))
        provider = ProviderConfig(**merged.get("provider", {}))
        overlay = OverlayConfig(**merged.get("overlay", {}))
        conversation = ConversationConfig(**merged.get("conversation", {}))
        typography = TypographyConfig(**merged.get("typography", {}))
        web_search = WebSearchConfig(**merged.get("web_search", {}))
        knowledge_base = KnowledgeBaseConfig(**merged.get("knowledge_base", {}))

        raw_mcp = merged.get("mcp_servers", [])
        mcp_servers = [
            MCPServerConfig(**s) if isinstance(s, dict) else s for s in raw_mcp
        ]

        return AppConfig(
            hotkeys=hotkeys,
            provider=provider,
            overlay=overlay,
            conversation=conversation,
            system_prompt=merged.get("system_prompt", AppConfig().system_prompt),
            typography=typography,
            web_search=web_search,
            knowledge_base=knowledge_base,
            mcp_servers=mcp_servers,
            edge_density_fallback_threshold=merged.get(
                "edge_density_fallback_threshold", 0.35
            ),
            setup_complete=merged.get("setup_complete", False),
        )
    except Exception as e:
        print(f"[Config] Error loading {path}: {e}. Using defaults.", file=sys.stderr)
        return AppConfig()


def save_config(config: AppConfig, config_path: Optional[Path | str] = None) -> None:
    """Saves configuration to disk."""
    path = get_config_path(str(config_path) if config_path else None)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(asdict(config), f, indent=2)
