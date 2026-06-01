import numpy as np


def seq_index_map(sequence):
    return {str(name): idx for idx, name in enumerate(sequence)}


def _sequence_positions(order, name):
    key = str(name)
    candidates = [key]
    if not key.startswith("M"):
        candidates.append(f"M{key}")
    elif len(key) > 1:
        candidates.append(key[1:])
    out = []
    for cand in candidates:
        if cand in order and order[cand] not in out:
            out.append(order[cand])
    return out


def choose_reference_bpms(selected_bpms, actuators, sequence, min_refs=2):
    order = seq_index_map(sequence)
    bpm_names = [str(name) for name in selected_bpms]
    act_names = [str(name) for name in actuators]
    if not bpm_names or not act_names:
        return []
    act_pos = []
    for name in act_names:
        act_pos.extend(_sequence_positions(order, name))
    if not act_pos:
        return []
    upstream_limit = min(act_pos)
    refs = []
    for name in bpm_names:
        pos = _sequence_positions(order, name)
        if pos and min(pos) < upstream_limit:
            refs.append(name)
    return refs if len(refs) >= int(min_refs) else []


def explain_reference_selection(selected_bpms, actuators, sequence, min_refs=2):
    order = seq_index_map(sequence)
    bpm_names = [str(name) for name in selected_bpms]
    act_names = [str(name) for name in actuators]
    if not bpm_names:
        return [], "no BPMs selected"
    if not act_names:
        return [], "no actuators selected"
    act_pos = []
    for name in act_names:
        act_pos.extend(_sequence_positions(order, name))
    if not act_pos:
        return [], "selected actuators are not in the sequence"
    upstream_limit = min(act_pos)
    refs = []
    for name in bpm_names:
        pos = _sequence_positions(order, name)
        if pos and min(pos) < upstream_limit:
            refs.append(name)
    if len(refs) < int(min_refs):
        return refs, f"need at least {int(min_refs)} upstream reference BPMs, found {len(refs)}"
    return refs, ""


def collect_rows_from_bpms(bpms, names):
    all_names = [str(name) for name in bpms.get("names", [])]
    if not all_names:
        return None
    index = {name: i for i, name in enumerate(all_names)}
    cols = [index[name] for name in names if name in index]
    if not cols:
        return None
    x = np.asarray(bpms.get("x", []), dtype=float)
    y = np.asarray(bpms.get("y", []), dtype=float)
    if x.ndim != 2 or y.ndim != 2 or x.shape != y.shape:
        return None
    return x[:, cols], y[:, cols], [all_names[i] for i in cols]


def fit_jitter_model(bpms_list, reference_bpms, target_bpms, ridge=1e-6):
    ref_bpms = [str(name) for name in reference_bpms]
    tgt_bpms = [str(name) for name in target_bpms if str(name) not in ref_bpms]
    if not ref_bpms or not tgt_bpms:
        return None, "missing reference or target BPMs"

    x_ref_rows = []
    y_ref_rows = []
    x_tgt_rows = []
    y_tgt_rows = []

    for bpms in bpms_list:
        ref_data = collect_rows_from_bpms(bpms, ref_bpms)
        tgt_data = collect_rows_from_bpms(bpms, tgt_bpms)
        if ref_data is None or tgt_data is None:
            continue
        x_ref, y_ref, refs_found = ref_data
        x_tgt, y_tgt, tgts_found = tgt_data
        if refs_found != ref_bpms or tgts_found != tgt_bpms:
            continue
        if x_ref.shape[0] == 0:
            continue
        x_ref_rows.append(x_ref)
        y_ref_rows.append(y_ref)
        x_tgt_rows.append(x_tgt)
        y_tgt_rows.append(y_tgt)

    if not x_ref_rows:
        return None, "no BPM snapshots matched the requested reference/target BPMs"

    x_ref_all = np.vstack(x_ref_rows)
    y_ref_all = np.vstack(y_ref_rows)
    x_tgt_all = np.vstack(x_tgt_rows)
    y_tgt_all = np.vstack(y_tgt_rows)

    x_ref_mean = np.nanmean(x_ref_all, axis=0)
    y_ref_mean = np.nanmean(y_ref_all, axis=0)
    x_tgt_mean = np.nanmean(x_tgt_all, axis=0)
    y_tgt_mean = np.nanmean(y_tgt_all, axis=0)

    x_ref_all = np.nan_to_num(x_ref_all - x_ref_mean, nan=0.0)
    y_ref_all = np.nan_to_num(y_ref_all - y_ref_mean, nan=0.0)
    x_tgt_all = np.nan_to_num(x_tgt_all - x_tgt_mean, nan=0.0)
    y_tgt_all = np.nan_to_num(y_tgt_all - y_tgt_mean, nan=0.0)

    def solve_weights(x_in, y_out):
        gram = x_in.T @ x_in
        gram += float(ridge) * np.eye(gram.shape[0], dtype=float)
        return np.linalg.solve(gram, x_in.T @ y_out)

    wx = solve_weights(x_ref_all, x_tgt_all)
    wy = solve_weights(y_ref_all, y_tgt_all)

    return {
        "reference_bpms": ref_bpms,
        "target_bpms": tgt_bpms,
        "x_ref_mean": x_ref_mean,
        "y_ref_mean": y_ref_mean,
        "x_weights": wx,
        "y_weights": wy,
    }, ""


def apply_jitter_subtraction(bpms, model):
    if not model:
        return bpms

    all_names = [str(name) for name in bpms.get("names", [])]
    idx = {name: i for i, name in enumerate(all_names)}
    ref_bpms = model["reference_bpms"]
    tgt_bpms = model["target_bpms"]
    if any(name not in idx for name in ref_bpms):
        return bpms
    if not any(name in idx for name in tgt_bpms):
        return bpms

    x = np.asarray(bpms.get("x", []), dtype=float).copy()
    y = np.asarray(bpms.get("y", []), dtype=float).copy()
    t = np.asarray(bpms.get("tmit", []), dtype=float).copy()
    s = np.asarray(bpms.get("S", []), dtype=float).copy()

    ref_idx = [idx[name] for name in ref_bpms]
    tgt_model_idx = [i for i, name in enumerate(tgt_bpms) if name in idx]
    tgt_idx = [idx[tgt_bpms[i]] for i in tgt_model_idx]
    if x.ndim != 2 or y.ndim != 2 or not tgt_idx:
        return bpms

    x_ref = np.nan_to_num(x[:, ref_idx] - model["x_ref_mean"], nan=0.0)
    y_ref = np.nan_to_num(y[:, ref_idx] - model["y_ref_mean"], nan=0.0)
    x_pred = x_ref @ model["x_weights"][:, tgt_model_idx]
    y_pred = y_ref @ model["y_weights"][:, tgt_model_idx]
    x[:, tgt_idx] = x[:, tgt_idx] - x_pred
    y[:, tgt_idx] = y[:, tgt_idx] - y_pred

    corrected = dict(bpms)
    corrected["x"] = x
    corrected["y"] = y
    return corrected
