import os, sys, pyjapc
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

"""Test of one quadrupole and method get_quadrupoles"""

print("Testing quadrupole CA.QFD0350, reading its values directly from japc/pyda... ")
quadrupole = "CA.QFD0350"
setting = client.get(f"{quadrupole}/SettingPPM", context=context_empty).data["current"]
print(f"{quadrupole}/SettingPPM#current = {setting}")

acquisition = client.get(f"{quadrupole}/Acquisition", context = context_acquisition).data["currentAverage"]
print(f"{quadrupole}/Acquisition#currentAverage = {acquisition}")

status = client.get(f"{quadrupole}/Status", context = "").data
print(f"{quadrupole}/Status = {status}")
print("================================================================================")
print("Testing quadrupole CA.QFD0350, reading its values directly from interface, using get_quadrupoles method... ")

result = I.get_quadrupoles(names=["CA.QFD0350"])
print(f"names from method get_quadrupoles: {result['names']}")
print(f"bdes  from method get_quadrupoles: {result['bdes']}")
print(f"bact  from method get_quadrupoles: {result['bact']}")

"""================================="""

"""Test of one corrector and method get_correctors"""

print("Testing corrector CA.DHG0130, reading its values directly from japc/pyda... ")
corrector = "CA.DHG0130"
setting = client.get(f"{corrector}/SettingPPM", context = context_empty).data["current"]
print(f"{corrector}/SettingPPM#current = {setting}")

acquisition = client.get(f"{corrector}/Acquisition", context = context_acquisition).data["currentAverage"]
print(f"{corrector}/Acquisition#currentAverage = {acquisition}")

status = client.get(f"{corrector}/Status", context = context_empty).data
print(f"{corrector}/Status = {status}")
print("================================================================================")
print("Testing corrector CA.DHG0130, reading its values directly from interface, using get_correctors method... ")

result = I.get_correctors(names=["CA.DHG0130"])
print(f"names from method get_correctors: {result['names']}")
print(f"bdes  from method get_correctors: {result['bdes']}")
print(f"bact  from method get_correctors: {result['bact']}")

"""================================="""

"""Test of one screen and method get_screens"""

print("Testing screen CA.BTV0390L, reading its values directly from japc/pyda... ")
camera = client.get("CA.BTV0390.DigiCam/LastImage", context=context_empty).data

image = camera["image2D"]
print(f"image from PyDa = {image}")

hpixel = camera["pixelCalSet1"]
print(f"hpixel from PyDa = {hpixel}")

vpixel = camera["pixelCalSet2"]
print(f"vpixel from PyDa = {vpixel}")

proj_x = camera["projDataSet1"]
print(f"proj_x.shape = {proj_x.shape}")

proj_y = camera["projDataSet2"]
print(f"proj_y.shape = {proj_y.shape}")

x_positions = camera["imagePositionSet1"]
print(f"x_positions.shape = {x_positions.shape}")

y_positions = camera["imagePositionSet2"]
print(f"y_positions.shape = {y_positions.shape}")

inout = client.get("CA.BTV0390_CAS.BTV0420/OPSettingSystem1", context = context_empty).data["positionChannel1"]
print(f"inout from PyDa = {inout}")

print("================================================================================")
print("Testing screen CA.BTV0390L, reading its values directly from interface, using get_screens method... ")
result = I.get_screens(names=["CA.BTV0390L"])
print(f"names from get_screens: {result['names']}")
print(f"hpixel from get_screens: {result['hpixel']}")
print(f"vpixel from get_screens: {result['vpixel']}")
print(f"x from get_screens: {result['x']}")
print(f"y from get_screens: {result['y']}")
print(f"sigx from get_screens:  {result['sigx']}")
print(f"sigy from get_screens:  {result['sigy']}")
print(f"sum from get_screens: {result['sum']}")
print(f"images from get_screens: {result['images']}")
print(f"inout from get_screens: {result['inout']}")
"""================================="""


