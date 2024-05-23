from State import State
import numpy
import glob

# Use glob to get the list of DATA files
datafiles = glob.glob('DATA*.json')

# Sanity check: retains only the files that form a pair pm excitation


