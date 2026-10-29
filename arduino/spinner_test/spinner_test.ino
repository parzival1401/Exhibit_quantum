/*
  spinner_test.ino — TS-USP02 Arcade Spinner Diagnostic (Arduino Mega)
  =====================================================================

  A stand-alone test, not part of the exhibit. It only answers one
  question: what does the spinner send on its RX1 / TX1 wires?

  Wiring (Arduino Mega)
  ---------------------
    Spinner 5V   → Mega 5V
    Spinner GND  → Mega GND
    Spinner TX1  → Mega pin 19 (RX1)
    Spinner RX1  → Mega pin 18 (TX1)

  If the labels on the spinner are from the Mega's point of view, the
  two signal wires are swapped. RAW mode below tells you which wire is
  actually talking, so start there.

  Modes (type a letter in the Serial Monitor, 115200 baud, then Enter)
  --------------------------------------------------------------------
    r  RAW mode (start-up default). Pins 18 and 19 are plain inputs —
       nothing is driven, so it is safe whichever way round the wires
       are. Every 250 ms it prints:
         - the level of each pin (UART idles HIGH)
         - how many edges each pin saw
         - a quadrature count, in case the wires are really A/B
         - the shortest pulse on each pin and the baud rate it implies
       Turn the spinner and watch. A pin with fast, short pulses and an
       estimated baud near a standard value is a serial line. Both pins
       toggling with similar edge counts and a count that goes up one
       way and down the other is a quadrature encoder.

    u  UART mode. Opens Serial1 at the current baud and prints every
       byte the spinner sends, in hex and ASCII, 16 bytes per line.
    b  Next baud rate in the list (works in either mode).
    h  Print this help again.
*/

const int PIN_TX1 = 18;   // Mega TX1 — goes to spinner RX1
const int PIN_RX1 = 19;   // Mega RX1 — goes to spinner TX1

const long BAUDS[] = {9600, 19200, 38400, 57600, 115200, 250000,
                      4800, 2400, 1200, 31250};
const int  N_BAUDS = sizeof(BAUDS) / sizeof(BAUDS[0]);
int baudIndex = 0;

enum Mode { RAW, UART };
Mode mode = RAW;

// ── RAW mode state, written by the interrupts ────────────────────────
volatile unsigned long edges18 = 0, edges19 = 0;
volatile unsigned long last18 = 0,  last19 = 0;
volatile unsigned long min18 = 0xFFFFFFFF, min19 = 0xFFFFFFFF;
volatile long quadCount = 0;
volatile uint8_t quadState = 0;

// Quadrature lookup: index is (previous AB << 2) | current AB.
// +1 / -1 for a valid step, 0 for no change or a skipped (invalid) step.
const int8_t QUAD_TABLE[16] = { 0, -1,  1,  0,
                                1,  0,  0, -1,
                               -1,  0,  0,  1,
                                0,  1, -1,  0 };

void updateQuad() {
  uint8_t ab = (digitalRead(PIN_TX1) << 1) | digitalRead(PIN_RX1);
  quadCount += QUAD_TABLE[(quadState << 2) | ab];
  quadState = ab;
}

void isr18() {
  unsigned long now = micros();
  unsigned long w = now - last18;
  if (w < min18) min18 = w;
  last18 = now;
  edges18++;
  updateQuad();
}

void isr19() {
  unsigned long now = micros();
  unsigned long w = now - last19;
  if (w < min19) min19 = w;
  last19 = now;
  edges19++;
  updateQuad();
}

// ── UART mode state ──────────────────────────────────────────────────
byte lineBuf[16];
int  lineLen = 0;
unsigned long lastByteMs = 0;
unsigned long totalBytes = 0;

unsigned long lastReportMs = 0;

void printHelp() {
  Serial.println();
  Serial.println(F("=== TS-USP02 spinner test ==="));
  Serial.println(F("  r = RAW mode (watch pins 18/19, safe default)"));
  Serial.println(F("  u = UART mode (print bytes from Serial1)"));
  Serial.println(F("  b = next baud rate"));
  Serial.println(F("  h = this help"));
  Serial.print(F("Mode: "));
  Serial.print(mode == RAW ? F("RAW") : F("UART"));
  Serial.print(F("   Baud: "));
  Serial.println(BAUDS[baudIndex]);
  Serial.println();
}

