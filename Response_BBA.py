import os
import numpy as np

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

def svd_info(M):
    s = np.linalg.svd(M, compute_uv=False)
    mn, mx = float(s.min()), float(s.max())
    cond = (mx / mn) if mn > 0 else float("inf")
    rank = int(np.linalg.matrix_rank(M))
    return {"min_sigma": mn, "max_sigma": mx, "cond": cond, "rank": rank}
