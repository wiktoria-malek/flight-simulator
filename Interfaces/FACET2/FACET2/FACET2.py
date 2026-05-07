# -*- coding: utf-8 -*-
"""
Python translation of the Octave RF-Track lattice builder:

    function L = load_FACET()    # laod 'lattice.py'
    function L = import_BMAD()   # load 'FACET-II-Wakes.lat.bmad'

"""

import math
import numpy as np

import RF_Track as rft  # RF-Track Python module / bindings

def import_BMAD():

    import pytao
    from pytao import Tao, SubprocessTao

    # Load the lattice file 'FACET-II-Wakes.lat.bmad'
    tao_init_file = "tao.init"
    tao = Tao("-init " + tao_init_file + " -noplot")

    # Define which attributes to print out for each element
    attributeDict = {
        'Drift': '-attribute L',
        'Monitor': '-attribute L',
        'Marker': '-attribute L',
        'HKicker': '-attribute L',
        'VKicker': '-attribute L',
        'SBend': '-attribute L -attribute P0C -attribute angle -attribute e1 -attribute e2 -attribute fint -attribute hgap',
        'Quadrupole': '-attribute L -attribute P0C -attribute K1',
        'Sextupole': '-attribute L -attribute P0C -attribute K2',
        'Lcavity': '-attribute L -attribute Gradient -attribute PHI0 -attribute RF_FREQUENCY'
    }

    # Store all the 
    elements = tao.cmd("sho lat PR10571:ENDL3F_2")
    # elements = tao.cmd("sho lat 1400:end")

    # Cycle through all the elements in the lattice and extract the desired information and put it in a dictionary.
    # -------------------------
    # Init wakefields
    # -------------------------
    if False:
        # Equivalent to the Octave block (disabled in original script)
        # load('/afs/.../wake_facet.dat') srwf_Sl = Wakefield_1d(WT_tot, WL_tot, dz)
        #
        # In Python, you would typically do something like:
        #   import numpy as np
        #   data = np.loadtxt('/afs/.../wake_facet.dat')
        #   WT_tot = data[:, ...]
        #   WL_tot = data[:, ...]
        #   dz     = ...
        #   srwf_Sl = rft.Wakefield_1d(WT_tot, WL_tot, dz)
        raise NotImplementedError("Wakefield file loading branch is disabled (if 0 in Octave).")
    else:
        freq = 2.856e9
        ph_adv = 2 * math.pi / 3  # assumption
        a_over_lambda = 0.15

        # Octave: lambda = rft.clight*1e3 / freq; % mm
        lam_mm = rft.clight * 1e3 / freq  # mm
        l_mm = lam_mm * ph_adv / (2 * math.pi)  # cell length [mm]
        a_mm = a_over_lambda * lam_mm  # iris aperture [mm]
        g_mm = l_mm - 3  # gap length [mm] (overridden below)
        g_mm = l_mm - 10  # mm

        # Octave: srwf_Sl = rft.ShortRangeWakefield(a/1e3, g/1e3, l/1e3)
        srwf_Sl = rft.ShortRangeWakefield(a_mm / 1e3, g_mm / 1e3, l_mm / 1e3)

    # -------------------------
    # Lattice + helpers
    # -------------------------
    L = rft.Lattice()

    def add_marker(name: str):
        E = rft.Screen()
        E.set_name(name)
        L.append(E)
        return E

    def add_quad(name: str, l: float, p0c: float, k1: float):
        # Octave: Quadrupole(l, p0c / -1e6, k1)
        E = rft.Quadrupole(l, p0c / -1e6, k1)
        E.set_name(name)
        L.append(E)
        return E

    def add_drift(name: str, l: float):
        E = rft.Drift(l)
        E.set_name(name)
        L.append(E)
        return E

    def add_bpm(name: str):
        E = rft.Bpm()
        E.set_name(name)
        L.append(E)
        return E

    def add_solenoid(name: str, l: float):
        # Octave script uses a Drift placeholder for solenoids
        E = rft.Drift(l)
        E.set_name(name)
        L.append(E)
        return E

    def add_kicker(name: str):
        E = rft.Corrector()
        E.set_name(name)
        L.append(E)
        return E

    def add_sextupole(name: str, l: float, p0c: float, k2: float):
        E = rft.Sextupole(l, p0c / -1e6, k2)
        E.set_name(name)
        L.append(E)
        return E

    def add_sbend(name: str, l: float, angle: float, p0c: float, e1: float, e2: float, fint: float, hgap: float):
        E = rft.SBend(l, angle, p0c / -1e6, e1, e2)
        E.set_name(name)
        E.set_fint(fint)
        E.set_hgap(hgap)
        L.append(E)
        return E

    def add_lcavity(name: str, l: float, gradient: float, freq: float, phi0: float):
        # Octave:
        #   phid = 360.0 * phi0; % deg
        #   ph_adv = 2*pi/3;
        #   lcell = rft.clight / freq * ph_adv / 2 / pi;
        #   ncells = round(l / lcell)
        phid = 360.0 * phi0  # degrees
        ph_adv_local = 2 * math.pi / 3
        lcell = rft.clight / freq * ph_adv_local / 2 / math.pi
        ncells = int(round(l / lcell))

        E = rft.TW_Structure(gradient, 0, freq, ph_adv_local, ncells)
        E.set_odeint_algorithm("rk2")
        E.set_nsteps(100)
        E.set_phid(phid)
        E.set_name(name)

        if freq > 10e9:
            # kept as in Octave (commented out)
            # E.add_collective_effect(srwf_Xt)
            # E.add_collective_effect(srwf_Xl)
            # E.set_cfx_nsteps(10)
            pass
        else:
            # Octave: E.add_collective_effect(srwf_Sl) E.set_cfx_nsteps(10)
            E.add_collective_effect(srwf_Sl)
            E.set_cfx_nsteps(10)

        if E.get_length() != l:
            L.append(rft.Drift((l - E.get_length()) / 2))
            L.append(E)
            L.append(rft.Drift((l - E.get_length()) / 2))
        else:
            L.append(E)

        return E

    p0c = np.nan # if undefined takes p0c from BMAD
    toKeep = ['Drift', 'Quadrupole', 'SBend', 'RBend', 'Lcavity', 'Sextupole', 'Monitor', 'Marker', 'HKicker', 'VKicker' ]
    for e in elements[3:-3]:
        # Find the key for the given element
        key = e[24:41].strip()
        name = e[9:23].strip()
        #print([key,name])
        if key in toKeep:
            if "#" not in name:     
                printString = 'sho lat ' + name + ' ' + attributeDict[key]
            elif name.split("#")[1] == '1':
                # print(temp)
                printString = 'sho lat ' + name.split("#")[0] + ' ' + attributeDict[key]
            else:
                continue
            taoOut = tao.cmd(printString)[2]
        
            # Turn everything into a dictionary so you can print it all.
            temp = [x for x in taoOut.split(' ') if x != '']
            name = temp[1]
            key = temp[2]
            temp[3:] = [float(x) for x in temp[3:]]
            s = temp[3]
            length = temp[5]
            if key == 'Drift':
                add_drift (name, length)
        
            elif key == 'Marker':
                add_marker (name)
        
            elif key == 'Monitor':
                add_bpm (name)
        
            elif key == 'HKicker' or key == 'VKicker':
                add_kicker (name)
        
            elif key == 'Lcavity':
                gradient = temp[6]
                phi0 = temp[7]
                freq = temp[8]
                add_lcavity (name, length, gradient, freq, phi0)
        
            elif key == 'Quadrupole':
                p0c = np.nan if p0c==np.nan else temp[6]
                k1 = temp[7]
                add_quad (name, length, p0c, k1)
        
            elif key == 'Sextupole':
                p0c = np.nan if p0c==np.nan else temp[6]
                k2 = temp[7]
                add_sextupole (name, length, p0c, k2)
        
            elif key == 'SBend':
                p0c = np.nan if p0c==np.nan else temp[6]
                angle = temp[7]
                e1 = temp[8]
                e2 = temp[9]
                fint = temp[10]
                hgap = temp[11]
                add_sbend (name, length, angle, p0c, e1, e2, fint, hgap)

    return L

