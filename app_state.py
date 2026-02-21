"""
app_state.py — Unified State Manager
Holds the two live colors, the currently selected image region, and all
inter-window signals so the three windows stay synchronised automatically.
"""

from PyQt6.QtCore import QObject, pyqtSignal


class AppState(QObject):
    # Emitted when Window 1 toggles an RGB channel
    rgb_color_changed = pyqtSignal(object)          # payload: (R, G, B)

    # Emitted when Window 3 performs a quantum collapse
    quantum_color_changed = pyqtSignal(object)      # payload: (R, G, B)

    # Emitted when the user clicks a region in Window 2
    selected_region_changed = pyqtSignal(object)    # payload: int region id

    # Emitted when Window 1's Push button is clicked
    push_rgb_requested = pyqtSignal()

    # Emitted when Window 3's Push button is clicked
    push_quantum_requested = pyqtSignal()

    def __init__(self):
        super().__init__()
        self._rgb_color      = (0, 0, 0)
        self._quantum_color  = (90, 60, 180)
        self._selected_region = -1          # -1 = nothing selected

    # ── rgb_color ──────────────────────────────────────────────────────── #
    @property
    def rgb_color(self):
        return self._rgb_color

    @rgb_color.setter
    def rgb_color(self, value):
        self._rgb_color = tuple(int(v) for v in value)
        self.rgb_color_changed.emit(self._rgb_color)

    # ── quantum_color ──────────────────────────────────────────────────── #
    @property
    def quantum_color(self):
        return self._quantum_color

    @quantum_color.setter
    def quantum_color(self, value):
        self._quantum_color = tuple(int(v) for v in value)
        self.quantum_color_changed.emit(self._quantum_color)

    # ── selected_region ────────────────────────────────────────────────── #
    @property
    def selected_region(self):
        return self._selected_region

    @selected_region.setter
    def selected_region(self, value):
        self._selected_region = int(value)
        self.selected_region_changed.emit(self._selected_region)

    # ── Push triggers ──────────────────────────────────────────────────── #
    def request_push_rgb(self):
        """Window 1 asks Window 2 to fill the selected region with rgb_color."""
        self.push_rgb_requested.emit()

    def request_push_quantum(self):
        """Window 3 asks Window 2 to fill the selected region with quantum_color."""
        self.push_quantum_requested.emit()
