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
    assert loaded.overlay.prompt_clutter_avoidance is True
    assert loaded.overlay.prompt_fallback == "cursor"


def test_autostart_logic(monkeypatch, tmp_path):
    from desktop_ambient_ai.utils.autostart import setup_autostart, disable_autostart
    import sys

    # 1. Windows test
    monkeypatch.setattr(sys, "platform", "win32")
    fake_appdata = tmp_path / "win_appdata"
    (fake_appdata / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup").mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("APPDATA", str(fake_appdata))

    assert setup_autostart() is True
    vbs = fake_appdata / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup" / "vi.si.on.vbs"
    assert vbs.exists()
    vbs_text = vbs.read_text(encoding="utf-8")
    assert "desktop_ambient_ai.main" in vbs_text or "run vi.si.on" in vbs_text
    assert disable_autostart() is True
    assert not vbs.exists()

    # 2. Linux test
    monkeypatch.setattr(sys, "platform", "linux")
    fake_home = tmp_path / "linux_home"
    monkeypatch.setattr(Path, "home", lambda: fake_home)

    assert setup_autostart() is True
    desktop = fake_home / ".config" / "autostart" / "vi.si.on.desktop"
    assert desktop.exists()
    assert "run vi.si.on" in desktop.read_text(encoding="utf-8")
    assert disable_autostart() is True
    assert not desktop.exists()

    # 3. macOS test
    monkeypatch.setattr(sys, "platform", "darwin")
    fake_mac_home = tmp_path / "mac_home"
    monkeypatch.setattr(Path, "home", lambda: fake_mac_home)

    assert setup_autostart() is True
    plist = fake_mac_home / "Library" / "LaunchAgents" / "com.mitro54.vi.si.on.plist"
    assert plist.exists()
    assert "com.mitro54.vi.si.on" in plist.read_text(encoding="utf-8")
    assert disable_autostart() is True
    assert not plist.exists()

