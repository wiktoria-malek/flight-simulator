try:
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QVBoxLayout, QHBoxLayout, QDialog, QLabel, QWidget, QComboBox, QSizePolicy
except ImportError:
    from PyQt5.QtCore import Qt
    from PyQt5.QtWidgets import QVBoxLayout, QHBoxLayout, QDialog, QLabel, QWidget, QComboBox, QSizePolicy
import numpy as np
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use("QtAgg")
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from Backend.draw_beamline_script import drawBeamline

class ShowBeamline(QDialog):
    def __init__(self, interface, parent=None):
        super().__init__(parent)
        self.interface = interface
        self.lattice = getattr(self.interface, "lattice", None)
        self.setWindowTitle("Beamline View")
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)
        self.setMinimumSize(800, 500)
        self.resize(1000, 650)
        self.setSizeGripEnabled(True)
        self.session = None
        self.figure = Figure(figsize=(10, 6), constrained_layout=True)
        self.canvas = FigureCanvas(self.figure)
        self.canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        plot_widget = QWidget(self)
        plot_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        plot_layout = QVBoxLayout(plot_widget)
        plot_layout.setContentsMargins(0, 0, 0, 0)
        plot_layout.setSpacing(0)
        plot_layout.addWidget(self.canvas, 1)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)
        layout.addWidget(plot_widget, 1)

    def _display_beamline_view(self, quad_selected=None, screens = None):
        L = self.lattice
        self.figure.clear()
        ax = self.figure.subplots(1, 1)
        drawer = drawBeamline(ax)
        L.accept(drawer)
        self.canvas.draw()

    def update_beamline_view(self, quad_selected=None, screens = None):
        pass


