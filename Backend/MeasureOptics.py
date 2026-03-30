import numpy as np
from scipy.optimize import least_squares


class MeasureOptics:

    def __init__(self, interface, n_starts=5, rng_seed=42): #every time it's the same random set of numbers, pseudorandom
        self.interface = interface
        self.n_starts = int(n_starts) # how many restars with initial values
        self.rng = np.random.default_rng(rng_seed) # exactly for random starting points in _fit_plane

    def get_from_session(self, session):

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

        fit_x = self._fit_plane(K1_values=K1_values, sigma=sigx, sigma_std=sigx_std, K1_nom=K1_nom, plane="x")
        fit_y = self._fit_plane(K1_values=K1_values, sigma=sigy, sigma_std=sigy_std, K1_nom=K1_nom, plane="y")

        return {
            "type": "screen0_twiss_vs_K1",
            "screens": screens,
            "K1_values": K1_values.tolist(),
            "K1_nom": K1_nom,
            "fit_x": fit_x,
            "fit_y": fit_y,
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

        beta0 = np.exp(beta_log_p0 + beta_log_p1 * dK1 + beta_log_p2 * dK1**2)
        alpha0 = alpha_p0 + alpha_p1 * dK1

        return beta0, alpha0

    @staticmethod
    def _get_transport_at_K1(measured_optics, plane, K1_values): # it doesn't use any class state
        fit = measured_optics[f"fit_{plane}"]
        params = np.asarray(fit["transport_params"], dtype=float)

        result = []
        for _ in K1_values:
            Rs = [np.eye(2)]
            for R11, R12 in params:
                Rs.append(np.array([
                    [R11, R12], # it just refactors the params so it can be used easier later in the code
                    [0.0, 1.0]
                ]))
            result.append(Rs)

        return result

    def _fit_plane(self, K1_values, sigma, sigma_std, K1_nom, plane):
        '''
        It takes beam sizes at each plane and adjust model optics that tells is
        how beam sizes at screens change throughout the quadrupole scan.

        So it returns:
        Twiss parameters at the first screen: beta_0 = exp(p0 + p1 dK1 + p2 dK1^2)
                                              alpha_0 = q0 + q1 dK1
        And transport from screen0 to other screens. -> R11, R12

        '''
        nsteps, nscreens = sigma.shape
        dK1_values = K1_values - K1_nom

        sigma2_raw = sigma ** 2 # nsteps x nscreens
        sigma2_ref = np.maximum(sigma2_raw[:, [0]], 1e-30) # takes all raws from columns 0, so sigma**2 at first screen, it's a column, 1e-30 so we don't divide by zero
        sigma2_ratio = sigma2_raw / sigma2_ref
        '''
        sigma_i^2 = emit * (R11**2 * beta0 - 2 * R11 * R12 * alpha0 + R12^2 * gamma0)
        sigma_0^2 = emit * beta0
        So by calculating ratio, we don't need emittance yet.
        When we know the optics, then we infer emitance.
        '''
        sigma_safe = np.maximum(np.abs(sigma), 1e-30) # sigma, but cannot be 0
        ref_safe = np.maximum(np.abs(sigma[:, [0]]), 1e-30)

        rel_err_num = 2.0 * np.abs(sigma_std) / sigma_safe # 2 * dsigma/sigma
        rel_err_den = 2.0 * np.abs(sigma_std[:, [0]]) / ref_safe # for denominator
        ratio_err = sigma2_ratio * np.sqrt(rel_err_num**2 + rel_err_den**2) # error propagation, derr/err = np.sqrt((dA/A)^2 + (dB/B)^2)
        ratio_err[:, 0] = 1e-6 # because usually for the first screen the ratio_err = 1, so giving a small error
        ratio_err[~np.isfinite(ratio_err)] = np.nan

        nom_idx = int(np.argmin(np.abs(dK1_values)))
        sig2_0 = float(sigma2_raw[nom_idx, 0])

        beta_guess = max(sig2_0 / 1e-3, 1e-6) # starting point

        x0_twiss = np.array([
            np.log(beta_guess),
            0.0, # beta_log_p1
            0.0, # beta_log_p2
            0.0, # alpha_p0
            0.0  # alpha_p1
        ], dtype=float) # so, beta0(dK1) = const
                        #     alpha0(dK1) = 0

        t0 = np.zeros((nscreens - 1, 2), dtype=float)
        t0[:, 0] = 1.0   # R11
        t0[:, 1] = 1.0   # R12

        x0_canonical = np.concatenate([x0_twiss, t0.ravel()]) # optimizer wants a vector with numbers, that's why

        def unpack(x):
            beta_log_p0 = float(x[0])
            beta_log_p1 = float(x[1])
            beta_log_p2 = float(x[2])
            alpha_p0 = float(x[3])
            alpha_p1 = float(x[4])
            t_params = x[5:].reshape(nscreens - 1, 2)
            return beta_log_p0, beta_log_p1, beta_log_p2, alpha_p0, alpha_p1, t_params

        def predict(x):
            '''
            If parameters are x, what ratio sigma_i^2 / sigma_0^2 model assumes.
            '''
            beta_log_p0, beta_log_p1, beta_log_p2, alpha_p0, alpha_p1, t_params = unpack(x)

            pred = np.full((nsteps, nscreens), np.nan)

            for k, dK1 in enumerate(dK1_values):
                beta0 = np.exp(beta_log_p0 + beta_log_p1 * dK1 + beta_log_p2 * dK1**2) # beta0 > 0
                beta0 = max(beta0, 1e-12)
                alpha0 = alpha_p0 + alpha_p1 * dK1
                gamma0 = (1.0 + alpha0**2) / beta0

                pred[k, 0] = 1.0

                for i, (R11, R12) in enumerate(t_params):
                    numer = (R11**2 * beta0 - 2.0 * R11 * R12 * alpha0 + R12**2 * gamma0)
                    pred[k, i + 1] = numer / beta0 # ratio

            return pred

        def residuals(x):
            pred = predict(x)
            res = []

            for k in range(nsteps):
                for i in range(nscreens):
                    y = sigma2_ratio[k, i] # from data
                    y_p = pred[k, i] # model assumptions
                    err = ratio_err[k, i]

                    if np.isfinite(y) and np.isfinite(y_p):
                        if np.isfinite(err) and err > 0:
                            res.append((y_p - y) / err)
                        else:
                            res.append(y_p - y)

            return np.asarray(res)

        best_fit = None # among all starts
        best_cost = np.inf

        def run(x0): # (model - data) / error
            try: # what best adjusts model to data
                return least_squares(residuals, x0, method="trf", max_nfev=5000) # trf is not doing big steps, max_nfev is max evaluations of residuals function
            except Exception:
                return None

        r = run(x0_canonical)
        if r is not None and r.cost < best_cost:
            best_cost = r.cost
            best_fit = r

        # random restarts
        for _ in range(self.n_starts - 1):
            t_rand = np.zeros((nscreens - 1, 2), dtype=float)
            t_rand[:, 0] = self.rng.uniform(-2.0, 2.0, nscreens - 1)   # R11, in given range, random is uniform
            t_rand[:, 1] = self.rng.uniform(0.01, 10.0, nscreens - 1)  # R12

            x0_rand = np.concatenate([x0_twiss, t_rand.ravel()])

            r = run(x0_rand)
            if r is not None and r.cost < best_cost:
                best_cost = r.cost
                best_fit = r

        if best_fit is None:
            raise RuntimeError(f"Transport fit failed for plane {plane}")

        beta_log_p0, beta_log_p1, beta_log_p2, alpha_p0, alpha_p1, t_params = unpack(best_fit.x)

        beta0_vals = np.exp(beta_log_p0 + beta_log_p1 * dK1_values + beta_log_p2 * dK1_values**2)
        alpha0_vals = alpha_p0 + alpha_p1 * dK1_values

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
        }