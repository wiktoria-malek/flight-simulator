from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QVBoxLayout, QDialog, QLabel, QPlainTextEdit)
import matplotlib
from PyQt6 import uic
matplotlib.use("QtAgg")

class BPM_weights(QDialog):
    def __init__(self, bpm_name, parent=None):
        super().__init__(parent)
        uic.loadUi('UI files/BPM_weights.ui', self)
        self.setWindowTitle(f"BPM weights - {bpm_name}")
        self.button_apply.clicked.connect(self.accept)
        self.button_cancel.clicked.connect(self.reject)
    def set_values(self,w_orb,w_dfs,w_wfs):
        self.w_orbit.setValue(w_orb)
        self.w_dfs.setValue(w_dfs)
        self.w_wfs.setValue(w_wfs)

    def get_values(self):
        return self.w_orbit.value(), self.w_dfs.value(),self.w_wfs.value()


