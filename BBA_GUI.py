import sys, os, re, matplotlib
from datetime import datetime
import numpy as np
try:
    from PyQt6 import uic
    from PyQt6.QtCore import Qt,QProcess,QProcessEnvironment
    from PyQt6.QtWidgets import (QApplication, QRadioButton,QSizePolicy, QMainWindow, QFileDialog, QListWidget, QListWidgetItem,QMessageBox,QProgressDialog, QVBoxLayout, QPushButton, QDialog, QLabel,QStyledItemDelegate)
    from PyQt6.QtGui import QPainter
    pyqt_version = 6
except ImportError:
    from PyQt5 import uic
    from PyQt5.QtCore import Qt,QProcess,QProcessEnvironment
    from PyQt5.QtWidgets import (QApplication, QRadioButton,QSizePolicy, QMainWindow, QFileDialog, QListWidget, QListWidgetItem,QMessageBox,QProgressDialog, QVBoxLayout, QPushButton, QDialog, QLabel,QStyledItemDelegate)
    from PyQt5.QtGui import QPainter
    pyqt_version = 5
matplotlib.use("QtAgg")
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from Backend.LogConsole_BBA import LogConsole
from Backend.TestOrbits_BBA import TestOrbits
from Backend.SaveOrLoad import SaveOrLoad
from Backend.DFS_WFS_Correction_BBA import DFS_WFS_Correction_BBA
import matplotlib.pyplot as plt
from Backend.BPM_weights import BPM_weights
from traceback import print_exception
from Interfaces.interface_setup import INTERFACE_SETUP

class BpmWeightsDelegate(QStyledItemDelegate):
    WEIGHTS_ROLE = int(Qt.ItemDataRole.UserRole) + 1

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
            bpm_name = str(index.data(Qt.ItemDataRole.UserRole) or index.data(Qt.ItemDataRole.DisplayRole) or "")
            weights = str(index.data(self.WEIGHTS_ROLE) or "")
            r = opt.rect
            margin = 6
            painter.setFont(opt.font)
            fm = painter.fontMetrics()
            w_w = fm.horizontalAdvance(weights) if weights else 0
            left_rect = r.adjusted(margin, 0, -(w_w + 2 * margin), 0)
            right_rect = r.adjusted(margin, 0, (-margin-15), 0)
            painter.setPen(opt.palette.color(opt.palette.ColorRole.Text))
            painter.drawText(left_rect, int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft), bpm_name)
            if weights:
                painter.drawText(right_rect, int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight), weights)
        finally:
            painter.restore()

