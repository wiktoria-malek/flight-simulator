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
from Backend.State import State

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

    def save_session_settings(self, w1, w2, w3, rcond, iters, gain, beta, max_horizontal_current,max_vertical_current, is_triangular,bpm_weights,Axx, Ayy,Axy,Ayx, Bx, By, is_jitter_subtraction_checked, machine_state_file):
        time_str = datetime.now().strftime("%y%m%d%H%M%S")
        default_dir = f"~/CERN-Flight_Simulator-Data/"
        default_dir = os.path.expanduser(os.path.expandvars(default_dir))
        save_session_dir = os.path.join(default_dir, f"BBA_{self.interface.get_name()}{time_str}_session_settings")
        os.makedirs(save_session_dir, exist_ok=True)
        self.session_database_3.setText(save_session_dir)

        if machine_state_file is not None:
            machine_state_file.save(filename=os.path.join(save_session_dir, "machine_status.pkl"))
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

    def load_emittance_measurement_session(self):
        default_dir = f"~/CERN-Flight_Simulator-Data/"
        default_dir = os.path.expanduser(os.path.expandvars(default_dir))
        os.makedirs(default_dir, exist_ok=True)
        folder = QFileDialog.getExistingDirectory(self, "Select database", default_dir)
        if not folder:
            return
        self.load_screens_data_database.setText(folder)
        quad_selected = None
        screens = []
        folder_base_name = os.path.basename(os.path.normpath(folder))
        if folder_base_name.startswith("states_"):
            quad_selected = folder_base_name.removeprefix("states_")
        else:
            quad_selected = None
        # load quadrupoles
        quad_txt = os.path.join(folder, "quadrupoles.txt")
        if os.path.isfile(quad_txt):
            self._loading_func(elements_list=self.quadrupoles_list, filename="quadrupoles.txt", loading_name="Load Quadrupoles", use_dialog=False, base_dir=folder)
            selected_quads = self.quadrupoles_list.selectedItems()
            if selected_quads:
                quad_selected = selected_quads[0].data(Qt.ItemDataRole.UserRole) or selected_quads[0].text()
        else:
            self.quadrupoles_list.clearSelection()
            if quad_selected:
                for it in self.quadrupoles_list.findItems(quad_selected, Qt.MatchFlag.MatchExactly):
                    it.setSelected(True)
            else:
                for name in os.listdir(folder):
                    if name.startswith("states_"):
                        quad_selected = name.removeprefix("states_")
                        for it in self.quadrupoles_list.findItems(quad_selected, Qt.MatchFlag.MatchExactly):
                            it.setSelected(True)
                        break

        emittance_settings_path = os.path.join(folder, "emittance_settings.json")

        state_files = []
        state_folder_path = folder
        for filename in sorted(os.listdir(state_folder_path)):
            if filename.endswith(".pkl"):
                state_files.append(os.path.join(state_folder_path, filename))
        self.loaded_state_files = state_files
        self.loaded_states_from_scan = []
        for state_file in state_files:
            try:
                self.loaded_states_from_scan.append(State(filename=state_file))
            except Exception as e:
                print(f"Couldn't load {state_file}, because {e}")
        print(f"Loaded {len(self.loaded_states_from_scan)} states")

        screens_txt = os.path.join(folder, "screens.txt")
        if os.path.isfile(screens_txt):
            # load screens
            self._loading_func(elements_list=self.screens_list, filename="screens.txt", loading_name="Load Screens", use_dialog=False, base_dir=folder)
            screens = [item.data(Qt.ItemDataRole.UserRole) or item.text() for item in self.screens_list.selectedItems()]
        else:
            screens_list_from_interface = list(getattr(self.interface, "screens", []))
            screens = []
            screen_indices = []
            for path in self.loaded_state_files:
                filename = os.path.basename(path)
                parts = filename.replace(".pkl", "").split("_")
                screen_i = int(parts[1]) # screen_0000_step_0003_shot_0001.pkl -> 0000
                if screen_i not in screen_indices:
                    screen_indices.append(screen_i)
            screens = [screens_list_from_interface[screen_i] for screen_i in sorted(screen_indices)]
            self.screens_list.clearSelection()
            for screen in screens:
                for it in self.screens_list.findItems(screen, Qt.MatchFlag.MatchExactly):
                    it.setSelected(True)

        if not os.path.isfile(emittance_settings_path):
            QMessageBox.warning(self, "Load session", "The folder doesn't contain scan settings values. Using currently set settings.")
            delta_min = float(self.delta_min_scan.value())
            delta_max = float(self.delta_max_scan.value())
            read_filenames = []
            for path in self.loaded_state_files:
                filename = os.path.basename(path)
                parts = filename.replace(".pkl", "").split("_")
                screen_i = int(parts[1]) # screen_0000_step_0003_shot_0001.pkl -> 0000
                step_i = int(parts[3]) # screen_0000_step_0003_shot_0001.pkl -> 0003
                shot_i = int(parts[5]) # screen_0000_step_0003_shot_0001.pkl -> 0001
                read_filenames.append((screen_i, step_i, shot_i))

            if not read_filenames:
                QMessageBox.warning(self, "Load session", "Couldn't find names like screen_0000_step_0003_shot_0001.pkl.")
                return

            nscreens = max(screen_i for screen_i, step_i, shot_i in read_filenames)+1
            nshots = max(shot_i for screen_i, step_i, shot_i in read_filenames)+1
            scan_steps = max(step_i for screen_i, step_i, shot_i in read_filenames)+1

            print(f"Nshots: {nshots}, Scan steps: {scan_steps}")

            initial_points_xopt = int(self.xopt_initial_points_spin.value())
            xopt_steps = int(self.xopt_steps_spin.value())
            ls_steps = int(self.nm_steps_spin.value())
            is_fit_quad_strength_checked = bool(self.fit_quadrupole_strength_checkbox.isChecked())
            self.emittance_settings = {
                "delta_min": delta_min,
                "delta_max": delta_max,
                "scan_steps": scan_steps,
                "nshots": nshots,
                "nscreens": nscreens,
                "initial_points_xopt": initial_points_xopt,
                "xopt_steps": xopt_steps,
                "ls_steps": ls_steps,
                "is_fit_quad_strength_checked": is_fit_quad_strength_checked,
                "screens": screens if screens is not None else [],
                "quad_name": quad_selected if quad_selected else None,
            }

        else:
            with open(emittance_settings_path, "r") as f:
                self.emittance_settings = json.load(f)


            if "delta_min" in self.emittance_settings: self.delta_min_scan.setValue(float(self.emittance_settings["delta_min"]))
            if "delta_max" in self.emittance_settings: self.delta_max_scan.setValue(float(self.emittance_settings["delta_max"]))
            if "scan_steps" in self.emittance_settings: self.steps_settings.setValue(float(self.emittance_settings["scan_steps"]))
            if "nshots" in self.emittance_settings: self.meas_per_step.setValue(float(self.emittance_settings["nshots"]))
            if "initial_points_xopt" in self.emittance_settings: self.xopt_initial_points_spin.setValue(int(self.emittance_settings["initial_points_xopt"]))
            if "xopt_steps" in self.emittance_settings: self.xopt_steps_spin.setValue(int(self.emittance_settings["xopt_steps"]))
            if "ls_steps" in self.emittance_settings: self.nm_steps_spin.setValue(int(self.emittance_settings["ls_steps"]))
            if "is_fit_quad_strength_checked" in self.emittance_settings: self.fit_quadrupole_strength_checkbox.setChecked(
                bool(self.emittance_settings["is_fit_quad_strength_checked"]))

        QMessageBox.information(self.load_screens_data_database, "Data directory selected", "Loaded session")


        return self.loaded_states_from_scan

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

    def save_emittance_measurement_session(self, session=None, initial_points_xopt=None, xopt_steps=None, ls_steps=None, is_fit_quad_strength_checked=None):
        save_session_dir = self.load_screens_data_database.text()
        os.makedirs(save_session_dir, exist_ok=True)
        self._saving_func(elements_list=self.quadrupoles_list, filename="quadrupoles.txt", saving_name="Save quadrupoles", use_dialog=False, base_dir=save_session_dir)
        self._saving_func(elements_list=self.screens_list, filename="screens.txt", saving_name="Save screens", use_dialog=False, base_dir=save_session_dir)
        settings_path = os.path.join(save_session_dir, "emittance_settings.json")

        if os.path.isfile(settings_path):
            try:
                with open(settings_path, "r") as f:
                    self.emittance_settings = json.load(f)
            except Exception:
                self.emittance_settings = {}
        else:
            self.emittance_settings = {}

        if session is not None:
            self.emittance_settings.update({
                "delta_min": session["delta_min"],
                "delta_max": session["delta_max"],
                "scan_steps": session["steps"],
                "nshots": session["nshots"],
                "data_session": self.load_screens_data_database.text(),
                "quad_name": session["quad_name"],
                "screens": session["screens"],
                "nscreens": session["nscreens"],
                "reference_screen": session.get("reference_screen"),
                "K1_0": session.get("K1_0"),
                "K1_values": session.get("K1_values"),
                "sigma_unit": session.get("sigma_unit", "mm"),
            })
        if initial_points_xopt is not None:
            self.emittance_settings["initial_points_xopt"] = int(initial_points_xopt)
        if xopt_steps is not None:
            self.emittance_settings["xopt_steps"] = int(xopt_steps)
        if ls_steps is not None:
            self.emittance_settings["ls_steps"] = int(ls_steps)
        if is_fit_quad_strength_checked is not None:
            self.emittance_settings["is_fit_quad_strength_checked"] = bool(is_fit_quad_strength_checked)
        with open(settings_path, "w") as f:
            json.dump(self.emittance_settings, f, indent=2)
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