# vi.si.on Overlay

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![PyQt6](https://img.shields.io/badge/GUI-PyQt6-green.svg)](https://riverbankcomputing.com/software/pyqt/)
[![Ollama](https://img.shields.io/badge/Local%20LLM-Ollama-purple.svg)](https://ollama.com/)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)

An ambient, non-intrusive, transparent desktop AI assistant for **Windows**, **Linux** (Ubuntu / Wayland / X11), and **macOS**. Will eventually bring a version of this that adapts to br.ai.n.

**vi.si.on** captures user queries via system-wide hotkeys, performs real-time visual clutter analysis to locate open screen space, computes ambient contrast schemes across mixed-DPI displays, and streams responses from local LLMs (via [Ollama](https://ollama.com)) or cloud backends (via [LiteLLM](https://github.com/BerriAI/litellm)).

---

## 🌟 Key Features

### ⚡ Dual Interaction Modes
- **`Alt + 1` — Ephemeral Quick Query**:
  - Ultra-low latency responses optimized for brief lookups.
  - Automatically dispatched to a designated fast model with short VRAM keep-alive (`keep_alive_quick`).
- **`Alt + 2` — Persistent Conversation & Session Switcher**:
  - Resumes the active multi-turn session.
  - Press `Alt + 2` repeatedly or use `↑` / `↓` to cycle through conversation history.
  - Dispatched to a dedicated reasoning model with long context memory (`keep_alive_conversation`).
- **`Alt + Shift + 2` — Fresh Conversation**: Instantly initializes a new session thread.
- **`Alt + 3` — Multi-Region Visual Snipper**: Captures and stacks one or more screen regions for multimodal visual reasoning.
- **`Esc` — Dismiss**: Smoothly dismisses active modals or overlays.

---

### 🧠 Dual-Model Routing & VRAM Optimization
- **Tiered Model Routing**: Decouples fast 1-turn tasks from deep multi-turn reasoning to optimize token throughput and memory footprint.
- **Resident Model Detection**: Inspects running backend state (`client.ps()`) to prioritize models already cached in GPU memory, avoiding cold-start initialization.
- **Clean VRAM Eviction**: Unloads model weights upon application exit to free GPU resources.

---

### 📜 Ambient Scrolling & Read Timer Management
- **Zero-Focus Hover Scrolling**: Scroll through long outputs immediately without having to focus or click the overlay window.
- **Smart Countdown Pause**: Hovering over or scrolling content automatically suspends the auto-dismiss timer, resuming smoothly when interaction finishes.

---

### 👁️ Computer Vision Spatial Placement & Mixed-DPI Support
- **Spatial Clutter Avoidance ($O(1)$ Integral Images)**: Analyzes desktop edge density via Canny edge detection and 2D integral convolutions, positioning overlays over unoccupied wallpaper or quiet desktop regions.
- **Mixed-DPI Calibration**: Normalizes coordinate systems between high-density displays (e.g., 4K @ 150%/200%) and standard displays (1080p @ 100%).
- **Display Affinity**: Keeps multi-turn conversations anchored to the monitor on which the interaction originated.

---

### 🎨 Adaptive Ambient Contrast Engine
- **W3C Relative Luminance Calculation**: Evaluates background pixels beneath input prompts and output overlays:
  - **Light Backgrounds**: Frosted light glass backing with high-contrast slate typography (`#0F172A`).
  - **Dark Backgrounds**: Obsidian glass backing with bright typography (`#F8FAFC`).

---

### ✂️ Multimodal Region Snipping (`Alt + 3`)
- **Native Resolution Capture**: Transparent capture overlay maintains pixel-accurate resolution across all attached displays.
- **Multi-Region Stacking**: Attach multiple rectangular snips into a unified context payload for simultaneous visual analysis.
- **Dynamic Capability Discovery**: Introspects model tensor architectures and runtime parameters to verify vision support dynamically.

---

### 🔌 Extensibility: Web Search, Local RAG & MCP Tools
- **Model Context Protocol (MCP)**: Native client supporting both local `stdio` processes and remote `SSE` endpoints (e.g., filesystem, GitHub, databases, memory).
- **SearXNG Web Search**: Private, self-hosted search engine tool calling.
- **ChromaDB Vector Store**: Auto-indexes local directories for retrieval-augmented generation (RAG).

---

## 🚀 Installation & Quick Start

### Prerequisites
- Python 3.10+ (Python 3.11, 3.12, and 3.13 supported)
- [`uv`](https://docs.astral.sh/uv/) (Fast Python package manager)
- [Ollama](https://ollama.com/) (Local runner) or API keys for Cloud providers (OpenAI, Anthropic, Gemini, Groq).

#### Linux GUI Dependencies
```bash
# Ubuntu / Debian / Pop!_OS
sudo apt update && sudo apt install -y libgl1 libglib2.0-0 libxcb-cursor0 libxkbcommon-x11-0 libegl1 libx11-xcb1

# Arch Linux / Manjaro
sudo pacman -S --needed mesa libglvnd glib2 libxkbcommon-x11 xcb-util-cursor

# Fedora / RHEL
sudo dnf install -y mesa-libGL glib2 libxkbcommon-x11 xcb-util-cursor
```

---

### 1. Clone & Setup

```bash
git clone https://github.com/mitro54/vi.si.on.git
cd vi.si.on

# Sync project dependencies
uv sync --all-groups
```

---

## 💻 Running the Application

### Windows (PowerShell / Terminal / CMD)
```powershell
python -m uv run vi.si.on
```

### Linux / macOS
```bash
uv run vi.si.on
```

### Graphical Setup Wizard
Launch the interactive configuration wizard at any time:
```bash
python -m uv run vi.si.on --wizard
```

### Test Suite Execution
```bash
python -m uv run pytest
```

---

## 🚀 Autostart Configuration

### One-Command Setup (Windows, Linux, macOS)
Configure **vi.si.on** to launch silently in the background on user login:

```bash
# Enable background autostart
python -m uv run vi.si.on --enable-autostart

# Disable autostart
python -m uv run vi.si.on --disable-autostart
```

- **Windows**: Places a lightweight launcher (`vi.si.on.vbs`) in `%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup` without a console window.
- **Linux**: Creates an XDG desktop entry at `~/.config/autostart/vi.si.on.desktop`.
- **macOS**: Registers a LaunchAgent plist at `~/Library/LaunchAgents/com.vision.overlay.plist`.

---

## ⌨️ Hotkeys Reference

| Hotkey | Action | Description |
|---|---|---|
| **`Alt + 1`** | **Quick Query** | Low-latency ephemeral query; automatically promotes to conversation on follow-up. |
| **`Alt + 2`** | **Conversation / Switcher** | Resumes active session. Press repeatedly or use `↑`/`↓` to switch history. |
| **`Alt + Shift + 2`** | **New Thread** | Starts a fresh persistent conversation. |
| **`Alt + 3`** | **Region Snipper** | Screen selection tool; supports stacking multiple snips. |
| **`Alt + ↑ / ↓`** | **Session Cycling** | Cycles across conversation threads. |
| **`Esc`** | **Dismiss** | Fades out active modal or overlay. |
| **Mouse Wheel** | **Scroll Text** | Scrolls content and pauses the auto-dismiss timer. |

---

## ⚙️ Configuration (`config.json`)

Configuration can be modified via the **Setup Wizard** (`--wizard`) or directly in [`config.json`](config.json):

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
    "min_width": 440,
    "min_height": 300,
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
  },
  "mcp_servers": []
}
```

### Configuration Reference

| Section | Parameter | Default | Description |
|---|---|---|---|
| **`provider`** | `type` | `"ollama"` | Backend provider: `"ollama"` (local) or `"litellm"` (cloud APIs). |
| | `model_quick` | `"qwen2.5-coder:14b"` | Model for `Alt + 1` fast queries. |
| | `model_conversation` | `"qwen3.8:27b"` | Model for `Alt + 2` conversational reasoning. |
| | `num_ctx_quick` | `8192` | KV context window tokens for fast queries. |
| | `num_ctx_conversation` | `16384` | KV context window tokens for multi-turn sessions. |
| | `keep_alive_quick` | `"3m"` | Duration to maintain fast model in VRAM. |
| | `keep_alive_conversation` | `"10m"` | Duration to maintain reasoning model in VRAM. |
| **`overlay`** | `prompt_placement` | `"center"` | Placement for prompt modal: `"center"`, `"cursor"`, or `"clearest_area"`. |
| | `prompt_clutter_avoidance` | `true` | Repositions prompt modal away from visually dense screen areas. |
| | `prompt_fallback` | `"cursor"` | Fallback position when preferred location is obstructed: `"cursor"`, `"spatial"`, `"center"`, or `"none"`. |
| | `answer_placement` | `"clearest_area"` | Destination for response overlay: `"clearest_area"`, `"center"`, or `"cursor"`. |
| | `screen_target` | `"same_screen"` | Display target: `"same_screen"` (active monitor) or `"alternate_screen"` (secondary monitor). |
| | `auto_close` | `"timer"` | Dismissal trigger: `"timer"` (timed countdown), `"manual"` (`Esc` only), or `"immediate"`. |
| | `auto_close_seconds` | `15` | Timer duration before overlay dismisses (hover/scroll pauses timer). |
| | `min_width` / `min_height` | `440` / `300` | Minimum bounding box in logical pixels. |
| **`conversation`**| `promotion_timeout_seconds` | `15` | Window during which follow-up queries promote into persistent sessions. |
| | `persist_to_disk` | `true` | Saves conversations to SQLite database (`conversations.db`). |
| **`typography`** | `font_base_size` | `15` | Baseline typography point size. |
| | `font_min_size` | `13` | Minimum typography point size threshold. |
| **`web_search`** | `enabled` | `false` | Enables SearXNG search tool execution. |
| | `searxng_url` | `"http://localhost:8888"` | URL for SearXNG service. |
| **`knowledge_base`**| `enabled` | `false` | Enables ChromaDB document vector store (RAG). |
| | `watch_directory` | `null` | Directory path monitored for automated document indexing. |
| **`mcp_servers`** | `mcp_servers` | `[]` | List of Model Context Protocol servers (`stdio` or `sse`). |

---

## 🏗️ Multi-Agent Architecture

```
[User Trigger / Hotkey (Alt+1 / Alt+2 / Alt+Shift+2 / Alt+3)]
│
▼
┌──────────────────┐
│ Orchestrator     │ ◄── Dispatches events, manages state machine & IPC
└────────┬─────────┘
         │
         ├────────────────────────────────────────┐
         ▼                                        ▼
┌──────────────────┐                     ┌───────────────────────────┐
│ Spatial & Visual │                     │ Inference Worker          │
│ Analyzer Agent   │                     │ (Ollama / LiteLLM Bridge) │
└────────┬─────────┘                     └────────┬──────────────────┘
         │ (TargetRect, ContrastScheme,           │ (Streaming Tokens,
         │  DPI Scale Factor)                     │  MCP / SearXNG / ChromaDB)
         ▼                                        ▼
┌───────────────────────────────────────────────────────────┐
│ Dynamic UI / Renderer Agent (PyQt6 Hardware Overlay)      │
└───────────────────────────────────────────────────────────┘
```

For comprehensive specifications, see [AGENTS.md](AGENTS.md) and [SYSTEM_SPEC.md](SYSTEM_SPEC.md).

---

## 📄 License

Distributed under the [GNU General Public License v3.0 (GPL-3.0)](LICENSE).
