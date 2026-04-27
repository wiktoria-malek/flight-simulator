import numpy as np
from scipy.stats import median_abs_deviation
import pandas as pd
from xopt import Xopt
from xopt.vocs import VOCS, select_best
from xopt.evaluator import Evaluator
from xopt.generators.bayesian import ExpectedImprovementGenerator

class OptimizationStopped(Exception):
    def __init__(self, message = "Optimization stopped", payload = None):
        super().__init__(message)
        self.payload = payload

class OptimizationPaused(Exception):
    def __init__(self, message="Optimization paused", payload=None):
        super().__init__(message)
        self.payload = payload

class Optimization_EM:
    def __init__(self, interface, n_starts=8, rng_seed=42):
        self.interface = interface
        self.n_starts = int(n_starts)
        self.rng = np.random.default_rng(rng_seed)
        self._stop_requested = False
        self._pause_requested = False
        self.best_out_so_far = None
        self._last_completed_output = None
        self.print_M = True
        self.xopt_initial_points = max(3, int(n_starts))
        self.xopt_steps = max(30, 10 * int(n_starts))

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

    def fit_from_session(self, session, initial_guess = None):
        was_pause_requested = bool(self._pause_requested)
        self.clear_stop()
        self._pause_requested = was_pause_requested
        if self.print_M:
            print("Starting to fit Twiss parameters and emittance...")
        screens = list(session.get("screens", []))
        quad_name = session.get("quad_name")
        K1_values = np.asarray(session.get("K1_values", []), dtype=float)

        sigx = np.asarray(session.get("sigx_mean", []), dtype=float)
        sigy = np.asarray(session.get("sigy_mean", []), dtype=float)
        sigx_std = np.asarray(session.get("sigx_std", []), dtype=float)
        sigy_std = np.asarray(session.get("sigy_std", []), dtype=float)

        if not quad_name:
            raise ValueError("Session does not contain quad_name")
        if len(screens) < 2:
            raise ValueError("At least two screens are required")
        if K1_values.size == 0:
            raise ValueError("Session does not contain K1_values")
        if sigx.ndim != 2 or sigy.ndim != 2:
            raise ValueError("Invalid sigma array shape")
        if sigx.shape != sigy.shape:
            raise ValueError("sigx and sigy shapes do not match")
        if sigx.shape[0] != K1_values.size:
            raise ValueError("K1_values and sigma arrays have incompatible lengths")

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

        fit_x = None
        fit_y = None
        try:
            fit_x = self._fit_plane(plane="x", screens=screens, quad_name=quad_name, K1_values=K1_values, sigma=sigx, sigma_std=sigx_std,
                                    initial_guess = (initial_guess or {}).get("x") if isinstance(initial_guess, dict) else None)

            if self.print_M:
                print(
                    f"Plane x done: "
                    f"success={fit_x['success']}, "
                    f"cost={fit_x['cost']:.6g}, "
                    f"stopped={fit_x.get('stopped', False)}, "
                    f"emit={fit_x['emit']:.6g}, "
                    f"beta0={fit_x['beta0']:.6g}, "
                    f"alpha0={fit_x['alpha0']:.6g}"
                )
        except (OptimizationStopped, OptimizationPaused):
            fit_x = None
        try:
            fit_y = self._fit_plane(plane="y", screens=screens, quad_name=quad_name, K1_values=K1_values, sigma=sigy, sigma_std=sigy_std,
                                    initial_guess = (initial_guess or {}).get("y") if isinstance(initial_guess, dict) else None)

            if self.print_M:
                print(
                    f"Plane y done: "
                    f"success={fit_y['success']}, "
                    f"cost={fit_y['cost']:.6g}, "
                    f"stopped={fit_y.get('stopped', False)}, "
                    f"emit={fit_y['emit']:.6g}, "
                    f"beta0={fit_y['beta0']:.6g}, "
                    f"alpha0={fit_y['alpha0']:.6g}"
                )
        except (OptimizationStopped, OptimizationPaused):
            fit_y = None

        if fit_x is None:
            fit_x = _plane_no_solution("x", sigma2_template_x)
        if fit_y is None:
            fit_y = _plane_no_solution("y", sigma2_template_y)

        gamma_rel, beta_rel = self.interface.get_beam_factors()
        emit_x_norm = (
            gamma_rel * beta_rel * fit_x["emit"]
            if np.isfinite(gamma_rel) and np.isfinite(beta_rel) and np.isfinite(fit_x["emit"])
            else np.nan
        )
        emit_y_norm = (
            gamma_rel * beta_rel * fit_y["emit"]
            if np.isfinite(gamma_rel) and np.isfinite(beta_rel) and np.isfinite(fit_y["emit"])
            else np.nan
        )

        stopped = bool(fit_x.get("stopped", False) or fit_y.get("stopped", False) or self._stop_requested)

        result = {
            "screen0": screens[0],
            "quad_name": quad_name,
            "optimizer": "xopt_based_optimization",
            "transport_source": "rftrack_forward_scan",

            "emit_x_norm": emit_x_norm,
            "emit_y_norm": emit_y_norm,
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


    def _safe_sigma2_errors(self, sig, sig_std): # so that the fit is not degenerated by dividing by 0
        sig = np.asarray(sig, dtype=float)
        sig_std = np.asarray(sig_std, dtype=float)

        sigma2 = sig ** 2
        sigma2_err = 2.0 * np.abs(sig) * np.abs(sig_std)

        screen_scale = np.nanmedian(sigma2, axis=0) # typical values, per each screen
        screen_scale = np.where(np.isfinite(screen_scale), screen_scale, np.nan)

        floor_per_screen = np.maximum(0.03 * np.abs(screen_scale), 1e-6) # error of sigma^2 cannot be lower than 3% of a typical sigma^2 value on each screen
        floor_per_screen = np.where(np.isfinite(floor_per_screen), floor_per_screen, 1e-6) # if a value is nan, in or -inf, it gets substituted as 1e-6

        sigma2_err = np.where(np.isfinite(sigma2_err), sigma2_err, np.nan)
        sigma2_err = np.maximum(sigma2_err, floor_per_screen[None, :]) # if error value is lower than minimum, it gets replaced
        sigma2_err[~np.isfinite(sigma2_err)] = 1e-6 # if it's wrong, it gets replaced by 1e-6

        return sigma2_err

    def _get_nominal_guess(self, plane):
        if hasattr(self.interface, "get_nominal_beam_twiss"):
            tw = self.interface.get_nominal_beam_twiss()
            if plane == "x":
                return (
                    tw["emit_x_norm"],
                    tw["beta_x"],
                    tw["alpha_x"],
                )
            return (
                tw["emit_y_norm"],
                tw["beta_y"],
                tw["alpha_y"],
            )

        if plane == "x":
            return (1.0, 5.0, 0.0)
        return (1.0, 5.0, 0.0)

    def _fit_plane(self, plane, screens, quad_name, K1_values, sigma, sigma_std, initial_guess = None):
        sigma = np.asarray(sigma, dtype=float)
        sigma_std = np.asarray(sigma_std, dtype=float)
        sigma2 = sigma ** 2
        sigma2_err = self._safe_sigma2_errors(sigma, sigma_std)

        nominal_emit_norm, nominal_beta0, nominal_alpha0 = self._get_nominal_guess(plane)

        gamma_rel, beta_rel = self.interface.get_beam_factors()
        beta_gamma = gamma_rel * beta_rel
        if not np.isfinite(beta_gamma) or beta_gamma <= 0:
            raise RuntimeError("Invalid beam factors")

        nominal_emit_norm = float(nominal_emit_norm) if np.isfinite(nominal_emit_norm) else 1.0
        nominal_emit_norm = max(nominal_emit_norm, 1e-6)

        nominal_beta0 = float(nominal_beta0) if np.isfinite(nominal_beta0) else 5.0
        nominal_beta0 = max(nominal_beta0, 1e-6)

        nominal_alpha0 = float(nominal_alpha0) if np.isfinite(nominal_alpha0) else 0.0

        valid = np.isfinite(sigma2) & np.isfinite(sigma2_err) & (sigma2_err > 0)
        if not np.any(valid): # if False
            raise RuntimeError(f"No valid measurements for plane {plane}")

        def predict_raw(emit_norm, beta0, alpha0, allow_stop = True):
            '''
            If a beam size on reference screen has certain twiss parameters and given emittance,
            what quadrupole scan should be?
            It's based on implementation in the RFTrack interface, where:
            it sets a quadrupole to each K1, build a bunch with given Twiss parameters, tracks it and
            read beam sizes at screens.
            '''
            emit_norm = float(emit_norm)
            beta0 = float(beta0)
            alpha0 = float(alpha0)

            if not np.isfinite(emit_norm) or emit_norm <= 0:
                raise RuntimeError(f"Invalid emit norm {emit_norm}")
            if not np.isfinite(beta0) or beta0 <= 0:
                raise RuntimeError(f"beta0 {beta0} must be positive")
            if not np.isfinite(alpha0):
                raise RuntimeError(f"alpha0 {alpha0} must be finite")

            emit_geom = max(emit_norm / beta_gamma, 1e-12)

            try:
                pred_sigma = self.interface.predict_emittance_scan_response(
                    plane=plane,
                    quad_name=quad_name,
                    screens=screens,
                    K1_values=K1_values,
                    emit=emit_geom,
                    beta0=beta0,
                    alpha0=alpha0,
                    stop_checker=(lambda: self._stop_requested or self._pause_requested) if allow_stop else None,
                )
            except RuntimeError as e:
                if str(e) == "__OPTIMIZATION_STOP__":
                    if self._pause_requested:
                        raise OptimizationPaused("Optimization paused.")
                    raise OptimizationStopped("Optimization stopped.")
                raise
            pred_sigma = np.asarray(pred_sigma, dtype=float)
            if pred_sigma.shape != sigma.shape:
                raise RuntimeError(
                    f"Sigma shape {pred_sigma.shape} does not match measured shape {sigma.shape}"
                )
            return pred_sigma ** 2

        valid = np.isfinite(sigma2) & np.isfinite(sigma2_err) & (sigma2_err > 0)


        def compute_cost(emit_norm, beta0, alpha0, allow_stop = True):
            '''
            It compares how well a scan is predicting a model, how much it differs from data and
            minimizes f, so that it's as small as possible.
            '''
            pred2 = predict_raw(emit_norm, beta0, alpha0, allow_stop = allow_stop)
            data_res = (pred2 - sigma2) / sigma2_err # predicted - measured / error^2
            res = np.asarray(data_res[valid].ravel(), dtype=float) # the better the match, the smaller the number
            if res.size == 0:
                return np.inf, pred2
            return float(np.mean(res**2)), pred2 # so positive and negative residuals are not cancalled and fit doesn't think it's perfect, it also punishes better worse solutions

        last_emit_norm = nominal_emit_norm # nominal starts from the interface
        last_beta0 = nominal_beta0
        last_alpha0 = nominal_alpha0

        if isinstance(initial_guess, dict) and bool(initial_guess.get("found", False)): # if it's starting after resuming, starts from best solution so far
            try:
                last_emit_norm_cand = float(initial_guess.get("emit_norm"))
                last_beta0_cand = float(initial_guess.get("beta0"))
                last_alpha0_cand = float(initial_guess.get("alpha0"))
            except Exception:
                last_emit_norm_cand = np.nan
                last_beta0_cand = np.nan
                last_alpha0_cand = np.nan

            if np.isfinite(last_emit_norm_cand) and last_emit_norm_cand > 0:
                last_emit_norm = max(last_emit_norm_cand, 1e-8)

            if np.isfinite(last_beta0_cand) and last_beta0_cand > 0:
                last_beta0 = max(last_beta0_cand, 1e-8)

            if np.isfinite(last_alpha0_cand):
                last_alpha0 = last_alpha0_cand

            if self.print_M:
                print(
                    f"Plane {plane}: resuming fitting, starting from last values before pausing. "
                    f"emit_norm={last_emit_norm:.6g}, "
                    f"beta0={last_beta0:.6g}, "
                    f"alpha0={last_alpha0:.6g}"
                )

        emit_low = max(1e-5, min(last_emit_norm, nominal_emit_norm) * 0.05) # minimal = 1e-5
        emit_high = max(emit_low * 10.0, max(last_emit_norm, nominal_emit_norm) * 20.0)

        beta_low = max(1e-4, min(last_beta0, nominal_beta0) * 0.05)
        beta_high = max(beta_low * 10.0, max(last_beta0, nominal_beta0) * 20.0)

        alpha_span = max(10.0, abs(last_alpha0), abs(nominal_alpha0))
        alpha_low = float(last_alpha0 - 2.0 * alpha_span)
        alpha_high = float(last_alpha0 + 2.0 * alpha_span)

        vocs = VOCS( # degrees of freedom
            variables = {
            "emit_norm": [float(emit_low), float(emit_high)],
            "beta0": [float(beta_low), float(beta_high)],
            "alpha0": [float(alpha_low), float(alpha_high)],

        },
            objectives={"f": "MINIMIZE"},
        )


        def evaluate(inputs):
            if self._stop_requested:
                raise OptimizationStopped("Optimization stopped.")

            if self._pause_requested:
                raise OptimizationPaused("Optimization paused.")

            emit_norm = float(inputs["emit_norm"])
            beta0 = float(inputs["beta0"])
            alpha0 = float(inputs["alpha0"])

            f, _ = compute_cost(emit_norm, beta0, alpha0, allow_stop = True)

            if self.print_M:
                    print(
                        f"Plane {plane}: "
                        f"Xopt eval emit_norm={emit_norm:.6g}, "
                        f"beta0={beta0:.6g}, "
                        f"alpha0={alpha0:.6g},"
                        f"f={f:.6g}"
                    )
            return {"f": f}

        evaluator = Evaluator(function = evaluate) # how to calculate merit function
        generator = ExpectedImprovementGenerator(vocs = vocs) # how to choose the next point
        X = Xopt(generator = generator, evaluator = evaluator, vocs = vocs)

        seeds = [
            {
                "emit_norm" : float(np.clip(last_emit_norm, emit_low, emit_high)),
                "beta0" : float(np.clip(last_beta0, beta_low, beta_high)),
                "alpha0" : float(np.clip(last_alpha0, alpha_low, alpha_high)),
            }
        ]

        for _ in range(self.xopt_initial_points - 1):
            seeds.append(
                {
                    "emit_norm": float(np.clip(last_emit_norm * np.exp(self.rng.normal(0.0, 0.6)), emit_low, emit_high)),
                    "beta0": float(np.clip(last_beta0 * np.exp(self.rng.normal(0.0, 0.4)), beta_low, beta_high)),
                    "alpha0": float(np.clip(last_alpha0 + self.rng.normal(0.0, 1.0), alpha_low, alpha_high)),
                }
            )

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
            idx = good["f"].astype(float).idxmin() # change each value to float
            row = good.loc[idx]
            cost = float(row["f"])

            if np.isfinite(cost) and cost < best_cost: # updates best solution
                best_cost = cost
                best_row = row

                if self.print_M:
                    print(
                        f"Plane {plane}: "
                        f" New best from Xopt, cost={best_cost:.6g}, "
                        f"emit_norm={float(row['emit_norm']):.6g}, "
                        f"beta0={float(row['beta0']):.6g}, "
                        f"alpha0={float(row['alpha0']):.6g}, "
                    )

        try:
            X.evaluate_data(pd.DataFrame(seeds)) # for bayesian optimization to suggest better solutions, it needs some data
            update_best_from_data()

            for i in range(self.xopt_steps):
                if self.print_M:
                    print(f"Plane {plane}: Xopt step {i + 1}/{self.xopt_steps}")
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

        if self.print_M:
            print(
                f"Plane {plane}: Xopt finished."
                f"evaluations = {0 if getattr(X, 'data', None) is None else len(X.data)},"
                f"best_found={best_row is not None}, stopped={stopped_during_fit}"
                )

        if best_row is None:
            raise RuntimeError(f"Xopt failed to find best fit solution for plane {plane}.")

        emit_norm_best = float(best_row["emit_norm"])
        beta0_best = float(best_row["beta0"])
        alpha0_best = float(best_row["alpha0"])
        emit_geom_best = max(emit_norm_best / beta_gamma, 1e-12)

        pred2 = predict_raw(emit_norm_best, beta0_best, alpha0_best, allow_stop = False)
        data_res = []
        per_screen_res = {screen: [] for screen in screens}

        for k in range(sigma.shape[0]):
            for i, screen in enumerate(screens):
                y = sigma2[k, i] # measured
                yp = pred2[k, i] # model for best fit
                err = sigma2_err[k, i]
                if np.isfinite(y) and np.isfinite(yp) and np.isfinite(err) and err > 0:
                    r = (yp - y) / err
                    data_res.append(r)
                    per_screen_res[screen].append(r) # for final best fit

        data_res = np.asarray(data_res, dtype=float)

        rms_res = float(np.sqrt(np.mean(data_res ** 2))) if data_res.size else np.nan
        mad_res = float(median_abs_deviation(data_res, scale="normal")) if data_res.size else np.nan

        per_screen_rms = {}
        for screen, vals in per_screen_res.items():
            vals = np.asarray(vals, dtype=float)
            per_screen_rms[screen] = float(np.sqrt(np.mean(vals ** 2))) if vals.size else np.nan

        finite_items = [(screen, val) for screen, val in per_screen_rms.items() if np.isfinite(val)]
        worst_screen = max(finite_items, key=lambda x: x[1])[0] if finite_items else None
        message = f"Xopt best after {0 if getattr(X, 'data', None) is None else len(X.data)} evaluations."

        return {
            "emit": float(emit_geom_best),
            "beta0": float(beta0_best),
            "alpha0": float(alpha0_best),
            "pred": pred2,
            "residual_rms": rms_res,
            "residual_mad": mad_res,
            "residual_rms_per_screen": per_screen_rms,
            "worst_screen": worst_screen,
            "success": True,
            "message": message,
            "cost": float(best_cost),
            "stopped": bool(stopped_during_fit),
        }