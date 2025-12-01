import sys
import numpy as np
import time, math

from epics import PV, ca

class InterfaceATF2_Linac:
    def get_name(self):
        return 'ATF2_Linac'

    def __init__(self, nsamples=1):
        self.nsamples = nsamples
        # Bpms and correctors in beamline order
        sequence = [ 
            'MB5L', 'MB6L', 'MB7L', 'ZH1L', 'ZV1L', 'MB8L', 'MB9L', 'MB10L', 
            'ZV2L', 'ZH2L', 'MB11L', 'ML1L', 'ML2L', 'ZV3L', 'ZH3L', 'ML3L',
            'ZH4L', 'ZV4L', 'ZH5L', 'ZV5L', 'ML4L', 'ZH6L', 'ZV6L', 'ML5L',
            'ZH7L', 'ZV7L', 'ML6L', 'ZH8L', 'ZV8L', 'ML7L', 'ZH9L', 'ML8L',
            'ZV9L', 'ML9L', 'ZH10L', 'ML10L', 'ZV10L', 'ML11L', 'ZH11L',
            'ML12L', 'ZV11L', 'ML13L', 'ZH12L', 'ML14L', 'ZV12L', 'ML15L',
            'ZV10T', 'ZV11T', 'ML1T', 'ZV13L'
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
        # Index of the selected BPMs in the Epics PV ATF2:monitors
        self.bpm_indexes = [index for index, string in enumerate(monitors) if string in self.bpms]
        # Bunch current monitors
        self.ict_names = [
            'gun:GUNcharge', 'l0:L0charge', 'linacbt:LNEcharge', 'linacbt:BTMcharge',
            'ext:EXTcharge', 'linacbt:BTEcharge', 'BIM:DR:nparticles', 'BIM:IP:nparticles'
        ]
        pv = PV('CM1L:phaseRead')
        self.phase_kl1 = pv.get()

    def change_energy(self, rel_phase=5, **kwargs):
        pv = PV('CM1L:phaseWrite')
        pv.put(self.phase_kl1+rel_phase)
        time.sleep(1)
        
    def reset_energy(self,**kwargs):
        pv = PV('CM1L:phaseWrite')
        pv.put(self.phase_kl1)
        time.sleep(1)

    def change_intensity(self, laserintensity=0.1,ang_offset=2.0,**kwargs):
        start = time.perf_counter()

        laserintensity = 0.1

        if laserintensity <= 0.0:
            raise ValueError('Laser intensity should be strict positive')

        elif laserintensity >= 1.0:
            raise ValueError(f'Laser intensity should be below 1: {laserintensity}')

        elif laserintensity >= 0.30:
            raise ValueError(f'Laser intensity should be below 0.3 - internal warning {laserintensity}')

        else:
            ang_offset = 2.0

            angle = 180.0 / np.pi / 4.0 * math.acos(2.0 * laserintensity - 1.0) - ang_offset

            ### calculate current angle

            # read x_counter

            x_counter = PV('INJ:LaserIntensityXcount').get()

            # os.system('caget -# 1 INJ:LaserIntensityXcount > /tmp/bba_laserxcount.txt')
            # [name, dummy, x_counter] = np.genfromtxt('/tmp/bba_laserxcount.txt', '%s %f %f')

            print(x_counter)

            angle_read = np.mod(x_counter, 72000) / 200.0 + ang_offset

            if not hasattr(self, '_angle_before'):
                self._angle_before = angle_read

            pulse = np.int32((angle - angle_read) * 200)

            if pulse >= 0:
                print('laser up')
                PV('INJ:setLaserIntUpAngle').put(int(pulse))
                # os.system(f"caput INJ:setLaserIntUpAngle {int(pulse)}")
            else:
                print('laser down')
                pulse = -pulse
                PV('INJ:setLaserIntDownAngle').put(int(pulse))
                # os.system(f'caput INJ:setLaserIntDownAngle {int(pulse)}')

            PV('INJ:setLaserIntSend').put(1)
            # os.system('caput INJ:setLaserIntSend 1')
            time.sleep(0.5)
            PV('INJ:setLaserIntSend').put(1)
            # os.system('caput INJ:setLaserIntSend.PROC 1')

            time.sleep(3)
            elapsed = time.perf_counter() - start
            print('InterfaceATF2::ChangeBunchCharge()', elapsed)
            return self

    def reset_intensity(self,**kwargs):
        start = time.perf_counter()

        ang_offset = 2.0

        angle = self._angle_before

        ### calculate current angle

        # read x_counter

        x_counter = PV('INJ:LaserIntensityXcount').get()
        print(x_counter)

        # os.system('caget -# 1 INJ:LaserIntensityXcount > /tmp/bba_laserxcount.txt')
        # [name, dummy, x_counter] = np.genfromtxt('/tmp/bba_laserxcount.txt', '%s %f %f')

        angle_read = np.mod(x_counter, 72000) / 200.0 + ang_offset

        pulse = int((angle - angle_read) * 200)

        if pulse >= 0:
            print('laser up')
            PV('INJ:setLaserIntUpAngle').put(int(pulse))
            # os.system(f"caput INJ:setLaserIntUpAngle {int(pulse)}")
        else:
            print('laser down')
            pulse = -pulse
            PV('INJ:setLaserIntDownAngle').put(int(pulse))
            # os.system(f'caput INJ:setLaserIntDownAngle {int(pulse)}')

        PV('INJ:setLaserIntSend').put(1)
        # os.system('caput INJ:setLaserIntSend 1')
        time.sleep(0.5)

        PV('INJ:setLaserIntSend.PROC').put(1)
        # os.system('caput INJ:setLaserIntSend.PROC 1')

        time.sleep(3)
        elapsed = time.perf_counter() - start
        print('InterfaceATF2::ChangeBunchCharge()', elapsed)
        return self

    def get_sequence(self, *args):
        return self.sequence

    def get_bpms_names(self, *args):
        return self.bpms

    def get_correctors_names(self):
        return self.corrs

    def get_hcorrectors_names(self):
        return [string for string in self.corrs if (string.lower().startswith('zh')) or (string.lower().startswith('zx'))]


    def get_vcorrectors_names(self):
        return [string for string in self.corrs if string.lower().startswith('zv')]

    def get_elements_position(self,names):
        return [index for index, string in enumerate(self.sequence) if string in names]

    def get_icts(self):
        return None # Reading the icts is time consuming and unnecessary for SysID and BBA
        print("Reading ict's...")
        charge = []
        for ict in self.ict_names:
            pv = PV(f'{ict}')
            charge.append(pv.get())
        print("ICT's read.")
        names = [ self.ict_names ] if type(self.ict_names) == str else self.ict_names
        charge = np.array(charge)
        icts = { "names": names, "charge": charge }
        return icts

    def get_correctors(self):
        print("Reading correctors' strengths...")
        bdes, bact = [], []
        for corrector in self.corrs:
            pv_des = PV(f'{corrector}:currentWrite')
            pv_act = PV(f'{corrector}:currentRead')
            bdes.append(pv_des.get())
            bact.append(pv_act.get())
        names = [ self.corrs ] if type(self.corrs) == str else self.corrs
        bdes = np.array(bdes)
        bact = np.array(bact)
        correctors = { "names": names, "bdes": bdes, "bact": bact }
        return correctors
    
    def get_bpms(self):
        print('Reading bpms...')
        p = PV('LINAC:monitors')
        x, y, tmit = [], [], []
        for sample in range(self.nsamples):
            print(f'Sample = {sample}')
            a = p.get().reshape((-1, 20))
            status = a[self.bpm_indexes, 0]
            # Set elements that are not equal to 1 to zero
            status[status != 1] = 0
            x.append(a[self.bpm_indexes, 1])
            y.append(a[self.bpm_indexes, 2])
            tmit.append(status * a[self.bpm_indexes, 3])
            time.sleep(0.35)
        names = [ self.bpms ] if type(self.bpms) == str else self.bpms
        x = np.vstack(x) / 1e3 # mm
        y = np.vstack(y) / 1e3 # mm
        tmit = np.vstack(tmit)
        bpms = { "names": names, "x": x, "y": y, "tmit": tmit }
        return bpms

    def push(self, names, corr_vals):
        if type(corr_vals) == float:
            corr_vals = np.array([corr_vals])
        if type(names) == str:
            names = [names]
        if len(names) != corr_vals.size:
            print('Error: len(names) != len(corr_vals) in push(names, corr_vals)') 
        for corrector, corr_val in zip(names, corr_vals):
            pv_des = PV(f'{corrector}:currentWrite')
            pv_des.put(corr_val)
        time.sleep(1)
    
    def vary_correctors(self, names, corr_vals):
        if type(corr_vals) is float:
            corr_vals = np.array([corr_vals])
        if type(names) == str:
            names = [names]
        if len(names) != corr_vals.size:
            print('Error: len(names) != len(corr_vals) in vary_correctors(names, corr_vals)') 
        for corrector, corr_val in zip(names, corr_vals):
            pv_des = PV(f'{corrector}:currentWrite')
            curr_val = pv_des.get()
            pv_des.put(curr_val + corr_val)
        time.sleep(1)
