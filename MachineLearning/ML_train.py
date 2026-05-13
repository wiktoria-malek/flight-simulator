'''
MAE - mean absolute error
RMSE - root mean squared error
R2 - score of fit quality. Best is 1.0

Input dataset is in MachineLearning/EM_dataset.npz

The model learns:
[emitx_norm, beta_x0, alpha_x0, emit_y_norm, beta_y0, alpha_y0, K1]
->
[sigx_OTR0X, sigx_OTR1X, sigx_OTR2X, sigx_OTR3X,
sigy_OTR0X, sigy_OTR1X, sigy_OTR2X, sigy_OTR3X]

'''

import sys, joblib
from pathlib import Path
import numpy as np
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.neural_network import MLPRegressor # multi-layer perceptron
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

CURRENT_FILE = Path(__file__).resolve()
PROJECT_ROOT = CURRENT_FILE.parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

DATASET_FILE = PROJECT_ROOT / "MachineLearning" / "EM_dataset.npz"
MODEL_FILE = PROJECT_ROOT / "MachineLearning" / "EM_model.joblib"

RANDOM_SEED = 12345
TEST_SIZE = 0.2

def main():
    if not DATASET_FILE.exists():
        raise FileNotFoundError(f"{DATASET_FILE} not found")
    data = np.load(DATASET_FILE, allow_pickle=True)
    X = np.asarray(data["X"], dtype=float)
    Y = np.asarray(data["Y"], dtype=float)

    param_names = [str(x) for x in data["param_names"]] if "param_names" in data.files else []
    sigma_names = [str(x) for x in data["sigma_names"]] if "sigma_names" in data.files else []

    if X.ndim != 2 or Y.ndim != 2:
        raise RuntimeError(f"Wrong shape for X or Y:  X= {X.shape} or Y= {Y.shape}")
    if X.shape[0] != Y.shape[0]:
        raise RuntimeError(f"X and Y must have the same number of samples")

    print("Loading data...")
    if param_names:
        print(f"Parameter names: {param_names}")
        print(f"sigma names: {sigma_names}")

    X_train, X_test, Y_train, Y_test = train_test_split(X, Y, test_size=TEST_SIZE, random_state=RANDOM_SEED)
    model = Pipeline([
        ("x_scaler", StandardScaler()),
        ("mlp", MLPRegressor(
            hidden_layer_sizes=(128, 128, 64),
            activation="relu",
            solver="adam",
            alpha=1e-5,
            learning_rate_init=1e-3,
            max_iter=3000,
            random_state=RANDOM_SEED,
            early_stopping=True,
            verbose=True,
            validation_fraction=0.15,
            n_iter_no_change=80,
        ) ),
    ])

    print("Training model...")
    model.fit(X_train, Y_train)
    Y_pred = model.predict(X_test)

    MAE = mean_absolute_error(Y_test, Y_pred)
    RMSE = np.sqrt(mean_squared_error(Y_test, Y_pred))
    R2 = r2_score(Y_test, Y_pred)

    print("Test quality:")
    print(f"MAE: {MAE}")
    print(f"RMSE: {RMSE}")
    print(f"R2: {R2}")

    print("Quality of each beam size:")
    for i in range(Y.shape[1]):
        name = sigma_names[i] if i < len(sigma_names) else f"sigma_{i}"
        sigma_mae = mean_absolute_error(Y_test[:, i], Y_pred[:, i])
        sigma_rmse = np.sqrt(mean_squared_error(Y_test[:, i], Y_pred[:, i]))
        sigma_r2 = r2_score(Y_test[:, i], Y_pred[:, i])

        print(f"{name}")
        print(f"MAE: {sigma_mae}")
        print(f"RMSE: {sigma_rmse}")
        print(f"R2: {sigma_r2}")

    result = {
        "model": model,
        "param_names": param_names,
        "sigma_names": sigma_names,
        "dataset_file": str(DATASET_FILE),
        "metrics": {
            "MAE": float(MAE),
            "RMSE": float(RMSE),
            "R2": float(R2),
        }
    }

    joblib.dump(result, MODEL_FILE)
    print("Done.")
    print(f"Saved model to {MODEL_FILE}")

if __name__ == "__main__":
    main()