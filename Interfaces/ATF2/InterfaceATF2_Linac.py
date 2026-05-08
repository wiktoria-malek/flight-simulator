import sys
import numpy as np
import time, math
from Backend.LogConsole import LogConsole
from Interfaces.AbstractMachineInterface import AbstractMachineInterface

from epics import PV, ca

class InterfaceATF2_Linac(AbstractMachineInterface):

    def get_name(self):
        return 'ATF2_Linac'

    def __init__(self, nsamples=1):
        self.log = print
        self.nsamples = nsamples
        # Bpms and correctors in beamline order
        sequence = [ 
            'MB5L', 'MB6L', 'MB7L', 'ZH1L', 'ZV1L', 'MB8L', 'MB9L', 'MB10L', 
            'ZV2L', 'ZH2L', 'MB11L', 'ML1L', 'ML2L', 'ZV3L', 'ZH3L', 'ML3L',
            'ZH4L', 'ZV4L', 'ZH5L', 'ZV5L', 'ML4L', 'ZH6L', 'ZV6L', 'ML5L',
            'ZH7L', 'ZV7L', 'ML6L', 'ZH8L', 'ZV8L', 'ML7L', 'ZH9L', 'ML8L',
            'ZV9L', 'ML9L', 'ZH10L', 'ML10L', 'ZV10L', 'ML11L', 'ZH11L',
            'ML12L', 'ZV11L', 'ML13L', 'ZH12L', 'ML14L', 'ZV12L', 'ML15L'
        ]
        '''
        sequence = [
            'MB5L', 'MB6L', 'MB7L', 'ZH1L', 'ZV1L', 'MB8L', 'MB9L', 'MB10L',
            'ZV2L', 'ZH2L', 'MB11L', 'ML1L', 'ML2L', 'ZV3L', 'ZH3L', 'ML3L',
            'ZH4L', 'ZV4L', 'ZH5L', 'ZV5L', 'ML4L', 'ZH6L', 'ZV6L', 'ML5L',
            'ZH7L', 'ZV7L', 'ML6L', 'ZH8L', 'ZV8L', 'ML7L', 'ZH9L', 'ML8L',
            'ZV9L', 'ML9L', 'ZH10L', 'ML10L', 'ZV10L', 'ML11L', 'ZH11L', 'ML12L',
            'ZV11L', 'ML13L', 'ZH12L', 'ML14L', 'ZV12L', 'ML15L', 'ZX10T', 'ZX11T',
            'ML1T', 'ZV13L', 'ZX12T', 'ML2T', 'ZY20T', 'ZY21T', 'ML101T', 'ML102T',
            'ZY22T', 'ZY23T', 'ML103T', 'ZX30T', 'ML3T', 'ZX31T', 'ZV30T', 'ZH30T',
            'ML104T', 'ZX32T', 'ML4T', 'ML105T', 'ZV40T', 'ZH40T', 'ML5T', 'ML6T',
            'ZX50T', 'ML106T', 'ZX50T', 'ML7T', 'ZX51T', 'ZV50T', 'ML8T', 'ZH50T',
            'ZV51T', 'ML9T', 'MB10T', 'MB11T'
        ]'''
        # ATF2' BPMs Epics names
        # https://atf.kek.jp/atfbin/view/ATF/EPICS_DATABASE
        monitors = [
            "MB5L", "MB6L", "MB7L", "MB8L", "MB9L", "MB10L", "MB11L", "ML1L",
            "ML2L", "ML3L", "ML4L", "ML5L", "ML6L", "ML7L", "ML8L", "ML9L",
            "ML10L", "ML11L", "ML12L", "ML13L", "ML14L", "ML15L", "ML1P", "ML2P",
            "ML3P", "ML4P", "GUN", "LN0", "LNE", "BTM", "BTE", "C44N16A08",
            "C44N16A09", "C44N16A10", "C44N16A11", "C44N16A12", "C44N16A13",
            "C44N16A14", "C44N16A15", "C45N09A00", "C45N09A01", "C45N09A02",
            "C45N09A03", "C45N09A04", "C45N09A05", "C45N09A06", "C45N09A07",
            "C45N09A08", "C45N09A09", "C45N09A10", "C45N09A11", "C45N09A12",
            "C45N09A13", "C45N09A14", "C45N09A15", "ML1T", "ML2T", "ML3T",
            "ML4T", "ML5T", "ML6T", "ML7T", "ML8T", "ML9T", "MB10T", "MB11T",
            "MB1T", "ML101T", "ML102T", "ML103T", "ML104T", "ML105T", "ML106T",
            "C43N16A08", "C43N16A09", "C43N16A10", "C43N16A11", "C43N16A12",
            "C43N16A13", "C43N16A14", "C43N16A15"
        ]
        # Use list comprehension to filter out strings starting with 'Z' or 'z'
        monitors_from_sequence = [string for string in sequence if not string.lower().startswith('z')]
        # Check if the bpms in the config files are known to Epics
        bpm_ok = all(bpm in monitors for bpm in monitors_from_sequence)
        if not bpm_ok:
            bpms_unknown = [bpm for bpm in monitors_from_sequence if bpm not in monitors]
            print(f'Unknown bpms {bpms_unknown} removed from list')
        # Only retain BPMs in config file which are known by Epics
        sequence_filtered = [element for element in sequence if (element in monitors) or element.lower().startswith('z')]
        # Subset of BPMs and correctors from the config file
        self.sequence = sequence_filtered
        self.bpms = [string for string in self.sequence if not string.lower().startswith('z')]
        self.corrs = [string for string in self.sequence if string.lower().startswith('z')]

        #screens??

        # Index of the selected BPMs in the Epics PV ATF2:monitors
        self.bpm_indexes = [index for index, string in enumerate(monitors) if string in self.bpms]
        # Bunch current monitors
        self.ict_names = [
            'gun:GUNcharge', 'l0:L0charge', 'linacbt:LNEcharge', 'linacbt:BTMcharge',
            'ext:EXTcharge', 'linacbt:BTEcharge', 'BIM:DR:nparticles', 'BIM:IP:nparticles'
        ]
        self.phase_kl1 = PV('CM1L:phaseRead').get()
        self.laser_intensity = PV('RFGun:LaserIntensity1:Read').get()

    def log_messages(self,console):
        self.log=console or print

    def get_beam_factors(self):
        # TO BE REPLACED WITH A PV OF REAL BEAM ENERGY
        Pref = 80
        gamma_rel = np.sqrt((Pref / 0.51099895) ** 2 + 1.0)
        beta_rel = np.sqrt(1.0 - 1.0 / gamma_rel ** 2)
        return gamma_rel, beta_rel

    def change_energy(self):
        pv = PV('CM1L:phaseWrite')
        rel_phase = 5
        pv.put(self.phase_kl1+rel_phase)
        time.sleep(1)
        dP_P = 0.0 # we don't really know it
        return dP_P
        
    def reset_energy(self):
        pv = PV('CM1L:phaseWrite')
        pv.put(self.phase_kl1)
        time.sleep(1)

    def change_intensity(self):
        new_laser_intensity = 0.15 # 0..1
        laser_intensity = new_laser_intensity * 100 * 3 # Korysko dixit: 100 for percent, 5 convesion factor
        print(f'Changing laser intensity to {laser_intensity}...')
        PV('RFGun:LaserIntensity1:Write').put(laser_intensity)
        time.sleep(3)
        return self

    def reset_intensity(self):
        print('Resetting laser intensity...')
        PV('RFGun:LaserIntensity1:Write').put(self.laser_intensity)
        return self

    def get_sequence(self):
        return self.sequence

    def get_hcorrectors_names(self):
        return [string for string in self.corrs if (string.lower().startswith('zh')) or (string.lower().startswith('zx'))]

    def get_vcorrectors_names(self):
        return [string for string in self.corrs if string.lower().startswith('zv')]

    def get_elements_indices(self,names):
        return [index for index, string in enumerate(self.sequence) if string in names]

    def get_target_dispersion(self, names=None):
        if names is None:
            names = self.bpms
        if isinstance(names, str):
            names = [names]
        n = len(names)
        return np.zeros(n, dtype=float), np.zeros(n, dtype=float)

    def get_icts(self, names=None):
        print("Reading ict's...")
        charge = []
        for ict in self.ict_names:
            pv = PV(f'{ict}')
            if 0:
                charge.append(pv.get())
            else:
                charge.append(1.0)

        icts = {
            "names": self.ict_names,
            "charge": np.array(charge),
        }

        if isinstance(names, str):
            names = [names]
        if names is not None:
            idx = np.array([i for i, s in enumerate(icts["names"]) if s in names])
            icts = {
                "names": np.array(icts["names"])[idx],
                "charge": np.array(icts["charge"])[idx],
            }

        return icts

    def get_correctors(self, names=None):
        print("Reading correctors' strengths...")
        bdes, bact = [], []
        for corrector in self.corrs:
            pv_des = PV(f'{corrector}:currentWrite')
            pv_act = PV(f'{corrector}:currentRead')
            bdes.append(pv_des.get())
            bact.append(pv_act.get())

        correctors = {
            "names": self.corrs,
            "bdes": np.array(bdes),
            "bact": np.array(bact),
        }

        if isinstance(names, str):
            names = [names]
        if names is not None:
            idx = np.array([i for i, s in enumerate(correctors["names"]) if s in names])
            correctors = {
                "names": np.array(correctors["names"])[idx],
                "bdes": np.array(correctors["bdes"])[idx],
                "bact": np.array(correctors["bact"])[idx],
            }

        return correctors

    def get_bpms(self, names=None):
        print('Reading bpms...')
        p = PV('LINAC:monitors')
        x, y, tmit = [], [], []
        for sample in range(self.nsamples):
            print(f'Sample = {sample}')
            a_pv = p.get()
            if hasattr(a_pv, "__len__") and len(a_pv) >= 20:
                a = a_pv.reshape((-1, 20))
                status = a[self.bpm_indexes, 0]
                status[status != 1] = 0
                if np.sum(np.isnan(a[self.bpm_indexes, 1:2])):
                    print('Attention please!!! Nan in raw data.... !!!!')
                x.append(a[self.bpm_indexes, 1])
                y.append(a[self.bpm_indexes, 2])
                tmit.append(status * a[self.bpm_indexes, 3])
            time.sleep(0.35)

        bpms = {
            "names": self.bpms,
            "x": np.vstack(x) / 1e3 if len(x) else np.empty((0, 0)),
            "y": np.vstack(y) / 1e3 if len(y) else np.empty((0, 0)),
            "tmit": np.vstack(tmit) if len(tmit) else np.empty((0, 0)),
        }

        if isinstance(names, str):
            names = [names]
        if names is not None:
            idx = np.array([i for i, s in enumerate(bpms["names"]) if s in names])
            bpms = {
                "names": np.array(bpms["names"])[idx],
                "x": np.array(bpms["x"])[:, idx],
                "y": np.array(bpms["y"])[:, idx],
                "tmit": np.array(bpms["tmit"])[:, idx],
            }

        return bpms

    @staticmethod
    def make_safe_float(value, default=np.nan):
        try:
            if value is None:
                return float(default)
            arr = np.asarray(value)
            if arr.size == 0:
                return float(default)
            return float(arr.flat[0])
        except Exception:
            return float(default)

    def _wait_for_corrector_readback(self, corrector, target, tolerance=1e-4, timeout=1.0, poll_interval=0.05):
        readback_pv = PV(f'{corrector}:currentRead')
        t0 = time.perf_counter()
        last_value = np.nan

        while time.perf_counter() - t0 < timeout:
            last_value = self.make_safe_float(readback_pv.get(), default=np.nan)

            if np.isfinite(last_value) and abs(last_value - float(target)) <= tolerance:
                return True

            time.sleep(poll_interval)

        self.log(
            f'Warning: {corrector}:currentRead did not reach target {float(target):.6g} '
            f'within {timeout:.2f}s. Last readback = {last_value:.6g}'
        )
        return False

    def set_correctors(self, names, corr_vals):
        if isinstance(names, str):
            names = [names]
        if not isinstance(corr_vals, (list, tuple, np.ndarray)):
            corr_vals = [corr_vals]
        if len(names) != len(corr_vals):
            print('Error: len(names) != len(corr_vals) in set_correctors(names, corr_vals)')
        for corrector, corr_val in zip(names, corr_vals):
            pv_des = PV(f'{corrector}:currentWrite')
            pv_des.put(corr_val)
            self._wait_for_corrector_readback(corrector, corr_val)

    def vary_correctors(self, names, corr_vals):
        if isinstance(names, str):
            names = [names]
        if not isinstance(corr_vals, (list, tuple, np.ndarray)):
            corr_vals = [corr_vals]
        if len(names) != len(corr_vals):
            print('Error: len(names) != len(corr_vals) in vary_correctors(names, corr_vals)')
        for corrector, corr_val in zip(names, corr_vals):
            pv_des = PV(f'{corrector}:currentWrite')
            curr_val = self.make_safe_float(pv_des.get(), default=np.nan)
            target = curr_val + float(corr_val)
            pv_des.put(target)
            self._wait_for_corrector_readback(corrector, target)
