import pickle as pkl
import pprint
filename_yesterday = "/local/home/clearop/CERN-Flight_Simulator-Data/CLEAR_20260827_143547_Kicker_Dispersion"
filename_today = "/local/home/clearop/CERN-Flight_Simulator-Data/CLEAR_20260826_150028_Kicker_Dispersion"

print("Yesterday: =========================")
with open(filename_yesterday, "rb") as pickle_file:
    data = pickle.load(pickle_file)
pprint(data)
print("=========================")

print("Today: =========================")
with open(filename_today, "rb") as pickle_file:
    data = pickle.load(pickle_file)
pprint(data)
print("=========================")


