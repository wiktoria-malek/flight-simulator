import numpy
import matplotlib.pyplot as pl

from epics import PV, ca

# Read the configuration file
with open('bpmcorr.txt', 'r') as file:
    bpmcorr = [line.strip() for line in file]

# Get the BPM names from Epics
p = PV('atf2:name')
bpm_names = p.get()

# Use list comprehension to filter out strings starting with 'Z' or 'z'
bpm_names_from_cfg = [string for string in bpmcorr if not string.lower().startswith('z')]

# Check if the bpms in the config files are known to Epics
bpm_ok = all(bpm in bpm_names for bpm in bpm_names_from_cfg)
if bpm_ok == False:
    bpms_unknown = [bpm for bpm in bpm_names_from_cfg if bpm not in bpm_names]
    print(f'Unknown bpms {bpms_unknown} removed from list')

# Only retains Bpms in config file which are know by Epics
bpmcorr_filtered = [element for element in bpmcorr if (element in bpm_names) or element.lower().startswith('z') ]






exit(0)




p = PV('ATF2:monitors')
a = p.get(as_numpy=True).reshape((-1,10))
print(a)
print(a.shape)

pl.figure()
pl.plot(a[:,4])
pl.show()

p = PV('LINAC:monitors')
a = p.get(as_numpy=True).reshape((-1,20))
print(a)
print(a.shape)

pl.figure()
pl.plot(a[:,4])
pl.show()
