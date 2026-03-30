import os
import sys
import numpy as np
import matplotlib
matplotlib.use("QtAgg")

from datetime import datetime
from scipy.optimize import least_squares

try:
    from PyQt6 import uic
    from PyQt6.QtWidgets import (
        QApplication, QMainWindow, QMessageBox, QVBoxLayout
    )
except ImportError:
    from PyQt5 import uic
    from PyQt5.QtWidgets import (
        QApplication, QMainWindow, QMessageBox, QVBoxLayout
    )

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from Backend.SaveOrLoad import SaveOrLoad
from Backend.EmittanceMeasurement import EmittanceMeasurement
from Backend.MeasureOptics import MeasureOptics


class MatplotlibWidget(FigureCanvas):
    def __init__(self, parent=None):
        self.figure = Figure(figsize=(6, 4), tight_layout=True)
        super().__init__(self.figure)
        self.setParent(parent)


class MainWindow(QMainWindow, SaveOrLoad, EmittanceMeasurement):

    def __init__(self, interface, dir_name):
        super().__init__()

        self.interface = interface
        self.dir_name = dir_name
        self.session = None

        ui_path = os.path.join(os.path.dirname(__file__),"UI files/Emittance_Measurement_GUI.ui")
        uic.loadUi(ui_path, self)

        self.setWindowTitle("Emittance Measurement GUI")
        self.fitResultsVBox.setStretch(0, 0)
        self.fitResultsVBox.setStretch(1, 1)

        self.canvas = MatplotlibWidget(self.plotPlaceholder)
        layout = self.plotPlaceholder.layout()
        if layout is None:
            layout = QVBoxLayout(self.plotPlaceholder)
        layout.addWidget(self.canvas)

        quadrupoles = list(self.interface.get_quadrupoles()["names"])

        screens_data = self.interface.get_screens()
        screens = list(screens_data["names"])
        screens_S = np.asarray(screens_data["S"], dtype=float)

        screen_pairs = sorted(zip(screens, screens_S),key=lambda x: x[1] if np.isfinite(x[1]) else np.inf) # assigns S position to each screen
        screens_sorted = [name for name, _ in screen_pairs] # only names

        self.quadrupoles_list.insertItems(0, quadrupoles)
        self.screens_list.insertItems(0, screens_sorted)

        self.first_screen_choice.clear()
        self.first_screen_choice.addItems(screens_sorted)

        self.quad_on_plot.clear()
        self.quad_on_plot.addItems(quadrupoles)

        self.screen_on_plot.clear()
        self.screen_on_plot.addItems(screens_sorted)

        self.start_button.clicked.connect(self._run_scan)
        self.measure_optics_button.clicked.connect(self._run_measure_optics)
        self.fit_emm_twiss_button.clicked.connect(self._fit_twiss_and_emittance)

        self._clear_fit_panel()
        self._reset_canvas()

    def _clear_fit_panel(self):
        self.result_reference_screen.setText("-")
        self.result_quad.setText("-")
        self.result_emit_x_norm.setText("-")
        self.result_emit_y_norm.setText("-")
        self.result_beta_x0.setText("-")
        self.result_alpha_x0.setText("-")
        self.result_beta_y0.setText("-")
        self.result_alpha_y0.setText("-")

    def _update_fit_panel(self, result):
        self.result_reference_screen.setText(str(result["screen0"]))
        self.result_quad.setText(str(result["quad_name"]))

        self.result_emit_x_norm.setText(f"{result['emit_x_norm']:.4f} mm·mrad")
        self.result_emit_y_norm.setText(f"{result['emit_y_norm']:.4f} mm·mrad")

        self.result_beta_x0.setText(f"{result['beta_x0']:.4f} m")
        self.result_alpha_x0.setText(f"{result['alpha_x0']:.4f}")
        self.result_beta_y0.setText(f"{result['beta_y0']:.4f} m")
        self.result_alpha_y0.setText(f"{result['alpha_y0']:.4f}")

    def _reset_canvas(self):
        fig = self.canvas.figure
        fig.clear()
        ax = fig.add_subplot(111)
        ax.set_title("Quadrupole scan")
        ax.set_xlabel("K1")
        ax.set_ylabel("Beam size")
        ax.grid(True, alpha=0.3)
        self.canvas.draw()

    def _get_sorted_selected_screens(self):
        selected = [it.text() for it in self.screens_list.selectedItems()]

        all_screens_data = self.interface.get_screens()
        all_names = list(all_screens_data["names"])
        all_S = np.asarray(all_screens_data["S"], dtype=float)

        if not selected:
            selected = all_names

        screen_to_S = {n: s for n, s in zip(all_names, all_S)}
        selected = sorted(selected,key=lambda name: screen_to_S.get(name, np.inf)) # lambda is a function def key(name)
        return selected

    def _draw_live_scan(self, session):
        if session is None:
            return

        K1_values = np.asarray(session["K1_values"], dtype=float)
        sigx = np.asarray(session["sigx_mean"], dtype=float)
        sigy = np.asarray(session["sigy_mean"], dtype=float)
        screens = list(session["screens"])
        quad_name = session.get("quad_name", "-")

        fig = self.canvas.figure
        fig.clear()

        ax1 = fig.add_subplot(211)
        ax2 = fig.add_subplot(212, sharex=ax1)

        for i, screen in enumerate(screens):
            mask_x = np.isfinite(sigx[:, i])
            mask_y = np.isfinite(sigy[:, i])

            ax1.plot(K1_values[mask_x], sigx[mask_x, i], 'o-', label=screen)
            ax2.plot(K1_values[mask_y], sigy[mask_y, i], 'o-', label=screen)

        title = f"Quadrupole scan: {quad_name}"
        ax1.set_title(title)
        ax1.set_ylabel("sigx")
        ax2.set_ylabel("sigy")
        ax2.set_xlabel("K1")

        ax1.grid(True, alpha=0.3)
        ax2.grid(True, alpha=0.3)
        ax1.legend(fontsize=8, ncol=2)
        ax2.legend(fontsize=8, ncol=2)

        fig.tight_layout()
        self.canvas.draw()

    def _plot_fit_overlay(self, pred_x, pred_y, result=None):
        if self.session is None:
            return

        K1_values = np.asarray(self.session["K1_values"], dtype=float)
        sigx = np.asarray(self.session["sigx_mean"], dtype=float)
        sigy = np.asarray(self.session["sigy_mean"], dtype=float)
        screens = list(self.session["screens"])

        fig = self.canvas.figure
        fig.clear()

        ax1 = fig.add_subplot(211)
        ax2 = fig.add_subplot(212, sharex=ax1)

        for i, screen in enumerate(screens):
            ax1.plot(K1_values, sigx[:, i], 'o', label=f"{screen} data")
            fit_x = np.sqrt(np.maximum(pred_x[:, i], 0.0))
            ax1.plot(K1_values, fit_x, '-', label=f"{screen} fit")

            ax2.plot(K1_values, sigy[:, i], 'o', label=f"{screen} data")
            fit_y = np.sqrt(np.maximum(pred_y[:, i], 0.0))
            ax2.plot(K1_values, fit_y, '-', label=f"{screen} fit")

        ax1.set_ylabel("sigx")
        ax2.set_ylabel("sigy")
        ax2.set_xlabel("K1")

        ax1.grid(True, alpha=0.3)
        ax2.grid(True, alpha=0.3)
        ax1.legend(fontsize=7, ncol=2)
        ax2.legend(fontsize=7, ncol=2)

        fig.tight_layout()
        self.canvas.draw()

    def _scan_progress_callback(self, session_partial, current_step, total_steps): # refreshes plot in the gui
        self.session = session_partial
        self._draw_live_scan(session_partial)
        QApplication.processEvents()

    def _run_scan(self):

        current_quad = self.quadrupoles_list.currentItem()
        if current_quad is None:
            QMessageBox.information(self, "Scan error", "No quadrupole selected.")
            return

        quad_name = current_quad.text()
        self.quad_on_plot.clear()
        self.quad_on_plot.addItem(quad_name)
        self.quad_on_plot.setCurrentText(quad_name)
        screens = self._get_sorted_selected_screens()
        self.screen_on_plot.clear()
        self.screen_on_plot.addItems(screens)
        if screens:
            self.screen_on_plot.setCurrentText(screens[0])
        if not screens:
            QMessageBox.information(self, "Scan error", "No screens available.")
            return

        delta_min = float(self.delta_min_scan.value())
        delta_max = float(self.delta_max_scan.value())
        steps = int(self.steps_settings.value())
        nshots = int(self.meas_per_step.value())

        self._clear_fit_panel()

        try:
            self.session = self.run_scan(
                quad_name=quad_name,
                delta_min=delta_min,
                delta_max=delta_max,
                steps=steps,
                nshots=nshots,
                screens=screens,
                reference_screen=screens[0],
                bpms=[],
                progress_callback=self._scan_progress_callback
            )
        except TypeError:
            QMessageBox.information(self,"Scan error","Error")
            return
        except Exception as e:
            QMessageBox.information(self, "Scan error", str(e))
            return

        self._draw_live_scan(self.session)
        QMessageBox.information(self, "Scan", "Scan completed.")

    def _run_measure_optics(self):
        if self.session is None:
            QMessageBox.information(self, "Error", "No session.")
            return
        try:
            measure_tool = MeasureOptics(self.interface, n_starts=5)
            optics = measure_tool.get_from_session(self.session)
        except Exception as e:
            QMessageBox.information(self, "Measure Optics", str(e))
            return

        self.session["measured_optics"] = optics
        QMessageBox.information(self, "Measure Optics", "Completed.")

    def _fit_twiss_and_emittance(self):

        if self.session is None:
            QMessageBox.information(self, "Fit", "No session.")
            return

        measured_optics = self.session.get("measured_optics")
        if not measured_optics:
            QMessageBox.information(self, "Fit", "Run Measure Optics first.")
            return

        screens = list(self.session["screens"])
        K1_values = np.asarray(self.session["K1_values"], dtype=float)
        sigx = np.asarray(self.session["sigx_mean"], dtype=float)
        sigy = np.asarray(self.session["sigy_mean"], dtype=float)
        sigx_std = np.asarray(self.session["sigx_std"], dtype=float)
        sigy_std = np.asarray(self.session["sigy_std"], dtype=float)

        nsteps = len(K1_values)
        nscreens = len(screens)

        def fit_plane(sig, sig_std, plane):

            sigma2 = sig ** 2
            sigma2_err = 2.0 * np.abs(sig) * np.abs(sig_std)
            sigma2_err[sigma2_err <= 0] = np.nan

            fit = measured_optics[f"fit_{plane}"]
            K1_nom = float(measured_optics["K1_nom"])

            beta0_vals, alpha0_vals = MeasureOptics._twiss_from_fit_params(fit, K1_values, K1_nom)
            t_params = np.asarray(fit["transport_params"], dtype=float) # it takes R11 and R12 for downstream screens

            def predict_emit(emit):
                pred = np.zeros((nsteps, nscreens), dtype=float)

                for k in range(nsteps):
                    beta0 = float(beta0_vals[k]) # twiss params for screen0 at each K1
                    alpha0 = float(alpha0_vals[k])
                    gamma0 = (1.0 + alpha0**2) / beta0

                    pred[k, 0] = emit * beta0

                    for i, (R11, R12) in enumerate(t_params):
                        pred[k, i + 1] = emit * (R11**2 * beta0- 2.0 * R11 * R12 * alpha0 + R12**2 * gamma0)

                return pred

            # initial guess from nominal screen0
            nom_idx = int(np.argmin(np.abs(np.asarray(self.session["deltas"], dtype=float))))
            emit_guess = max(sigma2[nom_idx, 0] / max(beta0_vals[nom_idx], 1e-12), 1e-12) # emit_guess = sigma_0^2 / beta0

            x0 = np.array([np.log(emit_guess)], dtype=float) # exp, because emit must be positive

            def residuals(p):
                emit = float(np.exp(p[0]))
                pred = predict_emit(emit)

                res = []
                for k in range(nsteps):
                    for i in range(nscreens):
                        y = sigma2[k, i]
                        yp = pred[k, i]
                        err = sigma2_err[k, i]

                        if np.isfinite(y) and np.isfinite(yp):
                            if np.isfinite(err):
                                res.append((yp - y) / err)
                            else:
                                res.append(yp - y)
                return np.asarray(res)

            lsq = least_squares(residuals, x0, method="trf")
            emit = float(np.exp(lsq.x[0]))
            pred = predict_emit(emit)

            beta0_nom = float(beta0_vals[nom_idx])
            alpha0_nom = float(alpha0_vals[nom_idx])

            return emit, beta0_nom, alpha0_nom, pred

        emit_x, beta_x0, alpha_x0, pred_x = fit_plane(sigx, sigx_std, "x")
        emit_y, beta_y0, alpha_y0, pred_y = fit_plane(sigy, sigy_std, "y")

        try:
            gamma_rel = (self.interface.Pref + self.interface.electronmass) / self.interface.electronmass
            beta_rel = np.sqrt(1 - 1 / gamma_rel**2)
            emit_x_norm = gamma_rel * beta_rel * emit_x
            emit_y_norm = gamma_rel * beta_rel * emit_y
        except Exception:
            emit_x_norm = np.nan
            emit_y_norm = np.nan

        result = {
            "screen0": screens[0],
            "quad_name": self.session["quad_name"],
            "emit_x_norm": emit_x_norm,
            "emit_y_norm": emit_y_norm,
            "beta_x0": beta_x0,
            "alpha_x0": alpha_x0,
            "beta_y0": beta_y0,
            "alpha_y0": alpha_y0,
        }

        self.session["fit_result_twiss_emit"] = result

        self._update_fit_panel(result)
        self._plot_fit_overlay(pred_x, pred_y, result=result)

        QMessageBox.information(
            self,
            "Fit complete",
            f"εₓ = {emit_x_norm:.4f} mm·mrad\n"
            f"εᵧ = {emit_y_norm:.4f} mm·mrad"
        )

if __name__ == "__main__":

    app = QApplication(sys.argv)

    from Backend import SelectInterface
    interface = SelectInterface.choose_acc_and_interface()

    if interface is None:
        sys.exit(0)

    project_name = (
        interface.get_name()
        if hasattr(interface, "get_name")
        else type(interface).__name__
    )

    time_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    dir_name = os.path.expanduser(
        f"~/flight-simulator-data/EM_{project_name}_{time_str}"
    )

    w = MainWindow(interface, dir_name)
    w.show()
    sys.exit(app.exec())