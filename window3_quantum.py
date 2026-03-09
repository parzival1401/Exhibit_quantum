"""
window3_quantum.py — Quantum Probability Palette (Window 3)

Heisenberg Auto-Move
────────────────────
The square selector can move autonomously, obeying the Uncertainty Principle:

    Δx · Δp  ≥  ℏ/2

  Slider LEFT  (small square, small Δx)
    → momentum highly uncertain → FAST, ERRATIC, diffuse path

  Slider RIGHT (large square, large Δx)
    → momentum well-defined    → SLOW, SMOOTH, predictable drift

Implementation
──────────────
  A QTimer fires every TICK_MS milliseconds.
  Each tick:
    1. momentum_spread  = HBAR / sq_size          (our ℏ analogue)
    2. Add Gaussian noise to velocity:
          vx += N(0, momentum_spread · NOISE_SCALE)
    3. Apply damping (DAMP) to prevent runaway acceleration.
    4. Clamp ‖v‖ ≤ momentum_spread · SPEED_SCALE.
    5. Accumulate sub-pixel movement (float accumulators fx, fy).
    6. Move selector; reflect velocity component at any wall hit.

Arrow keys still work during auto-move to steer the path.
"""

import numpy as np

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QSlider, QFrame,
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QImage, QPixmap, QPainter, QPen, QColor

from image_utils import create_gradient_palette, quantum_collapse

# ── Palette canvas dimensions ─────────────────────────────────────────────────
PAL_W = 520
PAL_H = 290

# ── Heisenberg motion constants ───────────────────────────────────────────────
HBAR        = 700.0    # ℏ analogue  (Δx · Δp product target)
NOISE_SCALE = 0.10     # fraction of momentum_spread added as noise each tick
SPEED_SCALE = 0.38     # fraction of momentum_spread used as max speed cap
DAMP        = 0.88     # velocity damping per tick (< 1 prevents runaway)
TICK_MS     = 50       # timer interval in milliseconds  (20 fps)


# ─────────────────────────────────────────────────────────────────────────────
# Gradient palette widget
# ─────────────────────────────────────────────────────────────────────────────

class GradientPaletteWidget(QWidget):
    """
    Renders the HSV gradient and overlays a movable/resizable square selector.
    move_selector() returns (actual_dx, actual_dy) so the caller can detect
    wall collisions and reflect the velocity vector.
    """

    def __init__(self, gradient_array: np.ndarray, parent=None):
        super().__init__(parent)
        self._gradient = gradient_array
        self._pixmap   = self._build_pixmap()

        self.sq_cx   = PAL_W // 2
        self.sq_cy   = PAL_H // 2
        self.sq_size = 50

        self.setFixedSize(PAL_W, PAL_H)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    def _build_pixmap(self) -> QPixmap:
        arr  = np.ascontiguousarray(self._gradient, dtype=np.uint8)
        h, w, c = arr.shape
        qimg = QImage(arr.data, w, h, w * c, QImage.Format.Format_RGB888)
        return QPixmap.fromImage(qimg)

    def move_selector(self, dx: int, dy: int) -> tuple:
        """Move the selector and return the actual displacement applied."""
        half      = self.sq_size // 2
        old_cx    = self.sq_cx
        old_cy    = self.sq_cy
        self.sq_cx = max(half, min(PAL_W - half, self.sq_cx + dx))
        self.sq_cy = max(half, min(PAL_H - half, self.sq_cy + dy))
        self.update()
        return (self.sq_cx - old_cx, self.sq_cy - old_cy)

    def set_selector_size(self, size: int):
        self.sq_size = size
        half = size // 2
        self.sq_cx = max(half, min(PAL_W - half, self.sq_cx))
        self.sq_cy = max(half, min(PAL_H - half, self.sq_cy))
        self.update()

    def selected_pixels(self) -> np.ndarray:
        half = self.sq_size // 2
        x1 = max(0, self.sq_cx - half)
        y1 = max(0, self.sq_cy - half)
        x2 = min(PAL_W, self.sq_cx + half)
        y2 = min(PAL_H, self.sq_cy + half)
        return self._gradient[y1:y2, x1:x2]

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.drawPixmap(0, 0, self._pixmap)

        half = self.sq_size // 2
        x, y = self.sq_cx - half, self.sq_cy - half
        sz   = self.sq_size

        painter.setPen(QPen(QColor(255, 255, 255), 2, Qt.PenStyle.SolidLine))
        painter.drawRect(x, y, sz, sz)
        painter.setPen(QPen(QColor(0, 0, 0), 1, Qt.PenStyle.DashLine))
        painter.drawRect(x + 2, y + 2, sz - 4, sz - 4)
        painter.end()


# ─────────────────────────────────────────────────────────────────────────────
# Window 3
# ─────────────────────────────────────────────────────────────────────────────

