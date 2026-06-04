import RF_Track as rft
import numpy as np
import time, os, re
from Backend.LogConsole import LogConsole
from datetime import datetime
from Interfaces.AbstractMachineInterface import AbstractMachineInterface
# from . import ipbsm_calc
# from .knobs import KnobSystem
class InterfaceATF2_Ext_RFTrack(AbstractMachineInterface):

# For OTR0X:
# emit x 5.2
# beta x 6.305152438
# alpha x -4.494292895

# emit y 0.03
# beta y 6.190329503
# alpha y 2.576336962

# For QD18X end:
# emit x 5.2
# beta x 1.105221776
# alpha x -0.7752115812

# emit y 0.03
# beta y 10.34240856
# alpha y -3.739163822

    def get_name(self):
        return 'ATF2_Ext_RFT'

    def __init__(self, population=2e10, jitter=1.0, bpm_resolution=0.0, nsamples=1, nparticles=1000):
        super().__init__()
        self.log = print
        self.rng = np.random.default_rng(12345) # uncomment for jitter subtraction check
        self.twiss_path = os.path.join(os.path.dirname(__file__), 'Ext_ATF2', 'ATF2_EXT_FF_v5.2.twiss')
        self.lattice = rft.Lattice(self.twiss_path)
        self.lattice.set_bpm_resolution(bpm_resolution)
        for s in self.lattice['*OTR*']:
            screen = rft.Screen()
            screen.set_name(s.get_name())
            s.replace_with(screen)
        self.sequence = [e.get_name() for e in self.lattice['*']]
        self._attach_wake_data_to_elements(wake_scale=0,nsteps=20)
        self.bpms = [e.get_name() for e in self.lattice.get_bpms()]
        self.corrs = [e.get_name() for e in self.lattice.get_correctors()]
        self.screens = [e.get_name() for e in self.lattice.get_screens()]
        self.quadrupoles = list(dict.fromkeys(e.get_name() for e in self.lattice.get_quadrupoles()))
        self.sextupoles = self._get_element_names_from_twiss_types({"SEXTUPOLE"})
        self.Pref = 1.2999999e3  # 1.3 GeV/c
        self.nparticles = nparticles
        self.electronmass = rft.electronmass
        self.population = population
        self.jitter = jitter
        self.nsamples = nsamples
        self.Q = -1
        self.dfs_test_energy = 0.98
        self.wfs_test_charge = 0.90
        self.coupling_roll = 0.0
        self.__setup_beam0()
        self.__track_bunch()
        self._saved_sextupoles_state = None
        self.qmag_xdes = {name: 0.0 for name in self.quadrupoles}
        self.qmag_ydes = {name: 0.0 for name in self.quadrupoles}
        self.qmag_rolldes = {name: 0.0 for name in self.quadrupoles}
        #self.qm_list = [s for s in self.interface.get_sequence() if str(s).upper().startswith("Q")]

        # ----------------------------
        # Knobs (linear / nonlinear)
        # ----------------------------

        #self.knobs = KnobSystem(self.lattice, p_ref=-self.Pref)

        self.kl_per_A = {
            "ZH100RX": 0.0007311, "ZH101RX": 0.0002322, "ZV100RX": 0.0002764, "ZV1X": 0.0003276, "ZX1X": 0.0,
            "ZV2X": 0.0003276,    "ZH1X": 0.0003018,    "ZV3X": 0.0003276,    "ZH2X": 0.0003018, "ZV4X": 0.0003276,
            "ZX2X": 0.0,          "ZV5X": 0.0003276,    "ZH3X": 0.0003018,    "ZV6X": 0.0003276, "ZH4X": 0.0003018,
            "ZV7X": 0.0003276,    "ZH5X": 0.0003018,    "ZV8X": 0.0003276,    "ZH6X": 0.0003018, "ZH7X": 0.0003018,
            "ZV9X": 0.0003276,    "ZH8X": 0.0003018,    "ZV10X": 0.0003276,   "ZH9X": 0.0003018, "ZV11X": 0.0003276,
            "ZH10X": 0.0003018,   "ZH1FF": 0.0003018,   "ZV1FF": 0.0003276,   "IPKICK": 0.0,     "QS1X": -0.0051397,
            "QS2X": -0.0051397,   "QF6X": -0.0216857,   "QF1FF": -0.0061125,  "QD0FF": 0.0070313,
        }

        self.Qmagnames = ['QS1X', 'QF1X', 'QD2X', 'QF3X', 'QF4X', 'QD5X', 'QF6X', 'QS2X', 'QF7X', 'QD8X', 'QF9X',
                          'QK1X', 'QD10X', 'QF11X', 'QK2X', 'QD12X', 'QF13X', 'QD14X', 'QF15X', 'QK3X', 'QD16X',
                          'QF17X', 'QK4X', 'QD18X', 'QF19X', 'QD20X', 'QF21X', 'QM16FF', 'QM15FF', 'QM14FF', 'QM13FF',
                          'QM12FF', 'QM11FF', 'QD10BFF', 'QD10AFF', 'QF9BFF', 'QF9AFF', 'QD8FF', 'QF7FF', 'QD6FF',
                          'QF5BFF', 'QF5AFF', 'QD4BFF', 'QD4AFF', 'QF3FF', 'QD2BFF', 'QD2AFF', 'QF1FF', 'QD0FF']


    def _get_element_names_from_twiss_types(self, allowed_types): # because rf track doesn't have get sextupoles
        with open(self.twiss_path, "r") as file:
            lines = [line.strip() for line in file if line.strip()]
        header_idx = None
        format_idx = None
        name_column = None
        type_column = None
        for i, line in enumerate(lines):
            if not line.startswith("*"):
                continue
            columns = line.lstrip("*").split()
            if "NAME" not in columns:
                continue
            type_col_name = None
            if "KEYWORD" in columns:
                type_col_name = "KEYWORD"
            elif "TYPE" in columns:
                type_col_name = "TYPE"
            else:
                continue
            header_idx = i
            name_column = columns.index("NAME")
            type_column = columns.index(type_col_name)
            for j in range(i + 1, len(lines)):
                if lines[j].startswith("$"):
                    format_idx = j
                    break
            break
        if header_idx is None or format_idx is None:
            return []
        names = []
        seen = set()
        for line in lines[format_idx + 1:]:
            if line.startswith("@") or line.startswith("*") or line.startswith("$"):
                continue
            data = line.split()
            if len(data) <= max(name_column, type_column):
                continue
            elem_name = data[name_column].strip('"')
            elem_type = data[type_column].strip('"').upper()
            if elem_type in allowed_types and elem_name not in seen:
                names.append(elem_name)
                seen.add(elem_name)
        return names

    def get_beam_factors(self):
        gamma_rel = np.sqrt((self.Pref / self.electronmass) ** 2 + 1.0)
        beta_rel = np.sqrt(1.0 - 1.0 / gamma_rel ** 2)
        return gamma_rel, beta_rel

    def log_messages(self, console):
        self.log = console or print

    def __setup_beam0(self):
        T = rft.Bunch6d_twiss()
        T.emitt_x = 5.2  # mm.mrad normalised emittance
        T.emitt_y = 0.03  # mm.mrad
        T.beta_x = 6.848560987  # m
        T.beta_y = 2.935758992  # m
        T.alpha_x = 1.108024744
        T.alpha_y = -1.907222942
        T.sigma_t = 8  # mm/c
        T.sigma_pt = 0.8  # permille
        # T_sigma_pt = 0.0001 # for test
        self.B0 = rft.Bunch6d_QR(rft.electronmass, self.population, self.Q, self.Pref, T, self.nparticles)

    def __setup_beam1(self):
        # Beam for DFS - Reduced energy
        Pref = self.dfs_test_energy * self.Pref
        T = rft.Bunch6d_twiss()
        T.emitt_x = 5.2  # mm.mrad normalised emittance
        T.emitt_y = 0.03  # mm.mrad
        T.beta_x = 6.848560987  # m
        T.beta_y = 2.935758992  # m
        T.alpha_x = 1.108024744
        T.alpha_y = -1.907222942
        T.sigma_t = 8  # mm/c
        T.sigma_pt = 0.8  # permille
        Nparticles = 1000  # number of macroparticles
        self.B0 = rft.Bunch6d_QR(rft.electronmass, self.population, self.Q, Pref, T, self.nparticles)

    def __setup_beam2(self):
        # Beam for WFS - Reduced bunch charge
        population = self.wfs_test_charge * self.population
        T = rft.Bunch6d_twiss()
        T.emitt_x = 5.2  # mm.mrad normalised emittance
        T.emitt_y = 0.03  # mm.mrad
        T.beta_x = 6.848560987  # m
        T.beta_y = 2.935758992  # m
        T.alpha_x = 1.108024744
        T.alpha_y = -1.907222942
        T.sigma_t = 8  # mm/c
        T.sigma_pt = 0.8  # permille
        Nparticles = 1000  # number of macroparticles
        self.B0 = rft.Bunch6d_QR(rft.electronmass, population, self.Q, self.Pref, T, self.nparticles)

    def __track_bunch(self):
        I0 = self.B0.get_info()
        # dx = self.jitter * I0.sigma_x
        # dy = self.jitter * I0.sigma_y
        # dz, dt, roll = 0.0, 0.0, float(self.coupling_roll)
        # pitch = self.jitter * I0.sigma_py
        # yaw = self.jitter * I0.sigma_px

        #Uncomment for jitter subtraction tests
        dx = self.rng.normal(0.0, self.jitter * I0.sigma_x)
        dy = self.rng.normal(0.0, self.jitter * I0.sigma_y)
        pitch = self.rng.normal(0.0, self.jitter * I0.sigma_py)
        yaw = self.rng.normal(0.0, self.jitter * I0.sigma_px)
        dz, dt, roll = 0.0, 0.0, float(self.coupling_roll)

        B0_offset = self.B0.displaced(dx, dy, dz, dt, roll, pitch, yaw)
        B1=self.lattice.track(B0_offset)
        I = B0_offset.get_info()

    def set_coupling_roll(self, angle_in_rad = 0.0):
        self.coupling_roll = float(angle_in_rad)
        self.__setup_beam0()
        self.__track_bunch()

    def change_energy(self):
        self.__setup_beam1()
        self.__track_bunch()
        dP_P = self.dfs_test_energy - 1.0
        return dP_P

    def reset_energy(self):
        self.__setup_beam0()
        self.__track_bunch()

    def change_intensity(self):  # reduced charge
        self.__setup_beam2()
        self.__track_bunch()

    def reset_intensity(self):
        self.__setup_beam0()
        self.__track_bunch()

    def get_sequence(self):
        return self.sequence

    def get_hcorrectors_names(self):
        return [string for string in self.corrs if
                (string.lower().startswith('zh')) or (string.lower().startswith('zx'))]

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
        #self.log("Reading ict's...")
        icts = {
            "names": self.bpms,
            "charge": np.array([bpm.get_total_charge() for bpm in self.lattice.get_bpms()])
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
        #self.log("Reading correctors' strengths...")
        bdes = np.zeros(len(self.corrs))
        for i, corrector in enumerate(self.corrs):
            if corrector[:2] == "ZH" or corrector[:2] == "ZX":
                bdes[i] = self.lattice[corrector].get_strength()[0] * 10
            elif corrector[:2] == "ZV":
                bdes[i] = self.lattice[corrector].get_strength()[1] * 10

        correctors = {"names": self.corrs, "bdes": bdes, "bact": bdes.copy()}

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
        #self.log('Reading bpms...')
        x = np.zeros((self.nsamples, len(self.bpms)))
        y = np.zeros(x.shape)
        tmit = np.zeros(x.shape)

        # for i in range(self.nsamples):
        #     for j, bpm in enumerate(self.bpms):
        #         b = self.lattice[bpm]
        #         reading = b.get_reading()
        #         x[i, j] = reading[0]
        #         y[i, j] = reading[1]
        #         tmit[i, j] = b.get_total_charge()


        # Uncomment for jitter subtraction tests
        for i in range(self.nsamples):
            self.__track_bunch()
            for j, bpm in enumerate(self.bpms):
                b = self.lattice[bpm]
                reading = b.get_reading()
                x[i, j] = reading[0]
                y[i, j] = reading[1]
                tmit[i, j] = b.get_total_charge()


        bpms = {"names": self.bpms, "x": x, "y": y, "tmit": tmit}

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

    def get_screens(self, names=None):
        #self.log('Reading screens...')
        if isinstance(names, str):
            names = [names]  # allows passing a single screen name
        hpixel = 0.001  # mm, horizontal size of a pixel
        vpixel = 0.001  # mm, vertical size of a pixel
        hpixel_list = []
        vpixel_list = []
        xb_list = []
        yb_list = []
        sigx_list = []
        sigy_list = []
        sigxy_list = []
        tilt_list = []
        sum_list = []
        images = []
        hedges_all = []
        vedges_all = []
        screen_names = []
        s_list=[]

        # get S positions of screens
        with open(self.twiss_path, "r") as file:
            lines = [line.strip() for line in file if line.strip()]

        star_symbol = next(i for i, line in enumerate(lines) if line.startswith("*"))
        dollar_sign = next(i for i, line in enumerate(lines) if line.startswith("$") and i > star_symbol)
        columns = lines[star_symbol].lstrip("*").split()
        try:
            name_column = columns.index("NAME")
            s_column = columns.index("S")
        except ValueError as e:
            raise RuntimeError("There are no such columns in the twiss file")

        s_values = {}
        for line in lines[dollar_sign + 1:]:
            data = line.split()
            if len(data) <= max(name_column, s_column):  # if a line has less column than needed, it is omitted
                continue
            screen_name = data[name_column].strip('"')
            try:
                s_values[screen_name] = (float(data[s_column]))
            except ValueError:
                continue

        for s in self.lattice.get_screens():
            screen_name = s.get_name()
            if names is not None and screen_name not in names:
                continue
            screen_names.append(screen_name)
            s_list.append(s_values.get(screen_name, np.nan))
            hpixel_list.append(hpixel)
            vpixel_list.append(vpixel)
            m = s.get_bunch().get_phase_space('%x %y')
            if m is None or len(m) == 0:  # empty bunch
                xb_list.append(np.nan)
                yb_list.append(np.nan)
                sigx_list.append(np.nan)
                sigy_list.append(np.nan)
                sigxy_list.append(np.nan)
                tilt_list.append(np.nan)
                sum_list.append(0)
                images.append(np.zeros((1, 1)))
                hedges_all.append(np.array([0, hpixel]))
                vedges_all.append(np.array([0, vpixel]))
                continue

            sumw = len(m[:, 0])  # number of particles in the screen; intensity
            x_mean = float(np.mean(m[:,0]))
            y_mean = float(np.mean(m[:,1]))
            x_centered = m[:,0] - x_mean
            y_centered = m[:,1] - y_mean

            sigx = float(np.std(m[:, 0])) # RMS x beam size
            sigy = float(np.std(m[:, 1])) # RMS y beam size
            sigxy = float(np.mean(x_centered * y_centered))
            tilt = float(0.5 * np.arctan2(2.0 * sigxy, sigx ** 2 - sigy ** 2))  # ellipse angle

            xb_list.append(x_mean) # mean x of particles
            yb_list.append(y_mean)
            sigx_list.append(sigx)
            sigy_list.append(sigy)
            sigxy_list.append(sigxy)
            tilt_list.append(tilt)
            sum_list.append(sumw)

            nx = int(np.ceil(np.ptp(m[:, 0]) / hpixel)) if np.ptp(
                m[:, 0]) > 0 else 1  # ceil rounds up, so it can take the whole range
            ny = int(np.ceil(np.ptp(m[:, 1]) / vpixel)) if np.ptp(m[:, 1]) > 0 else 1
            nx = int(np.clip(nx, 10, 400))
            ny = int(np.clip(ny, 10, 400))
            image, hedges, vedges = np.histogram2d(m[:, 0], m[:, 1], bins=(nx, ny))  # divides x axis into nx bins, y axis into ny bins and calculates how many particles are in each rectangle
            images.append(image)  # image[i,j] = nparticles in bin i on x axis and nparticles in bin j on y axis
            hedges_all.append(hedges)  # bin edges in x (nx + 1)
            vedges_all.append(vedges)  # bin edges in y (ny + 1)

        screens = {"names": screen_names,
                   "hpixel": np.array(hpixel_list, dtype=float),
                   "vpixel": np.array(vpixel_list, dtype=float),
                   "x": np.array(xb_list, dtype=float),
                   "y": np.array(yb_list, dtype=float),
                   "sigx": np.array(sigx_list, dtype=float),
                   "sigy": np.array(sigy_list, dtype=float),
                   "sigxy": np.array(sigxy_list, dtype=float),
                   "tilt": np.array(tilt_list, dtype=float),
                   "sum": np.array(sum_list, dtype=float),
                   "hedges": hedges_all,
                   "vedges": vedges_all,
                   "images": images,
                   "S": np.array(s_list, dtype=float),}
        return screens

    def get_quadrupoles(self, names=None):
        #self.log("Reading quadrupoles' strengths...")
        bdes = np.zeros(len(self.quadrupoles), dtype=float)

        for i, quadrupole_name in enumerate(self.quadrupoles):
            elements = self.lattice[quadrupole_name]
            if not isinstance(elements, list):
                elements = [elements]

            k1_values = []
            for element in elements:
                try:
                    strength = element.get_K1(self.Pref / self.Q)
                except Exception:
                    continue
                if isinstance(strength, (list, tuple, np.ndarray)):
                    if len(strength) > 0:
                        k1_values.append(float(strength[0]))
                else:
                    k1_values.append(float(strength))

            bdes[i] = k1_values[0] if k1_values else 0.0

        quadrupoles = {"names": self.quadrupoles, "bdes": bdes, "bact": bdes.copy(),
                       "xdes": np.array([self.qmag_xdes.get(name, 0.0) for name in self.quadrupoles], dtype=float),
                       "ydes": np.array([self.qmag_ydes.get(name, 0.0) for name in self.quadrupoles], dtype=float),
                       "rolldes": np.array([self.qmag_rolldes.get(name, 0.0) for name in self.quadrupoles], dtype=float)}

        if isinstance(names, str):
            names = [names]
        if names is not None:
            idx = np.array([i for i, s in enumerate(quadrupoles["names"]) if s in names])
            quadrupoles = {
                "names": np.array(quadrupoles["names"])[idx],
                "bdes": np.array(quadrupoles["bdes"])[idx],
                "bact": np.array(quadrupoles["bact"])[idx],
                "xdes": np.array(quadrupoles["xdes"])[idx],
                "ydes": np.array(quadrupoles["ydes"])[idx],
                "rolldes": np.array(quadrupoles["rolldes"])[idx],
            }

        return quadrupoles

    def apply_qmag_xyroll(self, names, x_um, y_um, roll_m, wait=True, max_attempts=5, attempt_timeout=30.0, settle_dt=0.5, tol_um=15.0):
        if isinstance(names, str):
            names = [names]

        nmag = len(names)

        def _expand(values):
            if np.isscalar(values):
                return np.full(nmag, float(values), dtype=float)
            arr = np.asarray(values, dtype=float).reshape(-1)
            if arr.size != nmag:
                raise ValueError(f"Length mismatch in apply_qmag_xyroll: expected {nmag}, got {arr.size}")
            return arr

        xs = _expand(x_um)
        ys = _expand(y_um)
        rolls = _expand(roll_m)

        for name, x_target, y_target, roll_target in zip(names, xs, ys, rolls):
            if name not in self.quadrupoles:
                raise ValueError(f"Quadrupole {name} not found in RFTrack interface.")

            elements = self.lattice[name]
            if not isinstance(elements, list):
                elements = [elements]

            x_offset = float(x_target) * 1e-6
            y_offset = float(y_target) * 1e-6
            roll_rad = float(roll_target)
            roll_mrad = roll_rad * 1e3

            for element in elements:
                element.set_offsets(x_offset, y_offset, 0.0, roll_mrad, 0.0, 0.0, "center")

            self.qmag_xdes[name] = float(x_target)
            self.qmag_ydes[name] = float(y_target)
            self.qmag_rolldes[name] = float(roll_target)

            print(
                f"Simulated mover {name}: "
                f"x={float(x_target):.3f} um, y={float(y_target):.3f} um, roll={float(roll_target):.6g} rad"
            )

        self.__track_bunch()

    def set_quadrupoles(self, names, values_range, track = True):
        if isinstance(names, str):
            names = [names]
        if not (isinstance(values_range, (list, tuple, np.ndarray))):
            values_range = [values_range]
        for quadrupole_name, value in zip(names, values_range):
            elements = self.lattice[quadrupole_name]
            if not isinstance(elements, (list)): elements = [elements]
            for element in elements:
                element.set_K1(self.Pref / self.Q,float(value))

        if track:
        # AS A TEST!
            self.__track_bunch()

    def set_correctors(self, names, corr_vals):
        if isinstance(names, str):
            names = [names]
        if not isinstance(corr_vals, (list, tuple, np.ndarray)):
            corr_vals = [corr_vals]
        for corr, val in zip(names, corr_vals):
            if corr[:2] == "ZH" or corr[:2] == "ZX":
                self.lattice[corr].set_strength(val / 10, 0.0)  # T*mm
            elif corr[:2] == "ZV":
                self.lattice[corr].set_strength(0.0, val / 10)  # T*mm
        self.__track_bunch()

    def vary_correctors(self, names, corr_vals):
        if isinstance(names, str):
            names = [names]
        if not isinstance(corr_vals, (list, tuple, np.ndarray)):
            corr_vals = [corr_vals]
        for corr, val in zip(names, corr_vals):
            if corr[:2] == "ZH" or corr[:2] == "ZX":
                self.lattice[corr].vary_strength(val / 10, 0.0)  # T*mm
            elif corr[:2] == "ZV":
                self.lattice[corr].vary_strength(0.0, val / 10)  # T*mm
        self.__track_bunch()


    def vary_quadrupoles(self, names, delta_values):
        if not isinstance(names, list):
            names = [names]
        if not isinstance(delta_values, (list, tuple, np.ndarray)):
            delta_values = [delta_values]
        for quadrupole_name, val in zip(names, delta_values):
            elements = self.lattice[quadrupole_name]
            if not isinstance(elements, list):
                elements = [elements]
            current_values=[]
            for element in elements:
                current=element.get_K1(self.Pref / self.Q)
                current=float(current[0]) if isinstance(current, (list, tuple,np.ndarray)) else float(current)
                current_values.append(current)
            if len(current_values)>1 and not np.allclose(current_values, current_values[0], rtol=0.0, atol=1e-12):
                self.log(f"Parts of quadrupole {quadrupole_name} have different values")
            target_value=(current_values[0] if len(current_values)>0 else 0.0) +float(val)
            for element in elements:
                element.set_K1(self.Pref / self.Q,target_value)

        self.__track_bunch()

    def __load_wake_data(self,path,trans_or_long,scale=1):
        '''
        The required input parameters to describe the wakefield are:
        Wt - A 1d vector with the transverse component of the wake function [V/pC/mm/m]
        Wl - A 1d vector with the longitudinal component of the wake function [V/pC/m]
        hz - the 1d mesh spacing of Wt and Wl [m]
        '''
        data=np.loadtxt(path)
        s = data[:,0]
        wake = data[:,1]
        trailing=s<=0
        s=s[trailing]
        wake=wake[trailing]

        index=np.argsort(s)
        s=s[index]
        wake=wake[index]

        hz=float(np.median(np.abs(np.diff(s)))) # m

        if trans_or_long=="transverse":
            Wt=wake.astype(float)
            Wl=np.zeros_like(Wt)
        elif trans_or_long=="longitudinal":
            Wl=wake.astype(float)
            Wt=np.zeros_like(Wl)
        return Wt,Wl,hz

    def _attach_wake_data_to_elements(self,wake_scale=1000,nsteps=20):
        wake_data_directory=os.path.join(os.path.dirname(__file__),"Ext_ATF2","WakeData")

        def _attach(name,WF):
            self.lattice[name].add_collective_effect(WF)
            self.lattice[name].set_cfx_nsteps(int(nsteps))

        cbpm_file = os.path.join(wake_data_directory, "atfCbpmWakeTBL03.dat")
        Wt, Wl, hz = self.__load_wake_data(cbpm_file, trans_or_long="transverse", scale=wake_scale)
        WF_cbpm = rft.Wakefield_1d(Wt, Wl, hz)

        attach_to_name = None
        for cand in ["L114E", "L114D", "L114F"]:
            if cand in self.sequence:
                attach_to_name = cand
                break

        if attach_to_name is None and "IPBPM" in self.sequence:
            i = self.sequence.index("IPBPM")
            for j in range(i - 1, -1, -1):
                if self.sequence[j].upper().startswith("L"):
                    attach_to_name = self.sequence[j]
                    break

        if attach_to_name is not None:
            _attach(attach_to_name, WF_cbpm)
        bellow_file = os.path.join(wake_data_directory, "atfBellowLongWakeTBL7.dat")
        if os.path.isfile(bellow_file):
            Wt, Wl, hz = self.__load_wake_data(bellow_file, trans_or_long="transverse", scale=wake_scale)
            WF_bellow = rft.Wakefield_1d(Wt, Wl, hz)

            drifts = [n for n in self.sequence if n.upper().startswith("L")]
            for n in drifts[::25]:
                try:
                    _attach(n, WF_bellow)
                except Exception:
                    pass

    def _get_elements_positions(self, names=None):
        if isinstance(names, str):
            names = [names]

        all_names = []
        all_s = []
        all_l = []
        s_pos = 0.0

        for element in self.lattice['*']:
            element_name = element.get_name()
            try:
                element_length = float(element.get_length())
            except Exception:
                element_length = 0.0

            if names is None or element_name in names:
                all_names.append(element_name)
                all_s.append(s_pos)
                all_l.append(element_length)

            s_pos += element_length

        return {
            "names": all_names,
            #"S": np.array(all_s, dtype=float),
            "L": np.array(all_l, dtype=float),
        }

    def align_everything(self):
        self.lattice.align_elements()
        self.__track_bunch()

    def misalign_quadrupoles(self, sigma_x=0.100, sigma_y=0.100):
        self.lattice.scatter_elements('quadrupole', sigma_x, sigma_y, 0, 0, 0, 0, 'center')
        self.__track_bunch()

    def misalign_bpms(self, sigma_x=0.100, sigma_y=0.100):
        self.lattice.scatter_elements('bpm', sigma_x, sigma_y, 0, 0, 0, 0, 'center')
        self.__track_bunch()

    def _build_bunch_from_guesses(self, emit_x, emit_y, beta_x0, beta_y0, alpha_x0, alpha_y0):
        T = rft.Bunch6d_twiss()
        T.emitt_x = float(emit_x)  # mm.mrad normalised emittance
        T.emitt_y = float(emit_y)  # mm.mrad
        T.beta_x = float(beta_x0)  # m
        T.beta_y = float(beta_y0)  # m
        T.alpha_x = float(alpha_x0)
        T.alpha_y = float(alpha_y0)
        T.sigma_t = 8  # mm/c
        T.sigma_pt = 0.8  # permille
        bunch = rft.Bunch6d_QR(rft.electronmass, self.population, self.Q, self.Pref, T, self.nparticles)
        return bunch

    def _read_tracked_bunch_screen_sigmas(self, screens):
        screen_data = self.get_screens(names = screens)
        name_to_index = {name: i for i, name in enumerate(screen_data["names"])}
        sigx = np.full(len(screens), np.nan, dtype=float)
        sigy = np.full(len(screens), np.nan, dtype=float)
        for i, screen in enumerate(screens):
            idx = name_to_index.get(screen)
            if idx is None:
                continue
            sigx[i] = float(screen_data["sigx"][idx])
            sigy[i] = float(screen_data["sigy"][idx])
        return sigx, sigy

    def predict_emittance_scan_response(self, quad_name, screens, K1_values, emit_x, emit_y, beta_x0, beta_y0, alpha_x0, alpha_y0, stop_checker = None, reference_screen = None):
        screens = list(screens)
        K1_values = np.asarray(K1_values, dtype=float)
        screens = list(screens)
        if len(screens) == 0:
            raise RuntimeError("No screens provided for emittance scan prediction.")
        if reference_screen is None:
            reference_screen = screens[0]
        if reference_screen not in screens:
            raise RuntimeError("reference_screen must be one of the selected screens.")

        start_element_name = str(quad_name)
        end_element_name = str(screens[-1])

        if quad_name not in self.quadrupoles:
            raise ValueError(f"Quadrupole {quad_name} not found in quadrupoles")
        if len(screens) == 0:
            raise ValueError("No screens")

        original_quads = self.get_quadrupoles(names=[quad_name])
        if len(original_quads["bdes"]) == 0:
            raise RuntimeError(f"Could not find original strength for quad {quad_name}")
        K1_original = float(original_quads["bdes"][0])

        B0_original = self.B0
        output_x = np.full((len(K1_values),len(screens)), np.nan, dtype=float)
        output_y = np.full((len(K1_values),len(screens)), np.nan, dtype=float)

        try:
            for k,K1 in enumerate(K1_values):
                if callable(stop_checker) and stop_checker():
                    raise RuntimeError("__OPTIMIZATION_STOP__")
                self.set_quadrupoles([quad_name], [float(K1)], track = False)

                # start_element = self.lattice[start_element_name]
                # if isinstance(start_element, list):
                #     start_element = start_element[0]
                # for si, screen_name in enumerate(screens):
                #     screen_elem = self.lattice[screen_name]
                #     if isinstance(screen_elem, list):
                #         screen_elem = screen_elem[-1]
                #     temp_bunch = self._build_bunch_from_guesses(
                #         emit_x=float(emit_x), emit_y=float(emit_y),
                #         beta_x0=float(beta_x0), beta_y0=float(beta_y0),
                #         alpha_x0=float(alpha_x0), alpha_y0=float(alpha_y0),
                #     )
                #
                #     tracked = self.lattice.track(temp_bunch, start_element, screen_elem)
                #     m = tracked.get_phase_space('%x %y')
                #     if m is not None and len(m) > 0:
                #         output_x[k, si] = float(np.std(m[:, 0]))
                #         output_y[k, si] = float(np.std(m[:, 1]))


## FOR A TEST
                start_element = self.lattice[start_element_name]
                if isinstance(start_element, list):
                    start_element = start_element[0]

                end_element = self.lattice[end_element_name]
                if isinstance(end_element, list):
                    end_element = end_element[-1]

                temp_bunch = self._build_bunch_from_guesses(
                    emit_x=float(emit_x), emit_y=float(emit_y),
                    beta_x0=float(beta_x0), beta_y0=float(beta_y0),
                    alpha_x0=float(alpha_x0), alpha_y0=float(alpha_y0),
                )

                tracked_to_last_screen = self.lattice.track(temp_bunch, start_element, end_element)
                for si, screen_name in enumerate(screens):
                    screen_elem = self.lattice[screen_name]
                    if isinstance(screen_elem, list):
                        screen_elem = screen_elem[-1]
                    bunch_at_screen = None
                    try:
                        bunch_at_screen = screen_elem.get_bunch()
                    except Exception:
                        bunch_at_screen = None
                    if bunch_at_screen is None and str(screen_name) == end_element_name:
                        bunch_at_screen = tracked_to_last_screen
                    if bunch_at_screen is None:
                        continue
                    m = bunch_at_screen.get_phase_space('%x %y')
                    if m is not None and len(m) > 0:
                        output_x[k, si] = float(np.std(m[:, 0]))
                        output_y[k, si] = float(np.std(m[:, 1]))
## FOR A TEST

        finally:
            self.set_quadrupoles([quad_name], [float(K1_original)], track=False)
            self.B0 = B0_original
            self.__track_bunch()

        return output_x, output_y

    def get_twiss_at_screen(self, name): # for printing emittance after bba using rft interface, can be deleted later
        if name not in self.screens:
            raise ValueError(f"Screen {name} not found")

        screen = self.lattice[name]
        bunch = screen.get_bunch()
        if bunch is None:
            raise RuntimeError(f"Screen {name} has no bunch. Track the beam first.")

        info = bunch.get_info()
        return {
            "name": name,
            "beta_x": float(info.beta_x),
            "alpha_x": float(info.alpha_x),
            "beta_y": float(info.beta_y),
            "alpha_y": float(info.alpha_y),
            "emitt_x": float(info.emitt_x),
            "emitt_y": float(info.emitt_y),
            "sigma_x": float(info.sigma_x),
            "sigma_y": float(info.sigma_y),
            "S": float(info.S),
        }

    def get_sextupoles(self, names = None):
        #self.log("Reading sextupoles' strengths...")
        bdes = np.zeros(len(self.sextupoles), dtype=float)

        for i, sextupole_name in enumerate(self.sextupoles):
            elements = self.lattice[sextupole_name]
            if not isinstance(elements, list):
                elements = [elements]

            k2_values = []
            for element in elements:
                try:
                    strength = element.get_strengths()
                except Exception:
                    continue
                strengths = np.asarray(strength, dtype = complex ).ravel()
                if strengths.size >= 3:
                    k2_values.append(float(np.real(strengths[2])))
                else:
                    k2_values.append(0.0)
            if len(k2_values) > 1 and not np.allclose(k2_values, k2_values[0], rtol = 0.0, atol = 1e-12):
                self.log(f"Parts of sextupole {sextupole_name} are not consistent.")

            bdes[i] = k2_values[0] if k2_values else 0.0

        sextupoles = {"names": self.sextupoles, "bdes": bdes, "bact": bdes.copy()}

        if isinstance(names, str):
            names = [names]
        if names is not None:
            idx = np.array([i for i, s in enumerate(sextupoles["names"]) if s in names])
            sextupoles = {
                "names": np.array(sextupoles["names"])[idx],
                "bdes": np.array(sextupoles["bdes"])[idx],
                "bact": np.array(sextupoles["bact"])[idx],
            }
        return sextupoles

    def set_sextupoles(self, names, values_range):
        if isinstance(names, str):
            names = [names]
        if not (isinstance(values_range, (list, tuple, np.ndarray))):
            values_range = [values_range]
        for sextupole_name, value in zip(names, values_range):
            elements = self.lattice[sextupole_name]
            if not isinstance(elements, (list)): elements = [elements]
            for element in elements:
                try:
                    strengths = element.get_strengths()
                except Exception:
                    continue
                strengths = np.asarray(strengths, dtype = complex).ravel()

                if strengths.size < 3:
                    padded = np.zeros(3, dtype = complex)
                    padded[:strengths.size] = strengths
                    strengths = padded
                strengths[2] = complex(float(value), 0.0)
                element.set_strengths(strengths)
        self.__track_bunch()

    def get_phase_space_transport_to_screens(self, reference_screen=None, screens=None):
        if screens is None:
            screens = list(self.screens)
        if isinstance(screens, str):
            screens = [screens]
        screens = list(screens)

        if reference_screen is None:
            reference_screen = screens[0]

        original_bunch = self.B0

        result = {
            "reference_screen": str(reference_screen),
            "screens": [str(s) for s in screens],
            "x": {"R11": [], "R12": [], "R21": [], "R22": []},
            "y": {"R33": [], "R34": [], "R43": [], "R44": []},
        }

        try:
            start_element = self.lattice[reference_screen]
            if isinstance(start_element, list):
                start_element = start_element[-1]

            end_element = self.lattice[screens[-1]]
            if isinstance(end_element, list):
                end_element = end_element[-1]

            bx = np.array([
                [1.0, 0.0, 0.0, 0.0, 0.0, self.Pref],
                [0.0, 1.0, 0.0, 0.0, 0.0, self.Pref],
            ], dtype=float)

            bunch_x = rft.Bunch6d(rft.electronmass, 0.0, self.Q, bx)
            tracked_x = self.lattice.track(bunch_x, start_element, end_element)

            for screen in screens:
                screen_element = self.lattice[screen]
                if isinstance(screen_element, list):
                    screen_element = screen_element[-1]

                b = screen_element.get_bunch()
                if b is None and str(screen) == str(screens[-1]):
                    b = tracked_x

                ps = np.asarray(b.get_phase_space("%x %xp"), dtype=float)

                result["x"]["R11"].append(float(ps[0, 0]))
                result["x"]["R12"].append(float(ps[1, 0]))
                result["x"]["R21"].append(float(ps[0, 1]))
                result["x"]["R22"].append(float(ps[1, 1]))

            by = np.array([
                [0.0, 0.0, 1.0, 0.0, 0.0, self.Pref],
                [0.0, 0.0, 0.0, 1.0, 0.0, self.Pref],
            ], dtype=float)

            bunch_y = rft.Bunch6d(rft.electronmass, 0.0, self.Q, by)
            tracked_y = self.lattice.track(bunch_y, start_element, end_element)

            for screen in screens:
                screen_element = self.lattice[screen]
                if isinstance(screen_element, list):
                    screen_element = screen_element[-1]

                b = screen_element.get_bunch()
                if b is None and str(screen) == str(screens[-1]):
                    b = tracked_y

                ps = np.asarray(b.get_phase_space("%y %yp"), dtype=float)

                # [
                #     [x_of_particle_0, xp_of_particle_0],
                #     [x_of_particle_1, xp_of_particle_1],
                # ]

                result["y"]["R33"].append(float(ps[0, 0]))
                result["y"]["R34"].append(float(ps[1, 0]))
                result["y"]["R43"].append(float(ps[0, 1]))
                result["y"]["R44"].append(float(ps[1, 1]))

        finally:
            self.B0 = original_bunch
            self.__track_bunch()

        return result


    '''
    SATO-SAN'S METHODS:
    '''

    # ----------------------------
    # Knobs (linear / nonlinear)
    # ----------------------------
    def get_linear_knob_names(self):
        return list(self.knobs.linear_matrix.keys())


    def get_nonlinear_knob_names(self):
        return list(self.knobs.nonlinear_matrix.keys())


    def set_linear_knob(self, knob_name: str, value: float):
        self.knobs.set_linear_knob(knob_name, float(value))
        self.knobs.apply()
        self._needs_tracking = True


    def set_nonlinear_knob(self, knob_name: str, value: float):
        self.knobs.set_nonlinear_knob(knob_name, float(value))
        self.knobs.apply()
        self._needs_tracking = True


    def reset_knobs(self):
        self.knobs.reset_knobs()
        self._needs_tracking = True

    def get_ipbsm_state(self):
        self.__track_bunch()
        B1_IP = self.lattice['IP'].get_bunch()

        ps = B1_IP.get_phase_space('%x %xp %y %yp %dt %P')
        y_positions = ps[:, 2] * 1e-3  # mm→m

        degMode, ModIPBSM, SigIPBSM = ipbsm_calc.FuncIPBSMbeamsize(y_positions)

        return {
            "modulation": ModIPBSM,
            "angle_deg": degMode,
            "sigma_y_m": SigIPBSM,
        }

    def get_quadrupole_movers_names(self):
        if hasattr(self, "Qmagnames") and self.Qmagnames:
            return [str(name) for name in self.Qmagnames]
        return [str(name) for name in self.quadrupoles]

    def apply_sum_knob(self, I):
        """
        SUM knob: QS1X +k, QS2X +k
        """
        print(f"Applying SUM knob: k = {I}")
        self.apply_qmag_current("QS1X", I)
        self.apply_qmag_current("QS2X", I)

        # self.__track_bunch()
        self._needs_tracking = True

    def apply_random_misalignment(
            self,
            seed: int,
            sigma_dx_um: float,
            sigma_dy_um: float,
            sigma_dtheta_urad: float,
            sigma_dk_rel: float, ):

        print(
            f"Applying random misalignment (custom): seed={seed}, "
            f"sigma_dx={sigma_dx_um}um, sigma_dy={sigma_dy_um}um, "
            f"sigma_dtheta={sigma_dtheta_urad}urad, sigma_dk_rel={sigma_dk_rel}"
        )

        rng = np.random.default_rng(seed)

        Qnames = self.Qmagnames

        for name in Qnames:
            dx = rng.normal(0.0, sigma_dx_um)
            dy = rng.normal(0.0, sigma_dy_um)
            dtheta = rng.normal(0.0, sigma_dtheta_urad)
            dk_rel = rng.normal(0.0, sigma_dk_rel)

            print(f"{name}: dx={dx:.1f}um  dy={dy:.1f}um  dθ={dtheta:.2f}urad  dk_rel={dk_rel:.3e}")

            self.apply_qmag_offsets(name, dx, dy, dtheta, add=False)
            elems = self.lattice[name]
            for elem in elems:
                k1l = elem.get_K1L(self.Pref)
                elem.set_K1L(self.Pref, k1l * (1 + dk_rel))

        self._needs_tracking = True

    def reset_lattice(self):
        self._build_lattice()

    def apply_qmag_current(self, name, dA):
        dk1l = self.kl_per_A[name] * dA
        print(f"Applying {name} current: dA = {dA}")
        elems = self.lattice[name]
        # 複数要素を同じだけ変える

        for elem in elems:
            k1l = elem.get_K1L(self.Pref)
            elem.set_K1L(self.Pref, k1l + dk1l / len(elems))
        # self.__track_bunch()
        self._needs_tracking = True


    def apply_qmag_offsets(self, name, dx, dy, dr, add=True):
        elems = self.lattice[name] + self.lattice[name + "MULT"]
        bpms = self.lattice["M" + name]
        if not isinstance(bpms, (list, tuple)):
            bpms = [bpms]

        for elem in elems:
            if add == True:
                x = elem.get_offsets()[0][0]  # mm
                y = elem.get_offsets()[0][1]  # mm
                z = elem.get_offsets()[0][2]  # mm
                r = elem.get_offsets()[0][3]  # rad
                elem.set_offsets(x * 1e-3 + dx * 1e-6, y * 1e-3 + dy * 1e-6, z * 1e-3, r + dr * 1e-6, 0, 0)
            else:
                elem.set_offsets(dx * 1e-6, dy * 1e-6, 0, dr * 1e-6, 0, 0)

        for bpm in bpms:
            if add == True:
                x = bpm.get_offsets()[0][0]  # mm
                y = bpm.get_offsets()[0][1]  # mm
                z = bpm.get_offsets()[0][2]  # mm
                bpm.set_offsets(x * 1e-3 + dx * 1e-6, y * 1e-3 + dy * 1e-6, z * 1e-3)
            else:
                bpm.set_offsets(dx * 1e-6, dy * 1e-6, 0)

    """
    def measure_dispersion(self):
        print("Measuring dispersion (RF-Track)...")

        # Nominal energy
        self.__setup_beam0()
        self.__track_bunch()
        bpms0 = self.get_bpms()
        x0 = np.mean(bpms0["x"], axis=0)
        y0 = np.mean(bpms0["y"], axis=0)

        # Reduced energy
        self.__setup_beam1()
        self.__track_bunch()
        bpms1 = self.get_bpms()
        x1 = np.mean(bpms1["x"], axis=0)
        y1 = np.mean(bpms1["y"], axis=0)

        # Restore nominal
        self.__setup_beam0()
        self.__track_bunch()

        delta = -0.02  # Pref -> 0.98 * Pref
        eta_x = (x1 - x0) / delta
        eta_y = (y1 - y0) / delta

        return {"eta_x": eta_x, "eta_y": eta_y}
    """

    def __ensure_tracked(self):
        if getattr(self, "_needs_tracking", False):
            self.__track_bunch()
            self._needs_tracking = False

    def _I_to_KL(self, name, I):
        if name not in self.kl_per_A:
            raise KeyError(f"kl_per_A is not defined for corrector '{name}'")
        return np.asarray(I, dtype=float) * self.kl_per_A[name]

    def _KL_to_I(self, name, kl):
        if name not in self.kl_per_A:
            raise KeyError(f"kl_per_A is not defined for corrector '{name}'")
        return np.asarray(kl, dtype=float) / self.kl_per_A[name]

    '''
    to be considered later:
    
        def _build_lattice(self):
        self.lattice = rft.Lattice(self.twiss_path)
        Scr = rft.Screen()
        self.lattice['IP'].replace_with(Scr)
        self.lattice.set_bpm_resolution(self.bpm_resolution)

        self.sequence = [e.get_name() for e in self.lattice["*"]]
        self.bpms = [e.get_name() for e in self.lattice.get_bpms()]
        self.corrs = [e.get_name() for e in self.lattice.get_correctors()]

        self.__setup_beam0()
        self.__track_bunch()
        
        
    def get_bpms(self):
        self.log("Reading bpms...")
        self.__ensure_tracked()

        nbpm = len(self.bpms)

        x = np.zeros((self.nsamples, nbpm))
        y = np.zeros_like(x)
        tmit = np.zeros_like(x)

        # s1 = np.array([self.lattice[bpm].get_S() for bpm in self.bpms])
        s = np.array([self.lattice[bpm].get_S() for bpm in self.bpms], dtype=float)

        for i in range(self.nsamples):
            for j, bpm in enumerate(self.bpms):
                b = self.lattice[bpm]
                reading = b.get_reading()
                x[i, j] = reading[0]
                y[i, j] = reading[1]
                tmit[i, j] = b.get_total_charge()

        return {
            "names": self.bpms,
            "x": x,
            "y": y,
            "tmit": tmit,
            "S": s,
        }
        
    def set_correctors(self, names, corr_vals):
        if isinstance(names, str):
            names = [names]
        if np.isscalar(corr_vals):
            corr_vals = [corr_vals] * len(names)
        elif not isinstance(corr_vals, (list, tuple, np.ndarray)):
            corr_vals = [corr_vals]
        if len(names) != len(corr_vals):
            self.log('Error: len(names) != len(corr_vals) in set_correctors(names, corr_vals)')
            return
        for corr, val in zip(names, corr_vals):
            if corr not in self.kl_per_A:
                self.log(f'Warning: missing kl_per_A for {corr}; skipping.')
                continue
            strength = float(val) * self.kl_per_A[corr] * 1000  # A -> T*mm
            if corr[:2] == "ZH" or corr[:2] == "ZX":
                self.lattice[corr].set_strength(strength, 0.0)
            elif corr[:2] == "ZV":
                self.lattice[corr].set_strength(0.0, strength)

        self.__track_bunch()
    
    
        def vary_correctors(self, names, corr_vals):
        if isinstance(names, str):
            names = [names]
        if np.isscalar(corr_vals):
            corr_vals = [corr_vals] * len(names)
        elif not isinstance(corr_vals, (list, tuple, np.ndarray)):
            corr_vals = [corr_vals]
        if len(names) != len(corr_vals):
            self.log('Error: len(names) != len(corr_vals) in vary_correctors(names, corr_vals)')
            return
        for corr, val in zip(names, corr_vals):
            if corr not in self.kl_per_A:
                self.log(f'Warning: missing kl_per_A for {corr}; skipping.')
                continue
            delta_strength = float(val) * self.kl_per_A[corr] * 1000  # A -> T*mm
            if corr[:2] == "ZH" or corr[:2] == "ZX":
                self.lattice[corr].vary_strength(delta_strength, 0.0)
            elif corr[:2] == "ZV":
                self.lattice[corr].vary_strength(0.0, delta_strength)
        self.__track_bunch()
        #self._needs_tracking = True 
    '''