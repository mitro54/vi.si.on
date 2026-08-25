# Ambient Desktop AI Overlay 🔮

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![PyQt6](https://img.shields.io/badge/GUI-PyQt6-green.svg)](https://riverbankcomputing.com/software/pyqt/)
[![Ollama](https://img.shields.io/badge/Local%20LLM-Ollama-purple.svg)](https://ollama.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

An ambient, non-intrusive, transparent desktop AI assistant for **Windows**, **Linux** (Ubuntu / WSL2 / Wayland / X11), and **macOS**. 

It listens for global hotkeys, performs real-time screen analysis to determine the least-cluttered desktop region, dynamically calculates contrast/typography parameters across mixed-DPI monitors, and streams responses from local LLMs (via [Ollama](https://ollama.com)) or cloud providers (via [LiteLLM](https://github.com/BerriAI/litellm)).

---

## 🌟 Key Features

### ⚡ Dual Interaction Modes & Hotkeys
- **`Alt + 1` — Quick One-Off Query**:
  - Ephemeral, low-latency answer box.
  - Automatically routes to your lightweight fast model (`num_ctx_quick: 8192`, `keep_alive_quick: 3m`).
- **`Alt + 2` — Active Conversation / Session Picker**:
  - Resumes your active persistent conversation.
  - Hold `Alt + 2` and use `↑` / `↓` arrow keys to browse and select past conversation sessions in an Alt-Tab style switcher.
  - Routes to your deep reasoning model (`num_ctx_conversation: 16384` / `65536`, `keep_alive_conversation: 10m`).
- **`Alt + Shift + 2` — New Conversation**: Starts a fresh, clean memorized conversation thread.
- **`Esc` — Instant Dismissal**: Smoothly fades out the overlay at any time.

---

### 🧠 Adaptive Dual-Model Routing & Hot Model Detection
- **Independent Model Assignment**: Use a lightweight, blazing-fast model (e.g., `qwen2.5-coder:14b` or `llama3.2:latest`) for 1-second quick questions, and a heavy reasoning model (e.g., `qwen3.8:27b` or `claude-3-5-sonnet`) for multi-turn conversations.
- **`🔥 [Hot in Memory]` Auto-Detection**: Automatically detects models already resident in GPU VRAM (`client.ps()`) to eliminate cold-start loading delays.
- **Smart Memory Eviction**: Automatically sets `keep_alive: 0` on application exit to cleanly unload model weights and free GPU VRAM immediately.

---

### 📜 Global Mouse-Wheel Scroll & Auto-Reading Pause
- **Zero-Click Hover Scrolling**: When an answer appears, rolling your scroll wheel **anywhere** immediately rolls the text up and down without needing to click or focus the window.
- **Reading Pause**: Any scroll movement instantly pauses the auto-close countdown (displaying **`"Paused"`**) so you can read long answers at your own leisure. Moving away smoothly resumes the countdown.

---

### 👁️ Computer Vision Spatial Engine & Mixed-DPI Scaling
- **Clutter Minimization (Canny Edge Convolutions + 2D Integral Images)**: Scans your screen in $O(1)$ box density convolutions to find the cleanest, least-cluttered desktop space (empty wallpaper or blank margins) so the overlay never covers your active work.
- **4K + 1080p Mixed-DPI Multi-Monitor Precision**: Synchronizes hardware screen capture bounds with Qt logical desktop coordinates (`QScreen.devicePixelRatio()`). Works seamlessly across 4K @ 150%/200% scaling and 1080p @ 100% secondary monitors.

---

### 🎨 Ambient Adaptive Contrast (Prompt Box & Answer Box)
- **W3C Relative Luminance Inversion**: Pre-analyzes background pixels directly behind both the **Prompt Input Box** and the **Answer Overlay**:
  - **Over White / Light Screens** (light web pages, PDFs, light themes): Renders a **frosted white glass backing** with **crisp dark slate text (`#0F172A`)**.
  - **Over Dark Screens** (dark IDEs, terminals, dark wallpapers): Renders a **dark obsidian glass backing** with **bright white text (`#F8FAFC`)**.

---

### 📝 Rich Real-Time Markdown Streaming
- Formats streaming tokens on the fly with syntax-styled code blocks, blockquotes, bold/italic, headers, and bullet lists.
- **Configurable Minimum Font Floor**: Enforces a strict minimum readable font size (e.g., `13pt` / `14pt`) so long answers stay sharp and comfortable to read.

---

### 🔄 Follow-Up Auto-Promotion
- If you ask a follow-up query (`Alt + 1`) while looking at an answer or within the configured grace period after it closes, the query is **automatically promoted** into a persistent saved conversation with expanded memory.

---

### 🌐 Augmented Tools & Local RAG
- **SearXNG Private Web Search**: Performs privacy-first web searches via tool calls to retrieve up-to-date information.
- **ChromaDB Local Knowledge Base**: Automatically watches and indexes any folder on your machine for vector search retrieval-augmented generation (RAG).

---

## 🚀 Installation & Setup

### Prerequisites
- Python 3.10+ (Python 3.11, 3.12, and 3.13 fully supported)
- [`uv`](https://docs.astral.sh/uv/) (Ultra-fast Python package and project manager)
- [Ollama](https://ollama.com/) running locally (`ollama serve`) OR API keys for Cloud providers (OpenAI, Anthropic, Gemini, Groq).

---

### 1. Clone & Install Dependencies

```bash
git clone https://github.com/mitro54/vi.si.on.git
cd vi.si.on

# Install and synchronize virtual environment dependencies with uv
uv sync --all-groups
```

> **Note for Multi-OS / WSL2 Users**: Virtual environments are OS-specific. If you share this folder between Windows (PowerShell) and WSL2/Linux, recreate the `.venv` when switching environments (`rm -rf .venv && uv sync`).

---

## 💻 Running the Application

### Running on Windows (PowerShell / Windows Terminal / CMD)
```powershell
# Launch the vi.si.on background assistant
python -m uv run vi.si.on
```

### Running on Linux / WSL2 (Ubuntu / X11 / Wayland)
```bash
uv run vi.si.on
```

### Launch Interactive Setup Wizard
To open the graphical configuration wizard at any time:
```powershell
python -m uv run vi.si.on --wizard
```

### Running the Test Suite
```powershell
python -m uv run pytest
```

---

## ⌨️ Hotkeys Reference

| Hotkey | Action | Behavior |
|---|---|---|
| **`Alt + 1`** | **Quick Chat** | Ephemeral query; uses fast model (`num_ctx_quick: 8192`, `keep_alive: 3m`). Auto-promotes on follow-up. |
| **`Alt + 2`** | **Conversation / Picker** | Resumes active session. Hold and use `↑`/`↓` to switch conversations. |
| **`Alt + Shift + 2`** | **New Conversation** | Starts a fresh persistent conversation session. |
| **`Esc`** | **Dismiss** | Instantly fades out active modal or overlay window. |
| **Scroll Wheel** | **Scroll Text** | Works anywhere over the screen; automatically pauses auto-close countdown. |

---

## ⚙️ Configuration (`config.json`)

All settings can be configured via the **Setup Wizard** (`--wizard`) or directly edited in [`config.json`](config.json):

```json
{
  "hotkeys": {
    "quick_chat": "<alt>+1",
    "conversation": "<alt>+2",
    "new_conversation": "<alt>+<shift>+2",
    "dismiss": "<esc>"
  },
  "provider": {
    "type": "ollama",
    "model_quick": "qwen2.5-coder:14b",
    "model_conversation": "qwen3.8:27b",
    "ollama_host": "http://127.0.0.1:11434",
    "litellm_model_quick": "gpt-4o-mini",
    "litellm_model_conversation": "gpt-4o",
    "api_keys": {},
    "num_ctx_quick": 8192,
    "num_ctx_conversation": 16384,
    "request_timeout_seconds": 120,
    "keep_alive_quick": "3m",
    "keep_alive_conversation": "10m"
  },
  "overlay": {
    "min_width": 400,
    "min_height": 280,
    "max_width": 620,
    "max_height": 520,
    "auto_close": "timer",
    "auto_close_seconds": 15,
    "screen_target": "same_screen",
    "prompt_placement": "center",
    "answer_placement": "clearest_area",
    "prefer_alternate_monitor": false
  },
  "conversation": {
    "promotion_timeout_seconds": 15,
    "persist_to_disk": true
  },
  "typography": {
    "font_base_size": 15,
    "font_min_size": 13,
    "downscale_threshold": 350,
    "downscale_rate": 200
  },
  "web_search": {
    "enabled": false,
    "searxng_url": "http://localhost:8888",
    "max_results": 5
  },
  "knowledge_base": {
    "enabled": false,
    "watch_directory": null,
    "persist_directory": null,
    "top_k": 3
  }
}
```

---

## 🐳 Optional: Local SearXNG Web Search

To enable private web search without third-party tracking, launch the bundled SearXNG container:

```bash
docker compose -f docker-compose.searxng.yml up -d
```
Then enable web search in the Setup Wizard or set `"enabled": true` under `"web_search"` in `config.json`.

---

## 🏗️ Multi-Agent Architecture

```
[User Trigger / Hotkey (Alt+1 / Alt+2 / Alt+Shift+2)]
│
▼
┌──────────────────┐
│ Orchestrator     │ ◄── Coordinates state machine & input hooks
└────────┬─────────┘
         │
         ├────────────────────────────────────────┐
         ▼                                        ▼
┌──────────────────┐                     ┌───────────────────────────┐
│ Spatial & Visual │                     │ Inference Worker          │
│ Analyzer Agent   │                     │ (Ollama / LiteLLM Bridge) │
└────────┬─────────┘                     └────────┬──────────────────┘
         │ (TargetRect, ContrastScheme,           │ (Streaming Tokens,
         │  DPI Scale Factor)                     │  SearXNG / ChromaDB Tools)
         ▼                                        ▼
┌───────────────────────────────────────────────────────────┐
│ Dynamic UI / Renderer Agent (PyQt6 Hardware-Accelerated)  │
└───────────────────────────────────────────────────────────┘
```

See [AGENTS.md](AGENTS.md) for agent specifications and [SYSTEM_SPEC.md](SYSTEM_SPEC.md) for algorithmic and mathematical specifications.

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).
