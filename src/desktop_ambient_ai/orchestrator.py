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
from PyQt6.QtCore import QObject, QPoint, QRect, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QCursor
from PyQt6.QtWidgets import QApplication

from .config import AppConfig
from .llm.base import BaseLLMWorker
from .llm.provider_factory import create_llm_worker
from .storage.conversation_store import ConversationSession, ConversationStore
from .tools.knowledge_base import KnowledgeBase
from .tools.tool_registry import ToolRegistry
from .tools.tool_worker import ToolExecutionWorker

from .ui.conversation_picker import ConversationPicker
from .ui.input_modal import InputModal
from .ui.overlay_view import OverlayView
from .ui.setup_wizard import SetupWizard
from .ui.snip_overlay import ScreenSnipper
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
    _sig_ocr_selection = pyqtSignal()
    _sig_dismiss = pyqtSignal()
    _sig_global_scroll = pyqtSignal(int)
    _sig_cycle_conv = pyqtSignal(int)

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
        self._snipping_from_modal: bool = False

        # Subsystems
        self.capture = ScreenCapture()
        self.spatial_finder = SpatialFinder(config)

        # UI Components
        self.input_modal = InputModal()
        self.overlay_view = OverlayView(config)
        self.conversation_picker = ConversationPicker(store)
        self.screen_snipper = ScreenSnipper(capture_engine=self.capture)

        # LLM Worker & Tool Execution Worker
        self.llm_worker: BaseLLMWorker = create_llm_worker(config.provider, parent=self)
        self.tool_worker = ToolExecutionWorker(tool_registry=self.tool_registry, parent=self)

        self._active_prompt_monitor: Optional[MonitorInfo] = None
        self._active_prompt_rect: Optional[Any] = None
        self._last_session_monitor: Optional[MonitorInfo] = None

        self._setup_signals()
        self._start_input_listeners()

    def _setup_signals(self) -> None:
        """Connects UI and LLM signals to orchestrator handlers."""
        self._sig_quick_chat.connect(self.trigger_quick_chat)
        self._sig_conversation.connect(self.trigger_conversation)
        self._sig_new_conversation.connect(self.trigger_new_conversation)
        self._sig_ocr_selection.connect(self.trigger_ocr_selection)
        self._sig_dismiss.connect(self.dismiss)
        self._sig_global_scroll.connect(self.overlay_view.scroll_by_delta)
        self._sig_cycle_conv.connect(self.cycle_conversation)

        # Screen Snipper events
        self.screen_snipper.region_selected.connect(self.on_region_snipped)
        self.screen_snipper.cancelled.connect(self.on_snip_cancelled)

        # Input modal events
        self.input_modal.query_submitted.connect(self.on_query_submitted)
        self.input_modal.dismissed.connect(self.on_input_dismissed)
        self.input_modal.cycle_conv_requested.connect(self.cycle_conversation)

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

        # Tool Worker events (async background execution)
        self.tool_worker.tool_results_ready.connect(self.on_tool_results_ready)
        self.tool_worker.tool_error.connect(self.on_stream_error)


    def _start_input_listeners(self) -> None:
        """Initializes global keyboard shortcuts and mouse scroll listener in daemon threads."""
        try:
            from pynput import keyboard, mouse

            hotkeys_map = {
                self.config.hotkeys.quick_chat: lambda: self._sig_quick_chat.emit(),
                self.config.hotkeys.conversation: lambda: self._sig_conversation.emit(),
                self.config.hotkeys.new_conversation: lambda: self._sig_new_conversation.emit(),
                self.config.hotkeys.ocr_selection: lambda: self._sig_ocr_selection.emit(),
                self.config.hotkeys.dismiss: lambda: self._sig_dismiss.emit(),
                "<alt>+<up>": lambda: self._sig_cycle_conv.emit(-1),
                "<alt>+<down>": lambda: self._sig_cycle_conv.emit(1),
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

    def _show_input_prompt(
        self,
        mode: str = "quick",
        turn_count: int = 1,
        title: Optional[str] = None,
        clear_text: bool = True,
        target_monitor: Optional[MonitorInfo] = None,
        exact_pos: Optional[QPoint] = None,
    ) -> None:
        """Helper to show modal with user configured placement, screen target, and adaptive luminance contrast."""
        self.state = AppState.INPUT_ACTIVE
        self.input_modal.set_mode(mode, turn_count=turn_count, title=title)
        target_mon = target_monitor or self._get_target_monitor()
        self._active_prompt_monitor = target_mon

        # Determine prompt coordinates and adaptive contrast theme
        modal_w, modal_h = self.input_modal.width(), self.input_modal.height()
        placement = self.config.overlay.prompt_placement

        use_clutter_avoidance = getattr(self.config.overlay, "prompt_clutter_avoidance", True)

        theme = None
        chosen_pos: Optional[QPoint] = None

        if exact_pos:
            chosen_pos = exact_pos
            try:
                frame = self.capture.capture_monitor(target_mon)
                dpr = float(target_mon.dpr) if hasattr(target_mon, "dpr") and target_mon.dpr else 1.0
                rel_x = max(0, int((exact_pos.x() - target_mon.left) * dpr))
                rel_y = max(0, int((exact_pos.y() - target_mon.top) * dpr))
                rel_w = int(modal_w * dpr)
                rel_h = int(modal_h * dpr)
                roi = frame[rel_y : rel_y + rel_h, rel_x : rel_x + rel_w]
                theme = self.spatial_finder._compute_theme(roi, is_fallback=False)
            except Exception:
                pass
        elif not use_clutter_avoidance:
            # Strict user placement without spatial clutter shifting
            if placement == "center" and target_mon:
                target_x = target_mon.left + (target_mon.width - modal_w) // 2
                target_y = target_mon.top + (target_mon.height - modal_h) // 2
            else:
                try:
                    from PyQt6.QtGui import QCursor
                    c = QCursor.pos()
                    target_x = c.x() - modal_w // 2
                    target_y = c.y() - modal_h // 2
                except Exception:
                    target_x = target_mon.left + (target_mon.width - modal_w) // 2
                    target_y = target_mon.top + (target_mon.height - modal_h) // 2
            margin = 24
            clamped_x = max(target_mon.left + margin, min(target_x, target_mon.right - modal_w - margin))
            clamped_y = max(target_mon.top + margin, min(target_y, target_mon.bottom - modal_h - margin))
            chosen_pos = QPoint(clamped_x, clamped_y)
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
        else:
            try:
                frame = self.capture.capture_monitor(target_mon)
                cursor_pt = None
                try:
                    from PyQt6.QtGui import QCursor
                    c = QCursor.pos()
                    cursor_pt = (c.x(), c.y())
                except Exception:
                    pass

                fallback_strat = getattr(self.config.overlay, "prompt_fallback", "cursor")
                opt_x, opt_y, opt_theme = self.spatial_finder.find_prompt_position(
                    frame=frame,
                    monitor=target_mon,
                    modal_w=modal_w,
                    modal_h=modal_h,
                    placement_pref=placement,
                    fallback_pref=fallback_strat,
                    cursor_pos=cursor_pt,
                )
                chosen_pos = QPoint(opt_x, opt_y)
                theme = opt_theme
            except Exception:
                fallback_x = target_mon.left + (target_mon.width - modal_w) // 2
                fallback_y = target_mon.top + (target_mon.height - modal_h) // 2
                chosen_pos = QPoint(fallback_x, fallback_y)

        self.input_modal.show_modal(
            monitor=target_mon,
            placement=placement,
            theme=theme,
            clear_text=clear_text,
            exact_pos=chosen_pos,
        )
        self._active_prompt_rect = self.input_modal.geometry()

    @pyqtSlot()
    def trigger_quick_chat(self) -> None:
        """Handles Alt+1 trigger for quick query. Retains fast model & warm KV cache across quick follow-ups."""
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
            # Keep on fast quick model with existing KV cache / context window for instant follow-up response!
            self._current_session = self._last_quick_session
            turn_count = len([m for m in self._current_session.messages if m.get("role") == "user"]) + 1
            followup_mon = self._last_session_monitor or self._active_prompt_monitor
            self._show_input_prompt(
                mode="quick",
                turn_count=turn_count,
                title="Quick Follow-up",
                target_monitor=followup_mon,
            )
        else:
            self._current_session = self.store.create_session(mode="quick")
            self._last_quick_session = self._current_session
            self._show_input_prompt(mode="quick", turn_count=1)

    @pyqtSlot()
    def trigger_conversation(self) -> None:
        """Handles Alt+2 trigger: opens active persistent conversation or promotes quick chat with deep reasoning model."""
        if self.state == AppState.INPUT_ACTIVE:
            self.input_modal.hide()
            self.state = AppState.IDLE
            return

        # If user was in a quick session and explicitly presses Alt+2: promote to persistent & load deep model!
        if self._last_quick_session and self._current_session == self._last_quick_session and self._current_session.mode == "quick":
            self._last_quick_session.promote_to_persistent()
            turn_count = len([m for m in self._current_session.messages if m.get("role") == "user"]) + 1
            followup_mon = self._last_session_monitor or self._active_prompt_monitor
            self._show_input_prompt(
                mode="conversation",
                turn_count=turn_count,
                title=self._last_quick_session.title,
                target_monitor=followup_mon,
            )
            return

        latest = self.store.get_latest_persistent()
        if latest:
            self._current_session = latest
            turn_count = len([m for m in latest.messages if m.get("role") == "user"]) + 1
            followup_mon = self._last_session_monitor or self._active_prompt_monitor
            self._show_input_prompt(mode="conversation", turn_count=turn_count, title=latest.title, target_monitor=followup_mon)
        else:
            self._current_session = self.store.create_session(mode="persistent")
            self._show_input_prompt(mode="conversation", turn_count=1, title="New Conversation")

    @pyqtSlot()
    def trigger_new_conversation(self) -> None:
        """Handles Alt+Shift+2: starts a brand new persistent conversation."""
        self._current_session = self.store.create_session(mode="persistent")
        self._last_session_monitor = None
        self._show_input_prompt(mode="conversation", turn_count=1, title="New Conversation")

    @pyqtSlot()
    def trigger_ocr_selection(self) -> None:
        """Handles Alt+3 trigger for interactive screen region snipping."""
        if self.screen_snipper.isVisible():
            self.screen_snipper._cancel()
            return

        if self.input_modal.isVisible():
            self._snipping_from_modal = True
            self._saved_prompt_pos = self.input_modal.pos()
            self._saved_prompt_monitor = self._active_prompt_monitor
            # If a trailing '3' was accidentally captured in the text input, clean it
            txt = self.input_modal.input_edit.text()
            if txt.endswith("3"):
                self.input_modal.input_edit.setText(txt[:-1])
            self.input_modal.hide()
        else:
            self._snipping_from_modal = False
            self._saved_prompt_pos = None
            self._saved_prompt_monitor = None

        self.screen_snipper.start_selection()

    @pyqtSlot(bytes, str, object, QRect)
    def on_region_snipped(self, png_bytes: bytes, b64_png: str, crop_bgr: Any, rect: QRect) -> None:
        """Attaches snipped image to active or newly opened prompt box."""
        is_capable = self.llm_worker.is_vision_capable()
        if not is_capable:
            vision_models = self.llm_worker.find_vision_models()
            is_capable = bool(vision_models)

        self.input_modal.attach_image_snip(b64_png, rect.width(), rect.height(), is_vision_capable=is_capable)

        if self._snipping_from_modal:
            self._show_input_prompt(
                mode=self.input_modal.mode,
                turn_count=self.input_modal.turn_count,
                clear_text=False,
                target_monitor=self._saved_prompt_monitor,
                exact_pos=self._saved_prompt_pos,
            )
        else:
            now = time.monotonic()
            is_followup = bool(
                self._last_quick_session
                and (self.overlay_view.isVisible() or now < self._promotion_deadline)
            )
            if is_followup and self._last_quick_session:
                self._last_quick_session.promote_to_persistent()
                self._current_session = self._last_quick_session
                turn_count = len([m for m in self._current_session.messages if m.get("role") == "user"]) + 1
                self._show_input_prompt(mode="conversation", turn_count=turn_count, title="Follow-up", clear_text=False)
            else:
                self._current_session = self.store.create_session(mode="quick")
                self._last_quick_session = self._current_session
                self._show_input_prompt(mode="quick", turn_count=1, clear_text=False)

    @pyqtSlot()
    def on_snip_cancelled(self) -> None:
        """Restores modal if snipper is cancelled."""
        if self._snipping_from_modal:
            self._show_input_prompt(
                mode=self.input_modal.mode,
                turn_count=self.input_modal.turn_count,
                clear_text=False,
                target_monitor=self._saved_prompt_monitor,
                exact_pos=self._saved_prompt_pos,
            )
        else:
            self.state = AppState.IDLE

    @pyqtSlot(int)
    def cycle_conversation(self, delta: int) -> None:
        """Cycles through past persistent conversation sessions in real time."""
        if self.conversation_picker.isVisible():
            if delta > 0:
                self.conversation_picker.select_next()
            else:
                self.conversation_picker.select_previous()
            return

        summaries = self.store.list_persistent(limit=30)
        if not summaries:
            return

        current_idx = 0
        if self._current_session and self._current_session.mode == "persistent":
            for idx, s in enumerate(summaries):
                if s.id == self._current_session.id:
                    current_idx = idx
                    break
            next_idx = (current_idx + delta) % len(summaries)
        else:
            next_idx = 0 if delta >= 0 else len(summaries) - 1

        target_summary = summaries[next_idx]
        session = self.store.get_session(target_summary.id)
        if session:
            self._current_session = session
            turn_count = len([m for m in session.messages if m.get("role") == "user"]) + 1
            if self.input_modal.isVisible():
                self.input_modal.set_mode("conversation", turn_count=turn_count, title=session.title)
            else:
                followup_mon = self._last_session_monitor or self._active_prompt_monitor
                self._show_input_prompt(
                    mode="conversation",
                    turn_count=turn_count,
                    title=session.title,
                    clear_text=False,
                    target_monitor=followup_mon,
                )

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
            followup_mon = self._last_session_monitor or self._active_prompt_monitor
            self._show_input_prompt(mode="conversation", turn_count=turn_count, title=session.title, target_monitor=followup_mon)

    @pyqtSlot()
    def on_picker_dismissed(self) -> None:
        self.state = AppState.IDLE

    @pyqtSlot()
    def dismiss(self) -> None:
        """Dismisses any active input modal or floating overlay."""
        if self.llm_worker.isRunning():
            self.llm_worker.cancel()

        if self.screen_snipper.isVisible():
            self.screen_snipper.hide()

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

        attached_imgs = self.input_modal.get_attached_images()
        self.input_modal.detach_image()

        # 1. Screen Capture: Lock strictly to the EXACT monitor where the prompt was displayed
        target_monitor = self._active_prompt_monitor or self._get_target_monitor()
        self._last_session_monitor = target_monitor
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
        self.llm_worker.start_stream(
            messages_payload,
            tools=tools if tools else None,
            mode=effective_mode,
            images=attached_imgs if attached_imgs else None,
        )

    def _select_target_monitor_and_frame(self) -> tuple[MonitorInfo, np.ndarray]:
        """Chooses target monitor (based on screen_target preference) and takes capture."""
        target_monitor = self._get_target_monitor()
        frame = self.capture.capture_monitor(target_monitor)
        return target_monitor, frame

    def _build_messages_payload(self, current_query: str) -> list[dict[str, Any]]:
        """Constructs LLM message payload with system prompt, RAG context, and session history."""
        system_content = self.config.system_prompt

        # Inject RAG Knowledge Base context if available
        if self.knowledge_base and self.config.knowledge_base.enabled and current_query:
            rag_context = self.knowledge_base.format_context_for_prompt(current_query)
            if rag_context:
                system_content += f"\n\n{rag_context}"

        payload: list[dict[str, Any]] = [{"role": "system", "content": system_content}]

        # Append session messages preserving tool_calls, name, and images
        if self._current_session:
            for m in self._current_session.messages:
                entry: dict[str, Any] = {
                    "role": m["role"],
                    "content": m.get("content", ""),
                }
                if m.get("tool_calls"):
                    entry["tool_calls"] = m["tool_calls"]
                if m.get("name"):
                    entry["name"] = m["name"]
                if m.get("images"):
                    entry["images"] = m["images"]
                payload.append(entry)

        return payload


    @pyqtSlot()
    def on_stream_complete(self) -> None:
        """Triggered when LLM token stream finishes."""
        self.state = AppState.DISPLAY
        self.overlay_view.finalize_display()

        # Save assistant message preserving raw markdown/LaTeX syntax
        full_text = self.overlay_view.get_raw_markdown() or self.overlay_view.content_edit.toPlainText()
        if self._current_session and full_text:
            self._current_session.add_message("assistant", full_text)


        # Set promotion deadline (60 seconds after completion)
        self._promotion_deadline = time.monotonic() + self.config.conversation.promotion_timeout_seconds

    @pyqtSlot(str)
    def on_stream_error(self, error_msg: str) -> None:
        """Handles streaming failure."""
        self.state = AppState.DISPLAY
        self.overlay_view.set_status("")
        self.overlay_view.append_token(f"\n\n[Error: {error_msg}]")
        self.overlay_view.finalize_display()

    @pyqtSlot(list)
    def on_tool_call_requested(self, tool_calls: list) -> None:
        """Dispatches requested tool calls to background worker thread to prevent UI freezing."""
        if not tool_calls:
            return

        # 1. Update live UI status label with specific tool & query details
        tool_status_parts = []
        for tc in tool_calls:
            name = tc.get("name", "")
            args = tc.get("arguments", {})
            if name == "web_search":
                q = args.get("query", "")
                tool_status_parts.append(f'🌐 Searching web for "{q}"')
            elif name == "search_knowledge_base":
                q = args.get("query", "")
                tool_status_parts.append(f'📚 Searching docs: "{q}"')
            else:
                tool_status_parts.append(f"⚡ Executing {name}")

        self.overlay_view.set_status(" | ".join(tool_status_parts))

        # 2. Execute tools in background worker without blocking Qt UI thread
        self.tool_worker.execute_async(tool_calls)

    @pyqtSlot(dict, list)
    def on_tool_results_ready(self, assistant_tool_msg: dict, tool_results: list) -> None:
        """Triggered when background tool execution completes. Resumes LLM generation."""
        if self._current_session:
            self._current_session.messages.append(assistant_tool_msg)
            self._current_session.messages.extend(tool_results)

            messages_payload = self._build_messages_payload("")
            effective_mode = getattr(self._current_session, "mode", "quick")
            tools = self.tool_registry.get_tool_definitions()

            self.overlay_view.reset_content_for_tool_response()
            self.overlay_view.set_status("✨ Synthesizing live search results...")
            self.llm_worker.start_stream(
                messages_payload,
                tools=tools if tools else None,
                mode=effective_mode,
            )




    @pyqtSlot()
    def on_input_dismissed(self) -> None:
        self.state = AppState.IDLE

    @pyqtSlot()
    def on_overlay_dismissed(self) -> None:
        self.state = AppState.IDLE
        # The promotion grace period timer starts from the moment the overlay disappears
        self._promotion_deadline = time.monotonic() + self.config.conversation.promotion_timeout_seconds
