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

Colour canvas
─────────────
With the controls gone, both side screens become the colour itself: the
whole window background is painted with the live value, so the classical
and quantum colours read across the room instead of from a small swatch.
Window 1 follows the RGB switches; Window 3 previews the colour under the
selector as it moves and snaps to the sampled value on collapse.
"""

from PyQt6.QtWidgets import QGraphicsView
from PyQt6.QtGui import QKeySequence, QShortcut, QColor
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
# Colour canvas — the whole window becomes the colour
# ─────────────────────────────────────────────────────────────────────────────

def _readable_ink(r: int, g: int, b: int) -> str:
    """Black or white text, whichever stays legible on this background.

    Same perceptual-luminance rule Window 1 already uses for its swatch,
    so the two agree on where the light/dark boundary falls.
    """
    return '#000000' if (0.299 * r + 0.587 * g + 0.114 * b) > 140 else '#ffffff'


def _paint_window(win, color):
    """Paint `win`'s background with `color` and keep its text legible.

    Three surfaces have to agree, because in full-screen mode the window
    is wrapped by scaling.apply_uniform_scaling():

      • the window itself      — the plain, unwrapped case;
      • the scaling view       — it covers the window when wrapped;
      • the scene behind it    — the design keeps its aspect ratio, so on
                                 a 16:9 screen there is empty space at the
                                 sides that would otherwise stay grey.

    The window rule is restricted to QMainWindow so it cannot leak into
    child widgets — the gradient palette must keep drawing its own pixels.
    """
    r, g, b = (int(v) for v in color)
    ink = _readable_ink(r, g, b)
    qcolor = QColor(r, g, b)

    win.setStyleSheet(
        f'QMainWindow {{ background-color: rgb({r},{g},{b}); }}'
    )

    central = win.centralWidget()
    if isinstance(central, QGraphicsView):
        central.setBackgroundBrush(qcolor)
        scene = central.scene()
        if scene is not None:
            scene.setBackgroundBrush(qcolor)

    # Labels are transparent by default but inherit no colour, so recolour
    # the ones that sit directly on the canvas.
    for lbl in getattr(win, '_canvas_labels', ()):
        if lbl is not None:
            lbl.setStyleSheet(f'color: {ink}; background: transparent;')


def _install_canvas(w1, w3):
    """Make both side windows paint themselves with their live colour."""

    # ── Window 1 — follows the RGB switches ────────────────────────────
    # The title is the only text left on this screen once the controls
    # are hidden, so it is the only label that needs recolouring.
    w1._canvas_labels = [c for c in w1.findChildren(type(w1.rgb_label))
                         if c is not w1.preview]

    def paint_w1(color):
        _paint_window(w1, color)

    w1.state.rgb_color_changed.connect(paint_w1)
    paint_w1(w1.state.rgb_color)

    # ── Window 3 — previews under the selector, snaps on collapse ──────
    w3._canvas_labels = [c for c in w3.findChildren(type(w3.result_lbl))
                         if c is not w3.swatch]

    def mean_under_selector():
        """Average colour of the pixels the selector currently covers.

        A preview, deliberately not a collapse: it is the mean, with no
        random sampling, so moving the selector shows where the colour
        would come from without pre-empting the collapse itself.
        """
        region = w3.palette.selected_pixels()
        if region.size == 0:
            return None
        return tuple(int(v) for v in region.reshape(-1, 3).mean(axis=0))

    def preview():
        color = mean_under_selector()
        if color is not None:
            _paint_window(w3, color)

    # move_selector() is the single place the selector position changes —
    # arrow keys, the Arduino pots and the Heisenberg animation all route
    # through it, so wrapping it catches every kind of movement.
    original_move = w3.palette.move_selector

    def move_and_preview(dx, dy):
        moved = original_move(dx, dy)
        preview()
        return moved

    w3.palette.move_selector = move_and_preview

    # Resizing the selector changes which pixels it covers too.
    original_set_size = w3.palette.set_selector_size

    def set_size_and_preview(size):
        original_set_size(size)
        preview()

    w3.palette.set_selector_size = set_size_and_preview

    # The Arduino pots assign sq_cx/sq_cy/sq_size straight onto the
    # palette instead of going through the methods above, so the preview
    # has to be hooked at apply_pots as well or hardware movement — the
    # exhibit's main input — would leave the canvas stale.
    #
    # This is a hook on the window rather than a replacement of the bound
    # method: main.py has already connected pots_changed to the original
    # w3.apply_pots by the time kiosk mode runs, and Qt holds on to that
    # original, so reassigning the attribute here would never be called.
    w3._kiosk_after_pots = preview

    # The collapse result overrides the preview until the next movement.
    w3.state.quantum_color_changed.connect(lambda c: _paint_window(w3, c))

    # Exposed so main.py can repaint once the windows have been placed:
    # full-screen placement wraps them in a scaling view that does not
    # exist yet, and a canvas painted only now would miss it.
    w1._kiosk_repaint = lambda: paint_w1(w1.state.rgb_color)
    w3._kiosk_repaint = preview

    preview()


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

    # After the controls are gone, give the emptied side screens over to
    # the colour itself.
    _install_canvas(w1, w3)

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


def repaint_canvas(*windows):
    """Repaint the colour canvas on any of `windows` that has one.

    Call after the windows are placed: full-screen placement re-parents
    the content into a scaling view, and the canvas has to be applied to
    that view as well as to the window.
    """
    for win in windows:
        hook = getattr(win, '_kiosk_repaint', None)
        if hook is not None:
            hook()


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
