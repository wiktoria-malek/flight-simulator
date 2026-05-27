from State import State
from datetime import datetime
from functools import partial
from collections import deque
import numpy as np
import threading
import signal
import time
import sys
import os
from PyQt6 import uic
from PyQt6.QtGui import QPixmap, QIcon, QPainter
from PyQt6.QtWidgets import QApplication, QMainWindow, QFileDialog, QListWidget, QMessageBox, QProgressBar, QComboBox
from PyQt6.QtCore import Qt, QThread, QTimer, QObject, pyqtSignal, pyqtSlot
from enum import Enum
import matplotlib
matplotlib.use('QtAgg')
import matplotlib.pyplot as plt

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from jitter_subtraction import explain_reference_selection, fit_jitter_model, apply_jitter_subtraction

OUTLIER_FACTOR = 10.0


def reject_large_outliers(values, factor=OUTLIER_FACTOR):
    arr = np.asarray(values, dtype=float).copy()
    if arr.ndim != 2 or arr.size == 0:
        return arr
    med_abs = np.nanmedian(np.abs(arr), axis=0)
    threshold = factor * med_abs
    for j, thr in enumerate(threshold):
        if not np.isfinite(thr) or thr <= 0:
            continue
        mask = np.isfinite(arr[:, j]) & (np.abs(arr[:, j]) > thr)
        arr[mask, j] = np.nan
    return arr


def orbit_from_bpms(bpms, names=None):
    all_names = list(bpms.get("names", []))
    x_all = np.asarray(bpms.get("x", []), dtype=float)
    y_all = np.asarray(bpms.get("y", []), dtype=float)
    t_all = np.asarray(bpms.get("tmit", []), dtype=float)
    if names is not None:
        m = {str(n): i for i, n in enumerate(all_names)}
        idx = [m[str(n)] for n in names if str(n) in m]
        names_use = [all_names[i] for i in idx]
        x_all = x_all[:, idx]
        y_all = y_all[:, idx]
        t_all = t_all[:, idx]
    else:
        names_use = all_names
    x_all = reject_large_outliers(x_all)
    y_all = reject_large_outliers(y_all)
    x = np.mean(x_all, axis=0)
    y = np.mean(y_all, axis=0)
    stdx = np.std(x_all, axis=0)
    stdy = np.std(y_all, axis=0)
    tmit = np.mean(t_all, axis=0)
    faulty = np.isnan(x) | np.isnan(y)
    x[faulty] = np.nan
    y[faulty] = np.nan
    return {"names": names_use, "x": x, "y": y, "stdx": stdx, "stdy": stdy, "tmit": tmit, "faulty": faulty, "nbpms": len(names_use)}

def save_machine_state(interface, filename, include_correctors=True, include_icts=True, include_quadrupoles=True, quadrupole_names=None):
    s = State()
    if include_correctors:
        s.correctors = interface.get_correctors()
    else:
        s.correctors = {"names": [], "bdes": np.array([]), "bact": np.array([])}
    if include_quadrupoles and hasattr(interface, "get_quadrupoles"):
        try:
            s.quadrupoles = interface.get_quadrupoles(quadrupole_names)
        except Exception:
            s.quadrupoles = None
    else:
        s.quadrupoles = None
    s.bpms = interface.get_bpms()
    if include_icts and hasattr(interface, "get_icts"):
        s.icts = interface.get_icts()
    else:
        s.icts = {"names": [], "charge": np.array([])}
    s.sequence = interface.get_sequence()
    s.hcorrectors_names = interface.get_hcorrectors_names()
    s.vcorrectors_names = interface.get_vcorrectors_names()
    s.timestamp = datetime.now()
    s.save(filename=filename)
    return s


def save_nominal_jitter_state(interface, filename, nshots=30):
    print(f"Acquiring nominal shots for jitter subtraction ({int(nshots)} shots)...")
    original_nsamples = getattr(interface, "nsamples", None)
    try:
        if original_nsamples is not None:
            interface.nsamples = int(nshots)
        s = State()
        s.correctors = {"names": [], "bdes": np.array([]), "bact": np.array([])}
        s.quadrupoles = None
        s.bpms = interface.get_bpms()
        s.icts = {"names": [], "charge": np.array([])}
        s.sequence = interface.get_sequence()
        s.hcorrectors_names = interface.get_hcorrectors_names()
        s.vcorrectors_names = interface.get_vcorrectors_names()
        s.timestamp = datetime.now()
        s.save(filename=filename)
    finally:
        if original_nsamples is not None:
            interface.nsamples = original_nsamples

class Mode(Enum):
    Orbit = "Orbit Correction"
    Dispersion = "Changed energy"
    Wakefield = "Changed intensity"
    All = "All modes at once"

