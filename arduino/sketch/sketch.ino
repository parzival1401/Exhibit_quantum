/*
  sketch.ino — Quantum Color Exhibit Hardware Controller (Arduino Mega)
  ======================================================================

  Wiring
  ------
  Window 1 — RGB toggle switches (active LOW with INPUT_PULLUP):
    SW_R    → pin 2   (Red   channel)
    SW_G    → pin 3   (Green channel)
    SW_B    → pin 4   (Blue  channel)

  Action switches (momentary, active LOW with INPUT_PULLUP):
    SW_PUSH → pin 5   (Push classical RGB colour to left image)
    SW_COL  → pin 6   (Collapse quantum + push to right image)

  Window 3 — selector:
    POT_S   → A2      Size / Heisenberg slider (wiper to A2, ends to 5V / GND)

    Two TS-USP02 spinners move the selector, one per axis. Each has one
    output line per direction that pulses LOW once per step (see
    arduino/HARDWARE_NOTES.md). Power both from the bottom plug's 5V / GND;
    leave its RX1 / TX1 unconnected. Signals come from the 6-pin top plug:
      Spinner 1 (X):  top pin 4 (right) → pin 18,  top pin 5 (left) → pin 19
      Spinner 2 (Y):  top pin 4 (right) → pin 20,  top pin 5 (left) → pin 21
    To reverse an axis, swap that spinner's two signal wires.

    The X / Y knobs the spinners replaced were on A0 / A1; nothing is read
    there now.

  Serial protocol
  ---------------
  One line per loop iteration at 115200 baud:

      S:1,0,1,0,0,A:0,0,80,E:3,-1\n

      S: switch states  R, G, B, Push, Collapse  (1 = pressed, 0 = released)
      A: X, Y, Size — X and Y are always 0 (no knobs); Size is raw ADC 0–1023.
         The slots stay so the line keeps the same shape as before.
      E: spinner steps since the previous line, X then Y
         (right steps minus left steps; negative means it turned left)

  Upload steps
  ------------
  1. Open Arduino IDE, open arduino/sketch/sketch.ino.
  2. Select Tools → Board → Arduino Mega or Mega 2560, and the right port.
  3. Upload.
  4. Run  python main.py  — it will auto-detect the port and connect.
*/

const int SW_R    = 2;
const int SW_G    = 3;
const int SW_B    = 4;
const int SW_PUSH = 5;   // push classical RGB → left image
const int SW_COL  = 6;   // collapse quantum   → right image
const int POT_S   = A2;

// Spinner lines, in the order of the counters below. 18–21 are external
// interrupt pins on the Mega, so no step is missed between loop passes.
const int SPIN1_R = 18;
const int SPIN1_L = 19;
const int SPIN2_R = 20;
const int SPIN2_L = 21;
const int SPIN_PINS[4] = {SPIN1_R, SPIN1_L, SPIN2_R, SPIN2_L};

// A real step is a LOW pulse of 0.5 ms or 8 ms (set by the spinner's DIP
// switch 3). Anything shorter is contact noise and is not counted.
const unsigned long MIN_PULSE_US = 200;

volatile int           spinCount[4] = {0, 0, 0, 0};   // steps since last line
volatile bool          spinLow[4]   = {false, false, false, false};
volatile unsigned long spinFell[4]  = {0, 0, 0, 0};

// Count a step when a line comes back HIGH after a long-enough LOW pulse.
void spinEdge(int i) {
  unsigned long now = micros();
  if (digitalRead(SPIN_PINS[i]) == LOW) {
    spinLow[i]  = true;
    spinFell[i] = now;
  } else if (spinLow[i]) {
    spinLow[i] = false;
    if (now - spinFell[i] >= MIN_PULSE_US) spinCount[i]++;
  }
}

void isrSpin1R() { spinEdge(0); }
void isrSpin1L() { spinEdge(1); }
void isrSpin2R() { spinEdge(2); }
void isrSpin2L() { spinEdge(3); }

void setup() {
  Serial.begin(115200);

  // INPUT_PULLUP: pin reads HIGH when switch is open, LOW when pressed
  pinMode(SW_R,    INPUT_PULLUP);
  pinMode(SW_G,    INPUT_PULLUP);
  pinMode(SW_B,    INPUT_PULLUP);
  pinMode(SW_PUSH, INPUT_PULLUP);
  pinMode(SW_COL,  INPUT_PULLUP);

  // The spinner outputs only pull LOW, so they need the pull-ups too
  for (int i = 0; i < 4; i++) pinMode(SPIN_PINS[i], INPUT_PULLUP);
  attachInterrupt(digitalPinToInterrupt(SPIN1_R), isrSpin1R, CHANGE);
  attachInterrupt(digitalPinToInterrupt(SPIN1_L), isrSpin1L, CHANGE);
  attachInterrupt(digitalPinToInterrupt(SPIN2_R), isrSpin2R, CHANGE);
  attachInterrupt(digitalPinToInterrupt(SPIN2_L), isrSpin2L, CHANGE);
}

void loop() {
  // Switches: invert because INPUT_PULLUP means LOW = pressed
  int r  = !digitalRead(SW_R);
  int g  = !digitalRead(SW_G);
  int b  = !digitalRead(SW_B);
  int p  = !digitalRead(SW_PUSH);
  int c  = !digitalRead(SW_COL);

  // Size slider: raw 0–1023
  int as_ = analogRead(POT_S);

  // Spinners: take the steps counted since the last line and start again
  noInterrupts();
  int ex = spinCount[0] - spinCount[1];
  int ey = spinCount[2] - spinCount[3];
  for (int i = 0; i < 4; i++) spinCount[i] = 0;
  interrupts();

  // Send one CSV line: "S:1,0,1,0,0,A:0,0,80,E:3,-1"
  Serial.print("S:");
  Serial.print(r);  Serial.print(",");
  Serial.print(g);  Serial.print(",");
  Serial.print(b);  Serial.print(",");
  Serial.print(p);  Serial.print(",");
  Serial.print(c);
  Serial.print(",A:0,0,");
  Serial.print(as_);
  Serial.print(",E:");
  Serial.print(ex); Serial.print(",");
  Serial.println(ey);

  delay(50);   // ~20 Hz — matches the app's TICK_MS
}
