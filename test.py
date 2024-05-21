from InterfaceATF2 import InterfaceATF2
from State import State
import os

import time

# Set up environment
data_path = 'Data'
try:
    os.mkdir(data_path)
except:
    pass

# Define interface    
I = InterfaceATF2(nsamples=10)

# Prepare for data taking
S = State(I)
S.get_machine()

print(S.get_icts('ext:EXTcharge'))

if False:
    I.write_correctors('ZV11X', 0.22)
    S.get_machine()
    c2 = S.get_correctors('ZV11X')
    print('c2',c2)


    S.vary_correctors('ZV11X', 0.01)
    c3 = S.get_correctors('ZV11X')
    print('c3',c3)


    S.vary_correctors('ZV11X', -0.01)
    c4 = S.get_correctors('ZV11X')
    print('c4',c4)



