import numpy as np

class CorrectionEngine:

    def __init__(self, interface):
        self.interface = interface
        self._has_real_scatter = False
        self._offenergy_flag = False
        self._highint_flag = False
        self._init_virtual_errors(0.100)
        self.accumulated = {}

    def _init_virtual_errors(self, sigma_mm: float):
        try:
            if hasattr(self.interface, "scatter_elements"):
                self.interface.scatter_elements("quadrupole", sigma_mm, sigma_mm, 0, 0, 0, 0, "center")
                self.interface.scatter_elements("bpm", sigma_mm, sigma_mm, 0, 0, 0, 0, "center")
                self._has_real_scatter = True
                self._bpm_bias_x = self._bpm_bias_y = None
                self._disp_y_vec = self._wake_y_vec = None
                return
        except Exception:
            pass

        bpms = self.interface.get_bpms()["names"]
        n = len(bpms)
        rng = np.random.default_rng()
        self._bpm_bias_x = rng.normal(0.0, sigma_mm, size=n)
        self._bpm_bias_y = rng.normal(0.0, sigma_mm, size=n)
        self._disp_y_vec = None
        self._wake_y_vec = None

    def set_offenergy_flag(self, on: bool): self._offenergy_flag = bool(on)
    def set_highintensity_flag(self, on: bool): self._highint_flag = bool(on)

    def _measure_orbit_xy(self, bpms_names, apply_synthetic=True):
        data = self.interface.get_bpms()
        idx = {n: i for i, n in enumerate(data["names"])}

        x_all = np.mean(np.asarray(data["x"]), axis=0)
        y_all = np.mean(np.asarray(data["y"]), axis=0)

        if apply_synthetic and not self._has_real_scatter:
            if self._bpm_bias_x is not None: x_all = x_all + self._bpm_bias_x
            if self._bpm_bias_y is not None: y_all = y_all + self._bpm_bias_y

            if self._offenergy_flag and self._disp_y_vec is not None:
                n = len(data["names"])
                y_all = y_all + 0.01 * self._disp_y_vec[n:]

            if self._highint_flag and self._wake_y_vec is not None:
                n = len(data["names"])
                y_all = y_all + self._wake_y_vec[n:]

        sel = np.array([idx[n] for n in bpms_names], dtype=int)
        return x_all[sel], y_all[sel]

    def _y_nom(self, bpms):
        x, y = self._measure_orbit_xy(bpms, apply_synthetic=True)
        return np.concatenate([x, y], axis=0)

    def compute_response_matrix(self, corrs, bpms, delta=0.01, triangular=False, progress_cb=None):
        nb, nc = len(bpms), len(corrs)
        Rx = np.zeros((nb, nc), float)
        Ry = np.zeros((nb, nc), float)

        orig = self._has_real_scatter
        if not orig:
            self._has_real_scatter = True

        for j, c in enumerate(corrs):
            if progress_cb and not progress_cb(j, len(corrs), f"Exciting {c} (+/-{delta:g})"):
                break

            self.interface.vary_correctors([c], [delta])
            xp, yp = self._measure_orbit_xy(bpms, apply_synthetic=False) #plus

            self.interface.vary_correctors([c], [-2*delta])
            xm, ym = self._measure_orbit_xy(bpms, apply_synthetic=False) #minus

            self.interface.vary_correctors([c], [delta])

            Rx[:, j] = (xp - xm) / (2.0 * delta)
            Ry[:, j] = (yp - ym) / (2.0 * delta)

        self._has_real_scatter = orig

        if triangular: #zeroes everything above the diagonal, corr j only affects bpm j
            Rx = np.tril(Rx)
            Ry = np.tril(Ry)

        return {"bpms": bpms, "correctors": corrs, "delta": float(delta), "Rx": Rx, "Ry": Ry}

    def solve_and_apply(self, orbit_w, disp_w, wake_w, rcond, max_iters, bpms, corrs, triangular=False,R_nom=None, R_disp=None, R_wake=None,iter_cb=None):
        if R_nom is None:
            rm = self.compute_response_matrix(corrs, bpms, delta=0.01, triangular=triangular)
            R_nom = np.vstack([rm["Rx"], rm["Ry"]])
        else:
            R_nom = np.array(R_nom, float)

        if disp_w > 0 and R_disp is None:
            rm0 = self.compute_response_matrix(corrs, bpms, delta=0.01, triangular=triangular)
            self.set_offenergy_flag(True)
            self.interface.change_energy()
            rm1 = self.compute_response_matrix(corrs, bpms, delta=0.01, triangular=triangular)
            self.interface.reset_energy()
            self.set_offenergy_flag(False)
            R_disp = np.vstack([rm1["Rx"], rm1["Ry"]]) - np.vstack([rm0["Rx"], rm0["Ry"]])

        if wake_w > 0 and R_wake is None:
            self.set_highintensity_flag(False)
            self.interface.reset_intensity()
            rL = self.compute_response_matrix(corrs, bpms, delta=0.01, triangular=triangular)
            self.set_highintensity_flag(True)
            self.interface.change_intensity()
            rH = self.compute_response_matrix(corrs, bpms, delta=0.01, triangular=triangular)
            self.interface.reset_intensity()
            self.set_highintensity_flag(False)
            R_wake = np.vstack([rH["Rx"], rH["Ry"]]) - np.vstack([rL["Rx"], rL["Ry"]])

        self.accumulated = {c: 0.0 for c in corrs}
        hist_orbit = []

        for it in range(int(max_iters)):
            y_nom = self._y_nom(bpms)

            A_terms = [orbit_w * R_nom]
            B_terms = [orbit_w * y_nom]

            if disp_w > 0 and R_disp is not None:
                self.set_offenergy_flag(True)
                self.interface.change_energy()
                y_off = self._y_nom(bpms)
                self.interface.reset_energy()
                self.set_offenergy_flag(False)
                disp_vec = y_off - y_nom
                A_terms.append(disp_w * R_disp)
                B_terms.append(disp_w * disp_vec)

            if wake_w > 0 and R_wake is not None:
                self.set_highintensity_flag(False)
                self.interface.reset_intensity()
                y_low = self._y_nom(bpms)
                self.set_highintensity_flag(True)
                self.interface.change_intensity()
                y_high = self._y_nom(bpms)
                self.interface.reset_intensity()
                self.set_highintensity_flag(False)
                wake_vec = y_high - y_low
                A_terms.append(wake_w * R_wake)
                B_terms.append(wake_w * wake_vec)

            A = np.vstack(A_terms)
            B = np.concatenate(B_terms, axis=0)

            dtheta, *_ = np.linalg.lstsq(A, -B, rcond=float(rcond)) #least squares method
                    #residuals,rank,singular values of A

            def orbit_norm(): #how big the orbit error is
                return float(np.linalg.norm(self._y_nom(bpms))) #root sum of squares
            base = orbit_norm() #orbit error before correction
            alpha = 4.0
            while alpha > 1e-3:
                self.interface.vary_correctors(corrs, (alpha * dtheta).tolist())
                new = orbit_norm()
                self.interface.vary_correctors(corrs, (-alpha * dtheta).tolist())
                if new <= base:
                    break
                alpha *= 0.5

            self.interface.vary_correctors(corrs, (alpha * dtheta).tolist()) #apply the accepted step
            for i, c in enumerate(corrs):
                self.accumulated[c] += alpha * dtheta[i] #scaling the correction

            y_nom_after = self._y_nom(bpms)

                    #numpy array with floats        #flatten into 1D vector
            y_i=np.asarray(y_nom_after, float).ravel()
            chi_orbit=np.sum(y_i*y_i)


            disp_rms = None
            if disp_w > 0 and R_disp is not None:
                self.set_offenergy_flag(True)
                self.interface.change_energy()
                y_off_after = self._y_nom(bpms)
                self.interface.reset_energy()
                self.set_offenergy_flag(False)
                disp_vec_after = y_off_after - y_nom_after
                disp_rms = float(np.linalg.norm(disp_vec_after) / np.sqrt(len(disp_vec_after)))
                                                                         #y nom has a length of 2N

            wake_rms = None
            if wake_w > 0 and R_wake is not None:
                self.set_highintensity_flag(False)
                self.interface.reset_intensity()
                y_low_after = self._y_nom(bpms)
                self.set_highintensity_flag(True)
                self.interface.change_intensity()
                y_high_after = self._y_nom(bpms)
                self.interface.reset_intensity()
                self.set_highintensity_flag(False)
                wake_vec_after = y_high_after - y_low_after
                wake_rms = float(np.linalg.norm(wake_vec_after) / np.sqrt(len(wake_vec_after)))


            if iter_cb:
                if not iter_cb(it, chi_orbit, disp_rms, wake_rms):
                    break

