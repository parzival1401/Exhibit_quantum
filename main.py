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
from PyQt6.QtGui import QPalette, QColor, QFont

from app_state        import AppState
from window1_rgb      import RGBControllerWindow
from window2_image    import ImageProcessorWindow
from window3_quantum  import QuantumPaletteWindow
from arduino_bridge   import ArduinoBridge
from scaling          import apply_uniform_scaling
from kiosk            import apply_kiosk_mode, repaint_canvas


# ─────────────────────────────────────────────────────────────────────────────
# Exhibition (final) presentation
# ─────────────────────────────────────────────────────────────────────────────
# False → development: every control is a visible, clickable button.
# True  → exhibition:  buttons and developer readouts are hidden and the
#                      exhibit is driven by the Arduino panel, with the
#                      keyboard commands in kiosk.py as a staff fallback.
#                      Press Esc to bring the controls back.
KIOSK_MODE = True

# Drop the window title bars in kiosk mode. Turn this off if the exhibit
# machine's window manager needs the title bar to place windows.
KIOSK_FRAMELESS = True


# ─────────────────────────────────────────────────────────────────────────────
# Manual screen assignment (exhibit / multi-monitor mode)
# ─────────────────────────────────────────────────────────────────────────────
# Only used when 3+ monitors are detected. Screens are sorted left-to-right
# by physical X position and indexed 0, 1, 2, ... — run this file once and
# check the console printout (or set IDENTIFY_SCREENS = True below) to see
# each index's position/resolution, then edit these to route windows to
# whichever physical monitor you want.
SCREEN_FOR_W1 = 0   # Classical RGB Controller
SCREEN_FOR_W2 = 1   # Dual-View Image Processor
SCREEN_FOR_W3 = 2   # Quantum Probability Palette

# Set True to print each detected screen's index/position/resolution and
# briefly flash its index full-screen on itself, then exit — use this to
# figure out which physical monitor is which index before wiring the
# SCREEN_FOR_W* constants above.
IDENTIFY_SCREENS = False



# ─────────────────────────────────────────────────────────────────────────────
# Dark-theme palette (applied globally via QApplication)
# ─────────────────────────────────────────────────────────────────────────────

def _install_font_substitutions():
    """Map the font names used in the UI onto fonts that exist per OS.

    The windows ask for 'Arial' and 'Courier'. Neither is guaranteed:
    macOS has no 'Courier' family under that name (Qt warns and falls
    back), and Linux has neither unless the MS fonts are installed.
    Registering substitutes here fixes every call site at once, so the
    exhibit looks the same on Windows, macOS and the Raspberry Pi.
    """
    QFont.insertSubstitutions('Arial', [
        'Arial', 'Helvetica Neue', 'Helvetica',      # Windows / macOS
        'Segoe UI', 'DejaVu Sans', 'Liberation Sans',  # Windows / Linux
        'Noto Sans', 'sans-serif',
    ])
    QFont.insertSubstitutions('Courier', [
        'Courier New', 'Menlo', 'Monaco',            # Windows / macOS
        'Consolas', 'DejaVu Sans Mono',              # Windows / Linux
        'Liberation Mono', 'Noto Sans Mono', 'monospace',
    ])


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
# Multi-monitor detection
# ─────────────────────────────────────────────────────────────────────────────

def _sorted_screens(app: QApplication) -> list:
    """Return connected screens sorted left-to-right by physical X position.

    Sorting by position (rather than OS plug/detection order) makes screen
    index 0 always the leftmost monitor and the last index always the
    rightmost, regardless of which order the OS happens to report them in.
    """
    return sorted(app.screens(), key=lambda s: s.availableGeometry().left())


def _print_screens(screens: list):
    print('\n  [display] Detected screens (index : name : position : resolution)')
    for i, s in enumerate(screens):
        g = s.geometry()
        print(f'    {i} : {s.name()} : ({g.left()}, {g.top()}) : {g.width()}x{g.height()}')
    print()


def _identify_screens(app: QApplication, screens: list):
    """Briefly flash each screen's index full-screen on itself, for wiring
    up SCREEN_FOR_W1/W2/W3. Blocks for a few seconds per screen, then exits.
    """
    from PyQt6.QtWidgets import QLabel
    from PyQt6.QtCore import Qt, QTimer

    _print_screens(screens)

    labels = []
    for i, s in enumerate(screens):
        lbl = QLabel(str(i))
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet('background-color: black; color: white; font-size: 200px;')
        lbl.setGeometry(s.geometry())
        lbl.showFullScreen()
        labels.append(lbl)

    QTimer.singleShot(4000, app.quit)
    sys.exit(app.exec())


