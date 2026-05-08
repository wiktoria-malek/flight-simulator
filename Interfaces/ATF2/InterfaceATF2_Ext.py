import sys, time, math, os
import numpy as np
from epics import PV, ca, caget
from Interfaces.AbstractMachineInterface import AbstractMachineInterface

class InterfaceATF2_Ext(AbstractMachineInterface):
    def get_name(self):
        return 'ATF2_Ext'

    def __init__(self, nsamples=1, nominal_intensity=0.15, wfs_intensity=0.1):
        self.nsamples = nsamples
        self.twiss_path = os.path.join(os.path.dirname(__file__), 'Ext_ATF2', 'ATF2_EXT_FF_v5.2.twiss')
        self.electronmass = 0.51099895 # MeV/c^2
        self.Pref = 1.2999999e3 # MeV/c, until a PV is specified
        self.screen_names = ['OTR0X', 'OTR1X', 'OTR2X', 'OTR3X']
        self.screen_pv_names = {
            'OTR0X': 'mOTR1',
            'OTR1X': 'mOTR2',
            'OTR2X': 'mOTR3',
            'OTR3X': 'mOTR4'
        }

        self.screen_image_shape = (960, 1280) # image size = 1280 x 960

        # Bpms and correctors in beamline order
        sequence = [
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
        sequence = [ 'MB1X', 'MB2X', 'ZV1X', 'MQF1X', 'ZV2X', 'MQD2X', 'MQF3X', 'ZH1X', 'ZV3X', 'MQF4X', 'ZH2X', 'MQD5X', 'ZV4X', 'ZV5X', 'MQF6X', 'MQF7X', 'ZVFB1X', 'ZHFB1X', 'ZH3X', 'MQD8X', 'ZV6X', 'ZHFB2X', 'MQF9X', 'ZH4X', 'ZVFB2X', 'ZV7X', 'MQD10X', 'ZH5X', 'MQF11X', 'ZV8X', 'MQD12X', 'ZH6X', 'MQF13X', 'MQD14X', 'ZH7X', 'MQF15X', 'ZV9X', 'MQD16X', 'ZH8X', 'MQF17X', 'ZV10X', 'MQD18X', 'ZH9X', 'MQF19X', 'ZV11X', 'MQD20X', 'ZVFB1FF', 'ZHFB1FF', 'ZH10X', 'MQF21X', 'MQM16FF', 'ZH1FF', 'ZV1FF', 'MQM15FF', 'MQM14FF', 'MQM12FF', 'MQM11FF', 'MQD10AFF', 'MQF9AFF', 'MQD8FF', 'MQF7FF', 'MQF5BFF', 'MQD4BFF', 'MQF3FF', 'MQD2BFF', 'MQD2AFF', 'MSF1FF', 'MPREIP', 'MW1IP', 'MPIP', 'MDUMP' ]
        # ATF2' BPMs Epics names
        # https://atf.kek.jp/atfbin/view/ATF/EPICS_DATABASE
        monitors = ['MB1X', 'MB2X', 'MQF1X', 'MQD2X', 'MQF3X', 'MQF4X',
                    'MQD5X', 'MQF6X', 'MQF7X', 'MQD8X', 'MQF9X', 'MQD10X', 'MQF11X',
                    'MQD12X', 'MQF13X', 'MQD14X', 'MQF15X', 'MQD16X', 'MQF17X', 'MQD18X',
                    'MQF19X', 'MQD20X', 'MQF21X', 'IPBPM1', 'IPBPM2', 'nBPM1', 'nBPM2',
                    'nBPM3', 'MQM16FF', 'MQM15FF', 'MQM14FF', 'MFB2FF', 'MQM13FF',
                    'MQM12FF', 'MFB1FF', 'MQM11FF', 'MQD10BFF', 'MQD10AFF', 'MQF9BFF',
                    'MSF6FF', 'MQF9AFF', 'MQD8FF', 'MQF7FF', 'MQD6FF', 'MQF5BFF',
                    'MSF5FF', 'MQF5AFF', 'MQD4BFF', 'MSD4FF', 'MQD4AFF', 'MQF3FF',
                    'MQD2BFF', 'MQD2AFF', 'MSF1FF', 'MQF1FF', 'MSD0FF', 'MQD0FF',
                    'M1&2IP', 'MPIP', 'MDUMP', 'ICT1X', 'ICTDUMP', 'MW1X', 'MW1IP',
                    'MPREIP', 'MIPA', 'MIPB']


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
        self.nominal_laser_intensity = nominal_intensity
        self.test_laser_intensity = wfs_intensity
        #PV('RFGun:LaserIntensity1:Read').get()

    def get_beam_factors(self):
        # TO BE REPLACED WITH A PV OF REAL BEAM ENERGY
        gamma_rel = np.sqrt((self.Pref / self.electronmass) ** 2 + 1.0)
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
        PV('RAMP:CONTROL_ON_SW').put(1)
        time.sleep(2)
        ### delta_freq MUST MATCH :MI2: to EPICS --> means "MINUS2"
        delta_freq = +4 # kHz
        # PV('RAMP:MI2:ONOFF_SW').put(1)
        PV('RAMP:PL4:ONOFF_SW').put(1)
        time.sleep(2)
        DR_freq = 714e3; # 714 MHz in kHz
        DR_momentum_compaction = 2.1e-3
        dP_P = -delta_freq / DR_freq / DR_momentum_compaction
        return dP_P

    def reset_energy(self):
        PV('RAMP:CONTROL_OFF_SW').put(0)
        time.sleep(2)

    def change_intensity(self):
        new_laser_intensity = self.test_laser_intensity
        print(f'Changing laser intensity to {new_laser_intensity}...')
        laser_intensity = new_laser_intensity * 100 * 5 # Korysko dixit: 100 for percent, 5 convesion factor
        PV('RFGun:LaserIntensity1:Write').put(laser_intensity)
        time.sleep(3)
        return self

    def reset_intensity(self):
        new_laser_intensity = self.nominal_laser_intensity
        print(f'Resetting laser intensity to {new_laser_intensity}...')
        laser_intensity = new_laser_intensity * 100 * 5 # Korysko dixit: 100 for percent, 5 convesion factor
        PV('RFGun:LaserIntensity1:Write').put(laser_intensity)
        time.sleep(3)
        return self
    
    def get_sequence(self):
        return self.sequence

    def get_hcorrectors_names(self):
        return [string for string in self.corrs if (string.lower().startswith('zh')) or (string.lower().startswith('zx'))]

    def get_vcorrectors_names(self):
        return [string for string in self.corrs if string.lower().startswith('zv')]

    def get_elements_indices(self,names):
        return [index for index, string in enumerate(self.sequence) if string in names]

    def get_target_dispersion(self, names=None): # for DR too
        if names is None:
            names = self.bpms
        if isinstance(names, str):
            names = [names]
        twiss_path = self.twiss_path
        with open(twiss_path, "r") as file:
            lines = [line.strip() for line in file if line.strip()]

        star_symbol = next(i for i, line in enumerate(lines) if line.startswith("*"))
        dollar_sign = next(i for i, line in enumerate(lines) if line.startswith("$") and i > star_symbol)
        columns = lines[star_symbol].lstrip("*").split()
        try:
            DX_column = columns.index("DX")
            DY_column = columns.index("DY")
            elements_names = columns.index("NAME")
        except ValueError as e:
            raise RuntimeError("There are no such columns in the twiss file")
        disp_values = {}
        target_disp_x, target_disp_y = [], []
        for line in lines[dollar_sign + 1:]:
            data = line.split()
            if len(data) <= max(DX_column, DY_column,
                                elements_names):  # if a line has less column than needed, it is omitted
                continue
            bpms_name = data[elements_names].strip('"')
            try:
                disp_values[bpms_name] = (float(data[DX_column]), float(data[DY_column]))
            except ValueError:
                continue
        for bpm in names:
            if bpm in disp_values:
                dx, dy = disp_values[bpm]
            else:
                dx, dy = float("nan"), float("nan")
            target_disp_x.append(dx)
            target_disp_y.append(dy)
        return target_disp_x, target_disp_y

    def get_icts(self, names=None):
        print("Reading ict's...")
        charge = []
        for ict in self.ict_names:
            pv = PV(f'{ict}')
            charge.append(pv.get())

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
        x, y, tmit = [], [], []
        for sample in range(self.nsamples):
            try:
                print(f'Sample = {sample}')
                m = caget('ATF2:monitors')
                a = m.reshape((-1, 10))
                status = a[self.bpm_indexes, 0]
                status[status != 1] = 0
                x.append(a[self.bpm_indexes, 1])
                y.append(a[self.bpm_indexes, 2])
                print('Interface::get_bpms() = ', a[self.bpm_indexes, 1])
                tmit.append(status * a[self.bpm_indexes, 3])
                time.sleep(1)
            except Exception as e:
                print(f'An error occurred: {e}')
                sample = sample - 1

        bpms = {
            "names": self.bpms,
            "x": np.vstack(x) / 1e3,
            "y": np.vstack(y) / 1e3,
            "tmit": np.vstack(tmit),
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

    def _wait_for_corrector_readback(self, corrector, target, tolerance=1e-4, timeout=1.0, poll_interval=0.05):
        readback_pv = PV(f'{corrector}:currentRead')
        t0 = time.perf_counter()
        last_value = np.nan
        while time.perf_counter() - t0 < timeout:
            try:
                last_value = self.make_safe_float(readback_pv.get(), default=np.nan)
            except Exception:
                last_value = np.nan
            if np.isfinite(last_value) and abs(last_value - float(target)) <= tolerance:
                return True
            time.sleep(poll_interval)
        print(
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
