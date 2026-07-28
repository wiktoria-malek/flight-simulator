from Interfaces.CLEAR.Setup_files.CLEAR_BPM_getHV import baseline_correct, find_peak, threshold_integral, plot_peak, plot_integral
import sys, time, math, os, json
import numpy as np
import pyda, pyda_japc
from scipy.integrate import trapezoid
from enum import Enum
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

class BPMsMode(Enum):
    """
    Acquire and process the horizontal (H) and vertical (V) BPM signals.

    Parameters
    ----------
    BPM : str
        BPM name: "BPM0530", "BPM0595", "BPM0690", "BPM0820", "BPM0890".
    mode : str
        - "peak"
            Return the peak value of the raw signal.
        - "baseline_peak"
            Return the peak value after baseline correction.
        - "integral"
            Return the integral of the baseline-corrected signal.
        - "integral_window"
            Return the integral of the baseline-corrected signal over the
            specified integration window, [min=0, max=730]. If not specified,
            running with default window.
        - "integral_threshold"
            Return the integral of the baseline-corrected signal between the
            5% peak threshold crossings.
    plot : optional
        Display processing plots.
    Returns
    -------
    H, V
        Processed H and V values.
    """
    peak = "peak"
    baseline_peak = "baseline_peak"
    integral = "integral"
    integral_window = "integral_window"
    integral_threshold = "integral_threshold"

