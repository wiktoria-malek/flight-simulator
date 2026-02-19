from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QVBoxLayout, QDialog, QLabel, QPlainTextEdit)
import matplotlib
from PyQt6 import uic
matplotlib.use("QtAgg")

class BPM_weights(QDialog):
    def __init__(self, bpm_name, parent=None):
        super().__init__(parent)
        uic.loadUi('BPM_weights.ui', self)
        self.setWindowTitle(f"BPM weights - {bpm_name}")



