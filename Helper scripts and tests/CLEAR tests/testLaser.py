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

# laser_readback =client.get('CK.LL-MKS11/Setting')
#laser_readback =client.get('CK.LL-MKS15/Setting')
steps_readback = client.get('CO.TOWB.102.UVATT2/Setting')
#PhaseSh_Sp to be checked but it's probably what we want to change
print(laser_readback)