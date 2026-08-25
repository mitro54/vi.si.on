"""
Clean, floating query input modal with mode indication and smooth fade transitions.
"""

from __future__ import annotations

from typing import Literal, Optional

from PyQt6.QtCore import QEasingCurve, QPropertyAnimation, QRect, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QCursor, QGuiApplication, QKeyEvent
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from .styles import generate_input_modal_qss


def _force_foreground_window(hwnd: int) -> None:
    """Forces Windows OS to grant active keyboard focus even when spawned from a background hook."""
    import sys
    if sys.platform == "win32":
        try:
            import ctypes
            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32

            # Release any lingering ALT key state from the hotkey press
            VK_MENU = 0x12
            KEYEVENTF_KEYUP = 0x0002
            user32.keybd_event(VK_MENU, 0, KEYEVENTF_KEYUP, 0)

            fg_hwnd = user32.GetForegroundWindow()
            fg_thread_id = user32.GetWindowThreadProcessId(fg_hwnd, None)
            app_thread_id = kernel32.GetCurrentThreadId()

            if fg_thread_id != 0 and fg_thread_id != app_thread_id:
                user32.AttachThreadInput(app_thread_id, fg_thread_id, True)

            user32.AllowSetForegroundWindow(-1)  # ASFW_ANY
            user32.BringWindowToTop(hwnd)
            user32.SetForegroundWindow(hwnd)
            user32.SetActiveWindow(hwnd)
            user32.SetFocus(hwnd)

            if fg_thread_id != 0 and fg_thread_id != app_thread_id:
                user32.AttachThreadInput(app_thread_id, fg_thread_id, False)
        except Exception:
            pass


