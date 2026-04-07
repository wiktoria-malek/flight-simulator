import argparse
import os
import numpy as np
import matplotlib.pyplot as plt

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from Interfaces.ATF2.InterfaceATF2_Ext_RFTrack import InterfaceATF2_Ext_RFTrack


def to_1d(values):
    arr = np.asarray(values, dtype=float)
    if arr.ndim == 2 and arr.shape[0] == 1:
        arr = arr[0]
    return arr.ravel()


def get_orbit(interface, bpms):
    state = interface.get_state()
    orbit = state.get_orbit(bpms)
    return to_1d(orbit["x"]), to_1d(orbit["y"])


def get_corr_values(interface, corr_name):
    info = interface.get_correctors([corr_name])
    bdes = to_1d(info["bdes"])[0]
    bact = to_1d(info["bact"])[0] if "bact" in info else np.nan
    return bdes, bact


def set_corr_bdes(interface, corr_name, value):
    interface.set_correctors([corr_name], np.array([value], dtype=float))


def measure_live_column(interface, corr_name, bpms, kick):
    bdes0, bact0 = get_corr_values(interface, corr_name)
    x0, y0 = get_orbit(interface, bpms)

    set_corr_bdes(interface, corr_name, bdes0 + kick)
    bdes_p, bact_p = get_corr_values(interface, corr_name)
    xp, yp = get_orbit(interface, bpms)

    set_corr_bdes(interface, corr_name, bdes0 - kick)
    bdes_m, bact_m = get_corr_values(interface, corr_name)
    xm, ym = get_orbit(interface, bpms)

    set_corr_bdes(interface, corr_name, bdes0)
    bdes_r, bact_r = get_corr_values(interface, corr_name)

    denom_bdes = bdes_p - bdes_m
    denom_bact = bact_p - bact_m if np.isfinite(bact_p) and np.isfinite(bact_m) else np.nan

    dOx_dbdes = (xp - xm) / denom_bdes
    dOy_dbdes = (yp - ym) / denom_bdes

    if np.isfinite(denom_bact) and abs(denom_bact) > 0:
        dOx_dbact = (xp - xm) / denom_bact
        dOy_dbact = (yp - ym) / denom_bact
    else:
        dOx_dbact = None
        dOy_dbact = None

    result = {
        "bdes0": bdes0,
        "bact0": bact0,
        "bdes_plus": bdes_p,
        "bact_plus": bact_p,
        "bdes_minus": bdes_m,
        "bact_minus": bact_m,
        "bdes_restore": bdes_r,
        "bact_restore": bact_r,
        "x0": x0,
        "y0": y0,
        "dOx_dbdes": dOx_dbdes,
        "dOy_dbdes": dOy_dbdes,
        "dOx_dbact": dOx_dbact,
        "dOy_dbact": dOy_dbact,
        "denom_bdes": denom_bdes,
        "denom_bact": denom_bact,
    }
    return result


def compare_vectors(model, live):
    model = np.asarray(model, dtype=float).ravel()
    live = np.asarray(live, dtype=float).ravel()

    good = np.isfinite(model) & np.isfinite(live)
    model = model[good]
    live = live[good]

    if model.size == 0:
        return {
            "corr": np.nan,
            "scale_model_to_live": np.nan,
            "scale_live_to_model": np.nan,
            "rms_diff": np.nan,
            "rms_model": np.nan,
            "rms_live": np.nan,
        }

    rms_model = float(np.sqrt(np.mean(model ** 2)))
    rms_live = float(np.sqrt(np.mean(live ** 2)))
    rms_diff = float(np.sqrt(np.mean((model - live) ** 2)))

    if model.size > 1 and np.std(model) > 0 and np.std(live) > 0:
        corr = float(np.corrcoef(model, live)[0, 1])
    else:
        corr = np.nan

    denom_model = float(model @ model)
    denom_live = float(live @ live)
    scale_model_to_live = float((model @ live) / denom_model) if denom_model > 0 else np.nan
    scale_live_to_model = float((live @ model) / denom_live) if denom_live > 0 else np.nan

    return {
        "corr": corr,
        "scale_model_to_live": scale_model_to_live,
        "scale_live_to_model": scale_live_to_model,
        "rms_diff": rms_diff,
        "rms_model": rms_model,
        "rms_live": rms_live,
    }


