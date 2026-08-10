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

I = CLEAR_real_machine()

client = pyda.SimpleClient(provider=pyda_japc.JapcProvider())
context_acquisition = "SCT.USER.SETUP"
context_empty = ""

print("================================================================================")
print("Testing BPM CA.BPM0530H-SA, reading its values directly from interface, using get_bpms method... ")
result = I.get_bpms(names=["CA.BPM0530", "CA.BPM0595"])
print(f"names from get_bpms: {result['names']}")
print(f"x from get_bpms: {result['x']}")
print(f"y from get_bpms: {result['y']}")
print(f"tmit from get_bpms: {result['tmit']}")
print("================================================================================")

