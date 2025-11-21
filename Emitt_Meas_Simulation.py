#2D projected emittance reconstruction with no noise
# TO DO: Mxy, conditions C1,C2,C3,C4
# maybe use rft to simulate the real beam
# add noises??

import numpy as np
import math
import RF_Track as rft
#class Emitt_Meas_Simulation():
def get_data_from_twiss_file():
    # madx
    with open('Ext_ATF2/ATF2_EXT_FF_v5.2.twiss', "r") as file:
        # lines=file.readlines()
        lines = [line.strip() for line in file if line.strip()]

    star_symbol = next(i for i, line in enumerate(lines) if line.startswith("*"))
    dollar_sign = next(i for i, line in enumerate(lines) if line.startswith("$") and i > star_symbol)
    columns = lines[star_symbol].lstrip("*").split()
    # R_11 = sqrt(beta_i/beta_0) (cos delta(mu) + alpha0 sin (delta mu))
    # R_12 = sqrt(beta_i beta_0) sin (delta mu)
    BETA_X_column = columns.index("BETX") # m
    BETA_Y_column = columns.index("BETY") # m
    ALPHA_X_column = columns.index("ALFX")
    ALPHA_Y_column = columns.index("ALFY")
    MU_X_column = columns.index("MUX") # should i divide it by 2pi or not
    MU_Y_column = columns.index("MUY")

    names = []
    twiss = {}
    elements_names = columns.index("NAME")

    for line in lines[dollar_sign + 1:]:
        data = line.split()
        name = data[elements_names].strip('"')
        names.append(name)

        twiss[name] = {
            "betx": float(data[BETA_X_column]),
            "bety": float(data[BETA_Y_column]),
            "alpx": float(data[ALPHA_X_column]),
            "alpy": float(data[ALPHA_Y_column]),
            "mux": float(data[MU_X_column]),
            "muy": float(data[MU_Y_column]),
        }

    entrance_index = names.index("ATF2$START")
    entrance_name = names[entrance_index]
    entrance = twiss[entrance_name]
    otr_names = ['OTR0X', 'OTR1X', 'OTR2X', 'OTR3X']
    otrs = {name: twiss[name] for name in otr_names}
    return entrance_name, entrance, otrs

def compute_transport_matrix():
    entrance_name, entrance, otrs = get_data_from_twiss_file()

    beta_x_0 = entrance["betx"]
    beta_y_0 = entrance["bety"]

    Mx_matrix_rows = []
    My_matrix_rows = []
    Mxy_matrix_rows = []

    for otr in otrs:
        delta_mux = otrs[otr]["mux"] - entrance["mux"]
        delta_muy = otrs[otr]["muy"] - entrance["muy"]
        R11_x = np.sqrt((otrs[otr]["betx"])/beta_x_0) * (math.cos(delta_mux) + entrance["alpx"] * math.sin(delta_mux))
        R12_x = np.sqrt(beta_x_0 * otrs[otr]["betx"]) * math.sin(delta_mux)

        R33_y = np.sqrt((otrs[otr]["bety"])/beta_y_0) * (math.cos(delta_muy) + entrance["alpy"] * math.sin(delta_muy))
        R34_y = np.sqrt(beta_y_0 * otrs[otr]["bety"]) * math.sin(delta_muy)

        Mx_matrix_rows.append([R11_x**2, 2*R11_x*R12_x, R12_x**2])
        My_matrix_rows.append([R33_y**2, 2*R33_y*R34_y, R34_y**2])
        Mxy_matrix_rows.append([R11_x*R33_y, R11_x * R34_y, R12_x * R33_y, R12_x * R34_y])

    Mx = np.array(Mx_matrix_rows)
    My = np.array(My_matrix_rows)
    Mxy = np.array(Mxy_matrix_rows)
    return Mx, My, Mxy

def compute_beam_matrix():
    entrance_name, entrance, otrs = get_data_from_twiss_file()
    emitt_x = 2e-9 # m * rad
    emitt_y = 1.18e-11 # m * rad
    beta_x_0 = entrance["betx"]
    beta_y_0 = entrance["bety"]
    alpha_x_0 = entrance["alpx"]
    alpha_y_0 = entrance["alpy"]
    gamma_y_0 = (1+alpha_y_0**2)/beta_y_0
    gamma_x_0 = (1+alpha_x_0**2)/beta_x_0

    # beam_matrix = np.block([emitt_x * beta_x_0, emitt_y * (-alpha_x_0)],
    #                                 [-alpha_x_0, gamma_x_0])
    sigma_1 = emitt_x * beta_x_0
    sigma_2 = emitt_x * (-alpha_x_0)
    sigma_5 = emitt_x * gamma_x_0
    sigma_8 = emitt_y * beta_y_0
    sigma_9 = emitt_y * (-alpha_y_0)
    sigma_10 = emitt_y * gamma_y_0

    Sigma_xy_beam = {
        "sigma_1" : sigma_1,
        "sigma_2" : sigma_2,
        "sigma_5" : sigma_5,
        "sigma_8" : sigma_8,
        "sigma_9" : sigma_9,
        "sigma_10" : sigma_10,
    }

    # sigma3, 4, 6 and 7 are zero if there's no coupling
    # how to calculate them?

    return Sigma_xy_beam


