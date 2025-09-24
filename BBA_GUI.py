import sys, os, pickle
from datetime import datetime
import numpy as np

from PyQt6 import uic
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QApplication, QMainWindow, QFileDialog, QListWidget, QMessageBox, QProgressDialog, QVBoxLayout, QPushButton, QDialog, QLabel)

try:
    import matplotlib
    matplotlib.use("QtAgg")
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
    from matplotlib.figure import Figure
except Exception:
    FigureCanvas = Figure = None

from DFS_WFS_Correction_BBA import CorrectionEngine
from Response_BBA import load_dfs_npz, load_wfs_npz


class ChiSquaredWindow(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("χ² = w₁·O + w₂·D + w₃·W")
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)
        self.setFixedSize(520, 320)
        self.setSizeGripEnabled(True)

        self.w1 = self.w2 = self.w3 = 1.0

        self._O = []
        self._D = []
        self._W = []

        self._O0=None
        self._D0=None
        self._W0=None

        layout = QVBoxLayout(self)
        self.info = QLabel("w1=1.0, w2=1.0, w3=1.0")
        layout.addWidget(self.info)

        self.fig = Figure(figsize=(5.0, 2.4), tight_layout=True)
        self.canvas = FigureCanvas(self.fig)
        layout.addWidget(self.canvas)

        self.ax = self.fig.add_subplot(111)
        (self.line_O,) = self.ax.plot([], [], marker="o", label="O (orbit)")
        (self.line_D,) = self.ax.plot([], [], marker="o", label="D (dispersion)")
        (self.line_W,) = self.ax.plot([], [], marker="o", label="W (wakefield)")

        self.ax.set_xlabel("Iteration")
        self.ax.set_ylabel("Value")
        self.ax.grid(True, alpha=0.3)
        self.ax.legend(loc="best")

    def set_weights(self, w1, w2, w3):
        self.w1, self.w2, self.w3 = float(w1), float(w2), float(w3)
        self.info.setText(f"w1={self.w1:g}, w2={self.w2:g}, w3={self.w3:g}")

    def clear(self):
        self._O.clear(); self._D.clear(); self._W.clear()
        self._O0=self._D0=self._W0=None
        self._set_lines([], [], [], [])

    def append_point(self, orbit_rms, disp_rms, wake_rms):

        O_beg=float(orbit_rms)
        D_beg=float(disp_rms)
        W_beg=float(wake_rms)

        # if self._O0 is None:
        #     self._O0=O_beg if O_beg !=0 else 1e-12
        #     self._D0=D_beg

        O = (O_beg/self._O0)*(O_beg/self._O0)
        D = (D_beg/self._D0)*(D_beg/self._D0)
        W = (W_beg/self._W0)*(W_beg/self._W0)

        self._O.append(O); self._D.append(D); self._W.append(W)
        self._redraw()

    def _redraw(self):
        x = list(range(1, len(self._O) + 1))
        self._set_lines(x, self._O, self._D, self._W)

    def _set_lines(self, x, O, D, W):
        self.line_O.set_data(x, O)
        self.line_D.set_data(x, D)
        self.line_W.set_data(x, W)

        self.ax.relim()
        self.ax.autoscale_view()
        self.canvas.draw_idle()

    def closeEvent(self, e):
        p = self.parent()
        if p is not None and hasattr(p, "_chi_dlg"):
            p._chi_dlg = None
        super().closeEvent(e)

    def seed_with_history(self, O, D, W):
        O=list(map(float, O))
        D=list(map(float, D))
        W=list(map(float, W))

        if O:
            self._O0=O[0] if O[0] != 0 else 1e-12
            self._D0=D[0] if D[0] != 0 else 1e-12
            self._W0=W[0] if W[0] != 0 else 1e-12

        self._O = [(value/self._O0) * (value/self._O0) for value in O]
        self._D = [(value/self._D0) * (value/self._D0) for value in D]
        self._W = [(value/self._W0) * (value/self._W0) for value in W]
        self._redraw()

