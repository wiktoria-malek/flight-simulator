import numpy as np
import matplotlib.pyplot as plt
import RF_Track as rft
from scipy.optimize import minimize
import re, os
from Interfaces.AbstractMachineInterface import AbstractMachineInterface

class InterfaceCLEAR_RFTrack(AbstractMachineInterface):
    def get_name(self):
        return 'CLEAR_RFT'

    def get_ITF(self, I):
        return 1.29404711e-2 - 2.59458259e-07 * I  # T/A

    def get_grad(self, I, Lquad=0.226):
        G_0 = I * self.get_ITF(I) / Lquad  # T/m
        return G_0

    def get_Quad_K(self, G_0, Pref):
        K = 299.8 * G_0 / Pref  # 1/m^2
        return K

    def get_Quad_K_from_I(self, I, Lquad, Pref):
        G_0 = self.get_grad(I, Lquad)
        K = self.get_Quad_K(G_0, Pref)
        return K

    def __build(self, filename):
        with open(filename) as file:
            lines = file.readlines()
        element_descriptions = {}
        previous_name = None
        quad_index = 0
        corr_index = 0
        for line in lines:
            if line[0:2] != ' "':
                continue

            text = re.findall(r'"([A-Za-z0-9.$_]+)"', line)
            numbers = re.findall(r'\d+\.\d+', line)
            name = text[0]

            if name == 'CA.BTV0800':
                continue
            element_type = None
            if 'QFD' in name or 'QDD' in name:
                element_type = 'Quadrupole'
            elif 'BTV' in name:
                element_type = 'Screen'
            elif 'DHG' in name or 'DHJ' in name or 'SDV' in name:
                element_type = 'Corrector'
            elif 'BPC' in name or 'BPM' in name:
                element_type = 'BPM'
            elif len(text) > 1 and text[1] == 'MARKER':
                element_type = 'Marker'

            if element_type is None:
                continue

            s_end = float(numbers[0])
            L = float(numbers[1])
            s_start = s_end - L

            L = round(L, 4)
            s_start = round(s_start, 4)
            s_end = round(s_end, 4)

            if previous_name is not None:
                L_drift = round(s_start - element_descriptions[previous_name]['s_end'], 4)
                if L_drift != 0:
                    element_descriptions[previous_name + ' Drift'] = {
                        'element_type': 'Drift',
                        'L': L_drift,
                        's_start': element_descriptions[previous_name]['s_end'],
                        's_end': s_start,
                        'quad_index': None,
                        'corr_index': None,
                    }

            element_descriptions[name] = {
                'element_type': element_type,
                'L': L,
                's_start': s_start,
                's_end': s_end,
                'quad_index': quad_index if element_type == 'Quadrupole' else None,
                'corr_index': corr_index if element_type == 'Corrector' else None,
            }

            if element_type == 'Quadrupole':
                quad_index += 1
            if element_type == 'Corrector':
                corr_index += 1

            previous_name = name

        def get_lattice(start, end, Pref, quad_currents, include_end=True):
            start_index = list(element_descriptions.keys()).index(start)
            end_index = list(element_descriptions.keys()).index(end)
            if include_end:
                end_index += 1
            lattice = rft.Lattice()
            names = list(element_descriptions.keys())
            elements = list(element_descriptions.values())
            for name, element_description in zip(names[start_index:end_index], elements[start_index:end_index]):
                element_type = element_description['element_type']
                L = element_description['L']
                quad_index = element_description['quad_index']

                if element_type == 'Drift':
                    element = rft.Drift(L)
                elif element_type == 'Quadrupole':
                    if 'QFD' in name:
                        K = self.get_Quad_K_from_I(quad_currents[quad_index], L, Pref)
                    elif 'QDD' in name:
                        K = - self.get_Quad_K_from_I(quad_currents[quad_index], L, Pref)
                    element = rft.Quadrupole(L, Pref / self.Q, K)
                elif element_type == 'Corrector':
                    element = rft.Corrector(L)
                elif element_type == 'BPM':
                    element = rft.Bpm(L)
                elif element_type == 'Screen' or element_type == 'Marker':
                    element = rft.Screen()
                else:
                    continue
                element.set_name(name)
                lattice.append(element)
            return lattice
        start = 'CA.STLINE$START'
        end = 'CA.STLINE$END'
        quad_currents = np.array([
            0,  # QFD350
            0,  # QDD355
            0,  # QFD360

            20,  # QFD510
            40.96551724137931,  # QDD515
            20,  # QFD520

            0,  # QFD760
            0,  # QDD765
            0,  # QFD770

            0,  # QDD870
            0  # QFD880
        ])  # A
        lattice = get_lattice(start, end, self.Pref, quad_currents)
        return lattice, element_descriptions, start, end

    def __init__(self, population=300 * rft.pC, jitter=0.0, bpm_resolution=0.0, nsamples=1, nparticles=10000):
        self.Pref = 198 # MeV/c
        self.Q=-1
        self.population = population
        self.jitter = jitter
        self.nsamples = nsamples
        self.nparticles = nparticles
        self.electronmass=rft.electronmass
        survey_path = os.path.join(os.path.dirname(__file__), "clear.survey0_filtered.tfs")
        self.lattice, self.element_descriptions, self.start, self.end = self.__build(filename=survey_path)
        self.lattice.set_bpm_resolution(bpm_resolution)
        self.log = print
        elements_in_lattice=list(self.lattice['*'])
        names_all=list(self.element_descriptions.keys())
        i0=names_all.index(self.start)
        i1=names_all.index(self.end)
        self.sequence = names_all[i0:i1 + 1]
        self._by_name=dict(zip(self.sequence,elements_in_lattice))
        self.bpms=[n for n in self.sequence if self.element_descriptions[n]['element_type'] == 'BPM']
        self.corrs=[n for n in self.sequence if self.element_descriptions[n]['element_type'] == 'Corrector']
        self.screens=[n for n in self.sequence if self.element_descriptions[n]['element_type'] == 'Screen']
        self.quadrupoles = [n for n in self.sequence if self.element_descriptions[n]['element_type'] == 'Quadrupole']
        self.sextupoles = []
        self.bpm_elements={n: self._by_name[n] for n in self.bpms}
        self.corrector_elements={n: self._by_name[n] for n in self.corrs}
        self.screen_elements={n: self._by_name[n] for n in self.screens}
        self.quadrupole_elements = {n: self._by_name[n] for n in self.quadrupoles}
        self.__setup_beam0()
        self.__track_bunch()
        self.freq=2.997e9
        self.nr_quad=11
        self.Lquad=0.226 #magnetic length of the quadrupole in [m]
        self.nominal_K=0.7752883624676146 #3.35  # 1/m

    def __setup_beam0(self):
        T = rft.Bunch6d_twiss()
        T.emitt_x = 7.04 # mm.mrad normalised emittance
        T.emitt_y = 3.39  # 0.727 # mm.mrad
        T.beta_x = 15.6 # m
        T.beta_y = 24  #2.73  # m
        T.alpha_x = -0.49
        T.alpha_y = -3.65 #0.339
        T.sigma_t = 10*rft.ps #or 37*rft.ps # mm/c
        T.sigma_pt = 10 # permille
        T.mean_xp=0.0
        T.mean_yp=0.0
        self.P0 = rft.Bunch6d_QR(rft.electronmass, self.population, 1, self.Pref, T, self.nparticles) # reference particle
        self.B0 = rft.Bunch6d_QR(rft.electronmass, self.population, self.Q, self.Pref, T, self.nparticles) # reference bunch
        self.dfs_test_energy = 0.98
        self.wfs_test_charge = 0.90

    def __setup_beam1(self):
        # Beam for DFS - Reduced energy
        Pref = self.dfs_test_energy * self.Pref
        T = rft.Bunch6d_twiss()
        T.emitt_x = 7.04 # mm.mrad normalised emittance
        T.emitt_y = 3.39  # 0.727 # mm.mrad
        T.beta_x = 15.6 # m
        T.beta_y = 24  #2.73  # m
        T.alpha_x = -0.49
        T.alpha_y = -3.65 #0.339
        T.sigma_t = 10*rft.ps #or 37*rft.ps # mm/c
        T.sigma_pt = 10 # permille
        T.mean_xp=0.0
        T.mean_yp=0.0
        self.B0 = rft.Bunch6d_QR(rft.electronmass, self.population, self.Q , Pref, T, self.nparticles)
        self.P0 = rft.Bunch6d_QR(rft.electronmass, self.population,  1 , Pref, T, self.nparticles)

    def __setup_beam2(self):
        # Beam for WFS - Reduced bunch charge
        population = self.wfs_test_charge * self.population
        T = rft.Bunch6d_twiss()
        T.emitt_x = 7.04 # mm.mrad normalised emittance
        T.emitt_y = 3.39  # 0.727 # mm.mrad
        T.beta_x = 15.6 # m
        T.beta_y = 24  #2.73  # m
        T.alpha_x = -0.49
        T.alpha_y = -3.65 #0.339
        T.sigma_t = 10*rft.ps #or 37*rft.ps # mm/c
        T.sigma_pt = 10 # permille
        T.mean_xp=0.0
        T.mean_yp=0.0
        self.B0 = rft.Bunch6d_QR(rft.electronmass, population, self.Q, self.Pref, T, self.nparticles)
        self.P0 = rft.Bunch6d_QR(rft.electronmass, population,  1, self.Pref, T, self.nparticles)

    def get_screens(self, names=None):
        if isinstance(names, str):
            names = [names]

        hpixel = 0.001
        vpixel = 0.001

        selected_screens = [screen for screen in self.screens if names is None or screen in names]

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
        s_list = []

        for screen_name in selected_screens:
            screen = self.screen_elements[screen_name]
            screen_names.append(screen_name)

            elem = self.element_descriptions.get(screen_name, {})
            s_list.append(elem.get("s_start", np.nan))

            hpixel_list.append(hpixel)
            vpixel_list.append(vpixel)

            bunch = screen.get_bunch()
            if bunch is None:
                xb_list.append(np.nan)
                yb_list.append(np.nan)
                sigx_list.append(np.nan)
                sigy_list.append(np.nan)
                sum_list.append(0.0)
                images.append(np.zeros((1, 1)))
                hedges_all.append(np.array([0.0, hpixel]))
                vedges_all.append(np.array([0.0, vpixel]))
                continue

            m = bunch.get_phase_space('%x %y')
            if m is None or len(m) == 0:
                xb_list.append(np.nan)
                yb_list.append(np.nan)
                sigx_list.append(np.nan)
                sigy_list.append(np.nan)
                sum_list.append(0.0)
                images.append(np.zeros((1, 1)))
                hedges_all.append(np.array([0.0, hpixel]))
                vedges_all.append(np.array([0.0, vpixel]))
                continue

            xb_list.append(float(np.mean(m[:, 0])))
            yb_list.append(float(np.mean(m[:, 1])))
            sigx_list.append(float(np.std(m[:, 0])))
            sigy_list.append(float(np.std(m[:, 1])))
            sum_list.append(float(len(m[:, 0])))

            nx = int(np.ceil(np.ptp(m[:, 0]) / hpixel)) if np.ptp(m[:, 0]) > 0 else 1
            ny = int(np.ceil(np.ptp(m[:, 1]) / vpixel)) if np.ptp(m[:, 1]) > 0 else 1
            nx = int(np.clip(nx, 10, 400))
            ny = int(np.clip(ny, 10, 400))

            image, hedges, vedges = np.histogram2d(m[:, 0], m[:, 1], bins=(nx, ny))
            images.append(image)
            hedges_all.append(hedges)
            vedges_all.append(vedges)

        return {
            "names": screen_names,
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
            "S": np.array(s_list, dtype=float),
        }

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

    def get_beam_factors(self):
        gamma_rel = np.sqrt((self.Pref / self.electronmass) ** 2 + 1.0)
        beta_rel = np.sqrt(1.0 - 1.0 / gamma_rel ** 2)
        return gamma_rel, beta_rel

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

    def _get_elements_positions(self, names=None):
        if isinstance(names, str):
            names = [names]
        selected = [name for name in self.sequence if names is None or name in names]
        return {
            "names": selected,
            "S": np.array([self.element_descriptions[name]["s_start"] for name in selected], dtype=float),
            "L": np.array([self.element_descriptions[name]["L"] for name in selected], dtype=float),
        }

    def get_sequence(self):
        return self.sequence

    def get_hcorrectors_names(self):
        return [string for string in self.corrs if "DHG" in string]

    def get_vcorrectors_names(self):
        return [string for string in self.corrs if ("DHJ" in string) or ("SDV" in string) ]

    def get_elements_position(self,names):
        return [index for index, string in enumerate(self.sequence) if string in names]

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

    def get_correctors(self,names=None):
        #self.log("Reading correctors' strengths...")
        bdes = np.zeros(len(self.corrs))
        for i,corrector in enumerate(self.corrs):
            c=self.corrector_elements[corrector]
            hx,hy=c.get_strength()
            if "DHG" in corrector: #horizontal
                bdes[i] = (hx*10)  # gauss*m
            elif ("SDV" in corrector) or ("DHJ" in corrector): #vertical
                bdes[i] = (hy*10)  # gauss*m
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

    def get_bpms(self, names=None):
        self.log('Reading bpms...')
        x = np.zeros((self.nsamples, len(self.bpms)))
        y = np.zeros_like(x)
        tmit = np.zeros_like(x)

        for i in range(self.nsamples):
            for j, bpm_name in enumerate(self.bpms):
                bpm = self.bpm_elements[bpm_name]
                reading = bpm.get_reading()
                x[i, j] = reading[0]
                y[i, j] = reading[1]
                tmit[i, j] = bpm.get_total_charge()

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

    def set_correctors(self, names, corr_vals):
        if isinstance(names, str):
            names = [names]
        if not isinstance(corr_vals, (list, tuple, np.ndarray)):
            corr_vals = [corr_vals]
        for corr, val in zip(names, corr_vals):
            c = self.corrector_elements[corr]
            if "DHG" in corr:
                c.set_strength(val / 10, 0.0)
            elif ("DHJ" in corr) or ("SDV" in corr):
                c.set_strength(0.0, val / 10)
        self.__track_bunch()

    def vary_correctors(self, names, corr_vals):
        if isinstance(names, str):
            names = [names]
        if not isinstance(corr_vals, (list, tuple, np.ndarray)):
            corr_vals = [corr_vals]
        for corr, val in zip(names, corr_vals):
            c = self.corrector_elements[corr]
            if "DHG" in corr:
                c.vary_strength(val / 10, 0.0)
            elif ("SDV" in corr) or ("DHJ" in corr):
                c.vary_strength(0.0, val / 10)
        self.__track_bunch()

    def _build_bunch_from_guesses(self, emit_x, emit_y, beta_x0, beta_y0, alpha_x0, alpha_y0):
        T = rft.Bunch6d_twiss()
        T.emitt_x = float(emit_x)
        T.emitt_y = float(emit_y)
        T.beta_x = float(beta_x0)
        T.beta_y = float(beta_y0)
        T.alpha_x = float(alpha_x0)
        T.alpha_y = float(alpha_y0)
        T.sigma_t = 10 * rft.ps
        T.sigma_pt = 10
        T.mean_xp = 0.0
        T.mean_yp = 0.0
        return rft.Bunch6d_QR(rft.electronmass, self.population, self.Q, self.Pref, T, self.nparticles)

    def _read_tracked_bunch_screen_sigmas(self, screens):
        screen_data = self.get_screens(names=screens)
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

    def predict_emittance_scan_response(self, quad_name, screens, K1_values, emit_x, emit_y, beta_x0, beta_y0, alpha_x0, alpha_y0, stop_checker=None, reference_screen=None):
        screens = list(screens)
        K1_values = np.asarray(K1_values, dtype=float)
        if len(screens) == 0:
            raise RuntimeError("No screens provided for emittance scan prediction.")
        if quad_name not in self.quadrupoles:
            raise ValueError(f"Quadrupole {quad_name} not found in quadrupoles")
        missing_screens = [screen for screen in screens if screen not in self.screens]
        if missing_screens:
            raise ValueError(f"Screens not found: {missing_screens}")
        original_quad = self.get_quadrupoles(names=[quad_name])
        if len(original_quad["bdes"]) == 0:
            raise RuntimeError(f"Could not find original strength for quad {quad_name}")

        K_original = float(original_quad["bdes"][0])
        B0_original = self.B0

        output_x = np.full((len(K1_values), len(screens)), np.nan, dtype=float)
        output_y = np.full((len(K1_values), len(screens)), np.nan, dtype=float)

        try:
            for k, K1 in enumerate(K1_values):
                if callable(stop_checker) and stop_checker():
                    raise RuntimeError("__OPTIMIZATION_STOP__")

                self.set_quadrupoles([quad_name], [float(K1)], track=False)
                self.B0 = self._build_bunch_from_guesses(emit_x, emit_y, beta_x0, beta_y0, alpha_x0, alpha_y0)
                self.__track_bunch()
                output_x[k, :], output_y[k, :] = self._read_tracked_bunch_screen_sigmas(screens)

        finally:
            self.B0 = B0_original
            self.set_quadrupoles([quad_name], [K_original], track=False)
            self.__track_bunch()

        return output_x, output_y

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

    def get_elements_indices(self, names):
        if isinstance(names, str):
            names = [names]
        name_to_index = {string: index for index, string in enumerate(self.sequence)}
        return [name_to_index.get(name, np.nan) for name in names]