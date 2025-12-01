import sys, os, pickle, re, matplotlib, glob, time,json
from datetime import datetime
import numpy as np
from PyQt6 import uic
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QApplication, QSizePolicy, QMainWindow, QFileDialog, QListWidget, QMessageBox,
                             QProgressDialog, QVBoxLayout, QPushButton, QDialog, QLabel)
from State import State
matplotlib.use("QtAgg")
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from ChiSquaredPopup_BBA import ChiSquaredWindow
from SaveOrLoad_BBA import SaveOrLoad_BBA
from DFS_WFS_Correction_BBA import DFS_WFS_Correction_BBA

class MainWindow(QMainWindow, SaveOrLoad_BBA, DFS_WFS_Correction_BBA):
    def __init__(self, interface, dir_name):
        super().__init__()
        self.cwd = os.getcwd()
        self.interface = interface
        self.dir_name = dir_name
        self._cancel = False
        self._number_re = re.compile(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?")
        self.S = State(interface=interface)
        ui_path = os.path.join(os.path.dirname(__file__), "BBA_GUI.ui")
        uic.loadUi(ui_path, self)
        self._data_dirs = {"traj": None, "dfs": None, "wfs": None}
        self._hist_orbit = []
        self._hist_disp = []
        self._hist_wake = []
        self._chi_dlg = None
        self._setup_canvases()
        self._populate_lists()
        self.save_correctors_button.clicked.connect(self._save_correctors)
        self.load_correctors_button.clicked.connect(self._load_correctors)
        self.clear_correctors_button.clicked.connect(self.correctors_list.clearSelection)
        self.save_bpms_button.clicked.connect(self._save_bpms)
        self.load_bpms_button.clicked.connect(self._load_bpms)
        self.clear_bpms_button.clicked.connect(self.bpms_list.clearSelection)

        if hasattr(self, "pushButton_8"):  # traj
            self.pushButton_8.clicked.connect(self._pick_and_load_traj_data)
        if hasattr(self, "pushButton_9"):  # dfs
            self.pushButton_9.clicked.connect(self._pick_and_load_disp_data)
        if hasattr(self, "pushButton_10"):  # wfs
            self.pushButton_10.clicked.connect(self._pick_and_load_wake_data)
        if hasattr(self, "popup_button"):
            self.popup_button.clicked.connect(self._show_chi_squared_graphs)
        if hasattr(self, "clear_graphs_button"):
            self.clear_graphs_button.clicked.connect(self._clear_graphs)
        if hasattr(self, "pushButton_11"):
            self.pushButton_11.clicked.connect(self.load_session_settings)

        self._running = False
        self.start_button.clicked.connect(self._on_start_click)
        self.stop_button.clicked.connect(self._stop_correction)
        self.corrs = self.S.get_correctors()["names"]
        self.setWindowTitle("BBA_GUI")
        self.lineEdit.setText("1")
        self.lineEdit_2.setText("10")
        self.lineEdit_3.setText("10")
        self.lineEdit_4.setText("0.001")
        self.lineEdit_5.setText("10")
        self.lineEdit_6.setText("0.4")
        self.dfs_reset_3.setText("grad = 1")
        self.dfs_change_3.setText("grad = 0.98")
        self.wfs_reset_3.setText("grad = 1")
        self.wfs_change_3.setText("grad = 0.90")

        correctors = self.interface.get_correctors()
        correctors_list = correctors['names']
        max_curr_h=0.0
        max_curr_v=0.0
        if correctors_list is not None:
            hcorrs = self.interface.get_hcorrectors_names()
            vcorrs = self.interface.get_vcorrectors_names()
            hcorr_indexes = np.array([index for index, string in enumerate(correctors_list) if string in hcorrs])
            vcorr_indexes = np.array([index for index, string in enumerate(correctors_list) if string in vcorrs])

            def clean_array(a):
                a = np.array([0 if x is None else x for x in a], dtype=float)
                a[np.isnan(a)] = 0
                return a

            max_curr_h = 1.15 * np.max(np.abs(clean_array(np.array(correctors['bdes'])[hcorr_indexes])))
            max_curr_v = 1.15 * np.max(np.abs(clean_array(np.array(correctors['bdes'])[vcorr_indexes])))

        self.max_horizontal_current_spinbox.setValue(max_curr_h)
        self.max_horizontal_current_spinbox.setSingleStep(0.01)
        self.max_vertical_current_spinbox.setValue(max_curr_v)
        self.max_vertical_current_spinbox.setSingleStep(0.01)

    def _on_start_click(self):
        if not self._running:
            self._running = True
            self._step = True
            try:
                self._start_correction()
            finally:
                self._running = False
        else:
            self._step = True

    def _read_all_parameters(self,text,grad=None):
        text = text.strip()
        params = {}
        for p in text.split(","):
            p = p.strip()
            if not p:
                continue
            k,v = p.split("=",1)
            k = k.strip()
            v = v.strip()
            try:
                params[k] = float(v)
            except ValueError:
                raise ValueError(f"Not a number encountered in {p}")
        return params

    def _expand_data_path(self,path):
        home=os.path.expanduser("~")
        #/Users/wiktoriamalek/Desktop/flight-simulator/Data/ATF2_Ext_RFT_20251023_111743_nominal
        if path.startswith(home+os.sep): #the character used by the operating system to separate pathname components
            return "~"+path[len(home):]
        return path

    def _setup_canvases(self):
        if FigureCanvas is None:
            self.traj_canvas = self.disp_canvas = self.wake_canvas = None
            return

        def install(host):
            fig = Figure(figsize=(5, 2.4), tight_layout=True)
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
        if title is not None:
            ax.set_title(title)
        else:
            ax.set_title(None)
        ax.set_title(title)
        ax.set_xlabel("Iteration", fontsize=8)
        ax.set_ylabel(ylabel="[mm]", fontsize=7)
        ax.tick_params(axis="both", which="major", labelsize=7)
        ax.yaxis.get_offset_text().set_fontsize(7)
        ax.grid(True, alpha=0.3)
        canvas.draw_idle()

    def _populate_lists(self):
        corrs = self.S.get_correctors()["names"]
        bpms = self.S.get_bpms()["names"]
        self.correctors_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.bpms_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.correctors_list.insertItems(0, corrs)
        self.bpms_list.insertItems(0, bpms)  # at the top of the list

    def _get_selection(self):
        corrs_all = self.S.get_correctors()["names"]
        bpms_all = self.S.get_bpms()["names"]
        corrs = [it.text() for it in self.correctors_list.selectedItems()] or corrs_all
        bpms = [it.text() for it in self.bpms_list.selectedItems()] or bpms_all
        return corrs, bpms

    def _force_triangular(self) -> bool:
        try:
            return bool(self.checkBox.isChecked())
        except Exception:
            return False

    def _with_progress(self, total, title):
        prog = QProgressDialog(title, "Cancel", 0, total, self)
        prog.setWindowModality(Qt.WindowModality.ApplicationModal)  # user cant interact with the main window
        prog.setMinimumDuration(0)

        def cb(i, n, text):
            prog.setMaximum(n)
            prog.setValue(i)
            prog.setLabelText(text)
            QApplication.processEvents()
            return not prog.wasCanceled()

        return prog, cb

    def _read_params(self):
        def getf(name, default):  # gets the text value and turns it into a float
            w = getattr(self, name, None)
            if w is None:
                return float(default)

            txt = (w.text() or "").strip()
            if txt:
                try:
                    return float(txt)
                except ValueError:
                    pass
            w.setText(f"{default:g}")
            return float(default)

        def geti(name, default):  # the same, but to an int
            w = getattr(self, name, None)
            if w is None:
                return int(default)

            txt = (w.text() or "").strip()
            if txt:
                try:
                    return int(float(txt))
                except ValueError:
                    pass
            w.setText(str(int(default)))
            return int(default)

        orbit_w = getf("lineEdit", 1.0)
        disp_w = getf("lineEdit_2", 10.0)
        wake_w = getf("lineEdit_3", 10.0)
        rcond = getf("lineEdit_4", 0.001)
        iters = geti("lineEdit_5", 10)
        gain = getf("lineEdit_6", 0.4)
        return orbit_w, disp_w, wake_w, rcond, iters, gain

    def _read_reset_intensity(self):
        text = self.wfs_reset_3.text()
        return self._read_all_parameters(text,grad=1)

    def _read_change_intensity(self):
        text = self.wfs_change_3.text()
        return self._read_all_parameters(text,grad=0.90)

    def _read_change_energy(self):
        text = self.dfs_change_3.text()
        return self._read_all_parameters(text,grad=0.98)

    def _read_reset_energy(self):
        text = self.dfs_reset_3.text()
        return self._read_all_parameters(text,grad=1)

    def _start_correction(self):
        try:
            self._cancel = False
            w1, w2, w3, rcond, iters, gain = self._read_params()
            wgt_orb, wgt_dfs, wgt_wfs = w1, w2, w3

            self._hist_orbit.clear()
            self._hist_disp.clear()
            self._hist_wake.clear()

            if getattr(self, "_chi_dlg", None):
                self._chi_dlg.set_weights(w1, w2, w3)
                self._chi_dlg.clear()

            corrs, bpms = self._get_selection()

            Cx = [s for s in corrs if (s.lower().startswith('zh') or ("DHG" in s) or (s.lower().startswith('zx')))]
            Cy = [s for s in corrs if (s.lower().startswith('zv') or (("SDV" in s) or ("DHJ" in s)))]

            Axx, Ayy, B0x, B0y = self._creating_response_matrices()

            self.setWindowTitle("BBA_GUI - [Correction running]")

            # DR_freq = 714e3; # 714 MHz in kHz
            # DR_momentum_compaction = 2.1e-3

            # dP_P = -deltafreq / DR_freq / DR_momentum_compaction
            grad = self._read_change_energy().get("grad")
            dP_P = grad - 1

            target_disp_x, target_disp_y = self._get_dispersion_from_twiss_file()
            max_curr_h = self.max_horizontal_current_spinbox.value() # gauss * m
            max_curr_v = self.max_vertical_current_spinbox.value() # gauss * m
            def clamp(val, max_val):
                if max_val == 0.0:
                    return val
                return max(-max_val, min(val, max_val))

            for it in range(iters):
                if self._cancel:
                    break
                self._step = False

                # nominal
                self.S.pull(self.interface)
                O0 = self.S.get_orbit(bpms)
                O0x = O0['x'].reshape(-1, 1)  # turns an array into a column vector
                O0y = O0['y'].reshape(-1, 1)

                # dfs
                dfs_params_change = self._read_change_energy()
                dfs_params_reset = self._read_reset_energy()
                self.interface.change_energy(**dfs_params_change)
                self.S.pull(self.interface)
                self.interface.reset_energy(**dfs_params_reset)
                O1 = self.S.get_orbit(bpms)
                O1x = O1['x'].reshape(-1, 1)
                O1y = O1['y'].reshape(-1, 1)

                # wfs
                wfs_params_change = self._read_change_intensity()
                wfs_params_reset = self._read_reset_intensity()
                self.interface.change_intensity(**wfs_params_change)
                self.S.pull(self.interface)
                self.interface.reset_intensity(**wfs_params_reset)
                O2 = self.S.get_orbit(bpms)
                O2x = O2['x'].reshape(-1, 1)
                O2y = O2['y'].reshape(-1, 1)

                Bx = np.vstack((
                    wgt_orb * (O0x - B0x),
                    wgt_dfs * ((O1x - O0x) - dP_P * target_disp_x * 1e3),
                    wgt_wfs * (O2x - O0x),
                ))
                By = np.vstack((
                    wgt_orb * (O0y - B0y),
                    wgt_dfs * ((O1y - O0y) - dP_P * target_disp_y * 1e3),
                    wgt_wfs * (O2y - O0y),
                ))

                # A = U * Sigma * V^T
                # A^+ = V * Sigma^+ * U^T

                corrX = -gain * (np.linalg.pinv(Axx, rcond=rcond) @ Bx)  # theta = - gain * Axx^+ *Bx
                corrY = -gain * (np.linalg.pinv(Ayy, rcond=rcond) @ By)

                vals_x = [clamp(v,max_curr_h) for v in corrX.ravel()]
                vals_y = [clamp(v,max_curr_v) for v in corrY.ravel()] # flattens an array
                vals = np.array(vals_x + vals_y)
                self.interface.vary_correctors(Cx + Cy, vals)

                self._hist_orbit.append(float(np.linalg.norm(O0x - B0x) + np.linalg.norm(O0y - B0y)))
                self._hist_disp.append(float(np.linalg.norm((O1x - O0x) - dP_P * target_disp_x) + np.linalg.norm(
                    (O1y - O0y) - dP_P * target_disp_y)))
                self._hist_wake.append(float(np.linalg.norm(O2x - O0x) + np.linalg.norm(O2y - O0y)))

                self._plot_series(self.traj_canvas, self.traj_fig, self._hist_orbit, None, None)
                self._plot_series(self.disp_canvas, self.disp_fig, self._hist_disp, None, None)
                self._plot_series(self.wake_canvas, self.wake_fig, self._hist_wake, None, None)
                QApplication.processEvents()

            self.setWindowTitle("BBA_GUI")
            QMessageBox.information(self, "Correction", "Correction finished.")
            self.save_session_settings(w1, w2, w3, rcond, iters, gain, Axx, Ayy, Bx, By)

        except Exception as e:
            self.setWindowTitle("BBA_GUI")
            QMessageBox.critical(self, "Correction error", str(e))

    def _stop_correction(self):
        self._cancel = True
        QMessageBox.information(self, "Correction", "Stop requested. Finishing current iteration...")

    def _show_chi_squared_graphs(self):
        if getattr(self, "_chi_dlg", None) is None:
            self._chi_dlg = ChiSquaredWindow(self)

        w1, w2, w3, *_ = self._read_params()
        self._chi_dlg.set_weights(w1, w2, w3)
        self._chi_dlg.info.setText = f"w1={w1:g}, w2={w2:g}, w3={w3:g}"
        self._chi_dlg.calculating_chi(self._hist_orbit, self._hist_disp, self._hist_wake)

        self._chi_dlg.show()
        self._chi_dlg.raise_()  # top of the stacking order
        self._chi_dlg.activateWindow()  # giving it a keyboard focus

    def _clear_graphs(self):
        # it doesnt do fresh - start, it only clears the graphs
        self._cancel = True
        self._hist_orbit.clear()
        self._hist_disp.clear()
        self._hist_wake.clear()
        self._plot_series(self.traj_canvas, self.traj_fig, [], None, "[mm]")
        self._plot_series(self.disp_canvas, self.disp_fig, [], None, "[mm]")
        self._plot_series(self.wake_canvas, self.wake_fig, [], None, "[mm]")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    #from SelectInterface import InterfaceSelectionDialog
    import SelectInterface
    dialog = SelectInterface.choose_acc_and_interface()
    if dialog is None:
        print("Selection cancelled.")
        sys.exit(1)

    I=dialog
    project_name=I.get_name()
    print(f"Selected interface: {project_name}")
    time_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = f"Data/{project_name}_{time_str}"
    w = MainWindow(I, out_dir)
    w.show()
    sys.exit(app.exec())