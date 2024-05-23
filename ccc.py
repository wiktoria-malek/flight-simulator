from InterfaceATF2_Linac import InterfaceATF2_Linac
from State import State
from datetime import datetime
from functools import partial

import matplotlib.pyplot as plt
import numpy as np
import signal
import os

# Create the working environment
project_name = 'new_SYSID'
time_str = datetime.now().strftime("%Y%m%d_%H%M%S")
dir_name = f"Data/{project_name}_{time_str}"
os.makedirs (dir_name)
os.chdir (dir_name)

# Connect to interface ATF2 Linac
I = InterfaceATF2_Linac (nsamples=10)
S = State ()
S.get_machine (I)

# Save the reference file
F = S.save (basename='machine_status')

# Install CTRL-C signal handler
def signal_handler(sig, frame, var):
    print('Caught CTRL-C, exiting gracefully!')
    S = var[0]
    F = var[1]
    S.load(F)
    #S.write_to_machine(I)
    exit(0)

signal.signal(signal.SIGINT, partial(signal_handler, var=(S,F)))

# The list of correctors to use 
C = [
    'ZH1L', 'ZV1L', 'ZV2L', 'ZH2L', 'ZV3L', 'ZH3L', 'ZH4L', 'ZV4L', 'ZH5L', 'ZV5L',
    'ZH6L', 'ZV6L', 'ZH7L', 'ZV7L', 'ZH8L', 'ZV8L', 'ZH9L', 'ZV9L', 'ZH10L', 'ZV10L',
    'ZH11L', 'ZV11L'
]

# The list of bmps to use
B = [
    "MB5L", "MB6L", "MB7L", "MB8L", "MB9L", "MB10L", "MB11L",
    "ML1L", "ML2L", "ML3L", "ML4L", "ML5L", "ML6L", "ML7L",
    "ML8L", "ML9L", "ML10L", "ML11L", "ML12L"
]

# Extra functions
def plot_orbit(orbit, figure):
    plt.figure(figure)
    plt.clf()
    errx = orbit['stdx'] / np.sqrt(orbit['stdx'].size)
    erry = orbit['stdy'] / np.sqrt(orbit['stdy'].size)
    plt.errorbar (range(orbit['nbpms']), np.transpose(orbit['x']), yerr=errx, lw=2, capsize=5, capthick=2, label="X")
    plt.errorbar (range(orbit['nbpms']), np.transpose(orbit['y']), yerr=erry, lw=2, capsize=5, capthick=2, label="Y")
    plt.legend (loc='upper left')
    plt.xlabel ('Bpm [#]')
    plt.ylabel ('Position [mm]')
    plt.draw()
    plt.pause(0.1)  

# Turn on interactive mode
plt.ion()

# Kick to achieve 1mm max excursion
kicks = 0.1 * np.ones(len(C), dtype=float) # kicks to excite 1mm oscillation
max_oscillation = 0.150 # mm

# 10 loops to measure the response matrix
print("Press CTRL-C to interrupt the program.")
Niter = 10
for iter in range (Niter):
    print(f'Iteration {iter}/{Niter}')
    for icorr, corrector in enumerate(C):

        # initial value
        corr = S.get_correctors (corrector)
        kick = kicks[icorr]

        # '+' excitation 
        print(f"Corrector {corrector} '+' excitation...")
        #I.write_correctors(corrector, corr['bdes'] + kick)
        S.get_machine (I)
        S.save (filename=f'DATA_{corrector}_p{iter:04d}.json')
        Op = S.get_orbit (B)
        plot_orbit(Op, 1)
        
        # '-' excitation 
        print(f"Corrector {corrector} '-' excitation...")
        #I.write_correctors(corrector, corr['bdes'] - kick)
        S.get_machine (I)
        S.save (filename=f'DATA_{corrector}_m{iter:04d}.json')
        Om = S.get_orbit (B)
        plot_orbit(Om, 2)
        
        # reset corrector
        #I.write_correctors(corrector, corr['bdes'])
        
        # Orbit difference
        Diff_x = (Op['x'] - Om['x']) / 2.0
        Diff_y = (Op['y'] - Om['y']) / 2.0
        Err_x = np.sqrt(np.square(Op['stdx']) + np.square(Om['stdx'])) / np.sqrt(Op['stdx'].size)
        Err_y = np.sqrt(np.square(Op['stdy']) + np.square(Om['stdy'])) / np.sqrt(Op['stdy'].size)
        
        # Tunes the kickers omplitude
        if corrector in S.get_hcorrectors_names():
            kicks[icorr] *= max_oscillation / np.max(np.absolute(Diff_x))
        else:
            kicks[icorr] *= max_oscillation / np.max(np.absolute(Diff_y))

        # weighted average
        kicks[icorr] = 0.8 * kicks[icorr] + 0.2 * kick
        np.savetxt('kicks.txt', kicks, delimiter='\n')

        # Plot orbit    
        plt.figure(3)
        plt.clf()
        plt.errorbar (range(Op['nbpms']), Diff_x, yerr=Err_x, lw=2, capsize=5, capthick=2, label="X")
        plt.errorbar (range(Op['nbpms']), Diff_y, yerr=Err_y, lw=2, capsize=5, capthick=2, label="Y")
        plt.legend (loc='upper left')
        plt.xlabel ('Bpm [#]')
        plt.ylabel ('Orbit [mm]')
        plt.draw()
        plt.pause(0.1)

plt.ioff()  # Turn off interactive mode
plt.show()  # Show the final plot                       

