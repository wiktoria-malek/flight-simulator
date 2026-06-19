try:
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QVBoxLayout, QHBoxLayout, QDialog, QLabel, QWidget, QComboBox
except ImportError:
    from PyQt5.QtCore import Qt
    from PyQt5.QtWidgets import QVBoxLayout, QHBoxLayout, QDialog, QLabel, QWidget, QComboBox
import numpy as np
import matplotlib
matplotlib.use("QtAgg")
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from matplotlib.lines import Line2D

class DisplayScreenImages(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Screen Images")
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)
        self.setMinimumSize(800, 500)
        self.resize(1000, 650)
        self.setSizeGripEnabled(True)
        self._plot_data = None
        self.figure = Figure(figsize=(10, 6), constrained_layout=True)
        self.canvas = FigureCanvas(self.figure)
        plot_widget = QWidget(self)
        plot_layout = QVBoxLayout(plot_widget)
        plot_layout.setContentsMargins(0, 0, 0, 0)
        plot_layout.addWidget(self.canvas)
        header = QWidget(self)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.addStretch(1)
        layout = QVBoxLayout(self)
        layout.addWidget(header)
        layout.addWidget(plot_widget)
