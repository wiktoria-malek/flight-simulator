import numpy as np
import matplotlib.pyplot as plt

# Initialize interface

# Real machine
# from Interfaces.ATF2.InterfaceATF2_Ext import InterfaceATF2_Ext
# I = InterfaceATF2_Ext(nsamples=3)

# Simulated machine
from Interfaces.ATF2.InterfaceATF2_Ext_RFTrack import InterfaceATF2_Ext_RFTrack
I = InterfaceATF2_Ext_RFTrack(jitter=0.01, bpm_resolution=0.1, nsamples=1, nparticles=10000)
I.misalign_quadrupoles()
I.misalign_bpms()

# Here we start the real stuff...
from State import State
EXT = State(interface=I)

# Read the orbit
O = EXT.get_orbit()

# 
OTR = EXT.get_screens()

image = OTR['images'][0]
hedges = OTR['hedges'][0]
vedges = OTR['vedges'][0]

# 3. Plot the result
fig, ax = plt.subplots()
# Transpose H so x is horizontal and y is vertical
c = ax.pcolormesh(hedges, vedges, image.T) 
fig.colorbar(c, ax=ax, label='Count')
ax.set_title('2D Histogram using pcolormesh')
ax.set_xlabel('X value')
ax.set_ylabel('Y value')
plt.show()




