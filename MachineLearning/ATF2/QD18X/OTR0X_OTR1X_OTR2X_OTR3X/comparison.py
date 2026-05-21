# import numpy as np
# loader = np.load('./EM_dataset_100k.npz')
#
# print(loader.files)
#
# print("X=",loader["X"])
# print("Y=",loader["Y"])


import numpy as np
from MachineLearning.ML_train import MLInterface
from Interfaces.ATF2.InterfaceATF2_Ext_RFTrack import InterfaceATF2_Ext_RFTrack

sim = InterfaceATF2_Ext_RFTrack()
ml = MLInterface(sim, quad_name="QD18X",
                 screens=["OTR0X","OTR1X","OTR2X","OTR3X"],
                 machine_name="ATF2")

K1_nom = -3.4565
K1_grid = K1_nom * (1 + np.linspace(-0.25, 0.25, 5))
truth = dict(emit_x=5.2, beta_x0=1.105221776, alpha_x0=-0.7752115812,
             emit_y=0.03, beta_y0=10.34240856, alpha_y0=-3.739163822)

sx_sim, sy_sim = sim.predict_emittance_scan_response(
    quad_name="QD18X", screens=["OTR0X","OTR1X","OTR2X","OTR3X"],
    K1_values=K1_grid, reference_screen="OTR0X", **truth)
sx_ml, sy_ml = ml.predict_emittance_scan_response(
    quad_name="QD18X", screens=["OTR0X","OTR1X","OTR2X","OTR3X"],
    K1_values=K1_grid, reference_screen="OTR0X", **truth)

print("sigx_sim:\n", sx_sim)
print("sigx_ml:\n", sx_ml)
print("rel_err sigx %:\n", (sx_ml - sx_sim)/sx_sim * 100)
print("sigy_sim:\n", sy_sim)
print("sigy_ml:\n", sy_ml)
print("rel_err sigy %:\n", (sy_ml - sy_sim)/sy_sim * 100)