class Machine(Enum):
    ATF2_DR = "ATF2_DR"
    ATF2_EXT = "ATF2_Ext"
    ATF2_LINAC = "ATF2_Linac"
    ATF2_DR_RFT = "ATF2_DR_RFT"
    ATF2_EXT_RFT = "ATF2_Ext_RFT"

class ActuatorMode(Enum):
    Kicker = "Kicker"
    QM = "QM"

class MatplotlibWidget(FigureCanvas):
    def __init__(self, parent=None, title='', orbit=None):
        fig = Figure(tight_layout=True)
        super().__init__(fig)
        self.setParent(parent)
        self.axes = fig.add_subplot(111)

class Worker(QObject):
    plot_data = pyqtSignal(dict, np.ndarray, np.ndarray, np.ndarray, np.ndarray, object, object, str)
    progress=pyqtSignal(int)
    finished = pyqtSignal()

    def __init__(self, interface, correctors, bpms, hkicks, vkicks, max_osc_h, max_osc_v,
                 max_curr_h, max_curr_v, Niter, output_dir, actuator_mode=ActuatorMode.Kicker):
        super().__init__()
        self.output_dir=output_dir
        self.interface = interface
        self.correctors = correctors
        self.hcorrs = self.interface.get_hcorrectors_names()
        self.vcorrs = self.interface.get_vcorrectors_names()
        self.bpms = bpms
        self.hkicks = hkicks
        self.vkicks = vkicks
        self.max_osc_h = max_osc_h
        self.max_osc_v = max_osc_v
        self.max_curr_h = max_curr_h
        self.max_curr_v = max_curr_v
        self.Niter = Niter
        self.actuator_mode = actuator_mode
        self.running = False
        self.progress_value=0

        if hasattr(self, "working_directory_dialog"):
            self.working_directory_dialog.clicked.connect(self._pick_and_load_data_dir)

    @pyqtSlot()
    def run(self):
        self.running = True

        if self.actuator_mode == ActuatorMode.QM:
            total_steps = self.Niter * len(self.correctors) * 2
        else:
            total_steps = self.Niter * len(self.correctors)
        self.progress_value=0
        I = self.interface
        vkicks = self.vkicks
        hkicks = self.hkicks

        if self.actuator_mode == ActuatorMode.QM:
            nominal_file = os.path.join(self.output_dir, "NOMINAL_JITTER.pkl")
            if not os.path.isfile(nominal_file):
                save_nominal_jitter_state(I, nominal_file, nshots=30)
            jitter_model = None
            try:
                nominal_bpms = State(filename=nominal_file).bpms
                ref_bpms, ref_reason = explain_reference_selection(self.bpms, self.correctors, I.get_sequence(), min_refs=2)
                if ref_bpms:
                    jitter_model, fit_reason = fit_jitter_model([nominal_bpms], ref_bpms, self.bpms)
                    if jitter_model is None:
                        print(f"Jitter subtraction disabled: {fit_reason}")
                else:
                    print(f"Jitter subtraction disabled: {ref_reason}")
            except Exception as exc:
                print(f"Jitter subtraction disabled: failed to build model ({exc})")
                jitter_model = None
        else:
            jitter_model = None

        def get_corrector_bdes(name):
            corr = I.get_correctors()
            names = list(corr.get("names", []))
            bdes = np.asarray(corr.get("bdes", []), dtype=float)
            for n, v in zip(names, bdes):
                if n == name:
                    return float(v)
            raise KeyError(f"Corrector not found: {name}")

        def clamp(val, max_val):
            if max_val == 0.0:
                return val
            return max(-max_val, min(val, max_val))

        def update_amplitude(current_amp, observed, target, max_range):
            if not np.isfinite(observed) or observed <= 0.0:
                new_amp = current_amp * 1.5
            else:
                scale = target / observed if target > 0 else 1.0
                scale = max(0.8, min(scale, 2.0))
                new_amp = current_amp * scale
            if max_range > 0:
                new_amp = min(new_amp, max_range)
            return max(new_amp, 1e-6)

        def finite_abs_max(arr):
            arr = np.asarray(arr)
            arr = arr[np.isfinite(arr)]
            if arr.size == 0:
                return 0.0
            return float(np.max(np.abs(arr)))

        if self.actuator_mode == ActuatorMode.QM:
            sequence = I.get_sequence()
            correctors = sorted(self.correctors, key=lambda n: sequence.index(n) if n in sequence else 10**9)

            for iter in range(self.Niter):
                if not self.running:
                    break

                for icorr, magnet in enumerate(correctors):
                    if not self.running:
                        break

                    q0 = self.interface.get_quadrupoles([magnet])
                    if len(q0["names"]) == 0:
                        continue
                    x0 = float(q0["xdes"][0])
                    y0 = float(q0["ydes"][0])
                    r0 = float(q0["rolldes"][0])

                    for axis in ("x", "y"):
                        if not self.running:
                            break

                        amp = hkicks[icorr] if axis == "x" else vkicks[icorr]
                        target = self.max_osc_h if axis == "x" else self.max_osc_v
                        max_range = self.max_curr_h if axis == "x" else self.max_curr_v
                        if max_range > 0:
                            amp = min(amp, max_range)

                        filename_p = f"DATA_{magnet}_{axis}_p{iter:04d}.pkl"
                        filename_m = f"DATA_{magnet}_{axis}_m{iter:04d}.pkl"

                        print(f"QM {magnet} axis={axis} '+' excitation...")
                        if not os.path.isfile(filename_p):
                            if axis == "x":
                                self.interface.apply_qmag_xyroll(magnet, x0 + amp, y0, r0)
                            else:
                                self.interface.apply_qmag_xyroll(magnet, x0, y0 + amp, r0)
                            state_p = save_machine_state(
                                I,
                                filename=filename_p,
                                include_correctors=False,
                                include_icts=False,
                                include_quadrupoles=True,
                                quadrupole_names=[magnet],
                            )
                            bpms_p_raw = state_p.bpms
                            Op = orbit_from_bpms(bpms_p_raw, self.bpms)
                        else:
                            bpms_p_raw = State(filename=filename_p).bpms
                            Op = orbit_from_bpms(bpms_p_raw, self.bpms)

                        print(f"QM {magnet} axis={axis} '-' excitation...")
                        if not os.path.isfile(filename_m):
                            if axis == "x":
                                self.interface.apply_qmag_xyroll(magnet, x0 - amp, y0, r0)
                            else:
                                self.interface.apply_qmag_xyroll(magnet, x0, y0 - amp, r0)
                            state_m = save_machine_state(
                                I,
                                filename=filename_m,
                                include_correctors=False,
                                include_icts=False,
                                include_quadrupoles=True,
                                quadrupole_names=[magnet],
                            )
                            bpms_m_raw = state_m.bpms
                            Om = orbit_from_bpms(bpms_m_raw, self.bpms)
                        else:
                            bpms_m_raw = State(filename=filename_m).bpms
                            Om = orbit_from_bpms(bpms_m_raw, self.bpms)

                        # Always restore this magnet before moving on.
                        self.interface.apply_qmag_xyroll(magnet, x0, y0, r0)

                        Diff_x = (Op['x'] - Om['x']) / 2.0
                        Diff_y = (Op['y'] - Om['y']) / 2.0
                        nsamples = Op['stdx'].size
                        Err_x = np.sqrt(np.square(Op['stdx']) + np.square(Om['stdx'])) / np.sqrt(nsamples)
                        Err_y = np.sqrt(np.square(Op['stdy']) + np.square(Om['stdy'])) / np.sqrt(nsamples)
                        print(
                            f"QM result {magnet}:{axis} "
                            f"max|dx|={finite_abs_max(Diff_x):.4g} mm, "
                            f"max|dy|={finite_abs_max(Diff_y):.4g} mm"
                        )
                        Diff_x_sub = None
                        Diff_y_sub = None
                        if jitter_model is not None:
                            try:
                                Op_sub = orbit_from_bpms(apply_jitter_subtraction(bpms_p_raw, jitter_model), self.bpms)
                                Om_sub = orbit_from_bpms(apply_jitter_subtraction(bpms_m_raw, jitter_model), self.bpms)
                                Diff_x_sub = (Op_sub['x'] - Om_sub['x']) / 2.0
                                Diff_y_sub = (Op_sub['y'] - Om_sub['y']) / 2.0
                            except Exception:
                                Diff_x_sub = None
                                Diff_y_sub = None
                        self.plot_data.emit(Op, Diff_x, Err_x, Diff_y, Err_y, Diff_x_sub, Diff_y_sub, f"{magnet}:{axis}")

                        self.progress_value += 1
                        percent = int(self.progress_value / total_steps * 100)
                        self.progress.emit(percent)

                        observed = max(finite_abs_max(Diff_x), finite_abs_max(Diff_y))
                        new_amp = update_amplitude(amp, observed, target, max_range)
                        if axis == "x":
                            hkicks[icorr] = new_amp
                        else:
                            vkicks[icorr] = new_amp

                        with open(os.path.join(self.output_dir, 'kicks.txt'), 'w') as f:
                            for i, c in enumerate(correctors):
                                f.write(f'{c} {hkicks[i]} {vkicks[i]}\n')
                        time.sleep(0.2)
        else:
            for iter in range(self.Niter):
                if self.running == False:
                    break

                for icorr, corrector in enumerate(self.correctors):
                    corr_bdes = get_corrector_bdes(corrector)
                    if self.running == False:
                        break

                    if corrector in self.hcorrs:
                        kick=hkicks[icorr]
                    elif corrector in self.vcorrs:
                        kick=vkicks[icorr]
                    else:
                        continue

                    if not self.running:
                        break

                    corr_changed = False

                    print(f"Corrector {corrector} '+' excitation...")
                    filename_p=f'DATA_{corrector}_p{iter:04d}.pkl'
                    if not os.path.isfile(filename_p):
                        print('corr[bds] =', corr_bdes, ' also kick = ', kick) 
                        curr_p = corr_bdes + kick
                        if corrector in self.hcorrs:
                            curr_p = clamp(curr_p, self.max_curr_h)
                        else:
                            curr_p = clamp(curr_p, self.max_curr_v)
                        self.interface.push(corrector, curr_p)
                        corr_changed = True

                        if not self.running:
                            break

                        save_machine_state(I, filename=filename_p)
                        Op = orbit_from_bpms(I.get_bpms(), self.bpms)
                    else:
                        Op = orbit_from_bpms(State(filename=filename_p).bpms, self.bpms)

                    print(f"Corrector {corrector} '-' excitation...")
                    filename_m=f'DATA_{corrector}_m{iter:04d}.pkl'
                    if not os.path.isfile(filename_m):
                        curr_m = corr_bdes - kick
                        if corrector in self.hcorrs:
                            curr_m = clamp(curr_m, self.max_curr_h)
                        else:
                            curr_m = clamp(curr_m, self.max_curr_v)
                        self.interface.push(corrector, curr_m)
                        corr_changed = True

                        if not self.running:
                            break

                        save_machine_state(I, filename=f'DATA_{corrector}_m{iter:04d}.pkl')
                        Om = orbit_from_bpms(I.get_bpms(), self.bpms)
                    else:
                        Om = orbit_from_bpms(State(filename=filename_m).bpms, self.bpms)

                    if corr_changed:
                        self.interface.push(corrector, corr_bdes)

                    Diff_x = (Op['x'] - Om['x']) / 2.0
                    Diff_y = (Op['y'] - Om['y']) / 2.0
                    nsamples = Op['stdx'].size
                    Err_x = np.sqrt(np.square(Op['stdx']) + np.square(Om['stdx'])) / np.sqrt(nsamples)
                    Err_y = np.sqrt(np.square(Op['stdy']) + np.square(Om['stdy'])) / np.sqrt(nsamples)
                    self.plot_data.emit(Op, Diff_x, Err_x, Diff_y, Err_y, None, None, corrector)

                    self.progress_value=self.progress_value + 1
                    percent = int(self.progress_value / total_steps * 100)
                    self.progress.emit(percent)

                    if corrector in self.hcorrs:
                        Diff_x_clean = Diff_x[~np.isnan(Diff_x)]
                        if np.max(np.abs(Diff_x_clean)) != 0.0:
                            hkicks[icorr] *= self.max_osc_h / np.max(np.abs(Diff_x_clean))
                        hkicks[icorr] = 0.8 * hkicks[icorr] + 0.2 * kick
                    else:
                        Diff_y_clean = Diff_y[~np.isnan(Diff_y)]
                        if np.max(np.abs(Diff_y_clean)) != 0.0:
                            vkicks[icorr] *= self.max_osc_v / np.max(np.abs(Diff_y_clean))
                        vkicks[icorr] = 0.8 * vkicks[icorr] + 0.2 * kick

                    with open(os.path.join(self.output_dir,'kicks.txt'), 'w') as f:
                        for i, c in enumerate(self.correctors):
                            f.write(f'{c} {hkicks[i]} {vkicks[i]}\n')

                    time.sleep(1)

        self.running = False
        self.finished.emit()

    def stop(self):
        self.running = False

