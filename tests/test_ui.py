"""
Unit tests for UI components instantiation and positioning.
"""

from PyQt6.QtWidgets import QApplication

from desktop_ambient_ai.config import AppConfig, OverlayConfig
from desktop_ambient_ai.storage.conversation_store import ConversationStore
from desktop_ambient_ai.ui.conversation_picker import ConversationPicker
from desktop_ambient_ai.ui.input_modal import InputModal
from desktop_ambient_ai.ui.overlay_view import OverlayView
from desktop_ambient_ai.vision.capture import MonitorInfo


def test_ui_components_instantiation(tmp_path):
    app = QApplication.instance() or QApplication([])

    cfg = AppConfig(overlay=OverlayConfig(min_width=400, min_height=280))
    store = ConversationStore(db_path=tmp_path / "test.db")

    # Test InputModal
    modal = InputModal()
    mon = MonitorInfo(index=1, left=0, top=0, width=1920, height=1080)
    modal.set_mode("quick")
    modal.show_modal(monitor=mon, placement="center")
    assert modal.isVisible()
    modal.hide()

    modal.set_mode("conversation", turn_count=2, title="Test Chat")
    modal.show_modal(monitor=mon, placement="cursor")
    assert modal.isVisible()
    modal.hide()

    # Test OverlayView
    overlay = OverlayView(cfg)
    assert overlay is not None

    # Test ConversationPicker
    picker = ConversationPicker(store)
    assert picker is not None


def test_input_modal_adaptive_theme():
    """Tests InputModal contrast switching for light and dark backgrounds."""
    app = QApplication.instance() or QApplication([])
    modal = InputModal()

    from desktop_ambient_ai.vision.spatial_finder import ThemeConfig

    # Dark background theme
    dark_theme = ThemeConfig(is_dark_background=True, text_color="#F8FAFC", backing_tint="rgba(15, 23, 42, 0.9)")
    modal.apply_theme(dark_theme)
    assert modal.theme.is_dark_background is True

    # Light background theme
    light_theme = ThemeConfig(is_dark_background=False, text_color="#0F172A", backing_tint="rgba(255, 255, 255, 0.94)")
    modal.apply_theme(light_theme)
    assert modal.theme.is_dark_background is False


def test_overlay_view_streaming_and_typography():
    """Tests OverlayView markdown rendering and minimum font floor constraint."""
    app = QApplication.instance() or QApplication([])
    cfg = AppConfig()
    overlay = OverlayView(cfg)

    from desktop_ambient_ai.vision.spatial_finder import DynamicTypography, SpatialResult, TargetRect, ThemeConfig
    spatial = SpatialResult(
        target_rect=TargetRect(x=100, y=100, width=500, height=350),
        theme=ThemeConfig(is_dark_background=True, text_color="#F8FAFC", backing_tint="rgba(15, 23, 42, 0.8)"),
        typography=DynamicTypography(base_font_size=15, min_font_size=13, downscale_threshold=100, downscale_rate=50),
        is_fallback_mode=False,
        monitor=MonitorInfo(index=1, left=0, top=0, width=1920, height=1080),
    )

    overlay.prepare_for_stream(spatial, mode="quick")
    assert overlay.isVisible()

    # Append markdown tokens
    overlay.append_token("# Header\n")
    overlay.append_token("This is **bold** text and `inline_code()`.\n\n")
    overlay.append_token("A " * 300)  # Large token count to trigger font downsizing

    # Verify font size never drops below min_font_size floor (13)
    assert overlay._current_font_size >= 13
    assert overlay.content_edit.toPlainText().startswith("Header")

    overlay.scroll_by_delta(1)
    overlay.scroll_by_delta(-1)
    overlay.hide()
