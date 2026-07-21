import os, sys, pyjapc
from pathlib import Path
import numpy as np
project_root_path = Path.cwd().resolve()
while (not (project_root_path / "Interfaces").exists() and project_root_path.parent != project_root_path):
    project_root_path = project_root_path.parent
sys.path.insert(0, str(project_root_path))
os.chdir(project_root_path)
from Interfaces.CLEAR.InterfaceCLEAR import CLEAR_real_machine

I = CLEAR_real_machine()

japc = pyjapc.PyJapc("SCT.USER.ALL", incaAcceleratorName="CTF")
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


"""Test of one quadrupole and method get_quadrupoles"""

print("Testing quadrupole CA.QFD0350, reading its values directly from japc/pyda... ")
quadrupole = "CA.QFD0350"
setting = japc.getParam(f"{quadrupole}/SettingPPM#current")
print(f"{quadrupole}/SettingPPM#current = {setting}")

acquisition = japc.getParam(f"{quadrupole}/Acquisition#currentAverage")
print(f"{quadrupole}/Acquisition#currentAverage = {acquisition}")

status = japc.getParam(f"{quadrupole}/Status")
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
setting = japc.getParam(f"{corrector}/SettingPPM#current")
print(f"{corrector}/SettingPPM#current = {setting}")

acquisition = japc.getParam(f"{corrector}/Acquisition#currentAverage")
print(f"{corrector}/Acquisition#currentAverage = {acquisition}")

status = japc.getParam(f"{corrector}/Status")
print(f"{corrector}/Status = {status}")
print("================================================================================")
print("Testing corrector CA.DHG0130, reading its values directly from interface, using get_correctors method... ")

result = I.get_correctors(names=["CA.DHG0130"])
print(f"names from method get_correctors: {result['names']}")
print(f"bdes  from method get_correctors: {result['bdes']}")
print(f"bact  from method get_correctors: {result['bact']}")

"""================================="""

"""Test of one screen and method get_screens"""

print("Testing screen CA.BTV0125, reading its values directly from japc/pyda... ")
image = japc.getParam("CA.BTV0125.DigiCam/LastImage#image2D")
print(f"image from japc = {image}")
hpixel = japc.getParam("CA.BTV0125.DigiCam/LastImage#pixelCalSet1")
print(f"hpixel from japc = {hpixel}")
vpixel = japc.getParam("CA.BTV0125.DigiCam/LastImage#pixelCalSet2")
print(f"vpixel from japc = {vpixel}")
inout = japc.getParam("CA.BTV0125_CA.BTV0215/OPSettingSystem1#positionChannel1")
print(f"inout from japc = {inout}")
proj_x = japc.getParam("CA.BTV0125.DigiCam/LastImage#projDataSet1")
print(f"proj_x.shape = {proj_x.shape}")
proj_y = japc.getParam("CA.BTV0125.DigiCam/LastImage#projDataSet2")
print(f"proj_y.shape = {proj_y.shape}")
x_positions = japc.getParam("CA.BTV0125.DigiCam/LastImage#imagePositionSet1")
print(f"x_positions.shape = {x_positions.shape}")
y_positions = japc.getParam("CA.BTV0125.DigiCam/LastImage#imagePositionSet2")
print(f"y_positions.shape = {y_positions.shape}")


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


