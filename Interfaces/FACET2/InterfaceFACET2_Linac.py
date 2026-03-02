import sys
import numpy as np
import time, math
from epics import get_pv

# must run on SLAC controls network
sys.path.append('/usr/local/facet/tools/python/F2_live_model/')
sys.path.append('/usr/local/facet/tools/python/F2_pytools/')
# sys.path.append('/home/fphysics/zack/workspace/F2_pytools/')
from bmad import BmadLiveModel
from F2_pytools.controls_jurisdiction import is_SLC
from F2_pytools.f2bsaBuffer import make_bpm_buffer, get_bpmdata
from F2_pytools.mags import set_magnets




# missing/deffered elements in the model to ignore
BPM_BLACKLIST = [
    'BPM19851','BPM19871'
    ]
CORRECTOR_BLACKLIST = [
    'YC57145','YC57146',
    'XCB2LE','XCB3RE','XCB3LE','XCB2RE',
    ]


def devname_swap_micro_primary(device):
    ds = device.split(':')
    return f'{ds[1]}:{ds[0]}:{ds[2]}'


class InterfaceFACET2_Linac:
    def get_name(self):
        return 'FACET2_Linac'

    def __init__(self, nsamples=10, livemodel=True, tao_initfile=None):
        self.log = print
        self.nsamples = nsamples
        if livemodel:
            self.f2m = BmadLiveModel(instanced=True, init_filename=tao_initfile)
        else:
            self.f2m = BmadLiveModel(design_only=True)
        _ix = self.f2m.ix
        self.sequence = list(self.f2m.elements[np.sort(np.append(_ix['BPMS'], _ix['COR']))])
        self.bpms =     list(self.f2m.elements[_ix['BPMS']])
        self.xcorrs =   list(self.f2m.elements[_ix['XCOR']])
        self.ycorrs =   list(self.f2m.elements[_ix['YCOR']])
        self.corrs =    list(self.f2m.elements[_ix['COR']])
        for bpmname in BPM_BLACKLIST:
            self.sequence.remove(bpmname)
            self.bpms.remove(bpmname)
        for corname in CORRECTOR_BLACKLIST:
            self.sequence.remove(corname)
            self.corrs.remove(corname)
            if corname.startswith('X'): self.xcorrs.remove(corname)
            if corname.startswith('Y'): self.ycorrs.remove(corname)
        self.bpmdevs =  [self.f2m.device_names[_ix[bpm]] for bpm in self.bpms]
        self.bpms_s =   [self.f2m.S[_ix[bpm]]  for bpm  in self.bpms]
        self.xcorrs_s = [self.f2m.S[_ix[xcor]] for xcor in self.xcorrs]
        self.ycorrs_s = [self.f2m.S[_ix[ycor]] for ycor in self.ycorrs]
        self.corrs_s =  [self.f2m.S[_ix[cor]]  for cor  in self.corrs]
        self.PVs = {
            'Q_setpoint':     get_pv('SIOC:SYS1:ML03:AO518'),
            'dl10_en':        get_pv('BEND:IN10:751:BDES'),
            'bc11_en':        get_pv('BEND:LI11:314:BDES'),
            'bc14_en':        get_pv('BEND:LI14:720:BDES'),
            'bc20_en':        get_pv('LI20:LGPS:1990:BDES'),
            'dl10e_setpoint': get_pv('PHYS:SYS1:1:F2LFB_DL10E_VERN'),
            'bc11e_setpoint': get_pv('PHYS:SYS1:1:F2LFB_BC11E_VERN'),
            'bc14e_setpoint': get_pv('PHYS:SYS1:1:F2LFB_BC14E_VERN'),
            'bc20e_setpoint': get_pv('PHYS:SYS1:1:F2LFB_BC20E_VERN'),
            }
        # initial bunch charge setpoint for reset_intensity
        self.init_charge_setpoint = self.PVs['Q_setpoint'].get()
        # initialize bpm data buffer
        self.bpm_buffer = make_bpm_buffer(self.f2m, self.bpms, Npts=self.nsamples)
        print('ready')

    def log_messages(self,console):
        self.log=console or print

    def change_energy(self, scale, where='dl10'):
        """
        scale beam energy at requested spectrometer
        writes a delta in MeV to the energy feedback setpoint, based on 'scale'
        returns the delta in % (scale-1)
        """
        if scale < 0.95 or scale > 1.05:
            raise ValueError('energy variation must be within +/-5%')
        if where not in ['dl10','bc11','bc14','bc20']:
            raise ValueError(f'invalid spectrometer {where}')
        E0 = self.PVs[f'{where}_en'].get() * 1e3 # convert GeV/c bend setting to MeV
        Edes = scale * E0
        self.PVs[f'{where}e_setpoint'].put(Edes-E0)
        return scale - 1.0 # energy delta in %
        
    def reset_energy(self, where='dl10'):
        self.PVs[f'{where}e_setpoint'].put(0)

    def change_intensity(self, scale):
        """
        scale bunch charge (by a sensible amount)
        slow convergence due to low-gain feedback system
        """
        if scale < 0.5 or scale > 1.5:
            raise ValueError('charge change must be within +/-50%')
        Q_old = self.PVs['Q_setpoint'].get()
        Q_new = scale * Q_old
        print(f'Setting charge feedback setpoint to {100.*scale}% ({Q_old}-->{Q_new}pC)')
        self.PVs['charge_setpoint'].put(Q_new)
        print(f'waiting {5*scale}s ...')
        time.sleep(5*scale) # sleep 5s per % change to charge setpoint
        return self

    def reset_intensity(self):
        print(f'restoring charge setpoint to {self.init_charge_setpoint} ...')
        self.PVs['charge_setpoint'].put(self.init_charge_setpoint)
        return self

    def get_sequence(self, *args): return self.sequence

    def get_bpms_names(self, *args): return self.bpms

    def get_correctors_names(self): return self.corrs

    def get_hcorrectors_names(self): return self.xcorrs

    def get_vcorrectors_names(self): return self.ycorrs

    def get_elements_position(self, names): return [self.f2m.S[self.f2m.ix[name]] for name in names]

    def get_correctors(self):
        print("Reading correctors' strengths...")
        bdes, bact = [], []
        for corname in self.corrs:
            devname = self.f2m.device_names[self.f2m.ix[corname]]
            if devname == '': continue # some model elements don't have an actual magnet
            bdes.append(get_pv(f'{devname}:BDES').get())
            bact.append(get_pv(f'{devname}:BACT').get())
        return { "names": self.corrs, "bdes": bdes, "bact": bact }
    
    def get_bpms(self): return get_bpmdata(self.bpm_buffer)

    def push(self, names, corr_vals):
        """ write BDES to correctors """
        if type(corr_vals) == float:
            corr_vals = np.array([corr_vals])
        if type(names) == str:
            names = [names]
        if len(names) != len(corr_vals):
            raise ValueError('len(names) != len(corr_vals) in push(names, corr_vals)') 
        devnames = [self.f2m.device_names[self.f2m.ix[name]] for name in names]
        set_magnets(devnames, corr_vals)
    
    def vary_correctors(self, names, corr_vals):
        """ write deltas to correctors """
        if type(corr_vals) is float:
            corr_vals = np.array([corr_vals])
        if type(names) == str:
            names = [names]
        if len(names) != len(corr_vals):
            raise ValueError('len(names) != len(corr_vals) in vary_correctors(names, corr_vals)')
        devnames = [self.f2m.device_names[self.f2m.ix[name]] for name in names]
        bdes_init = [get_pv(f'{devname}:BDES').get() for devname in devnames]
        updated_corr_vals = [bdes+delta for bdes,delta in zip(bdes_init, corr_vals)]
        set_magnets(devnames, updated_corr_vals)

