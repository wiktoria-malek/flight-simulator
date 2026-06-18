from epics import PV, ca, caget
from Interfaces.ATF2.InterfaceATF2_DR import InterfaceATF2_DR
import numpy as np

I = InterfaceATF2_DR(nsamples= 10)

# Reading initial BPM readings
bmps0 = I.get_bmps()

# Changing the energy
dP_P = self.interface.change_energy()

# Reading BPM readings after changing the energy
bmps1 = I.get_bmps()

# Resetting the energy
I.reset_energy()

x0 = np.mean(bmps0["x"], axis=0)
y0 = np.mean(bmps0["y"], axis=0)

x1 = np.mean(bmps1["x"], axis=0)
y1 = np.mean(bmps1["y"], axis=0)

Dx = (x1 - x0) / dP_P
Dy = (y1 - y0) / dP_P

for bpm, dx, dy in zip(bpms0["names"], Dx, Dy):
    print(f"BPM: {bpm}, Dx: {dx}, Dy: {dy}")
print("Arc dispersion =", I.get_arc_dispersion())
