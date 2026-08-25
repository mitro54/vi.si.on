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


def test_spatial_analysis_mixed_dpi_4k():
    """Verifies that 4K displays with 1.5x/2.0x scaling output correct logical desktop coordinates."""
    cfg = AppConfig(overlay=OverlayConfig(min_width=400, min_height=280))
    finder = SpatialFinder(cfg)

    # Physical 4K frame (3840x2160), Logical Qt screen (2560x1440), DPR=1.5
    dark_4k_frame = np.zeros((2160, 3840, 3), dtype=np.uint8)
    monitor_4k = MonitorInfo(
        index=1,
        left=0,
        top=0,
        width=2560,
        height=1440,
        dpr=1.5,
        physical_left=0,
        physical_top=0,
        physical_width=3840,
        physical_height=2160,
    )

    result = finder.analyze(dark_4k_frame, monitor_4k)

    # Window bounds must match logical desktop constraints
    assert result.target_rect.width >= 400
    assert result.target_rect.height >= 280
    assert result.target_rect.x + result.target_rect.width <= 2560
    assert result.target_rect.y + result.target_rect.height <= 1440


def test_find_prompt_position_prefers_center_and_avoids_clutter():
    """Verifies that prompt box prefers screen center on clean screens, but avoids heavily cluttered centers."""
    cfg = AppConfig()
    finder = SpatialFinder(cfg)
    monitor = MonitorInfo(index=1, left=0, top=0, width=1920, height=1080)
    modal_w, modal_h = 540, 110

    # 1. Clean screen: Must place directly at screen center
    clean_frame = np.full((1080, 1920, 3), 40, dtype=np.uint8)
    opt_x, opt_y, theme = finder.find_prompt_position(clean_frame, monitor, modal_w, modal_h)

    expected_center_x = (1920 - modal_w) // 2
    expected_center_y = (1080 - modal_h) // 2
    assert opt_x == expected_center_x
    assert opt_y == expected_center_y
    assert theme.is_dark_background is True

    # 2. Cluttered center: Must shift away from cluttered center
    cluttered_frame = np.full((1080, 1920, 3), 40, dtype=np.uint8)
    # Heavy noise in the center region
    cluttered_frame[400:680, 700:1220] = np.random.randint(0, 255, (280, 520, 3), dtype=np.uint8)

    opt_x2, opt_y2, theme2 = finder.find_prompt_position(cluttered_frame, monitor, modal_w, modal_h)
    # Position shifted away from the noise in the center
    assert (opt_x2, opt_y2) != (expected_center_x, expected_center_y)
    assert 0 <= opt_x2 <= 1920 - modal_w
    assert 0 <= opt_y2 <= 1080 - modal_h


