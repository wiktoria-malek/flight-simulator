import RF_Track as rft
import numpy as np
import os

wake_data_directory = os.path.join(os.path.dirname(__file__), "Ext_ATF2", "WakeData")

T = rft.Bunch6d_twiss()
T.emitt_x = 5.2
T.emitt_y = 0.03
T.beta_x  = 6.8
T.beta_y  = 2.9
T.alpha_x = 0.0
T.alpha_y = 0.0
T.sigma_t = 8
T.sigma_pt = 0.8

Pref = 1.3e3
population = 2e10
Q = -1
nparticles = 20000
B0 = rft.Bunch6d_QR(rft.electronmass, population, Q, Pref, T, nparticles)

lat = rft.Lattice()
d = rft.Drift(1.0)
d.set_name("D1")
lat.append(d)

hz = 1e-3  # m
s = -np.arange(0, 200) * hz
Wt = 1e6 * np.exp(s / (20*hz))
Wl = np.zeros_like(Wt)

WF = rft.Wakefield_1d(Wt, Wl, hz)
lat["D1"].add_collective_effect(WF)

lat["D1"].set_cfx_nsteps(20)

I0 = B0.get_info()
B = B0.displaced(5*I0.sigma_x, 0.0, 0, 0, 0, 0, 0)

m0 = B.get_phase_space("%xp")
B1 = lat.track(B)
m1 = B1.get_phase_space("%xp")

print("mean xp before:", float(np.mean(m0)))
print("mean xp after :", float(np.mean(m1)))
print("delta mean xp :", float(np.mean(m1) - np.mean(m0)))

for file in os.listdir(wake_data_directory):
    if file.endswith(".dat"):
        print("file :", file)