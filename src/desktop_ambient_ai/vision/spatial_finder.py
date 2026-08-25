"""
Computer vision heuristics for spatial clutter minimization and dynamic contrast styling.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Tuple

import cv2
import numpy as np

from ..config import AppConfig, OverlayConfig, TypographyConfig
from .capture import MonitorInfo


@dataclass
class TargetRect:
    x: int
    y: int
    width: int
    height: int


@dataclass
class ThemeConfig:
    is_dark_background: bool = True
    text_color: str = "#F8FAFC"
    backing_tint: str = "rgba(15, 23, 42, 0.78)"
    text_shadow: str = "0 1px 3px rgba(0, 0, 0, 0.9)"
    border_color: str = "rgba(148, 163, 184, 0.25)"
    accent_color: str = "#38BDF8"


@dataclass
class DynamicTypography:
    base_font_size: int
    min_font_size: int
    downscale_threshold: int
    downscale_rate: int
    line_height: float = 1.45


@dataclass
class SpatialResult:
    target_rect: TargetRect
    theme: ThemeConfig
    typography: DynamicTypography
    is_fallback_mode: bool
    monitor: MonitorInfo


class SpatialFinder:
    """Finds the least-cluttered desktop region and generates adaptive typography/contrast schemes."""

    def __init__(self, config: AppConfig):
        self.config = config

    def analyze(
        self,
        frame: np.ndarray,
        monitor: MonitorInfo,
        desired_width: int | None = None,
        desired_height: int | None = None,
        prompt_rect: Optional[Any] = None,
    ) -> SpatialResult:
        """
        Executes edge density scanning on the frame to identify the clearest screen region,
        computes background luminance, and returns complete spatial parameters.
        """
        overlay_cfg: OverlayConfig = self.config.overlay
        w_min = max(200, overlay_cfg.min_width)
        h_min = max(150, overlay_cfg.min_height)
        w_max = max(w_min, overlay_cfg.max_width)
        h_max = max(h_min, overlay_cfg.max_height)

        dpr = float(monitor.dpr) if hasattr(monitor, "dpr") and monitor.dpr else 1.0
        frame_h, frame_w = frame.shape[:2]

        # Convert logical min/max dimensions to physical pixels for CV analysis
        phys_w_min = int(w_min * dpr)
        phys_h_min = int(h_min * dpr)
        phys_w_max = int(w_max * dpr)
        phys_h_max = int(h_max * dpr)

        desired_phys_w = int(desired_width * dpr) if desired_width else None
        desired_phys_h = int(desired_height * dpr) if desired_height else None

        phys_win_w = desired_phys_w if desired_phys_w else phys_w_min + (phys_w_max - phys_w_min) // 2
        phys_win_h = desired_phys_h if desired_phys_h else phys_h_min + (phys_h_max - phys_h_min) // 2

        phys_win_w = min(max(phys_win_w, phys_w_min), max(100, frame_w - int(48 * dpr)))
        phys_win_h = min(max(phys_win_h, phys_h_min), max(100, frame_h - int(48 * dpr)))

        # 1. Check Placement Strategy
        margin = int(32 * dpr)
        is_fallback = False
        best_x = margin
        best_y = margin

        placement = overlay_cfg.answer_placement

        if placement == "center":
            best_x = max(0, (frame_w - phys_win_w) // 2)
            best_y = max(0, (frame_h - phys_win_h) // 2)
        elif placement in ("cursor", "prompt"):
            if prompt_rect is not None:
                # Align directly with the location where the user saw the prompt box
                rel_px = int((prompt_rect.x() - monitor.left) * dpr)
                rel_py = int((prompt_rect.y() - monitor.top) * dpr)
                best_x = max(margin, min(rel_px, frame_w - phys_win_w - margin))
                best_y = max(margin, min(rel_py, frame_h - phys_win_h - margin))
            else:
                try:
                    from PyQt6.QtGui import QCursor
                    c_pos = QCursor.pos()
                    rel_cx = int((c_pos.x() - monitor.left) * dpr)
                    rel_cy = int((c_pos.y() - monitor.top) * dpr)
                    best_x = max(margin, min(rel_cx - phys_win_w // 2, frame_w - phys_win_w - margin))
                    best_y = max(margin, min(rel_cy - phys_win_h // 2, frame_h - phys_win_h - margin))
                except Exception:
                    best_x = max(0, (frame_w - phys_win_w) // 2)
                    best_y = max(0, (frame_h - phys_win_h) // 2)
        else:
            # Default: 'clearest_area' (AI spatial clutter minimization)
            # 1. Grayscale & Canny Edge Detection
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            edges = cv2.Canny(gray, threshold1=50, threshold2=150)

            # 2. Integral image for O(1) box density calculation
            integral = cv2.integral(edges)

            step = max(8, int(24 * dpr))
            min_density = float("inf")
            max_scan_x = frame_w - phys_win_w - margin
            max_scan_y = frame_h - phys_win_h - margin

            if max_scan_x > margin and max_scan_y > margin:
                for y in range(margin, max_scan_y, step):
                    for x in range(margin, max_scan_x, step):
                        density = (
                            integral[y + phys_win_h, x + phys_win_w]
                            - integral[y, x + phys_win_w]
                            - integral[y + phys_win_h, x]
                            + integral[y, x]
                        )
                        if density < min_density:
                            min_density = density
                            best_x = x
                            best_y = y
            else:
                best_x = max(0, (frame_w - phys_win_w) // 2)
                best_y = max(0, (frame_h - phys_win_h) // 2)
                min_density = 0

            # Check for High Clutter Fallback Mode
            max_possible_sum = phys_win_w * phys_win_h * 255.0
            normalized_density = min_density / max_possible_sum if max_possible_sum > 0 else 0.0
            is_fallback = normalized_density > self.config.edge_density_fallback_threshold

            if is_fallback:
                best_x = max(margin, frame_w - phys_win_w - margin)
                best_y = max(margin, frame_h - phys_win_h - margin)

        # Convert physical best box back to Qt logical desktop coordinates
        logical_best_x = int(best_x / dpr)
        logical_best_y = int(best_y / dpr)
        logical_win_w = max(w_min, int(phys_win_w / dpr))
        logical_win_h = max(h_min, int(phys_win_h / dpr))

        abs_x = monitor.left + logical_best_x
        abs_y = monitor.top + logical_best_y
        target_rect = TargetRect(x=abs_x, y=abs_y, width=logical_win_w, height=logical_win_h)

        # 5. Luminance & Theme Computation on selected ROI
        roi = frame[best_y : best_y + phys_win_h, best_x : best_x + phys_win_w]
        theme = self._compute_theme(roi, is_fallback)

        # 6. Dynamic Typography
        typo_cfg: TypographyConfig = self.config.typography
        typography = DynamicTypography(
            base_font_size=typo_cfg.font_base_size,
            min_font_size=typo_cfg.font_min_size,
            downscale_threshold=typo_cfg.downscale_threshold,
            downscale_rate=typo_cfg.downscale_rate,
            line_height=1.45,
        )

        return SpatialResult(
            target_rect=target_rect,
            theme=theme,
            typography=typography,
            is_fallback_mode=is_fallback,
            monitor=monitor,
        )

    def _compute_theme(self, roi: np.ndarray, is_fallback: bool) -> ThemeConfig:
        """Calculates W3C Relative Luminance and returns polarized contrast scheme."""
        if roi.size == 0:
            # Default dark theme fallback
            return ThemeConfig(
                is_dark_background=True,
                text_color="#F8FAFC",
                backing_tint="rgba(15, 23, 42, 0.78)",
                text_shadow="0 1px 3px rgba(0, 0, 0, 0.9)",
                border_color="rgba(148, 163, 184, 0.25)",
                accent_color="#38BDF8",
            )

        # Convert BGR to float sRGB in [0, 1]
        bgr_norm = roi.astype(np.float32) / 255.0
        rgb_norm = bgr_norm[:, :, ::-1]

        # W3C Linearization formula
        linear = np.where(
            rgb_norm <= 0.04045,
            rgb_norm / 12.92,
            ((rgb_norm + 0.055) / 1.055) ** 2.4,
        )

        # Relative luminance L = 0.2126*R + 0.7152*G + 0.0722*B
        luminance_map = (
            0.2126 * linear[:, :, 0]
            + 0.7152 * linear[:, :, 1]
            + 0.0722 * linear[:, :, 2]
        )
        mean_luminance = float(np.mean(luminance_map))

        # If mean luminance > 0.5, the background is light
        if mean_luminance > 0.5:
            # Light wallpaper: Dark text with light backing shield
            return ThemeConfig(
                is_dark_background=False,
                text_color="#0F172A",  # Slate 900
                backing_tint="rgba(255, 255, 255, 0.82)" if is_fallback else "rgba(255, 255, 255, 0.65)",
                text_shadow="0 1px 2px rgba(255, 255, 255, 0.8)",
                border_color="rgba(15, 23, 42, 0.15)",
                accent_color="#0284C7",
            )
        else:
            # Dark wallpaper: Light text with dark backing shield
            return ThemeConfig(
                is_dark_background=True,
                text_color="#F8FAFC",  # Slate 50
                backing_tint="rgba(15, 23, 42, 0.85)" if is_fallback else "rgba(15, 23, 42, 0.70)",
                text_shadow="0 1px 3px rgba(0, 0, 0, 0.9)",
                border_color="rgba(148, 163, 184, 0.25)",
                accent_color="#38BDF8",
            )

    def find_prompt_position(
        self,
        frame: Optional[np.ndarray],
        monitor: MonitorInfo,
        modal_w: int,
        modal_h: int,
        placement_pref: str = "center",
        fallback_pref: str = "cursor",
        cursor_pos: Optional[Tuple[int, int]] = None,
    ) -> tuple[int, int, ThemeConfig]:
        """Finds optimal placement for input prompt modal respecting user preferences and clutter.

        - placement_pref: "center", "cursor", or "clearest_area"
        - fallback_pref: "cursor", "center", "spatial", or "none"
        """
        dpr = float(monitor.dpr) if hasattr(monitor, "dpr") and monitor.dpr else 1.0
        fallback_x = monitor.left + (monitor.width - modal_w) // 2
        fallback_y = monitor.top + (monitor.height - modal_h) // 2
        fallback_theme = ThemeConfig(
            is_dark_background=True,
            text_color="#F8FAFC",
            backing_tint="rgba(15, 23, 42, 0.88)",
            text_shadow="0 1px 3px rgba(0, 0, 0, 0.9)",
            border_color="rgba(148, 163, 184, 0.25)",
            accent_color="#38BDF8",
        )

        if frame is None or frame.size == 0:
            return fallback_x, fallback_y, fallback_theme

        try:
            frame_h, frame_w = frame.shape[:2]
            phys_w = min(int(modal_w * dpr), frame_w)
            phys_h = min(int(modal_h * dpr), frame_h)
            margin = int(24 * dpr)

            center_x = max(0, (frame_w - phys_w) // 2)
            center_y = max(0, (frame_h - phys_h) // 2)

            cursor_x, cursor_y = center_x, center_y
            has_cursor = False
            if cursor_pos is not None:
                cx, cy = cursor_pos
                if (monitor.left <= cx < monitor.right) and (monitor.top <= cy < monitor.bottom):
                    rel_cx = int((cx - monitor.left) * dpr)
                    rel_cy = int((cy - monitor.top) * dpr)
                    cursor_x = max(margin, min(rel_cx - phys_w // 2, frame_w - phys_w - margin))
                    cursor_y = max(margin, min(rel_cy - phys_h // 2, frame_h - phys_h - margin))
                    has_cursor = True

            # 1. Canny edges with fine thresholds to detect text, code, and UI elements
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            edges = cv2.Canny(gray, threshold1=30, threshold2=100)
            integral = cv2.integral(edges)

            def get_density(px: int, py: int, pw: int, ph: int) -> float:
                x1, y1 = max(0, px), max(0, py)
                x2, y2 = min(frame_w, px + pw), min(frame_h, py + ph)
                if x2 <= x1 or y2 <= y1:
                    return float("inf")
                sum_edges = (
                    integral[y2, x2]
                    - integral[y1, x2]
                    - integral[y2, x1]
                    + integral[y1, x1]
                )
                area = (x2 - x1) * (y2 - y1)
                return float(sum_edges) / float(area * 255.0) if area > 0 else float("inf")

            ACCEPTABLE_CLUTTER = 0.02
            center_density = get_density(center_x, center_y, phys_w, phys_h)
            cursor_density = get_density(cursor_x, cursor_y, phys_w, phys_h) if has_cursor else float("inf")

            chosen_x, chosen_y = center_x, center_y

            # Tier 1 & Tier 2 Evaluation with configurable fallback
            if placement_pref == "clearest_area":
                chosen_x, chosen_y = self._scan_clearest_area(
                    integral, frame_w, frame_h, phys_w, phys_h, margin, center_x, center_y, dpr
                )
            elif placement_pref == "cursor" and has_cursor:
                if cursor_density <= ACCEPTABLE_CLUTTER:
                    chosen_x, chosen_y = cursor_x, cursor_y
                elif fallback_pref == "none":
                    chosen_x, chosen_y = cursor_x, cursor_y
                elif fallback_pref == "center" and center_density <= ACCEPTABLE_CLUTTER:
                    chosen_x, chosen_y = center_x, center_y
                else:
                    # Spatial scan
                    chosen_x, chosen_y = self._scan_clearest_area(
                        integral, frame_w, frame_h, phys_w, phys_h, margin, cursor_x, cursor_y, dpr
                    )
            else:
                # Default 'center' preference
                if center_density <= ACCEPTABLE_CLUTTER:
                    chosen_x, chosen_y = center_x, center_y
                elif fallback_pref == "none":
                    chosen_x, chosen_y = center_x, center_y
                elif fallback_pref == "cursor" and has_cursor and cursor_density <= ACCEPTABLE_CLUTTER:
                    chosen_x, chosen_y = cursor_x, cursor_y
                else:
                    # Spatial scan
                    chosen_x, chosen_y = self._scan_clearest_area(
                        integral, frame_w, frame_h, phys_w, phys_h, margin, center_x, center_y, dpr
                    )

            logical_x = monitor.left + int(chosen_x / dpr)
            logical_y = monitor.top + int(chosen_y / dpr)

            roi = frame[chosen_y : chosen_y + phys_h, chosen_x : chosen_x + phys_w]
            theme = self._compute_theme(roi, is_fallback=False)

            return logical_x, logical_y, theme
        except Exception:
            return fallback_x, fallback_y, fallback_theme

    def _scan_clearest_area(
        self,
        integral: np.ndarray,
        frame_w: int,
        frame_h: int,
        phys_w: int,
        phys_h: int,
        margin: int,
        origin_x: int,
        origin_y: int,
        dpr: float,
    ) -> tuple[int, int]:
        """Scans grid to find the lowest clutter area with distance penalty from origin."""
        step = max(8, int(16 * dpr))
        max_scan_x = frame_w - phys_w - margin
        max_scan_y = frame_h - phys_h - margin

        best_score = float("inf")
        chosen_x = origin_x
        chosen_y = origin_y

        if max_scan_x > margin and max_scan_y > margin:
            max_diag = math.hypot(frame_w / 2, frame_h / 2) or 1.0

            for y in range(margin, max_scan_y, step):
                for x in range(margin, max_scan_x, step):
                    x1, y1 = max(0, x), max(0, y)
                    x2, y2 = min(frame_w, x + phys_w), min(frame_h, y + phys_h)
                    sum_edges = (
                        integral[y2, x2]
                        - integral[y1, x2]
                        - integral[y2, x1]
                        + integral[y1, x1]
                    )
                    area = (x2 - x1) * (y2 - y1)
                    density = float(sum_edges) / float(area * 255.0) if area > 0 else float("inf")

                    dist = math.hypot(x - origin_x, y - origin_y) / max_diag
                    score = density + 0.03 * dist
                    if score < best_score:
                        best_score = score
                        chosen_x = x
                        chosen_y = y

        return chosen_x, chosen_y
