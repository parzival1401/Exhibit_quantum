"""
arduino_bridge.py — Physical Hardware Bridge (Arduino via USB Serial)

Reads from an Arduino that sends one CSV line every ~50 ms:
    S:1,0,1,A:512,256,80

    S: switch states  R, G, B  (0 or 1)
    A: potentiometer  X, Y, Size  (0–1023 each)

Emits two Qt signals that the windows connect to:
    switches_changed(r: bool, g: bool, b: bool)   → Window 1 toggle buttons
    pots_changed(x: int, y: int, size: int)        → Window 3 selector / slider

The bridge runs in a daemon thread so it never blocks the UI.
If no Arduino is found the app starts normally with a console warning.
"""

import threading

from PyQt6.QtCore import QObject, pyqtSignal


def _auto_detect_port() -> str | None:
    """Scan serial ports and return the first that looks like an Arduino."""
    try:
        import serial.tools.list_ports
        for p in serial.tools.list_ports.comports():
            desc   = (p.description or '').lower()
            device = (p.device or '').lower()
            if ('arduino' in desc or 'ch340' in desc or
                    'ch341' in desc or 'usbmodem' in device or
                    'usbserial' in device):
                return p.device
    except Exception:
        pass
    return None


class ArduinoBridge(QObject):
    """
    Connects to an Arduino over USB serial and translates hardware
    input into Qt signals consumable by the GUI windows.
    """

    # Emitted whenever RGB switch states change — payload: (R_on, G_on, B_on)
    switches_changed = pyqtSignal(bool, bool, bool)

    # Emitted whenever potentiometer values arrive — payload: raw 0-1023 each
    pots_changed = pyqtSignal(int, int, int)   # x, y, size

    # Emitted on the rising edge of each action button (momentary press)
    push_rgb_pressed  = pyqtSignal()   # SW_PUSH → push classical colour to left image
    collapse_pressed  = pyqtSignal()   # SW_COL  → collapse quantum + push to right image

    def __init__(self, port: str = None, baud: int = 115200):
        super().__init__()
        self._port     = port or _auto_detect_port()
        self._baud     = baud
        self._running  = False
        self._thread   = None
        self._ser      = None

        # Remember last switch state to avoid redundant signals
        self._last_sw   = (False, False, False)
        # Rising-edge tracking for action buttons
        self._last_push = False
        self._last_col  = False

    # ── Public API ────────────────────────────────────────────────────────

    def start(self):
        """Open the serial port and start the background reader thread."""
        if not self._port:
            print('[Arduino] No Arduino port detected — running in software-only mode')
            return

        try:
            import serial
            self._ser     = serial.Serial(self._port, self._baud, timeout=1)
            self._running = True
            self._thread  = threading.Thread(
                target=self._read_loop, daemon=True, name='ArduinoReader'
            )
            self._thread.start()
            print(f'[Arduino] Connected on {self._port} @ {self._baud} baud')
        except Exception as exc:
            print(f'[Arduino] Could not open {self._port}: {exc}')
            print('[Arduino] Running in software-only mode')

    def stop(self):
        """Stop the reader thread and close the serial port."""
        self._running = False
        if self._ser:
            try:
                self._ser.close()
            except Exception:
                pass

    # ── Internal reader loop ──────────────────────────────────────────────

    def _read_loop(self):
        while self._running:
            try:
                raw  = self._ser.readline()
                line = raw.decode('ascii', errors='ignore').strip()
                if not line:
                    continue
                self._parse_line(line)
            except Exception:
                pass   # silently ignore malformed lines / read errors

    def _parse_line(self, line: str):
        """
        Parse 'S:1,0,1,0,0,A:512,256,80' and emit the appropriate signals.
        Both sections must be present; missing or malformed lines are dropped.

        S: five switch values — R, G, B, Push, Collapse
        A: three pot values   — X, Y, Size  (0–1023 raw ADC)

        push_rgb_pressed / collapse_pressed fire only on the rising edge
        (button goes from released → pressed) to avoid repeated triggers.
        """
        try:
            if 'S:' not in line or 'A:' not in line:
                return

            s_raw, a_raw = line.split('S:')[1].split(',A:')
            vals = [int(v) for v in s_raw.split(',')]
            sr, sg, sb = vals[0], vals[1], vals[2]
            sp = vals[3] if len(vals) > 3 else 0   # SW_PUSH (backwards-compat)
            sc = vals[4] if len(vals) > 4 else 0   # SW_COL  (backwards-compat)
            ax, ay, az = (int(v) for v in a_raw.split(','))

            # RGB toggles — emit only on state change
            r, g, b = bool(sr), bool(sg), bool(sb)
            if (r, g, b) != self._last_sw:
                self._last_sw = (r, g, b)
                self.switches_changed.emit(r, g, b)

            # Action buttons — emit only on rising edge (press, not hold)
            push = bool(sp)
            col  = bool(sc)
            if push and not self._last_push:
                self.push_rgb_pressed.emit()
            if col and not self._last_col:
                self.collapse_pressed.emit()
            self._last_push = push
            self._last_col  = col

            # Always emit pot values (windows apply their own deadband)
            self.pots_changed.emit(
                max(0, min(1023, ax)),
                max(0, min(1023, ay)),
                max(0, min(1023, az)),
            )

        except Exception:
            pass   # drop malformed lines silently
