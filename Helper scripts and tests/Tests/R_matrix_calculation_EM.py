import numpy as np
import RF_Track as rft

I = np.loadtxt("input_2000.txt")
O = np.loadtxt("output_2000.txt")

mass = rft.electronmass  # MeV/c^2
momentum = 1300  # MeV/c

beta_gamma = momentum / mass

emitt_x = I[:, 0] / beta_gamma  # mm.mrad, geometric emittance
emitt_y = I[:, 3] / beta_gamma  # mm.mrad, geometric emittance
beta_x = I[:, 1]
beta_y = I[:, 4]
alpha_x = I[:, 2]
alpha_y = I[:, 5]

S1_x = O[:, 0]  # mm
S1_y = O[:, 1]
S2_x = O[:, 2]
S2_y = O[:, 3]
S3_x = O[:, 4]
S3_y = O[:, 5]
S4_x = O[:, 6]
S4_y = O[:, 7]

gamma_x = (1 + alpha_x**2) / beta_x
gamma_y = (1 + alpha_y**2) / beta_y

ones = np.ones(len(I))

Cx = np.column_stack((beta_x * emitt_x, -alpha_x * emitt_x, gamma_x * emitt_x, ones))
Cy = np.column_stack((beta_y * emitt_y, -alpha_y * emitt_y, gamma_y * emitt_y, ones))

Bx = np.column_stack((S1_x, S2_x, S3_x, S4_x)) ** 2
By = np.column_stack((S1_y, S2_y, S3_y, S4_y)) ** 2

Rx = Bx.T @ np.linalg.pinv(Cx.T)
Ry = By.T @ np.linalg.pinv(Cy.T)

print("Rx =")
print(Rx)

print("Ry =")
print(Ry)