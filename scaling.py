"""
scaling.py — Uniform content scale-up helper for fixed-size windows.

Window 1 (RGB Controller) and Window 3 (Quantum Palette) are built at a
fixed pixel design size. When a window is placed full-screen on a
monitor (see main.py._place_windows), we want that entire design —
buttons, fonts, the palette canvas — to scale up together and fill the
screen, rather than sitting fixed-size in a corner.

apply_uniform_scaling() re-parents a QMainWindow's existing central
widget into a QGraphicsScene via a QGraphicsProxyWidget, and fits that
scene to the view on every resize (KeepAspectRatio), so the whole
design grows/shrinks as one image while every widget inside keeps
working exactly as before (clicks, hover, focus, etc. all pass through
the proxy untouched).
"""

from PyQt6.QtWidgets import (
    QGraphicsScene, QGraphicsView, QGraphicsProxyWidget,
)
from PyQt6.QtGui import QPainter, QColor
from PyQt6.QtCore import Qt

import theme


class _ScalingView(QGraphicsView):
    """QGraphicsView that keeps its scene fit to the viewport on resize."""

    def __init__(self, scene: QGraphicsScene, parent=None):
        super().__init__(scene, parent)
        self.setRenderHints(QPainter.RenderHint.Antialiasing |
                             QPainter.RenderHint.SmoothPixmapTransform)
        self.setFrameShape(QGraphicsView.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.fitInView(self.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)


def apply_uniform_scaling(window, design_size=None):
    """
    Wrap `window`'s current central widget so its fixed design layout
    scales up/down as one unit to fill the window.

    `design_size` is the canvas the layout is built on. Give it the
    screen's shape (main.py passes 960×540, half of 1920×1080) and the
    design fills the screen edge to edge, at exactly 2× on a Full HD
    monitor. Without it the window's current size is used, and a design
    of another shape is letterboxed with bars at the sides.

    Call this AFTER the window's _build_ui() has run and setFixedSize()
    has been removed (the window must be resizable for scaling to have
    any effect).
    """
    content = window.centralWidget()
    if design_size is None:
        design_size = content.sizeHint() if content.size().isEmpty() else content.size()

    content.setParent(None)
    content.resize(design_size)

    scene = QGraphicsScene()
    proxy = QGraphicsProxyWidget()
    proxy.setWidget(content)
    scene.addItem(proxy)
    scene.setSceneRect(0, 0, design_size.width(), design_size.height())

    # Let whatever is painted behind the scene show through the design.
    # A window that paints its own background (Window 1's colour canvas)
    # would otherwise be covered by an opaque content widget.
    content.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
    content.setAutoFillBackground(False)

    view = _ScalingView(scene)

    # The view covers the window, so the window's own background cannot
    # show through it. Start it on the shared ground; a window that paints
    # its own canvas overwrites this from repaint_background().
    ground = QColor(theme.BG_DEEP)
    view.setBackgroundBrush(ground)
    scene.setBackgroundBrush(ground)

    window.setCentralWidget(view)
    return view
