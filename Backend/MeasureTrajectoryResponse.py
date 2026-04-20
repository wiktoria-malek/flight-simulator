import numpy as np
from scipy.optimize import least_squares

class MeasureTrajectoryResponse:
    def __init__(self, interface):
        self.interface = interface

    @staticmethod
    def _safe_anchor_ratio(response_matrix, anchor_row=0):
        arr = np.asarray(response_matrix, dtype=float)
        if arr.ndim != 2:
            raise ValueError("Response matrix must have 2 dimensions")
        if arr.shape[0] == 0:
            return np.zeros((0, arr.shape[1]), dtype=float)

        base = arr[[anchor_row], :]
        with np.errstate(divide="ignore", invalid="ignore"):
            rel = arr / base
        rel[~np.isfinite(rel)] = np.nan
        return rel

    @staticmethod
    def _screen_response_scale(raw_response_cube, anchor_screen=0):
        cube = np.asarray(raw_response_cube, dtype=float)
        if cube.ndim != 3:
            raise ValueError("raw_response_cube must have shape (nK1, nscreen, ncorrector)")
        if cube.shape[1] == 0:
            return np.zeros((cube.shape[0], 0), dtype=float)

        amp = np.nanmedian(np.abs(cube), axis=2)
        anchor = amp[:, [anchor_screen]]
        with np.errstate(divide="ignore", invalid="ignore"):
            scale = amp / anchor
        scale[~np.isfinite(scale)] = np.nan
        scale[:, 0] = 1.0
        return scale
    @staticmethod
    def _response_amplitude_by_monitor(response_matrix):
        arr = np.asarray(response_matrix, dtype=float)
        if arr.ndim != 2:
            raise ValueError("response_matrix must have 2 dimensions")
        if arr.shape[0] == 0:
            return np.zeros(0, dtype=float)

        with np.errstate(invalid="ignore"):
            amp = np.sqrt(np.nanmean(arr ** 2, axis=1))
        amp[~np.isfinite(amp)] = np.nan
        return amp

    @staticmethod
    def _interp_monitor_quantity_to_s(source_S, source_values, target_S):
        source_S = np.asarray(source_S, dtype=float)
        source_values = np.asarray(source_values, dtype=float)
        target_S = np.asarray(target_S, dtype=float)

        mask = np.isfinite(source_S) & np.isfinite(source_values)
        if np.count_nonzero(mask) == 0:
            return np.full(target_S.shape, np.nan, dtype=float)
        if np.count_nonzero(mask) == 1:
            return np.full(target_S.shape, float(source_values[mask][0]), dtype=float)

        xs = source_S[mask]
        ys = source_values[mask]
        order = np.argsort(xs)
        xs = xs[order]
        ys = ys[order]
        return np.interp(target_S, xs, ys)
    def _get_model_optics_for_names(self, names, plane):
        if not hasattr(self.interface, "_get_optics_from_twiss_file"):
            raise RuntimeError("Interface does not provide twiss-file optics")

        optics = self.interface._get_optics_from_twiss_file()
        all_names = list(optics.get("names", []))
        beta_key = "betx" if plane == "x" else "bety"
        alpha_key = "alfx" if plane == "x" else "alfy"
        mu_key = "mux" if plane == "x" else "muy"

        beta_arr = np.asarray(optics.get(beta_key, []), dtype=float)
        alpha_arr = np.asarray(optics.get(alpha_key, []), dtype=float)
        mu_arr = np.asarray(optics.get(mu_key, []), dtype=float)
        s_arr = np.asarray(optics.get("S", []), dtype=float)

        beta = []
        alpha = []
        mu = []
        S = []
        for name in names:
            if name not in all_names:
                raise ValueError(f"Element {name} not found in twiss file")
            i = all_names.index(name)
            beta.append(float(beta_arr[i]))
            alpha.append(float(alpha_arr[i]))
            mu.append(float(mu_arr[i]))
            S.append(float(s_arr[i]))

        return {
            "names": list(names),
            "S": np.asarray(S, dtype=float),
            "beta": np.asarray(beta, dtype=float),
            "alpha": np.asarray(alpha, dtype=float),
            "mu": np.asarray(mu, dtype=float),
        }

    @staticmethod
    def _estimate_alpha_from_beta(S, beta):
        S = np.asarray(S, dtype=float)
        beta = np.asarray(beta, dtype=float)
        alpha = np.full(beta.shape, np.nan, dtype=float)

        mask = np.isfinite(S) & np.isfinite(beta)
        if np.count_nonzero(mask) < 3:
            return alpha

        xs = S[mask]
        ys = beta[mask]
        order = np.argsort(xs)
        xs = xs[order]
        ys = ys[order]

        d_beta_ds = np.gradient(ys, xs)
        alpha_fit = -0.5 * d_beta_ds

        alpha_idx = np.where(mask)[0][order]
        alpha[alpha_idx] = alpha_fit
        return alpha

    def _fit_plane_measured_transport(self, session, traj, plane):
        screen_names = list(traj.get("screen_names", []))
        bpm_names = list(traj.get("bpm_names", []))
        corrector_names = list(traj.get("correctors", []))
        base_K1_values = np.asarray(traj.get("base_K1_values", []), dtype=float)
        raw_screen = np.asarray(traj.get("raw_Rxx" if plane == "x" else "raw_Ryy", []), dtype=float)
        raw_bpm = np.asarray(traj.get("raw_bpm_Rxx" if plane == "x" else "raw_bpm_Ryy", []), dtype=float)

        if len(screen_names) < 2:
            raise ValueError("At least two screens are required")
        if raw_screen.ndim != 3:
            raise ValueError("raw screen response cube must have shape (nK1, nscreen, ncorrector)")
        if raw_bpm.ndim != 3:
            raise ValueError("raw bpm response cube must have shape (nK1, nbpm, ncorrector)")
        if base_K1_values.size == 0:
            raise ValueError("No base K1 values available")
        if not corrector_names:
            raise ValueError("No correctors available for measured transport fit")

        deltas = np.asarray(session.get("deltas", []), dtype=float)
        scan_K1_values = np.asarray(session.get("K1_values", []), dtype=float)

        if scan_K1_values.size and deltas.size == scan_K1_values.size:
            nom_scan_idx = int(np.argmin(np.abs(deltas)))
            nominal_target = float(scan_K1_values[nom_scan_idx])
            nom_base_idx = int(np.argmin(np.abs(base_K1_values - nominal_target)))
            K1_nom = nominal_target
        else:
            nom_base_idx = int(len(base_K1_values) // 2)
            K1_nom = float(base_K1_values[nom_base_idx])

        model_monitors = self._get_model_optics_for_names(bpm_names + screen_names, plane)
        model_correctors = self._get_model_optics_for_names(corrector_names, plane)

        mon_names = list(model_monitors["names"])
        mon_S = np.asarray(model_monitors["S"], dtype=float)
        mon_beta_model = np.asarray(model_monitors["beta"], dtype=float)
        mon_mu_model = np.asarray(model_monitors["mu"], dtype=float)

        corr_mu_model = np.asarray(model_correctors["mu"], dtype=float)

        R_nom = np.vstack([
            np.asarray(raw_bpm[nom_base_idx], dtype=float),
            np.asarray(raw_screen[nom_base_idx], dtype=float),
        ])

        if R_nom.shape[0] != len(mon_names):
            raise ValueError("Combined response row count does not match monitor list")
        if R_nom.shape[1] != len(corrector_names):
            raise ValueError("Combined response column count does not match corrector list")

        sort_idx = np.argsort(mon_S)
        mon_names = [mon_names[i] for i in sort_idx]
        mon_S = mon_S[sort_idx]
        mon_beta_model = mon_beta_model[sort_idx]
        mon_mu_model = mon_mu_model[sort_idx]
        R_nom = R_nom[sort_idx, :]

        valid_monitor = np.isfinite(mon_S) & np.isfinite(mon_beta_model) & np.isfinite(mon_mu_model)
        if np.count_nonzero(valid_monitor) < 4:
            raise ValueError("Not enough valid monitor optics for measured transport fit")

        mon_names_fit = [n for i, n in enumerate(mon_names) if valid_monitor[i]]
        mon_S_fit = mon_S[valid_monitor]
        mon_beta_model_fit = mon_beta_model[valid_monitor]
        mon_mu_model_fit = mon_mu_model[valid_monitor]
        R_fit = R_nom[valid_monitor, :]

        valid_corr = np.isfinite(corr_mu_model)
        if np.count_nonzero(valid_corr) < 2:
            raise ValueError("Not enough valid corrector optics for measured transport fit")

        corr_names_fit = [n for i, n in enumerate(corrector_names) if valid_corr[i]]
        corr_mu_model_fit = corr_mu_model[valid_corr]
        R_fit = R_fit[:, valid_corr]

        nmon = len(mon_names_fit)
        ncorr = len(corr_names_fit)

        log_beta_model = np.log(np.maximum(mon_beta_model_fit, 1e-12))
        mu_model = np.asarray(mon_mu_model_fit, dtype=float)
        corr_phase_model = np.asarray(corr_mu_model_fit, dtype=float)

        amp0 = np.ones(ncorr, dtype=float)
        for ic in range(ncorr):
            basis = np.sqrt(np.maximum(mon_beta_model_fit, 1e-12)) * np.sin(
                2.0 * np.pi * (mu_model - corr_phase_model[ic])
            )
            denom = np.dot(basis, basis)
            if np.isfinite(denom) and denom > 1e-12:
                amp0[ic] = float(np.dot(R_fit[:, ic], basis) / denom)
            else:
                amp0[ic] = 1.0

        amp0 = np.where(np.abs(amp0) < 1e-6, 1.0, amp0)

        x0 = np.concatenate([
            np.zeros(nmon, dtype=float),  # dlogbeta monitors
            np.zeros(nmon, dtype=float),  # dmu monitors
            np.log(np.abs(amp0)),         # corrector amplitudes
            np.zeros(ncorr, dtype=float), # corrector phase offsets
        ])

        def unpack(x):
            dlogb = x[:nmon]
            dmu = x[nmon:2 * nmon]
            log_amp = x[2 * nmon:2 * nmon + ncorr]
            dphi = x[2 * nmon + ncorr:2 * nmon + 2 * ncorr]

            beta = np.exp(log_beta_model + dlogb)
            mu = mu_model + dmu
            amp = np.exp(log_amp)
            phi = corr_phase_model + dphi
            return beta, mu, amp, phi, dlogb, dmu, log_amp, dphi

        def predict(x):
            beta, mu, amp, phi, *_ = unpack(x)
            pred = np.zeros((nmon, ncorr), dtype=float)
            root_beta = np.sqrt(np.maximum(beta, 1e-12))
            for ic in range(ncorr):
                pred[:, ic] = amp[ic] * root_beta * np.sin(2.0 * np.pi * (mu - phi[ic]))
            return pred

        data_scale = np.nanmedian(np.abs(R_fit))
        if not np.isfinite(data_scale) or data_scale <= 0:
            data_scale = 1.0

        def residuals(x):
            beta, mu, amp, phi, dlogb, dmu, log_amp, dphi = unpack(x)
            pred = predict(x)
            res = []

            valid = np.isfinite(R_fit)
            data_res = np.zeros_like(pred)
            data_res[valid] = (pred[valid] - R_fit[valid]) / data_scale
            res.extend(data_res[valid].ravel().tolist())


            res.extend((dlogb / 0.35).tolist())
            res.extend((dmu / 0.03).tolist())
            res.extend((dphi / 0.05).tolist())
            res.extend((log_amp / 2.0).tolist())


            if nmon >= 3:
                res.extend((np.diff(dlogb, n=2) / 0.10).tolist())
                res.extend((np.diff(dmu, n=2) / 0.01).tolist())


            dmu_abs = np.diff(mu)
            for v in dmu_abs:
                res.append(max(0.002 - v, 0.0) / 0.001)


            for b in beta:
                res.append(max(1e-3 - b, 0.0) / 1e-3)
                res.append(max(b - 1e3, 0.0) / 50.0)

            return np.asarray(res, dtype=float)

        lower = np.concatenate([
            np.full(nmon, -1.5, dtype=float),
            np.full(nmon, -0.20, dtype=float),
            np.full(ncorr, -20.0, dtype=float),
            np.full(ncorr, -0.20, dtype=float),
        ])
        upper = np.concatenate([
            np.full(nmon, 1.5, dtype=float),
            np.full(nmon, 0.20, dtype=float),
            np.full(ncorr, 20.0, dtype=float),
            np.full(ncorr, 0.20, dtype=float),
        ])

        fit = least_squares(
            residuals,
            x0,
            method="trf",
            loss="soft_l1",
            f_scale=1.0,
            bounds=(lower, upper),
            max_nfev=10000,
        )

        beta_fit, mu_fit, amp_fit, phi_fit, *_ = unpack(fit.x)
        alpha_fit = self._estimate_alpha_from_beta(mon_S_fit, beta_fit)

        screen_mask = np.array([name in screen_names for name in mon_names_fit], dtype=bool)
        screen_names_fit = [name for name, keep in zip(mon_names_fit, screen_mask) if keep]
        screen_S_fit = mon_S_fit[screen_mask]
        beta_screen_fit = beta_fit[screen_mask]
        alpha_screen_fit = alpha_fit[screen_mask]
        mu_screen_fit = mu_fit[screen_mask]

        if len(screen_names_fit) != len(screen_names):
            raise ValueError("Not all selected screens are available in fitted monitor optics")

        order_screen = [screen_names_fit.index(name) for name in screen_names]
        screen_S_fit = screen_S_fit[order_screen]
        beta_screen_fit = beta_screen_fit[order_screen]
        alpha_screen_fit = alpha_screen_fit[order_screen]
        mu_screen_fit = mu_screen_fit[order_screen]

        beta0 = float(max(beta_screen_fit[0], 1e-12))
        alpha0 = float(np.nan_to_num(alpha_screen_fit[0], nan=0.0))
        mu0 = float(mu_screen_fit[0])

        transport_params = []
        for i in range(1, len(screen_names)):
            betai = float(max(beta_screen_fit[i], 1e-12))
            mui = float(mu_screen_fit[i])
            dmu = 2.0 * np.pi * (mui - mu0)

            R11 = np.sqrt(betai / beta0) * (np.cos(dmu) + alpha0 * np.sin(dmu))
            R12 = np.sqrt(betai * beta0) * np.sin(dmu)
            transport_params.append([R11, R12])

        return {
            "screen_names": screen_names,
            "screen_S": screen_S_fit.tolist(),
            "beta_screen": beta_screen_fit.tolist(),
            "alpha_screen": alpha_screen_fit.tolist(),
            "mu_screen": mu_screen_fit.tolist(),
            "transport_params": np.asarray(transport_params, dtype=float).tolist(),
            "monitor_names": mon_names_fit,
            "monitor_S": mon_S_fit.tolist(),
            "beta_monitor": beta_fit.tolist(),
            "alpha_monitor": alpha_fit.tolist(),
            "mu_monitor": mu_fit.tolist(),
            "corrector_names": corr_names_fit,
            "corrector_phase": phi_fit.tolist(),
            "corrector_amplitude": amp_fit.tolist(),
            "nominal_base_index": int(nom_base_idx),
            "K1_nom": float(K1_nom),
            "fit_cost": float(fit.cost),
            "fit_success": bool(fit.success),
            "fit_message": str(fit.message),
        }

    def _get_model_screen_optics(self, screen_names, plane):
        if not hasattr(self.interface, "_get_optics_from_twiss_file"):
            raise RuntimeError("Interface does not provide twiss-file optics")

        optics = self.interface._get_optics_from_twiss_file()
        names = list(optics.get("names", []))
        beta_key = "betx" if plane == "x" else "bety"
        alpha_key = "alfx" if plane == "x" else "alfy"
        mu_key = "mux" if plane == "x" else "muy"

        beta = []
        alpha = []
        mu = []
        S = []

        for screen in screen_names:
            if screen not in names:
                raise ValueError(f"Screen {screen} not found in twiss file")
            i = names.index(screen)
            beta.append(float(np.asarray(optics[beta_key], dtype=float)[i]))
            alpha.append(float(np.asarray(optics[alpha_key], dtype=float)[i]))
            mu.append(float(np.asarray(optics[mu_key], dtype=float)[i]))
            S.append(float(np.asarray(optics["S"], dtype=float)[i]))

        return {
            "screen_names": list(screen_names),
            "S": S,
            "beta": beta,
            "alpha": alpha,
            "mu": mu,
        }

    def _get_model_transport_params(self, screen_names, plane):
        model = self._get_model_screen_optics(screen_names, plane)
        beta = np.asarray(model["beta"], dtype=float)
        alpha = np.asarray(model["alpha"], dtype=float)
        mu = np.asarray(model["mu"], dtype=float)

        beta0 = float(beta[0])
        alpha0 = float(alpha[0])
        mu0 = float(mu[0])

        params = []
        for i in range(1, len(screen_names)):
            betai = float(beta[i])
            mui = float(mu[i])
            dmu = 2.0 * np.pi * (mui - mu0)
            R11 = np.sqrt(max(betai, 1e-12) / max(beta0, 1e-12)) * (np.cos(dmu) + alpha0 * np.sin(dmu))
            R12 = np.sqrt(max(betai, 1e-12) * max(beta0, 1e-12)) * np.sin(dmu)
            params.append([R11, R12])
        return np.asarray(params, dtype=float)

    def get_from_session(self, session):
        scans = session.get("screen_response_scans")
        if not scans:
            raise ValueError("No scans")

        screen_names = list(scans.get("screen_names", []))
        K1_values = np.asarray(scans.get("K1_values", []), dtype=float)
        K1_indices = list(scans.get("K1_indices", []))
        responses = list(scans.get("responses", []))
        scan_K1_values = np.asarray(session.get("K1_values", []), dtype=float)

        if len(screen_names) < 2:
            raise ValueError("At least two screens are required in screen_response_scans")
        if len(K1_values) != len(responses):
            raise ValueError("screen_response_scans has inconsistent K1_values/responses lengths")
        if len(K1_values) == 0:
            raise ValueError("screen_response_scans is empty")

        correctors = None
        bpm_names = None
        bpm_S = None
        raw_Rxx = []
        raw_Ryy = []
        raw_bpm_Rxx = []
        raw_bpm_Ryy = []
        rel_Rxx = []
        rel_Ryy = []
        mean_rel_x = []
        mean_rel_y = []

        for resp in responses:
            resp_screens = list(resp.get("screens", []))
            if resp_screens != screen_names:
                raise ValueError("Inconsistent screen ordering in screen_response_scans")

            resp_correctors = list(resp.get("correctors", []))
            if correctors is None:
                correctors = resp_correctors
            elif resp_correctors != correctors:
                raise ValueError("Inconsistent corrector ordering in screen_response_scans")

            Rxx = np.asarray(resp.get("Rxx", []), dtype=float)
            Ryy = np.asarray(resp.get("Ryy", []), dtype=float)

            if Rxx.ndim != 2 or Ryy.ndim != 2:
                raise ValueError("Response matrices must be 2D")
            if Rxx.shape != Ryy.shape:
                raise ValueError("Rxx and Ryy must have the same shape")
            if Rxx.shape[0] != len(screen_names):
                raise ValueError("Response matrix row count does not match number of screens")

            raw_Rxx.append(Rxx)
            raw_Ryy.append(Ryy)

            resp_bpm_names = list(resp.get("bpm_names", []))
            resp_bpm_S = list(resp.get("bpm_S", []))
            bpm_Rxx_data = resp.get("bpm_Rxx")
            bpm_Ryy_data = resp.get("bpm_Ryy")

            if bpm_Rxx_data is None and bpm_Ryy_data is None:
                bpm_Rxx = np.empty((0, Rxx.shape[1]), dtype=float)
                bpm_Ryy = np.empty((0, Ryy.shape[1]), dtype=float)
                resp_bpm_names = []
                resp_bpm_S = []
            else:
                bpm_Rxx = np.asarray(bpm_Rxx_data, dtype=float)
                bpm_Ryy = np.asarray(bpm_Ryy_data, dtype=float)

                if bpm_Rxx.ndim != 2 or bpm_Ryy.ndim != 2:
                    raise ValueError("BPM response matrices must be 2D")
                if bpm_Rxx.shape != bpm_Ryy.shape:
                    raise ValueError("BPM Rxx and Ryy must have the same shape")
                if bpm_Rxx.shape[1] != Rxx.shape[1]:
                    raise ValueError("BPM response matrix corrector dimension does not match screen response")
                if resp_bpm_names and bpm_Rxx.shape[0] != len(resp_bpm_names):
                    raise ValueError("BPM response row count does not match bpm_names")
                if not resp_bpm_names and bpm_Rxx.shape[0]:
                    resp_bpm_names = [f"BPM_{i}" for i in range(bpm_Rxx.shape[0])]
                if len(resp_bpm_S) != len(resp_bpm_names):
                    resp_bpm_S = [np.nan] * len(resp_bpm_names)

            if bpm_names is None:
                bpm_names = resp_bpm_names
                bpm_S = resp_bpm_S
            elif resp_bpm_names != bpm_names:
                raise ValueError("Inconsistent BPM ordering in screen_response_scans")

            raw_bpm_Rxx.append(bpm_Rxx)
            raw_bpm_Ryy.append(bpm_Ryy)

            rel_x = self._safe_anchor_ratio(Rxx, anchor_row=0)
            rel_y = self._safe_anchor_ratio(Ryy, anchor_row=0)
            rel_Rxx.append(rel_x)
            rel_Ryy.append(rel_y)

            mean_rel_x.append(np.nanmean(rel_x, axis=1))
            mean_rel_y.append(np.nanmean(rel_y, axis=1))

        raw_Rxx = np.asarray(raw_Rxx, dtype=float)
        raw_Ryy = np.asarray(raw_Ryy, dtype=float)
        raw_bpm_Rxx = np.asarray(raw_bpm_Rxx, dtype=float)
        raw_bpm_Ryy = np.asarray(raw_bpm_Ryy, dtype=float)
        rel_Rxx = np.asarray(rel_Rxx, dtype=float)
        rel_Ryy = np.asarray(rel_Ryy, dtype=float)
        mean_rel_x = np.asarray(mean_rel_x, dtype=float)
        mean_rel_y = np.asarray(mean_rel_y, dtype=float)

        interp_mean_rel_x = np.full((len(scan_K1_values), len(screen_names)), np.nan, dtype=float)
        interp_mean_rel_y = np.full((len(scan_K1_values), len(screen_names)), np.nan, dtype=float)

        if scan_K1_values.size:
            for j in range(len(screen_names)):
                x_base = mean_rel_x[:, j]
                y_base = mean_rel_y[:, j]

                mask_x = np.isfinite(K1_values) & np.isfinite(x_base)
                mask_y = np.isfinite(K1_values) & np.isfinite(y_base)

                if np.count_nonzero(mask_x) >= 2:
                    order = np.argsort(K1_values[mask_x])
                    interp_mean_rel_x[:, j] = np.interp(
                        scan_K1_values,
                        K1_values[mask_x][order],
                        x_base[mask_x][order],
                    )
                elif np.count_nonzero(mask_x) == 1:
                    interp_mean_rel_x[:, j] = float(x_base[mask_x][0])

                if np.count_nonzero(mask_y) >= 2:
                    order = np.argsort(K1_values[mask_y])
                    interp_mean_rel_y[:, j] = np.interp(
                        scan_K1_values,
                        K1_values[mask_y][order],
                        y_base[mask_y][order],
                    )
                elif np.count_nonzero(mask_y) == 1:
                    interp_mean_rel_y[:, j] = float(y_base[mask_y][0])

        scale_x = self._screen_response_scale(raw_Rxx, anchor_screen=0)
        scale_y = self._screen_response_scale(raw_Ryy, anchor_screen=0)

        return {
            "type": "trajectory_response_scan",
            "quad_name": session.get("quad_name"),
            "screen_names": screen_names,
            "correctors": [] if correctors is None else correctors,
            "bpm_names": [] if bpm_names is None else bpm_names,
            "bpm_S": [] if bpm_S is None else bpm_S,
            "K1_indices": K1_indices,
            "base_K1_values": K1_values.tolist(),
            "scan_K1_values": scan_K1_values.tolist(),
            "raw_Rxx": raw_Rxx.tolist(),
            "raw_Ryy": raw_Ryy.tolist(),
            "raw_bpm_Rxx": raw_bpm_Rxx.tolist(),
            "raw_bpm_Ryy": raw_bpm_Ryy.tolist(),
            "screen_scale_x": scale_x.tolist(),
            "screen_scale_y": scale_y.tolist(),
            "rel_Rxx": rel_Rxx.tolist(),
            "rel_Ryy": rel_Ryy.tolist(),
            "mean_rel_x": mean_rel_x.tolist(),
            "mean_rel_y": mean_rel_y.tolist(),
            "interp_mean_rel_x": interp_mean_rel_x.tolist(),
            "interp_mean_rel_y": interp_mean_rel_y.tolist(),
        }

    def fit_measured_transport_from_session(self, session):

        '''
        R_11 = np.sqrt(beta_i/beta0)(cos delta(mu) + alpha0 sin (delta(mu))
        R_12 = np.sqrt(beta_i * beta_0) sin (delta(mu))
        '''
        traj = session.get("measured_transport")
        if not isinstance(traj, dict) or traj.get("type") != "trajectory_response_scan":
            traj = self.get_from_session(session)

        fit_x = self._fit_plane_measured_transport(session, traj, "x")
        fit_y = self._fit_plane_measured_transport(session, traj, "y")

        return {
            "type": "measured_fitted_transport",
            "mode": "monitor_response_optics_fit",
            "quad_name": traj.get("quad_name"),
            "screen_names": fit_x["screen_names"],
            "screen_S": fit_x["screen_S"],
            "K1_nom": fit_x["K1_nom"],
            "transport_params_x": fit_x["transport_params"],
            "transport_params_y": fit_y["transport_params"],
            "beta_screen_x": fit_x["beta_screen"],
            "beta_screen_y": fit_y["beta_screen"],
            "alpha_screen_x": fit_x["alpha_screen"],
            "alpha_screen_y": fit_y["alpha_screen"],
            "mu_screen_x": fit_x["mu_screen"],
            "mu_screen_y": fit_y["mu_screen"],
            "monitor_names_x": fit_x["monitor_names"],
            "monitor_names_y": fit_y["monitor_names"],
            "monitor_S_x": fit_x["monitor_S"],
            "monitor_S_y": fit_y["monitor_S"],
            "beta_monitor_x": fit_x["beta_monitor"],
            "beta_monitor_y": fit_y["beta_monitor"],
            "alpha_monitor_x": fit_x["alpha_monitor"],
            "alpha_monitor_y": fit_y["alpha_monitor"],
            "mu_monitor_x": fit_x["mu_monitor"],
            "mu_monitor_y": fit_y["mu_monitor"],
            "corrector_names_x": fit_x["corrector_names"],
            "corrector_names_y": fit_y["corrector_names"],
            "corrector_phase_x": fit_x["corrector_phase"],
            "corrector_phase_y": fit_y["corrector_phase"],
            "corrector_amplitude_x": fit_x["corrector_amplitude"],
            "corrector_amplitude_y": fit_y["corrector_amplitude"],
            "fit_cost_x": fit_x["fit_cost"],
            "fit_cost_y": fit_y["fit_cost"],
            "fit_success_x": fit_x["fit_success"],
            "fit_success_y": fit_y["fit_success"],
            "fit_message_x": fit_x["fit_message"],
            "fit_message_y": fit_y["fit_message"],
        }
