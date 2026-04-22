import os, sys, pickle
import numpy as np
import matplotlib
matplotlib.use("QtAgg")
import matplotlib.colors as mcolors
from datetime import datetime
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
from Backend.Optimization_EM import Optimization_EM
from Backend.QuadrupoleScan_EM import QuadrupoleScan_EM

class MatplotlibWidget(FigureCanvas):
    def __init__(self, parent=None):
        self.figure = Figure(figsize=(6, 4), tight_layout=True)
        super().__init__(self.figure)
        self.setParent(parent)

class MainWindow(QMainWindow, SaveOrLoad,QuadrupoleScan_EM):
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
        self.run_optimization_button.clicked.connect(self._run_optimization)
        self.setWindowTitle("Emittance Measurement GUI")
        self.fitResultsVBox.setStretch(0, 0)
        self.fitResultsVBox.setStretch(1, 1)
        self.progressBar.setValue(0)

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
        self._set_progress(0)
        self._clear_fit_panel()
        self._reset_canvas()
        self.screens_list.itemSelectionChanged.connect(self._screen_selection_changed)
        self._filter_quadrupoles_in_gui()

    def _set_progress(self, value):
        self.progressBar.setRange(0, 100)
        self.progressBar.setValue(int(max(0, min(100,value))))
        QApplication.processEvents()

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

    def _run_optimization(self):
        if self.session is None:
            QMessageBox.information(self, "Optimization", "No session.")
            return
        self._set_progress(0)
        try:
            tool = Optimization_EM(self.interface, n_starts=3)
            self._set_progress(30)
            output = tool.fit_from_session(self.session)
            self._set_progress(85)
            result = output["result"]
            pred_x = np.asarray(output["pred_x"], dtype=float)
            pred_y = np.asarray(output["pred_y"], dtype=float)
            self.session["optimization_result"] = result
            self.session["optimization_pred_x"] = pred_x.tolist()
            self.session["optimization_pred_y"] = pred_y.tolist()
            self._update_fit_panel(result)
            self._plot_fit_overlay(pred_x, pred_y, result)
            self._set_progress(100)

            QMessageBox.information(
                self,
                "Optimization complete",
                f"εₓ = {result['emit_x_norm']:.4f} mm·mrad\n"
                f"εᵧ = {result['emit_y_norm']:.4f} mm·mrad\n"
                f"βₓ0 = {result['beta_x0']:.4f} m, αₓ0 = {result['alpha_x0']:.4f}\n"
                f"βᵧ0 = {result['beta_y0']:.4f} m, αᵧ0 = {result['alpha_y0']:.4f}"
            )

        except Exception as e:
            self._set_progress(0)
            QMessageBox.information(self, "Optimization", str(e))

    def _scan_progress_callback(self, session_partial, current_step, total_steps): # refreshes plot in the gui
        self.session = session_partial
        self._draw_live_scan(session_partial)
        if total_steps:
            self._set_progress(100.0 * float(current_step) / float(total_steps))
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
        self._set_progress(0)
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
            self._set_progress(0)
            QMessageBox.information(self,"Scan error","Error")
            return
        except Exception as e:
            self._set_progress(0)
            QMessageBox.information(self, "Scan error", str(e))
            return

        self._draw_live_scan(self.session)
        self._set_progress(90)
        try:
            self.session["screen_response_scans"] = self._measure_screen_response()
        except Exception as e:
            self.session["screen_response_scans"] = None
            QMessageBox.information(self, "Scan error", str(e))

        quality_msg = self._describe_scan_quality()
        if quality_msg is None:
            QMessageBox.information(self, "Scan", "Scan completed.")
            self._set_progress(100)
        else:
            QMessageBox.information(self, "Scan", f"Scan completed.")
            self._set_progress(100)


    @staticmethod
    def _fmt_float(value, digits=3):
        try:
            value = float(value)
        except (TypeError, ValueError):
            return "n/a"
        return f"{value:.{digits}f}" if np.isfinite(value) else "n/a"

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
