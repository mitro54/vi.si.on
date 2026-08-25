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
        # Determine best execution target: prefer pythonw.exe for silent, windowless launch
        pythonw = Path(py_exec).with_name("pythonw.exe")
        uv_bin = shutil.which("uv")

        if pythonw.exists():
            exec_target = f'""{pythonw}"" -m desktop_ambient_ai.main'
        elif uv_bin:
            exec_target = f'cmd /c ""{uv_bin}"" run vi.si.on'
        else:
            exec_target = f'""{py_exec}"" -m desktop_ambient_ai.main'

        # Run silently with no popup window
        vbs_content = f'''Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "{repo_dir}"
WshShell.Run "{exec_target}", 0, False
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
        # Automatically register GNOME custom shortcuts if on GNOME/Ubuntu
        setup_gnome_shortcuts()
        return True

    elif sys.platform == "darwin":
        # macOS: Create user LaunchAgent plist
        agents_dir = Path.home() / "Library" / "LaunchAgents"
        agents_dir.mkdir(parents=True, exist_ok=True)

        plist_file = agents_dir / "com.mitro54.vi.si.on.plist"
        uv_bin = shutil.which("uv")
        if uv_bin:
            prog_args = f"""        <string>{uv_bin}</string>
        <string>run</string>
        <string>vi.si.on</string>"""
        else:
            prog_args = f"""        <string>{py_exec}</string>
        <string>-m</string>
        <string>desktop_ambient_ai.main</string>"""

        plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.mitro54.vi.si.on</string>
    <key>ProgramArguments</key>
    <array>
{prog_args}
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


def setup_gnome_shortcuts() -> bool:
    """Configures GNOME custom shortcuts for vi.si.on on Ubuntu/Wayland via gsettings."""
    import subprocess

    if not shutil.which("gsettings"):
        return False

    repo_dir = get_repo_root()
    uv_bin = shutil.which("uv") or "uv"
    py_exec = sys.executable

    if shutil.which("uv"):
        exec_cmd = f"{uv_bin} run vi.si.on"
    else:
        exec_cmd = f"'{py_exec}' -m desktop_ambient_ai.main"

    shortcuts = [
        ("vision-quick", "vi.si.on Quick Query", f"sh -c \"cd '{repo_dir}' && {exec_cmd} --quick\"", "<Alt>1"),
        ("vision-conv", "vi.si.on Active Thread", f"sh -c \"cd '{repo_dir}' && {exec_cmd} --conversation\"", "<Alt>2"),
        ("vision-new", "vi.si.on New Thread", f"sh -c \"cd '{repo_dir}' && {exec_cmd} --new\"", "<Alt><Shift>2"),
        ("vision-snip", "vi.si.on Region Snip", f"sh -c \"cd '{repo_dir}' && {exec_cmd} --snip\"", "<Alt>3"),
        ("vision-picker", "vi.si.on History Picker", f"sh -c \"cd '{repo_dir}' && {exec_cmd} --picker\"", "<Alt><Shift>h"),
    ]

    try:
        res = subprocess.run(
            ["gsettings", "get", "org.gnome.settings-daemon.plugins.media-keys", "custom-keybindings"],
            capture_output=True,
            text=True,
            check=True,
        )
        current = res.stdout.strip()
        existing_paths = []
        if current.startswith("[") and current.endswith("]"):
            content = current[1:-1].strip()
            if content and content != "@as []":
                existing_paths = [p.strip().strip("'\"") for p in content.split(",") if p.strip()]

        for key_id, name, cmd, binding in shortcuts:
            path = f"/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/{key_id}/"
            if path not in existing_paths:
                existing_paths.append(path)

            schema = f"org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:{path}"
            subprocess.run(["gsettings", "set", schema, "name", name], check=True)
            subprocess.run(["gsettings", "set", schema, "command", cmd], check=True)
            subprocess.run(["gsettings", "set", schema, "binding", binding], check=True)

        paths_str = "[" + ", ".join(f"'{p}'" for p in existing_paths) + "]"
        subprocess.run(
            ["gsettings", "set", "org.gnome.settings-daemon.plugins.media-keys", "custom-keybindings", paths_str],
            check=True,
        )
        print("[Shortcuts] Configured GNOME desktop custom shortcuts for vi.si.on (Alt+1, Alt+2, Alt+Shift+2, Alt+3, Alt+Shift+H).")
        return True
    except Exception as e:
        print(f"[Shortcuts] Note: Could not configure GNOME shortcuts automatically: {e}")
        return False


def disable_gnome_shortcuts() -> bool:
    """Removes vi.si.on custom shortcuts from GNOME settings."""
    import subprocess

    if not shutil.which("gsettings"):
        return False

    try:
        res = subprocess.run(
            ["gsettings", "get", "org.gnome.settings-daemon.plugins.media-keys", "custom-keybindings"],
            capture_output=True,
            text=True,
            check=True,
        )
        current = res.stdout.strip()
        if not (current.startswith("[") and current.endswith("]")):
            return False

        content = current[1:-1].strip()
        if not content or content == "@as []":
            return False

        existing_paths = [p.strip().strip("'\"") for p in content.split(",") if p.strip()]
        new_paths = [p for p in existing_paths if "vision-" not in p]

        paths_str = "[" + ", ".join(f"'{p}'" for p in new_paths) + "]" if new_paths else "@as []"
        subprocess.run(
            ["gsettings", "set", "org.gnome.settings-daemon.plugins.media-keys", "custom-keybindings", paths_str],
            check=True,
        )
        print("[Shortcuts] Removed GNOME custom shortcuts for vi.si.on.")
        return True
    except Exception:
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
        removed = False
        if desktop_file.exists():
            desktop_file.unlink()
            print(f"[Autostart] Removed Linux autostart: {desktop_file}")
            removed = True
        else:
            print("[Autostart] Linux autostart was not enabled.")
        disable_gnome_shortcuts()
        return removed

    elif sys.platform == "darwin":
        plist_file = Path.home() / "Library" / "LaunchAgents" / "com.mitro54.vi.si.on.plist"
        if plist_file.exists():
            plist_file.unlink()
            print(f"[Autostart] Removed macOS autostart: {plist_file}")
            return True
        print("[Autostart] macOS autostart was not enabled.")
        return False

    return False
