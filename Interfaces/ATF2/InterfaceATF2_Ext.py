import sys, time, math, os, threading, struct
import numpy as np
from epics import PV, ca, caget
from Interfaces.AbstractMachineInterface import AbstractMachineInterface
from collections import defaultdict

class CurrentDropToZeroError(RuntimeError):
    def __init__(self, message, *, target=None, readback=None, magnets=None):
        super().__init__(message)
        self.target = dict(target or {})
        self.readback = dict(readback or {})
        self.magnets = list(magnets or [])


class InterfaceATF2_Ext(AbstractMachineInterface):
    def get_name(self):
        return 'ATF2_Ext'

    def __init__(self, nsamples=10, nominal_intensity=0.15, wfs_intensity=0.1):
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
        self.bpm_sample_interval_s = 0.5

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
        #sequence = [ 'MB1X', 'MB2X', 'ZV1X', 'MQF1X', 'ZV2X', 'MQD2X', 'MQF3X', 'ZH1X', 'ZV3X', 'MQF4X', 'ZH2X', 'MQD5X', 'ZV4X', 'ZV5X', 'MQF6X', 'MQF7X', 'ZVFB1X', 'ZHFB1X', 'ZH3X', 'MQD8X', 'ZV6X', 'ZHFB2X', 'MQF9X', 'ZH4X', 'ZVFB2X', 'ZV7X', 'MQD10X', 'ZH5X', 'MQF11X', 'ZV8X', 'MQD12X', 'ZH6X', 'MQF13X', 'MQD14X', 'ZH7X', 'MQF15X', 'ZV9X', 'MQD16X', 'ZH8X', 'MQF17X', 'ZV10X', 'MQD18X', 'ZH9X', 'MQF19X', 'ZV11X', 'MQD20X', 'ZVFB1FF', 'ZHFB1FF', 'ZH10X', 'MQF21X', 'MQM16FF', 'ZH1FF', 'ZV1FF', 'MQM15FF', 'MQM14FF', 'MQM12FF', 'MQM11FF', 'MQD10AFF', 'MQF9AFF', 'MQD8FF', 'MQF7FF', 'MQF5BFF', 'MQD4BFF', 'MQF3FF', 'MQD2BFF', 'MQD2AFF', 'MSF1FF', 'MPREIP', 'MW1IP', 'MPIP', 'MDUMP' ]
        # ATF2' BPMs Epics names
        # https://atf.kek.jp/atfbin/view/ATF/EPICS_DATABASE
        '''
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
        '''

        monitors = [
            "MB1X", "MB2X", "MQF1X", "MQD2X", "MQF3X", "MQF4X", "MQD5X", "MQF6X",
            "MQF7X", "MQD8X", "MQF9X", "MQD10X", "MQF11X", "MQD12X", "MQF13X",
            "MQD14X", "MQF15X", "MQD16X", "MQF17X", "MQD18X", "MQF19X",
            "MQF21X", "MQM16FF",
            "MQM15FF", "MQM14FF",
            "MQM11FF", "MQD10BFF", "MQD10AFF", "MQF9AFF",
            "MQD8FF", "MQF7FF", "MQF5BFF", "MQD4BFF", "MQF3FF", "MQD2BFF", "MQD2AFF",
            "MSF1FF", "MPREIP", "MIPB"
            ]

        self.MONITOR_INDEX_TO_NAME = {
            0: "MB1X",
            1: "MB2X",
            2: "MQF1X",
            3: "MQD2X",
            4: "MQF3X",
            5: "MQF4X",
            6: "MQD5X",
            7: "MQF6X",
            8: "MQF7X",
            9: "MQD8X",
            10: "MQF9X",
            11: "MQD10X",
            12: "MQF11X",
            13: "MQD12X",
            14: "MQF13X",
            15: "MQD14X",
            16: "MQF15X",
            17: "MQD16X",
            18: "MQF17X",
            19: "MQD18X",
            20: "MQF19X",
            21: "MQD20X",
            22: "MQF21X",
            23: "IPBPM1",
            24: "IPBPM2",
            25: "nBPM1",
            26: "nBPM2",
            27: "nBPM3",
            28: "MQM16FF",
            29: "MQM15FF",
            30: "MQM14FF",
            31: "MFB2FF",
            32: "MQM13FF",
            33: "MQM12FF",
            34: "MFB1FF",
            35: "MQM11FF",
            36: "MQD10BFF",
            37: "MQD10AFF",
            38: "MQF9BFF",
            39: "MSF6FF",
            40: "MQF9AFF",
            41: "MQD8FF",
            42: "MQF7FF",
            43: "MQD6FF",
            44: "MQF5BFF",
            45: "MSF5FF",
            46: "MQF5AFF",
            47: "MQD4BFF",
            48: "MSD4FF",
            49: "MQD4AFF",
            50: "MQF3FF",
            51: "MQD2BFF",
            52: "MQD2AFF",
            53: "MSF1FF",
            54: "MQF1FF",
            55: "MSD0FF",
            56: "MQD0FF",
            57: "M1&2IP",
            58: "MPIP",
            59: "MDUMP",
            60: "ICT1X",
            61: "ICTDUMP",
            62: "MW1X",
            63: "MW1IP",
            64: "MPREIP",
            65: "MIPA",
            66: "MIPB"}

        # Keep the full configured order for future element classes (quads, sextupoles, movers).
        self.sequence_raw = list(sequence)
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
        self.movable_magnets = [string for string in self.sequence_raw if string.upper().startswith(('MQ', 'MS'))]
        self.qmag_alias_to_canonical = {}
        for name in self.movable_magnets:
            self.qmag_alias_to_canonical[name] = name
        q_aliases = [string for string in self.sequence_raw if string.upper().startswith('Q')]
        for qname in q_aliases:
            candidate = f"M{qname}"
            if candidate in self.movable_magnets:
                self.qmag_alias_to_canonical[qname] = candidate
            else:
                # Keep alias as-is if no canonical counterpart exists.
                self.qmag_alias_to_canonical[qname] = qname
        # Index of the selected BPMs in the Epics PV ATF2:monitors
        self.bpm_indexes = [index for index, string in enumerate(monitors) if string in self.bpms]
        # Bunch current monitors
        self.ict_names = [
            'gun:GUNcharge', 'l0:L0charge', 'linacbt:LNEcharge', 'linacbt:BTMcharge',
            'ext:EXTcharge', 'linacbt:BTEcharge', 'BIM:DR:nparticles', 'BIM:IP:nparticles'
        ]
        self.nominal_laser_intensity = nominal_intensity
        self.laser_intensity = PV('RFGun:LaserIntensity1:Read').get()
        self.test_laser_intensity = wfs_intensity
        #PV('RFGun:LaserIntensity1:Read').get()

        # IPBSM hooks and FF knob definitions (real machine)
        self.error_history = []
        self.pv_trigger = PV("IPBSM:FringeScan:RemoteScanStart")
        self.pv_end = PV("IPBSM:FringeScan:RemoteScanFinish")
        self._ipbsm_lock = threading.Lock()
        self.datafile = "/atf/data/ipbsm/knob/knob_fringe_result_v2.dat"

        self.linear_matrix = {
            "Ax": {"SD0FF": (-116.5, 0), "SF1FF": (-35.2, 0), "SD4FF": (-37.8, 0), "SF5FF": (0, 0), "SF6FF": (-623.4, 0)},
            "Ex": {"SD0FF": (-813.0, 0), "SF1FF": (793.5, 0), "SD4FF": (-137.9, 0), "SF5FF": (0, 0), "SF6FF": (1492.9, 0)},
            "Ay": {"SD0FF": (-98.9, 0), "SF1FF": (-9.6, 0), "SD4FF": (-246.7, 0), "SF5FF": (0, 0), "SF6FF": (120.0, 0)},
            "Ey": {"SD0FF": (0, 374.1), "SF1FF": (0, -120.0), "SD4FF": (0, -451.3), "SF5FF": (0, 0), "SF6FF": (0, -64.3)},
            "Coup1": {"SD0FF": (0, -100), "SF1FF": (0, 100), "SD4FF": (0, 0), "SF5FF": (0, 0), "SF6FF": (0, 0)},
            "Coup2": {"SD0FF": (0, 107.8), "SF1FF": (0, 4.2), "SD4FF": (0, 152.6), "SF5FF": (0, 0), "SF6FF": (0, 90.4)},
            "Spare1": {"SD0FF": (-676.0, 0), "SF1FF": (-316.0, 0), "SD4FF": (252.0, 0), "SF5FF": (587.0, 0), "SF6FF": (593.0, 0)},
            "Spare2": {"SD0FF": (0, 78.0), "SF1FF": (0, 188.0), "SD4FF": (0, -55.0), "SF5FF": (-179.0, 0), "SF6FF": (0, 38.0)},
            "Spare3": {"SD0FF": (0, 0), "SF1FF": (0, 0), "SD4FF": (0, 1), "SF5FF": (0, 0), "SF6FF": (0, 0)},
        }
        self.nonlinear_matrix = {
            "Y24": {"SK1FF": 0.0, "SK2FF": 0.0, "SK3FF": 0.0, "SK4FF": 0.0, "SD0FF": 0.119, "SF1FF": -0.013, "SD4FF": -0.554, "SF5FF": -0.083, "SF6FF": -0.175},
            "Y46": {"SK1FF": 0.0, "SK2FF": 0.0, "SK3FF": 0.0, "SK4FF": 0.0, "SD0FF": 0.259, "SF1FF": -0.057, "SD4FF": 1.049, "SF5FF": -0.106, "SF6FF": -0.056},
            "Y22": {"SK1FF": -1.629, "SK2FF": 0.174, "SK3FF": 1.024, "SK4FF": 2.435, "SD0FF": 0.0, "SF1FF": 0.0, "SD4FF": 0.0, "SF5FF": 0.0, "SF6FF": 0.0},
            "Y26": {"SK1FF": 1.763, "SK2FF": -0.126, "SK3FF": 0.463, "SK4FF": -0.701, "SD0FF": 0.0, "SF1FF": 0.0, "SD4FF": 0.0, "SF5FF": 0.0, "SF6FF": 0.0},
            "Y66": {"SK1FF": 5.571, "SK2FF": -0.207, "SK3FF": -4.668, "SK4FF": -6.673, "SD0FF": 0.0, "SF1FF": 0.0, "SD4FF": 0.0, "SF5FF": 0.0, "SF6FF": 0.0},
            "Y44": {"SK1FF": 0.037, "SK2FF": 1.614, "SK3FF": -0.458, "SK4FF": -0.186, "SD0FF": 0.0, "SF1FF": 0.0, "SD4FF": 0.0, "SF5FF": 0.0, "SF6FF": 0.0},
            "Spare": {"SK1FF": 0.0, "SK2FF": 0.0, "SK3FF": 0.0, "SK4FF": 0.0, "SD0FF": 0.0, "SF1FF": 0.0, "SD4FF": 0.0, "SF5FF": 0.0, "SF6FF": 0.0},
        }
        self._linear_knob_values = {k: 0.0 for k in self.linear_matrix.keys()}
        self._nonlinear_knob_values = {k: 0.0 for k in self.nonlinear_matrix.keys()}
        self.corrector_knob_pvs = {
            "corrector 1": {
                "pv_set": "IPBPM:PMC:D:setPosWrite",
                "pv_move": "IPBPM:PMC:D:Move.PROC",
                "pv_busy": "IPBPM:PMC:D:busyStatus",
            },
            "Abe chamber": {
                "pv_set": "WAKECHAMBER:VER:SETVAL",
                "pv_move": "WAKECHAMBER:VER:CHANGE_ABS_AND_MOVE:PROC",
                "pv_busy": "WAKECHAMBER:VER:BUSY",
            },
        }
        self._corrector_knob_values = {k: float("nan") for k in self.corrector_knob_pvs.keys()}
        self.zscan_mode_axes = {
            "2-8": "M8LY",
            "30": "M30LY",
            "174": "M174LY",
        }
        self.zscan_knob_name = "Z scan knob"
        self._zscan_knob_values = {self.zscan_knob_name: 0.0}


    def _build_qmag_pv_names(self, mag_name, slacsys_mov_notation=None):
        # slacsys_mov_notation is kept as an explicit hook for future system-specific naming.
        if slacsys_mov_notation is None:
            slacsys_mov_notation = f"{mag_name}:"

        return {
            "pv_read_lvdt1": slacsys_mov_notation + "lvdt1",
            "pv_read_lvdt2": slacsys_mov_notation + "lvdt2",
            "pv_read_lvdt3": slacsys_mov_notation + "lvdt3",
            "pv_read_lvdt_x": slacsys_mov_notation + "x:lvdt",
            "pv_read_lvdt_y": slacsys_mov_notation + "y:lvdt",
            "pv_read_lvdt_tilt": slacsys_mov_notation + "tilt:lvdt",
            "pv_read_lvdt1_raw": slacsys_mov_notation + "lvdt1:raw",
            "pv_read_lvdt2_raw": slacsys_mov_notation + "lvdt2:raw",
            "pv_read_lvdt3_raw": slacsys_mov_notation + "lvdt3:raw",
            "pv_set_x": f"{mag_name}:MAG:DES:X",
            "pv_set_y": f"{mag_name}:MAG:DES:Y",
            "pv_set_roll": f"{mag_name}:MAG:DES:R",
            "pv_read_enc_x": f"{mag_name}:ENC:X",
            "pv_read_enc_y": f"{mag_name}:ENC:Y",
            "pv_read_enc_roll": f"{mag_name}:ENC:R",
            "pv_read_enc1_mrp": f"{mag_name}:ENC1:MRP",
            "pv_read_enc2_mrp": f"{mag_name}:ENC2:MRP",
            "pv_read_enc3_mrp": f"{mag_name}:ENC3:MRP",
            "pv_read_enc1_step": f"{mag_name}:ENC1",
            "pv_read_enc2_step": f"{mag_name}:ENC2",
            "pv_read_enc3_step": f"{mag_name}:ENC3",
            "pv_read_enc1_angl": f"{mag_name}:ENC1:ANG",
            "pv_read_enc2_angl": f"{mag_name}:ENC2:ANG",
            "pv_read_enc3_angl": f"{mag_name}:ENC3:ANG",
            "pv_read_pot_x": f"{mag_name}:POT:X",
            "pv_read_pot_y": f"{mag_name}:POT:Y",
            "pv_read_pot_roll": f"{mag_name}:POT:R",
            "pv_read_pot1_mrp": f"{mag_name}:POT1:MRP",
            "pv_read_pot2_mrp": f"{mag_name}:POT2:MRP",
            "pv_read_pot3_mrp": f"{mag_name}:POT3:MRP",
            "pv_read_pot1_ang": f"{mag_name}:POT1:ANG",
            "pv_read_pot2_ang": f"{mag_name}:POT2:ANG",
            "pv_read_pot3_ang": f"{mag_name}:POT3:ANG",
            "pv_read_pot1_count": f"{mag_name}:POT1:RBV",
            "pv_read_pot2_count": f"{mag_name}:POT2:RBV",
            "pv_read_pot3_count": f"{mag_name}:POT3:RBV",
            "pv_read_pot1_volt": f"{mag_name}:POT1:INV",
            "pv_read_pot2_volt": f"{mag_name}:POT2:INV",
            "pv_read_pot3_volt": f"{mag_name}:POT3:INV",
            "pv_read_pot1_volt_mean": f"{mag_name}:POT1:INV:AVG",
            "pv_read_pot2_volt_mean": f"{mag_name}:POT2:INV:AVG",
            "pv_read_pot3_volt_mean": f"{mag_name}:POT3:INV:AVG",
            "pv_read_pot1_lim_upper": f"{mag_name}:POT1:PLM",
            "pv_read_pot1_lim_lower": f"{mag_name}:POT1:NLM",
            "pv_read_pot2_lim_upper": f"{mag_name}:POT2:PLM",
            "pv_read_pot2_lim_lower": f"{mag_name}:POT2:NLM",
            "pv_read_pot3_lim_upper": f"{mag_name}:POT3:PLM",
            "pv_read_pot3_lim_lower": f"{mag_name}:POT3:NLM",
            "pv_set_mtr1_stop": f"{mag_name}:M1:STOP",
            "pv_set_mtr2_stop": f"{mag_name}:M2:STOP",
            "pv_set_mtr3_stop": f"{mag_name}:M3:STOP",
            "pv_set_mtr1_pos_abs": f"{mag_name}:M1:MOV:ABS",
            "pv_set_mtr2_pos_abs": f"{mag_name}:M2:MOV:ABS",
            "pv_set_mtr3_pos_abs": f"{mag_name}:M3:MOV:ABS",
            "pv_set_mtr1_pos_rel": f"{mag_name}:M1:MOV:REL",
            "pv_set_mtr2_pos_rel": f"{mag_name}:M2:MOV:REL",
            "pv_set_mtr3_pos_rel": f"{mag_name}:M3:MOV:REL",
            "pv_motorsteps1": f"{mag_name}:M1:POS",
            "pv_motorsteps2": f"{mag_name}:M2:POS",
            "pv_motorsteps3": f"{mag_name}:M3:POS",
            "pv_read_mtr1_step": f"{mag_name}:M1:DES:STP",
            "pv_read_mtr2_step": f"{mag_name}:M2:DES:STP",
            "pv_read_mtr3_step": f"{mag_name}:M3:DES:STP",
            "pv_read_mtr1_angl": f"{mag_name}:M1:ANG",
            "pv_read_mtr2_angl": f"{mag_name}:M2:ANG",
            "pv_read_mtr3_angl": f"{mag_name}:M3:ANG",
            "pv_read_mtr1_busy": f"_{mag_name}:M1:BUSY",
            "pv_read_mtr2_busy": f"_{mag_name}:M2:BUSY",
            "pv_read_mtr3_busy": f"_{mag_name}:M3:BUSY",
            "pv_set_mag_move": f"{mag_name}:MOVE",
            "pv_dotrim": f"{mag_name}:TRIM",
            "pv_set_mag_x": f"{mag_name}:MAG:X",
            "pv_set_mag_y": f"{mag_name}:MAG:Y",
            "pv_set_mag_roll": f"{mag_name}:MAG:R",
            "pv_set_mag_stop": f"{mag_name}:STOP",
        }

    def _pv_get(self, pv_name, default=np.nan, timeout=0.7):
        try:
            pv = PV(pv_name)
            if not pv.wait_for_connection(timeout=timeout):
                return default
            val = pv.get(timeout=timeout)
            if val is None:
                return default
            return float(val)
        except Exception:
            return default

    def _pv_put(self, pv_name, value):
        PV(pv_name).put(value)


    def insert_screen(self, screen_name):
        screen_pv_name = self.screen_pv_names.get(screen_name)
        if screen_pv_name is None:
            raise ValueError(f"Unknown screen: {screen_name}")

        PV(f"{screen_pv_name}:Target:WRITE:IN").put(1)
        time.sleep(2)

    def extract_screen(self, screen_name):
        screen_pv_name = self.screen_pv_names.get(screen_name)
        if screen_pv_name is None:
            raise ValueError(f"Unknown screen: {screen_name}")

        PV(f"{screen_pv_name}:Target:WRITE:OUT").put(1)
        time.sleep(2)

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

    def get_movable_magnets_names(self):
        return self.movable_magnets

    def get_quadrupoles(self, names=None, include_pv_names=False):
        if names is None:
            names = self.qmags
        if type(names) == str:
            names = [names]
        names = [name for name in names if name in self.qmag_pv]

        ides, iact = [], []
        xdes, ydes, rolldes = [], [], []
        xact, yact, rollact = [], [], []

        for name in names:
            pv = self.qmag_pv[name]
            canonical = self.qmag_alias_to_canonical.get(name, name)
            ides.append(self._pv_get(f"{canonical}:currentWrite"))
            iact.append(self._pv_get(f"{canonical}:currentRead"))
            xdes.append(self._pv_get(pv["pv_set_x"]))
            ydes.append(self._pv_get(pv["pv_set_y"]))
            rolldes.append(self._pv_get(pv["pv_set_roll"]))
            xact.append(self._pv_get(pv["pv_read_enc_x"]))
            yact.append(self._pv_get(pv["pv_read_enc_y"]))
            rollact.append(self._pv_get(pv["pv_read_enc_roll"]))

        data = {
            "names": names,
            "ides": np.array(ides, dtype=float),
            "iact": np.array(iact, dtype=float),
            "xdes": np.array(xdes, dtype=float),
            "ydes": np.array(ydes, dtype=float),
            "rolldes": np.array(rolldes, dtype=float),
            "xact": np.array(xact, dtype=float),
            "yact": np.array(yact, dtype=float),
            "rollact": np.array(rollact, dtype=float),
        }
        if include_pv_names:
            data["pvs"] = {name: dict(self.qmag_pv[name]) for name in names}
        return data

    def _decode_ipbsm_dat(self, raw: bytes):
        offset = 0
        save_amplitude, = struct.unpack_from("<d", raw, offset); offset += 8
        save_eamplitude, = struct.unpack_from("<d", raw, offset); offset += 8
        save_beamsize, = struct.unpack_from("<d", raw, offset); offset += 8
        save_ebeamsize, = struct.unpack_from("<d", raw, offset); offset += 8
        save_average, = struct.unpack_from("<d", raw, offset); offset += 8
        save_phase, = struct.unpack_from("<d", raw, offset); offset += 8
        save_filename = raw[offset:offset + 256].split(b"\x00", 1)[0].decode(errors="ignore")
        offset += 256
        save_ict_average, = struct.unpack_from("<d", raw, offset)
        return {
            "modulation": float(save_amplitude),
            "error": abs(float(save_eamplitude)),
            "beamsize": float(save_beamsize),
            "ebeamsize": float(save_ebeamsize),
            "average": float(save_average),
            "phase": float(save_phase),
            "filename": str(save_filename),
            "ict_average": float(save_ict_average),
        }


    # Backward-compatibility alias for the typo used in discussion.
    def get_quadropoles(self, names=None, include_pv_names=False):
        return self.get_quadrupoles(names=names, include_pv_names=include_pv_names)

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

    def get_elements_indices(self, names):
        if isinstance(names, str):
            names = [names]
        name_to_index = {string: index for index, string in enumerate(self.sequence)}
        return [name_to_index.get(name, np.nan) for name in names]

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





