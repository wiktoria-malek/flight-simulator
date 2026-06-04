import argparse
import os
import re
import sys
from glob import glob

import numpy as np

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
    
from Backend.State import State

QM_FILE_RE = re.compile(r"DATA_(.+)_(x|y)_(p|m)(\d+)\.pkl$")


def finite_max_abs(values):
    arr = np.asarray(values, dtype=float).ravel()
    arr = arr[np.isfinite(arr)]
    return float(np.max(np.abs(arr))) if arr.size else np.nan


def finite_median_abs(values):
    arr = np.asarray(values, dtype=float).ravel()
    arr = arr[np.isfinite(arr)]
    return float(np.median(np.abs(arr))) if arr.size else np.nan


def find_qm_pairs(data_dir):
    pairs = {}
    for path in glob(os.path.join(data_dir, "DATA_*.pkl")):
        m = QM_FILE_RE.match(os.path.basename(path))
        if not m:
            continue
        quad, axis, sign, iteration = m.groups()
        pairs.setdefault((quad, axis, iteration), {})[sign] = path

    return [
        (key, files["p"], files["m"])
        for key, files in sorted(pairs.items())
        if "p" in files and "m" in files
    ]


def choose_bpms(state, requested_bpms=None):
    all_names = [str(n) for n in state.bpms.get("names", [])]
    if requested_bpms:
        chosen = [str(n) for n in requested_bpms if str(n) in all_names]
        if chosen:
            return chosen
    return all_names


def get_quad_coordinate_um(state, quad, axis):
    q = state.get_quadrupoles(quad)
    if len(q.get("names", [])) == 0:
        return np.nan
    key = "xdes" if axis == "x" else "ydes"
    vals = np.asarray(q.get(key, []), dtype=float).ravel()
    return float(vals[0]) if vals.size else np.nan


def analyse_pair(quad, axis, plus_file, minus_file, requested_bpms=None):
    sp = State(filename=plus_file)
    sm = State(filename=minus_file)

    bpms = choose_bpms(sp, requested_bpms)
    op = sp.get_orbit(bpms)
    om = sm.get_orbit(bpms)

    q_plus_um = get_quad_coordinate_um(sp, quad, axis)
    q_minus_um = get_quad_coordinate_um(sm, quad, axis)
    denom_um = q_plus_um - q_minus_um
    denom_mm = denom_um * 1e-3

    dx_orbit_mm = np.asarray(op["x"], dtype=float) - np.asarray(om["x"], dtype=float)
    dy_orbit_mm = np.asarray(op["y"], dtype=float) - np.asarray(om["y"], dtype=float)

    with np.errstate(divide="ignore", invalid="ignore"):
        rx_mm_per_um = dx_orbit_mm / denom_um
        ry_mm_per_um = dy_orbit_mm / denom_um
        rx_mm_per_mm = dx_orbit_mm / denom_mm
        ry_mm_per_mm = dy_orbit_mm / denom_mm

    print("=" * 100)
    print(f"quad={quad}, axis={axis}")
    print(f"plus : {os.path.basename(plus_file)}")
    print(f"minus: {os.path.basename(minus_file)}")
    print(f"q_plus  = {q_plus_um:.9g} um")
    print(f"q_minus = {q_minus_um:.9g} um")
    print(f"denom_um = {denom_um:.9g} um")
    print(f"denom_mm = {denom_mm:.9g} mm")
    print(f"BPMs used: {len(bpms)}")
    print(f"max |x_plus - x_minus| = {finite_max_abs(dx_orbit_mm):.9g} mm")
    print(f"max |y_plus - y_minus| = {finite_max_abs(dy_orbit_mm):.9g} mm")
    print("--- Correct units for QM BBA: mm/um ---")
    print(f"max    |Rx| = {finite_max_abs(rx_mm_per_um):.9g} mm/um")
    print(f"median |Rx| = {finite_median_abs(rx_mm_per_um):.9g} mm/um")
    print(f"max    |Ry| = {finite_max_abs(ry_mm_per_um):.9g} mm/um")
    print(f"median |Ry| = {finite_median_abs(ry_mm_per_um):.9g} mm/um")
    print("--- Suspicious if GUI matches these: mm/mm ---")
    print(f"max    |Rx| = {finite_max_abs(rx_mm_per_mm):.9g} mm/mm")
    print(f"median |Rx| = {finite_median_abs(rx_mm_per_mm):.9g} mm/mm")
    print(f"max    |Ry| = {finite_max_abs(ry_mm_per_mm):.9g} mm/mm")
    print(f"median |Ry| = {finite_median_abs(ry_mm_per_mm):.9g} mm/mm")

    return {
        "quad": quad,
        "axis": axis,
        "denom_um": denom_um,
        "max_rx_mm_per_um": finite_max_abs(rx_mm_per_um),
        "max_ry_mm_per_um": finite_max_abs(ry_mm_per_um),
        "max_rx_mm_per_mm": finite_max_abs(rx_mm_per_mm),
        "max_ry_mm_per_mm": finite_max_abs(ry_mm_per_mm),
    }


def main():
    parser = argparse.ArgumentParser(description="Debug QM SysID response matrix units.")
    parser.add_argument("data_dir", help="Folder with QM SysID DATA_*.pkl files")
    parser.add_argument("--quad", default=None, help="Optional mover name, e.g. QD0FF")
    parser.add_argument("--axis", choices=["x", "y"], default=None)
    parser.add_argument("--iteration", default=None, help="Optional iteration, e.g. 0000")
    parser.add_argument("--bpms", nargs="*", default=None)
    parser.add_argument("--max-pairs", type=int, default=5)
    args = parser.parse_args()

    data_dir = os.path.expanduser(os.path.expandvars(args.data_dir))
    pairs = find_qm_pairs(data_dir)

    if args.quad:
        pairs = [p for p in pairs if p[0][0] == args.quad]
    if args.axis:
        pairs = [p for p in pairs if p[0][1] == args.axis]
    if args.iteration:
        pairs = [p for p in pairs if p[0][2] == args.iteration]

    if not pairs:
        print("No complete QM p/m pairs found.")
        print("Expected e.g. DATA_QD0FF_x_p0000.pkl and DATA_QD0FF_x_m0000.pkl")
        return

    print(f"Found {len(pairs)} complete QM p/m pairs in: {data_dir}")

    summaries = []
    for (quad, axis, iteration), plus_file, minus_file in pairs[: args.max_pairs]:
        summaries.append(analyse_pair(quad, axis, plus_file, minus_file, args.bpms))

    print("=" * 100)
    print("SUMMARY")
    for s in summaries:
        print(
            f"{s['quad']} {s['axis']}: denom={s['denom_um']:.6g} um, "
            f"maxR(mm/um)=({s['max_rx_mm_per_um']:.6g}, {s['max_ry_mm_per_um']:.6g}), "
            f"maxR(mm/mm)=({s['max_rx_mm_per_mm']:.6g}, {s['max_ry_mm_per_mm']:.6g})"
        )


if __name__ == "__main__":
    main()