import RF_Track as rft
import numpy as np
import time
from LogConsole_BBA import LogConsole
from datetime import datetime

class InterfaceATF2_Ext_RFTrack():
    def get_name(self):
        return 'ATF2_Ext_RFT'

    def __init__(self, population=2e10, jitter=0.0, bpm_resolution=0.0, nsamples=1,nparticles=1000):
        self.log = print
        self.lattice = rft.Lattice('Interfaces/ATF2/Ext_ATF2/ATF2_EXT_FF_v5.2.twiss')
        self.lattice.set_bpm_resolution(bpm_resolution)
        for s in self.lattice['*OTR*']:
            screen = rft.Screen()
            screen.set_name(s.get_name())
            s.replace_with(screen)
        self.sequence = [ e.get_name() for e in self.lattice['*']]
        self.bpms = [ e.get_name() for e in self.lattice.get_bpms()]
        self.corrs = [ e.get_name() for e in self.lattice.get_correctors()]
        self.screens = [ e.get_name() for e in self.lattice.get_screens()]
        self.Pref = 1.2999999e3 # 1.3 GeV/c
        self.nparticles = nparticles
        self.population = population
        self.jitter = jitter
        self.nsamples = nsamples
        self.dfs_test_energy = 0.98
        self.wfs_test_charge = 0.90
        self.__setup_beam0()
        self.__track_bunch()

    def log_messages(self,console):
        self.log=console or print

    def __setup_beam0(self):
        T = rft.Bunch6d_twiss()
        T.emitt_x = 5.2 # mm.mrad normalised emittance
        T.emitt_y = 0.03 # mm.mrad
        T.beta_x = 6.848560987 # m
        T.beta_y = 2.935758992 # m
        T.alpha_x = 1.108024744
        T.alpha_y = -1.907222942
        T.sigma_t = 8 # mm/c
        T.sigma_pt = 0.8 # permille
        self.B0 = rft.Bunch6d_QR(rft.electronmass, self.population, -1, self.Pref, T, self.nparticles)
        
    def __setup_beam1(self):
        # Beam for DFS - Reduced energy
        Pref = self.dfs_test_energy * self.Pref
        T = rft.Bunch6d_twiss()
        T.emitt_x = 5.2 # mm.mrad normalised emittance
        T.emitt_y = 0.03 # mm.mrad
        T.beta_x = 6.848560987 # m
        T.beta_y = 2.935758992 # m
        T.alpha_x = 1.108024744
        T.alpha_y = -1.907222942
        T.sigma_t = 8 # mm/c
        T.sigma_pt = 0.8 # permille
        Nparticles = 1000 # number of macroparticles
        self.B0 = rft.Bunch6d_QR(rft.electronmass, self.population, -1, Pref, T, self.nparticles)

    def __setup_beam2(self):
        # Beam for WFS - Reduced bunch charge
        population = self.wfs_test_charge * self.population
        T = rft.Bunch6d_twiss()
        T.emitt_x = 5.2 # mm.mrad normalised emittance
        T.emitt_y = 0.03 # mm.mrad
        T.beta_x = 6.848560987 # m
        T.beta_y = 2.935758992 # m
        T.alpha_x = 1.108024744
        T.alpha_y = -1.907222942
        T.sigma_t = 8 # mm/c
        T.sigma_pt = 0.8 # permille
        Nparticles = 1000 # number of macroparticles
        self.B0 = rft.Bunch6d_QR(rft.electronmass, population, -1, self.Pref, T, self.nparticles)

    def __track_bunch(self):
        I0 = self.B0.get_info()
        dx = self.jitter*I0.sigma_x
        dy = self.jitter*I0.sigma_y
        dz, dt, roll = 0.0, 0.0, 0.0
        pitch = self.jitter*I0.sigma_py
        yaw   = self.jitter*I0.sigma_px
        B0_offset = self.B0.displaced(dx, dy, dz, dt, roll, pitch, yaw)
        self.lattice.track(B0_offset)
        I=B0_offset.get_info()
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

    def change_intensity(self): #reduced charge
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

    def get_hcorrectors_names(self):
        return [string for string in self.corrs if (string.lower().startswith('zh')) or (string.lower().startswith('zx'))]

    def get_vcorrectors_names(self):
        return [string for string in self.corrs if string.lower().startswith('zv')]

    def get_elements_position(self,names):
        return [index for index, string in enumerate(self.sequence) if string in names]

    def get_target_dispersion(self, names=None):
        if names is None:
            names = self.get_bpms_names()
        with open('Interfaces/ATF2/Ext_ATF2/ATF2_EXT_FF_v5.2.twiss', "r") as file:
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
        disp_values={}
        target_disp_x, target_disp_y = [], []
        for line in lines[dollar_sign + 1:]:
            data = line.split()
            if len(data) <= max(DX_column, DY_column, elements_names): #if a line has less column than needed, it is omitted
                continue
            bpms_name = data[elements_names].strip('"')
            try:
                disp_values[bpms_name] = (float(data[DX_column]),float(data[DY_column]))
            except ValueError:
                continue
        for bpm in names:
            if bpm in disp_values:
                dx,dy = disp_values[bpm]
            else:
                dx,dy = float("nan"), float("nan")
            target_disp_x.append(dx)
            target_disp_y.append(dy)
        return target_disp_x, target_disp_y

    def get_icts(self):
        self.log("Reading ict's...")
        charge = [ bpm.get_total_charge() for bpm in self.lattice.get_bpms() ]
        icts = {
            "names": self.bpms,
            "charge": charge
        }        
        return icts

    def get_correctors(self):
        #print("Reading correctors' strengths...")
        self.log("Reading correctors' strengths...")
        bdes = np.zeros(len(self.corrs))
        for i,corrector in enumerate(self.corrs):
            if corrector[:2] == "ZH" or corrector[:2] == "ZX":
                bdes[i] = (self.lattice[corrector].get_strength()[0]*10)  # gauss*m
            elif corrector[:2] == "ZV":
                bdes[i] = (self.lattice[corrector].get_strength()[1]*10)  # gauss*m
        correctors = { "names": self.corrs, "bdes": bdes, "bact": bdes }
        return correctors
    
    def get_bpms(self):
        self.log('Reading bpms...')
        x = np.zeros((self.nsamples, len(self.bpms)))
        y = np.zeros(x.shape)
        tmit = np.zeros(x.shape)
        for i in range(self.nsamples):
            for j,bpm in enumerate(self.bpms):
                b = self.lattice[bpm]
                reading = b.get_reading()
                x[i,j] = reading[0]
                y[i,j] = reading[1]
                tmit[i,j] = b.get_total_charge()
        bpms = { "names": self.bpms, "x": x, "y": y, "tmit": tmit }
        return bpms

    def get_screens(self, names=None):
        self.log('Reading screens...')
        nscreens = len(self.screens)
        hpixel = np.ones(nscreens) * 0.001 # mm, horizonatl size of a pixel
        vpixel = np.ones(nscreens) * 0.001 # mm, vertical size of a pixel
        images = []
        hedges_all = []
        vedges_all = []
        screen_names = []
        for i,s in enumerate(self.lattice.get_screens()):
            if names==None or (s.get_name() in names):
                screen_names.append(s.get_name())
                m = s.get_bunch().get_phase_space('%x %y')
                nx = int(np.ceil(np.ptp(m[:,0]) / hpixel[i]))
                ny = int(np.ceil(np.ptp(m[:,1]) / vpixel[i]))
                image, hedges, vedges = np.histogram2d(m[:,0], m[:,1], bins=(nx,ny))
                images.append(image)
                hedges_all.append(hedges)
                vedges_all.append(vedges)
        screens = { "names": screen_names,
                    "hpixel": hpixel,
                    "vpixel": vpixel,
                    "hedges" : hedges_all,
                    "vedges" : vedges_all,
                    "images": images }
        return screens

    def push(self, names, corr_vals):
        if not isinstance(names, list):
            names = [ names ] # makes it a list
        for corr, val in zip(names, corr_vals):
            if corr[:2] == "ZH" or corr[:2] == "ZX":
                self.lattice[corr].set_strength(val/10, 0.0)  # T*mm
            elif corr[:2] == "ZV":
                self.lattice[corr].set_strength(0.0, val/10)  # T*mm
        self.__track_bunch()
    
    def vary_correctors(self, names, corr_vals):
        if not isinstance(names, list):
            names = [ names ] # makes it a list
        for corr, val in zip(names, corr_vals):
            if corr[:2] == "ZH" or corr[:2] == "ZX":
                self.lattice[corr].vary_strength(val/10, 0.0)  # T*mm
            elif corr[:2] == "ZV":
                self.lattice[corr].vary_strength(0.0, val/10)  # T*mm
        self.__track_bunch()

    def align_everything(self):
        self.lattice.align_elements()
        self.__track_bunch()

    def misalign_quadrupoles(self,sigma_x=0.100,sigma_y=0.100):
        self.lattice.scatter_elements('quadrupole', sigma_x, sigma_y, 0, 0, 0, 0, 'center')
        self.__track_bunch()

    def misalign_bpms(self,sigma_x=0.100,sigma_y=0.100):
        self.lattice.scatter_elements('bpm', sigma_x, sigma_y, 0, 0, 0, 0, 'center')
        self.__track_bunch()

