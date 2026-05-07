import RF_Track as rft
import numpy as np
import time, os, re
from Backend.LogConsole import LogConsole
from datetime import datetime
from Interfaces.AbstractMachineInterface import AbstractMachineInterface

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

    def __init__(self, population=2e10, jitter=0.0, bpm_resolution=0.0, nsamples=1, nparticles=1000):
        super().__init__()
        self.log = print
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
        self.__setup_beam0()
        self.__track_bunch()
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
        dx = self.jitter * I0.sigma_x
        dy = self.jitter * I0.sigma_y
        dz, dt, roll = 0.0, 0.0, 0.0
        pitch = self.jitter * I0.sigma_py
        yaw = self.jitter * I0.sigma_px
        B0_offset = self.B0.displaced(dx, dy, dz, dt, roll, pitch, yaw)
        B1=self.lattice.track(B0_offset)
        I = B0_offset.get_info()

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
            "S": np.array(all_s, dtype=float),
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