# Documentation Generation Prompt — Exhibit Quantum

Copy everything below this line and paste it into your LLM of choice.

---

## CONTEXT

You are generating **technical documentation** for a senior design project called **Exhibit Quantum**, a museum-grade interactive exhibit application built with Python. The audience is a mix of:
- Senior design faculty reviewers (need high-level design rationale)
- Future developers / maintainers (need technical depth)
- Museum operators (need setup/usage instructions)

The documentation should be professional, clear, and thorough.

---

## PROJECT OVERVIEW

**Exhibit Quantum** is a museum exhibit that teaches visitors about quantum mechanics concepts (specifically the Heisenberg Uncertainty Principle) through an interactive paint-by-numbers coloring experience. Visitors color regions of an image using two parallel systems:

1. **Classical RGB** — binary ON/OFF toggle for each Red, Green, Blue channel (deterministic, controllable)
2. **Quantum Collapse** — a probabilistic color selector modeled after quantum measurement (the "collapsed" color is sampled from a probability distribution)

The contrast between classical (predictable) and quantum (probabilistic) color selection is the core educational metaphor.

**Hardware:** The exhibit supports physical controls via an Arduino microcontroller — three toggle switches for RGB and three potentiometers for controlling the quantum selector's position and size. This makes it touchscreen and hands-on museum friendly.

---

## TECHNICAL SPECIFICATIONS

### Stack

| Component | Technology |
|-----------|-----------|
| Language | Python 3.11+ |
| GUI Framework | PyQt6 |
| Image Processing | OpenCV (`cv2`), Pillow (`PIL`), NumPy |
| Hardware Bridge | PySerial (USB serial at 115200 baud) |
| QR Code Generation | `qrcode[pil]` |
| SVG Rendering | `PyQt6.QtSvg.QSvgRenderer` |

### Dependencies (`requirements.txt`)
```
PyQt6>=6.4.0
Pillow>=9.0.0
opencv-python>=4.7.0
numpy>=1.24.0
qrcode[pil]>=7.3.1
pyserial>=3.5
```

### How to Run
```bash
pip install -r requirements.txt
python main.py
```

---

## ARCHITECTURE

The application consists of **three synchronized PyQt6 windows** arranged side-by-side on screen. All inter-window communication flows through a central `AppState` object using Qt signals/slots (observer pattern).

### Window Layout

```
┌─────────────────┬──────────────────────────┬──────────────────┐
│  Window 1       │  Window 2                │  Window 3        │
│  Classical RGB  │  Image Processor         │  Quantum Palette │
│  (300×520 px)   │  (900×660 px min)        │  (560×650 px)    │
│                 │                          │                  │
│  • R/G/B toggle │  • Gallery / Welcome     │  • HSV gradient  │
│  • Color swatch │  • Dual-panel coloring   │  • Selector box  │
│  • Push button  │  • Save / Print / QR     │  • Collapse btn  │
└─────────────────┴──────────────────────────┴──────────────────┘
```

### Signal Flow Diagram

```
AppState (Central Signal Bus)
├── rgb_color_changed(tuple)       → Window 2 LEFT panel re-renders
├── quantum_color_changed(tuple)   → Window 2 RIGHT panel re-renders
├── selected_region_changed(int)   → Windows 1 & 3 highlight feedback
├── push_rgb_requested()           → Window 2 fills LEFT region
└── push_quantum_requested()       → Window 2 fills RIGHT region

Window 1 (RGB) → AppState.rgb_color
Window 3 (Quantum) → AppState.quantum_color
Window 2 → AppState.selected_region

ArduinoBridge (daemon thread, serial)
├── switches_changed(r, g, b) → Window 1.apply_switches()
├── pots_changed(x, y, size)  → Window 3.apply_pots()
├── push_rgb_pressed()        → AppState.request_push_rgb()
└── collapse_pressed()        → Window 3.collapse_and_push()
```

---

## FILE-BY-FILE SPECIFICATION

### `main.py` (130 lines)
- Entry point
- Builds dark Fusion theme (grays + cool purples)
- Instantiates `AppState`, three windows, and `ArduinoBridge`
- Connects Arduino signals to window slots
- Positions windows side-by-side using `QScreen.availableGeometry()`

### `app_state.py` (70 lines)
- `AppState(QObject)` — single source of truth
- **Signals:** `rgb_color_changed`, `quantum_color_changed`, `selected_region_changed`, `push_rgb_requested`, `push_quantum_requested`
- **Properties:** `rgb_color (tuple)`, `quantum_color (tuple)`, `selected_region (int, -1 = none)`
- **Methods:** `request_push_rgb()`, `request_push_quantum()`

### `window1_rgb.py` (196 lines)
- `RGBControllerWindow(QMainWindow)`
- Three binary toggle buttons (each channel is 0 or 255)
- Large color preview swatch with luminance-aware text color
- "Push Color" button → `AppState.request_push_rgb()`
- `apply_switches(r, g, b)` — called by Arduino bridge

