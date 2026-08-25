"""
High-performance transparent screen snipping overlay.
Maintains exact 1:1 pixel-perfect desktop resolution across mixed-DPI multi-monitor displays.
"""

from __future__ import annotations

import base64
from typing import Optional

from PyQt6.QtCore import QBuffer, QByteArray, QIODevice, QPoint, QRect, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QGuiApplication, QPainter, QPen, QPixmap
from PyQt6.QtWidgets import QApplication, QWidget

from ..vision.capture import ScreenCapture


class ScreenSnipper(QWidget):
    """Full-screen interactive region selection overlay for Alt+3 snipping."""

    region_selected = pyqtSignal(bytes, str, object, QRect)  # (png_bytes, b64_png, None, qrect)
    cancelled = pyqtSignal()

    def __init__(self, capture_engine: Optional[ScreenCapture] = None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.capture_engine = capture_engine or ScreenCapture()

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setCursor(Qt.CursorShape.CrossCursor)

        self._start_pos: Optional[QPoint] = None
        self._current_pos: Optional[QPoint] = None
        self._is_selecting = False
        self._virtual_rect = QRect()

    def start_selection(self) -> None:
        """Positions transparent canvas across all monitors with zero zoom or DPI distortion."""
        screens = QGuiApplication.screens()
        if not screens:
            self.cancelled.emit()
            return

        min_x = min(s.geometry().left() for s in screens)
        min_y = min(s.geometry().top() for s in screens)
        max_x = max(s.geometry().right() for s in screens)
        max_y = max(s.geometry().bottom() for s in screens)
        vw = max_x - min_x + 1
        vh = max_y - min_y + 1
        self._virtual_rect = QRect(min_x, min_y, vw, vh)

        self.setGeometry(self._virtual_rect)
        self._start_pos = None
        self._current_pos = None
        self._is_selecting = False

        self.show()
        self.raise_()
        self.activateWindow()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._start_pos = event.pos()
            self._current_pos = event.pos()
            self._is_selecting = True
            self.update()
        elif event.button() == Qt.MouseButton.RightButton:
            self._cancel()

    def mouseMoveEvent(self, event):
        if self._is_selecting and self._start_pos:
            self._current_pos = event.pos()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._is_selecting:
            self._is_selecting = False
            self._current_pos = event.pos()
            self._finish_selection()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self._cancel()
        else:
            super().keyPressEvent(event)

    def _cancel(self) -> None:
        self.hide()
        self.cancelled.emit()

    def _finish_selection(self) -> None:
        if not self._start_pos or not self._current_pos:
            self._cancel()
            return

        sel_rect = QRect(self._start_pos, self._current_pos).normalized()

        # Hide overlay BEFORE capturing the screen so the overlay itself is not visible in the snip
        self.hide()
        QApplication.processEvents()

        if sel_rect.width() < 12 or sel_rect.height() < 12:
            self.cancelled.emit()
            return

        # Map local widget coordinate to global desktop space
        global_top_left = self.mapToGlobal(sel_rect.topLeft())
        global_sel_rect = QRect(global_top_left, sel_rect.size())

        # Determine target screen based on selection center
        center = global_sel_rect.center()
        target_screen = QGuiApplication.screenAt(center) or QGuiApplication.primaryScreen()
        geo = target_screen.geometry()

        local_x = global_sel_rect.x() - geo.x()
        local_y = global_sel_rect.y() - geo.y()
        local_w = global_sel_rect.width()
        local_h = global_sel_rect.height()

        # Native hardware screen grab with 100% native resolution
        cropped_pixmap = target_screen.grabWindow(0, local_x, local_y, local_w, local_h)
        if cropped_pixmap.isNull():
            self.cancelled.emit()
            return

        # Encode to PNG bytes and base64
        byte_array = QByteArray()
        buffer = QBuffer(byte_array)
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        cropped_pixmap.save(buffer, "PNG")
        png_bytes = byte_array.data()
        b64_png = base64.b64encode(png_bytes).decode("utf-8")

        self.region_selected.emit(png_bytes, b64_png, None, sel_rect)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 1. Fill entire canvas with translucent dim curtain
        curtain_color = QColor(0, 0, 0, 95)
        painter.fillRect(self.rect(), curtain_color)

        # 2. If dragging: clear cutout to reveal the 100% native crisp desktop underneath
        if self._start_pos and self._current_pos:
            sel_rect = QRect(self._start_pos, self._current_pos).normalized()

            # Punch clear hole through dim curtain
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
            painter.fillRect(sel_rect, Qt.GlobalColor.transparent)
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)

            # Glowing neon border
            border_pen = QPen(QColor(56, 189, 248, 255), 2)
            painter.setPen(border_pen)
            painter.setBrush(QColor(56, 189, 248, 15))
            painter.drawRect(sel_rect)

            # Corner accents
            corner_len = min(14, min(sel_rect.width() // 3, sel_rect.height() // 3))
            if corner_len > 4:
                accent_pen = QPen(QColor(255, 255, 255, 255), 3)
                painter.setPen(accent_pen)
                # Top-Left
                painter.drawLine(sel_rect.left(), sel_rect.top(), sel_rect.left() + corner_len, sel_rect.top())
                painter.drawLine(sel_rect.left(), sel_rect.top(), sel_rect.left(), sel_rect.top() + corner_len)
                # Top-Right
                painter.drawLine(sel_rect.right(), sel_rect.top(), sel_rect.right() - corner_len, sel_rect.top())
                painter.drawLine(sel_rect.right(), sel_rect.top(), sel_rect.right(), sel_rect.top() + corner_len)
                # Bottom-Left
                painter.drawLine(sel_rect.left(), sel_rect.bottom(), sel_rect.left() + corner_len, sel_rect.bottom())
                painter.drawLine(sel_rect.left(), sel_rect.bottom(), sel_rect.left(), sel_rect.bottom() - corner_len)
                # Bottom-Right
                painter.drawLine(sel_rect.right(), sel_rect.bottom(), sel_rect.right() - corner_len, sel_rect.bottom())
                painter.drawLine(sel_rect.right(), sel_rect.bottom(), sel_rect.right(), sel_rect.bottom() - corner_len)

            # Live dimensions tag
            dim_text = f"{sel_rect.width()} × {sel_rect.height()} px"
            painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
            badge_w, badge_h = 100, 22
            badge_x = sel_rect.center().x() - badge_w // 2
            badge_y = sel_rect.bottom() + 8
            if badge_y + badge_h > self.height() - 8:
                badge_y = sel_rect.top() - badge_h - 8

            badge_rect = QRect(badge_x, badge_y, badge_w, badge_h)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(15, 23, 42, 230))
            painter.drawRoundedRect(badge_rect, 4, 4)

            painter.setPen(QColor(248, 250, 252))
            painter.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, dim_text)
        else:
            # Top instructional hint banner
            painter.setFont(QFont("Segoe UI", 12, QFont.Weight.DemiBold))
            painter.setPen(QColor(248, 250, 252, 220))
            hint_rect = QRect(0, 32, self.width(), 36)
            painter.drawText(
                hint_rect,
                Qt.AlignmentFlag.AlignCenter,
                "Drag to select a screen area • Press Esc to cancel",
            )
