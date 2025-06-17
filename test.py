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
I = InterfaceATF2(nsamples=1)

# Prepare for data taking
S = State(I)
S.pull()
S.save('Data/uno')

U = State(I)
U.load('Data/uno')
U.save('Data/tre')


print('SAVED!')
print(S.get_icts('ext:EXTcharge'))

if False:
    I.push('ZV11X', 0.22)
    S.pull()
    c2 = S.get_correctors('ZV11X')
    print('c2',c2)


    S.vary_correctors('ZV11X', 0.01)
    c3 = S.get_correctors('ZV11X')
    print('c3',c3)


    S.vary_correctors('ZV11X', -0.01)
    c4 = S.get_correctors('ZV11X')
    print('c4',c4)



