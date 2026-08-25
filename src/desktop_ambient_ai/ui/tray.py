"""
System Tray Manager for background ambient presence and quick actions.
"""

from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtGui import QAction, QColor, QIcon, QPainter, QPixmap
from PyQt6.QtWidgets import QMenu, QMessageBox, QSystemTrayIcon


class SystemTrayManager(QObject):
    """Manages the system tray icon, notifications, and menu actions."""

    quick_chat_requested = pyqtSignal()
    conversation_requested = pyqtSignal()
    new_conversation_requested = pyqtSignal()
    settings_requested = pyqtSignal()
    quit_requested = pyqtSignal()

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.tray_icon = QSystemTrayIcon(self)
        self._init_icon()
        self._init_menu()

    def _init_icon(self) -> None:
        # Generate a high-contrast glowing orb icon programmatically
        pixmap = QPixmap(32, 32)
        pixmap.fill(QColor(0, 0, 0, 0))

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Outer glow
        painter.setBrush(QColor(14, 165, 233, 100))
        painter.setPen(QColor(0, 0, 0, 0))
        painter.drawEllipse(2, 2, 28, 28)

        # Inner vibrant core
        painter.setBrush(QColor(56, 189, 248, 255))
        painter.drawEllipse(6, 6, 20, 20)

        # Sparkle accent
        painter.setBrush(QColor(255, 255, 255, 240))
        painter.drawEllipse(10, 10, 6, 6)

        painter.end()

        self.tray_icon.setIcon(QIcon(pixmap))
        self.tray_icon.setToolTip("vi.si.on")
        self.tray_icon.show()

    def _init_menu(self) -> None:
        menu = QMenu()

        act_quick = QAction("⚡ Quick Query (Alt+1)", self)
        act_quick.triggered.connect(self.quick_chat_requested.emit)
        menu.addAction(act_quick)

        act_conv = QAction("🗨 Active Conversation (Alt+2)", self)
        act_conv.triggered.connect(self.conversation_requested.emit)
        menu.addAction(act_conv)

        act_new_conv = QAction("➕ New Conversation (Alt+Shift+2)", self)
        act_new_conv.triggered.connect(self.new_conversation_requested.emit)
        menu.addAction(act_new_conv)

        menu.addSeparator()

        act_settings = QAction("⚙ Settings / Setup Wizard...", self)
        act_settings.triggered.connect(self.settings_requested.emit)
        menu.addAction(act_settings)

        act_about = QAction("ℹ About vi.si.on", self)
        act_about.triggered.connect(self._show_about)
        menu.addAction(act_about)

        menu.addSeparator()

        act_quit = QAction("✕ Quit vi.si.on", self)
        act_quit.triggered.connect(self.quit_requested.emit)
        menu.addAction(act_quit)

        self.tray_icon.setContextMenu(menu)

    def _show_about(self) -> None:
        QMessageBox.information(
            None,
            "About vi.si.on",
            "<h3>vi.si.on 🔮</h3>"
            "<p>An ambient, non-intrusive transparent desktop assistant with computer vision spatial clutter minimization, "
            "adaptive luminance contrast, and streaming inference.</p>"
            "<p><b>Version:</b> 0.1.0</p>",
        )

    def show_notification(self, title: str, message: str) -> None:
        """Displays balloon / system notification."""
        self.tray_icon.showMessage(title, message, QSystemTrayIcon.MessageIcon.Information, 4000)
