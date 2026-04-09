import os, pickle, re, matplotlib, glob
import numpy as np
matplotlib.use("QtAgg")
from Backend.State import State

'''
Mutual response matrix calculation algorithm.
'''

class ResponseMatrix_DFS_WFS():

    def _compute_response_matrix_from_directory(self, directory, correctors, bpms=None, screens=None, triangular=False, monitor_mode="bpm_only"):
        info=self._find_useful_files(directory)
        if not info["ok"]:
            raise RuntimeError(f"Could not find any valid DATA pairs in {directory}")

        return self._compute_response_matrix(pairs=info["pairs"],correctors=correctors, bpms=bpms, triangular=triangular, screens=screens, monitor_mode = monitor_mode)


    def _find_useful_files(self, directory):
        datafiles=sorted(glob.glob(os.path.join(directory, 'DATA*.pkl')))
        pairs=[]

        for fp in datafiles:
            basename=os.path.basename(fp)
            if "_p" not in basename:
                continue
            fm=fp.replace("_p","_m")
            if os.path.exists(fm):
                pairs.append((fp, fm))

        return {"ok":bool(pairs), "dir":directory, "pairs":pairs}

    def _compute_response_matrix(self, pairs, correctors, bpms = None, screens=None, triangular=False, monitor_mode = "bpm_only"):
        if not hasattr(self, 'sequence'):
            file = pairs[0][0]
            S = State(filename=file)
            self.sequence = S.get_sequence()

        hcorrs = [string for string in correctors if self._is_h_corrector(string)]
        vcorrs = [string for string in correctors if self._is_v_corrector(string)]

        if monitor_mode not in ("bpm_only", "screen_only", "bpm_plus_screens"):
            raise ValueError(f"Unsupported monitor_mode: {monitor_mode}")
        bpms = list(bpms or [])
        screens = list(screens or [])

        if monitor_mode == "bpm_only" and not bpms:
            raise ValueError("Application requires a non-empty bpms list")
        if monitor_mode == "screen_only" and not screens:
            raise ValueError("Application requires a non-empty screens list")
        if monitor_mode == "bpm_plus_screens" and not (bpms or screens):
            raise ValueError("Application requires at least one bpm or screen")

        monitor_names_ref = []
        monitor_types_ref = []

        if monitor_mode in ("bpm_only", "bpm_plus_screens") and bpms:
            last_bpm = bpms[-1]

            # Pick all correctors preceding the last bpm
            hcorrs = [corr for corr in hcorrs if self.sequence.index(corr) < self.sequence.index(last_bpm)]
            vcorrs = [corr for corr in vcorrs if self.sequence.index(corr) < self.sequence.index(last_bpm)]

            # Pick all bpms following the first corrector
            if hcorrs:
                bpms = [bpm for bpm in bpms if self.sequence.index(bpm) > self.sequence.index(hcorrs[0])]
            if vcorrs:
                bpms = [bpm for bpm in bpms if self.sequence.index(bpm) > self.sequence.index(vcorrs[0])]

        if monitor_mode == "bpm_only":
            monitor_names_ref = list(bpms)
            monitor_types_ref = ["bpm"] * len(bpms)
        elif monitor_mode == "screen_only":
            monitor_names_ref = list(screens)
            monitor_types_ref = ["screen"] * len(screens)
        else:
            monitor_names_ref = list(bpms) + list(screens)
            monitor_types_ref = ["bpm"] * len(bpms) + ["screen"] * len(screens)
        nmonitors = len(monitor_names_ref)

        if nmonitors == 0:
            raise ValueError("No monitor devices selected for response matrix computation")

        # Read all orbits
        Bx = np.empty((0, nmonitors))
        By = np.empty((0, nmonitors))
        Cx = np.empty((0, len(hcorrs)))
        Cy = np.empty((0, len(vcorrs)))
        B_mask = np.full((1, nmonitors), True, dtype=bool)

        for fp, fm in pairs:
            Sp = State(filename=fp)
            Sm = State(filename=fm)

            # Op = Sp.get_orbit(bpms)
            # Om = Sm.get_orbit(bpms)

            Mp = self._get_monitor_readings(Sp, bpms=bpms, screens=screens, monitor_mode=monitor_mode)
            Mm = self._get_monitor_readings(Sm, bpms = bpms, screens = screens, monitor_mode=monitor_mode)

            if not monitor_names_ref:
                monitor_names_ref = list(Mp["names"])
                monitor_types_ref = list(Mp["types"])
            elif list(Mp["names"]) != monitor_names_ref:
                raise RuntimeError(f"Wrong monitor order")

            all_not_finite = not np.any(np.isfinite(Mp['x']))
            all_not_finite |= not np.any(np.isfinite(Mm['x']))
            all_not_finite |= not np.any(np.isfinite(Mp['y']))
            all_not_finite |= not np.any(np.isfinite(Mm['y']))

            if all_not_finite:
                print(f"Skipping all-NaN files: {os.path.basename(fp)} / {os.path.basename(fm)}")
                continue

            B_mask &= np.isfinite(Mp['x']) & np.isfinite(Mm['x']) & np.isfinite(Mp['y']) & np.isfinite(Mm['y'])
            Cx_p = Sp.get_correctors(hcorrs)['bact']
            Cy_p = Sp.get_correctors(vcorrs)['bact']
            Cx_m = Sm.get_correctors(hcorrs)['bact']
            Cy_m = Sm.get_correctors(vcorrs)['bact']

            Bx = np.vstack((Bx, Mp['x']))
            Bx = np.vstack((Bx, Mm['x']))
            By = np.vstack((By, Mp['y']))
            By = np.vstack((By, Mm['y']))
            Cx = np.vstack((Cx, Cx_p))
            Cx = np.vstack((Cx, Cx_m))
            Cy = np.vstack((Cy, Cy_p))
            Cy = np.vstack((Cy, Cy_m))

        B_mask = B_mask.ravel()

        # Compute the response matrices
        ones_column_x = np.ones((Cx.shape[0], 1))
        ones_column_y = np.ones((Cy.shape[0], 1))

        # Add the column of ones to the matrix
        Cx = np.hstack((Cx, ones_column_x)).astype(float)
        Cy = np.hstack((Cy, ones_column_y)).astype(float)

        Bx = Bx.astype(float) # facet2 might give objects instead of floats64, like atf2
        By = By.astype(float) # so we do a conversion of a whole array so that every element is a float and lstsq gets a normal, numeric array

        def lstsq(C, B):
            return np.transpose(np.linalg.lstsq(C, B[:, B_mask], rcond=None)[0])

        Rxx_ = lstsq(Cx, Bx)
        Rxy_ = lstsq(Cy, Bx)
        Ryx_ = lstsq(Cx, By)
        Ryy_ = lstsq(Cy, By)

        # Response matrices: remove offset column
        Rxx_ = Rxx_[:, :-1]
        Rxy_ = Rxy_[:, :-1]
        Ryx_ = Ryx_[:, :-1]
        Ryy_ = Ryy_[:, :-1]

        # Restore nan columns
        k = B_mask.size

        Rxx = np.full((k,Rxx_.shape[1]), np.nan)
        Rxy = np.full((k,Rxy_.shape[1]), np.nan)
        Ryx = np.full((k,Ryx_.shape[1]), np.nan)
        Ryy = np.full((k,Ryy_.shape[1]), np.nan)

        Rxx[B_mask,:] = Rxx_
        Rxy[B_mask,:] = Rxy_
        Ryx[B_mask,:] = Ryx_
        Ryy[B_mask,:] = Ryy_

        # Reference trajectory
        Bx = np.mean(Bx, axis=0).reshape(-1, 1)
        By = np.mean(By, axis=0).reshape(-1, 1)

        # Zero the response of all bpms preceeding the correctors
        if triangular and bpms:
            for corr in hcorrs:
                bpm_indexes = [monitor_names_ref.index(bpm) for bpm in bpms if self.sequence.index(bpm) < self.sequence.index(corr)]
                Rxx[bpm_indexes, hcorrs.index(corr)] = 0
                Ryx[bpm_indexes, hcorrs.index(corr)] = 0

            for corr in vcorrs:
                bpm_indexes = [monitor_names_ref.index(bpm) for bpm in bpms if self.sequence.index(bpm) < self.sequence.index(corr)]
                Rxy[bpm_indexes, vcorrs.index(corr)] = 0
                Ryy[bpm_indexes, vcorrs.index(corr)] = 0

        return Rxx, Ryy, Rxy, Ryx, Bx, By, hcorrs, vcorrs, monitor_names_ref, monitor_types_ref

    def _get_data_from_loaded_directories(self, selected_bpms, selected_corrs, selected_screens = None, monitor_mode = "bpm_only", _force_triangular=False):
        info_traj = self._data_dirs.get("traj")
        info_dfs = self._data_dirs.get("dfs")
        info_wfs = self._data_dirs.get("wfs")

        w1, w2, w3, rcond, iters, gain, beta = self._read_params()

        if not (info_traj and info_traj["ok"]):
            raise RuntimeError("Please select a trajectory data directory")
        if w2 > 0 and not (info_dfs and info_dfs["ok"]):
            raise RuntimeError("Please select a dispersion data directory")
        if w3 > 0 and not (info_wfs and info_wfs["ok"]):
            raise RuntimeError("Please select a wakefield data directory")

        triangular = bool(self._force_triangular() or _force_triangular)

        R0xx, R0yy, R0xy, R0yx, B0x, B0y, hcorrs0, vcorrs0, monitors0, monitor_types0 = self._compute_response_matrix(
            pairs=info_traj["pairs"], correctors=selected_corrs, bpms=selected_bpms, screens=selected_screens, triangular=triangular, monitor_mode=monitor_mode)

        if w2 > 0:
            R1xx, R1yy, R1xy, R1yx, B1x, B1y, hcorrs1, vcorrs1, monitors1, monitor_types1 = self._compute_response_matrix(
                pairs=info_dfs["pairs"], correctors=selected_corrs, bpms=selected_bpms, screens=selected_screens, triangular=triangular, monitor_mode=monitor_mode)

        else:
            R1xx, R1yy, R1xy, R1yx = R0xx.copy(), R0yy.copy(), R0xy.copy(), R0yx.copy()
            B1x, B1y = B0x.copy(), B0y.copy()
            hcorrs1, vcorrs1, monitors1, monitor_types1 = list(hcorrs0), list(vcorrs0), list(monitors0), list(
            monitor_types0)

        if w3 > 0:
            R2xx, R2yy, R2xy, R2yx, B2x, B2y, hcorrs2, vcorrs2, monitors2, monitor_types2 = self._compute_response_matrix(
                pairs=info_wfs["pairs"], correctors=selected_corrs, bpms=selected_bpms, screens=selected_screens, triangular=triangular, monitor_mode=monitor_mode)
        else:
            R2xx, R2yy, R2xy, R2yx = R0xx.copy(), R0yy.copy(), R0xy.copy(), R0yx.copy()
            B2x, B2y = B0x.copy(), B0y.copy()
            hcorrs2, vcorrs2, monitors2, monitor_types2 = list(hcorrs0), list(vcorrs0), list(monitors0), list(monitor_types0)

        return (
            R0xx, R0yy, R0xy, R0yx, B0x, B0y,
            R1xx, R1yy, R1xy, R1yx, B1x, B1y,
            R2xx, R2yy, R2xy, R2yx, B2x, B2y,
            hcorrs0, vcorrs0, hcorrs1, vcorrs1, hcorrs2, vcorrs2,
            monitors0, monitor_types0, monitors1, monitor_types1, monitors2, monitor_types2,
        )
    def _creating_response_matrices(self):

        w1, w2, w3, rcond, iters, gain,beta = self._read_params()
        wgt_orb, wgt_dfs, wgt_wfs = w1, w2, w3

        corrs, bpms = self._get_selection()
        monitor_mode = getattr(self, "_response_monitor_mode", "bpm_only")
        screens = getattr(self, "_response_screens", [])
        (
            R0xx, R0yy, R0xy, R0yx, B0x, B0y,
            R1xx, R1yy, R1xy, R1yx, B1x, B1y,
            R2xx, R2yy, R2xy, R2yx, B2x, B2y,
            hcorrs0, vcorrs0, hcorrs1, vcorrs1, hcorrs2, vcorrs2,
            monitors0, monitor_types0, monitors1, monitor_types1, monitors2, monitor_types2,
        ) = self._get_data_from_loaded_directories(
            selected_corrs=corrs, selected_bpms=bpms, selected_screens=screens, monitor_mode=monitor_mode,
            _force_triangular=self._force_triangular()
        )
        def _handle_missing_corrector(R,corrs,corrs_ref):
            if corrs== corrs_ref:
                return R
            else:
                index={c: i for i, c in enumerate(corrs)}
                final_matrix=np.zeros((R.shape[0],len(corrs_ref)), dtype=float)
                for j,c in enumerate(corrs_ref):
                    i=index.get(c)
                    if i is not None:
                        final_matrix[:,j] = R[:,i]
                return final_matrix

        def _handle_missing_monitor(Rxx,Ryy,Rxy,Ryx,Bx,By,monitors,monitors_ref):
            if monitors == monitors_ref:
                return Rxx, Ryy, Rxy, Ryx, Bx, By
            index = {m: i for i, m in enumerate(monitors)}
            monitor_indexes = [index[m] for m in monitors_ref]

            return (
                Rxx[monitor_indexes, :],
                Ryy[monitor_indexes, :],
                Rxy[monitor_indexes, :],
                Ryx[monitor_indexes, :],
                Bx[monitor_indexes, :],
                By[monitor_indexes, :],
            )

        #intersection
        hcorrs=[c for c in hcorrs0 if (c in hcorrs1 and c in hcorrs2)]
        vcorrs=[c for c in vcorrs0 if (c in vcorrs1 and c in vcorrs2)]
        monitors = [m for m in monitors0 if (m in monitors1 and m in monitors2)]

        R0xx=_handle_missing_corrector(R0xx, hcorrs0,hcorrs)
        R0yy=_handle_missing_corrector(R0yy, vcorrs0,vcorrs)
        R0xy=_handle_missing_corrector(R0xy, vcorrs0,vcorrs)
        R0yx=_handle_missing_corrector(R0yx, hcorrs0,hcorrs)
        R1xx=_handle_missing_corrector(R1xx, hcorrs1,hcorrs)
        R1yy=_handle_missing_corrector(R1yy, vcorrs1,vcorrs)
        R1xy=_handle_missing_corrector(R1xy, vcorrs1,vcorrs)
        R1yx=_handle_missing_corrector(R1yx, hcorrs1,hcorrs)
        R2xx=_handle_missing_corrector(R2xx, hcorrs2,hcorrs)
        R2yy=_handle_missing_corrector(R2yy, vcorrs2,vcorrs)
        R2xy=_handle_missing_corrector(R2xy, vcorrs2,vcorrs)
        R2yx=_handle_missing_corrector(R2yx, hcorrs2,hcorrs)

        R0xx, R0yy, R0xy, R0yx, B0x, B0y = _handle_missing_monitor(R0xx, R0yy, R0xy, R0yx, B0x, B0y, monitors0, monitors)
        R1xx, R1yy, R1xy, R1yx, B1x, B1y = _handle_missing_monitor(R1xx, R1yy, R1xy, R1yx, B1x, B1y, monitors1, monitors)
        R2xx, R2yy, R2xy, R2yx, B2x, B2y = _handle_missing_monitor(R2xx, R2yy, R2xy, R2yx, B2x, B2y, monitors2, monitors)

        Axx=[]
        Ayy=[]
        Axy=[]
        Ayx=[]

        if wgt_orb > 0:
            Axx.append(wgt_orb * R0xx)
            Ayy.append(wgt_orb * R0yy)
            Axy.append(wgt_orb * R0xy)
            Ayx.append(wgt_orb * R0yx)

        if wgt_dfs > 0:
            Axx.append(wgt_dfs * (R1xx - R0xx))
            Ayy.append(wgt_dfs * (R1yy - R0yy))
            Axy.append(wgt_dfs * (R1xy - R0xy))
            Ayx.append(wgt_dfs * (R1yx - R0yx))

        if wgt_wfs > 0:
            Axx.append(wgt_wfs * (R2xx - R0xx))
            Ayy.append(wgt_wfs * (R2yy - R0yy))
            Axy.append(wgt_wfs * (R2xy - R0xy))
            Ayx.append(wgt_wfs * (R2yx - R0yx))

        Axx = np.vstack(Axx)
        Ayy = np.vstack(Ayy)
        Axy = np.vstack(Axy)
        Ayx = np.vstack(Ayx)

        return Axx, Ayy, Axy, Ayx, B0x, B0y, hcorrs, vcorrs, monitors

    def _get_monitor_readings(self, state, bpms=None, screens=None, monitor_mode="bpm_only"):
        names = []
        x = []
        y = []
        types = []

        bpms = list(bpms or [])
        screens = list(screens or [])

        if monitor_mode not in ("bpm_only", "screen_only", "bpm_plus_screens"):
            raise ValueError(f"Unsupported monitor_mode: {monitor_mode}")

        use_bpms = monitor_mode in ("bpm_only", "bpm_plus_screens")
        use_screens = monitor_mode in ("screen_only", "bpm_plus_screens")

        if use_bpms and bpms:
            orbit = state.get_orbit(bpms)
            idx = {str(name): i for i, name in enumerate(orbit["names"])}
            for name in bpms:
                key = str(name)
                i = idx.get(key)
                names.append(key)
                if i is None:
                    x.append(np.nan)
                    y.append(np.nan)
                else:
                    x.append(float(orbit["x"][i]))
                    y.append(float(orbit["y"][i]))
                types.append("bpm")

        if use_screens and screens:
            scr = state.get_screens(screens)
            idx = {str(name): i for i, name in enumerate(scr["names"])}
            for name in screens:
                key = str(name)
                i = idx.get(key)
                names.append(key)
                if i is None:
                    x.append(np.nan)
                    y.append(np.nan)
                else:
                    x.append(float(scr["x"][i]))
                    y.append(float(scr["y"][i]))
                types.append("screen")

        return {
            "names": names,
            "x": np.asarray(x, dtype=float),
            "y": np.asarray(y, dtype=float),
            "types": types,
        }