void startRaw() {
  Serial1.end();
  pinMode(PIN_TX1, INPUT_PULLUP);
  pinMode(PIN_RX1, INPUT_PULLUP);

  noInterrupts();
  edges18 = edges19 = 0;
  min18 = min19 = 0xFFFFFFFF;
  last18 = last19 = micros();
  quadCount = 0;
  quadState = (digitalRead(PIN_TX1) << 1) | digitalRead(PIN_RX1);
  interrupts();

  attachInterrupt(digitalPinToInterrupt(PIN_TX1), isr18, CHANGE);
  attachInterrupt(digitalPinToInterrupt(PIN_RX1), isr19, CHANGE);
  mode = RAW;
  Serial.println(F(">> RAW mode"));
}

void startUart() {
  detachInterrupt(digitalPinToInterrupt(PIN_TX1));
  detachInterrupt(digitalPinToInterrupt(PIN_RX1));
  Serial1.end();
  Serial1.begin(BAUDS[baudIndex]);
  lineLen = 0;
  totalBytes = 0;
  mode = UART;
  Serial.print(F(">> UART mode at "));
  Serial.println(BAUDS[baudIndex]);
}

// Print the buffered bytes as "HEX ... | ascii".
void flushLine() {
  if (lineLen == 0) return;
  for (int i = 0; i < 16; i++) {
    if (i < lineLen) {
      if (lineBuf[i] < 0x10) Serial.print('0');
      Serial.print(lineBuf[i], HEX);
      Serial.print(' ');
    } else {
      Serial.print(F("   "));
    }
  }
  Serial.print(F("| "));
  for (int i = 0; i < lineLen; i++) {
    char c = (char)lineBuf[i];
    Serial.print((c >= 32 && c < 127) ? c : '.');
  }
  Serial.println();
  lineLen = 0;
}

void reportRaw() {
  noInterrupts();
  unsigned long e18 = edges18, e19 = edges19;
  unsigned long m18 = min18,   m19 = min19;
  long q = quadCount;
  min18 = min19 = 0xFFFFFFFF;   // shortest pulse is per report window
  interrupts();

  Serial.print(F("pin18="));  Serial.print(digitalRead(PIN_TX1));
  Serial.print(F(" pin19=")); Serial.print(digitalRead(PIN_RX1));
  Serial.print(F(" | edges18=")); Serial.print(e18);
  Serial.print(F(" edges19="));   Serial.print(e19);
  Serial.print(F(" | quad="));    Serial.print(q);

  Serial.print(F(" | min18="));
  if (m18 == 0xFFFFFFFF) Serial.print('-');
  else { Serial.print(m18); Serial.print(F("us ~")); Serial.print(1000000UL / max(m18, 1UL)); Serial.print(F("bd")); }

  Serial.print(F(" min19="));
  if (m19 == 0xFFFFFFFF) Serial.print('-');
  else { Serial.print(m19); Serial.print(F("us ~")); Serial.print(1000000UL / max(m19, 1UL)); Serial.print(F("bd")); }

  Serial.println();
}

void handleCommand(char c) {
  switch (c) {
    case 'r': case 'R': startRaw();  break;
    case 'u': case 'U': startUart(); break;
    case 'b': case 'B':
      baudIndex = (baudIndex + 1) % N_BAUDS;
      Serial.print(F(">> Baud now "));
      Serial.println(BAUDS[baudIndex]);
      if (mode == UART) startUart();
      break;
    case 'h': case 'H': case '?': printHelp(); break;
    default: break;   // ignore Enter / newline characters
  }
}

void setup() {
  Serial.begin(115200);   // USB to the computer
  while (!Serial) {}      // no-op on the Mega, harmless elsewhere
  startRaw();
  printHelp();
}

void loop() {
  while (Serial.available()) handleCommand(Serial.read());

  if (mode == RAW) {
    if (millis() - lastReportMs >= 250) {
      lastReportMs = millis();
      reportRaw();
    }
  } else {
    while (Serial1.available()) {
      lineBuf[lineLen++] = Serial1.read();
      totalBytes++;
      lastByteMs = millis();
      if (lineLen == 16) flushLine();
    }
    // A pause in the data ends the line, so separate packets stay apart.
    if (lineLen > 0 && millis() - lastByteMs > 50) flushLine();

    if (millis() - lastReportMs >= 2000) {
      lastReportMs = millis();
      if (totalBytes == 0) {
        Serial.print(F("(no bytes yet at "));
        Serial.print(BAUDS[baudIndex]);
        Serial.println(F(" — turn the spinner, or press b)"));
      }
    }
  }
}
