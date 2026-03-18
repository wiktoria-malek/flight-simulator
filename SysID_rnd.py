from Interfaces.FACET2.InterfaceFACET2_Linac import InterfaceFACET2_Linac
from State import State
import numpy as np
import fnmatch

I = InterfaceFACET2_Linac(nsamples=3)
S = State(I)

names = [str(name) for name in S.get_correctors()['names']]
selection = fnmatch.filter(names, 'XC11*') + fnmatch.filter(names, 'XC12*')

corrs = S.get_correctors(selection)

bdes = corrs['bdes']

kick_rms = 0.0001

nSamples = 100
for sample in range(nSamples):
    new_bdes = bdes + kick_rms*np.random.randn(*bdes.shape)
    I.push(selection, new_bdes)
    S.pull(I)
    S.save(filename=f'SAMPLE_{sample}.pkl')

I.push(selection, bdes)