"""================================="""

"""Test of one BPM and method get_bpms"""

print("Testing BPM CA.BPM0530H-SA, reading its values directly from japc/pyda... ")
bpm = "CA.BPM0530"
hsamples = client.get(f"{bpm}H-SA/SamplesFromTrigger", context = context_acquisition).data
print(f"{bpm}H-SA/SamplesFromTrigger = {hsamples}")

vsamples = client.get(f"{bpm}V-SA/SamplesFromTrigger", context = context_acquisition).data
print(f"{bpm}V-SA/SamplesFromTrigger = {vsamples}")

Ssamples = client.get(f"{bpm}S-SA/SamplesFromTrigger", context = context_acquisition).data
print(f"{bpm}S-SA/SamplesFromTrigger = {Ssamples}")

h = np.asarray(hsamples["samples"], dtype=float).ravel()
v = np.asarray(vsamples["samples"], dtype=float).ravel()
s = np.asarray(Ssamples["samples"], dtype=float).ravel()
Hpos = np.sum(h)/np.sum(s)
Vpos = np.sum(v)/np.sum(s)

print("Hpos:", Hpos)
print("Vpos:", Vpos)
plt.figure()
plt.plot(h, label="H")
plt.plot(v, label="V")
plt.plot(s, label="S")
plt.legend()
plt.figure()
plt.show()

print("================================================================================")
print("Testing BPM CA.BPM0530H-SA, reading its values directly from interface, using get_bpms method... ")
result = I.get_bpms(names=["CA.BPM0530"])
print(f"names from get_bpms: {result['names']}")
print(f"x from get_bpms: {result['x']}")
print(f"y from get_bpms: {result['y']}")
print(f"tmit from get_bpms: {result['tmit']}")
"""================================="""













# print("================================================================================")
# print("Testing BPM CA.BPM0530, reading its values directly from interface, using get_bpms method... ")
#
# result = I.get_bpms(names=["CA.BPM0530"])
# print(f"names from method get_bpms: {result['names']}")
# print(f"bdes  from method get_bpms: {result['bdes']}")
# print(f"bact  from method get_bpms: {result['bact']}")

"""================================="""

# # print("Methods to test Orbit Measurement.")
# # state = State(correctors=correctors)
# # print("Reading method 'get_orbit'...")
# # bpms = I.get_bpms(names=["CA.BPM0530H-AS"])
# # orbit = state.get_orbit()
# # print("Successfully run method 'get_orbit'!")
# # print("Reading method 'get_state'...")
# # I.get_state()
# # print("Successfully run method 'get_state'!")
# # print("Reading method 'get_bpms'...")
# # I.get_bpms()
# # print("Successfully run method 'get_bpms'!")
# # print("Orbit Measurement is able to run.")

# print("Trying to read corrector current...")
# print(japc.getParam("CA.DHG0130/SettingPPM#current")) # this works!, A
# print(japc.getParam("CA.DHG0130/Status"))
# print("Reading method 'get_correctors'...")
# I.get_correctors()
# print("Successfully run method 'get_correctors'!")
#
# print("Methods to test reading screens.")
# print("Reading method 'get_screens' with inserted screen...")
# #I.get_screens()
# print("Last image reading...")
# #pixelCalSet1 or 2
# #print(japc.getParam("CA.BTV0125.DigiCam/LastImage#image2D"))
# print(japc.getParam("CA.BTV0390_CAS.BTV0420/OPSettingSystem1#positionChannel1")) # anything else than 0 meanssscreen is in
#
# # 0 out, 1 in
# print("Successfully run method 'get_screens' with inserted screen!")
#
# print("Reading method 'get_screens' without inserted screen (no beam)...")
# #I.get_screens()
# print("Successfully run method 'get_screens' without inserted screen (no beam)!")
#
# print(japc.getParam("CA.QFD0350/SettingPPM#current")) # this works!, A