def setup_beam0_and_lattice():
    # sigma_i = R * sigma_0 * R^t
    # sigma_xi = sqrt(sigma_i_11)
    # sigma_yi = sqrt(sigma_i_33)
    # R is a linear transfer matrix

    sigma_x = []
    sigma_y = []
    lattice = rft.Lattice('Ext_ATF2/ATF2_EXT_FF_v5.2.twiss')
    population = 2e10
    mass = rft.electronmass
    charge = -1
    Pref = 1.2999999e3 # 1.3 GeV/c
    Twiss = rft.Bunch6dT_twiss()
    Twiss.beta_x = 6.848560987        # m
    Twiss.beta_y = 2.935758992         # m
    Twiss.alpha_x = 1.108024744
    Twiss.alpha_y = -1.907222942
    Twiss.emitt_x = 2e-9     # m rad
    Twiss.emitt_y = 1.18e-11 # m rad
    nParticles = 10000 # number of macroparticles
    B0 = rft.Bunch6dT(mass, population, charge, Pref, Twiss, nParticles)
    #lost particles function
    return lattice, B0

def track_to_otr(lattice, bunch, element_name):
    L0 = rft.Lattice()

    found = False
    n_elem = lattice.get_length()

    for i in range(653):
        elem = lattice[i]
        L0.append_ref(elem)
        if getattr(elem, "name", "") == element_name:
            found = True
            break
    return L0.track(bunch)

def measure_sigmas():
    otr_names = ['OTR0X', 'OTR1X', 'OTR2X', 'OTR3X']
    lattice, _ = setup_beam0_and_lattice()
    sigma_x = []
    sigma_y = []

    for name in otr_names:
        _, B0 = setup_beam0_and_lattice()
        Bout = track_to_otr(lattice, B0, name)

        M = Bout.get_phase_space("%x %y")
        sigma_x.append((M[:, 0]))
        sigma_y.append((M[:, 1]))

    return np.array(sigma_x), np.array(sigma_y)

def calculate_sigmas(Mx, My, Mxy, Sigma_xy_beam):
    # sigma_i = R * sigma_0 * R^t

    # sigma_xi = sqrt(sigma_i_11)
    # sigma_yi = sqrt(sigma_i_33)

    # R is a linear transfer matrix

    sigma1 = Sigma_xy_beam["sigma_1"]
    sigma2 = Sigma_xy_beam["sigma_2"]
    sigma5 = Sigma_xy_beam["sigma_5"]
    sigma8 = Sigma_xy_beam["sigma_8"]
    sigma9 = Sigma_xy_beam["sigma_9"]
    sigma10 = Sigma_xy_beam["sigma_10"]

    sigma_p_x2 = Mx @ np.array([sigma1,sigma2,sigma5]) # @ is a matrix multiplication, * is element wise
    sigma_p_y2 = My @ np.array([sigma8, sigma9, sigma10])

    sigma_x_i = np.sqrt(sigma_p_x2)
    sigma_y_i = np.sqrt(sigma_p_y2)

    return sigma_x_i, sigma_y_i

def solve_least_squares(Mx, My, Mxy, sigma_x_i, sigma_y_i):
    sigma_x2 = sigma_x_i **2
    sigma_y2 = sigma_y_i **2

    sigma_x_meas,*_ = np.linalg.lstsq(Mx, sigma_x2, rcond=None)
    sigma_y_meas, *_ = np.linalg.lstsq(My, sigma_y2, rcond=None)

    sigma1,sigma2,sigma5 = sigma_x_meas
    sigma8,sigma9,sigma10 = sigma_y_meas

    emittance_x = np.sqrt(np.abs(sigma1 * sigma5-sigma2**2))
    emittance_y = np.sqrt(np.abs(sigma8 * sigma10 - sigma9**2))

    beta_x = sigma1 / emittance_x
    beta_y = sigma8 / emittance_y

    alpha_x = -sigma2 / emittance_x
    alpha_y = -sigma9 / emittance_y

    gamma_x = sigma5 / emittance_x
    gamma_y = sigma10 / emittance_y

    return emittance_x, emittance_y, beta_x, beta_y, alpha_x, alpha_y, gamma_x, gamma_y

if __name__ == "__main__":
    entrance_name, entrance, otrs = get_data_from_twiss_file()
    # print("Entrance:", entrance_name, entrance)
    # print("OTRs:", otrs)
    Mx,My,Mxy = compute_transport_matrix()
    Sigma_xy_beam = compute_beam_matrix()

    sigma_x_i, sigma_y_i=calculate_sigmas(Mx, My, Mxy, Sigma_xy_beam)
    #sigma_x_i, sigma_y_i=measure_sigmas()

    emittance_x, emittance_y, beta_x, beta_y, alpha_x, alpha_y, gamma_x, gamma_y = solve_least_squares(Mx, My, Mxy, sigma_x_i, sigma_y_i)
    #print(emittance_x, emittance_y, beta_x, beta_y, alpha_x, alpha_y, gamma_x, gamma_y)
    print("emittance_x", emittance_x)
    print("emittance_y", emittance_y)
    print("beta_x", beta_x)
    print("beta_y", beta_y)


