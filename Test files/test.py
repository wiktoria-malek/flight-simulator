import numpy as np
import math
import RF_Track as rft
import matplotlib.pyplot as plt

class Emitt_Meas_Simulation:
    def __init__(self):
        self.Pref=1.2999999e3
        self.lattice = rft.Lattice('../Ext_ATF2/ATF2_EXT_FF_v5.2.twiss')
        self.sequence = [ e.get_name() for e in self.lattice['*']]
        self.screens = [e.get_name() for e in self.lattice['*OTR*']]
        for s in self.lattice['*OTR*']:
            screen = rft.Screen()
            screen.set_name(s.get_name())
            s.replace_with(screen)

if __name__ == "__main__":
    w = Emitt_Meas_Simulation()
    print(w.sequence)