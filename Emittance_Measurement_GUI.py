import os, sys, pickle
import numpy as np
import matplotlib
matplotlib.use("QtAgg")
import matplotlib.colors as mcolors
from datetime import datetime
from scipy.optimize import least_squares
from scipy.stats import median_abs_deviation
try:
    from PyQt6 import uic
    from PyQt6.QtWidgets import (
        QApplication, QMainWindow, QMessageBox, QVBoxLayout
    )
    from PyQt6.QtCore import Qt, QTimer
except ImportError:
    from PyQt5 import uic
    from PyQt5.QtWidgets import (
        QApplication, QMainWindow, QMessageBox, QVBoxLayout
    )
    from PyQt5.QtCore import Qt, QTimer

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from Backend.SaveOrLoad import SaveOrLoad
from Backend.MeasureTrajectoryResponse import MeasureTrajectoryResponse
from Backend.EmittanceMeasurement import EmittanceMeasurement
from Backend.MeasureOptics import MeasureOptics

class MatplotlibWidget(FigureCanvas):
    def __init__(self, parent=None):
        self.figure = Figure(figsize=(6, 4), tight_layout=True)
        super().__init__(self.figure)
        self.setParent(parent)


class MainWindow(QMainWindow, SaveOrLoad, EmittanceMeasurement):
    def _describe_scan_quality(self):
        if self.session is None:
            return None
        quality = self.session.get("scan_quality")
        if not quality:
            return None

        best_x = quality.get("best_rel_var_x")
        best_y = quality.get("best_rel_var_y")
        best_screen_x = quality.get("best_screen_x")
        best_screen_y = quality.get("best_screen_y")
        recommendation = quality.get("recommendation", "unknown")

        def fmt(v):
            return "n/a" if v is None else f"{100.0 * float(v):.1f}%"

        return (
            f"Scan quality\n"
            f"best x variation: {fmt(best_x)} at {best_screen_x}\n"
            f"best y variation: {fmt(best_y)} at {best_screen_y}\n"
            f"recommendation: {recommendation}"
        )

    def _assess_fit_quality(self, result):
        fit_x_rms = result.get("fit_x_residual_rms")
        fit_y_rms = result.get("fit_y_residual_rms")
        fit_x_rms_per_screen = result.get("fit_x_residual_rms_per_screen", {})
        fit_y_rms_per_screen = result.get("fit_y_residual_rms_per_screen", {})
        worst_screen_x = result.get("worst_screen_x")
        worst_screen_y = result.get("worst_screen_y")
        emit_x = result.get("emit_x_norm")
        emit_y = result.get("emit_y_norm")
        beta_x = result.get("beta_x0")
        beta_y = result.get("beta_y0")
        alpha_x = result.get("alpha_x0")
        alpha_y = result.get("alpha_y0")
        beta_x_scale = result.get("beta_x_scale_vs_measured")
        beta_y_scale = result.get("beta_y_scale_vs_measured")
        alpha_x_offset = result.get("alpha_x_offset_vs_measured")
        alpha_y_offset = result.get("alpha_y_offset_vs_measured")

        physical = True
        trustworthy = True
        reasons = []

        def bad(v):
            return v is None or (not np.isfinite(float(v)))

        for label, value in [
            ("emit_x_norm", emit_x),
            ("emit_y_norm", emit_y),
            ("beta_x0", beta_x),
            ("beta_y0", beta_y),
            ("alpha_x0", alpha_x),
            ("alpha_y0", alpha_y),
        ]:
            if bad(value):
                physical = False
                trustworthy = False
                reasons.append(f"{label} is not finite")

        if physical:
            if emit_x <= 0 or emit_y <= 0:
                physical = False
                trustworthy = False
                reasons.append("non-positive emittance")

            if beta_x <= 0 or beta_y <= 0:
                physical = False
                trustworthy = False
                reasons.append("non-positive beta")

            if beta_x > 50.0 or beta_y > 50.0:
                trustworthy = False
                reasons.append("beta is very large")

            if abs(alpha_x) > 5.0 or abs(alpha_y) > 5.0:
                trustworthy = False
                reasons.append("alpha is very large")

            if emit_x > 50.0 or emit_y > 50.0:
                trustworthy = False
                reasons.append("emittance is very large")

        for label, value in [
            ("fit_x_residual_rms", fit_x_rms),
            ("fit_y_residual_rms", fit_y_rms),
            ("beta_x_scale_vs_measured", beta_x_scale),
            ("beta_y_scale_vs_measured", beta_y_scale),
            ("alpha_x_offset_vs_measured", alpha_x_offset),
            ("alpha_y_offset_vs_measured", alpha_y_offset),
        ]:
            if bad(value):
                trustworthy = False
                reasons.append(f"{label} is not finite")

        if not bad(fit_x_rms) and float(fit_x_rms) > 5.0:
            trustworthy = False
            reasons.append("x residual RMS is large")
        if not bad(fit_y_rms) and float(fit_y_rms) > 5.0:
            trustworthy = False
            reasons.append("y residual RMS is large")

        if worst_screen_x is not None:
            wx = fit_x_rms_per_screen.get(worst_screen_x)
            if wx is not None and np.isfinite(float(wx)) and float(wx) > 6.0:
                trustworthy = False
                reasons.append(f"worst x screen is {worst_screen_x}")

        if worst_screen_y is not None:
            wy = fit_y_rms_per_screen.get(worst_screen_y)
            if wy is not None and np.isfinite(float(wy)) and float(wy) > 6.0:
                trustworthy = False
                reasons.append(f"worst y screen is {worst_screen_y}")

        if not bad(beta_x_scale) and not (0.4 <= float(beta_x_scale) <= 2.5):
            trustworthy = False
            reasons.append("x beta scale drifted too far from measured optics")
        if not bad(beta_y_scale) and not (0.4 <= float(beta_y_scale) <= 2.5):
            trustworthy = False
            reasons.append("y beta scale drifted too far from measured optics")

        if not bad(alpha_x_offset) and abs(float(alpha_x_offset)) > 2.0:
            trustworthy = False
            reasons.append("x alpha offset is large")
        if not bad(alpha_y_offset) and abs(float(alpha_y_offset)) > 1.0:
            trustworthy = False
            reasons.append("y alpha offset is large")

        if physical and trustworthy:
            status = "trusted"
        elif physical:
            status = "physical_but_untrusted"
        else:
            status = "non_physical"

        return {
            "fit_is_physical": bool(physical),
            "fit_is_trustworthy": bool(trustworthy),
            "fit_quality_status": status,
            "fit_quality_reasons": reasons,
        }

    def __init__(self, interface, dir_name):
        super().__init__()
        self.interface = interface
        self.dir_name = dir_name
        self.session = None
        self.screen_response_file = None

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
        self.screens_list.itemSelectionChanged.connect(self._screen_selection_changed)
        self._filter_quadrupoles_in_gui()
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

        def lighten_plot_color(color, amount = 0.45):
            rgb = np.array(mcolors.to_rgb(color), dtype=float)
            return tuple(rgb + (1.0 - rgb) * amount)

        ax1 = fig.add_subplot(211)
        ax2 = fig.add_subplot(212, sharex=ax1)

        color_cycle = matplotlib.rcParams['axes.prop_cycle'].by_key().get('color', [])
        if not color_cycle:
            color_cycle = ['C0', 'C1', 'C2', 'C3', 'C4', 'C5', 'C6', 'C7', 'C8', 'C9']

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

        def lighten_color(color, amount=0.45):
            import matplotlib.colors as mcolors
            rgb = np.array(mcolors.to_rgb(color), dtype=float)
            return tuple(rgb + (1.0 - rgb) * amount)

        ax1 = fig.add_subplot(211)
        ax2 = fig.add_subplot(212, sharex=ax1)

        color_cycle = matplotlib.rcParams['axes.prop_cycle'].by_key().get('color', [])
        if not color_cycle:
            color_cycle = ['C0', 'C1', 'C2', 'C3', 'C4', 'C5', 'C6', 'C7', 'C8', 'C9']

        for i, screen in enumerate(screens):
            base_color = color_cycle[i % len(color_cycle)]
            fit_color = lighten_color(base_color, amount=0.45)

            ax1.plot(
                K1_values, sigx[:, i], 'o',
                color=base_color,
                label=f"{screen} data"
            )
            fit_x = np.sqrt(np.maximum(pred_x[:, i], 0.0))
            ax1.plot(
                K1_values, fit_x, '-',
                color=fit_color,
                linewidth=2.0,
                label=f"{screen} fit"
            )

            ax2.plot(
                K1_values, sigy[:, i], 'o',
                color=base_color,
                label=f"{screen} data"
            )
            fit_y = np.sqrt(np.maximum(pred_y[:, i], 0.0))
            ax2.plot(
                K1_values, fit_y, '-',
                color=fit_color,
                linewidth=2.0,
                label=f"{screen} fit"
            )

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

        try:
            self.session["screen_response_scans"] = self._measure_screen_response()
        except Exception as e:
            self.session["screen_response_scans"] = None
            QMessageBox.information(self, "Scan error", str(e))

        quality_msg = self._describe_scan_quality()
        if quality_msg is None:
            QMessageBox.information(self, "Scan", "Scan completed.")
        else:
            QMessageBox.information(self, "Scan", f"Scan completed.\n\n{quality_msg}")

    def _run_measure_optics(self):
        if self.session is None:
            QMessageBox.information(self, "Error", "No session.")
            return

        diagnostic_note = None
        fitted_note = None
        transport_source = "measured_fitted"
        self.session["transport_decision"] = {
            "active_transport_source": transport_source,
            "reason": "measured optics / measured transport first, then emittance and Twiss reconstruction",
        }

        try:
            if self.session.get("screen_response_scans") is None:
                self.session["screen_response_scans"] = self._measure_screen_response()
        except Exception:
            self.session["screen_response_scans"] = None

        try:
            transport_tool = MeasureTrajectoryResponse(self.interface)
            measured_transport = transport_tool.get_from_session(self.session)
            self.session["measured_transport"] = measured_transport
            diagnostic_note = self._info_measured_transport()

            measured_fitted_transport = transport_tool.fit_measured_transport_from_session(self.session)
            self.session["measured_fitted_transport"] = measured_fitted_transport
            fitted_note = self._info_measured_fitted_transport()
        except Exception as e:
            self.session["measured_transport"] = None
            self.session["measured_fitted_transport"] = None
            diagnostic_note = f"trajectory-response diagnostic unavailable: {e}"
            fitted_note = None
            QMessageBox.information(self, "Measure Optics", str(e))
            return

        try:
            measure_tool = MeasureOptics(self.interface, n_starts=5, transport_source=transport_source)
            optics = measure_tool.get_from_session(self.session)
        except Exception as e:
            QMessageBox.information(self, "Measure Optics", str(e))
            return

        self.session["measured_optics"] = optics

        msg = f"Completed using {transport_source} transport."
        if diagnostic_note:
            msg += "\n\nTrajectory-response diagnostic:\n" + diagnostic_note
        if fitted_note:
            msg += "\n\nMeasured-fitted transport:\n" + fitted_note
        QMessageBox.information(self, "Measure Optics", msg)

    @staticmethod
    def _fmt_float(value, digits=3):
        try:
            value = float(value)
        except (TypeError, ValueError):
            return "n/a"
        return f"{value:.{digits}f}" if np.isfinite(value) else "n/a"

    def _info_measured_transport(self):
        meas_transport = None if self.session is None else self.session.get("measured_transport")

        if not meas_transport:
            return None

        K1_vals = np.asarray(meas_transport.get("base_K1_values", []), dtype=float)
        mean_rel_x = np.asarray(meas_transport.get("mean_rel_x", []), dtype=float)
        mean_rel_y = np.asarray(meas_transport.get("mean_rel_y", []), dtype=float)
        screens = list(meas_transport.get("screen_names", []))
        correctors = list(meas_transport.get("correctors", []))
        bpm_names = list(meas_transport.get("bpm_names", []))
        raw_bpm_Rxx = np.asarray(meas_transport.get("raw_bpm_Rxx", []), dtype=float)
        raw_bpm_Ryy = np.asarray(meas_transport.get("raw_bpm_Ryy", []), dtype=float)

        if K1_vals.size == 0 or mean_rel_x.ndim != 2 or mean_rel_y.ndim != 2 or len(screens) == 0:
            return None

        lines = []
        lines.append(f"trajectory-response diagnostic, correctors={len(correctors)}, bpms={len(bpm_names)}")
        if raw_bpm_Rxx.ndim == 3:
            lines.append(f"raw_bpm_Rxx shape={raw_bpm_Rxx.shape}")
        if raw_bpm_Ryy.ndim == 3:
            lines.append(f"raw_bpm_Ryy shape={raw_bpm_Ryy.shape}")

        for i, K1 in enumerate(K1_vals):
            x_parts = []
            y_parts = []

            for j, screen in enumerate(screens):
                xval = mean_rel_x[i, j] if i < mean_rel_x.shape[0] and j < mean_rel_x.shape[1] else np.nan
                yval = mean_rel_y[i, j] if i < mean_rel_y.shape[0] and j < mean_rel_y.shape[1] else np.nan

                if np.isfinite(xval):
                    x_parts.append(f"{screen}: {xval:.3f}")
                if np.isfinite(yval):
                    y_parts.append(f"{screen}: {yval:.3f}")

            lines.append(f"K1={K1:.6g}")

            if x_parts:
                lines.append(" mean_rel_x " + ", ".join(x_parts))
            if y_parts:
                lines.append(" mean_rel_y " + ", ".join(y_parts))

        return "\n".join(lines)

    def _info_measured_fitted_transport(self):
        fitted = None if self.session is None else self.session.get("measured_fitted_transport")
        if not isinstance(fitted, dict):
            return None

        screens = list(fitted.get("screen_names", []))
        bx = np.asarray(fitted.get("beta_screen_x", []), dtype=float)
        by = np.asarray(fitted.get("beta_screen_y", []), dtype=float)
        px = np.asarray(fitted.get("transport_params_x", []), dtype=float)
        py = np.asarray(fitted.get("transport_params_y", []), dtype=float)

        lines = []
        lines.append(f"mode={fitted.get('mode', 'unknown')}")
        if px.ndim == 2:
            lines.append(f"transport_params_x shape={px.shape}")
        if py.ndim == 2:
            lines.append(f"transport_params_y shape={py.shape}")
        if len(screens) == bx.size:
            lines.append("beta_screen_x " + ", ".join(f"{s}: {v:.3f}" for s, v in zip(screens, bx) if np.isfinite(v)))
        if len(screens) == by.size:
            lines.append("beta_screen_y " + ", ".join(f"{s}: {v:.3f}" for s, v in zip(screens, by) if np.isfinite(v)))
        return "\n".join(lines)

    def _get_twiss_s_positions(self, names):
        names = list(names)
        positions = [np.nan] * len(names)
        if not hasattr(self.interface, "_get_optics_from_twiss_file"):
            return positions

        try:
            optics = self.interface._get_optics_from_twiss_file()
            optics_names = list(optics.get("names", []))
            optics_s = np.asarray(optics.get("S", []), dtype=float)
            lookup = {
                name: float(optics_s[i])
                for i, name in enumerate(optics_names)
                if i < optics_s.size and np.isfinite(optics_s[i])
            }
            positions = [lookup.get(name, np.nan) for name in names]
        except Exception:
            positions = [np.nan] * len(names)
        return positions

    def _filter_quadrupoles_in_gui(self):
        if not hasattr(self,"quadrupoles_list") or self.quadrupoles_list is None:
            return
        if not hasattr(self,"screens_list") or self.screens_list is None:
            return
        selected_screens = self._get_sorted_selected_screens()
        if not selected_screens:
            return

        screen_position = self._get_twiss_s_positions(selected_screens)
        finite_screen_S = [float(s) for s in screen_position if np.isfinite(s)]
        if not finite_screen_S:
            return
        last_screen_position = max(finite_screen_S)
        current_quad = None
        this_quad = self.quadrupoles_list.currentItem()
        if this_quad is not None:
            current_quad = this_quad.text()

        all_quadrupoles = list(self.interface.get_quadrupoles().get("names",[]))
        quad_S = self._get_twiss_s_positions(all_quadrupoles)

        before_last_screen_quads = [name for name, s in zip(all_quadrupoles, quad_S) if np.isfinite(s) and float(s) < last_screen_position]
        self.quadrupoles_list.blockSignals(True)
        self.quadrupoles_list.clear()
        self.quadrupoles_list.addItems(before_last_screen_quads)

        if current_quad in before_last_screen_quads:
            try:
                match_flag = Qt.MatchFlag.MatchExactly
            except AttributeError:
                match_flag = Qt.MatchExactly
            matching = self.quadrupoles_list.findItems(current_quad, match_flag)
            if matching:
                self.quadrupoles_list.setCurrentItem(matching[0])
            elif self.quadrupoles_list.count() > 0:
                self.quadrupoles_list.setCurrentRow(0)
            self.quadrupoles_list.blockSignals(False)

    def _screen_selection_changed(self):
        self._filter_quadrupoles_in_gui()

    @staticmethod
    def _mean_bpm_axis(bpms, axis):
        names = list(bpms.get("names", []))
        arr = np.asarray(bpms.get(axis, []), dtype=float)
        if arr.ndim == 2:
            values = np.nanmean(arr, axis=0)
        elif arr.ndim == 1:
            values = arr
        else:
            values = np.full(len(names), np.nan, dtype=float)

        if values.size != len(names):
            fixed = np.full(len(names), np.nan, dtype=float)
            n = min(fixed.size, values.size)
            if n:
                fixed[:n] = values[:n]
            values = fixed
        return values

    def _safe_sigma2_errors(self, sig, sig_std):
        sig = np.asarray(sig, dtype=float)
        sig_std = np.asarray(sig_std, dtype=float)

        sigma2 = sig ** 2
        sigma2_err = 2.0 * np.abs(sig) * np.abs(sig_std)

        screen_scale = np.nanmedian(sigma2, axis=0)
        screen_scale = np.where(np.isfinite(screen_scale), screen_scale, np.nan)

        floor_per_screen = np.maximum(0.03 * np.abs(screen_scale), 1e-6)
        floor_per_screen = np.where(np.isfinite(floor_per_screen), floor_per_screen, 1e-6)

        sigma2_err = np.where(np.isfinite(sigma2_err), sigma2_err, np.nan)
        sigma2_err = np.maximum(sigma2_err, floor_per_screen[None, :])
        sigma2_err[~np.isfinite(sigma2_err)] = 1e-6

        return sigma2_err

    def _beam_factors(self):
        gamma_rel, beta_rel = self.interface.get_beam_factors()
        return gamma_rel, beta_rel


    def _fit_plane(self, sig, sig_std, plane, measured_optics):
        screens = list(self.session["screens"])
        K1_values = np.asarray(self.session["K1_values"], dtype=float)
        deltas = np.asarray(self.session["deltas"], dtype=float)

        sig = np.asarray(sig, dtype=float)
        sig_std = np.asarray(sig_std, dtype=float)
        sigma2 = sig ** 2
        sigma2_err = self._safe_sigma2_errors(sig, sig_std)

        nsteps = len(K1_values)
        nscreens = len(screens)

        fit = measured_optics[f"fit_{plane}"]
        K1_nom = float(measured_optics["K1_nom"])
        dK1_values = K1_values - K1_nom
        beta0_measured, alpha0_measured = MeasureOptics._twiss_from_fit_params(fit, K1_values, K1_nom)
        beta0_measured = np.asarray(beta0_measured, dtype=float)
        alpha0_measured = np.asarray(alpha0_measured, dtype=float)
        transport_params = np.asarray(fit["transport_params"], dtype=float)
        screen_scale_params = np.asarray(
            fit.get("screen_scale_params", np.ones(nscreens - 1)),
            dtype=float
        )
        nom_idx = int(np.argmin(np.abs(deltas)))
        beta0_ref = float(beta0_measured[nom_idx])
        alpha0_ref = float(alpha0_measured[nom_idx])
        beta_prior_scale = max(0.08 * abs(beta0_ref), 0.02)
        alpha_prior_scale = 0.20
        emit_guess = max(sigma2[nom_idx, 0] / max(beta0_ref, 1e-12), 1e-12)

        # p[0] = log(emit)
        # p[1] = log(beta_scale)
        # p[2] = alpha_offset
        x0 = np.array([
            np.log(emit_guess),
        ], dtype=float)

        def predict_sigma2(emit):
            beta_step = np.maximum(beta0_measured, 1e-12)
            alpha_step = alpha0_measured
            gamma_step = (1.0 + alpha_step ** 2) / beta_step

            pred = np.zeros((nsteps, nscreens), dtype=float)
            pred[:, 0] = emit * beta_step

            for i, row in enumerate(transport_params):
                row = np.asarray(row, dtype=float).ravel()
                if row.size != 2:
                    raise ValueError(f"Expected constant downstream transport with 2 parameters, got {row.size}")

                R11, R12 = row
                pred[:, i + 1] = emit * screen_scale_params[i] * (
                        R11 ** 2 * beta_step
                        - 2.0 * R11 * R12 * alpha_step
                        + R12 ** 2 * gamma_step
                )

            return pred, beta_step, alpha_step

        def residuals(p):
            emit = float(np.exp(p[0]))
            pred, beta_step, alpha_step = predict_sigma2(emit)

            valid_downstream = (
                    np.isfinite(sigma2[:, 1:]) &
                    np.isfinite(sigma2_err[:, 1:]) &
                    (sigma2_err[:, 1:] > 0)
            )
            pred_downstream = pred[:, 1:]
            meas_downstream = sigma2[:, 1:]
            err_downstream = sigma2_err[:, 1:]

            safe_pred_downstream = np.where(np.isfinite(pred_downstream), pred_downstream, 0.0)
            data_residuals = (safe_pred_downstream - meas_downstream) / err_downstream
            invalid_penalty = np.where(
                valid_downstream & ~np.isfinite(pred_downstream),
                1e6,
                0.0,
            )
            data_residuals = np.where(
                valid_downstream,
                data_residuals + invalid_penalty,
                0.0,
            )

            res = data_residuals[valid_downstream].ravel().tolist()

            y0 = sigma2[nom_idx, 0]
            yp0 = pred[nom_idx, 0]
            err0 = sigma2_err[nom_idx, 0]
            if np.isfinite(y0) and np.isfinite(yp0) and np.isfinite(err0) and err0 > 0:
                res.append(0.25 * (yp0 - y0) / err0)
            elif np.isfinite(y0) and np.isfinite(err0) and err0 > 0:
                res.append(1e6)

            return np.asarray(res, dtype=float)

        lsq = least_squares(
            residuals,
            x0,
            method="trf",
            loss="soft_l1",
            f_scale=1.0,
            bounds=(
                np.array([np.log(1e-8)], dtype=float),
                np.array([np.log(1e3)], dtype=float),
            ),
        )

        emit = float(np.exp(lsq.x[0]))
        pred, beta_step, alpha_step = predict_sigma2(emit)
        beta_scale = 1.0
        alpha_offset = 0.0

        data_res = []
        per_screen_res = {screen: [] for screen in screens}

        for k in range(nsteps):
            for i, screen in enumerate(screens):
                y = sigma2[k, i]
                yp = pred[k, i]
                err = sigma2_err[k, i]

                if np.isfinite(y) and np.isfinite(yp) and np.isfinite(err) and err > 0:
                    if i == 0 and k != nom_idx:
                        continue
                    weight = 0.35 if i == 0 else 1.0
                    r = weight * (yp - y) / err
                    data_res.append(r)
                    per_screen_res[screen].append(r)

        data_res = np.asarray(data_res, dtype=float)

        if data_res.size:
            rms_res = float(np.sqrt(np.mean(data_res ** 2)))
            mad_res = float(median_abs_deviation(data_res, scale="normal"))
        else:
            rms_res = np.nan
            mad_res = np.nan

        per_screen_rms = {}
        for screen, vals in per_screen_res.items():
            vals = np.asarray(vals, dtype=float)
            if vals.size:
                per_screen_rms[screen] = float(np.sqrt(np.mean(vals ** 2)))
            else:
                per_screen_rms[screen] = np.nan

        finite_items = [(screen, val) for screen, val in per_screen_rms.items() if np.isfinite(val)]
        worst_screen = max(finite_items, key=lambda x: x[1])[0] if finite_items else None

        return {
            "emit": emit,
            "beta0": float(beta_step[nom_idx]),
            "alpha0": float(alpha_step[nom_idx]),
            "pred": pred,
            "beta0_measured": beta0_ref,
            "alpha0_measured": alpha0_ref,
            "beta_scale": beta_scale,
            "alpha_offset": alpha_offset,
            "beta_step": beta_step.tolist(),
            "alpha_step": alpha_step.tolist(),
            "residual_rms": rms_res,
            "residual_mad": mad_res,
            "residual_rms_per_screen": per_screen_rms,
            "worst_screen": worst_screen,
            "success": bool(lsq.success),
            "message": str(lsq.message),
            "cost": float(lsq.cost),
        }

    def _measure_screen_response_current_state(self,correctors, delta_corr = 1e-4):
        screens = list(self.session["screens"])
        corr_data0 = self.interface.get_correctors(correctors)
        corr_names = list(corr_data0["names"])
        corr_bdes0 = np.asarray(corr_data0["bdes"], dtype=float)

        configured_bpms = self.session.get("bpms", [])
        bpm_names = [] if configured_bpms is None else list(configured_bpms)
        if not bpm_names:
            try:
                bpm_names = list(self.interface.get_bpms()["names"])
            except Exception:
                bpm_names = []

        ns = len(screens)
        nb = len(bpm_names)
        nc = len(corr_names)
        Rxx = np.full((ns, nc), np.nan, dtype=float)
        Ryy = np.full((ns, nc), np.nan, dtype=float)
        bpm_Rxx = np.full((nb, nc), np.nan, dtype=float)
        bpm_Ryy = np.full((nb, nc), np.nan, dtype=float)

        try:
            for j, _ in enumerate(corr_names):
                vals_p = corr_bdes0.copy()
                vals_m = corr_bdes0.copy()
                vals_p[j] += delta_corr
                vals_m[j] -= delta_corr

                self.interface.set_correctors(corr_names, vals_p.tolist())
                state_p = self.interface.get_state()

                self.interface.set_correctors(corr_names, vals_m.tolist())
                state_m = self.interface.get_state()

                sp = state_p.get_screens(screens)
                sm = state_m.get_screens(screens)

                dx = (np.asarray(sp["x"], dtype=float) - np.asarray(sm["x"], dtype=float)) / (2.0 * delta_corr)
                dy = (np.asarray(sp["y"], dtype=float) - np.asarray(sm["y"], dtype=float)) / (2.0 * delta_corr)

                Rxx[:, j] = dx
                Ryy[:, j] = dy

                if nb:
                    bp = state_p.get_bpms(bpm_names)
                    bm = state_m.get_bpms(bpm_names)
                    bpm_dx = (self._mean_bpm_axis(bp, "x") - self._mean_bpm_axis(bm, "x")) / (2.0 * delta_corr)
                    bpm_dy = (self._mean_bpm_axis(bp, "y") - self._mean_bpm_axis(bm, "y")) / (2.0 * delta_corr)
                    n_bpm = min(nb, bpm_dx.size, bpm_dy.size)
                    if n_bpm:
                        bpm_Rxx[:n_bpm, j] = bpm_dx[:n_bpm]
                        bpm_Ryy[:n_bpm, j] = bpm_dy[:n_bpm]

        finally:
            self.interface.set_correctors(corr_names, corr_bdes0.tolist())

        return {
            "Rxx": Rxx.tolist(),
            "Ryy": Ryy.tolist(),
            "correctors": corr_names,
            "screens": screens,
            "bpm_Rxx": bpm_Rxx.tolist(),
            "bpm_Ryy": bpm_Ryy.tolist(),
            "bpm_names": bpm_names,
            "bpm_S": self._get_twiss_s_positions(bpm_names),
            "delta_corr": float(delta_corr),
        }

    def _set_scan_quad_to_step(self, step_index):
        quad_name = self.session["quad_name"]
        K1_values = np.asarray(self.session["K1_values"], dtype=float)
        target_K1 = float(K1_values[step_index])

        quads = self.interface.get_quadrupoles([quad_name])
        names = list(quads["names"])
        if not names:
            raise RuntimeError("Quadrupole not found")
        self.interface.set_quadrupoles(names, [target_K1])
        return target_K1

    def _measure_screen_response(self):
        if self.session is None:
            raise RuntimeError("No session")
        quad_name = self.session["quad_name"]
        K1_values = np.asarray(self.session["K1_values"], dtype=float)
        deltas = np.asarray(self.session["deltas"], dtype=float)

        nom_idx = int(np.argmin(np.abs(deltas)))
        indexes = [0, nom_idx, len(K1_values) - 1]

        all_corrs = self.interface.get_correctors()["names"]
        correctors = [c for c in all_corrs if str(c).lower().startswith(("zh", "zx", "zv"))][:6]

        if not correctors:
            raise RuntimeError("No correctors found")

        quad_data0 = self.interface.get_quadrupoles([quad_name])
        quad_names0 = list(quad_data0["names"])
        if not quad_names0:
            raise RuntimeError("Quadrupole not found")
        quad_bdes0 = np.asarray(quad_data0["bdes"], dtype=float)

        output = {
            "correctors": correctors,
            "screen_names": list(self.session["screens"]),
            "bpm_names": [],
            "bpm_S": [],
            "K1_indices": indexes,
            "K1_values": [],
            "responses": [],
        }
        try:
            for idx in indexes:
                K1 = self._set_scan_quad_to_step(idx)
                resp = self._measure_screen_response_current_state(correctors = correctors, delta_corr = 1e-4)
                output["K1_values"].append(K1)
                output["responses"].append(resp)
                if not output["bpm_names"] and resp.get("bpm_names"):
                    output["bpm_names"] = list(resp.get("bpm_names", []))
                    output["bpm_S"] = list(resp.get("bpm_S", []))
        finally:
            self.interface.set_quadrupoles(quad_names0,quad_bdes0.tolist())
        self.session["screen_response_scans"] = output
        return output

    def _fit_twiss_and_emittance(self):

        if self.session is None:
            QMessageBox.information(self, "Fit", "No session.")
            return

        measured_optics = self.session.get("measured_optics")
        transport_source = None if not measured_optics else measured_optics.get("transport_source")
        if not measured_optics:
            QMessageBox.information(self, "Fit", "Run Measure Optics first.")
            return
        if transport_source not in {"model", "measured_fitted"}:
            QMessageBox.information(self, "Fit", "Current fit supports only model or measured_fitted transport.")
            return
        quality = self.session.get("scan_quality", {})
        if not quality.get("is_good_for_joint_fit", False):
            msg = self._describe_scan_quality()
            QMessageBox.information(
                self,
                "Fit",
                "This scan does not excite both planes strongly enough for a reliable joint emittance/Twiss fit.\n\n"
                + (msg if msg is not None else "Choose another quadrupole or a larger scan range.")
            )
            return

        screens = list(self.session["screens"])
        K1_values = np.asarray(self.session["K1_values"], dtype=float)
        sigx = np.asarray(self.session["sigx_mean"], dtype=float)
        sigy = np.asarray(self.session["sigy_mean"], dtype=float)
        sigx_std = np.asarray(self.session["sigx_std"], dtype=float)
        sigy_std = np.asarray(self.session["sigy_std"], dtype=float)

        nsteps = len(K1_values)
        nscreens = len(screens)
        if nscreens < 2:
            QMessageBox.information(self, "Fit", "At least two screens are required for the fit.")
            return
        fit_x = self._fit_plane(sigx, sigx_std, "x", measured_optics)
        fit_y = self._fit_plane(sigy, sigy_std, "y", measured_optics)

        emit_x = fit_x["emit"]
        beta_x0 = fit_x["beta0"]
        alpha_x0 = fit_x["alpha0"]
        pred_x = fit_x["pred"]

        emit_y = fit_y["emit"]
        beta_y0 = fit_y["beta0"]
        alpha_y0 = fit_y["alpha0"]
        pred_y = fit_y["pred"]
        gamma_rel, beta_rel = self._beam_factors()
        emit_x_norm = gamma_rel * beta_rel * emit_x if np.isfinite(gamma_rel) and np.isfinite(beta_rel) else np.nan
        emit_y_norm = gamma_rel * beta_rel * emit_y if np.isfinite(gamma_rel) and np.isfinite(beta_rel) else np.nan
        result = {
            "screen0": screens[0],
            "quad_name": self.session["quad_name"],
            "transport_source": transport_source,
            "scan_quality_recommendation": quality.get("recommendation"),
            "best_rel_var_x": quality.get("best_rel_var_x"),
            "best_rel_var_y": quality.get("best_rel_var_y"),
            "emit_x_norm": emit_x_norm,
            "emit_y_norm": emit_y_norm,
            "beta_x0": beta_x0,
            "alpha_x0": alpha_x0,
            "beta_y0": beta_y0,
            "alpha_y0": alpha_y0,
            "beta_x0_measured": fit_x["beta0_measured"],
            "alpha_x0_measured": fit_x["alpha0_measured"],
            "beta_x_scale_vs_measured": fit_x["beta_scale"],
            "alpha_x_offset_vs_measured": fit_x["alpha_offset"],
            "beta_y_scale_vs_measured": fit_y["beta_scale"],
            "alpha_y_offset_vs_measured": fit_y["alpha_offset"],
            "beta_y0_measured": fit_y["beta0_measured"],
            "alpha_y0_measured": fit_y["alpha0_measured"],
            "fit_x_success": fit_x["success"],
            "fit_y_success": fit_y["success"],
            "fit_x_message": fit_x["message"],
            "fit_y_message": fit_y["message"],
            "fit_x_residual_rms": fit_x["residual_rms"],
            "fit_y_residual_rms": fit_y["residual_rms"],
            "fit_x_residual_mad": fit_x["residual_mad"],
            "fit_y_residual_mad": fit_y["residual_mad"],
            "fit_x_cost": fit_x["cost"],
            "fit_y_cost": fit_y["cost"],
            "fit_x_residual_rms_per_screen": fit_x["residual_rms_per_screen"],
            "worst_screen_x": fit_x["worst_screen"],
            "fit_y_residual_rms_per_screen": fit_y["residual_rms_per_screen"],
            "worst_screen_y": fit_y["worst_screen"],
        }

        fit_quality = self._assess_fit_quality(result)
        result.update(fit_quality)

        fit_reasons = result.get("fit_quality_reasons", [])
        reasons_text = "none" if not fit_reasons else "; ".join(fit_reasons[:6])

        QMessageBox.information(
            self,
            "Fit complete",
            f"εₓ = {emit_x_norm:.4f} mm·mrad\n"
            f"εᵧ = {emit_y_norm:.4f} mm·mrad\n"
            f"βₓ0 = {beta_x0:.4f} m, αₓ0 = {alpha_x0:.4f}\n"
            f"βᵧ0 = {beta_y0:.4f} m, αᵧ0 = {alpha_y0:.4f}\n"
            f"measured βₓ0 = {fit_x['beta0_measured']:.4f}, αₓ0 = {fit_x['alpha0_measured']:.4f}\n"
            f"measured βᵧ0 = {fit_y['beta0_measured']:.4f}, αᵧ0 = {fit_y['alpha0_measured']:.4f}\n\n"
            f"Scan quality: {quality.get('recommendation', 'unknown')}\n"
            f"Fit quality: {result.get('fit_quality_status', 'unknown')}\n"
            f"Notes: {reasons_text}"
        )

        self.session["fit_result_twiss_emit"] = result
        print(f"quad_name: {self.session['quad_name']}")
        print(f"delta_min: {self.session['delta_min']}")
        print(f"delta_max: {self.session['delta_max']}")
        print(f"εₓ = {emit_x_norm:.4f} mm·mrad")
        print(f"εᵧ = {emit_y_norm:.4f} mm·mrad")
        print(f"βₓ0 = {beta_x0:.4f} m, αₓ0 = {alpha_x0:.4f}")
        print(f"βᵧ0 = {beta_y0:.4f} m, αᵧ0 = {alpha_y0:.4f}")
        print(f"measured βₓ0 = {fit_x['beta0_measured']:.4f}, αₓ0 = {fit_x['alpha0_measured']:.4f}")
        print(f"measured βᵧ0 = {fit_y['beta0_measured']:.4f}, αᵧ0 = {fit_y['alpha0_measured']:.4f}")
        print("fit_x_residual_rms =", result["fit_x_residual_rms"])
        print("fit_y_residual_rms =", result["fit_y_residual_rms"])
        print("fit_x_residual_rms_per_screen =", result["fit_x_residual_rms_per_screen"])
        print("fit_y_residual_rms_per_screen =", result["fit_y_residual_rms_per_screen"])
        print("worst_screen_x =", result["worst_screen_x"])
        print("worst_screen_y =", result["worst_screen_y"])
        truth = self.interface.get_twiss_at_screen("OTR0X")
        print("Twiss parameters from rftrack interface: ", truth)
        scans = self.session.get("screen_response_scans")
        if isinstance(scans, dict):
            print(scans.keys())
        meas_t = self.session.get("measured_transport")
        if isinstance(meas_t, dict):
            print(meas_t.keys())
            print("raw_Rxx shape =", np.asarray(meas_t.get("raw_Rxx", []), dtype=float).shape)
            print("raw_Ryy shape =", np.asarray(meas_t.get("raw_Ryy", []), dtype=float).shape)
            print("raw_bpm_Rxx shape =", np.asarray(meas_t.get("raw_bpm_Rxx", []), dtype=float).shape)
            print("raw_bpm_Ryy shape =", np.asarray(meas_t.get("raw_bpm_Ryy", []), dtype=float).shape)
            print(meas_t.get("mean_rel_y"))
        else:
            print("No measured_transport diagnostic available")
        self._update_fit_panel(result)
        self._plot_fit_overlay(pred_x, pred_y, result)

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
