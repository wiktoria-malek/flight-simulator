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


class PhaseSpaces(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Phase Space Graphs")
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

        self.location_combo = QComboBox(self)
        self.location_combo.currentIndexChanged.connect(self._redraw_current_location)
        header = QWidget(self)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.addStretch(1)
        header_layout.addWidget(QLabel("Location:", self))
        header_layout.addWidget(self.location_combo)
        layout = QVBoxLayout(self)
        layout.addWidget(header)
        layout.addWidget(plot_widget)


    @staticmethod
    def _ellipse_points(beta0, alpha0):
        '''
        gamma * x^2 + 2*alpha*x*x'+ beta x'^2 = emittance
        gamma = (1+alpha^2)/beta
        In normalised coordinates:
        u = x / sqrt(emittance)
        u' = x' / sqrt(emittance)
        And then:
        gamma * u^2 + 2 * alpha * u * u' + beta * u'^2 = 1
        u = sqrt(beta) * cos(theta)
        u' = -(alpha * cos(theta) + sin(theta)) / sqrt(beta)

        If you substitute u and u' above gamma * u^2 + 2 * alpha * u * u' + beta * u'^2 = 1,
        one gets cos(theta)^2 + sin(theta)^2 = 1, so an ellipse.
        '''

        beta0 = float(beta0)
        alpha0 = float(alpha0)

        theta = np.linspace(0.0, 2.0 * np.pi, 500)
        u = np.sqrt(beta0) * np.cos(theta)
        up = -(alpha0 * np.cos(theta) + np.sin(theta)) / np.sqrt(beta0)

        return u, up

    @staticmethod
    def _is_valid(beta0, alpha0):
        try:
            beta0 = float(beta0)
            alpha0 = float(alpha0)
        except Exception:
            return False

        return np.isfinite(beta0) and np.isfinite(alpha0) and beta0 > 0.0

    def plot_from_result(self, result, reference_name=None, screen_parameters = None):
        self.figure.clear()

        if not isinstance(result, dict):
            ax = self.figure.add_subplot(111)
            ax.text(0.5, 0.5, "No optimization result provided.", ha="center", va="center", transform=ax.transAxes)
            ax.axis("off")
            self.canvas.draw_idle()
            return

        screens_twiss = []
        reference_label = reference_name or "fitted scan reference"
        screens_twiss.append((
            reference_label,
            {
                "beta_x": result.get("beta_x0", np.nan),
                "beta_y": result.get("beta_y0", np.nan),
                "alpha_x": result.get("alpha_x0", np.nan),
                "alpha_y": result.get("alpha_y0", np.nan),
                "emit_x_norm": result.get("emit_x_norm", np.nan),
                "emit_y_norm": result.get("emit_y_norm", np.nan),
            }))

        if isinstance(screen_parameters, dict):
            screens_dict = screen_parameters.get("screens", screen_parameters)
            if isinstance(screens_dict, dict):
                for screen_name, values in screens_dict.items():
                    if isinstance(values, dict):
                        screens_twiss.append((str(screen_name), values))

        self._plot_data = {
            "result": result,
            "screens_twiss": screens_twiss,
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
        locations = self._plot_data.get("screens_twiss", [])
        if not locations:
            ax = self.figure.add_subplot(111)
            ax.text(0.5, 0.5, "No data to build phase-space ellipse available.", ha="center", va="center", transform=ax.transAxes)
            ax.axis("off")
            self.canvas.draw_idle()
            return

        idx = int(self.location_combo.currentIndex())
        if idx < 0 or idx >= len(locations):
            idx = 0
        location_name, values = locations[idx]
        beta_x = values.get("beta_x", values.get("beta_x0", np.nan))
        alpha_x = values.get("alpha_x", values.get("alpha_x0", np.nan))
        beta_y = values.get("beta_y", values.get("beta_y0", np.nan))
        alpha_y = values.get("alpha_y", values.get("alpha_y0", np.nan))
        emit_x_norm = values.get("emit_x_norm", np.nan)
        emit_y_norm = values.get("emit_y_norm", np.nan)
        ax_x = self.figure.add_subplot(121)
        ax_y = self.figure.add_subplot(122)

        def draw_one(ax, beta0, alpha0, emit_norm, plane_label):
            ax.axhline(0.0, color="0.5", linestyle=":", linewidth=1.0)
            ax.axvline(0.0, color="0.5", linestyle=":", linewidth=1.0)
            ax.grid(True, alpha=0.3)
            ax.set_aspect("equal", adjustable="box")
            ax.set_xlabel("Position")
            ax.set_ylabel("Angle")

            try:
                ax.set_box_aspect(1.0)
            except Exception:
                pass
            ax.set_aspect("equal", adjustable="datalim")
            if not self._is_valid(beta0, alpha0):
                ax.text(
                    0.5, 0.5,
                    "Invalid fitted Twiss",
                    ha="center",
                    va="center",
                    transform=ax.transAxes,
                )
                return

            beta0 = float(beta0)
            alpha0 = float(alpha0)
            u, up = self._ellipse_points(beta0, alpha0)
            ax.plot(u, up, color="blue", linewidth=2.0, label="fitted ellipse")
            pad = 1.25
            ax.set_xlim(np.nanmin(u) * pad, np.nanmax(u) * pad)
            ax.set_ylim(np.nanmin(up) * pad, np.nanmax(up) * pad)
            ax.legend(fontsize=8)

            try:
                emit_norm_float = float(emit_norm)
            except Exception:
                emit_norm_float = np.nan

        draw_one(ax_x, beta_x, alpha_x, emit_x_norm, "Normalised Horizontal Phase Space")
        draw_one(ax_y, beta_y, alpha_y, emit_y_norm, "Normalised Vertical Phase Space")
        self.figure.suptitle(f"Location: {location_name}", fontsize=11)
        self.canvas.draw_idle()

    @staticmethod
    def _draw_projection_lines(ax, R11, R12, sigma_over_sqrt_emit, color=None, label=None):
        '''
        R11 * u0 + R12 * u0' = ± sigma_screen
        but we draw normalised quantitites, so:
        U = u0 / sqrt(epsilon)
        U' = u0' / sqrt(epsilon)
        So:
        R11 * U * sqrt(epsilon) + R12 * U' * sqrt(epsilon) = sigma_screen
        R11 * U + R12 * U' = sigma_screen/sqrt(epsilon)

        horizontal line: U
        vertical line: U'
        y = U' = (sigma_screen/sqrt(epsilon) - R11 * U) / R12
        '''
        pass

    def _plot(self, interface, screens, quad_name, sigx, sigy, result, step_index=None):
        '''
        The colored lines are the constraints from each screen. For one screen i:
        u_i = R11_i * u0 + R12_i * u0'
        '''
        pass