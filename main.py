"""
main.py — Quantum-Inspired Color & Image PoC  (entry point)

Run:
    python main.py

Dependencies (install once):
    pip install -r requirements.txt

Three synchronized windows open side-by-side:

  Window 1 (left)   Classical RGB Controller
      • Toggle R / G / B buttons to build a composite colour (0 or 255 per channel).
      • The active colour is sent live to Window 2's LEFT panel.

  Window 2 (centre) Dual-View Image Processor
      • Auto-generates (or loads) a paint-by-numbers template on first run.
      • LEFT  side → template filled with the Classical RGB colour.
      • RIGHT side → template filled with the Quantum Collapsed colour.
      • Both sides update instantly whenever their source colour changes.

  Window 3 (right)  Quantum Probability Palette
      • Displays a 2-D HSV colour gradient (X = Hue, Y = Brightness).
      • Arrow keys move the square selector; slider resizes it.
      • Pressing Enter (or the Collapse button) reads all pixels in the square,
        models them as a joint Normal distribution, and performs a weighted
        random sample → the "Collapsed" colour.
      • The collapsed colour is sent live to Window 2's RIGHT panel.
"""

import sys
import os

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QPalette, QColor

from app_state        import AppState
from window1_rgb      import RGBControllerWindow
from window2_image    import ImageProcessorWindow
from window3_quantum  import QuantumPaletteWindow


# ─────────────────────────────────────────────────────────────────────────────
# Dark-theme palette (applied globally via QApplication)
# ─────────────────────────────────────────────────────────────────────────────

def _dark_palette() -> QPalette:
    p = QPalette()
    p.setColor(QPalette.ColorRole.Window,          QColor(42,  42,  42 ))
    p.setColor(QPalette.ColorRole.WindowText,      QColor(220, 220, 220))
    p.setColor(QPalette.ColorRole.Base,            QColor(28,  28,  28 ))
    p.setColor(QPalette.ColorRole.AlternateBase,   QColor(45,  45,  45 ))
    p.setColor(QPalette.ColorRole.Text,            QColor(220, 220, 220))
    p.setColor(QPalette.ColorRole.BrightText,      QColor(255, 255, 255))
    p.setColor(QPalette.ColorRole.Button,          QColor(55,  55,  55 ))
    p.setColor(QPalette.ColorRole.ButtonText,      QColor(220, 220, 220))
    p.setColor(QPalette.ColorRole.Highlight,       QColor(90,  70,  180))
    p.setColor(QPalette.ColorRole.HighlightedText, QColor(255, 255, 255))
    p.setColor(QPalette.ColorRole.ToolTipBase,     QColor(55,  55,  55 ))
    p.setColor(QPalette.ColorRole.ToolTipText,     QColor(220, 220, 220))
    return p


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

def main():
    app = QApplication(sys.argv)
    app.setApplicationName('Quantum Color PoC')
    app.setStyle('Fusion')
    app.setPalette(_dark_palette())

    # Shared state: the single source of truth for both live colours
    state = AppState()

    # Instantiate windows
    w1 = RGBControllerWindow(state)
    w2 = ImageProcessorWindow(state)
    w3 = QuantumPaletteWindow(state)

    # ── Position windows side-by-side ─────────────────────────────────────
    screen_rect = app.primaryScreen().availableGeometry()
    top_y       = max(80, screen_rect.top() + 80)

    # Window 1: fixed at left
    w1.move(screen_rect.left() + 20, top_y)

    # Window 2: to the right of W1
    w1_right = screen_rect.left() + 20 + w1.width() + 14
    w2.move(w1_right, top_y)

    # Window 3: to the right of W2
    w3.move(w1_right + w2.width() + 14, top_y)

    w1.show()
    w2.show()
    w3.show()

    # Give Window 3 keyboard focus so arrow-keys work immediately
    w3.setFocus()
    w3.raise_()

    print('\n'
          '  ╔══════════════════════════════════════════════════════╗\n'
          '  ║   Quantum Color PoC  — All three windows are open   ║\n'
          '  ╠══════════════════════════════════════════════════════╣\n'
          '  ║  Window 1  Toggle R / G / B to set classical colour  ║\n'
          '  ║  Window 2  Live dual-view image fill                 ║\n'
          '  ║  Window 3  ↑↓←→ move • Slider resize • Enter=Collapse║\n'
          '  ╚══════════════════════════════════════════════════════╝\n')

    sys.exit(app.exec())
    


if __name__ == '__main__':
    main()
