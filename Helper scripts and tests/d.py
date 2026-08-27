import pickle as pkl

filename_yesterday = "/local/home/clearop/CERN-Flight_Simulator-Data/CLEAR_20260827_143547_Kicker_Dispersion"
filename_today = "/local/home/clearop/CERN-Flight_Simulator-Data/CLEAR_20260826_150028_Kicker_Dispersion"

with open(filename, "rb") as pickle_file:
    data = pickle.load(pickle_file)