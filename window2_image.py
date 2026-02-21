"""
window2_image.py — Dual-View Image Processor (Window 2)

New behaviour (per-region coloring)
────────────────────────────────────
  1. The template image is segmented into distinct regions via connected
     components (identify_regions in image_utils.py).
  2. Click any region on EITHER panel to SELECT it (yellow highlight).
  3. Window 1 → "Push Color to Left Image"  → fills that region on the LEFT.
  4. Window 3 → "Push Color to Right Image" → fills that region on the RIGHT.
  5. Each region keeps its own colour independently on each panel.
  6. "Save Image" exports the current left+right state side-by-side as PNG.

Template loading
────────────────
  Auto-scans the project folder for a file whose name contains 'test' or
  'crayo'.  If nothing is found it auto-generates test_pattern.png.
  SVG files are rasterised via PyQt6.QtSvg (no external libraries needed).
"""

import os
import numpy as np
from PIL import Image

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QFrame, QSizePolicy, QPushButton, QFileDialog,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QImage, QPixmap, QColor, QCursor

from image_utils import identify_regions, apply_region_colors, find_test_image
from generate_test_image import create_test_image


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _to_pixmap(array: np.ndarray) -> QPixmap:
    arr  = np.ascontiguousarray(array, dtype=np.uint8)
    h, w, c = arr.shape
    qimg = QImage(arr.data, w, h, w * c, QImage.Format.Format_RGB888)
    return QPixmap.fromImage(qimg)


# ─────────────────────────────────────────────────────────────────────────────
# Clickable QLabel — emits (x, y) in label-space on left-click
# ─────────────────────────────────────────────────────────────────────────────

class ClickableLabel(QLabel):
    clicked = pyqtSignal(float, float)

    def __init__(self):
        super().__init__()
        self.setCursor(QCursor(Qt.CursorShape.CrossCursor))

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(event.position().x(), event.position().y())
        super().mousePressEvent(event)


# ─────────────────────────────────────────────────────────────────────────────
# Image panel widget
# ─────────────────────────────────────────────────────────────────────────────