def load_bba_matrices(interface, nominal_state, start_state, session_dir, traj_dir, disp_dir=None, wake_dir=None):
    from PyQt6.QtWidgets import QApplication
    from BBA_GUI import MainWindow

    app = QApplication.instance()
    owns_app = False
    if app is None:
        app = QApplication([])
        owns_app = True

    win = MainWindow(interface=interface, dir_name=session_dir, nominal_state=nominal_state, start_state=start_state)

    try:
        for rb in getattr(win, "radio_buttons", []):
            txt = (rb.text() or "").strip().lower()
            rb.setChecked(txt == "orbit")
    except Exception:
        pass

    if hasattr(win, "lineEdit"):
        win.lineEdit.setText("1.0")
    if hasattr(win, "lineEdit_2"):
        win.lineEdit_2.setText("0.0")
    if hasattr(win, "lineEdit_3"):
        win.lineEdit_3.setText("0.0")

    traj_dir = os.path.expanduser(os.path.expandvars(traj_dir)) if traj_dir else ""
    disp_dir = os.path.expanduser(os.path.expandvars(disp_dir)) if disp_dir else ""
    wake_dir = os.path.expanduser(os.path.expandvars(wake_dir)) if wake_dir else ""

    if traj_dir:
        win._data_dirs["traj"] = win._find_useful_files(traj_dir)
        win.trajectory_response_3.setText(traj_dir)
    else:
        win._data_dirs["traj"] = None

    if disp_dir:
        win._data_dirs["dfs"] = win._find_useful_files(disp_dir)
        win.dfs_response_3.setText(disp_dir)
    else:
        win._data_dirs["dfs"] = None
        if hasattr(win, "dfs_response_3"):
            win.dfs_response_3.setText("")

    if wake_dir:
        win._data_dirs["wfs"] = win._find_useful_files(wake_dir)
        win.wfs_response_3.setText(wake_dir)
    else:
        win._data_dirs["wfs"] = None
        if hasattr(win, "wfs_response_3"):
            win.wfs_response_3.setText("")

    print("traj_dir passed to BBA:", traj_dir)
    print("disp_dir passed to BBA:", disp_dir)
    print("wake_dir passed to BBA:", wake_dir)
    print("win._data_dirs keys:", {k: (None if v is None else v.get("ok", None)) for k, v in win._data_dirs.items()})
    if win._data_dirs.get("traj") is not None:
        traj_info = win._data_dirs["traj"]
        print("traj info: ok=", traj_info.get("ok"), "dir=", traj_info.get("dir"), "pairs=", len(traj_info.get("pairs", [])))
    if win._data_dirs.get("dfs") is not None:
        dfs_info = win._data_dirs["dfs"]
        print("dfs info: ok=", dfs_info.get("ok"), "dir=", dfs_info.get("dir"), "pairs=", len(dfs_info.get("pairs", [])))
    if win._data_dirs.get("wfs") is not None:
        wfs_info = win._data_dirs["wfs"]
        print("wfs info: ok=", wfs_info.get("ok"), "dir=", wfs_info.get("dir"), "pairs=", len(wfs_info.get("pairs", [])))
    Axx, Ayy, Axy, Ayx, B0x, B0y, hcorrs, vcorrs, bpms_common = win._creating_response_matrices()

    if owns_app:
        app.quit()

    return {
        "Axx": np.asarray(Axx, dtype=float),
        "Ayy": np.asarray(Ayy, dtype=float),
        "Axy": np.asarray(Axy, dtype=float),
        "Ayx": np.asarray(Ayx, dtype=float),
        "B0x": np.asarray(B0x, dtype=float),
        "B0y": np.asarray(B0y, dtype=float),
        "hcorrs": list(hcorrs),
        "vcorrs": list(vcorrs),
        "bpms": list(bpms_common),
    }


