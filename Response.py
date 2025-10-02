import numpy as np
import pickle
def reorder_matrix_to_gui(R, file_bpms, file_corrs, gui_bpms, gui_corrs):
    file_bpms = [str(b) for b in file_bpms]
    file_corrs = [str(c) for c in file_corrs]
    gui_bpms  = [str(b) for b in gui_bpms]
    gui_corrs = [str(c) for c in gui_corrs]

    miss_b = [b for b in gui_bpms if b not in file_bpms]
    miss_c = [c for c in gui_corrs if c not in file_corrs]
    if miss_b or miss_c:
        msg = []
        if miss_b: msg.append(f"Missing BPMs in file: {miss_b}")
        if miss_c: msg.append(f"Missing Correctors in file: {miss_c}")
        raise RuntimeError("\n".join(msg))

    fb = {b: i for i, b in enumerate(file_bpms)}
    row_x = [fb[b] for b in gui_bpms]
    if R.shape[0] == len(file_bpms):
        row_order=row_x
    else:
        row_y = [i + len(file_bpms) for i in row_x]
        row_order = row_x + row_y

    fc = {c: j for j, c in enumerate(file_corrs)}
    col_order = [fc[c] for c in gui_corrs]

    return R[np.ix_(row_order, col_order)]

def load_dfs_npz(path, gui_bpms, gui_corrs):
    D = np.load(path, allow_pickle=True)
    bpms = list(map(str, D["bpms"]))
    corrs = list(map(str, D["correctors"]))

    if "Rx_nom" in D and "Ry_nom" in D:
        R0 = np.vstack([np.asarray(D["Rx_nom"]), np.asarray(D["Ry_nom"])])
    elif "Rx" in D and "Ry" in D:
        R0 = np.vstack([np.asarray(D["Rx"]), np.asarray(D["Ry"])])
    else:
        raise KeyError("DFS file has no Rx_nom/Ry_nom (or Rx/Ry).")

    Rd = None
    if "Rx_test" in D and "Ry_test" in D:
        R1 = np.vstack([np.asarray(D["Rx_test"]), np.asarray(D["Ry_test"])])
        Rd = R1 - R0

    R0 = reorder_matrix_to_gui(R0, bpms, corrs, gui_bpms, gui_corrs)
    if Rd is not None:
        Rd = reorder_matrix_to_gui(Rd, bpms, corrs, gui_bpms, gui_corrs)
    return R0, Rd

def load_wfs_npz(path, gui_bpms, gui_corrs):
    D = np.load(path, allow_pickle=True)
    need = all(k in D for k in ("Rx_low", "Ry_low", "Rx_high", "Ry_high"))
    if not need:
        raise KeyError("WFS file must contain Rx_low/Ry_low and Rx_high/Ry_high.")
    bpms = list(map(str, D["bpms"]))
    corrs = list(map(str, D["correctors"]))
    Rl = np.vstack([np.asarray(D["Rx_low"]),  np.asarray(D["Ry_low"])])
    Rh = np.vstack([np.asarray(D["Rx_high"]), np.asarray(D["Ry_high"])])
    Rw = Rh - Rl
    return reorder_matrix_to_gui(Rw, bpms, corrs, gui_bpms, gui_corrs)

class Response():
    def __init__(self,filename=None):
        if filename is not None:
            self.load(filename)
        else:
            self.bpms = []
            self.hcorrs = []
            self.vcorrs = []
            self.Rxx = []
            self.Rxy = []
            self.Ryx = []
            self.Ryy = []
            self.Bx = []
            self.By = []

    def submatrix_B(self, bpms):
        bpm_indexes = [index for index, string in enumerate(self.bpms) if string in bpms]
        return (self.Bx[bpm_indexes],
                self.By[bpm_indexes])

    def submatrix_Rx(self, bpms, hcorrs):
        bpm_indexes = [index for index, string in enumerate(self.bpms) if string in bpms]
        hcorrs_indexes = [index for index, string in enumerate(self.hcorrs) if string in hcorrs]
        Rxx = self.Rxx[bpm_indexes,:]
        Ryx = self.Ryx[bpm_indexes,:]
        return (Rxx[:,hcorrs_indexes],
                Ryx[:,hcorrs_indexes])

    def submatrix_Ry(self, bpms, vcorrs):
        bpm_indexes = [index for index, string in enumerate(self.bpms) if string in bpms]
        vcorrs_indexes = [index for index, string in enumerate(self.vcorrs) if string in vcorrs]
        Rxy = self.Rxy[bpm_indexes,:]
        Ryy = self.Ryy[bpm_indexes,:]
        return (Rxy[:,vcorrs_indexes],
                Ryy[:,vcorrs_indexes])

    def load(self,filename):
        with open(filename, "rb") as pickle_file:
            data = pickle.load(pickle_file)
        self.bpms = data['bpms']
        self.hcorrs = data['hcorrs']
        self.vcorrs = data['vcorrs']
        self.Rxx = data['Rxx']
        self.Rxy = data['Rxy']
        self.Ryx = data['Ryx']
        self.Ryy = data['Ryy']
        self.Bx = data['Bx']
        self.By = data['By']

    def save(self, filename):
        R = {
            "bpms": self.bpms,
            "hcorrs": self.hcorrs,
            "vcorrs": self.vcorrs,
            "Rxx": self.Rxx,
            "Rxy": self.Rxy,
            "Ryx": self.Ryx,
            "Ryy": self.Ryy,
            "Bx": self.Bx,
            "By": self.By
        }
        with open(filename, "wb") as pickle_file:
            pickle.dump(R, pickle_file)
