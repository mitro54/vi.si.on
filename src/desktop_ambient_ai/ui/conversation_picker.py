"""
Alt-Tab style Conversation Picker popup for switching past memorized sessions.
"""

from __future__ import annotations

from typing import List, Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QCursor, QGuiApplication, QKeyEvent
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..storage.conversation_store import ConversationStore, ConversationSummary
from .styles import generate_picker_qss


class ConversationPicker(QWidget):
    """Floating Alt-Tab style selector for historical conversations."""

    conversation_selected = pyqtSignal(str)  # conversation_id
    dismissed = pyqtSignal()

    def __init__(self, store: ConversationStore, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.store = store
        self._summaries: List[ConversationSummary] = []

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setObjectName("PickerRoot")
        self.setStyleSheet(generate_picker_qss())

        self.setFixedSize(500, 360)
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        # Title
        header = QLabel("🗨 Select Conversation (↑ / ↓ to navigate, Enter to load)", self)
        header.setObjectName("PickerTitle")
        layout.addWidget(header)

        # List
        self.list_widget = QListWidget(self)
        self.list_widget.setObjectName("ConversationList")
        self.list_widget.itemDoubleClicked.connect(self._on_item_chosen)
        layout.addWidget(self.list_widget)

    def show_picker(self) -> None:
        """Populates past conversations, positions popup, and highlights first item."""
        self._summaries = self.store.list_persistent(limit=15)
        self.list_widget.clear()

        if not self._summaries:
            item = QListWidgetItem("No saved conversations yet. Press Alt+Shift+2 to start one.")
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.list_widget.addItem(item)
        else:
            for s in self._summaries:
                title = s.title[:45] if s.title else "Untitled Conversation"
                time_snippet = s.updated_at.split("T")[0] if "T" in s.updated_at else s.updated_at
                label_text = f"<b>{title}</b>  <span style='color: #94A3B8;'>({s.message_count} msgs • {time_snippet})</span><br/><span style='color: #64748B; font-size: 11px;'>{s.last_snippet[:70]}...</span>"
                item = QListWidgetItem()
                item.setData(Qt.ItemDataRole.UserRole, s.id)
                self.list_widget.addItem(item)

                # Custom widget for rich formatted text
                lbl = QLabel(label_text, self)
                lbl.setStyleSheet("background: transparent; color: #F8FAFC;")
                lbl.setTextFormat(Qt.TextFormat.RichText)
                self.list_widget.setItemWidget(item, lbl)

            self.list_widget.setCurrentRow(0)

        # Position at screen center
        cursor_pos = QCursor.pos()
        screen = QGuiApplication.screenAt(cursor_pos) or QGuiApplication.primaryScreen()
        geo = screen.geometry() if screen else self.geometry()
        x = geo.left() + (geo.width() - self.width()) // 2
        y = geo.top() + (geo.height() - self.height()) // 2
        self.move(x, y)

        self.show()
        self.raise_()
        self.activateWindow()
        self.list_widget.setFocus()

    def select_next(self) -> None:
        """Navigates to next conversation item."""
        count = self.list_widget.count()
        if count > 0:
            row = (self.list_widget.currentRow() + 1) % count
            self.list_widget.setCurrentRow(row)

    def select_previous(self) -> None:
        """Navigates to previous conversation item."""
        count = self.list_widget.count()
        if count > 0:
            row = (self.list_widget.currentRow() - 1 + count) % count
            self.list_widget.setCurrentRow(row)

    def confirm_selection(self) -> None:
        """Loads currently highlighted item."""
        current_item = self.list_widget.currentItem()
        if current_item:
            conv_id = current_item.data(Qt.ItemDataRole.UserRole)
            if conv_id:
                self.hide()
                self.conversation_selected.emit(conv_id)
                return
        self.hide()
        self.dismissed.emit()

    def _on_item_chosen(self, item: QListWidgetItem) -> None:
        conv_id = item.data(Qt.ItemDataRole.UserRole)
        if conv_id:
            self.hide()
            self.conversation_selected.emit(conv_id)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.confirm_selection()
            event.accept()
        elif event.key() == Qt.Key.Key_Escape:
            self.hide()
            self.dismissed.emit()
            event.accept()
        elif event.key() == Qt.Key.Key_Down:
            self.select_next()
            event.accept()
        elif event.key() == Qt.Key.Key_Up:
            self.select_previous()
            event.accept()
        else:
            super().keyPressEvent(event)
