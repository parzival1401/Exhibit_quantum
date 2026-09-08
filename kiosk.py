"""
kiosk.py — Exhibition (final) presentation mode.

Development mode shows every control as a clickable button so the app can
be driven with a mouse. In the exhibition the visitor drives everything
from the physical Arduino panel, so those buttons are noise: they invite
clicks that the exhibit does not want, and they make the screens look
like a debugging tool instead of an installation.

apply_kiosk_mode() hides that chrome while leaving every code path
intact. Nothing is deleted — the buttons still exist and still work if
something calls click() on them; they are simply not shown. The actions
they performed remain reachable two ways:

  • Arduino hardware   — already wired in main.py (switches, pots, the
                         push and collapse buttons).
  • Keyboard commands  — installed here as a staff fallback so the
                         exhibit still runs if the Arduino is unplugged.

Keyboard commands (work from any of the three windows)
──────────────────────────────────────────────────────
  Window 1 — classical side
      R / G / B      toggle that colour channel
      P  or  Space   push the classical colour into the selected region

  Window 3 — quantum side
      ↑ ↓ ← →        move the palette selector
      [  /  ]        shrink / grow the selector (Δx, and so the speed)
      A              start / stop Heisenberg auto-move
      Enter          collapse the palette to a single colour
      Q              collapse and push into the selected region

  Staff
      Ctrl+S         save the artwork
      Ctrl+P         print the artwork
      Ctrl+G         return to the gallery
      Esc            leave kiosk mode (show the buttons again)
"""

from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtCore import Qt


# ─────────────────────────────────────────────────────────────────────────────
# Hiding chrome
# ─────────────────────────────────────────────────────────────────────────────

# The controls kiosk mode takes away, per window. Named in one place so
# hiding and the Esc restore can never drift apart. The gradient palette,
# the colour previews and the artwork itself are absent from these lists
# on purpose — those are the exhibit.
_W1_CHROME = ('btn_r', 'btn_g', 'btn_b', 'push_btn', 'rgb_label', 'status')

_W2_CHROME = ('save_btn', 'qr_btn', 'print_btn', 'choose_btn', 'back_btn')

_W3_CHROME = ('anim_btn', 'collapse_btn', 'push_btn', 'pots_btn',
              'slider', 'size_lbl', 'heis_lbl', 'stats_lbl')


def _hide(widget):
    """Hide a widget if the window actually has it (defensive: the UI is
    built in pieces and not every attribute exists on every page)."""
    if widget is not None:
        widget.hide()


def _show(widget):
    if widget is not None:
        widget.show()


def _hide_window1(w1):
    for name in _W1_CHROME:
        _hide(getattr(w1, name, None))


def _hide_window3(w3):
    for name in _W3_CHROME:
        _hide(getattr(w3, name, None))


def _hide_window2(w2):
    """Hide W2's staff buttons and the Staff menu bar."""
    for name in _W2_CHROME:
        _hide(getattr(w2, name, None))

    mb = w2.menuBar()
    if mb is not None:
        # setVisible(False), not hide(): on macOS the menu bar is the
        # native global bar, and a plain hide() cannot be undone by
        # show() when kiosk mode is exited.
        mb.setVisible(False)


# ─────────────────────────────────────────────────────────────────────────────
# Keyboard commands
# ─────────────────────────────────────────────────────────────────────────────

def _bind(window, key: str, handler):
    """Bind `key` on `window` to `handler`.

    ApplicationShortcut means the command fires no matter which of the
    three windows currently holds focus — the visitor (or a staff member)
    should not have to click a window first to make a key work.
    """
    sc = QShortcut(QKeySequence(key), window)
    sc.setContext(Qt.ShortcutContext.ApplicationShortcut)
    sc.activated.connect(handler)
    return sc


