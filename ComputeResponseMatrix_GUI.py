from State import State
from Response import Response
from PyQt6 import uic
import numpy as np
import glob,sys,os,argparse,matplotlib
from SaveOrLoad import SaveOrLoad
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout,
    QLineEdit, QListWidget, QPushButton,
    QCheckBox, QFileDialog, QSizePolicy,QMessageBox,
)
from PyQt6.QtCore import Qt,QTimer
from SaveOrLoad import SaveOrLoad
matplotlib.use('QtAgg')
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

class MatplotlibWidget(FigureCanvas):
    def __init__(self, parent=None, title='', orbit=None):
        fig = Figure(tight_layout=True)
        super().__init__(fig)
        self.setParent(parent)
        self.axes = fig.add_subplot(111)

class MainWindow(QMainWindow, SaveOrLoad):
    def __init__(self,data_dir_1=None,data_dir_2=None,comp_difference=False,auto_click_compute=False):
        super().__init__()
        uic.loadUi("ComputeResponseMatrix_GUI.ui", self)
        self.cwd = os.getcwd()
        self.R=None
        self.data_dir_1=data_dir_1
        self.data_dir_2=data_dir_2
        self.comp_difference=comp_difference
        self.auto_click_compute=auto_click_compute
        self.setWindowTitle("Compute Response Matrix Tool")
        self.setGeometry(100, 100, 600, 700)
        self.data_directory_1.setText(self.cwd)
        self.choose_directory_1.clicked.connect(lambda: self._pick_directory_with_data(self.data_directory_1))
        self.choose_directory_2.clicked.connect(lambda:self._pick_directory_with_data(self.data_directory_2))
        self.compute_button.clicked.connect(self.__compute_button_clicked)
        self.save_as_button.clicked.connect(self.__save_as_button_clicked)
        self.diff_checkbox.toggled.connect(self._compute_difference_clicked)
        self._compute_difference_clicked(self.diff_checkbox.isChecked())

        layout = self.plot_widget.layout()
        if layout is None:
            layout = QVBoxLayout(self.plot_widget)
        self.plot = MatplotlibWidget(self.plot_widget)
        self.plot.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(self.plot)

        if self.data_dir_1:
            self.data_directory_1.setText(self.data_dir_1)
            self._load_lists_from_directory(self.data_dir_1)
        if self.comp_difference==True:
            self.diff_checkbox.setChecked(True)
            self._compute_difference_clicked(checked=True)
        if self.data_dir_2:
            self.data_directory_2.setText(self.data_dir_2)
            self._load_lists_from_directory(self.data_dir_2)
        if self.auto_click_compute:
            QTimer.singleShot(0, self.__compute_button_clicked)





    def _compute_difference_clicked(self,checked):
        checked=bool(checked)
        self.label_dir_2.setEnabled(checked)
        self.choose_directory_2.setEnabled(checked)
        self.data_directory_2.setEnabled(checked)

    def _pick_directory_with_data(self,line_edit):
        base=(line_edit.text() or self.cwd).strip()
        folder=QFileDialog.getExistingDirectory(self,"Select data directory",base)
        if not folder:
            return
        line_edit.setText(folder)
        if line_edit is self.data_directory_1:
            self._load_lists_from_directory(folder)

    def _load_lists_from_directory(self,folder):
        datafiles=sorted(glob.glob(os.path.join(folder,"DATA*.pkl")))
        if not datafiles:
            return
        S=State(filename=datafiles[0])
        self.sequence=S.sequence
        self.correctors=list(S.get_correctors()["names"])
        self.bpms=list(S.get_bpms()["names"])

        self.correctors_list.clear()
        self.correctors_list.addItems([str(c) for c in self.correctors])

        self.bpms_list.clear()
        self.bpms_list.addItems([str(b) for b in self.bpms])

    def _compute_response_of_one_data_directory(self,directory):
        datafiles=sorted(glob.glob(os.path.join(directory, "DATA*.pkl")))
        if not datafiles:
            QMessageBox.warning(self,"No DATA files found.","No valid data found")
            return

        S = State(filename=datafiles[0])
        sequence=S.sequence

        correctors = [item.text() for item in self.correctors_list.selectedItems()]
        bpms = [item.text() for item in self.bpms_list.selectedItems()]

        if not correctors:
            for i in range(self.correctors_list.count()):
                self.correctors_list.item(i).setSelected(True)
            correctors = self.correctors

        if not bpms:
            for i in range(self.bpms_list.count()):
                self.bpms_list.item(i).setSelected(True)
            bpms = self.bpms

        hcorrs = [string for string in correctors if
                  (string.lower().startswith('zh') or string.lower().startswith('zx'))]
        vcorrs = [string for string in correctors if string.lower().startswith('zv')]

        # Pick all correctors preceding the last bpm
        hcorrs = [corr for corr in hcorrs if sequence.index(corr) < sequence.index(bpms[-1])]
        vcorrs = [corr for corr in vcorrs if sequence.index(corr) < sequence.index(bpms[-1])]

        # Pick all bpms following the first corrector
        bpms = [bpm for bpm in bpms if sequence.index(bpm) > sequence.index(hcorrs[0])]
        bpms = [bpm for bpm in bpms if sequence.index(bpm) > sequence.index(vcorrs[0])]

        # Read all orbits
        Bx = np.empty((0, len(bpms)))
        By = np.empty((0, len(bpms)))
        Cx = np.empty((0, len(hcorrs)))
        Cy = np.empty((0, len(vcorrs)))
        datafiles_p = [f for f in datafiles if f[-9] == 'p']
        for datafile_p in datafiles_p:
            datafile_m = datafile_p[:-9] + 'm' + datafile_p[-8:]
            if os.path.exists(datafile_m):
                Sp = State(filename=datafile_p)
                Sm = State(filename=datafile_m)
                Op = Sp.get_orbit(bpms)
                Om = Sm.get_orbit(bpms)
                Cx_p = Sp.get_correctors(hcorrs)['bact']
                Cy_p = Sp.get_correctors(vcorrs)['bact']
                Cx_m = Sm.get_correctors(hcorrs)['bact']
                Cy_m = Sm.get_correctors(vcorrs)['bact']
                if 0:
                    O_x = Op['x'] - Om['x']
                    O_y = Op['y'] - Om['y']
                    C_x = Cx_p - Cx_m
                    C_y = Cy_p - Cy_m
                    Bx = np.vstack((Bx, O_x))
                    By = np.vstack((By, O_y))
                    Cx = np.vstack((Cx, C_x))
                    Cy = np.vstack((Cy, C_y))
                    print(Cx, Bx)
                else:
                    Bx = np.vstack((Bx, Op['x']))
                    Bx = np.vstack((Bx, Om['x']))
                    By = np.vstack((By, Op['y']))
                    By = np.vstack((By, Om['y']))
                    Cx = np.vstack((Cx, Cx_p))
                    Cx = np.vstack((Cx, Cx_m))
                    Cy = np.vstack((Cy, Cy_p))
                    Cy = np.vstack((Cy, Cy_m))
            else:
                print(
                    f"Data file '{datafile_m}' does not exist, ignoring counterpart '{datafile_p}' for response matrix computation")

        # Compute the response matrices
        ones_column_x = np.ones((Cx.shape[0], 1))
        ones_column_y = np.ones((Cy.shape[0], 1))

        # Add the column of ones to the matrix
        Cx = np.hstack((Cx, ones_column_x))
        Cy = np.hstack((Cy, ones_column_y))

        Rxx = np.transpose(np.linalg.lstsq(Cx, Bx, rcond=None)[0])
        Rxy = np.transpose(np.linalg.lstsq(Cy, Bx, rcond=None)[0])
        Ryx = np.transpose(np.linalg.lstsq(Cx, By, rcond=None)[0])
        Ryy = np.transpose(np.linalg.lstsq(Cy, By, rcond=None)[0])

        # Reference trajectory
        '''
        Bx = Rxx[:,-1]
        By = Ryy[:,-1]
        '''

        Bx = np.mean(Bx, axis=0).reshape(-1, 1)
        By = np.mean(By, axis=0).reshape(-1, 1)

        # Response matrices
        Rxx = Rxx[:, :-1]
        Rxy = Rxy[:, :-1]
        Ryx = Ryx[:, :-1]
        Ryy = Ryy[:, :-1]

        # Zero the response of all bpms preceeding the correctors
        if self.triangular_checkbox.isChecked():
            for corr in hcorrs:
                bpm_indexes = [bpms.index(bpm) for bpm in bpms if sequence.index(bpm) < sequence.index(corr)]
                Rxx[bpm_indexes, hcorrs.index(corr)] = 0
                Ryx[bpm_indexes, hcorrs.index(corr)] = 0

            for corr in vcorrs:
                bpm_indexes = [bpms.index(bpm) for bpm in bpms if sequence.index(bpm) < sequence.index(corr)]
                Rxy[bpm_indexes, vcorrs.index(corr)] = 0
                Ryy[bpm_indexes, vcorrs.index(corr)] = 0

        # Save on disk
        R = Response()
        R.bpms = bpms
        R.hcorrs = hcorrs
        R.vcorrs = vcorrs
        R.Rxx = Rxx
        R.Rxy = Rxy
        R.Ryx = Ryx
        R.Ryy = Ryy
        R.Bx = Bx
        R.By = By
        return R

    def _substract_matrices(self,R1,R2):
        if R1.Rxx.shape != R2.Rxx.shape or R1.Ryy.shape != R2.Ryy.shape:
            raise RuntimeError("Response matrices must have same shape")
        R = Response()
        R.bpms = R1.bpms
        R.hcorrs = R1.hcorrs
        R.vcorrs = R1.vcorrs
        R.Rxx = R1.Rxx-R2.Rxx
        R.Rxy = R1.Rxy-R2.Rxy
        R.Ryx = R1.Ryx-R2.Ryx
        R.Ryy = R1.Ryy-R2.Ryy
        R.Bx = R1.Bx-R2.Bx
        R.By = R1.By-R2.By
        return R

    def __save_correctors_button_clicked(self):
        self._save_correctors()

    def __load_correctors_button_clicked(self):
        self._load_correctors()

    def __clear_correctors_button_clicked(self):
        self.correctors_list.clearSelection()

    def __save_bpms_button_clicked(self):
        self._save_bpms()

    def __load_bpms_button_clicked(self):
        self._load_bpms()

    def __clear_bpms_button_clicked(self):
        self.bpms_list.clearSelection()

    def _plot_response_matrix(self,R):
        # Clear existing figure
        self.plot.figure.clf()

        # === 3D surface plots ===
        # If you want to show both sets (2D + 3D), you need two canvases.
        # But if you want to reuse the same canvas, just do this after the first draw:

        # Clear and re-plot the 3D figure
        self.plot.figure.clf()
        fig1 = self.plot.figure
        # fig1.set_size_inches(12, 10)

        ax1 = fig1.add_subplot(2, 2, 1, projection='3d')
        ax3 = fig1.add_subplot(2, 2, 3, projection='3d')
        ax2 = fig1.add_subplot(2, 2, 2, projection='3d')
        ax4 = fig1.add_subplot(2, 2, 4, projection='3d')

        x = np.array(range(len(R.hcorrs)))
        y = np.array(range(len(R.bpms)))
        X, Y = np.meshgrid(x, y)

        ax1.plot_surface(X, Y, R.Rxx, cmap='viridis')
        ax1.set_title('$R_{xx}$')
        ax1.set_xlabel('Corrector [#]')
        ax1.set_ylabel('BPM [#]')

        ax3.plot_surface(X, Y, R.Ryx, cmap='viridis')
        ax3.set_title('$R_{yx}$')
        ax3.set_xlabel('Corrector [#]')
        ax3.set_ylabel('BPM [#]')

        x = np.array(range(len(R.vcorrs)))
        X, Y = np.meshgrid(x, y)

        ax2.plot_surface(X, Y, R.Rxy, cmap='viridis')
        ax2.set_title('$R_{xy}$')
        ax2.set_xlabel('Corrector [#]')
        ax2.set_ylabel('BPM [#]')

        ax4.plot_surface(X, Y, R.Ryy, cmap='viridis')
        ax4.set_title('$R_{yy}$')
        ax4.set_xlabel('Corrector [#]')
        ax4.set_ylabel('BPM [#]')

        fig1.tight_layout()

        self.plot.draw()
        self.plot.flush_events()
        self.plot.repaint()

    def __compute_button_clicked(self):
        try:
            directory_1=(self.data_directory_1.text() or "").strip()
            if not directory_1:
                QMessageBox.warning(self, "Error", "No data directory specified")
                return
            R1=self._compute_response_of_one_data_directory(directory_1)

            if self.diff_checkbox.isChecked():
                directory_2 = (self.data_directory_2.text() or "").strip()
                if not directory_2:
                    QMessageBox.warning(self, "Error", "No second data directory specified")
                    return
                R2 = self._compute_response_of_one_data_directory(directory_2)
                self.R=self._substract_matrices(R1=R1,R2=R2)
            else:
                self.R=R1
            self._plot_response_matrix(R=self.R)

        except Exception as e:
            QMessageBox.warning(self, "Error", str(e))

    def __save_as_button_clicked(self):
        dir_name = self.cwd + '/response2.pkl'
        os.chdir (self.cwd)
        filename, _ = QFileDialog.getSaveFileName(None, "Save Response Matrix", dir_name, "Pickle Files (*.pkl)")
        if filename:
            self.R.save(filename)

if __name__ == '__main__':
    parser=argparse.ArgumentParser(description='Compute Response Matrix GUI')
    parser.add_argument("--dir1",default=None,help="First data directory")
    parser.add_argument("--dir2",default=None,help="Second data directory")
    parser.add_argument("--diff",action="store_true",help="Difference between responses")
    parser.add_argument("--compute",action="store_true",help="Auto-click Compute button")
    args=parser.parse_args()

    dir1=args.dir1
    dir2=args.dir2

    app = QApplication(sys.argv)
    window = MainWindow(data_dir_1=args.dir1,
        data_dir_2=args.dir2,
        comp_difference=args.diff,
        auto_click_compute=args.compute,)
    window.show()
    sys.exit(app.exec())
