# Multi-Agent Architecture: vi.si.on 🔮

## 1. System Overview
**vi.si.on** is an ambient, non-intrusive, transparent local desktop AI assistant. It intercepts user queries via global hotkeys, performs real-time screen analysis to determine the least-cluttered desktop region, dynamically calculates contrast/typography parameters, and streams responses from a local LLM runner (e.g., Ollama) or cloud providers via LiteLLM.

## 2. Agent Topography & Pipeline

```
[User Trigger / Hotkey (Alt+1 / Alt+2 / Alt+Shift+2)]
│
▼
┌──────────────────┐
│ Orchestrator     │ ◄── Dispatches query payload & coordinates state machine
└────────┬─────────┘
         │
         ├────────────────────────────────────────┐
         ▼                                        ▼
┌──────────────────┐                     ┌───────────────────────────┐
│ Spatial & Visual │                     │ Inference Worker          │
│ Analyzer Agent   │                     │ (Ollama / LiteLLM Bridge) │
└────────┬─────────┘                     └────────┬──────────────────┘
         │ (SpatialCoordinates,                   │ (Token Stream,
         │  ContrastScheme, ScaleFactor)          │  Tool Calls: Web/KB/MCP)
         ▼                                        ▼
┌───────────────────────────────────────────────────────────┐
│ Dynamic UI / Renderer Agent (PyQt6 Overlay Engine)        │
└───────────────────────────────────────────────────────────┘
```

---

## 3. Agent Specifications

### 3.1. Orchestrator Agent (`orchestrator.py`)
* **Role**: System state manager and event coordinator.
* **Responsibilities**:
  1. Listen for global keyboard shortcuts (`Alt+1` for quick chat, `Alt+2` for conversation/picker, `Alt+Shift+2` for fresh conversation).
  2. Spawn and focus the modal input prompt at the cursor location or screen center.
  3. Manage automatic quick-to-persistent conversation promotion if a follow-up query occurs within 60s of stream completion.
  4. Perform focus-aware monitor selection (preferring non-focused display if multi-monitor).
  5. Upon user query submission:
     - Instantly capture current screen buffer (before rendering changes).
     - Dispatch screen buffer to the **Spatial & Visual Analyzer Agent**.
     - Dispatch prompt string & context to the **Inference Worker Agent**.
  6. Coordinate auto-close countdown with hover pause, dismissal hotkeys (`Esc`), and smooth fade-out lifecycle.

### 3.2. Spatial & Visual Analyzer Agent (`spatial_finder.py`, `capture.py`)
* **Role**: Computer vision and perceptual heuristics processor.
* **Responsibilities**:
  1. **Region Detection**: Process raw screen captures (via `mss`) using edge-density convolutions (Canny + 2D Integral Images) to identify the global minimum for visual noise adhering to user-configured minimum dimensions.
  2. **Luminance Profiling**: Extract the chosen Region of Interest (ROI), compute Relative Luminance ($L$), and determine the optimal foreground/text contrast polarity.
  3. **Typography Adaptation**: Calculate baseline font sizing, line height, and max token boundaries based on the detected region dimensions.
* **Output Payload**:
  ```json
  {
    "target_rect": {"x": 1120, "y": 640, "width": 520, "height": 380},
    "theme": {
      "text_color": "#F8FAFC",
      "backing_tint": "rgba(15, 23, 42, 0.45)",
      "text_shadow": "0 1px 3px rgba(0, 0, 0, 0.9)"
    },
    "typography": {
      "base_font_size": 15,
      "min_font_size": 11,
      "line_height": 1.4
    }
  }
  ```

### 3.3. Inference Worker Agent (`ollama_client.py`, `litellm_client.py`)
* **Role**: Local/Cloud LLM execution and token streaming.
* **Responsibilities**:
  1. Connect to Ollama via local HTTP API (`localhost:11434`) or Cloud LLMs via LiteLLM.
  2. Maintain conversation context and delegate context window management to provider backend.
  3. Stream tokens asynchronously using thread-safe Qt signals to avoid UI blocking.
  4. Coordinate function/tool calling for SearXNG Web Search, ChromaDB Knowledge Base, and MCP servers.
  5. Manage cancel-tokens when queries are interrupted by the user.

### 3.4. Dynamic UI / Renderer Agent (`overlay_view.py`, `input_modal.py`, `conversation_picker.py`)
* **Role**: Frameless, transparent, hardware-accelerated desktop view.
* **Responsibilities**:
  1. Initialize with `FramelessWindowHint`, `WindowStaysOnTopHint`, and `WA_TranslucentBackground`.
  2. Reposition and resize to the bounds provided by the Spatial Analyzer, respecting user minimum dimensions.
  3. Apply dynamic CSS stylesheets for contrast and readability.
  4. Stream-render tokens with dynamic auto-scrolling and real-time font downsizing as character thresholds are crossed.
  5. Support click-through mode (`WA_TransparentForMouseEvents`) once output streaming completes if configured.
