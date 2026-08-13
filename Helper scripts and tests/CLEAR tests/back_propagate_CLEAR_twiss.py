from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


S_STLINE_START = 0.0
S_QFD0350_ENTRANCE = 18.2834


@dataclass(frozen=True)
class Twiss:
    beta: float
    alpha: float
    emittance: float

REFERENCE_TWISS = {
    "x": Twiss(beta=17.9, alpha=0.236, emittance=12.7),
    "y": Twiss(beta=8.07, alpha=-1.72, emittance=4.34),
}


def covariance(twiss: Twiss) -> np.ndarray:
    gamma = (1.0 + twiss.alpha**2) / twiss.beta
    return twiss.emittance * np.array(
        [[twiss.beta, -twiss.alpha], [-twiss.alpha, gamma]], dtype=float
    )


def twiss_from_covariance(sigma: np.ndarray) -> Twiss:
    emittance = float(np.sqrt(np.linalg.det(sigma)))
    return Twiss(
        beta=float(sigma[0, 0] / emittance),
        alpha=float(-sigma[0, 1] / emittance),
        emittance=emittance,
    )


def drift_matrix(length: float) -> np.ndarray:
    return np.array([[1.0, length], [0.0, 1.0]])


def propagate_twiss(twiss: Twiss, matrix: np.ndarray) -> Twiss:
    return twiss_from_covariance(matrix @ covariance(twiss) @ matrix.T)


def back_propagate_to_stline(
    twiss_at_qfd350: Twiss,
    length: float = S_QFD0350_ENTRANCE - S_STLINE_START,
) -> Twiss:
    return propagate_twiss(twiss_at_qfd350, drift_matrix(-length))


def beta_in_drift(twiss_at_start: Twiss, distances: np.ndarray) -> np.ndarray:
    """Evaluate beta(s) after a drift, starting from the supplied Twiss."""
    gamma = (1.0 + twiss_at_start.alpha**2) / twiss_at_start.beta
    return (
        twiss_at_start.beta
        - 2.0 * twiss_at_start.alpha * distances
        + gamma * distances**2
    )


def print_twiss(label: str, twiss: Twiss) -> None:
    print(
        f"{label:<24} beta = {twiss.beta:10.6f} m, "
        f"alpha = {twiss.alpha:10.6f}, "
        f"emittance = {twiss.emittance:8.4f} mm mrad"
    )


def main() -> None:
    length = S_QFD0350_ENTRANCE - S_STLINE_START
    forward_matrix = drift_matrix(length)

    print("CLEAR equivalent Twiss back-propagation")
    print(f"Transport in current simplified model: {length:.4f} m drift\n")

    stline_twiss: dict[str, Twiss] = {}
    for plane, reference in REFERENCE_TWISS.items():
        upstream = back_propagate_to_stline(reference, length)
        recovered = propagate_twiss(upstream, forward_matrix)
        stline_twiss[plane] = upstream

        print(f"Plane {plane}")
        print_twiss("  reference at QFD350", reference)
        print_twiss("  use at STLINE start", upstream)
        print_twiss("  forward check", recovered)
        assert np.allclose(
            [recovered.beta, recovered.alpha, recovered.emittance],
            [reference.beta, reference.alpha, reference.emittance],
            rtol=1e-12,
            atol=1e-12,
        )
        print()

    print("__setup_beam0:")
    print(f"T.beta_x = {stline_twiss['x'].beta:.6f}")
    print(f"T.alpha_x = {stline_twiss['x'].alpha:.6f}")
    print(f"T.emitt_x = {stline_twiss['x'].emittance:.4f}")
    print(f"T.beta_y = {stline_twiss['y'].beta:.6f}")
    print(f"T.alpha_y = {stline_twiss['y'].alpha:.6f}")
    print(f"T.emitt_y = {stline_twiss['y'].emittance:.4f}")

if __name__ == "__main__":
    main()
