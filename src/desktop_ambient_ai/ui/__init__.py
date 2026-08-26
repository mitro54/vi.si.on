"""
UI components package (InputModal, OverlayView, ConversationPicker, SetupWizard, SystemTray).
"""

from .conversation_picker import ConversationPicker
from .input_modal import InputModal
from .math_renderer import MathParser, render_markdown_with_math
from .overlay_view import OverlayView
from .setup_wizard import SetupWizard
from .styles import (
    generate_input_modal_qss,
    generate_overlay_qss,
    generate_picker_qss,
    generate_wizard_qss,
)
from .tray import SystemTrayManager

__all__ = [
    "ConversationPicker",
    "InputModal",
    "MathParser",
    "OverlayView",
    "SetupWizard",
    "SystemTrayManager",
    "generate_input_modal_qss",
    "generate_overlay_qss",
    "generate_picker_qss",
    "generate_wizard_qss",
    "render_markdown_with_math",
]

