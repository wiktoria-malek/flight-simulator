import pickle
import numpy as np
f = pickle.load(open("/Users/wiktoriamalek/flight-simulator-data/ATF2_Linac_20251202_051813_Dispersion/DATA_ZH1L_p0000.pkl", "rb"))

bxp = np.asarray(f["bpms"]["x"])
names = list(map(str, f["bpms"]["names"]))

print("names:", names, len(names))
print("bxp.shape:", bxp.shape)
