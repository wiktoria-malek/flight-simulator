from State import State
from datetime import datetime
from functools import partial
from collections import deque

import numpy as np
import threading
import signal
import sys
import os

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QListWidget, QPushButton, QSpinBox, QDoubleSpinBox,
    QComboBox, QCheckBox, QAbstractItemView, QFileDialog, QSizePolicy
)
from PyQt6.QtCore import Qt, QThread, QTimer, QObject, pyqtSignal

import matplotlib
matplotlib.use('QtAgg')

import matplotlib.pyplot as plt

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

class MatplotlibWidget(FigureCanvas):
    def __init__(self, parent=None, title='', orbit=None):
        fig = Figure(tight_layout=True)
        super().__init__(fig)
        self.setParent(parent)
        self.axes = fig.add_subplot(111)

class Worker(QObject):
    plot_data = pyqtSignal(dict, np.ndarray, np.ndarray, np.ndarray, np.ndarray, str)
    finished = pyqtSignal()

    def __init__(self, interface, state, correctors, bpms, kicks, max_osc_h, max_osc_v, max_curr_h, max_curr_v, Niter, running_flag):
        super().__init__()
        self.interface = interface
        self.S = state
        self.correctors = correctors
        self.bpms = bpms
        self.kicks = kicks
        self.max_osc_h = max_osc_h
        self.max_osc_v = max_osc_v
        self.max_curr_h = max_curr_h
        self.max_curr_v = max_curr_v
        self.Niter = Niter
        self.running = running_flag

    def run(self):
        I = self.interface
        S = self.S
        kicks = self.kicks

        def clamp(val, max_val):
            if max_val == 0.0:
                return val
            return max(-max_val, min(val, max_val))

        for iter in range(self.Niter):
            if not self.running.is_set():
                break
            for icorr, corrector in enumerate(self.correctors):
                if not self.running.is_set():
                    break

                corr = S.get_correctors(corrector)
                kick = kicks[icorr]

                print(f"Corrector {corrector} '+' excitation...")
                curr_p = corr['bdes'] + kick
                if corrector in S.get_hcorrectors_names():
                    curr_p = clamp(curr_p, self.max_curr_h)
                else:
                    curr_p = clamp(curr_p, self.max_curr_v)
                I.push(corrector, curr_p)
                S.pull(I)
                S.save(filename=f'DATA_{corrector}_p{iter:04d}.pkl')
                Op = S.get_orbit(self.bpms)

                print(f"Corrector {corrector} '-' excitation...")
                curr_m = corr['bdes'] - kick
                if corrector in S.get_hcorrectors_names():
                    curr_m = clamp(curr_m, self.max_curr_h)
                else:
                    curr_m = clamp(curr_m, self.max_curr_v)
                S.pull(I)
                S.save(filename=f'DATA_{corrector}_m{iter:04d}.pkl')
                Om = S.get_orbit(self.bpms)

                I.push(corrector, corr['bdes'])

                Diff_x = (Op['x'] - Om['x']) / 2.0
                Diff_y = (Op['y'] - Om['y']) / 2.0
                nsamples = Op['stdx'].size
                Err_x = np.sqrt(np.square(Op['stdx']) + np.square(Om['stdx'])) / np.sqrt(nsamples)
                Err_y = np.sqrt(np.square(Op['stdy']) + np.square(Om['stdy'])) / np.sqrt(nsamples)

                if corrector in S.get_hcorrectors_names():
                    Diff_x_clean = Diff_x[~np.isnan(Diff_x)]
                    kicks[icorr] *= self.max_osc_h / np.max(np.abs(Diff_x_clean))
                else:
                    Diff_y_clean = Diff_y[~np.isnan(Diff_y)]
                    kicks[icorr] *= self.max_osc_v / np.max(np.abs(Diff_y_clean))

                kicks[icorr] = 0.8 * kicks[icorr] + 0.2 * kick
                np.savetxt('kicks.txt', kicks, delimiter='\n')

                self.plot_data.emit(Op, Diff_x, Err_x, Diff_y, Err_y, corrector)

        self.finished.emit()

