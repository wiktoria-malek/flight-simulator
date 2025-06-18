# from InterfaceATF2_Linac import InterfaceATF2_Linac
from InterfaceATF2_Ext_RFTrack import InterfaceATF2_Ext_RFTrack
from State import State
from datetime import datetime
from functools import partial

import numpy as np
import signal
import sys
import os

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QListWidget, QPushButton, QSpinBox, QDoubleSpinBox,
    QComboBox, QCheckBox, QAbstractItemView, QFileDialog
)
from PyQt6.QtCore import Qt

import matplotlib
matplotlib.use('Qt5Agg')

import matplotlib.pyplot as plt

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

class MatplotlibWidget(FigureCanvas):
    def __init__(self, parent=None, title='', orbit=None):
        self.fig = Figure()
        super().__init__(self.fig)
        self.axes = self.fig.add_subplot(111)
        # self.plot_orbit(orbit)
        
    def plot_orbit(self,orbit):
        errx = orbit['stdx'] / np.sqrt(orbit['stdx'].size)
        erry = orbit['stdy'] / np.sqrt(orbit['stdy'].size)
        self.plot.axes.errorbar (range(orbit['nbpms']), np.transpose(orbit['x']), yerr=errx, lw=2, capsize=5, capthick=2, label="X")
        self.plot.axes.errorbar (range(orbit['nbpms']), np.transpose(orbit['y']), yerr=erry, lw=2, capsize=5, capthick=2, label="Y")
        self.plot.axes.legend (loc='upper left')
        self.plot.axes.xlabel ('Bpm [#]')
        self.plot.axes.ylabel ('Position [mm]')

