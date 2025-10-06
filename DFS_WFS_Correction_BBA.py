import numpy as np
from State import State

class CorrectionEngine:
    def __init__(self,interface):
        self.interface=interface
        self.accumulated={}

    def _measure_orbit_vec(self,bpms):
        S=State(interface=self.interface)
        O=S.get_orbit(bpms)
        x=O["x"].reshape(-1,1) #column vector
        y=O["y"].reshape(-1,1)
        return x,y

    def compute_response_matrix(self,corrs,bpms, delta=0.01,triangular=False,progress_cb=None):
        nb,nc=len(bpms),len(corrs)
        Rx=np.zeros((nb,nc))
        Ry=np.zeros((nb,nc))


        for j,c in enumerate(corrs):
            if progress_cb and not progress_cb(j, len(corrs), f"Exciting {c} (±{delta:g}) "):
                break
            self.interface.vary_correctors([c],[delta])
            xp,yp=self._measure_orbit_vec(bpms)

            self.interface.vary_correctors([c],[-2*delta])
            xm,ym=self._measure_orbit_vec(bpms)

            self.interface.vary_correctors([c],[delta])

            Rx[:,j]=((xp-xm)/(2*delta)).flatten()
            Ry[:,j]=((yp-ym)/(2*delta)).flatten()

        if triangular:
            Rx=np.tril(Rx)
            Ry=np.tril(Ry)

        return {"bpms": bpms,"correctors":corrs,"Rx":Rx,"Ry":Ry,"delta":float(delta)}

    def set_offenergy_flag(self, on: bool):
        pass

    def set_highintensity_flag(self, on: bool):
        pass

    def solve_and_apply(self, *,orbit_w, disp_w, wake_w,rcond, max_iters,bpms, corrs,triangular=False,
                        R_nom=None, R_disp=None, R_wake=None,
                        iter_cb=None, y_ref=None,
                        scale_change_energy=0.98, scale_reset_energy=1.0,
                        scale_change_intensity=0.9, scale_reset_intensity=1.0):
        gain=0.4
        self.accumulated={c: 0.0 for c in corrs}

        orbit_w=float(orbit_w)
        disp_w=float(disp_w)
        wake_w=float(wake_w)

        if y_ref is not None:
            y_ref=np.asarray(y_ref,float).reshape(-1,1) #making it that way for the y_nom-y_ref

        for it in range(int(max_iters)):
            #nominal
            O0x,O0y=self._measure_orbit_vec(bpms)

            #dfs
            self.interface.change_energy(scale=scale_change_energy)
            O1x, O1y = self._measure_orbit_vec(bpms)
            self.interface.reset_energy(scale=scale_reset_energy)


            #wfs
            self.interface.reset_intensity(scale=scale_reset_intensity)
            OLx, OLy = self._measure_orbit_vec(bpms)
            self.interface.change_intensity(scale=scale_change_intensity)
            OHx, OHy = self._measure_orbit_vec(bpms)
            self.interface.reset_intensity(scale=scale_reset_intensity)


            y_nom=np.vstack([O0x,O0y])
            y_off=np.vstack([O1x,O1y])
            y_low=np.vstack([OLx,OLy])
            y_high=np.vstack([OHx,OHy])


            A_terms=[]
            B_terms=[]


            if (orbit_w!=0) and (R_nom is not None):
                A_terms.append(orbit_w * R_nom)
                B_terms.append(orbit_w * (y_nom-y_ref) if y_ref is not None else orbit_w * y_nom)

            if (disp_w!=0) and (R_disp is not None):
                A_terms.append(disp_w * R_disp)
                B_terms.append(disp_w * (y_off-y_nom))

            if (wake_w!=0) and (R_wake is not None):
                A_terms.append(wake_w * R_wake)
                B_terms.append(wake_w * (y_high-y_low))

            A=np.vstack(A_terms)
            B=np.vstack(B_terms)

            dtheta, *_ = np.linalg.lstsq(A, -B, rcond=float(rcond))
            kicks = (gain * dtheta).ravel().tolist() #to keep it stable
            self.interface.vary_correctors(corrs, kicks)

            for i, c in enumerate(corrs):
                self.accumulated[c] += kicks[i]

            orbit_rms=float(np.linalg.norm(y_nom)/np.sqrt(y_nom.size)) # sqrt(1/N Σy_nom^2/)
            disp_rms=float(np.linalg.norm(y_off-y_nom)/np.sqrt(y_off.size)) \
                        if (disp_w and R_disp is not None) else None
            wake_rms=float(np.linalg.norm(y_high-y_low)/np.sqrt(y_nom.size)) \
                        if (wake_w and R_wake is not None) else None

            if iter_cb and not iter_cb(it, orbit_rms, disp_rms, wake_rms):
                break