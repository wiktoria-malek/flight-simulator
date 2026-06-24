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

    def plot_screen_images(self, result, reference_name=None, screen_parameters = None):
        self.figure.clear()

        if not isinstance(result, dict):
            ax = self.figure.add_subplot(111)
            ax.text(0.5, 0.5, "No screen readings provided.", ha="center", va="center", transform=ax.transAxes)
            ax.axis("off")
            self.canvas.draw_idle()
            return

        screens_readings = []
        reference_label = reference_name or "screen readings"
        screens_readings.append((
            reference_label,
            {
                "sigma_x": result.get("sigx", np.nan),
                "sigma_y": result.get("sigy", np.nan),
                "K1": result.get("K1", np.nan),
                "intensity_x": result.get("intensity_x", np.nan),
                "intensity_y": result.get("intensity_y", np.nan),
            }))

        if isinstance(screen_parameters, dict):
            screens_dict = screen_parameters.get("screens", screen_parameters)
            if isinstance(screens_dict, dict):
                for screen_name, values in screens_dict.items():
                    if isinstance(values, dict):
                        screens_readings.append((str(screen_name), values))

        self._plot_data = {
            "result": result,
            "screens_readings": screens_readings,
        }

        self.location_combo.blockSignals(True)
        self.location_combo.clear()
        for name, _ in screens_twiss:
            self.location_combo.addItem(str(name))
        self.location_combo.blockSignals(False)
        self._redraw_current_location()

    def _redraw_current_location(self):
        self.figure.clear()
        if not isinstance(self._plot_data, dict):
            self.canvas.draw_idle()
            return
        locations = self._plot_data.get("screens_readings", [])
        if not locations:
            ax = self.figure.add_subplot(111)
            ax.text(0.5, 0.5, "No images to display.", ha="center", va="center", transform=ax.transAxes)
            ax.axis("off")
            self.canvas.draw_idle()
            return

        idx = int(self.location_combo.currentIndex())
        if idx < 0 or idx >= len(locations):
            idx = 0
        location_name, values = locations[idx]

        sigx = values.get("sigx", np.nan)
        sigx = values.get("sigy", np.nan)
        K1 = values.get("K1", np.nan)
        intensity_x = values.get("intensity_x", np.nan)
        intensity_y = values.get("intensity_y", np.nan)
        ax_x = self.figure.add_subplot(121)
        ax_y = self.figure.add_subplot(122)

        def draw_one(ax, sigx, sigy, intensity_x, intensity_y):
            ax.axhline(0.0, color="0.5", linestyle=":", linewidth=1.0)
            ax.axvline(0.0, color="0.5", linestyle=":", linewidth=1.0)
            ax.grid(True, alpha=0.3)
            ax.set_aspect("equal", adjustable="box")
            ax.set_xlabel("σx")
            ax.set_ylabel("σy")
            ax.set_title("Screen Image")
            try:
                ax.set_box_aspect(1.0)
            except Exception:
                pass
            ax.set_aspect("equal", adjustable="datalim")
            beta0 = float(beta0)
            alpha0 = float(alpha0)
            theta_ref = np.linspace(0.0, 2.0 * np.pi, 500)
            ax.plot(np.cos(theta_ref), np.sin(theta_ref), color="black", linestyle="--", linewidth=1.2, alpha=0.7)
            ax.plot(u, up, color="black", linewidth=2.0)
            reference_name = str(self._plot_data.get("projection_reference", ""))

        draw_one(ax_x, sigx, sigy, intensity_x, intensity_y, "Screen Image")
        self.canvas.draw_idle()

