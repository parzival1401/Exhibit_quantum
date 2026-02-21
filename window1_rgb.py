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
    QPushButton, QLabel, QFrame,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont


# ─────────────────────────────────────────────────────────────────────────────
# Helper: a single RGB channel toggle button
# ─────────────────────────────────────────────────────────────────────────────

_BTN_STYLE = """
QPushButton {{
    background-color : {off_bg};
    color            : {off_fg};
    border-radius    : 10px;
    border           : 2px solid {border};
    font-size        : 15px;
    font-weight      : bold;
    padding          : 6px 0px;
}}
QPushButton:checked {{
    background-color : {on_bg};
    color            : white;
    border           : 3px solid white;
}}
QPushButton:hover {{
    border-color     : #cccccc;
}}
"""


def _channel_button(label: str, off_bg: str, on_bg: str, border: str) -> QPushButton:
    btn = QPushButton(label)
    btn.setCheckable(True)
    btn.setMinimumHeight(70)
    btn.setFont(QFont('Arial', 13, QFont.Weight.Bold))
    btn.setStyleSheet(
        _BTN_STYLE.format(
            off_bg=off_bg, on_bg=on_bg, border=border, off_fg='#cccccc'
        )
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
        self.setFixedSize(300, 520)
        self._build_ui()

    # ── UI construction ──────────────────────────────────────────────────

    def _build_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setSpacing(12)
        layout.setContentsMargins(18, 18, 18, 18)

        # Title
        title = QLabel('Classical RGB Controller')
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setFont(QFont('Arial', 13, QFont.Weight.Bold))
        layout.addWidget(title)

        # ── Color preview ──────────────────────────────────────────────
        self.preview = QLabel()
        self.preview.setMinimumHeight(130)
        self.preview.setFrameShape(QFrame.Shape.Box)
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setFont(QFont('Courier', 15, QFont.Weight.Bold))
        layout.addWidget(self.preview)

        # ── RGB numeric label ──────────────────────────────────────────
        self.rgb_label = QLabel('R=0   G=0   B=0')
        self.rgb_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.rgb_label.setFont(QFont('Courier', 11))
        layout.addWidget(self.rgb_label)

        # ── Three toggle buttons ───────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        self.btn_r = _channel_button('R', '#5a1010', '#ff3333', '#aa2222')
        self.btn_g = _channel_button('G', '#0f4a0f', '#33cc44', '#228822')
        self.btn_b = _channel_button('B', '#0f1f5a', '#4477ff', '#2244cc')

        self.btn_r.clicked.connect(lambda: self._toggle('R'))
        self.btn_g.clicked.connect(lambda: self._toggle('G'))
        self.btn_b.clicked.connect(lambda: self._toggle('B'))

        btn_row.addWidget(self.btn_r)
        btn_row.addWidget(self.btn_g)
        btn_row.addWidget(self.btn_b)
        layout.addLayout(btn_row)

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

        # ── Status line ────────────────────────────────────────────────
        self.status = QLabel('All channels  OFF')
        self.status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status.setFont(QFont('Arial', 10))
        self.status.setStyleSheet('color: #888888;')
        layout.addWidget(self.status)

        layout.addStretch()

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

    # ── Preview repaint ───────────────────────────────────────────────────

    def _refresh_preview(self):
        r = 255 if self._channels.get('R') else 0
        g = 255 if self._channels.get('G') else 0
        b = 255 if self._channels.get('B') else 0

        # Perceptual luminance → decide text colour
        lum = 0.299 * r + 0.587 * g + 0.114 * b
        fg  = '#000000' if lum > 140 else '#ffffff'

        self.preview.setStyleSheet(
            f'background-color: rgb({r},{g},{b});'
            f'border: 2px solid #444;'
            f'color: {fg};'
        )
        self.preview.setText(f'({r}, {g}, {b})')
        self.rgb_label.setText(f'R={r:>3}   G={g:>3}   B={b:>3}')
