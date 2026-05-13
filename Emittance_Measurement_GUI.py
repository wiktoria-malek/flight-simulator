import os, sys, time, copy
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

from Interfaces.interface_setup import INTERFACE_SETUP
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from Backend.SaveOrLoad import SaveOrLoad
from Backend.Optimization_EM import Optimization_EM
from Backend.QuadrupoleScan_EM import QuadrupoleScan_EM
from Backend.LogConsole import LogConsole
from Backend.PhaseSpaceGraphs_EM import PhaseSpaces

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

            left_rect = QRect(r.left() + margin, r.top(), max(10, r.width() - s_column_width - 3 * margin), r.height())
            right_rect = QRect(r.left() + r.width() - s_column_width - margin, r.top(), s_column_width, r.height())
            elided_name = fm.elidedText(device_name, Qt.TextElideMode.ElideRight, max(10, left_rect.width()))
            painter.drawText(left_rect, int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft), elided_name)
            if s_text:
                painter.drawText(right_rect, int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft), s_text)
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
    progress = pyqtSignal(str, int, int)

    def __init__(self, interface, session, n_starts = 3, xopt_initial_points = None, xopt_steps = None, nm_steps = None, fit_quadrupole_strength = False):
        super().__init__()
        self.interface = interface
        self.session = session
        self.n_starts = n_starts
        self.xopt_initial_points = xopt_initial_points
        self.xopt_steps = xopt_steps
        self.nm_steps = nm_steps
        self.fit_quadrupole_strength = bool(fit_quadrupole_strength)


    def _emit_progress(self, phase, current, total):
        self.progress.emit(str(phase), int(current), int(total))

    def _get_interface_initial_settings(self):
        interface_class_name=self.interface.__class__.__name__
        interface_module_name=self.interface.__class__.__module__

        for machine_interfaces in INTERFACE_SETUP.values():
            for interface_defaults in machine_interfaces:
                if (interface_defaults.get("class_name")==interface_class_name) and (interface_defaults.get("module")==interface_module_name):
                    return interface_defaults
        return None

    def _get_interface_bounds(self):
        interface_defaults=self._get_interface_initial_settings()
        if interface_defaults is None:
            return {}
        return dict(interface_defaults.get("bounds", {}))

    def run(self):
        try:
            tool = Optimization_EM(interface = self.interface, n_starts = self.n_starts, xopt_initial_points = self.xopt_initial_points, xopt_steps = self.xopt_steps, nm_steps = self.nm_steps, fit_quadrupole_strength = self.fit_quadrupole_strength,
                                   progress_callback=self._emit_progress)
            self.optimizer_ready.emit(tool)
            bounds = self._get_interface_bounds()
            output = tool.fit_from_session(self.session, bounds = bounds)
            self.finished.emit(output)
        except Exception as e:
            self.error.emit(str(e))
        finally:
            self.done.emit()

