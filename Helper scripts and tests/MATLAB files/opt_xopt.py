import numpy as np
import matplotlib.pyplot as plt
import RF_Track as rft

from xopt import Xopt
from xopt.vocs import VOCS, select_best
from xopt.evaluator import Evaluator
from xopt.generators.bayesian import ExpectedImprovementGenerator

# Simulation-specific scripts
from load_beam_ASTRA import load_beam_ASTRA
from create_bunch import create_bunch

# Customize the SC algorithm.
SC = rft.SpaceCharge_PIC_FreeSpace (16, 16, 16) # The three inputs are the number of mesh cells in X, Y, and Z.
SC.set_smooth (0.5) # set smooth factor
SC.set_mirror (0.0) # set position of cathode

# Set RF-Track to use 'SC' for space-charge calculations
rft.cvar.SC_engine = SC

# Create the bunch
Q_pC = 700
beam0_rft = create_bunch(Q_pC=Q_pC, Nparticles=50000)

# Setup the Volume
def setup_volume(gun_gradient, gun_phase, sol_field, linac_gradient):

    sparcmap = 'Gun_Ez_2021_Astra_norm1_fix.txt'
    linacmap = 'esrf_linac_cband_equal_spacing_fix.txt'
    solmap = 'esrf_sol_fix.txt'

    z, ez = np.loadtxt(sparcmap, unpack=True)

    freq = 2.856e9
    dz = z[1] - z[0]
    length = z[-1] - z[0]

    egun = rft.RF_FieldMap_1d (gun_gradient * ez, dz, -1, freq, 1)
    egun.set_phid(gun_phase)

    zsol, sol = np.loadtxt(solmap, unpack=True)
    dzsol = zsol[1] - zsol[0]

    solenoid = rft.Static_Magnetic_FieldMap_1d (sol * sol_field, dzsol)

    zlinac, linac = np.loadtxt(linacmap, unpack=True)

    dzlinac = zlinac[1] - zlinac[0]
    linac_length = zlinac[-1] - zlinac[0]

    linacphase = 0*-43.01491830703458

    linac_rft = rft.RF_FieldMap_1d (linac_gradient * (linac), dzlinac, linac_length, 5.712e9, 1)
    linac_rft.set_phid(linacphase)

    linacphase2 = 0*259.9850816929654

    linac_rft2 = rft.RF_FieldMap_1d (linac_gradient * (linac), dzlinac, linac_length, 5.712e9, 1)
    linac_rft2.set_phid(linacphase2)
    
    c_pos = [ 0.0, 1.85018942, 3.01314042 ]

    volume_egun = rft.Volume()
    volume_egun.add(egun, 0, 0, c_pos[0])
    volume_egun.add(solenoid, 0, 0, 0.204, 'center')
    volume_egun.add(linac_rft, 0, 0, c_pos[1])
    volume_egun.add(linac_rft2, 0, 0, c_pos[2])
    
    volume_egun.set_s0(0.0) # entrance boundary
    #volume_egun.set_s1(c_pos[1]) # exit boundary, stops at the entrance of the first linac structure
    volume_egun.set_s1(4.576) # exit boundary

    volume_egun.odeint_algorithm = 'rk2' # pick your favourite algorithm, 'rk2', 'rkf45', 'leapfrog', and 'analytic' are valid options
    volume_egun.odeint_epsabs = 1e-6
    volume_egun.dt_mm = 0.5 # mm/c, integration step size
    volume_egun.sc_dt_mm = 0.5 # mm/c, the time step of the space-charge effect calculation
    volume_egun.emission_nsteps = 50
    volume_egun.emission_range = 50

    return volume_egun

def track_emittance(X, beam0_rft):
    gun_gradient = 120e6
    gun_phase = X[0]
    sol_field = X[1]
    linac_gradient = 135e6

    volume_egun = setup_volume(gun_gradient, gun_phase, sol_field, linac_gradient)
    volume_egun.autophase(beam0_rft)

    volume_egun.track(beam0_rft)
    I1 = volume_egun.get_bunch_at_s1().get_info()
    M = I1.emitt_4d

    print(f'{gun_phase}, {sol_field} => {I1.sigma_x}, {I1.emitt_4d}')
    
    return M

# Define the merit function
merit = lambda X: track_emittance(X, beam0_rft)

# Xopt starts here
def evaluate(inputs):
    x1 = inputs["x1"]
    x2 = inputs["x2"]

    # Here you would call Octave, RF-Track, a script, or a control-system measurement
    f = merit([ x1, x2 ])

    return {"f": f}

vocs = VOCS(
    variables={
        "x1": [-5.0, 0.0],
        "x2": [0.28, 0.30],
    },
    objectives={"f": "MINIMIZE"},
)

generator = ExpectedImprovementGenerator(vocs=vocs)
evaluator = Evaluator(function=evaluate)

X = Xopt(generator=generator, evaluator=evaluator, vocs=vocs)

# Initial points
X.random_evaluate(5)

# Iterations
for _ in range(30):
    X.step()

print(X.data)
best = select_best(X.vocs, X.data)
print(f"Current best: f({best[2]}) = {best[1].item():.6f}")
    
