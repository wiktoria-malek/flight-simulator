import numpy as np
import time, os
from datetime import datetime
from Interfaces.AbstractMachineInterface import AbstractMachineInterface
import RF_Track as rft
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from FACET2 import FACET2

class InterfaceFACET2_Linac_RFTrack(AbstractMachineInterface):
    def get_name(self):
        return 'FACET2_Linac_RFT'

    def __init__(self, population=rft.nC, jitter=0.0, bpm_resolution=0.0, nsamples=1, nparticles=1000):
        super().__init__()
        self.log = print
        self.lattice = FACET2.load_FACET()
        self.lattice.set_bpm_resolution(bpm_resolution)
        self.sequence = [ e.get_name() for e in self.lattice['*']]
        self.bpms = [ e.get_name() for e in self.lattice.get_bpms()]
        self.corrs = [ e.get_name() for e in self.lattice.get_correctors()]
        self.screens = [ e.get_name() for e in self.lattice.get_screens()]
        self.Pref = np.sqrt(125.0**2 - rft.electronmass**2)
        self.bunch_length_ps = 3
        self.nparticles = nparticles
        self.population = population
        self.jitter = jitter
        self.nsamples = nsamples
        self.dfs_test_energy = 0.98
        self.wfs_test_charge = 0.90
        self.__setup_beam0()
        self.__track_bunch()
        self._saved_sextupoles_state = None
        self.sextupoles = self._get_element_names_from_twiss_types({"SEXTUPOLE"})

    def log_messages(self,console):
        self.log=console or print

    def __setup_beam0(self):
        T = rft.Bunch6d_twiss()
        T.beta_x = 5.6
        T.alpha_x = -2.11
        T.beta_y = 2.9
        T.alpha_y = 0.0
        T.sigma_t = self.bunch_length_ps * rft.ps
        T.sigma_pt = 0.0
        T.emitt_x = 3.2
        T.emitt_y = 3.2
        T.sigma_pt = 0.8 # permille
        self.B0 = rft.Bunch6d_QR(rft.electronmass, self.population, -1, self.Pref, T, self.nparticles)

    def __setup_beam1(self):
        # Beam for DFS - Reduced energy
        Pref = self.dfs_test_energy * self.Pref
        T = rft.Bunch6d_twiss()
        T.beta_x = 5.6
        T.alpha_x = -2.11
        T.beta_y = 2.9
        T.alpha_y = 0.0
        T.sigma_t = self.bunch_length_ps * rft.ps
        T.sigma_pt = 0.0
        T.emitt_x = 3.2
        T.emitt_y = 3.2
        T.sigma_pt = 0.8 # permille
        self.B0 = rft.Bunch6d_QR(rft.electronmass, self.population, -1, Pref, T, self.nparticles)

    def __setup_beam2(self):
        # Beam for WFS - Reduced bunch charge
        population = self.wfs_test_charge * self.population
        T = rft.Bunch6d_twiss()
        T.beta_x = 5.6
        T.alpha_x = -2.11
        T.beta_y = 2.9
        T.alpha_y = 0.0
        T.sigma_t = self.bunch_length_ps * rft.ps
        T.sigma_pt = 0.0
        T.emitt_x = 3.2
        T.emitt_y = 3.2
        T.sigma_pt = 0.8 # permille
        self.B0 = rft.Bunch6d_QR(rft.electronmass, population, -1, self.Pref, T, self.nparticles)

    def __track_bunch(self):
        I0 = self.B0.get_info()
        dx = self.jitter*I0.sigma_x
        dy = self.jitter*I0.sigma_y
        dz, dt, roll = 0.0, 0.0, 0.0
        pitch = self.jitter*I0.sigma_py
        yaw   = self.jitter*I0.sigma_px
        B0_offset = self.B0.displaced(dx, dy, dz, dt, roll, pitch, yaw)
        B1 = self.lattice.track(B0_offset)
        I = B1.get_info()
        self.log("Emittance after tracking:")
        self.log(f"εx = {I.emitt_x}[mm.mrad]")
        self.log(f"εy = {I.emitt_y}[mm.mrad]")
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

    def get_hcorrectors_names(self):
        return [string for string in self.corrs if string.lower().startswith('x')]

    def get_vcorrectors_names(self):
        return [string for string in self.corrs if string.lower().startswith('y')]

    def get_elements_position(self,names):
        return [index for index, string in enumerate(self.sequence) if string in names]

    def get_target_dispersion(self, names=None):
        target_disp_x = np.array([0.0])
        target_disp_y = np.array([0.0])
        return target_disp_x, target_disp_y

    def get_icts(self):
        self.log("Reading ict's...")
        charge = [ bpm.get_total_charge() for bpm in self.lattice.get_bpms() ]
        icts = {
            "names": self.bpms,
            "charge": charge
        }
        return icts

    def get_correctors(self,names=None):
        self.log("Reading correctors' strengths...")
        bdes = np.zeros(len(self.corrs))
        for i,corrector in enumerate(self.corrs):
            if corrector[:2] == "XC":
                bdes[i] = (self.lattice[corrector].get_strength()[0]*10)  # gauss*m
            elif corrector[:2] == "YC":
                bdes[i] = (self.lattice[corrector].get_strength()[1]*10)  # gauss*m
        correctors = { "names": self.corrs, "bdes": bdes, "bact": bdes }

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

    def get_bpms(self,names=None):
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
            names = [names] # allows passing a single screen name
        hpixel =  0.001 # mm, horizontal size of a pixel
        vpixel =  0.001 # mm, vertical size of a pixel
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
            screen_name=s.get_name()
            if names is not None and screen_name not in names:
                continue
            screen_names.append(screen_name)
            hpixel_list.append(hpixel)
            vpixel_list.append(vpixel)
            m = s.get_bunch().get_phase_space('%x %y')
            if m is None or len(m) == 0: #empty bunch
                xb_list.append(np.nan)
                yb_list.append(np.nan)
                sigx_list.append(np.nan)
                sigy_list.append(np.nan)
                sum_list.append(0)
                images.append(np.zeros((1,1)))
                hedges_all.append(np.array([0,hpixel]))
                vedges_all.append(np.array([0,vpixel]))
                continue

            sumw=len(m[:,0]) # number of particles in the screen; intensity
            xb_list.append(np.mean(m[:,0])) # mean x of particles
            yb_list.append(np.mean(m[:,1])) # mean y of particles
            sigx_list.append(np.std(m[:,0])) # RMS x beam size
            sigy_list.append(np.std(m[:,1])) # RMS y beam size
            sum_list.append(sumw)

            nx = int(np.ceil(np.ptp(m[:,0]) / hpixel)) if np.ptp(m[:,0]) > 0 else 1 # ceil rounds up, so it can take the whole range
            ny = int(np.ceil(np.ptp(m[:, 1]) / vpixel)) if np.ptp(m[:, 1]) > 0 else 1
            nx=int(np.clip(nx,10,400))
            ny=int(np.clip(ny,10,400))
            image, hedges, vedges = np.histogram2d(m[:, 0], m[:, 1], bins=(nx, ny)) # divides x axis into nx bins, y axis into ny bins and calculates how many particles are in each rectangle
            images.append(image) # image[i,j] = nparticles in bin i on x axis and nparticles in bin j on y axis
            hedges_all.append(hedges) # bin edges in x (nx + 1)
            vedges_all.append(vedges) # bin edges in y (ny + 1)

        screens = {"names": screen_names,
                   "hpixel": np.array(hpixel_list, dtype=float),
                   "vpixel": np.array(vpixel_list, dtype=float),
                   "x": np.array(xb_list, dtype=float),
                   "y": np.array(yb_list, dtype=float),
                   "sigx": np.array(sigx_list, dtype=float),
                   "sigy": np.array(sigy_list, dtype=float),
                   "sum": np.array(sum_list, dtype=float),
                   "S": np.array([], dtype=float),
                   "hedges": hedges_all,
                   "vedges": vedges_all,
                   "images": images}
        return screens

    def set_correctors(self, names, corr_vals):
        if not isinstance(names, list):
            names = [ names ] # makes it a list
        for corr, val in zip(names, corr_vals):
            if corr[:2] == "XC":
                self.lattice[corr].set_strength(val/10, 0.0)  # T*mm
            elif corr[:2] == "YC":
                self.lattice[corr].set_strength(0.0, val/10)  # T*mm
        self.__track_bunch()

    def vary_correctors(self, names, corr_vals):
        if not isinstance(names, list):
            names = [ names ] # makes it a list
        for corr, val in zip(names, corr_vals):
            if corr[:2] == "XC":
                self.lattice[corr].vary_strength(val/10, 0.0)  # T*mm
            elif corr[:2] == "YC":
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

