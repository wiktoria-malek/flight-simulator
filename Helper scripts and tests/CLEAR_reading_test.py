import numpy as np
import matplotlib
import pickle, os, sys
from pathlib import Path
project_root_path = Path.cwd().resolve()
while not (project_root_path / "Interfaces").exists() and project_root_path.parent != project_root_path:
    project_root_path = project_root_path.parent
sys.path.insert(0, str(project_root_path))
os.chdir(project_root_path)
from Backend.State import State
from Interfaces.CLEAR.InterfaceCLEAR import CLEAR_real_machine
import pyjapc

I = CLEAR_real_machine()


print("Methods to test Orbit Measurement.")
# print("Reading method 'get_state'...")
# I.get_state()
# print("Successfully run method 'get_state'!")

print("Reading method 'get_orbit'...")
state = State(bpms=bpms, correctors=correctors)
orbit = state.get_orbit()
print("Successfully run method 'get_orbit'!")

print("Reading method 'get_correctors'...")
I.get_correctors()
print("Successfully run method 'get_correctors'!")
#
# print("Reading method 'get_bpms'...")
# I.get_bpms()
# print("Successfully run method 'get_bpms'!")
# print("Orbit Measurement is able to run.")


print("Methods to test reading screens.")
print("Reading method 'get_screens' with inserted screen...")
I.get_screens()
print("Successfully run method 'get_screens' with inserted screen!")

print("Reading method 'get_screens' without inserted screen (no beam)...")
I.get_screens()
print("Successfully run method 'get_screens' without inserted screen (no beam)!")
