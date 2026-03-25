from datetime import datetime
import numpy as np
from Backend.SaveOrLoad import SaveOrLoad
import time, sys, os,matplotlib
try:
    from PyQt6 import uic
    from PyQt6.QtWidgets import QApplication, QMainWindow, QFileDialog, QListWidget,QMessageBox
    from PyQt6.QtCore import Qt, QThread, QObject, pyqtSignal, pyqtSlot
    from PyQt6.QtTest import QTest
    pyqt_version = 6
except ImportError:
    from PyQt5 import uic
    from PyQt5.QtWidgets import QApplication, QMainWindow, QFileDialog, QListWidget,QMessageBox
    from PyQt5.QtCore import Qt, QThread, QObject, pyqtSignal, pyqtSlot
    from PyQt5.QtTest import QTest
    pyqt_version = 5
from enum import Enum
matplotlib.use('QtAgg')
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from Interfaces.interface_setup import INTERFACE_SETUP

class Mode(Enum):
    Orbit = "Orbit Correction"
    Dispersion = "Changed energy"
    Wakefield = "Changed intensity"
    All = "All modes at once"

class MatplotlibWidget(FigureCanvas):
    def __init__(self, parent=None, title='', orbit=None):
        fig = Figure(tight_layout=True)
        super().__init__(fig)
        self.setParent(parent)
        self.axes = fig.add_subplot(111)

class Worker(QObject):
    plot_data = pyqtSignal(dict, np.ndarray, np.ndarray, np.ndarray, np.ndarray, object,str)
    progress=pyqtSignal(int)
    finished = pyqtSignal()

    def __init__(self, interface, state, correctors, bpms, hkicks,vkicks, max_osc_h, max_osc_v, max_curr_h, max_curr_v, Niter,output_dir):
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
        self.running = False
        self.paused = False
        self.progress_value=0

    @pyqtSlot()
    def run(self):
        self.running = True
        self.paused = False
        self.progress_value=0
        I = self.interface
        vkicks = self.vkicks
        hkicks = self.hkicks
        pending_steps=0

        for iter in range(self.Niter):
            for corrector in self.correctors:
                filename_p=os.path.join(self.output_dir, f'DATA_{corrector}_p{iter:04d}.pkl')
                filename_m = os.path.join(self.output_dir, f'DATA_{corrector}_m{iter:04d}.pkl')
                if not (os.path.isfile(filename_p) and os.path.isfile(filename_m)):
                    pending_steps+=1 # if a file is missing, a step is added, if both are present, they are not considered worth iterating
        total_steps=max(pending_steps,1)


        def clamp(val, max_val):
            if max_val == 0.0:
                return val
            return max(-max_val, min(val, max_val))

        for iter in range(self.Niter):
            if not self.running: break
            if self.paused:      self._await_user()

            for icorr, corrector in enumerate(self.correctors):
                corr = I.get_correctors(corrector)
                if not self.running: break
                if self.paused:      self._await_user()

                if corrector in self.hcorrs:
                    max_curr=self.max_curr_h
                    kick=hkicks[icorr]
                elif corrector in self.vcorrs:
                    max_curr=self.max_curr_v
                    kick=vkicks[icorr]

                if not self.running: break
                if self.paused:      self._await_user()

                corr_changed = False

                filename_p=os.path.join(self.output_dir, f'DATA_{corrector}_p{iter:04d}.pkl')
                filename_m=os.path.join(self.output_dir, f'DATA_{corrector}_m{iter:04d}.pkl')

                corr_fully_measured=os.path.isfile(filename_p) and os.path.isfile(filename_m)
                measured_this_corr=False

                if not corr_fully_measured:
                    print(f"Corrector {corrector} '+' excitation...")
                if not os.path.isfile(filename_p):
                    print('corr[bds] =', corr['bdes'], ' also kick = ', kick) 
                    curr_p = corr['bdes'] + kick
                    if corrector in self.hcorrs:
                        curr_p = clamp(curr_p, self.max_curr_h)
                    else:
                        curr_p = clamp(curr_p, self.max_curr_v)
                    I.set_correctors(corrector, curr_p)
                    corr_changed = True

                    if not self.running: break
                    if self.paused:      self._await_user()
                    measured_this_corr=True
                    state_p=I.get_state()
                    state_p.save(filename=filename_p)
                else:
                    state_p=self.interface.get_state().__class__(filename=filename_p)
                Op = state_p.get_orbit(self.bpms)
                if not corr_fully_measured:
                    print(f"Corrector {corrector} '-' excitation...")
                if not os.path.isfile(filename_m):
                    curr_m = corr['bdes'] - kick
                    if corrector in self.hcorrs:
                        curr_m = clamp(curr_m, self.max_curr_h)
                    else:
                        curr_m = clamp(curr_m, self.max_curr_v)
                    I.set_correctors(corrector, curr_m)
                    corr_changed = True

                    if not self.running: break
                    if self.paused:      self._await_user()
                    measured_this_corr=True

                    state_m=I.get_state()
                    state_m.save(filename=filename_m)
                else:
                    state_m=self.interface.get_state().__class__(filename=filename_m)
                Om = state_m.get_orbit(self.bpms)

                if corr_changed:
                    I.set_correctors(corrector, corr['bdes'])

                if not self.running: break
                if self.paused:      self._await_user()

                Diff_x = (Op['x'] - Om['x']) / 2.0
                Diff_y = (Op['y'] - Om['y']) / 2.0
                nsamples = Op['stdx'].size
                Err_x = np.sqrt(np.square(Op['stdx']) + np.square(Om['stdx'])) / np.sqrt(nsamples)
                Err_y = np.sqrt(np.square(Op['stdy']) + np.square(Om['stdy'])) / np.sqrt(nsamples)
                if measured_this_corr:
                    self.plot_data.emit(Op, Diff_x, Err_x, Diff_y, Err_y, self.bpms, corrector)
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
                if measured_this_corr:
                    t0=time.monotonic() #saves current time, but not a system time, it's for measuring time difference
                    while self.running and (time.monotonic() -t0) <1:
                        time.sleep(0.05)

        self.running = False
        self.finished.emit()

    def pause(self):
        self.paused = True

    def unpause(self):
        self.paused = False

    def stop(self):
        self.running = False
        self.paused = False

    def _await_user(self):
        reminder = '  -> [ SCAN PAUSED ] Press "resume" button to continue'
        while self.paused and self.running:
            for j in range(4):
                print(f"{reminder}{j * '.'}", end='\r')
                QTest.qWait(500)
                if not self.paused or not self.running:
                    break

