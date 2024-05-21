from InterfaceATF2_Linac import InterfaceATF2_Linac
from State import State
from datetime import datetime

import matplotlib.pyplot as plt
import numpy as np
import os

# Create the working environment
project_name = 'new_SYSID' 
time_str = datetime.now().strftime("%Y%m%d_%H%M%S")
dir_name = f"Data/{project_name}_{time_str}"
os.makedirs (dir_name)
os.chdir (dir_name)

# Connect interface to ATF2 Linac
I = InterfaceATF2_Linac (nsamples=10)
S = State ()
S.get_machine (interface=I)

# save the reference file
F = S.save (basename='machine_status')

# The list of correctors to use 
C = [
    'ZH1L', 'ZV1L', 'ZV2L', 'ZH2L', 'ZV3L', 'ZH3L', 'ZH4L', 'ZV4L', 'ZH5L', 'ZV5L',
    'ZH6L', 'ZV6L', 'ZH7L', 'ZV7L', 'ZH8L', 'ZV8L', 'ZH9L', 'ZV9L', 'ZH10L', 'ZV10L',
    'ZH11L', 'ZV11L', 'ZH12L', 'ZV12L'
]

# Extra functions
def plot_orbit(orbit, figure):
    plt.figure(figure)
    plt.clf()
    plt.errorbar (range(orbit['nbpms']), np.transpose(orbit['x']), yerr=orbit['stdx'], lw=2, capsize=5, capthick=2, label="X")
    plt.errorbar (range(orbit['nbpms']), np.transpose(orbit['y']), yerr=orbit['stdy'], lw=2, capsize=5, capthick=2, label="Y")
    plt.legend (loc='upper left')
    plt.xlabel ('Bpm [#]')
    plt.ylabel ('Position [um]')
    plt.draw()
    plt.pause(0.1)  

plt.ion()  # Turn on interactive mode

# Kick to achieve 1mm max excursion
kicks = 0.01 * np.ones(len(C), dtype=float)
target_oscillation = 0.3

# 10 loops to measure the response matrix
try:
    print("Press CTRL-C to interrupt the program.")
    Niter = 10
    for iter in range (Niter):
        print(f'Iteration {iter}/{Niter}')
        for icorr, corrector in enumerate(C):

            # initial value
            corr = S.get_correctors (corrector)

            print(f'Corrector {corrector} +excitation...')
            # '+' excitation 
            I.vary_correctors (corrector, +kicks[icorr])
            S.get_machine (I)
            S.save (filename=f'DATA_{corrector}_p{iter:04d}.json')
            Op = S.get_orbit ()
            plot_orbit(Op, 1)
            
            print(f'Corrector {corrector} -excitation...')
            # '-' excitation 
            I.vary_correctors (corrector, -2*kicks[icorr])
            S.get_machine (I)
            S.save (filename=f'DATA_{corrector}_m{iter:04d}.json')
            Om = S.get_orbit ()
            plot_orbit(Om, 2)
            
            # Orbit difference
            Diff_x = (Op['x'] - Om['x']) / 2.0
            Diff_y = (Op['y'] - Om['y']) / 2.0
            
            plt.figure(3)
            plt.clf()
            plt.plot (Diff_x, lw=2, label="X")
            plt.plot (Diff_y, lw=2, label="Y")
            plt.legend (loc='upper left')
            plt.xlabel ('Bpm [#]')
            plt.ylabel ('Orbit [um]')
            plt.draw()
            plt.pause(0.1)  
        
            # reset corrector
            I.write_correctors(corrector, corr['bdes'])

except KeyboardInterrupt:
    print("Caught CTRL-C, restoring the initial machine!")
    S.load(F)
    S.write_to_machine(I)

plt.ioff()  # Turn off interactive mode
plt.show()  # Show the final plot                       


