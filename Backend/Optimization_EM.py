import numpy as np
from scipy.stats import median_abs_deviation
from scipy.optimize import minimize
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

class Optimization_EM:
    def __init__(self, interface, n_starts=8, rng_seed=42, xopt_initial_points = 8, xopt_steps = 50, nm_steps = 100):
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
        joint_initial_guess = None
        if isinstance(initial_guess, dict):
            guess_x = (initial_guess or {}).get("x") if isinstance((initial_guess or {}).get("x"), dict) else {}
            guess_y = (initial_guess or {}).get("y") if isinstance((initial_guess or {}).get("y"), dict) else {}

            joint_initial_guess = {
                "emit_x_norm": guess_x.get("emit_norm"),
                "beta_x0": guess_x.get("beta0"),
                "alpha_x0": guess_x.get("alpha0"),
                "emit_y_norm": guess_y.get("emit_norm"),
                "beta_y0": guess_y.get("beta0"),
                "alpha_y0": guess_y.get("alpha0"),
            }

        try:
            joint_fit = self._fit_6d(screens=screens, quad_name=quad_name, K1_values=K1_values,
                                    sigx=sigx, sigx_std=sigx_std, sigy=sigy, sigy_std=sigy_std,
                                    initial_guess=joint_initial_guess)
            fit_x = {
                "emit": joint_fit["emit_x"],
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
                "emit": joint_fit["emit_y"],
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
                    f"emit_x={joint_fit['emit_x']:.6g}, beta_x0={joint_fit['beta_x0']:.6g}, alpha_x0={joint_fit['alpha_x0']:.6g}, "
                    f"emit_y={joint_fit['emit_y']:.6g}, beta_y0={joint_fit['beta_y0']:.6g}, alpha_y0={joint_fit['alpha_y0']:.6g}"
                )

        except (OptimizationStopped, OptimizationPaused) as e:
            if isinstance(getattr(e, "solution", None), dict):
                joint_fit = e.solution
                fit_x = {
                        "emit": joint_fit["emit_x"],
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
                        "emit": joint_fit["emit_y"],
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
            "emit_x": emit_x_geom,
            "beta_x0": float(best_row["beta_x0"]),
            "alpha_x0": float(best_row["alpha_x0"]),
            "emit_y": emit_y_geom,
            "beta_y0": float(best_row["beta_y0"]),
            "alpha_y0": float(best_row["alpha_y0"]),
            "pred_x": pred2_x,
            "pred_y": pred2_y,
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

    def _fit_6d(self, screens, quad_name, K1_values, sigx, sigx_std, sigy, sigy_std, initial_guess = None):
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

        emit_x_norm0, emit_y_norm0, beta_x0_0, beta_y0_0, alpha_x0_0, alpha_y0_0 = 2.0, 0.1, 10.0, 10.0, 0.0, 0.0
        if isinstance(initial_guess, dict):
            try:
                emit_x_norm0 = max(float(initial_guess.get("emit_x_norm", emit_x_norm0)), 1e-8)
            except Exception:
                pass
            try:
                emit_y_norm0 = max(float(initial_guess.get("emit_y_norm", emit_y_norm0)), 1e-8)
            except Exception:
                pass
            try:
                beta_x0_0 = max(float(initial_guess.get("beta_x0", beta_x0_0)), 1e-8)
            except Exception:
                pass
            try:
                beta_y0_0 = max(float(initial_guess.get("beta_y0", beta_y0_0)), 1e-8)
            except Exception:
                pass
            try:
                alpha_x0_0 = float(initial_guess.get("alpha_x0", alpha_x0_0))
            except Exception:
                pass
            try:
                alpha_y0_0 = float(initial_guess.get("alpha_y0", alpha_y0_0))
            except Exception:
                pass

        bounds = {
            "emit_x_norm": [1.0, 10.0],
            "beta_x0": [0.3, 25.0],
            "alpha_x0": [-10.0, 10.0],
            "emit_y_norm": [0.005, 0.2],
            "beta_y0": [0.3, 30.0],
            "alpha_y0": [-10.0, 10.0],
        }

        vocs = VOCS( # degrees of freedom
            variables = {i: [float(vals[0]), float(vals[1])] for i, vals in bounds.items()
        },
            objectives={"f": "MINIMIZE"},
        )

        def predict_raw(emit_x_norm, beta_x0, alpha_x0, emit_y_norm, beta_y0, alpha_y0, allow_stop = True):
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

            if emit_x_norm <= 0.0 or emit_y_norm <= 0.0 or beta_x0 <= 0.0 or beta_y0 <= 0.0:
                raise RuntimeError("Invalid joint fit paramaters. Emittance and beta should be positive.")
            emit_x_geom = max(emit_x_norm / beta_gamma, 1e-12)
            emit_y_geom = max(emit_y_norm / beta_gamma, 1e-12)

            try:
                pred_sigx, pred_sigy = self.interface.predict_emittance_scan_response(
                    quad_name=quad_name,
                    screens=screens,
                    K1_values=K1_values,
                    emit_x=emit_x_norm,
                    emit_y=emit_y_norm,
                    beta_x0=beta_x0,
                    beta_y0=beta_y0,
                    alpha_x0=alpha_x0,
                    alpha_y0=alpha_y0,
                    reference_screen=screens[0],
                    stop_checker=(lambda: self._stop_requested or self._pause_requested) if allow_stop else None,
                )
            except RuntimeError as e:
                if str(e) == "__OPTIMIZATION_STOP__":
                    if self._pause_requested:
                        raise OptimizationPaused("Optimization paused.")
                    raise OptimizationStopped("Optimization stopped.")
                raise
            pred_sigx = np.asarray(pred_sigx, dtype=float)
            pred_sigy = np.asarray(pred_sigy, dtype=float)
            if pred_sigx.shape != sigx.shape or pred_sigy.shape != sigy.shape:
                raise RuntimeError(
                    f"Sigma shape does not match measured shape"
                )
            return pred_sigx ** 2, pred_sigy ** 2

        def compute_cost(emit_x_norm, beta_x0, alpha_x0, emit_y_norm, beta_y0, alpha_y0, allow_stop = True):
            '''
            It compares how well a scan is predicting a model, how much it differs from data and
            minimizes f, so that it's as small as possible.
            '''
            if allow_stop and (self._stop_requested or self._pause_requested):
                if self._pause_requested:
                    raise OptimizationPaused("Optimization paused.")
                raise OptimizationStopped("Optimization stopped.")
            pred2_x, pred2_y = predict_raw(emit_x_norm, beta_x0, alpha_x0, emit_y_norm, beta_y0, alpha_y0, allow_stop = allow_stop)
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
            if self._stop_requested:
                raise OptimizationStopped("Optimization stopped.")
            if self._pause_requested:
                raise OptimizationPaused("Optimization paused.")

            f, _, _= compute_cost(float(inputs["emit_x_norm"]), float(inputs["beta_x0"]), float(inputs["alpha_x0"]),
                                float(inputs["emit_y_norm"]), float(inputs["beta_y0"]), float(inputs["alpha_y0"]), allow_stop = True)

            if self.print_M:
                print(
                    "Joint fit solution: "
                    f"emit_x_norm={float(inputs['emit_x_norm']):.6g}, beta_x0={float(inputs['beta_x0']):.6g}, alpha_x0={float(inputs['alpha_x0']):.6g}, "
                    f"emit_y_norm={float(inputs['emit_y_norm']):.6g}, beta_y0={float(inputs['beta_y0']):.6g}, alpha_y0={float(inputs['alpha_y0']):.6g}, f={f:.6g}"
                )
            return {"f": f}

        evaluator = Evaluator(function = evaluate) # how to calculate merit function
        generator = ExpectedImprovementGenerator(vocs = vocs) # how to choose the next point
        X = Xopt(generator = generator, evaluator = evaluator, vocs = vocs)

        seeds = [{
            "emit_x_norm": float(np.clip(emit_x_norm0, *bounds["emit_x_norm"])),
            "beta_x0": float(np.clip(beta_x0_0, *bounds["beta_x0"])),
            "alpha_x0": float(np.clip(alpha_x0_0, *bounds["alpha_x0"])),
            "emit_y_norm": float(np.clip(emit_y_norm0, *bounds["emit_y_norm"])),
            "beta_y0": float(np.clip(beta_y0_0, *bounds["beta_y0"])),
            "alpha_y0": float(np.clip(alpha_y0_0, *bounds["alpha_y0"])),
        }]

        total_initial = max(1, int(self.xopt_initial_points))

        for _ in range(max(0, total_initial - 1)):
            seeds.append({
                "emit_x_norm": float(np.exp(self.rng.uniform(np.log(bounds["emit_x_norm"][0]), np.log(bounds["emit_x_norm"][1])))),
                "beta_x0": float(np.exp(self.rng.uniform(np.log(bounds["beta_x0"][0]), np.log(bounds["beta_x0"][1])))),
                "alpha_x0": float(self.rng.uniform(bounds["alpha_x0"][0], bounds["alpha_x0"][1])),
                "emit_y_norm": float(np.exp(self.rng.uniform(np.log(bounds["emit_y_norm"][0]), np.log(bounds["emit_y_norm"][1])))),
                "beta_y0": float(np.exp(self.rng.uniform(np.log(bounds["beta_y0"][0]), np.log(bounds["beta_y0"][1])))),
                "alpha_y0": float(self.rng.uniform(bounds["alpha_y0"][0], bounds["alpha_y0"][1])),
            })

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

        try:
            X.evaluate_data(pd.DataFrame(seeds)) # for bayesian optimization to suggest better solutions, it needs some data
            update_best_from_data()
            for i in range(self.xopt_steps):
                if self.print_M:
                    print(f"Joint Xopt step {i + 1}/{self.xopt_steps}")
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

        if self._stop_requested or self._pause_requested:
            pred2_x_partial, pred2_y_partial = predict_raw(
                emit_x_norm_best, beta_x0_best, alpha_x0_best,
                emit_y_norm_best, beta_y0_best, alpha_y0_best,
                allow_stop=False
            )

            solution = self._build_joint_partial_output(
                screens=screens,
                sigma2_x=sig_x2,
                sigma2_y=sig_y2,
                pred2_x=pred2_x_partial,
                pred2_y=pred2_y_partial,
                best_row=best_row,
                best_cost=best_cost,
            )
            if self._pause_requested:
                raise OptimizationPaused("Optimization paused.", solution=solution)
            raise OptimizationStopped("Optimization stopped.", solution=solution)

        pred2_x, pred2_y = predict_raw(
            emit_x_norm_best, beta_x0_best, alpha_x0_best,
            emit_y_norm_best, beta_y0_best, alpha_y0_best,
            allow_stop=True,
        )
        run_nelder_mead = True # make True to run this algorithm
        if not run_nelder_mead:
            solution = self._build_joint_partial_output(
                screens=screens,
                sigma2_x=sig_x2,
                sigma2_y=sig_y2,
                pred2_x=pred2_x,
                pred2_y=pred2_y,
                best_row=best_row,
                best_cost=best_cost,
            )
            solution["message"] = "Joint x+y Xopt only. Nelder-Mead disabled for test."
            solution["stopped"] = bool(stopped_during_fit)
            return solution

        if self.print_M:
            print(f"Starting local optimization from f={best_cost:.4g}...")

        params_order = ["emit_x_norm", "beta_x0", "alpha_x0",
                       "emit_y_norm", "beta_y0", "alpha_y0"]

        low_nm = np.array([bounds[p][0] for p in params_order])
        high_nm = np.array([bounds[p][1] for p in params_order])

        x0_nm = np.array([
            emit_x_norm_best, beta_x0_best, alpha_x0_best,
            emit_y_norm_best, beta_y0_best, alpha_y0_best,
        ])

        nm_maxiter = self.nm_steps
        nm_best_cost   = [best_cost]
        nm_best_params = [x0_nm.copy()]
        nm_stopped     = [False]
        nm_iter        = [0]

        def _f_nm(p):
            penalty = float(np.sum(
                np.maximum(low_nm - p, 0.0) ** 2 +
                np.maximum(p - high_nm, 0.0) ** 2
            )) * 1e6
            p_c = np.clip(p, low_nm, high_nm)
            try:
                p2x, p2y = predict_raw(
                    p_c[0], p_c[1], p_c[2], p_c[3], p_c[4], p_c[5],
                    allow_stop=False,
                )
            except Exception:
                return 1e12 + penalty
            rx = (p2x - sig_x2)[valid_x].ravel() if np.any(valid_x) else np.array([], dtype=float)
            ry = (p2y - sig_y2)[valid_y].ravel() if np.any(valid_y) else np.array([], dtype=float)

            rx = rx[np.isfinite(rx)]
            ry = ry[np.isfinite(ry)]

            if rx.size == 0 and ry.size == 0:
                return 1e12 + penalty

            scale_x = np.nanmedian(np.abs(sig_x2[valid_x])) ** 2 if np.any(valid_x) else 1.0
            scale_y = np.nanmedian(np.abs(sig_y2[valid_y])) ** 2 if np.any(valid_y) else 1.0

            scale_x = max(float(scale_x), 1e-30)
            scale_y = max(float(scale_y), 1e-30)

            cost_x = float(np.mean(rx ** 2)) / scale_x if rx.size else 0.0
            cost_y = float(np.mean(ry ** 2)) / scale_y if ry.size else 0.0

            f = 0.5 * (cost_x + cost_y)
            total = f + penalty
            if np.isfinite(total) and total < nm_best_cost[0]:
                nm_best_cost[0] = total
                nm_best_params[0] = p_c.copy()
            return total

        def _nm_callback(p):
            nm_iter[0] += 1
            if self.print_M:
                p_c = np.clip(np.asarray(p, dtype=float), low_nm, high_nm)
                print(
                    f" NM iteration {nm_iter[0]}/{nm_maxiter}: "
                    f"best_f={nm_best_cost[0]:.4g}, "
                    f"current_emit_x={p_c[0]:.6g}, current_beta_x={p_c[1]:.6g}, current_alpha_x={p_c[2]:.6g}, "
                    f"current_emit_y={p_c[3]:.6g}, current_beta_y={p_c[4]:.6g}, current_alpha_y={p_c[5]:.6g}"
                )
            if self._stop_requested or self._pause_requested:
                nm_stopped[0] = True
                raise StopIteration("NM stop requested")
        try:
            res_nm = minimize(
                _f_nm, x0_nm, method="Nelder-Mead",
                options={"maxiter": nm_maxiter, "xatol": 1e-5, "fatol": 1e-5, "adaptive": True},
                callback=_nm_callback,
            )
            p_nm = np.clip(res_nm.x, low_nm, high_nm)
            if np.isfinite(res_nm.fun) and res_nm.fun < nm_best_cost[0]:
                nm_best_cost[0] = float(res_nm.fun)
                nm_best_params[0] = p_nm
            if self.print_M:
                print(f"  NM finished: cost={nm_best_cost[0]:.4g}, success={res_nm.success}, "
                      f"nit={res_nm.nit}/{nm_maxiter}")
        except StopIteration:
            nm_stopped[0] = True
            if self.print_M:
                print("  NM interrupted.")
        except Exception as e:
            if self.print_M:
                print(f"  NM failed ({e}), using BO result.")

        p_final = nm_best_params[0]
        best_cost_final = nm_best_cost[0]

        best_row = best_row.copy()
        best_row["emit_x_norm"] = float(p_final[0])
        best_row["beta_x0"]     = float(p_final[1])
        best_row["alpha_x0"]    = float(p_final[2])
        best_row["emit_y_norm"] = float(p_final[3])
        best_row["beta_y0"]     = float(p_final[4])
        best_row["alpha_y0"]    = float(p_final[5])

        stopped_during_fit = stopped_during_fit or nm_stopped[0]

        if stopped_during_fit or self._stop_requested or self._pause_requested:
            pred2_x_p, pred2_y_p = predict_raw(
                *p_final.tolist(), allow_stop=False
            )
            solution = self._build_joint_partial_output(
                screens=screens, sigma2_x=sig_x2,
                sigma2_y=sig_y2,
                pred2_x=pred2_x_p, pred2_y=pred2_y_p,
                best_row=best_row, best_cost=best_cost_final,
            )
            if self._pause_requested:
                raise OptimizationPaused("Optimization paused.", solution=solution)
            raise OptimizationStopped("Optimization stopped.", solution=solution)

        pred2_x, pred2_y = predict_raw(*p_final.tolist(), allow_stop=True)

        solution = self._build_joint_partial_output(
            screens=screens, sigma2_x=sig_x2,
            sigma2_y=sig_y2,
            pred2_x=pred2_x, pred2_y=pred2_y,
            best_row=best_row, best_cost=best_cost_final,
        )
        solution["message"] = "Joint x+y Xopt + Nelder-Mead."
        solution["stopped"] = bool(stopped_during_fit)
        return solution