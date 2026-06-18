import os
import numpy as np

'''
LinearResponse - pure mathematics behind linear response approach
linear_response_engine.py - using this mathematics on session from GUI
'''
class LinearResponse:
    def __init__(self, coefficients_path=None, dataset_path=None):
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))

        if coefficients_path is None:
            coefficients_path = os.path.join(
                project_root,
                "MachineLearning",
                "R_matrix_recovered_coefficients.npz",
            )

        if dataset_path is None:
            dataset_path = os.path.join(
                project_root,
                "MachineLearning",
                "R_matrix_dataset_fixedK1.npz",
            )

        self.coefficients_path = coefficients_path
        self.dataset_path = dataset_path

        if os.path.isfile(self.coefficients_path):
            self._load_coefficients(self.coefficients_path)
        elif os.path.isfile(self.dataset_path):
            self.fit_coefficients_from_R_dataset(self.dataset_path)
            self.save_coefficients(self.coefficients_path)
        else:
            raise FileNotFoundError(
                "Linear response data not found. Expected either "
                f"{self.coefficients_path} or {self.dataset_path}."
            )

    def _load_coefficients(self, path):
        data = np.load(path, allow_pickle=True)
        self.screens = [str(s) for s in data["screens"]]
        self.Rx = np.asarray(data["Rx_fit"], dtype=float)
        self.Ry = np.asarray(data["Ry_fit"], dtype=float)

    def save_coefficients(self, path=None):
        if path is None:
            path = self.coefficients_path
        os.makedirs(os.path.dirname(path), exist_ok=True)
        np.savez(
            path,
            screens=np.asarray(self.screens),
            Rx_fit=self.Rx,
            Ry_fit=self.Ry,
        )

    def fit_coefficients_from_R_dataset(self, dataset_path=None):
        if dataset_path is None:
            dataset_path = self.dataset_path

        dataset = np.load(dataset_path, allow_pickle=True)
        I = np.asarray(dataset["X"], dtype=float)
        O = np.asarray(dataset["Y"], dtype=float)
        self.screens = [str(s) for s in dataset["screens"]]

        beta_gamma = self._get_beta_gamma(dataset)

        emit_x = I[:, 0] / beta_gamma
        beta_x = I[:, 1]
        alpha_x = I[:, 2]
        gamma_x = (1.0 + alpha_x**2) / beta_x

        emit_y = I[:, 3] / beta_gamma
        beta_y = I[:, 4]
        alpha_y = I[:, 5]
        gamma_y = (1.0 + alpha_y**2) / beta_y

        ones = np.ones(len(I))
        Cx = np.column_stack((beta_x * emit_x, -alpha_x * emit_x, gamma_x * emit_x, ones))
        Cy = np.column_stack((beta_y * emit_y, -alpha_y * emit_y, gamma_y * emit_y, ones))

        Bx = O[:, 0::2]**2
        By = O[:, 1::2]**2

        self.Rx = np.linalg.lstsq(Cx, Bx, rcond=None)[0].T
        self.Ry = np.linalg.lstsq(Cy, By, rcond=None)[0].T

        return self.Rx, self.Ry

    @staticmethod
    def _get_beta_gamma(dataset):
        if "beta_gamma" in dataset.files:
            return float(dataset["beta_gamma"])
        return 1300.0 / 0.51099895

    def predict_sigma2_from_twiss_set(
        self,
        screens,
        emit_x_norm,
        beta_x0,
        alpha_x0,
        emit_y_norm,
        beta_y0,
        alpha_y0,
        beta_gamma,
    ):
        emit_x_geom = float(emit_x_norm) / float(beta_gamma)
        emit_y_geom = float(emit_y_norm) / float(beta_gamma)

        beta_x0 = float(beta_x0)
        alpha_x0 = float(alpha_x0)
        beta_y0 = float(beta_y0)
        alpha_y0 = float(alpha_y0)

        gamma_x = (1.0 + alpha_x0**2) / beta_x0
        gamma_y = (1.0 + alpha_y0**2) / beta_y0

        Cx = np.array([beta_x0 * emit_x_geom, -alpha_x0 * emit_x_geom, gamma_x * emit_x_geom, 1.0])
        Cy = np.array([beta_y0 * emit_y_geom, -alpha_y0 * emit_y_geom, gamma_y * emit_y_geom, 1.0])

        idx = [self.screens.index(str(screen)) for screen in screens]

        pred_x = Cx @ self.Rx[idx].T
        pred_y = Cy @ self.Ry[idx].T

        return pred_x.reshape(1, -1), pred_y.reshape(1, -1)

    def solve_twiss_from_measured_sigma2(self, screens, sigma2_x, sigma2_y, beta_gamma):
        idx = [self.screens.index(str(screen)) for screen in screens]

        if len(idx) < 3:
            raise RuntimeError("At least 3 screens are required for direct linear R-response fit.")

        Rx = self.Rx[idx]
        Ry = self.Ry[idx]

        Mx = Rx[:, :3] # R11^2 2R111R12 R12^2
        My = Ry[:, :3]

        yx = np.asarray(sigma2_x, dtype=float).reshape(-1) - Rx[:, 3]
        yy = np.asarray(sigma2_y, dtype=float).reshape(-1) - Ry[:, 3]

        px = np.linalg.lstsq(Mx, yx, rcond=None)[0]
        py = np.linalg.lstsq(My, yy, rcond=None)[0]

        emit_x = np.sqrt(px[0] * px[2] - px[1] ** 2)
        beta_x0 = px[0] / emit_x
        alpha_x0 = -px[1] / emit_x

        emit_y = np.sqrt(py[0] * py[2] - py[1] ** 2)
        beta_y0 = py[0] / emit_y
        alpha_y0 = -py[1] / emit_y

        return {
            "emit_x": emit_x,
            "emit_y": emit_y,
            "emit_x_norm": emit_x * beta_gamma,
            "emit_y_norm": emit_y * beta_gamma,
            "beta_x0": beta_x0,
            "alpha_x0": alpha_x0,
            "beta_y0": beta_y0,
            "alpha_y0": alpha_y0,
            "pred_x": (Mx @ px + Rx[:, 3]).reshape(1, -1),
            "pred_y": (My @ py + Ry[:, 3]).reshape(1, -1),
        }