# Exhibit Quantum

An interactive museum exhibit that teaches the difference between classical
and quantum behaviour by letting visitors colour a drawing two ways at once.

Visitors pick a region of a line drawing, then colour it from two sources
side by side:

- **Classically** — three switches set Red, Green and Blue fully on or off.
  Eight colours, always the same result for the same switches.
- **Quantum-mechanically** — a selector box roams a rainbow palette and
  *collapses* to a colour sampled from the pixels underneath it, weighted by
  probability. The same box position can give a different colour each time.

The contrast between the two halves of the finished drawing is the lesson:
one side is determined, the other is drawn from a distribution.

The exhibit runs across three screens and is driven by a physical Arduino
panel of switches and knobs, so visitors interact with hardware rather than
a mouse.

## Screens

| Screen | Role |
| ------ | ---- |
| **1 — Classical** | The mixed colour fills the display. Three lamps along the bottom light up to show which channels are on. |
| **2 — Drawing** | The main menu: welcome, gallery of drawings, and the dual-panel colouring view. Save, print and QR code live here. |
| **3 — Quantum** | The rainbow palette as a full-screen canvas with the selector box on it, over two meters showing the size/speed trade-off. |

A region follows both colours live — flipping a switch or moving the selector
repaints it immediately, with no separate confirm step.

## The physics

The selector box obeys an analogue of the Heisenberg uncertainty principle,
`Δx · Δp ≈ ℏ`. The box size is the position uncertainty `Δx`, and the code
derives the momentum spread from it:

- **Small box** — position is pinned down, so momentum is uncertain: the box
  moves fast and erratically.
- **Large box** — position is vague, so momentum is well defined: the box
  drifts slowly and smoothly.

The two meters on screen 3 show this as opposing bars: as SIZE fills, SPEED
empties. Collapsing samples the pixels under the box as a joint normal
distribution and draws one colour from it.

## Requirements

- Python 3.11 or newer
- The packages in `requirements.txt` (PyQt6, NumPy, Pillow, OpenCV, qrcode,
  pySerial)
- Optional: an Arduino running `arduino/sketch/sketch.ino`

Runs on Windows, macOS and Linux, including a Raspberry Pi.

## Running it

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

The windows detect the attached monitors and place themselves. With three
screens each window goes full-screen on its own; with fewer they tile side
by side on one, which is the convenient arrangement for development.

## Configuration

All of it sits at the top of `main.py`:

| Setting | Purpose |
| ------- | ------- |
| `SCREEN_FOR_W1/W2/W3` | Which physical monitor shows which window. Screens are numbered left to right. |
| `IDENTIFY_SCREENS` | Set `True` to flash each screen's number on itself, to find out which is which. |
| `KIOSK_FRAMELESS` | Drop the window title bars. Turn off if the window manager needs them. |
| `ARDUINO_DEBUG` | Print the readings arriving from the panel. See *Troubleshooting*. |

## Controls

The exhibit is driven by the Arduino panel: three switches for the colour
channels, three knobs for the selector's position and size, and two buttons
for push and collapse.

Every action also has a keyboard command, so the exhibit still runs if the
panel is unplugged:

| Key | Action |
| --- | ------ |
| `R` `G` `B` | Toggle that colour channel |
| `P` / `Space` | Push the classical colour into the selected region |
| Arrow keys | Move the selector |
| `[` `]` | Shrink / grow the selector (and so speed it up / slow it down) |
| `A` | Start or stop the automatic movement |
| `Enter` | Collapse |
| `Q` | Collapse and push |
| `Ctrl+S` / `Ctrl+P` / `Ctrl+G` | Save / print / back to gallery |
| `Esc` | Reveal the hidden controls |

## Adding drawings

Drop black-and-white line art into `images/` as PNG, JPG, BMP or SVG; it
appears in the gallery on the next run. Enclosed white areas become colourable
regions, so outlines need to be closed.

To show visitors what a finished drawing can look like, put a coloured version
in `colored/` under the same base name — `images/dinosaur.svg` pairs with
`colored/dinosaur.png`.

## Troubleshooting

**The panel does nothing.** Set `ARDUINO_DEBUG = True` in `main.py` and watch
the terminal. Switch flips and button presses print as they happen, tagged
`EVENT`; the knobs print about once a second. Nothing at all means the board
is not being found — the app says so at startup and carries on in
software-only mode. Detection is by USB vendor ID, so a clone with an unusual
chip may need its ID adding to `_ARDUINO_VIDS` in `arduino_bridge.py`.

**A window is on the wrong monitor.** Set `IDENTIFY_SCREENS = True`, run once
to see each screen's number, then set `SCREEN_FOR_W1/W2/W3` accordingly.

**The QR code will not download.** The image is served from the exhibit
machine over the local network, so the phone has to be on the same Wi-Fi.

## Layout

```
main.py                  entry point: theme, monitor detection, placement
app_state.py             shared state and the signals that sync the windows
window1_rgb.py           classical colour screen
window2_image.py         gallery, drawing and saving
window3_quantum.py       quantum palette, Heisenberg motion, meters
image_utils.py           region detection, colour fill, quantum sampling
arduino_bridge.py        reads the panel over USB serial
kiosk.py                 exhibition presentation and keyboard commands
scaling.py               grows a fixed layout to fill a screen
generate_test_image.py   makes a test drawing
arduino/sketch/          the Arduino firmware
images/                  line-art templates
colored/                 finished references shown beside each template
```

`explanation.txt` is a plain-language walkthrough of the whole project for
non-technical readers.
