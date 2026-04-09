import numpy as np
from scipy.optimize import least_squares


class MeasureOptics:

    def __init__(self, interface, n_starts=5, rng_seed=42): #every time it's the same random set of numbers, pseudorandom
        self.interface = interface
        self.n_starts = int(n_starts) # how many restarts with initial values
        self.rng = np.random.default_rng(rng_seed) # exactly for random starting points in _fit_plane

    def get_from_session(self, session, screen_response = None):

        screens = list(session.get("screens", []))
        K1_values = np.asarray(session.get("K1_values", []), dtype=float)
        deltas = np.asarray(session.get("deltas", []), dtype=float)

        sigx = np.asarray(session.get("sigx_mean", []), dtype=float)
        sigy = np.asarray(session.get("sigy_mean", []), dtype=float)
        sigx_std = np.asarray(session.get("sigx_std", []), dtype=float)
        sigy_std = np.asarray(session.get("sigy_std", []), dtype=float)

        if len(screens) < 2:
            raise ValueError("At least 2 screens are required.")

        if sigx.ndim != 2 or sigy.ndim != 2:
            raise ValueError("Invalid sigma array shape.")

        if deltas.size == K1_values.size and deltas.size > 0:
            idx0 = int(np.argmin(np.abs(deltas))) # which K1 is the most nominal, so delta=0, it's basically K1_0 [1/m2]
        else:
            idx0 = len(K1_values) // 2

        K1_nom = float(K1_values[idx0])

        model_twiss_screen0 = None
        try:
            if hasattr(self.interface, "get_twiss_at_screen") and screens:
                model_twiss_screen0 = self.interface.get_twiss_at_screen(screens[0])
        except Exception:
            model_twiss_screen0 = None

        fit_x = self._fit_plane(K1_values=K1_values, sigma=sigx, sigma_std=sigx_std, K1_nom=K1_nom, plane="x", model_twiss=model_twiss_screen0, screen_response=screen_response, screens = screens)
        fit_y = self._fit_plane(K1_values=K1_values, sigma=sigy, sigma_std=sigy_std, K1_nom=K1_nom, plane="y", model_twiss=model_twiss_screen0, screen_response=screen_response, screens = screens)

        return {
            "type": "screen0_twiss_vs_K1",
            "screens": screens,
            "K1_values": K1_values.tolist(),
            "K1_nom": K1_nom,
            "fit_x": fit_x,
            "fit_y": fit_y,
            "screen_response": screen_response,
        }

    @staticmethod
    def _twiss_from_fit_params(fit, K1_values, K1_nom):
        K1_values = np.asarray(K1_values, dtype=float)
        dK1 = K1_values - float(K1_nom)

        beta_log_p0 = float(fit["beta_log_p0"])
        beta_log_p1 = float(fit["beta_log_p1"])
        beta_log_p2 = float(fit["beta_log_p2"])
        alpha_p0 = float(fit["alpha_p0"])
        alpha_p1 = float(fit["alpha_p1"])
        alpha_p2 = float(fit.get("alpha_p2", 0.0))

        beta0 = np.exp(beta_log_p0 + beta_log_p1 * dK1 + beta_log_p2 * dK1**2)
        alpha0 = alpha_p0 + alpha_p1 * dK1 + alpha_p2 * dK1**2

        return beta0, alpha0

    @staticmethod
    def _get_transport_at_K1(measured_optics, plane, K1_values):
        fit = measured_optics[f"fit_{plane}"]
        params = np.asarray(fit["transport_params"], dtype=float)
        K1_values = np.asarray(K1_values, dtype=float)
        K1_nom = float(measured_optics["K1_nom"])
        dK1_values = K1_values - K1_nom

        result = []
        for dK1 in dK1_values:
            Rs = [np.eye(2)]
            for row in params:
                row = np.asarray(row, dtype=float).ravel()
                if row.size == 2:
                    R11, R12 = row
                elif row.size == 4:
                    R11_0, R11_1, R12_0, R12_1 = row
                    R11 = R11_0 + R11_1 * dK1
                    R12 = R12_0 + R12_1 * dK1
                else:
                    raise ValueError(f"Unexpected transport parameter size: {row.size}")

                Rs.append(np.array([
                    [R11, R12],
                    [0.0, 1.0]
                ]))
            result.append(Rs)

        return result

    def _fit_plane(self, K1_values, sigma, sigma_std, K1_nom, plane, model_twiss=None, screen_response=None, screens=None):
        nsteps, nscreens = sigma.shape
        dK1_values = K1_values - K1_nom

        sigma2_raw = sigma ** 2 # nsteps x nscreens
        sigma2_err = 2.0 * np.abs(sigma) * np.abs(sigma_std)

        screen_scale = np.nanmedian(sigma2_raw, axis=0)
        screen_scale = np.where(np.isfinite(screen_scale), screen_scale, np.nan)

        floor_per_screen = np.maximum(0.03 * np.abs(screen_scale), 1e-6)
        floor_per_screen = np.where(np.isfinite(floor_per_screen), floor_per_screen, 1e-6)

        sigma2_err = np.where(np.isfinite(sigma2_err), sigma2_err, np.nan)
        sigma2_err = np.maximum(sigma2_err, floor_per_screen[None, :])
        sigma2_err[~np.isfinite(sigma2_err)] = 1e-6

        valid_downstream = (
                np.isfinite(sigma2_raw[:, 1:]) &
                np.isfinite(sigma2_err[:, 1:]) &
                (sigma2_err[:, 1:] > 0)
        )
        nom_idx = int(np.argmin(np.abs(dK1_values)))
        sig2_0 = float(np.nanmedian(sigma2_raw[:, 0]))

        model_beta_guess = np.nan
        model_alpha_guess = np.nan
        if isinstance(model_twiss, dict):
            model_beta_guess = float(model_twiss.get(f"beta_{plane}", np.nan))
            model_alpha_guess = float(model_twiss.get(f"alpha_{plane}", np.nan))

        if np.isfinite(model_beta_guess) and model_beta_guess > 1e-6:
            beta_guess = float(model_beta_guess)
        else:
            beta_guess = max(sig2_0 / 1e-3, 1e-6)

        if np.isfinite(model_alpha_guess):
            alpha_guess = float(model_alpha_guess)
        else:
            alpha_guess = 0.0

        screen_names = list(screens or [])
        response_rel_amp = None
        response_monitor_names = []
        response_matrix = None

        if screen_response is not None:
            response_monitor_names = [str(name) for name in getattr(screen_response, "bpms", [])]

            if plane == "x":
                response_matrix = np.asarray(getattr(screen_response, "Rxx", None), dtype=float)
            else:
                response_matrix = np.asarray(getattr(screen_response, "Ryy", None), dtype=float)

            if response_matrix is not None and response_matrix.ndim == 2 and response_matrix.shape[0] == len(response_monitor_names):
                row_norms = np.linalg.norm(np.nan_to_num(response_matrix, nan = 0.0), axis=1)
                response_map = {name: float(val) for name, val in zip(response_monitor_names, row_norms)}
                amps = np.asarray([response_map.get(str(name), np.nan) for name in screen_names], dtype=float)
                if amps.size == nscreens and amps.size >=2 and np.all(np.isfinite(amps[1:])):
                    ref = np.nanmedian(amps[1:])
                    if np.isfinite(ref) and ref > 0:
                        response_rel_amp = amps[1:] / ref

        x0_twiss = np.array([
            np.log(beta_guess),  # beta_log_p0
            0.0,                 # beta_log_p1
            0.0,                 # beta_log_p2
            alpha_guess,         # alpha_p0
            0.0,                 # alpha_p1
            0.0                  # alpha_p2
        ], dtype=float)

        c0 = np.ones(nscreens - 1, dtype=float)
        t0 = np.zeros((nscreens - 1, 2), dtype=float)
        t0[:, 0] = 1.0  # R11
        t0[:, 1] = 1.0  # R12

        x0_canonical = np.concatenate([x0_twiss, c0, t0.ravel()])

        def unpack(x):
            beta_log_p0 = float(x[0])
            beta_log_p1 = float(x[1])
            beta_log_p2 = float(x[2])
            alpha_p0 = float(x[3])
            alpha_p1 = float(x[4])
            alpha_p2 = float(x[5])

            c_params = x[6:6 + (nscreens - 1)]
            t_params = x[6 + (nscreens - 1):].reshape(nscreens - 1, 2)

            return beta_log_p0, beta_log_p1, beta_log_p2, alpha_p0, alpha_p1, alpha_p2, c_params, t_params

        def predict(x):
            beta_log_p0, beta_log_p1, beta_log_p2, alpha_p0, alpha_p1, alpha_p2, c_params, t_params = unpack(x)

            pred = np.full((nsteps, nscreens), np.nan, dtype=float)

            for k, dK1 in enumerate(dK1_values):
                beta0 = np.exp(beta_log_p0 + beta_log_p1 * dK1 + beta_log_p2 * dK1 ** 2)
                beta0 = max(beta0, 1e-12)
                alpha0 = alpha_p0 + alpha_p1 * dK1 + alpha_p2 * dK1 ** 2
                gamma0 = (1.0 + alpha0 ** 2) / beta0

                sigma2_ref_meas = max(float(sigma2_raw[k, 0]), 1e-12)
                pred[k, 0] = sigma2_ref_meas

                for i, (R11, R12) in enumerate(t_params):
                    numer = (R11 ** 2 * beta0 - 2.0 * R11 * R12 * alpha0 + R12 ** 2 * gamma0)
                    val = c_params[i] * sigma2_ref_meas * (numer / beta0)
                    if np.isfinite(val):
                        pred[k, i + 1] = val

            return pred

        def residuals(x):
            pred = predict(x)
            res = []

            pred_downstream = pred[:, 1:]
            meas_downstream = sigma2_raw[:, 1:]
            err_downstream = sigma2_err[:, 1:]

            safe_pred_downstream = np.where(np.isfinite(pred_downstream), pred_downstream, 0.0)
            data_residuals = (safe_pred_downstream - meas_downstream) / err_downstream

            invalid_penalty = np.where(
                valid_downstream & ~np.isfinite(pred_downstream),
                1e6,
                0.0
            )

            data_residuals = np.where(
                valid_downstream,
                data_residuals + invalid_penalty,
                0.0
            )

            res.extend(data_residuals[valid_downstream].ravel().tolist())

            _, _, _, _, _, _, c_params, t_params = unpack(x)

            for c in c_params:
                res.append((c - 1.0) / 0.08)

            if response_rel_amp is not None:
                model_amp = np.sqrt(np.sum(np.asarray(t_params, dtype=float) ** 2, axis=1))
                model_ref = np.nanmedian(model_amp)
                if np.isfinite(model_ref) and model_ref > 0:
                    model_ref_amp = model_amp / model_ref
                    for meas_rel, model_rel in zip(response_rel_amp, model_ref_amp):
                        if np.isfinite(meas_rel) and np.isfinite(model_rel):
                            res.append((model_rel - meas_rel) / 0.35)
                        else:
                            res.append(1e6)

            beta_log_p0, beta_log_p1, beta_log_p2, alpha_p0, alpha_p1, alpha_p2, _, _ = unpack(x)

            if np.isfinite(model_beta_guess) and model_beta_guess > 1e-6:
                res.append((beta_log_p0 - np.log(model_beta_guess)) / 0.60)
            if np.isfinite(model_alpha_guess):
                res.append((alpha_p0 - model_alpha_guess) / 1.20)

            res.append(beta_log_p1 / 0.12)
            res.append(beta_log_p2 / 0.12)
            res.append(alpha_p1 / 0.15)
            res.append(alpha_p2 / 0.15)

            beta_vals = np.exp(beta_log_p0 + beta_log_p1 * dK1_values + beta_log_p2 * dK1_values ** 2)
            alpha_vals = alpha_p0 + alpha_p1 * dK1_values + alpha_p2 * dK1_values ** 2

            for b in beta_vals:
                if np.isfinite(b):
                    res.append(max(0.2 - b, 0.0) / 0.1)
                    res.append(max(b - 30.0, 0.0) / 5.0)
                else:
                    res.append(1e6)
                    res.append(1e6)

            for a in alpha_vals:
                if np.isfinite(a):
                    res.append(max(abs(a) - 5.0, 0.0) / 0.5)
                else:
                    res.append(1e6)

            return np.asarray(res, dtype=float)

        last_error = None
        best_fit = None
        best_cost = np.inf

        def run(x0):
            nonlocal last_error
            try:
                lower = np.concatenate([
                    np.array([np.log(1e-8), -1.5, -1.5, -8.0, -2.0, -2.0], dtype=float),
                    np.full(nscreens - 1, 0.90, dtype=float),
                    np.tile(np.array([-10.0, 0.05], dtype=float), nscreens - 1),
                ])
                upper = np.concatenate([
                    np.array([np.log(1e4), 1.5, 1.5, 8.0, 2.0, 2.0], dtype=float),
                    np.full(nscreens - 1, 1.10, dtype=float),
                    np.tile(np.array([10.0, 20.0], dtype=float), nscreens - 1),
                ])

                x0 = np.asarray(x0, dtype=float)
                if x0.shape != lower.shape:
                    raise ValueError(f"Initial guess shape {x0.shape} does not match bounds shape {lower.shape}")

                eps = 1e-10
                x0 = np.minimum(np.maximum(x0, lower + eps), upper - eps)

                return least_squares(
                    residuals,
                    x0,
                    method="trf",
                    loss="soft_l1",
                    f_scale=1.0,
                    bounds=(lower, upper),
                    max_nfev=5000,
                )
            except Exception as e:
                last_error = e
                return None

        r = run(x0_canonical)
        if r is not None:
            beta_log_p0, beta_log_p1, beta_log_p2, alpha_p0, alpha_p1, alpha_p2, _, _ = unpack(r.x)
            beta_vals = np.exp(beta_log_p0 + beta_log_p1 * dK1_values + beta_log_p2 * dK1_values ** 2)
            alpha_vals = alpha_p0 + alpha_p1 * dK1_values + alpha_p2 * dK1_values ** 2

            penalty = 0.0
            penalty += 50.0 * np.sum(np.maximum(np.abs(alpha_vals) - 5.0, 0.0))
            penalty += 50.0 * np.sum(np.maximum(0.2 - beta_vals, 0.0))
            score = float(r.cost) + penalty

            if score < best_cost:
                best_cost = score
                best_fit = r

        # random restarts
        for _ in range(self.n_starts - 1):
            c_rand = self.rng.uniform(0.95, 1.05, nscreens - 1)
            t_rand = np.zeros((nscreens - 1, 2), dtype=float)
            t_rand[:, 0] = self.rng.uniform(-3.0, 3.0, nscreens - 1)  # R11
            t_rand[:, 1] = self.rng.uniform(0.2, 8.0, nscreens - 1)  # R12

            x0_rand = np.concatenate([x0_twiss, c_rand, t_rand.ravel()])

            r = run(x0_rand)
            if r is not None:
                beta_log_p0, beta_log_p1, beta_log_p2, alpha_p0, alpha_p1, alpha_p2, _, _ = unpack(r.x)
                beta_vals = np.exp(beta_log_p0 + beta_log_p1 * dK1_values + beta_log_p2 * dK1_values ** 2)
                alpha_vals = alpha_p0 + alpha_p1 * dK1_values + alpha_p2 * dK1_values ** 2

                penalty = 0.0
                penalty += 50.0 * np.sum(np.maximum(np.abs(alpha_vals) - 5.0, 0.0))
                penalty += 50.0 * np.sum(np.maximum(0.2 - beta_vals, 0.0))
                score = float(r.cost) + penalty

                if score < best_cost:
                    best_cost = score
                    best_fit = r

        if best_fit is None:
            if last_error is None:
                raise RuntimeError(f"Transport fit failed for plane {plane}")
            raise RuntimeError(f"Transport fit failed for plane {plane}: {last_error}")
        beta_log_p0, beta_log_p1, beta_log_p2, alpha_p0, alpha_p1, alpha_p2, c_params, t_params = unpack(best_fit.x)

        beta0_vals = np.exp(beta_log_p0 + beta_log_p1 * dK1_values + beta_log_p2 * dK1_values**2)
        alpha0_vals = alpha_p0 + alpha_p1 * dK1_values + alpha_p2 * dK1_values**2

        return {
            "beta_log_p0": float(beta_log_p0),
            "beta_log_p1": float(beta_log_p1),
            "beta_log_p2": float(beta_log_p2),
            "alpha_p0": float(alpha_p0),
            "alpha_p1": float(alpha_p1),
            "transport_params": t_params.tolist(),
            "beta0_vs_K1": beta0_vals.tolist(),
            "alpha0_vs_K1": alpha0_vals.tolist(),
            "cost": float(best_fit.cost),
            "success": bool(best_fit.success),
            "message": str(best_fit.message),
            "plane": plane,
            "alpha_p2": float(alpha_p2),
            "screen_scale_params": c_params.tolist(),
            "response_monitor_names": response_monitor_names,
            "response_rel_amp": None if response_rel_amp is None else response_rel_amp.tolist(),
        }