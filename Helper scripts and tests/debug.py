import pickle
from pprint import pprint
filename=("/Users/wiktoriamalek/CERN-Flight_Simulator-Data/EM_Data/EM_ATF2_Ext20260626_215117/states_QD18X/screen_0002_step_0001_shot_0000.pkl")


with open(filename, "rb") as pickle_file:
    data = pickle.load(pickle_file)

pprint(data, width=120)