class QuantumPaletteWindow(QMainWindow):

    def __init__(self, state):
        super().__init__()
        self.state         = state
        self._gradient     = create_gradient_palette(PAL_W, PAL_H)
        self._last_collapse = state.quantum_color

        # ── Heisenberg velocity state ──────────────────────────────────
        self._vx = 0.0     # current x velocity (pixels / tick, float)
        self._vy = 0.0     # current y velocity
        self._fx = 0.0     # sub-pixel x accumulator
        self._fy = 0.0     # sub-pixel y accumulator

        # ── Arduino potentiometer control flag ─────────────────────────
        self._pots_enabled = True

        # ── Animation timer ────────────────────────────────────────────
        self._timer = QTimer(self)
        self._timer.setInterval(TICK_MS)
        self._timer.timeout.connect(self._animate_step)
        self._animating = False

        self.setWindowTitle('Window 3 — Quantum Probability Palette')
        self.setFixedSize(560, 650)

        self._build_ui()
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setFocus()

    # ── UI construction ───────────────────────────────────────────────────

    def _build_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setSpacing(7)
        layout.setContentsMargins(16, 12, 16, 12)

        # Title
        title = QLabel('Quantum Probability Palette')
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setFont(QFont('Arial', 14, QFont.Weight.Bold))
        layout.addWidget(title)

        # Instructions
        info = QLabel(
            '↑↓←→ Move  ·  Slider: Size & Velocity  ·  Enter / ⚡: Collapse'
        )
        info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info.setFont(QFont('Arial', 9))
        info.setStyleSheet('color: #888888;')
        layout.addWidget(info)

        # Gradient palette
        self.palette = GradientPaletteWidget(self._gradient)
        pal_row = QHBoxLayout()
        pal_row.addStretch()
        pal_row.addWidget(self.palette)
        pal_row.addStretch()
        layout.addLayout(pal_row)

        # ── Size / velocity slider ─────────────────────────────────────
        slider_row = QHBoxLayout()
        slider_row.setSpacing(10)

        slider_row.addWidget(QLabel('Small\n(fast)'))

        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(10, 150)
        self.slider.setValue(50)
        self.slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.slider.setTickInterval(20)
        self.slider.valueChanged.connect(self._on_size_change)
        slider_row.addWidget(self.slider)

        slider_row.addWidget(QLabel('Large\n(slow)'))

        self.size_lbl = QLabel('50 px')
        self.size_lbl.setFixedWidth(48)
        self.size_lbl.setFont(QFont('Arial', 10))
        slider_row.addWidget(self.size_lbl)

        layout.addLayout(slider_row)

        # ── Heisenberg uncertainty display ─────────────────────────────
        self.heis_lbl = QLabel(self._heisenberg_text())
        self.heis_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.heis_lbl.setFont(QFont('Courier', 9))
        self.heis_lbl.setStyleSheet('color: #aaaaee;')
        layout.addWidget(self.heis_lbl)

        # ── Auto-Move toggle button ────────────────────────────────────
        self.anim_btn = QPushButton('⚛  Auto-Move  [Heisenberg]')
        self.anim_btn.setMinimumHeight(44)
        self.anim_btn.setFont(QFont('Arial', 11, QFont.Weight.Bold))
        self._style_anim_btn(False)
        self.anim_btn.clicked.connect(self._toggle_animation)
        layout.addWidget(self.anim_btn)

        # ── Collapse button ────────────────────────────────────────────
        self.collapse_btn = QPushButton('⚡  Collapse  [Enter]')
        self.collapse_btn.setMinimumHeight(44)
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

        # ── Push button ────────────────────────────────────────────────
        self.push_btn = QPushButton('▶  Push Color to Right Image')
        self.push_btn.setMinimumHeight(44)
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
        self.push_btn.clicked.connect(lambda: self.state.request_push_quantum())
        layout.addWidget(self.push_btn)

        # ── Result display ─────────────────────────────────────────────
        result_row = QHBoxLayout()
        result_row.setSpacing(10)

        result_row.addWidget(QLabel('Collapsed:'))

        self.swatch = QLabel()
        self.swatch.setFixedSize(60, 34)
        self.swatch.setStyleSheet(
            'background-color: rgb(90,60,180); border: 2px solid #555;'
        )
        result_row.addWidget(self.swatch)

        self.result_lbl = QLabel('(90, 60, 180)')
        self.result_lbl.setFont(QFont('Courier', 12))
        result_row.addWidget(self.result_lbl)

        result_row.addStretch()
        layout.addLayout(result_row)

        # Stats line
        self.stats_lbl = QLabel(
            'Press Enter or click Collapse to sample a colour.'
        )
        self.stats_lbl.setFont(QFont('Arial', 9))
        self.stats_lbl.setStyleSheet('color: #888888;')
        self.stats_lbl.setWordWrap(True)
        layout.addWidget(self.stats_lbl)

        # ── Arduino potentiometer toggle ───────────────────────────────
        self.pots_btn = QPushButton()
        self.pots_btn.setMinimumHeight(38)
        self.pots_btn.setFont(QFont('Arial', 10, QFont.Weight.Bold))
        self._style_pots_btn(True)
        self.pots_btn.clicked.connect(self._toggle_pots)
        layout.addWidget(self.pots_btn)

    # ── Arduino potentiometer enable / disable ────────────────────────────

    def _style_pots_btn(self, enabled: bool):
        if enabled:
            self.pots_btn.setText('🎛  Arduino Pots  [ON]')
            self.pots_btn.setStyleSheet("""
                QPushButton {
                    background-color : #1a4a2a;
                    color            : #88ffaa;
                    border-radius    : 8px;
                    border           : 2px solid #3a8a4a;
                }
                QPushButton:hover   { background-color : #2a5a3a; }
                QPushButton:pressed { background-color : #0a3a1a; }
            """)
        else:
            self.pots_btn.setText('🎛  Arduino Pots  [OFF]')
            self.pots_btn.setStyleSheet("""
                QPushButton {
                    background-color : #3a2a2a;
                    color            : #aa6666;
                    border-radius    : 8px;
                    border           : 2px solid #6a3a3a;
                }
                QPushButton:hover   { background-color : #4a3a3a; }
                QPushButton:pressed { background-color : #2a1a1a; }
            """)

    def _toggle_pots(self):
        self._pots_enabled = not self._pots_enabled
        self._style_pots_btn(self._pots_enabled)
        state_str = 'enabled' if self._pots_enabled else 'disabled'
        self.stats_lbl.setText(f'Arduino potentiometers {state_str}.')

    # ── Arduino hardware input ─────────────────────────────────────────────

    _POT_DEADBAND  = 8     # raw ADC units of change to consider a pot "moving"
    _last_raw_x    = 512   # last seen raw values (initialised to mid-range)
    _last_raw_y    = 512
    _last_raw_s    = 512

    def apply_pots(self, raw_x: int, raw_y: int, raw_size: int):
        """
        Called by ArduinoBridge every ~50 ms.

        Deadband is checked against the PREVIOUS raw pot reading, not against
        the selector position.  This means:
          • Stationary pot → no override; Heisenberg auto-move runs freely.
          • Actively turned pot → stop auto-move and take absolute control of X/Y.
          • Size pot always updates the slider (works alongside auto-move).
        """
        if not self._pots_enabled:
            return

        pots_moving = (
            abs(raw_x - self._last_raw_x) > self._POT_DEADBAND or
            abs(raw_y - self._last_raw_y) > self._POT_DEADBAND
        )
        self._last_raw_x = raw_x
        self._last_raw_y = raw_y
        self._last_raw_s = raw_size

        new_size = 10 + int(raw_size / 1023 * (150 - 10))

        if pots_moving:
            # User is turning X/Y pots → stop animation and move to pot position
            if self._animating:
                self._toggle_animation()
            self.palette.sq_cx = int(raw_x / 1023 * (PAL_W - 1))
            self.palette.sq_cy = int(raw_y / 1023 * (PAL_H - 1))
        # else: pots are idle → let animation (or keyboard) control X/Y freely

        # Size pot always applies (controls Heisenberg speed when animating)
        self.palette.sq_size = new_size
        self.palette.update()
        self.slider.setValue(new_size)

    # ── Heisenberg helpers ─────────────────────────────────────────────────

    def _momentum_spread(self) -> float:
        """Δp  =  ℏ / Δx  (our uncertainty-principle analogue)."""
        return HBAR / max(1, self.palette.sq_size)

    def _heisenberg_text(self) -> str:
        sq  = self.palette.sq_size if hasattr(self, 'palette') else 50
        dp  = HBAR / sq
        return (
            f'Δx = {sq:>4} px   ·   Δp ≈ {dp:>6.1f}   ·   '
            f'Δx·Δp = {sq * dp:.0f}  (ℏ = {HBAR:.0f})'
        )

    def _style_anim_btn(self, running: bool):
        if running:
            self.anim_btn.setText('⏸  Pause Auto-Move')
            self.anim_btn.setStyleSheet("""
                QPushButton {
                    background-color : #6a2e8a;
                    color            : #f0d0ff;
                    border-radius    : 10px;
                    border           : 2px solid #aa60dd;
                }
                QPushButton:hover   { background-color : #7a3e9a; }
                QPushButton:pressed { background-color : #5a1e7a; }
            """)
        else:
            self.anim_btn.setText('⚛  Auto-Move  [Heisenberg]')
            self.anim_btn.setStyleSheet("""
                QPushButton {
                    background-color : #2a3a2a;
                    color            : #99dd99;
                    border-radius    : 10px;
                    border           : 2px solid #4a7a4a;
                }
                QPushButton:hover   { background-color : #3a4a3a; }
                QPushButton:pressed { background-color : #1a2a1a; }
            """)

    # ── Animation control ──────────────────────────────────────────────────

    def _toggle_animation(self):
        if self._animating:
            self._timer.stop()
            self._animating = False
            self._style_anim_btn(False)
            self.stats_lbl.setText('Auto-Move paused.')
        else:
            # Give a small initial kick in a random direction
            dp = self._momentum_spread()
            self._vx = np.random.uniform(-dp * 0.2, dp * 0.2)
            self._vy = np.random.uniform(-dp * 0.2, dp * 0.2)
            self._fx = 0.0
            self._fy = 0.0
            self._timer.start()
            self._animating = True
            self._style_anim_btn(True)

    # ── Heisenberg animation step ──────────────────────────────────────────

    def _animate_step(self):
        """
        Called every TICK_MS ms.

        Physics (Heisenberg-inspired):
          momentum_spread  =  HBAR / sq_size          [Δp ∝ 1/Δx]
          noise per tick   ~  N(0,  momentum_spread · NOISE_SCALE)
          max speed        =  momentum_spread · SPEED_SCALE
          damping per tick =  DAMP  (prevents infinite acceleration)

        Large square → momentum_spread small → slow, smooth path.
        Small square → momentum_spread large → fast, erratic path.
        """
        dp        = self._momentum_spread()
        max_speed = dp * SPEED_SCALE

        # Add uncertainty noise to velocity (Heisenberg kick)
        self._vx += np.random.normal(0.0, dp * NOISE_SCALE)
        self._vy += np.random.normal(0.0, dp * NOISE_SCALE)

        # Damping
        self._vx *= DAMP
        self._vy *= DAMP

        # Clamp to max speed
        speed = np.hypot(self._vx, self._vy)
        if speed > max_speed and speed > 0:
            self._vx = self._vx / speed * max_speed
            self._vy = self._vy / speed * max_speed

        # Accumulate sub-pixel displacement
        self._fx += self._vx
        self._fy += self._vy

        dx = int(self._fx)
        dy = int(self._fy)
        self._fx -= dx
        self._fy -= dy

        # Move and detect boundary hits → reflect velocity
        actual_dx, actual_dy = self.palette.move_selector(dx, dy)
        if dx != 0 and actual_dx == 0:
            self._vx = -self._vx
            self._fx = 0.0
        if dy != 0 and actual_dy == 0:
            self._vy = -self._vy
            self._fy = 0.0

        # Live uncertainty display
        self.heis_lbl.setText(self._heisenberg_text())

    # ── Slider callback ────────────────────────────────────────────────────

    def _on_size_change(self, value: int):
        self.palette.set_selector_size(value)
        self.size_lbl.setText(f'{value} px')
        self.heis_lbl.setText(self._heisenberg_text())

    # ── Quantum Collapse ───────────────────────────────────────────────────

    def _do_collapse(self):
        region = self.palette.selected_pixels()
        pixels = region.reshape(-1, 3).astype(np.float64)
        if len(pixels) == 0:
            return

        means = np.mean(pixels, axis=0)
        stds  = np.maximum(np.std(pixels, axis=0), 1.0)

        color = quantum_collapse(
            self._gradient,
            self.palette.sq_cx,
            self.palette.sq_cy,
            self.palette.sq_size,
        )

        self.state.quantum_color = color
        self._last_collapse      = color

        r, g, b = color
        self.swatch.setStyleSheet(
            f'background-color: rgb({r},{g},{b}); border: 2px solid #555;'
        )
        self.result_lbl.setText(f'({r:>3}, {g:>3}, {b:>3})')
        self.stats_lbl.setText(
            f'n={len(pixels)}  ·  '
            f'μ=({int(means[0])},{int(means[1])},{int(means[2])})  ·  '
            f'σ=({int(stds[0])},{int(stds[1])},{int(stds[2])})'
        )

    # ── Keyboard ───────────────────────────────────────────────────────────

    def keyPressEvent(self, event):
        key  = event.key()
        step = 5
        if   key == Qt.Key.Key_Left:
            self.palette.move_selector(-step, 0)
        elif key == Qt.Key.Key_Right:
            self.palette.move_selector( step, 0)
        elif key == Qt.Key.Key_Up:
            self.palette.move_selector(0, -step)
        elif key == Qt.Key.Key_Down:
            self.palette.move_selector(0,  step)
        elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._do_collapse()
        else:
            super().keyPressEvent(event)
