"""
window2_image.py — Dual-View Image Processor (Window 2)

On startup:
  1. Scans the project directory for a 'test_pattern.png' (or any file whose
     name contains 'test').  If none found → calls generate_test_image.py to
     create one automatically.
  2. Loads the template and stores it as a numpy array.

Split-screen layout:
  LEFT  panel → template regions filled with the CLASSICAL RGB color
                (updates in real-time as Window 1 toggles channels)
  RIGHT panel → template regions filled with the QUANTUM COLLAPSED color
                (updates whenever Window 3 fires a Collapse event)

The fill algorithm lives in image_utils.apply_color_to_template.
"""

import os
import numpy as np
from PIL import Image

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QFrame, QSizePolicy,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QImage, QPixmap, QColor

from image_utils import apply_color_to_template, find_test_image
from generate_test_image import create_test_image


# ─────────────────────────────────────────────────────────────────────────────
# Utility: numpy RGB → QPixmap
# ─────────────────────────────────────────────────────────────────────────────

def _to_pixmap(array: np.ndarray) -> QPixmap:
    arr = np.ascontiguousarray(array, dtype=np.uint8)
    h, w, c = arr.shape
    qimg = QImage(arr.data, w, h, w * c, QImage.Format.Format_RGB888)
    return QPixmap.fromImage(qimg)


# ─────────────────────────────────────────────────────────────────────────────
# Image panel widget (reusable)
# ─────────────────────────────────────────────────────────────────────────────

