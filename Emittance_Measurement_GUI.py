import os, sys, pickle, time
import numpy as np
import matplotlib
matplotlib.use("QtAgg")
import matplotlib.colors as mcolors
from datetime import datetime
try:
    pyqt_version = 6
    from PyQt6 import uic
    from PyQt6.QtWidgets import (
        QApplication, QMainWindow, QMessageBox, QVBoxLayout, QListWidgetItem, QStyledItemDelegate
    )
    from PyQt6.QtCore import Qt, QTimer, QRect, QObject, QThread, pyqtSignal
    from PyQt6.QtGui import QPainter, QPixmap, QFont
except ImportError:
    pyqt_version = 5
    from PyQt5 import uic
    from PyQt5.QtWidgets import (
        QApplication, QMainWindow, QMessageBox, QVBoxLayout, QListWidgetItem, QStyledItemDelegate
    )
    from PyQt5.QtCore import Qt, QTimer, QRect, QObject, QThread, pyqtSignal
    from PyQt5.QtGui import QPainter, QPixmap, QFont

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from Backend.SaveOrLoad import SaveOrLoad
from Backend.Optimization_EM import Optimization_EM
from Backend.QuadrupoleScan_EM import QuadrupoleScan_EM


class SPositionDelegate(QStyledItemDelegate):
    S_ROLE = int(Qt.ItemDataRole.UserRole) + 1
    def paint(self, painter: QPainter, option, index):
        painter.save()
        try:
            opt = option
            self.initStyleOption(opt, index)
            style = opt.widget.style() if opt.widget is not None else None
            if style is not None:
                opt_no_text = opt
                opt_no_text.text = ""
                style.drawControl(style.ControlElement.CE_ItemViewItem, opt_no_text, painter, opt.widget)

            device_name = str(index.data(Qt.ItemDataRole.UserRole) or index.data(Qt.ItemDataRole.DisplayRole) or "")
            s_text = str(index.data(self.S_ROLE) or "")
            r = opt.rect
            margin = 8
            painter.setFont(opt.font)
            painter.setPen(opt.palette.color(opt.palette.ColorRole.Text))

            fm = painter.fontMetrics()
            s_column_width = max(fm.horizontalAdvance("S = 000.000 m"), 90)

            left_rect = QRect(
                r.left() + margin,
                r.top(),
                max(10, r.width() - s_column_width - 3 * margin),
                r.height(),
            )

            right_rect = QRect(
                r.left() + r.width() - s_column_width - margin,
                r.top(),
                s_column_width,
                r.height(),
            )

            elided_name = fm.elidedText(
                device_name,
                Qt.TextElideMode.ElideRight,
                max(10, left_rect.width())
            )

            painter.drawText(
                left_rect,
                int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft),
                elided_name
            )

            if s_text:
                painter.drawText(
                    right_rect,
                    int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft),
                    s_text
                )
        finally:
            painter.restore()

class MatplotlibWidget(FigureCanvas):
    def __init__(self, parent=None):
        self.figure = Figure(figsize=(6, 4), tight_layout=True)
        super().__init__(self.figure)
        self.setParent(parent)

