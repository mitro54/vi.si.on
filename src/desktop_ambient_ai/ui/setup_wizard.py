"""
Interactive first-launch Setup Wizard for models, hotkeys, dimensions, typography, and tools.
"""

from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
    QWizard,
    QWizardPage,
)

from ..config import AppConfig, save_config
from ..llm.ollama_client import OllamaWorker
from .styles import generate_wizard_qss


def _wrap_in_scroll(inner_widget: QWidget, parent: QWidget) -> QScrollArea:
    """Wraps an inner widget in a borderless, transparent QScrollArea."""
    scroll = QScrollArea(parent)
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    scroll.setStyleSheet("background: transparent; border: none;")
    scroll.setWidget(inner_widget)
    return scroll


class WelcomePage(QWizardPage):
    def __init__(self, config: AppConfig, parent=None):
        super().__init__(parent)
        self.config = config
        self.setTitle("Welcome to vi.si.on")
        self.setSubTitle("Choose your preferred AI backend provider to get started.")

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(10, 10, 10, 10)

        container = QWidget(self)
        layout = QVBoxLayout(container)
        layout.setSpacing(16)
        layout.setContentsMargins(10, 10, 10, 10)

        info = QLabel(
            "<b>vi.si.on</b> is an ambient, transparent AI assistant. It stays quiet in your system tray, "
            "analyzes desktop screen clutter in real time, and streams helpful responses without interrupting your active workflow.",
            container,
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: #E2E8F0; font-size: 13px; line-height: 1.4;")
        layout.addWidget(info)

        group = QGroupBox("Inference Engine Selection", container)
        g_layout = QVBoxLayout(group)
        g_layout.setSpacing(12)

        self.radio_ollama = QRadioButton("Local Ollama (Private, Free, Fully Offline)", group)
        self.radio_cloud = QRadioButton("Cloud Provider (OpenAI, Anthropic, Google Gemini, Groq via LiteLLM)", group)

        if self.config.provider.type == "litellm":
            self.radio_cloud.setChecked(True)
        else:
            self.radio_ollama.setChecked(True)

        g_layout.addWidget(self.radio_ollama)
        g_layout.addWidget(self.radio_cloud)
        layout.addWidget(group)

        layout.addStretch()
        outer_layout.addWidget(_wrap_in_scroll(container, self))

    def nextId(self) -> int:
        return 1 if self.radio_ollama.isChecked() else 2


class OllamaModelPage(QWizardPage):
    def __init__(self, config: AppConfig, parent=None):
        super().__init__(parent)
        self.config = config
        self.setTitle("Local Ollama Model Selection")
        self.setSubTitle("Select distinct models for quick queries and deeper conversations.")

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(10, 10, 10, 10)

        container = QWidget(self)
        layout = QVBoxLayout(container)
        layout.setSpacing(14)
        layout.setContentsMargins(10, 10, 10, 10)

        # Host and scan bar
        host_layout = QHBoxLayout()
        host_layout.addWidget(QLabel("Ollama Host:", container))
        self.host_input = QLineEdit(self.config.provider.ollama_host, container)
        host_layout.addWidget(self.host_input)

        self.refresh_btn = QPushButton("Scan Models", container)
        self.refresh_btn.setObjectName("SecondaryBtn")
        self.refresh_btn.clicked.connect(self._refresh_models)
        host_layout.addWidget(self.refresh_btn)
        layout.addLayout(host_layout)

        # Quick Chat Model
        layout.addWidget(QLabel("⚡ Quick Chat Model (Low-latency / Instant Questions):", container))
        self.quick_model_combo = QComboBox(container)
        layout.addWidget(self.quick_model_combo)

        # Conversation Model
        layout.addWidget(QLabel("🗨 Conversation Model (Deep Reasoning / Multi-Turn Memory):", container))
        self.conv_model_combo = QComboBox(container)
        layout.addWidget(self.conv_model_combo)

        self.status_label = QLabel("", container)
        layout.addWidget(self.status_label)

        # Context, Keep-Alive and Timeout Group
        adv_group = QGroupBox("Context Window & GPU VRAM Management", container)
        adv_layout = QVBoxLayout(adv_group)
        adv_layout.setSpacing(10)

        q_ctx_box = QHBoxLayout()
        q_ctx_box.addWidget(QLabel("Quick Chat Context:", adv_group))
        self.quick_ctx_combo = QComboBox(adv_group)
        self.quick_ctx_combo.addItems(["2048", "4096", "8192 (Recommended)", "16384", "32768"])
        q_cur = str(self.config.provider.num_ctx_quick)
        q_idx = self.quick_ctx_combo.findText(q_cur, Qt.MatchFlag.MatchStartsWith)
        self.quick_ctx_combo.setCurrentIndex(q_idx if q_idx >= 0 else 2)
        q_ctx_box.addWidget(self.quick_ctx_combo)
        adv_layout.addLayout(q_ctx_box)

        c_ctx_box = QHBoxLayout()
        c_ctx_box.addWidget(QLabel("Conversation Context:", adv_group))
        self.conv_ctx_combo = QComboBox(adv_group)
        self.conv_ctx_combo.addItems(["8192", "16384 (Recommended)", "32768", "65536", "131072"])
        c_cur = str(self.config.provider.num_ctx_conversation)
        c_idx = self.conv_ctx_combo.findText(c_cur, Qt.MatchFlag.MatchStartsWith)
        self.conv_ctx_combo.setCurrentIndex(c_idx if c_idx >= 0 else 1)
        c_ctx_box.addWidget(self.conv_ctx_combo)
        adv_layout.addLayout(c_ctx_box)

        # Keep Alive inputs
        ka_box = QHBoxLayout()
        ka_box.addWidget(QLabel("Quick Keep-Alive in VRAM:", adv_group))
        self.quick_ka_input = QLineEdit(self.config.provider.keep_alive_quick or "3m", adv_group)
        self.quick_ka_input.setPlaceholderText("e.g. 3m, 5m, 10m")
        ka_box.addWidget(self.quick_ka_input)

        ka_box.addWidget(QLabel("Conv Keep-Alive:", adv_group))
        self.conv_ka_input = QLineEdit(self.config.provider.keep_alive_conversation or "10m", adv_group)
        self.conv_ka_input.setPlaceholderText("e.g. 10m, 30m")
        ka_box.addWidget(self.conv_ka_input)
        adv_layout.addLayout(ka_box)

        t_box = QHBoxLayout()
        t_box.addWidget(QLabel("Generation Timeout (s):", adv_group))
        self.timeout_spin = QSpinBox(adv_group)
        self.timeout_spin.setRange(10, 600)
        self.timeout_spin.setValue(self.config.provider.request_timeout_seconds)
        t_box.addWidget(self.timeout_spin)
        adv_layout.addLayout(t_box)

        layout.addWidget(adv_group)
        layout.addStretch()
        outer_layout.addWidget(_wrap_in_scroll(container, self))

    def initializePage(self) -> None:
        self._refresh_models()

    def _refresh_models(self) -> None:
        self.quick_model_combo.clear()
        self.conv_model_combo.clear()
        host = self.host_input.text().strip() or "http://127.0.0.1:11434"
        models = OllamaWorker.list_models(host)
        running_models = OllamaWorker.get_running_models(host)

        if models:
            hot_count = len(running_models)
            msg = f"Found {len(models)} installed models."
            if hot_count > 0:
                msg += f" ({hot_count} currently active in VRAM 🔥)"
            self.status_label.setText(msg)
            self.status_label.setStyleSheet("color: #4ADE80;")

            q_selected_idx = 0
            c_selected_idx = 0

            cur_quick = self.config.provider.model_quick or self.config.provider.model or ""
            cur_conv = self.config.provider.model_conversation or self.config.provider.model or ""

            for idx, m in enumerate(models):
                name = m.get("name", "")
                size = m.get("size", "")
                param = m.get("param_size", "")
                is_hot = any(rm == name or rm in name or name in rm for rm in running_models)
                hot_badge = "🔥 [Hot in Memory] " if is_hot else ""
                extra = f" ({param}, {size})" if param or size else ""
                label = f"{hot_badge}{name}{extra}"

                self.quick_model_combo.addItem(label, name)
                self.conv_model_combo.addItem(label, name)

                if cur_quick and cur_quick in name:
                    q_selected_idx = idx
                if cur_conv and cur_conv in name:
                    c_selected_idx = idx

            self.quick_model_combo.setCurrentIndex(q_selected_idx)
            self.conv_model_combo.setCurrentIndex(c_selected_idx)
        else:
            self.status_label.setText("No Ollama models found. Ensure Ollama is running ('ollama serve').")
            self.status_label.setStyleSheet("color: #F87171;")
            self.quick_model_combo.addItem("llama3.2:latest (Default Fallback)", "llama3.2:latest")
            self.conv_model_combo.addItem("llama3.2:latest (Default Fallback)", "llama3.2:latest")

    def nextId(self) -> int:
        return 3


class CloudModelPage(QWizardPage):
    def __init__(self, config: AppConfig, parent=None):
        super().__init__(parent)
        self.config = config
        self.setTitle("Cloud Provider Settings")
        self.setSubTitle("Configure API keys and model names for cloud inference.")

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(10, 10, 10, 10)

        container = QWidget(self)
        layout = QVBoxLayout(container)
        layout.setSpacing(14)
        layout.setContentsMargins(10, 10, 10, 10)

        layout.addWidget(QLabel("Provider Template:", container))
        self.provider_combo = QComboBox(container)
        self.provider_combo.addItems([
            "OpenAI (gpt-4o-mini / gpt-4o)",
            "Anthropic (claude-3-5-haiku / claude-3-5-sonnet)",
            "Google Gemini (gemini-1.5-flash / gemini-1.5-pro)",
            "Groq (llama-3.1-8b / llama-3.1-70b)",
            "Custom LiteLLM Models",
        ])
        self.provider_combo.currentIndexChanged.connect(self._on_template_change)
        layout.addWidget(self.provider_combo)

        layout.addWidget(QLabel("⚡ Quick Chat Model Identifier (Fast):", container))
        self.quick_model_input = QLineEdit(
            self.config.provider.litellm_model_quick or self.config.provider.litellm_model or "gpt-4o-mini",
            container,
        )
        layout.addWidget(self.quick_model_input)

        layout.addWidget(QLabel("🗨 Conversation Model Identifier (Deep Reasoning):", container))
        self.conv_model_input = QLineEdit(
            self.config.provider.litellm_model_conversation or self.config.provider.litellm_model or "gpt-4o",
            container,
        )
        layout.addWidget(self.conv_model_input)

        layout.addWidget(QLabel("API Key:", container))
        self.key_input = QLineEdit(container)
        self.key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.key_input.setPlaceholderText("sk-...")
        layout.addWidget(self.key_input)

        timeout_box = QHBoxLayout()
        timeout_box.addWidget(QLabel("Generation Timeout (s):", container))
        self.cloud_timeout_spin = QSpinBox(container)
        self.cloud_timeout_spin.setRange(10, 600)
        self.cloud_timeout_spin.setValue(self.config.provider.request_timeout_seconds)
        timeout_box.addWidget(self.cloud_timeout_spin)
        layout.addLayout(timeout_box)

        layout.addStretch()
        outer_layout.addWidget(_wrap_in_scroll(container, self))

    def _on_template_change(self, index: int) -> None:
        templates = [
            ("gpt-4o-mini", "gpt-4o"),
            ("claude-3-5-haiku-20241022", "claude-3-5-sonnet-20241022"),
            ("gemini/gemini-1.5-flash", "gemini/gemini-1.5-pro"),
            ("groq/llama-3.1-8b-instant", "groq/llama-3.1-70b-versatile"),
            ("gpt-4o-mini", "gpt-4o"),
        ]
        if index < len(templates):
            q_m, c_m = templates[index]
            self.quick_model_input.setText(q_m)
            self.conv_model_input.setText(c_m)

    def nextId(self) -> int:
        return 3


class DisplayPlacementPage(QWizardPage):
    def __init__(self, config: AppConfig, parent=None):
        super().__init__(parent)
        self.config = config
        self.setTitle("Display, Window Dimensions & Smart Positioning")
        self.setSubTitle("Customize minimum bounding dimensions, screen placement, and clutter avoidance.")

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(10, 10, 10, 10)

        container = QWidget(self)
        layout = QVBoxLayout(container)
        layout.setSpacing(14)
        layout.setContentsMargins(10, 10, 10, 10)

        # Dimension Sliders Group
        dim_group = QGroupBox("Window Dimensions (Bounding Box Limits)", container)
        d_layout = QVBoxLayout(dim_group)
        d_layout.setSpacing(10)

        # Min Width slider
        w_box = QHBoxLayout()
        w_box.addWidget(QLabel("Min Width:", dim_group))
        self.w_slider = QSlider(Qt.Orientation.Horizontal, dim_group)
        self.w_slider.setRange(250, 800)
        self.w_slider.setValue(self.config.overlay.min_width)
        self.w_label = QLabel(f"{self.w_slider.value()} px", dim_group)
        self.w_slider.valueChanged.connect(self._update_preview)
        w_box.addWidget(self.w_slider)
        w_box.addWidget(self.w_label)
        d_layout.addLayout(w_box)

        # Min Height slider
        h_box = QHBoxLayout()
        h_box.addWidget(QLabel("Min Height:", dim_group))
        self.h_slider = QSlider(Qt.Orientation.Horizontal, dim_group)
        self.h_slider.setRange(180, 600)
        self.h_slider.setValue(self.config.overlay.min_height)
        self.h_label = QLabel(f"{self.h_slider.value()} px", dim_group)
        self.h_slider.valueChanged.connect(self._update_preview)
        h_box.addWidget(self.h_slider)
        h_box.addWidget(self.h_label)
        d_layout.addLayout(h_box)

        # Max limits
        max_box = QHBoxLayout()
        max_box.addWidget(QLabel("Max Width (px):", dim_group))
        self.max_w_spin = QSpinBox(dim_group)
        self.max_w_spin.setRange(400, 2560)
        self.max_w_spin.setValue(self.config.overlay.max_width)
        max_box.addWidget(self.max_w_spin)

        max_box.addWidget(QLabel("Max Height (px):", dim_group))
        self.max_h_spin = QSpinBox(dim_group)
        self.max_h_spin.setRange(300, 1600)
        self.max_h_spin.setValue(self.config.overlay.max_height)
        max_box.addWidget(self.max_h_spin)
        d_layout.addLayout(max_box)

        layout.addWidget(dim_group)

        # Live Scale Preview Box with generous dedicated height
        preview_group = QGroupBox("Proportional Window Scale Preview", container)
        preview_group.setMinimumHeight(130)
        p_layout = QVBoxLayout(preview_group)
        p_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.preview_frame = QFrame(preview_group)
        self.preview_frame.setObjectName("PreviewFrame")
        self.preview_frame.setStyleSheet(
            "background: rgba(14, 165, 233, 0.18); border: 2px dashed #38BDF8; border-radius: 8px;"
        )
        self.preview_label = QLabel("", self.preview_frame)
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setStyleSheet("color: #38BDF8; font-weight: 700; font-size: 12px;")
        p_layout.addWidget(self.preview_frame, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(preview_group)

        # Placement Configuration Group
        pos_group = QGroupBox("Screen Positioning & Clutter Avoidance", container)
        pos_layout = QVBoxLayout(pos_group)
        pos_layout.setSpacing(10)

        # Screen Target
        s_box = QHBoxLayout()
        s_box.addWidget(QLabel("Target Monitor:", pos_group))
        self.screen_target_combo = QComboBox(pos_group)
        self.screen_target_combo.addItems([
            "Same screen (Active monitor where you are working)",
            "Alternate screen (Secondary display if multi-monitor)",
        ])
        if self.config.overlay.screen_target == "alternate_screen" or self.config.overlay.prefer_alternate_monitor:
            self.screen_target_combo.setCurrentIndex(1)
        else:
            self.screen_target_combo.setCurrentIndex(0)
        s_box.addWidget(self.screen_target_combo)
        pos_layout.addLayout(s_box)

        # Prompt Placement
        p_box = QHBoxLayout()
        p_box.addWidget(QLabel("Prompt Box Location:", pos_group))
        self.prompt_pos_combo = QComboBox(pos_group)
        self.prompt_pos_combo.addItems([
            "Center of screen (Recommended)",
            "Near mouse cursor",
            "Clearest screen area (Automatic AI scan)",
        ])
        if self.config.overlay.prompt_placement == "cursor":
            self.prompt_pos_combo.setCurrentIndex(1)
        elif self.config.overlay.prompt_placement == "clearest_area":
            self.prompt_pos_combo.setCurrentIndex(2)
        else:
            self.prompt_pos_combo.setCurrentIndex(0)
        p_box.addWidget(self.prompt_pos_combo)
        pos_layout.addLayout(p_box)

        # Clutter Avoidance Toggle & Fallback
        c_box = QHBoxLayout()
        self.clutter_avoid_cb = QCheckBox("Enable Smart Clutter Avoidance", pos_group)
        self.clutter_avoid_cb.setToolTip("Automatically shifts prompt modal away from dense background code/text.")
        self.clutter_avoid_cb.setChecked(getattr(self.config.overlay, "prompt_clutter_avoidance", True))
        c_box.addWidget(self.clutter_avoid_cb)

        c_box.addWidget(QLabel("Fallback:", pos_group))
        self.fallback_combo = QComboBox(pos_group)
        self.fallback_combo.addItems([
            "Check mouse cursor, then scan",
            "Direct spatial scan (Skip mouse)",
            "Check screen center, then scan",
            "None (Strictly lock position)",
        ])
        fb_val = getattr(self.config.overlay, "prompt_fallback", "cursor")
        if fb_val == "spatial":
            self.fallback_combo.setCurrentIndex(1)
        elif fb_val == "center":
            self.fallback_combo.setCurrentIndex(2)
        elif fb_val == "none":
            self.fallback_combo.setCurrentIndex(3)
        else:
            self.fallback_combo.setCurrentIndex(0)
        c_box.addWidget(self.fallback_combo)
        pos_layout.addLayout(c_box)

        # Answer Placement
        a_box = QHBoxLayout()
        a_box.addWidget(QLabel("Answer Box Location:", pos_group))
        self.answer_pos_combo = QComboBox(pos_group)
        self.answer_pos_combo.addItems([
            "Clearest screen space (AI clutter minimization)",
            "Center of screen",
            "Near mouse cursor",
        ])
        if self.config.overlay.answer_placement == "center":
            self.answer_pos_combo.setCurrentIndex(1)
        elif self.config.overlay.answer_placement == "cursor":
            self.answer_pos_combo.setCurrentIndex(2)
        else:
            self.answer_pos_combo.setCurrentIndex(0)
        a_box.addWidget(self.answer_pos_combo)
        pos_layout.addLayout(a_box)

        # Auto Close Mode & Timer
        auto_box = QHBoxLayout()
        auto_box.addWidget(QLabel("Auto-Close Behavior:", pos_group))
        self.auto_combo = QComboBox(pos_group)
        self.auto_combo.addItems(["Timer (Countdown after generation)", "Immediate (Flash read)", "Manual (Esc only)"])
        self.auto_combo.setCurrentIndex(
            0 if self.config.overlay.auto_close == "timer" else (1 if self.config.overlay.auto_close == "immediate" else 2)
        )
        auto_box.addWidget(self.auto_combo)

        auto_box.addWidget(QLabel("Timer (s):", pos_group))
        self.timer_spin = QSpinBox(pos_group)
        self.timer_spin.setRange(5, 120)
        self.timer_spin.setValue(self.config.overlay.auto_close_seconds)
        auto_box.addWidget(self.timer_spin)
        pos_layout.addLayout(auto_box)

        layout.addWidget(pos_group)
        layout.addStretch()

        outer_layout.addWidget(_wrap_in_scroll(container, self))
        self._update_preview()

    def _update_preview(self) -> None:
        w_val = self.w_slider.value()
        h_val = self.h_slider.value()
        self.w_label.setText(f"{w_val} px")
        self.h_label.setText(f"{h_val} px")

        # Proportional scale in max 240x80 canvas
        scale = min(240 / w_val, 80 / h_val)
        pw = max(60, int(w_val * scale))
        ph = max(35, int(h_val * scale))
        self.preview_frame.setFixedSize(pw, ph)
        self.preview_label.setGeometry(0, 0, pw, ph)
        self.preview_label.setText(f"{w_val} × {h_val}")

    def nextId(self) -> int:
        return 4


class TypographyMemoryPage(QWizardPage):
    def __init__(self, config: AppConfig, parent=None):
        super().__init__(parent)
        self.config = config
        self.setTitle("Typography & Conversation Memory")
        self.setSubTitle("Configure adaptive text scaling, readability limits, and session memory.")

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(10, 10, 10, 10)

        container = QWidget(self)
        layout = QVBoxLayout(container)
        layout.setSpacing(14)
        layout.setContentsMargins(10, 10, 10, 10)

        # Typography Card
        typo_group = QGroupBox("Adaptive Font Sizing & Readability Floor", container)
        typo_layout = QVBoxLayout(typo_group)
        typo_layout.setSpacing(10)

        font_box = QHBoxLayout()
        font_box.addWidget(QLabel("Base Font Size (pt):", typo_group))
        self.font_base_spin = QSpinBox(typo_group)
        self.font_base_spin.setRange(12, 26)
        self.font_base_spin.setValue(self.config.typography.font_base_size)
        font_box.addWidget(self.font_base_spin)

        font_box.addWidget(QLabel("Minimum Readable Floor (pt):", typo_group))
        self.font_min_spin = QSpinBox(typo_group)
        self.font_min_spin.setRange(10, 22)
        self.font_min_spin.setValue(self.config.typography.font_min_size)
        font_box.addWidget(self.font_min_spin)
        typo_layout.addLayout(font_box)

        scale_box = QHBoxLayout()
        scale_box.addWidget(QLabel("Downscale Trigger Threshold (chars):", typo_group))
        self.downscale_thresh_spin = QSpinBox(typo_group)
        self.downscale_thresh_spin.setRange(100, 2000)
        self.downscale_thresh_spin.setValue(self.config.typography.downscale_threshold)
        scale_box.addWidget(self.downscale_thresh_spin)

        scale_box.addWidget(QLabel("Downscale Rate (chars/pt):", typo_group))
        self.downscale_rate_spin = QSpinBox(typo_group)
        self.downscale_rate_spin.setRange(50, 1000)
        self.downscale_rate_spin.setValue(self.config.typography.downscale_rate)
        scale_box.addWidget(self.downscale_rate_spin)
        typo_layout.addLayout(scale_box)

        layout.addWidget(typo_group)

        # Conversation Memory Card
        mem_group = QGroupBox("Conversation Memory & Auto-Promotion", container)
        mem_layout = QVBoxLayout(mem_group)
        mem_layout.setSpacing(10)

        promo_box = QHBoxLayout()
        promo_box.addWidget(QLabel("Follow-up Auto-Promotion Window (sec):", mem_group))
        self.promo_spin = QSpinBox(mem_group)
        self.promo_spin.setRange(5, 180)
        self.promo_spin.setValue(self.config.conversation.promotion_timeout_seconds)
        promo_box.addWidget(self.promo_spin)
        mem_layout.addLayout(promo_box)

        self.persist_cb = QCheckBox("Persist Conversation Sessions to Disk", mem_group)
        self.persist_cb.setToolTip("Saves multi-turn conversation context across reboots and restarts.")
        self.persist_cb.setChecked(self.config.conversation.persist_to_disk)
        mem_layout.addWidget(self.persist_cb)

        layout.addWidget(mem_group)
        layout.addStretch()

        outer_layout.addWidget(_wrap_in_scroll(container, self))

    def nextId(self) -> int:
        return 5


class HotkeysPage(QWizardPage):
    def __init__(self, config: AppConfig, parent=None):
        super().__init__(parent)
        self.config = config
        self.setTitle("Global Hotkey Shortcuts")
        self.setSubTitle("Customize system-wide keyboard triggers for prompt and screen capture.")

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(10, 10, 10, 10)

        container = QWidget(self)
        layout = QVBoxLayout(container)
        layout.setSpacing(14)
        layout.setContentsMargins(10, 10, 10, 10)

        group = QGroupBox("Keyboard Shortcuts Configuration", container)
        g_layout = QVBoxLayout(group)
        g_layout.setSpacing(10)

        # Quick Chat
        q_box = QHBoxLayout()
        q_box.addWidget(QLabel("⚡ Quick One-Off Query:", group))
        self.hk_quick_input = QLineEdit(self.config.hotkeys.quick_chat, group)
        q_box.addWidget(self.hk_quick_input)
        g_layout.addLayout(q_box)

        # Active Conversation
        c_box = QHBoxLayout()
        c_box.addWidget(QLabel("🗨 Active Conversation / Switcher:", group))
        self.hk_conv_input = QLineEdit(self.config.hotkeys.conversation, group)
        c_box.addWidget(self.hk_conv_input)
        g_layout.addLayout(c_box)

        # New Conversation
        nc_box = QHBoxLayout()
        nc_box.addWidget(QLabel("➕ Fresh Conversation Thread:", group))
        self.hk_new_input = QLineEdit(self.config.hotkeys.new_conversation, group)
        nc_box.addWidget(self.hk_new_input)
        g_layout.addLayout(nc_box)

        # OCR / Snip
        s_box = QHBoxLayout()
        s_box.addWidget(QLabel("✂ Multi-Region Screen Snipper:", group))
        self.hk_snip_input = QLineEdit(self.config.hotkeys.ocr_selection, group)
        s_box.addWidget(self.hk_snip_input)
        g_layout.addLayout(s_box)

        # Dismiss
        d_box = QHBoxLayout()
        d_box.addWidget(QLabel("✕ Dismiss Active Modal / Overlay:", group))
        self.hk_dismiss_input = QLineEdit(self.config.hotkeys.dismiss, group)
        d_box.addWidget(self.hk_dismiss_input)
        g_layout.addLayout(d_box)

        layout.addWidget(group)
        layout.addStretch()

        outer_layout.addWidget(_wrap_in_scroll(container, self))

    def nextId(self) -> int:
        return 6


class ToolsFeaturesPage(QWizardPage):
    def __init__(self, config: AppConfig, parent=None):
        super().__init__(parent)
        self.config = config
        self.setTitle("Tools, Web Search & Knowledge Base")
        self.setSubTitle("Configure external search augmentation and document vector index.")

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(10, 10, 10, 10)

        container = QWidget(self)
        layout = QVBoxLayout(container)
        layout.setSpacing(14)
        layout.setContentsMargins(10, 10, 10, 10)

        # Web Search Group
        web_group = QGroupBox("SearXNG Private Web Search", container)
        w_layout = QVBoxLayout(web_group)
        w_layout.setSpacing(10)

        self.web_cb = QCheckBox("Enable Private Web Search Tool Calling", web_group)
        self.web_cb.setChecked(self.config.web_search.enabled)
        w_layout.addWidget(self.web_cb)

        web_box = QHBoxLayout()
        web_box.addWidget(QLabel("SearXNG URL:", web_group))
        self.searx_url_input = QLineEdit(self.config.web_search.searxng_url, web_group)
        web_box.addWidget(self.searx_url_input)

        web_box.addWidget(QLabel("Max Results:", web_group))
        self.searx_max_spin = QSpinBox(web_group)
        self.searx_max_spin.setRange(1, 20)
        self.searx_max_spin.setValue(self.config.web_search.max_results)
        web_box.addWidget(self.searx_max_spin)
        w_layout.addLayout(web_box)

        layout.addWidget(web_group)

        # Knowledge Base Group
        kb_group = QGroupBox("ChromaDB Document Knowledge Base (RAG)", container)
        kb_layout = QVBoxLayout(kb_group)
        kb_layout.setSpacing(10)

        self.kb_cb = QCheckBox("Enable Local Knowledge Base Auto-Ingestion", kb_group)
        self.kb_cb.setChecked(self.config.knowledge_base.enabled)
        kb_layout.addWidget(self.kb_cb)

        kb_box = QHBoxLayout()
        kb_box.addWidget(QLabel("Watch Folder Path:", kb_group))
        self.kb_dir_input = QLineEdit(self.config.knowledge_base.watch_directory or "", kb_group)
        self.kb_dir_input.setPlaceholderText("Select folder to automatically index documents...")
        kb_box.addWidget(self.kb_dir_input)

        self.browse_btn = QPushButton("Browse...", kb_group)
        self.browse_btn.setObjectName("SecondaryBtn")
        self.browse_btn.clicked.connect(self._browse_kb_dir)
        kb_box.addWidget(self.browse_btn)
        kb_layout.addLayout(kb_box)

        top_box = QHBoxLayout()
        top_box.addWidget(QLabel("Top Relevant Documents to Retrieve (Top K):", kb_group))
        self.kb_topk_spin = QSpinBox(kb_group)
        self.kb_topk_spin.setRange(1, 10)
        self.kb_topk_spin.setValue(self.config.knowledge_base.top_k)
        top_box.addWidget(self.kb_topk_spin)
        kb_layout.addLayout(top_box)

        layout.addWidget(kb_group)
        layout.addStretch()

        outer_layout.addWidget(_wrap_in_scroll(container, self))

    def _browse_kb_dir(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "Select Knowledge Base Folder")
        if directory:
            self.kb_dir_input.setText(directory)

    def nextId(self) -> int:
        return 7


class SummaryPage(QWizardPage):
    def __init__(self, config: AppConfig, parent=None):
        super().__init__(parent)
        self.config = config
        self.setTitle("Setup Complete")
        self.setSubTitle("Review your settings and click Finish to apply configuration.")

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(10, 10, 10, 10)

        container = QWidget(self)
        layout = QVBoxLayout(container)
        layout.setSpacing(14)
        layout.setContentsMargins(10, 10, 10, 10)

        self.summary_label = QLabel("", container)
        self.summary_label.setObjectName("SummaryLabel")
        self.summary_label.setWordWrap(True)
        layout.addWidget(self.summary_label)

        layout.addStretch()
        outer_layout.addWidget(_wrap_in_scroll(container, self))

    def initializePage(self) -> None:
        wizard: SetupWizard = self.wizard()
        w_page: WelcomePage = wizard.page(0)
        is_ollama = w_page.radio_ollama.isChecked()

        if is_ollama:
            o_page: OllamaModelPage = wizard.page(1)
            q_m = o_page.quick_model_combo.currentText()
            c_m = o_page.conv_model_combo.currentText()
            provider_desc = f"Local Ollama (Quick: {q_m} | Conversation: {c_m})"
        else:
            c_page: CloudModelPage = wizard.page(2)
            provider_desc = f"Cloud LiteLLM (Quick: {c_page.quick_model_input.text()} | Conv: {c_page.conv_model_input.text()})"

        d_page: DisplayPlacementPage = wizard.page(3)
        min_w = d_page.w_slider.value()
        min_h = d_page.h_slider.value()
        prompt_pos = d_page.prompt_pos_combo.currentText()
        clutter_on = "Enabled" if d_page.clutter_avoid_cb.isChecked() else "Disabled"

        t_page: ToolsFeaturesPage = wizard.page(6)
        web_on = "Enabled" if t_page.web_cb.isChecked() else "Disabled"
        kb_on = f"Enabled ({t_page.kb_dir_input.text()})" if t_page.kb_cb.isChecked() else "Disabled"

        text = (
            f"<div style='line-height: 1.6; font-size: 13px; color: #E2E8F0;'>"
            f"<b>Inference Backend:</b> {provider_desc}<br/>"
            f"<b>Minimum Overlay Size:</b> {min_w} × {min_h} px<br/>"
            f"<b>Prompt Location:</b> {prompt_pos} (Clutter Avoidance: {clutter_on})<br/>"
            f"<b>Web Search:</b> {web_on}<br/>"
            f"<b>Knowledge Base:</b> {kb_on}<br/><br/>"
            f"<span style='color: #38BDF8;'>Click <b>Finish</b> to save and start using vi.si.on. If you close this window before clicking Finish, your configuration remains unchanged.</span>"
            f"</div>"
        )
        self.summary_label.setText(text)
        self.summary_label.setTextFormat(Qt.TextFormat.RichText)

    def nextId(self) -> int:
        return -1


class SetupWizard(QWizard):
    """Main Setup Wizard dialog with complete configuration coverage."""

    def __init__(self, config: AppConfig, parent=None):
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("vi.si.on — Setup Wizard")

        # Force ClassicStyle to disable Windows Aero white background injection
        self.setWizardStyle(QWizard.WizardStyle.ClassicStyle)

        # Force full dark mode palette
        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window, QColor("#0B1120"))
        palette.setColor(QPalette.ColorRole.WindowText, QColor("#F8FAFC"))
        palette.setColor(QPalette.ColorRole.Base, QColor("#1E293B"))
        palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#0F172A"))
        palette.setColor(QPalette.ColorRole.ToolTipBase, QColor("#1E293B"))
        palette.setColor(QPalette.ColorRole.ToolTipText, QColor("#F8FAFC"))
        palette.setColor(QPalette.ColorRole.Text, QColor("#F8FAFC"))
        palette.setColor(QPalette.ColorRole.Button, QColor("#1E293B"))
        palette.setColor(QPalette.ColorRole.ButtonText, QColor("#F8FAFC"))
        palette.setColor(QPalette.ColorRole.BrightText, QColor("#38BDF8"))
        palette.setColor(QPalette.ColorRole.Highlight, QColor("#0284C7"))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#FFFFFF"))
        self.setPalette(palette)

        self.setStyleSheet(generate_wizard_qss())
        self.resize(840, 720)
        self.setMinimumSize(780, 640)

        self.setPage(0, WelcomePage(config, self))
        self.setPage(1, OllamaModelPage(config, self))
        self.setPage(2, CloudModelPage(config, self))
        self.setPage(3, DisplayPlacementPage(config, self))
        self.setPage(4, TypographyMemoryPage(config, self))
        self.setPage(5, HotkeysPage(config, self))
        self.setPage(6, ToolsFeaturesPage(config, self))
        self.setPage(7, SummaryPage(config, self))

    def accept(self) -> None:
        """Applies wizard selections to config and saves to disk ONLY when Finish is clicked."""
        w_page: WelcomePage = self.page(0)
        if w_page.radio_ollama.isChecked():
            self.config.provider.type = "ollama"
            o_page: OllamaModelPage = self.page(1)
            self.config.provider.ollama_host = o_page.host_input.text().strip() or "http://127.0.0.1:11434"

            q_model = o_page.quick_model_combo.currentData() or o_page.quick_model_combo.currentText()
            c_model = o_page.conv_model_combo.currentData() or o_page.conv_model_combo.currentText()
            self.config.provider.model_quick = str(q_model)
            self.config.provider.model_conversation = str(c_model)
            self.config.provider.model = str(q_model)

            # Parse context sizes from dropdowns
            q_ctx_text = o_page.quick_ctx_combo.currentText().split()[0]
            c_ctx_text = o_page.conv_ctx_combo.currentText().split()[0]
            try:
                self.config.provider.num_ctx_quick = int(q_ctx_text)
            except Exception:
                self.config.provider.num_ctx_quick = 8192

            try:
                self.config.provider.num_ctx_conversation = int(c_ctx_text)
            except Exception:
                self.config.provider.num_ctx_conversation = 16384

            self.config.provider.num_ctx = self.config.provider.num_ctx_quick
            self.config.provider.keep_alive_quick = o_page.quick_ka_input.text().strip() or "3m"
            self.config.provider.keep_alive_conversation = o_page.conv_ka_input.text().strip() or "10m"
            self.config.provider.request_timeout_seconds = o_page.timeout_spin.value()
        else:
            self.config.provider.type = "litellm"
            c_page: CloudModelPage = self.page(2)
            self.config.provider.litellm_model_quick = c_page.quick_model_input.text().strip() or "gpt-4o-mini"
            self.config.provider.litellm_model_conversation = c_page.conv_model_input.text().strip() or "gpt-4o"
            self.config.provider.litellm_model = self.config.provider.litellm_model_quick

            api_key = c_page.key_input.text().strip()
            if api_key:
                if "claude" in self.config.provider.litellm_model:
                    self.config.provider.api_keys["ANTHROPIC_API_KEY"] = api_key
                elif "gemini" in self.config.provider.litellm_model:
                    self.config.provider.api_keys["GEMINI_API_KEY"] = api_key
                elif "groq" in self.config.provider.litellm_model:
                    self.config.provider.api_keys["GROQ_API_KEY"] = api_key
                else:
                    self.config.provider.api_keys["OPENAI_API_KEY"] = api_key
            self.config.provider.request_timeout_seconds = c_page.cloud_timeout_spin.value()

        # Display & Placement Page
        d_page: DisplayPlacementPage = self.page(3)
        self.config.overlay.min_width = d_page.w_slider.value()
        self.config.overlay.min_height = d_page.h_slider.value()
        self.config.overlay.max_width = d_page.max_w_spin.value()
        self.config.overlay.max_height = d_page.max_h_spin.value()

        auto_idx = d_page.auto_combo.currentIndex()
        self.config.overlay.auto_close = "timer" if auto_idx == 0 else ("immediate" if auto_idx == 1 else "manual")
        self.config.overlay.auto_close_seconds = d_page.timer_spin.value()

        self.config.overlay.screen_target = "alternate_screen" if d_page.screen_target_combo.currentIndex() == 1 else "same_screen"
        self.config.overlay.prefer_alternate_monitor = (self.config.overlay.screen_target == "alternate_screen")

        p_idx = d_page.prompt_pos_combo.currentIndex()
        self.config.overlay.prompt_placement = (
            "center" if p_idx == 0 else ("cursor" if p_idx == 1 else "clearest_area")
        )
        self.config.overlay.prompt_clutter_avoidance = d_page.clutter_avoid_cb.isChecked()

        fb_idx = d_page.fallback_combo.currentIndex()
        self.config.overlay.prompt_fallback = (
            "cursor" if fb_idx == 0 else ("spatial" if fb_idx == 1 else ("center" if fb_idx == 2 else "none"))
        )

        ans_idx = d_page.answer_pos_combo.currentIndex()
        if ans_idx == 1:
            self.config.overlay.answer_placement = "center"
        elif ans_idx == 2:
            self.config.overlay.answer_placement = "cursor"
        else:
            self.config.overlay.answer_placement = "clearest_area"

        # Typography & Memory Page
        tm_page: TypographyMemoryPage = self.page(4)
        self.config.typography.font_base_size = tm_page.font_base_spin.value()
        self.config.typography.font_min_size = tm_page.font_min_spin.value()
        self.config.typography.downscale_threshold = tm_page.downscale_thresh_spin.value()
        self.config.typography.downscale_rate = tm_page.downscale_rate_spin.value()

        self.config.conversation.promotion_timeout_seconds = tm_page.promo_spin.value()
        self.config.conversation.persist_to_disk = tm_page.persist_cb.isChecked()

        # Hotkeys Page
        hk_page: HotkeysPage = self.page(5)
        self.config.hotkeys.quick_chat = hk_page.hk_quick_input.text().strip() or "<alt>+1"
        self.config.hotkeys.conversation = hk_page.hk_conv_input.text().strip() or "<alt>+2"
        self.config.hotkeys.new_conversation = hk_page.hk_new_input.text().strip() or "<alt>+<shift>+2"
        self.config.hotkeys.ocr_selection = hk_page.hk_snip_input.text().strip() or "<alt>+3"
        self.config.hotkeys.dismiss = hk_page.hk_dismiss_input.text().strip() or "<esc>"

        # Tools & Features Page
        t_page: ToolsFeaturesPage = self.page(6)
        self.config.web_search.enabled = t_page.web_cb.isChecked()
        self.config.web_search.searxng_url = t_page.searx_url_input.text().strip() or "http://localhost:8888"
        self.config.web_search.max_results = t_page.searx_max_spin.value()

        self.config.knowledge_base.enabled = t_page.kb_cb.isChecked()
        self.config.knowledge_base.watch_directory = t_page.kb_dir_input.text().strip() or None
        self.config.knowledge_base.top_k = t_page.kb_topk_spin.value()

        self.config.setup_complete = True
        save_config(self.config)

        super().accept()
