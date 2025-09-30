from PyQt6 import uic
from PyQt6.QtCore import Qt, QProcess, QProcessEnvironment
from datetime import datetime
from PyQt6.QtWidgets import (QApplication, QMainWindow, QFileDialog, QListWidget, QMessageBox, QProgressDialog, QVBoxLayout, QPushButton, QDialog, QLabel)
import sys, time,os

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.cwd = os.getcwd()
        self._cancel = False

        ui_path = os.path.join(os.path.dirname(__file__), "MainPanel.ui")
        uic.loadUi(ui_path, self)
        self.application_choice=None

        self.sysid_interface_button.clicked.connect(self.handle_sysid_click)
        self.compute_matrix_button.clicked.connect(self.handle_compute_response_matrix_click)
        self.bba_interface_button.clicked.connect(self.handle_bba_click)
        self.emittance_interface_button.clicked.connect(self.handle_emittance_click)
        self.knobs_interface_button.clicked.connect(self.handle_knobs_click)

        self._procs=[]
        self.setWindowTitle("Choose the application")

    def handle_sysid_click(self):
        sysid_path = os.path.join(os.path.dirname(__file__), "SysID_GUI.py")

        proc = QProcess(self)
        proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        proc.setWorkingDirectory(self.cwd)

        env = QProcessEnvironment.systemEnvironment()
        proc.setProcessEnvironment(env)

        proc.start(sys.executable, [sysid_path])

        proc.readyReadStandardOutput.connect(lambda p=proc: print(bytes(p.readAllStandardOutput()).decode(errors="ignore"), end=""))

        self._procs.append(proc)



    def handle_bba_click(self):
        bba_path = os.path.join(os.path.dirname(__file__), "BBA_GUI.py")

        proc = QProcess(self)
        proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        proc.setWorkingDirectory(self.cwd)

        env = QProcessEnvironment.systemEnvironment()
        proc.setProcessEnvironment(env)

        proc.start(sys.executable, [bba_path])

        proc.readyReadStandardOutput.connect(lambda p=proc: print(bytes(p.readAllStandardOutput()).decode(errors="ignore"), end=""))

        self._procs.append(proc)
    def handle_emittance_click(self):
        pass
    def handle_knobs_click(self):
        pass
    def handle_compute_response_matrix_click(self):
        compute_response_matrix_path = os.path.join(os.path.dirname(__file__), "ComputeResponseMatrix_GUI.py")

        proc = QProcess(self)
        proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        proc.setWorkingDirectory(self.cwd)

        env = QProcessEnvironment.systemEnvironment()
        proc.setProcessEnvironment(env)

        proc.start(sys.executable, [compute_response_matrix_path])

        proc.readyReadStandardOutput.connect(lambda p=proc: print(bytes(p.readAllStandardOutput()).decode(errors="ignore"), end=""))

        self._procs.append(proc)
if __name__ == "__main__":
    app = QApplication([])
    app.setQuitOnLastWindowClosed(False)

    time_str = datetime.now().strftime("%Y%m%d_%H%M%S")

    w = MainWindow()
    w.show()
    sys.exit(app.exec())