class ImagePanel(QWidget):
    """One side of the split view: title + image display + colour swatch."""

    def __init__(self, label_text: str, swatch_color: tuple):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setSpacing(6)
        layout.setContentsMargins(0, 0, 0, 0)

        # Panel title
        title = QLabel(label_text)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setFont(QFont('Arial', 12, QFont.Weight.Bold))
        layout.addWidget(title)

        # Image display
        self.img_label = QLabel()
        self.img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.img_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self.img_label.setStyleSheet(
            'border: 2px solid #555555; background-color: #1c1c1c;'
        )
        layout.addWidget(self.img_label)

        # Colour swatch strip
        self.swatch = QLabel()
        self.swatch.setFixedHeight(28)
        self.swatch.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.swatch.setFont(QFont('Courier', 10))
        self._set_swatch(swatch_color)
        layout.addWidget(self.swatch)

    def _set_swatch(self, color: tuple):
        r, g, b = color
        lum = 0.299 * r + 0.587 * g + 0.114 * b
        fg  = '#000000' if lum > 140 else '#ffffff'
        self.swatch.setStyleSheet(
            f'background-color: rgb({r},{g},{b}); color: {fg};'
        )
        self.swatch.setText(f'RGB  ({r}, {g}, {b})')

    def update_image(self, template_array: np.ndarray, color: tuple, label_size):
        """Apply *color* to the template and show the result scaled to the label."""
        filled  = apply_color_to_template(template_array, color)
        pixmap  = _to_pixmap(filled)
        scaled  = pixmap.scaled(
            label_size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.img_label.setPixmap(scaled)
        self._set_swatch(color)


# ─────────────────────────────────────────────────────────────────────────────
# Window 2
# ─────────────────────────────────────────────────────────────────────────────

class ImageProcessorWindow(QMainWindow):
    def __init__(self, state):
        super().__init__()
        self.state          = state
        self.template_array = None   # set by _load_template()

        self.setWindowTitle('Window 2 — Dual-View Image Processor')
        self.setMinimumSize(820, 540)

        self._load_template()
        self._build_ui()

        # Wire state signals
        self.state.rgb_color_changed.connect(self._on_rgb_change)
        self.state.quantum_color_changed.connect(self._on_quantum_change)

        # First paint
        self._render_left(self.state.rgb_color)
        self._render_right(self.state.quantum_color)

    # ── Template loading ─────────────────────────────────────────────────

    def _load_template(self):
        project_dir = os.path.dirname(os.path.abspath(__file__))

        # 1. Try to find an existing test image (SVG or raster)
        img_path = find_test_image(project_dir)

        # 2. Auto-generate if none found
        if img_path is None:
            img_path = create_test_image(
                filename=os.path.join(project_dir, 'test_pattern.png')
            )

        # 3. SVG → rasterise via cairosvg, then hand off to Pillow
        if img_path.lower().endswith('.svg'):
            pil_img = self._svg_to_pil(img_path)
        else:
            pil_img = Image.open(img_path).convert('RGB')

        pil_img = pil_img.resize((400, 400), Image.LANCZOS)
        self.template_array = np.array(pil_img)
        print(f'[Window 2] Template loaded: {img_path}')

    @staticmethod
    def _svg_to_pil(svg_path: str) -> Image.Image:
        """
        Rasterise an SVG using PyQt6's built-in QSvgRenderer.
        No extra native libraries required — Qt handles it natively.
        """
        from PyQt6.QtSvg import QSvgRenderer
        from PyQt6.QtGui import QImage, QPainter, QColor

        renderer = QSvgRenderer(svg_path)
        size = renderer.defaultSize()
        w = size.width()  * 2 if size.isValid() else 1200
        h = size.height() * 2 if size.isValid() else 1200

        # Render onto a white RGB888 canvas
        qimg = QImage(w, h, QImage.Format.Format_RGB888)
        qimg.fill(QColor(255, 255, 255))
        painter = QPainter(qimg)
        renderer.render(painter)
        painter.end()

        # Convert QImage bytes → numpy → PIL
        ptr = qimg.bits()
        ptr.setsize(qimg.sizeInBytes())
        arr = np.frombuffer(ptr, dtype=np.uint8).reshape((h, w, 3))
        return Image.fromarray(arr.copy(), 'RGB')

    # ── UI construction ──────────────────────────────────────────────────

    def _build_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        main = QVBoxLayout(root)
        main.setSpacing(10)
        main.setContentsMargins(14, 14, 14, 14)

        # Title
        title = QLabel('Dual-View Image Processor')
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setFont(QFont('Arial', 14, QFont.Weight.Bold))
        main.addWidget(title)

        # Split view
        split = QHBoxLayout()
        split.setSpacing(10)

        self.left_panel  = ImagePanel('← Classical RGB',      (0, 0, 0))
        self.right_panel = ImagePanel('→ Quantum Collapse', (90, 60, 180))

        split.addWidget(self.left_panel)

        # Vertical divider
        div = QFrame()
        div.setFrameShape(QFrame.Shape.VLine)
        div.setFrameShadow(QFrame.Shadow.Sunken)
        div.setStyleSheet('color: #555555;')
        split.addWidget(div)

        split.addWidget(self.right_panel)
        main.addLayout(split)

        # Status bar
        self.status = QLabel(
            'Toggle RGB channels in Window 1  ·  Press Enter in Window 3 to Collapse'
        )
        self.status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status.setFont(QFont('Arial', 9))
        self.status.setStyleSheet('color: #777777;')
        main.addWidget(self.status)

    # ── Render helpers ───────────────────────────────────────────────────

    def _render_left(self, color: tuple):
        if self.template_array is None:
            return
        self.left_panel.update_image(
            self.template_array, color,
            self.left_panel.img_label.size()
        )

    def _render_right(self, color: tuple):
        if self.template_array is None:
            return
        self.right_panel.update_image(
            self.template_array, color,
            self.right_panel.img_label.size()
        )

    # ── State slots ──────────────────────────────────────────────────────

    def _on_rgb_change(self, color):
        self._render_left(color)
        self.status.setText(
            f'Classical RGB updated → ({color[0]}, {color[1]}, {color[2]})'
        )

    def _on_quantum_change(self, color):
        self._render_right(color)
        self.status.setText(
            f'Quantum Collapse → ({color[0]}, {color[1]}, {color[2]})'
        )

    # ── Resize event: re-scale pixmaps to new panel size ─────────────────

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.template_array is not None:
            self._render_left(self.state.rgb_color)
            self._render_right(self.state.quantum_color)
