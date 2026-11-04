# Hardware notes — new controls under evaluation

Context for anyone (or any Claude session) picking up the hardware work.
This records what we know about two controls being considered for the
panel, what is still unknown, and how we are testing them. Last updated
2026-10-29.

## The panel before the spinners

Until 2026-11-03 `arduino/sketch/sketch.ino` targeted an Arduino Uno:

| Input | Pin | Purpose |
| ----- | --- | ------- |
| SW_R, SW_G, SW_B | 2, 3, 4 | RGB toggle switches (screen 1) |
| SW_PUSH | 5 | Push classical colour to the left image |
| SW_COL | 6 | Collapse quantum colour to the right image |
| POT_X, POT_Y | A0, A1 | Selector box X / Y (screen 3) |
| POT_S | A2 | Selector box size — the Heisenberg slider |

It sends one line every 50 ms at 115200 baud, e.g.
`S:1,0,1,0,0,A:512,256,80`, which `arduino_bridge.py` parses. Switches use
`INPUT_PULLUP` (LOW = pressed). Pots read raw 0–1023.

## 1. Motorized slide potentiometer (10 kΩ linear, 5 V DC motor)

**Can the Arduino read it? Yes**, exactly like the existing pots.

- The pot part has 3 pins: one end to 5V, the other end to GND, the wiper
  to an analog pin. `analogRead()` gives about 0–1023, linear with travel.
  10 kΩ suits the Arduino ADC.
- Wired to A2 it is a drop-in replacement for `POT_S`: no sketch or Python
  change needed.
- The ends may not reach exactly 0 / 1023; map with a small margin. A
  0.1 µF capacitor from wiper to GND reduces jitter.

**The motor is optional.** It only matters if the software should move the
slider itself (e.g. return it to centre between visitors).

- Never drive the motor from an Arduino pin. Use an H-bridge driver
  (TB6612FNG, DRV8833 or L293D) on a separate 5 V supply of several
  hundred mA, with grounds tied together.
- Positioning is a closed loop: read the wiper, drive toward the target,
  stop inside a deadband (otherwise it oscillates).
- The running motor adds noise to the wiper reading: average readings,
  keep motor wiring away from the wiper wire.
- Many models have a 4th **touch-sense pin (T)** wired to the metal knob.
  It lets the code cut the motor when a visitor grabs the knob, which
  matters in an exhibit. Pinout differs by manufacturer: check the
  datasheet of the exact part.

## 2. TS-USP02 adjustable arcade spinner

**What it is.** Glen's Retro Show (GRS) spinner, sold by ThunderStick
Studios for Arcade1Up cabinets. Hall-effect sensor, plugs into the
Arcade1Up interface board with a JST connector, not USB. "Adjustable" means
a sensitivity / resolution setting (counts per turn). The vendor publishes
no pinout, voltage or protocol.

**Key difference from a pot.** A spinner turns endlessly and reports
*relative* motion (how far and which way), not an absolute position. The
software has to accumulate counts.

### Solved (2026-11-03): one pulse line per direction

The board (silk-screened "tsticks") has a microcontroller, a magnetic
sensor, LED1/LED2 (one blinks per direction) and three connectors:

| Connector | What it is |
| --------- | ---------- |
| 4-pin header, right edge: 3.3V / SWIM / GND / NRST | Chip programming port. Do not connect. |
| 4-pin plug, bottom: 5V / GND / RX1 / TX1 | Power, plus a serial port for the bundled "SY USBtoUART" adapter. **Silent when the knob turns** — not the spinner output. |
| 6-pin plug, top (next to transistors Q1–Q3) | **The spinner output.** |

Top plug, pins numbered left to right with the board as photographed
(6-pin plug at the top, DIP switch bottom right), measured against GND
with the board powered from the bottom plug:

| Pin | Idle voltage | Function |
| --- | ------------ | -------- |
| 1 | 5 V | Power |
| 2, 3, 6 | 0 V | Not identified (GND or unused) |
| 4 | 4.75 V | **RIGHT** pulses |
| 5 | 0 V | **LEFT** pulses (open-collector: floats at 0 V without a pull-up) |

Both outputs are **active LOW**: with `INPUT_PULLUP` they read 1 at rest
and drop to 0 for each step. One pulse per step on the line for that
direction — not quadrature. Count falling edges on each line: right
count minus left count is the motion.

