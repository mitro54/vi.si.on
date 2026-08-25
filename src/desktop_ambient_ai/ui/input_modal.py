"""
Clean, floating query input modal with mode indication, multi-image attachments, and smooth fade transitions.
"""

from __future__ import annotations

from typing import Any, List, Literal, Optional

from PyQt6.QtCore import QEasingCurve, QPoint, QPropertyAnimation, QRect, Qt, QTimer, pyqtSignal
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


class PromptLineEdit(QLineEdit):
    """Custom LineEdit that intercepts hotkey combinations to prevent accidental character insertions and enable arrow navigation."""

    alt_ocr_pressed = pyqtSignal()
    cycle_conv_requested = pyqtSignal(int)  # -1 for prev, +1 for next

    def keyPressEvent(self, event: QKeyEvent) -> None:
        is_alt = bool(event.modifiers() & Qt.KeyboardModifier.AltModifier)

        # 1. Intercept Alt+1, Alt+2, Alt+3 so numbers are NEVER typed into prompt text
        if is_alt and event.key() in (Qt.Key.Key_1, Qt.Key.Key_2, Qt.Key.Key_3):
            event.accept()
            if event.key() == Qt.Key.Key_3:
                self.alt_ocr_pressed.emit()
            elif event.key() == Qt.Key.Key_2:
                # Repeatedly pressing or holding Alt+2 cycles to the next conversation!
                self.cycle_conv_requested.emit(1)
            return

        # 2. Intercept Alt+Up / Alt+Down or Up/Down arrows to cycle conversations
        if (is_alt and event.key() == Qt.Key.Key_Up) or (not self.text() and event.key() == Qt.Key.Key_Up):
            event.accept()
            self.cycle_conv_requested.emit(-1)
            return

        if (is_alt and event.key() == Qt.Key.Key_Down) or (not self.text() and event.key() == Qt.Key.Key_Down):
            event.accept()
            self.cycle_conv_requested.emit(1)
            return

        super().keyPressEvent(event)


