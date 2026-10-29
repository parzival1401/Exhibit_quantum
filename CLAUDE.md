# Exhibit Quantum — project context

Senior design project (Spring 2026): an interactive museum exhibit that
teaches the difference between classical and quantum behaviour by having
visitors colour a line drawing two ways at once. Python + PyQt6 app across
three screens, driven by an Arduino panel of switches and knobs.

`README.md` is the operator guide (setup, keys, troubleshooting).
`explanation.txt` is the plain-language version for non-technical readers.
`arduino/HARDWARE_NOTES.md` covers new controls under evaluation.

## Objective

Visitors colour regions of the same drawing from two sources, side by side:

- **Classical (left image)** — three switches set R, G, B fully on or off.
  Eight possible colours; the same switches always give the same result.
- **Quantum (right image)** — a selector box on a rainbow palette
  *collapses* to a colour sampled from the pixels under it by probability.
  The same position can give a different colour each time.

The contrast between the determined half and the probabilistic half is the
lesson. The selector also models the Heisenberg uncertainty principle,
`Δx · Δp ≈ ℏ`: box size is `Δx`, and momentum spread is derived from it.

- **Small box** → position known, momentum uncertain → fast, erratic motion.
- **Large box** → position vague, momentum well defined → slow, smooth drift.

## Screens

| Window | File | Role |
| ------ | ---- | ---- |
| 1 — Classical | `window1_rgb.py` | Mixed RGB colour fills the screen; three lamps show which channels are on. |
| 2 — Drawing | `window2_image.py` | Welcome → gallery → dual-panel colouring view. Save PNG, print, QR code download. |
| 3 — Quantum | `window3_quantum.py` | HSV gradient palette with the selector box, plus SIZE / SPEED meters that move in opposition. |

A region is selected by clicking/touching it on either panel of window 2.
Its colour follows both sources live — no separate confirm step.

## Modules and key functions

| File | What it does |
| ---- | ------------ |
| `main.py` | Entry point. Config flags at the top (`SCREEN_FOR_W1/W2/W3`, `IDENTIFY_SCREENS`, `KIOSK_FRAMELESS`, `ARDUINO_DEBUG`). Builds the windows, connects the Arduino signals, places windows: one per monitor with 3+ screens, tiled on one screen otherwise. |
| `app_state.py` | `AppState(QObject)`: the single source of truth shared by the windows. Properties `rgb_color`, `quantum_color`, `selected_region`; signals `rgb_color_changed`, `quantum_color_changed`, `selected_region_changed`, `push_rgb_requested`, `push_quantum_requested`. |
| `window1_rgb.py` | `RGBControllerWindow`. `apply_switches(r, g, b)` takes the hardware switch states. |
| `window2_image.py` | `ImageProcessorWindow` (stacked welcome/gallery/colouring pages), `ImageCard`, `ImagePanel`, `QRDialog`. Loads PNG/JPG/BMP/SVG from `images/` (SVG via QtSvg); pairs each with a finished reference in `colored/` by base name. QR code is served by a small local HTTP server, so the phone must be on the same network. |
| `window3_quantum.py` | `QuantumPaletteWindow`, `GradientPaletteWidget` (palette + selector), `UncertaintyBar` (meters). Heisenberg motion runs on a QTimer: each tick `momentum_spread = HBAR / size`, Gaussian velocity noise, damping, speed cap, wall reflection. `apply_pots(x, y, size)` takes the knobs; `collapse_and_push()` collapses and fills the right image. Tunables: `HBAR`, `NOISE_SCALE`, `SPEED_SCALE`, `DAMP`, `TICK_MS`, `SIZE_MIN/MAX`. |
| `image_utils.py` | `create_gradient_palette` (X = hue, Y = brightness), `identify_regions` (connected components on light pixels; dark = outline = region 0), `apply_region_colors`, `apply_color_to_template`, `quantum_collapse` (per-channel normal distribution over the box's pixels → weighted random pick of one pixel). |
| `arduino_bridge.py` | `ArduinoBridge(QObject)`: auto-detects the board by USB vendor ID (`_ARDUINO_VIDS`), reads serial in a daemon thread, emits `switches_changed`, `pots_changed`, `push_rgb_pressed`, `collapse_pressed`. No board → software-only mode. |
| `kiosk.py` | Exhibition mode: hides buttons and dev readouts, frameless windows, keyboard commands (staff fallback). `Esc` reveals controls, `X` quits. |
| `scaling.py` | `apply_uniform_scaling`: grows a fixed layout to fill a screen. |
| `theme.py` | Shared dark colour tokens and stylesheet helpers for all three screens. |
| `generate_test_image.py` | Makes a test drawing. |

Keyboard fallback: `R` `G` `B` toggle channels, `P`/`Space` push classical,
arrows move selector, `[` `]` resize, `A` auto-move, `Enter` collapse, `Q`
collapse + push, `Ctrl+S/P/G` save / print / gallery.

## Hardware

**Current panel** — `arduino/sketch/sketch.ino`, written for an Arduino Uno:

| Input | Pin | Drives |
| ----- | --- | ------ |
| SW_R, SW_G, SW_B (toggles) | 2, 3, 4 | Window 1 colour channels |
| SW_PUSH (momentary) | 5 | Push classical colour to left image |
| SW_COL (momentary) | 6 | Collapse quantum + push to right image |
| POT_X, POT_Y | A0, A1 | Selector X / Y |
| POT_S | A2 | Selector size (the Heisenberg slider) |

Switches use `INPUT_PULLUP` (LOW = pressed). The board sends one line every
50 ms at 115200 baud: `S:r,g,b,push,col,A:x,y,size` (pots raw 0–1023).
Push/collapse fire on the rising edge. Pots set position directly when
auto-move is off and nudge velocity when it is on; the first reading only
sets a baseline.

**Under evaluation** (details in `arduino/HARDWARE_NOTES.md`):

- Motorized 10 kΩ linear slide pot: reads like any pot; a drop-in for
  POT_S. The motor would need an H-bridge driver and its own supply.
- TS-USP02 arcade spinner, wires labelled 5V / GND / RX1 / TX1: protocol
  unknown (UART or quadrature). Being tested on an Arduino Mega with
  `arduino/spinner_test/spinner_test.ino`; not yet run on hardware.

**Not documented yet:** the exhibit computer, the monitor models and
whether they are touchscreens, the printer, and the enclosure.

## Requirements

Python 3.11+, packages in `requirements.txt` (PyQt6, NumPy, Pillow,
OpenCV, qrcode, pySerial). Runs on Windows, macOS and Linux, including a
Raspberry Pi. Start with `python main.py`.