class MainWindow(QMainWindow):
    def __set_status_in_title(self, status):
        self.setWindowTitle("SYSID - " + self.interface.__class__.__name__ + " " + status)

    @pyqtSlot(int)
    def _update_progress(self,value):
        self.progressBar.setValue(value)

    def __init__(self, interface, dir_name):
        super().__init__()

        # SysID
        self.worker = None
        self.thread = None
        self._activate_mode=None

        self.cwd = os.getcwd()
        self.interface = interface
        bpms_list = list(interface.get_bpms()['names'])
        self._bpm_order = {name: i for i, name in enumerate(bpms_list)}
        # Do not read corrector PVs at startup; this can block and is unnecessary for QM mode.
        if hasattr(self.interface, "get_correctors_names"):
            try:
                correctors_list = list(self.interface.get_correctors_names())
            except Exception:
                correctors_list = []
        else:
            correctors_list = []
        self.kicker_list = list(correctors_list)
        if hasattr(self.interface, "get_quadrupoles_names"):
            try:
                self.qm_list = list(self.interface.get_quadrupoles_names())
            except Exception:
                self.qm_list = []
        else:
            self.qm_list = []
        if not self.qm_list:
            try:
                self.qm_list = [s for s in self.interface.get_sequence() if str(s).upper().startswith("Q")]
            except Exception:
                self.qm_list = []
        else:
            q_only = [s for s in self.qm_list if str(s).upper().startswith("Q")]
            if q_only:
                self.qm_list = q_only
        self.actuator_mode = ActuatorMode.Kicker

        max_curr_h = 1.0
        max_curr_v = 1.0

        # Load the interface
        uic.loadUi("SysID_GUI.ui", self)

        # Replace the placeholder with your real widget
        self.right_layout.removeWidget(self.plot_widget)
        self.plot_widget.deleteLater()
        self.plot_widget = MatplotlibWidget(self)
        self.right_layout.addWidget(self.plot_widget)

        # Setting up the interface
        self.save_correctors_button.clicked.connect(self.__save_correctors_button_clicked)
        self.load_correctors_button.clicked.connect(self.__load_correctors_button_clicked)
        self.clear_correctors_button.clicked.connect(self.__clear_correctors_button_clicked)
        self.save_bpms_button.clicked.connect(self.__save_bpms_button_clicked)
        self.load_bpms_button.clicked.connect(self.__load_bpms_button_clicked)
        self.clear_bpms_button.clicked.connect(self.__clear_bpms_button_clicked)
        self.start_button.clicked.connect(self.__start_button_clicked)
        self.stop_button.clicked.connect(self.__stop_button_clicked)

        self.choose_mode.setCurrentText(Mode.Orbit.value)
        self.mode=Mode.Orbit
        self.choose_mode.currentTextChanged.connect(self._choose_the_correction_mode)
        self.initial_hkick_settings.setText("0.01")
        self.initial_vkick_settings.setText("0.01")

        self.actuator_mode_combo = QComboBox(self)
        self.actuator_mode_combo.addItems([ActuatorMode.Kicker.value, ActuatorMode.QM.value])
        self.correctors_header_layout.addWidget(self.actuator_mode_combo)
        self.actuator_mode_combo.currentTextChanged.connect(self._on_actuator_mode_changed)

        self.correctors_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self._refresh_corrector_list()
        self.bpms_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.bpms_list.insertItems(0, bpms_list)
        self.working_directory_input.setText(dir_name)
        self.max_horizontal_current_spinbox.setValue(max_curr_h)
        self.max_horizontal_current_spinbox.setSingleStep(0.01)
        self.max_vertical_current_spinbox.setValue(max_curr_v)
        self.max_vertical_current_spinbox.setSingleStep(0.01)
        self.horizontal_excursion_spinbox.setValue(0.5)
        self.horizontal_excursion_spinbox.setSingleStep(0.1)
        self.vertical_excursion_spinbox.setValue(0.5)
        self.vertical_excursion_spinbox.setSingleStep(0.1)

        if hasattr(self, "working_directory_dialog"):
            self.working_directory_dialog.clicked.connect(self._pick_and_load_data_dir)
        self.__set_status_in_title("[Idle]")
        interface_name=interface.get_name()
        machine = Machine(interface_name)

        self.modes_to_do=[]
        self.counter=0
        self.current_mode=None
        self._refresh_actuator_labels()

    def _order_bpms(self, names):
        return sorted(names, key=lambda n: self._bpm_order.get(n, 10**9))

    def _available_actuators(self):
        items = list(self.qm_list) if self.actuator_mode == ActuatorMode.QM else list(self.kicker_list)
        seq = self.interface.get_sequence()
        return sorted(items, key=lambda n: seq.index(n) if n in seq else 10**9)

    def _refresh_corrector_list(self, preserve_selection=False):
        selected = {it.text() for it in self.correctors_list.selectedItems()} if preserve_selection else set()
        items = self._available_actuators()
        self.correctors_list.clear()
        self.correctors_list.insertItems(0, items)
        if preserve_selection:
            for name in selected:
                matches = self.correctors_list.findItems(name, Qt.MatchFlag.MatchExactly)
                for it in matches:
                    it.setSelected(True)

    def _refresh_actuator_labels(self):
        if self.actuator_mode == ActuatorMode.QM:
            self.correctors_label.setText("Quadrupoles")
            self.initial_hkick_label.setText("Initial X [um]")
            self.initial_vkick_label.setText("Initial Y [um]")
            self.current_label.setText("Max range [um]")
            self.horizontal_current_label.setText("X:")
            self.vertical_current_label.setText(" Y:")
            self.max_horizontal_current_spinbox.setMaximum(1e6)
            self.max_vertical_current_spinbox.setMaximum(1e6)
            self.max_horizontal_current_spinbox.setSingleStep(10.0)
            self.max_vertical_current_spinbox.setSingleStep(10.0)
            self.max_horizontal_current_spinbox.setValue(1000.0)
            self.max_vertical_current_spinbox.setValue(1000.0)
            self.initial_hkick_settings.setText("100")
            self.initial_vkick_settings.setText("100")
            self.choose_mode.setCurrentText(Mode.Orbit.value)
            self.choose_mode.setEnabled(False)
        else:
            self.correctors_label.setText("Correctors")
            self.initial_hkick_label.setText("Initial hkick")
            self.initial_vkick_label.setText("Initial vkick")
            self.current_label.setText("Max strength (gauss*m)")
            self.horizontal_current_label.setText("H:")
            self.vertical_current_label.setText(" V:")
            self.max_horizontal_current_spinbox.setMaximum(99.99)
            self.max_vertical_current_spinbox.setMaximum(99.99)
            self.max_horizontal_current_spinbox.setSingleStep(0.01)
            self.max_vertical_current_spinbox.setSingleStep(0.01)
            self.initial_hkick_settings.setText("0.01")
            self.initial_vkick_settings.setText("0.01")
            self.choose_mode.setEnabled(True)

    def _on_actuator_mode_changed(self, text):
        self.actuator_mode = ActuatorMode(text)
        self._refresh_corrector_list(preserve_selection=False)
        self._refresh_actuator_labels()

    def _current_measuring_mode(self):
        if self.mode == Mode.All:
            self.modes_to_do=[Mode.Orbit,Mode.Dispersion,Mode.Wakefield]
        else:
            self.modes_to_do=[self.mode]
        self.counter=0

    def _start_next_mode(self):
        initial_hkick=self._read_initial_kicks()
        #selected_correctors = self.interface.get_correctors()['names']
        #kicks=initial_hkick*np.ones(len(self.selected_correctors),dtype=float)
        if self.counter>=len(self.modes_to_do):
            self.__set_status_in_title("[Idle]")
            self.progressBar.setValue(100)
            return
        mode=self.modes_to_do[self.counter]
        self.current_mode=mode
        print(f"Currently at mode: {mode.name}")
        self.__set_status_in_title(f"[Running {mode.name} mode]")
        status = State(filename='machine_status')
        if self.actuator_mode != ActuatorMode.QM:
            status.push(self.interface)

        if mode==Mode.Dispersion:
            self.interface.change_energy()
            print("Energy changed")
        elif mode==Mode.Wakefield:
            self.interface.change_intensity()
            print("Intensity changed")
        self.progressBar.setValue(0)

    def _read_all_parameters(self,text):
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

    def _choose_the_correction_mode(self):
        data_mode=self.choose_mode.currentText()
        self.mode=Mode(data_mode)

    def __save_correctors_button_clicked(self):
        dir_name = self.working_directory_input.text()
        os.makedirs (dir_name, exist_ok=True)
        os.chdir (dir_name)
        selected_correctors = self.correctors_list.selectedItems()
        dir_name = self.working_directory_input.text() + '/correctors.txt'
        filename, _ = QFileDialog.getSaveFileName(None, "Save File", dir_name, "Text Files (*.txt)")
        if filename:
            with open(filename, 'w') as f:
                for item in selected_correctors:
                    f.write(f"{item.text()}\n")

    def __load_correctors_button_clicked(self):
        dir_name = self.working_directory_input.text() + '/correctors.txt'
        filename, _ = QFileDialog.getOpenFileName(None, "Open File", dir_name, "Text Files (*.txt)")
        if filename:
            with open(filename, 'r') as f:
                selected_correctors = [line.strip() for line in f]
        else:
            selected_correctors = self._available_actuators()

        self.correctors_list.clearSelection()
        for item in selected_correctors:
            items = self.correctors_list.findItems(item, Qt.MatchFlag.MatchExactly)
            for item in items:
                item.setSelected(True)

    def __clear_correctors_button_clicked(self):
        self.correctors_list.clearSelection()

    def __save_bpms_button_clicked(self):
        dir_name = self.working_directory_input.text()
        os.makedirs (dir_name, exist_ok=True)
        os.chdir (dir_name)
        selected_bpms = self.bpms_list.selectedItems()
        dir_name = self.working_directory_input.text() + '/bpms.txt'
        filename, _ = QFileDialog.getSaveFileName(None, "Save File", dir_name, "Text Files (*.txt)")
        if filename:
            with open(filename, 'w') as f:
                for item in selected_bpms:
                    f.write(f"{item.text()}\n")

    def __load_bpms_button_clicked(self):
        dir_name = self.working_directory_input.text() + '/bpms.txt'
        filename, _ = QFileDialog.getOpenFileName(None, "Open File", dir_name, "Text Files (*.txt)")
        if filename:
            with open(filename, 'r') as f:
                selected_bpms = [line.strip() for line in f]
        else:
            selected_bpms = self.interface.get_bpms()['names']

        self.bpms_list.clearSelection()
        for item in selected_bpms:
            items = self.bpms_list.findItems(item, Qt.MatchFlag.MatchExactly)
            for item in items:
                item.setSelected(True)

    def __clear_bpms_button_clicked(self):
        self.bpms_list.clearSelection()

    def _read_initial_kicks(self):
        text=self.initial_hkick_settings.text().strip()
        if not text:
            return 0.1
        try:
            return float(text)
        except ValueError as e:
            print(e)
            return 0.1

    def __start_button_clicked(self):
        dir_name = self.working_directory_input.text()
        os.makedirs (dir_name, exist_ok=True)
        os.chdir (dir_name)
        if self.actuator_mode == ActuatorMode.QM:
            if not hasattr(self.interface, "get_quadrupoles") or not hasattr(self.interface, "apply_qmag_xyroll"):
                QMessageBox.critical(self, "QM mode", "This interface does not support QM mode APIs.")
                return
            if len(self._available_actuators()) == 0:
                QMessageBox.critical(self, "QM mode", "No quadrupole list available in this interface.")
                return
        if self.actuator_mode == ActuatorMode.QM:
            save_machine_state(
                self.interface,
                filename='machine_status.pkl',
                include_correctors=False,
                include_icts=False,
                include_quadrupoles=False,
            )
        else:
            save_machine_state(
                self.interface,
                filename='machine_status.pkl',
                include_correctors=True,
                include_icts=True,
                include_quadrupoles=True,
            )

        self.progressBar.setValue(0)
        if self.thread and self.thread.isRunning():
            return  # already running

        selected_correctors = [item.text() for item in self.correctors_list.selectedItems()]
        self.selected_correctors = selected_correctors
        if not selected_correctors:
            for i in range(self.correctors_list.count()):
                self.correctors_list.item(i).setSelected(True)
            selected_correctors = self._available_actuators()

        # Always scan in beamline order from upstream to downstream.
        seq = self.interface.get_sequence()
        selected_correctors = sorted(selected_correctors, key=lambda n: seq.index(n) if n in seq else 10**9)

        selected_bpms = [item.text() for item in self.bpms_list.selectedItems()]
        self.selected_bpms = selected_bpms
        if not selected_bpms:
            for i in range(self.bpms_list.count()):
                self.bpms_list.item(i).setSelected(True)
            selected_bpms = self.interface.get_bpms()['names']
        selected_bpms = self._order_bpms(list(selected_bpms))

        self._current_measuring_mode()
        self._start_next_mode()

        # kicks = 0.1 * np.ones(len(selected_correctors), dtype=float)
        initial_hkick=float(self.initial_hkick_settings.text())
        initial_vkick=float(self.initial_vkick_settings.text())
        hkicks=initial_hkick*np.ones(len(selected_correctors), dtype=float)
        vkicks=initial_vkick*np.ones(len(selected_correctors), dtype=float)

        max_osc_h = self.horizontal_excursion_spinbox.value()
        max_osc_v = self.vertical_excursion_spinbox.value()
        max_curr_h = self.max_horizontal_current_spinbox.value()
        max_curr_v = self.max_vertical_current_spinbox.value()
        Niter = int(self.niter_number.text())
        print(f"Niter: {Niter}")

        self.thread = QThread()
        self.worker = Worker(self.interface, selected_correctors, selected_bpms, hkicks, vkicks, max_osc_h,
                             max_osc_v, max_curr_h, max_curr_v, Niter, dir_name, self.actuator_mode)
        self.worker.moveToThread(self.thread)

        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)

        # Cleanup after thread is done
        def clear_thread():
            try:
                if self.current_mode==Mode.Orbit:
                    print("Orbit mode active.")
                elif self.current_mode==Mode.Dispersion:
                    self.interface.reset_energy()
                elif self.current_mode==Mode.Wakefield:
                    self.interface.reset_intensity()
            except Exception as e:
                print(e)
            print("Restoring initial correctors' settings...")
            status = State(filename='machine_status')
            if self.actuator_mode != ActuatorMode.QM:
                status.push(self.interface)
            self.progressBar.setValue(100)
            self.thread = None
            self.worker = None
            self.counter+=1
            if self.counter< len(self.modes_to_do):
                self._start_next_mode()
                project_name = self.interface.get_name()
                time_str = datetime.now().strftime("%Y%m%d_%H%M%S")
                dir_name = f"~/flight-simulator-data/{project_name}_{time_str}"
                dir_name = os.path.expanduser(os.path.expandvars(dir_name))
                os.makedirs(dir_name, exist_ok=True)
                self.working_directory_input.setText(dir_name)

                initial_hkick = self._read_initial_kicks()
                hkicks = initial_hkick * np.ones(len(selected_correctors), dtype=float)
                vkicks = initial_vkick * np.ones(len(selected_correctors), dtype=float)
                max_osc_h = self.horizontal_excursion_spinbox.value()
                max_osc_v = self.vertical_excursion_spinbox.value()
                max_curr_h = self.max_horizontal_current_spinbox.value()
                max_curr_v = self.max_vertical_current_spinbox.value()
                Niter = int(self.niter_number.text())
                print(f"Niter: {Niter}")
                self.thread = QThread()
                self.worker = Worker(self.interface, selected_correctors, selected_bpms, hkicks, vkicks,
                                     max_osc_h, max_osc_v, max_curr_h, max_curr_v, Niter, dir_name, self.actuator_mode)
                self.worker.moveToThread(self.thread)

                self.thread.started.connect(self.worker.run)
                self.worker.finished.connect(self.thread.quit)
                self.worker.finished.connect(self.worker.deleteLater)
                self.thread.finished.connect(self.thread.deleteLater)
                self.thread.finished.connect(clear_thread)
                self.worker.plot_data.connect(self.__update_plot)
                self.worker.progress.connect(self._update_progress)
                self.thread.start()
            else:
                self.__set_status_in_title("[Idle]")

        self.thread.finished.connect(clear_thread)
        self.worker.plot_data.connect(self.__update_plot)
        self.worker.progress.connect(self._update_progress)

        self.thread.start()

    def __stop_button_clicked(self):
        if self.worker:
            self.__set_status_in_title("[Stopping...]")
            self.worker.stop()
            self.progressBar.setValue(0)
        self.__set_status_in_title("[Idle]")
        print('SysID stopped.')

    def __update_plot(self, Op, Diff_x, Err_x, Diff_y, Err_y, Diff_x_sub, Diff_y_sub, corrector):
        self.plot_widget.axes.clear()
        diff_len = len(Diff_x)
        scale = np.arange(diff_len)
        if isinstance(Op.get("names"), (list, np.ndarray)) and len(Op.get("names")) == diff_len:
            selected_bpms = [str(b) for b in Op.get("names")]
        else:
            selected_bpms = [item.text() for item in self.bpms_list.selectedItems()]
            if len(selected_bpms) != diff_len:
                selected_bpms = [f"BPM{i+1}" for i in range(diff_len)]
        self.plot_widget.axes.errorbar(scale, np.asarray(Diff_x).reshape(-1), yerr=np.asarray(Err_x).reshape(-1), lw=2, capsize=5, capthick=2, linestyle="-", color="red", label="X raw")
        self.plot_widget.axes.errorbar(scale, np.asarray(Diff_y).reshape(-1), yerr=np.asarray(Err_y).reshape(-1), lw=2, capsize=5, capthick=2, linestyle="-", color="blue", label="Y raw")
        if Diff_x_sub is not None:
            self.plot_widget.axes.plot(scale, np.asarray(Diff_x_sub).reshape(-1), linestyle="--", linewidth=2, color="red", label="X subtracted")
        if Diff_y_sub is not None:
            self.plot_widget.axes.plot(scale, np.asarray(Diff_y_sub).reshape(-1), linestyle="--", linewidth=2, color="blue", label="Y subtracted")
        self.plot_widget.axes.legend(loc='upper left')
        self.plot_widget.axes.set_xticks(scale)
        self.plot_widget.axes.set_xticklabels(selected_bpms,rotation=90,fontsize=8)
        self.plot_widget.axes.set_ylabel('Orbit [mm]')
        self.plot_widget.axes.set_title(f"Actuator '{corrector}'")
        self.plot_widget.axes.grid(color='#EEEEEE')
        self.plot_widget.draw()
        self.plot_widget.repaint()

    def _pick_and_load_data_dir(self):
        default_dir = os.path.join(self.cwd, "Data")
        os.makedirs(default_dir, exist_ok=True)
        folder = QFileDialog.getExistingDirectory(self, "Select data directory", default_dir)
        if not folder:
            return
        self.working_directory_input.setText(folder)


## MAIN
if __name__ == "__main__":
    app = QApplication(sys.argv)

    ## Select interface
    #from SelectInterface import InterfaceSelectionDialog
    import SelectInterface
    #dialog = InterfaceSelectionDialog()
    dialog = SelectInterface.choose_acc_and_interface()
    if dialog is None:
        print("Selection cancelled.")
        sys.exit(1)

    # if dialog.exec():
    #     print(f"Selected interface: {dialog.selected_interface_name}")
    #     I = dialog.selected_interface
    # else:
    #     print("Selection cancelled.")
    #     sys.exit(1)
    I=dialog
    project_name = I.get_name()
    print(f"Selected interface: {project_name}")

    ## Prepare project space
    #project_name = dialog.selected_interface_name
    time_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    dir_name = f"~/flight-simulator-data/{project_name}_{time_str}"
    dir_name = os.path.expanduser(os.path.expandvars(dir_name))

    ## Main Window
    window = MainWindow(interface=I, dir_name=dir_name)
    window.show()
    sys.exit(app.exec())
