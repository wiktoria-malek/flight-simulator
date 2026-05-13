'''
Learns what is currently done by interface.predict_emittance_scan_response()

Input parameters per sample:
emit_x_norm, beta_x0, alpha_x0,
emit_y_norm, beta_y0, alpha_y0,
K1

Output targets per sample:
sigx on selected screens + sigy on selected screens
'''

import sys
import time
from pathlib import Path

import numpy as np

THIS_FILE = Path(__file__).resolve()
PROJECT_ROOT = THIS_FILE.parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from Interfaces.ATF2.InterfaceATF2_Ext_RFTrack import InterfaceATF2_Ext_RFTrack

OUTPUT_FILE = PROJECT_ROOT / "MachineLearning" / "EM_dataset.npz"

QUAD_NAME = "QD18X"
SCREENS = ["OTR0X", "OTR1X", "OTR2X", "OTR3X"]
REFERENCE_SCREEN = SCREENS[0]

N_SAMPLES = 2000
RANDOM_SEED = 12345

BOUNDS =  {
                    "emit_x_norm": [0.5, 8.0],
                    "beta_x0": [0.2, 5.0],
                    "alpha_x0": [-4.0, 2.0],
                    "emit_y_norm": [0.005, 0.12],
                    "beta_y0": [2.0, 20.0],
                    "alpha_y0": [-8.0, 2.0],
                }


K1_RELATIVE_CHANGE = (-0.30, 0.30)

def samples_uniform(rng,name):
    low, high = BOUNDS[name]
    return float(rng.uniform(low, high))


def get_nominal_K1(interface, quad_name):
    quads = interface.get_quadrupoles()
    names = list(quads["names"])
    strengths = np.asarray(quads["bdes"], dtype=float)
    if quad_name not in names:
        raise RuntimeError(f"Quad {quad_name} not present in interface. Available examples: {names[:10]}")
    return float(strengths[names.index(quad_name)])

def build_sample(rng, K1_nominal):
    emit_x_norm = samples_uniform(rng, "emit_x_norm")
    beta_x0 = samples_uniform(rng, "beta_x0")
    alpha_x0 = samples_uniform(rng, "alpha_x0")
    emit_y_norm = samples_uniform(rng, "emit_y_norm")
    beta_y0 = samples_uniform(rng, "beta_y0")
    alpha_y0 = samples_uniform(rng, "alpha_y0")

    K1_delta = float(rng.uniform(K1_RELATIVE_CHANGE[0], K1_RELATIVE_CHANGE[1]))
    K1 = float(K1_nominal*(1.0+K1_delta))
    parameters = np.array([
        emit_x_norm, beta_x0, alpha_x0,
        emit_y_norm, beta_y0, alpha_y0,
        K1,
    ], dtype=float)

    return parameters

def main():
    rng = np.random.default_rng(RANDOM_SEED)
    interface = InterfaceATF2_Ext_RFTrack(nparticles=2000)
    K1_nominal = get_nominal_K1(interface, QUAD_NAME)
    print(f"{QUAD_NAME} nominal K1: {K1_nominal}")
    print(f"Generating {N_SAMPLES} samples")

    X = []
    Y = []
    failed = 0
    t0 = time.perf_counter()

    for i in range(N_SAMPLES):
        parameters = build_sample(rng, K1_nominal)
        emit_x_norm, beta_x0, alpha_x0, emit_y_norm, beta_y0, alpha_y0, K1 = parameters
        try:
            pred_sigx, pred_sigy = interface.predict_emittance_scan_response(quad_name=QUAD_NAME,
                                    screens=SCREENS, K1_values = np.array([K1], dtype=float),
                                    emit_x = emit_x_norm, emit_y = emit_y_norm, beta_x0 = beta_x0, alpha_x0 = alpha_x0,
                                    beta_y0 = beta_y0, alpha_y0 = alpha_y0, reference_screen = REFERENCE_SCREEN, stop_checker = None)
            pred_sigx = np.asarray(pred_sigx, dtype=float)
            pred_sigy = np.asarray(pred_sigy, dtype=float)

            if pred_sigx.shape != (1, len(SCREENS)) or pred_sigy.shape != (1, len(SCREENS)):
                raise RuntimeError(f"Shapes are inconsistent with sigx = {pred_sigx.shape} and sigy = {pred_sigy.shape}")
            sigma = np.concatenate([pred_sigx[0, :], pred_sigy[0, :]]).astype(float)
            if not (np.all(np.isfinite(parameters)) and np.all(np.isfinite(sigma))):
                raise RuntimeError("Parameters or sigmas are not finite.")
            X.append(parameters)
            Y.append(sigma)
        except Exception as e:
            failed += 1
            print(f"Sample {i} failed due to {e}")

        if (i+1) % 50 == 0 or i ==0:
            elapsed = time.perf_counter() - t0
            print(f"Elapsed time: {elapsed} seconds = {elapsed/60} minutes")
            print(f"{i + 1}/{N_SAMPLES} samples processed")
            print(f"{len(X)} samples are valid")
            print(f"{failed} samples failed")

    X = np.asarray(X, dtype=float)
    Y = np.asarray(Y, dtype=float)

    if X.size == 0 or Y.size == 0:
        raise RuntimeError("X and Y are empty")

    np.savez(
        OUTPUT_FILE,
        X=X,
        Y=Y,
        param_names=np.array([
            "emit_x_norm",
            "beta_x0",
            "alpha_x0",
            "emit_y_norm",
            "beta_y0",
            "alpha_y0",
            "K1",
        ]),
        sigma_names=np.array([f"sigx_{screen}" for screen in SCREENS] + [f"sigy_{screen}" for screen in SCREENS]),
        screens=np.array(SCREENS),
        quad_name=np.array(QUAD_NAME),
        reference_screen=np.array(REFERENCE_SCREEN),
        K1_relative_change=np.array(K1_RELATIVE_CHANGE, dtype=float),
    )

    print("Done.")
    print(f"Saved dataset to: {OUTPUT_FILE}")
    print(f"X shape: {X.shape}")
    print(f"Y shape: {Y.shape}")
    print(f"Failed samples: {failed}")



if __name__ == "__main__":
    main()
