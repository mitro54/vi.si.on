"""
Unit tests for Computer Vision spatial clutter minimization and dynamic luminance styling.
"""

import numpy as np

from desktop_ambient_ai.config import AppConfig, OverlayConfig
from desktop_ambient_ai.vision.capture import MonitorInfo
from desktop_ambient_ai.vision.spatial_finder import SpatialFinder


def test_spatial_analysis_dark_screen():
    cfg = AppConfig(overlay=OverlayConfig(min_width=400, min_height=280))
    finder = SpatialFinder(cfg)

    # 1920x1080 solid dark image (e.g. RGB 20, 20, 30)
    dark_frame = np.full((1080, 1920, 3), (30, 20, 20), dtype=np.uint8)
    monitor = MonitorInfo(index=1, left=0, top=0, width=1920, height=1080)

    result = finder.analyze(dark_frame, monitor)

    assert result.target_rect.width >= 400
    assert result.target_rect.height >= 280
    assert result.theme.is_dark_background is True
    assert result.theme.text_color == "#F8FAFC"
    assert "rgba(15, 23, 42" in result.theme.backing_tint


def test_spatial_analysis_light_screen():
    cfg = AppConfig(overlay=OverlayConfig(min_width=400, min_height=280))
    finder = SpatialFinder(cfg)

    # 1920x1080 solid light image (e.g. RGB 240, 245, 250)
    light_frame = np.full((1080, 1920, 3), (250, 245, 240), dtype=np.uint8)
    monitor = MonitorInfo(index=1, left=0, top=0, width=1920, height=1080)

    result = finder.analyze(light_frame, monitor)

    assert result.target_rect.width >= 400
    assert result.target_rect.height >= 280
    assert result.theme.is_dark_background is False
    assert result.theme.text_color == "#0F172A"
    assert "rgba(255, 255, 255" in result.theme.backing_tint


def test_spatial_analysis_avoids_clutter():
    cfg = AppConfig(overlay=OverlayConfig(min_width=300, min_height=200, max_width=300, max_height=200))
    finder = SpatialFinder(cfg)

    # Left half cluttered with high frequency random noise, right half clean/smooth
    frame = np.zeros((600, 800, 3), dtype=np.uint8)
    frame[:, :400] = np.random.randint(0, 255, (600, 400, 3), dtype=np.uint8)
    monitor = MonitorInfo(index=1, left=0, top=0, width=800, height=600)

    result = finder.analyze(frame, monitor)

    # The chosen window x position must be on the clean right half (>= 400)
    assert result.target_rect.x >= 400

