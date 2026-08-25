"""
Unit tests for Multimodal Region Snipping (Alt+3) and dynamic vision model detection.
"""

from unittest.mock import MagicMock, patch

from PyQt6.QtCore import QRect
from PyQt6.QtWidgets import QApplication

from desktop_ambient_ai.config import AppConfig, ProviderConfig
from desktop_ambient_ai.llm.litellm_client import LiteLLMWorker
from desktop_ambient_ai.llm.ollama_client import OllamaWorker
from desktop_ambient_ai.ui.input_modal import InputModal
from desktop_ambient_ai.ui.snip_overlay import ScreenSnipper


def test_screen_snipper_instantiation():
    app = QApplication.instance() or QApplication([])
    snipper = ScreenSnipper()
    assert snipper is not None
    assert snipper.cursor().shape() is not None


def test_input_modal_image_attachment():
    app = QApplication.instance() or QApplication([])
    modal = InputModal()
    modal.show()

    assert modal.get_attached_image() is None
    assert len(modal.get_attached_images()) == 0
    assert not modal.img_chip.isVisible()

    # Attach first dummy base64 png
    dummy_b64_1 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
    modal.attach_image_snip(dummy_b64_1, 400, 300, is_vision_capable=True)

    assert modal.get_attached_image() == dummy_b64_1
    assert len(modal.get_attached_images()) == 1
    assert modal.img_chip.isVisible()
    assert "400×300" in modal.img_chip.text()

    # Attach second image
    dummy_b64_2 = "second_image_base64"
    modal.attach_image_snip(dummy_b64_2, 640, 480, is_vision_capable=True)

    assert len(modal.get_attached_images()) == 2
    assert modal.get_attached_images()[0] == dummy_b64_1
    assert modal.get_attached_images()[1] == dummy_b64_2
    assert "2 Regions Attached" in modal.img_chip.text()

    # Detach images
    modal.detach_image()
    assert modal.get_attached_image() is None
    assert len(modal.get_attached_images()) == 0
    assert not modal.img_chip.isVisible()
    modal.hide()


def test_ollama_dynamic_vision_capability_detection():
    # Mock vision capable model
    mock_vision_info = MagicMock()
    mock_vision_info.capabilities = ["completion", "vision"]
    mock_vision_info.details.families = ["qwen2vl", "clip"]

    # Mock non-vision text model
    mock_text_info = MagicMock()
    mock_text_info.capabilities = ["completion", "tools"]
    mock_text_info.details.families = ["qwen2"]

    with patch("ollama.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        mock_client.show.side_effect = lambda m: mock_vision_info if "vision" in m else mock_text_info

        assert OllamaWorker.is_model_vision_capable("http://127.0.0.1:11434", "llama3.2-vision:latest") is True
        assert OllamaWorker.is_model_vision_capable("http://127.0.0.1:11434", "qwen2.5-coder:14b") is False


def test_litellm_vision_capability_detection():
    cfg = AppConfig(provider=ProviderConfig(type="litellm", litellm_model="gpt-4o"))
    worker = LiteLLMWorker(cfg.provider)

    assert worker.is_vision_capable("gpt-4o") is True
    assert worker.is_vision_capable("claude-3-5-sonnet") is True
    assert worker.is_vision_capable("gemini-1.5-flash") is True
