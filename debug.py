import pickle

filename=("/Users/wiktoriamalek/CERN-Flight_Simulator-Data/EmittanceMeasurement_ATF2_Ext_RFT260707103618_session/emittance_session.pkl")
with open(filename, "rb") as pickle_file:
    data = pickle.load(pickle_file)

print(data)
