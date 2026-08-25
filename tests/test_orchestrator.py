"""
Unit tests for Orchestrator state machine, hotkey signals, and slot dispatching.
"""

from unittest.mock import MagicMock

from PyQt6.QtCore import QRect
from PyQt6.QtWidgets import QApplication

from desktop_ambient_ai.config import AppConfig
from desktop_ambient_ai.orchestrator import AppState, Orchestrator
from desktop_ambient_ai.storage.conversation_store import ConversationStore
from desktop_ambient_ai.tools.tool_registry import ToolRegistry


def test_orchestrator_initialization_and_slots(tmp_path):
    app = QApplication.instance() or QApplication([])

    cfg = AppConfig()
    store = ConversationStore(db_path=tmp_path / "test.db")
    tool_registry = ToolRegistry(config=cfg)

    orchestrator = Orchestrator(
        config=cfg,
        store=store,
        tool_registry=tool_registry,
    )

    assert orchestrator.state == AppState.IDLE

    # Test slots execution
    orchestrator.trigger_quick_chat()
    assert orchestrator.input_modal.isVisible()
    orchestrator.dismiss()

    orchestrator.trigger_conversation()
    assert orchestrator.input_modal.isVisible()
    orchestrator.dismiss()

    orchestrator.trigger_new_conversation()
    assert orchestrator.input_modal.isVisible()
    orchestrator.dismiss()

    # Test snipper slot invocation
    dummy_b64 = "dummy_base64"
    dummy_rect = QRect(100, 100, 400, 300)
    orchestrator.on_region_snipped(b"png", dummy_b64, None, dummy_rect)
    assert orchestrator.input_modal.get_attached_image() == dummy_b64
    orchestrator.input_modal.hide()

    orchestrator.dismiss()
    assert orchestrator.state == AppState.IDLE


def test_orchestrator_conversation_cycling(tmp_path):
    app = QApplication.instance() or QApplication([])

    cfg = AppConfig()
    store = ConversationStore(db_path=tmp_path / "test_cycle.db")
    tool_registry = ToolRegistry(config=cfg)

    # Create 3 distinct conversation threads
    s1 = store.create_session("persistent", title="Chat 1")
    s1.add_message("user", "Hello 1")
    s2 = store.create_session("persistent", title="Chat 2")
    s2.add_message("user", "Hello 2")
    s3 = store.create_session("persistent", title="Chat 3")
    s3.add_message("user", "Hello 3")

    orchestrator = Orchestrator(
        config=cfg,
        store=store,
        tool_registry=tool_registry,
    )

    orchestrator.trigger_conversation()
    assert orchestrator.input_modal.isVisible()

    # Cycle next
    orchestrator.cycle_conversation(1)
    assert orchestrator.input_modal.isVisible()

    # Cycle previous
    orchestrator.cycle_conversation(-1)
    assert orchestrator.input_modal.isVisible()

    orchestrator.dismiss()
    assert orchestrator.state == AppState.IDLE
