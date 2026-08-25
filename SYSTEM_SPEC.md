# vi.si.on — System Specification & Implementation Details

## 1. Tech Stack Requirements

* **Runtime**: Python 3.10+ (Cross-platform: Linux/WSL2/Ubuntu, macOS, Windows)
* **GUI Engine**: `PyQt6` (Hardware-accelerated translucent frameless windows)
* **Screen Grabber**: `mss` (High-performance multi-monitor screenshot capture)
* **Computer Vision**: `OpenCV` (`cv2`), `NumPy`
* **Local LLM Runner**: Ollama (supports any user-installed local LLM or multimodal vision model)
* **Cloud LLM Support**: `litellm` (OpenAI, Anthropic, Google, Mistral, Groq, etc.)
* **Web Search**: SearXNG JSON API via `httpx`
* **Knowledge Base**: ChromaDB for vector retrieval + `watchdog` for folder auto-ingestion
* **Tool Protocols**: Model Context Protocol (`mcp[cli]>=2.0`)
* **Global Input Hook**: `pynput` with Wayland CLI trigger fallback

---

## 2. Mathematical & Algorithmic Heuristics

### 2.1. Least-Cluttered Space Detection
To avoid rendering text on top of icons, IDE text, or active visual elements:

1. **Grayscale Conversion**:
   $$\text{Gray} = 0.299R + 0.587G + 0.114B$$
2. **Canny Edge Detection**:
   Extract high-frequency structural elements with thresholds $T_{\text{low}} = 50$, $T_{\text{high}} = 150$.
3. **Integral Box Convolution**:
   Generate an edge density map $D(x, y)$ using 2D Integral Images for $O(1)$ box sums with target window dimensions $(W_t, H_t)$ adhering to user minimum constraints $(W_{\min}, H_{\min})$:
   $$D(x, y) = \sum_{i=0}^{W_t-1} \sum_{j=0}^{H_t-1} E(x+i, y+j)$$
4. **Window Selection**:
   Find $(x^*, y^*) = \arg\min_{(x,y)} D(x, y)$ within screen boundary margins.

### 2.2. Perceptual Luminance & Contrast Calculation
Determine text and background styling using W3C Relative Luminance:

$$L = 0.2126 R_{\text{linear}} + 0.7152 G_{\text{linear}} + 0.0722 B_{\text{linear}}$$

Where $C_{\text{linear}} = C_{\text{srgb}} / 12.92$ if $C_{\text{srgb}} \le 0.04045$, else $(\frac{C_{\text{srgb}} + 0.055}{1.055})^{2.4}$.

* **If $L_{\text{ROI}} > 0.5$ (Light Wallpaper/Workspace)**:
  * Foreground: `#0F172A` (Slate 900)
  * Backing Shield: `rgba(255, 255, 255, 0.45)`
  * Shadow: `0 1px 2px rgba(255, 255, 255, 0.8)`
* **If $L_{\text{ROI}} \le 0.5$ (Dark Wallpaper/Workspace)**:
  * Foreground: `#F8FAFC` (Slate 50)
  * Backing Shield: `rgba(0, 0, 0, 0.45)`
  * Shadow: `0 1px 3px rgba(0, 0, 0, 0.9)`

### 2.3. Dynamic Font Downscaling (Adaptive Typometry)
As token count $N$ increases during streaming, downscale the font size $S$ to maximize visible text before scroll-bars engage:

$$S(N) = \max\left(S_{\min}, \; S_{\text{base}} - \left\lfloor \frac{N - N_{\text{threshold}}}{k} \right\rfloor\right)$$

* $S_{\text{base}} = 15\text{px}$
* $S_{\min} = 11\text{px}$
* $N_{\text{threshold}} = 250\text{ characters}$
* $k = 150\text{ characters per 1px reduction}$

---

## 3. UI Window States & Transitions

```
┌──────────────┐      Alt+1 / Alt+2       ┌──────────────┐
│ HIDDEN/IDLE  │ ───────────────────────► │ INPUT_ACTIVE │
└──────────────┘                          └──────┬───────┘
▲                                                │ Enter Key
│                                                ▼
│ Auto-close / Esc                        ┌──────────────┐
└──────────────────────────────────────── │ STREAMING /  │
                                          │ RENDERING    │
                                          └──────────────┘
```

### Window Flag Configuration (PyQt6)
```python
window.setWindowFlags(
    Qt.WindowType.FramelessWindowHint |
    Qt.WindowType.WindowStaysOnTopHint |
    Qt.WindowType.SubWindow |
    Qt.WindowType.NoDropShadowWindowHint
)
window.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
```

---

## 4. Acceptance Criteria & Safety

1. **Multi-Monitor Awareness**: Focus-aware monitor selection targets alternate displays when available to minimize workflow interruption.
2. **Anti-Cheat Safe**: Uses standard non-intrusive desktop window flags. No DLL injection, DirectX hooking, or game memory reading. Suppressed in exclusive fullscreen.
3. **Adaptive Auto-Promotion**: Follow-up queries submitted within 60s of stream completion automatically convert one-off chats into persistent memorized sessions.
4. **Non-Blocking Architecture**: LLM token streaming and computer vision operations execute in dedicated asynchronous/threaded workers without blocking the UI event loop.
