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
    def __init__(self, interface, parent=None, quad_selected=None, screens = None):
        super().__init__(parent)
        self.interface = interface
        self.quad_selected = str(quad_selected[0])
        self.screens = [str(screen) for screen in screens]
        self.lattice = getattr(self.interface, "lattice", None)
        self.setWindowTitle("Beamline View")
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)
        self.setMinimumSize(800, 500)
        self.resize(1000, 650)
        self.setSizeGripEnabled(True)
        self.figure = Figure(figsize=(10, 6), constrained_layout=True)
        self.canvas = FigureCanvas(self.figure)
        self.canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        plot_widget = QWidget(self)
        plot_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        plot_layout = QVBoxLayout(plot_widget)
        plot_layout.setContentsMargins(0, 0, 0, 0)
        plot_layout.setSpacing(0)
        plot_layout.addWidget(self.canvas, 1)
        header = QWidget(self)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.addWidget(QLabel("Start element:", self))
        self.start_element_combobox = QComboBox(self)
        self.start_element_combobox.currentIndexChanged.connect(self.update_beamline_view)
        header_layout.addWidget(self.start_element_combobox)
        header_layout.addWidget(QLabel("Last element:", self))
        self.last_element_combobox = QComboBox(self)
        self.last_element_combobox.currentIndexChanged.connect(self.update_beamline_view)
        header_layout.addWidget(self.last_element_combobox)
        header_layout.addStretch(1)
        self.last_screen = self.screens[-1]

        mapped_quad_elements = self.interface._map_quadrupoles_names_from_lattice(self.quad_selected)

        if not isinstance(mapped_quad_elements, list):
            mapped_quad_elements = [mapped_quad_elements]
        self.start_element_name = mapped_quad_elements[0].get_name()
        start_positions = self.interface._get_elements_positions(names=self.start_element_name)["S"]
        self.first_element_position = float(start_positions[0])
        self.last_element_position = self.interface._get_elements_positions(names = self.last_screen)['S'][0]

        self.lattice_names = self.interface._get_elements_positions()["names"]
        self.start_element_combobox.addItems([str(e) for e in self.lattice_names])
        self.last_element_combobox.addItems([str(e) for e in self.lattice_names])

        self.start_element_combobox.setCurrentText(self.start_element_name)
        self.last_element_combobox.setCurrentText(self.last_screen)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)
        layout.addWidget(header, 0)
        layout.addWidget(plot_widget, 1)

    def _display_beamline_view(self):
        start_element = self.start_element_combobox.currentText()
        last_element = self.last_element_combobox.currentText()
        self.figure.clear()
        ax = self.figure.subplots(1, 1)
        drawer = drawBeamline(ax)
        ax.set_xlim(self.first_element_position, self.last_element_position)
        self.lattice.accept(drawer)
        self.canvas.draw()

    def update_beamline_view(self, quad_selected=None, screens = None):
        pass


