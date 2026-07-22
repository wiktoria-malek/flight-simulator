import sys, time, math, os
import numpy as np
import pyda, pyda_japc

try:
    from Interfaces.CLEAR import config
    try:
        from Interfaces.CLEAR import clear_lattice
    except Exception:
        clear_lattice = None
except ImportError:
    import config
    try:
        import clear_lattice
    except Exception:
        clear_lattice = None
from Interfaces.AbstractMachineInterface import AbstractMachineInterface

class CLEAR_real_machine(AbstractMachineInterface):
    def get_name(self):
        return 'CLEAR'

    def __init__(self, nsamples=1, nominal_intensity=1.5, wfs_intensity=1.0):
        self.nsamples = nsamples
        self.electronmass = 0.51099895 # MeV/c^2
        self.Pref = 198 # MeV/c
        self.laser_attenuator_readback = [
            'CA.GUN-ATTN/AQN#actualPosition',
            'CA.GUN-ATTN/CMD#requestedPosition',
        ]
        self.laser_attenuator_min = 0.0
        self.laser_attenuator_max = 3.0
        self.laser_motor_attenuator_readback = [
            'CTF2Motor2B/Acquisition#position',
            'CTF2Motor2B/Acquisition#actualPosition',
            'CTF2Motor2B/Status#position',
            'CTF2Motor2B/Setting#targetPosition',
        ]

        self.uv_attenuator_params = {
            'UVATT1': 'CO.TOWB.101.UVATT1/Setting#position',
            'UVATT2': 'CO.TOWB.102.UVATT2/Setting#position',
        }
        self.uv_attenuator_ranges = {
            'UVATT1': (2017.0, 5526.0),
            'UVATT2': (1549.0, 5159.0),
        }
        self.shutter_set_params = {
            'UVBEAM1': 'CO.TOSL.101.UVBEAM1_Set_Pos/SettingBoolean#value',
            'UVBEAM2': 'CO.TOSL.101.UVBEAM2_Set_Pos/SettingBoolean#value',
        }
        self.shutter_readback_params = {
            'UVBEAM1': 'CO.TOSL.101.UVBEAM1_Acq_Pos/AcquisitionBoolean#value',
            'UVBEAM2': 'CO.TOSL.101.UVBEAM2_Acq_Pos/AcquisitionBoolean#value',
        }

        self.energy_param = [
            'CA.BEAM/Acquisition#momentum',
            'CA.BEAM/Acquisition#energy',
        ]

        self.context = "SCT.USER.SETUP"
        self.log = print
        self.client = pyda.SimpleClient(provider=pyda_japc.JapcProvider())

        # Bpms and correctors in beamline order
        sequence = [
            'CA.DHG0130', 'CA.DVG0130', 'CA.BPC0220',
            'CA.DHG0225', 'CA.DVG0225', 'CA.BPC0240',
            'CA.DHG0245', 'CA.DVG0245', 'CA.BPC0260',
            'CA.DHG0265', 'CA.BPC0310',
            'CA.DHG0320', 'CA.DVG0320', 'CA.SDV0340',
            'CA.QFD0350', 'CA.QDD0355', 'CA.QFD0360',
            'CA.DHG0385', 'CA.DVG0385',
            'CA.BTV0390L', 'CA.BTV0390H',
            'CA.QFD0510', 'CA.QDD0515', 'CA.QFD0520',
            'CA.BPM0530', 'CA.DHJ0540', 'CA.DVJ0540',
            'CA.DHJ0590', 'CA.DVJ0590', 'CA.BPM0595',
            'CA.BTV0620', 'CA.BPM0690', 'CA.DHJ0710', 'CA.DVJ0710',
            'CA.BTV0730', 'CA.QFD0760', 'CA.QDD0765', 'CA.QFD0770',
            'CA.DHJ0780', 'CA.DVJ0780', 'CA.BTV0810', 'CA.BPM0820',
            'CA.DHJ0840', 'CA.DVJ0840',
            'CA.QDD0870', 'CA.QFD0880', 'CA.BPM0890', 'CA.BTV0910',
        ]

        monitors = [
                     'CA.BPC0220', 'CA.BPC0240', 'CA.BPC0260',
                     'CA.BPC0310', 'CA.BPM0530', 'CA.BPM0595',
                     'CA.BPM0690', 'CA.BPM0820', 'CA.BPM0890',
        ]

        correctors = [
            'CA.DHG0130', 'CA.DVG0130',
            'CA.DHG0225', 'CA.DVG0225',
            'CA.DHG0245', 'CA.DVG0245',
            'CA.DHG0265',
            'CA.DHG0320', 'CA.DVG0320',
            'CA.SDV0340',
            'CA.DHG0385', 'CA.DVG0385',
            'CA.DHJ0540', 'CA.DVJ0540',
            'CA.DHJ0590', 'CA.DVJ0590',
            'CA.DHJ0710', 'CA.DVJ0710',
            'CA.DHJ0780', 'CA.DVJ0780',
            'CA.DHJ0840', 'CA.DVJ0840',
        ]

        self.screen_status_params = {
            "CA.BTV0390L": "CA.BTV0390_CAS.BTV0420/OPSettingSystem1#positionChannel1",
            "CA.BTV0390H": "CA.BTV0390_CAS.BTV0420/OPSettingSystem1#positionChannel1",
            "CA.BTV0620":  "CAS.BTV0440_CA.BTV0620/OPSettingSystem2#positionChannel2",
            "CA.BTV0730":  "CA.BTV0730_CA.BTV0800/OPSettingSystem1#positionChannel1",
            "CA.BTV0810":  "CA.BTV0805_CA.BTV0810/OPSettingSystem2#positionChannel2",
            "CA.BTV0910":  "CA.BTV0910_CAS.BTV0930/OPSettingSystem1#positionChannel1",
        }

        self.corrector_set_params = {name: f'{name}/SettingPPM' for name in correctors}
        self.corrector_get_params = {name: f'{name}/Acquisition' for name in correctors}

        self.sextupoles = []
        self.quadrupoles = list(config.quad_names)
        monitors_from_sequence = [element for element in sequence if element in monitors]
        bpm_ok = all(bpm in monitors for bpm in monitors_from_sequence)
        if not bpm_ok:
            bpms_unknown = [bpm for bpm in monitors_from_sequence if bpm not in monitors]
            self.log(f'Unknown bpms {bpms_unknown} removed from list')

        sequence_filtered = [
            element for element in sequence
            if element in monitors or element in correctors or element in self.quadrupoles or element in config.cameras
        ]
        self.sequence = sequence_filtered
        self.bpms = [element for element in self.sequence if element in monitors]
        self.corrs = [element for element in self.sequence if element in correctors]
        self.screen_names = list(config.cameras.keys())
        self.screens = self.screen_names
        self.screen_config = config.cameras
        self.bpm_indexes = [index for index, string in enumerate(sequence) if string in self.bpms]

        # Bunch current monitors
        self.ict_names = [
            'CA.BCMGUN/Acquisition#charge',
            'CA.BCMVESPER/Acquisition#charge',
            'CA.BCM0395/Acquisition#charge',
            'CS.BCM0620/Acquisition#charge',
            'CA.BCMTHZ/Acquisition#charge',
            'CA.BCMTHZ2/Acquisition#charge',
        ]

        self.bcm_sample_params = {
            "Gun_BCM": "CA.SABCM01/Samples#samples",
            "Vesper_BCM": "CA.SABPMCAL-SIS5-2/Samples#samples",
        }

        self.bcm_sensitivity = {
            "6dB": 2.085,
            "12dB": 4.18,
            "18dB": 8.35,
            "20dB": 10.42,
            "26dB1": 20.97,
            "26dB2": 20.95,
            "32dB": 41.9,
            "40dB": 105.0,
        }
        self.nominal_laser_intensity = nominal_intensity
        self.test_laser_intensity = wfs_intensity
        self.quadrupoles = list(config.quad_names)
        self.quad_set_params = dict(zip(config.quad_names, config.current_set_params))
        self.quad_get_params = dict(zip(config.quad_names, config.current_get_params))
        self.quad_status_params = dict(zip(config.quad_names, config.current_status_params))

        self.twiss_path = None

    def get_beam_factors(self):
        pref = self.Pref
        try:
            data = self.client.get("CA.BEAM/Acquisition").data
        except Exception as e:
            data={}
        for field in ("momentum", "energy"):
            value = self.make_safe_float(data.get(field), default = np.nan)
            if np.isfinite(value) and value > 0:
                pref = value
                break
        gamma_rel = np.sqrt((pref / self.electronmass) ** 2 + 1.0)
        beta_rel = np.sqrt(1.0 - 1.0 / gamma_rel ** 2)
        return gamma_rel, beta_rel

    def _read_twiss_file(self):
        if self.twiss_path is None:
            raise FileNotFoundError('No CLEAR twiss file configured')
        with open(self.twiss_path, "r") as file:
            lines = [line.strip() for line in file if line.strip()]
        star_symbol = next(i for i, line in enumerate(lines) if line.startswith("*"))
        dollar_sign = next(i for i, line in enumerate(lines) if line.startswith("$") and i > star_symbol)
        columns = lines[star_symbol].lstrip("*").split()
        return lines, columns, dollar_sign

    def _get_twiss_s_positions(self, names):
        names = list(names)

        if clear_lattice is not None and hasattr(clear_lattice, 'element_descriptions'):
            s_pos = {}
            for elem_name, elem_data in clear_lattice.element_descriptions.items():
                if isinstance(elem_data, dict) and 's_center' in elem_data:
                    s_pos[elem_name] = elem_data['s_center']
            return [s_pos.get(name.rstrip('LH'), s_pos.get(name, np.nan)) for name in names]

        if self.twiss_path is None:
            return [np.nan] * len(names)

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
    def make_safe_float(value, default=np.nan):  # so even if japc address returns none, empty array or whatever, interface still works
        try:
            if value is None:
                return float(default)
            arr = np.asarray(value)
            if arr.size == 0:
                return float(default)
            return float(arr.flat[0])
        except Exception:
            return float(default)

    def change_energy(self):
        self.log('Function change_energy needs implementation.')
        return 0.0

    def reset_energy(self):
        self.log('Function reset_energy needs implementation.')

    def change_intensity(self):
        target_position = self.set_laser_motor_attenuator_position(self.test_laser_intensity)
        self.log(f'CLEAR test intensity set through motor attenuator: {target_position:.3f} ksteps')
        return self

    def reset_intensity(self):
        target_position = self.set_laser_motor_attenuator_position(self.nominal_laser_intensity)
        self.log(f'CLEAR nominal intensity restored through motor attenuator: {target_position:.3f} ksteps')
        return self

    def get_sequence(self):
        return self.sequence

    def get_hcorrectors_names(self):
        return [name for name in self.corrs if ("DHG" in name) or ("DHJ" in name)]

    def get_vcorrectors_names(self):
        return [name for name in self.corrs if ("DVG" in name) or ("DVJ" in name) or ("SDV" in name)]

    def get_elements_indices(self, names):
        if isinstance(names, str):
            names = [names]
        name_to_index = {string: index for index, string in enumerate(self.sequence)}
        return [name_to_index.get(name, np.nan) for name in names]

    def _read_screen_status(self, screen_name):
        try:
            address = self.screen_status_params[screen_name]
            property_address, field = address.rsplit("#", 1)
            value = self.client.get(property_address, context=self.context).data[field]
            return self.make_safe_float(value)
        except Exception as exc:
            self.log(f"Could not read screen status for {screen_name}: {exc}")
            return np.nan

    def _acquire_screen_data(self, screen_name):
        japc_camera = self.screen_config.get(screen_name, {}).get("japc_name", screen_name.rstrip("LH"))
        camera_config = self.screen_config.get(screen_name, {})
        selector = camera_config.get("japc_selector", self.context)
        try:
            return self.client.get(f"{japc_camera}.DigiCam/LastImage", context=selector).data
        except Exception as exc:
            self.log(f"Could not read camera data from {screen_name}. Reason: {exc}")
            return None

    def set_screen_camera_on(self, screen_name, on=True):
        japc_camera = self.screen_config.get(screen_name, {}).get('japc_name', screen_name.rstrip('LH'))
        self.client.set(f'{japc_camera}.DigiCam/Setting', {"cameraSwitch": int(bool(on))})

    def set_screen_filter(self, screen_name, filter_value):
        japc_camera = self.screen_config.get(screen_name, {}).get('japc_name', screen_name.rstrip('LH'))
        self.client.set(f'{japc_camera}.DigiCam/Setting', {"filterSelect": filter_value})

    def set_screen_video_gain(self, screen_name, gain_value):
        japc_camera = self.screen_config.get(screen_name, {}).get('japc_name', screen_name.rstrip('LH'))
        self.client.set(f'{japc_camera}.DigiCam/Setting', {"videoGain": gain_value})

    def set_screen_select(self, screen_name, screen_value):
        japc_camera = self.screen_config.get(screen_name, {}).get('japc_name', screen_name.rstrip('LH'))
        self.client.set(f'{japc_camera}.DigiCam/Setting', {"screenSelect": screen_value})

    def get_icts(self, names=None):
        self.log("Reading ict's...")
        if names is None:
            names = self.ict_names
        if isinstance(names, str):
            names = [names]
        charge = []
        for name in names:
            property_address, field = name.rsplit("#", 1)
            try:
                value = self.client.get(property_address, context=self.context).data[field]
            except Exception:
                value = np.nan
            charge.append(self.make_safe_float(value))
        return {
            "names": list(names),
            "charge": np.asarray(charge, dtype=float),
        }

    def get_correctors(self, names=None):
        #{corr_name}/SettingPPM#current
        self.log("Reading correctors' strengths...")
        selected_names = self.corrs if names is None else ([names] if isinstance(names, str) else list(names))

        bdes, bact = [], []
        for corrector in selected_names:
            setting_data = self.client.get(self.corrector_set_params[corrector],context = self.context).data
            acquisition_data = self.client.get(self.corrector_get_params[corrector], context = self.context).data
            bdes.append(setting_data['current'])
            bact.append(acquisition_data['currentAverage'])

        return {
            "names": list(selected_names),
            "bdes": np.asarray(bdes, dtype=float),
            "bact": np.asarray(bact, dtype=float),
        }

    def get_bpms(self, names=None):
        self.log('Reading bpms...')
        selected_names = self.bpms if names is None else ([names] if isinstance(names, str) else list(names))

        x, y, tmit = [], [], []
        for sample in range(self.nsamples):
            self.log(f'Sample = {sample}')
            x_sample, y_sample, tmit_sample = [], [], []
            for bpm in selected_names:
                x_sample.append(self._read_bpm_plane(bpm, 'x'))
                y_sample.append(self._read_bpm_plane(bpm, 'y'))
                tmit_sample.append(self._read_bpm_intensity(bpm))
            x.append(x_sample)
            y.append(y_sample)
            tmit.append(tmit_sample)
            time.sleep(1)

        return {
            "names": list(selected_names),
            "x": np.asarray(x, dtype=float),
            "y": np.asarray(y, dtype=float),
            "tmit": np.asarray(tmit, dtype=float),
        }


    def _wait_for_corrector_readback(self, corrector, target, tolerance=1e-4, timeout=1.0, poll_interval=0.05):
        readback_param = self.corrector_get_params[corrector]
        t0 = time.perf_counter()
        last_value = np.nan
        while time.perf_counter() - t0 < timeout:
            try:
                data = self.client.get(readback_param, context=self.context).data
                last_value = self.make_safe_float(data.get('currentAverage'), default=np.nan)
            except Exception:
                last_value = np.nan

            if np.isfinite(last_value) and abs(last_value - float(target)) <= tolerance:
                return True
            time.sleep(poll_interval)
        self.log(
            f'Warning: {readback_param} did not reach target {float(target):.6g} '
            f'within {timeout:.2f}s. Last readback = {last_value:.6g}'
        )
        return False

    def set_correctors(self, names, corr_vals):
        if isinstance(names, str):
            names = [names]
        if not isinstance(corr_vals, (list, tuple, np.ndarray)):
            corr_vals = [corr_vals]
        if len(names) != len(corr_vals):
            self.log('Error: len(names) != len(corr_vals) in set_correctors(names, corr_vals)')
            return
        for corrector, corr_val in zip(names, corr_vals):
            target = float(corr_val)
            self.client.set(self.corrector_set_params[corrector], {'current': target}, context=self.context)
            self._wait_for_corrector_readback(corrector, target)

    def vary_correctors(self, names, corr_vals):
        if isinstance(names, str):
            names = [names]
        if not isinstance(corr_vals, (list, tuple, np.ndarray)):
            corr_vals = [corr_vals]
        if len(names) != len(corr_vals):
            self.log('Error: len(names) != len(corr_vals) in vary_correctors(names, corr_vals)')
            return
        current = self.get_correctors(names)['bdes']
        target = current + np.asarray(corr_vals, dtype=float)
        self.set_correctors(names, target)

    def get_quadrupoles(self, names=None):
        if names is None:
            names = self.quadrupoles
        if isinstance(names, str):
            names = [names]

        bdes = []
        bact = []

        for quadrupole in names:
            set_address = self.quad_set_params[quadrupole]
            set_property, set_field = set_address.rsplit("#", 1)

            get_address = self.quad_get_params[quadrupole]
            get_property, get_field = get_address.rsplit("#", 1)

            try:
                set_value = self.client.get(set_property, context=self.context).data[set_field]
            except Exception:
                set_value = np.nan
            try:
                get_value = self.client.get(get_property, context=self.context).data[get_field]
            except Exception:
                get_value = np.nan

            bdes.append(self.make_safe_float(set_value))
            bact.append(self.make_safe_float(get_value))

        return {
            "names": list(names),
            "bdes": np.asarray(bdes, dtype=float),
            "bact": np.asarray(bact, dtype=float),
        }

    def set_quadrupoles(self, names, values):
        if isinstance(names, str):
            names = [names]
        if not isinstance(values, (list, tuple, np.ndarray)):
            values = [values]
        if len(names) != len(values):
            raise ValueError(f"len(names)={len(names)} != len(values)={len(values)}")

        for quadrupole, value in zip(names, values):
            address = self.quad_set_params[quadrupole]
            property_address, field = address.rsplit("#", 1)
            self.client.set(property_address, {field: float(value)}, context=self.context)

        time.sleep(1)

    def _read_bpm_plane(self, bpm, plane):
        plane = plane.lower()
        try:
            data = self.client.get(f"{bpm}/Acquisition", context=self.context).data
            return self.make_safe_float(data.get(plane), default=np.nan)
        except Exception:
            return np.nan

    def _read_bpm_intensity(self, bpm):
        try:
            data = self.client.get(f"{bpm}/Acquisition", context=self.context).data
        except Exception:
            return np.nan
        for field in ("intensity", "sum", "charge"):
            if field in data:
                return self.make_safe_float(data[field], default=np.nan)
        return np.nan

    # def insert_screen(self, screen_name):
    #     screen_pv_name = self.screen_pv_names.get(screen_name)
    #     if screen_pv_name is None:
    #         raise ValueError(f"Unknown screen: {screen_name}")
    #     status = PV(f'{screen_pv_name}:Target:READ:INOUT').get()
    #     PV(f"{screen_pv_name}:Target:WRITE:IN").put(1)
    #
    # def extract_screen(self, screen_name):
    #     screen_pv_name = self.screen_pv_names.get(screen_name)
    #     if screen_pv_name is None:
    #         raise ValueError(f"Unknown screen: {screen_name}")
    #     PV(f"{screen_pv_name}:Target:WRITE:OUT").put(1)

    def get_screens(self, names=None):
        self.log('Reading screens...')

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
        inout_list = []

        for screen_name in selected_names:
            camera_config = self.screen_config.get(screen_name, {}) # gets pixel size and resolutino
            hpixel = float(camera_config.get('s_x_res', np.nan))
            vpixel = float(camera_config.get('s_y_res', np.nan))
            status = self._read_screen_status(screen_name) # is screen inserted or extracted?
            camera_data = self._acquire_screen_data(screen_name)
            if camera_data is None:
                x_mean = np.nan
                y_mean = np.nan
                sigx = np.nan
                sigy = np.nan
                total = 0.0
                image = np.zeros((1,1))
                hedges = np.array([0.0, 1.0])
                vedges = np.array([0.0, 1.0])
            else:
                image = np.asarray(camera_data["image2D"], dtype=float)
                proj_x = np.asarray(camera_data["projDataSet1"], dtype=float)
                proj_y = np.asarray(camera_data["projDataSet2"], dtype=float)
                x_positions = np.asarray(camera_data["imagePositionSet1"], dtype=float)
                y_positions = np.asarray(camera_data["imagePositionSet2"], dtype=float)
                proj_x = np.nan_to_num(proj_x, nan = 0.0)
                proj_y = np.nan_to_num(proj_y, nan = 0.0)
                proj_x = proj_x - np.min(proj_x)
                proj_y = proj_y - np.min(proj_y)
                total_x = float(np.sum(proj_x))
                total_y = float(np.sum(proj_y))
                total = float(np.nansum(image))
                if total_x > 0.0:
                    x_mean = float(np.sum(x_positions * proj_x) / total_x)
                    sigx = float(np.sqrt(np.sum((x_positions - x_mean) ** 2 * proj_x) / total_x))
                else:
                    x_mean = np.nan
                    sigx = np.nan
                if total_y > 0.0:
                    y_mean = float(np.sum(y_positions * proj_y) / total_y)
                    sigy = float(np.sqrt(np.sum((y_positions - y_mean) ** 2 * proj_y) / total_y))
                else:
                    y_mean = np.nan
                    sigy = np.nan
                hedges = x_positions
                vedges = y_positions

            hpixel_list.append(hpixel)
            vpixel_list.append(vpixel)
            xb_list.append(x_mean) # x_mean is a center of the beam
            yb_list.append(y_mean)
            sigx_list.append(sigx)
            sigy_list.append(sigy)
            sum_list.append(total) # sum of all pixels -> intensity
            images.append(image)
            hedges_all.append(hedges) # pixel coordinates
            vedges_all.append(vedges)
            inout_list.append(status)

        return {
            "names": list(selected_names),
            "hpixel": np.asarray(hpixel_list, dtype=float), # mm
            "vpixel": np.asarray(vpixel_list, dtype=float), # mm
            "x": np.asarray(xb_list, dtype=float),
            "y": np.asarray(yb_list, dtype=float),
            "sigx": np.asarray(sigx_list, dtype=float), # we need to get that from the image
            "sigy": np.asarray(sigy_list, dtype=float),
            "sum": np.asarray(sum_list, dtype=float),
            "hedges": hedges_all, #imagePositionSet1 i think its an array
            "vedges": vedges_all,
            "images": images, #image2D
            "S": np.asarray(s_positions, dtype=float),
            "inout": np.asarray(inout_list, dtype=float),
        }

    def get_target_dispersion(self, names=None):
        if names is None:
            names = self.bpms
        if isinstance(names, str):
            names = [names]

        if self.twiss_path is None:
            return [np.nan] * len(names), [np.nan] * len(names)

        lines, columns, dollar_sign = self._read_twiss_file()
        try:
            dx_column = columns.index('DX')
            dy_column = columns.index('DY')
            name_column = columns.index('NAME')
        except ValueError:
            return [np.nan] * len(names), [np.nan] * len(names)

        disp_values = {}
        for line in lines[dollar_sign + 1:]:
            data = line.split()
            if len(data) <= max(dx_column, dy_column, name_column):
                continue
            elem_name = data[name_column].strip('"')
            try:
                disp_values[elem_name] = (float(data[dx_column]), float(data[dy_column]))
            except ValueError:
                continue

        target_disp_x, target_disp_y = [], []
        for bpm in names:
            dx, dy = disp_values.get(bpm, (np.nan, np.nan))
            target_disp_x.append(dx)
            target_disp_y.append(dy)
        return target_disp_x, target_disp_y


    @staticmethod
    def _screen_data_from_image(image, hpixel, vpixel):
        if image is None:
            return np.nan, np.nan, np.nan, np.nan, 0.0, np.zeros((1, 1)), np.array([0.0, 1.0]), np.array([0.0, 1.0])

        img = np.asarray(image, dtype=float).copy()
        img[~np.isfinite(img)] = 0.0
        img = img - np.nanmin(img) # lowest values are treated as background, so subtracts lowest value from every cell
        total = float(np.sum(img)) # intensity
        ny, nx = img.shape

        if total <= 0.0 or nx == 0 or ny == 0:
            hedges = np.arange(nx + 1, dtype=float) * (hpixel if np.isfinite(hpixel) and hpixel > 0 else 1.0)
            vedges = np.arange(ny + 1, dtype=float) * (vpixel if np.isfinite(vpixel) and vpixel > 0 else 1.0)
            return np.nan, np.nan, np.nan, np.nan, 0.0, img, hedges, vedges

        if not np.isfinite(hpixel) or hpixel <= 0:
            hpixel = 1.0
        if not np.isfinite(vpixel) or vpixel <= 0:
            vpixel = 1.0

        x_centers = (np.arange(nx, dtype=float) - 0.5 * (nx - 1)) * hpixel # subtracts centre of the image, multiplies by the pixel size and therefore its a position with resect to centre of the image
        y_centers = (np.arange(ny, dtype=float) - 0.5 * (ny - 1)) * vpixel

        proj_x = np.sum(img, axis=0) # sum of intensity in each column
        proj_y = np.sum(img, axis=1) # sum of intensity in each row

        x_mean = float(np.sum(x_centers * proj_x) / total) # center of intensity of the image
        y_mean = float(np.sum(y_centers * proj_y) / total)
        sigx = float(np.sqrt(max(np.sum(((x_centers - x_mean) ** 2) * proj_x) / total, 0.0)))
        sigy = float(np.sqrt(max(np.sum(((y_centers - y_mean) ** 2) * proj_y) / total, 0.0)))

        hedges = (np.arange(nx + 1, dtype=float) - 0.5 * nx) * hpixel
        vedges = (np.arange(ny + 1, dtype=float) - 0.5 * ny) * vpixel
        return x_mean, y_mean, sigx, sigy, total, img, hedges, vedges

    def log_messages(self, console):
        self.log = console or print

    def _read_screen_setting(self, screen_name):
        japc_camera = self.screen_config.get(screen_name, {}).get('japc_name', screen_name.rstrip('LH'))
        try:
            return self.client.get(f'{japc_camera}.DigiCam/Setting', context = self.context).data
        except Exception as e:
            print(e)
            return None

    def _read_screen_h_matrix(self, screen_name):
        japc_camera = self.screen_config.get(screen_name, {}).get('japc_name', screen_name.rstrip('LH'))
        try:
            return self.client.get(f'{japc_camera}.Settings/Settings', context=self.context).data['h_matrix']
        except Exception:
            return None


    @staticmethod
    def _roi_from_setting(setting, image_shape):
        if setting is None:
            return np.array([0, image_shape[1], 0, image_shape[0]], dtype=int)
        try:
            if setting.get('imageROIEnable'):
                x0, y0, dx, dy = setting['imageROI']
                return np.array([x0, x0 + dx, y0, y0 + dy], dtype=int) # left and right edge of x, the same for y
            _, _, width, height = setting['imageWindow'] # if not enabled, takes the whole screen image
            return np.array([0, width, 0, height], dtype=int)
        except Exception:
            return np.array([0, image_shape[1], 0, image_shape[0]], dtype=int)

    @staticmethod
    def _auto_aoi_from_image(image, threshold_fraction=0.2, margin=20):
        img = np.asarray(image, dtype=float)
        if img.size == 0 or not np.any(np.isfinite(img)):
            return None

        work = img.copy()
        work[~np.isfinite(work)] = 0.0
        work = work - np.nanmin(work)
        peak = np.nanmax(work)
        if not np.isfinite(peak) or peak <= 0:
            return None

        mask = work >= threshold_fraction * peak # if the most intense pixel has a value of 1000, then, takes values from 200 up, assuming that for example, threshold is 0.2
        ys, xs = np.where(mask)
        if xs.size == 0 or ys.size == 0:
            return None

        ny, nx = work.shape
        # calculates a smaller rectangle, to isolate the beam from the rest + 20
        x0 = max(0, int(xs.min()) - margin)
        x1 = min(nx, int(xs.max()) + margin + 1)
        y0 = max(0, int(ys.min()) - margin)
        y1 = min(ny, int(ys.max()) + margin + 1)
        return x0, x1, y0, y1

    def _intensity_to_attenuator_position(self, value):
        return float(np.clip(float(value), self.laser_attenuator_min, self.laser_attenuator_max))

    def get_laser_attenuator_position(self):
        for address in self.laser_attenuator_readback:
            property_address, field = address.rsplit('#', 1)
            try:
                value = self.client.get(property_address, context = self.context).data[field]
                value = self.make_safe_float(value)
                if np.isfinite(value):
                    return value/1e3
            except Exception:
                pass
        return np.nan

    def set_laser_motor_attenuator_position(self, position):
        position = float(np.clip(float(position), 0.0, 3.0))
        command_position = position * 1e3
        self.log(f'Setting CLEAR motor attenuator to {position:.3f} ksteps, ({command_position:.0f} steps)...')
        self.client.set('CTF2Motor2B/Setting', {'targetPosition': command_position}, context=self.context)
        time.sleep(1)
        return position

    def get_laser_motor_attenuator_position(self):
        for address in self.laser_motor_attenuator_readback:
            property_address, field = address.rsplit('#', 1)
            try:
                value = self.client.get(property_address, context = self.context).data[field]
                value = self.make_safe_float(value)
                if np.isfinite(value):
                    return value/1e3
            except Exception:
                pass
        return np.nan

    def set_uv_attenuator_position(self, attenuator_name, position):
        if attenuator_name not in self.uv_attenuator_params:
            raise ValueError(f'Unknown UV attenuator {attenuator_name}. Expected one of {list(self.uv_attenuator_params)}')
        min_pos, max_pos = self.uv_attenuator_ranges.get(attenuator_name, (-np.inf, np.inf))
        position = float(np.clip(float(position), min_pos, max_pos))
        self.log(f'Setting {attenuator_name} to {position:.1f}...')
        property_address, field = (self.uv_attenuator_params[attenuator_name].rsplit('#', 1))
        self.client.set(property_address, {field: position}, context=self.context)
        time.sleep(1)
        return position

    def set_uv_attenuator_percent(self, attenuator_name, percent):
        if attenuator_name not in self.uv_attenuator_ranges:
            raise ValueError(f'Unknown UV attenuator {attenuator_name}. Expected one of {list(self.uv_attenuator_ranges)}')
        min_pos, max_pos = self.uv_attenuator_ranges[attenuator_name]
        percent = float(np.clip(float(percent), 0.0, 100.0))
        position = min_pos + (max_pos - min_pos) * percent / 100.0
        return self.set_uv_attenuator_position(attenuator_name, position)

    def set_shutter(self, shutter_name, open_shutter=True):
        if shutter_name not in self.shutter_set_params:
            raise ValueError(f'Unknown shutter {shutter_name}. Expected one of {list(self.shutter_set_params)}')

        property_address, field = self.shutter_set_params[shutter_name].rsplit('#', 1)
        self.client.set(property_address, {field: bool(open_shutter)}, context = self.context)
        time.sleep(0.5)
        return bool(open_shutter)

    def get_shutter(self, shutter_name):
        if shutter_name not in self.shutter_readback_params:
            raise ValueError(f'Unknown shutter {shutter_name}. Expected one of {list(self.shutter_readback_params)}')

        address = self.shutter_readback_params[shutter_name]
        property_address, field = address.rsplit('#', 1)
        try:
            value = self.client.get(property_address, context = self.context).data[field]
        except Exception:
            return np.nan
        return bool(value)

    def _read_bcm_scope(self, scope_name):
        try:
            data = self.client.get(f"{scope_name}/Acquisition").data
            signal = np.asarray(data["value"], dtype=float) * data["sensitivity"] + data["offset"]
            return float(np.mean(signal[20:60]))
        except Exception:
            return np.nan

    def _read_bcm_charge(self, bcm_name):
        try:
            sample_address = self.bcm_sample_params[bcm_name]
            property_address, field = sample_address.rsplit("#", 1)
            samples = self.client.get(property_address, context=self.context).data[field]
            gain = self.client.get("CA.BCM01GAIN/Setting").data["enumValue"]

            samples = np.asarray(samples, dtype=float) / 1000.0
            waveform = samples.reshape(samples.shape[0], -1)[0] if samples.ndim > 1 else samples

            voltage = float(np.mean(waveform[4000:8000])) * 2.13
            sensitivity = self.bcm_sensitivity.get(str(gain), np.nan)

            return 10.0 * voltage / sensitivity
        except Exception:
            return np.nan

