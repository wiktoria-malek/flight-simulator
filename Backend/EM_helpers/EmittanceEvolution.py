try:
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QVBoxLayout, QDialog, QLabel, QSizePolicy
except ImportError:
    from PyQt5.QtCore import Qt
    from PyQt5.QtWidgets import QVBoxLayout, QDialog, QLabel, QSizePolicy
import numpy as np
import matplotlib
matplotlib.use("QtAgg")
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure


class EmittanceEvolution(QDialog):
    def __init__(self, interface, parent=None, screens=None):
        super().__init__(parent)
        self.setWindowTitle("Emittance evolution")
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)
        self.setMinimumSize(800, 500)
        self.resize(1000, 650)
        self.setSizeGripEnabled(True)
        self.interface = interface
        self.screens = list(screens or [])
        self.figure = Figure(figsize=(10, 6), constrained_layout=True)
        self.canvas = FigureCanvas(self.figure)
        self.canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.header = QLabel("", self)
        self.header.setWordWrap(True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)
        layout.addWidget(self.header, 0)
        layout.addWidget(self.canvas, 1)

    def _model_interface(self):
        return getattr(self.interface, "tracking_interface", self.interface)

    def _plot_plane(self, axes, s, emittance, fitted, fitted_error, names, label, colour):
        axes.plot(s, emittance, "o-", color=colour, label=f"RF-Track model {label}")
        for position, value, name in zip(s, emittance, names):
            if np.isfinite(value):
                axes.annotate(f"{name}\n{value:.4g}", (position, value), textcoords="offset points",
                              xytext=(0, 8), ha="center", fontsize=7)
        if np.isfinite(fitted):
            axes.axhline(fitted, color="k", linestyle="--", linewidth=1.0, label=f"fit {label} = {fitted:.4g}")
            if np.isfinite(fitted_error) and fitted_error > 0:
                axes.axhspan(fitted - fitted_error, fitted + fitted_error, color="k", alpha=0.08)
        axes.set_ylabel(f"{label} [mm·mrad]")
        axes.margins(x=0.08, y=0.22)
        axes.grid(True, alpha=0.3)
        axes.legend(fontsize=8, loc="best")

    def _display_emittance_evolution(self, screens=None, result=None):
        if screens is not None:
            self.screens = list(screens)
        self.figure.clear()
        axes_x = self.figure.add_subplot(2, 1, 1)
        axes_y = self.figure.add_subplot(2, 1, 2, sharex=axes_x)

        try:
            emittance = self._model_interface().get_emittance_at_screens(names=self.screens or None)
        except Exception as e:
            self.header.setText(f"RF-Track model could not be read: {e}")
            self.canvas.draw_idle()
            return

        names = list(emittance.get("names", []))
        if not names:
            self.header.setText("No tracked bunch is available on the selected screens. Track the model beam first.")
            self.canvas.draw_idle()
            return

        s = np.asarray(emittance["S"], dtype=float)
        emit_x = np.asarray(emittance["emitt_x"], dtype=float)
        emit_y = np.asarray(emittance["emitt_y"], dtype=float)
        result = result if isinstance(result, dict) else {}

        self._plot_plane(axes_x, s, emit_x, float(result.get("emit_x_norm", np.nan)),
                         float(result.get("emit_x_norm_err", np.nan)), names, "εₓ (norm.)", "tab:blue")
        self._plot_plane(axes_y, s, emit_y, float(result.get("emit_y_norm", np.nan)),
                         float(result.get("emit_y_norm_err", np.nan)), names, "εᵧ (norm.)", "tab:red")
        axes_y.set_xlabel("S [m]")
        axes_x.set_title("Normalised emittance predicted by RF-Track at the selected screens")

        growth_x = emit_x[-1] / emit_x[0] - 1.0 if emit_x.size > 1 and emit_x[0] > 0 else np.nan
        growth_y = emit_y[-1] / emit_y[0] - 1.0 if emit_y.size > 1 and emit_y[0] > 0 else np.nan
        self.header.setText(
            f"Current model state, {len(names)} screen(s): {', '.join(names)}.  "
            f"Δεₓ = {100.0 * growth_x:.2f} %, Δεᵧ = {100.0 * growth_y:.2f} % between the first and the last screen.  "
            "The bunch is the one tracked with the model's present magnet settings, not a re-tracking of the fit result."
        )
        self.canvas.draw_idle()
