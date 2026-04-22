import numpy as np
from scipy.optimize import least_squares
from scipy.stats import median_abs_deviation


class Optimization_EM:
    def __init__(self, interface, n_starts=8, rng_seed=42):
        self.interface = interface
        self.n_starts = int(n_starts)
        self.rng = np.random.default_rng(rng_seed)

    def fit_from_session(self, session):
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

        fit_x = self._fit_plane(
            plane="x",
            screens=screens,
            quad_name=quad_name,
            K1_values=K1_values,
            sigma=sigx,
            sigma_std=sigx_std,
        )

        fit_y = self._fit_plane(
            plane="y",
            screens=screens,
            quad_name=quad_name,
            K1_values=K1_values,
            sigma=sigy,
            sigma_std=sigy_std,
        )

        gamma_rel, beta_rel = self.interface.get_beam_factors()
        emit_x_norm = gamma_rel * beta_rel * fit_x["emit"] if np.isfinite(gamma_rel) and np.isfinite(beta_rel) else np.nan
        emit_y_norm = gamma_rel * beta_rel * fit_y["emit"] if np.isfinite(gamma_rel) and np.isfinite(beta_rel) else np.nan

        result = {
            "screen0": screens[0],
            "quad_name": quad_name,
            "optimizer": "least_squares_direct_scan",
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
        }

        return {
            "result": result,
            "pred_x": fit_x["pred"],
            "pred_y": fit_y["pred"],
        }

    def _safe_sigma2_errors(self, sig, sig_std):
        sig = np.asarray(sig, dtype=float)
        sig_std = np.asarray(sig_std, dtype=float)

        sigma2 = sig ** 2
        sigma2_err = 2.0 * np.abs(sig) * np.abs(sig_std)

        screen_scale = np.nanmedian(sigma2, axis=0)
        screen_scale = np.where(np.isfinite(screen_scale), screen_scale, np.nan)

        floor_per_screen = np.maximum(0.03 * np.abs(screen_scale), 1e-6)
        floor_per_screen = np.where(np.isfinite(floor_per_screen), floor_per_screen, 1e-6)

        sigma2_err = np.where(np.isfinite(sigma2_err), sigma2_err, np.nan)
        sigma2_err = np.maximum(sigma2_err, floor_per_screen[None, :])
        sigma2_err[~np.isfinite(sigma2_err)] = 1e-6

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

    def _fit_plane(self, plane, screens, quad_name, K1_values, sigma, sigma_std):
        sigma = np.asarray(sigma, dtype=float)
        sigma_std = np.asarray(sigma_std, dtype=float)
        sigma2 = sigma ** 2
        sigma2_err = self._safe_sigma2_errors(sigma, sigma_std)

        nominal_emit_norm, nominal_beta0, nominal_alpha0 = self._get_nominal_guess(plane)

        gamma_rel, beta_rel = self.interface.get_beam_factors()
        gb = gamma_rel * beta_rel
        if not np.isfinite(gb) or gb <= 0:
            raise RuntimeError("Invalid beam factors")

        nominal_emit_geom = float(nominal_emit_norm) / gb
        if not np.isfinite(nominal_emit_geom) or nominal_emit_geom <= 0:
            nominal_emit_geom = 1e-6

        def unpack(p):
            log_emit = float(p[0])
            log_beta0 = float(p[1])
            alpha0 = float(p[2])

            emit = np.exp(log_emit)
            beta0 = np.exp(log_beta0)
            return emit, beta0, alpha0

        def predict(p):
            emit, beta0, alpha0 = unpack(p)
            pred_sigma = self.interface.predict_emittance_scan_response(
                plane=plane,
                quad_name=quad_name,
                screens=screens,
                K1_values=K1_values,
                emit=emit,
                beta0=beta0,
                alpha0=alpha0,
            )
            pred_sigma = np.asarray(pred_sigma, dtype=float)
            if pred_sigma.shape != sigma.shape:
                raise RuntimeError(
                    f"Predicted sigma shape {pred_sigma.shape} does not match measured shape {sigma.shape}"
                )
            return pred_sigma ** 2

        valid = np.isfinite(sigma2) & np.isfinite(sigma2_err) & (sigma2_err > 0)

        def residuals(p):
            pred2 = predict(p)
            data_res = (pred2 - sigma2) / sigma2_err
            return np.asarray(data_res[valid].ravel(), dtype=float)

        starts = [
            np.array([
                np.log(nominal_emit_geom),
                np.log(max(float(nominal_beta0), 1e-8)),
                float(nominal_alpha0),
            ], dtype=float)
        ]

        for _ in range(self.n_starts - 1):
            starts.append(np.array([
                np.log(nominal_emit_geom) + self.rng.normal(0.0, 0.8),
                np.log(max(float(nominal_beta0), 1e-8)) + self.rng.normal(0.0, 0.5),
                float(nominal_alpha0) + self.rng.normal(0.0, 1.0),
            ], dtype=float))

        lower = np.array([np.log(1e-10), np.log(1e-4), -10.0], dtype=float)
        upper = np.array([np.log(1e2), np.log(1e4), 10.0], dtype=float)

        best = None
        best_cost = np.inf

        for x0 in starts:
            x0 = np.minimum(np.maximum(x0, lower + 1e-12), upper - 1e-12)

            fit = least_squares(
                residuals,
                x0,
                method="trf",
                loss="soft_l1",
                f_scale=1.0,
                bounds=(lower, upper),
                max_nfev=50,
            )

            if fit.cost < best_cost:
                best_cost = float(fit.cost)
                best = fit

        if best is None:
            raise RuntimeError(f"Direct fit failed for plane {plane}")

        emit, beta0, alpha0 = unpack(best.x)
        pred2 = predict(best.x)

        data_res = []
        per_screen_res = {screen: [] for screen in screens}

        for k in range(sigma.shape[0]):
            for i, screen in enumerate(screens):
                y = sigma2[k, i]
                yp = pred2[k, i]
                err = sigma2_err[k, i]
                if np.isfinite(y) and np.isfinite(yp) and np.isfinite(err) and err > 0:
                    r = (yp - y) / err
                    data_res.append(r)
                    per_screen_res[screen].append(r)

        data_res = np.asarray(data_res, dtype=float)

        rms_res = float(np.sqrt(np.mean(data_res ** 2))) if data_res.size else np.nan
        mad_res = float(median_abs_deviation(data_res, scale="normal")) if data_res.size else np.nan

        per_screen_rms = {}
        for screen, vals in per_screen_res.items():
            vals = np.asarray(vals, dtype=float)
            per_screen_rms[screen] = float(np.sqrt(np.mean(vals ** 2))) if vals.size else np.nan

        finite_items = [(screen, val) for screen, val in per_screen_rms.items() if np.isfinite(val)]
        worst_screen = max(finite_items, key=lambda x: x[1])[0] if finite_items else None

        return {
            "emit": float(emit),
            "beta0": float(beta0),
            "alpha0": float(alpha0),
            "pred": pred2,
            "residual_rms": rms_res,
            "residual_mad": mad_res,
            "residual_rms_per_screen": per_screen_rms,
            "worst_screen": worst_screen,
            "success": bool(best.success),
            "message": str(best.message),
            "cost": float(best.cost),
        }