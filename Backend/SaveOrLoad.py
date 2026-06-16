import os, pickle, json
from datetime import datetime
try:
    from PyQt6.QtWidgets import (
        QDialog, QVBoxLayout, QDialogButtonBox,
        QRadioButton, QLabel,QFileDialog, QMessageBox
        )
    from PyQt6.QtCore import QEvent, Qt
except ImportError:
    from PyQt5.QtWidgets import (
        QDialog, QVBoxLayout, QDialogButtonBox,
        QRadioButton, QLabel,QFileDialog, QMessageBox
        )
    from PyQt5.QtCore import QEvent, Qt
import numpy as np

class SaveOrLoad():

    def _refactor_names_order(self,elements_list, selected_names):
        state=getattr(self,"initial_state",None)

        if state is not None:
            if hasattr(self,"correctors_list") and elements_list is self.correctors_list:
                actuator_mode = getattr(getattr(self,"actuator_mode",None),"name", "Kicker")
                if actuator_mode == "QM" and hasattr(self, "qm_corrs"):
                    ref_list = [str(x) for x in self.qm_corrs]
                else:
                    ref_list = [str(x) for x in state.get_correctors()["names"]]
            elif hasattr(self, "bpms_list") and elements_list is self.bpms_list:
                    ref_list=[str(x) for x in state.get_bpms()["names"]]
            elif hasattr(self,"quadrupoles_list") and elements_list is self.quadrupoles_list:
                ref_list = [str(x) for x in state.get_quadrupoles()["names"]]
            elif hasattr(self,"screens_list") and elements_list is self.screens_list:
                ref_list = [str(x) for x in state.get_screens()["names"]]
            else:
                ref_list=[elements_list.item(i).text() for i in range(elements_list.count())]
        else:
            ref_list = [elements_list.item(i).text() for i in range(elements_list.count())]

        selected_set={str(x) for x in selected_names}
        return [name for name in ref_list if name in selected_set]


    def _saving_func(self, elements_list, filename, saving_name, *, use_dialog=True,base_dir=None):  # * - must be passed by keyword
        items = elements_list.selectedItems()
        if not items:
            selected_names = [elements_list.item(i).text() for i in range(elements_list.count())]
        else:
            selected_names=[it.text() for it in items]

        ordered_names=self._refactor_names_order(elements_list,selected_names)
        base = base_dir or self.dir_name
        os.makedirs(base, exist_ok=True)
        if use_dialog:
            fn, _ = QFileDialog.getSaveFileName(self, f"{saving_name}", os.path.join(base, f"{filename}"),"Text (*.txt)")
            if not fn:
                return
        else:
            fn = os.path.join(base, filename)
        with open(fn, "w") as f:
            for it in ordered_names:
                f.write(f"{it}\n")

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
            state = getattr(self, "initial_state", None)
            if state is not None:
                if hasattr(self, "bpms_list") and elements_list is self.bpms_list:
                    selected = state.get_bpms()["names"]
                elif hasattr(self, "correctors_list") and elements_list is self.correctors_list:
                    actuator_mode = getattr(getattr(self, "actuator_mode", None), "name", "Kicker")
                    if actuator_mode == "QM" and hasattr(self, "qm_corrs"):
                        selected = self.qm_corrs
                    else:
                        selected = state.get_correctors()["names"]
                elif hasattr(self, "quadrupoles_list") and elements_list is self.quadrupoles_list:
                    selected = state.get_quadrupoles()["names"]
                elif hasattr(self, "screens_list") and elements_list is self.screens_list:
                    selected = state.get_screens()["names"]
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
        default_dir = f"~/CERN-Flight_Simulator-Data/"
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

    def save_session_settings(self, w1, w2, w3, rcond, iters, gain, beta, max_horizontal_current,max_vertical_current, is_triangular,bpm_weights,Axx, Ayy,Axy,Ayx, Bx, By, is_jitter_subtraction_checked):
        time_str = datetime.now().strftime("%y%m%d%H%M%S")
        default_dir = f"~/CERN-Flight_Simulator-Data/"
        default_dir = os.path.expanduser(os.path.expandvars(default_dir))
        save_session_dir = os.path.join(default_dir, f"BBA_{self.interface.get_name()}{time_str}_session_settings")
        os.makedirs(save_session_dir, exist_ok=True)

        self._saving_func(elements_list=self.correctors_list, filename="correctors.txt", saving_name="Save Correctors",
                          use_dialog=False, base_dir=save_session_dir)
        self._saving_func(elements_list=self.bpms_list, filename="bpms.txt", saving_name="Save BPMs", use_dialog=False,
                          base_dir=save_session_dir)

        correction_settings = {
            "actuator_mode": "Kicker",
            "w1": w1,
            "w2": w2,
            "w3": w3,
            "rcond": rcond,
            "iters": iters,
            "gain": gain,
            "beta": beta,
            "max_horizontal_current" : max_horizontal_current,
            "max_vertical_current" : max_vertical_current,
            "is_triangular" : is_triangular,
            "is_jitter_subtraction_checked": is_jitter_subtraction_checked,
            "bpm_weights" : bpm_weights,
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
        default_dir = f"~/CERN-Flight_Simulator-Data/"
        default_dir = os.path.expanduser(os.path.expandvars(default_dir))
        os.makedirs(default_dir, exist_ok=True)
        folder = QFileDialog.getExistingDirectory(self, "Select database", default_dir)
        if not folder:
            return
        if hasattr(self, "load_session_button"):
            self.session_database.setText(folder)
        # load quadrupoles
        self._loading_func(elements_list=self.quadrupoles_list, filename="quadrupoles.txt",
                           loading_name="Load Quadrupoles", use_dialog=False, base_dir=folder)
        # load screens
        self._loading_func(elements_list=self.screens_list, filename="screens.txt", loading_name="Load Screens",
                           use_dialog=False, base_dir=folder)

        scan_settings_path = os.path.join(folder, "scan_settings.json")
        if not os.path.isfile(scan_settings_path):
            QMessageBox.warning(self, "Load session", "Wrong data in the folder.")
            return
        try:
            with open(scan_settings_path, "r") as f:
                settings = json.load(f)
        except Exception as e:
            QMessageBox.warning(self, "Load session", "Wrong data in the folder.")
            return
        QMessageBox.information(self.session_database, "Data directory selected", "Loaded session")

        if "delta_min" in settings: self.delta_min_scan.setValue(float(settings["delta_min"]))
        if "delta_max" in settings: self.delta_max_scan.setValue(float(settings["delta_max"]))
        if "steps" in settings: self.steps_settings.setValue(float(settings["steps"]))
        if "nshots" in settings: self.meas_per_step.setValue(float(settings["nshots"]))

    def load_session_settings(self):
        default_dir = f"~/CERN-Flight_Simulator-Data/"
        default_dir = os.path.expanduser(os.path.expandvars(default_dir))
        os.makedirs(default_dir, exist_ok=True)
        folder = QFileDialog.getExistingDirectory(self, "Select database", default_dir)
        if not folder:
            return
        if hasattr(self, "session_database_3"):
            self.session_database_3.setText(folder)
        correction_settings_path = os.path.join(folder, "correction_settings.json")
        if not os.path.isfile(correction_settings_path):
            QMessageBox.warning(self, "Load session", "Selected folder doesn't contain proper correction settings.")
            return
        try:
            with open(correction_settings_path, "r") as f:
                settings = json.load(f)
                actuator_mode = settings.get("actuator_mode", "Kicker")
        except Exception as e:
            QMessageBox.warning(self,"Load session",f"Couldn't read correction_settings.json: {e}")
            return

        # Set actuator mode in combo if present
        if hasattr(self, "actuator_mode_combo"):
            mode_text = "Quadrupole movers" if actuator_mode == "QM" else "Correctors"
            idx = self.actuator_mode_combo.findText(mode_text)
            if idx >= 0:
                self.actuator_mode_combo.setCurrentIndex(idx)

        if hasattr(self, "_refresh_corrector_list"):
            self._refresh_corrector_list()
        if hasattr(self, "_update_qm_widgets_visibility"):
            self._update_qm_widgets_visibility()
        if hasattr(self, "_refresh_metric_plots_for_mode"):
            self._refresh_metric_plots_for_mode()
        if hasattr(self, "_refresh_specific_bpm_candidates"):
            self._refresh_specific_bpm_candidates()

        if actuator_mode == "QM" and os.path.isfile(os.path.join(folder, "quadrupole_movers.txt")):
            actuator_filename = "quadrupole_movers.txt"
        else:
            actuator_filename = "correctors.txt"

        self._loading_func(elements_list=self.correctors_list, filename=actuator_filename,
                           loading_name="Load Actuators", use_dialog=False, base_dir=folder)
        self._loading_func(elements_list=self.bpms_list, filename="bpms.txt", loading_name="Load BPMs",
                           use_dialog=False, base_dir=folder)

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
                return
        QMessageBox.information(self.session_database_3, "Data directory selected", "Loaded session")

        if "w1" in settings: self.lineEdit.setText(str(settings["w1"]))
        if "w2" in settings: self.lineEdit_2.setText(str(settings["w2"]))
        if "w3" in settings: self.lineEdit_3.setText(str(settings["w3"]))
        if "rcond" in settings: self.lineEdit_4.setText(str(settings["rcond"]))
        if "iters" in settings:  self.lineEdit_5.setText(str(settings["iters"]))
        if "gain" in settings: self.lineEdit_6.setText(str(settings["gain"]))
        if "beta" in settings: self.lineEdit_beta.setText(str(settings["beta"]))
        if "is_triangular" in settings: self.triangular_checkbox.setChecked(settings["is_triangular"])
        if "is_jitter_subtraction_checked" in settings: self.subtract_jitter_checkbox.setChecked(settings["is_jitter_subtraction_checked"])
        if "bpm_weights" in settings:
            for bpm_name, weights in settings["bpm_weights"].items():
                try:
                    w1_bpm, w2_bpm, w3_bpm = weights
                    self.bpm_weights[str(bpm_name)] = (float(w1_bpm), float(w2_bpm), float(w3_bpm))
                except Exception:
                    continue
            for i in range(self.bpms_list.count()):
                item = self.bpms_list.item(i)
                self._update_bpm_weights(item)

        data_dirs = settings.get("data_dirs") or {}
        if hasattr(self, "trajectory_response_3"):
            self.trajectory_response_3.setText(data_dirs.get("traj") or "")

        if actuator_mode == "Kicker":
            if "max_horizontal_current" in settings:
                self.max_horizontal_current_spinbox.setValue(settings["max_horizontal_current"])
            if "max_vertical_current" in settings:
                self.max_vertical_current_spinbox.setValue(settings["max_vertical_current"])
            if hasattr(self, "dfs_response_3"):
                self.dfs_response_3.setText(data_dirs.get("dfs") or "")
            if hasattr(self, "wfs_response_3"):
                self.wfs_response_3.setText(data_dirs.get("wfs") or "")
        else:
            if hasattr(self, "_refresh_specific_bpm_candidates"):
                self._refresh_specific_bpm_candidates()
            if "specific_bpm" in settings and hasattr(self, "specific_bpm_combo"):
                idx = self.specific_bpm_combo.findText(str(settings["specific_bpm"]))
                if idx >= 0:
                    self.specific_bpm_combo.setCurrentIndex(idx)
            if "max_horizontal_range" in settings:
                self.max_horizontal_current_spinbox.setValue(settings["max_horizontal_range"])
            if "max_vertical_range" in settings:
                self.max_vertical_current_spinbox.setValue(settings["max_vertical_range"])

    def save_emittance_measurement_session(self,session):
        time_str = datetime.now().strftime("%y%m%d%H%M%S")
        default_dir=os.path.expanduser(os.path.expandvars("~/CERN-Flight_Simulator-Data/"))
        save_session_dir=os.path.join(default_dir, f"EmittanceMeasurement_{self.interface.get_name()}{time_str}_session")
        os.makedirs(save_session_dir, exist_ok=True)

        self._saving_func(elements_list=self.quadrupoles_list, filename="quadrupoles.txt",saving_name="Save quadrupoles",use_dialog=False, base_dir=save_session_dir)
        self._saving_func(elements_list=self.screens_list, filename="screens.txt",saving_name="Save screens",use_dialog=False, base_dir=save_session_dir)

        with open(os.path.join(save_session_dir,"emittance_session.pkl"),"wb") as f: # write in a binary format
            pickle.dump(session,f)

        self.session_database.setText(save_session_dir)

        return save_session_dir


    def load_emittance_measurement_session(self):
        default_dir = os.path.expanduser(os.path.expandvars("~/CERN-Flight_Simulator-Data/"))
        os.makedirs(default_dir, exist_ok=True)
        folder = QFileDialog.getExistingDirectory(self, "Select database", default_dir)
        if not folder:
            return
        self._loading_func(elements_list=self.quadrupoles_list, filename="quadrupoles.txt", loading_name="Load quadrupoles", use_dialog=False, base_dir=folder)
        self._loading_func(elements_list=self.screens_list, filename="screens.txt", loading_name="Load screens", use_dialog=False, base_dir=folder)

        session_path=os.path.join(folder, "emittance_session.pkl")
        if not os.path.isfile(session_path):
            QMessageBox.warning(self, "Load session", "Session not found")
            return None
        try:
            with open(session_path,"rb") as f:
                session=pickle.load(f)
        except Exception:
            QMessageBox.warning(self, "Load session", "Session not found")
            return None
        self.session_database.setText(folder)
        return session

        self.session_database.setText(save_session_dir)

        return save_session_dir

    def save_session_settings_qm_correction(self, w1, w2, w3, specific_bpm, rcond, iters, gain, beta, max_horizontal_range, max_vertical_range, is_triangular, bpm_weights, response, is_jitter_subtraction_checked):
        time_str = datetime.now().strftime("%y%m%d%H%M%S")
        default_dir = os.path.expanduser(os.path.expandvars("~/CERN-Flight_Simulator-Data/"))
        save_session_dir = os.path.join(default_dir, f"BBA_{self.interface.get_name()}{time_str}_QM_session_settings")
        os.makedirs(save_session_dir, exist_ok=True)
        self._saving_func(elements_list=self.correctors_list, filename="quadrupole_movers.txt", saving_name="Save Quadrupole Movers", use_dialog=False, base_dir=save_session_dir)
        self._saving_func(elements_list=self.bpms_list, filename="bpms.txt", saving_name="Save BPMs", use_dialog=False, base_dir=save_session_dir)
        correction_settings = {
            "actuator_mode": "QM",
            "w1": w1,
            "w2": w2,
            "w3": w3,
            "specific_bpm": specific_bpm,
            "rcond": rcond,
            "iters": iters,
            "gain": gain,
            "beta": beta,
            "max_horizontal_range": max_horizontal_range,
            "max_vertical_range": max_vertical_range,
            "is_triangular": is_triangular,
            "is_jitter_subtraction_checked": is_jitter_subtraction_checked,
            "bpm_weights": bpm_weights,
            "data_dirs": {
                k: (self._expand_data_path(v["dir"]) if v else None)
                for k, v in self._data_dirs.items()
            },
        }

        with open(os.path.join(save_session_dir, "correction_settings.json"), "w") as f:
            json.dump(correction_settings, f, indent=2)

        def __save_graph_data(path, series):
            with open(path, "w") as f:
                f.write("Iteration\tvalue\n")
                for i, v in enumerate(series, start=1):
                    f.write(f"{i}\t{v}\n")

        __save_graph_data(os.path.join(save_session_dir, "trajectory_x_after_correction.txt"), self._hist_orbit_x)
        __save_graph_data(os.path.join(save_session_dir, "trajectory_y_after_correction.txt"), self._hist_orbit_y)
        __save_graph_data(os.path.join(save_session_dir, "trajectory_combined_after_correction.txt"), self._hist_orbit)
        __save_graph_data(os.path.join(save_session_dir, "orbit_rms_x_after_correction.txt"), self._hist_abs_rms_x)
        __save_graph_data(os.path.join(save_session_dir, "orbit_rms_y_after_correction.txt"), self._hist_abs_rms_y)
        __save_graph_data(os.path.join(save_session_dir, "orbit_rms_xy_after_correction.txt"), self._hist_abs_rms_xy)

        qm_matrices = {}
        if response is not None:
            for key in ("qcorrs", "bpms", "R_xx", "R_xy", "R_yx", "R_yy", "T_xx", "T_yy"):
                if key in response:
                    qm_matrices[key] = response[key]

        with open(os.path.join(save_session_dir, "qm_correction_matrices.pkl"), "wb") as f:
            pickle.dump(qm_matrices, f)

        return save_session_dir