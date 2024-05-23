import sys
sys.path.append('/userhome/alatina/flight-simulator')

from State import State
import numpy as np
import glob
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
        Cp_x = Sp.get_correctors(hcorrs)['bdes']
        Cm_x = Sm.get_correctors(hcorrs)['bdes']
        Cp_y = Sp.get_correctors(vcorrs)['bdes']
        Cm_y = Sm.get_correctors(vcorrs)['bdes']
        if 0:
            O_x = Op['x'] - Om['x']
            O_y = Op['y'] - Om['y']
            C_x = Cp_x - Cm_x
            C_y = Cp_y - Cm_y
            Bx = np.vstack((Bx, O_x))
            By = np.vstack((By, O_y))
            Cx = np.vstack((Cx, C_x))
            Cy = np.vstack((Cy, C_y))
        else:
            Bx = np.vstack((Bx, Op['x']))
            Bx = np.vstack((Bx, Om['x']))
            By = np.vstack((Bx, Op['y']))
            By = np.vstack((Bx, Om['y']))
            Cx = np.vstack((Cx, Cp_x))
            Cx = np.vstack((Cx, Cm_x))
            Cy = np.vstack((Cx, Cp_y))
            Cy = np.vstack((Cx, Cm_y))
    else:
        print(f"Data file '{datafile_m}' does not exist, ignoring counterpart '{datafile_p}' for response matrix computation")

print(Bx)
print(By)
print(Cx)
print(Cy)

#Rxx = np.linalg.lstsq(Cx.T, Bx.T)[0]
#Rxx = np.dot(Bx, np.linalg.pinv(Cx))
#print(Rxx)

np.savetxt('Bx.txt', Bx)
np.savetxt('By.txt', By)
np.savetxt('Cx.txt', Cx)
np.savetxt('Cy.txt', Cy)

