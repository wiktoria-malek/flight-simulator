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

    def _read_twiss_file(self):
        with open(self.twiss_path, "r") as file:
            lines = [line.strip() for line in file if line.strip()]
        star_symbol = next(i for i, line in enumerate(lines) if line.startswith("*"))
        dollar_sign = next(i for i, line in enumerate(lines) if line.startswith("$") and i > star_symbol)
        columns = lines[star_symbol].lstrip("*").split()
        return lines, columns, dollar_sign

    def  _get_twiss_s_positions(self, names):
        names = list(names)
        lines, columns, dollar_sign = self._read_twiss_file()
        try:
            name_column = columns.index("NAME")
            s_column = columns.index("S")
        except ValueError:
            return [np.nan] * len(names)
        s_pos = {}

        for line in lines[dollar_sign + 1:]:
            data = line.split()
            if len(data) <= max(name_column, s_column):
                continue
            elem_name = data[name_column].strip('"')
            try:
                s_pos[elem_name] = float(data[s_column])
            except ValueError:
                continue
        return [s_pos.get(name, np.nan) for name in names]

    @staticmethod
    def make_safe_float(value, default = np.nan): #so even if pv returns none, empty array or whatever, interface still works
        try:
            if value is None:
                return float(default)
            arr = np.asarray(value)
            if arr.size == 0:
                return float(default)
            return float(arr.flat[0])
        except Exception:
            return float(default)

    def _valid_pv_value(self, pv_names, default = np.nan):
        for pv_name in pv_names:
            try:
                value = caget(pv_name)
            except Exception:
                continue
            value = self.make_safe_float(value, default = np.nan)
            if np.isfinite(value):
                return value
        return float(default)

    def _read_screen_status(self, screen_pv_name):
        return self.make_safe_float(caget(f'{screen_pv_name}:Target:READ:INOUT'), default=np.nan)

    def _read_screen_calibration(self, screen_pv_name, plane):
        if plane.lower()=='h':
            pvs = [
                f'{screen_pv_name}:H:x1:Calibration:Factor',
                f'{screen_pv_name}:H:X1:Calibration:Factor',
            ]
        else:
            pvs = [
                f'{screen_pv_name}:V:y1:Calibration:Factor',
                f'{screen_pv_name}:V:Y1:Calibration:Factor',
            ]
        return self._valid_pv_value(pvs, default = np.nan)

    def _acquire_screen_image(self, screen_pv_name):
        try:
            PV(f'{screen_pv_name}:CAMERA:Acquire').put(1)
            time.sleep(2)
        except Exception:
            pass

        raw_img = caget(f'{screen_pv_name}:IMAGE:ArrayData')
        if raw_img is None:
            return None
        raw_img = np.asanyarray(raw_img)
        if raw_img.size == 0:
            return None

        nx, ny = self.screen_image_shape
        correct_image_size = ny * nx
        if raw_img.size < correct_image_size:
            return None
        raw_img = raw_img[:correct_image_size]

        image = raw_img.reshape((ny, nx)).astype(float)
        return image

    @staticmethod
    def _screen_data_from_image(image,hpixel,vpixel):
        if image is None:
            return np.nan, np.nan, np.nan, np.nan, 0.0, np.zeros((1,1)), np.array([0.0, 1.0]), np.array([0.0, 1.0])
        img = np.asarray(image, dtype=float)
        img[~np.isfinite(img)] = 0.0
        total = float(np.sum(img)) # intensity
        ny ,nx  = img.shape # rows, columns

        if total <= 0.0 or nx == 0 or ny == 0:
            hedges = np.arange(nx + 1, dtype = float) * (hpixel if np.isfinite(hpixel) and hpixel > 0 else 1)
            vedges = np.arange(ny + 1, dtype = float) * (vpixel if np.isfinite(vpixel) and vpixel > 0 else 1)

            return np.nan, np.nan, np.nan, np.nan, 0.0, img, hedges, vedges

        if not np.isfinite(hpixel) or hpixel <= 0:
            hpixel = 1e-3
        if not np.isfinite(vpixel) or vpixel <= 0:
            vpixel = 1e-3

        x_centers = (np.arange(nx, dtype = float) - 0.5 * (nx -1)) * hpixel # middle of the pixel
        y_centers = (np.arange(ny, dtype = float) - 0.5 * (ny -1) ) * vpixel

        proj_x = np.sum(img, axis = 0)
        proj_y = np.sum(img, axis = 1)

        x_mean = float(np.sum(x_centers * proj_x) / total)
        y_mean = float(np.sum(y_centers * proj_y) / total)
        sigx = float(np.sqrt(max(np.sum(((x_centers - x_mean) ** 2) * proj_x) / total, 0.0)))
        sigy = float(np.sqrt(max(np.sum(((y_centers - y_mean) ** 2) * proj_y) / total, 0.0)))

        hedges = (np.arange(nx + 1, dtype = float) - 0.5 * nx) * hpixel
        vedges = (np.arange(ny + 1, dtype = float) - 0.5 * ny) * vpixel

        return x_mean, y_mean, sigx, sigy, total, img, hedges, vedges

    def get_screens(self, names=None):
        print('Reading screens...')

        if isinstance(names, str):
            names = [names]
        selected_names = self.screen_names if names is None else [name for name in self.screen_names if name in names]

        s_positions = self._get_twiss_s_positions(selected_names)

        hpixel_list = []
        vpixel_list = []
        xb_list = []
        yb_list = []
        sigx_list = []
        sigy_list = []
        sum_list = []
        images = []
        hedges_all = []
        vedges_all = []
        inout_list = [] # is screen in or out

        for screen_name in selected_names:
            screen_pv_name = self.screen_pv_names.get(screen_name)
            if screen_pv_name is None:
                hpixel_list.append(np.nan)
                vpixel_list.append(np.nan)
                xb_list.append(np.nan)
                yb_list.append(np.nan)
                sigx_list.append(np.nan)
                sigy_list.append(np.nan)
                sum_list.append(0.0)
                images.append(np.zeros((1, 1)))
                hedges_all.append(np.array([0.0, 1.0]))
                vedges_all.append(np.array([0.0, 1.0]))
                inout_list.append(np.nan)
                continue

            status = self._read_screen_status(screen_pv_name)
            hpixel = self._read_screen_calibration(screen_pv_name, 'h')
            vpixel = self._read_screen_calibration(screen_pv_name, 'v')
            image = self._acquire_screen_image(screen_pv_name)
            x_mean, y_mean, sigx, sigy, total, image, hedges, vedges = self._screen_data_from_image(image, hpixel, vpixel)

            hpixel_list.append(hpixel)
            vpixel_list.append(vpixel)
            xb_list.append(x_mean)
            yb_list.append(y_mean)
            sigx_list.append(sigx)
            sigy_list.append(sigy)
            sum_list.append(total)
            images.append(image)
            hedges_all.append(hedges)
            vedges_all.append(vedges)
            inout_list.append(status)

        screens = {
            "names": selected_names,
            "hpixel": np.asarray(hpixel_list, dtype=float),
            "vpixel": np.asarray(vpixel_list, dtype=float),
            "x": np.asarray(xb_list, dtype=float),
            "y": np.asarray(yb_list, dtype=float),
            "sigx": np.asarray(sigx_list, dtype=float),
            "sigy": np.asarray(sigy_list, dtype=float),
            "sum": np.asarray(sum_list, dtype=float),
            "hedges": hedges_all,
            "vedges": vedges_all,
            "images": images,
            "S": np.asarray(s_positions, dtype=float),
            "inout": np.asarray(inout_list, dtype=float),
        }
        return screens

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

    def get_elements_position(self,names):
        return [index for index, string in enumerate(self.sequence) if string in names]

    def get_target_dispersion(self, names=None):
        if names is None:
            names = self.bpms
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
        time.sleep(1)

    def vary_correctors(self, names, corr_vals):
        if isinstance(names, str):
            names = [names]
        if not isinstance(corr_vals, (list, tuple, np.ndarray)):
            corr_vals = [corr_vals]
        if len(names) != len(corr_vals):
            print('Error: len(names) != len(corr_vals) in vary_correctors(names, corr_vals)')
        for corrector, corr_val in zip(names, corr_vals):
            pv_des = PV(f'{corrector}:currentWrite')
            curr_val = pv_des.get()
            pv_des.put(curr_val + corr_val)
        time.sleep(1)
