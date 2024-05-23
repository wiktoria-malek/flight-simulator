import sys
sys.path.append('/userhome/alatina/flight-simulator')

from State import State
from Response import Response
import matplotlib.pyplot as plt
import numpy as np
import glob
import json
import os

# Use glob to get the list of DATA files
datafiles = glob.glob('DATA*.json')

# Prepare for computation
S = State(datafiles[0])
sequence = S.get_sequence()
correctors = S.get_correctors()['names']

# Pick all bpms following the first corrector
bpms = [ bpm for bpm in S.get_bpms()['names'] if sequence.index(bpm) > sequence.index(correctors[0]) ]

# Pick all correctors preceding the last bpm
hcorrs = [ corr for corr in S.get_hcorrectors_names() if sequence.index(corr) < sequence.index(bpms[-1]) ]
vcorrs = [ corr for corr in S.get_vcorrectors_names() if sequence.index(corr) < sequence.index(bpms[-1]) ]

# Read all orbits
Bx = np.empty((0,len(bpms)))
By = np.empty((0,len(bpms)))
Cx = np.empty((0,len(hcorrs)))
Cy = np.empty((0,len(vcorrs)))
datafiles_p = [f for f in datafiles if f[-10] == 'p']
for datafile_p in datafiles_p:
    datafile_m = datafile_p[:-10] + 'm' + datafile_p[-9:]
    if os.path.exists(datafile_m):
        Sp = State(datafile_p)
        Sm = State(datafile_m)
        Op = Sp.get_orbit (bpms)
        Om = Sm.get_orbit (bpms)
        Cx_p = Sp.get_correctors(hcorrs)['bact']
        Cy_p = Sp.get_correctors(vcorrs)['bact']
        Cx_m = Sm.get_correctors(hcorrs)['bact']
        Cy_m = Sm.get_correctors(vcorrs)['bact']
        if 0:
            O_x = Op['x'] - Om['x']
            O_y = Op['y'] - Om['y']
            C_x = Cx_p - Cx_m
            C_y = Cy_p - Cy_m
            Bx = np.vstack((Bx, O_x))
            By = np.vstack((By, O_y))
            Cx = np.vstack((Cx, C_x))
            Cy = np.vstack((Cy, C_y))
        else:
            Bx = np.vstack((Bx, Op['x']))
            Bx = np.vstack((Bx, Om['x']))
            By = np.vstack((By, Op['y']))
            By = np.vstack((By, Om['y']))
            Cx = np.vstack((Cx, Cx_p))
            Cx = np.vstack((Cx, Cx_m))
            Cy = np.vstack((Cy, Cy_p))
            Cy = np.vstack((Cy, Cy_m))
    else:
        print(f"Data file '{datafile_m}' does not exist, ignoring counterpart '{datafile_p}' for response matrix computation")

# Compute the response matrices
Rxx = np.linalg.lstsq(Bx, Cx, rcond=None)[0]
Rxy = np.linalg.lstsq(Bx, Cy, rcond=None)[0]
Ryx = np.linalg.lstsq(By, Cx, rcond=None)[0]
Ryy = np.linalg.lstsq(By, Cy, rcond=None)[0]

# Zero the response of all bpms preceeding the correctors
for corr in hcorrs:
     bpm_indexes = [ bpms.index(bpm) for bpm in bpms if sequence.index(bpm) < sequence.index(corr) ]
     Rxx[bpm_indexes, hcorrs.index(corr)] = 0
     Ryx[bpm_indexes, hcorrs.index(corr)] = 0

for corr in vcorrs:
     bpm_indexes = [ bpms.index(bpm) for bpm in bpms if sequence.index(bpm) < sequence.index(corr) ]
     Rxy[bpm_indexes, vcorrs.index(corr)] = 0
     Ryy[bpm_indexes, vcorrs.index(corr)] = 0

# Save on disk
R = Response()
R.bpms = bpms
R.hcorrs = hcorrs
R.vcorrs = vcorrs
R.Rxx = Rxx
R.Rxy = Rxy
R.Ryx = Ryx
R.Ryy = Ryy

R.save('response.json')

# Plot it
fig = plt.figure(figsize=(9, 9), facecolor="w")
ax = fig.add_subplot(111, projection="3d")

x = np.array(range(len(hcorrs)))
y = np.array(range(len(bpms)))
X, Y = np.meshgrid(x, y)

surf = ax.plot_surface(X, Y, Rxx)

plt.show()


