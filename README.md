# vi.si.on Overlay

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![PyQt6](https://img.shields.io/badge/GUI-PyQt6-green.svg)](https://riverbankcomputing.com/software/pyqt/)
[![Ollama](https://img.shields.io/badge/Local%20LLM-Ollama-purple.svg)](https://ollama.com/)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)

An ambient, non-intrusive, transparent desktop AI assistant for **Windows**, **Linux** (Ubuntu / WSL2 / Wayland / X11), and **macOS**. Will eventually bring a version of this that adapts to br.ai.n.

It listens for global hotkeys, performs real-time screen analysis to determine the least-cluttered desktop region, dynamically calculates contrast/typography parameters across mixed-DPI monitors, and streams responses from local LLMs (via [Ollama](https://ollama.com)) or cloud providers (via [LiteLLM](https://github.com/BerriAI/litellm)).

---

## 🌟 Key Features

### ⚡ Dual Interaction Modes & Hotkeys
- **`Alt + 1` — Quick One-Off Query**:
  - Ephemeral, low-latency answer box.
  - Automatically routes to your lightweight fast model (`keep_alive_quick: 3m`).
- **`Alt + 2` — Active Conversation / Real-Time Switcher**:
  - Resumes your active persistent conversation.
  - **Hold or press `Alt + 2` repeatedly** (or use `↑` / `↓` arrow keys) to cycle through past conversation sessions in real time without any numbers being typed into your query.
  - Routes to your deep reasoning model (`keep_alive_conversation: 10m`).
- **`Alt + Shift + 2` — New Conversation**: Starts a fresh, clean memorized conversation thread.
- **`Alt + 3` — Multi-Region Screen Snipper**: Captures one or multiple screen regions for multimodal visual analysis.
- **`Esc` — Instant Dismissal**: Smoothly fades out active modals or overlay windows at any time.

---

### 🧠 Adaptive Dual-Model Routing & Hot Model Detection
- **Independent Model Assignment**: Use a lightweight, blazing-fast model for 1-second quick questions, and a heavy reasoning model for multi-turn conversations.
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
- **Same-Screen Conversation Locking**: Automatically remembers and stays locked to the exact monitor where the conversation started for all follow-up turns.

---

### 🎨 Ambient Adaptive Contrast (Prompt Box & Answer Box)
- **W3C Relative Luminance Inversion**: Pre-analyzes background pixels directly behind both the **Prompt Input Box** and the **Answer Overlay**:
  - **Over White / Light Screens** (light web pages, PDFs, light themes): Renders a **frosted white glass backing** with **crisp dark slate text (`#0F172A`)**.
  - **Over Dark Screens** (dark IDEs, terminals, dark wallpapers): Renders a **dark obsidian glass backing** with **bright white text (`#F8FAFC`)**.

---

### ✂️ Multimodal Multi-Screen Snipping & Dynamic Vision (`Alt + 3`)
- **Live Transparent Overlay (Zero Zoom Distortion)**: Displays a native transparent overlay with live cutout preview, maintaining 100% native pixel-perfect resolution on 4K and multi-monitor setups.
- **Multi-Screenshot Stacking**:
  - Press `Alt + 3` once to snip a region (`🖼 1 Region (640×480)`).
  - Press `Alt + 3` again to snip additional regions (`🖼 2 Regions Attached`, `🖼 3 Regions Attached`).
  - All attached screenshots are sent simultaneously in a single multimodal query.
- **Dynamic Model Capability Detection**:
  - Automatically inspects Ollama GGUF model capabilities (`capabilities: ['vision']`, tensor families) and LiteLLM endpoints without requiring static model lists.

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

#### Linux System Packages (PyQt6 & OpenCV GUI dependencies):
On Linux distributions, install the required graphics and X11/xcb libraries:
```bash
# Ubuntu / Debian / Pop!_OS / Linux Mint
sudo apt update && sudo apt install -y libgl1 libglib2.0-0 libxcb-cursor0 libxkbcommon-x11-0 libegl1 libx11-xcb1

# Arch Linux / Manjaro
sudo pacman -S --needed mesa libglvnd glib2 libxkbcommon-x11 xcb-util-cursor

# Fedora / RHEL
sudo dnf install -y mesa-libGL glib2 libxkbcommon-x11 xcb-util-cursor
```

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

# Or directly if uv is added to your PATH:
uv run vi.si.on
```

### Running on Linux (Ubuntu / Arch / Fedora / Wayland / X11)
```bash
uv run vi.si.on
```
*(On Linux Wayland sessions, `vi.si.on` automatically routes display rendering via `xcb;wayland` to ensure transparent hardware overlays and global shortcut capture.)*

### Launch Interactive Setup Wizard
To open the graphical configuration wizard at any time:
```bash
python -m uv run vi.si.on --wizard
```

### Running the Test Suite
```bash
python -m uv run pytest
```

---

## 🚀 Running on System Startup (Autostart)

### 1. One-Command Setup (Windows & Linux)
You can configure **vi.si.on** to automatically start in the background when you log in:

```bash
# On Windows (PowerShell / CMD)
python -m uv run vi.si.on --enable-autostart

# On Linux
uv run vi.si.on --enable-autostart

# Disable autostart
uv run vi.si.on --disable-autostart
```

* **On Windows**: Generates a silent background launcher (`vi.si.on.vbs`) in your Windows Startup directory (`%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup`), launching `vi.si.on` without an intrusive terminal window pop-up.
* **On Linux**: Generates an XDG Autostart desktop entry at `~/.config/autostart/vi.si.on.desktop`.

---

### 2. Linux Systemd User Service (Alternative)
For advanced Linux users running systemd:

1. Create `~/.config/systemd/user/vi.si.on.service`:
```ini
[Unit]
Description=vi.si.on Ambient Desktop AI Overlay
After=graphical-session.target

[Service]
Type=simple
WorkingDirectory=%h/vi.si.on
ExecStart=/usr/local/bin/uv run vi.si.on
Restart=on-failure
Environment=QT_QPA_PLATFORM=xcb

[Install]
WantedBy=graphical-session.target
```

2. Enable and start the service:
```bash
systemctl --user daemon-reload
systemctl --user enable --now vi.si.on.service
```

---

## ⌨️ Hotkeys Reference

| Hotkey | Action | Behavior |
|---|---|---|
| **`Alt + 1`** | **Quick Chat** | Ephemeral query; uses fast model. Auto-promotes on follow-up. |
| **`Alt + 2`** | **Conversation / Switcher** | Resumes active session. Press `Alt + 2` or `↑`/`↓` to cycle past conversations in real time. |
| **`Alt + Shift + 2`** | **New Conversation** | Starts a fresh persistent conversation session. |
| **`Alt + 3`** | **Snip Screen Area** | Interactive transparent region snipper; supports attaching multiple screenshots. |
| **`Alt + ↑ / ↓`** | **Cycle Conversations** | Switches conversation context across memorized threads. |
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
    "ocr_selection": "<alt>+3",
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
    "prefer_alternate_monitor": false,
    "prompt_clutter_avoidance": true,
    "prompt_fallback": "cursor"
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

### Configuration Options Guide

| Section | Parameter | Default | Description |
|---|---|---|---|
| **`provider`** | `type` | `"ollama"` | Inference backend: `"ollama"` for local models, `"litellm"` for cloud APIs (OpenAI, Anthropic, Gemini, Groq). |
| | `model_quick` | `"qwen2.5-coder:14b"` | Lightweight model for `Alt + 1` ephemeral 1-second queries. |
| | `model_conversation` | `"qwen3.8:27b"` | Deep reasoning model with memory context for `Alt + 2` conversations. |
| | `num_ctx_quick` | `8192` | KV cache context window tokens for fast queries. |
| | `num_ctx_conversation` | `16384` | KV cache context window tokens for multi-turn conversations. |
| | `keep_alive_quick` | `"3m"` | Duration to keep quick model loaded in GPU VRAM after a query. |
| | `keep_alive_conversation` | `"10m"` | Duration to keep conversation model loaded in GPU VRAM. |
| **`overlay`** | `prompt_placement` | `"center"` | Where the prompt box opens: `"center"`, `"cursor"`, or `"clearest_area"`. |
| | `prompt_clutter_avoidance` | `true` | When `true`, automatically shifts modal away from dense background code/text. |
| | `prompt_fallback` | `"cursor"` | Fallback if preferred spot is busy: `"cursor"` (mouse area), `"spatial"` (direct scan), `"center"`, or `"none"`. |
| | `answer_placement` | `"clearest_area"` | Where the answer box renders: `"clearest_area"` (AI spatial scan), `"center"`, or `"cursor"`. |
| | `screen_target` | `"same_screen"` | Monitor destination: `"same_screen"` (active monitor) or `"alternate_screen"` (secondary display). |
| | `auto_close` | `"timer"` | Dismiss behavior: `"timer"` (countdown after generation), `"manual"` (Esc only), or `"immediate"`. |
| | `auto_close_seconds` | `15` | Seconds before answer window closes automatically (scrolling pauses countdown). |
| | `min_width` / `min_height` | `400` / `280` | Minimum bounding box in logical pixels. |
| **`conversation`**| `promotion_timeout_seconds` | `15` | Grace window in seconds where follow-up `Alt + 1` queries are auto-promoted into conversations. |
| | `persist_to_disk` | `true` | Automatically saves and restores conversation threads across app restarts. |
| **`typography`** | `font_base_size` | `15` | Starting font size in points for short answers. |
| | `font_min_size` | `13` | Minimum readable floor size; answers will never scale smaller than this floor. |
| **`web_search`** | `enabled` | `false` | Enables private web search tool calling via SearXNG. |
| | `searxng_url` | `"http://localhost:8888"` | URL of your local or remote SearXNG instance. |
| **`knowledge_base`**| `enabled` | `false` | Enables local ChromaDB retrieval-augmented generation (RAG). |
| | `watch_directory` | `null` | Absolute folder path to watch and automatically index markdown/text documents. |

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

This project is licensed under the [GNU General Public License v3.0 (GPL-3.0)](LICENSE).
