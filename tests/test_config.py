"""
Unit tests for configuration management.
"""

import json
from pathlib import Path

from desktop_ambient_ai.config import (
    AppConfig,
    HotkeyConfig,
    OverlayConfig,
    ProviderConfig,
    load_config,
    save_config,
)


def test_default_config():
    cfg = AppConfig()
    assert cfg.hotkeys.quick_chat == "<alt>+1"
    assert cfg.hotkeys.conversation == "<alt>+2"
    assert cfg.hotkeys.new_conversation == "<alt>+<shift>+2"
    assert cfg.overlay.min_width == 400
    assert cfg.overlay.min_height == 280
    assert cfg.overlay.auto_close == "timer"
    assert cfg.conversation.promotion_timeout_seconds == 60


def test_save_and_load_config(tmp_path: Path):
    cfg_file = tmp_path / "custom_config.json"
    cfg = AppConfig(
        hotkeys=HotkeyConfig(quick_chat="<ctrl>+1"),
        provider=ProviderConfig(type="litellm", model="gpt-4o"),
        overlay=OverlayConfig(min_width=500, min_height=350, auto_close="manual"),
    )
    save_config(cfg, cfg_file)
    assert cfg_file.exists()

    loaded = load_config(cfg_file)
    assert loaded.hotkeys.quick_chat == "<ctrl>+1"
    assert loaded.provider.type == "litellm"
    assert loaded.provider.model == "gpt-4o"
    assert loaded.overlay.min_width == 500
    assert loaded.overlay.min_height == 350
    assert loaded.overlay.auto_close == "manual"
