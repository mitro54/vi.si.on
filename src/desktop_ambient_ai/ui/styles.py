"""
Dynamic QSS stylesheet generator for glassmorphism, adaptive contrast, and UI components.
"""

from __future__ import annotations

from ..vision.spatial_finder import ThemeConfig


def generate_overlay_qss(theme: ThemeConfig, font_size: int, is_fallback: bool = False) -> str:
    """Generates dynamic stylesheet for the ambient response overlay."""
    backdrop_blur = "backdrop-filter: blur(16px);" if is_fallback else ""
    return f"""
    QWidget#OverlayRoot {{
        background-color: {theme.backing_tint};
        border: 1px solid {theme.border_color};
        border-radius: 16px;
        {backdrop_blur}
    }}

    QTextEdit#ContentDisplay {{
        background: transparent;
        color: {theme.text_color};
        font-family: 'Segoe UI', 'Inter', -apple-system, BlinkMacSystemFont, 'Roboto', sans-serif;
        font-size: {font_size}px;
        line-height: 1.45;
        border: none;
        selection-background-color: {theme.accent_color};
        selection-color: #FFFFFF;
    }}

    QTextEdit#ContentDisplay pre, QTextEdit#ContentDisplay code {{
        font-family: 'Cascadia Code', 'Fira Code', 'Consolas', 'Courier New', monospace;
        font-size: {max(10, font_size - 1)}px;
        background-color: {'rgba(30, 41, 59, 0.75)' if theme.is_dark_background else 'rgba(241, 245, 249, 0.85)'};
        color: {'#38BDF8' if theme.is_dark_background else '#0284C7'};
        border-radius: 4px;
        padding: 3px 5px;
    }}

    QTextEdit#ContentDisplay blockquote {{
        border-left: 3px solid {theme.accent_color};
        padding-left: 8px;
        color: {'rgba(203, 213, 225, 0.9)' if theme.is_dark_background else 'rgba(71, 85, 105, 0.9)'};
    }}

    QScrollBar:vertical {{
        background: transparent;
        width: 6px;
        margin: 0px;
    }}

    QScrollBar::handle:vertical {{
        background: rgba(148, 163, 184, 0.35);
        min-height: 24px;
        border-radius: 3px;
    }}

    QScrollBar::handle:vertical:hover {{
        background: {theme.accent_color};
    }}

    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0px;
    }}

    QScrollBar:horizontal {{
        height: 0px;
        background: transparent;
    }}

    QScrollBar::handle:horizontal {{
        height: 0px;
        background: transparent;
    }}

    QLabel#HeaderBadge {{
        background-color: rgba(56, 189, 248, 0.15);
        color: {theme.accent_color};
        font-weight: 600;
        font-size: 11px;
        padding: 3px 8px;
        border-radius: 6px;
        border: 1px solid rgba(56, 189, 248, 0.3);
    }}

    QLabel#TimerLabel {{
        color: rgba(148, 163, 184, 0.85);
        font-size: 11px;
        font-weight: 500;
    }}

    QPushButton#DismissBtn {{
        background: transparent;
        color: rgba(148, 163, 184, 0.7);
        border: none;
        font-size: 13px;
        font-weight: bold;
        border-radius: 10px;
        padding: 2px 6px;
    }}

    QPushButton#DismissBtn:hover {{
        background: rgba(239, 68, 68, 0.2);
        color: #EF4444;
    }}
    """