class ImagePanel(QWidget):
    """One half of the split view: title + clickable image + colour swatch."""
    region_clicked = pyqtSignal(float, float)   # label-space coordinates

    def __init__(self, title: str, swatch_color: tuple):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setSpacing(6)
        layout.setContentsMargins(0, 0, 0, 0)

        lbl = QLabel(title)
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setFont(QFont('Arial', 12, QFont.Weight.Bold))
        layout.addWidget(lbl)

        self.img_label = ClickableLabel()
        self.img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.img_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self.img_label.setStyleSheet(
            'border: 2px solid #555555; background-color: #1c1c1c;'
        )
        self.img_label.clicked.connect(self.region_clicked)
        layout.addWidget(self.img_label)

        self.swatch = QLabel()
        self.swatch.setFixedHeight(28)
        self.swatch.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.swatch.setFont(QFont('Courier', 10))
        self._set_swatch(swatch_color)
        layout.addWidget(self.swatch)

    def _set_swatch(self, color: tuple):
        r, g, b = color
        lum = 0.299 * r + 0.587 * g + 0.114 * b
        fg  = '#000' if lum > 140 else '#fff'
        self.swatch.setStyleSheet(
            f'background-color: rgb({r},{g},{b}); color: {fg};'
        )
        self.swatch.setText(f'RGB  ({r}, {g}, {b})')

    def update_image(self, array: np.ndarray, swatch_color: tuple = None):
        pixmap = _to_pixmap(array)
        scaled = pixmap.scaled(
            self.img_label.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.img_label.setPixmap(scaled)
        if swatch_color is not None:
            self._set_swatch(swatch_color)


# ─────────────────────────────────────────────────────────────────────────────
# Window 2
# ─────────────────────────────────────────────────────────────────────────────

class ImageProcessorWindow(QMainWindow):

    def __init__(self, state):
        super().__init__()
        self.state           = state
        self.template_array  = None
        self.region_labels   = None
        self.num_regions     = 0

        # Per-panel colour dictionaries:  { region_id (int) : (R, G, B) }
        self.left_region_colors  = {}
        self.right_region_colors = {}

        self.setWindowTitle('Window 2 — Dual-View Image Processor')
        self.setMinimumSize(860, 600)

        self._load_template()
        self._build_ui()

        # Wire state signals
        self.state.selected_region_changed.connect(self._on_region_selected)
        self.state.push_rgb_requested.connect(self._push_rgb)
        self.state.push_quantum_requested.connect(self._push_quantum)

        # Initial render
        self._render_left()
        self._render_right()

    # ── Template loading ──────────────────────────────────────────────────

    def _load_template(self):
        project_dir = os.path.dirname(os.path.abspath(__file__))
        img_path    = find_test_image(project_dir)

        if img_path is None:
            img_path = create_test_image(
                filename=os.path.join(project_dir, 'test_pattern.png')
            )

        if img_path.lower().endswith('.svg'):
            pil_img = self._svg_to_pil(img_path)
        else:
            pil_img = Image.open(img_path).convert('RGB')

        pil_img = pil_img.resize((400, 400), Image.LANCZOS)
        self.template_array = np.array(pil_img)

        self.num_regions, self.region_labels = identify_regions(self.template_array)
        print(
            f'[Window 2] Template: {img_path} '
            f'| regions detected: {self.num_regions - 1}'
        )

    @staticmethod
    def _svg_to_pil(svg_path: str) -> Image.Image:
        """Rasterise SVG via PyQt6.QtSvg — no native cairo needed."""
        from PyQt6.QtSvg import QSvgRenderer
        from PyQt6.QtGui import QImage, QPainter, QColor

        renderer = QSvgRenderer(svg_path)
        size = renderer.defaultSize()
        w = size.width()  * 2 if size.isValid() else 1200
        h = size.height() * 2 if size.isValid() else 1200

        qimg = QImage(w, h, QImage.Format.Format_RGB888)
        qimg.fill(QColor(255, 255, 255))
        painter = QPainter(qimg)
        renderer.render(painter)
        painter.end()

        ptr = qimg.bits()
        ptr.setsize(qimg.sizeInBytes())
        arr = np.frombuffer(ptr, dtype=np.uint8).reshape((h, w, 3))
        return Image.fromarray(arr.copy(), 'RGB')

    # ── UI construction ───────────────────────────────────────────────────

    def _build_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        main = QVBoxLayout(root)
        main.setSpacing(8)
        main.setContentsMargins(14, 14, 14, 14)

        # Title
        title = QLabel('Dual-View Image Processor')
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setFont(QFont('Arial', 13, QFont.Weight.Bold))
        main.addWidget(title)

        # Selection status
        self.sel_label = QLabel(
            'Click a region on the image to select it → then push a colour'
        )
        self.sel_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.sel_label.setFont(QFont('Arial', 10))
        self.sel_label.setStyleSheet('color: #aaaaaa;')
        main.addWidget(self.sel_label)

        # ── Split view ────────────────────────────────────────────────
        split = QHBoxLayout()
        split.setSpacing(10)

        self.left_panel  = ImagePanel('← Classical RGB',   (0, 0, 0))
        self.right_panel = ImagePanel('→ Quantum Collapse', (90, 60, 180))

        self.left_panel.region_clicked.connect(
            lambda x, y: self._select_region(self.left_panel.img_label, x, y)
        )
        self.right_panel.region_clicked.connect(
            lambda x, y: self._select_region(self.right_panel.img_label, x, y)
        )

        split.addWidget(self.left_panel)

        div = QFrame()
        div.setFrameShape(QFrame.Shape.VLine)
        div.setFrameShadow(QFrame.Shadow.Sunken)
        div.setStyleSheet('color: #555555;')
        split.addWidget(div)

        split.addWidget(self.right_panel)
        main.addLayout(split)

        # ── Save button ───────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        save_btn = QPushButton('💾  Save Image')
        save_btn.setMinimumHeight(38)
        save_btn.setFont(QFont('Arial', 11))
        save_btn.setStyleSheet("""
            QPushButton {
                background-color : #1e5a1e;
                color            : #bbffbb;
                border-radius    : 9px;
                border           : 2px solid #2e8a2e;
                padding          : 0 20px;
            }
            QPushButton:hover   { background-color : #2e7a2e; }
            QPushButton:pressed { background-color : #0e4a0e; }
        """)
        save_btn.clicked.connect(self._save_image)
        btn_row.addWidget(save_btn)
        btn_row.addStretch()
        main.addLayout(btn_row)

        # Status bar
        self.status = QLabel(
            'Use Window 1 or Window 3 Push buttons to fill the selected region'
        )
        self.status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status.setFont(QFont('Arial', 9))
        self.status.setStyleSheet('color: #777777;')
        main.addWidget(self.status)

    # ── Click / region selection ──────────────────────────────────────────

    def _label_to_template(self, label: QLabel, lx: float, ly: float):
        """Map label-space (lx, ly) → template pixel (tx, ty), or (None, None)."""
        pm = label.pixmap()
        if pm is None:
            return None, None

        lw, lh = label.width(), label.height()
        pw, ph = pm.width(), pm.height()
        if pw == 0 or ph == 0:
            return None, None

        off_x = (lw - pw) / 2
        off_y = (lh - ph) / 2

        if not (off_x <= lx <= off_x + pw and off_y <= ly <= off_y + ph):
            return None, None

        th, tw = self.template_array.shape[:2]
        tx = int((lx - off_x) / pw * tw)
        ty = int((ly - off_y) / ph * th)
        return max(0, min(tw - 1, tx)), max(0, min(th - 1, ty))

    def _select_region(self, label: QLabel, lx: float, ly: float):
        if self.region_labels is None:
            return
        tx, ty = self._label_to_template(label, lx, ly)
        if tx is None:
            return
        rid = int(self.region_labels[ty, tx])
        if rid > 0:
            self.state.selected_region = rid
        else:
            self.status.setText(
                'Clicked on an outline — click inside a coloured region'
            )

    # ── Push handlers ─────────────────────────────────────────────────────

    def _push_rgb(self):
        rid = self.state.selected_region
        if rid <= 0:
            self.status.setText(
                'No region selected — click on the image first'
            )
            return
        color = self.state.rgb_color
        self.left_region_colors[rid] = color
        self._render_left()
        r, g, b = color
        self.left_panel._set_swatch(color)
        self.status.setText(
            f'Left  region #{rid}  filled with RGB ({r}, {g}, {b})'
        )

    def _push_quantum(self):
        rid = self.state.selected_region
        if rid <= 0:
            self.status.setText(
                'No region selected — click on the image first'
            )
            return
        color = self.state.quantum_color
        self.right_region_colors[rid] = color
        self._render_right()
        r, g, b = color
        self.right_panel._set_swatch(color)
        self.status.setText(
            f'Right region #{rid}  filled with Quantum ({r}, {g}, {b})'
        )

    # ── Render ────────────────────────────────────────────────────────────

    def _render_left(self):
        if self.template_array is None:
            return
        arr = apply_region_colors(
            self.template_array, self.region_labels,
            self.left_region_colors, self.state.selected_region,
        )
        self.left_panel.update_image(arr)

    def _render_right(self):
        if self.template_array is None:
            return
        arr = apply_region_colors(
            self.template_array, self.region_labels,
            self.right_region_colors, self.state.selected_region,
        )
        self.right_panel.update_image(arr)

    # ── State slots ───────────────────────────────────────────────────────

    def _on_region_selected(self, rid: int):
        if rid > 0:
            self.sel_label.setText(
                f'Region #{rid} selected  —  push a colour from Window 1 or Window 3'
            )
            self.sel_label.setStyleSheet('color: #ffdd44;')
        else:
            self.sel_label.setText(
                'Click a region on the image to select it → then push a colour'
            )
            self.sel_label.setStyleSheet('color: #aaaaaa;')
        self._render_left()
        self._render_right()

    # ── Save ─────────────────────────────────────────────────────────────

    def _save_image(self):
        path, _ = QFileDialog.getSaveFileName(
            self, 'Save Coloured Image', 'colored_result.png',
            'PNG (*.png);;JPEG (*.jpg *.jpeg)'
        )
        if not path:
            return

        left_arr  = apply_region_colors(
            self.template_array, self.region_labels, self.left_region_colors
        )
        right_arr = apply_region_colors(
            self.template_array, self.region_labels, self.right_region_colors
        )
        combined = np.hstack([left_arr, right_arr])
        Image.fromarray(combined.astype(np.uint8), 'RGB').save(path)
        self.status.setText(f'Saved → {path}')

    # ── Resize ────────────────────────────────────────────────────────────

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.template_array is not None:
            self._render_left()
            self._render_right()
