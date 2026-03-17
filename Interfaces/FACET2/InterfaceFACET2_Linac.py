import sys
import numpy as np
import time, math
from epics import get_pv
from Interfaces.AbstractMachineInterface import AbstractMachineInterface
# must run on SLAC controls network
sys.path.append('/usr/local/facet/tools/python/F2_live_model/')
sys.path.append('/usr/local/facet/tools/python/F2_pytools/')
# sys.path.append('/home/fphysics/zack/workspace/F2_pytools/')
from bmad import BmadLiveModel
from F2_pytools.controls_jurisdiction import is_SLC
from F2_pytools.f2bsaBuffer import make_bpm_buffer, get_bpmdata2
from F2_pytools.mags import set_magnets
from traceback import print_exception

# missing/deffered elements in the model to ignore
BPM_BLACKLIST = [
    'BPM19851', 'BPM19871'
]
CORRECTOR_BLACKLIST = [
    'YC57145', 'YC57146',
    'XCB2LE', 'XCB3RE', 'XCB3LE', 'XCB2RE', 'XC1EX',
]


def devname_swap_micro_primary(device):
    ds = device.split(':')
    return f'{ds[1]}:{ds[0]}:{ds[2]}'


class InterfaceFACET2_Linac(AbstractMachineInterface):
    def get_name(self):
        return 'FACET2_Linac'

    def __init__(self, nsamples=10, livemodel=False, tao_initfile=None):
        self.log = print
        self.nsamples = nsamples
        if livemodel:
            self.f2m = BmadLiveModel(instanced=True, init_filename=tao_initfile)
            # Brho = self.f2m.live.Brho
        else:
            self.f2m = BmadLiveModel(design_only=True)
            # Brho = self.f2m.design.Brho
        _ix = self.f2m.ix
        self.sequence = list(self.f2m.elements[np.sort(np.append(_ix['BPMS'], _ix['COR']))])
        self.bpms = list(self.f2m.elements[_ix['BPMS']])
        self.xcorrs = list(self.f2m.elements[_ix['XCOR']])
        self.ycorrs = list(self.f2m.elements[_ix['YCOR']])
        self.corrs = list(self.f2m.elements[_ix['COR']])
        for bpmname in BPM_BLACKLIST:
            self.sequence.remove(bpmname)
            self.bpms.remove(bpmname)
        for corname in CORRECTOR_BLACKLIST:
            self.sequence.remove(corname)
            self.corrs.remove(corname)
            if corname.startswith('X'): self.xcorrs.remove(corname)
            if corname.startswith('Y'): self.ycorrs.remove(corname)
        self.bpmdevs = [self.f2m.device_names[_ix[bpm]] for bpm in self.bpms]
        self.bpms_s = [self.f2m.S[_ix[bpm]] for bpm in self.bpms]
        self.xcorrs_s = [self.f2m.S[_ix[xcor]] for xcor in self.xcorrs]
        self.ycorrs_s = [self.f2m.S[_ix[ycor]] for ycor in self.ycorrs]
        self.corrs_s = [self.f2m.S[_ix[cor]] for cor in self.corrs]
        # self.Brho =     [Brho[ix[elem]] for elem in self.sequence]
        self.PVs = {
            'Q_setpoint': get_pv('SIOC:SYS1:ML03:AO518'),
            'Q_readback': get_pv('TORO:IN10:431:TMIT_PC'),
            'UVWP_angle': get_pv('WPLT:LT10:150:WP_ANGLE'),
            'dl10_en': get_pv('BEND:IN10:751:BDES'),
            'bc11_en': get_pv('BEND:LI11:314:BDES'),
            'bc14_en': get_pv('BEND:LI14:720:BDES'),
            'bc20_en': get_pv('LI20:LGPS:1990:BDES'),
            'dl10e_setpoint': get_pv('PHYS:SYS1:1:F2LFB_DL10E_VERN'),
            'bc11e_setpoint': get_pv('PHYS:SYS1:1:F2LFB_BC11E_VERN'),
            'bc14e_setpoint': get_pv('PHYS:SYS1:1:F2LFB_BC14E_VERN'),
            'bc20e_setpoint': get_pv('PHYS:SYS1:1:F2LFB_BC20E_VERN'),
        }
        # initial bunch charge setpoint for reset_intensity
        self.init_charge_setpoint = self.PVs['Q_setpoint'].get()
        self.UVWP_init = self.PVs['UVWP_angle'].get()
        # initialize bpm data buffer
        self.bpm_buffer = make_bpm_buffer(self.f2m, self.bpms, Npts=self.nsamples)
        print('InterfaceFACET2_Linac is ready')

    def log_messages(self, console):
        self.log = console or print

    def _meascharge(self):
        qraw = []
        for j in range(self.nsamples):
            qraw.append(self.PVs['Q_readback'].get())
            time.sleep(0.1)
        return np.nanmean(qraw)

    def change_energy(self):
        """ set beam to -2MeV at DL10 and disable downstream feedbacks """
        print('Lowering beam energy starting from BC11')
        get_pv(f'PHYS:SYS1:1:F2LFB_BC11E_VERN').put(-3.0)
        get_pv(f'PHYS:SYS1:1:F2LFB_BC14E_VERN').put(-40.0)
        get_pv(f'PHYS:SYS1:1:F2LFB_BC20E_VERN').put(-40.0)
        # get_pv(f'PHYS:SYS1:1:F2LFB_BC11BL_TARGET').put(4400)
        # get_pv(f'PHYS:SYS1:1:F2LFB_BC14BL_TARGET').put(5000)
        time.sleep(5.0)
        return -(3.0 / 335.0)

    def reset_energy(self):
        """ zero dl10 setpoint, re-enable feedbacks """
        print('Restoring beam energy at BC11, re-enabling feedbacks')
        get_pv(f'PHYS:SYS1:1:F2LFB_BC11E_VERN').put(0)
        get_pv(f'PHYS:SYS1:1:F2LFB_BC14E_VERN').put(0)
        get_pv(f'PHYS:SYS1:1:F2LFB_BC20E_VERN').put(0)
        # get_pv(f'PHYS:SYS1:1:F2LFB_BC11BL_TARGET').put(5000)
        # get_pv(f'PHYS:SYS1:1:F2LFB_BC14BL_TARGET').put(8000)
        time.sleep(5.0)

    def change_intensity(self):
        """ lowers bunch charge by ~200pC (2.5deg UV WP angle adjustment) """
        self.UVWP_init = self.PVs['UVWP_angle'].get()
        self.Q_init = self._meascharge()
        self.PVs['UVWP_angle'].put(self.UVWP_init - 2.5)
        time.sleep(2.0)
        self.Q_new = self._meascharge()
        self.PVs['Q_setpoint'].put(self.Q_new)
        print(f'Charge changed: {self.Q_init:.1f}  {self.Q_new:.1f} pC')
        return self

    def reset_intensity(self):
        """ restore bunch charge to initial settings """
        print(f'restoring charge setpoint to {self.init_charge_setpoint} pC')
        self.PVs['UVWP_angle'].put(self.UVWP_init)
        self.PVs['Q_setpoint'].put(self.init_charge_setpoint)
        return self

    def get_icts(self, *args, **kwargs):
        return {"names": [], "charge": []}

    def get_sequence(self, *args):
        return self.sequence

    def get_bpms_names(self, *args):
        return self.bpms

    def get_correctors_names(self):
        return self.corrs

    def get_hcorrectors_names(self):
        return self.xcorrs

    def get_vcorrectors_names(self):
        return self.ycorrs

    def get_elements_position(self, names):
        return [self.f2m.S[self.f2m.ix[name]] for name in names]

    def get_target_dispersion(self, names):
        return [0. for _ in names], [0. for _ in names]

    def get_correctors(self):
        print("Reading correctors' strengths...")
        bdes, bact = [], []
        for corname in self.corrs:
            devname = self.f2m.device_names[self.f2m.ix[corname]]
            if devname == '':
                print(f'skipping {corname}')
                continue  # some model elements don't have an actual magnet
            bdes.append(get_pv(f'{devname}:BDES').get())
            bact.append(get_pv(f'{devname}:BACT').get())
        return {"names": self.corrs, "bdes": np.array(bdes), "bact": np.array(bact)}

    def get_bpms(self):
        itry = 0
        while itry < 10:
            try:
                bpmdata = get_bpmdata2(self.bpm_buffer)
                return bpmdata
            except Exception as e:
                print('BPM data acquisition failed! trying again ...')
                print_exception(e)
                itry += 1
        else:
            print(f'unable to get BPMs after {itry} tries')
            return self._dummy_bpmdata()

    def _dummy_bpmdata(self):
        """ mock BPM data, all nans """
        N, M = len(self.bpm_buffer.devicelist), self.bpm_buffer.EPICS_Npts
        xraw = np.empty((N, M))
        yraw = np.empty((N, M))
        qraw = np.empty((N, M))
        xraw.fill(np.nan)
        yraw.fill(np.nan)
        qraw.fill(np.nan)
        return {
            'names': self.bpm_buffer.elemlist,
            'x': xraw.transpose(),
            'y': yraw.transpose(),
            'tmit': qraw.transpose(),
        }

    def set_correctors(self, names, corr_vals):
        """ write BDES to correctors """
        if type(corr_vals) == float:
            corr_vals = np.array([corr_vals])
        if type(names) == str:
            names = [names]
        if len(names) != len(corr_vals):
            raise ValueError('len(names) != len(corr_vals) in set_correctors(names, corr_vals)')
        devnames = [self.f2m.device_names[self.f2m.ix[name]] for name in names]
        set_magnets(devnames, corr_vals, perturb=True)
        time.sleep(1)

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
        updated_corr_vals = [bdes + delta for bdes, delta in zip(bdes_init, corr_vals)]
        set_magnets(devnames, updated_corr_vals, perturb=True)
        time.sleep(1)

