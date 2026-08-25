"""
Multi-monitor screenshot grabber and window focus detector.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import List, Optional, Tuple

import mss
import numpy as np

# Qt 6 automatically manages DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 on Windows.



@dataclass
class MonitorInfo:
    index: int
    left: int           # Logical desktop coordinates (Qt space)
    top: int            # Logical desktop coordinates (Qt space)
    width: int          # Logical width (Qt space)
    height: int         # Logical height (Qt space)
    dpr: float = 1.0    # Device pixel ratio (1.0 on 1080p, 1.5 or 2.0 on 4K)
    physical_left: int = 0
    physical_top: int = 0
    physical_width: int = 0
    physical_height: int = 0

    @property
    def right(self) -> int:
        return self.left + self.width

    @property
    def bottom(self) -> int:
        return self.top + self.height

    def contains(self, x: int, y: int) -> bool:
        return self.left <= x < self.right and self.top <= y < self.bottom


class ScreenCapture:
    """Handles cross-platform monitor enumeration, screenshot capture, and focus detection."""

    def __init__(self):
        self._sct = mss.mss()

    def get_all_monitors(self) -> List[MonitorInfo]:
        """Returns individual monitors synchronized with Qt logical space and physical grab bounds."""
        monitors = []
        sct_displays = self._sct.monitors[1:] if len(self._sct.monitors) > 1 else self._sct.monitors

        try:
            from PyQt6.QtGui import QGuiApplication
            screens = QGuiApplication.screens()
            if screens:
                for idx, screen in enumerate(screens, start=1):
                    geo = screen.geometry()
                    dpr = float(screen.devicePixelRatio()) or 1.0

                    phys_left = int(geo.left() * dpr)
                    phys_top = int(geo.top() * dpr)
                    phys_w = int(geo.width() * dpr)
                    phys_h = int(geo.height() * dpr)

                    # Match with MSS hardware monitor bounds if available
                    if idx - 1 < len(sct_displays):
                        m = sct_displays[idx - 1]
                        phys_left = m["left"]
                        phys_top = m["top"]
                        phys_w = m["width"]
                        phys_h = m["height"]

                    monitors.append(
                        MonitorInfo(
                            index=idx,
                            left=geo.left(),
                            top=geo.top(),
                            width=geo.width(),
                            height=geo.height(),
                            dpr=dpr,
                            physical_left=phys_left,
                            physical_top=phys_top,
                            physical_width=phys_w,
                            physical_height=phys_h,
                        )
                    )
                return monitors
        except Exception:
            pass

        # Fallback to raw MSS enumeration if Qt GUI application is not initialized
        for idx, m in enumerate(sct_displays, start=1):
            monitors.append(
                MonitorInfo(
                    index=idx,
                    left=m["left"],
                    top=m["top"],
                    width=m["width"],
                    height=m["height"],
                    dpr=1.0,
                    physical_left=m["left"],
                    physical_top=m["top"],
                    physical_width=m["width"],
                    physical_height=m["height"],
                )
            )
        return monitors

    def get_monitor_under_cursor(self, mouse_x: int, mouse_y: int) -> MonitorInfo:
        """Finds which monitor contains the given cursor coordinates."""
        monitors = self.get_all_monitors()
        for m in monitors:
            if m.contains(mouse_x, mouse_y):
                return m
        return monitors[0]

    def get_focused_window_rect(self) -> Optional[Tuple[int, int, int, int]]:
        """
        Returns (left, top, width, height) of currently focused foreground window.
        Returns None if undetermined or on unsupported environments.
        """
        if sys.platform == "win32":
            try:
                import ctypes
                from ctypes import wintypes
                hwnd = ctypes.windll.user32.GetForegroundWindow()
                if hwnd:
                    rect = wintypes.RECT()
                    ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect))
                    return (
                        rect.left,
                        rect.top,
                        rect.right - rect.left,
                        rect.bottom - rect.top,
                    )
            except Exception:
                pass
        elif sys.platform.startswith("linux"):
            try:
                import subprocess
                out = subprocess.check_output(["xdotool", "getactivewindow", "getwindowgeometry"], text=True)
                lines = out.strip().splitlines()
                pos_line = next((l for l in lines if "Position:" in l), None)
                geo_line = next((l for l in lines if "Geometry:" in l), None)
                if pos_line and geo_line:
                    pos = pos_line.split("Position:")[1].split()[0].split(",")
                    geo = geo_line.split("Geometry:")[1].split()[0].split("x")
                    return (int(pos[0]), int(pos[1]), int(geo[0]), int(geo[1]))
            except Exception:
                pass
        return None

    def get_focused_window_monitor(self) -> MonitorInfo:
        """Determines which monitor houses the active foreground window."""
        monitors = self.get_all_monitors()
        rect = self.get_focused_window_rect()
        if rect:
            x, y, w, h = rect
            center_x = x + w // 2
            center_y = y + h // 2
            for m in monitors:
                if m.contains(center_x, center_y):
                    return m
        # Fallback to primary / first monitor
        return monitors[0]

    def is_exclusive_fullscreen(self) -> bool:
        """
        Heuristic to detect if focused window covers an entire monitor without margins.
        Helps protect games and avoid anti-cheat collision or game overlay flicker.
        """
        rect = self.get_focused_window_rect()
        if not rect:
            return False
        wx, wy, ww, wh = rect
        monitors = self.get_all_monitors()
        for m in monitors:
            # Check if window geometry matches full monitor bounds
            if abs(wx - m.left) <= 5 and abs(wy - m.top) <= 5 and abs(ww - m.width) <= 10 and abs(wh - m.height) <= 10:
                return True
        return False

    def capture_monitor(self, monitor: MonitorInfo) -> np.ndarray:
        """Captures a screenshot of the specified monitor and returns a BGR NumPy array."""
        bbox = {
            "left": monitor.physical_left if monitor.physical_width > 0 else monitor.left,
            "top": monitor.physical_top if monitor.physical_height > 0 else monitor.top,
            "width": monitor.physical_width if monitor.physical_width > 0 else monitor.width,
            "height": monitor.physical_height if monitor.physical_height > 0 else monitor.height,
        }
        sct_img = self._sct.grab(bbox)
        # Convert BGRA to BGR numpy array
        img = np.array(sct_img)
        if img.shape[2] == 4:
            img = img[:, :, :3]  # Drop alpha channel
        return img
