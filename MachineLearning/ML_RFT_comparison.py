import sys
from pathlib import Path
import joblib
import numpy as np

THIS_FILE = Path(__file__).resolve()
PROJECT_ROOT = THIS_FILE.parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from Interfaces.ATF2.InterfaceATF2_Ext_RFTrack import InterfaceATF2_Ext_RFTrack

MODEL_FILE = PROJECT_ROOT / "MachineLearning" / "EM_model.joblib"

QUAD_NAME = "QD18X"
SCREENS = ["OTR0X", "OTR1X", "OTR2X", "OTR3X"]

interface = InterfaceATF2_Ext_RFTrack(nparticles=2000)

quads = interface.get_quadrupoles()
K1_0 = float(quads["bdes"][list(quads["names"]).index(QUAD_NAME)])

params = {
    "emit_x": 5.0,
    "beta_x0": 2.0,
    "alpha_x0": -1.0,
    "emit_y": 0.03,
    "beta_y0": 5.0,
    "alpha_y0": 1.0,
}

K1_values = K1_0 * np.linspace(0.9, 1.1, 5)

rf_sigx, rf_sigy = interface.predict_emittance_scan_response(
    quad_name=QUAD_NAME,
    screens=SCREENS,
    K1_values=K1_values,
    reference_screen=SCREENS[0],
    **params,
)

payload = joblib.load(MODEL_FILE)
model = payload["model"]

X = []
for K1 in K1_values:
    X.append([
        params["emit_x"],
        params["beta_x0"],
        params["alpha_x0"],
        params["emit_y"],
        params["beta_y0"],
        params["alpha_y0"],
        K1,
    ])

Y_ml = model.predict(np.array(X))

ml_sigx = Y_ml[:, :len(SCREENS)]
ml_sigy = Y_ml[:, len(SCREENS):]

print("\nRF sigx:")
print(rf_sigx)

print("\nML sigx:")
print(ml_sigx)

print("\nRF sigy:")
print(rf_sigy)

print("\nML sigy:")
print(ml_sigy)

print("\nAbsolute error sigx:")
print(np.abs(rf_sigx - ml_sigx))

print("\nAbsolute error sigy:")
print(np.abs(rf_sigy - ml_sigy))

print("\nMean abs error sigx:", np.mean(np.abs(rf_sigx - ml_sigx)))
print("Mean abs error sigy:", np.mean(np.abs(rf_sigy - ml_sigy)))