"""
Cross-platform autostart manager for Windows and Linux.
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path


def get_repo_root() -> Path:
    """Returns absolute path to the repository directory."""
    return Path(__file__).resolve().parent.parent.parent.parent


def setup_autostart() -> bool:
    """Configures vi.si.on to start automatically on user login."""
    repo_dir = get_repo_root()
    py_exec = sys.executable

    if sys.platform == "win32":
        # Windows: Create silent VBS launcher in User Startup folder
        startup_dir = (
            Path(os.environ.get("APPDATA", ""))
            / "Microsoft"
            / "Windows"
            / "Start Menu"
            / "Programs"
            / "Startup"
        )
        if not startup_dir.exists():
            startup_dir.mkdir(parents=True, exist_ok=True)

        vbs_path = startup_dir / "vi.si.on.vbs"
        # Run using exact python executable silently with no popup window
        vbs_content = f'''Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "{repo_dir}"
WshShell.Run "cmd /c ""{py_exec}"" -m uv run vi.si.on", 0, False
'''
        vbs_path.write_text(vbs_content, encoding="utf-8")
        print(f"[Autostart] Enabled for Windows: {vbs_path}")
        return True

    elif sys.platform.startswith("linux"):
        # Linux: Create XDG Autostart desktop entry
        autostart_dir = Path.home() / ".config" / "autostart"
        autostart_dir.mkdir(parents=True, exist_ok=True)

        uv_bin = shutil.which("uv") or "uv"
        desktop_file = autostart_dir / "vi.si.on.desktop"
        desktop_content = f"""[Desktop Entry]
Type=Application
Name=vi.si.on
Comment=Ambient Desktop AI Assistant
Exec=sh -c "cd '{repo_dir}' && {uv_bin} run vi.si.on"
Terminal=false
StartupNotify=false
X-GNOME-Autostart-enabled=true
"""
        desktop_file.write_text(desktop_content, encoding="utf-8")
        print(f"[Autostart] Enabled for Linux (XDG): {desktop_file}")
        return True

    elif sys.platform == "darwin":
        # macOS: Create user LaunchAgent plist
        agents_dir = Path.home() / "Library" / "LaunchAgents"
        agents_dir.mkdir(parents=True, exist_ok=True)

        plist_file = agents_dir / "com.mitro54.vi.si.on.plist"
        plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.mitro54.vi.si.on</string>
    <key>ProgramArguments</key>
    <array>
        <string>{py_exec}</string>
        <string>-m</string>
        <string>uv</string>
        <string>run</string>
        <string>vi.si.on</string>
    </array>
    <key>WorkingDirectory</key>
    <string>{repo_dir}</string>
    <key>RunAtLoad</key>
    <true/>
</dict>
</plist>
"""
        plist_file.write_text(plist_content, encoding="utf-8")
        print(f"[Autostart] Enabled for macOS (LaunchAgent): {plist_file}")
        return True

    return False


def disable_autostart() -> bool:
    """Removes vi.si.on from autostart."""
    if sys.platform == "win32":
        startup_dir = (
            Path(os.environ.get("APPDATA", ""))
            / "Microsoft"
            / "Windows"
            / "Start Menu"
            / "Programs"
            / "Startup"
        )
        vbs_path = startup_dir / "vi.si.on.vbs"
        if vbs_path.exists():
            vbs_path.unlink()
            print(f"[Autostart] Removed Windows autostart: {vbs_path}")
            return True
        print("[Autostart] Windows autostart was not enabled.")
        return False

    elif sys.platform.startswith("linux"):
        desktop_file = Path.home() / ".config" / "autostart" / "vi.si.on.desktop"
        if desktop_file.exists():
            desktop_file.unlink()
            print(f"[Autostart] Removed Linux autostart: {desktop_file}")
            return True
        print("[Autostart] Linux autostart was not enabled.")
        return False

    elif sys.platform == "darwin":
        plist_file = Path.home() / "Library" / "LaunchAgents" / "com.mitro54.vi.si.on.plist"
        if plist_file.exists():
            plist_file.unlink()
            print(f"[Autostart] Removed macOS autostart: {plist_file}")
            return True
        print("[Autostart] macOS autostart was not enabled.")
        return False

    return False
