import numpy as np
from scipy.stats import median_abs_deviation, qmc
from scipy.optimize import minimize, least_squares
import pandas as pd
from xopt import Xopt
from xopt.vocs import VOCS, select_best
from xopt.evaluator import Evaluator
from xopt.generators.bayesian import ExpectedImprovementGenerator

class OptimizationStopped(Exception):
    def __init__(self, message = "Optimization stopped", solution = None):
        super().__init__(message)
        self.solution = solution

class OptimizationPaused(Exception):
    def __init__(self, message="Optimization paused", solution=None):
        super().__init__(message)
        self.solution = solution

class Optimization:
    def __init__(self, interface, n_starts=8, rng_seed=42, xopt_initial_points = 8, xopt_steps = 50, nm_steps = 100, fit_quadrupole_strength=False, progress_callback=None):
        self.progress_callback = progress_callback
        self.interface = interface
        self.n_starts = int(n_starts)
        self.rng = np.random.default_rng(rng_seed)
        self._stop_requested = False
        self._pause_requested = False
        self.best_out_so_far = None
        self._last_completed_output = None
        self.print_M = True
        self.xopt_initial_points = xopt_initial_points
        self.xopt_steps = xopt_steps
        self.nm_steps = nm_steps
        self.xopt_local_seed_fraction = 0.25
        self.xopt_use_global_seed = True
        self.xopt_local_alpha_sigma = 0.8
        self.xopt_local_refine = False
        self.xopt_local_refine_maxiter = 25
        self.fit_quadrupole_strength = bool(fit_quadrupole_strength)

    def _emit_progress(self, phase, current, total):
        if self.progress_callback is None:
            return
        self.progress_callback(str(phase), int(current), int(total))

    def request_pause(self):
        self._pause_requested = True

    def clear_pause(self):
        self._pause_requested = False

    def request_stop(self):
        self._stop_requested = True

    def clear_stop(self):
        self._stop_requested = False
        self.best_out_so_far = None
        self._last_completed_output = None
        self._pause_requested = False

    def _calculate_optimalization_errors(self, ls_result, n_params_fallback=None):
        n_default = int(n_params_fallback) if n_params_fallback is not None else 6

        if ls_result is None:
            return {
                "param_errors": np.full(n_default, np.nan),
                "cov": None,
                "reduced_chi2_like": np.nan,
                "chi2_like": np.nan,
            }

        try:
            J = np.asarray(ls_result.jac, dtype=float)
            r = np.asarray(ls_result.fun, dtype=float) # residual sigma^2 pred - sigma^2 meas
            p = np.asarray(ls_result.x, dtype=float)
        except AttributeError:
            return {
                "param_errors": np.full(n_default, np.nan),
                "cov": None,
                "reduced_chi2_like": np.nan,
                "chi2_like": np.nan,
            }

        ndata = len(r) # number of measurements
        npar = len(p) # number of parameters
        dof = max(ndata - npar, 1) # degrees of freedom

        chi2_like = float(np.sum(r ** 2)) # the smaller, the better the model
        reduced_chi2_like = chi2_like / dof # average error per 1 measurement

        try:
            """
            Cov = s^2 * (J.T * J )^(-1)
            s^2 = sum(r_i^2)/(N - p)
            on diagonal line of cov matrix are variances of parameters
            """

            cov = np.linalg.pinv(J.T @ J) * reduced_chi2_like
            param_errors = np.sqrt(np.maximum(np.diag(cov), 0.0))
        except Exception:
            cov = None
            param_errors = np.full(npar, np.nan)

        return {
            "param_errors": param_errors,
            "cov": cov,
            "reduced_chi2_like": reduced_chi2_like,
            "chi2_like": chi2_like,
        }

    def fit_from_session(self, session, bounds):
        was_pause_requested = bool(self._pause_requested)
        self.clear_stop()
        self._pause_requested = was_pause_requested
        if self.print_M:
            print("Starting to fit Twiss parameters and emittance...")
        screens = list(session.get("screens", []))
        quad_name = session.get("quad_name")
        K1_values = np.asarray(session.get("K1_values", []), dtype=float)

        try:
            quad_k1_0_readback = np.asarray(session.get("K1_0", K1_values[len(K1_values)//2] if K1_values.size else np.nan))
        except Exception:
            quad_k1_0_readback = np.nan

        sigx = np.asarray(session.get("sigx_mean", []), dtype=float)
        sigy = np.asarray(session.get("sigy_mean", []), dtype=float)
        sigx_std = np.asarray(session.get("sigx_std", []), dtype=float)
        sigy_std = np.asarray(session.get("sigy_std", []), dtype=float)

        if not quad_name:
            raise ValueError("Session does not contain quad_name")
        if len(screens) < 1:
            raise ValueError("At least one screen is required")
        if K1_values.size == 0:
            raise ValueError("Session does not contain K1_values")
        if sigx.ndim != 2 or sigy.ndim != 2:
            raise ValueError("Invalid sigma array shape")
        if sigx.shape != sigy.shape:
            raise ValueError("sigx and sigy shapes do not match")
        if sigx.shape[0] != K1_values.size:
            raise ValueError("K1_values and sigma arrays have incompatible lengths")
        if not bounds:
            raise ValueError("Add bounds for optimizer to interface_setup.py")

        sigma2_template_x = np.asarray(sigx ** 2 if sigx.size else np.empty((0, len(screens))), dtype=float)
        sigma2_template_y = np.asarray(sigy ** 2 if sigy.size else np.empty((0, len(screens))), dtype=float)

        def _plane_no_solution(plane_name, sigma2_template):
            return {
                "emit": np.nan,
                "beta0": np.nan,
                "alpha0": np.nan,
                "pred": np.full_like(sigma2_template, np.nan, dtype=float),
                "residual_rms": np.nan,
                "residual_mad": np.nan,
                "residual_rms_per_screen": {screen: np.nan for screen in screens},
                "worst_screen": None,
                "success": False,
                "message": f"No solution found yet for plane {plane_name}",
                "cost": np.nan,
                "stopped": True,
            }
        joint_fit = None
        fit_x = None
        fit_y = None

        try:
            joint_fit = self._fit_6d(screens=screens, quad_name=quad_name, K1_values=K1_values,
                                    sigx=sigx, sigx_std=sigx_std, sigy=sigy, sigy_std=sigy_std, bounds = bounds)

            fit_x = {
                "emit": joint_fit["emit_x_geom"],
                "beta0": joint_fit["beta_x0"],
                "alpha0": joint_fit["alpha_x0"],
                "pred": joint_fit["pred_x"],
                "residual_rms": joint_fit["residual_rms_x"],
                "residual_mad": joint_fit["residual_mad_x"],
                "residual_rms_per_screen": joint_fit["residual_rms_per_screen_x"],
                "worst_screen": joint_fit["worst_screen_x"],
                "success": joint_fit["success"],
                "message": joint_fit["message"],
                "cost": joint_fit["cost"],
                "stopped": bool(joint_fit.get("stopped", False)),
            }
            fit_y = {
                "emit": joint_fit["emit_y_geom"],
                "beta0": joint_fit["beta_y0"],
                "alpha0": joint_fit["alpha_y0"],
                "pred": joint_fit["pred_y"],
                "residual_rms": joint_fit["residual_rms_y"],
                "residual_mad": joint_fit["residual_mad_y"],
                "residual_rms_per_screen": joint_fit["residual_rms_per_screen_y"],
                "worst_screen": joint_fit["worst_screen_y"],
                "success": joint_fit["success"],
                "message": joint_fit["message"],
                "cost": joint_fit["cost"],
                "stopped": bool(joint_fit.get("stopped", False)),
            }

            if self.print_M:
                print(
                    f"Joint fit done: success={joint_fit['success']}, cost={joint_fit['cost']:.6g}, "
                    f"emit_x_geom={joint_fit['emit_x_geom']:.6g}, beta_x0={joint_fit['beta_x0']:.6g}, alpha_x0={joint_fit['alpha_x0']:.6g}, "
                    f"emit_y_geom={joint_fit['emit_y_geom']:.6g}, beta_y0={joint_fit['beta_y0']:.6g}, alpha_y0={joint_fit['alpha_y0']:.6g}"
                )

        except (OptimizationStopped, OptimizationPaused) as e:
            if isinstance(getattr(e, "solution", None), dict):
                joint_fit = e.solution
                fit_x = {
                        "emit": joint_fit["emit_x_geom"],
                        "beta0": joint_fit["beta_x0"],
                        "alpha0": joint_fit["alpha_x0"],
                        "pred": joint_fit["pred_x"],
                        "residual_rms": joint_fit["residual_rms_x"],
                        "residual_mad": joint_fit["residual_mad_x"],
                        "residual_rms_per_screen": joint_fit["residual_rms_per_screen_x"],
                        "worst_screen": joint_fit["worst_screen_x"],
                        "success": joint_fit["success"],
                        "message": joint_fit["message"],
                        "cost": joint_fit["cost"],
                        "stopped": True,
                    }
                fit_y = {
                        "emit": joint_fit["emit_y_geom"],
                        "beta0": joint_fit["beta_y0"],
                        "alpha0": joint_fit["alpha_y0"],
                        "pred": joint_fit["pred_y"],
                        "residual_rms": joint_fit["residual_rms_y"],
                        "residual_mad": joint_fit["residual_mad_y"],
                        "residual_rms_per_screen": joint_fit["residual_rms_per_screen_y"],
                        "worst_screen": joint_fit["worst_screen_y"],
                        "success": joint_fit["success"],
                        "message": joint_fit["message"],
                        "cost": joint_fit["cost"],
                        "stopped": True,
                    }
            else:
                fit_x = None
                fit_y = None

        if fit_x is None:
            fit_x = _plane_no_solution("x", sigma2_template_x)
        if fit_y is None:
            fit_y = _plane_no_solution("y", sigma2_template_y)

        gamma_rel, beta_rel = self.interface.get_beam_factors()
        beta_gamma = (
            gamma_rel * beta_rel
            if np.isfinite(gamma_rel) and np.isfinite(beta_rel)
            else np.nan
        )
        emit_x_norm = (
            beta_gamma * fit_x["emit"]
            if np.isfinite(beta_gamma) and np.isfinite(fit_x["emit"])
            else np.nan
        )
        emit_y_norm = (
            beta_gamma * fit_y["emit"]
            if np.isfinite(beta_gamma) and np.isfinite(fit_y["emit"])
            else np.nan
        )

        emit_x_geom = fit_x["emit"]
        emit_y_geom = fit_y["emit"]

        stopped = bool(fit_x.get("stopped", False) or fit_y.get("stopped", False) or self._stop_requested)

        err_dict = {}
        reduced_chi2_like = np.nan
        chi2_like = np.nan
        if isinstance(joint_fit, dict):
            err_dict = dict(joint_fit.get("param_errors") or {})
            reduced_chi2_like = float(joint_fit.get("reduced_chi2_like", np.nan))
            chi2_like = float(joint_fit.get("chi2_like", np.nan))

        emit_x_norm_err = float(err_dict.get("emit_x_norm", np.nan))
        emit_y_norm_err = float(err_dict.get("emit_y_norm", np.nan))
        beta_x0_err = float(err_dict.get("beta_x0", np.nan))
        alpha_x0_err = float(err_dict.get("alpha_x0", np.nan))
        beta_y0_err = float(err_dict.get("beta_y0", np.nan))
        alpha_y0_err = float(err_dict.get("alpha_y0", np.nan))
        quad_k1_0_err = float(err_dict.get("quad_k1_0", np.nan))

        if np.isfinite(beta_gamma) and beta_gamma > 0:
            emit_x_geom_err = emit_x_norm_err / beta_gamma * 1e3 if np.isfinite(emit_x_norm_err) else np.nan
            emit_y_geom_err = emit_y_norm_err / beta_gamma * 1e3 if np.isfinite(emit_y_norm_err) else np.nan
        else:
            emit_x_geom_err = np.nan
            emit_y_geom_err = np.nan

        result = {
            "screen0": screens[0],
            "quad_name": quad_name,
            "emit_x_norm": emit_x_norm,
            "emit_y_norm": emit_y_norm,
            "emit_x_geom": emit_x_geom * 1e3 , # nm*rad
            "emit_y_geom": emit_y_geom * 1e3, # nm*rad
            "beta_x0": fit_x["beta0"],
            "alpha_x0": fit_x["alpha0"],
            "beta_y0": fit_y["beta0"],
            "alpha_y0": fit_y["alpha0"],
            "fit_x_success": fit_x["success"],
            "fit_y_success": fit_y["success"],
            "fit_x_message": fit_x["message"],
            "fit_y_message": fit_y["message"],
            "fit_x_cost": fit_x["cost"],
            "fit_y_cost": fit_y["cost"],
            "fit_x_residual_rms": fit_x["residual_rms"],
            "fit_y_residual_rms": fit_y["residual_rms"],
            "fit_x_residual_mad": fit_x["residual_mad"],
            "fit_y_residual_mad": fit_y["residual_mad"],
            "fit_x_residual_rms_per_screen": fit_x["residual_rms_per_screen"],
            "fit_y_residual_rms_per_screen": fit_y["residual_rms_per_screen"],
            "worst_screen_x": fit_x["worst_screen"],
            "worst_screen_y": fit_y["worst_screen"],
            "fit_x_found": bool(np.isfinite(fit_x["emit"])),
            "fit_y_found": bool(np.isfinite(fit_y["emit"])),
            "paused": bool(self._pause_requested),
            "stopped": stopped,
            "fit_quadrupole_strength": bool(self.fit_quadrupole_strength),
            "quad_k1_0": (
                float(joint_fit.get("quad_k1_0", np.nan))
                if bool(self.fit_quadrupole_strength) and isinstance(joint_fit, dict)
                else quad_k1_0_readback
            ),
            "quad_k1_0_is_fitted": bool(self.fit_quadrupole_strength),
            "emit_x_norm_err": emit_x_norm_err,
            "emit_y_norm_err": emit_y_norm_err,
            "emit_x_geom_err": emit_x_geom_err,
            "emit_y_geom_err": emit_y_geom_err,
            "beta_x0_err": beta_x0_err,
            "alpha_x0_err": alpha_x0_err,
            "beta_y0_err": beta_y0_err,
            "alpha_y0_err": alpha_y0_err,
            "quad_k1_0_err": quad_k1_0_err,
            "fit_reduced_chi2_like": reduced_chi2_like,
            "fit_chi2_like": chi2_like,
        }

        output = {
            "result": result,
            "pred_x": fit_x["pred"],
            "pred_y": fit_y["pred"],
        }
        self.best_out_so_far = output
        self._last_completed_output = output
        self._pause_requested = False

        if self.print_M:
            print(
                f"Final result: "
                f"stopped={result['stopped']}, "
                f"emit_x_norm={result['emit_x_norm']:.6g}, "
                f"emit_y_norm={result['emit_y_norm']:.6g}, "
                f"fit_x_cost={result['fit_x_cost']:.6g}, "
                f"fit_y_cost={result['fit_y_cost']:.6g}"
            )
            print(
                f"Partial solution: "
                f"fit_x_found={result['fit_x_found']}, "
                f"fit_y_found={result['fit_y_found']}"
            )

        return output

    def _build_joint_partial_output(self, screens, sigma2_x, sigma2_y, pred2_x, pred2_y, best_row, best_cost):
        if best_row is None or pred2_x is None or pred2_y is None:
            return None
        per_screen_res_x = {screen: [] for screen in screens}
        per_screen_res_y = {screen: [] for screen in screens}
        data_res_x = []
        data_res_y = []

        for k in range(pred2_x.shape[0]):
            for i, screen in enumerate(screens):
                yx = sigma2_x[k, i]
                ypx = pred2_x[k, i]
                if np.isfinite(yx) and np.isfinite(ypx):
                    rx = (ypx - yx)
                    data_res_x.append(rx)
                    per_screen_res_x[screen].append(rx)

                yy = sigma2_y[k, i]
                ypy = pred2_y[k, i]
                if np.isfinite(yy) and np.isfinite(ypy):
                    ry = (ypy - yy)
                    data_res_y.append(ry)
                    per_screen_res_y[screen].append(ry)

        data_res_x = np.asarray(data_res_x, dtype=float)
        data_res_y = np.asarray(data_res_y, dtype=float)

        rms_res_x = float(np.sqrt(np.mean(data_res_x ** 2))) if data_res_x.size else np.nan
        rms_res_y = float(np.sqrt(np.mean(data_res_y ** 2))) if data_res_y.size else np.nan
        mad_res_x = float(median_abs_deviation(data_res_x, scale="normal")) if data_res_x.size else np.nan
        mad_res_y = float(median_abs_deviation(data_res_y, scale="normal")) if data_res_y.size else np.nan

        per_screen_rms_x = {}
        per_screen_rms_y = {}
        for screen in screens:
            arrx = np.asarray(per_screen_res_x[screen], dtype=float)
            arry = np.asarray(per_screen_res_y[screen], dtype=float)
            per_screen_rms_x[screen] = float(np.sqrt(np.mean(arrx ** 2))) if arrx.size else np.nan
            per_screen_rms_y[screen] = float(np.sqrt(np.mean(arry ** 2))) if arry.size else np.nan

        finite_x = [(screen, val) for screen, val in per_screen_rms_x.items() if np.isfinite(val)]
        finite_y = [(screen, val) for screen, val in per_screen_rms_y.items() if np.isfinite(val)]
        worst_screen_x = max(finite_x, key=lambda x: x[1])[0] if finite_x else None
        worst_screen_y = max(finite_y, key=lambda x: x[1])[0] if finite_y else None

        gamma_rel, beta_rel = self.interface.get_beam_factors()
        beta_gamma = gamma_rel * beta_rel

        emit_x_geom = max(float(best_row["emit_x_norm"]) / beta_gamma, 1e-12) if np.isfinite(beta_gamma) and beta_gamma > 0 else np.nan
        emit_y_geom = max(float(best_row["emit_y_norm"]) / beta_gamma, 1e-12) if np.isfinite(beta_gamma) and beta_gamma > 0 else np.nan

        return {
            "emit_x_geom": emit_x_geom,
            "beta_x0": float(best_row["beta_x0"]),
            "alpha_x0": float(best_row["alpha_x0"]),
            "emit_y_geom": emit_y_geom,
            "beta_y0": float(best_row["beta_y0"]),
            "alpha_y0": float(best_row["alpha_y0"]),
            "pred_x": pred2_x,
            "pred_y": pred2_y,
            "emit_x_norm": float(best_row["emit_x_norm"]),
            "emit_y_norm": float(best_row["emit_y_norm"]),
            "residual_rms_x": rms_res_x,
            "residual_rms_y": rms_res_y,
            "residual_mad_x": mad_res_x,
            "residual_mad_y": mad_res_y,
            "residual_rms_per_screen_x": per_screen_rms_x,
            "residual_rms_per_screen_y": per_screen_rms_y,
            "worst_screen_x": worst_screen_x,
            "worst_screen_y": worst_screen_y,
            "success": True,
            "message": "Best joint solution found so far.",
            "cost": float(best_cost) if np.isfinite(best_cost) else np.nan,
            "stopped": True,
        }

    def _fit_6d(self, screens, quad_name, K1_values, sigx, sigx_std, sigy, sigy_std, bounds):
        sigx = np.asarray(sigx, dtype=float)
        sigy = np.asarray(sigy, dtype=float)
        sigx_std = np.asarray(sigx_std, dtype=float)
        sigy_std = np.asarray(sigy_std, dtype=float)
        sig_x2 = sigx ** 2
        sig_y2 = sigy ** 2

        valid_x = np.isfinite(sig_x2)
        valid_y = np.isfinite(sig_y2)

        if not np.any(valid_x) and not np.any(valid_y): # if False
            raise RuntimeError(f"No valid measurements for joint fit")

        gamma_rel, beta_rel = self.interface.get_beam_factors()
        beta_gamma = gamma_rel * beta_rel

        if not np.isfinite(beta_gamma) or beta_gamma <= 0:
            raise RuntimeError("Invalid beam factors")

        bounds = dict(bounds or {})
        required_bounds = ["emit_x_norm", "beta_x0", "alpha_x0", "emit_y_norm", "beta_y0", "alpha_y0"]
        missing_bounds = [name for name in required_bounds if name not in bounds]
        if missing_bounds:
            raise ValueError(f"Missing optimizer bounds in interface_setup.py: {missing_bounds}")
        K1_values = np.asarray(K1_values, dtype=float)
        K1_0_readback = float(K1_values[len(K1_values)//2])
        deltas_for_fit = K1_values / K1_0_readback - 1.0

        if self.fit_quadrupole_strength:
            low = 0.7 * K1_0_readback
            high = 1.3 * K1_0_readback
            bounds["quad_k1_0"] = [min(low,high), max(low,high)]


        vocs = VOCS( # degrees of freedom
            variables = {i: [float(vals[0]), float(vals[1])] for i, vals in bounds.items()
        },
            objectives={"f": "MINIMIZE"},
        )

        params_order = ["emit_x_norm", "beta_x0", "alpha_x0",
                       "emit_y_norm", "beta_y0", "alpha_y0"]

        if self.fit_quadrupole_strength:
            params_order.append("quad_k1_0")

        low_bounds = np.array([bounds[p][0] for p in params_order], dtype=float)
        high_bounds = np.array([bounds[p][1] for p in params_order], dtype=float)

        def predict_sigma2_from_fit_params(emit_x_norm, beta_x0, alpha_x0, emit_y_norm, beta_y0, alpha_y0, allow_stop = True, quad_k1_0 = None):
            '''
            If the beam at the scanned quadrupole has certain Twiss parameters and given emittance,
            what quadrupole scan should be?
            It's based on implementation in the RFTrack interface, where:
            it sets a quadrupole to each K1, builds a bunch with given Twiss parameters at quad_name,
            tracks only the lattice view from quad_name to the last selected screen,
            and reads beam sizes at screens.
            '''
            emit_x_norm = float(emit_x_norm)
            beta_x0 = float(beta_x0)
            alpha_x0 = float(alpha_x0)
            emit_y_norm = float(emit_y_norm)
            beta_y0 = float(beta_y0)
            alpha_y0 = float(alpha_y0)

            if emit_x_norm < 0.0 or emit_y_norm < 0.0 or beta_x0 < 0.0 or beta_y0 < 0.0:
                raise RuntimeError("Invalid joint fit paramaters. Emittance and beta should be positive.")
            emit_x_geom = emit_x_norm / beta_gamma
            emit_y_geom = emit_y_norm / beta_gamma

            if self.fit_quadrupole_strength:
                if quad_k1_0 is None:
                    raise RuntimeError("quad_k1_0 must be provided when fitting quadrupole strength.")
                K1_values_used = float(quad_k1_0) * (1.0 + deltas_for_fit)
            else:
                K1_values_used = K1_values

            try:
                pred_sigx, pred_sigy = self.interface.predict_emittance_scan_response(quad_name=quad_name, screens=screens,
                    K1_values=K1_values_used, emit_x=emit_x_norm, emit_y=emit_y_norm, beta_x0=beta_x0, beta_y0=beta_y0,
                    alpha_x0=alpha_x0, alpha_y0=alpha_y0, reference_screen=screens[0], stop_checker=(lambda: self._stop_requested or self._pause_requested) if allow_stop else None)

            except RuntimeError as e:
                if str(e) == "__OPTIMIZATION_STOP__":
                    if self._pause_requested:
                        raise OptimizationPaused("Optimization paused.")
                    raise OptimizationStopped("Optimization stopped.")
                raise
            pred_sigx = np.asarray(pred_sigx, dtype=float)
            pred_sigy = np.asarray(pred_sigy, dtype=float)
            if pred_sigx.shape != sigx.shape or pred_sigy.shape != sigy.shape:
                raise RuntimeError(f"Sigma shape does not match measured shape")
            return pred_sigx ** 2, pred_sigy ** 2

        def compute_cost(emit_x_norm, beta_x0, alpha_x0, emit_y_norm, beta_y0, alpha_y0, allow_stop = True, quad_k1_0 = None):
            '''
            It compares how well a scan is predicting a model, how much it differs from data and
            minimizes f, so that it's as small as possible.
            '''
            if allow_stop and (self._stop_requested or self._pause_requested):
                if self._pause_requested:
                    raise OptimizationPaused("Optimization paused.")
                raise OptimizationStopped("Optimization stopped.")
            pred2_x, pred2_y = predict_sigma2_from_fit_params(emit_x_norm, beta_x0, alpha_x0, emit_y_norm, beta_y0, alpha_y0, allow_stop = allow_stop, quad_k1_0 = quad_k1_0)
            rx = (pred2_x - sig_x2)[valid_x] if np.any(valid_x) else np.array([], dtype=float)
            ry = (pred2_y - sig_y2)[valid_y] if np.any(valid_y) else np.array([], dtype=float)
            # res = np.concatenate([np.asarray(rx, dtype = float).ravel(), np.asarray(ry, dtype = float).ravel()]) # the better the match, the smaller the number
            #
            # if res.size == 0:
            #     return np.inf, pred2_x, pred2_y
            # return float(np.mean(res**2)), pred2_x, pred2_y # so positive and negative residuals are not cancalled and fit doesn't think it's perfect, it also punishes better worse solutions

            # AS A TEST!
            rx = rx[np.isfinite(rx)]
            ry = ry[np.isfinite(ry)]

            scale_x = np.nanmedian(np.abs(sig_x2[valid_x])) ** 2 if np.any(valid_x) else 1.0
            scale_y = np.nanmedian(np.abs(sig_y2[valid_y])) ** 2 if np.any(valid_y) else 1.0

            scale_x = max(float(scale_x), 1e-30)
            scale_y = max(float(scale_y), 1e-30)

            cost_x = float(np.mean(rx ** 2)) / scale_x if rx.size else 0.0
            cost_y = float(np.mean(ry ** 2)) / scale_y if ry.size else 0.0

            return 0.5 * (cost_x + cost_y), pred2_x, pred2_y

        def evaluate(inputs):
            if self._stop_requested or self._pause_requested:
                return {"f": 12.0, "cost_real": 1e12}
            quad_k1_0 = float(inputs["quad_k1_0"]) if self.fit_quadrupole_strength else None
            try:
                f, _, _= compute_cost(float(inputs["emit_x_norm"]), float(inputs["beta_x0"]), float(inputs["alpha_x0"]),
                                    float(inputs["emit_y_norm"]), float(inputs["beta_y0"]), float(inputs["alpha_y0"]), allow_stop = False, quad_k1_0 = quad_k1_0)
                f_real = float(f)
                f_objective = float(np.log10(max(f_real, 1e-12)))

            except Exception as e:
                if self.print_M:
                    print(f"Joint fit evaluation failed, assigning large cost: {type(e).__name__}: {e}")
                return {"f": 12.0, "cost_real": 1e12}

            if self.print_M:
                print(
                    "Joint fit solution: "
                    f"emit_x_norm={float(inputs['emit_x_norm']):.6g}, beta_x0={float(inputs['beta_x0']):.6g}, alpha_x0={float(inputs['alpha_x0']):.6g}, "
                    f"emit_y_norm={float(inputs['emit_y_norm']):.6g}, beta_y0={float(inputs['beta_y0']):.6g}, alpha_y0={float(inputs['alpha_y0']):.6g}, "
                    f"cost_real={f_real:.6g}, f_log10={f_objective:.6g}"
                )
            return {"f": f_objective, "cost_real": f_real}

        evaluator = Evaluator(function = evaluate) # how to calculate merit function
        generator = ExpectedImprovementGenerator(vocs = vocs) # how to choose the next point
        X = Xopt(generator = generator, evaluator = evaluator, vocs = vocs)
        total_initial = max(1, int(self.xopt_initial_points))

        best_row = None # from X.data
        best_cost = np.inf
        stopped_during_fit = False

        def update_best_from_data():
            '''
            After each evaluation looks at X.data and chooses the best point.
            '''
            nonlocal best_row, best_cost # it allows the inner function to overwrite best_row, best_cost, not create it again
            data = getattr(X, "data", None)
            if data is None or len(data) == 0:
                return
            good = data.copy()
            if "xopt_error" in good.columns:
                try:
                    good = good[~good["xopt_error"].astype(bool)] # chooses only points where there was no xopt_error
                except Exception:
                    pass
            if len(good) == 0 or "f" not in good.columns:
                return
            cost_column = "cost_real" if "cost_real" in good.columns else "f"
            idx = good[cost_column].astype(float).idxmin() # change each value to float
            row = good.loc[idx]
            cost = float(row[cost_column])

            if np.isfinite(cost) and cost < best_cost: # updates best solution using the real, not log-transformed, cost
                best_cost = cost
                best_row = row

        try:
            # X.random_evaluate(total_initial) # for bayesian optimization to suggest better solutions, it needs some data

            # update_best_from_data()

            lhs_seed = int(self.rng.integers(0, 2**31 - 1))
            sampler = qmc.LatinHypercube(d=len(params_order), seed = lhs_seed)
            unit_samples = sampler.random(n=total_initial)
            lhs_samples = qmc.scale(unit_samples, low_bounds, high_bounds)
            lhs_df = pd.DataFrame(lhs_samples, columns=params_order)
            if self.print_M:
                print(f"Joint Xopt init: {total_initial} samples in {len(params_order)} degrees of freedom")
            X.evaluate_data(lhs_df)
            update_best_from_data()

            for i in range(self.xopt_steps):
                if self.print_M:
                    print(f"Joint Xopt step {i + 1}/{self.xopt_steps}")
                self._emit_progress("Xopt", i + 1, self.xopt_steps)
                if self._stop_requested:
                    if best_row is not None:
                        stopped_during_fit = True
                        break
                    raise OptimizationStopped("Optimization stopped.")
                if self._pause_requested:
                    if best_row is not None:
                        stopped_during_fit = True
                        break
                    raise OptimizationPaused("Optimization paused.")

                X.step()
                update_best_from_data()
                if self._stop_requested or self._pause_requested:
                    stopped_during_fit = True
                    break

        except OptimizationStopped:
            if best_row is not None:
                stopped_during_fit = True
            else:
                raise
        except OptimizationPaused:
            if best_row is not None:
                stopped_during_fit = True
            else:
                raise
        if best_row is None:
            raise RuntimeError("Joint Xopt failed to find best fit solution.")

        if self.print_M:
            print(
                f"Joint Xopt finished. "
                f"evaluations={0 if getattr(X, 'data', None) is None else len(X.data)}, "
                f"best_found={best_row is not None}, stopped={stopped_during_fit}"
            )

        emit_x_norm_best = float(best_row["emit_x_norm"])
        beta_x0_best = float(best_row["beta_x0"])
        alpha_x0_best = float(best_row["alpha_x0"])
        emit_y_norm_best = float(best_row["emit_y_norm"])
        beta_y0_best = float(best_row["beta_y0"])
        alpha_y0_best = float(best_row["alpha_y0"])
        quad_k1_0_best = float(best_row["quad_k1_0"]) if self.fit_quadrupole_strength else None

        if self._stop_requested or self._pause_requested:
            pred2_x_partial, pred2_y_partial = predict_sigma2_from_fit_params(
                emit_x_norm_best, beta_x0_best, alpha_x0_best,
                emit_y_norm_best, beta_y0_best, alpha_y0_best,
                allow_stop=False, quad_k1_0 = quad_k1_0_best,
            )

            solution = self._build_joint_partial_output(screens=screens, sigma2_x=sig_x2, sigma2_y=sig_y2, pred2_x=pred2_x_partial, pred2_y=pred2_y_partial, best_row=best_row, best_cost=best_cost)
            if self._pause_requested:
                raise OptimizationPaused("Optimization paused.", solution=solution)
            #raise OptimizationStopped("Optimization stopped.", solution=solution)
            return solution
        pred2_x, pred2_y = predict_sigma2_from_fit_params(
            emit_x_norm_best, beta_x0_best, alpha_x0_best,
            emit_y_norm_best, beta_y0_best, alpha_y0_best,
            allow_stop=True, quad_k1_0 = quad_k1_0_best,
        )

        local_max_nfev = int(getattr(self, "nm_steps", 5000))
        run_local_ls = local_max_nfev > 0

        if not run_local_ls:
            solution = self._build_joint_partial_output(
                screens=screens,
                sigma2_x=sig_x2,
                sigma2_y=sig_y2,
                pred2_x=pred2_x,
                pred2_y=pred2_y,
                best_row=best_row,
                best_cost=best_cost,
            )
            solution["message"] = "Joint x+y Xopt only. No least squares."
            solution["stopped"] = bool(stopped_during_fit)
            return solution

        if self.print_M:
            print(f"Starting local optimization from f={best_cost:.4g}...")

        x0_values = [
            emit_x_norm_best, beta_x0_best, alpha_x0_best,
            emit_y_norm_best, beta_y0_best, alpha_y0_best,
        ]

        if self.fit_quadrupole_strength:
            x0_values.append(quad_k1_0_best)

        x0 = np.array(x0_values, dtype=float)
        x0 = np.clip(x0, low_bounds, high_bounds)

        local_max_nfev = int(getattr(self, "nm_steps", 5000))

        # Build several local-optimization starts. A single LS start from the BO best point
        # can get stuck if BO found a boundary/local minimum. ML predictions are cheap, so
        # use top Xopt points plus additional interior points.
        ls_starts = []

        def _clip_to_interior(point, margin_fraction=0.03):
            point = np.asarray(point, dtype=float)
            margin = float(margin_fraction) * (high_bounds - low_bounds)
            return np.clip(point, low_bounds + margin, high_bounds - margin)

        ls_starts.append(_clip_to_interior(x0, margin_fraction=0.03))

        data_for_starts = getattr(X, "data", None)
        if data_for_starts is not None and len(data_for_starts) > 0:
            good = data_for_starts.copy()
            if "xopt_error" in good.columns:
                try:
                    good = good[~good["xopt_error"].astype(bool)]
                except Exception:
                    pass
            cost_column = "cost_real" if "cost_real" in good.columns else "f"
            if cost_column in good.columns:
                try:
                    good = good.sort_values(cost_column, ascending=True)
                    for _, row in good.head(8).iterrows():
                        candidate = np.array([float(row[p]) for p in params_order], dtype=float)
                        ls_starts.append(_clip_to_interior(candidate, margin_fraction=0.03))
                except Exception:
                    pass

        try:
            sampler_ls = qmc.LatinHypercube(d=len(params_order), seed=int(self.rng.integers(0, 2**31 - 1)))
            unit_ls = sampler_ls.random(n=128)
            interior_low = low_bounds + 0.05 * (high_bounds - low_bounds)
            interior_high = high_bounds - 0.05 * (high_bounds - low_bounds)
            interior_samples = qmc.scale(unit_ls, interior_low, interior_high)
            for candidate in interior_samples:
                ls_starts.append(np.asarray(candidate, dtype=float))
        except Exception:
            pass

        # remove near-duplicate starts
        unique_starts = []
        for candidate in ls_starts:
            if not np.all(np.isfinite(candidate)):
                continue
            if not any(np.allclose(candidate, other, rtol=1e-5, atol=1e-8) for other in unique_starts):
                unique_starts.append(candidate)
        ls_starts = unique_starts

        ls_best_cost = [float(best_cost)]
        ls_best_params = [x0.copy()]
        ls_stopped = [False]
        ls_eval = [0]

        scale_x = np.nanmedian(np.abs(sig_x2[valid_x])) ** 2 if np.any(valid_x) else 1.0
        scale_y = np.nanmedian(np.abs(sig_y2[valid_y])) ** 2 if np.any(valid_y) else 1.0
        scale_x = max(float(scale_x), 1e-30)
        scale_y = max(float(scale_y), 1e-30)
        n_x = max(int(np.count_nonzero(valid_x)), 1)
        n_y = max(int(np.count_nonzero(valid_y)), 1)

        def _ls_residuals(z):
            if self._stop_requested or self._pause_requested:
                ls_stopped[0] = True
                raise StopIteration("Local least-squares stop requested")

            p_c = np.asarray(z, dtype=float)
            try:
                p2x, p2y = predict_sigma2_from_fit_params(
                    p_c[0], p_c[1], p_c[2],
                    p_c[3], p_c[4], p_c[5],
                    quad_k1_0=(p_c[6] if self.fit_quadrupole_strength else None),
                    allow_stop=False,
                )
            except Exception:
                return np.full(n_x + n_y, 1e3, dtype=float)

            rx = (p2x - sig_x2)[valid_x].ravel() if np.any(valid_x) else np.array([], dtype=float)
            ry = (p2y - sig_y2)[valid_y].ravel() if np.any(valid_y) else np.array([], dtype=float)
            rx = rx[np.isfinite(rx)]
            ry = ry[np.isfinite(ry)]

            if rx.size == 0 and ry.size == 0:
                return np.full(n_x + n_y, 1e3, dtype=float)

            rx_scaled = np.sqrt(0.5 / n_x) * rx / np.sqrt(scale_x) if rx.size else np.array([], dtype=float)
            ry_scaled = np.sqrt(0.5 / n_y) * ry / np.sqrt(scale_y) if ry.size else np.array([], dtype=float)
            residuals = np.concatenate([rx_scaled, ry_scaled])

            f = float(np.sum(residuals ** 2))
            if np.isfinite(f) and f < ls_best_cost[0]:
                ls_best_cost[0] = f
                ls_best_params[0] = p_c.copy()

            ls_eval[0] += 1
            self._emit_progress("Least squares", min(ls_eval[0], local_max_nfev), local_max_nfev)
            if self.print_M:
                print(
                    f" LS {ls_eval[0]} (max_nfev={local_max_nfev}): "
                    f"best_f={ls_best_cost[0]:.4g}, "
                    f"current_emit_x={p_c[0]:.6g}, current_beta_x={p_c[1]:.6g}, current_alpha_x={p_c[2]:.6g}, "
                    f"current_emit_y={p_c[3]:.6g}, current_beta_y={p_c[4]:.6g}, current_alpha_y={p_c[5]:.6g}"
                    + (f", current_quad_k1_0={p_c[6]:.6g}" if self.fit_quadrupole_strength else "")
                )

            return residuals

        best_res_ls = None
        best_res_ls_cost = np.inf
        try:
            for start_idx, x0_try in enumerate(ls_starts):
                if self.print_M:
                    print(f"Starting LS multi-start {start_idx + 1}/{len(ls_starts)} from {x0_try}")
                try:
                    res_try = least_squares(_ls_residuals, x0_try, bounds=(low_bounds, high_bounds), method="trf", loss="linear", f_scale=1.0, max_nfev=local_max_nfev, x_scale=np.maximum(high_bounds - low_bounds, 1e-12), ftol=1e-8, xtol=1e-8, gtol=1e-8)
                    p_try = np.asarray(res_try.x, dtype=float)
                    f_try, _, _ = compute_cost(p_try[0], p_try[1], p_try[2], p_try[3], p_try[4], p_try[5], quad_k1_0=(p_try[6] if self.fit_quadrupole_strength else None), allow_stop=False)
                    if np.isfinite(f_try) and f_try < best_res_ls_cost:
                        best_res_ls_cost = float(f_try)
                        best_res_ls = res_try
                    if np.isfinite(f_try) and f_try < ls_best_cost[0]:
                        ls_best_cost[0] = float(f_try)
                        ls_best_params[0] = p_try.copy()
                    if self.print_M:
                        print(
                            f"  LS start {start_idx + 1}/{len(ls_starts)} finished: "
                            f"cost={float(f_try):.4g}, success={res_try.success}, "
                            f"nfev={res_try.nfev}/{local_max_nfev}, message={res_try.message}"
                        )
                except StopIteration:
                    ls_stopped[0] = True
                    if self.print_M:
                        print("  LS interrupted.")
                    break
                except Exception as e:
                    if self.print_M:
                        print(f"  LS start {start_idx + 1}/{len(ls_starts)} failed ({e}).")

            if self.print_M:
                if best_res_ls is not None:
                    print(f"  Best LS multi-start cost={ls_best_cost[0]:.4g}")
                else:
                    print(f"  No LS start improved BO result; using BO cost={ls_best_cost[0]:.4g}")

        except Exception as e:
            if self.print_M:
                print(f"  LS multi-start failed ({e}), using BO result.")

        p_final = ls_best_params[0]
        best_cost_final = ls_best_cost[0]

        best_row = best_row.copy()
        if self.fit_quadrupole_strength:
            best_row["quad_k1_0"] = float(p_final[6])
        best_row["emit_x_norm"] = float(p_final[0])
        best_row["beta_x0"] = float(p_final[1])
        best_row["alpha_x0"] = float(p_final[2])
        best_row["emit_y_norm"] = float(p_final[3])
        best_row["beta_y0"] = float(p_final[4])
        best_row["alpha_y0"] = float(p_final[5])

        stopped_during_fit = stopped_during_fit or ls_stopped[0]

        if stopped_during_fit or self._stop_requested or self._pause_requested:
            pred2_x_p, pred2_y_p = predict_sigma2_from_fit_params(p_final[0], p_final[1], p_final[2], p_final[3], p_final[4], p_final[5], quad_k1_0=(p_final[6] if self.fit_quadrupole_strength else None), allow_stop=False)
            solution = self._build_joint_partial_output(screens=screens, sigma2_x=sig_x2, sigma2_y=sig_y2, pred2_x=pred2_x_p, pred2_y=pred2_y_p, best_row=best_row, best_cost=best_cost_final)
            if self._pause_requested:
                raise OptimizationPaused("Optimization paused.", solution=solution)
            #raise OptimizationStopped("Optimization stopped.", solution=solution)
            return solution

        pred2_x, pred2_y = predict_sigma2_from_fit_params(p_final[0], p_final[1], p_final[2], p_final[3], p_final[4], p_final[5], quad_k1_0=(p_final[6] if self.fit_quadrupole_strength else None), allow_stop=True)

        solution = self._build_joint_partial_output(screens=screens, sigma2_x=sig_x2, sigma2_y=sig_y2, pred2_x=pred2_x, pred2_y=pred2_y, best_row=best_row, best_cost=best_cost_final)
        solution["message"] = "Joint x+y Bayesian optimization + least-squares."
        solution["stopped"] = bool(stopped_during_fit)

        fit_error = self._calculate_optimalization_errors(best_res_ls, n_params_fallback=len(params_order))
        param_errors = fit_error["param_errors"]
        if param_errors is None or len(param_errors) != len(params_order):
            err_dict = {p: np.nan for p in params_order}
        else:
            err_dict = {p: float(e) for p, e in zip(params_order, param_errors)}

        solution["param_errors"] = err_dict
        solution["reduced_chi2_like"] = fit_error["reduced_chi2_like"]
        solution["chi2_like"] = fit_error["chi2_like"]
        solution["param_cov"] = fit_error["cov"]

        if self.print_M:
            print(
                f"Fit parameter errors (1-sigma): "
                + ", ".join(f"{k}={v:.4g}" for k, v in err_dict.items())
                + f", reduced_chi2_like={fit_error['reduced_chi2_like']:.4g}"
            )

        return solution