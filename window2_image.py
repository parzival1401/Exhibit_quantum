"""
window2_image.py — Dual-View Image Processor (Window 2)
Museum Exhibition Edition

User flow
─────────
  1. Welcome screen  — large START button, suitable for all ages
  2. Gallery screen  — clickable image cards loaded from the images/ folder
  3. Coloring screen — dual-panel per-region coloring

Coloring behaviour
──────────────────
  • Click any region on either panel to select it (yellow highlight).
  • Window 1 → "Push Color to Left Image"  fills that region (classical RGB).
  • Window 3 → "Push Color to Right Image" fills that region (quantum).
  • Each region keeps its colour independently on each panel.
  • "Save Image" exports left + right side-by-side as PNG.

Staff / admin
─────────────
  Menu bar → File → "Open Image…" bypasses the gallery for any file.
  SVG files are rasterised via PyQt6.QtSvg (no external libraries needed).
"""

import os
import threading
import socketserver
import http.server
import socket as _socket
import tempfile
import numpy as np
from PIL import Image

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QFrame, QSizePolicy, QPushButton, QFileDialog,
    QMessageBox, QStackedWidget, QScrollArea, QDialog,
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QFont, QImage, QPixmap, QColor, QCursor, QAction

from image_utils import identify_regions, apply_region_colors

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

PROJECT_DIR     = os.path.dirname(os.path.abspath(__file__))
IMAGES_DIR      = os.path.join(PROJECT_DIR, 'images')
os.makedirs(IMAGES_DIR, exist_ok=True)

_SUPPORTED_EXTS = ('.png', '.jpg', '.jpeg', '.bmp', '.svg')
_IMAGE_FILTER   = 'Images (*.png *.jpg *.jpeg *.bmp *.svg);;All files (*)'
_THUMB_W        = 210      # card thumbnail width  (px)
_THUMB_H        = 190      # card thumbnail height (px)
_CARD_COLS      = 3        # columns in the gallery grid


# ─────────────────────────────────────────────────────────────────────────────
# Local HTTP server helpers (for QR code download)
# ─────────────────────────────────────────────────────────────────────────────

