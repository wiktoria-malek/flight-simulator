import os, sys, pyjapc, time
import pyda, pyda_japc
from pathlib import Path
import numpy as np
project_root_path = Path.cwd().resolve()
while (not (project_root_path / "Interfaces").exists() and project_root_path.parent != project_root_path):
    project_root_path = project_root_path.parent
sys.path.insert(0, str(project_root_path))
os.chdir(project_root_path)
from Interfaces.CLEAR.InterfaceCLEAR import CLEAR_real_machine
import matplotlib.pyplot as plt

I = CLEAR_real_machine(nsamples=3)
bpms = I.bpms
bpm0 = I.get_bpms(bpms)

I.change_energy()
bpm1 = I.get_bpms(bpms)
I.reset_energy()

x0_samples = np.asarray(bpm0["x"], dtype=float)
y0_samples = np.asarray(bpm0["y"], dtype=float)
x1_samples = np.asarray(bpm1["x"], dtype=float)
y1_samples = np.asarray(bpm1["y"], dtype=float)

dx = x1 - x0
dy = y1 - y0

err_dx = np.sqrt(np.nanstd(x0_samples, axis=0, ddof=1)**2 / x0_samples.shape[0] + np.nanstd(x1_samples, axis=0, ddof=1)**2 / x1_samples.shape[0])
err_dy = np.sqrt(np.nanstd(y0_samples, axis=0, ddof=1)**2 / y0_samples.shape[0] + np.nanstd(y1_samples, axis=0, ddof=1)**2 / y1_samples.shape[0])

plt.errorbar(range(len(dx)), dx, yerr=err_dx, fmt="o-", label="delta x")
plt.errorbar(range(len(dy)), dy, yerr=err_dy, fmt="o-", label="delta y")
plt.xlabel("BPM index")
plt.ylabel("Orbit change [mm]")
plt.grid()
plt.legend()
plt.show()