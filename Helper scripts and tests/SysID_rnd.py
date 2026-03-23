#from Interfaces.FACET2.InterfaceFACET2_Linac import InterfaceFACET2_Linac
from Interfaces.FACET2.InterfaceFACET2_Linac_RFTrack import InterfaceFACET2_Linac_RFTrack
from Backend.State import State
import numpy as np
import fnmatch

# I = InterfaceFACET2_Linac(nsamples=3)
I = InterfaceFACET2_Linac_RFTrack(nsamples=3)

state=I.get_state()

names = [str(name) for name in state.get_correctors()['names']]
selection = fnmatch.filter(names, 'XC11*') + fnmatch.filter(names, 'XC12*')

corrs = state.get_correctors(selection)

bdes = corrs['bdes']

kick_rms = 0.0001

nSamples = 100
for sample in range(nSamples):
    new_bdes = bdes + kick_rms*np.random.randn(*bdes.shape)
    I.set_correctors(selection, new_bdes)
    state=I.get_state()
    state.save(filename=f'SAMPLE_{sample}.pkl')

I.set_correctors(selection, bdes)