class MainWindow(QMainWindow):
    def __init__(self, interface, dir_name):
        super().__init__()
        self.cwd = os.getcwd()
        self.interface = interface
        self.dir_name = dir_name
        self._cancel = False

        ui_path = os.path.join(os.path.dirname(__file__), "BBA_GUI.ui")
        uic.loadUi(ui_path, self)

        #self.setCentralWidget(popup_button)

        self.engine = CorrectionEngine(interface)
        self._hist_orbit = []
        self._hist_disp = []
        self._hist_wake = []

        self._setup_canvases()
        self._populate_lists()

        self.save_correctors_button.clicked.connect(self._save_correctors)
        self.load_correctors_button.clicked.connect(self._load_correctors)
        self.clear_correctors_button.clicked.connect(self.correctors_list.clearSelection)
        self.save_bpms_button.clicked.connect(self._save_bpms)
        self.load_bpms_button.clicked.connect(self._load_bpms)
        self.clear_bpms_button.clicked.connect(self.bpms_list.clearSelection)

        if hasattr(self, "pushButton_8"):
            self.pushButton_8.clicked.connect(self._pick_and_load_traj_response)
        if hasattr(self, "pushButton_9"):
            self.pushButton_9.clicked.connect(self._build_and_save_dfs)
        if hasattr(self, "pushButton_10"):
            self.pushButton_10.clicked.connect(self._build_and_save_wfs)

        if hasattr(self, "popup_button"):
            self.popup_button.clicked.connect(self._show_kai_squared_graphs)

        self.start_button.clicked.connect(self._start_correction)
        self.stop_button.clicked.connect(self._stop_correction)

        self.setWindowTitle("BBA")

    #def button_clicked(self):
        #print("clicked")
    def _setup_canvases(self):
        if FigureCanvas is None:
            self.traj_canvas = self.disp_canvas = self.wake_canvas = None
            return

        def install(host):
            fig = Figure(figsize=(4, 2.2), tight_layout=True)
            canvas = FigureCanvas(fig)
            layout = host.layout()
            if layout is None:
                from PyQt6.QtWidgets import QVBoxLayout
                layout = QVBoxLayout(host)
                layout.setContentsMargins(0, 0, 0, 0)
            layout.addWidget(canvas)
            return fig, canvas

        self.traj_fig, self.traj_canvas = install(self.plot_widget_3)
        self.disp_fig, self.disp_canvas = install(self.plot_widget_4)
        self.wake_fig, self.wake_canvas = install(self.plot_widget_5)

    def _plot_series(self, canvas, fig, values, title, ylabel):
        if canvas is None:
            return
        fig.clear()
        ax = fig.add_subplot(111)
        if values:
            ax.plot(range(1, len(values) + 1), values, marker="o")
        ax.set_title(title)
        ax.set_xlabel("Iteration")
        ax.set_ylabel(ylabel)
        ax.grid(True, alpha=0.3)
        canvas.draw_idle()

    def _populate_lists(self):
        corrs = self.interface.get_correctors()["names"]
        bpms = self.interface.get_bpms()["names"]
        self.correctors_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.bpms_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.correctors_list.insertItems(0, corrs)
        self.bpms_list.insertItems(0, bpms)

    def _selected_or_all(self, widget, full):
        sel = [it.text() for it in widget.selectedItems()]
        return sel if sel else list(full)

    def _get_selection(self):
        corrs_all = self.interface.get_correctors()["names"]
        bpms_all = self.interface.get_bpms()["names"]
        corrs = self._selected_or_all(self.correctors_list, corrs_all)
        bpms = self._selected_or_all(self.bpms_list, bpms_all)
        return corrs, bpms

    def _force_triangular(self) -> bool:
        try:
            return bool(self.checkBox.isChecked())
        except Exception:
            return False

    def _save_correctors(self):
        os.makedirs(self.dir_name, exist_ok=True)
        fn, _ = QFileDialog.getSaveFileName(self, "Save Correctors",os.path.join(self.dir_name, "correctors.txt"), "Text (*.txt)")
        if not fn:
            return
        with open(fn, "w") as f:
            for it in self.correctors_list.selectedItems():
                f.write(f"{it.text()}\n")

    def _load_correctors(self):
        fn, _ = QFileDialog.getOpenFileName(self, "Load Correctors",os.path.join(self.dir_name, "correctors.txt"), "Text (*.txt)")
        selected = []
        if fn:
            with open(fn, "r") as f:
                selected = [ln.strip() for ln in f]
        else:
            selected = self.interface.get_correctors()["names"]
        self.correctors_list.clearSelection()
        for name in selected:
            for it in self.correctors_list.findItems(name, Qt.MatchFlag.MatchExactly):
                it.setSelected(True)

    def _save_bpms(self):
        os.makedirs(self.dir_name, exist_ok=True)
        fn, _ = QFileDialog.getSaveFileName(self, "Save BPMs", os.path.join(self.dir_name, "bpms.txt"), "Text (*.txt)")
        if not fn:
            return
        with open(fn, "w") as f:
            for it in self.bpms_list.selectedItems():
                f.write(f"{it.text()}\n")

    def _load_bpms(self):
        fn, _ = QFileDialog.getOpenFileName(self, "Load BPMs", os.path.join(self.dir_name, "bpms.txt"), "Text (*.txt)")
        selected = []
        if fn:
            with open(fn, "r") as f:
                selected = [ln.strip() for ln in f]
        else:
            selected = self.interface.get_bpms()["names"]
        self.bpms_list.clearSelection()
        for name in selected:
            for it in self.bpms_list.findItems(name, Qt.MatchFlag.MatchExactly):
                it.setSelected(True)

    def _with_progress(self, total, title):
        prog = QProgressDialog(title, "Cancel", 0, total, self)
        prog.setWindowModality(Qt.WindowModality.ApplicationModal)
        prog.setMinimumDuration(0)

        def cb(i, n, text):
            prog.setMaximum(n)
            prog.setValue(i)
            prog.setLabelText(text)
            QApplication.processEvents()
            return not prog.wasCanceled()

        return prog, cb

    def _build_and_save_dfs(self):
        try:
            default_dir = os.path.join(self.cwd, "Data")
            os.makedirs(default_dir, exist_ok=True)
            fn, _ = QFileDialog.getSaveFileName(self, "Save DFS response (R & R')",os.path.join(default_dir, "dfs_response.npz"),"NumPy archive (*.npz)")
            if not fn:
                return

            corrs, bpms = self._get_selection()

            prog, cb = self._with_progress(len(corrs), "Measuring response (nominal)…")
            R_nom = self.engine.compute_response_matrix(corrs, bpms, delta=0.01,triangular=self._force_triangular(), progress_cb=cb)
            prog.close()

            self.engine.set_offenergy_flag(True)
            self.interface.change_energy()
            prog, cb = self._with_progress(len(corrs), "Measuring response (off-energy)…")
            R_test = self.engine.compute_response_matrix(corrs, bpms, delta=0.01,
                                                         triangular=self._force_triangular(), progress_cb=cb)
            prog.close()
            self.interface.reset_energy()
            self.engine.set_offenergy_flag(False)

            np.savez(
                fn,
                bpms=np.array(bpms, dtype=object),
                correctors=np.array(corrs, dtype=object),
                delta_nom=R_nom["delta"], Rx_nom=R_nom["Rx"], Ry_nom=R_nom["Ry"],
                delta_test=R_test["delta"], Rx_test=R_test["Rx"], Ry_test=R_test["Ry"],
                note="DFS: response at nominal (R) and changed energy (R').",
            )
            if hasattr(self, "dfs_response_3"):
                self.dfs_response_3.setText(fn)
            QMessageBox.information(self, "DFS", f"Saved DFS responses to:\n{fn}")
        except Exception as e:
            QMessageBox.critical(self, "DFS error", str(e))

    def _build_and_save_wfs(self):
        try:
            default_dir = os.path.join(self.cwd, "Data")
            os.makedirs(default_dir, exist_ok=True)
            fn, _ = QFileDialog.getSaveFileName(self, "Save WFS response (R_low & R_high)",os.path.join(default_dir, "wfs_response.npz"),"NumPy archive (*.npz)" )
            if not fn:
                return

            corrs, bpms = self._get_selection()

            self.engine.set_highintensity_flag(False)
            self.interface.reset_intensity()
            prog, cb = self._with_progress(len(corrs), "Measuring response (low intensity)…")
            R_low = self.engine.compute_response_matrix(corrs, bpms, delta=0.01,triangular=self._force_triangular(), progress_cb=cb)
            prog.close()

            self.engine.set_highintensity_flag(True)
            self.interface.change_intensity()
            prog, cb = self._with_progress(len(corrs), "Measuring response (high intensity)…")
            R_high = self.engine.compute_response_matrix(corrs, bpms, delta=0.01,triangular=self._force_triangular(), progress_cb=cb)
            prog.close()
            self.interface.reset_intensity()
            self.engine.set_highintensity_flag(False)

            np.savez(
                fn,
                bpms=np.array(bpms, dtype=object),
                correctors=np.array(corrs, dtype=object),
                delta_low=R_low["delta"],  Rx_low=R_low["Rx"],  Ry_low=R_low["Ry"],
                delta_high=R_high["delta"], Rx_high=R_high["Rx"], Ry_high=R_high["Ry"],
                note="WFS: response at low and high intensity for wakefield-free steering.",
            )
            if hasattr(self, "wfs_response_3"):
                self.wfs_response_3.setText(fn)
            QMessageBox.information(self, "WFS", f"Saved WFS responses to:\n{fn}")
        except Exception as e:
            QMessageBox.critical(self, "WFS error", str(e))

    def _pick_and_load_traj_response(self):

        default_dir = os.path.join(self.cwd, "Data")
        os.makedirs(default_dir, exist_ok=True)

        folder = QFileDialog.getExistingDirectory(self, "Select response folder", default_dir)
        if not folder:
            return

        try:
            pkl_file = os.path.join(folder, "response.pkl")
            npz_file = os.path.join(folder, "dfs_response.npz")

           #for sys id
            if os.path.isfile(pkl_file):
                with open(pkl_file, "rb") as f:
                    obj = pickle.load(f)

                self.traj_response = {
                    "file": pkl_file,
                    "bpms": list(map(str, getattr(obj, "bpms", []))),
                    "hcorrs": list(map(str, getattr(obj, "hcorrs", []))),
                    "vcorrs": list(map(str, getattr(obj, "vcorrs", []))),
                    "Rxx": np.asarray(getattr(obj, "Rxx"), float),
                    "Ryy": np.asarray(getattr(obj, "Ryy"), float),
                    "Bx": np.asarray(getattr(obj, "Bx"), float),
                    "By": np.asarray(getattr(obj, "By"), float),
                    "source": "pkl",
                }
                if hasattr(self, "trajectory_response_3"):
                    self.trajectory_response_3.setText(pkl_file)
                QMessageBox.information(self, "Response loaded (PKL)",
                                        f"Loaded SysID response from '{os.path.basename(folder)}'.")
                return

            # for dfs
            if os.path.isfile(npz_file):
                D = np.load(npz_file, allow_pickle=True)
                files = set(D.files)

                if {"Rx_nom", "Ry_nom"} <= files:
                    Rx = np.asarray(D["Rx_nom"], float)
                    Ry = np.asarray(D["Ry_nom"], float)
                elif {"Rx", "Ry"} <= files:
                    Rx = np.asarray(D["Rx"], float)
                    Ry = np.asarray(D["Ry"], float)
                else:
                    raise KeyError(
                        "dfs_response.npz must contain Rx_nom/Ry_nom (or legacy Rx/Ry). "
                        f"Found keys: {sorted(files)}"
                    )

                bpms = list(map(str, D["bpms"])) if "bpms" in files else []
                correctors = list(map(str, D["correctors"])) if "correctors" in files else []

                self.traj_response = {
                    "file": npz_file,
                    "bpms": bpms,
                    "correctors": correctors,
                    "Rx": Rx,
                    "Ry": Ry,
                    "source": "npz",
                }
                if hasattr(self, "trajectory_response_3"):
                    self.trajectory_response_3.setText(npz_file)
                QMessageBox.information(self, "Response loaded (NPZ)",
                                        f"Loaded DFS response from '{os.path.basename(folder)}'.")
                return

            raise FileNotFoundError(
                "This folder doesn’t contain a trajectory response.\n"
                "Expected either 'response.pkl' (SysID) or 'dfs_response.npz' (DFS)."
            )

        except Exception as e:
            QMessageBox.critical(self, "Load error", str(e))

    def _read_params(self):
        def getf(name, default):
            w = getattr(self, name, None)
            try:
                t = (w.text() or "").strip()
                return float(t) if t else float(default)
            except Exception:
                return float(default)
        def geti(name, default):
            w = getattr(self, name, None)
            try:
                t = (w.text() or "").strip()
                return int(float(t)) if t else int(default)
            except Exception:
                return int(default)

        orbit_w = getf("lineEdit", 1.0)
        disp_w  = getf("lineEdit_2", 10.0)
        wake_w  = getf("lineEdit_3", 10.0)
        rcond   = getf("lineEdit_4", 0.001)
        iters   = geti("lineEdit_5", 10)
        return orbit_w, disp_w, wake_w, rcond, iters

    def _start_correction(self):
        try:
            self._cancel = False

            w1, w2, w3, rcond, iters = self._read_params()
            orbit_w, disp_w, wake_w = w1, w2, w3

            self._hist_orbit.clear()
            self._hist_disp.clear()
            self._hist_wake.clear()

            if getattr(self, "_chi_dlg", None):
                self._chi_dlg.set_weights(w1, w2, w3)
                self._chi_dlg.clear()

            corrs, bpms = self._get_selection()

            R_nom, R_disp, R_wake = None, None, None
            if hasattr(self, "dfs_response_3"):
                dfs_path = (self.dfs_response_3.text() or "").strip()
                if dfs_path and os.path.isfile(dfs_path):
                    R_nom, R_disp = load_dfs_npz(dfs_path, bpms, corrs)

            if hasattr(self, "wfs_response_3"):
                wfs_path = (self.wfs_response_3.text() or "").strip()
                if wfs_path and os.path.isfile(wfs_path):
                    R_wake = load_wfs_npz(wfs_path, bpms, corrs)


            def on_iter(i, orbit_rms, disp_rms, wake_rms):
                if orbit_rms is not None: self._hist_orbit.append(orbit_rms)
                if disp_rms is not None: self._hist_disp.append(disp_rms)
                if wake_rms is not None: self._hist_wake.append(wake_rms)

                self._plot_series(self.traj_canvas, self.traj_fig, self._hist_orbit, "Orbit norm", "‖y_nom‖ [mm]")
                self._plot_series(self.disp_canvas, self.disp_fig, self._hist_disp, "Dispersion Free Steering", "‖y_off − y_nom‖ [mm]")
                self._plot_series(self.wake_canvas, self.wake_fig, self._hist_wake, "Wakefield Free Steering","‖y_high − y_low‖ [mm]")

                if getattr(self, "_chi_dlg", None):
                    self._chi_dlg.append_point(orbit_rms or 0.0, disp_rms or 0.0, wake_rms or 0.0)

                QApplication.processEvents()
                return not self._cancel

            self.setWindowTitle("BBA - [Correction running]")
            self.engine.solve_and_apply(
                orbit_w=orbit_w, disp_w=disp_w, wake_w=wake_w,
                rcond=rcond, max_iters=iters,
                bpms=bpms, corrs=corrs,
                triangular=self._force_triangular(),
                R_nom=R_nom, R_disp=R_disp, R_wake=R_wake,
                iter_cb=on_iter,
            )
            self.setWindowTitle("BBA")
            QMessageBox.information(self, "Correction", "Correction finished.")
        except Exception as e:
            self.setWindowTitle("BBA")
            QMessageBox.critical(self, "Correction error", str(e))

    def _stop_correction(self):
        self._cancel = True
        QMessageBox.information(self, "Correction", "Stop requested. Finishing current iteration...")

    def _show_kai_squared_graphs(self):
        if getattr(self, "_chi_dlg", None) is None:
            self._chi_dlg = ChiSquaredWindow(self)

        w1, w2, w3, *_ = self._read_params()
        self._chi_dlg.set_weights(w1, w2, w3)

        self._chi_dlg.seed_with_history(self._hist_orbit, self._hist_disp, self._hist_wake)

        self._chi_dlg.show()
        self._chi_dlg.raise_()
        self._chi_dlg.activateWindow()


if __name__ == "__main__":
    app = QApplication(sys.argv)

    from SelectInterface import InterfaceSelectionDialog
    dialog = InterfaceSelectionDialog()
    if dialog.exec():
        I = dialog.selected_interface
        print(f"Selected interface: {dialog.selected_interface_name}")
    else:
        print("Selection cancelled.")
        sys.exit(1)

    project_name = dialog.selected_interface_name
    time_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = f"Data/{project_name}_{time_str}"

    w = MainWindow(I, out_dir)
    w.show()
    sys.exit(app.exec())
