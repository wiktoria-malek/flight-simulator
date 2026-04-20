import RF_Track as rft
import numpy as np
import time, os, re, copy
from Backend.LogConsole_BBA import LogConsole
from datetime import datetime
from Interfaces.AbstractMachineInterface import AbstractMachineInterface

class InterfaceATF2_Linac_RFTrack(AbstractMachineInterface):

    def get_name(self):
        return 'ATF2_Linac_RFT'

    def __init__(self, population=1e+10, jitter=0.0, bpm_resolution=0.0, nsamples=1, nparticles=1000):
        super().__init__()
        self.log = print
        self.twiss_path = os.path.join(os.path.dirname(__file__), 'Linac_ATF2', 'linacend.tws')
        self.madx_path = os.path.join(os.path.dirname(__file__), 'Linac_ATF2', 'End_linac.madx')
        self.Pref0 = 80
        self.Pref = self.Pref0
        self.nparticles = nparticles
        self.electronmass = rft.electronmass
        self.population = population
        self.jitter = jitter
        self.nsamples = nsamples
        self.Q = -1
        self.dfs_test_energy = 0.98
        self.wfs_test_charge = 0.90
        self.freq = 2855.9822615999997e+6 # Hz
        self.lattice = self._build_lattice()
        self.lattice.set_bpm_resolution(bpm_resolution)
        self.sequence = [e.get_name() for e in self.lattice['*']]
        self.bpms = [e.get_name() for e in self.lattice.get_bpms()]
        self.corrs = [e.get_name() for e in self.lattice.get_correctors()]
        self.quadrupoles = list(dict.fromkeys(e.get_name() for e in self.lattice.get_quadrupoles()))
        self.__setup_beam0()
        self.__track_bunch()
        self.sextupoles = self._get_element_names_from_twiss_types({"SEXTUPOLE"})
        self._saved_sextupoles_state = None

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
        gamma_rel = np.sqrt((self.Pref0 / self.electronmass) ** 2 + 1.0)
        beta_rel = np.sqrt(1.0 - 1.0 / gamma_rel ** 2)
        return gamma_rel, beta_rel

    def log_messages(self, console):
        self.log = console or print

    def __setup_beam0(self):
        T = rft.Bunch6d_twiss()
        T.emitt_x = 24.7e-4  # mm.mrad normalised emittance
        T.emitt_y = 24.7e-4  # mm.mrad
        T.beta_x = 0.451  # m
        T.beta_y = 2.236  # m
        T.alpha_x = -3.599
        T.alpha_y = -10.419
        T.sigma_t = 8  # mm/c
        T.sigma_pt = 0.8  # permille
        self.B0 = rft.Bunch6d_QR(rft.electronmass, self.population, self.Q, self.Pref, T, self.nparticles)

    def __setup_beam1(self):
        # Beam for DFS - Reduced energy
        Pref = self.dfs_test_energy * self.Pref0
        T = rft.Bunch6d_twiss()
        T.emitt_x = 24.7e-4  # mm.mrad normalised emittance
        T.emitt_y = 24.7e-4  # mm.mrad
        T.beta_x = 0.451  # m
        T.beta_y = 2.236  # m
        T.alpha_x = -3.599
        T.alpha_y = -10.419
        T.sigma_t = 8  # mm/c
        T.sigma_pt = 0.8  # permille
        Nparticles = 1000  # number of macroparticles
        self.B0 = rft.Bunch6d_QR(rft.electronmass, self.population, self.Q, Pref, T, self.nparticles)

    def __setup_beam2(self):
        # Beam for WFS - Reduced bunch charge
        population = self.wfs_test_charge * self.population
        T = rft.Bunch6d_twiss()
        T.emitt_x = 24.7e-4  # mm.mrad normalised emittance
        T.emitt_y = 24.7e-4  # mm.mrad
        T.beta_x = 0.451  # m
        T.beta_y = 2.236  # m
        T.alpha_x = -3.599
        T.alpha_y = -10.419
        T.sigma_t = 8  # mm/c
        T.sigma_pt = 0.8  # permille
        Nparticles = 1000  # number of macroparticles
        self.B0 = rft.Bunch6d_QR(rft.electronmass, population, self.Q, self.Pref, T, self.nparticles)

    def __track_bunch(self):
        I0 = self.B0.get_info()
        dx = self.jitter * I0.sigma_x
        dy = self.jitter * I0.sigma_y
        dz, dt, roll = 0.0, 0.0, 0.0
        pitch = self.jitter * I0.sigma_py
        yaw = self.jitter * I0.sigma_px
        B0_offset = self.B0.displaced(dx, dy, dz, dt, roll, pitch, yaw)
        self.B1 = self.lattice.track(B0_offset)
        I = self.B1.get_info()

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

    def get_elements_position(self, names):
        return [index for index, string in enumerate(self.sequence) if string in names]

    def _set_name(self, element, name):
        try:
            element.set_name(name)
        except Exception:
            pass
        return element

    def _make_tw(self, name):
        a0 = 25.5e6 # V/m, principal Fourier coefficient
        ph_adv = 2 * np.pi / 3  # radian, phase advance per cell
        n_cells = -85  # number of cells, negative sign indicates a start from the beginning of the cell
        TW = rft.TW_Structure(a0, 0, self.freq, ph_adv, n_cells)  # 0=el primer elemento del armonico
        phid = -91.67 + 90  # LAG -.2546388888888886 [2*pi]
        TW.set_phid(phid)
        self._set_name(TW, name)
        return TW

    def _make_twb1(self, name):
        BCph_adv = 2.0908741;
        BCBn_cells = -85;
        TWB1 = rft.TW_Structure(0, 0, self.freq, BCph_adv, BCBn_cells)  # TW Bunching
        BCphid = -90 + 90
        TWB1.set_phid(BCphid)
        self._set_name(TWB1, name)
        return TWB1

    def _make_twb2(self, name):
        BC2ph_adv = 2.0958035;
        BC2Bn_cells = -85;
        TWB2 = rft.TW_Structure(0, 0, self.freq, BC2ph_adv, BC2Bn_cells)  # TW Bunching 2
        BCphid = -90 + 90
        TWB2.set_phid(BCphid)
        self._set_name(TWB2, name)
        return TWB2

    def _append_drift(self, lattice, length, name = None):
        if length <= 1e-12:
            return
        Drift = rft.Drift(float(length))
        if name is not None:
            self._set_name(Drift, name)
        lattice.append(Drift)

    def _append_main_linac(self, lattice):
        charge = -1
        P_Q = self.Pref0 / charge
        pos_actual = 0.0

        quad_specifics = [
            # name, LQ, pos_quad, strength
            ('QA1L', 0.132, 1.356, 1.1835109401030304),
            ('QA2L', 0.182, 1.703, -9.264115425347802),
            ('QA3L', 0.182, 2.128, 7.601904693021979),
            ('QA4L', 0.182, 4.774, -8.309547432909891),
            ('QA5L', 0.132, 5.171, 10.368563413319697),
            ('QD1L', 0.132, 9.548499999999997, -6.394111798396212),
            ('QF1L', 0.182, 9.948499999999996, 8.468997394013186),
            ('QD2L', 0.132, 10.348499999999994, -6.415397177518939),
            ('QF2L', 0.125, 14.143499999999994, 4.6362775786152),
            ('QD3L', 0.125, 14.894999999999994, -4.7315774972976),
            ('QF3L', 0.125, 18.986999999999995, 5.8107864654864),
            ('QD4L', 0.125, 19.73699999999999, -5.1676165334704),
            ('QF4L', 0.125, 23.84099999999999, 7.6235715827536),
            ('QD5L', 0.125, 24.491999999999987, -6.7358412875152),
            ('QF5L', 0.125, 28.486499999999985, 7.6898162668192),
            ('QD6L', 0.125, 29.13649999999998, -6.8687757100048),
            ('QF6L', 0.125, 36.74699999999999, 4.4820119116136),
            ('QD7L', 0.125, 37.397, -4.4944090948816),
            ('QS5L', 0.125, 45.298760000000016, 0.9884761807816),
            ('QS6L', 0.125, 53.137260000000026, -1.1188273572312),
            ('QS7L', 0.125, 60.66226000000003, 0.8013307329232),
            ('QS8L', 0.125, 71.47405000000003, -0.522816766032),
            ('QM1L', 0.175, 78.59605000000002, 1.4909714285714286),
            ('QM2L', 0.325, 79.61655000000002, -1.894584615384615),
            ('QM3L', 0.175, 81.59355000000002, 3.646114285714286),
        ]

        cavity_specifics = [
            ('CA1L', 7.3835, 'TW'),
            ('CA2L', 12.142714999999995, 'TW'),
            ('CA3L', 17.006999999999994, 'TW'),
            ('CA4L', 21.87099999999999, 'TW'),
            ('CB1L', 26.520499999999988, 'TWB1'),
            ('CA5L', 31.180499999999984, 'TW'),
            ('CA6L', 34.78399999999999, 'TW'),
            ('CA7L', 39.43000000000001, 'TW'),
            ('CA8L', 43.03397000000001, 'TW'),
            ('CA9L', 47.26726000000002, 'TW'),
            ('CA10L', 50.872260000000026, 'TW'),
            ('CA11L', 55.10826000000003, 'TW'),
            ('CA12L', 58.397760000000034, 'TW'),
            ('CB2L', 62.63276000000003, 'TWB2'),
            ('CA13L', 65.91976000000003, 'TW'),
            ('CA14L', 69.20926000000003, 'TW'),
            ('CA15L', 73.44305000000003, 'TW'),
            ('CA16L', 76.73305000000002, 'TW'),
        ]

        actions = []

        for name, length, pos, k1 in quad_specifics:
            actions.append(
                {
                    'element_type': 'quadrupole',
                    'position': pos,
                    'name': name,
                    'length': length,
                    'k1': k1,
                }
            )
        tw = self._make_tw('tw')
        twb1 = self._make_twb1('twb1')
        twb2 = self._make_twb2('twb2')

        cavity_length = {
            'TW' : tw.get_length(),
            'TWB1' : twb1.get_length(),
            'TWB2' : twb2.get_length(),
        }

        for name, pos, ctype in cavity_specifics:
            actions.append(
                {
                    'element_type': 'cavity',
                    'position': pos,
                    'name': name,
                    'ctype': ctype,
                    'length': cavity_length[ctype],
                }
            )

        actions.sort(key = lambda item: item['position'])

        drift_id = 1

        for item in actions:
            drift = item['position'] - item['length'] / 2.0 - pos_actual
            self._append_drift(lattice, drift, f'DRIFT_LINAC_{drift_id:03d}')
            drift_id += 1

            if item['element_type'] == 'quadrupole':
                quadrupole = rft.Quadrupole(item['length'], P_Q, item['k1'])
                self._set_name(quadrupole, item['name'])
                lattice.append(quadrupole)
            else:
                if item['ctype'] == 'TW':
                    cavity = self._make_tw(item['name'])
                elif item['ctype'] == 'TWB1':
                    cavity = self._make_twb1(item['name'])
                else:
                    cavity = self._make_twb2(item['name'])
                lattice.append(cavity)
                try:
                    lattice.unset_t0()
                except Exception:
                    pass

            pos_actual = item['position'] + item['length'] / 2.0
        pos_IPZL = 83.40465000000002
        self._append_drift(lattice, pos_IPZL - pos_actual, 'DRIFT_TO_IPZL')
        ipzl = rft.Drift(0.0)
        self._set_name(ipzl, 'IPZL')
        lattice.append(ipzl)

    def _get_endlinac_twiss(self):
        try:
            from cpymad.madx import Madx
            madx = Madx(stdout=True)
            madx.call(self.madx_path);
        except Exception as e:
            self.log("Could not get endlinac twiss data")

    def _append_endlinac(self, lattice):
        self._get_endlinac_twiss()
        if not os.path.isfile(self.twiss_path):
            raise FileNotFoundError("Could not find endlinac twiss file")
        lattice.append(rft.Lattice(self.twiss_path))

    def _adjust_strength_with_autophase(self, lattice):
        mass = rft.electronmass
        charge = self.Q
        population = self.population
        Pi = self.Pref0
        P_Q = Pi / charge
        P0 = rft.Bunch6d(mass, population, charge, np.array([0, 0, 0, 0, 0, Pi]).T)

        TWL = rft.Lattice()
        TWL.append(self._make_tw('AUTOPHASE_TW'))
        try:
            TWL.unset_t0()
        except Exception:
            pass

        try:
            Pmax = TWL.autophase(P0)
            p_gain = Pmax - Pi
        except Exception as e:
            self.log(f"Autophase failed, keeping nominal main linac quadrupoles: {e}")
            return

        groups = [
            ['QA1L', 'QA2L', 'QA3L', 'QA4L', 'QA5L'],
            ['QD1L', 'QF1L', 'QD2L'],
            ['QF2L', 'QD3L'],
            ['QF3L', 'QD4L'],
            ['QF4L', 'QD5L', 'QF5L', 'QD6L'],
            ['QF6L', 'QD7L'],
            ['QS5L'],
            ['QS6L'],
            ['QS7L'],
            ['QS8L'],
            ['QM1L', 'QM2L', 'QM3L'],
        ]
        increments_after_group = [1, 1, 1, 1, 2, 2, 2, 2, 2, 2, 0]

        p = Pi
        for names, inc in zip(groups, increments_after_group):
            for name in names:
                try:
                    element = lattice[name]
                    current_K1 = element.get_K1(P_Q)
                    if isinstance(current_K1, (list, tuple, np.ndarray)):
                        current_K1 = float(current_K1[0])
                    else:
                        current_K1 = float(current_K1)
                    element.set_K1(p / charge, current_K1)
                except Exception as e:
                    self.log(f"Could not set K1 for {name}: {e}")
            p += inc * p_gain

    def _build_lattice(self):
        lattice = rft.Lattice()
        self._append_main_linac(lattice)
        self._append_endlinac(lattice)
        self._adjust_strength_with_autophase(lattice)
        return lattice

    def get_target_dispersion(self, names=None): # for DR too
        if names is None:
            names = self.get_bpms()["names"]
        twiss_path = os.path.join(os.path.dirname(__file__), 'Linac_ATF2', 'linacend.tws')
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
        self.log("Reading ict's...")
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
        self.log("Reading correctors' strengths...")
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
        self.log('Reading bpms...')
        x = np.zeros((self.nsamples, len(self.bpms)))
        y = np.zeros(x.shape)
        tmit = np.zeros(x.shape)

        for i in range(self.nsamples):
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
        self.log('Reading screens...')
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
                sum_list.append(0)
                images.append(np.zeros((1, 1)))
                hedges_all.append(np.array([0, hpixel]))
                vedges_all.append(np.array([0, vpixel]))
                continue

            sumw = len(m[:, 0])  # number of particles in the screen; intensity
            xb_list.append(np.mean(m[:, 0]))  # mean x of particles
            yb_list.append(np.mean(m[:, 1]))  # mean y of particles
            sigx_list.append(np.std(m[:, 0]))  # RMS x beam size
            sigy_list.append(np.std(m[:, 1]))  # RMS y beam size
            sum_list.append(sumw)

            nx = int(np.ceil(np.ptp(m[:, 0]) / hpixel)) if np.ptp(
                m[:, 0]) > 0 else 1  # ceil rounds up, so it can take the whole range
            ny = int(np.ceil(np.ptp(m[:, 1]) / vpixel)) if np.ptp(m[:, 1]) > 0 else 1
            nx = int(np.clip(nx, 10, 400))
            ny = int(np.clip(ny, 10, 400))
            image, hedges, vedges = np.histogram2d(m[:, 0], m[:, 1], bins=(nx,
                                                                           ny))  # divides x axis into nx bins, y axis into ny bins and calculates how many particles are in each rectangle
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
                   "sum": np.array(sum_list, dtype=float),
                   "hedges": hedges_all,
                   "vedges": vedges_all,
                   "images": images,
                   "S": np.array(s_list, dtype=float),}
        return screens

    def get_quadrupoles(self, names=None):
        self.log("Reading quadrupoles' strengths...")
        bdes = np.zeros(len(self.quadrupoles), dtype=float)

        for i, quadrupole_name in enumerate(self.quadrupoles):
            elements = self.lattice[quadrupole_name]
            if not isinstance(elements, list):
                elements = [elements]

            k1_values = []
            for element in elements:
                try:
                    strength = element.get_K1(self.Pref0 / self.Q)
                except Exception:
                    continue
                if isinstance(strength, (list, tuple, np.ndarray)):
                    if len(strength) > 0:
                        k1_values.append(float(strength[0]))
                else:
                    k1_values.append(float(strength))

            bdes[i] = k1_values[0] if k1_values else 0.0

        quadrupoles = {"names": self.quadrupoles, "bdes": bdes, "bact": bdes.copy()}

        if isinstance(names, str):
            names = [names]
        if names is not None:
            idx = np.array([i for i, s in enumerate(quadrupoles["names"]) if s in names])
            quadrupoles = {
                "names": np.array(quadrupoles["names"])[idx],
                "bdes": np.array(quadrupoles["bdes"])[idx],
                "bact": np.array(quadrupoles["bact"])[idx],
            }

        return quadrupoles

    def set_quadrupoles(self, names, values_range):
        if isinstance(names, str):
            names = [names]
        if not (isinstance(values_range, (list, tuple, np.ndarray))):
            values_range = [values_range]
        for quadrupole_name, value in zip(names, values_range):
            elements = self.lattice[quadrupole_name]
            if not isinstance(elements, (list)): elements = [elements]
            for element in elements:
                element.set_K1(self.Pref0 / self.Q,float(value))
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
                current=element.get_K1(self.Pref0 / self.Q)
                current=float(current[0]) if isinstance(current, (list, tuple,np.ndarray)) else float(current)
                current_values.append(current)
            if len(current_values)>1 and not np.allclose(current_values, current_values[0], rtol=0.0, atol=1e-12):
                self.log(f"Parts of quadrupole {quadrupole_name} have different values")
            target_value=(current_values[0] if len(current_values)>0 else 0.0) +float(val)
            for element in elements:
                element.set_K1(self.Pref0 / self.Q,target_value)

        self.__track_bunch()

    def _get_optics_from_twiss_file(self,names=None):
        with open(self.twiss_path, "r") as file:
            lines = [line.strip() for line in file if line.strip()]

        star_symbol = next(i for i, line in enumerate(lines) if line.startswith("*"))
        dollar_sign = next(i for i, line in enumerate(lines) if line.startswith("$") and i > star_symbol)
        columns = lines[star_symbol].lstrip("*").split()

        cols=["NAME","S","BETX","ALFX","BETY","ALFY","MUX","MUY","L"]
        index={}
        for col in cols:
            try:
                index[col]=columns.index(col)
            except ValueError:
                raise RuntimeError(f"Column {col} not found in twiss file")
        result={k: [] for k in cols}

        duplicated={}
        for line in lines[dollar_sign + 1:]:
            data = line.split()
            if len(data) <= max(index.values()):  # if a line has less column than needed, it is omitted
                continue
            name = data[index["NAME"]].strip('"')
            result["NAME"].append(name)

            if name not in duplicated:
                duplicated[name]={col:[] for col in cols[1:]}
            for col in cols[1:]:
                try:
                    duplicated[name][col].append(float(data[index[col]]))
                except ValueError:
                    duplicated[name][col].append(float("nan"))
        result_names=list(duplicated.keys())
        result={col:[] for col in cols[1:]}

        for name in result_names:
            vals=duplicated[name]
            result["S"].append(vals["S"][0])
            result["BETX"].append(vals["BETX"][0])
            result["ALFX"].append(vals["ALFX"][0])
            result["MUX"].append(vals["MUX"][0])
            result["L"].append(sum(vals["L"]))
            result["BETY"].append(vals["BETY"][0])
            result["ALFY"].append(vals["ALFY"][0])
            result["MUY"].append(vals["MUY"][0])
        return {
            "names":result_names,
            "S": np.array(result["S"]),
            "betx": np.array(result["BETX"]),
            "alfx": np.array(result["ALFX"]),
            "bety": np.array(result["BETY"]),
            "alfy": np.array(result["ALFY"]),
            "mux": np.array(result["MUX"]),
            "muy": np.array(result["MUY"]),
            "L": np.array(result["L"]),
        }

    def get_twiss_at_element(self,name):
        optics=self._get_optics_from_twiss_file()
        names=list(optics["names"])
        if name not in names:
            raise ValueError(f"Element {name} not found in twiss file")
        i=names.index(name)
        return {
            "name": names[i],
            "S": float(optics["S"][i]),
            "betx": float(optics["betx"][i]),
            "alfx": float(optics["alfx"][i]),
            "bety": float(optics["bety"][i]),
            "alfy": float(optics["alfy"][i]),
        }

    def align_everything(self):
        self.lattice.align_elements()
        self.__track_bunch()

    def misalign_quadrupoles(self, sigma_x=0.02, sigma_y=0.02):
        self.lattice.scatter_elements('quadrupole', sigma_x, sigma_y, 0, 0, 0, 0, 'center')
        self.__track_bunch()

    def misalign_bpms(self, sigma_x=0.100, sigma_y=0.100):
        self.lattice.scatter_elements('bpm', sigma_x, sigma_y, 0, 0, 0, 0, 'center')
        self.__track_bunch()
    def get_sextupoles(self, names = None):
        self.log("Reading sextupoles' strengths...")
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