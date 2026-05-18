import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

CURRENT_FILE = Path(__file__).resolve()
PROJECT_ROOT = CURRENT_FILE.parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from Interfaces.ATF2.InterfaceATF2_Ext_RFTrack import InterfaceATF2_Ext_RFTrack
from MachineLearning.ML_train import MLInterface, get_ml_model_file


MACHINE_NAME = "ATF2"
QUAD_NAME = "QD18X"
SCREENS = ["OTR0X", "OTR1X", "OTR2X", "OTR3X"]

EMIT_X_NORM = 5.26475
BETA_X0 = 1.12907
ALPHA_X0 = -0.784728

EMIT_Y_NORM = 0.0301546
BETA_Y0 = 10.5417
ALPHA_Y0 = -3.79125

N_K1_POINTS = 11
DELTA_MIN = -0.20
DELTA_MAX = 0.20
MANUAL_K1_0 = None


def get_nominal_k1(interface, quad_name):
    if MANUAL_K1_0 is not None:
        return float(MANUAL_K1_0)

    quad_data = interface.get_quadrupoles(names=[quad_name])
    if "bdes" not in quad_data or len(quad_data["bdes"]) == 0:
        raise RuntimeError(f"Could not read nominal K1 for {quad_name}.")
    return float(quad_data["bdes"][0])


def relative_error(reference, prediction):
    reference = np.asarray(reference, dtype=float)
    prediction = np.asarray(prediction, dtype=float)
    scale = np.maximum(np.abs(reference), 1e-12)
    return (prediction - reference) / scale


def print_summary(name, rf_values, ml_values):
    diff = ml_values - rf_values
    rel = relative_error(rf_values, ml_values)

    print(f"\n{name}")
    print("RFTrack:")
    print(rf_values)
    print("ML:")
    print(ml_values)
    print("ML - RFTrack:")
    print(diff)
    print("relative error:")
    print(rel)
    print(f"MAE      = {np.nanmean(np.abs(diff)):.6g}")
    print(f"RMSE     = {np.sqrt(np.nanmean(diff ** 2)):.6g}")
    print(f"max abs  = {np.nanmax(np.abs(diff)):.6g}")
    print(f"max rel  = {np.nanmax(np.abs(rel)):.6g}")


def plot_comparison(k1_values, rf_values, ml_values, plane_name):
    for screen_index, screen_name in enumerate(SCREENS):
        plt.figure()
        plt.plot(k1_values, rf_values[:, screen_index], marker="o", label="RFTrack")
        plt.plot(k1_values, ml_values[:, screen_index], marker="x", label="ML")
        plt.xlabel("K1")
        plt.ylabel(f"sigma {plane_name}")
        plt.title(f"{plane_name} response at {screen_name}")
        plt.legend()
        plt.grid(True)


def main():
    print("Creating RFTrack interface...")
    interface = InterfaceATF2_Ext_RFTrack()

    k1_0 = get_nominal_k1(interface, QUAD_NAME)
    deltas = np.linspace(DELTA_MIN, DELTA_MAX, N_K1_POINTS)
    k1_values = k1_0 * (1.0 + deltas)

    model_file = get_ml_model_file(MACHINE_NAME, QUAD_NAME, SCREENS)
    print(f"Machine      : {MACHINE_NAME}")
    print(f"Quadrupole   : {QUAD_NAME}")
    print(f"Screens      : {SCREENS}")
    print(f"K1_0         : {k1_0}")
    print(f"K1_values    : {k1_values}")
    print(f"ML model file: {model_file}")

    if not model_file.exists():
        raise FileNotFoundError(f"ML model file not found: {model_file}")

    print("Loading ML interface...")
    ml_interface = MLInterface(
        interface,
        quad_name=QUAD_NAME,
        screens=SCREENS,
        machine_name=MACHINE_NAME,
    )

    print("Running RFTrack forward prediction...")
    rf_sigx, rf_sigy = interface.predict_emittance_scan_response(
        quad_name=QUAD_NAME,
        screens=SCREENS,
        K1_values=k1_values,
        emit_x=EMIT_X_NORM,
        emit_y=EMIT_Y_NORM,
        beta_x0=BETA_X0,
        beta_y0=BETA_Y0,
        alpha_x0=ALPHA_X0,
        alpha_y0=ALPHA_Y0,
        reference_screen=SCREENS[0],
    )

    print("Running ML forward prediction...")
    ml_sigx, ml_sigy = ml_interface.predict_emittance_scan_response(
        quad_name=QUAD_NAME,
        screens=SCREENS,
        K1_values=k1_values,
        emit_x=EMIT_X_NORM,
        emit_y=EMIT_Y_NORM,
        beta_x0=BETA_X0,
        beta_y0=BETA_Y0,
        alpha_x0=ALPHA_X0,
        alpha_y0=ALPHA_Y0,
        reference_screen=SCREENS[0],
    )

    rf_sigx = np.asarray(rf_sigx, dtype=float)
    rf_sigy = np.asarray(rf_sigy, dtype=float)
    ml_sigx = np.asarray(ml_sigx, dtype=float)
    ml_sigy = np.asarray(ml_sigy, dtype=float)

    print_summary("Horizontal sigma comparison", rf_sigx, ml_sigx)
    print_summary("Vertical sigma comparison", rf_sigy, ml_sigy)

    plot_comparison(k1_values, rf_sigx, ml_sigx, "x")
    plot_comparison(k1_values, rf_sigy, ml_sigy, "y")
    plt.show()


if __name__ == "__main__":
    main()

