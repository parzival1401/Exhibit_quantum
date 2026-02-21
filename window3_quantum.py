"""
window3_quantum.py — Quantum Probability Palette (Window 3)

Layout
──────
  ┌─────────────────────────────────────────────┐
  │  [title + instructions]                     │
  │  ┌─────────────────────────────────────┐    │
  │  │  2-D HSV Gradient Palette           │    │
  │  │  (X = Hue 0→360°, Y = Value high→low│    │
  │  │   square selector drawn on top)     │    │
  │  └─────────────────────────────────────┘    │
  │  [Selector Size slider]                     │
  │  [⚡ Collapse button]                        │
  │  [Collapsed colour swatch + RGB label]      │
  │  [Distribution statistics text]             │
  └─────────────────────────────────────────────┘

Controls
────────
  ↑ ↓ ← →  Move the square selector (step = 5 px)
  Slider    Resize the square (10 … 150 px)
  Enter     Perform the Quantum Collapse and update Window 2 (right side)

Quantum Collapse algorithm  (see image_utils.quantum_collapse for details)
  1. Gather all pixels inside the selector square.
  2. Compute per-channel mean (μ) and std-dev (σ).
  3. Score each pixel via the joint Normal PDF:
       P(px) = ∏ₖ  exp(−½·((pxₖ−μₖ)/σₖ)²)
  4. Normalise scores → probability distribution.
  5. Weighted random sample → one pixel = the collapsed colour.
"""

import numpy as np

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QSlider, QFrame,
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QFont, QImage, QPixmap, QPainter, QPen, QColor

from image_utils import create_gradient_palette, quantum_collapse

# ── Palette canvas dimensions ─────────────────────────────────────────────────
PAL_W = 520
PAL_H = 290


# ─────────────────────────────────────────────────────────────────────────────
# Gradient palette widget
# ─────────────────────────────────────────────────────────────────────────────

class GradientPaletteWidget(QWidget):
    """
    Renders the HSV gradient and overlays a movable/resizable square selector.
    Key events are handled by the parent window and forwarded via the
    move_selector() / set_selector_size() methods.
    """

    def __init__(self, gradient_array: np.ndarray, parent=None):
        super().__init__(parent)
        self._gradient = gradient_array      # (PAL_H × PAL_W × 3) uint8 RGB
        self._pixmap   = self._build_pixmap()

        # Selector state (centre coordinates + half-size)
        self.sq_cx   = PAL_W // 2
        self.sq_cy   = PAL_H // 2
        self.sq_size = 50                    # side length in pixels

        self.setFixedSize(PAL_W, PAL_H)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    # ── Build backing pixmap from the gradient array ─────────────────────

    def _build_pixmap(self) -> QPixmap:
        arr  = np.ascontiguousarray(self._gradient, dtype=np.uint8)
        h, w, c = arr.shape
        qimg = QImage(arr.data, w, h, w * c, QImage.Format.Format_RGB888)
        return QPixmap.fromImage(qimg)

    # ── Public interface ──────────────────────────────────────────────────

    def move_selector(self, dx: int, dy: int):
        half = self.sq_size // 2
        self.sq_cx = max(half, min(PAL_W - half, self.sq_cx + dx))
        self.sq_cy = max(half, min(PAL_H - half, self.sq_cy + dy))
        self.update()

    def set_selector_size(self, size: int):
        self.sq_size = size
        # Re-clamp centre so the square stays inside the canvas
        half = size // 2
        self.sq_cx = max(half, min(PAL_W - half, self.sq_cx))
        self.sq_cy = max(half, min(PAL_H - half, self.sq_cy))
        self.update()

    def selected_pixels(self) -> np.ndarray:
        """Return the pixel sub-array currently inside the selector square."""
        half = self.sq_size // 2
        x1   = max(0, self.sq_cx - half)
        y1   = max(0, self.sq_cy - half)
        x2   = min(PAL_W, self.sq_cx + half)
        y2   = min(PAL_H, self.sq_cy + half)
        return self._gradient[y1:y2, x1:x2]

    # ── Paint ─────────────────────────────────────────────────────────────

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.drawPixmap(0, 0, self._pixmap)

        half = self.sq_size // 2
        x    = self.sq_cx - half
        y    = self.sq_cy - half
        sz   = self.sq_size

        # Outer white border (2 px)
        painter.setPen(QPen(QColor(255, 255, 255), 2, Qt.PenStyle.SolidLine))
        painter.drawRect(x, y, sz, sz)

        # Inner black dashed border (1 px, inset by 2)
        painter.setPen(QPen(QColor(0, 0, 0), 1, Qt.PenStyle.DashLine))
        painter.drawRect(x + 2, y + 2, sz - 4, sz - 4)

        painter.end()


# ─────────────────────────────────────────────────────────────────────────────
# Window 3
# ─────────────────────────────────────────────────────────────────────────────

