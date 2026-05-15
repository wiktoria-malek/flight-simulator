'''
Learns what is currently done by interface.predict_emittance_scan_response()

Input parameters per sample:
emit_x_norm, beta_x0, alpha_x0,
emit_y_norm, beta_y0, alpha_y0,
K1

Output targets per sample:
sigx on selected screens + sigy on selected screens
'''

import sys, time
from pathlib import Path
from Interfaces.interface_setup import INTERFACE_SETUP
import numpy as np

THIS_FILE = Path(__file__).resolve()
PROJECT_ROOT = THIS_FILE.parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

OUTPUT_FILE = PROJECT_ROOT / "MachineLearning" / "EM_dataset.npz"
N_SAMPLES = 2000
RANDOM_SEED = 12345

PARAMETER_NAMES = [
    "emit_x_norm",
    "beta_x0",
    "alpha_x0",
    "emit_y_norm",
    "beta_y0",
    "alpha_y0",
    "K1",
]

def _get_interface_initial_settings(interface):
    interface_class_name = interface.__class__.__name__
    interface_module_name = interface.__class__.__module__

    for machine_name, machine_interfaces in INTERFACE_SETUP.items():
        for interface_defaults in machine_interfaces:
            if (interface_defaults.get("class_name") == interface_class_name) and (
                    interface_defaults.get("module") == interface_module_name):
                result = dict(interface_defaults)
                result["machine"] = machine_name
                return result
    return None

def _get_interface_bounds(interface):
    interface_defaults =_get_interface_initial_settings(interface)
    if interface_defaults is None:
        return {}
    return dict(interface_defaults.get("bounds", {}))

def samples_uniform(rng, bounds, name):
    low, high = bounds[name]
    return float(rng.uniform(low, high))

def get_nominal_K1(interface, quad_name):
    quads = interface.get_quadrupoles()
    names = list(quads["names"])
    strengths = np.asarray(quads["bdes"], dtype=float)
    if quad_name not in names:
        raise RuntimeError(f"Quad {quad_name} not present in interface. Available examples: {names[:10]}")
    return float(strengths[names.index(quad_name)])

def build_sample(rng, K1_nominal, bounds, relative_k_change):
    emit_x_norm = samples_uniform(rng, bounds, "emit_x_norm")
    beta_x0 = samples_uniform(rng, bounds, "beta_x0")
    alpha_x0 = samples_uniform(rng, bounds, "alpha_x0")
    emit_y_norm = samples_uniform(rng, bounds, "emit_y_norm")
    beta_y0 = samples_uniform(rng, bounds, "beta_y0")
    alpha_y0 = samples_uniform(rng, bounds, "alpha_y0")
    K1_delta = float(rng.uniform(relative_k_change[0], relative_k_change[1]))
    K1 = float(K1_nominal*(1.0+K1_delta))
    parameters = np.array([
        emit_x_norm, beta_x0, alpha_x0,
        emit_y_norm, beta_y0, alpha_y0,
        K1,
    ], dtype=float)

    return parameters



def generate_dataset(quad_name, screens, interface, k1_relative_change, n_samples, output_file, log_callback, progress_callback, stop_checker):
    rng = np.random.default_rng(RANDOM_SEED)
    log = log_callback if callable(log_callback) else print
    n_samples = int(n_samples)
    output_file = Path(output_file)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    K1_nominal = get_nominal_K1(interface, quad_name)
    bounds = _get_interface_bounds(interface)
    log(f"{quad_name} nominal K1: {K1_nominal}")
    log(f"Generating {n_samples} samples")
    log(f"Screens: {screens}")
    log(f"K1 relative change: {k1_relative_change}")
    log(f"Output file: {output_file}")

    X = []
    Y = []
    failed = 0
    t0 = time.perf_counter()

    for i in range(n_samples):
        if callable(stop_checker) and stop_checker():
            log("Dataset generation stopped by user.")
            break
        parameters = build_sample(rng, K1_nominal, bounds, k1_relative_change)
        emit_x_norm, beta_x0, alpha_x0, emit_y_norm, beta_y0, alpha_y0, K1 = parameters
        try:
            pred_sigx, pred_sigy = interface.predict_emittance_scan_response(
                quad_name=quad_name,
                screens=screens,
                K1_values=np.array([K1], dtype=float),
                emit_x=emit_x_norm,
                emit_y=emit_y_norm,
                beta_x0=beta_x0,
                alpha_x0=alpha_x0,
                beta_y0=beta_y0,
                alpha_y0=alpha_y0,
                reference_screen=screens[0],
                stop_checker=None,
            )
            pred_sigx = np.asarray(pred_sigx, dtype=float)
            pred_sigy = np.asarray(pred_sigy, dtype=float)

            if pred_sigx.shape != (1, len(screens)) or pred_sigy.shape != (1, len(screens)):
                raise RuntimeError(f"Shapes are inconsistent with sigx = {pred_sigx.shape} and sigy = {pred_sigy.shape}")
            sigma = np.concatenate([pred_sigx[0, :], pred_sigy[0, :]]).astype(float)
            if not (np.all(np.isfinite(parameters)) and np.all(np.isfinite(sigma))):
                raise RuntimeError("Parameters or sigmas are not finite.")
            X.append(parameters)
            Y.append(sigma)
        except Exception as e:
            failed += 1
            log(f"Sample {i+1} failed due to {e}")

        if callable(progress_callback):
            progress_callback(i + 1, n_samples)
        if (i + 1) % 50 == 0 or i == 0:
            elapsed = time.perf_counter() - t0
            log(f"Elapsed time: {elapsed:.2f} seconds = {elapsed / 60:.2f} minutes")
            log(f"{i + 1}/{n_samples} samples processed")
            log(f"{len(X)} samples are valid")
            log(f"{failed} samples failed")

    X = np.asarray(X, dtype=float)
    Y = np.asarray(Y, dtype=float)

    if X.size == 0 or Y.size == 0:
        raise RuntimeError("X and Y are empty")

    np.savez(
        output_file,
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
        sigma_names=np.array([f"sigx_{screen}" for screen in screens] + [f"sigy_{screen}" for screen in screens]),
        screens=np.array(screens),
        quad_name=np.array(quad_name),
        reference_screen=np.array(screens[0]),
        K1_relative_change=np.array(k1_relative_change, dtype=float),
        bounds=np.array([bounds[name] for name in PARAMETER_NAMES[:-1]], dtype=float),
        bounds_names=np.array(PARAMETER_NAMES[:-1]),
        interface_class_name=np.array(interface.__class__.__name__),
        interface_module=np.array(interface.__class__.__module__),
    )

    log("Done.")
    log(f"Saved dataset to: {output_file}")
    log(f"X shape: {X.shape}")
    log(f"Y shape: {Y.shape}")
    log(f"Failed samples: {failed}")

    return {
        "output_file": str(output_file),
        "X_shape": X.shape,
        "Y_shape": Y.shape,
        "failed": int(failed),
        "valid": int(X.shape[0]),
    }