def generate_input_modal_qss(theme: Optional[ThemeConfig] = None) -> str:
    """Generates stylesheet for the floating input prompt adapting dynamically to background luminance."""
    if theme and not theme.is_dark_background:
        # Light background (e.g. white browser, light PDF) -> Dark slate text with frosted glass backing
        return """
        QWidget#InputModalRoot {
            background-color: rgba(255, 255, 255, 0.94);
            border: 1px solid rgba(15, 23, 42, 0.18);
            border-radius: 14px;
        }

        QLineEdit#PromptInput {
            background: transparent;
            color: #0F172A;
            font-family: 'Segoe UI', 'Inter', -apple-system, BlinkMacSystemFont, 'Roboto', sans-serif;
            font-size: 15px;
            border: none;
            padding: 6px 10px;
            selection-background-color: #0284C7;
            selection-color: #FFFFFF;
        }

        QLabel#ModeBadge {
            background-color: rgba(2, 132, 199, 0.12);
            color: #0284C7;
            font-size: 11px;
            font-weight: 600;
            padding: 4px 8px;
            border-radius: 6px;
            border: 1px solid rgba(2, 132, 199, 0.28);
        }

        QLabel#HintLabel {
            color: #64748B;
            font-size: 11px;
            font-weight: 500;
        }
        """
    else:
        # Dark background -> Bright white text with dark frosted glass backing
        return """
        QWidget#InputModalRoot {
            background-color: rgba(15, 23, 42, 0.90);
            border: 1px solid rgba(56, 189, 248, 0.35);
            border-radius: 14px;
        }

        QLineEdit#PromptInput {
            background: transparent;
            color: #F8FAFC;
            font-family: 'Segoe UI', 'Inter', -apple-system, BlinkMacSystemFont, 'Roboto', sans-serif;
            font-size: 15px;
            border: none;
            padding: 6px 10px;
            selection-background-color: #0284C7;
            selection-color: #FFFFFF;
        }

        QLabel#ModeBadge {
            background-color: rgba(14, 165, 233, 0.2);
            color: #38BDF8;
            font-size: 11px;
            font-weight: 600;
            padding: 4px 8px;
            border-radius: 6px;
            border: 1px solid rgba(14, 165, 233, 0.35);
        }

        QLabel#HintLabel {
            color: #94A3B8;
            font-size: 11px;
            font-weight: 500;
        }
        """


def generate_picker_qss() -> str:
    """Generates stylesheet for the Alt-Tab style conversation selector."""
    return """
    QWidget#PickerRoot {
        background-color: rgba(15, 23, 42, 0.95);
        border: 1px solid rgba(56, 189, 248, 0.4);
        border-radius: 16px;
    }

    QLabel#PickerTitle {
        color: #F8FAFC;
        font-size: 14px;
        font-weight: 700;
        padding-bottom: 4px;
    }

    QListWidget#ConversationList {
        background: transparent;
        border: none;
        outline: none;
    }

    QListWidget#ConversationList::item {
        background: rgba(30, 41, 59, 0.6);
        border: 1px solid rgba(148, 163, 184, 0.15);
        border-radius: 10px;
        padding: 10px;
        margin-bottom: 6px;
        color: #F8FAFC;
    }

    QListWidget#ConversationList::item:selected {
        background: rgba(2, 132, 199, 0.35);
        border: 1px solid #38BDF8;
    }

    QListWidget#ConversationList::item:hover {
        background: rgba(51, 65, 85, 0.8);
    }
    """


