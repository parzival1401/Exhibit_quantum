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
from PyQt6.QtGui import QPainter
from PyQt6.QtCore import Qt


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


def apply_uniform_scaling(window):
    """
    Wrap `window`'s current central widget so its fixed design layout
    scales up/down as one unit to fill the window.

    Call this AFTER the window's _build_ui() has run and setFixedSize()
    has been removed (the window must be resizable for scaling to have
    any effect).
    """
    content = window.centralWidget()
    design_size = content.sizeHint() if content.size().isEmpty() else content.size()

    content.setParent(None)
    content.resize(design_size)

    scene = QGraphicsScene()
    proxy = QGraphicsProxyWidget()
    proxy.setWidget(content)
    scene.addItem(proxy)
    scene.setSceneRect(0, 0, design_size.width(), design_size.height())

    # Let whatever is painted behind the scene show through the design.
    # Kiosk mode paints the window/scene with the live colour, and an
    # opaque content widget would sit on top of it as a grey slab.
    content.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
    content.setAutoFillBackground(False)

    view = _ScalingView(scene)
    window.setCentralWidget(view)
    return view
