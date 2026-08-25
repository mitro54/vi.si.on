"""
Central Orchestrator Agent: coordinates hotkeys, vision pipeline, state machine, and LLM streaming.
"""

from __future__ import annotations

import sys
import threading
import time
from enum import Enum
from typing import Any, Dict, List, Optional

import numpy as np
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QCursor
from PyQt6.QtWidgets import QApplication

from .config import AppConfig
from .llm.base import BaseLLMWorker
from .llm.provider_factory import create_llm_worker
from .storage.conversation_store import ConversationSession, ConversationStore
from .tools.knowledge_base import KnowledgeBase
from .tools.tool_registry import ToolRegistry
from .ui.conversation_picker import ConversationPicker
from .ui.input_modal import InputModal
from .ui.overlay_view import OverlayView
from .ui.setup_wizard import SetupWizard
from .vision.capture import MonitorInfo, ScreenCapture
from .vision.spatial_finder import SpatialFinder, SpatialResult


class AppState(Enum):
    IDLE = "IDLE"
    INPUT_ACTIVE = "INPUT_ACTIVE"
    ANALYZING = "ANALYZING"
    STREAMING = "STREAMING"
    DISPLAY = "DISPLAY"


class Orchestrator(QObject):
    """Central event coordinator and multi-agent lifecycle orchestrator."""

    # Internal thread-safe signals emitted from pynput listener
    _sig_quick_chat = pyqtSignal()
    _sig_conversation = pyqtSignal()
    _sig_new_conversation = pyqtSignal()
    _sig_dismiss = pyqtSignal()
    _sig_global_scroll = pyqtSignal(int)

    def __init__(
        self,
        config: AppConfig,
        store: ConversationStore,
        tool_registry: ToolRegistry,
        knowledge_base: Optional[KnowledgeBase] = None,
        parent: Optional[QObject] = None,
    ):
        super().__init__(parent)
        self.config = config
        self.store = store
        self.tool_registry = tool_registry
        self.knowledge_base = knowledge_base

        self.state = AppState.IDLE
        self._current_session: Optional[ConversationSession] = None
        self._last_quick_session: Optional[ConversationSession] = None
        self._promotion_deadline: float = 0.0

        # Subsystems
        self.capture = ScreenCapture()
        self.spatial_finder = SpatialFinder(config)

        # UI Components
        self.input_modal = InputModal()
        self.overlay_view = OverlayView(config)
        self.conversation_picker = ConversationPicker(store)

        # LLM Worker
        self.llm_worker: BaseLLMWorker = create_llm_worker(config.provider, parent=self)

        self._active_prompt_monitor: Optional[MonitorInfo] = None
        self._active_prompt_rect: Optional[Any] = None

        self._setup_signals()
        self._start_input_listeners()

    def _setup_signals(self) -> None:
        """Connects UI and LLM signals to orchestrator handlers."""
        self._sig_quick_chat.connect(self.trigger_quick_chat)
        self._sig_conversation.connect(self.trigger_conversation)
        self._sig_new_conversation.connect(self.trigger_new_conversation)
        self._sig_dismiss.connect(self.dismiss)
        self._sig_global_scroll.connect(self.overlay_view.scroll_by_delta)

        # Input modal events
        self.input_modal.query_submitted.connect(self.on_query_submitted)
        self.input_modal.dismissed.connect(self.on_input_dismissed)

        # Overlay events
        self.overlay_view.dismissed.connect(self.on_overlay_dismissed)

        # Conversation picker events
        self.conversation_picker.conversation_selected.connect(self.on_conversation_selected)
        self.conversation_picker.dismissed.connect(self.on_picker_dismissed)

        # LLM Worker events
        self.llm_worker.token_received.connect(self.overlay_view.append_token)
        self.llm_worker.stream_complete.connect(self.on_stream_complete)
        self.llm_worker.stream_error.connect(self.on_stream_error)
        self.llm_worker.tool_call_requested.connect(self.on_tool_call_requested)

    def _start_input_listeners(self) -> None:
        """Initializes global keyboard shortcuts and mouse scroll listener in daemon threads."""
        try:
            from pynput import keyboard, mouse

            hotkeys_map = {
                self.config.hotkeys.quick_chat: lambda: self._sig_quick_chat.emit(),
                self.config.hotkeys.conversation: lambda: self._sig_conversation.emit(),
                self.config.hotkeys.new_conversation: lambda: self._sig_new_conversation.emit(),
                self.config.hotkeys.dismiss: lambda: self._sig_dismiss.emit(),
            }

            self._hotkey_listener = keyboard.GlobalHotKeys(hotkeys_map)
            self._hotkey_thread = threading.Thread(target=self._hotkey_listener.run, daemon=True)
            self._hotkey_thread.start()

            def _on_mouse_scroll(x, y, dx, dy):
                if self.overlay_view.isVisible():
                    self._sig_global_scroll.emit(int(dy))

            self._mouse_listener = mouse.Listener(on_scroll=_on_mouse_scroll)
            self._mouse_thread = threading.Thread(target=self._mouse_listener.run, daemon=True)
            self._mouse_thread.start()
        except Exception as e:
            print(f"[Orchestrator] Global input hook initialization failed: {e}", file=sys.stderr)

    def _get_target_monitor(self) -> MonitorInfo:
        """Determines target monitor based on screen_target preference."""
        all_monitors = self.capture.get_all_monitors()
        focused_monitor = self.capture.get_focused_window_monitor()

        use_alternate = (
            self.config.overlay.screen_target == "alternate_screen"
            or self.config.overlay.prefer_alternate_monitor
        )

        if len(all_monitors) > 1 and use_alternate:
            alternates = [m for m in all_monitors if m.index != focused_monitor.index]
            return alternates[0] if alternates else focused_monitor
        return focused_monitor

    def _show_input_prompt(self, mode: str = "quick", turn_count: int = 1, title: Optional[str] = None) -> None:
        """Helper to show modal with user configured placement, screen target, and adaptive luminance contrast."""
        self.state = AppState.INPUT_ACTIVE
        self.input_modal.set_mode(mode, turn_count=turn_count, title=title)
        target_mon = self._get_target_monitor()
        self._active_prompt_monitor = target_mon

        # Compute anticipated modal coordinates to analyze background luminance
        modal_w, modal_h = self.input_modal.width(), self.input_modal.height()
        placement = self.config.overlay.prompt_placement

        if placement == "center" and target_mon:
            target_x = target_mon.left + (target_mon.width - modal_w) // 2
            target_y = target_mon.top + (target_mon.height - modal_h) // 2
        else:
            try:
                from PyQt6.QtGui import QCursor
                c_pos = QCursor.pos()
                target_x = c_pos.x() - modal_w // 2
                target_y = c_pos.y() - modal_h // 2
            except Exception:
                target_x = target_mon.left + (target_mon.width - modal_w) // 2
                target_y = target_mon.top + (target_mon.height - modal_h) // 2

        margin = 24
        clamped_x = max(target_mon.left + margin, min(target_x, target_mon.right - modal_w - margin))
        clamped_y = max(target_mon.top + margin, min(target_y, target_mon.bottom - modal_h - margin))

        # Capture background pixels directly behind the prompt box to determine contrast polarity
        theme = None
        try:
            frame = self.capture.capture_monitor(target_mon)
            dpr = float(target_mon.dpr) if hasattr(target_mon, "dpr") and target_mon.dpr else 1.0
            rel_x = max(0, int((clamped_x - target_mon.left) * dpr))
            rel_y = max(0, int((clamped_y - target_mon.top) * dpr))
            rel_w = int(modal_w * dpr)
            rel_h = int(modal_h * dpr)
            roi = frame[rel_y : rel_y + rel_h, rel_x : rel_x + rel_w]
            theme = self.spatial_finder._compute_theme(roi, is_fallback=False)
        except Exception:
            pass

        self.input_modal.show_modal(monitor=target_mon, placement=placement, theme=theme)
        self._active_prompt_rect = self.input_modal.geometry()

    @pyqtSlot()
    def trigger_quick_chat(self) -> None:
        """Handles Alt+1 trigger for quick query with immediate promotion upon opening."""
        if self.state == AppState.INPUT_ACTIVE:
            self.input_modal.hide()
            self.state = AppState.IDLE
            return

        now = time.monotonic()
        is_followup = bool(
            self._last_quick_session
            and (self.overlay_view.isVisible() or now < self._promotion_deadline)
        )

        if is_followup and self._last_quick_session:
            # Promote previous quick session immediately upon reopening the prompt box!
            # This ensures the user has unlimited time to type their follow-up without timer pressure.
            self._last_quick_session.promote_to_persistent()
            self._current_session = self._last_quick_session
            turn_count = len([m for m in self._current_session.messages if m.get("role") == "user"]) + 1
            self._show_input_prompt(mode="conversation", turn_count=turn_count, title="Follow-up")
        else:
            self._current_session = self.store.create_session(mode="quick")
            self._last_quick_session = self._current_session
            self._show_input_prompt(mode="quick", turn_count=1)

    @pyqtSlot()
    def trigger_conversation(self) -> None:
        """Handles Alt+2 trigger: opens active persistent conversation or picker."""
        if self.state == AppState.INPUT_ACTIVE:
            self.input_modal.hide()
            self.state = AppState.IDLE
            return

        latest = self.store.get_latest_persistent()
        if latest:
            self._current_session = latest
            turn_count = len([m for m in latest.messages if m.get("role") == "user"]) + 1
            self._show_input_prompt(mode="conversation", turn_count=turn_count, title=latest.title)
        else:
            self._current_session = self.store.create_session(mode="persistent")
            self._show_input_prompt(mode="conversation", turn_count=1, title="New Conversation")

    @pyqtSlot()
    def trigger_new_conversation(self) -> None:
        """Handles Alt+Shift+2: starts a brand new persistent conversation."""
        self._current_session = self.store.create_session(mode="persistent")
        self._show_input_prompt(mode="conversation", turn_count=1, title="New Conversation")

    @pyqtSlot()
    def show_conversation_picker(self) -> None:
        """Displays conversation picker popup."""
        self.conversation_picker.show_picker()

    @pyqtSlot(str)
    def on_conversation_selected(self, conv_id: str) -> None:
        """Loads selected conversation from store and opens prompt for follow-up."""
        session = self.store.get_session(conv_id)
        if session:
            self._current_session = session
            turn_count = len([m for m in session.messages if m.get("role") == "user"]) + 1
            self._show_input_prompt(mode="conversation", turn_count=turn_count, title=session.title)

    @pyqtSlot()
    def on_picker_dismissed(self) -> None:
        self.state = AppState.IDLE

    @pyqtSlot()
    def dismiss(self) -> None:
        """Dismisses any active input modal or floating overlay."""
        if self.llm_worker.isRunning():
            self.llm_worker.cancel()

        if self.input_modal.isVisible():
            self.input_modal.hide()

        if self.conversation_picker.isVisible():
            self.conversation_picker.hide()

        if self.overlay_view.isVisible():
            self.overlay_view.dismiss_smoothly()

        self.state = AppState.IDLE

    @pyqtSlot(str, str)
    def on_query_submitted(self, query: str, mode: str) -> None:
        """Processes submitted query with spatial analysis and LLM inference."""
        self.state = AppState.ANALYZING

        if not self._current_session:
            self._current_session = self.store.create_session(mode="quick")
            self._last_quick_session = self._current_session

        effective_mode = "conversation" if self._current_session.mode == "persistent" else "quick"
        is_promoted = (
            effective_mode == "conversation"
            and len([m for m in self._current_session.messages if m.get("role") == "user"]) > 0
        )

        # 1. Screen Capture: Lock strictly to the EXACT monitor where the prompt was displayed
        target_monitor = self._active_prompt_monitor or self._get_target_monitor()
        frame = self.capture.capture_monitor(target_monitor)

        # Check exclusive fullscreen game safety
        if self.capture.is_exclusive_fullscreen():
            print("[Orchestrator] Exclusive fullscreen detected. Suppressing overlay to protect application.")

        # 2. Run Spatial Analysis (on target monitor, aligning with prompt geometry)
        spatial = self.spatial_finder.analyze(
            frame=frame,
            monitor=target_monitor,
            prompt_rect=self._active_prompt_rect,
        )

        # 3. Prepare Overlay View
        turn_count = len([m for m in self._current_session.messages if m.get("role") == "user"]) + 1
        self.overlay_view.prepare_for_stream(spatial, mode=effective_mode, turn_count=turn_count)
        if is_promoted:
            self.overlay_view.mark_promoted()

        # 4. Prepare Context & Message History
        self._current_session.add_message("user", query)

        messages_payload = self._build_messages_payload(query)
        tools = self.tool_registry.get_tool_definitions()

        # 5. Start LLM Streaming
        self.state = AppState.STREAMING
        self.llm_worker.start_stream(messages_payload, tools=tools if tools else None, mode=effective_mode)

    def _select_target_monitor_and_frame(self) -> tuple[MonitorInfo, np.ndarray]:
        """Chooses target monitor (based on screen_target preference) and takes capture."""
        target_monitor = self._get_target_monitor()
        frame = self.capture.capture_monitor(target_monitor)
        return target_monitor, frame

    def _build_messages_payload(self, current_query: str) -> List[Dict[str, Any]]:
        """Constructs LLM message payload with system prompt, RAG context, and session history."""
        system_content = self.config.system_prompt

        # Inject RAG Knowledge Base context if available
        if self.knowledge_base and self.config.knowledge_base.enabled:
            rag_context = self.knowledge_base.format_context_for_prompt(current_query)
            if rag_context:
                system_content += f"\n\n{rag_context}"

        payload: List[Dict[str, Any]] = [{"role": "system", "content": system_content}]

        # Append session messages
        if self._current_session:
            for m in self._current_session.messages:
                payload.append({"role": m["role"], "content": m["content"]})

        return payload

    @pyqtSlot()
    def on_stream_complete(self) -> None:
        """Triggered when LLM token stream finishes."""
        self.state = AppState.DISPLAY
        self.overlay_view.finalize_display()

        # Save assistant message
        full_text = self.overlay_view.content_edit.toPlainText()
        if self._current_session and full_text:
            self._current_session.add_message("assistant", full_text)

        # Set promotion deadline (60 seconds after completion)
        self._promotion_deadline = time.monotonic() + self.config.conversation.promotion_timeout_seconds

    @pyqtSlot(str)
    def on_stream_error(self, error_msg: str) -> None:
        """Handles streaming failure."""
        self.state = AppState.DISPLAY
        self.overlay_view.append_token(f"\n\n[Error: {error_msg}]")
        self.overlay_view.finalize_display()

    @pyqtSlot(list)
    def on_tool_call_requested(self, tool_calls: list) -> None:
        """Executes requested tool calls and sends results back to LLM to resume generation."""
        self.overlay_view.append_token("\n*Executing tool calls...*\n")
        tool_results = []
        for tc in tool_calls:
            name = tc.get("name", "")
            args = tc.get("arguments", {})
            result_str = self.tool_registry.execute(name, args)
            tool_results.append({
                "role": "tool",
                "name": name,
                "content": result_str,
            })

        # Append tool interactions to conversation messages and resume stream
        if self._current_session:
            self._current_session.messages.extend(tool_results)
            messages_payload = self._build_messages_payload("")
            self.llm_worker.start_stream(messages_payload)

    @pyqtSlot()
    def on_input_dismissed(self) -> None:
        self.state = AppState.IDLE

    @pyqtSlot()
    def on_overlay_dismissed(self) -> None:
        self.state = AppState.IDLE
        # The promotion grace period timer starts from the moment the overlay disappears
        self._promotion_deadline = time.monotonic() + self.config.conversation.promotion_timeout_seconds