class MainWindow(QMainWindow, SaveOrLoad, QuadrupoleScan_EM):
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
        screen_order, screen_order_type = self._get_element_order_values(screens)
        screen_pairs = sorted(zip(screens, screen_order),key=lambda x: x[1] if np.isfinite(x[1]) else np.inf) # assigns S position to each screen
        screens_sorted = [name for name, _ in screen_pairs] # only names
        self._show_s_values_and_device_lists(self.quadrupoles_list, quadrupoles)
        self._show_s_values_and_device_lists(self.screens_list, screens_sorted)
        self.show_scan_on_all_screens.toggled.connect(self._on_show_all_screens_toggled)
        self.screen_on_plot.setEnabled(not self.show_scan_on_all_screens.isChecked())
        self.quad_on_plot.clear()
        self.quad_on_plot.addItems(quadrupoles)
        self.screen_on_plot.clear()
        self.screen_on_plot.addItems(screens_sorted)
        self.start_button_scan.clicked.connect(self._run_scan)
        self.stop_button_scan.clicked.connect(self._stop_scan)
        self.quad_on_plot.currentIndexChanged.connect(lambda _=None: self._draw_live_scan(self.session))
        self.screen_on_plot.currentIndexChanged.connect(lambda _=None: self._draw_live_scan(self.session))
        self._set_progress(0)
        self._clear_fit_panel()
        self._reset_canvas()
        self.screens_list.itemSelectionChanged.connect(self._screen_selection_changed)
        self._last_selected_quadrupoles = []
        self._filter_quadrupoles_in_gui()
        self.clear_plots_button.clicked.connect(self._clear_plots)
        self.log_console=None
        self.phase_spaces = None
        self.log_console_button.clicked.connect(self._show_console_log)
        self.phase_spaces_button.clicked.connect(self._show_phase_spaces)
        self.pause_button.clicked.connect(self._pause_task)
        self.resume_button.clicked.connect(self._resume_task)
        self._scan_pause_requested = False
        self._scan_is_paused = False
        self._optimization_paused = False
        self._last_scan_status = None

    def _log_scan_status(self, session_partial, current_step, total_steps):
        if not isinstance(session_partial, dict):
            return

        if session_partial.get("mode") == "multi_quad_scan":
            current_quad = str(session_partial.get("current_quadrupole", "-")).strip() or "-"
            quad_idx = int(session_partial.get("current_quadrupole_index", 0)) + 1
            total_quads = int(session_partial.get("total_quadrupoles", 0))
            completed = list(session_partial.get("completed_quadrupoles", []))
            skipped = list(session_partial.get("skipped_quadrupoles", []))
            skipped_names = [str(item.get("quad_name", "")).strip() for item in skipped if isinstance(item, dict)]

            status = ("multi", current_quad, quad_idx, int(current_step), int(total_steps), tuple(completed), tuple(skipped_names))
            if status == self._last_scan_status:
                return
            self._last_scan_status = status
            finished_msg = ", ".join(completed) if completed else "none yet"
            skipped_msg = ", ".join(skipped_names) if skipped_names else "none"

            self.log(
                f"Scanning quadrupole {quad_idx}/{total_quads}: {current_quad} | "
                f"step {int(current_step) + 1}/{int(total_steps)} | "
                f"finished: {finished_msg} | skipped, because of K1_0 = 0: {skipped_msg}"
            )

        else:
            quad_name = str(session_partial.get("quad_name", "-")).strip() or "-"
            status = ("single", quad_name, int(current_step), int(total_steps))
            if status == self._last_scan_status:
                return
            self._last_scan_status = status
            self.log(f"Scanning quadrupole {quad_name} | step {int(current_step) + 1}/{int(total_steps)}")

    def _on_show_all_screens_toggled(self, checked):
        self.screen_on_plot.setEnabled(not bool(checked))
        self._draw_live_scan(self.session)

    def _pause_task(self):
        if self._is_scanning:
            self.log("Pausing scan...")
            self._scan_pause_requested = True
            return

        if self._is_optimizing and self._current_optimizer is not None:
            self.log("Pausing optimization...")
            self._current_optimizer.request_pause()
            return

    def _resume_task(self):
        if self._is_scanning and (self._scan_pause_requested or self._scan_is_paused):
            self.log("Resuming scan...")
            self._scan_pause_requested = False
            self._scan_is_paused = False
            return
        if self._optimization_paused and not self._is_optimizing and self.session is not None:
            self.log("Resuming optimization...")
            self._optimization_paused = False
            self._run_optimization()
            return

    def _stop_scan(self):
        self.log("Stopping scan...")
        if self._is_scanning:
            self._scan_stop_requested = True
            self._scan_pause_requested = False
            self._scan_is_paused = False

    def _clear_plots(self):
        self.session = None
        self._scan_stop_requested = False
        self._scan_pause_requested = False
        self._optimization_paused=False
        self._scan_is_paused = False
        self.quad_on_plot.clear()
        self.screen_on_plot.clear()
        quadrupoles = list(self.interface.get_quadrupoles()["names"])
        screens_data = self.interface.get_screens()
        screens = list(screens_data["names"])
        screen_order, screen_order_type = self._get_element_order_values(screens)
        screen_pairs = sorted(zip(screens, screen_order),key=lambda x: x[1] if np.isfinite(x[1]) else np.inf)
        screens_sorted = [name for name, _ in screen_pairs]
        self.quad_on_plot.addItems(quadrupoles)
        self.screen_on_plot.addItems(screens_sorted)
        self._clear_fit_panel()
        self._reset_canvas()
        self._set_progress(0)

    def _stop_optimization(self):
        self.log("Stopping optimization...")
        self._optimization_paused = False
        if self._is_optimizing and self._current_optimizer is not None:
            self._current_optimizer.request_stop()

    def _get_element_order_values(self, names):
        names = list(names)
        s_positions = self._get_twiss_s_positions(names)
        s_values = []
        for value in s_positions:
            try:
                value = float(value)
            except (ValueError, TypeError):
                value = np.nan
            s_values.append(value)

        if any(np.isfinite(s_values)):
            return s_values, "S"
        sequence_indices = None
        try:
            sequence_indices = self.interface.get_elements_indices(names)
        except Exception:
            sequence_indices = None
        if sequence_indices is not None:
            try:
                sequence_indices = list(sequence_indices)
            except TypeError:
                sequence_indices = None
        if sequence_indices is not None and len(sequence_indices) == len(names):
            index_values = []
            for value in sequence_indices:
                try:
                    value = float(value)
                except (ValueError, TypeError):
                    value = np.nan
                index_values.append(value)
            if any(np.isfinite(index_values)):
                return index_values, "index"
        return [np.nan] * len(names), ""

    def _show_s_values_and_device_lists(self, list_widget, names):
        names = list(names)
        order_values, order_kind = self._get_element_order_values(names)
        list_widget.clear()
        for name, order_value in zip(names, order_values):
            item = QListWidgetItem(str(name))
            item.setData(Qt.ItemDataRole.UserRole, str(name))
            list_widget.addItem(item)
            try:
                order_value = float(order_value)
            except (ValueError, TypeError):
                order_value = np.nan

            if np.isfinite(order_value):
                if order_kind == "index":
                    order_text = f"index = {int(order_value)}"
                else:
                    order_text = f"S = {order_value:.3f} m"
            else:
                order_text = ""
            item.setData(SPositionDelegate.S_ROLE, order_text)

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
        self.result_quad_strength.setText("-")
        self.result_emit_x_norm.setText("-")
        self.result_emit_y_norm.setText("-")
        self.result_beta_x0.setText("-")
        self.result_alpha_x0.setText("-")
        self.result_beta_y0.setText("-")
        self.result_alpha_y0.setText("-")
        self.result_reference_screen.setText("-")

    def _update_fit_panel(self, result):
        self.result_quad.setText(str(result["quad_name"]))
        self.result_reference_screen.setText(result["screen0"])

        def fmt_value(value, suffix=""): # formats numbers to text
            try:
                value = float(value)
            except Exception:
                return "-"
            if not np.isfinite(value):
                return "-"
            return f"{value:.4f}{suffix}"

        quad_strength_text = fmt_value(result.get("quad_k1_0"), " 1/m²")
        if result.get("quad_k1_0_is_fitted", False) and quad_strength_text != "-":
            quad_strength_text += " (fit)"
        elif quad_strength_text != "-":
            quad_strength_text += " (nominal)"
        self.result_quad_strength.setText(quad_strength_text)
        self.result_emit_x_norm.setText(fmt_value(result.get("emit_x_norm"), " mm·mrad"))
        self.result_emit_y_norm.setText(fmt_value(result.get("emit_y_norm"), " mm·mrad"))
        self.result_beta_x0.setText(fmt_value(result.get("beta_x0"), " m"))
        self.result_alpha_x0.setText(fmt_value(result.get("alpha_x0")))
        self.result_beta_y0.setText(fmt_value(result.get("beta_y0"), " m"))
        self.result_alpha_y0.setText(fmt_value(result.get("alpha_y0")))
        self.result_reference_screen.setText(result["screen0"])

    def _reset_canvas(self):
        fig = self.canvas.figure
        fig.clear()
        ax = fig.add_subplot(111)
        ax.set_title("Quadrupole scan")
        ax.set_xlabel("K1")
        ax.set_ylabel("Beam size")
        ax.grid(True, alpha=0.3)
        self.canvas.draw()

    def _get_selection(self):
        quadrupoles_all = []
        for i in range(self.quadrupoles_list.count()):
            it = self.quadrupoles_list.item(i)
            quadrupoles_all.append(it.data(Qt.ItemDataRole.UserRole) or it.text())

        screens_all = []
        for i in range(self.screens_list.count()):
            it = self.screens_list.item(i)
            screens_all.append(it.data(Qt.ItemDataRole.UserRole) or it.text())

        selected_quadrupoles = []
        for i in range(self.quadrupoles_list.count()):
            it = self.quadrupoles_list.item(i)
            if it.isSelected():
                selected_quadrupoles.append(it.data(Qt.ItemDataRole.UserRole) or it.text())

        selected_screens = []
        for i in range(self.screens_list.count()):
            it = self.screens_list.item(i)
            if it.isSelected():
                selected_screens.append(it.data(Qt.ItemDataRole.UserRole) or it.text())

        quadrupoles = selected_quadrupoles or quadrupoles_all
        screens = selected_screens or screens_all

        return quadrupoles, screens

    def _draw_live_scan(self, session):
        if session is None:
            return
        self._refresh_plot_comboboxes_from_session(session)
        session_to_plot = self._get_session_for_selected_quad(session)
        if session_to_plot is None:
            return
        K1_values = np.asarray(session_to_plot["K1_values"], dtype=float)
        sigx = np.asarray(session_to_plot["sigx_mean"], dtype=float)
        sigy = np.asarray(session_to_plot["sigy_mean"], dtype=float)
        screens = list(session_to_plot["screens"])
        quad_name = session_to_plot.get("quad_name", "-")

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


        if self.show_scan_on_all_screens.isChecked():
            screen_indices = list(range(len(screens)))
        else:
            selected_screen = self.screen_on_plot.currentText().strip()
            if selected_screen in screens:
                screen_indices = [screens.index(selected_screen)]
            else:
                screen_indices = list(range(len(screens)))

        for i in screen_indices:
            screen = screens[i]
            mask_x = np.isfinite(sigx[:, i])
            mask_y = np.isfinite(sigy[:, i])

            ax1.plot(K1_values[mask_x], sigx[mask_x, i], 'o-', label=screen)
            ax2.plot(K1_values[mask_y], sigy[mask_y, i], 'o-', label=screen)

        if session_to_plot.get("is_conventional_em", False):
            title = f"Conventional multi-screen EM: {quad_name}"
        else:
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

            ax1.plot(K1_values, sigx[:, i], 'o', color=base_color, label=f"{screen} data")
            fit_x = np.sqrt(np.maximum(pred_x[:, i], 0.0))
            ax1.plot(K1_values, fit_x, '-', color=fit_color, linewidth=2.0, label=f"{screen} fit")
            ax2.plot(K1_values, sigy[:, i], 'o', color=base_color, label=f"{screen} data")
            fit_y = np.sqrt(np.maximum(pred_y[:, i], 0.0))
            ax2.plot(K1_values, fit_y, '-', color=fit_color, linewidth=2.0, label=f"{screen} fit")

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
        self.log("Fitting emittance and twiss parameters at scanned quadrupole started...")
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
        xopt_initial_points = int(self.xopt_initial_points_spin.value())
        xopt_steps = int(self.xopt_steps_spin.value())
        nm_steps = int(self.nm_steps_spin.value())

        # FOR TESTS!!!
        # scale = 0.8
        # session_bad = copy.deepcopy(self.session)
        # session_bad["K1_0"] = self.session["K1_0"] * scale
        # session_bad["K1_values"] = (np.asarray(self.session["K1_values"]) * scale).tolist()
        # FOR TESTS!!! in order to test again, pass sessios_bad to the worker, instead of self.session


        worker = OptimizationWorker(self.interface, self.session, n_starts=3, xopt_initial_points=xopt_initial_points, xopt_steps=xopt_steps, nm_steps = nm_steps, fit_quadrupole_strength = bool(self.fit_quadrupole_strength_checkbox.isChecked()))

        worker.moveToThread(thread)
        worker.optimizer_ready.connect(self._store_current_optimizer)
        worker.finished.connect(self._on_optimization_output)
        worker.error.connect(self._on_optimization_error)
        worker.progress.connect(self._on_optimization_progress)
        worker.done.connect(thread.quit)
        worker.done.connect(worker.deleteLater)

        thread.finished.connect(self._on_optimization_finished)
        thread.finished.connect(thread.deleteLater)
        thread.started.connect(worker.run)

        self._optimization_thread = thread
        self._optimization_worker = worker
        self._set_progress(30)
        thread.start()

    def _on_optimization_progress(self, phase, current, total):
        total = max(int(total), 1)
        current = max(0, min(int(current), total))

        if str(phase).lower().startswith("xopt"):
            value = 30 + 40 * current / total
        else:
            value = 70 + 25 * current / total

        self._set_progress(value)
        self.progressBar.setFormat(f"{phase}: {current}/{total}")

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

        joint_found = bool(
            np.isfinite(result.get("emit_x_norm", np.nan)) and np.isfinite(result.get("emit_y_norm", np.nan)))
        paused = bool(result.get("paused", False))

        if paused:
            if joint_found:
                message = (
                    "Best joint solution found so far.\n\n"
                    f"εₓ = {result['emit_x_norm']:.4f} mm·mrad\n"
                    f"εᵧ = {result['emit_y_norm']:.4f} mm·mrad\n"
                    f"βₓ0 = {result['beta_x0']:.4f} m, αₓ0 = {result['alpha_x0']:.4f}\n"
                    f"βᵧ0 = {result['beta_y0']:.4f} m, αᵧ0 = {result['alpha_y0']:.4f}"
                )
            else:
                message = "Optimization was paused before any joint solution was found."

            self._optimization_paused = True
            QMessageBox.information(self, "Optimization paused", message)

        elif result.get("stopped", False):
            self._optimization_paused = False

            if joint_found:
                message = (
                    "Best joint solution found so far.\n\n"
                    f"εₓ = {result['emit_x_norm']:.4f} mm·mrad\n"
                    f"εᵧ = {result['emit_y_norm']:.4f} mm·mrad\n"
                    f"βₓ0 = {result['beta_x0']:.4f} m, αₓ0 = {result['alpha_x0']:.4f}\n"
                    f"βᵧ0 = {result['beta_y0']:.4f} m, αᵧ0 = {result['alpha_y0']:.4f}"
                )
            else:
                message = "Optimization was stopped before any joint solution was found."

            QMessageBox.information(self, "Optimization stopped", message)

        else:
            self._optimization_paused = False
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
        self._optimization_paused = False
        if message == "Optimization stopped.":
            QMessageBox.information(
                self,
                "Optimization stopped",
                "Optimization was stopped before any solution was found."
            )
            self.log("Optimization was stopped before any solution was found.")
        else:
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
        self._log_scan_status(session_partial, current_step, total_steps)
        self._draw_live_scan(session_partial)
        if total_steps:
            self._set_progress(100.0 * float(current_step) / float(total_steps))
        QApplication.processEvents()
        if self._scan_stop_requested:
            raise KeyboardInterrupt("Scan stopped by user.")

    def _run_scan(self):
        quadrupoles, _ = self._get_selection()
        if len(quadrupoles) == 0:
            QMessageBox.information(self, "Scan error", "No quadrupole selected.")
            return
        quad_label = quadrupoles[0] if len(quadrupoles) == 1 else f"multi-quad scan ({len(quadrupoles)} quadrupoles)"
        steps_preview = int(self.steps_settings.value())
        if steps_preview == 0:
            self.log(f"Running conventional multi-screen EM for {quad_label}...")
        else:
            self.log(f"Running quadrupole scan for {quad_label}...")
        self.quad_on_plot.blockSignals(True)
        self.quad_on_plot.clear()
        self.quad_on_plot.addItems(quadrupoles)
        if quadrupoles:
            self.quad_on_plot.setCurrentIndex(0)
        self.quad_on_plot.blockSignals(False)
        selected_items = self.screens_list.selectedItems()
        if not selected_items:
            self.screens_list.blockSignals(True)
            self.screens_list.selectAll()
            self.screens_list.blockSignals(False)

        _, screens = self._get_selection()
        self.screen_on_plot.blockSignals(True)
        self.screen_on_plot.clear()
        self.screen_on_plot.addItems(screens)
        if screens:
            self.screen_on_plot.setCurrentIndex(0)
        self.screen_on_plot.blockSignals(False)
        if not screens:
            QMessageBox.information(self, "Scan error", "No screens available.")
            return

        delta_min = float(self.delta_min_scan.value())
        delta_max = float(self.delta_max_scan.value())
        steps = int(self.steps_settings.value())
        nshots = int(self.meas_per_step.value())

        self._last_scan_status = None
        self._scan_stop_requested = False
        self._is_scanning = True

        self._clear_fit_panel()
        self._set_progress(0)
        try:
            self.session = self.run_scan(
                quad_name=quadrupoles,
                delta_min=delta_min,
                delta_max=delta_max,
                steps=steps,
                nshots=nshots,
                screens=screens,
                reference_screen=screens[0],
                bpms=[],
                progress_callback=self._scan_progress_callback
            )
            if steps == 0:
                self.log("Conventional multi-screen EM finished.")
            else:
                self.log("Quadrupole scan finished.")
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
        QMessageBox.information(self, "Scan", f"Scan completed.")
        self._set_progress(100)

    def _get_twiss_s_positions(self, names):
        names = list(names)
        positions = [np.nan] * len(names)
        if not hasattr(self.interface, "_get_elements_positions"):
            return positions

        try:
            pos = self.interface._get_elements_positions()
            pos_names = list(pos.get("names", []))
            s = np.asarray(pos.get("S", []), dtype=float)
            lookup = {
                name: float(s[i])
                for i, name in enumerate(pos_names)
                if i < s.size and np.isfinite(s[i])
            }
            positions = [lookup.get(name, np.nan) for name in names]
        except Exception:
            positions = [np.nan] * len(names)
        return positions

    def _get_session_for_selected_quad(self, session):
        if not isinstance(session, dict):
            return session
        if session.get("mode") != "multi_quad_scan":
            return session
        per_quad = list(session.get("per_quad_sessions", []))
        if len(per_quad) == 0:
            return None
        combo_index = int(self.quad_on_plot.currentIndex())
        if 0 <= combo_index < len(per_quad):
            return per_quad[combo_index]
        selected_quad = self.quad_on_plot.currentText().strip()
        if selected_quad:
            for quad_session in per_quad:
                if str(quad_session.get("quad_name", "")).strip() == selected_quad:
                    return quad_session

        return per_quad[0]

    def _refresh_plot_comboboxes_from_session(self, session):
        if not isinstance(session, dict):
            return
        if session.get("mode") == "multi_quad_scan":
            per_quad = list(session.get("per_quad_sessions", []))
            quad_names = [str(qs.get("quad_name", "")).strip() for qs in per_quad if isinstance(qs, dict)]
            if quad_names:
                current_quad = self.quad_on_plot.currentText().strip()
                self.quad_on_plot.blockSignals(True)
                self.quad_on_plot.clear()
                self.quad_on_plot.addItems(quad_names)
                if current_quad in quad_names:
                    self.quad_on_plot.setCurrentText(current_quad)
                else:
                    self.quad_on_plot.setCurrentIndex(0)
                self.quad_on_plot.blockSignals(False)

            session_to_plot = self._get_session_for_selected_quad(session)
            if isinstance(session_to_plot, dict):
                screens = list(session_to_plot.get("screens", []))
                current_screen = self.screen_on_plot.currentText().strip()
                self.screen_on_plot.blockSignals(True)
                self.screen_on_plot.clear()
                self.screen_on_plot.addItems(screens)
                if current_screen in screens:
                    self.screen_on_plot.setCurrentText(current_screen)
                elif screens:
                    self.screen_on_plot.setCurrentIndex(0)
                self.screen_on_plot.blockSignals(False)

        else:
            quad_name = str(session.get("quad_name", "")).strip()
            screens = list(session.get("screens", []))

            if quad_name:
                self.quad_on_plot.blockSignals(True)
                self.quad_on_plot.clear()
                self.quad_on_plot.addItem(quad_name)
                self.quad_on_plot.setCurrentIndex(0)
                self.quad_on_plot.blockSignals(False)

            current_screen = self.screen_on_plot.currentText().strip()
            self.screen_on_plot.blockSignals(True)
            self.screen_on_plot.clear()
            self.screen_on_plot.addItems(screens)
            if current_screen in screens:
                self.screen_on_plot.setCurrentText(current_screen)
            elif screens:
                self.screen_on_plot.setCurrentIndex(0)
            self.screen_on_plot.blockSignals(False)

        self.screen_on_plot.setEnabled(not self.show_scan_on_all_screens.isChecked())

    def _filter_quadrupoles_in_gui(self):
        if not hasattr(self, "quadrupoles_list") or self.quadrupoles_list is None:
            return
        if not hasattr(self, "screens_list") or self.screens_list is None:
            return

        previously_selected = []
        for i in range(self.quadrupoles_list.count()):
            item = self.quadrupoles_list.item(i)
            if item.isSelected():
                previously_selected.append(item.data(Qt.ItemDataRole.UserRole) or item.text())

        if previously_selected:
            self._last_selected_quadrupoles = list(previously_selected)
        else:
            self._last_selected_quadrupoles = list(getattr(self, "_last_selected_quadrupoles", []))

        _, selected_screens = self._get_selection()
        if not selected_screens:
            return

        screen_position, screen_order_kind = self._get_element_order_values(selected_screens)
        finite_screen_positions = [float(s) for s in screen_position if np.isfinite(s)]
        if not finite_screen_positions:
            return

        first_screen_position = min(finite_screen_positions)
        last_screen_position = max(finite_screen_positions)
        all_quadrupoles = list(self.interface.get_quadrupoles().get("names", []))
        quad_order, quad_order_kind = self._get_element_order_values(all_quadrupoles)

        if quad_order_kind != screen_order_kind: # S [m] or index
            return

        quad_pos = {name: float(s) for name, s in zip(all_quadrupoles, quad_order) if np.isfinite(s)}

        before_last_screen_quads = [
            name for name in all_quadrupoles
            if name in quad_pos and quad_pos[name] < last_screen_position
        ]

        valid_previous = [q for q in getattr(self, "_last_selected_quadrupoles", []) if q in before_last_screen_quads]
        upstream_to_first_screen_quads = [name for name in before_last_screen_quads if quad_pos[name] < first_screen_position]

        self.quadrupoles_list.blockSignals(True)
        self._show_s_values_and_device_lists(self.quadrupoles_list, before_last_screen_quads)

        if valid_previous:
            for i in range(self.quadrupoles_list.count()):
                item = self.quadrupoles_list.item(i)
                item_name = item.data(Qt.ItemDataRole.UserRole) or item.text()
                if item_name in valid_previous:
                    item.setSelected(True)
            self._last_selected_quadrupoles = list(valid_previous)
        elif upstream_to_first_screen_quads:
            closest_quad = max(upstream_to_first_screen_quads, key=lambda name: quad_pos[name])
            for i in range(self.quadrupoles_list.count()):
                item = self.quadrupoles_list.item(i)
                item_name = item.data(Qt.ItemDataRole.UserRole) or item.text()
                if item_name == closest_quad:
                    item.setSelected(True)
                    self._last_selected_quadrupoles = [closest_quad]
                    break
        elif self.quadrupoles_list.count() > 0:
            item = self.quadrupoles_list.item(0)
            if item is not None:
                item.setSelected(True)
                item_name = item.data(Qt.ItemDataRole.UserRole) or item.text()
                self._last_selected_quadrupoles = [item_name]
        else:
            self._last_selected_quadrupoles = []

        self.quadrupoles_list.blockSignals(False)

    def _screen_selection_changed(self):
        self._filter_quadrupoles_in_gui()

    def _show_console_log(self):
        if self.log_console is None:
            self.log_console=LogConsole(self)
        self.log_console.show()
        self.log_console.raise_()
        self.log_console.activateWindow()

    def _show_phase_spaces(self):
        result = None
        reference_name = None

        if isinstance(self.session, dict):
            result = self.session.get("optimization_result")
            reference_name = self.session.get("quad_name") or self.session.get("current_quadrupole")

        if self.phase_spaces is None:
            self.phase_spaces = PhaseSpaces(self)

        screens = []
        session_to_plot = None
        if isinstance(self.session, dict):
            session_to_plot = self._get_session_for_selected_quad(self.session)
            if isinstance(session_to_plot, dict):
                screens = list(session_to_plot.get("screens", []))

        if not isinstance(result, dict):
            QMessageBox.information(self, "Phase Space", "Run the emittance/Twiss optimization first." )
            return

        session_to_plot = self._get_session_for_selected_quad(self.session) if isinstance(self.session, dict) else None

        if isinstance(session_to_plot, dict) and screens:
            self.phase_spaces.plot_projection_constraints(result, session_to_plot, interface=self.interface)
        else:
            self.phase_spaces.plot_from_result(result, reference_name=reference_name)

        self.phase_spaces.show()
        self.phase_spaces.raise_()
        self.phase_spaces.activateWindow()

    def log(self,text):
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line=f"[{timestamp}] {text}"
        if self.log_console is None:
            self.log_console=LogConsole(self)
        self.log_console.log(line)

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
