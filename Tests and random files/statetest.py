from Interfaces.FACET2.InterfaceFACET2_Linac import InterfaceFACET2_Linac
import numpy as np
import fnmatch

I = InterfaceFACET2_Linac(nsamples=3)
initial_state = I.capture_state()

names = [str(name) for name in initial_state.get_correctors()['names']]
selection = fnmatch.filter(names, 'XC11*') + fnmatch.filter(names, 'XC12*')

corrs = initial_state.get_correctors(selection)

bdes = corrs['bdes']

kick_rms = 0.0001

nSamples = 100
for sample in range(nSamples):
    new_bdes = bdes + kick_rms*np.random.randn(*bdes.shape)
    I.set_correctors(selection, new_bdes)
    state=I.capture_state()
    state.save(filename=f'SAMPLE_{sample}.pkl')

I.set_correctors(selection, bdes)