class InputModal(QWidget):
    """Floating modal prompt to receive user queries."""

    query_submitted = pyqtSignal(str, str)  # (query_text, mode)
    dismissed = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.mode: Literal["quick", "conversation"] = "quick"
        self.turn_count: int = 1
        self._anim: Optional[QPropertyAnimation] = None

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Window
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setObjectName("InputModalRoot")
        self.setStyleSheet(generate_input_modal_qss())

        self.setFixedSize(540, 100)
        self._init_ui()

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(14, 12, 14, 12)
        main_layout.setSpacing(8)

        # Top Bar: Mode Badge + Shortcuts Hint
        top_bar = QHBoxLayout()
        top_bar.setContentsMargins(0, 0, 0, 0)

        self.mode_badge = QLabel("⚡ Quick Query", self)
        self.mode_badge.setObjectName("ModeBadge")
        top_bar.addWidget(self.mode_badge)

        top_bar.addStretch()

        self.hint_label = QLabel("Enter to submit • Esc to close", self)
        self.hint_label.setObjectName("HintLabel")
        top_bar.addWidget(self.hint_label)

        main_layout.addLayout(top_bar)

        # Bottom: Text Input
        self.input_edit = QLineEdit(self)
        self.input_edit.setObjectName("PromptInput")
        self.input_edit.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.input_edit.setPlaceholderText("Ask anything (Ollama / Web / Knowledge Base)...")
        self.input_edit.returnPressed.connect(self._on_submit)
        main_layout.addWidget(self.input_edit)

    def set_mode(self, mode: Literal["quick", "conversation"], turn_count: int = 1, title: Optional[str] = None) -> None:
        """Updates modal visual mode and context labels."""
        self.mode = mode
        self.turn_count = turn_count
        if mode == "quick":
            self.mode_badge.setText("⚡ Quick One-Off")
        else:
            conv_label = f"🗨 Conversation (#{turn_count})"
            if title and title != "New Conversation":
                conv_label = f"🗨 {title[:25]} (#{turn_count})"
            self.mode_badge.setText(conv_label)
        self._refresh_badge_style()

    def apply_theme(self, theme: Optional[Any]) -> None:
        """Applies adaptive stylesheet based on background luminance."""
        self.theme = theme
        self.setStyleSheet(generate_input_modal_qss(theme))
        self._refresh_badge_style()

    def _refresh_badge_style(self) -> None:
        """Updates badge colors based on mode and current background contrast."""
        is_dark = self.theme.is_dark_background if hasattr(self, "theme") and self.theme else True
        if self.mode == "quick":
            if is_dark:
                self.mode_badge.setStyleSheet(
                    "background-color: rgba(14, 165, 233, 0.2); color: #38BDF8; border: 1px solid rgba(14, 165, 233, 0.35);"
                )
            else:
                self.mode_badge.setStyleSheet(
                    "background-color: rgba(2, 132, 199, 0.12); color: #0284C7; border: 1px solid rgba(2, 132, 199, 0.28);"
                )
        else:
            if is_dark:
                self.mode_badge.setStyleSheet(
                    "background-color: rgba(168, 85, 247, 0.2); color: #C084FC; border: 1px solid rgba(168, 85, 247, 0.35);"
                )
            else:
                self.mode_badge.setStyleSheet(
                    "background-color: rgba(147, 51, 234, 0.12); color: #7E22CE; border: 1px solid rgba(147, 51, 234, 0.28);"
                )

    def show_modal(self, monitor: Optional[Any] = None, placement: str = "cursor", theme: Optional[Any] = None) -> None:
        """Positions modal based on user placement preference ('cursor' or 'center') and target monitor."""
        if theme:
            self.apply_theme(theme)
        if placement == "center" and monitor:
            target_x = monitor.left + (monitor.width - self.width()) // 2
            target_y = monitor.top + (monitor.height - self.height()) // 2
        elif placement == "center":
            cursor_pos = QCursor.pos()
            screen = QGuiApplication.screenAt(cursor_pos) or QGuiApplication.primaryScreen()
            geo = screen.geometry() if screen else QRect(0, 0, 1920, 1080)
            target_x = geo.left() + (geo.width() - self.width()) // 2
            target_y = geo.top() + (geo.height() - self.height()) // 2
        else:
            cursor_pos = QCursor.pos()
            target_x = cursor_pos.x() - self.width() // 2
            target_y = cursor_pos.y() - self.height() // 2

        # Clamp inside target monitor or active screen
        margin = 24
        if monitor:
            clamped_x = max(monitor.left + margin, min(target_x, monitor.right - self.width() - margin))
            clamped_y = max(monitor.top + margin, min(target_y, monitor.bottom - self.height() - margin))
        else:
            cursor_pos = QCursor.pos()
            screen = QGuiApplication.screenAt(cursor_pos) or QGuiApplication.primaryScreen()
            geo = screen.geometry() if screen else QRect(0, 0, 1920, 1080)
            clamped_x = max(geo.left() + margin, min(target_x, geo.right() - self.width() - margin))
            clamped_y = max(geo.top() + margin, min(target_y, geo.bottom() - self.height() - margin))

        self.move(clamped_x, clamped_y)
        self.input_edit.clear()
        self.setWindowOpacity(0.0)
        self.show()
        self.raise_()
        self.setWindowState(self.windowState() & ~Qt.WindowState.WindowMinimized | Qt.WindowState.WindowActive)
        self.activateWindow()

        hwnd = int(self.winId())
        _force_foreground_window(hwnd)

        # Multi-stage focus grab to ensure focus locks in even after physical Alt key release
        self.input_edit.setFocus(Qt.FocusReason.ActiveWindowFocusReason)
        QTimer.singleShot(30, self._ensure_focus)
        QTimer.singleShot(90, self._ensure_focus)

        # Fade in
        self._anim = QPropertyAnimation(self, b"windowOpacity")
        self._anim.setDuration(160)
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.setEasingCurve(QEasingCurve.Type.OutQuad)
        self._anim.start()

    def _ensure_focus(self) -> None:
        """Reinforces foreground and keyboard focus."""
        if self.isVisible():
            hwnd = int(self.winId())
            _force_foreground_window(hwnd)
            self.activateWindow()
            self.input_edit.setFocus(Qt.FocusReason.ActiveWindowFocusReason)

    def show_at_cursor(self) -> None:
        """Backward-compatible helper."""
        self.show_modal(placement="cursor")

    def _on_submit(self) -> None:
        text = self.input_edit.text().strip()
        if text:
            self.hide()
            self.query_submitted.emit(text, self.mode)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.hide()
            self.dismissed.emit()
            event.accept()
        else:
            super().keyPressEvent(event)