class CLEAR_real_machine(AbstractMachineInterface):
    def get_name(self):
        return 'CLEAR'

    def __init__(self, nsamples=1, nominal_intensity=1.5, wfs_intensity=1.0):
        # would be nice to call here functions that do _read_intensity_nominal and energy
        # at the constructor, so that we dont lose time during operations like change_energy/intensity to read them
        self.steps_readback_position = 0.0
        self.energy_readback = 0.0
        self.bpm_mode = BPMsMode.peak
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

        self.context_acquisition = "SCT.USER.SETUP"
        self.context_empty = ""
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
        self.cam_props = self.CamList() # Load camera configuration from assets/cameras.json
        self.camList = list(self.cam_props.keys())

    def CamList(self):
        _JSON_PATH = os.path.join(os.path.dirname(__file__), 'cameras.json')
        """Return the full device configuration dict (keyed by BTV device name)."""
        with open(_JSON_PATH) as f:
            data = json.load(f)
        return data['devices']

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
        self.energy_readback = self.client.get('CK.LL-MKS11/Setting').data['PhaseSh_SP'] #changes value globally
        self.log(f"Value before changing energy: {self.energy_readback}")
        new_energy = 0.9 * self.energy_readback # as a test!
        self.client.set('CK.LL-MKS11/Setting', data = {"PhaseSh_SP" : new_energy})
        self.log(f"Value after changing energy: {new_energy}")
        time.sleep(10)
        self.energy_readback = self.client.get('CK.LL-MKS11/Setting').data['PhaseSh_SP']
        print(self.energy_readback)
        return self.energy_readback

    def reset_energy(self):
        print(f"Resetting energy to {self.energy_readback}...")
        # self.client.set('CK.LL-MKS11/Setting', data = {"PhaseSh_SP" : self.energy_readback})
        print(f"Energy has been reset to {self.energy_readback}...")

    def change_intensity(self):
        self.steps_readback_position = self.client.get('CO.TOWB.102.UVATT2/Setting').data['position']
        self.steps_readback_position_min = self.client.get('CO.TOWB.102.UVATT2/Setting').data['position_min']
        self.steps_readback_position_max =self.client.get('CO.TOWB.102.UVATT2/Setting').data['position_max']
        print(f'Changing intensity to ...')
        nominal_settings_steps = self.steps_readback_position
        N_steps = 100 # to be verified!
        new_laser_settings = nominal_settings_steps - N_steps
        self.log(f"The new laser settings will be set to {new_laser_settings}... Nominal value is {self.steps_readback_position}.")
        #self.client.set('CO.TOWB.102.UVATT2/Setting', data={"position": new_laser_settings})
        self.log(f"The new laser settings has been set to {new_laser_settings}. Nominal value was {self.steps_readback_position}.")
        return self

    def reset_intensity(self):
        print(f"Resetting intensity to {self.steps_readback_position}...")
        # self.client.set('CO.TOWB.102.UVATT2/Setting', data = {"position" : self.steps_readback_position})
        print(f"Intensity steps has been reset to {self.steps_readback_position}...")

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
            value = self.client.get(property_address, context=self.context_empty).data[field]
            return self.make_safe_float(value)
        except Exception as exc:
            self.log(f"Could not read screen status for {screen_name}: {exc}")
            return np.nan

    def _acquire_screen_data(self, screen_name):
        japc_camera = self.screen_config.get(screen_name, {}).get("japc_name", screen_name.rstrip("LH"))
        camera_config = self.screen_config.get(screen_name, {})
        selector = camera_config.get("japc_selector", self.context_empty)
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
                value = self.client.get(property_address, context=self.context_empty).data[field]
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
            setting_data = self.client.get(self.corrector_set_params[corrector],context = self.context_empty).data
            acquisition_data = self.client.get(self.corrector_get_params[corrector], context = self.context_acquisition).data
            bdes.append(setting_data['current'])
            bact.append(acquisition_data['currentAverage'])

        return {
            "names": list(selected_names),
            "bdes": np.asarray(bdes, dtype=float),
            "bact": np.asarray(bact, dtype=float),
        }

    def get_bpms(self, names=None):
        window = (260, 360)
        self.log('Reading bpms...')
        selected_names = self.bpms if names is None else ([names] if isinstance(names, str) else list(names))
        x, y, tmit = [], [], []
        mode = self.bpm_mode
        for sample in range(self.nsamples):
            self.log(f'Sample = {sample}')
            x_sample, y_sample, tmit_sample = [], [], []
            for bpm in selected_names:
                hsamples = self.client.get(f"{bpm}H-SA/SamplesFromTrigger", context = self.context_acquisition).data
                vsamples = self.client.get(f"{bpm}V-SA/SamplesFromTrigger", context=self.context_acquisition).data
                ssamples = self.client.get(f"{bpm}S-SA/SamplesFromTrigger", context=self.context_acquisition).data
                H_samples = np.asarray(hsamples["samples"], dtype=float).ravel()
                V_samples = np.asarray(vsamples["samples"], dtype=float).ravel()
                S_samples = np.asarray(ssamples["samples"], dtype=float).ravel()
                H_b_samples = baseline_correct(H_samples)
                V_b_samples = baseline_correct(V_samples)
                s_sum = np.sum(S_samples)
                if mode == BPMsMode.peak: # Find peak (largest magnitude, keeping the sign)
                    H, H_idx = find_peak(H_samples)
                    V, V_idx = find_peak(V_samples)
                    # plot_peak([H_samples, V_samples], [H_idx, V_idx], [H, V], ["H", "V"], BPM)

                elif mode == BPMsMode.baseline_peak: # Find peak on baseline corrected signal (largest magnitude, keeping the sign)
                    H, H_idx = find_peak(H_b_samples)
                    V, V_idx = find_peak(V_b_samples)
                    # plot_peak([H_b_samples, V_b_samples], [H_idx, V_idx], [H, V], ["H", "V"], BPM, )

                elif mode == BPMsMode.integral: # Integration of full BPM signal with baseline correction
                    H = trapezoid(H_b_samples)
                    V = trapezoid(V_b_samples)
                    # plot_integral(signals=[H_b_samples, V_b_samples], integrals=[H, V], labels=["H", "V"], BPM=BPM)

                elif mode == BPMsMode.integral_window: # Integration of fixed window BPM signal with baseline correction
                    window_start, window_end = window
                    H = trapezoid(H_b_samples[window_start:window_end])
                    V = trapezoid(V_b_samples[window_start:window_end])
                    # plot_integral(signals=[H_b_samples, V_b_samples], integrals=[H, V], labels=["H", "V"], BPM=BPM, starts=[window_start, window_start], ends=[window_end, window_end], )

                elif mode == BPMsMode.integral_threshold: # Integration between 5% of the peak threshold region with baseline correction
                    H, H_start, H_end, H_peak_idx = threshold_integral(H_b_samples)
                    V, V_start, V_end, V_peak_idx = threshold_integral(V_b_samples)
                    # plot_integral(signals=[H_b_samples, V_b_samples], integrals=[H, V], labels=["H", "V"], BPM=BPM, starts=[H_start, V_start], ends=[H_end, V_end], )

                else:
                    raise ValueError(
                        f"Unknown mode '{mode}'. " "Choose from: 'peak', 'baseline_peak', " "'integral', 'integral_window', 'integral_threshold'.")

                x_sample.append(H)
                y_sample.append(V)
                tmit_sample.append(s_sum)
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

    def _wait_for_corrector_readback(self, corrector, target, tolerance= 5e-3, timeout=10.0, poll_interval=0.05):
        readback_param = self.corrector_get_params[corrector]
        t0 = time.perf_counter()
        last_value = np.nan
        while time.perf_counter() - t0 < timeout:
            try:
                data = self.client.get(readback_param, context=self.context_acquisition).data
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

    def _wait_for_quadrupole_readback(self, readback_value, target, tolerance= 5e-3, timeout=10.0, poll_interval=0.05):
        t0 = time.perf_counter()
        last_value = np.nan
        while time.perf_counter() - t0 < timeout:
            try:
                last_value = self.client.get(readback_value, context = self.context_acquisition).data["currentAverage"]
            except Exception as e:
                last_value = np.nan

            if np.isfinite(last_value) and abs(last_value - float(target)) <= tolerance:
                return True
            time.sleep(poll_interval)
        self.log(
            f'Warning: {readback_value} did not reach target {float(target):.6g} '
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
            target = corr_val
            self.client.set(self.corrector_set_params[corrector], data={'current': target})
            self._wait_for_magnet_readback(corrector, target)

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
                set_value = self.client.get(set_property, context=self.context_empty).data[set_field]
            except Exception:
                set_value = np.nan
            try:
                get_value = self.client.get(get_property, context=self.context_acquisition).data[get_field]
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
            self.client.set(property_address, data={field: value})
            acq_path = f"{quadrupole}/Acquisition"
            self._wait_for_quadrupole_readback(acq_path, value)

    def _get_screen_movement_info(self, screen_name):
        btv_key = screen_name.rstrip("LH")
        cam = self.cam_props.get(btv_key)
        if cam is None: raise RuntimeError(f"Camera {btv_key} not found")
        if not bool(cam.get("screenInstalled")): raise RuntimeError(f"Camera {btv_key} not installed")

        screen_props = {
            "btv_key": btv_key,
            "btvdevice": cam.get('controlDeviceName'),  # None when not configured
            "ctrl_type" : cam.get('controlDeviceType'),
            "ctrl_fields" : cam.get('controlDeviceFields', {}),
            "screen_mover_device" : cam.get('screenMoverDevice'), # None for most cameras
            "screen_mover_type" : cam.get('screenMoverType'),
            "screen_mover_fields" : cam.get('screenMoverFields') or {}
        }

        screen_props["system"] = int(screen_props["ctrl_fields"].get("system", 1))
        screen_props["has_custom_screen_mover"] = isinstance(screen_props["screen_mover_device"], str)

        if screen_props["system"] == 1:
            screen_props["set_prop"] = 'OPSettingSystem1'
            screen_props["get_prop"] = 'ExpertSettingDCSystem1'
            screen_props["get_set_field"] = 'positionChannel1'
            screen_props["description_field"] = 'dcm1DriverNames'

        elif screen_props["system"] == 2:
            screen_props["set_prop"] = 'OPSettingSystem2'
            screen_props["get_prop"] = 'ExpertSettingDCSystem2'
            screen_props["get_set_field"] = 'positionChannel5'
            screen_props["description_field"] = 'dcm3DriverNames'

        else:
            screen_props["set_prop"] = screen_props["get_prop"] = screen_props["field"] = screen_props["description_field"] = None

        return screen_props

    def _screen_position_label(self, screen_props):
        if screen_props["has_custom_screen_mover"]:
            return [str(k) for k in screen_props["screen_mover_fields"].get("setpoints", {})]
        else:
            description_data = self.client.get(f"{screen_props['btvdevice']}/Description", context=self.context_empty).data[screen_props["description_field"]]
        return [str(value).strip() for value in list(description_data) if str(value).strip()]

    def _get_screen_position(self, screen_name):
        screen_props = self._get_screen_movement_info(screen_name)
        screen_position_labels = self._screen_position_label(screen_props)
        if screen_props["has_custom_screen_mover"]:
            try:
                positions_path = int(self.client.get(f"{screen_props['screen_mover_device']}/Acquisition", context=self.context_empty).data["position"])
            except Exception as e:
                self.log(f"Error: {e}")
                return None
            # Build reverse map: integer value → label
            setpoints = screen_props["screen_mover_fields"].get("setpoints", {})
            reversed_map = {v: k for k, v in setpoints.items()}
            return reversed_map.get(positions_path, str(positions_path))
        try:
            value = self.client.get(f"{screen_props['btvdevice']}/{screen_props['get_prop']}", context=self.context_empty).data[screen_props['get_field']]
            index = int(value.value if hasattr(val, "value") else val)
        except Exception as e:
            self.log(f"Error: {e}")
            return None
        return screen_position_labels[index] if 0<=index<len(screen_position_labels) else None

    def _move_screen(self, screen_name, requested_position):
        screen_props = self._get_screen_movement_info(screen_name)
        screen_position_labels = self._screen_position_label(screen_props)
        requested_movement_type = requested_position.lower()
        labels = [_labels.lower() for _labels in screen_position_labels]
        # if requested_movement_type in labels:
        index = labels.index(requested_movement_type)
        # else:
        #     index = None
        label = labels[index]
        
        if screen_props["has_custom_screen_mover"]:
            setpoints = screen_props["screen_mover_fields"].get("setpoints", {})
            if label not in setpoints:
                raise RuntimeError(f"Setpoint {label} not found in screen_mover_fields")
            value = setpoints[label]
            device = screen_props["screen_mover_device"]
            mover_type = screen_props["screen_mover_type"]
            if mover_type == "BStepMotorVME":
                self.client.set(f"{device}/Move", data={"mode": 2, "value": value, "units": 2})
            elif mover_type == "NewFocusPicomotor":
                self.client.set(f"{device}/Setting#position", data={"position": value})
            else: raise RuntimeError(f"Unknown mover type: {mover_type}")
            self.log(f"Moved {screen_name} to position {label}")
            return label
        # ---- Standard BTVCTRL screen command ----
        if not screen_props["btvdevice"] or screen_props["set_prop"] is None:
            raise RuntimeError(f"No BTVCTRL controller for {screen_name}")
        propert_address, field = screen_props["set_prop"].rsplit("#", 1)
        self.client.set(f"{screen_props['btvdevice']}/{property_addres}", data={field: index})
        self.log(f"Moved {screen_name} -> {label}")
        return label

    def insert_screen(self, screen_name):
        #return self._move_screen(screen_name, 1)
        info = self._get_screen_movement_info(screen_name)
        # First, read if the screen is already inserted!
        current_screen_inout_status = self.client.get(f"{info['btvdevice']}/{info['set_prop']}").data[info['get_set_field']] # 0 or not == 0 means screen is out, whatever else means IN
        if current_screen_inout_status.value == 0:
            self.log(f"Inserting {screen_name}...")
            self.client.set(f"{info['btvdevice']}/{info['set_prop']}", data={f"{info['get_set_field']}": 1}) # 1, meaning INSERT the screen
            self.log(f"Inserted {screen_name}!")
            current_screen_inout_status2 = self.client.get(f"{info['btvdevice']}/{info['set_prop']}").data[info['get_set_field']]
            print("Current Screen Inout Status:", current_screen_inout_status2)
        else:
            print(current_screen_inout_status.value)
            self.log(f"Screen {screen_name} already inserted")
            return

    def extract_screen(self, screen_name):
        # return self._move_screen(screen_name, 1)
        screen_name = screen_name.rstrip("LH")
        info = self._get_screen_movement_info(screen_name)
        # First, read if the screen is already extracted!
        current_screen_inout_status = self.client.get(f"{info['btvdevice']}/{info['set_prop']}").data[info['get_set_field']]  # 0 or not == 0 means screen is out, whatever else means IN
        if current_screen_inout_status.value == 0:
            self.log(f"Screen {screen_name} already extracted")
            return
        else:
            self.log(f"Extracting {screen_name}...")
            self.client.set(f"{info['btvdevice']}/{info['set_prop']}", data={f"{info['get_set_field']}": 0})  # 0, meaning EXTRACT the screen
            self.log(f"Extracted {screen_name}!")

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
            return self.client.get(f'{japc_camera}.DigiCam/Setting', context = self.context_empty).data
        except Exception as e:
            print(e)
            return None

    def _read_screen_h_matrix(self, screen_name):
        japc_camera = self.screen_config.get(screen_name, {}).get('japc_name', screen_name.rstrip('LH'))
        try:
            return self.client.get(f'{japc_camera}.Settings/Settings', context=self.context_empty).data['h_matrix']
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
                value = self.client.get(property_address, context = self.context_empty).data[field]
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
        self.client.set('CTF2Motor2B/Setting', {'targetPosition': command_position}, context=self.context_empty)
        time.sleep(1)
        return position

    def get_laser_motor_attenuator_position(self):
        for address in self.laser_motor_attenuator_readback:
            property_address, field = address.rsplit('#', 1)
            try:
                value = self.client.get(property_address, context = self.context_empty).data[field]
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
        self.client.set(property_address, {field: position}, context=self.context_empty)
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
        self.client.set(property_address, {field: bool(open_shutter)}, context = self.context_empty)
        time.sleep(0.5)
        return bool(open_shutter)

    def get_shutter(self, shutter_name):
        if shutter_name not in self.shutter_readback_params:
            raise ValueError(f'Unknown shutter {shutter_name}. Expected one of {list(self.shutter_readback_params)}')
        address = self.shutter_readback_params[shutter_name]
        property_address, field = address.rsplit('#', 1)
        try:
            value = self.client.get(property_address, context = self.context_empty).data[field]
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
            samples = self.client.get(property_address, context=self.context_empty).data[field]
            gain = self.client.get("CA.BCM01GAIN/Setting").data["enumValue"]

            samples = np.asarray(samples, dtype=float) / 1000.0
            waveform = samples.reshape(samples.shape[0], -1)[0] if samples.ndim > 1 else samples

            voltage = float(np.mean(waveform[4000:8000])) * 2.13
            sensitivity = self.bcm_sensitivity.get(str(gain), np.nan)

            return 10.0 * voltage / sensitivity
        except Exception:
            return np.nan