### `window2_image.py` (1096 lines)
- `ImageProcessorWindow(QMainWindow)` — center window, museum UX hub
- Three-page stacked UI:
  - **Page 0 (Welcome):** Big START button
  - **Page 1 (Gallery):** Scrollable image grid (3-column), shows colored reference badge
  - **Page 2 (Coloring):** Dual-panel coloring view + save/print/QR
- Region click → coordinate mapping → `identify_regions()` lookup
- `left_region_colors` / `right_region_colors` dict per region ID
- SVG rasterization via `QSvgRenderer`
- QR code download: starts `SimpleHTTPRequestHandler` on random free port, generates QR with LAN IP
- Print: `QPrinter` + `QPrintDialog`
- Supporting classes: `ImageCard`, `ImagePanel`, `ClickableLabel`, `QRDialog`

### `window3_quantum.py` (575 lines)
- `QuantumPaletteWindow(QMainWindow)` + `GradientPaletteWidget(QWidget)`
- **Gradient canvas (520×290 px):**
  - X-axis: Hue 0°→360° (full rainbow)
  - Y-axis: Value 255→20 (bright top, dark bottom)
  - Saturation: fixed at 220
- **Selector:** white dashed square, resizable 10–150 px
- **Heisenberg Physics (50ms timer):**
  - Constants: `HBAR=700`, `NOISE_SCALE=0.10`, `SPEED_SCALE=0.38`, `DAMP=0.88`
  - `momentum_spread = HBAR / sq_size`
  - Each tick: add `N(0, momentum_spread * NOISE_SCALE)` noise to velocity, damp, clamp, move, reflect at walls
  - Small square → large Δp → fast erratic motion
  - Large square → small Δp → slow smooth drift
- **Quantum Collapse:** calls `image_utils.quantum_collapse()`, emits `quantum_color_changed`
- **Arduino pot integration:** deadband=8 ADC; when animation OFF → absolute position; when ON → velocity kicks
- **Keyboard:** arrow keys move selector ±5px, Enter collapses

### `image_utils.py` (271 lines)

#### `create_gradient_palette(width, height) → ndarray`
- Returns H×W×3 uint8 RGB HSV gradient

#### `apply_color_to_template(template, color, fill_threshold=180, outline_threshold=80) → ndarray`
- Luminance-based fill:
  - lum ≥ 180 → solid color fill
  - lum ≤ 80 → keep black outline
  - 80 < lum < 180 → proportional blend
- Perceptual luminance: `0.299R + 0.587G + 0.114B`

#### `quantum_collapse(gradient_array, sq_x, sq_y, sq_size) → tuple`
- Extracts pixels inside selector square
- Models each RGB channel as `N(μ, σ)` (min σ=1.0)
- Joint probability: `P(pixel) = ∏ N(c; μ_c, σ_c)` over RGB channels
- Weighted random sample → one (R, G, B) result
- This is the core quantum simulation

#### `identify_regions(template_array) → (num_labels, labels)`
- Connected-component labeling on pixels with lum > 80
- Returns H×W int32 array of region IDs (0 = outline)

#### `apply_region_colors(template, region_labels, region_colors, selected_region=-1) → ndarray`
- Fills all non-outline pixels with default gray
- Applies per-region color dict
- Highlights selected region: `0.55 * old + 0.45 * yellow`

#### `find_test_image(directory) → str | None`
- Two-pass finder: prefers filenames with 'test'/'crayo', SVG first

### `arduino_bridge.py` (159 lines)
- `ArduinoBridge(QObject)` — daemon thread, silent fallback
- Auto-detects port: scans for 'arduino', 'ch340', 'ch341', 'usbmodem', 'usbserial'
- **Serial protocol (115200 baud):**
  ```
  S:1,0,1,0,0,A:512,256,80
  │             │
  │             └── 3 pot values: X, Y, Size (0–1023 ADC)
  └── 5 switch values: R, G, B, SW_PUSH, SW_COL (0 or 1)
  ```
- Emits signals only on state change (debounced switches, rising-edge buttons)
- Always emits `pots_changed` (deadband handled downstream)

### `generate_test_image.py` (123 lines)
- Generates mandala-style paint-by-numbers PNG template
- Concentric circles + spokes on white background with black outlines
- All fills pure white (255,255,255), all lines pure black (0,0,0), 3px line width
- Designed for clean luminance-threshold region detection

---

## KEY ALGORITHMS

