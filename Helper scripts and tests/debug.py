# import pickle
# from pprint import pprint
# #filename=("/Users/wiktoriamalek/CERN-Flight_Simulator-Data/EM_Data/EM_ATF2_Ext20260626_215117/states_QD18X/screen_0002_step_0001_shot_0000.pkl")
# filename = "/Users/wiktoriamalek/CERN-Flight_Simulator-Data/BBA_ATF2_Ext_RFT260812190259_session_settings/machine_status.pkl"
#
# with open(filename, "rb") as pickle_file:
#     data = pickle.load(pickle_file)
#
# pprint(data, width=120)


import numpy as np

nshots = 10 # 5
sigma_values = np.random.uniform(1,5, size=nshots)

sigma = np.nanmean(sigma_values)
std_sigma = np.std(sigma_values)
print(f"sigma: {sigma}")
print(f"std_sigma: {std_sigma}")

uncertainty = std_sigma/np.sqrt(nshots)
print(f"uncertainty: {uncertainty}")