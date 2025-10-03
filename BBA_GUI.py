import sys, os, pickle
from datetime import datetime
import numpy as np
import re
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
from Response import load_dfs_npz, load_wfs_npz, reorder_matrix_to_gui


class ChiSquaredWindow(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("χ² = w₁·O + w₂·D + w₃·W")
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)
        #self.setFixedSize(520, 320)
        self.setMinimumSize(520, 320)
        self.resize(700, 420)
        self.setSizeGripEnabled(True)
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

        O_beg=float(orbit_rms) if orbit_rms is not None else np.nan
        D_beg=float(disp_rms) if disp_rms is not None else np.nan
        W_beg=float(wake_rms) if wake_rms is not None else np.nan

        if self._O0 is None:
        #self._O0,self._D0,self._W0=O_beg,D_beg,W_beg
            eps=np.finfo(float).eps

            self._O0=O_beg if np.isfinite(O_beg) and O_beg !=0 else eps
            self._D0=D_beg if np.isfinite(D_beg) and D_beg !=0 else eps
            self._W0=W_beg if np.isfinite(W_beg) and W_beg !=0 else eps

        O = (O_beg/self._O0)**2 if np.isfinite(O_beg) else np.nan
        D = (D_beg/self._D0)**2 if np.isfinite(D_beg) else np.nan
        W = (W_beg/self._W0)**2 if np.isfinite(W_beg) else np.nan

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

    def calculating_chi(self, O, D, W):

        if not O:
            return

        if self._O0 is None:
            self._O0=next((value for value in O if value), 1)
            self._D0=next((value for value in D if value), 1)
            self._W0=next((value for value in W if value),1)

        self._O = [(value/self._O0)**2 for value in O]
        self._D = [(value/self._D0)**2 for value in D]
        self._W = [(value/self._W0)**2 for value in W]
        self._redraw()