def _get_local_ip() -> str:
    """Return the machine's LAN IP (falls back to 127.0.0.1)."""
    try:
        s = _socket.socket(_socket.AF_INET, _socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return '127.0.0.1'


def _start_file_server(directory: str):
    """Start a SimpleHTTPRequestHandler on a random free port in a daemon thread.
    Returns (server, port)."""

    class _Silent(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **kw):
            super().__init__(*a, directory=directory, **kw)
        def log_message(self, *a):
            pass   # suppress console noise

    server = socketserver.TCPServer(('', 0), _Silent)
    port   = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, port


# ─────────────────────────────────────────────────────────────────────────────
# QR Code dialog
# ─────────────────────────────────────────────────────────────────────────────

class QRDialog(QDialog):
    """Full-screen-friendly dialog showing a scannable QR code."""

    def __init__(self, url: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Scan to Download Your Artwork')
        self.setModal(True)
        self.setMinimumSize(440, 540)
        self.setStyleSheet('background-color: #06061a;')

        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(32, 28, 32, 28)

        title = QLabel('Scan with your phone')
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setFont(QFont('Arial', 18, QFont.Weight.Bold))
        title.setStyleSheet('color: #ccccff;')
        layout.addWidget(title)

        sub = QLabel('Download your colored artwork to your camera roll')
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setFont(QFont('Arial', 10))
        sub.setStyleSheet('color: #556677;')
        layout.addWidget(sub)

        # Generate QR image
        try:
            import qrcode
            qr = qrcode.QRCode(box_size=9, border=2)
            qr.add_data(url)
            qr.make(fit=True)
            pil_qr = qr.make_image(
                fill_color='white', back_color='#06061a'
            ).convert('RGB')
            arr = np.array(pil_qr)
            pixmap = _to_pixmap(arr)
        except Exception as exc:
            pixmap = None
            err_lbl = QLabel(f'QR generation failed:\n{exc}')
            err_lbl.setStyleSheet('color: #ff6666;')
            err_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(err_lbl)

        if pixmap:
            qr_lbl = QLabel()
            qr_lbl.setPixmap(
                pixmap.scaled(
                    QSize(340, 340),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
            qr_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            qr_lbl.setStyleSheet('border: none;')
            layout.addWidget(qr_lbl)

        url_lbl = QLabel(url)
        url_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        url_lbl.setFont(QFont('Courier', 9))
        url_lbl.setStyleSheet('color: #445566;')
        url_lbl.setWordWrap(True)
        layout.addWidget(url_lbl)

        close_btn = QPushButton('Done  ✓')
        close_btn.setMinimumHeight(52)
        close_btn.setFont(QFont('Arial', 14, QFont.Weight.Bold))
        close_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        close_btn.setStyleSheet("""
            QPushButton {
                background-color : #1a1aaa;
                color            : #ffffff;
                border-radius    : 14px;
                border           : 2px solid #5555ff;
            }
            QPushButton:hover   { background-color : #2525cc; }
            QPushButton:pressed { background-color : #0f0f77; }
        """)
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)


# ─────────────────────────────────────────────────────────────────────────────
# Image loading helpers
# ─────────────────────────────────────────────────────────────────────────────

def _svg_to_array(svg_path: str, size: int = 400) -> np.ndarray:
    """Rasterise an SVG via PyQt6.QtSvg and return an H×W×3 uint8 array."""
    from PyQt6.QtSvg import QSvgRenderer
    from PyQt6.QtGui import QImage as _QI, QPainter, QColor as _QC

    renderer = QSvgRenderer(svg_path)
    default  = renderer.defaultSize()
    w = default.width()  * 2 if default.isValid() else size
    h = default.height() * 2 if default.isValid() else size

    qimg = _QI(w, h, _QI.Format.Format_RGB888)
    qimg.fill(_QC(255, 255, 255))
    painter = QPainter(qimg)
    renderer.render(painter)
    painter.end()

    ptr = qimg.bits()
    ptr.setsize(qimg.sizeInBytes())
    arr = np.frombuffer(ptr, dtype=np.uint8).reshape((h, w, 3)).copy()
    pil = Image.fromarray(arr, 'RGB').resize((size, size), Image.LANCZOS)
    return np.array(pil)


def _load_image_array(path: str, size: int = 400) -> np.ndarray | None:
    """Load any supported image file and return an H×W×3 uint8 array, or None."""
    try:
        if path.lower().endswith('.svg'):
            return _svg_to_array(path, size)
        pil = Image.open(path).convert('RGB').resize((size, size), Image.LANCZOS)
        return np.array(pil)
    except Exception:
        return None


def _to_pixmap(array: np.ndarray) -> QPixmap:
    arr  = np.ascontiguousarray(array, dtype=np.uint8)
    h, w, _ = arr.shape
    qimg = QImage(arr.data, w, h, w * 3, QImage.Format.Format_RGB888)
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
# Gallery image card
# ─────────────────────────────────────────────────────────────────────────────

class ImageCard(QWidget):
    """Clickable thumbnail card shown in the gallery screen."""
    selected = pyqtSignal(str)   # full file path

    _BASE  = ('background-color: #1a1a2e; border-radius: 14px;'
              ' border: 2px solid #333355;')
    _HOVER = ('background-color: #22223e; border-radius: 14px;'
              ' border: 2px solid #8888ee;')
    _PRESS = ('background-color: #2e2e55; border-radius: 14px;'
              ' border: 3px solid #bbbbff;')

    def __init__(self, path: str, thumb_array: np.ndarray):
        super().__init__()
        self._path = path
        self.setFixedSize(_THUMB_W + 20, _THUMB_H + 56)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._apply(self._BASE)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 8)
        layout.setSpacing(6)

        # Thumbnail image
        pixmap = _to_pixmap(thumb_array)
        scaled = pixmap.scaled(
            QSize(_THUMB_W, _THUMB_H),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        img_lbl = QLabel()
        img_lbl.setPixmap(scaled)
        img_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        img_lbl.setStyleSheet('border: none; background: transparent;')
        layout.addWidget(img_lbl)

        # Filename label (truncated)
        name = os.path.splitext(os.path.basename(path))[0]
        if len(name) > 24:
            name = name[:22] + '…'
        name_lbl = QLabel(name)
        name_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name_lbl.setFont(QFont('Arial', 10))
        name_lbl.setStyleSheet('color: #ccccff; border: none; background: transparent;')
        name_lbl.setWordWrap(True)
        layout.addWidget(name_lbl)

    def _apply(self, style: str):
        self.setStyleSheet(f'QWidget {{ {style} }}')

    def enterEvent(self, event):
        self._apply(self._HOVER)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._apply(self._BASE)
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._apply(self._PRESS)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._apply(self._BASE)
            self.selected.emit(self._path)
        super().mouseReleaseEvent(event)


# ─────────────────────────────────────────────────────────────────────────────
# Image panel widget (one half of the coloring split-view)
# ─────────────────────────────────────────────────────────────────────────────

class ImagePanel(QWidget):
    region_clicked = pyqtSignal(float, float)

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
# Window 2 — Museum Exhibition
# ─────────────────────────────────────────────────────────────────────────────

class ImageProcessorWindow(QMainWindow):

    PAGE_WELCOME  = 0
    PAGE_GALLERY  = 1
    PAGE_COLORING = 2

    def __init__(self, state):
        super().__init__()
        self.state            = state
        self.template_array   = None
        self.region_labels    = None
        self.num_regions      = 0
        self.left_region_colors  = {}
        self.right_region_colors = {}

        # QR code server state
        self._qr_server  = None
        self._qr_port    = None
        self._qr_tmp_dir = tempfile.mkdtemp(prefix='quantum_exhibit_')

        self.setWindowTitle('Window 2 — Quantum Color Exhibit')
        self.setMinimumSize(900, 660)

        self._build_ui()
        self._build_menu()

        self.state.selected_region_changed.connect(self._on_region_selected)
        self.state.push_rgb_requested.connect(self._push_rgb)
        self.state.push_quantum_requested.connect(self._push_quantum)

    # ── Stacked UI ────────────────────────────────────────────────────────

    def _build_ui(self):
        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        self.stack.addWidget(self._make_welcome_page())   # PAGE_WELCOME  = 0
        self.stack.addWidget(self._make_gallery_page())   # PAGE_GALLERY  = 1
        self.stack.addWidget(self._make_coloring_page())  # PAGE_COLORING = 2

        self.stack.setCurrentIndex(self.PAGE_WELCOME)

    # ── Page 0 — Welcome ──────────────────────────────────────────────────

    def _make_welcome_page(self) -> QWidget:
        page = QWidget()
        page.setStyleSheet('background-color: #06061a;')
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(22)

        title = QLabel('QUANTUM COLOR')
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setFont(QFont('Arial', 40, QFont.Weight.Bold))
        title.setStyleSheet('color: #aaaaff;')
        layout.addWidget(title)

        subtitle = QLabel('A painting experience inspired by quantum mechanics')
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setFont(QFont('Arial', 14))
        subtitle.setStyleSheet('color: #6677aa;')
        layout.addWidget(subtitle)

        layout.addSpacing(30)

        start_btn = QPushButton('▶   START')
        start_btn.setMinimumSize(300, 100)
        start_btn.setFont(QFont('Arial', 26, QFont.Weight.Bold))
        start_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        start_btn.setStyleSheet("""
            QPushButton {
                background-color : #1a1aaa;
                color            : #ffffff;
                border-radius    : 20px;
                border           : 3px solid #5555ff;
            }
            QPushButton:hover   { background-color : #2525cc; border-color: #9999ff; }
            QPushButton:pressed { background-color : #0f0f77; }
        """)
        start_btn.clicked.connect(self._go_to_gallery)

        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(start_btn)
        row.addStretch()
        layout.addLayout(row)

        layout.addSpacing(24)

        hint = QLabel('Touch or click START to choose an image and begin')
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setFont(QFont('Arial', 11))
        hint.setStyleSheet('color: #334455;')
        layout.addWidget(hint)

        return page

    # ── Page 1 — Gallery ──────────────────────────────────────────────────

    def _make_gallery_page(self) -> QWidget:
        page = QWidget()
        page.setStyleSheet('background-color: #0d0d22;')
        outer = QVBoxLayout(page)
        outer.setContentsMargins(20, 14, 20, 14)
        outer.setSpacing(12)

        # Top bar
        top = QHBoxLayout()

        back_btn = QPushButton('← Back')
        back_btn.setFixedSize(120, 44)
        back_btn.setFont(QFont('Arial', 12))
        back_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        back_btn.setStyleSheet("""
            QPushButton {
                background-color : #1e1e44;
                color            : #aaaadd;
                border-radius    : 10px;
                border           : 1px solid #444488;
            }
            QPushButton:hover   { background-color : #2a2a66; }
            QPushButton:pressed { background-color : #111133; }
        """)
        back_btn.clicked.connect(
            lambda: self.stack.setCurrentIndex(self.PAGE_WELCOME)
        )
        top.addWidget(back_btn)

        gal_title = QLabel('Choose an Image to Color')
        gal_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        gal_title.setFont(QFont('Arial', 17, QFont.Weight.Bold))
        gal_title.setStyleSheet('color: #ccccff;')
        top.addWidget(gal_title, stretch=1)

        top.addSpacing(120)   # visual balance opposite the back button
        outer.addLayout(top)

        # Scrollable grid area
        self.gallery_scroll = QScrollArea()
        self.gallery_scroll.setWidgetResizable(True)
        self.gallery_scroll.setStyleSheet("""
            QScrollArea { border: none; background: transparent; }
            QScrollBar:vertical {
                background: #1a1a2e; width: 10px; border-radius: 5px;
            }
            QScrollBar::handle:vertical {
                background: #555599; border-radius: 5px; min-height: 20px;
            }
        """)

        self.gallery_inner = QWidget()
        self.gallery_inner.setStyleSheet('background: transparent;')
        self.gallery_grid  = QGridLayout(self.gallery_inner)
        self.gallery_grid.setSpacing(20)
        self.gallery_grid.setContentsMargins(10, 10, 10, 10)

        self.gallery_scroll.setWidget(self.gallery_inner)
        outer.addWidget(self.gallery_scroll, stretch=1)

        # Placeholder shown when images/ is empty
        self.no_images_lbl = QLabel(
            'No images found.\n\n'
            'Add PNG, JPG, or SVG files to the images/ folder\n'
            f'({IMAGES_DIR})'
        )
        self.no_images_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.no_images_lbl.setFont(QFont('Arial', 12))
        self.no_images_lbl.setStyleSheet('color: #445566;')
        self.no_images_lbl.hide()
        outer.addWidget(self.no_images_lbl)

        return page

    # ── Page 2 — Coloring ─────────────────────────────────────────────────

    def _make_coloring_page(self) -> QWidget:
        page = QWidget()
        page.setStyleSheet('background-color: #111118;')
        main = QVBoxLayout(page)
        main.setSpacing(6)
        main.setContentsMargins(14, 8, 14, 8)

        # Top bar: "Choose Another Image" + current filename
        top = QHBoxLayout()

        choose_btn = QPushButton('🖼  Choose Another Image')
        choose_btn.setFixedHeight(38)
        choose_btn.setFont(QFont('Arial', 11))
        choose_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        choose_btn.setStyleSheet("""
            QPushButton {
                background-color : #1e1e44;
                color            : #aaaadd;
                border-radius    : 9px;
                border           : 1px solid #3333aa;
                padding          : 0 14px;
            }
            QPushButton:hover   { background-color : #2a2a66; }
            QPushButton:pressed { background-color : #111133; }
        """)
        choose_btn.clicked.connect(self._go_to_gallery)
        top.addWidget(choose_btn)

        top.addStretch()

        self.cur_img_lbl = QLabel('')
        self.cur_img_lbl.setFont(QFont('Arial', 10))
        self.cur_img_lbl.setStyleSheet('color: #666688;')
        top.addWidget(self.cur_img_lbl)

        main.addLayout(top)

        # Region selection status
        self.sel_label = QLabel(
            'Click a region on the image to select it → then push a colour'
        )
        self.sel_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.sel_label.setFont(QFont('Arial', 10))
        self.sel_label.setStyleSheet('color: #aaaaaa;')
        main.addWidget(self.sel_label)

        # Split view
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
        main.addLayout(split, stretch=1)

        # Bottom bar: Save button
        bot = QHBoxLayout()
        bot.addStretch()

        save_btn = QPushButton('💾  Save Image')
        save_btn.setMinimumHeight(40)
        save_btn.setFont(QFont('Arial', 11))
        save_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        save_btn.setStyleSheet("""
            QPushButton {
                background-color : #1e5a1e;
                color            : #bbffbb;
                border-radius    : 9px;
                border           : 2px solid #2e8a2e;
                padding          : 0 22px;
            }
            QPushButton:hover   { background-color : #2e7a2e; }
            QPushButton:pressed { background-color : #0e4a0e; }
        """)
        save_btn.clicked.connect(self._save_image)
        bot.addWidget(save_btn)

        bot.addSpacing(14)

        qr_btn = QPushButton('📱  Get QR Code')
        qr_btn.setMinimumHeight(40)
        qr_btn.setFont(QFont('Arial', 11))
        qr_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        qr_btn.setStyleSheet("""
            QPushButton {
                background-color : #1a1a6a;
                color            : #aaaaff;
                border-radius    : 9px;
                border           : 2px solid #3333cc;
                padding          : 0 22px;
            }
            QPushButton:hover   { background-color : #2525aa; }
            QPushButton:pressed { background-color : #0f0f55; }
        """)
        qr_btn.clicked.connect(self._show_qr_code)
        bot.addWidget(qr_btn)

        bot.addStretch()
        main.addLayout(bot)

        self.status = QLabel(
            'Use Window 1 or Window 3 Push buttons to fill the selected region'
        )
        self.status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status.setFont(QFont('Arial', 9))
        self.status.setStyleSheet('color: #777777;')
        main.addWidget(self.status)

        return page

    # ── Staff / admin menu bar ────────────────────────────────────────────

    def _build_menu(self):
        mb = self.menuBar()
        mb.setStyleSheet("""
            QMenuBar {
                background-color : #1e1e1e;
                color            : #aaaaaa;
                font-size        : 11px;
            }
            QMenuBar::item:selected { background-color: #333333; }
            QMenu {
                background-color : #252525;
                color            : #dddddd;
                border           : 1px solid #444444;
            }
            QMenu::item:selected { background-color: #3a3a5a; }
            QMenu::separator     { height: 1px; background: #444444; margin: 3px 0; }
        """)

        file_menu = mb.addMenu('Staff')

        act_open = QAction('Open Any Image…', self)
        act_open.setShortcut('Ctrl+O')
        act_open.triggered.connect(self._staff_open_image)
        file_menu.addAction(act_open)

        file_menu.addSeparator()

        act_save = QAction('Save Image', self)
        act_save.setShortcut('Ctrl+S')
        act_save.triggered.connect(self._save_image)
        file_menu.addAction(act_save)

        act_home = QAction('Go to Welcome Screen', self)
        act_home.triggered.connect(
            lambda: self.stack.setCurrentIndex(self.PAGE_WELCOME)
        )
        file_menu.addAction(act_home)

    # ── Gallery navigation ────────────────────────────────────────────────

    def _go_to_gallery(self):
        self._refresh_gallery()
        self.stack.setCurrentIndex(self.PAGE_GALLERY)

    def _refresh_gallery(self):
        # Remove old cards
        while self.gallery_grid.count():
            item = self.gallery_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Scan images/ folder
        try:
            entries = sorted(os.listdir(IMAGES_DIR))
        except OSError:
            entries = []

        paths = [
            os.path.join(IMAGES_DIR, f)
            for f in entries
            if f.lower().endswith(_SUPPORTED_EXTS) and not f.startswith('.')
        ]

        if not paths:
            self.gallery_scroll.hide()
            self.no_images_lbl.show()
            return

        self.no_images_lbl.hide()
        self.gallery_scroll.show()

        for idx, path in enumerate(paths):
            arr = _load_image_array(path, size=_THUMB_H)
            if arr is None:
                continue
            card = ImageCard(path, arr)
            card.selected.connect(self._on_gallery_selected)
            row, col = divmod(idx, _CARD_COLS)
            self.gallery_grid.addWidget(card, row, col)

        # Push cards to the top-left inside the scroll area
        self.gallery_grid.setRowStretch(self.gallery_grid.rowCount(), 1)
        self.gallery_grid.setColumnStretch(_CARD_COLS, 1)

    def _on_gallery_selected(self, path: str):
        self._load_template_from_path(path)
        self.stack.setCurrentIndex(self.PAGE_COLORING)

    # ── Template loading ──────────────────────────────────────────────────

    def _load_template_from_path(self, img_path: str):
        arr = _load_image_array(img_path, size=400)
        if arr is None:
            QMessageBox.warning(
                self, 'Load Error',
                f'Could not open image:\n{img_path}'
            )
            return

        self.template_array      = arr
        self.left_region_colors  = {}
        self.right_region_colors = {}
        self.state.selected_region = -1

        self.num_regions, self.region_labels = identify_regions(self.template_array)
        fname = os.path.basename(img_path)
        print(
            f'[Window 2] Template: {img_path} '
            f'| regions detected: {self.num_regions - 1}'
        )

        self.setWindowTitle(f'Window 2 — Quantum Color Exhibit  [{fname}]')
        self.cur_img_lbl.setText(fname)
        self.status.setText(f'Loaded: {fname}  ({self.num_regions - 1} regions)')

        self._render_left()
        self._render_right()

    def _staff_open_image(self):
        """Admin-only: open any file from anywhere on disk."""
        path, _ = QFileDialog.getOpenFileName(
            self, 'Open Template Image', PROJECT_DIR, _IMAGE_FILTER
        )
        if path:
            self._load_template_from_path(path)
            self.stack.setCurrentIndex(self.PAGE_COLORING)

    # ── Click / region selection ──────────────────────────────────────────

    def _label_to_template(self, label: QLabel, lx: float, ly: float):
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
            self.status.setText('No region selected — click on the image first')
            return
        color = self.state.rgb_color
        self.left_region_colors[rid] = color
        self._render_left()
        self.left_panel._set_swatch(color)
        r, g, b = color
        self.status.setText(f'Left  region #{rid}  filled with RGB ({r}, {g}, {b})')

    def _push_quantum(self):
        rid = self.state.selected_region
        if rid <= 0:
            self.status.setText('No region selected — click on the image first')
            return
        color = self.state.quantum_color
        self.right_region_colors[rid] = color
        self._render_right()
        self.right_panel._set_swatch(color)
        r, g, b = color
        self.status.setText(f'Right region #{rid}  filled with Quantum ({r}, {g}, {b})')

    # ── Render ────────────────────────────────────────────────────────────

    def _render_left(self):
        if self.template_array is None or self.region_labels is None:
            return
        arr = apply_region_colors(
            self.template_array, self.region_labels,
            self.left_region_colors, self.state.selected_region,
        )
        self.left_panel.update_image(arr)

    def _render_right(self):
        if self.template_array is None or self.region_labels is None:
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

    # ── QR Code ───────────────────────────────────────────────────────────

    def _show_qr_code(self):
        if self.template_array is None or self.region_labels is None:
            self.status.setText('No image loaded yet — please select one first')
            return

        # Auto-save current result to temp folder (no dialog needed)
        fname    = 'quantum_artwork.png'
        tmp_path = os.path.join(self._qr_tmp_dir, fname)

        left_arr  = apply_region_colors(
            self.template_array, self.region_labels, self.left_region_colors
        )
        right_arr = apply_region_colors(
            self.template_array, self.region_labels, self.right_region_colors
        )
        combined = np.hstack([left_arr, right_arr])
        Image.fromarray(combined.astype(np.uint8), 'RGB').save(tmp_path)

        # Start local HTTP server once (reused for all QR requests)
        if self._qr_server is None:
            self._qr_server, self._qr_port = _start_file_server(self._qr_tmp_dir)

        ip  = _get_local_ip()
        url = f'http://{ip}:{self._qr_port}/{fname}'

        self.status.setText(f'QR ready — visitors can scan to download  ({url})')
        QRDialog(url, self).exec()

    # ── Save ─────────────────────────────────────────────────────────────

    def _save_image(self):
        if self.template_array is None:
            self.status.setText('No image loaded yet — please select one first')
            return
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
