import os, sys, json, matplotlib, pickle
from datetime import datetime
import numpy as np
from SaveOrLoad import SaveOrLoad
matplotlib.use("QtAgg")
from PyQt6 import uic
from PyQt6.QtWidgets import QApplication, QMainWindow,QMessageBox,QFileDialog,QVBoxLayout, QListWidget
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from State import State

class MatplotlibWidget(FigureCanvas):
    def __init__(self, parent=None):
        fig = Figure(figsize=(5, 3.2), tight_layout=True)
        super().__init__(fig)
        self.setParent(parent)
        self.ax = fig.add_subplot(111)

class MainWindow(QMainWindow,SaveOrLoad):
    def __init__(self, interface, dir_name):
        super().__init__()
        self.interface = interface
        self.dir_name = dir_name
        self._cancel = False
        self.S = State(interface=self.interface)
        ui_path = os.path.join(os.path.dirname(__file__), "UI files/Emittance_Measurement_GUI.ui")
        uic.loadUi(ui_path, self)
        self.setWindowTitle("Emittance Measurement GUI")
        self.session = None
        self.canvas = MatplotlibWidget(self.plotPlaceholder)
        layout = self.plotPlaceholder.layout()
        if layout is None:
            layout = QVBoxLayout(self.plotPlaceholder)
            layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.canvas)
        quadrupoles_list = interface.get_quadrupoles()['names']
        screens_list = interface.get_screens()['names']
        self.quadrupoles_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.quadrupoles_list.insertItems(0, quadrupoles_list)
        self.screens_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.screens_list.insertItems(0, screens_list)
        self.load_quadrupoles_button.clicked.connect(self._load_quadrupoles)
        self.load_screens_button.clicked.connect(self._load_screens)
        self.stop_button.clicked.connect(self._stop_scan)
        self.start_button.clicked.connect(self._run_scan)
        #self.load_session_button.clicked.connect(self._load_session_em)

    def _stop_scan(self):
        self._cancel = True
        QMessageBox.information(self, "Scan", "Stop requested. Finishing current iteration...")

    def _get_selection(self):
        quadrupoles_all = self.S.get_quadrupoles()["names"]
        screens_all = self.S.get_screens()["names"]
        quadrupoles = [it.text() for it in self.quadrupoles_list.selectedItems()] or quadrupoles_all
        screens = [it.text() for it in self.screens_list.selectedItems()] or screens_all
        return quadrupoles, screens

    def _run_scan(self):
        selected_quadrupoles =[it.text() for it in self.quadrupoles_list.selectedItems()]
        selected_screens =[it.text() for it in self.screens_list.selectedItems()]
        max_delta=float(self.delta_max_scan.value())
        min_delta=float(self.delta_min_scan.value())
        steps=int(self.steps_settings.value())
        nshots=int(self.meas_per_step.value())
        deltas=np.linspace(min_delta, max_delta, steps)

        if max_delta<=min_delta:
            QMessageBox.information(self, "Scan", "Max delta must be bigger than min delta.!")

        quadrupoles=self.interface.get_quadrupoles()
        quad_name=selected_quadrupoles[0]
        quad_index=list(quadrupoles['names']).index(quad_name)
        K1_0=float(quadrupoles['bdes'][quad_index])
        K1_values=K1_0*(1+deltas)
        print("quad:", quad_name, "K1_0:", K1_0)
        print("K1 min/max:", float(K1_values.min()), float(K1_values.max()))
        number_of_screens=len(selected_screens)
        sigx_mean=np.full((steps,number_of_screens), np.nan,dtype=float)
        sigy_mean=np.full((steps,number_of_screens), np.nan,dtype=float)
        sigx_std=np.full((steps,number_of_screens), np.nan,dtype=float)
        sigy_std=np.full((steps,number_of_screens), np.nan,dtype=float)

        initial_K1_0=K1_0

        for i, K1 in enumerate(K1_values):
            if self._cancel:
               break
            self.interface.set_quadrupoles([quad_name],[float(K1)])
            sx_shots=np.full((nshots,number_of_screens), np.nan,dtype=float)
            sy_shots=np.full((nshots,number_of_screens), np.nan,dtype=float)

            for j in range(nshots):
                if self._cancel:
                    break
                screens=self.interface.get_screens(selected_screens)
                for k,sname in enumerate(selected_screens):
                    sx_shots[j,k]=float(screens['sigx'][k])
                    sy_shots[j,k]=float(screens['sigy'][k])
            sigx_mean[i,:]=np.nanmean(sx_shots,axis=0)
            sigy_mean[i,:]=np.nanmean(sy_shots,axis=0)
            sigx_std[i,:]=np.nanstd(sx_shots,axis=0)
            sigy_std[i,:]=np.nanstd(sy_shots,axis=0)

            self.canvas.ax.clear()
            self.canvas.ax.plot(deltas[:i+1],sigx_mean[:i+1,0]**2,'b')
            self.canvas.ax.set_xlabel("delta value")
            self.canvas.ax.set_ylabel("sigx^2 value")
            self.canvas.ax.grid(True)
            self.canvas.draw_idle()

            QApplication.processEvents()

        self.interface.set_quadrupoles([quad_name],[float(initial_K1_0)])
        QMessageBox.information(self, "Scan", "Scan finished.")
        self._save_session_quad_scan(delta_min=min_delta,delta_max=max_delta,steps=steps,nshots=nshots,quad_name=quad_name,K1_0=initial_K1_0,sigx_mean=sigx_mean,sigy_mean=sigy_mean,sigx_std=sigx_std,sigy_std=sigy_std)


    def _fit_twiss(self):
        pass
    def _get_transport_martix(self):
        M0=self.interface.B0.get_phase_space('%x %xp %y %yp')
        B1=self.interface.lattice.track


if __name__ == "__main__":
    app = QApplication(sys.argv)

    import SelectInterface
    dialog = SelectInterface.choose_acc_and_interface()
    if dialog is None:
        print("Selection cancelled.")
        sys.exit(1)

    I = dialog
    project_name = I.get_name() if hasattr(I, "get_name") else type(I).__name__
    print(f"Selected interface: {project_name}")

    time_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    dir_name = f"~/flight-simulator-data/EM_{project_name}_{time_str}_session"
    dir_name = os.path.expanduser(os.path.expandvars(dir_name))

    w = MainWindow(interface=I, dir_name=dir_name)
    w.show()
    sys.exit(app.exec())