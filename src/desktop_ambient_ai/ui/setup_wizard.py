"""
Interactive first-launch Setup Wizard for models, hotkeys, dimensions, and tools.
"""

from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QRadioButton,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWizard,
    QWizardPage,
)

from ..config import AppConfig, save_config
from ..llm.ollama_client import OllamaWorker
from .styles import generate_wizard_qss


class WelcomePage(QWizardPage):
    def __init__(self, config: AppConfig, parent=None):
        super().__init__(parent)
        self.config = config
        self.setTitle("Welcome to vi.si.on Overlay")
        self.setSubTitle("Choose your preferred AI backend provider to get started.")

        layout = QVBoxLayout(self)
        layout.setSpacing(14)

        info = QLabel(
            "vi.si.on runs silently in the background, analyzing screen clutter "
            "and streaming helpful answers without interrupting your active workflow.",
            self,
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        group = QGroupBox("Inference Engine", self)
        g_layout = QVBoxLayout(group)

        self.radio_ollama = QRadioButton("Local Ollama (Private, Free, Offline)", group)
        self.radio_cloud = QRadioButton("Cloud Provider (OpenAI, Anthropic, Gemini, Mistral via LiteLLM)", group)

        if self.config.provider.type == "litellm":
            self.radio_cloud.setChecked(True)
        else:
            self.radio_ollama.setChecked(True)

        g_layout.addWidget(self.radio_ollama)
        g_layout.addWidget(self.radio_cloud)
        layout.addWidget(group)

        layout.addStretch()

    def nextId(self) -> int:
        return 1 if self.radio_ollama.isChecked() else 2


class OllamaModelPage(QWizardPage):
    def __init__(self, config: AppConfig, parent=None):
        super().__init__(parent)
        self.config = config
        self.setTitle("Local Ollama Model Selection")
        self.setSubTitle("Select distinct models for quick queries and deeper conversations.")

        layout = QVBoxLayout(self)

        host_layout = QHBoxLayout()
        host_layout.addWidget(QLabel("Ollama Host:", self))
        self.host_input = QLineEdit(self.config.provider.ollama_host, self)
        host_layout.addWidget(self.host_input)

        self.refresh_btn = QPushButton("Scan Models", self)
        self.refresh_btn.setObjectName("SecondaryBtn")
        self.refresh_btn.clicked.connect(self._refresh_models)
        host_layout.addWidget(self.refresh_btn)
        layout.addLayout(host_layout)

        # Quick Chat Model selection
        layout.addWidget(QLabel("⚡ Quick Chat Model (Fast / Low Latency):", self))
        self.quick_model_combo = QComboBox(self)
        layout.addWidget(self.quick_model_combo)

        # Conversation Model selection
        layout.addWidget(QLabel("🗨 Conversation Model (Deep / Memory):", self))
        self.conv_model_combo = QComboBox(self)
        layout.addWidget(self.conv_model_combo)

        self.status_label = QLabel("", self)
        layout.addWidget(self.status_label)

        # Advanced Ollama Context & Timeout settings
        adv_group = QGroupBox("Context Window & Execution Limits", self)
        adv_layout = QVBoxLayout(adv_group)

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

        t_box = QHBoxLayout()
        t_box.addWidget(QLabel("Generation Timeout (s):", adv_group))
        self.timeout_spin = QSpinBox(adv_group)
        self.timeout_spin.setRange(10, 600)
        self.timeout_spin.setValue(self.config.provider.request_timeout_seconds)
        t_box.addWidget(self.timeout_spin)
        adv_layout.addLayout(t_box)

        layout.addWidget(adv_group)

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

        layout = QVBoxLayout(self)

        form_layout = QVBoxLayout()
        form_layout.addWidget(QLabel("Provider Template:", self))
        self.provider_combo = QComboBox(self)
        self.provider_combo.addItems(["OpenAI (gpt-4o-mini / gpt-4o)", "Anthropic (claude-3-5-haiku / claude-3-5-sonnet)", "Google Gemini (gemini-1.5-flash / gemini-1.5-pro)", "Groq (llama-3.1-8b / llama-3.1-70b)", "Custom LiteLLM Models"])
        self.provider_combo.currentIndexChanged.connect(self._on_template_change)
        form_layout.addWidget(self.provider_combo)

        form_layout.addWidget(QLabel("⚡ Quick Chat Model Identifier (Fast):", self))
        self.quick_model_input = QLineEdit(self.config.provider.litellm_model_quick or self.config.provider.litellm_model or "gpt-4o-mini", self)
        form_layout.addWidget(self.quick_model_input)

        form_layout.addWidget(QLabel("🗨 Conversation Model Identifier (Deep Reasoning):", self))
        self.conv_model_input = QLineEdit(self.config.provider.litellm_model_conversation or self.config.provider.litellm_model or "gpt-4o", self)
        form_layout.addWidget(self.conv_model_input)

        form_layout.addWidget(QLabel("API Key:", self))
        self.key_input = QLineEdit(self)
        self.key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.key_input.setPlaceholderText("sk-...")
        form_layout.addWidget(self.key_input)

        timeout_box = QHBoxLayout()
        timeout_box.addWidget(QLabel("Generation Timeout (s):", self))
        self.cloud_timeout_spin = QSpinBox(self)
        self.cloud_timeout_spin.setRange(10, 600)
        self.cloud_timeout_spin.setValue(self.config.provider.request_timeout_seconds)
        timeout_box.addWidget(self.cloud_timeout_spin)
        form_layout.addLayout(timeout_box)

        layout.addLayout(form_layout)
        layout.addStretch()

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


class DisplaySettingsPage(QWizardPage):
    def __init__(self, config: AppConfig, parent=None):
        super().__init__(parent)
        self.config = config
        self.setTitle("Display & Minimum Dimensions")
        self.setSubTitle("Define the minimum acceptable window bounds and auto-dismiss behavior.")

        layout = QVBoxLayout(self)

        # Min Width slider
        w_box = QHBoxLayout()
        w_box.addWidget(QLabel("Min Width (px):", self))
        self.w_slider = QSlider(Qt.Orientation.Horizontal, self)
        self.w_slider.setRange(250, 800)
        self.w_slider.setValue(self.config.overlay.min_width)
        self.w_label = QLabel(f"{self.w_slider.value()} px", self)
        self.w_slider.valueChanged.connect(self._update_preview)
        w_box.addWidget(self.w_slider)
        w_box.addWidget(self.w_label)
        layout.addLayout(w_box)

        # Min Height slider
        h_box = QHBoxLayout()
        h_box.addWidget(QLabel("Min Height (px):", self))
        self.h_slider = QSlider(Qt.Orientation.Horizontal, self)
        self.h_slider.setRange(180, 600)
        self.h_slider.setValue(self.config.overlay.min_height)
        self.h_label = QLabel(f"{self.h_slider.value()} px", self)
        self.h_slider.valueChanged.connect(self._update_preview)
        h_box.addWidget(self.h_slider)
        h_box.addWidget(self.h_label)
        layout.addLayout(h_box)

        # Live Scale Preview Box
        preview_group = QGroupBox("Proportional Dimension Preview", self)
        p_layout = QVBoxLayout(preview_group)
        self.preview_frame = QFrame(self)
        self.preview_frame.setObjectName("PreviewFrame")
        self.preview_frame.setStyleSheet(
            "background: rgba(14, 165, 233, 0.15); border: 2px dashed #38BDF8; border-radius: 8px;"
        )
        self.preview_label = QLabel("", self.preview_frame)
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setStyleSheet("color: #38BDF8; font-weight: 600;")
        p_layout.addWidget(self.preview_frame, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(preview_group)

        # Auto Close Mode & Timer
        auto_box = QHBoxLayout()
        auto_box.addWidget(QLabel("Auto-Close Behavior:", self))
        self.auto_combo = QComboBox(self)
        self.auto_combo.addItems(["Timer (Countdown after generation)", "Immediate (Flash read)", "Manual (Esc only)"])
        self.auto_combo.setCurrentIndex(0 if self.config.overlay.auto_close == "timer" else (1 if self.config.overlay.auto_close == "immediate" else 2))
        auto_box.addWidget(self.auto_combo)

        auto_box.addWidget(QLabel("Timer (sec):", self))
        self.timer_spin = QSpinBox(self)
        self.timer_spin.setRange(5, 120)
        self.timer_spin.setValue(self.config.overlay.auto_close_seconds)
        auto_box.addWidget(self.timer_spin)
        layout.addLayout(auto_box)

        # Placement Configuration Group
        pos_group = QGroupBox("Screen & Positioning Options", self)
        pos_layout = QVBoxLayout(pos_group)

        # Screen Target
        s_box = QHBoxLayout()
        s_box.addWidget(QLabel("Target Monitor:", pos_group))
        self.screen_target_combo = QComboBox(pos_group)
        self.screen_target_combo.addItems([
            "Same screen (Active monitor where you are working)",
            "Alternate screen (Secondary display if multi-monitor)"
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
            "Near mouse cursor",
            "Center of screen"
        ])
        self.prompt_pos_combo.setCurrentIndex(1 if self.config.overlay.prompt_placement == "center" else 0)
        p_box.addWidget(self.prompt_pos_combo)
        pos_layout.addLayout(p_box)

        # Answer Placement
        a_box = QHBoxLayout()
        a_box.addWidget(QLabel("Answer Box Location:", pos_group))
        self.answer_pos_combo = QComboBox(pos_group)
        self.answer_pos_combo.addItems([
            "Clearest screen space (AI clutter minimization)",
            "Center of screen",
            "Near mouse cursor"
        ])
        if self.config.overlay.answer_placement == "center":
            self.answer_pos_combo.setCurrentIndex(1)
        elif self.config.overlay.answer_placement == "cursor":
            self.answer_pos_combo.setCurrentIndex(2)
        else:
            self.answer_pos_combo.setCurrentIndex(0)
        a_box.addWidget(self.answer_pos_combo)
        pos_layout.addLayout(a_box)

        layout.addWidget(pos_group)

        # Typography & Font Readability Group
        typo_group = QGroupBox("Typography & Readability", self)
        typo_layout = QHBoxLayout(typo_group)

        typo_layout.addWidget(QLabel("Base Font Size (pt):", typo_group))
        self.font_base_spin = QSpinBox(typo_group)
        self.font_base_spin.setRange(12, 26)
        self.font_base_spin.setValue(self.config.typography.font_base_size)
        typo_layout.addWidget(self.font_base_spin)

        typo_layout.addWidget(QLabel("Minimum Readable Floor (pt):", typo_group))
        self.font_min_spin = QSpinBox(typo_group)
        self.font_min_spin.setRange(10, 22)
        self.font_min_spin.setValue(self.config.typography.font_min_size)
        typo_layout.addWidget(self.font_min_spin)

        layout.addWidget(typo_group)

        self._update_preview()

    def _update_preview(self) -> None:
        w_val = self.w_slider.value()
        h_val = self.h_slider.value()
        self.w_label.setText(f"{w_val} px")
        self.h_label.setText(f"{h_val} px")

        # Scale preview to max 220x110
        scale = min(220 / w_val, 110 / h_val)
        pw = int(w_val * scale)
        ph = int(h_val * scale)
        self.preview_frame.setFixedSize(pw, ph)
        self.preview_label.setGeometry(0, 0, pw, ph)
        self.preview_label.setText(f"{w_val} × {h_val}")

    def nextId(self) -> int:
        return 4


class ToolsFeaturesPage(QWizardPage):
    def __init__(self, config: AppConfig, parent=None):
        super().__init__(parent)
        self.config = config
        self.setTitle("Tools, Web Search & Knowledge Base")
        self.setSubTitle("Configure external augmentation tools.")

        layout = QVBoxLayout(self)

        # Web Search
        self.web_cb = QCheckBox("Enable SearXNG Private Web Search", self)
        self.web_cb.setChecked(self.config.web_search.enabled)
        layout.addWidget(self.web_cb)

        web_box = QHBoxLayout()
        web_box.addWidget(QLabel("SearXNG URL:", self))
        self.searx_url_input = QLineEdit(self.config.web_search.searxng_url, self)
        web_box.addWidget(self.searx_url_input)
        layout.addLayout(web_box)

        layout.addSpacing(12)

        # Knowledge Base
        self.kb_cb = QCheckBox("Enable ChromaDB Knowledge Base (Auto-Ingestion)", self)
        self.kb_cb.setChecked(self.config.knowledge_base.enabled)
        layout.addWidget(self.kb_cb)

        kb_box = QHBoxLayout()
        kb_box.addWidget(QLabel("Watch Folder Path:", self))
        self.kb_dir_input = QLineEdit(self.config.knowledge_base.watch_directory or "", self)
        self.kb_dir_input.setPlaceholderText("Select folder to automatically index documents...")
        kb_box.addWidget(self.kb_dir_input)

        self.browse_btn = QPushButton("Browse...", self)
        self.browse_btn.setObjectName("SecondaryBtn")
        self.browse_btn.clicked.connect(self._browse_kb_dir)
        kb_box.addWidget(self.browse_btn)
        layout.addLayout(kb_box)

        layout.addStretch()

    def _browse_kb_dir(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "Select Knowledge Base Folder")
        if directory:
            self.kb_dir_input.setText(directory)

    def nextId(self) -> int:
        return 5


class SummaryPage(QWizardPage):
    def __init__(self, config: AppConfig, parent=None):
        super().__init__(parent)
        self.config = config
        self.setTitle("Setup Complete")
        self.setSubTitle("Review your settings and click Finish to start vi.si.on.")

        layout = QVBoxLayout(self)

        self.summary_label = QLabel("", self)
        self.summary_label.setObjectName("SummaryLabel")
        self.summary_label.setWordWrap(True)
        layout.addWidget(self.summary_label)

        layout.addStretch()

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

        d_page: DisplaySettingsPage = wizard.page(3)
        min_w = d_page.w_slider.value()
        min_h = d_page.h_slider.value()

        t_page: ToolsFeaturesPage = wizard.page(4)
        web_on = "Enabled" if t_page.web_cb.isChecked() else "Disabled"
        kb_on = f"Enabled ({t_page.kb_dir_input.text()})" if t_page.kb_cb.isChecked() else "Disabled"

        text = (
            f"<b>Provider:</b> {provider_desc}<br/>"
            f"<b>Minimum Overlay Size:</b> {min_w} × {min_h} px<br/>"
            f"<b>Web Search:</b> {web_on}<br/>"
            f"<b>Knowledge Base:</b> {kb_on}<br/>"
        )
        self.summary_label.setText(text)
        self.summary_label.setTextFormat(Qt.TextFormat.RichText)

    def nextId(self) -> int:
        return -1


class SetupWizard(QWizard):
    """Main Setup Wizard dialog."""

    def __init__(self, config: AppConfig, parent=None):
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("vi.si.on — Setup Wizard")
        self.setStyleSheet(generate_wizard_qss())
        self.setFixedSize(640, 560)

        self.setPage(0, WelcomePage(config, self))
        self.setPage(1, OllamaModelPage(config, self))
        self.setPage(2, CloudModelPage(config, self))
        self.setPage(3, DisplaySettingsPage(config, self))
        self.setPage(4, ToolsFeaturesPage(config, self))
        self.setPage(5, SummaryPage(config, self))

    def accept(self) -> None:
        """Applies wizard selections to config and saves to disk."""
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
            self.config.provider.request_timeout_seconds = o_page.timeout_spin.value()
        else:
            self.config.provider.type = "litellm"
            c_page: CloudModelPage = self.page(2)
            self.config.provider.litellm_model_quick = c_page.quick_model_input.text().strip() or "gpt-4o-mini"
            self.config.provider.litellm_model_conversation = c_page.conv_model_input.text().strip() or "gpt-4o"
            self.config.provider.litellm_model = self.config.provider.litellm_model_quick

            api_key = c_page.key_input.text().strip()
            if api_key:
                # Key based on provider
                if "claude" in self.config.provider.litellm_model:
                    self.config.provider.api_keys["ANTHROPIC_API_KEY"] = api_key
                elif "gemini" in self.config.provider.litellm_model:
                    self.config.provider.api_keys["GEMINI_API_KEY"] = api_key
                elif "groq" in self.config.provider.litellm_model:
                    self.config.provider.api_keys["GROQ_API_KEY"] = api_key
                else:
                    self.config.provider.api_keys["OPENAI_API_KEY"] = api_key
            self.config.provider.request_timeout_seconds = c_page.cloud_timeout_spin.value()

        d_page: DisplaySettingsPage = self.page(3)
        self.config.overlay.min_width = d_page.w_slider.value()
        self.config.overlay.min_height = d_page.h_slider.value()
        auto_idx = d_page.auto_combo.currentIndex()
        self.config.overlay.auto_close = "timer" if auto_idx == 0 else ("immediate" if auto_idx == 1 else "manual")
        self.config.overlay.auto_close_seconds = d_page.timer_spin.value()

        # Placement configs
        self.config.overlay.screen_target = "alternate_screen" if d_page.screen_target_combo.currentIndex() == 1 else "same_screen"
        self.config.overlay.prefer_alternate_monitor = (self.config.overlay.screen_target == "alternate_screen")
        self.config.overlay.prompt_placement = "center" if d_page.prompt_pos_combo.currentIndex() == 1 else "cursor"

        ans_idx = d_page.answer_pos_combo.currentIndex()
        if ans_idx == 1:
            self.config.overlay.answer_placement = "center"
        elif ans_idx == 2:
            self.config.overlay.answer_placement = "cursor"
        else:
            self.config.overlay.answer_placement = "clearest_area"

        # Typography settings
        self.config.typography.font_base_size = d_page.font_base_spin.value()
        self.config.typography.font_min_size = d_page.font_min_spin.value()

        t_page: ToolsFeaturesPage = self.page(4)
        self.config.web_search.enabled = t_page.web_cb.isChecked()
        self.config.web_search.searxng_url = t_page.searx_url_input.text().strip() or "http://localhost:8888"
        self.config.knowledge_base.enabled = t_page.kb_cb.isChecked()
        self.config.knowledge_base.watch_directory = t_page.kb_dir_input.text().strip() or None

        self.config.setup_complete = True
        save_config(self.config)

        super().accept()
