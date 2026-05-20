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
RANDOM_SEED = 2137

PARAMETER_NAMES = [
    "emit_x_norm",
    "beta_x0",
    "alpha_x0",
    "emit_y_norm",
    "beta_y0",
    "alpha_y0",
    "K1",
]

N_K1_PER_TWISS = 11

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

def build_k1_set(rng, K1_nominal, relative_k_change, number_of_k1_per_twiss_set, jitter_fraction=0.05):
    delta_min = float(relative_k_change[0])
    delta_max = float(relative_k_change[1])
    number_of_k1_per_twiss_set = int(number_of_k1_per_twiss_set)

    if number_of_k1_per_twiss_set <= 1:
        relative_values = np.array([float(rng.uniform(delta_min, delta_max))], dtype=float)
    else:
        relative_values = np.linspace(delta_min, delta_max, number_of_k1_per_twiss_set, dtype=float)
        if jitter_fraction > 0:
            step = (delta_max - delta_min) / max(number_of_k1_per_twiss_set - 1, 1)
            relative_values += rng.uniform(-jitter_fraction * step, jitter_fraction * step, size = relative_values.shape)
            relative_values = np.clip(relative_values, delta_min, delta_max)
            relative_values[0] = delta_min
            relative_values[-1] = delta_max
    return K1_nominal * (1.0 + relative_values)

def generate_dataset(quad_name, screens, interface, k1_relative_change, n_samples, output_file, log_callback, progress_callback, stop_checker):
    rng = np.random.default_rng(RANDOM_SEED)
    log = log_callback if callable(log_callback) else print
    n_samples = int(n_samples)
    output_file = Path(output_file)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    K1_nominal = get_nominal_K1(interface, quad_name)
    bounds = _get_interface_bounds(interface)

    n_k1_per_twiss_set = min(N_K1_PER_TWISS, max(1, n_samples))
    n_twiss_combinations = max(1, int(np.ceil(n_samples / n_k1_per_twiss_set)))
    n_total = n_k1_per_twiss_set * n_twiss_combinations

    log(f"{quad_name} nominal K1: {K1_nominal}")
    log(f"Generating {n_samples} rows with {n_twiss_combinations} twiss combinations and {n_k1_per_twiss_set} K1s per sample.")
    log(f"Screens: {screens}")
    log(f"K1 relative change: {k1_relative_change}")
    log(f"Output file: {output_file}")

    X = []
    Y = []
    failed = 0
    processed_rows = 0
    t0 = time.perf_counter()

    for twiss_combination in range(n_twiss_combinations):
        if callable(stop_checker) and stop_checker():
            log("Dataset generation stopped by user.")
            break
        twiss_parameters = build_sample(rng, K1_nominal, bounds, k1_relative_change)
        emit_x_norm, beta_x0, alpha_x0, emit_y_norm, beta_y0, alpha_y0, _ = twiss_parameters
        K1_array = build_k1_set(rng, K1_nominal, k1_relative_change, n_k1_per_twiss_set)
        try:
            pred_sigx, pred_sigy = interface.predict_emittance_scan_response(
                quad_name=quad_name,
                screens=screens,
                K1_values=np.asarray(K1_array, dtype=float),
                emit_x=emit_x_norm,
                emit_y=emit_y_norm,
                beta_x0=beta_x0,
                alpha_x0=alpha_x0,
                beta_y0=beta_y0,
                alpha_y0=alpha_y0,
                reference_screen=screens[0],
                stop_checker=None,
            )
            required_shape = (len(K1_array), len(screens))
            if pred_sigx.shape != required_shape or pred_sigy.shape != required_shape:
                raise RuntimeError(f"Shapes are mismatched.")

            for k_idx, K1 in enumerate(K1_array):
                parameters = np.array([emit_x_norm, beta_x0, alpha_x0, emit_y_norm, beta_y0, alpha_y0, float(K1)], dtype=float)
                sigma2 = np.concatenate([pred_sigx[k_idx,:]**2, pred_sigy[k_idx,:]**2]).astype(float)

                if not (np.all(np.isfinite(parameters)) and np.all(np.isfinite(sigma2))):
                    continue

                X.append(parameters)
                Y.append(sigma2)
                processed_rows += 1

        except Exception as e:
            failed += 1
            log(f"Twiss combination {twiss_combination+1} failed due to {e}")

        if callable(progress_callback):
            progress_callback(min(processed_rows, n_samples), n_samples)
        if (twiss_combination + 1) % 50 == 0 or twiss_combination == 0:
            elapsed = time.perf_counter() - t0
            log(f"Elapsed time: {elapsed:.2f} seconds = {elapsed / 60:.2f} minutes = {elapsed / 3600} hours")
            log(f"{twiss_combination + 1}/{n_twiss_combinations} Twiss combinations processed")
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
        sigma_names=np.array([f"sigx2_{screen}" for screen in screens] + [f"sigy2_{screen}" for screen in screens]),
        screens=np.array(screens),
        quad_name=np.array(quad_name),
        reference_screen=np.array(screens[0]),
        K1_relative_change=np.array(k1_relative_change, dtype=float),
        bounds=np.array([bounds[name] for name in PARAMETER_NAMES[:-1]], dtype=float),
        bounds_names=np.array(PARAMETER_NAMES[:-1]),
        interface_class_name=np.array(interface.__class__.__name__),
        interface_module=np.array(interface.__class__.__module__),
        K1_nominal=np.array(K1_nominal, dtype=float),
        n_requested_samples = np.array(n_samples, dtype=int),
        n_twiss_combinations = np.array(n_twiss_combinations, dtype=int),
        n_k1_per_twiss_set = np.array(n_k1_per_twiss_set, dtype=int),
    )

    log("Done.")
    log(f"Saved dataset to: {output_file}")
    log(f"X shape: {X.shape}")
    log(f"Y shape: {Y.shape}")
    log(f"Failed Twiss combinations: {failed}")

    return {
        "output_file": str(output_file),
        "X_shape": X.shape,
        "Y_shape": Y.shape,
        "failed": int(failed),
        "valid": int(X.shape[0]),
        "n_twiss_combinations": int(n_twiss_combinations),
        "n_k1_per_twiss_set": int(n_k1_per_twiss_set),
    }
