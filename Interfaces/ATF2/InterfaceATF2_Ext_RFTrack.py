import RF_Track as rft
import numpy as np
import time, os
from LogConsole_BBA import LogConsole
from datetime import datetime

class InterfaceATF2_Ext_RFTrack():

    def get_name(self):
        return 'ATF2_Ext_RFT'

    def __init__(self, population=2e10, jitter=0.0, bpm_resolution=0.0, nsamples=1, nparticles=1000):
        super().__init__()
        self.log = print
        twiss_path = os.path.join(os.path.dirname(__file__), 'Ext_ATF2', 'ATF2_EXT_FF_v5.2.twiss')
        self.lattice = rft.Lattice(twiss_path)
        self.lattice.set_bpm_resolution(bpm_resolution)
        for s in self.lattice['*OTR*']:
            screen = rft.Screen()
            screen.set_name(s.get_name())
            s.replace_with(screen)
        self.sequence = [e.get_name() for e in self.lattice['*']]
        self._attach_wake_data_to_elements(wake_scale=1000,nsteps=20)
        self.bpms = [e.get_name() for e in self.lattice.get_bpms()]
        self.corrs = [e.get_name() for e in self.lattice.get_correctors()]
        self.screens = [e.get_name() for e in self.lattice.get_screens()]
        self.quadrupoles = [e.get_name() for e in self.lattice.get_quadrupoles()]
        self.Pref = 1.2999999e3  # 1.3 GeV/c
        self.nparticles = nparticles
        self.population = population
        self.jitter = jitter
        self.nsamples = nsamples
        self.Q = -1
        self.dfs_test_energy = 0.98
        self.wfs_test_charge = 0.90
        self.__setup_beam0()
        self.__track_bunch()

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
        I = B1.get_info()
        self.log("Emittance after tracking:")
        self.log(f"εx = {I.emitt_x}[mm.rad]")
        self.log(f"εy = {I.emitt_y}[mm.rad]")
        self.log(f"εz = {I.emitt_z}[mm.permille]")

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

    def get_bpms_names(self):
        return self.bpms

    def get_screens_names(self):
        return self.screens

    def get_correctors_names(self):
        return self.corrs

    def get_quadrupoles_names(self):
        return self.quadrupoles

    def get_hcorrectors_names(self):
        return [string for string in self.corrs if
                (string.lower().startswith('zh')) or (string.lower().startswith('zx'))]

    def get_vcorrectors_names(self):
        return [string for string in self.corrs if string.lower().startswith('zv')]

    def get_elements_position(self, names):
        return [index for index, string in enumerate(self.sequence) if string in names]

    def get_target_dispersion(self, names=None):
        if names is None:
            names = self.get_bpms_names()
        twiss_path = os.path.join(os.path.dirname(__file__), 'Ext_ATF2', 'ATF2_EXT_FF_v5.2.twiss')
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

    def get_icts(self):
        self.log("Reading ict's...")
        charge = [bpm.get_total_charge() for bpm in self.lattice.get_bpms()]
        icts = {
            "names": self.bpms,
            "charge": charge
        }
        return icts

    def get_correctors(self):
        self.log("Reading correctors' strengths...")
        bdes = np.zeros(len(self.corrs))
        for i, corrector in enumerate(self.corrs):
            if corrector[:2] == "ZH" or corrector[:2] == "ZX":
                bdes[i] = (self.lattice[corrector].get_strength()[0] * 10)  # gauss*m
            elif corrector[:2] == "ZV":
                bdes[i] = (self.lattice[corrector].get_strength()[1] * 10)  # gauss*m
        correctors = {"names": self.corrs, "bdes": bdes, "bact": bdes}
        return correctors

    def get_bpms(self):
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

        for s in self.lattice.get_screens():
            screen_name = s.get_name()
            if names is not None and screen_name not in names:
                continue
            screen_names.append(screen_name)
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
                   "images": images}
        return screens

    def get_quadrupoles(self):  # returns quadrupole strengths
        self.log("Reading quadrupoles' strengths...")
        bdes = np.zeros(len(self.quadrupoles), dtype=float)  # one value per each quadrupole

        for i, quadrupole_name in enumerate(self.quadrupoles):
            quadrupole = self.lattice[quadrupole_name]
            quadrupole = quadrupole[0] if isinstance(quadrupole, list) else quadrupole
            try:
                strength = quadrupole.get_K1(self.Pref / self.Q)  # 1/m2
            except Exception:
                strength = 0.0
            if isinstance(strength, (list, tuple, np.ndarray)):
                bdes[i] = float(strength[0]) if len(strength) > 0 else 0.0
            else:
                bdes[i] = float(strength)
        return {"names": self.quadrupoles, "bdes": bdes, "bact": bdes.copy()}

    def set_quadrupoles(self, names, values_range):
        if isinstance(names, str):
            names = [names]
        if not (isinstance(values_range, list)):
            values_range = [values_range]

        for quadrupole_name, value in zip(names, values_range):
            quadrupole = self.lattice[quadrupole_name]
            quadrupole = quadrupole[0] if isinstance(quadrupole, list) else quadrupole
            quadrupole.set_K1(self.Pref / self.Q, float(value))

        self.__track_bunch()

    def push(self, names, corr_vals):
        if not isinstance(names, list):
            names = [names]  # makes it a list
        for corr, val in zip(names, corr_vals):
            if corr[:2] == "ZH" or corr[:2] == "ZX":
                self.lattice[corr].set_strength(val / 10, 0.0)  # T*mm
            elif corr[:2] == "ZV":
                self.lattice[corr].set_strength(0.0, val / 10)  # T*mm
        self.__track_bunch()

    def vary_correctors(self, names, corr_vals):
        if not isinstance(names, list):
            names = [names]  # makes it a list
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
            quadrupole = self.lattice[quadrupole_name]
            quadrupole = quadrupole[0] if isinstance(quadrupole, list) else quadrupole
            current = quadrupole.get_K1(self.Pref / self.Q)
            current = float(current[0]) if isinstance(current, (list, tuple, np.ndarray)) else float(current)
            quadrupole.set_K1(self.Pref / self.Q, current + val)
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
        Wt, Wl, hz = self._load_wake_data(cbpm_file, trans_or_long="transverse", scale=wake_scale)
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
            Wt, Wl, hz = self._load_wake_data(bellow_file, trans_or_long="transverse", scale=wake_scale)
            WF_bellow = rft.Wakefield_1d(Wt, Wl, hz)

            drifts = [n for n in self.sequence if n.upper().startswith("L")]
            for n in drifts[::25]:
                try:
                    attach_to(n, WF_bellow)
                except Exception:
                    pass

    def align_everything(self):
        self.lattice.align_elements()
        self.__track_bunch()

    def misalign_quadrupoles(self, sigma_x=0.100, sigma_y=0.100):
        self.lattice.scatter_elements('quadrupole', sigma_x, sigma_y, 0, 0, 0, 0, 'center')
        self.__track_bunch()

    def misalign_bpms(self, sigma_x=0.100, sigma_y=0.100):
        self.lattice.scatter_elements('bpm', sigma_x, sigma_y, 0, 0, 0, 0, 'center')
        self.__track_bunch()

