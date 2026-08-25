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