def _show_on_screen(win, screen):
    """Show `win` full-screen on `screen`.

    setGeometry() alone is not enough: showFullScreen() asks the window
    system to fill "the window's screen", and until the window has been
    shown it is still associated with the primary screen — so a second
    window would snap back onto the primary display and leave its own
    monitor empty. Creating the native handle first (via show()) lets us
    hand the window to the right screen before going full-screen, which
    is also the path that behaves consistently on Windows.
    """
    geo = screen.geometry()
    win.setGeometry(geo)
    win.show()                       # create the native window handle

    handle = win.windowHandle()
    if handle is not None:
        handle.setScreen(screen)     # bind it to the intended monitor

    win.setGeometry(geo)             # re-apply: setScreen can move the window
    win.showFullScreen()


def _place_windows(app: QApplication, w1, w2, w3):
    """Place the three windows across the detected monitors.

    3+ screens connected → one window full-screen per monitor, routed via
                            SCREEN_FOR_W1/W2/W3 (exhibit / kiosk mode).
    <3 screens connected  → fall back to today's side-by-side tiling on a
                            single screen (desktop / dev mode) — unchanged.
    """
    screens = _sorted_screens(app)
    _print_screens(screens)

    if len(screens) >= 3:
        # W1 and W3 are built at a fixed design size — scale that whole
        # design up to fill the screen. W2 already re-renders its image
        # panels on resize (see ImageProcessorWindow.resizeEvent), so it
        # scales natively and needs no wrapper.
        apply_uniform_scaling(w1)
        apply_uniform_scaling(w3)

        assignments = [
            (w1, SCREEN_FOR_W1),
            (w2, SCREEN_FOR_W2),
            (w3, SCREEN_FOR_W3),
        ]
        for win, idx in assignments:
            _show_on_screen(win, screens[idx])
        print(f'  [display] {len(screens)} monitors detected — fullscreen per window '
              f'(W1→screen {SCREEN_FOR_W1}, W2→screen {SCREEN_FOR_W2}, W3→screen {SCREEN_FOR_W3}).\n')
        return

    # ── Fallback: tile on one screen (original behaviour, unchanged) ──────
    screen_rect = screens[0].availableGeometry() if screens else app.primaryScreen().availableGeometry()
    top_y       = max(80, screen_rect.top() + 80)

    w1.move(screen_rect.left() + 20, top_y)

    w1_right = screen_rect.left() + 20 + w1.width() + 14
    w2.move(w1_right, top_y)

    w3.move(w1_right + w2.width() + 14, top_y)

    w1.show()
    w2.show()
    w3.show()

    print(f'  [display] {len(screens)} monitor(s) detected — tiling side-by-side on one screen.\n')


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

def main():
    app = QApplication(sys.argv)
    app.setApplicationName('Quantum Color PoC')
    # Fusion is the one style that renders identically on every OS; the
    # native Windows and macOS styles ignore parts of the stylesheets the
    # windows rely on.
    app.setStyle('Fusion')
    app.setPalette(_dark_palette())
    _install_font_substitutions()

    if IDENTIFY_SCREENS:
        _identify_screens(app, _sorted_screens(app))
        return  # _identify_screens exits the process itself

    # Shared state: the single source of truth for both live colours
    state = AppState()

    # Instantiate windows
    w1 = RGBControllerWindow(state)
    w2 = ImageProcessorWindow(state)
    w3 = QuantumPaletteWindow(state)

    # ── Arduino physical controls ──────────────────────────────────────────
    # Auto-detects the Arduino USB port. If none is found, the app runs
    # normally in software-only mode (no error, just a console message).
    bridge = ArduinoBridge()
    bridge.switches_changed.connect(w1.apply_switches)          # 3 RGB switches → W1
    bridge.pots_changed.connect(w3.apply_pots)                  # 3 pots → W3 selector
    bridge.push_rgb_pressed.connect(state.request_push_rgb)     # SW_PUSH → left image
    bridge.collapse_pressed.connect(w3.collapse_and_push)       # SW_COL  → collapse + right image
    bridge.start()

    # ── Exhibition presentation ───────────────────────────────────────────
    # Applied before the windows are shown: the frameless flag re-shows a
    # window if it is set later, which would fight the placement below.
    # The shortcuts are parked on `app` because Qt destroys shortcut
    # objects that get garbage collected, which would silently kill every
    # keyboard command.
    if KIOSK_MODE:
        app._kiosk_shortcuts = apply_kiosk_mode(
            w1, w2, w3, frameless=KIOSK_FRAMELESS
        )

    # ── Position windows: fullscreen per monitor (3+ screens) or tiled ─────
    _place_windows(app, w1, w2, w3)

    if KIOSK_MODE:
        # Placement may have wrapped the side windows in a scaling view,
        # which the canvas painted before placement would not have reached.
        repaint_canvas(w1, w3)

    # Give Window 3 keyboard focus so arrow-keys work immediately
    w3.setFocus()
    w3.raise_()

    if not KIOSK_MODE:
        # In kiosk mode the command list printed by apply_kiosk_mode()
        # already says how to drive the exhibit, and these button-based
        # instructions would contradict it.
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
