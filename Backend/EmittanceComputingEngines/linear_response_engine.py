import numpy as np
import os
from scipy.stats import median_abs_deviation
from Backend.EM_helpers.LinearResponse import LinearResponse
from Backend.EmittanceComputingEngines.AbstractComputingEngine import AbstractComputingEngine

class LinearResponseEngine(AbstractComputingEngine):

    name = "linear_r_response"
    display_name = "Linear R-response model"

    def fit_from_session(self, session, bounds=None):
        screens = list(session.get("screens", []))
        quad_name = session.get("quad_name")
        K1L_values = np.asarray(session.get("K1L_values", []), dtype=float)

        sigx = np.asarray(session.get("sigx_mean", []), dtype=float)
        sigy = np.asarray(session.get("sigy_mean", []), dtype=float)

        if not quad_name:
            raise ValueError("Session does not contain quad_name")
        if len(screens) < 3:
            raise RuntimeError("Direct linear R-response fit requires at least 3 screens.")
        if K1L_values.size != 1:
            raise RuntimeError("Direct linear R-response fit works only for fixed K1L, so use steps = 0.")
        if sigx.ndim != 2 or sigy.ndim != 2:
            raise ValueError("Invalid sigma array shape")
        if sigx.shape != sigy.shape:
            raise ValueError("sigx and sigy shapes do not match")
        if sigx.shape[0] != K1L_values.size:
            raise ValueError("K1L_values and sigma arrays have incompatible lengths")

        try:
            quad_k1l_0_readback = float(session.get("K1L_0", K1L_values[0]))
        except Exception:
            quad_k1l_0_readback = float(K1L_values[0])

        sigma2_x = np.asarray(sigx ** 2, dtype=float)
        sigma2_y = np.asarray(sigy ** 2, dtype=float)

        gamma_rel, beta_rel, beta_gamma = self.interface.get_beam_factors()

        if not np.isfinite(beta_gamma) or beta_gamma <= 0:
            raise RuntimeError("Invalid beam factors")

        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
        machine_name = getattr(self.interface, "machine_name", [])
        coefficients_path = os.path.join(project_root, "MachineLearning", str(machine_name), str(quad_name), "Linear_Response_coefficients.npz")
        dataset_path = os.path.join(project_root, "MachineLearning", str(machine_name), str(quad_name), "Linear_Response_dataset.npz")
        linear = LinearResponse(coefficients_path=coefficients_path, dataset_path=dataset_path, beta_gamma=beta_gamma)
        direct = linear.solve_twiss_from_measured_sigma2(screens=screens, sigma2_x=sigma2_x[0], sigma2_y=sigma2_y[0])

        pred_x = np.asarray(direct["pred_x"], dtype=float)
        pred_y = np.asarray(direct["pred_y"], dtype=float)

        res_x = pred_x - sigma2_x
        res_y = pred_y - sigma2_y

        data_res_x = res_x.reshape(-1)
        data_res_y = res_y.reshape(-1)

        rms_x = float(np.sqrt(np.nanmean(data_res_x ** 2))) if data_res_x.size else np.nan
        rms_y = float(np.sqrt(np.nanmean(data_res_y ** 2))) if data_res_y.size else np.nan
        mad_x = float(median_abs_deviation(data_res_x, scale="normal")) if data_res_x.size else np.nan
        mad_y = float(median_abs_deviation(data_res_y, scale="normal")) if data_res_y.size else np.nan

        per_screen_x = {screen: float(abs(res_x[0, i])) for i, screen in enumerate(screens)}
        per_screen_y = {screen: float(abs(res_y[0, i])) for i, screen in enumerate(screens)}

        worst_screen_x = max(per_screen_x, key=per_screen_x.get) if per_screen_x else None
        worst_screen_y = max(per_screen_y, key=per_screen_y.get) if per_screen_y else None

        result = {
            "screen0": screens[0],
            "quad_name": quad_name,
            "emit_x_norm": direct["emit_x_norm"],
            "emit_y_norm": direct["emit_y_norm"],
            "emit_x_geom": direct["emit_x_norm"] / beta_gamma * 1e3, # um
            "emit_y_geom": direct["emit_y_norm"] / beta_gamma * 1e3, # um
            "beta_x0": direct["beta_x0"],
            "alpha_x0": direct["alpha_x0"],
            "beta_y0": direct["beta_y0"],
            "alpha_y0": direct["alpha_y0"],
            "fit_x_cost": 0.0,
            "fit_y_cost": 0.0,
            "fit_x_residual_rms": rms_x,
            "fit_y_residual_rms": rms_y,
            "fit_x_residual_mad": mad_x,
            "fit_y_residual_mad": mad_y,
            "fit_x_residual_rms_per_screen": per_screen_x,
            "fit_y_residual_rms_per_screen": per_screen_y,
            "worst_screen_x": worst_screen_x,
            "worst_screen_y": worst_screen_y,
            "fit_x_found": True,
            "fit_y_found": True,
            "paused": False,
            "stopped": False,
            "fit_quadrupole_strength": False,
            "quad_k1l_0": quad_k1l_0_readback,
            "quad_k1l_0_is_fitted": False,
            "fit_method": self.name,
        }

        return {
            "result": result,
            "pred_x": pred_x,
            "pred_y": pred_y,
        }