class MainWindow(QMainWindow):
    def __set_status_in_title(self, status):
        self.setWindowTitle("SYSID - " + self.interface.__class__.__name__ + " " + status)

    def __init__(self, interface, dir_name):
        super().__init__()

        self.cwd = os.getcwd()
        self.interface = interface
        bpms_list = interface.get_bpms()['names']
        correctors = I.get_correctors()
        correctors_list = correctors['names']

        if correctors_list is not None:
            hcorrs = I.get_hcorrectors_names()
            vcorrs = I.get_vcorrectors_names()
            hcorr_indexes = np.array([index for index, string in enumerate(correctors_list) if string in hcorrs])
            vcorr_indexes = np.array([index for index, string in enumerate(correctors_list) if string in vcorrs])
            max_curr_h = 1.15 * np.max(np.abs(np.array(correctors['bdes'])[hcorr_indexes]))
            max_curr_v = 1.15 * np.max(np.abs(np.array(correctors['bdes'])[vcorr_indexes]))

        self.running = threading.Event()
        self.worker_thread = None

        self.__set_status_in_title("[Idle]")
        self.setGeometry(100, 100, 600, 700)

        main_widget = QWidget()
        self.setCentralWidget(main_widget)

        main_layout = QVBoxLayout(main_widget)
        top_layout = QHBoxLayout()
        main_layout.addLayout(top_layout)

        # Left side layout
        left_layout = QVBoxLayout()
        top_layout.addLayout(left_layout,1)

        # Correctors list
        correctors_layout = QHBoxLayout()
        left_layout.addLayout(correctors_layout)

        correctors_label = QLabel("Correctors:")
        correctors_layout.addWidget(correctors_label)

        self.correctors_list = QListWidget()
        self.correctors_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.correctors_list.insertItems(0, correctors_list)
        left_layout.addWidget(self.correctors_list)

        # Save / Load / Clear correctors buttons
        button_layout = QHBoxLayout()
        left_layout.addLayout(button_layout)

        self.save_correctors_button = QPushButton("Save As..")
        self.save_correctors_button.clicked.connect(self.__save_correctors_button_clicked)
        button_layout.addWidget(self.save_correctors_button)

        self.load_correctors_button = QPushButton("Load..")
        self.load_correctors_button.clicked.connect(self.__load_correctors_button_clicked)
        button_layout.addWidget(self.load_correctors_button)

        self.clear_correctors_button = QPushButton("Clear")
        self.clear_correctors_button.clicked.connect(self.__clear_correctors_button_clicked)
        button_layout.addWidget(self.clear_correctors_button)

        # Middle layout
        middle_layout = QVBoxLayout()
        top_layout.addLayout(middle_layout)

        # BPMs list
        bpms_layout = QHBoxLayout()
        left_layout.addLayout(bpms_layout)

        bpms_label = QLabel("BPMs:")
        bpms_layout.addWidget(bpms_label)

        self.bpms_list = QListWidget()
        self.bpms_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.bpms_list.insertItems(0, bpms_list)
        left_layout.addWidget(self.bpms_list)

        # Save / Load / Clear bpms buttons
        button_layout = QHBoxLayout()
        left_layout.addLayout(button_layout)

        self.save_bpms_button = QPushButton("Save As..")
        self.save_bpms_button.clicked.connect(self.__save_bpms_button_clicked)
        button_layout.addWidget(self.save_bpms_button)

        self.load_bpms_button = QPushButton("Load..")
        self.load_bpms_button.clicked.connect(self.__load_bpms_button_clicked)
        button_layout.addWidget(self.load_bpms_button)

        self.clear_bpms_button = QPushButton("Clear")
        self.clear_bpms_button.clicked.connect(self.__clear_bpms_button_clicked)
        button_layout.addWidget(self.clear_bpms_button)

        # Right side layout
        right_layout = QVBoxLayout()
        top_layout.addLayout(right_layout,2)

        # Info section
        info_layout = QVBoxLayout()
        right_layout.addLayout(info_layout)

        self.info_label = QLabel("Data Storage:")
        self.info_label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        info_layout.addWidget(self.info_label)

        self.working_directory_input = QLineEdit("Working directory:")
        self.working_directory_input.setText(dir_name)
        info_layout.addWidget(self.working_directory_input)

        # Options sectionQFileDialog
        options_layout = QVBoxLayout()
        right_layout.addLayout(options_layout)

        self.options_label = QLabel("Options")
        self.options_label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        options_layout.addWidget(self.options_label)

        cycle_mode_layout = QHBoxLayout()
        options_layout.addLayout(cycle_mode_layout)

        self.cycle_mode_label = QLabel("Cycle mode:")
        cycle_mode_layout.addWidget(self.cycle_mode_label)

        self.cycle_mode_combobox = QComboBox()
        self.cycle_mode_combobox.addItems(["Repeat all"])
        cycle_mode_layout.addWidget(self.cycle_mode_combobox)

        # Correctors Current
        current_layout = QHBoxLayout()
        options_layout.addLayout(current_layout)

        self.current_label = QLabel("Max current:")
        current_layout.addWidget(self.current_label)
        current_layout.addStretch()  # This stretch  expands to fill space

        self.horizontal_current_label = QLabel("H:")
        current_layout.addWidget(self.horizontal_current_label)

        self.max_horizontal_current_spinbox = QDoubleSpinBox()
        self.max_horizontal_current_spinbox.setValue(max_curr_h)
        self.max_horizontal_current_spinbox.setSingleStep(0.01)
        self.max_horizontal_current_spinbox.setSuffix(" A")
        current_layout.addWidget(self.max_horizontal_current_spinbox)

        self.vertical_current_label = QLabel("V:")
        current_layout.addWidget(self.vertical_current_label)

        self.max_vertical_current_spinbox = QDoubleSpinBox()
        self.max_vertical_current_spinbox.setValue(max_curr_v)
        self.max_vertical_current_spinbox.setSingleStep(0.01)
        self.max_vertical_current_spinbox.setSuffix(" A")
        current_layout.addWidget(self.max_vertical_current_spinbox)

        # Orbit Excursion
        excursion_layout = QHBoxLayout()
        options_layout.addLayout(excursion_layout)

        self.excursion_label = QLabel("Orbit excursion:")
        excursion_layout.addWidget(self.excursion_label)
        excursion_layout.addStretch()  # This stretch  expands to fill space

        self.horizontal_excursion_label = QLabel("H:")
        excursion_layout.addWidget(self.horizontal_excursion_label)

        self.horizontal_excursion_spinbox = QDoubleSpinBox()
        self.horizontal_excursion_spinbox.setValue(1.0)
        self.horizontal_excursion_spinbox.setSingleStep(0.1)
        self.horizontal_excursion_spinbox.setSuffix(" mm")
        excursion_layout.addWidget(self.horizontal_excursion_spinbox)

        self.vertical_excursion_label = QLabel("V:")
        excursion_layout.addWidget(self.vertical_excursion_label)

        self.vertical_excursion_spinbox = QDoubleSpinBox()
        self.vertical_excursion_spinbox.setValue(1.0)
        self.vertical_excursion_spinbox.setSingleStep(0.1)
        self.vertical_excursion_spinbox.setSuffix(" mm")
        excursion_layout.addWidget(self.vertical_excursion_spinbox)

        # Plot
        self.plot = MatplotlibWidget(self)
        options_layout.addWidget(self.plot)

        # Plot queue and timer for smoother updates
        self._plot_queue = deque()
        self._plot_timer = QTimer()
        self._plot_timer.timeout.connect(self.__flush_plot_queue)
        self._plot_timer.start(200)  # Adjust this interval as needed

        # Start and Stop buttons
        buttons_layout = QHBoxLayout()
        main_layout.addLayout(buttons_layout)

        self.start_button = QPushButton("START")
        self.start_button.setStyleSheet("background-color: green; color: white;")
        self.start_button.clicked.connect(self.__start_button_clicked)
        buttons_layout.addWidget(self.start_button)

        self.stop_button = QPushButton("STOP")
        self.stop_button.setStyleSheet("background-color: red; color: white;")
        self.stop_button.clicked.connect(self.__stop_button_clicked)
        buttons_layout.addWidget(self.stop_button)

    def __save_correctors_button_clicked(self):
        dir_name = self.cwd + '/' + self.working_directory_input.text()
        os.makedirs (dir_name, exist_ok=True)
        os.chdir (dir_name)
        selected_correctors = self.correctors_list.selectedItems()
        dir_name = self.cwd + '/' + self.working_directory_input.text() + '/correctors.txt'
        filename, _ = QFileDialog.getSaveFileName(None, "Save File", dir_name, "Text Files (*.txt)")
        if filename:
            with open(filename, 'w') as f:
                for item in selected_correctors:
                    f.write(f"{item.text()}\n")

    def __load_correctors_button_clicked(self):
        dir_name = self.cwd + '/' + self.working_directory_input.text() + '/correctors.txt'
        filename, _ = QFileDialog.getOpenFileName(None, "Open File", dir_name, "Text Files (*.txt)")
        if filename:
            with open(filename, 'r') as f:
                selected_correctors = [line.strip() for line in f]
        else:
            selected_correctors = self.interface.get_correctors()['names']

        self.correctors_list.clearSelection()
        for item in selected_correctors:
            items = self.correctors_list.findItems(item, Qt.MatchFlag.MatchExactly)
            for item in items:
                item.setSelected(True)

    def __clear_correctors_button_clicked(self):
        self.correctors_list.clearSelection()

    def __save_bpms_button_clicked(self):
        dir_name = self.cwd + '/' + self.working_directory_input.text()
        os.makedirs (dir_name, exist_ok=True)
        os.chdir (dir_name)
        selected_bpms = self.bpms_list.selectedItems()
        dir_name = self.cwd + '/' + self.working_directory_input.text() + '/bpms.txt'
        filename, _ = QFileDialog.getSaveFileName(None, "Save File", dir_name, "Text Files (*.txt)")
        if filename:
            with open(filename, 'w') as f:
                for item in selected_bpms:
                    f.write(f"{item.text()}\n")

    def __load_bpms_button_clicked(self):
        dir_name = self.cwd + '/' + self.working_directory_input.text() + '/bpms.txt'
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

    def __start_button_clicked(self):
        if self.worker_thread and self.worker_thread.isRunning():
            return  # already running

        self.__set_status_in_title("[Running...]")
        self.running.set()

        dir_name = self.cwd + '/' + self.working_directory_input.text()
        os.makedirs(dir_name, exist_ok=True)
        os.chdir(dir_name)

        selected_correctors = [item.text() for item in self.correctors_list.selectedItems()]
        if not selected_correctors:
            for i in range(self.correctors_list.count()):
                self.correctors_list.item(i).setSelected(True)
            selected_correctors = self.interface.get_correctors()['names']

        selected_bpms = [item.text() for item in self.bpms_list.selectedItems()]
        if not selected_bpms:
            for i in range(self.bpms_list.count()):
                self.bpms_list.item(i).setSelected(True)
            selected_bpms = self.interface.get_bpms()['names']

        S = State(interface=self.interface)
        S.save(basename='machine_status')

        kicks = 0.1 * np.ones(len(selected_correctors), dtype=float)
        max_osc_h = self.horizontal_excursion_spinbox.value()
        max_osc_v = self.vertical_excursion_spinbox.value()
        max_curr_h = self.max_horizontal_current_spinbox.value()
        max_curr_v = self.max_vertical_current_spinbox.value()
        Niter = 3

        self.worker_thread = QThread()
        self.worker = Worker(self.interface, S, selected_correctors, selected_bpms, kicks, max_osc_h, max_osc_v, max_curr_h, max_curr_v, Niter, self.running)
        self.worker.moveToThread(self.worker_thread)

        self.worker_thread.started.connect(self.worker.run)
        self.worker.plot_data.connect(self.__update_plot)
        self.worker.finished.connect(self.worker_thread.quit)
        self.worker_thread.finished.connect(self.worker_thread.deleteLater)
        self.worker.finished.connect(lambda: self.__set_status_in_title("[Idle]"))
        self.worker_thread.finished.connect(lambda: setattr(self, 'worker_thread', None))

        self.worker_thread.start()

    def __update_plot(self, Op, Diff_x, Err_x, Diff_y, Err_y, corrector):
        self._plot_queue.append((Op, Diff_x, Err_x, Diff_y, Err_y, corrector))

    def __flush_plot_queue(self):
        if not self._plot_queue:
            return
        Op, Diff_x, Err_x, Diff_y, Err_y, corrector = self._plot_queue.popleft()

        self.plot.axes.clear()
        self.plot.axes.errorbar(range(Op['nbpms']), Diff_x, yerr=Err_x, lw=2, capsize=5, capthick=2, label="X")
        self.plot.axes.errorbar(range(Op['nbpms']), Diff_y, yerr=Err_y, lw=2, capsize=5, capthick=2, label="Y")
        self.plot.axes.legend(loc='upper left')
        self.plot.axes.set_xlabel('Bpm [#]')
        self.plot.axes.set_ylabel('Orbit [mm]')
        self.plot.axes.set_title(f"Corrector '{corrector}'")
        self.plot.draw()
        self.plot.flush_events()
        self.plot.update()
        self.plot.repaint()

    def __stop_button_clicked(self):
        if self.worker_thread and self.worker_thread.isRunning():
            self.__set_status_in_title("[Stopping...]")
            self.running.clear()

## MAIN
app = QApplication(sys.argv)

## Select interface
from SelectInterface import InterfaceSelectionDialog
dialog = InterfaceSelectionDialog()
if dialog.exec():
    print(f"Selected interface: {dialog.selected_interface_name}")
    I = dialog.selected_interface
else:
    print("Selection cancelled.")
    sys.exit(1)

## Prepare project space
project_name = 'new_SYSID'
time_str = datetime.now().strftime("%Y%m%d_%H%M%S")
dir_name = f"Data/{project_name}_{time_str}"

## Main Window
window = MainWindow(I, dir_name)
window.show()
sys.exit(app.exec())
