import json
import sys, os, pickle, re, matplotlib, glob, time
from datetime import datetime
import numpy as np
from PyQt6 import uic
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QApplication, QSizePolicy, QMainWindow, QFileDialog, QListWidget, QMessageBox,QProgressDialog, QVBoxLayout, QPushButton, QDialog, QLabel)
from State import State
matplotlib.use("QtAgg")
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from Response import Response
from ChiSquaredPopup_BBA import ChiSquaredWindow

class MainWindow(QMainWindow):
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
        self.setWindowTitle("BBA")
        self.lineEdit.setText("1")
        self.lineEdit_2.setText("10")
        self.lineEdit_3.setText("10")
        self.lineEdit_4.setText("0.001")
        self.lineEdit_5.setText("10")
        self.lineEdit_6.setText("0.4")
        self.dfs_reset_3.setText("1")
        self.dfs_change_3.setText("0.98")
        self.wfs_reset_3.setText("1")
        self.wfs_change_3.setText("0.90")

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

    def _finding_float(self, text, default):
        m = self._number_re.search(text)
        return float(m.group(0)) if m else default

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
        ax.set_ylabel(ylabel, fontsize=7)
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

    def _saving_func(self, elements_list, filename, saving_name, *, use_dialog=True,
                     base_dir=None):  # * - must be passed by keyword
        items = elements_list.selectedItems()
        if not items:
            items = [elements_list.item(i) for i in range(elements_list.count())]
        base = base_dir or self.dir_name
        os.makedirs(base, exist_ok=True)
        if use_dialog:
            fn, _ = QFileDialog.getSaveFileName(self, f"{saving_name}", os.path.join(self.dir_name, f"{filename}"),"Text (*.txt)")
            if not fn:
                return
        else:
            fn = os.path.join(base, filename)
        with open(fn, "w") as f:
            for it in items:
                f.write(f"{it.text()}\n")

    def _loading_func(self, elements_list, filename, loading_name, *, use_dialog=True, base_dir=None):
        base = base_dir or self.dir_name
        if use_dialog:
            fn, _ = QFileDialog.getOpenFileName(self, f"{loading_name}", os.path.join(base, f"{filename}"),"Text (*.txt)")
        else:
            fn = os.path.join(base, filename)
        selected = None
        if fn and os.path.isfile(fn):
            with open(fn, "r") as f:
                selected = [ln.strip() for ln in f]
        if selected is None:
            selected = (
                self.S.get_bpms()["names"] if elements_list is self.bpms_list else self.S.get_correctors()["names"])

        elements_list.clearSelection()
        for name in selected:
            for it in elements_list.findItems(name, Qt.MatchFlag.MatchExactly):
                it.setSelected(True)

    def _save_correctors(self):
        self._saving_func(elements_list=self.correctors_list, filename="correctors.txt", saving_name="Save Correctors")

    def _save_bpms(self):
        self._saving_func(elements_list=self.bpms_list, filename="bpms.txt", saving_name="Save BPMs")

    def _load_correctors(self):
        self._loading_func(loading_name="Load Correctors", filename="correctors.txt",
                           elements_list=self.correctors_list)

    def _load_bpms(self):
        self._loading_func(loading_name="Load BPMs", filename="bpms.txt", elements_list=self.bpms_list)

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

    def _pick_and_load_data_dir(self, button_ui, button_name, oper):
        default_dir = os.path.join(self.cwd, "Data")
        os.makedirs(default_dir, exist_ok=True)
        folder = QFileDialog.getExistingDirectory(self, "Select data directory", default_dir)
        if not folder:
            return
        info = self._find_useful_files(folder)
        if not info["ok"]:
            QMessageBox.warning(self, "Load data", "Wrong data directory selected")
        self._data_dirs[oper] = info
        button_ui.setText(folder)
        QMessageBox.information(button_ui, "Data directory selected", button_name)

    def _pick_and_load_disp_data(self):
        self._pick_and_load_data_dir(oper="dfs", button_ui=self.dfs_response_3, button_name="DFS Data Loaded")

    def _pick_and_load_wake_data(self):
        self._pick_and_load_data_dir(oper="wfs", button_ui=self.wfs_response_3, button_name="WFS Data Loaded")

    def _pick_and_load_traj_data(self):
        self._pick_and_load_data_dir(oper="traj", button_ui=self.trajectory_response_3,button_name="Trajectory Data Loaded")

    def _find_useful_files(self, directory):
        p_files = glob.glob(os.path.join(directory, "DATA_*_p*.pkl"))
        m_files = glob.glob(os.path.join(directory, "DATA_*_m*.pkl"))

        regex = re.compile(r"DATA_(.+)_(p|m)(\d+)\.pkl$")  # 3 groups - name corr, plus or minus, iteration
        p_index = {}
        m_index = {}

        for p in p_files:
            r = regex.search(os.path.basename(p))
            if r:
                corr, pm, iter = r.group(1), r.group(2), r.group(3)
                p_index[(corr, iter)] = p

        for m in m_files:
            r = regex.search(os.path.basename(m))
            if r:
                corr, pm, iter = r.group(1), r.group(2), r.group(3)
                m_index[(corr, iter)] = m

        valid_pairs = {}

        for (corr, iter), fp in p_index.items():
            fm = m_index.get((corr, iter))
            if fm:
                valid_pairs.setdefault(corr, []).append((fp, fm))  # dict for each corrector

        return {
            "ok": bool(valid_pairs),
            "dir": directory,
            "pairs": valid_pairs,
            "p_files": p_files,
            "m_files": m_files,
        }

    def _heaviside_function_for_checkbox(self, bpms, correctors):
        bpms_position = self.interface.get_elements_position(bpms)
        corrs_position = self.interface.get_elements_position(correctors)

        M = np.zeros((len(bpms), len(correctors)), dtype=bool)

        for j, cj in enumerate(corrs_position):
            for i, bi in enumerate(bpms_position):
                M[i, j] = (bi >= cj)

        return M

    def _get_data_from_loaded_directories(self, selected_bpms, selected_corrs, _force_triangular=False):

        info_traj = self._data_dirs["traj"]
        info_dfs = self._data_dirs["dfs"]
        info_wfs = self._data_dirs["wfs"]

        if not (info_traj and info_traj["ok"] and info_dfs and info_dfs["ok"] and info_wfs and info_wfs["ok"]):
            raise RuntimeError("Please select all data directories")

        hcorrs = [string for string in selected_corrs if (string.lower().startswith('zh') or ("DHG" in string) or (string.lower().startswith('zx')))]
        vcorrs = [string for string in selected_corrs if
                  (string.lower().startswith('zv') or (("SDV" in string) or ("DHJ" in string)))]

        pairs0 = info_traj["pairs"]
        pairs1 = info_dfs["pairs"]
        pairs2 = info_wfs["pairs"]

        R0xx = np.full((len(selected_bpms), len(hcorrs)), np.nan, dtype=float)
        R0yy = np.full((len(selected_bpms), len(vcorrs)), np.nan, dtype=float)
        R0xy = np.zeros((len(selected_bpms), len(vcorrs)))
        R0yx = np.zeros((len(selected_bpms), len(hcorrs)))

        R1xx = np.full((len(selected_bpms), len(hcorrs)), np.nan, dtype=float)
        R1yy = np.full((len(selected_bpms), len(vcorrs)), np.nan, dtype=float)
        R1xy = np.zeros((len(selected_bpms), len(vcorrs)))
        R1yx = np.zeros((len(selected_bpms), len(hcorrs)))

        R2xx = np.full((len(selected_bpms), len(hcorrs)), np.nan, dtype=float)
        R2yy = np.full((len(selected_bpms), len(vcorrs)), np.nan, dtype=float)
        R2xy = np.zeros((len(selected_bpms), len(vcorrs)))
        R2yx = np.zeros((len(selected_bpms), len(hcorrs)))
        rows_B0x, rows_B0y = [], []

        pos = {b: i for i, b in enumerate(selected_bpms)}
        nb = len(selected_bpms)

        def _calculating_Rxx_or_Ryy(which_matrix, corrs_type, plane, pairs):

            for j, corr in enumerate(corrs_type):  # j is a column
                if corr not in pairs:
                    continue
                cols = []  # one column per plus/minus iteration
                for fp, fm in pairs[corr]:
                    with open(fp, "rb") as f:
                        plus_file = pickle.load(f)
                    with open(fm, "rb") as f:
                        minus_file = pickle.load(f)

                    bxp = np.asarray(plus_file["bpms"]["x"]).squeeze()  # turns into a vector (N,) instead of (N,1)
                    byp = np.asarray(plus_file["bpms"]["y"]).squeeze()
                    bxm = np.asarray(minus_file["bpms"]["x"]).squeeze()
                    bym = np.asarray(minus_file["bpms"]["y"]).squeeze()

                    bact_p = np.asarray(plus_file["correctors"]["bact"]).squeeze()
                    bact_m = np.asarray(minus_file["correctors"]["bact"]).squeeze()

                    bpms_names = list(map(str, plus_file["bpms"]["names"]))
                    present = [b for b in selected_bpms if b in bpms_names]

                    if not present:
                        continue
                    indeces = [bpms_names.index(b) for b in present]
                    corrs_names = list(map(str, plus_file["correctors"]["names"]))

                    if corr not in corrs_names:
                        continue
                    i_corr = corrs_names.index(corr)
                    if plane == "x":
                        plus_value = bxp[indeces]
                        minus_value = bxm[indeces]
                    elif plane == "y":
                        plus_value = byp[indeces]
                        minus_value = bym[indeces]

                    k_plus = float(bact_p[i_corr])
                    k_minus = float(bact_m[i_corr])
                    if pairs == pairs0 and plane == "x":
                        px = bxp[indeces]
                        mx = bxm[indeces]
                        B0_x = (px + mx) / 2
                        rowx = np.full(nb, np.nan)
                        for k, b in enumerate(present):
                            rowx[pos[b]] = B0_x[k]
                        rows_B0x.append(rowx)

                        py = byp[indeces]
                        my = bym[indeces]
                        B0_y = (py + my) / 2
                        rowy = np.full(nb, np.nan)
                        for k, b in enumerate(present):
                            rowy[pos[b]] = B0_y[k]
                        rows_B0y.append(rowy)

                    if k_plus - k_minus == 0:
                        continue
                    column_value = np.full(len(selected_bpms), np.nan, dtype=float)
                    for k, b in enumerate(present):
                        column_value[pos[b]] = (plus_value[k] - minus_value[k]) / (k_plus - k_minus)
                    cols.append(column_value)

                if cols:
                    which_matrix[:, j] = np.nanmean(np.vstack(cols), axis=0)
            return which_matrix

        R0xx = _calculating_Rxx_or_Ryy(which_matrix=R0xx, corrs_type=hcorrs, plane="x", pairs=pairs0)
        R0yy = _calculating_Rxx_or_Ryy(which_matrix=R0yy, corrs_type=vcorrs, plane="y", pairs=pairs0)

        B0x = np.nanmean(np.vstack(rows_B0x), axis=0).reshape(-1, 1)
        B0y = np.nanmean(np.vstack(rows_B0y), axis=0).reshape(-1, 1)

        R1xx = _calculating_Rxx_or_Ryy(which_matrix=R1xx, corrs_type=hcorrs, plane="x", pairs=pairs1)
        R1yy = _calculating_Rxx_or_Ryy(which_matrix=R1yy, corrs_type=vcorrs, plane="y", pairs=pairs1)

        R2xx = _calculating_Rxx_or_Ryy(which_matrix=R2xx, corrs_type=hcorrs, plane="x", pairs=pairs2)
        R2yy = _calculating_Rxx_or_Ryy(which_matrix=R2yy, corrs_type=vcorrs, plane="y", pairs=pairs2)

        if self._force_triangular() or _force_triangular:
            corrs, bpms = selected_corrs, selected_bpms
            Cx = [s for s in corrs if (s.lower().startswith('zh') or ("DHG" in s) or (s.lower.startswith('zx'))       )]
            Cy = [s for s in corrs if (s.lower().startswith('zv') or (("SDV" in s) or ("DHJ" in s)))]

            Mx = self._heaviside_function_for_checkbox(correctors=Cx, bpms=bpms)
            My = self._heaviside_function_for_checkbox(correctors=Cy, bpms=bpms)

            R0xx = np.where(Mx, R0xx, 0.0)  # builds new array, R0xx shape, if Mx is true otherwise 0.0
            R1xx = np.where(Mx, R1xx, 0.0)
            R2xx = np.where(Mx, R2xx, 0.0)

            R0yy = np.where(My, R0yy, 0.0)
            R1yy = np.where(My, R1yy, 0.0)
            R2yy = np.where(My, R2yy, 0.0)

        return R0xx, R0yy, R0xy, R0yx, R1xx, R1yy, R1xy, R1yx, R2xx, R2yy, R2xy, R2yx, B0x, B0y

    def _creating_response_matrices(self):

        w1, w2, w3, rcond, iters, gain = self._read_params()
        wgt_orb, wgt_dfs, wgt_wfs = w1, w2, w3

        corrs, bpms = self._get_selection()
        R0xx, R0yy, R0xy, R0yx, R1xx, R1yy, R1xy, R1yx, R2xx, R2yy, R2xy, R2yx, B0x, B0y = self._get_data_from_loaded_directories(
            selected_corrs=corrs, selected_bpms=bpms, _force_triangular=self._force_triangular())

        R0 = np.block([
            [R0xx, R0xy],
            [R0yx, R0yy],
        ])

        R1 = np.block([
            [R1xx, R1xy],
            [R1yx, R1yy],
        ])

        R2 = np.block([
            [R2xx, R2xy],
            [R2yx, R2yy],
        ])

        R_nom = R0
        R_disp = R1 - R0
        R_wake = R2 - R0

        Axx = np.vstack((
            wgt_orb * R0xx,
            wgt_dfs * (R1xx - R0xx),
            wgt_wfs * (R2xx - R0xx),
        ))

        Ayy = np.vstack((
            wgt_orb * R0yy,
            wgt_dfs * (R1yy - R0yy),
            wgt_wfs * (R2yy - R0yy),
        ))

        return Axx, Ayy, B0x, B0y

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
        scale = self._finding_float(self.wfs_reset_3.text(), 1)
        return scale

    def _read_change_intensity(self):
        scale = self._finding_float(self.wfs_change_3.text(), 0.9)
        return scale

    def _read_change_energy(self):
        scale = self._finding_float(self.dfs_change_3.text(), 0.98)
        return scale

    def _read_reset_energy(self):
        scale = self._finding_float(self.dfs_reset_3.text(), 1)
        return scale

    def _get_dispersion_from_twiss_file(self):
        # madx
        corrs, bpms = self._get_selection()
        with open('Ext_ATF2/ATF2_EXT_FF_v5.2.twiss', "r") as file:
            # lines=file.readlines()
            lines = [line.strip() for line in file if line.strip()]

        star_symbol = next(i for i, line in enumerate(lines) if line.startswith("*"))
        dollar_sign = next(i for i, line in enumerate(lines) if line.startswith("$") and i > star_symbol)
        columns = lines[star_symbol].lstrip("*").split()

        DX_column = columns.index("DX")
        DY_column = columns.index("DY")
        elements_names = columns.index("NAME")

        bpms_dx, bpms_dy = {}, {}
        for line in lines[dollar_sign + 1:]:
            data = line.split()
            bpms_name = data[elements_names].strip('"')

            bpms_dx[bpms_name] = float(data[DX_column])
            bpms_dy[bpms_name] = float(data[DY_column])

        target_disp_x = np.array([bpms_dx.get(bpm, 0.0) for bpm in bpms]).reshape(-1, 1)
        target_disp_y = np.array([bpms_dy.get(bpm, 0.0) for bpm in bpms]).reshape(-1, 1)

        # what about the units??
        return target_disp_x, target_disp_y

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

            self.setWindowTitle("BBA - [Correction running]")

            # DR_freq = 714e3; # 714 MHz in kHz
            # DR_momentum_compaction = 2.1e-3

            # dP_P = -deltafreq / DR_freq / DR_momentum_compaction

            dP_P = self._read_change_energy() - 1

            target_disp_x, target_disp_y = self._get_dispersion_from_twiss_file()

            for it in range(iters):
                if self._cancel:
                    break
                self._step = False

                # nominal
                self.S.pull(self.interface)
                O0 = self.S.get_orbit(bpms)
                O0x = O0['x'].reshape(-1, 1)
                O0y = O0['y'].reshape(-1, 1)

                # dfs
                self.interface.change_energy(scale=self._read_change_energy())
                self.S.pull(self.interface)
                self.interface.reset_energy(scale=self._read_reset_energy())
                O1 = self.S.get_orbit(bpms)
                O1x = O1['x'].reshape(-1, 1)
                O1y = O1['y'].reshape(-1, 1)

                # wfs
                self.interface.change_intensity(scale=self._read_change_intensity())
                self.S.pull(self.interface)
                self.interface.reset_intensity(scale=self._read_reset_intensity())
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
                    wgt_dfs * ((O1y - O0y) - dP_P * target_disp_y  * 1e3),
                    wgt_wfs * (O2y - O0y),
                ))

                corrX = -gain * (np.linalg.pinv(Axx, rcond=rcond) @ Bx)
                corrY = -gain * (np.linalg.pinv(Ayy, rcond=rcond) @ By)

                vals = np.concatenate([corrX.ravel(), corrY.ravel()])  # flattens an array
                self.interface.vary_correctors(Cx + Cy, vals)

                self._hist_orbit.append(float(np.linalg.norm(O0x - B0x) + np.linalg.norm(O0y - B0y)))
                self._hist_disp.append(float(np.linalg.norm((O1x - O0x) - dP_P * target_disp_x) + np.linalg.norm(
                    (O1y - O0y) - dP_P * target_disp_y)))
                self._hist_wake.append(float(np.linalg.norm(O2x - O0x) + np.linalg.norm(O2y - O0y)))

                self._plot_series(self.traj_canvas, self.traj_fig, self._hist_orbit, None, None)
                self._plot_series(self.disp_canvas, self.disp_fig, self._hist_disp, None, None)
                self._plot_series(self.wake_canvas, self.wake_fig, self._hist_wake, None, None)
                QApplication.processEvents()

            self.setWindowTitle("BBA")
            QMessageBox.information(self, "Correction", "Correction finished.")
            self.save_session_settings(w1, w2, w3, rcond, iters, gain, Axx, Ayy, Bx, By)

        except Exception as e:
            self.setWindowTitle("BBA")
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
        self._cancel = True

        self._hist_orbit.clear()
        self._hist_disp.clear()
        self._hist_wake.clear()

        self._plot_series(self.traj_canvas, self.traj_fig, [], None, "[mm]")
        self._plot_series(self.disp_canvas, self.disp_fig, [], None, "[mm]")
        self._plot_series(self.wake_canvas, self.wake_fig, [], None, "[mm]")

    def save_session_settings(self, w1, w2, w3, rcond, iters, gain, Axx, Ayy, Bx, By):

        save_session_dir = os.path.join("Data", f"BBA_{self.interface.get_name()}_{time_str}_session_settings")
        os.makedirs(save_session_dir, exist_ok=True)

        self._saving_func(elements_list=self.correctors_list, filename="correctors.txt", saving_name="Save Correctors",
                          use_dialog=False, base_dir=save_session_dir)
        self._saving_func(elements_list=self.bpms_list, filename="bpms.txt", saving_name="Save BPMs", use_dialog=False,
                          base_dir=save_session_dir)

        correction_settings = {
            "w1": w1,
            "w2": w2,
            "w3": w3,
            "rcond": rcond,
            "iters": iters,
            "gain": gain,
            "dfs_reset": self._read_reset_energy(),
            "dfs_change": self._read_change_energy(),
            "wfs_reset": self._read_reset_intensity(),
            "wfs_change": self._read_change_intensity(),
            "data_dirs": {k: (v["dir"] if v else None) for k, v in self._data_dirs.items()},

        }

        with open(os.path.join(save_session_dir, "correction_settings.json"), "w") as f:
            json.dump(correction_settings, f, indent=2)

        def __save_graph_data(path, series):
            with open(path, "w") as f:
                f.write("Iteration\tvalue\n")
                for i, v in enumerate(series, start=1):
                    f.write(f"{i}\t{v}\n")

        __save_graph_data(os.path.join(save_session_dir, "trajectory_after_correction.txt"), self._hist_orbit)
        __save_graph_data(os.path.join(save_session_dir, "dispersion_after_correction.txt"), self._hist_disp)
        __save_graph_data(os.path.join(save_session_dir, "wakefield_after_correction.txt"), self._hist_wake)

        corrs, bpms = self._get_selection()
        R0xx, R0yy, R0xy, R0yx, R1xx, R1yy, R1xy, R1yx, R2xx, R2yy, R2xy, R2yx, B0x, B0y = self._get_data_from_loaded_directories(
            selected_corrs=corrs, selected_bpms=bpms)

        correction_matrices = {
            "Axx": Axx, "Ayy": Ayy, "B0x": B0x, "B0y": B0y,
            "R0xx": R0xx, "R1xx": R1xx, "R2xx": R2xx,
            "R0yy": R0yy, "R1yy": R1yy, "R2yy": R2yy,
            "Bx": Bx, "By": By,
        }
        with open(os.path.join(save_session_dir, "correction_matrices.pkl"), "wb") as f:
            pickle.dump(correction_matrices, f)

    def load_session_settings(self):
        default_dir = os.path.join(self.cwd, "Data")
        os.makedirs(default_dir, exist_ok=True)
        folder = QFileDialog.getExistingDirectory(self, "Select database", default_dir)
        if not folder:
            return
        if hasattr(self, "session_database_3"):
            self.session_database_3.setText(folder)
        QMessageBox.information(self.session_database_3, "Data directory selected", "Loaded session")

        # load correctors
        self._loading_func(elements_list=self.correctors_list, filename="correctors.txt",
                           loading_name="Load Correctors", use_dialog=False, base_dir=folder)
        # load bpms
        self._loading_func(elements_list=self.bpms_list, filename="bpms.txt", loading_name="Load BPMs",
                           use_dialog=False, base_dir=folder)

        correction_settings_path = os.path.join(folder, "correction_settings.json")
        try:
            with open(correction_settings_path, "r") as f:
                settings = json.load(f)
                paths = settings.get("data_dirs") or {}
                for key, path in paths.items():
                    if not path:
                        continue
                    info = self._find_useful_files(path)
                    if info["ok"]:
                        self._data_dirs[key] = info
                    else:
                        QMessageBox.warning(self, "Load session", "Data directory not found")

        except Exception as e:
            QMessageBox.warning(self, "Load session", str(e))
            settings = {}

        if "w1" in settings: self.lineEdit.setText(str(settings["w1"]))
        if "w2" in settings: self.lineEdit_2.setText(str(settings["w2"]))
        if "w3" in settings: self.lineEdit_3.setText(str(settings["w3"]))
        if "rcond" in settings: self.lineEdit_4.setText(str(settings["rcond"]))
        if "iters" in settings:  self.lineEdit_5.setText(str(settings["iters"]))
        if "gain" in settings: self.lineEdit_6.setText(str(settings["gain"]))
        if "dfs_reset" in settings: self.dfs_reset_3.setText(str(settings["dfs_reset"]))
        if "dfs_change" in settings: self.dfs_change_3.setText(str(settings["dfs_change"]))
        if "wfs_reset" in settings:  self.wfs_reset_3.setText(str(settings["wfs_reset"]))
        if "wfs_change" in settings: self.wfs_change_3.setText(str(settings["wfs_change"]))
        if hasattr(self, "trajectory_response_3"): self.trajectory_response_3.setText(
            settings["data_dirs"]["traj"] or "")
        if hasattr(self, "dfs_response_3"): self.dfs_response_3.setText(settings["data_dirs"]["dfs"] or "")
        if hasattr(self, "wfs_response_3"): self.wfs_response_3.setText(settings["data_dirs"]["wfs"] or "")


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