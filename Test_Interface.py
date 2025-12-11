import matplotlib.pyplot as plt

from State import State
from Interfaces.ATF2.InterfaceATF2_Ext import InterfaceATF2_Ext
I = InterfaceATF2_Ext(nsamples=3)

I.reset_energy()

bpms = I.get_bpms_names()

S = State(I)


C = S.get_correctors('ZH4X')
C_bdes = C['bdes']

I.push('ZH4X', C_bdes+0.01)
S.pull(I)

B1 = S.get_orbit(bpms)
b1x = B1['x']

I.push('ZH4X', C_bdes-0.01)
S.pull(I)
B2 = S.get_orbit(bpms)
b2x = B2['x'] 

I.push('ZH4X', C_bdes)


Dx = b2x - b1x



plt.plot(Dx)
plt.show()