class MainWindow(QMainWindow, SaveOrLoad):
    def __set_status_in_title(self, status):
        self.setWindowTitle("SYSID - " + self.interface.__class__.__name__ + " " + status)

    @pyqtSlot(int)
    def _update_progress(self,value):
        self.progressBar.setValue(value)

    def _update_folder_path(self):
        base = os.path.expanduser(os.path.expandvars("~/flight-simulator-data"))
        project_name=self.interface.get_name()
        mode=self.mode
        time_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        folder_path=os.path.join(base,f"{project_name}_{time_str}_{mode.name}")
        self.working_directory_input.setText(folder_path)

    def __init__(self, interface, dir_name):
        super().__init__()

        # SysID
        self.worker = None
        self.thread = None
        self._activate_mode=None
        self.stop_requested = False
        self.cwd = os.getcwd()
        self.interface = interface
        bpms_list = interface.get_bpms()['names']
        correctors = self.interface.get_correctors()
        correctors_list = correctors['names']

        if correctors_list is not None:
            hcorrs = self.interface.get_hcorrectors_names()
            vcorrs = self.interface.get_vcorrectors_names()
            hcorr_indexes = np.array([index for index, string in enumerate(correctors_list) if string in hcorrs])
            vcorr_indexes = np.array([index for index, string in enumerate(correctors_list) if string in vcorrs])
            def clean_array(a):
                a = np.array([0 if x is None else x for x in a], dtype=float)
                a[np.isnan(a)] = 0
                return a
            max_curr_h = 1.15 * np.max(np.abs(clean_array(np.array(correctors['bdes'][hcorr_indexes]))))
            max_curr_v = 1.15 * np.max(np.abs(clean_array(np.array(correctors['bdes'][vcorr_indexes]))))

        # Load the interface
        uic.loadUi("UI files/SysID_GUI.ui", self)

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
        self.pause_button.clicked.connect(self.__pause_button_clicked)
        self.resume_button.clicked.connect(self.__unpause_button_clicked)
        self.mode=Mode.Orbit
        self._update_folder_path()
        self.choose_mode.currentTextChanged.connect(self._choose_the_correction_mode)
        # self.initial_hkick_settings.setText("0.01")
        # self.initial_vkick_settings.setText("0.01")

        #for FACET2:
        # self.initial_hkick_settings.setText("0.0001")
        # self.initial_vkick_settings.setText("0.0001")

        self.correctors_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.correctors_list.insertItems(0, correctors_list)
        self.bpms_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.bpms_list.insertItems(0, bpms_list)
        self.working_directory_input.setText(dir_name+'_Orbit')
        self.max_horizontal_current_spinbox.setValue(max_curr_h)
        self.max_horizontal_current_spinbox.setSingleStep(0.01)
        self.max_vertical_current_spinbox.setValue(max_curr_v)
        self.max_vertical_current_spinbox.setSingleStep(0.01)
        self.horizontal_excursion_spinbox.setValue(0.5)
        self.horizontal_excursion_spinbox.setSingleStep(0.1)
        self.vertical_excursion_spinbox.setValue(0.5)
        self.vertical_excursion_spinbox.setSingleStep(0.1)

        self.working_directory_dialog.clicked.connect(self._pick_and_load_data_dir)
        self.__set_status_in_title("[Idle]")
        interface_name=interface.get_name()
        self.modes_to_do=[]
        self.counter=0
        self.current_mode=None
        units_settings, sysid_kick, bpm_unit, corrs_unit=self._get_interface_units()
        self.sysid_kick=sysid_kick
        self.bpm_unit=bpm_unit
        self.corrs_unit=corrs_unit
        self.initial_hkick_settings.setText(str(self.sysid_kick))
        self.initial_vkick_settings.setText(str(self.sysid_kick))
        self._set_directory_edit_enabled(True)

    def _set_directory_edit_enabled(self, enabled):
        self.working_directory_input.setEnabled(enabled)
        self.working_directory_dialog.setEnabled(enabled)

    def _current_measuring_mode(self):
        if self.mode == Mode.All:
            self.modes_to_do=[Mode.Orbit,Mode.Dispersion,Mode.Wakefield]
        else:
            self.modes_to_do=[self.mode]
        self.counter=0

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

    def _start_next_mode(self):
        #initial_hkick=self._read_initial_kicks()
        #selected_correctors = self.interface.get_correctors()['names']
        #kicks=initial_hkick*np.ones(len(self.selected_correctors),dtype=float)
        if self.counter>=len(self.modes_to_do):
            self.__set_status_in_title("[Idle]")
            self.progressBar.setValue(100)
            return
        mode=self.modes_to_do[self.counter]
        self.current_mode=mode
        dir_name=self.mode_dirs[mode]
        os.chdir(dir_name)
        self.working_directory_input.setText(dir_name)

        print(f"Currently at mode: {mode.name}")
        self.__set_status_in_title(f"[Running {mode.name} mode]")
        self.progressBar.setValue(0)
        machine_state=self.interface.get_state().__class__(filename=os.path.join(dir_name,'machine_status.pkl'))
        self.interface.restore_correctors_state(machine_state)

        if mode==Mode.Dispersion:
            self.interface.change_energy()
            print("Energy changed")
        elif mode==Mode.Wakefield:
            self.interface.change_intensity()
            print("Intensity changed")

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
        self._update_folder_path()

    def __save_correctors_button_clicked(self):
        self._saving_func(elements_list=self.correctors_list, filename="correctors.txt", saving_name="Save Correctors", base_dir=self.working_directory_input.text())

    def __load_correctors_button_clicked(self):
        self._loading_func(elements_list=self.correctors_list, filename="correctors.txt", loading_name="Load Correctors", base_dir=self.working_directory_input.text())

    def __clear_correctors_button_clicked(self):
        self.correctors_list.clearSelection()

    def __save_bpms_button_clicked(self):
        self._saving_func(elements_list=self.bpms_list, filename="bpms.txt", saving_name="Save BPMs", base_dir=self.working_directory_input.text())

    def __load_bpms_button_clicked(self):
        self._loading_func(elements_list=self.bpms_list, filename="bpms.txt", loading_name="Load BPMs", base_dir=self.working_directory_input.text())

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

    def _sort_elements(self, unsorted_names, which='corrs'):
        """
        sorts a list of correctors or BPMs in machine (s) order
        meant to handle the selection-order-sorted results of QTableWidget.SelectedItems()
        """
        sorted_names = []
        reference_namelist = self.interface.corrs if (which == 'corrs') else self.interface.bpms
        for name in reference_namelist:
            if name in unsorted_names: sorted_names.append(str(name))
        return sorted_names

    def _read_filenames(self,basedir,filename):
        path=os.path.join(basedir,filename)
        if not os.path.isfile(path):
            return []
        with open(path,'r') as f:
            return [line.strip() for line in f if line.strip()]

    def _is_a_valid_directory_to_resume(self,base_dir):
        if not base_dir:
            return False
        base_dir=os.path.expanduser(os.path.expandvars(base_dir)) # environmental names, like $HOME
        return (
            os.path.isdir(base_dir) # checks if it's a directory, not a file for example
            and os.path.isfile(os.path.join(base_dir,'machine_status.pkl')) # is there such file
            and os.path.isfile(os.path.join(base_dir,'correctors.txt'))
            and os.path.isfile(os.path.join(base_dir, 'bpms.txt'))
        )

    def _save_names_if_missing(self,base_dir,filename,names):
        path=os.path.join(base_dir,filename)
        if os.path.isfile(path):
            return
        with open(path,'w') as f:
            for item in names:
                f.write(f"{item}\n")

    def __start_button_clicked(self):
        self.progressBar.setValue(0)
        self._set_directory_edit_enabled(False)
        self.stop_requested=False
        if self.thread and self.thread.isRunning():
            return  # already running

        selected_correctors = self._sort_elements([item.text() for item in self.correctors_list.selectedItems()], which='corrs')

        if not selected_correctors:
            for i in range(self.correctors_list.count()):
                self.correctors_list.item(i).setSelected(True)
            selected_correctors = self.interface.get_correctors()['names']

        selected_bpms = self._sort_elements([item.text() for item in self.bpms_list.selectedItems()], which='bpms')
        self.selected_bpms = selected_bpms
        if not selected_bpms:
            for i in range(self.bpms_list.count()):
                self.bpms_list.item(i).setSelected(True)
            selected_bpms = self.interface.get_bpms()['names']

        resume_directory=os.path.expanduser(os.path.expandvars(self.working_directory_input.text()))
        is_valid_resume_directory=self.mode!=Mode.All and self._is_a_valid_directory_to_resume(resume_directory)
        if is_valid_resume_directory:
            saved_correctors=self._read_filenames(resume_directory,'correctors.txt')
            saved_bpms=self._read_filenames(resume_directory,'bpms.txt')
            if saved_correctors:
                selected_correctors=self._sort_elements(saved_correctors,'corrs')
            if saved_bpms:
                selected_bpms=self._sort_elements(saved_bpms,'bpms')
            self.selected_bpms=selected_bpms
            QMessageBox.information(self,"Resuming SysID", "Resuming SysID from a given directory")
        self._current_measuring_mode()

        self.mode_dirs={}
        project_name = self.interface.get_name()
        base = os.path.expanduser(os.path.expandvars("~/flight-simulator-data"))

        for mode in self.modes_to_do:
            if len(self.modes_to_do)==1:
                d=resume_directory
            else:
                time_str=datetime.now().strftime("%Y%m%d_%H%M%S")
                d = os.path.join(base, f"{project_name}_{time_str}_{mode.name}")
            os.makedirs(d, exist_ok=True)
            self.mode_dirs[mode] = d

            self._save_names_if_missing(d,'correctors.txt',selected_correctors)
            self._save_names_if_missing(d,'bpms.txt',selected_bpms)


        machine_state=self.interface.get_state()
        for mode,d in self.mode_dirs.items():
            machine_status=os.path.join(d,'machine_status.pkl')
            if not os.path.isfile(machine_status):
                machine_state.save(filename=machine_status)

        self.counter=0
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
        out_dir=self.mode_dirs[self.current_mode]
        self.worker = Worker(self.interface, None, selected_correctors, selected_bpms, hkicks,vkicks ,max_osc_h, max_osc_v, max_curr_h, max_curr_v, Niter,out_dir)
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
            #self.S.load('machine_status')
            current_dir=self.mode_dirs[self.current_mode]
            machine_state=self.interface.get_state().__class__(filename=os.path.join(current_dir,"machine_status.pkl"))
            self.interface.restore_correctors_state(machine_state)
            self.progressBar.setValue(100)
            self.thread = None
            self.worker = None
            self.counter+=1
            if self.stop_requested:
                self._set_directory_edit_enabled(True)
                self.__set_status_in_title("[Idle]")
                return
            if self.counter< len(self.modes_to_do):
                self._start_next_mode()
                initial_hkick = float(self.initial_hkick_settings.text())
                initial_vkick=float(self.initial_vkick_settings.text())
                hkicks = initial_hkick * np.ones(len(selected_correctors), dtype=float)
                vkicks = initial_vkick * np.ones(len(selected_correctors), dtype=float)
                max_osc_h = self.horizontal_excursion_spinbox.value()
                max_osc_v = self.vertical_excursion_spinbox.value()
                max_curr_h = self.max_horizontal_current_spinbox.value()
                max_curr_v = self.max_vertical_current_spinbox.value()
                Niter = int(self.niter_number.text())
                print(f"Niter: {Niter}")
                self.thread = QThread()
                out_dir = self.mode_dirs[self.current_mode]
                self.worker = Worker(self.interface, None, selected_correctors, selected_bpms, hkicks, vkicks,max_osc_h,max_osc_v, max_curr_h, max_curr_v, Niter,out_dir)
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
                self._set_directory_edit_enabled(True)
                self.__set_status_in_title("[Idle]")

        self.thread.finished.connect(clear_thread)
        self.worker.plot_data.connect(self.__update_plot)
        self.worker.progress.connect(self._update_progress)

        self.thread.start()

    def __stop_button_clicked(self):
        self.stop_requested = True
        if self.worker:
            self.__set_status_in_title("[Stopping...]")
            self.worker.stop()
            self.progressBar.setValue(0)
        self.__set_status_in_title("[Idle]")
        print('SysID stopped.')

    def __pause_button_clicked(self):
        if self.worker:
            self.__set_status_in_title("[PAUSED]")
            self.worker.pause()

    def __unpause_button_clicked(self):
        if self.worker:
            mode = self.modes_to_do[self.counter]
            self.__set_status_in_title(f"[Running {mode.name} mode]")
            self.worker.unpause()

    def __update_plot(self, Op, Diff_x, Err_x, Diff_y, Err_y, bpm_names,corrector):
        Diff_x=np.asarray(Diff_x).ravel()
        Diff_y=np.asarray(Diff_y).ravel()
        Err_x=np.asarray(Err_x).ravel()
        Err_y=np.asarray(Err_y).ravel()
        bpm_names=[str(x) for x in bpm_names]

        self.plot_widget.axes.clear()
        n=min(len(Diff_x),len(Diff_y),len(Err_x),len(Err_y))
        scale=np.arange(n) # np.arange(start,stop,step) -> 0,n,1
        self.plot_widget.axes.errorbar(scale, Diff_x, yerr=Err_x, lw=2, capsize=5, capthick=2, label="X")
        self.plot_widget.axes.errorbar(scale, Diff_y, yerr=Err_y, lw=2, capsize=5, capthick=2, label="Y")
        self.plot_widget.axes.legend(loc='upper left')
        self.plot_widget.axes.set_xticks(scale)
        self.plot_widget.axes.set_xticklabels(bpm_names[:n],rotation=90,fontsize=8)
        self.plot_widget.axes.set_ylabel(f'Orbit [{self.bpm_unit}]')
        self.plot_widget.axes.set_title(f"Corrector '{corrector}'")
        self.plot_widget.axes.grid(color='#EEEEEE')
        self.plot_widget.draw()
        self.plot_widget.repaint()

    def _pick_and_load_data_dir(self):
        default_dir = os.path.join(self.cwd)
        os.makedirs(default_dir, exist_ok=True)
        folder = QFileDialog.getExistingDirectory(self, "Select data directory", default_dir)
        if not folder:
            return
        self.working_directory_input.setText(folder)

        if not self._is_a_valid_directory_to_resume(folder):
            return

        self._loading_func(
            elements_list=self.correctors_list,
            filename="correctors.txt",
            loading_name="Load Correctors",
            use_dialog=False,
            base_dir=folder,
        )
        self._loading_func(
            elements_list=self.bpms_list,
            filename="bpms.txt",
            loading_name="Load BPMs",
            use_dialog=False,
            base_dir=folder,
        )
        QMessageBox.information(self,"Directory loaded","Loaded directory data to be resumed.")

## MAIN
app = QApplication(sys.argv)

## Select interface
#from SelectInterface import InterfaceSelectionDialog
from Backend import SelectInterface

#dialog = InterfaceSelectionDialog()
dialog = SelectInterface.choose_acc_and_interface()
if dialog is None:
    print("Selection cancelled.")
    sys.exit(1)

I=dialog
project_name=I.get_name()
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