def generate_wizard_qss() -> str:
    """Generates modern dark-themed stylesheet for the Setup Wizard."""
    return """
    QWizard {
        background-color: #0B1120;
        color: #F8FAFC;
        font-family: 'Segoe UI', 'Inter', -apple-system, BlinkMacSystemFont, 'Roboto', sans-serif;
    }

    QWizardPage {
        background-color: #0B1120;
        color: #F8FAFC;
    }

    QWidget {
        background-color: transparent;
        color: #F8FAFC;
        font-family: 'Segoe UI', 'Inter', -apple-system, BlinkMacSystemFont, 'Roboto', sans-serif;
    }

    QLabel {
        color: #E2E8F0;
        font-size: 13px;
        background: transparent;
    }

    QLabel#WizardHeader, QLabel[wizard_title="true"] {
        color: #38BDF8;
        font-size: 17px;
        font-weight: 700;
        padding-bottom: 4px;
    }

    QLabel#WizardSubHeader {
        color: #94A3B8;
        font-size: 13px;
        margin-bottom: 10px;
    }

    QGroupBox {
        background-color: rgba(30, 41, 59, 0.45);
        border: 1px solid rgba(56, 189, 248, 0.25);
        border-radius: 12px;
        margin-top: 14px;
        padding: 14px;
        padding-top: 20px;
        font-weight: 600;
        color: #38BDF8;
    }

    QGroupBox::title {
        subcontrol-origin: margin;
        subcontrol-position: top left;
        left: 14px;
        padding: 0 8px;
        background-color: #0B1120;
        color: #38BDF8;
        border-radius: 4px;
    }

    QLineEdit, QComboBox, QSpinBox {
        background-color: #1E293B;
        border: 1px solid rgba(148, 163, 184, 0.25);
        border-radius: 8px;
        color: #F8FAFC;
        padding: 7px 12px;
        font-size: 13px;
        min-height: 22px;
    }

    QLineEdit:focus, QComboBox:focus, QSpinBox:focus {
        border: 1px solid #38BDF8;
        background-color: #1E293B;
    }

    QComboBox::drop-down {
        border: none;
        width: 24px;
    }

    QComboBox QAbstractItemView {
        background-color: #1E293B;
        border: 1px solid #38BDF8;
        color: #F8FAFC;
        selection-background-color: #0284C7;
        selection-color: #FFFFFF;
        padding: 4px;
        border-radius: 6px;
    }

    QListWidget {
        background-color: #1E293B;
        border: 1px solid rgba(148, 163, 184, 0.25);
        border-radius: 8px;
        color: #F8FAFC;
        padding: 4px;
    }

    QListWidget::item {
        padding: 8px;
        border-radius: 6px;
        color: #F8FAFC;
    }

    QListWidget::item:selected {
        background-color: #0284C7;
        color: #FFFFFF;
    }

    QPushButton {
        background-color: #0284C7;
        color: #FFFFFF;
        border: 1px solid rgba(56, 189, 248, 0.4);
        border-radius: 8px;
        padding: 8px 18px;
        font-weight: 600;
        font-size: 13px;
        min-width: 70px;
    }

    QPushButton:hover {
        background-color: #0369A1;
        border: 1px solid #38BDF8;
    }

    QPushButton:pressed {
        background-color: #075985;
    }

    QPushButton:disabled {
        background-color: rgba(51, 65, 85, 0.5);
        color: #64748B;
        border: 1px solid transparent;
    }

    QPushButton#SecondaryBtn {
        background-color: #334155;
        color: #F8FAFC;
        border: 1px solid rgba(148, 163, 184, 0.2);
    }

    QPushButton#SecondaryBtn:hover {
        background-color: #475569;
        border: 1px solid rgba(148, 163, 184, 0.4);
    }

    QSlider::groove:horizontal {
        border: 1px solid #334155;
        height: 6px;
        background: #1E293B;
        border-radius: 3px;
    }

    QSlider::sub-page:horizontal {
        background: #38BDF8;
        border-radius: 3px;
    }

    QSlider::handle:horizontal {
        background: #FFFFFF;
        border: 2px solid #38BDF8;
        width: 16px;
        margin-top: -6px;
        margin-bottom: -6px;
        border-radius: 8px;
    }

    QCheckBox, QRadioButton {
        color: #F8FAFC;
        font-size: 13px;
        spacing: 8px;
        background: transparent;
    }

    QCheckBox::indicator, QRadioButton::indicator {
        width: 16px;
        height: 16px;
        border: 1px solid #64748B;
        border-radius: 4px;
        background-color: #1E293B;
    }

    QRadioButton::indicator {
        border-radius: 8px;
    }

    QCheckBox::indicator:checked, QRadioButton::indicator:checked {
        background-color: #0284C7;
        border: 1px solid #38BDF8;
    }

    QDialogButtonBox {
        background-color: #0B1120;
        border-top: 1px solid rgba(56, 189, 248, 0.2);
        padding-top: 14px;
        margin-top: 10px;
    }

    QScrollBar:vertical {
        border: none;
        background: #0B1120;
        width: 8px;
        margin: 0;
    }

    QScrollBar::handle:vertical {
        background: #334155;
        min-height: 20px;
        border-radius: 4px;
    }

    QScrollBar::handle:vertical:hover {
        background: #38BDF8;
    }

    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
        height: 0px;
    }
    """
