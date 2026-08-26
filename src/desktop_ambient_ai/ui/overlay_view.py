"""
Dynamic transparent response overlay with adaptive contrast and auto-downscaling typometry.
"""

from __future__ import annotations

import math

from PyQt6.QtCore import (
    QEasingCurve,
    QEvent,
    QPropertyAnimation,
    QRect,
    Qt,
    QTimer,
    pyqtSignal,
)
from PyQt6.QtGui import QGuiApplication, QTextCursor, QTextOption, QWheelEvent
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..config import AppConfig
from ..vision.spatial_finder import SpatialResult
from .math_renderer import render_markdown_with_math
from .styles import generate_overlay_qss


class OverlayView(QWidget):
    """Ambient floating overlay rendering LLM responses with dynamic contrast."""

    dismissed = pyqtSignal()
    promoted = pyqtSignal()

    def __init__(self, config: AppConfig, parent: QWidget | None = None):
        super().__init__(parent)
        self.config = config
        self.spatial_result: SpatialResult | None = None
        self._raw_markdown: str = ""
        self._char_count: int = 0
        self._current_font_size: int = config.typography.font_base_size
        self._fade_anim: QPropertyAnimation | None = None

        # Auto close timer state
        self._auto_close_timer = QTimer(self)
        self._auto_close_timer.setInterval(1000)
        self._auto_close_timer.timeout.connect(self._on_timer_tick)
        self._remaining_seconds: int = config.overlay.auto_close_seconds
        self._is_streaming: bool = False

        # Render batching timer for smooth 60fps UI performance during token streaming
        self._pending_render: bool = False
        self._render_timer = QTimer(self)
        self._render_timer.setInterval(35)
        self._render_timer.timeout.connect(self._flush_render)

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setMouseTracking(True)
        self.setObjectName("OverlayRoot")

        self._init_ui()

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(18, 14, 18, 16)
        main_layout.setSpacing(10)

        # Header Bar: Mode Badge + Auto Close Countdown + Dismiss Button
        header_bar = QHBoxLayout()
        header_bar.setContentsMargins(0, 0, 0, 0)

        self.badge_label = QLabel("⚡ Quick Response", self)
        self.badge_label.setObjectName("HeaderBadge")
        header_bar.addWidget(self.badge_label)

        self.status_label = QLabel("", self)
        self.status_label.setObjectName("HeaderStatus")
        self.status_label.setVisible(False)
        header_bar.addWidget(self.status_label)

        header_bar.addStretch()

        self.copy_btn = QPushButton("📋 Copy", self)
        self.copy_btn.setObjectName("CopyBtn")
        self.copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.copy_btn.setToolTip("Copy response (Markdown) to clipboard")
        self.copy_btn.clicked.connect(self._copy_to_clipboard)
        header_bar.addWidget(self.copy_btn)

        self.timer_label = QLabel("", self)
        self.timer_label.setObjectName("TimerLabel")
        header_bar.addWidget(self.timer_label)

        self.dismiss_btn = QPushButton("✕", self)
        self.dismiss_btn.setObjectName("DismissBtn")
        self.dismiss_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.dismiss_btn.setToolTip("Dismiss (Esc)")
        self.dismiss_btn.clicked.connect(self.dismiss_smoothly)
        header_bar.addWidget(self.dismiss_btn)

        main_layout.addLayout(header_bar)

        # Content Text Display
        self.content_edit = QTextEdit(self)
        self.content_edit.setObjectName("ContentDisplay")
        self.content_edit.setReadOnly(True)
        self.content_edit.setUndoRedoEnabled(False)
        self.content_edit.setAcceptRichText(True)
        self.content_edit.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self.content_edit.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.content_edit.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        opt = QTextOption()
        opt.setWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
        self.content_edit.document().setDefaultTextOption(opt)
        self.content_edit.document().setDocumentMargin(8)
        self.content_edit.setMouseTracking(True)
        self.content_edit.viewport().setMouseTracking(True)
        self.content_edit.viewport().installEventFilter(self)
        main_layout.addWidget(self.content_edit)

    def set_status(self, text: str) -> None:
        """Updates real-time activity status (e.g. searching web, running tools, thinking)."""
        if not text:
            self.status_label.setText("")
            self.status_label.setVisible(False)
        else:
            self.status_label.setText(text)
            self.status_label.setVisible(True)

    def prepare_for_stream(self, spatial: SpatialResult, mode: str = "quick", turn_count: int = 1) -> None:
        """Applies geometry, dynamic styles, and resets text buffers before streaming begins."""
        self.spatial_result = spatial
        self._raw_markdown = ""
        self._char_count = 0
        self._is_streaming = True
        self._pending_render = False
        self._render_timer.stop()
        self._auto_close_timer.stop()
        self.timer_label.setText("")
        self.set_status("Thinking...")
        self._reset_copy_btn()


        # Position and size enforcing user-configured minimum constraints
        rect = spatial.target_rect
        w = max(self.config.overlay.min_width, rect.width)
        h = max(self.config.overlay.min_height, rect.height)

        # Clamp strictly within target monitor's visible work area
        target_screen = None
        for s in QGuiApplication.screens():
            s_geo = s.geometry()
            if s_geo.contains(rect.x, rect.y):
                target_screen = s
                break
        if not target_screen:
            target_screen = QGuiApplication.primaryScreen()

        if target_screen:
            avail = target_screen.availableGeometry()
            pad = 16
            final_w = min(w, avail.width() - 2 * pad)
            final_h = min(h, avail.height() - 2 * pad)
            final_x = max(avail.left() + pad, min(rect.x, avail.right() - final_w - pad))
            final_y = max(avail.top() + pad, min(rect.y, avail.bottom() - final_h - pad))
            self.setGeometry(QRect(final_x, final_y, final_w, final_h))
        else:
            self.setGeometry(QRect(rect.x, rect.y, w, h))

        # Reset typography & styling
        self._current_font_size = spatial.typography.base_font_size
        self.setStyleSheet(generate_overlay_qss(spatial.theme, self._current_font_size, spatial.is_fallback_mode))

        # Badge state
        if mode == "quick":
            self.badge_label.setText("⚡ Quick Response")
        else:
            self.badge_label.setText(f"🗨 Conversation (#{turn_count})")

        self.content_edit.clear()

        # Fade in
        self.setWindowOpacity(0.0)
        self.show()
        self.raise_()

        self._fade_anim = QPropertyAnimation(self, b"windowOpacity")
        self._fade_anim.setDuration(220)
        self._fade_anim.setStartValue(0.0)
        self._fade_anim.setEndValue(1.0)
        self._fade_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._fade_anim.start()

    def get_raw_markdown(self) -> str:
        """Returns the unparsed raw markdown received during generation."""
        return self._raw_markdown

    def append_token(self, token: str) -> None:
        """Appends streaming token to buffer and batches render updates for smooth UI performance."""
        self._raw_markdown += token
        self._char_count += len(token)
        self._pending_render = True

        if not self._render_timer.isActive():
            self._render_timer.start()

    def _flush_render(self) -> None:
        """Flushes accumulated streaming tokens to the UI with full Markdown and math formatting."""
        if not self._pending_render and self.content_edit.toPlainText():
            return
        self._pending_render = False
        self._render_timer.stop()

        # Render rich HTML with full LaTeX mathematical notation and syntax-highlighted code
        theme = self.spatial_result.theme if self.spatial_result else None
        html_content = render_markdown_with_math(self._raw_markdown, theme=theme)
        self.content_edit.setHtml(html_content)
        opt = QTextOption()
        opt.setWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
        self.content_edit.document().setDefaultTextOption(opt)

        # Ensure auto-scroll follows generation
        cursor = self.content_edit.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.content_edit.setTextCursor(cursor)
        self.content_edit.ensureCursorVisible()

        # Dynamic typometry formula: S(N) = max(S_min, S_base - floor((N - N_thresh) / k))
        if self.spatial_result:
            typo = self.spatial_result.typography
            if self._char_count > typo.downscale_threshold:
                downscale_steps = math.floor((self._char_count - typo.downscale_threshold) / typo.downscale_rate)
                new_font_size = max(typo.min_font_size, typo.base_font_size - downscale_steps)
                if new_font_size != self._current_font_size:
                    self._current_font_size = new_font_size
                    self.setStyleSheet(
                        generate_overlay_qss(
                            self.spatial_result.theme,
                            self._current_font_size,
                            self.spatial_result.is_fallback_mode,
                        )
                    )

    def finalize_display(self) -> None:
        """Called when streaming finishes. Flushes any pending tokens and arms auto-close timers."""
        self._is_streaming = False
        self._render_timer.stop()
        self.set_status("")
        self._flush_render()


        auto_mode = self.config.overlay.auto_close

        if auto_mode == "timer":
            self._remaining_seconds = self.config.overlay.auto_close_seconds
            self.timer_label.setText(f"Closing in {self._remaining_seconds}s")
            self._auto_close_timer.start()
        elif auto_mode == "immediate":
            QTimer.singleShot(1800, self.dismiss_smoothly)


    def mark_promoted(self) -> None:
        """Visual indication when a quick query is auto-promoted to a persistent conversation."""
        self.badge_label.setText("🗨 Promoted to Saved Conversation")
        self.badge_label.setStyleSheet(
            "background-color: rgba(168, 85, 247, 0.25); color: #C084FC; font-weight: 700; "
            "padding: 3px 8px; border-radius: 6px; border: 1px solid rgba(168, 85, 247, 0.45);"
        )

    def _on_timer_tick(self) -> None:
        """Countdown tick for timer-based auto-close."""
        self._remaining_seconds -= 1
        if self._remaining_seconds > 0:
            self.timer_label.setText(f"Closing in {self._remaining_seconds}s")
        else:
            self._auto_close_timer.stop()
            self.dismiss_smoothly()

    def scroll_by_delta(self, dy: int) -> None:
        """Scrolls content up/down smoothly and pauses the auto-close timer."""
        if not self.isVisible():
            return
        if not self._is_streaming and self._auto_close_timer.isActive():
            self._auto_close_timer.stop()
            self.timer_label.setText("Paused")

        sb = self.content_edit.verticalScrollBar()
        # dy is positive for scroll up, negative for scroll down
        step = -dy * 50
        sb.setValue(sb.value() + step)

    def wheelEvent(self, event: QWheelEvent) -> None:
        """Enables smooth mouse-wheel scrolling across the entire overlay."""
        delta = event.angleDelta().y()
        if delta != 0:
            dy = 1 if delta > 0 else -1
            self.scroll_by_delta(dy)
            event.accept()
        else:
            super().wheelEvent(event)

    def eventFilter(self, watched, event: QEvent) -> bool:
        """Intercepts viewport events to ensure scroll wheel always rolls text and pauses timer."""
        if event.type() == QEvent.Type.Wheel:
            delta = event.angleDelta().y()
            if delta != 0:
                dy = 1 if delta > 0 else -1
                self.scroll_by_delta(dy)
                return True
        elif event.type() == QEvent.Type.Enter:
            if not self._is_streaming and self._auto_close_timer.isActive():
                self._auto_close_timer.stop()
                self.timer_label.setText("Paused")
        elif event.type() == QEvent.Type.Leave:
            if (
                not self._is_streaming
                and self.config.overlay.auto_close == "timer"
                and not self.geometry().contains(self.mapFromGlobal(self.cursor().pos()))
            ):
                self._auto_close_timer.start()

        return super().eventFilter(watched, event)

    def enterEvent(self, event) -> None:
        """Pauses auto-close timer on hover so user can comfortably read."""
        if not self._is_streaming and self._auto_close_timer.isActive():
            self._auto_close_timer.stop()
            self.timer_label.setText("Paused")
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        """Resumes auto-close countdown when cursor leaves the overlay."""
        if not self._is_streaming and self.config.overlay.auto_close == "timer":
            self._auto_close_timer.start()
        super().leaveEvent(event)

    def dismiss_smoothly(self) -> None:
        """Performs smooth fade-out animation and hides window."""
        self._auto_close_timer.stop()
        if self.isVisible() and self.windowOpacity() > 0.0:
            self._fade_anim = QPropertyAnimation(self, b"windowOpacity")
            self._fade_anim.setDuration(200)
            self._fade_anim.setStartValue(self.windowOpacity())
            self._fade_anim.setEndValue(0.0)
            self._fade_anim.setEasingCurve(QEasingCurve.Type.InQuad)
            self._fade_anim.finished.connect(self._on_fade_finished)
            self._fade_anim.start()
        else:
            self.hide()
            self.dismissed.emit()

    def _copy_to_clipboard(self) -> None:
        """Copies markdown response to system clipboard with visual confirmation and pauses timer."""
        text_to_copy = self._raw_markdown.strip() if self._raw_markdown else self.content_edit.toPlainText().strip()
        if not text_to_copy:
            return

        clipboard = QGuiApplication.clipboard()
        if clipboard:
            clipboard.setText(text_to_copy)

        # Pause countdown timer while user interacts with copy
        if not self._is_streaming and self._auto_close_timer.isActive():
            self._auto_close_timer.stop()
            self.timer_label.setText("Paused")

        self.copy_btn.setText("✓ Copied!")
        self.copy_btn.setToolTip("Copied response to clipboard!")
        QTimer.singleShot(1800, self._reset_copy_btn)

    def _reset_copy_btn(self) -> None:
        """Restores copy button text and tooltip."""
        if hasattr(self, "copy_btn"):
            self.copy_btn.setText("📋 Copy")
            self.copy_btn.setToolTip("Copy response (Markdown) to clipboard")

    def _on_fade_finished(self) -> None:
        self.hide()
        self.dismissed.emit()


