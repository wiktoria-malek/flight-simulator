import numpy as np

try:
    from PyQt6.QtWidgets import QMessageBox
except ImportError:
    from PyQt5.QtWidgets import QMessageBox

from Backend.BBA_helpers.Sextupole_Restoration_Popup import Sextupole_Restoration_Popup

class Sextupole_Restoration_Logic:
    def _show_sextupole_restoration_popup(self):
        if self.sextupole_restoration_popup is None:
            self.sextupole_restoration_popup = Sextupole_Restoration_Popup(self)
        if not self.sextupole_restoration_history:
            QMessageBox.information(self, "Sextupole restoration", "No sextupole restoration data available yet.")
            return
        self.sextupole_restoration_popup.plot_sextupole_history(self.sextupole_restoration_history)
        self.sextupole_restoration_popup.show()
        self.sextupole_restoration_popup.raise_()
        self.sextupole_restoration_popup.activateWindow()

    def _snapshot_correction_params(self):
        def text_of(name):
            widget = getattr(self, name, None)
            return widget.text() if widget is not None else None

        return {
            "orbit_w": text_of("lineEdit"),
            "dfs_w": text_of("lineEdit_2"),
            "wfs_w": text_of("lineEdit_3"),
            "iters": text_of("lineEdit_5"),
            "actuator_mode": self.actuator_mode,
            "nominal_state": self.nominal_state,
            "reset_ref_orb": self.reset_ref_orb,
        }

    def _restore_correction_params(self, snapshot):
        def set_text(name, value):
            widget = getattr(self, name, None)
            if widget is not None and value is not None:
                widget.setText(value)

        set_text("lineEdit", snapshot["orbit_w"])
        set_text("lineEdit_2", snapshot["dfs_w"])
        set_text("lineEdit_3", snapshot["wfs_w"])
        set_text("lineEdit_5", snapshot["iters"])
        self.nominal_state = snapshot["nominal_state"]
        self.reset_ref_orb = snapshot["reset_ref_orb"]
        if self.actuator_mode != snapshot["actuator_mode"]:
            self.actuator_mode = snapshot["actuator_mode"]
            self.actuator_mode_combo.setCurrentText(self.actuator_mode.value)
            self._refresh_corrector_list()
            self._update_qm_widgets_visibility()
            self._refresh_specific_bpm_candidates()
            self._refresh_metric_plots_for_mode()


    def _orbit_residual_to_reference(self, state, reference_state, bpms):
        state = self._apply_jitter_subtraction_to_state(state)
        orbit = state.get_orbit(bpms)
        reference_orbit = reference_state.get_orbit(bpms)
        dx = np.asarray(orbit["x"], dtype=float).reshape(-1) - np.asarray(reference_orbit["x"], dtype=float).reshape(-1)
        dy = np.asarray(orbit["y"], dtype=float).reshape(-1) - np.asarray(reference_orbit["y"], dtype=float).reshape(-1)
        return {
            "dx": dx,
            "dy": dy,
            "rms_x": float(np.sqrt(np.nanmean(dx ** 2))),
            "rms_y": float(np.sqrt(np.nanmean(dy ** 2))),
            "rms_xy": float(np.sqrt(np.nanmean(dx ** 2 + dy ** 2))),
        }


    def _set_orbit_only_params(self, iters=None):
        self.lineEdit.setText("1.0")
        self.lineEdit_2.setText("0.0")
        self.lineEdit_3.setText("0.0")
        if iters is not None:
            self.lineEdit_5.setText(str(int(iters)))

    def _restore_sextupoles_one_by_one_with_orbit_correction(self, saved_state, golden_state, orbit_iters=None, steps_per_sextupole=1):
        sextupoles = saved_state.get_sextupoles()
        names = list(sextupoles["names"])
        values = np.asarray(sextupoles["bdes"], dtype=float).ravel()
        if len(names) == 0:
            return []

        targets = {str(name): float(value) for name, value in zip(names, values)}
        ordered_names = []
        seen = set()
        for name in names:
            key = str(name)
            if key in targets and key not in seen:
                ordered_names.append(key)
                seen.add(key)

        snapshot = self._snapshot_correction_params()
        history = []
        try:
            actuator_mode_cls = self.actuator_mode.__class__
            if self.actuator_mode != actuator_mode_cls.Kicker:
                self.actuator_mode = actuator_mode_cls.Kicker
                self.actuator_mode_combo.setCurrentText(actuator_mode_cls.Kicker.value)
                self._refresh_corrector_list()
                self._update_qm_widgets_visibility()
                self._refresh_specific_bpm_candidates()
                self._refresh_metric_plots_for_mode()

            self.nominal_state = golden_state
            self.reset_ref_orb = False
            self._set_orbit_only_params(iters=orbit_iters)

            _, bpms_for_summary = self._get_selection()
            bpms_for_summary = list(bpms_for_summary)

            steps = max(1, int(steps_per_sextupole))
            for name in ordered_names:
                if self._cancel:
                    break
                target = targets[name]
                if np.isclose(target, 0.0, rtol=0.0, atol=1e-15):
                    self.interface.set_sextupoles([name], [0.0])
                    self.log(f"Skipped sextupole {name}: nominal strength is zero.")
                    continue
                for step in range(1, steps + 1):
                    if self._cancel:
                        break
                    value = target * step / steps
                    self.interface.set_sextupoles([name], [value])
                    before = self._orbit_residual_to_reference(self.interface.get_state(), golden_state, bpms_for_summary)
                    self.log(f"Restored sextupole {name} to {value:g} ({step}/{steps}). Restoring post-BBA orbit with correctors.")
                    self.log(f"Residual before orbit correction for {name}: x={before['rms_x']:g}, y={before['rms_y']:g}, xy={before['rms_xy']:g}")
                    self.reset_ref_orb = False
                    old_suppress_main_plots = getattr(self, "_suppress_main_plots", False)
                    self._suppress_main_plots = True
                    try:
                        self._start_correction(silent=True, preserve_plots=True)
                    finally:
                        self._suppress_main_plots = old_suppress_main_plots
                    after = self._orbit_residual_to_reference(self.interface.get_state(), golden_state, bpms_for_summary)
                    self.log(f"Residual after orbit correction for {name}: x={after['rms_x']:g}, y={after['rms_y']:g}, xy={after['rms_xy']:g}")
                    history.append({
                        "name": name,
                        "step": step,
                        "steps": steps,
                        "value": value,
                        "bpms": list(bpms_for_summary),
                        "before_dx": before["dx"],
                        "before_dy": before["dy"],
                        "after_dx": after["dx"],
                        "after_dy": after["dy"],
                        "before_rms_x": before["rms_x"],
                        "before_rms_y": before["rms_y"],
                        "before_rms_xy": before["rms_xy"],
                        "after_rms_x": after["rms_x"],
                        "after_rms_y": after["rms_y"],
                        "after_rms_xy": after["rms_xy"],
                    })
        finally:
            self._restore_correction_params(snapshot)
        return history

    def filtering_norm_x(self, Ox, Bx):
        Ox[np.isnan(Ox)] = 0
        Bx[np.isnan(Bx)] = 0
        return float(np.linalg.norm(Ox - Bx))

    def filtering_norm_y(self, Oy, By):
        Oy[np.isnan(Oy)] = 0
        By[np.isnan(By)] = 0
        return float(np.linalg.norm(Oy - By))

