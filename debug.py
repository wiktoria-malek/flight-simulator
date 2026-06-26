import pickle

filename=("/Users/wiktoriamalek/CERN-Flight_Simulator-Data/EM_ATF2_Ext_RFT20260626_181248/states_QD18X/screen_0000_step_0000_shot_0000.pkl")
with open(filename, "rb") as pickle_file:
    data = pickle.load(pickle_file)

print(data)
print(data)