class MainWindow(QMainWindow):
    def __init__(self, interface, dir_name):
        super().__init__()
        self.cwd = os.getcwd()
        self.interface = interface
        self.dir_name = dir_name
        self._cancel = False
        self._number_re = re.compile(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?")

        ui_path = os.path.join(os.path.dirname(__file__), "BBA_GUI.ui")
        uic.loadUi(ui_path, self)

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
        self.lineEdit.setText("1")
        self.lineEdit_2.setText("10")
        self.lineEdit_3.setText("10")
        self.lineEdit_4.setText("0.001")
        self.lineEdit_5.setText("10")

    def _finding_float(self,text, default):
        m = self._number_re.search(text)
        return float(m.group(0)) if m else default

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
        self.bpms_list.insertItems(0, bpms) #at the top of the list

    def _selected_or_all(self, widget, full):
        sel = [it.text() for it in widget.selectedItems()] #selected items
        return sel if sel else list(full) #if not,then full

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
                selected = [ln.strip() for ln in f] #makes a list
        else:
            selected = self.interface.get_bpms()["names"]
        self.bpms_list.clearSelection()
        for name in selected:
            for it in self.bpms_list.findItems(name, Qt.MatchFlag.MatchExactly):
                it.setSelected(True)

    def _with_progress(self, total, title):
        prog = QProgressDialog(title, "Cancel", 0, total, self)
        prog.setWindowModality(Qt.WindowModality.ApplicationModal) #user cant interact with the main window
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
            fn, _ = QFileDialog.getSaveFileName(self, "Save DFS response (R_nom & R_off')",os.path.join(default_dir, "dfs_response.npz"),"NumPy archive (*.npz)")
            if not fn:
                return

            corrs, bpms = self._get_selection()
            delta_nom_energy=self._read_change_energy()
            reset_energy=self._read_reset_energy()

            self.engine.set_offenergy_flag(False)
            self.interface.reset_energy(reset_energy)

            prog, cb = self._with_progress(len(corrs), "Measuring R  (nominal energy)…")
            R_nom = self.engine.compute_response_matrix(corrs, bpms, delta=0.01,triangular=self._force_triangular(),progress_cb=cb)
            prog.close()

            self.engine.set_offenergy_flag(True)
            self.interface.change_energy(delta_nom_energy)

            prog, cb = self._with_progress(len(corrs), "Measuring R′ (off-energy)…")
            R_off = self.engine.compute_response_matrix(corrs, bpms, delta=0.01,triangular=self._force_triangular(),progress_cb=cb)
            prog.close()

            self.interface.reset_energy(reset_energy)
            self.engine.set_offenergy_flag(False)

            np.savez( #npz is a zip of numpy arrays
                fn, #file that user selected
                bpms=np.array(bpms, dtype=object),
                correctors=np.array(corrs, dtype=object),
                delta_nom=R_nom["delta"], Rx_nom=R_nom["Rx"], Ry_nom=R_nom["Ry"],
                delta_test=R_off["delta"], Rx_test=R_off["Rx"], Ry_test=R_off["Ry"],
                note="DFS: response at nominal (R) and changed energy (R').",
            )               #delta is a step size used for varying correctors

            self.dfs_response_3.setText(fn)
            QMessageBox.information(self, "DFS", f"Saved DFS responses to:\n{fn}")
        except Exception as e:
            QMessageBox.critical(self, "DFS error", str(e))

    def _build_and_save_wfs(self):
        try:
            default_dir = os.path.join(self.cwd, "Data")
            os.makedirs(default_dir, exist_ok=True)
            fn, _ = QFileDialog.getSaveFileName(self, "Save WFS response (R_low & R_high)",os.path.join(default_dir, "wfs_response.npz"),"NumPy archive (*.npz)")
            if not fn:
                return

            corrs, bpms = self._get_selection()
            change_intensity=self._read_change_intensity()
            reset_intensity=self._read_reset_intensity()

            self.engine.set_highintensity_flag(False)
            self.interface.reset_intensity(reset_intensity)

            prog, cb = self._with_progress(len(corrs), "Measuring R_low (low current)…")
            R_low = self.engine.compute_response_matrix(corrs, bpms, delta=0.01,triangular=self._force_triangular(),progress_cb=cb)
            prog.close()

            self.engine.set_highintensity_flag(True)
            self.interface.change_intensity(change_intensity)

            prog, cb = self._with_progress(len(corrs), "Measuring R_high (high current)…")
            R_high = self.engine.compute_response_matrix(corrs, bpms, delta=0.01,triangular=self._force_triangular(),progress_cb=cb)
            prog.close()

            self.interface.reset_intensity(reset_intensity)
            self.engine.set_highintensity_flag(False)

            np.savez(
                fn,
                bpms=np.array(bpms, dtype=object),
                correctors=np.array(corrs, dtype=object),
                delta_low=R_low["delta"], Rx_low=R_low["Rx"], Ry_low=R_low["Ry"],
                delta_high=R_high["delta"], Rx_high=R_high["Rx"], Ry_high=R_high["Ry"],
                note="WFS: response at low and high intensity for wakefield-free steering.",
            )
            self.wfs_response_3.setText(fn)
            QMessageBox.information(self, "WFS",f"Saved WFS responses to:\n{fn}")

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

                def _g(o, key):
                    return o[key] if isinstance(o, dict) else getattr(o, key, [])

                self.traj_response = {
                    "file": pkl_file,
                    "bpms": list(map(str, _g(obj, "bpms"))),
                    "hcorrs": list(map(str, _g(obj, "hcorrs"))),
                    "vcorrs": list(map(str, _g(obj, "vcorrs"))),
                    "Rxx": np.asarray(_g(obj, "Rxx"), float),
                    "Ryy": np.asarray(_g(obj, "Ryy"), float),
                    "Bx": np.asarray(_g(obj, "Bx"), float),
                    "By": np.asarray(_g(obj, "By"), float),
                    "source": "pkl",
                }
                self.traj_file=pkl_file

                if hasattr(self, "trajectory_response_3"):
                    self.trajectory_response_3.setText(pkl_file)
                QMessageBox.information(self, "Response loaded (PKL)",f"Loaded SysID response from '{os.path.basename(folder)}'.")

                return


            # for dfs
            if os.path.isfile(npz_file):
                D = np.load(npz_file, allow_pickle=True)
                files = set(D.files)
                                        #is subset of
                if {"Rx_nom", "Ry_nom"} <= files:
                    Rx = np.asarray(D["Rx_nom"], float)
                    Ry = np.asarray(D["Ry_nom"], float)
                elif {"Rx", "Ry"} <= files:
                    Rx = np.asarray(D["Rx"], float)
                    Ry = np.asarray(D["Ry"], float)
                else:
                    raise KeyError(
                        f"dfs_response.npz must contain Rx_nom/Ry_nom (or Rx/Ry).Found keys: {sorted(files)}"
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
                self.traj_file=npz_file
                if hasattr(self, "trajectory_response_3"):
                    self.trajectory_response_3.setText(npz_file)
                QMessageBox.information(self, "Response loaded (NPZ)",f"Loaded DFS response from '{os.path.basename(folder)}'.")
                return

            raise FileNotFoundError("This folder doesn’t contain a trajectory response.\n Expected either 'response.pkl' (SysID) or 'dfs_response.npz' (DFS).")

        except Exception as e:
            QMessageBox.critical(self, "Load error", str(e))

    def _read_params(self):
        def getf(name, default): #gets the text value and turns it into a float
            w = getattr(self, name, None)
            if w is None:
                return float(default)

            txt=(w.text() or "").strip()
            if txt:
                try:
                    return float(txt)
                except ValueError:
                    pass
            w.setText(f"{default:g}")
            return float(default)
        def geti(name, default): #the same, but to an int
            w = getattr(self, name, None)
            if w is None:
                return int(default)

            txt=(w.text() or "").strip()
            if txt:
                try:
                    return int(float(txt))
                except ValueError:
                    pass
            w.setText(str(int(default)))
            return int(default)
        orbit_w = getf("lineEdit", 1.0)
        disp_w  = getf("lineEdit_2", 10.0)
        wake_w  = getf("lineEdit_3", 10.0)
        rcond   = getf("lineEdit_4", 0.001)
        iters   = geti("lineEdit_5", 10)
        return orbit_w, disp_w, wake_w, rcond, iters

    def _read_reset_intensity(self):
        scale=self._finding_float(self.wfs_reset_3.text(),1)
        return scale

    def _read_change_intensity(self):
        scale=self._finding_float(self.wfs_change_3.text(),0.9)
        return scale

    def _read_change_energy(self):
        scale=self._finding_float(self.dfs_change_3.text(), 0.98)
        return scale


    def _read_reset_energy(self):
        scale=self._finding_float(self.dfs_reset_3.text(), 1)
        return scale

    def _using_traj_response(self,corrs, bpms):
        if not getattr(self, "traj_response", None):
            return None, corrs, None
        tr = self.traj_response
        h_gui = [c for c in corrs if c in tr.get("hcorrs",[])]
        v_gui = [c for c in corrs if c in tr.get("vcorrs",[])]
        if not (h_gui or v_gui):
            return None, corrs,None

        Rx = reorder_matrix_to_gui(np.asarray(tr["Rxx"]), tr["bpms"],tr["hcorrs"], bpms, h_gui)
        Ry = reorder_matrix_to_gui(np.asarray(tr["Ryy"]), tr["bpms"],tr["vcorrs"], bpms, v_gui)

        nb, nh, nv = len(bpms), len(h_gui), len(v_gui)
        Rx_full = np.zeros((nb, nh + nv))
        Ry_full = np.zeros((nb, nh + nv))
        Rx_full[:, :nh] = Rx
        Ry_full[:, nh:] = Ry
        R_nom = {"delta": 0.01, "Rx": Rx_full, "Ry": Ry_full}
        #B0 = np.concatenate([np.asarray(tr["Bx"]).ravel(),np.asarray(tr["By"]).ravel()])
        file_bpms=list(map(str,tr["bpms"]))
        selected_index=[file_bpms.index(b) for b in bpms]

        Bx_selected=np.asarray(tr["Bx"], float).ravel()[selected_index]
        By_selected=np.asarray(tr["By"], float).ravel()[selected_index]
        B0=np.concatenate([Bx_selected, By_selected]).astype(float).reshape(-1,1)
        return R_nom, h_gui + v_gui, B0

    def _start_correction(self):

        R_nom, R_disp, R_wake = None, None, None

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
            print("Selected corrs: ")
            print(corrs)

            R_nom_tr, corrs,B0 = self._using_traj_response(corrs, bpms)
            if R_nom_tr is not None:
                R_nom = np.vstack([R_nom_tr["Rx"], R_nom_tr["Ry"]])
            else:
                B0=None
            if hasattr(self, "dfs_response_3"):
                dfs_path = (self.dfs_response_3.text() or "").strip()
                if dfs_path and os.path.isfile(dfs_path):
                    dfs_data=load_dfs_npz(dfs_path,bpms,corrs)
                    if isinstance(dfs_data,tuple) and len(dfs_data)==2:
                        R_nom,R_disp=dfs_data

            if hasattr(self, "wfs_response_3"):
                wfs_path = (self.wfs_response_3.text() or "").strip()
                if wfs_path and os.path.isfile(wfs_path):
                    wfs_data=load_wfs_npz(wfs_path,bpms,corrs)
                    if wfs_data is not None:
                        R_wake=wfs_data


            def on_iter(i, orbit_rms, disp_rms, wake_rms):
                if orbit_rms is not None: self._hist_orbit.append(orbit_rms)
                if disp_rms is not None: self._hist_disp.append(disp_rms)
                if wake_rms is not None: self._hist_wake.append(wake_rms)

                self._plot_series(self.traj_canvas, self.traj_fig, self._hist_orbit, "Orbit norm", "‖y_nom‖ [mm]")
                self._plot_series(self.disp_canvas, self.disp_fig, self._hist_disp, "Dispersion Free Steering", "‖y_off − y_nom‖ [mm]")
                self._plot_series(self.wake_canvas, self.wake_fig, self._hist_wake, "Wakefield Free Steering","‖y_high − y_low‖ [mm]")

                if getattr(self, "_chi_dlg", None):
                    self._chi_dlg.append_point(orbit_rms or 0.0, disp_rms or 0.0, wake_rms or 0.0)

                QApplication.processEvents() #so the GUI doesnt freeze with long operations
                return not self._cancel

            self.setWindowTitle("BBA - [Correction running]")
            self.engine.solve_and_apply(
                orbit_w=orbit_w, disp_w=disp_w, wake_w=wake_w,
                rcond=rcond, max_iters=iters,
                bpms=bpms, corrs=corrs,
                triangular=self._force_triangular(),
                R_nom=R_nom, R_disp=R_disp, R_wake=R_wake,
                iter_cb=on_iter,
                scale_change_energy=self._read_change_energy(),
                scale_reset_energy=self._read_reset_energy(),
                scale_change_intensity=self._read_change_intensity(),
                scale_reset_intensity=self._read_reset_intensity(),
                y_ref=B0,

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

        self._chi_dlg.calculating_chi(self._hist_orbit, self._hist_disp, self._hist_wake)

        self._chi_dlg.show()
        self._chi_dlg.raise_() #top of the stacking order
        self._chi_dlg.activateWindow() #giving it a keyboard focus


if __name__ == "__main__":
    app = QApplication([])

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
