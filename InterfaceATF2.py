import numpy as np
import time

from epics import PV, ca

class InterfaceATF2:
    def __init__(self, nsamples=1):
        self.nsamples = nsamples
        # Configuration file in beamline order
        bpmcorr = [
            "MB2X", "ZV1X", "MQF1X", "ZV2X", "MQD2X", "MQF3X", "ZH1X", "ZV3X", "MQF4X",
            "ZH2X", "MQD5X", "ZV4X", "ZV5X", "MQF6X", "MQF7X", "ZH3X", "MQD8X", "ZV6X",
            "MQF9X", "ZH4X", "FONTK1", "ZV7X", "FONTP1", "MQD10X", "ZH5X", "MQF11X",
            "FONTK2", "ZV8X", "FONTP2", "MQD12X", "ZH6X", "MQF13X", "MQD14X", "FONTP3",
            "ZH7X", "MQF15X", "ZV9X", "MQD16X", "ZH8X", "MQF17X", "ZV10X", "MQD18X",
            "ZH9X", "MQF19X", "ZV11X", "MQD20X", "ZH10X", "MQF21X", "IPT1", "IPT2",
            "IPT3", "IPT4", "MQM16FF", "ZH1FF", "ZV1FF", "MQM15FF", "MQM14FF", "FB2FF",
            "MQM13FF", "MQM12FF", "MQM11FF", "MQD10BFF", "MQD10AFF", "MQF9BFF",
            "MSF6FF", "MQF9AFF", "MQD8FF", "MQF7FF", "MQD6FF", "MQF5BFF", "MSF5FF",
            "MQF5AFF", "MQD4BFF", "MSD4FF", "MQD4AFF", "MQF3FF", "MQD2BFF", "MQD2AFF",
            "MSF1FF", "MQF1FF", "MSD0FF", "MQD0FF", "PREIP", "IPA", "IPB", "IPC", "M-PIP"
        ]
        # BPM names
        bpm_names = [
            "MB1X", "MB2X", "MQF1X", "MQD2X", "MQF3X", "MQF4X", "MQD5X", "MQF6X",
            "MQF7X", "MQD8X", "MQF9X", "MQD10X", "MQF11X", "MQD12X", "MQF13X",
            "MQD14X", "MQF15X", "MQD16X", "MQF17X", "MQD18X", "MQF19X", "MQD20X",
            "MQF21X", "IPBPM1", "IPBPM2", "nBPM1", "nBPM2", "nBPM3", "MQM16FF",
            "MQM15FF", "MQM14FF", "MFB2FF", "MQM13FF", "MQM12FF", "MFB1FF",
            "MQM11FF", "MQD10BFF", "MQD10AFF", "MQF9BFF", "MSF6FF", "MQF9AFF",
            "MQD8FF", "MQF7FF", "MQD6FF", "MQF5BFF", "MSF5FF", "MQF5AFF",
            "MQD4BFF", "MSD4FF", "MQD4AFF", "MQF3FF", "MQD2BFF", "MQD2AFF",
            "MSF1FF", "MQF1FF", "MSD0FF", "MQD0FF", "M1&2IP", "MPIP", "MDUMP",
            "ICT1X", "ICTDUMP", "MW1X", "MW1IP", "MPREIP", "MIPA", "MIPB"
        ]
        # Use list comprehension to filter out strings starting with 'Z' or 'z'
        bpm_names_from_cfg = [string for string in bpmcorr if not string.lower().startswith('z')]
        # Check if the bpms in the config files are known to Epics
        bpm_ok = all(bpm in bpm_names for bpm in bpm_names_from_cfg)
        if not bpm_ok:
            bpms_unknown = [bpm for bpm in bpm_names_from_cfg if bpm not in bpm_names]
            print(f'Unknown bpms {bpms_unknown} removed from list')
        # Only retain BPMs in config file which are known by Epics
        bpmcorr_filtered = [element for element in bpmcorr if (element in bpm_names) or element.lower().startswith('z')]
        # Subset of BPMs and correctors from the config file
        self.bpmcorr = bpmcorr_filtered
        self.bpms = [string for string in self.bpmcorr if not string.lower().startswith('z')]
        self.corrs = [string for string in self.bpmcorr if string.lower().startswith('z')]
        # Index of the selected BPMs in the Epics PV ATF2:monitors
        self.bpm_indexes = [index for index, string in enumerate(bpm_names) if string in self.bpms]
    
    def read_correctors(self):
        print("Reading correctors' strengths...")
        bdes, bact = [], []
        for corrector in self.corrs:
            pv_des = PV(f'{corrector}:currentWrite')
            pv_act = PV(f'{corrector}:currentRead')
            bdes.append(pv_des.get())
            bact.append(pv_act.get())
        names = np.array(self.corrs)
        bdes = np.array(bdes)
        bact = np.array(bact)
        correctors = {
            "names": names,
            "bdes": bdes,
            "bact": bact
        }
        return correctors
    
    def read_bpms(self):
        print('Reading bpms...')
        p = PV('ATF2:monitors')
        x, y, tmit = [], [], []
        for sample in range(self.nsamples):
            a = p.get().reshape((-1, 10))
            x.append(a[self.bpm_indexes, 1])
            y.append(a[self.bpm_indexes, 2])
            tmit.append(a[self.bpm_indexes, 3])
            if self.nsamples>0:
                time.sleep(1)
        names = np.array(self.bpms)
        x = np.vstack(x)
        y = np.vstack(y)
        tmit = np.vstack(tmit)
        bpms = {
            "names": names,
            "x": x,
            "y": y,
            "tmit": tmit
        }
        return bpms

    def write_correctors(self, names, corr_vals):
        if type(corr_vals) == float:
            corr_vals = np.array([corr_vals])
        if type(names) == str:
            names = np.array([names])
        if names.size != corr_vals.size:
            print('Error: len(names) != len(corr_vals) in set_correctors(names, corr_vals)') 
        for corrector, corr_val in zip(names, corr_vals):
            pv_des = PV(f'{corrector}:currentWrite')
            pv_des.put(corr_val)
        time.sleep(1)
    
    def vary_correctors(self, names, corr_vals):
        if type(corr_vals) is float:
            corr_vals = np.array([corr_vals])
        if type(names) == str:
            names = np.array([names])
        if names.size != corr_vals.size:
            print('Error: len(names) != len(corr_vals) in vary_correctors(names, corr_vals)') 
        correctors = self.read_correctors()
        corr_indexes = [index for index, string in enumerate(correctors['names']) if string in names]
        old_val = correctors['bdes'][corr_indexes]
        self.write_correctors(names, old_val + corr_vals)