class InputModal(QWidget):
    """Floating modal prompt to receive user queries."""

    query_submitted = pyqtSignal(str, str)  # (query_text, mode)
    dismissed = pyqtSignal()
    ocr_requested = pyqtSignal()
    cycle_conv_requested = pyqtSignal(int)  # -1 for prev, +1 for next

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.mode: Literal["quick", "conversation"] = "quick"
        self.turn_count: int = 1
        self._anim: Optional[QPropertyAnimation] = None
        self._attached_images: List[str] = []
        self._attached_metadata: List[tuple[int, int]] = []
        self.theme: Optional[Any] = None

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Window
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setObjectName("InputModalRoot")
        self.setStyleSheet(generate_input_modal_qss())

        self.setFixedSize(540, 110)
        self._init_ui()

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(14, 10, 14, 10)
        main_layout.setSpacing(6)

        # Top Bar: Mode Badge + Attached Image Chip + Shortcuts Hint
        top_bar = QHBoxLayout()
        top_bar.setContentsMargins(0, 0, 0, 0)
        top_bar.setSpacing(8)

        self.mode_badge = QLabel("⚡ Quick Query", self)
        self.mode_badge.setObjectName("ModeBadge")
        top_bar.addWidget(self.mode_badge)

        # Region Image Attachment Pill Chip
        self.img_chip = QLabel("🖼 Region Attached", self)
        self.img_chip.setObjectName("ImageChip")
        self.img_chip.setStyleSheet(
            "background-color: rgba(16, 185, 129, 0.2); color: #34D399; "
            "border: 1px solid rgba(16, 185, 129, 0.4); border-radius: 4px; padding: 2px 6px; font-size: 11px; font-weight: bold;"
        )
        self.img_chip.hide()
        top_bar.addWidget(self.img_chip)

        top_bar.addStretch()

        self.hint_label = QLabel("Enter to submit • Alt+2 / ↑↓ switch • Alt+3 snip • Esc", self)
        self.hint_label.setObjectName("HintLabel")
        top_bar.addWidget(self.hint_label)

        main_layout.addLayout(top_bar)

        # Bottom: Text Input
        self.input_edit = PromptLineEdit(self)
        self.input_edit.setObjectName("PromptInput")
        self.input_edit.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.input_edit.setPlaceholderText("Ask anything (or press Alt+3 to select a screen area)...")
        self.input_edit.returnPressed.connect(self._on_submit)
        self.input_edit.alt_ocr_pressed.connect(self.ocr_requested.emit)
        self.input_edit.cycle_conv_requested.connect(self.cycle_conv_requested.emit)
        main_layout.addWidget(self.input_edit)

    def attach_image_snip(self, b64_png: str, width: int, height: int, is_vision_capable: bool = True) -> None:
        """Attaches a snipped screen image to the active prompt. Supports multiple images."""
        self._attached_images.append(b64_png)
        self._attached_metadata.append((width, height))

        total = len(self._attached_images)
        if is_vision_capable:
            if total == 1:
                self.img_chip.setText(f"🖼 1 Region ({width}×{height})")
            else:
                self.img_chip.setText(f"🖼 {total} Regions Attached")
            self.img_chip.setStyleSheet(
                "background-color: rgba(16, 185, 129, 0.2); color: #34D399; "
                "border: 1px solid rgba(16, 185, 129, 0.4); border-radius: 4px; padding: 2px 6px; font-size: 11px; font-weight: bold;"
            )
        else:
            self.img_chip.setText(f"⚠️ Model lacks vision ({total} attached)")
            self.img_chip.setStyleSheet(
                "background-color: rgba(245, 158, 11, 0.2); color: #FBBF24; "
                "border: 1px solid rgba(245, 158, 11, 0.4); border-radius: 4px; padding: 2px 6px; font-size: 11px; font-weight: bold;"
            )
        self.img_chip.show()
        self.input_edit.setPlaceholderText("Ask a question about the snipped screen area(s)...")

    def detach_image(self) -> None:
        """Clears all attached images."""
        self._attached_images.clear()
        self._attached_metadata.clear()
        self.img_chip.hide()
        self.input_edit.setPlaceholderText("Ask anything (or press Alt+3 to select a screen area)...")

    def get_attached_image(self) -> Optional[str]:
        """Returns the primary attached image, if any."""
        return self._attached_images[0] if self._attached_images else None

    def get_attached_images(self) -> List[str]:
        """Returns all attached image payloads."""
        return list(self._attached_images)

    def set_mode(self, mode: Literal["quick", "conversation"], turn_count: int = 1, title: Optional[str] = None) -> None:
        """Updates modal visual mode and context labels."""
        self.mode = mode
        self.turn_count = turn_count
        if mode == "quick":
            if turn_count > 1:
                self.mode_badge.setText(f"⚡ Quick Follow-up (#{turn_count})")
            else:
                self.mode_badge.setText("⚡ Quick One-Off")
        else:
            conv_label = f"🗨 Conversation (#{turn_count})"
            if title and title not in ("New Conversation", "Follow-up", "Quick Follow-up"):
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

    def show_modal(
        self,
        monitor: Optional[Any] = None,
        placement: str = "cursor",
        theme: Optional[Any] = None,
        clear_text: bool = True,
        exact_pos: Optional[QPoint] = None,
    ) -> None:
        """Positions modal based on user placement preference ('cursor' or 'center') and target monitor."""
        if theme:
            self.apply_theme(theme)

        if exact_pos:
            clamped_x, clamped_y = exact_pos.x(), exact_pos.y()
        else:
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
        if clear_text:
            self.input_edit.clear()
            self.detach_image()

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
        if not text and self._attached_images:
            text = "Describe and analyze the attached screen region(s) in detail."
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
