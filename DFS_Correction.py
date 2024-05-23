import sys
sys.path.append('/userhome/alatina/flight-simulator')

from InterfaceATF2_Linac import InterfaceATF2_Linac
from Response import Response
from State import State

from datetime import datetime
from functools import partial

import matplotlib.pyplot as plt
import numpy as np
import signal
import os

R0 = Response('response0.json')
R1 = Response('response1.json')

# The list of correctors to use 
Cx = R0.hcorrs
Cy = R0.vcorrs

B = R0.bpms

# Start correction
R0xx, R0xy = R0.submatrix_Rx(B, Cx)
R0yx, R0yy = R0.submatrix_Ry(B, Cy)

R1xx, R1xy = R1.submatrix_Rx(B, Cx)
R1yx, R1yy = R1.submatrix_Ry(B, Cy)

B0x, B0y = R0.submatrix_B(B)

# DFS parameters
gain = 0.5
wgt_orb = 1
wgt_dfsx = 10
wgt_dfsy = 10
rcond = 0.000001

# Correction!
I = InterfaceATF2_Linac(nsamples=3)
S = State ()

norm_Orbit_x = []
norm_Orbit_y = []
norm_Disp_x = []
norm_Disp_y = []

# Turn on interactive plotting mode
plt.ion()
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(8, 6))
fig.suptitle('Convergence')

for iteration in range(15):

    # Nominal orbit
    print('Measuring trajectory...')
    S.get_machine(I)
    O0 = S.get_orbit(B)

    # Dispersive orbit
    print('Measuring dispersion...')
    I.change_energy()
    S.get_machine(I)
    I.reset_energy()
    O1 = S.get_orbit(B)

    # Python's transpose.......
    O0x = O0['x'].reshape(-1,1)
    O0y = O0['y'].reshape(-1,1)
    O1x = O1['x'].reshape(-1,1)
    O1y = O1['y'].reshape(-1,1)

    # DFS system of equations
    Bx = np.vstack((wgt_orb  * (O0x - B0x),
                    wgt_dfsx * (O1x - O0x)))

    By = np.vstack((wgt_orb  * (O0y - B0y),
                    wgt_dfsy * (O1y - O0y)))

    Rxx = np.vstack((wgt_orb  *  R0xx,
                     wgt_dfsx * (R1xx - R0xx)))

    Ryy = np.vstack((wgt_orb  *  R0yy,
                     wgt_dfsy * (R1yy - R0yy)))

    corrX = -gain * (np.linalg.pinv(Rxx, rcond=rcond) @ Bx)
    corrY = -gain * (np.linalg.pinv(Ryy, rcond=rcond) @ By)

    norm_Orbit_x = np.hstack((norm_Orbit_x, np.linalg.norm(O0x - B0x)))
    norm_Orbit_y = np.hstack((norm_Orbit_y, np.linalg.norm(O0y - B0y)))
    norm_Disp_x = np.hstack((norm_Disp_x, np.linalg.norm(O1x - O0x)))
    norm_Disp_y = np.hstack((norm_Disp_y, np.linalg.norm(O1y - O0y)))

    # Clear previous plots
    ax1.clear()
    ax2.clear()

    # Plot the updated data
    ax1.plot(range(iteration+1), norm_Orbit_x, label='X axis')
    ax1.plot(range(iteration+1), norm_Orbit_y, label='Y axis')
    ax1.set_title('Trajectory')
    ax1.set_xlabel ('Iteration [#]')
    ax1.set_ylabel ('Orbit [mm]')
    ax1.legend (loc='upper left')
    
    ax2.plot(range(iteration+1), norm_Disp_x, label='X axis')
    ax2.plot(range(iteration+1), norm_Disp_y, label='Y axis')
    ax2.set_title('Dispersion')
    ax2.set_xlabel ('Iteration [#]')
    ax2.set_ylabel ('Dispersion [mm]')
    ax2.legend (loc='upper left')
    
    # Redraw the plot
    plt.tight_layout()
    plt.show()
    plt.pause(0.1)

print('Done!')

plt.ioff()  # Turn off interactive mode
plt.show()  # Show the final plot