class QuantumPaletteWindow(QMainWindow):

    def __init__(self, state):
        super().__init__()
        self.state          = state
        self._gradient      = create_gradient_palette(PAL_W, PAL_H)
        self._last_collapse = state.quantum_color   # remember last result

        self.setWindowTitle('Window 3 — Quantum Probability Palette')
        self.setFixedSize(560, 510)

        self._build_ui()
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setFocus()

    # ── UI construction ──────────────────────────────────────────────────

    def _build_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setSpacing(8)
        layout.setContentsMargins(16, 14, 16, 14)

        # Title
        title = QLabel('Quantum Probability Palette')
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setFont(QFont('Arial', 14, QFont.Weight.Bold))
        layout.addWidget(title)

        # Instructions
        info = QLabel('↑↓←→ Move  ·  Slider: Resize  ·  Enter / Button: Collapse')
        info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info.setFont(QFont('Arial', 9))
        info.setStyleSheet('color: #888888;')
        layout.addWidget(info)

        # ── Gradient palette ───────────────────────────────────────────
        self.palette = GradientPaletteWidget(self._gradient)
        # Centre it horizontally
        pal_row = QHBoxLayout()
        pal_row.addStretch()
        pal_row.addWidget(self.palette)
        pal_row.addStretch()
        layout.addLayout(pal_row)

        # ── Size slider row ────────────────────────────────────────────
        slider_row = QHBoxLayout()
        slider_row.setSpacing(10)

        lbl = QLabel('Selector size:')
        lbl.setFont(QFont('Arial', 10))
        slider_row.addWidget(lbl)

        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(10, 150)
        self.slider.setValue(50)
        self.slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.slider.setTickInterval(20)
        self.slider.valueChanged.connect(self._on_size_change)
        slider_row.addWidget(self.slider)

        self.size_lbl = QLabel('50 px')
        self.size_lbl.setFixedWidth(48)
        self.size_lbl.setFont(QFont('Arial', 10))
        slider_row.addWidget(self.size_lbl)

        layout.addLayout(slider_row)

        # ── Collapse button ────────────────────────────────────────────
        self.collapse_btn = QPushButton('⚡  Collapse  [Enter]')
        self.collapse_btn.setMinimumHeight(46)
        self.collapse_btn.setFont(QFont('Arial', 13, QFont.Weight.Bold))
        self.collapse_btn.setStyleSheet("""
            QPushButton {
                background-color : #3a2e7a;
                color            : #e8e0ff;
                border-radius    : 10px;
                border           : 2px solid #6a5fcc;
            }
            QPushButton:hover   { background-color : #4a3e9a; }
            QPushButton:pressed { background-color : #2a1e5a; }
        """)
        self.collapse_btn.clicked.connect(self._do_collapse)
        layout.addWidget(self.collapse_btn)

        # ── Result display row ─────────────────────────────────────────
        result_row = QHBoxLayout()
        result_row.setSpacing(10)

        collapsed_lbl = QLabel('Collapsed:')
        collapsed_lbl.setFont(QFont('Arial', 11))
        result_row.addWidget(collapsed_lbl)

        self.swatch = QLabel()
        self.swatch.setFixedSize(60, 36)
        self.swatch.setStyleSheet(
            'background-color: rgb(90,60,180); border: 2px solid #555;'
        )
        result_row.addWidget(self.swatch)

        self.result_lbl = QLabel('(90, 60, 180)')
        self.result_lbl.setFont(QFont('Courier', 12))
        result_row.addWidget(self.result_lbl)

        result_row.addStretch()
        layout.addLayout(result_row)

        # ── Statistics / distribution info ─────────────────────────────
        self.stats_lbl = QLabel(
            'Press Enter or click Collapse to sample a colour from the selection.'
        )
        self.stats_lbl.setFont(QFont('Arial', 9))
        self.stats_lbl.setStyleSheet('color: #888888;')
        self.stats_lbl.setWordWrap(True)
        layout.addWidget(self.stats_lbl)

    # ── Slider callback ───────────────────────────────────────────────────

    def _on_size_change(self, value: int):
        self.palette.set_selector_size(value)
        self.size_lbl.setText(f'{value} px')

    # ── Quantum Collapse ──────────────────────────────────────────────────

    def _do_collapse(self):
        region  = self.palette.selected_pixels()
        pixels  = region.reshape(-1, 3).astype(np.float64)

        if len(pixels) == 0:
            return

        # Statistics for the display label
        means = np.mean(pixels, axis=0)
        stds  = np.std(pixels,  axis=0)
        stds  = np.maximum(stds, 1.0)

        # Weighted sample via Normal distribution
        color = quantum_collapse(
            self._gradient,
            self.palette.sq_cx,
            self.palette.sq_cy,
            self.palette.sq_size,
        )

        # Push to shared state → Window 2 right panel updates immediately
        self.state.quantum_color = color
        self._last_collapse      = color

        # Update swatch + numeric label
        r, g, b = color
        self.swatch.setStyleSheet(
            f'background-color: rgb({r},{g},{b}); border: 2px solid #555;'
        )
        self.result_lbl.setText(f'({r:>3}, {g:>3}, {b:>3})')

        # Update statistics line
        n = len(pixels)
        self.stats_lbl.setText(
            f'Sampled from {n} pixels  ·  '
            f'μ = ({int(means[0])}, {int(means[1])}, {int(means[2])})  ·  '
            f'σ = ({int(stds[0])}, {int(stds[1])}, {int(stds[2])})'
        )

    # ── Keyboard handling ─────────────────────────────────────────────────

    def keyPressEvent(self, event):
        key  = event.key()
        step = 5

        if   key == Qt.Key.Key_Left:
            self.palette.move_selector(-step,  0)
        elif key == Qt.Key.Key_Right:
            self.palette.move_selector( step,  0)
        elif key == Qt.Key.Key_Up:
            self.palette.move_selector( 0, -step)
        elif key == Qt.Key.Key_Down:
            self.palette.move_selector( 0,  step)
        elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._do_collapse()
        else:
            super().keyPressEvent(event)
