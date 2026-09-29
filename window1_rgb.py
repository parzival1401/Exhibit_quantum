"""
window1_rgb.py — Classical RGB Controller (Window 1)

Three checkable toggle buttons: Red · Green · Blue.
  ON  → channel value 255
  OFF → channel value 0

The composite (R, G, B) is written to AppState in real-time, which
immediately triggers a repaint in Window 2's left panel.
"""

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QSizePolicy,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont


# ─────────────────────────────────────────────────────────────────────────────
# Helper: a single RGB channel toggle button
# ─────────────────────────────────────────────────────────────────────────────

# A channel lamp: dim and grey when the channel is off, saturated with a
# glowing ring when it is on, so which channels are contributing to the
# mix is readable at a glance from across the room.
_BTN_STYLE = """
QPushButton {{
    background-color : {off_bg};
    color            : #777777;
    border-radius    : 40px;
    border           : 3px solid {border};
    font-size        : 30px;
    font-weight      : bold;
}}
QPushButton:checked {{
    background-color : {on_bg};
    color            : #ffffff;
    border           : 5px solid #ffffff;
}}
QPushButton:hover {{
    border-color     : #cccccc;
}}
"""

_LAMP_SIZE = 80     # diameter of a channel lamp, in pixels


def _channel_button(label: str, off_bg: str, on_bg: str, border: str) -> QPushButton:
    btn = QPushButton(label)
    btn.setCheckable(True)
    btn.setFixedSize(_LAMP_SIZE, _LAMP_SIZE)
    btn.setFont(QFont('Arial', 22, QFont.Weight.Bold))
    btn.setStyleSheet(
        _BTN_STYLE.format(off_bg=off_bg, on_bg=on_bg, border=border)
    )
    return btn


# ─────────────────────────────────────────────────────────────────────────────
# Window 1
# ─────────────────────────────────────────────────────────────────────────────

