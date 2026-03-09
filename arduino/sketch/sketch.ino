/*
  sketch.ino — Quantum Color Exhibit Hardware Controller
  ========================================================

  Wiring
  ------
  Window 1 — RGB toggle switches (active LOW with INPUT_PULLUP):
    SW_R    → pin 2   (Red   channel)
    SW_G    → pin 3   (Green channel)
    SW_B    → pin 4   (Blue  channel)

  Action switches (momentary, active LOW with INPUT_PULLUP):
    SW_PUSH → pin 5   (Push classical RGB colour to left image)
    SW_COL  → pin 6   (Collapse quantum + push to right image)

  Window 3 — Potentiometers (wiper to analog pin, ends to 5V / GND):
    POT_X → A0  (selector square X position)
    POT_Y → A1  (selector square Y position)
    POT_S → A2  (selector square Size / Heisenberg slider)

  Serial protocol
  ---------------
  One line per loop iteration at 115200 baud:

      S:1,0,1,0,0,A:512,256,80\n

      S: switch states  R, G, B, Push, Collapse  (1 = pressed, 0 = released)
      A: potentiometer  X, Y, Size  (raw ADC value 0–1023)

  Upload steps
  ------------
  1. Open Arduino IDE, open arduino/sketch/sketch.ino.
  2. Select your board (e.g. Arduino Uno) and the correct COM / /dev/cu port.
  3. Upload.
  4. Run  python main.py  — it will auto-detect the port and connect.
*/

const int SW_R    = 2;
const int SW_G    = 3;
const int SW_B    = 4;
const int SW_PUSH = 5;   // push classical RGB → left image
const int SW_COL  = 6;   // collapse quantum   → right image
const int POT_X   = A0;
const int POT_Y   = A1;
const int POT_S   = A2;

void setup() {
  Serial.begin(115200);

  // INPUT_PULLUP: pin reads HIGH when switch is open, LOW when pressed
  pinMode(SW_R,    INPUT_PULLUP);
  pinMode(SW_G,    INPUT_PULLUP);
  pinMode(SW_B,    INPUT_PULLUP);
  pinMode(SW_PUSH, INPUT_PULLUP);
  pinMode(SW_COL,  INPUT_PULLUP);
}

void loop() {
  // Switches: invert because INPUT_PULLUP means LOW = pressed
  int r  = !digitalRead(SW_R);
  int g  = !digitalRead(SW_G);
  int b  = !digitalRead(SW_B);
  int p  = !digitalRead(SW_PUSH);
  int c  = !digitalRead(SW_COL);

  // Potentiometers: raw 0–1023
  int ax  = analogRead(POT_X);
  int ay  = analogRead(POT_Y);
  int as_ = analogRead(POT_S);

  // Send one CSV line: "S:1,0,1,0,0,A:512,256,80"
  Serial.print("S:");
  Serial.print(r);  Serial.print(",");
  Serial.print(g);  Serial.print(",");
  Serial.print(b);  Serial.print(",");
  Serial.print(p);  Serial.print(",");
  Serial.print(c);
  Serial.print(",A:");
  Serial.print(ax); Serial.print(",");
  Serial.print(ay); Serial.print(",");
  Serial.println(as_);

  delay(50);   // ~20 Hz — matches the app's TICK_MS
}