class MainWindow(QMainWindow, SaveOrLoad, DFS_WFS_Correction_BBA):
    def __init__(self, interface, dir_name):
        super().__init__()
        self.cwd = os.getcwd()
        self.interface = interface
        self.dir_name = dir_name
        self._cancel = False
        self._number_re = re.compile(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?")
        self.initial_state=interface.get_state() # initial, for restoring
        self.state=interface.get_state() # for latter use
        self.reset_reference_orbit=False
        ui_path = os.path.join(os.path.dirname(__file__), "UI files/BBA_GUI.ui")
        uic.loadUi(ui_path, self)
        self.bpms_list.setItemDelegate(BpmWeightsDelegate(self.bpms_list))
        self._data_dirs = {"traj": None, "dfs": None, "wfs": None}
        self._hist_orbit, self._hist_disp,self._hist_wake=[],[],[]
        self._hist_orbit_x,self._hist_orbit_y = [],[]
        self._hist_disp_x,self._hist_disp_y = [],[]
        self._hist_wake_x,self._hist_wake_y = [],[]
        self._hist_orbit_x_err,self._hist_orbit_y_err, self._hist_orbit_err = [],[],[]
        self._hist_disp_x_err,self._hist_disp_y_err,self._hist_disp_err = [],[],[]
        self._hist_wake_x_err,self._hist_wake_y_err,self._hist_wake_err = [],[],[]
        self.log_console=None
        self.show_response_matrix=None
        self.test_orbits=None
        self._setup_canvases()
        self.bpm_weights={}
        self._populate_lists()
        self._procs=[]
        self.load_correctors_button.clicked.connect(self._load_correctors)
        self.load_bpms_button.clicked.connect(self._load_bpms)
        self.radio_buttons=[self.mode_orbit,self.mode_dispersion, self.mode_wakefield]
        self.pushButton_log.clicked.connect(self._show_console_log)
        self.pushButton_testorb.clicked.connect(self._show_test_orbits)
        self.session_database_3.setText(dir_name)
        self.pushButton_8.clicked.connect(self._pick_and_load_traj_data)
        self.pushButton_9.clicked.connect(self._pick_and_load_disp_data)
        self.pushButton_10.clicked.connect(self._pick_and_load_wake_data)
        self.clear_graphs_button.clicked.connect(self._clear_graphs)
        self.pushButton_11.clicked.connect(self.load_session_settings)
        self.restore_initial_settings.clicked.connect(self._restore_initial_settings)
        self.modes= [ 'Orbit', 'Dispersion', 'Wakefield']
        self._running = False
        self.appropriate_settings_energy=None
        self.appropriate_settings_intensity=None
        self.appropriate_settings_reset_e=None
        self.appropriate_settings_reset_ch=None
        self.start_button.clicked.connect(self._on_start_click)
        self.stop_button.clicked.connect(self._stop_correction)
        self.corrs = self.initial_state.get_correctors()["names"]
        self.setWindowTitle("BBA GUI")
        self.lineEdit.setText("1")
        self.lineEdit_2.setText("10")
        self.lineEdit_3.setText("10")
        self.lineEdit_4.setText("0.001")
        self.lineEdit_5.setText("10")
        self.lineEdit_6.setText("0.4")
        self.lineEdit_beta.setText("0")
        self.compute_response_matrix_button.clicked.connect(self._display_response_matrix)
        self.pushButton_reset_ref_orbit.clicked.connect(self._reset_reference_orbit)
        self.reset_ref_orb=False
        self.bpms_list.itemDoubleClicked.connect(self._edit_bpm_weights)
        correctors = self.interface.get_correctors()
        correctors_list = correctors['names']
        self.hcorrector_names=set(map(str, self.interface.get_hcorrectors_names() or [])) # takes correctors names, if None, then use an empty list, makes everything a string and saves as a set without the duplicates
        self.vcorrector_names=set(map(str, self.interface.get_vcorrectors_names() or []))

        units_settings, sysid_kick, bpm_unit, corrs_unit=self._get_interface_units()
        self.sysid_kick=sysid_kick
        self.bpm_unit=bpm_unit
        self.corrs_unit=corrs_unit


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

    def _get_interface_initial_settings(self):
        interface_class_name=self.interface.__class__.__name__
        interface_module_name=self.interface.__class__.__module__

        for machine_interfaces in INTERFACE_SETUP.values():
            for interface_defaults in machine_interfaces:
                if (interface_defaults.get("class_name")==interface_class_name) and (interface_defaults.get("module")==interface_module_name):
                    return interface_defaults
        return None

    def _get_interface_units(self):
        interface_defaults=self._get_interface_initial_settings()
        if interface_defaults is None:
            return {},0.01,"mm",""
        units_settings=interface_defaults.get("units",{})
        sysid_kick=units_settings.get("sysid_corrector_kick",0.01)
        bpm_unit=units_settings.get("bpm_position","mm")
        corrs_unit=units_settings.get("corrector_strength","T*mm")

        return units_settings, sysid_kick,bpm_unit,corrs_unit

    def _restore_initial_settings(self):
        self.log("Restoring initial settings...")
        self._cancel=True
        self._running=False
        self.interface.reset_energy()
        self.interface.reset_intensity()
        self.interface.restore_correctors_state(self.initial_state)
        self.reset_ref_orb=True
        self._clear_graphs()
        self.log("Machine initial settings restored.")

    def _is_h_corrector(self, s):
        return str(s) in self.hcorrector_names
    def _is_v_corrector(self, s):
        return str(s) in self.vcorrector_names

    def _edit_bpm_weights(self,bpm):
        bpm_name = bpm.data(Qt.ItemDataRole.UserRole) or (bpm.text() or "")
        if not bpm_name:
            bpm_name=(bpm.text() or "").split("    [",1)[0]
        bpm_window=BPM_weights(bpm_name=bpm_name,parent=self)
        if bpm_name in self.bpm_weights:
            w_orb,w_dfs,w_wfs=self.bpm_weights[bpm_name]
            bpm_window.set_values(w_orb,w_dfs,w_wfs)

        if bpm_window.exec()==QDialog.DialogCode.Accepted:
            self.bpm_weights[bpm_name] = bpm_window.get_values()
            self._update_bpm_weights(bpm)

    def _on_start_click(self):
        print("Starting button clicked...")
        self.log("Starting button clicked...")
        if not self._running:
            self._running = True
            self._step = True
            try:
                self._start_correction()
            finally:
                self._running = False
        else:
            self._step = True

    def _expand_data_path(self,path):
        home=os.path.expanduser("~")
        if path.startswith(home+os.sep): #the character used by the operating system to separate pathname components
            return "~"+path[len(home):]
        return path

    def _setup_canvases(self):
        if FigureCanvas is None:
            self.traj_canvas = self.disp_canvas = self.wake_canvas = None
            self.traj_ax=self.disp_ax = self.wake_ax = None
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
            ax = fig.add_subplot(111)
            return fig, canvas,ax

        self.traj_fig, self.traj_canvas, self.traj_ax = install(self.plot_widget_3)
        self.disp_fig, self.disp_canvas,self.disp_ax = install(self.plot_widget_4)
        self.wake_fig, self.wake_canvas, self.wake_ax = install(self.plot_widget_5)

    def _plot_series(self, ax, canvas, values_x,values_y, vals,title=None, error_x=None,error_y=None,error_all=None):
        ylabel = f"Residual norm [{self.bpm_unit}]"
        if canvas is None or ax is None:
            return
        ax.clear()

        if values_x:
            err_x=error_x if error_x is not None else None
            ax.errorbar(range(1, len(values_x) + 1), values_x,yerr=err_x, marker="o",color='red',label="x",capsize=6, elinewidth=2, capthick=2, markersize=4) #yerr - height of the error bar on the plot, capsize - size of the top line on the error bar
        if values_y:
            err_y=error_y if error_y is not None else None
            ax.errorbar(range(1, len(values_y) + 1), values_y, yerr=err_y,marker="o",color='blue',label="y", capsize=6, elinewidth=2, capthick=2, markersize=4)
        if vals:
            err_all=error_all if error_all is not None else None
            ax.errorbar(range(1, len(vals) + 1), vals, yerr=err_all,linestyle="dashed",color='black',label="combined norm",capsize=6, elinewidth=2, capthick=2, markersize=4)
        if values_x or values_y:
            ax.legend(fontsize=7,loc="upper right")
        if title is not None:
            ax.set_title(title)
        ax.set_xlabel("Iteration", fontsize=6)
        if ylabel is not None:
            ax.set_ylabel(ylabel, fontsize=6)
        ax.tick_params(axis="both", which="major", labelsize=7)
        ax.yaxis.get_offset_text().set_fontsize(7)
        ax.grid(True, alpha=0.3)
        canvas.draw_idle()

    def _get_bpm_weights_text(self,bpm_name):
        wbpm_orb, wbpm_dfs, wbpm_wfs = self.bpm_weights.get(bpm_name, (1.0, 1.0, 1.0))
        return f"[w1 = {wbpm_orb:g}, w2 = {wbpm_dfs:g}, w3 = {wbpm_wfs:g}]" # general format, removes reduntant zeros at the end etc.

    def _update_bpm_weights(self, item):
        bpm_name=item.data(Qt.ItemDataRole.UserRole) or (item.text() or "") # it gives a clean name of the item, even if there is another text (like weights)
        item.setData(BpmWeightsDelegate.WEIGHTS_ROLE, self._get_bpm_weights_text(bpm_name))
        item.setText(bpm_name)

    def _populate_lists(self):
        corrs = self.initial_state.get_correctors()["names"]
        bpms = self.initial_state.get_bpms()["names"]
        self.correctors_list.insertItems(0, corrs)
        for bpm_name in bpms:
            bpm_name=str(bpm_name)
            item=QListWidgetItem(bpm_name)
            item.setData(Qt.ItemDataRole.UserRole, bpm_name)
            item.setData(BpmWeightsDelegate.WEIGHTS_ROLE, self._get_bpm_weights_text(bpm_name))
            self.bpms_list.addItem(item)

    def _get_selection(self):
        corrs_all = self.initial_state.get_correctors()["names"]
        bpms_all = self.initial_state.get_bpms()["names"]

        selected_corrs = []
        for i in range(self.correctors_list.count()):
            it = self.correctors_list.item(i)
            if it.isSelected():
                selected_corrs.append(it.text())
        corrs = selected_corrs or corrs_all

        selected_bpms = []
        for i in range(self.bpms_list.count()):
            it = self.bpms_list.item(i)
            if it.isSelected():
                selected_bpms.append(it.data(Qt.ItemDataRole.UserRole))
        bpms = selected_bpms or bpms_all

        return corrs, bpms

    def _force_triangular(self) -> bool:
        return bool(self.triangular_checkbox.isChecked())

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

    def _calc_error(self,x_meas,y_meas,ref_x,ref_y, disp_x=None,disp_y=None):
        x_val=np.asarray(x_meas,dtype=float)
        y_val=np.asarray(y_meas,dtype=float)
        meanx=np.mean(x_val,axis=0)
        meany=np.mean(y_val,axis=0)
        faulty=(meanx==0.0) & (meany==0.0)
        if np.any(faulty):
            x_val[:,faulty]=np.nan
            y_val[:,faulty]=np.nan
        ref_x = np.asarray(ref_x, dtype=float).reshape(1, -1)
        ref_y = np.asarray(ref_y, dtype=float).reshape(1, -1)

        if disp_x is None:
            disp_x=0
        if disp_y is None:
            disp_y=0

        disp_x=np.asarray(disp_x,dtype=float).reshape(1,-1)
        disp_y=np.asarray(disp_y,dtype=float).reshape(1,-1)

        dx=x_val-ref_x-disp_x
        dy=y_val-ref_y-disp_y

        dx=np.nan_to_num(dx,nan=0,posinf=0,neginf=0)
        dy=np.nan_to_num(dy,nan=0,posinf=0,neginf=0)

        x_norm=np.linalg.norm(dx,axis=1)
        y_norm=np.linalg.norm(dy,axis=1)
        all_norm=x_norm+y_norm

        def std_calc(a):
            a=np.asarray(a,dtype=float)
            a=a[np.isfinite(a)]
            if a.size==0:
                return float("nan"), float("nan")
            if a.size==1:
                return float(a[0]), 0
            return float(np.mean(a)),float(np.std(a,ddof=1))
        mean_x,std_x=std_calc(x_norm)
        mean_y,std_y=std_calc(y_norm)
        mean_all,std_all=std_calc(all_norm)
        return mean_x,mean_y,std_x,std_y,mean_all,std_all

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
        beta = getf("lineEdit_beta", 0.0)
        return orbit_w, disp_w, wake_w, rcond, iters, gain,beta

    def _reset_reference_orbit(self):
        self.reset_ref_orb=True
        self.log("Resetting reference orbit")

    def _start_correction(self):
        try:
            corrs, bpms = self._get_selection()

            '''
            Restore only selected correctors
            '''
            # self.S0bdes = []
            # corrs, bpms = self._get_selection()
            print(f'debug: corrs = {corrs}')
            print(f'debug: bpms = {bpms}')
            # self.selected_correctors = []
            # # save list of initial bdes for reset
            # for cname, bdes in zip(self.S0.correctors['names'], self.S0.correctors['bdes']):
            #     if cname in corrs:
            #         self.S0bdes.append(bdes)
            #         self.selected_correctors.append(cname)
            print("Starting correction...")
            self.log("Starting correction...")
            self._cancel = False
            w1, w2, w3, rcond, iters, gain,beta = self._read_params()
            wgt_orb, wgt_dfs, wgt_wfs = w1, w2, w3
            corrs, bpms = self._get_selection()

            Cx = [s for s in corrs if self._is_h_corrector(s)]

            Cy = [s for s in corrs if self._is_v_corrector(s)]

            Axx, Ayy,Axy,Ayx, B0x, B0y,hcorrs,vcorrs, bpms_common = self._creating_response_matrices()
            bpms=list(bpms_common)

            n=len(bpms)
            wbpm_orb_vec,wbpm_dfs_vec,wbpm_wfs_vec=[],[],[]
            for bpm in bpms:
                wbpm_orb,wbpm_dfs,wbpm_wfs = self.bpm_weights.get(bpm,(1.0,1.0,1.0))
                wbpm_orb_vec.append(wbpm_orb)
                wbpm_dfs_vec.append(wbpm_dfs)
                wbpm_wfs_vec.append(wbpm_wfs)
            wbpm_orb_vec=np.array(wbpm_orb_vec,dtype=float).reshape(n,1)
            wbpm_dfs_vec=np.array(wbpm_dfs_vec,dtype=float).reshape(n,1)
            wbpm_wfs_vec=np.array(wbpm_wfs_vec,dtype=float).reshape(n,1)

            w_parts=[]
            if w1>0: w_parts.append(wbpm_orb_vec)
            if w2>0: w_parts.append(wbpm_dfs_vec)
            if w3>0: w_parts.append(wbpm_wfs_vec)

            W_x=np.vstack(w_parts)
            W_xy=np.vstack([W_x,W_x]) #because the weights are the same, B=vstack(bx,by)
            #W_xy=np.clip(W_xy, 0, 25) #idk, maybe later there's a need for clamp
            w_xy_bpms=np.sqrt(W_xy)

            self.setWindowTitle("BBA GUI - [Correction running]")

            target_disp_x, target_disp_y = self.interface.get_target_dispersion(bpms)

            max_curr_h = self.max_horizontal_current_spinbox.value() # gauss * m
            max_curr_v = self.max_vertical_current_spinbox.value() # gauss * m

            def clamp(val, max_val):
                val=np.asarray(val,dtype=float)
                max_val=np.asarray(max_val,dtype=float)
                result=val.copy()
                finite=np.isfinite(max_val)&(max_val>0.0)
                result[finite]=np.clip(result[finite],-max_val[finite],max_val[finite]) # clip limits the values in an array
                return result

            plt.ion()

            for it in range(iters):
                if self._cancel:
                    break
                self._step = False

                # nominal
                print("Measuring orbit")
                self.log("Measuring orbit")
                state0=self.interface.get_state()
                O0 = state0.get_orbit(bpms) #because axis=1 is mean from one whole measurement, not for 1 bpm
                O0x=np.asarray(O0['x'],dtype=float).reshape(-1,1)
                O0y=np.asarray(O0['y'],dtype=float).reshape(-1,1)
                bpms0=state0.get_bpms(bpms)
                x0_vals=np.asarray(bpms0['x'],dtype=float)
                y0_vals=np.asarray(bpms0['y'],dtype=float)

                if it == 0: #instead of golden orbit, correct from current orbit
                    B0x = O0x
                    B0y = O0y

                if self.reset_ref_orb==True:
                    B0x = O0x.copy()
                    B0y=O0y.copy()
                    self.reset_ref_orb=False
                    self.log("Reference orbit reset to current orbit")

                # dfs
                if w2>0:
                    print("Measuring dispersion")
                    self.log("Measuring dispersion")
                    dP_P = self.interface.change_energy()
                    state1=self.interface.get_state()
                    self.interface.reset_energy()
                    O1 = state1.get_orbit(bpms)
                    O1x=np.asarray(O1['x'],dtype=float).reshape(-1,1)
                    O1y=np.asarray(O1['y'],dtype=float).reshape(-1,1)
                    bpms1 = state1.get_bpms(bpms)
                    x1_vals = np.asarray(bpms1["x"], dtype=float)
                    y1_vals = np.asarray(bpms1["y"], dtype=float)
                    Dx = np.array([1e3 * dx * dP_P for dx in target_disp_x]).reshape(-1,1)
                    Dy = np.array([1e3 * dy * dP_P for dy in target_disp_y]).reshape(-1,1)
                    plt.clf()
                    plt.plot(Dx, label='nominal')
                else:
                    O1x=O1y=None
                    Dx=Dy=None

                # wfs
                if w3>0:
                    print("Measuring wakefield")
                    self.log("Measuring wakefield")
                    self.interface.change_intensity()
                    state2=self.interface.get_state()
                    self.interface.reset_intensity()
                    O2 = state2.get_orbit(bpms)
                    O2x = np.asarray(O2['x'], dtype=float).reshape(-1, 1)
                    O2y = np.asarray(O2['y'], dtype=float).reshape(-1, 1)
                    bpms2 = state2.get_bpms(bpms)
                    x2_vals = np.asarray(bpms2["x"], dtype=float)
                    y2_vals = np.asarray(bpms2["y"], dtype=float)
                else:
                    O2x=O2y=None
                self.test_orbits_data={
                    "selected_bpms": list(bpms),
                    "O0x": np.asarray(O0x).reshape(-1), # because np.array is creating a copy
                    "O1x": None if O1x is None else np.asarray(O1x).reshape(-1),
                    "O2x": None if O2x is None else np.asarray(O2x).reshape(-1),
                    "O0y": np.asarray(O0y).reshape(-1),
                    "O1y": None if O1y is None else np.asarray(O1y).reshape(-1),
                    "O2y": None if O2y is None else np.asarray(O2y).reshape(-1),
                }

                Bx=[]
                By=[]
                if w1>0:
                    Bx.append(wgt_orb*(O0x-B0x))
                    By.append(wgt_orb*(O0y-B0y))

                if w2>0 and O1x is not None:
                    plt.plot((O1x-O0x), label='measured')
                    plt.show()
                    Bx.append(wgt_dfs*((O1x-O0x) - Dx))
                    By.append(wgt_dfs*((O1y-O0y) - Dy))

                if w3>0 and O2x is not None:
                    By.append(wgt_wfs*(O2y-O0y))
                    Bx.append(wgt_wfs*(O2x-O0x))

                Bx=np.vstack(Bx)
                By=np.vstack(By)

                Axx[np.isnan(Axx)] = 0
                Ayy[np.isnan(Ayy)] = 0
                Axy[np.isnan(Axy)] = 0
                Ayx[np.isnan(Ayx)] = 0

                Axx[np.isnan(Bx.ravel()),:] =0 # flattens an array into 1d
                Axy[np.isnan(Bx.ravel()),:] =0 # flattens an array into 1d

                Ayy[np.isnan(By.ravel()),:] = 0
                Ayx[np.isnan(By.ravel()),:] = 0

                Bx[np.isnan(Bx)] = 0
                By[np.isnan(By)] = 0

                # A = U * Sigma * V^
                # A^+ = V * Sigma^+ * U^T

                filter_corr_x=np.all(np.isfinite(Axx),axis=0) & np.all(np.isfinite(Ayx),axis=0) #corrs
                filter_corr_y=np.all(np.isfinite(Ayy),axis=0) & np.all(np.isfinite(Axy),axis=0)

                Axx=Axx[:,filter_corr_x]
                Ayx=Ayx[:,filter_corr_x]

                Ayy=Ayy[:,filter_corr_y]
                Axy=Axy[:,filter_corr_y]

                Cy_cut=[corr for corr,true in zip(vcorrs,filter_corr_y) if true]
                Cx_cut=[corr for corr,true in zip(hcorrs,filter_corr_x) if true]

                A = np.block([[Axx,Axy],
                              [Ayx,Ayy]])

                B=np.vstack([Bx,By])

                A[np.isnan(A)] = 0
                B[np.isnan(B)] = 0

                # corrX = -gain * (np.linalg.pinv(Axx, rcond=rcond) @ Bx)  # theta = - gain * Axx^+ *Bx
                # corrY = -gain * (np.linalg.pinv(Ayy, rcond=rcond) @ By)

                A_weighted=w_xy_bpms*A
                B_weighted=w_xy_bpms*B

                #adding the (Aw.T*Aw+beta*I)-1
                if beta>0: # with beta, A.T@A+beta*I is always reversible, so we use solve, matrix is square and reversible
                    delta = -gain * np.linalg.solve(A_weighted.T@A_weighted+beta*np.eye(A_weighted.shape[1]),A_weighted.T@B_weighted) # without pinv, because we add beta so that singular values will not be near zero
                else: # np.eye(n) singular matrix with shape= number of columns
                    delta = -gain * (np.linalg.pinv(A_weighted, rcond=rcond) @ B_weighted)
                print(f"Delta is {delta}")
                nh=len(Cx_cut)
                corrX=delta[:nh] # horizontal changes
                corrY=delta[nh:] # vertical changes

                delta_x=np.asarray(corrX.ravel(),dtype=float) # asarray doesnt copy, like np.array
                delta_y=np.asarray(corrY.ravel(),dtype=float)
                delta_vals=np.concatenate([delta_x,delta_y])

                selected_correctors=Cx_cut+Cy_cut
                current_corrs=self.interface.get_correctors(selected_correctors)
                current_bdes=np.asarray(current_corrs['bdes'],dtype=float).ravel()

                max_vals_x=np.full(delta_x.shape,max_curr_h,dtype=float)
                max_vals_y=np.full(delta_y.shape,max_curr_v,dtype=float)
                max_vals=np.concatenate([max_vals_x,max_vals_y])

                new_bdes=current_bdes+delta_vals
                new_bdes=clamp(new_bdes,max_vals)
                self.interface.set_correctors(selected_correctors,new_bdes)
                vals=new_bdes-current_bdes

                # current_bdes + delta -> clamp(final_bdes) -> set_correctors(final_bdes)

                def filtering_norm_x(Ox,Bx):
                    Ox[np.isnan(Ox)] = 0
                    Bx[np.isnan(Bx)] = 0
                    return float(np.linalg.norm(Ox - Bx))

                def filtering_norm_y(Oy,By):
                    Oy[np.isnan(Oy)] = 0
                    By[np.isnan(By)] = 0
                    return float(np.linalg.norm(Oy - By))

                if w1>0:
                    mean_orbit_x,mean_orbit_y,err_x_orbit,err_y_orbit,mean_orbit_all,err_orbit_all=self._calc_error(x0_vals,y0_vals,ref_x=B0x.ravel(),ref_y=B0y.ravel()) # ravel makes data a vector
                    self._hist_orbit_x.append(mean_orbit_x)
                    self._hist_orbit_y.append(mean_orbit_y)
                    self._hist_orbit.append(mean_orbit_all)
                    self._hist_orbit_x_err.append(err_x_orbit)
                    self._hist_orbit_y_err.append(err_y_orbit)
                    self._hist_orbit_err.append(err_orbit_all)

                if w2>0 and O1x is not None and O1y is not None:
                    dx_disp=x1_vals-x0_vals
                    dy_disp=y1_vals-y0_vals
                    mean_disp_x,mean_disp_y,err_disp_x,err_disp_y,mean_disp_all,err_disp_all=self._calc_error(dx_disp,dy_disp,ref_x=np.zeros(dx_disp.shape[1]), ref_y=np.zeros(dy_disp.shape[1]),disp_x=Dx.ravel(),disp_y=Dy.ravel())
                    self._hist_disp_x.append(mean_disp_x)
                    self._hist_disp_y.append(mean_disp_y)
                    self._hist_disp.append(mean_disp_all)
                    self._hist_disp_x_err.append(err_disp_x)
                    self._hist_disp_y_err.append(err_disp_y)
                    self._hist_disp_err.append(err_disp_all)

                if w3>0 and O2x is not None:
                    dx_wake=x2_vals-x0_vals
                    dy_wake=y2_vals-y0_vals
                    mean_wake_x, mean_wake_y, err_wake_x, err_wake_y, mean_wake_all, err_wake_all = self._calc_error(dx_wake, dy_wake,ref_x=np.zeros(dx_wake.shape[1]), ref_y=np.zeros(dy_wake.shape[1]))
                    self._hist_wake_x.append(mean_wake_x)
                    self._hist_wake_y.append(mean_wake_y)
                    self._hist_wake.append(mean_wake_all)
                    self._hist_wake_x_err.append(err_wake_x)
                    self._hist_wake_y_err.append(err_wake_y)
                    self._hist_wake_err.append(err_wake_all)

                self._plot_series(ax=self.traj_ax, canvas=self.traj_canvas, values_x=self._hist_orbit_x,values_y=self._hist_orbit_y, vals=self._hist_orbit,error_x=self._hist_orbit_x_err, error_y=self._hist_orbit_y_err, error_all=self._hist_orbit_err, title=None)
                self._plot_series(ax=self.disp_ax, canvas=self.disp_canvas, values_x= self._hist_disp_x,values_y=self._hist_disp_y ,vals=self._hist_disp,error_x=self._hist_disp_x_err, error_y=self._hist_disp_y_err, error_all=self._hist_disp_err, title=None)
                self._plot_series(ax=self.wake_ax, canvas=self.wake_canvas, values_x=self._hist_wake_x, values_y=self._hist_wake_y ,vals=self._hist_wake,error_x=self._hist_wake_x_err, error_y=self._hist_wake_y_err, error_all=self._hist_wake_err, title=None)
                QApplication.processEvents()

            self.setWindowTitle("BBA GUI")
            QMessageBox.information(self, "Correction", "Correction finished.")
            state = self.interface.get_state()
            print(state.get_bpms())
            print(state.get_screens())
            self.log("Correction finished.")
            self.save_session_settings(w1, w2, w3, rcond, iters, gain, Axx, Ayy,Axy,Ayx, Bx, By)

        except Exception as e:
            self.setWindowTitle("BBA GUI")
            QMessageBox.critical(self, "Correction error", str(e))
            self.log(f"Correction error: {e}")
            print_exception(e)

    def _stop_correction(self):
        self._cancel = True
        QMessageBox.information(self, "Correction", "Stop requested. Finishing current iteration...")
        self.log("Stop requested. Finishing current iteration...")

    def _show_test_orbits(self):
        if self.test_orbits is None:
            self.test_orbits=TestOrbits(self)
        if not hasattr(self, "test_orbits_data") or self.test_orbits_data is None:
            QMessageBox.information(self, "No test orbits available", "No test orbits available.")
        else:
            self.test_orbits._plot_test_orbits(selected_bpms=self.test_orbits_data["selected_bpms"],O0x=self.test_orbits_data["O0x"],O0y=self.test_orbits_data["O0y"],
                                               O1x=self.test_orbits_data["O1x"],O1y=self.test_orbits_data["O1y"],O2x=self.test_orbits_data["O2x"],O2y=self.test_orbits_data["O2y"])
        self.test_orbits.show()
        self.test_orbits.raise_()
        self.test_orbits.activateWindow()

    def _show_console_log(self):
        if self.log_console is None:
            self.log_console=LogConsole(self)
        self.log_console.show()
        self.log_console.raise_()
        self.log_console.activateWindow()

    def log(self,text):
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line=f"[{timestamp}] {text}"
        if self.log_console is None:
            self.log_console=LogConsole(self)
            self.log_console.show()
        self.log_console.log(line)

    def _clear_graphs(self):
        # it doesnt do fresh - start, it only clears the graphs
        self._cancel = True
        self._hist_orbit_x.clear(),self._hist_orbit_y.clear()
        self._hist_disp_x.clear(),self._hist_disp_y.clear()
        self._hist_wake_x.clear(),self._hist_wake_y.clear()
        self._hist_orbit.clear(),self._hist_disp.clear(),self._hist_wake.clear()
        self._hist_orbit_x_err.clear(), self._hist_orbit_y_err.clear(), self._hist_orbit_err.clear()
        self._hist_disp_x_err.clear(), self._hist_disp_y_err.clear(), self._hist_disp_err.clear()
        self._hist_wake_x_err.clear(), self._hist_wake_y_err.clear(), self._hist_wake_err.clear()
        self._plot_series(self.traj_ax, self.traj_canvas, values_x=[], values_y=[],vals=[],title=None)
        self._plot_series(self.disp_ax, self.disp_canvas, values_x=[],values_y=[],vals=[], title=None)
        self._plot_series(self.wake_ax, self.wake_canvas, values_x=[],values_y=[], vals=[],title=None)

    def handling(self, app_name,cwd=None, args=None):
        try:
            path = os.path.join(os.path.dirname(__file__), app_name)
            workdir=os.path.expanduser(os.path.expandvars(cwd))

            proc = QProcess(self)
            proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
            proc.setWorkingDirectory(workdir)

            env = QProcessEnvironment.systemEnvironment()
            proc.setProcessEnvironment(env)

            argv = [path] + list(args or [])
            proc.start(sys.executable, argv)

            proc.readyReadStandardOutput.connect(
                lambda p=proc: print(bytes(p.readAllStandardOutput()).decode(errors="ignore"))
            )
            self._procs.append(proc)
            print(workdir)

        except Exception as e:
            self.log(f"Error: {e}")
            print(f"Error in handling: {e}")

    def _display_response_matrix(self):
        orbit_dir=self.trajectory_response_3.text()
        dispersion_dir=self.dfs_response_3.text()
        wakefield_dir=self.wfs_response_3.text()
        selected_mode=None
        for rb in self.radio_buttons:
            if rb.isChecked():
                selected_mode = rb.text()
                break
        if selected_mode is None:
            selected_mode = self.modes[0]

        if selected_mode==self.modes[0]:
            mode = "orbit"
            args = ["--dir1",orbit_dir,"--compute"]

        elif selected_mode==self.modes[1]:
            mode = "dispersion"
            if not dispersion_dir:
                QMessageBox.warning(self, "Warning", "No dispersion directory selected")
                return
            args = ["--dir1",dispersion_dir,"--dir2",orbit_dir,"--diff","--compute"]

        elif selected_mode==self.modes[2]:
            mode = "wakefield"
            if not wakefield_dir:
                QMessageBox.warning(self, "Warning", "No wakefield directory selected")
                return
            args = ["--dir1",wakefield_dir,"--dir2",orbit_dir,"--diff","--compute"]

        self.handling('ComputeResponseMatrix_GUI.py', cwd=self.cwd,args=args) # args = arguments passed to the second program

if __name__ == "__main__":
    app = QApplication(sys.argv)
    from Backend import SelectInterface

    dialog = SelectInterface.choose_acc_and_interface()
    if dialog is None:
        print("Selection cancelled.")
        sys.exit(1)

    I=dialog
    project_name=I.get_name()
    print(f"Selected interface: {project_name}")
    time_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    dir_name = f"~/flight-simulator-data/BBA_{I.get_name()}_{time_str}_session_settings"
    dir_name = os.path.expanduser(os.path.expandvars(dir_name))
    w = MainWindow(interface=I, dir_name=dir_name)

    if hasattr(I, "log_messages"):
        I.log_messages(w.log)

    w.show()
    sys.exit(app.exec())