def plot_overlay(bpms, live_main, model_main, title_main, live_cross=None, model_cross=None, title_cross=None):
    idx = np.arange(len(bpms))

    plt.figure(figsize=(14, 8))
    plt.subplot(2, 1, 1)
    plt.plot(idx, live_main, marker="o", label="live")
    plt.plot(idx, model_main, marker="o", label="matrix")
    plt.xticks(idx, bpms, rotation=90, fontsize=8)
    plt.grid(True, alpha=0.3)
    plt.ylabel("response")
    plt.title(title_main)
    plt.legend()

    if live_cross is not None and model_cross is not None:
        plt.subplot(2, 1, 2)
        plt.plot(idx, live_cross, marker="o", label="live")
        plt.plot(idx, model_cross, marker="o", label="matrix")
        plt.xticks(idx, bpms, rotation=90, fontsize=8)
        plt.grid(True, alpha=0.3)
        plt.ylabel("response")
        plt.title(title_cross or "cross-plane response")
        plt.legend()

    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Compare a live single-corrector response with the column used by BBA.")
    parser.add_argument("--corrector", default="ZV1X", help="Corrector name to test, e.g. ZV1X or ZH1X")
    parser.add_argument("--kick", type=float, default=0.001, help="Kick applied in the same unit as interface bdes")
    parser.add_argument("--traj-dir", required=True, help="Trajectory response directory used by BBA")
    parser.add_argument("--disp-dir", default="", help="Optional dispersion response directory")
    parser.add_argument("--wake-dir", default="", help="Optional wakefield response directory")
    parser.add_argument("--plot", action="store_true", help="Show overlay plots of live vs matrix columns")
    args = parser.parse_args()

    np.set_printoptions(precision=6, suppress=True, linewidth=220)

    interface = InterfaceATF2_Ext_RFTrack(jitter=0.0, bpm_resolution=0.0)
    interface.align_everything()
    nominal_state = interface.get_state()
    interface.misalign_quadrupoles()
    start_state = interface.get_state()

    session_dir = os.path.expanduser("~/flight-simulator-data/debug_compare_response")
    matrices = load_bba_matrices(
        interface=interface,
        nominal_state=nominal_state,
        start_state=start_state,
        session_dir=session_dir,
        traj_dir=args.traj_dir,
        disp_dir=(args.disp_dir or "").strip() or None,
        wake_dir=(args.wake_dir or "").strip() or None,
    )

    bpms = matrices["bpms"]
    live = measure_live_column(interface, args.corrector, bpms, args.kick)

    print("Corrector under test:", args.corrector)
    print("BPMS used by BBA matrix:")
    print(bpms)
    print()
    print("--- Live corrector values ---")
    print(f"bdes0={live['bdes0']:.6f}, bact0={live['bact0']:.6f}")
    print(f"plus : bdes={live['bdes_plus']:.6f}, bact={live['bact_plus']:.6f}")
    print(f"minus: bdes={live['bdes_minus']:.6f}, bact={live['bact_minus']:.6f}")
    print(f"restore: bdes={live['bdes_restore']:.6f}, bact={live['bact_restore']:.6f}")
    print(f"delta bdes={live['denom_bdes']:.6f}")
    if np.isfinite(live['denom_bact']):
        print(f"delta bact={live['denom_bact']:.6f}")
    else:
        print("delta bact=NaN / unavailable")
    print()

    is_h = args.corrector in matrices["hcorrs"]
    is_v = args.corrector in matrices["vcorrs"]

    if is_h and is_v:
        raise RuntimeError(f"Corrector {args.corrector} is present in both hcorrs and vcorrs. This should not happen.")
    if not is_h and not is_v:
        raise RuntimeError(
            f"Corrector {args.corrector} not found in matrix lists.\n"
            f"hcorrs={matrices['hcorrs']}\nvcorrs={matrices['vcorrs']}"
        )

    if is_v:
        j = matrices["vcorrs"].index(args.corrector)
        model_main = matrices["Ayy"][:, j]
        model_cross = matrices["Axy"][:, j]
        live_main = live["dOy_dbdes"]
        live_cross = live["dOx_dbdes"]
        main_name = "Ayy vs live dOy/dbdes"
        cross_name = "Axy vs live dOx/dbdes"
        print(f"Corrector {args.corrector} treated as V corrector at vcorrs index {j}")
    else:
        j = matrices["hcorrs"].index(args.corrector)
        model_main = matrices["Axx"][:, j]
        model_cross = matrices["Ayx"][:, j]
        live_main = live["dOx_dbdes"]
        live_cross = live["dOy_dbdes"]
        main_name = "Axx vs live dOx/dbdes"
        cross_name = "Ayx vs live dOy/dbdes"
        print(f"Corrector {args.corrector} treated as H corrector at hcorrs index {j}")

    stats_main = compare_vectors(model_main, live_main)
    stats_cross = compare_vectors(model_cross, live_cross)

    print()
    print("--- Main-plane comparison ---")
    print(main_name)
    print(f"corr = {stats_main['corr']:.6f}")
    print(f"scale model->live = {stats_main['scale_model_to_live']:.6f}")
    print(f"scale live->model = {stats_main['scale_live_to_model']:.6f}")
    print(f"RMS model = {stats_main['rms_model']:.6f}")
    print(f"RMS live = {stats_main['rms_live']:.6f}")
    print(f"RMS diff = {stats_main['rms_diff']:.6f}")

    print()
    print("--- Cross-plane comparison ---")
    print(cross_name)
    print(f"corr = {stats_cross['corr']:.6f}")
    print(f"scale model->live = {stats_cross['scale_model_to_live']:.6f}")
    print(f"scale live->model = {stats_cross['scale_live_to_model']:.6f}")
    print(f"RMS model = {stats_cross['rms_model']:.6f}")
    print(f"RMS live = {stats_cross['rms_live']:.6f}")
    print(f"RMS diff = {stats_cross['rms_diff']:.6f}")

    print()
    print("--- First 20 BPMs: model vs live (main plane) ---")
    for i, bpm in enumerate(bpms[:20]):
        print(f"{i:02d} {bpm:8s}  model={model_main[i]: .6f}  live={live_main[i]: .6f}")

    print()
    print("--- Matrix corrector order ---")
    print("hcorrs =", matrices["hcorrs"])
    print("vcorrs =", matrices["vcorrs"])

    if args.plot:
        plot_overlay(
            bpms=bpms,
            live_main=live_main,
            model_main=model_main,
            title_main=main_name,
            live_cross=live_cross,
            model_cross=model_cross,
            title_cross=cross_name,
        )