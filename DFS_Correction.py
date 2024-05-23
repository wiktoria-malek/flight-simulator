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
gain = 0.4
wgt_orb = 1
wgt_dfsx = 10
wgt_dfsy = 10
n_svx = 8
n_svy = 10

#
I = InterfaceATF2_Linac(nsamples=5)
S = State ()

# Nominal orbit
S.get_machine (I)
O0 = S.get_orbit(B)

# Python's transpose.......
O0x = O0['x'].reshape(-1,1)
O0y = O0['y'].reshape(-1,1)
O1x = O1['x'].reshape(-1,1)
O1y = O1['y'].reshape(-1,1)

# Dispersive orbit
#I.change_energy()
#S.get_machine()
O1 = S.get_orbit(B)

Bx = np.vstack((wgt_orb  * (O0x - B0x),
                wgt_dfsx * (O1x - O0x))) 

By = np.vstack((wgt_orb  * (O0y - B0y),
                wgt_dfsx * (O1y - O0y))) 

Rxx = np.vstack((wgt_orb  *  R0xx,
                 wgt_dfsx * (R1xx - R0xx)))

Ryy = np.vstack((wgt_orb  *  R0yy,
                 wgt_dfsx * (R1yy - R0yy)))

print(O0['x'])
print(B0x)
print(Bx.shape)
print(Rxx.shape)
print(np.linalg.pinv(Rxx, rcond=0.0001).shape)

corrX = -gain * (np.linalg.pinv(Rxx, rcond=0.0001) @ Bx)
corrY = -gain * (np.linalg.pinv(Ryy, rcond=0.0001) @ By)

print(corrX)
print(corrY)
