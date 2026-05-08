import sys, time, math, os
import numpy as np
import pyjapc

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
        self.energy_param = [
            'CA.BEAM/Acquisition#momentum',
            'CA.BEAM/Acquisition#energy',
        ]
        self.laser_attenuator_set_param = 'CA.GUN-ATTN/CMD#requestedPosition'
        self.laser_attenuator_readback = [
            'CA.GUN-ATTN/AQN#actualPosition',
            'CA.GUN-ATTN/CMD#requestedPosition',
        ]
        self.laser_attenuator_min = 0.0
        self.laser_attenuator_max = 3000.0
        self.laser_motor_attenuator_set_param = 'CTF2Motor2B/Setting#targetPosition'
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

        self.log = print
        self.japc = pyjapc.PyJapc("SCT.USER.ALL", incaAcceleratorName="CTF")

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

        self.corrector_set_params = {name: f'{name}/SettingPPM#current' for name in correctors}
        self.corrector_get_params = {name: f'{name}/Acquisition#currentAverage' for name in correctors}

        self.sextupoles = []
        self.quadrupoles = [
            'CA.QFD0350', 'CA.QDD0355', 'CA.QFD0360', 'CA.QFD0510',
            'CA.QDD0515', 'CA.QFD0520', 'CA.QFD0760', 'CA.QDD0765',
            'CA.QFD0770', 'CA.QDD0870', 'CA.QFD0880',
        ]

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
        self.bpm_indexes = [index for index, string in enumerate(monitors) if string in self.bpms]

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

        self.bcm_gain_param = "CA.BCM01GAIN/Setting#enumValue"

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
        for param in self.energy_param:
            try:
                value = self.japc.getParam(param)
                value = self.make_safe_float(value, default=np.nan)
                if np.isfinite(value) and value > 0:
                    pref = value
                    break
            except Exception:
                pass
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

    def _valid_japc_value(self, param_names, default=np.nan):
        for param_name in param_names:
            try:
                value = self.japc.getParam(param_name)
            except Exception:
                continue
            value = self.make_safe_float(value, default=np.nan)
            if np.isfinite(value):
                return value
        return float(default)

    def change_energy(self):
        self.log('Function change_energy needs implementation.')
        return 0.0

    def reset_energy(self):
        self.log('Function reset_energy needs implementation.')

    def _intensity_to_attenuator_position(self, value):
        value = float(value)
        if 0.0 <= value <= 1.0:
            value = self.laser_attenuator_min + value * (self.laser_attenuator_max - self.laser_attenuator_min)
        return float(np.clip(value, self.laser_attenuator_min, self.laser_attenuator_max))

    def get_laser_attenuator_position(self):
        value = self._valid_japc_value(self.laser_attenuator_readback, default=np.nan)
        return value / 1e3 if np.isfinite(value) else np.nan

    def set_laser_attenuator_position(self, position):
        position = self._intensity_to_attenuator_position(position)
        command_position = position * 1e3
        self.log(f'Setting CLEAR gun attenuator to {position:.3f} ksteps ({command_position:.0f} steps)...')
        self.japc.setParam(self.laser_attenuator_set_param, float(command_position))
        time.sleep(1)
        return position

    def get_laser_motor_attenuator_position(self):
        return self._valid_japc_value(self.laser_motor_attenuator_readback, default=np.nan)

    def set_laser_motor_attenuator_position(self, position):
        position = float(np.clip(float(position), 0.0, 3000.0))
        self.log(f'Setting CLEAR motor attenuator to {position:.1f} steps...')
        self.japc.setParam(self.laser_motor_attenuator_set_param, position)
        time.sleep(1)
        return position

    def set_uv_attenuator_position(self, attenuator_name, position):
        if attenuator_name not in self.uv_attenuator_params:
            raise ValueError(f'Unknown UV attenuator {attenuator_name}. Expected one of {list(self.uv_attenuator_params)}')
        min_pos, max_pos = self.uv_attenuator_ranges.get(attenuator_name, (-np.inf, np.inf))
        position = float(np.clip(float(position), min_pos, max_pos))
        self.log(f'Setting {attenuator_name} to {position:.1f}...')
        self.japc.setParam(self.uv_attenuator_params[attenuator_name], position)
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
        self.japc.setParam(self.shutter_set_params[shutter_name], bool(open_shutter))
        time.sleep(0.5)
        return bool(open_shutter)

    def get_shutter(self, shutter_name):
        if shutter_name not in self.shutter_readback_params:
            raise ValueError(f'Unknown shutter {shutter_name}. Expected one of {list(self.shutter_readback_params)}')
        value = self._valid_japc_value([self.shutter_readback_params[shutter_name]], default=np.nan)
        if not np.isfinite(value):
            return np.nan
        return bool(value)

    def change_intensity(self):
        target_position = self.set_laser_attenuator_position(self.test_laser_intensity)
        self.log(f'CLEAR test intensity set through gun attenuator: {target_position:.3f} ksteps')
        return self

    def reset_intensity(self):
        target_position = self.set_laser_attenuator_position(self.nominal_laser_intensity)
        self.log(f'CLEAR nominal intensity restored through gun attenuator: {target_position:.3f} ksteps')
        return self

    def get_sequence(self):
        return self.sequence

    def get_hcorrectors_names(self):
        return [name for name in self.corrs if ("DHG" in name) or ("DHJ" in name)]

    def get_vcorrectors_names(self):
        return [name for name in self.corrs if ("DVG" in name) or ("DVJ" in name) or ("SDV" in name)]

    def get_elements_indices(self, names):
        return [index for index, string in enumerate(self.sequence) if string in names]

    def log_messages(self, console):
        self.log = console or print

    def _read_screen_setting(self, screen_name):
        japc_camera = self.screen_config.get(screen_name, {}).get('japc_name', screen_name.rstrip('LH'))
        try:
            self.japc.setSelector('')
            return self.japc.getParam(f'{japc_camera}.DigiCam/Setting')
        except Exception:
            return None

    def _read_screen_h_matrix(self, screen_name):
        japc_camera = self.screen_config.get(screen_name, {}).get('japc_name', screen_name.rstrip('LH'))
        try:
            self.japc.setSelector('')
            return self.japc.getParam(f'{japc_camera}Settings/Settings#h_matrix')
        except Exception:
            return None

    def _read_screen_status(self, screen_name):
        japc_camera = self.screen_config.get(screen_name, {}).get('japc_name', screen_name.rstrip('LH'))
        candidates = [
            f'{japc_camera}/Acquisition#screenIn',
            f'{japc_camera}/Status#screenIn',
            f'{japc_camera}/Status#position',
        ]
        return self._valid_japc_value(candidates, default=np.nan)

    def _acquire_screen_image(self, screen_name):
        japc_camera = self.screen_config.get(screen_name, {}).get('japc_name', screen_name.rstrip('LH'))
        camera_config = self.screen_config.get(screen_name, {})
        selector = camera_config.get('japc_selector', '')
        try:
            self.japc.setSelector(selector)
            try:
                image = self.japc.getParam(f'{japc_camera}.DigiCam/LastImage#image2D')
            except Exception:
                try:
                    image = self.japc.getParam(f'{japc_camera}.DigiCam/ExtractionImage')
                except Exception:
                    image = self.japc.getParam(f'{japc_camera}/Image')
        except Exception as exc:
            self.log(f'Could not read image from {screen_name}: {exc}')
            return None
        if image is None:
            return None
        image = np.asarray(image, dtype=float)
        if image.size == 0:
            return None
        return image

    def set_screen_camera_on(self, screen_name, on=True):
        japc_camera = self.screen_config.get(screen_name, {}).get('japc_name', screen_name.rstrip('LH'))
        self.japc.setParam(f'{japc_camera}/Setting#cameraSwitch', int(bool(on)))

    def set_screen_filter(self, screen_name, filter_value):
        japc_camera = self.screen_config.get(screen_name, {}).get('japc_name', screen_name.rstrip('LH'))
        self.japc.setParam(f'{japc_camera}/Setting#filterSelect', filter_value)

    def set_screen_video_gain(self, screen_name, gain_value):
        japc_camera = self.screen_config.get(screen_name, {}).get('japc_name', screen_name.rstrip('LH'))
        self.japc.setParam(f'{japc_camera}/Setting#videoGain', gain_value)

    def set_screen_select(self, screen_name, screen_value):
        japc_camera = self.screen_config.get(screen_name, {}).get('japc_name', screen_name.rstrip('LH'))
        self.japc.setParam(f'{japc_camera}/Setting#screenSelect', screen_value)

    @staticmethod
    def _roi_from_setting(setting, image_shape):
        if setting is None:
            return np.array([0, image_shape[1], 0, image_shape[0]], dtype=int)
        try:
            if setting.get('imageROIEnable'):
                x0, y0, dx, dy = setting['imageROI']
                return np.array([x0, x0 + dx, y0, y0 + dy], dtype=int)
            _, _, width, height = setting['imageWindow']
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

        mask = work >= threshold_fraction * peak
        ys, xs = np.where(mask)
        if xs.size == 0 or ys.size == 0:
            return None

        ny, nx = work.shape
        x0 = max(0, int(xs.min()) - margin)
        x1 = min(nx, int(xs.max()) + margin + 1)
        y0 = max(0, int(ys.min()) - margin)
        y1 = min(ny, int(ys.max()) + margin + 1)
        return x0, x1, y0, y1

    @staticmethod
    def _screen_data_from_image(image, hpixel, vpixel):
        if image is None:
            return np.nan, np.nan, np.nan, np.nan, 0.0, np.zeros((1, 1)), np.array([0.0, 1.0]), np.array([0.0, 1.0])

        img = np.asarray(image, dtype=float).copy()
        img[~np.isfinite(img)] = 0.0
        img = img - np.nanmin(img)
        total = float(np.sum(img))
        ny, nx = img.shape

        if total <= 0.0 or nx == 0 or ny == 0:
            hedges = np.arange(nx + 1, dtype=float) * (hpixel if np.isfinite(hpixel) and hpixel > 0 else 1.0)
            vedges = np.arange(ny + 1, dtype=float) * (vpixel if np.isfinite(vpixel) and vpixel > 0 else 1.0)
            return np.nan, np.nan, np.nan, np.nan, 0.0, img, hedges, vedges

        if not np.isfinite(hpixel) or hpixel <= 0:
            hpixel = 1.0
        if not np.isfinite(vpixel) or vpixel <= 0:
            vpixel = 1.0

        x_centers = (np.arange(nx, dtype=float) - 0.5 * (nx - 1)) * hpixel
        y_centers = (np.arange(ny, dtype=float) - 0.5 * (ny - 1)) * vpixel

        proj_x = np.sum(img, axis=0)
        proj_y = np.sum(img, axis=1)

        x_mean = float(np.sum(x_centers * proj_x) / total)
        y_mean = float(np.sum(y_centers * proj_y) / total)
        sigx = float(np.sqrt(max(np.sum(((x_centers - x_mean) ** 2) * proj_x) / total, 0.0)))
        sigy = float(np.sqrt(max(np.sum(((y_centers - y_mean) ** 2) * proj_y) / total, 0.0)))

        hedges = (np.arange(nx + 1, dtype=float) - 0.5 * nx) * hpixel
        vedges = (np.arange(ny + 1, dtype=float) - 0.5 * ny) * vpixel
        return x_mean, y_mean, sigx, sigy, total, img, hedges, vedges

    def _read_bcm_scope(self, scope_name):
        try:
            data = self.japc.getParam(f"{scope_name}/Acquisition")
            signal = np.asarray(data["value"], dtype=float) * data["sensitivity"] + data["offset"]
            return float(np.mean(signal[20:60]))
        except Exception:
            return np.nan

    def _read_bpm_plane(self, bpm, plane):
        plane = plane.lower()
        candidates = [
            f'{bpm}/Acquisition#{plane}',
            f'{bpm}/Acquisition#{plane}Position',
            f'{bpm}/Acquisition#{plane}position',
            f'{bpm}/Acquisition#position{plane.upper()}',
            f'{bpm}/Acquisition#pos{plane.upper()}',
        ]
        return self._valid_japc_value(candidates, default=np.nan)

    def _read_bpm_intensity(self, bpm):
        candidates = [
            f'{bpm}/Acquisition#intensity',
            f'{bpm}/Acquisition#sum',
            f'{bpm}/Acquisition#charge',
        ]
        value = self._valid_japc_value(candidates, default=np.nan)
        return value if np.isfinite(value) else 1.0

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
            camera_config = self.screen_config.get(screen_name, {})
            hpixel = float(camera_config.get('s_x_res', np.nan))
            vpixel = float(camera_config.get('s_y_res', np.nan))

            status = self._read_screen_status(screen_name)
            setting = self._read_screen_setting(screen_name)
            image = self._acquire_screen_image(screen_name)
            if image is not None:
                roi = self._roi_from_setting(setting, image.shape)
                x0, x1, y0, y1 = roi
                x0 = max(0, min(int(x0), image.shape[1]))
                x1 = max(x0, min(int(x1), image.shape[1]))
                y0 = max(0, min(int(y0), image.shape[0]))
                y1 = max(y0, min(int(y1), image.shape[0]))
                image = image[y0:y1, x0:x1]

                auto_roi = self._auto_aoi_from_image(image)
                if auto_roi is not None:
                    ax0, ax1, ay0, ay1 = auto_roi
                    image = image[ay0:ay1, ax0:ax1]

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

        return {
            "names": np.asarray(selected_names),
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

    def _read_bcm_charge(self, bcm_name):
        try:
            samples = self.japc.getParam(self.bcm_sample_params[bcm_name])
            gain = self.japc.getParam(self.bcm_gain_param)

            samples = np.asarray(samples, dtype=float) / 1000.0
            waveform = samples.reshape(samples.shape[0], -1)[0] if samples.ndim > 1 else samples

            voltage = float(np.mean(waveform[4000:8000])) * 2.13
            sensitivity = self.bcm_sensitivity.get(str(gain), np.nan)

            return 10.0 * voltage / sensitivity
        except Exception:
            return np.nan

    def get_icts(self, names=None):
        self.log("Reading ict's...")

        if names is None:
            names = self.ict_names
        if isinstance(names, str):
            names = [names]

        charge = []
        for name in names:
            if name in self.bcm_sample_params:
                charge.append(self._read_bcm_charge(name))
            else:
                charge.append(self._valid_japc_value([name], default=np.nan))

        return {
            "names": np.asarray(names),
            "charge": np.asarray(charge, dtype=float),
        }

    def get_correctors(self, names=None):
        self.log("Reading correctors' strengths...")
        selected_names = self.corrs if names is None else ([names] if isinstance(names, str) else list(names))

        bdes, bact = [], []
        for corrector in selected_names:
            bdes.append(self._valid_japc_value([self.corrector_set_params[corrector]], default=np.nan))
            bact.append(self._valid_japc_value([self.corrector_get_params[corrector]], default=np.nan))

        return {
            "names": np.asarray(selected_names),
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
            "names": np.asarray(selected_names),
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
                last_value = self.make_safe_float(self.japc.getParam(readback_param), default=np.nan)
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
            self.japc.setParam(self.corrector_set_params[corrector], target)
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

        bdes, bact = [], []

        for quadrupole in names:
            bdes.append(self._valid_japc_value([self.quad_set_params[quadrupole]], default=np.nan))
            bact.append(self._valid_japc_value([self.quad_get_params[quadrupole]], default=np.nan))

        return {
            "names": np.array(names),
            "bdes": np.array(bdes, dtype=float),
            "bact": np.array(bact, dtype=float),
        }

    def set_quadrupoles(self, names, values):
        if isinstance(names, str):
            names = [names]
        if not isinstance(values, (list, tuple, np.ndarray)):
            values = [values]

        for quadrupole, value in zip(names, values):
            self.japc.setParam(self.quad_set_params[quadrupole], float(value))

        time.sleep(1)