class MainWindow(QMainWindow):
    def __init__(self, interface, dir_name):
        super().__init__()

        self.interface = interface
        correctors_list = interface.get_correctors()['names']
        
        self.setWindowTitle("CERN SYSID")
        self.setGeometry(100, 100, 400, 700)

        main_widget = QWidget()
        self.setCentralWidget(main_widget)

        main_layout = QVBoxLayout(main_widget)
        top_layout = QHBoxLayout()
        main_layout.addLayout(top_layout)

        # Left side layout
        left_layout = QVBoxLayout()
        top_layout.addLayout(left_layout)

        # Pattern input and correctors list
        pattern_layout = QHBoxLayout()
        left_layout.addLayout(pattern_layout)

        pattern_label = QLabel("Correctors:")
        pattern_layout.addWidget(pattern_label)

        self.correctors_list = QListWidget()
        self.correctors_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        self.correctors_list.insertItems(0, correctors_list)
        left_layout.addWidget(self.correctors_list)

        # Add and remove buttons
        button_layout = QHBoxLayout()
        left_layout.addLayout(button_layout)

        self.save_button = QPushButton("Save As..")
        self.save_button.clicked.connect(self.__save_button_clicked)
        button_layout.addWidget(self.save_button)

        self.load_button = QPushButton("Load..")
        self.load_button.clicked.connect(self.__load_button_clicked)
        button_layout.addWidget(self.load_button)

        self.clear_button = QPushButton("Clear")
        self.clear_button.clicked.connect(self.__clear_button_clicked)
        button_layout.addWidget(self.clear_button)
        
        #self.add_from_button = QPushButton("Add from...")
        #left_layout.addWidget(self.add_from_button)

        # Right side layout
        right_layout = QVBoxLayout()
        top_layout.addLayout(right_layout)

        # Info section
        info_layout = QVBoxLayout()
        right_layout.addLayout(info_layout)

        self.info_label = QLabel("Data storage:")
        info_layout.addWidget(self.info_label)

        self.working_directory_input = QLineEdit("Working directory:")
        self.working_directory_input.setText(dir_name)
        info_layout.addWidget(self.working_directory_input)

        self.current_corr_label = QLabel("Current corr: N/A")
        info_layout.addWidget(self.current_corr_label)

        # Options sectionQFileDialog
        options_layout = QVBoxLayout()
        right_layout.addLayout(options_layout)

        self.options_label = QLabel("Options")
        options_layout.addWidget(self.options_label)

        samples_layout = QHBoxLayout()
        options_layout.addLayout(samples_layout)

        self.samples_label = QLabel("N. of samples:")
        samples_layout.addWidget(self.samples_label)

        self.samples_spinbox = QSpinBox()
        self.samples_spinbox.setValue(3)
        samples_layout.addWidget(self.samples_spinbox)

        cycle_mode_layout = QHBoxLayout()
        options_layout.addLayout(cycle_mode_layout)

        self.cycle_mode_label = QLabel("Cycle mode:")
        cycle_mode_layout.addWidget(self.cycle_mode_label)

        self.cycle_mode_combobox = QComboBox()
        self.cycle_mode_combobox.addItems(["Repeat all"])
        cycle_mode_layout.addWidget(self.cycle_mode_combobox)

        excitation_layout = QHBoxLayout()
        options_layout.addLayout(excitation_layout)

        self.horizontal_excitation_label = QLabel("Excitation:    H:")
        excitation_layout.addWidget(self.horizontal_excitation_label)

        self.horizontal_excitation_spinbox = QDoubleSpinBox()
        self.horizontal_excitation_spinbox.setValue(1.0)
        self.horizontal_excitation_spinbox.setSingleStep(0.1)
        self.horizontal_excitation_spinbox.setSuffix(" mm")
        excitation_layout.addWidget(self.horizontal_excitation_spinbox)

        self.vertical_excitation_label = QLabel("V:")
        excitation_layout.addWidget(self.vertical_excitation_label)

        self.vertical_excitation_spinbox = QDoubleSpinBox()
        self.vertical_excitation_spinbox.setValue(1.0)
        self.vertical_excitation_spinbox.setSingleStep(0.1)
        self.vertical_excitation_spinbox.setSuffix(" mm")
        excitation_layout.addWidget(self.vertical_excitation_spinbox)

        self.plot = MatplotlibWidget(self)
        options_layout.addWidget(self.plot)

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

    def __save_button_clicked(self):
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

    def __load_button_clicked(self):
        dir_name = self.working_directory_input.text() + '/correctors.txt'
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

    def __clear_button_clicked(self):
        self.correctors_list.clearSelection()
            
    def __start_button_clicked(self):
        dir_name = self.working_directory_input.text()
        os.makedirs (dir_name, exist_ok=True)
        os.chdir (dir_name)
        
        print('Starting measurement...')
        
        selected_correctors = self.correctors_list.selectedItems()
        if len(selected_correctors) == 0:
            for i in range(self.correctors_list.count()):
                self.correctors_list.item(i).setSelected(True)
            selected_correctors = self.interface.get_correctors()['names']
       
        # Create a machine
        S = State (interface=self.interface)

        # Save the reference file
        F = S.save (basename='machine_status')

        kicks = 0.1 * np.ones(len(selected_correctors), dtype=float) # kicks to excite 1mm oscillation
        max_oscillation_h = self.horizontal_excitation_spinbox.value() # mm
        max_oscillation_v = self.vertical_excitation_spinbox.value() # mm

        selected_bpms = S.get_bpms()['names']
       
        Niter = 3
        for iter in range (Niter):
            print(f'Iteration {iter}/{Niter}')
            for icorr, corrector in enumerate(selected_correctors):

                self.current_corr_label.setText('Current corr: ' + corrector)
                
                # initial value
                corr = S.get_correctors (corrector)
                kick = kicks[icorr]

                # '+' excitation 
                print(f"Corrector {corrector} '+' excitation...")
                I.push(corrector, corr['bdes'] + kick)
                S.pull(I)
                S.save(filename=f'DATA_{corrector}_p{iter:04d}.pkl')
                Op = S.get_orbit(selected_bpms)
                
                # '-' excitation 
                print(f"Corrector {corrector} '-' excitation...")
                I.push(corrector, corr['bdes'] - kick)
                S.pull(I)
                S.save(filename=f'DATA_{corrector}_m{iter:04d}.pkl')
                Om = S.get_orbit (selected_bpms)
                
                # reset corrector
                I.push(corrector, corr['bdes'])
                
                # Orbit difference
                Diff_x = (Op['x'] - Om['x']) / 2.0
                Diff_y = (Op['y'] - Om['y']) / 2.0
                nsamples = Op['stdx'].size
                Err_x = np.sqrt(np.square(Op['stdx']) + np.square(Om['stdx'])) / np.sqrt(nsamples)
                Err_y = np.sqrt(np.square(Op['stdy']) + np.square(Om['stdy'])) / np.sqrt(nsamples)
                
                # Tunes the kickers omplitude
                if corrector in S.get_hcorrectors_names():
                    kicks[icorr] *= max_oscillation_h / np.max(np.absolute(Diff_x))
                else:
                    kicks[icorr] *= max_oscillation_v / np.max(np.absolute(Diff_y))

                # weighted average
                kicks[icorr] = 0.8 * kicks[icorr] + 0.2 * kick
                np.savetxt('kicks.txt', kicks, delimiter='\n')

                # Plot orbit    
                self.plot.axes.clear()
                self.plot.axes.errorbar (range(Op['nbpms']), Diff_x, yerr=Err_x, lw=2, capsize=5, capthick=2, label="X")
                self.plot.axes.errorbar (range(Op['nbpms']), Diff_y, yerr=Err_y, lw=2, capsize=5, capthick=2, label="Y")
                self.plot.axes.legend (loc='upper left')
                self.plot.axes.set_xlabel ('Bpm [#]')
                self.plot.axes.set_ylabel ('Orbit [mm]')
                self.plot.draw()
                
    def __stop_button_clicked(self):
        pass

## Connect to interface ATF2 Linac
# I = InterfaceATF2_Linac(nsamples=3)
I = InterfaceATF2_Ext_RFTrack(jitter=0.0, bpm_resolution=0.0, nsamples=1)

## Prepare interface
project_name = 'new_SYSID'
time_str = datetime.now().strftime("%Y%m%d_%H%M%S")
dir_name = f"Data/{project_name}_{time_str}"

## MAIN
app = QApplication(sys.argv)
window = MainWindow(I, dir_name)
window.show()
sys.exit(app.exec())