Wiring on the Mega (bottom plug RX1 / TX1 left unconnected on both):

| Spinner | 5V / GND | Top pin 4 (right) | Top pin 5 (left) |
| ------- | -------- | ----------------- | ---------------- |
| Spinner 1 | Mega 5V / GND | pin 18 | pin 19 |
| Spinner 2 | Mega 5V / GND | pin 20 (SDA) | pin 21 (SCL) |

18–21 are four of the Mega's six external-interrupt pins; 2 and 3 are
left for the RGB switches. Using 20 / 21 rules out I2C on this board.
The Mega has 10 kΩ pull-ups on 20 / 21, which suits these active-LOW
outputs. `spinner_test` only watches 18 / 19, so spinner 2 is untested.

**DIP switch** (unplug power before changing):

| SW1 | SW2 | Pulses per rotation |
| --- | --- | ------------------- |
| OFF | OFF | 16 |
| ON | OFF | 64 |
| OFF | ON | 512 |
| ON | ON | 1024 |

SW3 sets pulse length: ON = 0.5 ms, OFF = 8 ms (Arcade1Up default).
Tested at 1 OFF / 2 OFF / 3 OFF. With 8 ms pulses the line saturates at
roughly 60 pulses per second, so a fast spin at high resolution will
lose steps; switch SW3 ON for 0.5 ms pulses before raising resolution.

Short spikes (20–40 µs) appeared while the jumper was held by hand
against the plug; treat them as contact noise until seen with firm
wiring. A firmware filter can ignore pulses shorter than ~0.3 ms.

Manufacturer support: sales@thunderjoystick.com.

**Why a Mega.** The Uno only has interrupts on pins 2 and 3, which the
exhibit sketch already uses for SW_R / SW_G. The Mega has interrupts on
pins 2, 3, 18, 19, 20 and 21, so the spinner fits on 18 / 19 without
moving the switches.

### Test sketch: `arduino/spinner_test/spinner_test.ino`

Stand-alone diagnostic for the Mega, not part of the exhibit. Run on
hardware 2026-11-03; RAW mode is what found the pinout above.

Wiring: spinner 5V → 5V, GND → GND, spinner TX1 → pin 19 (RX1),
spinner RX1 → pin 18 (TX1). If the labels are from the Mega's side, the
two signal wires are reversed. RAW mode shows which one is talking.

Serial Monitor at 115200 baud; type a letter + Enter:

- `r` **RAW** (default, safe: both pins are inputs only). Every 250 ms
  prints each pin's level, edge counts, a quadrature count, and the
  shortest pulse width with the baud rate it implies.
  - One pin idling HIGH with short pulses near a standard baud → UART.
  - Both pins toggling with similar edge counts, `quad=` rising one way
    and falling the other → quadrature encoder.
  - Nothing at all → the spinner may only answer when polled; next step
    would be sending a request byte on TX1.
- `u` **UART**: opens Serial1 and prints received bytes as hex + ASCII,
  16 per line, a pause splitting packets.
- `b` cycles baud: 9600, 19200, 38400, 57600, 115200, 250000, 4800, 2400,
  1200, 31250.

## Open questions / next steps

1. The exhibit sketch (`arduino/sketch/sketch.ino`) now targets the Mega
   and reads both spinners (1 → X, 2 → Y) and the size slider on A2. The
   X / Y knobs are gone. Verified on hardware 2026-11-03: the selector
   follows both spinners at `_SPIN_STEP_PX = 20` (`window3_quantum.py`).
   Reverse an axis by swapping that spinner's two signal wires. Keep the
   Arduino IDE Serial Monitor closed while the app runs — two readers on
   one port split the data and the app misses steps.
2. The motorized slider can replace the size pot on A2 unchanged; its
   motor and touch pin are not used yet.

## Sources

- ThunderStick Studios, GRS Arcade Spinner:
  https://thunderstickstudio.com/products/grs-arcade-spinner
- TS-USP02 listing (Glenn's Retro Show spinner page):
  https://sites.google.com/view/gregsqna2/gaming/arcadecontrols/spinner
- Arcade1Up spinner to PC thread:
  http://forum.arcadecontrols.com/index.php?topic=158675.0