class OptimizationWorker(QObject):
    finished = pyqtSignal(object)
    error = pyqtSignal(str)
    optimizer_ready = pyqtSignal(object)
    done = pyqtSignal()

    def __init__(self, interface, session, n_starts = 3):
        super().__init__()
        self.interface = interface
        self.session = session
        self.n_starts = n_starts

    def run(self):
        try:
            tool = Optimization_EM(interface = self.interface, n_starts = self.n_starts)
            self.optimizer_ready.emit(tool)
            output = tool.fit_from_session(self.session)
            self.finished.emit(output)
        except Exception as e:
            self.error.emit(str(e))
        finally:
            self.done.emit()

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
        ui_path = os.path.join(os.path.dirname(__file__),"UI files/Emittance_Measurement_GUI.ui")
        uic.loadUi(ui_path, self)
        self._load_logo()
        self.start_optimization_button.clicked.connect(self._run_optimization)
        self.stop_optimization_button.clicked.connect(self._stop_optimization)
        self.setWindowTitle("Emittance Measurement GUI")
        self.fitResultsVBox.setStretch(0, 0)
        self.fitResultsVBox.setStretch(1, 1)
        self.progressBar.setValue(0)
        self.quadrupoles_list.setItemDelegate(SPositionDelegate(self.quadrupoles_list))
        self.screens_list.setItemDelegate(SPositionDelegate(self.screens_list))
        self._optimization_t0 = None
        self._scan_stop_requested = False
        self._is_scanning = False
        self._is_optimizing = False
        self._current_optimizer = None
        self._optimization_thread = None
        self._optimization_worker = None
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

        self._show_s_values_and_device_lists(self.quadrupoles_list, quadrupoles)
        self._show_s_values_and_device_lists(self.screens_list, screens_sorted)
        self.quad_on_plot.clear()
        self.quad_on_plot.addItems(quadrupoles)
        self.screen_on_plot.clear()
        self.screen_on_plot.addItems(screens_sorted)
        self.start_button_scan.clicked.connect(self._run_scan)
        self.stop_button_scan.clicked.connect(self._stop_scan)
        self._set_progress(0)
        self._clear_fit_panel()
        self._reset_canvas()
        self.screens_list.itemSelectionChanged.connect(self._screen_selection_changed)
        self._filter_quadrupoles_in_gui()

    def _stop_scan(self):
        if self._is_scanning:
            self._scan_stop_requested = True

    def _stop_optimization(self):
        if self._is_optimizing and self._current_optimizer is not None:
            self._current_optimizer.request_stop()

    def _show_s_values_and_device_lists(self, list_widget, names):
        names = list(names)
        s_positions = self._get_twiss_s_positions(names)
        list_widget.clear()

        for name, s_value in zip(names, s_positions):
            item = QListWidgetItem(str(name))
            item.setData(Qt.ItemDataRole.UserRole, str(name))
            list_widget.addItem(item)
            if s_value is not None:
                try:
                    s_value = float(s_value)
                except (ValueError, TypeError):
                    s_text = ""
                else:
                    s_text = f"S = {s_value:.3f} m" if np.isfinite(s_value) else ""
            else:
                s_text = ""
            item.setData(SPositionDelegate.S_ROLE, s_text)

    def _load_logo(self):
        self.logo_label.setText("")
        self.logo_label.setScaledContents(False)

        transform_mode = (
            Qt.TransformationMode.SmoothTransformation
            if pyqt_version == 6
            else Qt.SmoothTransformation
        )
        base_dir = os.path.dirname(os.path.abspath(__file__))
        logo_path = os.path.join(base_dir, "UI files", "Assets", "CERN_logo.png")
        if not os.path.isfile(logo_path):
            return
        pixmap = QPixmap(logo_path)
        if pixmap.isNull():
            return
        scaled = pixmap.scaledToHeight(80, transform_mode)
        self.logo_label.setPixmap(scaled)
        self.logo_label.setToolTip(logo_path)

    def _set_progress(self, value):
        self.progressBar.setRange(0, 100)
        self.progressBar.setValue(int(max(0, min(100,value))))
        QApplication.processEvents()

    def _clear_fit_panel(self):
        self.result_quad.setText("-")
        self.result_emit_x_norm.setText("-")
        self.result_emit_y_norm.setText("-")
        self.result_beta_x0.setText("-")
        self.result_alpha_x0.setText("-")
        self.result_beta_y0.setText("-")
        self.result_alpha_y0.setText("-")

    def _update_fit_panel(self, result):
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
        selected = []
        for item in self.screens_list.selectedItems():
            selected.append(item.data(Qt.ItemDataRole.UserRole) or item.text())
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
        if self._is_optimizing:
            return
        self._is_optimizing = True
        self._current_optimizer = None
        self._set_progress(0)
        self._optimization_t0 = time.perf_counter()
        thread = QThread(self)

        worker = OptimizationWorker(self.interface, self.session, n_starts=3)
        worker.moveToThread(thread)
        worker.optimizer_ready.connect(self._store_current_optimizer)
        worker.finished.connect(self._on_optimization_output)
        worker.error.connect(self._on_optimization_error)
        worker.done.connect(thread.quit)
        worker.done.connect(worker.deleteLater)

        thread.finished.connect(self._on_optimization_finished)
        thread.finished.connect(thread.deleteLater)
        thread.started.connect(worker.run)

        self._optimization_thread = thread
        self._optimization_worker = worker
        self._set_progress(30)
        thread.start()

    def _store_current_optimizer(self, optimizer):
        self._current_optimizer = optimizer

    def _on_optimization_output(self, output):
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

        elapsed = time.perf_counter() - self._optimization_t0

        if result.get("stopped", False):
            QMessageBox.information(
                self,
                "Optimization stopped",
                f"Showing best solution found so far.\n\n"
                f"εₓ = {result['emit_x_norm']:.4f} mm·mrad\n"
                f"εᵧ = {result['emit_y_norm']:.4f} mm·mrad\n"
                f"βₓ0 = {result['beta_x0']:.4f} m, αₓ0 = {result['alpha_x0']:.4f}\n"
                f"βᵧ0 = {result['beta_y0']:.4f} m, αᵧ0 = {result['alpha_y0']:.4f}"
            )
        else:
            QMessageBox.information(
                self,
                "Optimization complete",
                f"εₓ = {result['emit_x_norm']:.4f} mm·mrad\n"
                f"εᵧ = {result['emit_y_norm']:.4f} mm·mrad\n"
                f"βₓ0 = {result['beta_x0']:.4f} m, αₓ0 = {result['alpha_x0']:.4f}\n"
                f"βᵧ0 = {result['beta_y0']:.4f} m, αᵧ0 = {result['alpha_y0']:.4f}"
            )

        print(f"Elapsed time: {elapsed}s = {elapsed / 60}min")

    def _on_optimization_error(self, message):
        self._set_progress(0)
        QMessageBox.information(self, "Optimization", message)

    def _on_optimization_finished(self):
        self._is_optimizing = False
        self._current_optimizer = None
        self._optimization_worker = None
        self._optimization_thread = None

    def _scan_progress_callback(self, session_partial, current_step, total_steps):  # refreshes plot in the gui
        if self._scan_stop_requested:
            raise KeyboardInterrupt("Scan stopped by user.")
        self.session = session_partial
        self._draw_live_scan(session_partial)
        if total_steps:
            self._set_progress(100.0 * float(current_step) / float(total_steps))
        QApplication.processEvents()
        if self._scan_stop_requested:
            raise KeyboardInterrupt("Scan stopped by user.")

    def _run_scan(self):
        current_quad = self.quadrupoles_list.currentItem()
        if current_quad is None:
            QMessageBox.information(self, "Scan error", "No quadrupole selected.")
            return

        quad_name = current_quad.data(Qt.ItemDataRole.UserRole) or current_quad.text()
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

        self._scan_stop_requested = False
        self._is_scanning = True

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
        except KeyboardInterrupt as e:
            self._set_progress(0)
            QMessageBox.information(self, "Scan", str(e))
            return

        except TypeError:
            self._set_progress(0)
            QMessageBox.information(self,"Scan error","Error")
            return
        except Exception as e:
            self._set_progress(0)
            QMessageBox.information(self, "Scan error", str(e))
            return
        finally:
            self._is_scanning = False

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
        finite_screen_positions = [float(s) for s in screen_position if np.isfinite(s)]
        if not finite_screen_positions:
            return

        first_screen_position = min(finite_screen_positions)
        last_screen_position = max(finite_screen_positions)
        all_quadrupoles = list(self.interface.get_quadrupoles().get("names", []))

        quad_S = self._get_twiss_s_positions(all_quadrupoles)

        quad_pos = {name: float(s) for name, s in zip(all_quadrupoles, quad_S) if np.isfinite(s)}

        before_last_screen_quads = [
            name for name in all_quadrupoles
            if name in quad_pos and quad_pos[name] < last_screen_position
        ]
        self.quadrupoles_list.blockSignals(True)
        self._show_s_values_and_device_lists(self.quadrupoles_list, before_last_screen_quads)

        upstream_to_first_screen_quads = [name for name in before_last_screen_quads if quad_pos[name] < first_screen_position]

        if upstream_to_first_screen_quads:
            closest_quad = max(upstream_to_first_screen_quads, key = lambda name: quad_pos[name])
            for i in range(self.quadrupoles_list.count()):
                item = self.quadrupoles_list.item(i)
                item_name = item.data(Qt.ItemDataRole.UserRole) or item.text()
                if item_name == closest_quad:
                    self.quadrupoles_list.setCurrentItem(item)
                    break
        elif self.quadrupoles_list.count() > 0:
            self.quadrupoles_list.setCurrentRow(0)
        self.quadrupoles_list.blockSignals(False)

    def _screen_selection_changed(self):
        self._filter_quadrupoles_in_gui()

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
