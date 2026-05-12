import os, sys, matplotlib, pickle, time
from datetime import datetime
from Backend.ResponseMatrix_DFS_WFS import ResponseMatrix_DFS_WFS
import numpy as np
matplotlib.use("QtAgg")
try:
    pyqt_version = 6
    from PyQt6.QtWidgets import (
        QDialog, QVBoxLayout, QDialogButtonBox,
        QRadioButton, QLabel,QFileDialog, QApplication
        )
    from PyQt6.QtCore import QEvent, Qt
except ImportError:
    pyqt_version = 5
    from PyQt5.QtWidgets import (
        QDialog, QVBoxLayout, QDialogButtonBox,
        QRadioButton, QLabel, QFileDialog, QApplication
    )
    from PyQt5.QtCore import QEvent, Qt
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from scipy.optimize import least_squares

class QuadrupoleScan_EM:

    # 1 screen, steps = 0: run scan -> otherwise, we get only one sigma2 value, but we need to fit emit, beta and alpha
    # 2 screens: run scan
    # 3 screens: no need for scan, but no coupling terms
    # 4+ screens: no need for scan

    def run_scan(self, quad_name, screens, delta_min, delta_max, steps, nshots, bpms=None, reference_screen=None, progress_callback=None):
        if isinstance(quad_name, str):
            quad_names = [quad_name]
        else:
            quad_names = list(quad_name)
        if len(quad_names) == 0:
            raise ValueError("At least one quadrupole must be provided")

        if len(quad_names) == 1:
            return self._run_single_scan(quad_name=quad_names[0], screens=screens, delta_min=delta_min, delta_max=delta_max, steps=steps, nshots=nshots, bpms=bpms, reference_screen=reference_screen, progress_callback=progress_callback)
        per_quad_sessions = []
        cancelled = False
        skipped_quadrupoles = []
        completed_quadrupoles = []

        total_quads = len(quad_names)
        for quad_idx, quad_name in enumerate(quad_names):
            if getattr(self, "_scan_stop_requested", False) or getattr(self, "_cancel", False):
                cancelled = True
                break

            def _wrapped_progress(session_partial, i, nsteps, _quad_idx=quad_idx, _quad_name=quad_name):
                merged_partial = {
                    "mode": "multi_quad_scan",
                    "quadrupoles": quad_names,
                    "current_quadrupole": _quad_name,
                    "current_quadrupole_index": int(_quad_idx),
                    "total_quadrupoles": int(total_quads),
                    "completed_quadrupoles": list(completed_quadrupoles),
                    "skipped_quadrupoles": list(skipped_quadrupoles),
                    "per_quad_sessions": per_quad_sessions + [session_partial],
                    "cancelled": bool(session_partial.get("cancelled", False)),
                }
                if progress_callback is not None:
                    progress_callback(merged_partial, i, nsteps)

            try:
                single_session = self._run_single_scan(
                    quad_name=quad_name,
                    screens=screens,
                    delta_min=delta_min,
                    delta_max=delta_max,
                    steps=steps,
                    nshots=nshots,
                    bpms=bpms,
                    reference_screen=reference_screen,
                    progress_callback=_wrapped_progress,
                )
            except ValueError as e:
                msg = str(e)
                if "zero K1_0" in msg:
                    skipped_quadrupoles.append({"quad_name": quad_name, "reason": msg})
                    continue
                raise

            per_quad_sessions.append(single_session)
            completed_quadrupoles.append(quad_name)

            if bool(single_session.get("cancelled", False)):
                cancelled = True
                break

        return {
            "mode": "multi_quad_scan",
            "quadrupoles": quad_names,
            "screens": list(screens),
            "reference_screen": reference_screen if reference_screen is not None else (
                list(screens)[0] if len(list(screens)) > 0 else None),
            "bpms": list(bpms) if bpms is not None else None,
            "delta_min": float(delta_min),
            "delta_max": float(delta_max),
            "steps": int(steps),
            "nsteps_scan": 1 if int(steps) == 0 else int(steps),
            "measurement_mode": "conventional_multi_screen_em" if int(steps) == 0 else "quadrupole_scan",
            "is_conventional_em": bool(int(steps) == 0),
            "nshots": int(nshots),
            "per_quad_sessions": per_quad_sessions,
            "completed_quadrupoles": list(completed_quadrupoles),
            "skipped_quadrupoles": list(skipped_quadrupoles),
            "cancelled": bool(cancelled),
        }

    def _run_single_scan(self, quad_name, screens, delta_min, delta_max, steps, nshots, bpms = None, reference_screen=None, progress_callback=None):
        screens = list(screens)
        if bpms is None:
            bpms = list(self.interface.get_bpms()["names"])
        else:
            bpms = list(bpms)

        if len(screens) == 0:
            raise ValueError("At least one screen is required")
        if reference_screen is None:
            reference_screen = screens[0]
        if reference_screen not in screens:
            raise ValueError("reference_screen must be one of the selected screens")
        steps_requested = int(steps)
        if steps_requested < 0:
            raise ValueError("steps must be zero or positive")
        if steps_requested > 0 and delta_max <= delta_min:
            raise ValueError("delta_max must be larger than delta_min")

        screens = [reference_screen] + [s for s in screens if s != reference_screen] # so that reference screen is first on the list
        quadrupoles = self.interface.get_quadrupoles()
        quad_names = list(quadrupoles["names"])
        if quad_name not in quad_names:
            raise ValueError("Quadrupole name not found in quadrupoles")

        quad_index = quad_names.index(quad_name)
        K1_0 = float(quadrupoles["bdes"][quad_index])
        if np.isclose(K1_0, 0.0):
            raise ValueError("This quadrupole has zero K1_0. You should choose another one.")

        if steps_requested == 0:
            deltas = np.array([0.0], dtype=float)
            K1_values = np.array([K1_0], dtype=float)
            measurement_mode = "conventional_multi_screen_em"
        else:
            deltas = np.linspace(float(delta_min), float(delta_max), steps_requested)
            K1_values = K1_0 * (1 + deltas)
            measurement_mode = "quadrupole_scan"

        nsteps_scan = len(K1_values)
        nscreens = len(screens)
        nbpms = len(bpms)

        sigx_mean = np.full((nsteps_scan, nscreens), np.nan, dtype=float)
        sigy_mean = np.full((nsteps_scan, nscreens), np.nan, dtype=float)
        sigx_std = np.full((nsteps_scan, nscreens), np.nan, dtype=float)
        sigy_std = np.full((nsteps_scan, nscreens), np.nan, dtype=float)
        scan_steps = []

        output_dir = self._get_scan_dir(quad_name)
        cancel_requested = False

        try:
            for k, screen_name in enumerate(screens):
                while getattr(self, "_scan_pause_requested", False) and not getattr(self, "_scan_stop_requested", False):
                    setattr(self, "_scan_is_paused", True)
                    QApplication.processEvents()
                    time.sleep(0.05)

                setattr(self, "_scan_is_paused", False)

                if getattr(self, "_scan_stop_requested", False):
                    raise KeyboardInterrupt("Scan stopped by user.")
                if getattr(self, "_cancel", False):
                    cancel_requested = True
                    break

                insert_screen = getattr(self.interface, "insert_screen", None)
                extract_screen = getattr(self.interface, "extract_screen", None)
                if callable(insert_screen):
                    insert_screen(screen_name)

                try:
                    for i, K1 in enumerate(K1_values):
                        while getattr(self, "_scan_pause_requested", False) and not getattr(self, "_scan_stop_requested", False):
                            setattr(self, "_scan_is_paused", True)
                            QApplication.processEvents()
                            time.sleep(0.05)
                        setattr(self, "_scan_is_paused", False)

                        if getattr(self, "_scan_stop_requested", False):
                            raise KeyboardInterrupt("Scan stopped by user.")
                        if getattr(self, "_cancel", False):
                            cancel_requested = True
                            break

                        self.interface.set_quadrupoles([quad_name], [float(K1)])
                        sx_shots = np.full(nshots, np.nan, dtype=float)
                        sy_shots = np.full(nshots, np.nan, dtype=float)
                        state_files = []
                        for j in range(nshots):
                            while getattr(self, "_scan_pause_requested", False) and not getattr(self, "_scan_stop_requested", False):
                                setattr(self, "_scan_is_paused", True)
                                QApplication.processEvents()
                                time.sleep(0.05)

                            setattr(self, "_scan_is_paused", False)
                            if getattr(self, "_scan_stop_requested", False):
                                raise KeyboardInterrupt("Scan stopped by user.")
                            if getattr(self, "_cancel", False):
                                cancel_requested = True
                                break

                            state = self.interface.get_state()
                            state_filename = os.path.join(output_dir, f"screen_{k:04d}_step_{i:04d}_shot_{j:04d}.pkl")
                            state.save(filename=state_filename)
                            state_files.append(state_filename)
                            screens_data = state.get_screens([screen_name])
                            screen_name_to_index = {name: index for index, name in enumerate(screens_data["names"])}
                            idx = screen_name_to_index.get(screen_name)
                            if idx is not None:
                                sx_shots[j] = float(screens_data["sigx"][idx])
                                sy_shots[j] = float(screens_data["sigy"][idx])
                        if state_files:
                            sigx_mean[i, k] = np.nanmean(sx_shots)
                            sigy_mean[i, k] = np.nanmean(sy_shots)
                            sigx_std[i, k] = np.nanstd(sx_shots)
                            sigy_std[i, k] = np.nanstd(sy_shots)
                        existing_step = next((step for step in scan_steps if int(step.get("step_index", -1)) == int(i)), None)
                        if existing_step is None:
                            existing_step = {
                                "step_index": int(i),
                                "delta": float(deltas[i]),
                                "K1": float(K1),
                                "state_files": [],
                            }
                            scan_steps.append(existing_step)
                        existing_step["state_files"].extend(state_files)

                        session_partial = {
                            "mode": "single_quad_scan",
                            "delta_min": float(delta_min),
                            "delta_max": float(delta_max),
                            "steps": int(steps_requested),
                            "nshots": int(nshots),
                            "quad_name": quad_name,
                            "quadrupoles": [quad_name],
                            "screens": screens,
                            "reference_screen": reference_screen,
                            "K1_0": float(K1_0),
                            "sigx_mean": sigx_mean.tolist(),
                            "sigy_mean": sigy_mean.tolist(),
                            "sigx_std": sigx_std.tolist(),
                            "sigy_std": sigy_std.tolist(),
                            "deltas": deltas.tolist(),
                            "K1_values": K1_values.tolist(),
                            "scan_steps": scan_steps,
                            "states_dir": output_dir,
                            "measured_optics": None,
                            "fit_result_twiss_emit": None,
                            "cancelled": bool(cancel_requested),
                            "current_screen": screen_name,
                            "current_screen_index": int(k),
                            "measurement_mode": measurement_mode,
                            "is_conventional_em": bool(steps_requested == 0),
                            "nsteps_scan": int(nsteps_scan),
                        }

                        if progress_callback is not None:
                            completed = k * len(K1_values) + i + 1
                            total = len(screens) * len(K1_values)
                            progress_callback(session_partial, completed, total)
                        if cancel_requested:
                            break
                    if cancel_requested:
                        break

                finally:
                    if callable(extract_screen):
                        extract_screen(screen_name)
        finally:
            self.interface.set_quadrupoles([quad_name], [float(K1_0)])

        session = {
            "mode": "single_quad_scan",
            "delta_min": float(delta_min),
            "delta_max": float(delta_max),
            "steps": int(steps_requested),
            "nshots": int(nshots),
            "quad_name": quad_name,
            "quadrupoles": [quad_name],
            "screens": screens,
            "reference_screen": reference_screen,
            "bpms": bpms,
            "K1_0": float(K1_0),
            "sigx_mean": sigx_mean.tolist(),
            "sigy_mean": sigy_mean.tolist(),
            "sigx_std": sigx_std.tolist(),
            "sigy_std": sigy_std.tolist(),
            "deltas": deltas.tolist(),
            "K1_values": K1_values.tolist(),
            "scan_steps": scan_steps,
            "states_dir": output_dir,
            "measured_optics": None,
            "fit_result_twiss_emit": None,
            "cancelled": bool(cancel_requested),
            "measurement_mode": measurement_mode,
            "is_conventional_em": bool(steps_requested == 0),
            "nsteps_scan": int(nsteps_scan),
        }
        return session


    def _get_scan_dir(self,quad_name): # saves state files for each quadrupole
        base_dir=getattr(self,"dir_name",None)
        if not base_dir:
            base_dir=os.path.join(os.getcwd(),"emittance_measurement_session")
        scan_dir=os.path.join(base_dir,f"states_{quad_name}")
        os.makedirs(scan_dir,exist_ok=True) # if exists, no error while trying to create a folder
        return scan_dir