class RGBControllerWindow(QMainWindow):
    def __init__(self, state):
        super().__init__()
        self.state = state
        self._channels = {'R': False, 'G': False, 'B': False}

        self.setWindowTitle('Window 1 — Classical RGB Controller')
        self.resize(300, 520)
        self._build_ui()

    # ── UI construction ──────────────────────────────────────────────────

    def _build_ui(self):
        """
        The colour is the whole screen: no title, no read-out, nothing
        written on it. The mixed colour fills the window and the three
        channel lamps sit in a bar centred along the bottom.

        The lamps are the toggle buttons themselves rather than separate
        indicators: one widget per channel means the lit state and the
        click target can never disagree, and the Arduino switches drive
        the same widget through apply_switches().
        """
        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)

        # ── The colour field — takes every spare pixel ─────────────────
        # Transparent and textless: the window itself is painted with the
        # colour, and this just claims the space above the lamp bar.
        self.preview = QLabel()
        self.preview.setSizePolicy(QSizePolicy.Policy.Expanding,
                                   QSizePolicy.Policy.Expanding)
        layout.addWidget(self.preview, stretch=1)

        # ── Channel lamp bar, centred along the bottom ─────────────────
        self.btn_r = _channel_button('R', '#5a1010', '#ff3333', '#aa2222')
        self.btn_g = _channel_button('G', '#0f4a0f', '#33cc44', '#228822')
        self.btn_b = _channel_button('B', '#0f1f5a', '#4477ff', '#2244cc')

        self.btn_r.clicked.connect(lambda: self._toggle('R'))
        self.btn_g.clicked.connect(lambda: self._toggle('G'))
        self.btn_b.clicked.connect(lambda: self._toggle('B'))

        lamp_row = QHBoxLayout()
        lamp_row.setSpacing(18)
        lamp_row.addStretch()
        for btn in (self.btn_r, self.btn_g, self.btn_b):
            lamp_row.addWidget(btn)
        lamp_row.addStretch()

        lamp_bar = QWidget()
        lamp_bar.setLayout(lamp_row)
        lamp_row.setContentsMargins(20, 14, 20, 20)
        # Dark strip so the lamps stay readable whatever colour is mixed.
        lamp_bar.setStyleSheet('background-color: rgba(0, 0, 0, 150);')
        layout.addWidget(lamp_bar)

        # Kept for the code that still reads them (kiosk mode hides these,
        # and _refresh_preview writes to rgb_label), but no longer shown
        # in their own rows — the numbers live inside the preview now.
        self.rgb_label = QLabel()
        self.status    = QLabel()
        self.rgb_label.hide()
        self.status.hide()

        # ── Push button ────────────────────────────────────────────────
        self.push_btn = QPushButton('▶  Push Color to Left Image')
        self.push_btn.setMinimumHeight(46)
        self.push_btn.setFont(QFont('Arial', 11, QFont.Weight.Bold))
        self.push_btn.setStyleSheet("""
            QPushButton {
                background-color : #1a4a6a;
                color            : #aaddff;
                border-radius    : 10px;
                border           : 2px solid #2a6a9a;
            }
            QPushButton:hover   { background-color : #2a5a7a; }
            QPushButton:pressed { background-color : #0a3a5a; }
        """)
        self.push_btn.clicked.connect(lambda: self.state.request_push_rgb())
        layout.addWidget(self.push_btn)

        # Initial render
        self._refresh_preview()

    # ── Toggle logic ─────────────────────────────────────────────────────

    def _toggle(self, ch: str):
        btn_map = {'R': self.btn_r, 'G': self.btn_g, 'B': self.btn_b}
        self._channels[ch] = btn_map[ch].isChecked()
        self._push_state()

    def _push_state(self):
        r = 255 if self._channels['R'] else 0
        g = 255 if self._channels['G'] else 0
        b = 255 if self._channels['B'] else 0

        # Write to shared state → triggers Window 2 update via signal
        self.state.rgb_color = (r, g, b)
        self._refresh_preview()

        active = [ch for ch, on in self._channels.items() if on]
        self.status.setText(
            'Active: ' + ' + '.join(active) if active else 'All channels  OFF'
        )

    # ── Arduino hardware input ────────────────────────────────────────────

    def apply_switches(self, r: bool, g: bool, b: bool):
        """Called by ArduinoBridge — mirrors physical switch state onto the UI."""
        self._channels = {'R': r, 'G': g, 'B': b}
        self.btn_r.setChecked(r)
        self.btn_g.setChecked(g)
        self.btn_b.setChecked(b)
        self._push_state()   # updates AppState + refreshes preview

    # ── Preview repaint ───────────────────────────────────────────────────

    # Switching channels fully on or off can only ever produce these eight
    # colours, so they can simply be named.
    _COLOUR_NAMES = {
        (0,   0,   0  ): 'Black',
        (255, 0,   0  ): 'Red',
        (0,   255, 0  ): 'Green',
        (0,   0,   255): 'Blue',
        (255, 255, 0  ): 'Yellow',
        (255, 0,   255): 'Magenta',
        (0,   255, 255): 'Cyan',
        (255, 255, 255): 'White',
    }

    def _colour_name(self, r: int, g: int, b: int) -> str:
        return self._COLOUR_NAMES.get((r, g, b), '')

    def _refresh_preview(self):
        r = 255 if self._channels.get('R') else 0
        g = 255 if self._channels.get('G') else 0
        b = 255 if self._channels.get('B') else 0

        # The colour goes on the window, not on the preview, so it runs
        # edge to edge behind the lamp bar. The preview stays transparent
        # and empty — the screen shows the colour and nothing else.
        self.setStyleSheet(
            f'QMainWindow {{ background-color: rgb({r},{g},{b}); }}'
        )

        # Kept up to date for the hidden labels other code still reads.
        self.rgb_label.setText(f'R={r:>3}   G={g:>3}   B={b:>3}')
        self.status.setText(self._colour_name(r, g, b))
