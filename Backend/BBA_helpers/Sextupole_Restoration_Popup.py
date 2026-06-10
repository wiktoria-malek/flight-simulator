try:
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QVBoxLayout, QDialog, QLabel, QWidget, QTabWidget
except ImportError:
    from PyQt5.QtCore import Qt
    from PyQt5.QtWidgets import QVBoxLayout, QDialog, QLabel, QWidget, QTabWidget

import matplotlib
from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas

matplotlib.use("QtAgg")
import numpy as np


class Sextupole_Restoration_Popup(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)
        self.setMinimumSize(800, 600)
        self.resize(1000, 720)
        self.setSizeGripEnabled(True)

        layout = QVBoxLayout(self)
        self.summary_label = QLabel("")
        self.summary_label.setWordWrap(True)
        layout.addWidget(self.summary_label)
        self.tabs = QTabWidget(self)
        layout.addWidget(self.tabs)

        self.tab_iter = QWidget()
        self.tab_bpm = QWidget()
        self.tabs.addTab(self.tab_iter, "Sextupoles")
        self.tabs.addTab(self.tab_bpm, "Residuals by BPM")

        iter_layout = QVBoxLayout(self.tab_iter)
        iter_layout.setContentsMargins(18, 12, 18, 18)
        iter_layout.setSpacing(10)
        self.fig_iter = Figure(figsize=(6, 4), tight_layout=True)
        self.canvas_iter = FigureCanvas(self.fig_iter)
        self.axes_iter = self.fig_iter.add_subplot(111)
        iter_layout.addWidget(self.canvas_iter)

        bpm_layout = QVBoxLayout(self.tab_bpm)

        self.fig_x = Figure(figsize=(5, 4), tight_layout=True)
        self.canvas_x = FigureCanvas(self.fig_x)
        self.axes_x = self.fig_x.add_subplot(111)
        bpm_layout.addWidget(self.canvas_x)

        self.fig_y = Figure(figsize=(5, 4), tight_layout=True)
        self.canvas_y = FigureCanvas(self.fig_y)
        self.axes_y = self.fig_y.add_subplot(111)
        bpm_layout.addWidget(self.canvas_y)

    def _make_2d(self, values):
        if values is None:
            return None
        array = np.asarray(values, dtype=float)
        if array.ndim == 1:
            array = array.reshape(1, -1)
        return array

    def _absolute_rms_vals(self, values_x, values_y):
        x_array = self._make_2d(values_x)
        y_array = self._make_2d(values_y)
        if x_array is None or y_array is None:
            return None, None, None

        mean_x = np.nanmean(x_array, axis=0)
        mean_y = np.nanmean(y_array, axis=0)

        rms_x = float(np.sqrt(np.nanmean(mean_x ** 2)))
        rms_y = float(np.sqrt(np.nanmean(mean_y ** 2)))
        rms_xy = float(np.sqrt(np.nanmean(mean_x ** 2 + mean_y ** 2)))
        return rms_x, rms_y, rms_xy

    def _plot_rms_iter(self, rms_x_iter, rms_y_iter, rms_xy_iter):
        self.axes_iter.clear()

        if not rms_x_iter and not rms_y_iter and not rms_xy_iter:
            self.canvas_iter.draw_idle()
            return

        max_len = max(len(rms_x_iter), len(rms_y_iter), len(rms_xy_iter))
        iterations = np.arange(max_len)

        if rms_x_iter:
            self.axes_iter.plot(np.arange(len(rms_x_iter)), rms_x_iter, marker="o", label="RMS x")
        if rms_y_iter:
            self.axes_iter.plot(np.arange(len(rms_y_iter)), rms_y_iter, marker="o", label="RMS y")
        if rms_xy_iter:
            self.axes_iter.plot(np.arange(len(rms_xy_iter)), rms_xy_iter, marker="o", label="RMS combined")

        self.axes_iter.set_title("Sextupole restoration residuals")
        self.axes_iter.set_xlabel("Sextupole restoration step")
        self.axes_iter.set_ylabel("RMS [mm]")
        self.axes_iter.grid(True, alpha=0.3)
        self.axes_iter.set_xticks(iterations)
        self.axes_iter.legend(fontsize=8, loc="upper right")
        self.canvas_iter.draw_idle()

    def _plot_rms_orbits(self, selected_bpms, start_x, start_y, final_x=None, final_y=None, x1_vals=None, y1_vals=None,
                         x2_vals=None, y2_vals=None):
        def bpm_rms(values):
            array = self._make_2d(values)
            if array is None:
                return None
            return np.sqrt(np.nanmean(array ** 2, axis=0))

        def bpm_rms_difference(values_hi, values_lo):
            hi = self._make_2d(values_hi)
            lo = self._make_2d(values_lo)
            if hi is None or lo is None:
                return None
            return np.sqrt(np.nanmean((hi - lo) ** 2, axis=0))

        rms_x_orbit = bpm_rms(start_x)
        rms_y_orbit = bpm_rms(start_y)
        rms_x_final = bpm_rms(final_x)
        rms_y_final = bpm_rms(final_y)
        rms_x_dfs = bpm_rms_difference(x1_vals, start_x)
        rms_y_dfs = bpm_rms_difference(y1_vals, start_y)
        rms_x_wfs = bpm_rms_difference(x2_vals, start_x)
        rms_y_wfs = bpm_rms_difference(y2_vals, start_y)

        if rms_x_orbit is None or rms_y_orbit is None:
            return

        xpos = np.arange(len(selected_bpms))

        self.axes_x.clear()
        self.axes_y.clear()

        self.axes_x.plot(xpos, rms_x_orbit, marker="o", label="Start RMS")
        self.axes_y.plot(xpos, rms_y_orbit, marker="o", label="Start RMS")

        if rms_x_final is not None:
            self.axes_x.plot(xpos, rms_x_final, marker="o", label="Final RMS")
        if rms_y_final is not None:
            self.axes_y.plot(xpos, rms_y_final, marker="o", label="Final RMS")

        if rms_x_dfs is not None:
            self.axes_x.plot(xpos, rms_x_dfs, marker="o", label="DFS RMS")
        if rms_x_wfs is not None:
            self.axes_x.plot(xpos, rms_x_wfs, marker="o", label="WFS RMS")
        if rms_y_dfs is not None:
            self.axes_y.plot(xpos, rms_y_dfs, marker="o", label="DFS RMS")
        if rms_y_wfs is not None:
            self.axes_y.plot(xpos, rms_y_wfs, marker="o", label="WFS RMS")

        self.axes_x.set_title("Horizontal RMS per BPM")
        self.axes_y.set_title("Vertical RMS per BPM")
        self.axes_x.set_xlabel("BPM index")
        self.axes_y.set_xlabel("BPM index")
        self.axes_x.set_ylabel("RMS [mm]")
        self.axes_y.set_ylabel("RMS [mm]")
        self.axes_x.grid(True, alpha=0.3)
        self.axes_y.grid(True, alpha=0.3)
        self.axes_x.set_xticks(xpos)
        self.axes_y.set_xticks(xpos)
        self.axes_x.set_xticklabels(selected_bpms, rotation=90, fontsize=8)
        self.axes_y.set_xticklabels(selected_bpms, rotation=90, fontsize=8)
        self.axes_x.legend(fontsize=8, loc="upper right")
        self.axes_y.legend(fontsize=8, loc="upper right")
        self.canvas_x.draw_idle()
        self.canvas_y.draw_idle()

    def plot_all(
            self,
            selected_bpms,
            start_x,
            start_y,
            current_x=None,
            current_y=None,
            final_x=None,
            final_y=None,
            x1_vals=None,
            y1_vals=None,
            x2_vals=None,
            y2_vals=None,
            rms_x_iter=None,
            rms_y_iter=None,
            rms_xy_iter=None,
            nominal_x=None,
            nominal_y=None,
    ):
        rms_x_iter = [] if rms_x_iter is None else list(rms_x_iter)
        rms_y_iter = [] if rms_y_iter is None else list(rms_y_iter)
        rms_xy_iter = [] if rms_xy_iter is None else list(rms_xy_iter)

        if not rms_x_iter and not rms_y_iter and not rms_xy_iter:
            rms_x, rms_y, rms_xy = self._absolute_rms_vals(start_x, start_y)
            if rms_x is not None:
                rms_x_iter = [rms_x]
                rms_y_iter = [rms_y]
                rms_xy_iter = [rms_xy]
        nominal_summary = self._absolute_rms_vals(nominal_x, nominal_y)
        start_summary = self._absolute_rms_vals(start_x, start_y)
        current_summary = self._absolute_rms_vals(current_x, current_y)
        final_summary = self._absolute_rms_vals(final_x, final_y)

        parts = []
        if nominal_summary[0] is not None:
            parts.append(
                f"Nominal RMS: x={nominal_summary[0]:.6f} mm, "
                f"y={nominal_summary[1]:.6f} mm, "
                f"combined={nominal_summary[2]:.6f} mm"
            )
        if start_summary[0] is not None:
            parts.append(
                f"Start RMS: x={start_summary[0]:.6f} mm, "
                f"y={start_summary[1]:.6f} mm, "
                f"combined={start_summary[2]:.6f} mm"
            )
        if current_summary[0] is not None:
            parts.append(
                f"Last pre-correction RMS: x={current_summary[0]:.6f} mm, "
                f"y={current_summary[1]:.6f} mm, "
                f"combined={current_summary[2]:.6f} mm"
            )
        if final_summary[0] is not None:
            parts.append(
                f"Final RMS: x={final_summary[0]:.6f} mm, "
                f"y={final_summary[1]:.6f} mm, "
                f"combined={final_summary[2]:.6f} mm"
            )

        self.summary_label.setText(" | ".join(parts))
        self._plot_rms_iter(rms_x_iter, rms_y_iter, rms_xy_iter)
        self._plot_rms_orbits(
            selected_bpms=selected_bpms,
            start_x=start_x,
            start_y=start_y,
            final_x=final_x,
            final_y=final_y,
            x1_vals=x1_vals,
            y1_vals=y1_vals,
            x2_vals=x2_vals,
            y2_vals=y2_vals,
        )
    def plot_sextupole_history(self, history):
        history = list(history or [])
        if not history:
            self.summary_label.setText("No sextupole restoration data available.")
            return

        labels = [str(item.get("name", "")) for item in history]
        before_xy = np.asarray([item.get("before_rms_xy", np.nan) for item in history], dtype=float)
        after_xy = np.asarray([item.get("after_rms_xy", np.nan) for item in history], dtype=float)
        before_x = np.asarray([item.get("before_rms_x", np.nan) for item in history], dtype=float)
        after_x = np.asarray([item.get("after_rms_x", np.nan) for item in history], dtype=float)
        before_y = np.asarray([item.get("before_rms_y", np.nan) for item in history], dtype=float)
        after_y = np.asarray([item.get("after_rms_y", np.nan) for item in history], dtype=float)

        first_before = before_xy[0]
        last_after = after_xy[-1]
        total_improvement = first_before - last_after
        self.summary_label.setText(
            f"Post-BBA sextupole restoration summary | "
            f"initial residual={first_before:.6g} mm, "
            f"final residual={last_after:.6g} mm, "
            f"net improvement={total_improvement:.6g} mm"
        )

        xpos = np.arange(len(labels))
        self.axes_iter.clear()
        self.axes_iter.plot(xpos, before_xy, marker="o", label="Before orbit correction")
        self.axes_iter.plot(xpos, after_xy, marker="o", label="After orbit correction")
        self.axes_iter.set_title("Sextupole restoration residuals")
        self.axes_iter.set_xlabel("Sextupole")
        self.axes_iter.set_ylabel("Residual RMS to post-BBA orbit [mm]")
        self.axes_iter.set_xticks(xpos)
        self.axes_iter.set_xticklabels(labels, rotation=45, ha="right", fontsize=8)
        self.axes_iter.grid(True, alpha=0.3)
        self.axes_iter.legend(fontsize=8, loc="upper right")
        self.canvas_iter.draw_idle()

        last = history[-1]
        bpms = list(last.get("bpms", []))
        before_dx = np.asarray(last.get("before_dx", []), dtype=float)
        after_dx = np.asarray(last.get("after_dx", []), dtype=float)
        before_dy = np.asarray(last.get("before_dy", []), dtype=float)
        after_dy = np.asarray(last.get("after_dy", []), dtype=float)
        bpm_x = np.arange(len(bpms))

        self.axes_x.clear()
        self.axes_y.clear()
        if len(bpms) and before_dx.size == len(bpms) and after_dx.size == len(bpms):
            self.axes_x.plot(bpm_x, before_dx, marker="o", label="Before correction")
            self.axes_x.plot(bpm_x, after_dx, marker="o", label="After correction")
            self.axes_x.set_xticks(bpm_x)
            self.axes_x.set_xticklabels(bpms, rotation=90, fontsize=8)
        if len(bpms) and before_dy.size == len(bpms) and after_dy.size == len(bpms):
            self.axes_y.plot(bpm_x, before_dy, marker="o", label="Before correction")
            self.axes_y.plot(bpm_x, after_dy, marker="o", label="After correction")
            self.axes_y.set_xticks(bpm_x)
            self.axes_y.set_xticklabels(bpms, rotation=90, fontsize=8)

        self.axes_x.set_title(f"Horizontal residuals by BPM after {last.get('name', '')}")
        self.axes_y.set_title(f"Vertical residuals by BPM after {last.get('name', '')}")
        self.axes_x.set_xlabel("BPM")
        self.axes_y.set_xlabel("BPM")
        self.axes_x.set_ylabel("x - post-BBA x [mm]")
        self.axes_y.set_ylabel("y - post-BBA y [mm]")
        self.axes_x.grid(True, alpha=0.3)
        self.axes_y.grid(True, alpha=0.3)
        self.axes_x.legend(fontsize=8, loc="upper right")
        self.axes_y.legend(fontsize=8, loc="upper right")
        self.canvas_x.draw_idle()
        self.canvas_y.draw_idle()