def load_FACET():
    # -------------------------
    # Init wakefields
    # -------------------------
    if False:
        # Equivalent to the Octave block (disabled in original script)
        # load('/afs/.../wake_facet.dat') srwf_Sl = Wakefield_1d(WT_tot, WL_tot, dz)
        #
        # In Python you would typically do something like:
        #   import numpy as np
        #   data = np.loadtxt('/afs/.../wake_facet.dat')
        #   WT_tot = data[:, ...]
        #   WL_tot = data[:, ...]
        #   dz     = ...
        #   srwf_Sl = rft.Wakefield_1d(WT_tot, WL_tot, dz)
        raise NotImplementedError("Wakefield file loading branch is disabled (if 0 in Octave).")
    else:
        freq = 2.856e9
        ph_adv = 2 * math.pi / 3  # assumption
        a_over_lambda = 0.15

        # Octave: lambda = rft.clight*1e3 / freq; % mm
        lam_mm = rft.clight * 1e3 / freq  # mm
        l_mm = lam_mm * ph_adv / (2 * math.pi)  # cell length [mm]
        a_mm = a_over_lambda * lam_mm  # iris aperture [mm]
        g_mm = l_mm - 3  # gap length [mm] (overridden below)
        g_mm = l_mm - 10  # mm

        # Octave: srwf_Sl = rft.ShortRangeWakefield(a/1e3, g/1e3, l/1e3)
        srwf_Sl = rft.ShortRangeWakefield(a_mm / 1e3, g_mm / 1e3, l_mm / 1e3)

    # -------------------------
    # Lattice + helpers
    # -------------------------
    L = rft.Lattice()

    def add_marker(name: str):
        E = rft.Screen()
        E.set_name(name)
        L.append(E)
        return E

    def add_quad(name: str, l: float, p0c: float, k1: float):
        # Octave: Quadrupole(l, p0c / -1e6, k1)
        E = rft.Quadrupole(l, p0c / -1e6, k1)
        E.set_name(name)
        L.append(E)
        return E

    def add_drift(name: str, l: float):
        E = rft.Drift(l)
        E.set_name(name)
        L.append(E)
        return E

    def add_bpm(name: str):
        E = rft.Bpm()
        E.set_name(name)
        L.append(E)
        return E

    def add_solenoid(name: str, l: float):
        # Octave script uses a Drift placeholder for solenoids
        E = rft.Drift(l)
        E.set_name(name)
        L.append(E)
        return E

    def add_kicker(name: str):
        E = rft.Corrector()
        E.set_name(name)
        L.append(E)
        return E

    def add_sextupole(name: str, l: float, p0c: float, k2: float):
        E = rft.Sextupole(l, p0c / -1e6, k2)
        E.set_name(name)
        L.append(E)
        return E

    def add_sbend(name: str, l: float, angle: float, p0c: float, e1: float, e2: float, fint: float, hgap: float):
        E = rft.SBend(l, angle, p0c / -1e6, e1, e2)
        E.set_name(name)
        E.set_fint(fint)
        E.set_hgap(hgap)
        L.append(E)
        return E

    def add_lcavity(name: str, l: float, gradient: float, freq: float, phi0: float):
        # Octave:
        #   phid = 360.0 * phi0; % deg
        #   ph_adv = 2*pi/3;
        #   lcell = rft.clight / freq * ph_adv / 2 / pi;
        #   ncells = round(l / lcell)
        phid = 360.0 * phi0  # degrees
        ph_adv_local = 2 * math.pi / 3
        lcell = rft.clight / freq * ph_adv_local / 2 / math.pi
        ncells = int(round(l / lcell))

        E = rft.TW_Structure(gradient, 0, freq, ph_adv_local, ncells)
        E.set_odeint_algorithm("rk2")
        E.set_nsteps(100)
        E.set_phid(phid)
        E.set_name(name)

        if freq > 10e9:
            # kept as in Octave (commented out)
            # E.add_collective_effect(srwf_Xt)
            # E.add_collective_effect(srwf_Xl)
            # E.set_cfx_nsteps(10)
            pass
        else:
            # Octave: E.add_collective_effect(srwf_Sl) E.set_cfx_nsteps(10)
            E.add_collective_effect(srwf_Sl)
            E.set_cfx_nsteps(10)

        if E.get_length() != l:
            L.append(rft.Drift((l - E.get_length()) / 2))
            L.append(E)
            L.append(rft.Drift((l - E.get_length()) / 2))
        else:
            L.append(E)

        return E

    try:
        from . import lattice
    except ImportError:
        import lattice
    lattice.add_marker = add_marker
    lattice.add_quad = add_quad
    lattice.add_drift = add_drift
    lattice.add_bpm = add_bpm
    lattice.add_solenoid = add_solenoid
    lattice.add_kicker = add_kicker
    lattice.add_sextupole = add_sextupole
    lattice.add_sbend = add_sbend
    lattice.add_lcavity = add_lcavity
    lattice.build()
                        
    # -------------------------
    # Adjust phases
    # -------------------------
    K11_phase = -5.69444444444444434e-02

    # Octave: for K11 = L{'K11_[1-2]*'}; K11{1}.set_phid(360*K11_phase) end
    for K11 in L["K11_[1-2]*"]:
        K11.set_phid(360.0 * K11_phase)

    # Octave: for K11 = L{'K11_[3-9]*'}; phid = K11{1}.get_phid() K11{1}.set_phid(phid) end
    for K11 in L["K11_[3-9]*"]:
        phid = K11.get_phid()
        K11.set_phid(phid)

    return L

