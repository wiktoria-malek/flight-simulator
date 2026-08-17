import numpy as np
from scipy.optimize import least_squares
import pandas as pd
from Backend.EM_helpers.CheckLinearOptics import estimate_twiss_use_linear_optics_start, CheckLinearOpticsUnavailable

class OptimizationStopped(Exception):
    def __init__(self, message = "Optimization stopped", solution = None):
        super().__init__(message)
        self.solution = solution

class OptimizationPaused(Exception):
    def __init__(self, message="Optimization paused", solution=None):
        super().__init__(message)
        self.solution = solution

class Optimization:
    def __init__(self, interface, nm_steps=100, fit_quadrupole_strength=False, progress_callback=None):
        self.progress_callback = progress_callback
        self.interface = interface
        self._stop_requested = False
        self._pause_requested = False
        self.best_out_so_far = None
        self._last_completed_output = None
        self.nm_steps = int(nm_steps)
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

    def _calculate_optimalization_errors(self, ls_result, n_params=None):
        """
        Estimates how sure the model is, e.g. if the minimum region is big, then you can change the emittance
        by several percent and the cost will be the same -> not sure what emittance is, and the cost is big.

        If the minimum region found is narrow, then if you move the e.g. emittance value by small percent,
        the cost grows by a lot. -> it means that the error is small and value is well estimated.
        """
        n_default = int(n_params) if n_params is not None else 6

        if ls_result is None:
            return {
                "param_errors": np.full(n_default, np.nan, dtype=float),
                "cov": None,
                "reduced_chi2": np.nan,
                "chi2": np.nan,
            }

        try:
            J = np.asarray(ls_result.jac, dtype=float) # that's the information about how narrow the minimum region is, it's an array with derivatives
            r = np.asarray(ls_result.fun, dtype=float) # residual sigma predicted - sigma meas
            p = np.asarray(ls_result.x, dtype=float) # best set of parameters that least squares have found
        except AttributeError:
            return {
                "param_errors": np.full(n_default, np.nan),
                "cov": None,
                "reduced_chi2": np.nan,
                "chi2": np.nan,
            }

        ndata = len(r) # number of measurements
        npar = len(p) # number of parameters
        dof = max(ndata - npar, 1) # degrees of freedom

        """
        Sum of the residuals:
        """
        chi2 = float(np.sum(r ** 2)) # the smaller, the better the model, the bigger, the worse
        reduced_chi2 = chi2 / dof # average error per 1 measurement

        try:
            """
            Cov = s^2 * (J.T * J )^(-1)
            s^2 = sum(r_i^2)/(N - p)
            on diagonal line of cov matrix are variances of parameters: => calculating the relative difference to the average value for every measurement, making it squared, then taking the average of those values. For this method is means, taking it from J.
            e.g. |0.04   0.01  -0.02|   0   0   0               |
                 |0.01   0.25   0.03|   0   0   0               |  => var(emit_x) = 0.04, var(beta_x) = 0.25, var(alpha_x) = 0.16, other elements indicate coupling
                 |-0.02  0.03   0.16|   0   0   0               |
                 |  0     0       0     
                 |   0     0       0     other values, for y plane
                 |  0     0       0
                 std of those are the errors, so np.sqrt(emit_x = 0.04) = 0.2 is the estimated error
            """
            # J.T * J tells how steep is the minimum function. If it's narrow, then the result is big. If the wide, J.T * J is small. That's also why we need to multiply by reduced_chi2
            cov = np.linalg.pinv(J.T @ J) * reduced_chi2 # if you invert it, it becomes the opposite. Narrow region -> small cov matrix -> small errors; Wide region -? big cov matrix -> big errors;
            param_errors = np.sqrt(np.maximum(np.diag(cov), 0.0))
            print("Covariance matrix:")
            print(cov)
        except Exception:
            cov = None
            param_errors = np.full(npar, np.nan)

        return {
            "param_errors": param_errors,
            "cov": cov,
            "reduced_chi2": reduced_chi2,
            "chi2": chi2,
        }

    def fit_from_session(self, session, bounds):
        was_pause_requested = bool(self._pause_requested)
        self.clear_stop()
        self._pause_requested = was_pause_requested
        print("Starting to fit Twiss parameters and emittance...")
        screens = list(session.get("screens", []))
        quad_name = session.get("quad_name")
        K1L_values = np.asarray(session.get("K1L_values", []), dtype=float)

        try:
            quad_k1l_0_readback = np.asarray(session.get("K1L_0", K1L_values[len(K1L_values)//2] if K1L_values.size else np.nan))
        except Exception:
            quad_k1l_0_readback = np.nan

        sigx = np.asarray(session.get("sigx_mean", []), dtype=float)
        sigy = np.asarray(session.get("sigy_mean", []), dtype=float)
        sigx_shots = np.asarray(session.get("sigx_shots", []), dtype=float)
        sigy_shots = np.asarray(session.get("sigy_shots", []), dtype=float)
        if not quad_name:
            raise ValueError("Session does not contain quad_name")

        sigma_template_x = np.asarray(sigx if sigx.size else np.empty((0, len(screens))), dtype=float)
        sigma_template_y = np.asarray(sigy if sigy.size else np.empty((0, len(screens))), dtype=float)

        def _plane_no_solution(plane_name, sigma_template):
            return {
                "emit": np.nan,
                "beta0": np.nan,
                "alpha0": np.nan,
                "pred": np.full_like(sigma_template, np.nan, dtype=float),
                "cost": np.nan,
            }
        joint_fit = None
        fit_x = None
        fit_y = None

        try:
            joint_fit = self._fit_6d(screens=screens, quad_name=quad_name, K1L_values=K1L_values, sigx_shots=sigx_shots, sigy_shots=sigy_shots, bounds = bounds)

            fit_x = {
                "emit": joint_fit["emit_x_geom"],
                "beta0": joint_fit["beta_x0"],
                "alpha0": joint_fit["alpha_x0"],
                "pred": joint_fit["pred_x"],
                "cost": joint_fit["cost"],
            }
            fit_y = {
                "emit": joint_fit["emit_y_geom"],
                "beta0": joint_fit["beta_y0"],
                "alpha0": joint_fit["alpha_y0"],
                "pred": joint_fit["pred_y"],
                "cost": joint_fit["cost"],
            }

            print(
                f"Joint fit done with cost={joint_fit['cost']:.6g}, "
                f"emit_x_geom={joint_fit['emit_x_geom']:.6g}, beta_x0={joint_fit['beta_x0']:.6g}, alpha_x0={joint_fit['alpha_x0']:.6g}, "
                f"emit_y_geom={joint_fit['emit_y_geom']:.6g}, beta_y0={joint_fit['beta_y0']:.6g}, alpha_y0={joint_fit['alpha_y0']:.6g}")

        except (OptimizationStopped, OptimizationPaused) as e:
            if isinstance(getattr(e, "solution", None), dict):
                joint_fit = e.solution
                fit_x = {
                        "emit": joint_fit["emit_x_geom"],
                        "beta0": joint_fit["beta_x0"],
                        "alpha0": joint_fit["alpha_x0"],
                        "pred": joint_fit["pred_x"],
                        "cost": joint_fit["cost"],
                    }
                fit_y = {
                        "emit": joint_fit["emit_y_geom"],
                        "beta0": joint_fit["beta_y0"],
                        "alpha0": joint_fit["alpha_y0"],
                        "pred": joint_fit["pred_y"],
                        "cost": joint_fit["cost"],
                    }
            else:
                fit_x = None
                fit_y = None

        if fit_x is None:
            fit_x = _plane_no_solution("x", sigma_template_x)
        if fit_y is None:
            fit_y = _plane_no_solution("y", sigma_template_y)

        gamma_rel, beta_rel, beta_gamma = self.interface.get_beam_factors()
        emit_x_norm = (beta_gamma * fit_x["emit"] if np.isfinite(fit_x["emit"]) else np.nan)
        emit_y_norm = (beta_gamma * fit_y["emit"] if np.isfinite(fit_y["emit"]) else np.nan)
        emit_x_geom = fit_x["emit"]
        emit_y_geom = fit_y["emit"]

        err_dict = {}
        reduced_chi2 = np.nan
        chi2 = np.nan
        if isinstance(joint_fit, dict):
            err_dict = dict(joint_fit.get("param_errors") or {})
            reduced_chi2 = float(joint_fit.get("reduced_chi2", np.nan))
            chi2 = float(joint_fit.get("chi2", np.nan))

        emit_x_norm_err = float(err_dict.get("emit_x_norm", np.nan))
        emit_y_norm_err = float(err_dict.get("emit_y_norm", np.nan))
        beta_x0_err = float(err_dict.get("beta_x0", np.nan))
        alpha_x0_err = float(err_dict.get("alpha_x0", np.nan))
        beta_y0_err = float(err_dict.get("beta_y0", np.nan))
        alpha_y0_err = float(err_dict.get("alpha_y0", np.nan))
        quad_k1l_0_err = float(err_dict.get("quad_k1l_0", np.nan))

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
            "fit_x_cost": fit_x["cost"],
            "fit_y_cost": fit_y["cost"],
            "fit_quadrupole_strength": bool(self.fit_quadrupole_strength),
            "quad_k1l_0": (
                float(joint_fit.get("quad_k1l_0", np.nan))
                if bool(self.fit_quadrupole_strength) and isinstance(joint_fit, dict)
                else quad_k1l_0_readback
            ),
            "quad_k1l_0_is_fitted": bool(self.fit_quadrupole_strength),
            "emit_x_norm_err": emit_x_norm_err,
            "emit_y_norm_err": emit_y_norm_err,
            "emit_x_geom_err": emit_x_geom_err,
            "emit_y_geom_err": emit_y_geom_err,
            "beta_x0_err": beta_x0_err,
            "alpha_x0_err": alpha_x0_err,
            "beta_y0_err": beta_y0_err,
            "alpha_y0_err": alpha_y0_err,
            "quad_k1l_0_err": quad_k1l_0_err,
            "fit_reduced_chi2": reduced_chi2,
            "fit_chi2": chi2,
            "prediction_observable": "sigma",
        }

        output = {
            "result": result,
            "pred_x": fit_x["pred"],
            "pred_y": fit_y["pred"],
            "screens": list(session.get("screens", [])),
            "K1L_values": K1L_values.tolist(),
        }

        self.best_out_so_far = output
        self._last_completed_output = output
        self._pause_requested = False

        print(
            f"Final result: "
            f"emit_x_norm={result['emit_x_norm']:.6g}, "
            f"emit_y_norm={result['emit_y_norm']:.6g}, "
            f"fit_x_cost={result['fit_x_cost']:.6g}, "
            f"fit_y_cost={result['fit_y_cost']:.6g}"
        )

        return output

    def _build_joint_partial_output(self, screens, sigma_x, sigma_y, pred_x, pred_y, best_row, best_cost):
        if best_row is None or pred_x is None or pred_y is None:
            return None
        gamma_rel, beta_rel, beta_gamma = self.interface.get_beam_factors()
        emit_x_geom = max(float(best_row["emit_x_norm"]) / beta_gamma, 1e-12)
        emit_y_geom = max(float(best_row["emit_y_norm"]) / beta_gamma, 1e-12)

        return {
            "emit_x_geom": emit_x_geom,
            "beta_x0": float(best_row["beta_x0"]),
            "alpha_x0": float(best_row["alpha_x0"]),
            "emit_y_geom": emit_y_geom,
            "beta_y0": float(best_row["beta_y0"]),
            "alpha_y0": float(best_row["alpha_y0"]),
            "pred_x": pred_x,
            "pred_y": pred_y,
            "emit_x_norm": float(best_row["emit_x_norm"]),
            "emit_y_norm": float(best_row["emit_y_norm"]),
            "quad_k1l_0": (float(best_row["quad_k1l_0"]) if "quad_k1l_0" in best_row else np.nan),
            "cost": float(best_cost) if np.isfinite(best_cost) else np.nan,
        }

    def _fit_6d(self, screens, quad_name, K1L_values, sigx_shots, sigy_shots, bounds):

        # Beam size for every individual shot.
        sigma_x_shots = np.asarray(sigx_shots, dtype=float)
        sigma_y_shots = np.asarray(sigy_shots, dtype=float)

        # number of valid shots at each scan point and screen
        n_x_sum = np.sum(np.isfinite(sigma_x_shots), axis=2)
        n_y_sum = np.sum(np.isfinite(sigma_y_shots), axis=2)

        # Measured mean beam size.
        sig_x = np.nanmean(sigma_x_shots, axis=2)
        sig_y = np.nanmean(sigma_y_shots, axis=2)

        # Sample standard deviation of sigma, then standard error of its mean.
        s_sigx = np.nanstd(sigma_x_shots, axis=2, ddof=1)
        s_sigy = np.nanstd(sigma_y_shots, axis=2, ddof=1)

        fallback_u_x = np.maximum(0.08 * np.abs(sig_x), 1e-12)
        fallback_u_y = np.maximum(0.08 * np.abs(sig_y), 1e-12)
        u_x = np.where(n_x_sum >= 2, s_sigx / np.sqrt(n_x_sum), fallback_u_x)
        u_y = np.where(n_y_sum >= 2, s_sigy / np.sqrt(n_y_sum), fallback_u_y)
        u_x = np.where(np.isfinite(u_x) & (u_x > 0), u_x, fallback_u_x)
        u_y = np.where(np.isfinite(u_y) & (u_y > 0), u_y, fallback_u_y)

        # points usable in statistical chi2
        valid_x = np.isfinite(sig_x) & np.isfinite(u_x) & (u_x > 0) & (n_x_sum >= 1)
        valid_y = np.isfinite(sig_y) & np.isfinite(u_y) & (u_y > 0) & (n_y_sum >= 1)

        if not np.any(valid_x) and not np.any(valid_y):
            raise RuntimeError("No valid sigma_x or sigma_y measurements were available for the fit.")

        gamma_rel, beta_rel, beta_gamma = self.interface.get_beam_factors()
        bounds = dict(bounds or {})
        K1L_values = np.asarray(K1L_values, dtype=float)
        K1L_0_readback = float(K1L_values[len(K1L_values)//2])
        deltas_for_fit = K1L_values / K1L_0_readback - 1.0

        if self.fit_quadrupole_strength:
            low = 0.7 * K1L_0_readback
            high = 1.3 * K1L_0_readback
            bounds["quad_k1l_0"] = [min(low,high), max(low,high)]

        params_order = ["emit_x_norm", "beta_x0", "alpha_x0", "emit_y_norm", "beta_y0", "alpha_y0"]

        if self.fit_quadrupole_strength:
            params_order.append("quad_k1l_0")

        low_bounds = np.array([bounds[p][0] for p in params_order], dtype=float)
        high_bounds = np.array([bounds[p][1] for p in params_order], dtype=float)

        def predict_sigma_from_fit_params(emit_x_norm, beta_x0, alpha_x0, emit_y_norm, beta_y0, alpha_y0, allow_stop = True, quad_k1l_0 = None):
            emit_x_norm = float(emit_x_norm)
            beta_x0 = float(beta_x0)
            alpha_x0 = float(alpha_x0)
            emit_y_norm = float(emit_y_norm)
            beta_y0 = float(beta_y0)
            alpha_y0 = float(alpha_y0)

            if self.fit_quadrupole_strength:
                if quad_k1l_0 is None:
                    raise RuntimeError("quad_k1l_0 must be provided when fitting quadrupole strength.")
                K1L_values_used = float(quad_k1l_0) * (1.0 + deltas_for_fit)
            else:
                K1L_values_used = K1L_values

            try:
                pred_sigx, pred_sigy = self.interface.predict_emittance_scan_response(quad_name=quad_name, screens=screens,
                    K1L_values=K1L_values_used, emit_x=emit_x_norm, emit_y=emit_y_norm, beta_x0=beta_x0, beta_y0=beta_y0,
                    alpha_x0=alpha_x0, alpha_y0=alpha_y0, reference_screen=screens[0], stop_checker=(lambda: self._stop_requested or self._pause_requested) if allow_stop else None)

            except RuntimeError as e:
                if str(e) == "__OPTIMIZATION_STOP__":
                    if self._pause_requested:
                        raise OptimizationPaused("Optimization paused.")
                    raise OptimizationStopped("Optimization stopped.")
                raise
            pred_sigx = np.asarray(pred_sigx, dtype=float)
            pred_sigy = np.asarray(pred_sigy, dtype=float)
            return pred_sigx, pred_sigy

        def compute_cost(emit_x_norm, beta_x0, alpha_x0, emit_y_norm, beta_y0, alpha_y0, allow_stop = True, quad_k1l_0 = None):
            if allow_stop and (self._stop_requested or self._pause_requested):
                if self._pause_requested:
                    raise OptimizationPaused("Optimization paused.")
                raise OptimizationStopped("Optimization stopped.")
            pred_x, pred_y = predict_sigma_from_fit_params(emit_x_norm, beta_x0, alpha_x0, emit_y_norm, beta_y0, alpha_y0, allow_stop = allow_stop, quad_k1l_0 = quad_k1l_0)

            if np.any(valid_x) and not np.all(np.isfinite(pred_x[valid_x])): return 1e12, pred_x, pred_y
            if np.any(valid_y) and not np.all(np.isfinite(pred_y[valid_y])): return 1e12, pred_x, pred_y

            # cost : (model - measurement) / uncertainty
            residual_x = (pred_x - sig_x)[valid_x] / u_x[valid_x]
            residual_y = (pred_y - sig_y)[valid_y] / u_y[valid_y]

            # chi2 - sum of squared residuals

            chi2 = float(np.sum(residual_x ** 2) + np.sum(residual_y ** 2))

            return chi2, pred_x, pred_y

        original_low_bounds = low_bounds.copy()
        original_high_bounds = high_bounds.copy()
        best_row = None
        best_cost = np.inf
        stopped_during_fit = False

        try:
            linear_optics = estimate_twiss_use_linear_optics_start(self.interface, quad_name, screens, K1L_values, sig_x, sig_y, u_x, u_y, valid_x, valid_y, beta_gamma)
        except CheckLinearOpticsUnavailable as e:
            raise RuntimeError(f"Fit will not converge: {e} Try a different K1L scan range/number of steps, or scan a different quadrupole.") from e
        except Exception as e:
            raise RuntimeError(f"Fit will not converge: could not compute a linear-optics starting estimate. {e} Try a different K1L scan range/number of steps, or scan a different quadrupole.") from e

        x0_linear_optics_values = [linear_optics[p] for p in ("emit_x_norm", "beta_x0", "alpha_x0", "emit_y_norm", "beta_y0", "alpha_y0")]
        if self.fit_quadrupole_strength: x0_linear_optics_values.append(K1L_0_readback)
        x0_linear_optics = np.clip(np.array(x0_linear_optics_values, dtype=float), original_low_bounds, original_high_bounds)
        cost_linear_optics, _, _ = compute_cost(*x0_linear_optics[:6], allow_stop=False, quad_k1l_0=(float(x0_linear_optics[6]) if self.fit_quadrupole_strength else None))

        if not np.isfinite(cost_linear_optics):
            raise RuntimeError("Fit will not converge: the linear-optics starting estimate does not reproduce the measured beam sizes. Try a different K1L scan range/number of steps, or scan a different quadrupole.")

        row_values = dict(zip(params_order, x0_linear_optics))
        row_values["f"] = float(cost_linear_optics)
        best_row = pd.Series(row_values)
        best_cost = float(cost_linear_optics)
        rel_window = 0.15
        half_width = rel_window * (original_high_bounds - original_low_bounds)
        if self.fit_quadrupole_strength:
            half_width[-1] = original_high_bounds[-1] - original_low_bounds[-1]
        low_bounds = np.maximum(original_low_bounds, x0_linear_optics - half_width)
        high_bounds = np.minimum(original_high_bounds, x0_linear_optics + half_width)
        low_bounds = np.minimum(low_bounds, x0_linear_optics - 1e-9)
        high_bounds = np.maximum(high_bounds, x0_linear_optics + 1e-9)
        print(f"Linear optics cost: cost={cost_linear_optics:.6g}, x0={row_values}")

        emit_x_norm_best = float(best_row["emit_x_norm"])
        beta_x0_best = float(best_row["beta_x0"])
        alpha_x0_best = float(best_row["alpha_x0"])
        emit_y_norm_best = float(best_row["emit_y_norm"])
        beta_y0_best = float(best_row["beta_y0"])
        alpha_y0_best = float(best_row["alpha_y0"])
        quad_k1l_0_best = float(best_row["quad_k1l_0"]) if self.fit_quadrupole_strength else None

        if self._stop_requested or self._pause_requested:
            pred_x_partial, pred_y_partial = predict_sigma_from_fit_params(emit_x_norm_best, beta_x0_best, alpha_x0_best, emit_y_norm_best, beta_y0_best, alpha_y0_best, allow_stop=False, quad_k1l_0 = quad_k1l_0_best)
            solution = self._build_joint_partial_output(screens=screens, sigma_x=sig_x, sigma_y=sig_y, pred_x=pred_x_partial, pred_y=pred_y_partial, best_row=best_row, best_cost=best_cost)
            if self._pause_requested:
                raise OptimizationPaused("Optimization paused.", solution=solution)
            return solution
        pred_x, pred_y = predict_sigma_from_fit_params(emit_x_norm_best, beta_x0_best, alpha_x0_best, emit_y_norm_best, beta_y0_best, alpha_y0_best, allow_stop=True, quad_k1l_0 = quad_k1l_0_best)
        run_local_ls = self.nm_steps > 0

        if not run_local_ls:
            solution = self._build_joint_partial_output(screens=screens, sigma_x=sig_x, sigma_y=sig_y, pred_x=pred_x, pred_y=pred_y, best_row=best_row, best_cost=best_cost)
            solution["stopped"] = bool(stopped_during_fit)
            return solution

        print(f"Starting local optimization from f={best_cost:.4g}...")
        x0_values = [emit_x_norm_best, beta_x0_best, alpha_x0_best, emit_y_norm_best, beta_y0_best, alpha_y0_best]
        if self.fit_quadrupole_strength:
            x0_values.append(quad_k1l_0_best)

        x0 = np.array(x0_values, dtype=float)
        x0 = np.clip(x0, low_bounds, high_bounds)

        def _move_away_from_bounds_edges(point):
            point = np.asarray(point, dtype=float)
            margin = 0.03 * (high_bounds - low_bounds)
            return np.clip(point, low_bounds + margin, high_bounds - margin)

        ls_starts = [_move_away_from_bounds_edges(x0)]
        ls_best_cost = [float(best_cost)]
        ls_best_params = [x0.copy()]
        ls_stopped = [False]
        ls_eval = [0]

        n_x = max(int(np.count_nonzero(valid_x)), 1)
        n_y = max(int(np.count_nonzero(valid_y)), 1)

        def _ls_residuals(z):
            if self._stop_requested or self._pause_requested:
                ls_stopped[0] = True
                raise StopIteration("Local least-squares stop requested")

            p_c = np.asarray(z, dtype=float)
            try:
                px, py = predict_sigma_from_fit_params(p_c[0], p_c[1], p_c[2], p_c[3], p_c[4], p_c[5], quad_k1l_0=(p_c[6] if self.fit_quadrupole_strength else None), allow_stop=False)
            except Exception:
                return np.full(n_x + n_y, 1e3, dtype=float)

            residuals_x = ((px - sig_x)[valid_x] / u_x[valid_x]).ravel()
            residuals_y = ((py - sig_y)[valid_y] / u_y[valid_y]).ravel()

            residuals = np.concatenate([ residuals_x, residuals_y])

            f = float(np.sum(residuals ** 2))
            if np.isfinite(f) and f < ls_best_cost[0]:
                ls_best_cost[0] = f
                ls_best_params[0] = p_c.copy()

            ls_eval[0] += 1
            self._emit_progress("Least squares", min(ls_eval[0], self.nm_steps), self.nm_steps)
            print(
                f" LS {ls_eval[0]}: "
                f"best_f={ls_best_cost[0]:.4g}, "
                f"current_emit_x={p_c[0]:.6g}, current_beta_x={p_c[1]:.6g}, current_alpha_x={p_c[2]:.6g}, "
                f"current_emit_y={p_c[3]:.6g}, current_beta_y={p_c[4]:.6g}, current_alpha_y={p_c[5]:.6g}"
                + (f", current_quad_k1l_0={p_c[6]:.6g}" if self.fit_quadrupole_strength else "")
            )

            return residuals

        best_res_ls = None
        best_res_ls_cost = np.inf
        stagnant_starts = 0
        stagnation_patience = 25
        min_improvement_of_cost = 1e-3
        good_fit_final_cost = 5e-11

        try:
            for start_idx, x0_try in enumerate(ls_starts):
                print(f"Starting LS multi-start {start_idx + 1}/{len(ls_starts)} from {x0_try}")
                best_cost_in_this_start = [np.inf]
                steps_without_improvement = [0]
                reason_to_stop = [None]

                def exit_ls_if_no_improvement_or_reached_goal(intermediate_result):
                    current_cost = 2.0 * float(intermediate_result.cost)
                    if not np.isfinite(current_cost):
                        return
                    if current_cost <= good_fit_final_cost:
                        reason_to_stop[0] = "target cost reached"
                        raise StopIteration
                    if not np.isfinite(best_cost_in_this_start[0]):
                        best_cost_in_this_start[0] = current_cost
                        return
                    if current_cost < best_cost_in_this_start[0]:
                        relative_improvement = (best_cost_in_this_start[0] - current_cost) / max(abs(best_cost_in_this_start[0]), 1e-12)
                        best_cost_in_this_start[0] = current_cost
                        if relative_improvement >= min_improvement_of_cost:
                            steps_without_improvement[0] = 0
                        else:
                            steps_without_improvement[0] += 1
                    else:
                        steps_without_improvement[0] += 1

                    if steps_without_improvement[0] >= stagnation_patience:
                        reason_to_stop[0] = "no meaningful improvement"
                        raise StopIteration

                try:
                    res_try = least_squares(_ls_residuals, x0_try, bounds=(low_bounds, high_bounds), method="trf", loss="linear", f_scale=1.0, max_nfev=self.nm_steps, x_scale=np.maximum(high_bounds - low_bounds, 1e-12), ftol=1e-8, xtol=1e-8, gtol=1e-8, callback = exit_ls_if_no_improvement_or_reached_goal)
                    p_try = np.asarray(res_try.x, dtype=float)
                    f_try, _, _ = compute_cost(p_try[0], p_try[1], p_try[2], p_try[3], p_try[4], p_try[5], quad_k1l_0=(p_try[6] if self.fit_quadrupole_strength else None), allow_stop=False)
                    if np.isfinite(f_try) and f_try < best_res_ls_cost:
                        best_res_ls_cost = float(f_try)
                        best_res_ls = res_try
                    if np.isfinite(f_try) and f_try < ls_best_cost[0]:
                        ls_best_cost[0] = float(f_try)
                        ls_best_params[0] = p_try.copy()
                    print(
                        f"  LS start {start_idx + 1}/{len(ls_starts)} finished: "
                        f"cost={float(f_try):.4g}, success={res_try.success}, "
                        f"nfev={res_try.nfev}/{self.nm_steps}."
                    )
                    if reason_to_stop[0] is not None:
                        print(f"Stopping LS: {reason_to_stop[0]}.")
                        break

                except StopIteration:
                    ls_stopped[0] = True
                    print("  LS interrupted.")
                    break
                except Exception as e:
                    print(f"  LS start {start_idx + 1}/{len(ls_starts)} failed ({e}).")

            if best_res_ls is not None:
                print(f"  Best LS multi-start cost={ls_best_cost[0]:.4g}")
            else:
                print(f"  No LS start improved BO result; using BO cost={ls_best_cost[0]:.4g}")

        except Exception as e:
            print(f"  LS multi-start failed ({e}), using BO result.")

        p_final = ls_best_params[0]
        best_cost_final = ls_best_cost[0]

        best_row = best_row.copy()
        if self.fit_quadrupole_strength:
            best_row["quad_k1l_0"] = float(p_final[6])
        best_row["emit_x_norm"] = float(p_final[0])
        best_row["beta_x0"] = float(p_final[1])
        best_row["alpha_x0"] = float(p_final[2])
        best_row["emit_y_norm"] = float(p_final[3])
        best_row["beta_y0"] = float(p_final[4])
        best_row["alpha_y0"] = float(p_final[5])

        stopped_during_fit = stopped_during_fit or ls_stopped[0]

        if stopped_during_fit or self._stop_requested or self._pause_requested:
            pred_x_p, pred_y_p = predict_sigma_from_fit_params(p_final[0], p_final[1], p_final[2], p_final[3], p_final[4], p_final[5], quad_k1l_0=(p_final[6] if self.fit_quadrupole_strength else None), allow_stop=False)
            solution = self._build_joint_partial_output(screens=screens, sigma_x=sig_x, sigma_y=sig_y, pred_x=pred_x_p, pred_y=pred_y_p, best_row=best_row, best_cost=best_cost_final)
            if self._pause_requested:
                raise OptimizationPaused("Optimization paused.", solution=solution)
            #raise OptimizationStopped("Optimization stopped.", solution=solution)
            return solution

        pred_x, pred_y = predict_sigma_from_fit_params(p_final[0], p_final[1], p_final[2], p_final[3], p_final[4], p_final[5], quad_k1l_0=(p_final[6] if self.fit_quadrupole_strength else None), allow_stop=True)

        solution = self._build_joint_partial_output(screens=screens, sigma_x=sig_x, sigma_y=sig_y, pred_x=pred_x, pred_y=pred_y, best_row=best_row, best_cost=best_cost_final)
        fit_error = self._calculate_optimalization_errors(best_res_ls, n_params=len(params_order))
        param_errors = fit_error["param_errors"]
        if param_errors is None or len(param_errors) != len(params_order):
            err_dict = {p: np.nan for p in params_order}
        else:
            err_dict = {p: float(e) for p, e in zip(params_order, param_errors)}

        solution["param_errors"] = err_dict
        solution["reduced_chi2"] = fit_error["reduced_chi2"]
        solution["chi2"] = fit_error["chi2"]
        solution["param_cov"] = fit_error["cov"]

        print(
            f"Fit parameter errors: "
            + ", ".join(f"{k}={v:.4g}" for k, v in err_dict.items())
            + f", reduced_chi2={fit_error['reduced_chi2']:.4g}"
        )

        return solution
