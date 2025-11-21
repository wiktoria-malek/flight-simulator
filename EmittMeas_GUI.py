import sys, os, pickle, re, matplotlib, glob, time,json
from PyQt6 import uic
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QApplication, QSizePolicy, QMainWindow, QFileDialog, QListWidget, QMessageBox,
                             QProgressDialog, QVBoxLayout, QPushButton, QDialog, QLabel)
matplotlib.use("QtAgg")
class EmittMeasGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        here = os.path.dirname(os.path.abspath(__file__))
        ui_path = os.path.join(here, "EmittMeas_GUI.ui")
        uic.loadUi(ui_path, self)
        self.screensListWidget.addItems(["OTR0X", "OTR1X", "OTR2X", "OTR3X"])
        self.cwd = os.getcwd()
        self.loadTwissButton.clicked.connect(self._pick_and_load_lattice_data)

    def _loading_func(self, filename="", loading_name="Load file",*, use_dialog=True, base_dir=None):
        default_dir = base_dir or os.path.join(self.cwd, "Ext_ATF2")
        os.makedirs(default_dir, exist_ok=True)

        if use_dialog:
            start_path = os.path.join(default_dir, filename) if filename else default_dir
            fn, _ = QFileDialog.getOpenFileName(self,loading_name,start_path,"All files (*)")
            if not fn:
                return
        else:
            if not filename:
                return
            fn = filename
            if not os.path.isabs(fn):
                fn = os.path.join(default_dir, fn)

        if not os.path.isfile(fn):
            QMessageBox.warning(self, "Load data", f"File not found:\n{fn}")
            return

        with open(fn, "r") as f:
            selected = [ln.strip() for ln in f]

        QMessageBox.information(self, "Data file selected", f"Loaded:\n{fn}")
        self.twissFileLineEdit.setText(fn)

    def _pick_and_load_lattice_data(self):
        self._loading_func(loading_name="Load Lattice file")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = EmittMeasGUI()
    w.show()
    sys.exit(app.exec())
