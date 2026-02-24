import os, pickle, re, matplotlib, glob
import numpy as np
matplotlib.use("QtAgg")
from State import State

'''
Uses the same approach as Compute Response Matrix GUI.
'''

class DFS_WFS_Correction_BBA():
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

    def _compute_response_matrix(self,pairs,correctors,bpms,triangular=False):
        if not hasattr(self, 'sequence'): #is self.sequence already initialixed
            file=pairs[0][0]
            #self.datafiles = glob.glob('DATA*.pkl')
            S = State(filename=file)
            self.sequence = S.get_sequence()

        hcorrs = [string for string in correctors if (string.lower().startswith('zh') or string.lower().startswith('zx'))]
        vcorrs = [string for string in correctors if string.lower().startswith('zv')]

        hcorrs = [ corr for corr in hcorrs if self.sequence.index(corr) < self.sequence.index(bpms[-1]) ]
        vcorrs = [ corr for corr in vcorrs if self.sequence.index(corr) < self.sequence.index(bpms[-1]) ]

        if hcorrs:
            bpms = [ bpm for bpm in bpms if self.sequence.index(bpm) > self.sequence.index(hcorrs[0]) ]

        if vcorrs:
            bpms = [ bpm for bpm in bpms if self.sequence.index(bpm) > self.sequence.index(vcorrs[0]) ]

        # Read all orbits
        Bx = np.empty((0,len(bpms)))
        By = np.empty((0,len(bpms)))
        Cx = np.empty((0,len(hcorrs)))
        Cy = np.empty((0,len(vcorrs)))

        for fp, fm in pairs:
            Sp=State(filename=fp)
            Sm=State(filename=fm)

            Op = Sp.get_orbit(bpms)
            Om = Sm.get_orbit(bpms)

            Cx_p = Sp.get_correctors(hcorrs)['bact']
            Cy_p = Sp.get_correctors(vcorrs)['bact']
            Cx_m = Sm.get_correctors(hcorrs)['bact']
            Cy_m = Sm.get_correctors(vcorrs)['bact']

            if 0:
                O_x = Op['x'] - Om['x']
                O_y = Op['y'] - Om['y']
                C_x = Cx_p - Cx_m
                C_y = Cy_p - Cy_m
                Bx = np.vstack((Bx, O_x))
                By = np.vstack((By, O_y))
                Cx = np.vstack((Cx, C_x))
                Cy = np.vstack((Cy, C_y))
                print(Cx, Bx)

            else:
                Bx = np.vstack((Bx, Op['x']))
                Bx = np.vstack((Bx, Om['x']))
                By = np.vstack((By, Op['y']))
                By = np.vstack((By, Om['y']))
                Cx = np.vstack((Cx, Cx_p))
                Cx = np.vstack((Cx, Cx_m))
                Cy = np.vstack((Cy, Cy_p))
                Cy = np.vstack((Cy, Cy_m))

        # Compute the response matrices
        ones_column_x = np.ones((Cx.shape[0], 1))
        ones_column_y = np.ones((Cy.shape[0], 1))

        # Add the column of ones to the matrix
        Cx = np.hstack((Cx, ones_column_x))
        Cy = np.hstack((Cy, ones_column_y))

        Rxx = np.transpose(np.linalg.lstsq(Cx, Bx, rcond=None)[0])
        Rxy = np.transpose(np.linalg.lstsq(Cy, Bx, rcond=None)[0])
        Ryx = np.transpose(np.linalg.lstsq(Cx, By, rcond=None)[0])
        Ryy = np.transpose(np.linalg.lstsq(Cy, By, rcond=None)[0])

        # Reference trajectory

        Bx = np.mean(Bx,axis=0).reshape(-1,1)
        By = np.mean(By,axis=0).reshape(-1,1)

        # Response matrices
        Rxx = Rxx[:,:-1]
        Rxy = Rxy[:,:-1]
        Ryx = Ryx[:,:-1]
        Ryy = Ryy[:,:-1]

        # Zero the response of all bpms preceeding the correctors
        if triangular:
            for corr in hcorrs:
                 bpm_indexes = [ bpms.index(bpm) for bpm in bpms if self.sequence.index(bpm) < self.sequence.index(corr) ]

                 Rxx[bpm_indexes, hcorrs.index(corr)] = 0
                 Ryx[bpm_indexes, hcorrs.index(corr)] = 0

            for corr in vcorrs:
                 bpm_indexes = [ bpms.index(bpm) for bpm in bpms if self.sequence.index(bpm) < self.sequence.index(corr) ]

                 Rxy[bpm_indexes, vcorrs.index(corr)] = 0
                 Ryy[bpm_indexes, vcorrs.index(corr)] = 0

        return Rxx,Ryy,Rxy,Ryx,Bx,By, hcorrs,vcorrs


    def _get_data_from_loaded_directories(self, selected_bpms, selected_corrs, _force_triangular=False):

        info_traj = self._data_dirs["traj"]
        info_dfs = self._data_dirs["dfs"]
        info_wfs = self._data_dirs["wfs"]

        if not (info_traj and info_traj["ok"] and info_dfs and info_dfs["ok"] and info_wfs and info_wfs["ok"]):
            raise RuntimeError("Please select all data directories")

        triangular = bool(self._force_triangular() or _force_triangular)

        R0xx,R0yy,R0xy,R0yx,B0x,B0y,hcorrs0,vcorrs0=self._compute_response_matrix(pairs=info_traj["pairs"],correctors=selected_corrs, bpms=selected_bpms, triangular=triangular)
        R1xx,R1yy,R1xy,R1yx,B1x,B1y,hcorrs1,vcorrs1=self._compute_response_matrix(pairs=info_dfs["pairs"],correctors=selected_corrs, bpms=selected_bpms, triangular=triangular)
        R2xx,R2yy,R2xy,R2yx,B2x,B2y,hcorrs2,vcorrs2=self._compute_response_matrix(pairs=info_wfs["pairs"],correctors=selected_corrs, bpms=selected_bpms, triangular=triangular)

        return R0xx,R0yy,R0xy,R0yx,B0x,B0y,R1xx,R1yy,R1xy,R1yx,B1x,B1y,R2xx,R2yy,R2xy,R2yx,B2x,B2y, hcorrs0,vcorrs0,hcorrs1,vcorrs1,hcorrs2,vcorrs2

    def _creating_response_matrices(self):

        w1, w2, w3, rcond, iters, gain = self._read_params()
        wgt_orb, wgt_dfs, wgt_wfs = w1, w2, w3

        corrs, bpms = self._get_selection()

        R0xx,R0yy,R0xy,R0yx,B0x,B0y,R1xx,R1yy,R1xy,R1yx,B1x,B1y,R2xx,R2yy,R2xy,R2yx,B2x,B2y, hcorrs0,vcorrs0,hcorrs1,vcorrs1,hcorrs2,vcorrs2  = self._get_data_from_loaded_directories(selected_corrs=corrs, selected_bpms=bpms, _force_triangular=self._force_triangular())

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
        #intersection
        hcorrs=[c for c in hcorrs0 if (c in hcorrs1 and c in hcorrs2)]
        vcorrs=[c for c in vcorrs0 if (c in vcorrs1 and c in vcorrs2)]

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

        return Axx, Ayy,Axy,Ayx, B0x, B0y,hcorrs,vcorrs