### Heisenberg Uncertainty Engine (Window 3)
```
HBAR = 700  # ℏ analogue
momentum_spread = HBAR / selector_size   # Δp ∝ 1/Δx

Each tick (50ms):
  vx += Gaussian(0, momentum_spread * NOISE_SCALE)
  vy += Gaussian(0, momentum_spread * NOISE_SCALE)
  vx *= DAMP
  vy *= DAMP
  vx = clamp(vx, -max_speed, max_speed)   # max_speed = momentum_spread * SPEED_SCALE
  fx += vx; fy += vy   # float accumulator
  move selector by floor(fx), floor(fy)
  reflect velocity at canvas walls
```

### Quantum Collapse (image_utils.py)
```
pixels = all pixels inside selector square (N×3 array)
for each channel c in {R, G, B}:
    μ_c = mean(pixels[:, c])
    σ_c = max(std(pixels[:, c]), 1.0)
    pdf_c = N(pixels[:, c]; μ_c, σ_c)

weight_i = pdf_R[i] * pdf_G[i] * pdf_B[i]
weights = weights / sum(weights)
result = pixels[random_choice(weights)]
```

### Region Detection (image_utils.py)
```
lum = 0.299R + 0.587G + 0.114B
fillable_mask = (lum > 80)
labels = connected_components(fillable_mask)
```

### Region Coloring
```
for each pixel at (y, x):
    rid = region_labels[y, x]
    if rid == 0: keep outline
    elif rid in region_colors: apply region_colors[rid]
    else: apply default gray (225, 225, 225)
    if rid == selected_region: blend with yellow highlight
```

---

## USER EXPERIENCE FLOW

```
App Launch
    │
    ▼
Window 2: Welcome Page → [START]
    │
    ▼
Gallery Page: Choose image from grid
    │     (each card shows thumbnail + colored reference badge)
    ▼
Coloring Page: Dual-panel view
    │
    ├── Click region in either panel → region highlighted in yellow
    │
    ├── Window 1: Toggle R/G/B → adjust color swatch
    │   └── [Push Color] → fills LEFT panel region
    │
    ├── Window 3: Move selector / resize / press Enter or [Collapse]
    │   └── Collapsed color appears → [Push Color] → fills RIGHT panel region
    │
    ├── [Save Image] → export left+right side-by-side as PNG/JPEG
    ├── [Get QR Code] → local HTTP server + QR dialog for mobile download
    └── [Print] → send to default printer
```

---

## ARDUINO HARDWARE (OPTIONAL)

Physical controls mirror the software UI:

| Hardware | Maps To | Behavior |
|----------|---------|---------|
| Switch R | Window 1 Red toggle | Binary ON/OFF |
| Switch G | Window 1 Green toggle | Binary ON/OFF |
| Switch B | Window 1 Blue toggle | Binary ON/OFF |
| Pot X | Window 3 selector X position | Absolute when still; velocity kick when animating |
| Pot Y | Window 3 selector Y position | Same as X |
| Pot Size | Window 3 selector size | Always absolute (10–150px mapped from 0–1023) |
| Button PUSH | Push RGB color to left image | Rising edge only |
| Button COL | Collapse quantum + push to right | Rising edge only |

App runs normally without Arduino (silent fallback, console warning only).

---

## EDUCATIONAL CONCEPT

The exhibit teaches the **Heisenberg Uncertainty Principle** (Δx · Δp ≥ ℏ/2) through a visual analogy:

- **Position uncertainty (Δx)** = selector square size
- **Momentum uncertainty (Δp)** = how erratically the selector moves

A **small square** means you are trying to pin down the exact color — but the physics engine gives it high momentum noise, making it bounce around unpredictably (like a particle with a well-defined position but uncertain momentum).

A **large square** covers a broad color region (uncertain position) but moves slowly and smoothly (well-defined momentum).

Visitors experience this directly: shrinking the selector to "pick a precise color" causes it to fly around uncontrollably. Enlarging it calms the motion but at the cost of color precision. This mirrors real quantum behavior.

---

## DOCUMENT TO GENERATE

Using all of the above context, generate a complete **technical project document** with the following sections:

1. **Executive Summary** — 1 page, what the project is, why it was built, who uses it
2. **System Architecture** — diagrams (ASCII or described), component responsibilities, communication patterns
3. **Technical Design** — deep dive into each module, class/method descriptions, key algorithms with pseudocode
4. **Quantum Mechanics Educational Framework** — how the software models and teaches uncertainty principle
5. **Hardware Integration** — Arduino protocol, serial format, signal flow, fallback behavior
6. **User Experience Design** — UI flow, museum UX considerations, accessibility
7. **Setup & Deployment** — installation, running, image gallery setup, Arduino wiring (if applicable)
8. **Testing & Validation** — how to verify each component works correctly
9. **Future Work / Limitations** — known limitations, potential improvements
10. **Appendix** — full file structure, dependency table, constants reference

Write this document at a level appropriate for a **senior design capstone report**. Use formal technical language. Include tables where appropriate. Diagrams can be described in ASCII or Mermaid format.
