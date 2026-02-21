"""
app_state.py — Unified State Manager
Holds the two live colors and broadcasts changes to any connected window
via PyQt6 signals, so all three windows stay in sync automatically.
"""

from PyQt6.QtCore import QObject, pyqtSignal


class AppState(QObject):
    # Emitted whenever Window 1 toggles an RGB channel
    rgb_color_changed = pyqtSignal(object)   # payload: (R, G, B) tuple

    # Emitted whenever Window 3 performs a quantum collapse
    quantum_color_changed = pyqtSignal(object)  # payload: (R, G, B) tuple

    def __init__(self):
        super().__init__()
        self._rgb_color = (0, 0, 0)          # all channels off at startup
        self._quantum_color = (90, 60, 180)  # a nice starting purple

    # ------------------------------------------------------------------ #
    #  rgb_color property                                                  #
    # ------------------------------------------------------------------ #
    @property
    def rgb_color(self):
        return self._rgb_color

    @rgb_color.setter
    def rgb_color(self, value):
        self._rgb_color = tuple(int(v) for v in value)
        self.rgb_color_changed.emit(self._rgb_color)

    # ------------------------------------------------------------------ #
    #  quantum_color property                                              #
    # ------------------------------------------------------------------ #
    @property
    def quantum_color(self):
        return self._quantum_color

    @quantum_color.setter
    def quantum_color(self, value):
        self._quantum_color = tuple(int(v) for v in value)
        self.quantum_color_changed.emit(self._quantum_color)
