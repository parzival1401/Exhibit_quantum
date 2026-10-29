# Hardware notes — new controls under evaluation

Context for anyone (or any Claude session) picking up the hardware work.
This records what we know about two controls being considered for the
panel, what is still unknown, and how we are testing them. Last updated
2026-10-29.

## The panel today

`arduino/sketch/sketch.ino` targets an Arduino Uno:

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

**The wires on our unit are labelled 5V, GND, RX1, TX1.** That suggests
one of two possibilities, not yet confirmed:

- **Serial (UART):** the spinner has its own microcontroller and sends
  data bytes. Then we need the baud rate and the packet format.
- **Quadrature A/B mislabelled as RX/TX:** two square waves whose phase
  gives direction. Then it needs two interrupt pins and a pulse counter.

**Why a Mega.** The Uno only has interrupts on pins 2 and 3, which the
exhibit sketch already uses for SW_R / SW_G. The Mega has Serial1 on pins
18 (TX1) / 19 (RX1), and those same pins are also interrupt pins, so it
covers both possibilities without rewiring.

### Test sketch: `arduino/spinner_test/spinner_test.ino`

Stand-alone diagnostic for the Mega, not part of the exhibit. It has not
been run on hardware yet.

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

1. Run `spinner_test` and record which mode produced data, the baud rate
   and a sample of the bytes. Add the results here.
2. Decide what the spinner and the motorized slider control in the
   exhibit (e.g. slider replaces POT_S; spinner role TBD).
3. If the exhibit moves to the Mega, update `sketch.ino`'s header and
   the serial line format (e.g. append a spinner delta `E:<counts>`), and
   update the parser in `arduino_bridge.py` to match.

## Sources

- ThunderStick Studios, GRS Arcade Spinner:
  https://thunderstickstudio.com/products/grs-arcade-spinner
- TS-USP02 listing (Glenn's Retro Show spinner page):
  https://sites.google.com/view/gregsqna2/gaming/arcadecontrols/spinner
- Arcade1Up spinner to PC thread:
  http://forum.arcadecontrols.com/index.php?topic=158675.0
