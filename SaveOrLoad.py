import os, pickle, json
from datetime import datetime
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QApplication, QSizePolicy, QMainWindow, QFileDialog, QListWidget, QMessageBox,
                             QProgressDialog, QVBoxLayout, QPushButton, QDialog, QLabel)
import numpy as np

class SaveOrLoad():
    def _saving_func(self, elements_list, filename, saving_name, *, use_dialog=True,base_dir=None):  # * - must be passed by keyword
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
        if not selected:
            if elements_list is self.bpms_list:
                selected = self.S.get_bpms()["names"]
            elif elements_list is self.correctors_list:
                selected = self.S.get_correctors()["names"]
            elif elements_list is self.quadrupoles_list:
                selected = self.S.get_quadrupoles()["names"]
            elif elements_list is self.screens_list:
                selected = self.S.get_screens()["names"]
            else:
                selected = [elements_list.item(i).text() for i in range(elements_list.count())]
            elements_list.clearSelection()
        for name in selected:
            for it in elements_list.findItems(name, Qt.MatchFlag.MatchExactly):
                it.setSelected(True)

    def _save_correctors(self):
        self._saving_func(elements_list=self.correctors_list, filename="correctors.txt", saving_name="Save Correctors")

    def _save_bpms(self):
        self._saving_func(elements_list=self.bpms_list, filename="bpms.txt", saving_name="Save BPMs")

    def _load_correctors(self):
        self._loading_func(loading_name="Load Correctors", filename="correctors.txt",elements_list=self.correctors_list)

    def _load_bpms(self):
        self._loading_func(loading_name="Load BPMs", filename="bpms.txt", elements_list=self.bpms_list)

    def _load_quadrupoles(self):
        self._loading_func(loading_name="Load Quadrupoles", filename="quadrupoles.txt", elements_list=self.quadrupoles_list)

    def _load_screens(self):
        self._loading_func(loading_name="Load Screens", filename="screens.txt", elements_list=self.screens_list)

    def _pick_and_load_data_dir(self, button_ui, button_name, oper):
        default_dir = f"~/flight-simulator-data/"
        default_dir = os.path.expanduser(os.path.expandvars(default_dir))
        os.makedirs(default_dir, exist_ok=True)
        folder = QFileDialog.getExistingDirectory(self, "Select data directory", default_dir)
        if not folder:
            return
        info = self._find_useful_files(folder)
        if not info["ok"]:
            QMessageBox.warning(self, "Load data", "Wrong data directory selected")
        self._data_dirs[oper] = info
        button_ui.setText(folder)
        #QMessageBox.information(button_ui, "Data directory selected", button_name)

    def _pick_and_load_disp_data(self):
        self._pick_and_load_data_dir(oper="dfs", button_ui=self.dfs_response_3, button_name="DFS Data Loaded")

    def _pick_and_load_wake_data(self):
        self._pick_and_load_data_dir(oper="wfs", button_ui=self.wfs_response_3, button_name="WFS Data Loaded")

    def _pick_and_load_traj_data(self):
        self._pick_and_load_data_dir(oper="traj", button_ui=self.trajectory_response_3,button_name="Trajectory Data Loaded")

    def _save_session_quad_scan(self, delta_min,delta_max,steps,nshots,quad_name, K1_0,sigx_mean,sigy_mean,sigx_std,sigy_std, deltas=None,K1_values=None):
        time_str = datetime.now().strftime("%y%m%d%H%M%S")
        default_dir = f"~/flight-simulator-data/"
        default_dir = os.path.expanduser(os.path.expandvars(default_dir))
        save_session_dir = os.path.join(default_dir, f"Quadrupole_scan_{self.interface.get_name()}_{time_str}_session_settings")
        os.makedirs(save_session_dir, exist_ok=True)

        self._saving_func(elements_list=self.quadrupoles_list, filename="quadrupoles.txt", saving_name="Save Quadrupoles",
                          use_dialog=False, base_dir=save_session_dir)
        self._saving_func(elements_list=self.screens_list, filename="screens.txt", saving_name="Save Screens", use_dialog=False,
                          base_dir=save_session_dir)

        sigx_mean = np.asarray(sigx_mean, dtype=float)
        sigy_mean = np.asarray(sigy_mean, dtype=float)
        sigx_std = np.asarray(sigx_std, dtype=float)
        sigy_std = np.asarray(sigy_std, dtype=float)

        scan_settings = {
            "delta_min": delta_min,
            "delta_max": delta_max,
            "steps": steps,
            "nshots": nshots,
            "quad_name": quad_name,
            "K1_0": K1_0,
            "sigx_mean": sigx_mean.tolist(),
            "sigy_mean": sigy_mean.tolist(),
            "sigx_std": sigx_std.tolist(),
            "sigy_std": sigy_std.tolist(),
            "deltas": deltas.tolist() if deltas is not None else None,
            "K1_values": K1_values.tolist() if K1_values is not None else None,
        }

        with open(os.path.join(save_session_dir, "scan_settings.json"), "w") as f:
            json.dump(scan_settings, f, indent=2)
        self.session_database.setText(save_session_dir)

    def save_session_settings(self, w1, w2, w3, rcond, iters, gain, Axx, Ayy,Axy,Ayx, Bx, By):
        time_str = datetime.now().strftime("%y%m%d%H%M%S")
        default_dir = f"~/flight-simulator-data/"
        default_dir = os.path.expanduser(os.path.expandvars(default_dir))
        save_session_dir = os.path.join(default_dir, f"BBA_{self.interface.get_name()}_{time_str}_session_settings")
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
            "data_dirs": {k: (self._expand_data_path(v["dir"]) if v else None)
                          for k, v in self._data_dirs.items()},
        }

        with open(os.path.join(save_session_dir, "correction_settings.json"), "w") as f:
            json.dump(correction_settings, f, indent=2)

        def __save_graph_data(path, series):
            with open(path, "w") as f:
                f.write("Iteration\tvalue\n")
                for i, v in enumerate(series, start=1):
                    f.write(f"{i}\t{v}\n")

        __save_graph_data(os.path.join(save_session_dir, "trajectory_x_after_correction.txt"), self._hist_orbit_x)
        __save_graph_data(os.path.join(save_session_dir, "dispersion_x_after_correction.txt"), self._hist_disp_x)
        __save_graph_data(os.path.join(save_session_dir, "wakefield_x_after_correction.txt"), self._hist_wake_x)
        __save_graph_data(os.path.join(save_session_dir, "trajectory_y_after_correction.txt"), self._hist_orbit_y)
        __save_graph_data(os.path.join(save_session_dir, "dispersion_y_after_correction.txt"), self._hist_disp_y)
        __save_graph_data(os.path.join(save_session_dir, "wakefield_y_after_correction.txt"), self._hist_wake_y)

        corrs, bpms = self._get_selection()
        R0xx, R0yy, R0xy, R0yx, B0x, B0y, R1xx, R1yy, R1xy, R1yx, B1x, B1y, R2xx, R2yy, R2xy, R2yx, B2x, B2y, hcorrs0, vcorrs0, hcorrs1, vcorrs1, hcorrs2, vcorrs2, bpms0, bpms1, bpms2 = self._get_data_from_loaded_directories(
            selected_corrs=corrs, selected_bpms=bpms)
        correction_matrices = {
            "Axx": Axx, "Ayy": Ayy, "Axy":Axy, "Ayx":Ayx, "B0x": B0x, "B0y": B0y,
            "R0xx": R0xx, "R1xx": R1xx, "R2xx": R2xx,
            "R0yy": R0yy, "R1yy": R1yy, "R2yy": R2yy,
            "R0xy": R0xy, "R0yx": R0yx, "R1xy": R1xy, "R1yx": R1yx,
            "R2xy": R2xy, "R2yx": R2yx,
            "Bx": Bx, "By": By,
        }
        with open(os.path.join(save_session_dir, "correction_matrices.pkl"), "wb") as f:
            pickle.dump(correction_matrices, f)

    def load_session_settings_quad_scan(self):
        default_dir = f"~/flight-simulator-data/"
        default_dir = os.path.expanduser(os.path.expandvars(default_dir))
        os.makedirs(default_dir, exist_ok=True)
        folder = QFileDialog.getExistingDirectory(self, "Select database", default_dir)
        if not folder:
            return
        if hasattr(self, "load_session_button"):
            self.session_database.setText(folder)
        QMessageBox.information(self.session_database, "Data directory selected", "Loaded session")

        # load quadrupoles
        self._loading_func(elements_list=self.quadrupoles_list, filename="quadrupoles.txt",
                           loading_name="Load Quadrupoles", use_dialog=False, base_dir=folder)
        # load screens
        self._loading_func(elements_list=self.screens_list, filename="screens.txt", loading_name="Load Screens",
                           use_dialog=False, base_dir=folder)

        scan_settings_path = os.path.join(folder, "scan_settings.json")
        try:
            with open(scan_settings_path, "r") as f:
                settings = json.load(f)
        except Exception as e:
            QMessageBox.warning(self, "Load session", str(e))
            settings = {}
        self._quad_scan_session=settings

        if "delta_min" in settings: self.delta_min_scan.setValue(float(settings["delta_min"]))
        if "delta_max" in settings: self.delta_max_scan.setValue(float(settings["delta_max"]))
        if "steps" in settings: self.steps_settings.setValue(float(settings["steps"]))
        if "nshots" in settings: self.meas_per_step.setValue(float(settings["nshots"]))

    def load_session_settings(self):
        default_dir = f"~/flight-simulator-data/"
        default_dir = os.path.expanduser(os.path.expandvars(default_dir))
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
                    path = os.path.expanduser(os.path.expandvars(path))
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

        if hasattr(self, "trajectory_response_3"): self.trajectory_response_3.setText(settings["data_dirs"]["traj"] or "")
        if hasattr(self, "dfs_response_3"): self.dfs_response_3.setText(settings["data_dirs"]["dfs"] or "")
        if hasattr(self, "wfs_response_3"): self.wfs_response_3.setText(settings["data_dirs"]["wfs"] or "")

