from Interfaces.CLEAR.Setup_files.CLEAR_BPM_getHV import baseline_correct, find_peak, threshold_integral, plot_peak, plot_integral
import sys, time, math, os, json
import numpy as np
try:
    import pyda
    import pyda_japc
except ImportError:
    pyda = None
    pyda_japc = None
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
        self.screen_backgrounds = {}
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
            'CA.DHG0130', 'CA.DVG0130', #'CA.BPC0220',
            'CA.DHG0225', 'CA.DVG0225', #'CA.BPC0240',
            'CA.DHG0245', 'CA.DVG0245', #'CA.BPC0260',
            'CA.DHG0265', #'CA.BPC0310',
            'CA.DHG0320', 'CA.DVG0320', #'CA.SDV0340',
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
                     # 'CA.BPC0220', 'CA.BPC0240', 'CA.BPC0260',
                     # 'CA.BPC0310',
                    'CA.BPM0530', 'CA.BPM0595',
                     'CA.BPM0690', 'CA.BPM0820', 'CA.BPM0890',
        ]

        correctors = [
            'CA.DHG0130', 'CA.DVG0130',
            'CA.DHG0225', 'CA.DVG0225',
            'CA.DHG0245', 'CA.DVG0245',
            'CA.DHG0265', 'CA.DVG0265',
            'CA.DHG0320', 'CA.DVG0320',
            'CA.DHG0385', 'CA.DVG0385',
            'CA.DHJ0540', 'CA.DVJ0540',
            'CA.DHJ0590', 'CA.DVJ0590',
            'CA.DHJ0710', 'CA.DVJ0710',
            'CA.DHJ0780', 'CA.DVJ0780',
            'CA.DHJ0840', 'CA.DVJ0840',
            # 'CA.SDV0340',
        ]

        self.screen_status_params = {
            "CA.BTV0390L": "CA.BTV0390_CAS.BTV0420/OPSettingSystem1#positionChannel1",
            "CA.BTV0390H": "CA.BTV0390_CAS.BTV0420/OPSettingSystem1#positionChannel1",
            "CA.BTV0620":  "CAS.BTV0440_CA.BTV0620/OPSettingSystem2#positionChannel5",
            "CA.BTV0730":  "CA.BTV0730_CA.BTV0800/OPSettingSystem1#positionChannel1",
            "CA.BTV0810":  "CA.BTV0805_CA.BTV0810/OPSettingSystem2#positionChannel5",
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
        self.screen_config = config.cameras # it consists also screens that we should not use!
        # ["CA.BTV0125","CA.BTV0215","CA.BTV0235", "CA.BTV0390", "CAS.BTV0420", "CAS.BTV0440", "CAS.CAMVESPER1",
        #  "CA.BTV0545","CA.BTV0620", "CA.BTV0730","CA.BTV0800", "CA.BTV0805", "CA.BTV0810" , "CA.BTV0875",
        #  "CA.BTV0910", "CAS.BTV0930","CA.CAMAIR1", "CA.CAMAIR2", "CA.CAMAIR3","CA.CAMAIR4", "CS.BTV0120", "CS.BTV0305",
        #  "CS.BTV0420","CS.BTV0520", "CS.BTVVAC1","CS.CAMVAC1","CS.CAMAIR1","CS.CAMAIR2","CS.CAMAIR3","CS.CAMAIR4",
        #  "PHIN.BTV01","PHIN.BTV.Spectro","PHIN.VCAT"]
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
        time.sleep(10) # write a loop, dont guess time sleep
        after_energy_change = self.client.get('CK.LL-MKS11/Setting').data['PhaseSh_SP']
        print(after_energy_change)
        return after_energy_change

    def reset_energy(self):
        print(f"Resetting energy to {self.energy_readback}...")
        self.client.set('CK.LL-MKS11/Setting', data = {"PhaseSh_SP" : self.energy_readback})
        print(f"Energy has been reset to {self.energy_readback}...")
        after_energy_reset = self.client.get('CK.LL-MKS11/Setting').data['PhaseSh_SP']
        print(after_energy_reset)

    def change_intensity(self):
        self.steps_readback_position = self.client.get('CO.TOWB.102.UVATT2/Setting').data['position']
        self.steps_readback_position_min = self.client.get('CO.TOWB.102.UVATT2/Setting').data['position_min']
        self.steps_readback_position_max =self.client.get('CO.TOWB.102.UVATT2/Setting').data['position_max']
        print(f'Changing intensity to ...')
        nominal_settings_steps = self.steps_readback_position
        N_steps = 1000 # to be verified!
        new_laser_settings = nominal_settings_steps + N_steps
        self.log(f"The new laser settings will be set to {new_laser_settings}... Nominal value is {self.steps_readback_position}.")
        self.client.set('CO.TOWB.102.UVATT2/Setting', data={"position": new_laser_settings})
        self.log(f"The new laser settings has been set to {new_laser_settings}. Nominal value was {self.steps_readback_position}.")
        after_intensity_change = self.client.get('CO.TOWB.102.UVATT2/Setting').data['position']
        self.log(f"Read after change of intensity:", after_intensity_change)
        return self

    def reset_intensity(self):
        print(f"Resetting intensity to {self.steps_readback_position}...")
        self.client.set('CO.TOWB.102.UVATT2/Setting', data = {"position" : self.steps_readback_position})
        print(f"Intensity steps has been reset to {self.steps_readback_position}...")
        after_intensity_reset = self.client.get('CO.TOWB.102.UVATT2/Setting').data['position']
        self.log(f"Read after reset of intensity:", after_intensity_reset)

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

    def acquire_screen_background(self, screen_name, frames = 10):
        self.extract_screen(screen_name)
        background_frames = []
        for frame in range(frames):
            self.log(f"Acquiring {frame}/{frames} background frames...")
            camera_data = self._acquire_screen_data(screen_name)
            if camera_data is None:
                continue
            image = np.asarray(camera_data['image2D'], dtype=float)
            background_frames.append(image)
            self.log(f"Acquired {frame}/{frames} background frames...")
        if not background_frames:
            raise RuntimeError(f"No background frames available for {screen_name}")
        self.log(f"Acquired {frames} background frames. Calculating the median...")
        bg_img = np.median(np.stack(background_frames, axis=0), axis=0)
        self.log(f"Median calculated.")
        self.screen_backgrounds[screen_name] = bg_img
        return bg_img

    def acquire_screen_image(self, screen_name):
        self.insert_screen(screen_name)
        camera_data = self._acquire_screen_data(screen_name)
        if camera_data is None: raise RuntimeError(f"No camera data available for {screen_name}")
        beam_img = np.asarray(camera_data['image2D'], dtype=float)
        bg_img = self.screen_backgrounds[screen_name]
        subtracted_img = beam_img - bg_img
        subtracted_img[~np.isfinite(subtracted_img)] = 0.0
        subtracted_img[subtracted_img < 0.0] = 0.0
        return subtracted_img, bg_img.copy(), beam_img

    def get_screens(self, names=None):
        background_images, beam_images = [], []
        self.log(f'Reading screens {names}...')
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
            camera_config = self.screen_config.get(screen_name, {}) # gets pixel size and resolution
            hpixel = float(camera_config.get('s_x_res', np.nan))
            vpixel = float(camera_config.get('s_y_res', np.nan))

            try:
                # image = camera_data["image2D"]
                # proj_x = camera_data["projDataSet1"]
                # proj_y = camera_data["projDataSet2"]
                # x_positions = camera_data["imagePositionSet1"]
                # y_positions = camera_data["imagePositionSet2"]

                if screen_name not in self.screen_backgrounds:
                    self.log(f"Acquiring background image for {screen_name}.")
                    self.acquire_screen_background(screen_name, frames = 10)
                subtracted_img, bg_img, beam_img = self.acquire_screen_image(screen_name)
                x_mean, y_mean, sigx, sigy, total, img, hedges, vedges = self._screen_data_from_image(subtracted_img, hpixel, vpixel)
            except Exception as e:
                self.log(f"Couldn't acquire screen image for {screen_name}, because: {e}")
                x_mean = np.nan
                y_mean = np.nan
                sigx = np.nan
                sigy = np.nan
                total = 0.0
                subtracted_img = np.zeros((1, 1), dtype=float)
                bg_img = np.zeros((1, 1), dtype=float)
                beam_img = np.zeros((1, 1), dtype=float)
                hedges = np.array([0.0, 1.0], dtype=float)
                vedges = np.array([0.0, 1.0], dtype=float)

            status = self._read_screen_status(screen_name) # is screen inserted or extracted?
            hpixel_list.append(hpixel)
            vpixel_list.append(vpixel)
            xb_list.append(x_mean)
            yb_list.append(y_mean)
            sigx_list.append(sigx)
            sigy_list.append(sigy)
            sum_list.append(total)
            images.append(np.asarray(subtracted_img, dtype=float))
            background_images.append(np.asarray(bg_img, dtype=float))
            beam_images.append(np.asarray(beam_img, dtype=float))
            hedges_all.append(np.asarray(hedges, dtype=float))
            vedges_all.append(np.asarray(vedges, dtype=float))
            inout_list.append(status)

        return {
            "names": list(selected_names),
            "hpixel": np.asarray(hpixel_list, dtype=float), # mm
            "vpixel": np.asarray(vpixel_list, dtype=float), # mm
            "x": np.asarray(xb_list, dtype=float),
            "y": np.asarray(yb_list, dtype=float),
            "sigx": np.asarray(sigx_list, dtype=float),
            "sigy": np.asarray(sigy_list, dtype=float),
            "sum": np.asarray(sum_list, dtype=float),
            "hedges": hedges_all, #imagePositionSet1
            "vedges": vedges_all,
            "background_images": background_images,
            "beam_images": beam_images,
            "images": images, # subtracted images
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

    def _screen_data_from_image(self, image, hpixel, vpixel): # better be subtracted!
        if image is None or np.asarray(image, dtype=float).ndim!=2 or np.asarray(image, dtype=float).size==0:
            return np.nan, np.nan, np.nan, np.nan, 0.0, np.zeros((1, 1)), np.array([0.0, 1.0]), np.array([0.0, 1.0])

        # I_xi_yi, I = I_beam - I_background
        img = np.asarray(image, dtype=float).copy()
        img[~np.isfinite(img)] = 0.0
        img[img < 0] = 0.0
        ny, nx = img.shape # e.g. ny = no. of rows, nx = no. of columns
        j = np.arange(nx)
        i = np.arange(ny)
        summed_intensity = np.sum(img)
        if summed_intensity <= 0:
            hedges = (np.arange(nx + 1) - nx / 2) * hpixel
            vedges = (np.arange(ny + 1) - ny / 2) * vpixel
            return np.nan, np.nan, np.nan, np.nan, 0.0, img, hedges, vedges
        proj_x = np.sum(img, axis=0)
        proj_y = np.sum(img, axis=1)

        # center of each pixel can be expressed as: x_j = (j - (N_x - 1)/2)*hpixel, y_i = (i - (N_i - 1)/2)vhpixel

        '''
        x_centers and y_centers are arrays containing the physical coordinates of the centre of each pixel. 
        They allow to convert the image from pixel intensities into beam position and beam size.
        '''
        x_pixels_positions = (j - (nx - 1) / 2) * hpixel # coordinates of centre of each pixel
        y_pixels_positions = (i - (ny - 1) / 2) * vpixel
        x_mean_positions = np.sum((x_pixels_positions * proj_x) / summed_intensity)
        y_mean_positions = np.sum((y_pixels_positions * proj_y) / summed_intensity)

        sigx = np.sqrt(np.sum((x_pixels_positions - x_mean_positions)**2 * proj_x) / summed_intensity)
        sigy = np.sqrt(np.sum((y_pixels_positions - y_mean_positions)**2 * proj_y) / summed_intensity)

        hedges = (np.arange(nx+1) - nx / 2) * hpixel
        vedges = (np.arange(ny+1) - ny / 2) * vpixel

        return x_mean_positions, y_mean_positions, sigx, sigy, summed_intensity, img, hedges, vedges

    def log_messages(self, console):
        self.log = console or print

    def _read_screen_setting(self, screen_name):
        japc_camera = self.screen_config.get(screen_name, {}).get('japc_name', screen_name.rstrip('LH'))
        try:
            return self.client.get(f'{japc_camera}.DigiCam/Setting', context = self.context_empty).data
        except Exception as e:
            print(e)
            return None