def _install_commands(w1, w2, w3, shortcuts: list):
    # ── Window 1 — classical colour ────────────────────────────────────
    # Drive the real buttons rather than reimplementing the toggle, so
    # the hidden button, AppState and the Arduino all stay in agreement.
    def toggle(channel: str):
        def handler():
            btn = getattr(w1, f'btn_{channel.lower()}')
            btn.setChecked(not btn.isChecked())
            w1._toggle(channel)
        return handler

    shortcuts.append(_bind(w1, 'R', toggle('R')))
    shortcuts.append(_bind(w1, 'G', toggle('G')))
    shortcuts.append(_bind(w1, 'B', toggle('B')))

    shortcuts.append(_bind(w1, 'P',     w1.state.request_push_rgb))
    shortcuts.append(_bind(w1, 'Space', w1.state.request_push_rgb))

    # ── Window 3 — quantum side ────────────────────────────────────────
    step = 5
    shortcuts.append(_bind(w3, 'Left',  lambda: w3.palette.move_selector(-step, 0)))
    shortcuts.append(_bind(w3, 'Right', lambda: w3.palette.move_selector( step, 0)))
    shortcuts.append(_bind(w3, 'Up',    lambda: w3.palette.move_selector(0, -step)))
    shortcuts.append(_bind(w3, 'Down',  lambda: w3.palette.move_selector(0,  step)))

    # Selector size drives Δx, and through it the auto-move speed. Go
    # through the slider so its value stays the single source of truth
    # even while it is hidden.
    def resize_selector(delta: int):
        def handler():
            w3.slider.setValue(w3.slider.value() + delta)
        return handler

    shortcuts.append(_bind(w3, '[', resize_selector(-10)))
    shortcuts.append(_bind(w3, ']', resize_selector( 10)))

    shortcuts.append(_bind(w3, 'A',      w3._toggle_animation))
    shortcuts.append(_bind(w3, 'Return', w3._do_collapse))
    shortcuts.append(_bind(w3, 'Enter',  w3._do_collapse))
    shortcuts.append(_bind(w3, 'Q',      w3.collapse_and_push))

    # ── Staff ──────────────────────────────────────────────────────────
    shortcuts.append(_bind(w2, 'Ctrl+S', w2._save_image))
    shortcuts.append(_bind(w2, 'Ctrl+P', w2._print_image))
    shortcuts.append(_bind(w2, 'Ctrl+G', w2._go_to_gallery))


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

def apply_kiosk_mode(w1, w2, w3, frameless: bool = True):
    """
    Switch the three windows into exhibition presentation.

    Hides the buttons and developer readouts, optionally drops the window
    title bars, and installs the keyboard commands listed in this
    module's docstring. Returns the shortcut objects, which the caller
    must keep a reference to — Qt deletes shortcuts that go out of scope.

    `frameless` is applied before the windows are shown; setting a window
    flag on a visible window would force it to re-show and could disturb
    the per-monitor placement done in main.py.
    """
    _hide_window1(w1)
    _hide_window2(w2)
    _hide_window3(w3)

    if frameless:
        for win in (w1, w2, w3):
            win.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)

    shortcuts: list = []
    _install_commands(w1, w2, w3, shortcuts)

    # Esc reveals the chrome again, so staff are never locked out of a
    # machine whose Arduino has failed.
    shortcuts.append(_bind(w2, 'Escape', lambda: _exit_kiosk(w1, w2, w3)))

    print('\n'
          '  ╔══════════════════════════════════════════════════════╗\n'
          '  ║   KIOSK MODE — buttons hidden, commands active       ║\n'
          '  ╠══════════════════════════════════════════════════════╣\n'
          '  ║  R / G / B   toggle channel      P / Space  push     ║\n'
          '  ║  ↑↓←→ move   [ ] resize          A  auto-move        ║\n'
          '  ║  Enter collapse                  Q  collapse+push    ║\n'
          '  ║  Ctrl+S save   Ctrl+P print      Ctrl+G gallery      ║\n'
          '  ║  Esc  exit kiosk mode (show buttons again)           ║\n'
          '  ╚══════════════════════════════════════════════════════╝\n')

    return shortcuts


def _exit_kiosk(w1, w2, w3):
    """Show the controls kiosk mode hid (staff escape hatch).

    Deliberately mirrors the _hide_window* lists rather than un-hiding
    every child widget: the stacked pages in Window 2 that are not
    current are also 'hidden', and showing those would break the layout.
    """
    for name in _W1_CHROME:
        _show(getattr(w1, name, None))
    for name in _W2_CHROME:
        _show(getattr(w2, name, None))
    for name in _W3_CHROME:
        _show(getattr(w3, name, None))

    mb = w2.menuBar()
    if mb is not None:
        mb.setVisible(True)

    print('  [kiosk] Exited kiosk mode — controls visible again.\n')
