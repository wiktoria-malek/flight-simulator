# -*- coding: utf-8 -*-
"""
Liniac_Opt.py

Linac auto tuning GUI + worker.

Improvements (2026-01):
- Use BIM:L0_nparticles as upstream and selectable downstream ICT (LN0/DR/GUN/LNE/BTM/BTE) for transmission.
- Log additional ICTs (GUN/LNE/BTM/BTE) at every evaluation point.
- Always wait settle_sec (default 5s) after changing any PV before reading ICTs.
-nparticles Timing scan after klystron phase scan:
    PV: EVE_LINAC:OUT0:SetData  [ns], step=11.2ns, range=±15 steps around current
- Add Group-LBO mode (discrete / quantized to the same step sizes as sequential scans).
  Groups: L1–L4, L5–L8, Timing, QA, QM (only checked groups run, in this order).
"""

import sys
import time
import datetime
import csv
import math
import json
from pathlib import Path
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple, Optional

import numpy as np

from PyQt6.QtCore import QThread, QTimer, pyqtSignal, Qt
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QCheckBox, QLabel, QFileDialog, QTextEdit, QGroupBox,
    QMessageBox, QDoubleSpinBox, QSpinBox, QComboBox, QTabWidget, QSizePolicy, QLineEdit
)
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from Interfaces.ATF2.InterfaceATF2_Linac import InterfaceATF2_Linac

# ----------------------------
# Scan defaults (same values used by Sequential and Group-LBO)
# ----------------------------
PHASE_HALF_RANGE_DEG = 8.0
PHASE_STEP_DEG = 1.0

GUN_PHASE_HALF_RANGE_DEG = 5.0
GUN_PHASE_STEP_DEG = 0.1
L0_PHASE_HALF_RANGE_DEG = 5.0
L0_PHASE_STEP_DEG = 0.1
SOLENOIDE_MIN_A = 80.0
SOLENOIDE_MAX_A = 125.0
SOLENOIDE_STEP_A = 0.5

QA_HALF_RANGE_A = 1.0
QA_STEP_A = 0.05

QM_HALF_RANGE_A = 2.0
QM_STEP_A = 0.2

TIMING_STEP_NS = 11.2
TIMING_HALF_STEPS = 10  # ±15 steps

SETTLE_SEC_DEFAULT = 5.0

TARGET_LABELS = {
    "gun_sol_l0": "GUN, Solenoid, L0",
    "kly_phase": "Klystron phase",
    "kly_group_1": "Group 1 (L1-L4)",
    "kly_group_2": "Group 2 (L5-L8)",
    "timing": "Timing",
    "qa": "QA",
    "qm": "QM",
}
KLY_GROUP_1_SPECS = [
    (f"L{i}", f"CM{i}L:phaseWrite", f"CM{i}L:phaseRead", "deg")
    for i in range(1, 5)
]
KLY_GROUP_2_SPECS = [
    (f"L{i}", f"CM{i}L:phaseWrite", f"CM{i}L:phaseRead", "deg")
    for i in range(5, 9)
]
TARGET_VALUE_SPECS = {
    "gun_sol_l0": [
        ("GUN", "RFGUN:PHASE_WRITE", None, "deg"),
        ("Solenoid", "SOLENOIDE:internalCurrentWrite", None, "A"),
        ("L0", "CM0L:phaseWrite", None, "deg"),
    ],
    "kly_group_1": KLY_GROUP_1_SPECS,
    "kly_group_2": KLY_GROUP_2_SPECS,
    "timing": [("Timing", "EVE_LINAC:OUT0:SetData", None, "ns")],
    "qa": [(f"QA{i}L", f"QA{i}L:currentWrite", f"QA{i}L:currentRead", "A") for i in range(1, 6)],
    "qm": [(f"QM{i}L", f"QM{i}L:currentWrite", f"QM{i}L:currentRead", "A") for i in range(1, 4)],
}
RESTORE_PVS = [
    "RFGUN:PHASE_WRITE",
    "SOLENOIDE:internalCurrentWrite",
    "CM0L:phaseWrite",
    "EVE_LINAC:OUT0:SetData",
] + [f"CM{i}L:phaseWrite" for i in range(1, 9)] + [f"QA{i}L:currentWrite" for i in range(1, 6)] + [
    f"QM{i}L:currentWrite" for i in range(1, 4)
]


def _format_machine_value(value: float, unit: str) -> str:
    if not np.isfinite(float(value)):
        return "-"
    unit = str(unit)
    if unit == "deg":
        return f"{float(value):+.1f} {unit}"
    if unit == "ns":
        return f"{float(value):+.1f} {unit}"
    return f"{float(value):.3f} {unit}"


def build_display_value_texts(pv_values: Dict[str, float]) -> Dict[str, str]:
    texts: Dict[str, str] = {}
    for key, specs in TARGET_VALUE_SPECS.items():
        parts = []
        for label, pv_write, _pv_read, unit in specs:
            parts.append(f"{label}={_format_machine_value(pv_values.get(pv_write, float('nan')), unit)}")
        texts[key] = ", ".join(parts)
    return texts


@dataclass
class EvalResult:
    t_iso: str
    device_label: str
    pv_name: str
    set_value: float
    ict: Dict[str, float]          # L0/DR/GUN/LNE/BTM/BTE + Ttot
    score: float
    note: str = ""
    group: str = ""
    mode: str = ""


class OptimizationWorker(QThread):
    log_signal = pyqtSignal(str)
    status_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(dict)
    finished_signal = pyqtSignal()

    def __init__(self, config: dict, save_dir: str | Path):
        super().__init__()
        self.config = config
        self.save_dir = Path(save_dir)
        self.is_running = True

        self.settle_sec = float(config.get("settle_sec", SETTLE_SEC_DEFAULT))
        self.score_w_ttot = float(config.get("score_w_ttot", 1.0))
        self.score_w_downstream = float(config.get("score_w_downstream", 1.0))
        self.downstream_ict = str(config.get("downstream_ict", "DR")).upper()
        if self.downstream_ict == "L0":
            self.downstream_ict = "LN0"
        self._downstream_ict_key = "L0" if self.downstream_ict == "LN0" else self.downstream_ict
        if self._downstream_ict_key not in ("L0", "DR", "GUN", "LNE", "BTM", "BTE"):
            self.downstream_ict = "DR"
            self._downstream_ict_key = "DR"
        self.mode = str(config.get("mode", "SEQUENTIAL")).upper()
        self.reuse_initial_eval = bool(config.get("reuse_initial_eval", True))
        self._initial_snapshot = None
        self._initial_eval_consumed = False
        self._eval_counter = 0
        self._current_pv_values: Dict[str, float] = {}
        self.resume_csv_path = Path(str(config.get("resume_csv_path", "")).strip()).expanduser() if str(config.get("resume_csv_path", "")).strip() else None
        self._resume_seq_rows: Dict[Tuple[str, str, str], List[Dict[str, Any]]] = {}
        self._resume_group_rows: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}

        # Fixed machine interface for Linac operations
        self.interface = InterfaceATF2_Linac(nsamples=1)

        # Date folder + timestamped run files
        self.run_tag = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        self.date_tag = self.run_tag.split("_")[0]
        self.run_dir = self.save_dir / self.date_tag
        self.csv_path = self.run_dir / f"LiniacOptimization_Log_{self.run_tag}.csv"
        self._init_csv()
        self._load_resume_rows()

    # ----------------------------
    # CSV / logging
    # ----------------------------
    def _init_csv(self):
        self.run_dir.mkdir(parents=True, exist_ok=True)
        with open(self.csv_path, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow([
                "TimestampISO", "Mode", "Group", "DeviceLabel", "PV",
                "SetValue",
                "ICT_L0", "ICT_DR", "Ttot",
                "ICT_GUN", "ICT_LNE", "ICT_BTM", "ICT_BTE",
                "Score", "ScoreDownstreamICT", "ScoreWeight_Ttot", "ScoreWeight_Downstream", "Note"
            ])

    def _append_csv(self, r: EvalResult):
        ict = r.ict
        with open(self.csv_path, "a", newline="") as f:
            w = csv.writer(f)
            w.writerow([
                r.t_iso, r.mode, r.group, r.device_label, r.pv_name,
                r.set_value,
                ict.get("L0", float("nan")),
                ict.get("DR", float("nan")),
                ict.get("Ttot", float("nan")),
                ict.get("GUN", float("nan")),
                ict.get("LNE", float("nan")),
                ict.get("BTM", float("nan")),
                ict.get("BTE", float("nan")),
                r.score,
                self.downstream_ict,
                self.score_w_ttot,
                self.score_w_downstream,
                r.note
            ])

    def _emit_progress(self, payload: Dict[str, object]):
        self.progress_signal.emit(dict(payload))

    def _emit_group_state(self, group_key: str, state: str):
        self._emit_progress({
            "kind": "group_state",
            "group_key": str(group_key),
            "state": str(state),
        })

    def _emit_display_values(self):
        self._emit_progress({
            "kind": "current_values",
            "display_values": build_display_value_texts(self._current_pv_values),
        })

    def _record_evaluation(self, r: EvalResult, pv_updates: Optional[Dict[str, float]] = None):
        if pv_updates:
            for pv_name, value in pv_updates.items():
                self._current_pv_values[str(pv_name)] = float(value)
        self._eval_counter += 1
        self._emit_progress({
            "kind": "evaluation",
            "eval_index": int(self._eval_counter),
            "group": str(r.group),
            "mode": str(r.mode),
            "score": float(r.score),
            "ttot": float(r.ict.get("Ttot", float("nan"))),
            "downstream_label": str(self.downstream_ict),
            "downstream_value": float(self._downstream_value(r.ict)),
            "display_values": build_display_value_texts(self._current_pv_values),
        })

    def _resume_seq_key(self, mode: str, group: str, pv_name: str) -> Tuple[str, str, str]:
        return (str(mode), str(group), str(pv_name))

    def _resume_group_key(self, mode: str, group: str) -> Tuple[str, str]:
        return (str(mode), str(group))

    def _parse_resume_vector_note(self, note: str) -> Optional[Dict[str, float]]:
        text = str(note or "")
        brace = text.find("{")
        if brace < 0:
            return None
        try:
            raw = json.loads(text[brace:])
        except Exception:
            return None
        out: Dict[str, float] = {}
        try:
            for key, value in dict(raw).items():
                out[str(key)] = float(value)
        except Exception:
            return None
        return out

    def _load_resume_rows(self):
        if self.resume_csv_path is None:
            return
        if not self.resume_csv_path.exists():
            self.log_signal.emit(f"[RESUME] CSV not found: {self.resume_csv_path}")
            return

        row_count = 0
        with open(self.resume_csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for raw in reader:
                if not raw:
                    continue
                try:
                    ict = {
                        "L0": float(raw.get("ICT_L0", "nan")),
                        "DR": float(raw.get("ICT_DR", "nan")),
                        "Ttot": float(raw.get("Ttot", "nan")),
                        "GUN": float(raw.get("ICT_GUN", "nan")),
                        "LNE": float(raw.get("ICT_LNE", "nan")),
                        "BTM": float(raw.get("ICT_BTM", "nan")),
                        "BTE": float(raw.get("ICT_BTE", "nan")),
                    }
                    row = {
                        "t_iso": str(raw.get("TimestampISO", "")),
                        "mode": str(raw.get("Mode", "")),
                        "group": str(raw.get("Group", "")),
                        "device_label": str(raw.get("DeviceLabel", "")),
                        "pv_name": str(raw.get("PV", "")),
                        "set_value": float(raw.get("SetValue", "nan")),
                        "ict": ict,
                        "score": float(raw.get("Score", "nan")),
                        "note": str(raw.get("Note", "")),
                    }
                except Exception:
                    continue

                if row["pv_name"] == "MULTI":
                    vec = self._parse_resume_vector_note(row["note"])
                    if vec:
                        row["vector"] = vec
                        key = self._resume_group_key(row["mode"], row["group"])
                        self._resume_group_rows.setdefault(key, []).append(row)
                        row_count += 1
                else:
                    key = self._resume_seq_key(row["mode"], row["group"], row["pv_name"])
                    self._resume_seq_rows.setdefault(key, []).append(row)
                    row_count += 1

        self.log_signal.emit(f"[RESUME] Loaded {row_count} previous evaluations from {self.resume_csv_path}")

    def _resume_eval_result(self, row: Dict[str, Any]) -> EvalResult:
        return EvalResult(
            t_iso=str(row.get("t_iso", "")),
            device_label=str(row.get("device_label", "")),
            pv_name=str(row.get("pv_name", "")),
            set_value=float(row.get("set_value", float("nan"))),
            ict=dict(row.get("ict", {})),
            score=float(row.get("score", float("nan"))),
            note=str(row.get("note", "")),
            group=str(row.get("group", "")),
            mode=str(row.get("mode", "")),
        )

    def _resume_seq_completed_row(self, mode: str, group: str, pv_name: str) -> Optional[Dict[str, Any]]:
        rows = self._resume_seq_rows.get(self._resume_seq_key(mode, group, pv_name), [])
        done_rows = [row for row in rows if "OPTIMIZED_SET" in str(row.get("note", ""))]
        return done_rows[-1] if done_rows else None

    def _resume_group_completed_row(self, mode: str, group: str) -> Optional[Dict[str, Any]]:
        rows = self._resume_group_rows.get(self._resume_group_key(mode, group), [])
        done_rows = [row for row in rows if "OPTIMIZED_SET" in str(row.get("note", ""))]
        return done_rows[-1] if done_rows else None

    def _resume_scan_candidates(self, mode: str, group: str, pv_name: str, fallback: np.ndarray) -> np.ndarray:
        rows = self._resume_seq_rows.get(self._resume_seq_key(mode, group, pv_name), [])
        values = sorted({round(float(row.get("set_value", float("nan"))), 10) for row in rows if np.isfinite(float(row.get("set_value", float("nan"))))})
        if len(values) < 2:
            return fallback
        values_arr = np.array(values, dtype=float)
        fallback_diffs = np.diff(np.unique(np.asarray(fallback, dtype=float)))
        step = float(np.median(fallback_diffs[fallback_diffs > 0])) if np.any(fallback_diffs > 0) else float("nan")
        if (not np.isfinite(step)) or step <= 0.0:
            diffs = np.diff(values_arr)
            step = float(np.median(diffs[diffs > 0])) if np.any(diffs > 0) else float("nan")
        if (not np.isfinite(step)) or step <= 0.0:
            return fallback
        rebuilt = np.arange(values_arr[0], values_arr[-1] + step * 0.5, step, dtype=float)
        rebuilt = np.unique(np.round(rebuilt, 10))
        return rebuilt if rebuilt.size else fallback

    def _dump_initial_snapshot(self):
        """Dump initial machine/config snapshot for reproducibility."""
        snapshot_path = self.run_dir / f"InitialSnapshot_{self.run_tag}.json"
        setpoints: Dict[str, float] = {}
        for pv in RESTORE_PVS:
            setpoints[pv] = float(self._read_current(pv, None))

        initial_ict = self._read_icts()
        initial_score = self._score(initial_ict)

        data = {
            "timestamp": datetime.datetime.now().isoformat(timespec="seconds"),
            "mode": self.mode,
            "config": self.config,
            "initial_setpoints": setpoints,
            "initial_ict": initial_ict,
            "initial_score": initial_score,
        }
        with open(snapshot_path, "w") as f:
            json.dump(data, f, indent=2)
        self._initial_snapshot = data
        self._current_pv_values = {str(k): float(v) for k, v in setpoints.items()}
        self._emit_display_values()
        self.log_signal.emit(f"[INIT] Snapshot dumped: {snapshot_path}")

    def _try_reuse_initial_point(self, device_label: str, pv_name: str, set_value: float,
                                 mode: str, group: str, note: str) -> Optional[EvalResult]:
        if not self.reuse_initial_eval or self._initial_eval_consumed or (self._initial_snapshot is None):
            return None
        init_set = self._initial_snapshot.get("initial_setpoints", {})
        init_ict = self._initial_snapshot.get("initial_ict", {})
        init_score = float(self._initial_snapshot.get("initial_score", -1e30))
        if pv_name not in init_set:
            return None
        if abs(float(set_value) - float(init_set[pv_name])) > 1e-9:
            return None

        self._initial_eval_consumed = True
        r = EvalResult(
            t_iso=datetime.datetime.now().isoformat(timespec="seconds"),
            device_label=device_label,
            pv_name=pv_name,
            set_value=float(set_value),
            ict=dict(init_ict),
            score=float(init_score),
            note=f"{note}|REUSE_INIT",
            group=group,
            mode=mode,
        )
        self._append_csv(r)
        self._record_evaluation(r, {pv_name: float(set_value)})
        self.log_signal.emit(f"[INIT-REUSE] Reused initial eval for {device_label} ({pv_name}) at x={set_value:.6g}")
        return r

    def _try_reuse_initial_vector(self, labels: List[str], pvs: List[str], x_vec: np.ndarray,
                                  mode: str, group: str, note: str) -> Optional[EvalResult]:
        if not self.reuse_initial_eval or self._initial_eval_consumed or (self._initial_snapshot is None):
            return None
        init_set = self._initial_snapshot.get("initial_setpoints", {})
        init_ict = self._initial_snapshot.get("initial_ict", {})
        init_score = float(self._initial_snapshot.get("initial_score", -1e30))

        for pv, x in zip(pvs, x_vec):
            if pv not in init_set:
                return None
            if abs(float(x) - float(init_set[pv])) > 1e-9:
                return None

        self._initial_eval_consumed = True
        r = EvalResult(
            t_iso=datetime.datetime.now().isoformat(timespec="seconds"),
            device_label=",".join(labels),
            pv_name=",".join(pvs),
            set_value=float("nan"),
            ict=dict(init_ict),
            score=float(init_score),
            note=f"{note}|REUSE_INIT",
            group=group,
            mode=mode,
        )
        self._append_csv(r)
        self._record_evaluation(r, {pv: float(x) for pv, x in zip(pvs, x_vec)})
        self.log_signal.emit(f"[INIT-REUSE] Reused initial vector eval for group {group}")
        return r

    # ----------------------------
    # Stop
    # ----------------------------
    def stop(self):
        self.is_running = False
        self.log_signal.emit("!!! Stop Requested !!!")

    # ----------------------------
    # Measurement
    # ----------------------------
    
    def _read_icts(self) -> Dict[str, float]:
        return self.interface.read_icts_for_optimizer(
            downstream_key=self._downstream_ict_key,
            dr_samples=3,
            dr_interval_s=0.5,
        )

    def _downstream_value(self, ict: Dict[str, float]) -> float:
        return float(ict.get(self._downstream_ict_key, float("nan")))
    
    def _score(self, ict: Dict[str, float]) -> float:
        """
        Weighted score:
        score = w_t * Ttot + w_c * ICT_downstream
        where ICT_downstream is LN0/DR/GUN/LNE/BTM/BTE selected by config.
        """
        T = ict.get("Ttot", float("nan"))
        C = self._downstream_value(ict)

        if not np.isfinite(T) or not np.isfinite(C):
            return -1e30

        return self.score_w_ttot * float(T) + self.score_w_downstream * float(C)

    def _evaluate_point(self, device_label: str, pv_name: str, set_value: float,
                        mode: str, group: str, note: str = "") -> EvalResult:
        self.interface.pv_put(pv_name, set_value)

        # settle (requested: after change, wait a few seconds)
        t0 = time.time()
        while self.is_running and (time.time() - t0) < self.settle_sec:
            time.sleep(0.1)

        ict = self._read_icts()
        score = self._score(ict)

        r = EvalResult(
            t_iso=datetime.datetime.now().isoformat(timespec="seconds"),
            device_label=device_label,
            pv_name=pv_name,
            set_value=float(set_value),
            ict=ict,
            score=float(score),
            note=note,
            group=group,
            mode=mode,
        )
        self._append_csv(r)
        self._record_evaluation(r, {pv_name: float(set_value)})
        return r

    def _evaluate_point_multi(self, device_label: str, pv_to_value: Dict[str, float],
                              mode: str, group: str, note: str = "") -> EvalResult:
        # Put all PVs first
        self.interface.pv_put_many({k: float(v) for k, v in pv_to_value.items()})

        # Optional fixed wait after finishing all puts (recommended for multi-put updates)
        post_put_wait = float(self.config.get("post_put_wait_sec", 0.0))
        if self.is_running and post_put_wait > 0:
            time.sleep(post_put_wait)

        # Settle once
        t0 = time.time()
        while self.is_running and (time.time() - t0) < self.settle_sec:
            time.sleep(0.1)

        ict = self._read_icts()
        score = self._score(ict)

        # Store the vector in note (CSV-friendly)
        try:
            vec_note = json.dumps(pv_to_value, sort_keys=True)
        except Exception:
            vec_note = str(pv_to_value)

        r = EvalResult(
            t_iso=datetime.datetime.now().isoformat(timespec="seconds"),
            device_label=device_label,
            pv_name="MULTI",
            set_value=float("nan"),
            ict=ict,
            score=float(score),
            note=(note + (" | " if note else "") + vec_note),
            group=group,
            mode=mode,
        )
        self._append_csv(r)
        self._record_evaluation(r, {k: float(v) for k, v in pv_to_value.items()})
        return r

    # ----------------------------
    # GP posterior (N-D, RBF kernel with ARD)
    # ----------------------------
    def _kernel_rbf_ard(self, Xa: np.ndarray, Xb: np.ndarray, length_scales: np.ndarray, sigma_f: float) -> np.ndarray:
        # Xa: (N,D), Xb: (M,D)
        Xa = np.asarray(Xa, dtype=float)
        Xb = np.asarray(Xb, dtype=float)
        ls = np.asarray(length_scales, dtype=float)
        ls = np.maximum(ls, 1e-12)
        diff = (Xa[:, None, :] - Xb[None, :, :]) / ls[None, None, :]
        d2 = np.sum(diff * diff, axis=2)
        return (sigma_f ** 2) * np.exp(-0.5 * d2)

    def _gp_posterior_nd(self, X_train: np.ndarray, y_train: np.ndarray, X_test: np.ndarray,
                         length_scales: np.ndarray, sigma_f: float, sigma_n: float) -> Tuple[np.ndarray, np.ndarray]:
        # Standard GP regression posterior for scalar outputs
        X_train = np.asarray(X_train, dtype=float)
        y_train = np.asarray(y_train, dtype=float).reshape(-1)
        X_test = np.asarray(X_test, dtype=float)

        if X_train.ndim != 2 or X_test.ndim != 2:
            raise ValueError("X_train and X_test must be 2D arrays (N,D) and (M,D).")
        if X_train.shape[0] == 0:
            mu = np.zeros((X_test.shape[0],), dtype=float)
            std = np.ones((X_test.shape[0],), dtype=float)
            return mu, std

        K = self._kernel_rbf_ard(X_train, X_train, length_scales, sigma_f) + (sigma_n ** 2) * np.eye(X_train.shape[0])
        Ks = self._kernel_rbf_ard(X_train, X_test, length_scales, sigma_f)
        Kss = self._kernel_rbf_ard(X_test, X_test, length_scales, sigma_f)

        # Solve K^{-1} y via Cholesky for stability
        try:
            L = np.linalg.cholesky(K + 1e-12 * np.eye(K.shape[0]))
            alpha = np.linalg.solve(L.T, np.linalg.solve(L, y_train))
            mu = Ks.T @ alpha
            v = np.linalg.solve(L, Ks)
            cov = Kss - v.T @ v
        except np.linalg.LinAlgError:
            # Fallback: pseudo-inverse
            Kinv = np.linalg.pinv(K)
            mu = Ks.T @ (Kinv @ y_train)
            cov = Kss - Ks.T @ (Kinv @ Ks)

        var = np.clip(np.diag(cov), 1e-12, None)
        std = np.sqrt(var)
        return mu.reshape(-1), std.reshape(-1)

    # ----------------------------
    # Group BO (simultaneous multi-parameter BO via random candidate EI maximization)
    # ----------------------------
    def _group_bo_simultaneous(self, group_name: str, params: List[tuple]):
        """
        Simultaneous (multi-dimensional) BO for a group:
        - Each iteration proposes a vector of settings for all PVs in the group.
        - Candidate vectors are generated by random sampling within [cur-half, cur+half] per PV,
          then quantized to each PV step.
        - EI is maximized over the random candidate set.
        """
        if not self.is_running or len(params) == 0:
            return

        resume_key = self._resume_group_key("GROUP_BO_SIMUL", group_name)
        resume_rows = self._resume_group_rows.get(resume_key, [])
        resume_done_row = self._resume_group_completed_row("GROUP_BO_SIMUL", group_name)

        # Current baseline
        pvs = []
        steps_list = []
        cur_list = []
        lo_list = []
        hi_list = []
        for p in params:
            label, pv, step, half = p[:4]
            cur_i = float(self._read_current(pv, None))
            lo_i = cur_i - max(float(half), 0.0)
            hi_i = cur_i + max(float(half), 0.0)
            if len(p) >= 6:
                lo_i = float(p[4])
                hi_i = float(p[5])
                if hi_i < lo_i:
                    lo_i, hi_i = hi_i, lo_i
            if resume_rows:
                past_vals = []
                for row in resume_rows:
                    vec = row.get("vector", {})
                    if pv in vec:
                        try:
                            past_vals.append(float(vec[pv]))
                        except Exception:
                            pass
                if past_vals:
                    lo_i = min(lo_i, float(np.nanmin(past_vals)))
                    hi_i = max(hi_i, float(np.nanmax(past_vals)))
            cur_i = float(np.clip(cur_i, lo_i, hi_i))
            pvs.append(pv)
            steps_list.append(max(float(step), 1e-12))
            cur_list.append(cur_i)
            lo_list.append(lo_i)
            hi_list.append(hi_i)

        steps = np.array(steps_list, dtype=float)
        cur = np.array(cur_list, dtype=float)
        lo = np.array(lo_list, dtype=float)
        hi = np.array(hi_list, dtype=float)

        # Config
        min_init = int(self.config.get("gbo_min_init", 10))
        max_evals = int(self.config.get("gbo_max_evals", 100))
        cand_pool = int(self.config.get("gbo_candidate_pool", 1024))
        ei_tol = float(self.config.get("bo_ei_tol", 0.0))
        stall_iters = int(self.config.get("bo_stall_iters", 30))
        xi = float(self.config.get("bo_xi", 0.1))
        sigma_f = float(self.config.get("bo_sigma_f", 1.0))
        sigma_n = float(self.config.get("bo_sigma_n", 1e-1))

        # Length scales: heuristic proportional to range per dim
        ranges = np.maximum(hi - lo, steps)
        ls = np.maximum(ranges / 3.0, 1e-6)
        # Allow override
        if "gbo_length_scale_factor" in self.config:
            ls = np.maximum(ls * float(self.config["gbo_length_scale_factor"]), 1e-6)

        X, Y, R = [], [], []

        def quantize_vec(x: np.ndarray) -> np.ndarray:
            q = np.round((x - lo) / steps) * steps + lo
            return np.clip(q, lo, hi)

        def vec_to_dict(x: np.ndarray) -> Dict[str, float]:
            return {pv: float(val) for pv, val in zip(pvs, x)}

        def eval_vec(x: np.ndarray, note: str = ""):
            xq = quantize_vec(np.asarray(x, dtype=float))
            reused = self._try_reuse_initial_vector(labels=[lab for (lab, *_rest) in params], pvs=pvs, x_vec=xq,
                                                    mode="GROUP_BO_SIMUL", group=group_name, note=note)
            if reused is not None:
                X.append(xq.copy())
                Y.append(float(reused.score))
                R.append(reused)
                return reused
            r = self._evaluate_point_multi(
                device_label=f"Group:{group_name}",
                pv_to_value=vec_to_dict(xq),
                mode="GROUP_BO_SIMUL",
                group=group_name,
                note=note
            )
            X.append(xq.copy())
            Y.append(float(r.score))
            R.append(r)
            return r

        def current_best():
            idx = int(np.argmax(Y))
            return np.asarray(X[idx], dtype=float), float(Y[idx]), R[idx]

        self.log_signal.emit(f"--- GROUP_BO_SIMUL: {group_name} (D={len(params)}) ---")
        if resume_done_row is not None:
            vec = resume_done_row.get("vector", {})
            if isinstance(vec, dict):
                x_best = np.array([float(vec.get(pv, np.nan)) for pv in pvs], dtype=float)
                if np.all(np.isfinite(x_best)):
                    self.log_signal.emit(f"[RESUME] Group {group_name} already completed previously. Re-applying saved best vector.")
                    _ = self._evaluate_point_multi(
                        device_label=f"Group:{group_name}",
                        pv_to_value=vec_to_dict(quantize_vec(x_best)),
                        mode="GROUP_BO_SIMUL",
                        group=group_name,
                        note="RESUME_COMPLETED_SET"
                    )
                    return

        if resume_rows:
            dedup: Dict[Tuple[int, ...], Dict[str, Any]] = {}
            for row in resume_rows:
                note = str(row.get("note", ""))
                vec = row.get("vector", {})
                if (not isinstance(vec, dict)) or ("OPTIMIZED_SET" in note) or ("RESUME_COMPLETED_SET" in note):
                    continue
                x_vec = np.array([float(vec.get(pv, np.nan)) for pv in pvs], dtype=float)
                if not np.all(np.isfinite(x_vec)):
                    continue
                q_vec = quantize_vec(x_vec)
                key_vec = tuple(np.round((q_vec - lo) / steps).astype(int).tolist())
                prev = dedup.get(key_vec)
                if prev is None or float(row.get("score", float("-inf"))) >= float(prev.get("score", float("-inf"))):
                    dedup[key_vec] = row
            if dedup:
                for row in dedup.values():
                    vec = row["vector"]
                    x_vec = quantize_vec(np.array([float(vec[pv]) for pv in pvs], dtype=float))
                    X.append(x_vec.copy())
                    Y.append(float(row["score"]))
                    R.append(self._resume_eval_result(row))
                self.log_signal.emit(f"[RESUME] Warm start for group {group_name}: loaded {len(X)} previous evaluations.")

        # Initial design: current + random points
        if len(X) == 0:
            eval_vec(cur, note="GBO_INIT_CUR")
        while self.is_running and len(X) < min_init and len(X) < max_evals:
            rnd = lo + (hi - lo) * np.random.rand(len(params))
            eval_vec(rnd, note="GBO_INIT_RAND")

        stall = 0
        prev_best = None

        while self.is_running and len(X) < max_evals:
            X_train = np.vstack(X)
            y_train = np.array(Y, dtype=float)

            # Random candidate pool
            C = lo + (hi - lo) * np.random.rand(cand_pool, len(params))
            C = np.vstack([quantize_vec(C[i]) for i in range(C.shape[0])])

            # Deduplicate candidates and remove already evaluated
            # Use string keys with rounding to avoid floating noise
            def key(v):
                return tuple(np.round((v - lo) / steps).astype(int).tolist())
            seen = set(key(x) for x in X_train)
            cand_list = []
            for i in range(C.shape[0]):
                kkey = key(C[i])
                if kkey in seen:
                    continue
                cand_list.append(C[i])
                if len(cand_list) >= cand_pool:
                    break
            if len(cand_list) == 0:
                break
            C2 = np.vstack(cand_list)

            mu, std = self._gp_posterior_nd(X_train, y_train, C2, length_scales=ls, sigma_f=sigma_f, sigma_n=sigma_n)
            y_best = float(np.max(y_train))
            ei = self._expected_improvement(mu, std, y_best, xi=xi)
            j = int(np.argmax(ei))
            if float(ei[j]) < ei_tol:
                break

            eval_vec(C2[j], note="GBO_EI")

            bx, by, _ = current_best()
            bx_key = key(bx)
            if prev_best is not None and bx_key == prev_best:
                stall += 1
            else:
                stall = 0
                prev_best = bx_key
            if stall >= stall_iters:
                break

        best_x, best_score, best_r = current_best()
        best_c = self._downstream_value(best_r.ict)
        self.log_signal.emit(
            f"-> Best for Group {group_name}: score={best_score:.6g} "
            f"Ttot={best_r.ict.get('Ttot', float('nan')):.6f} {self.downstream_ict}={best_c:.6g}"
        )
        # Re-apply best settings to be safe (single multi-put)
        _ = self._evaluate_point_multi(
            device_label=f"Group:{group_name}",
            pv_to_value=vec_to_dict(best_x),
            mode="GROUP_BO_SIMUL",
            group=group_name,
            note="OPTIMIZED_SET"
        )


    # ----------------------------
    # Sequential 1D scan
    # ----------------------------
    
    # ----------------------------
    # Sequential 1D scan (Unimodal Bayesian Optimization on a discrete grid)
    # ----------------------------
    def _rbf_kernel(self, xa: np.ndarray, xb: np.ndarray, length_scale: float, sigma_f: float) -> np.ndarray:
        xa = xa.reshape(-1, 1)
        xb = xb.reshape(-1, 1)
        d2 = (xa - xb.T) ** 2
        return (sigma_f ** 2) * np.exp(-0.5 * d2 / (length_scale ** 2))
    
    def _gp_posterior(self, x_train: np.ndarray, y_train: np.ndarray, x_test: np.ndarray,
                      length_scale: float, sigma_f: float, sigma_n: float) -> tuple[np.ndarray, np.ndarray]:
        """Simple 1D GP posterior (no external deps). Returns mean, std."""
        if x_train.size == 0:
            return np.zeros_like(x_test, dtype=float), np.ones_like(x_test, dtype=float)
    
        K = self._rbf_kernel(x_train, x_train, length_scale, sigma_f) + (sigma_n ** 2) * np.eye(len(x_train))
        Ks = self._rbf_kernel(x_train, x_test, length_scale, sigma_f)
        Kss = self._rbf_kernel(x_test, x_test, length_scale, sigma_f) + 1e-12 * np.eye(len(x_test))
    
        # Cholesky for stability
        try:
            L = np.linalg.cholesky(K)
            alpha = np.linalg.solve(L.T, np.linalg.solve(L, y_train))
            mu = Ks.T @ alpha
            v = np.linalg.solve(L, Ks)
            cov = Kss - v.T @ v
            var = np.clip(np.diag(cov), 1e-12, np.inf)
            return mu.astype(float), np.sqrt(var).astype(float)
        except np.linalg.LinAlgError:
            # Fallback: diagonal posterior
            mu = np.full_like(x_test, float(np.mean(y_train)), dtype=float)
            std = np.full_like(x_test, float(np.std(y_train) + 1.0), dtype=float)
            return mu, std
    
    def _expected_improvement(self, mu: np.ndarray, std: np.ndarray, y_best: float, xi: float = 0.0) -> np.ndarray:
        """EI for maximization."""
        std = np.maximum(std, 1e-12)
        z = (mu - y_best - xi) / std
        # normal pdf/cdf (avoid scipy)
        pdf = (1.0 / np.sqrt(2.0 * np.pi)) * np.exp(-0.5 * z * z)
        cdf = 0.5 * (1.0 + np.vectorize(math.erf)(z / np.sqrt(2.0)))
        ei = (mu - y_best - xi) * cdf + std * pdf
        ei[std <= 1e-12] = 0.0
        return ei
    
    def _use_refinement(self, knob_name: str) -> bool:
        name = knob_name.lower()
        return ("qa" in name) or ("qm" in name)

    def perform_1d_scan(self, device_label: str, pv_name: str, scan_values: np.ndarray,
                        group: str = "", mode: str = "SEQUENTIAL"):

        if scan_values.size == 0 or (not self.is_running):
            return

        scan_values = self._resume_scan_candidates(mode, group, pv_name, np.asarray(scan_values, dtype=float))

        # Ensure sorted unique candidates
        candidates = np.unique(np.array(scan_values, dtype=float))
        candidates.sort()
    
        self.log_signal.emit(f"[BO-1D] Optimizing {device_label} ({pv_name}) on {len(candidates)} candidates ...")

        # Sequential method selection (user request):
        # - In SEQUENTIAL mode, allow choosing BO or discrete ternary search (unimodal assumption).
        # - In GROUP modes, always use BO.
        seq_method = str(self.config.get("seq_method", "BO")).upper()
        method = seq_method if str(mode).upper() == "SEQUENTIAL" else "BO"
    
        # Config knobs (reasonable defaults)
        min_init = int(self.config.get("bo_min_init", 5))      # initial evaluations
        max_evals = int(self.config.get("bo_max_evals", min(17, len(candidates))))
        ei_tol = float(self.config.get("bo_ei_tol", 1e-6))
        stall_iters = int(self.config.get("bo_stall_iters", 4))
        refine_enabled = bool(self.config.get("bo_refine", True))
        refine_factor = float(self.config.get("bo_refine_factor", 5.0))  # step -> step/refine_factor
    
        # GP hyperparams (heuristic)
        x_range = float(candidates[-1] - candidates[0]) if len(candidates) >= 2 else 1.0
        length_scale = float(self.config.get("bo_length_scale", max(x_range / 3.0, 1e-6)))
        sigma_f = float(self.config.get("bo_sigma_f", 1.0))
        sigma_n = float(self.config.get("bo_sigma_n", 1e-1))
        xi = float(self.config.get("bo_xi", 0.0))

        X, Y, R = [], [], []  # store evaluated (x, score, EvalResult)

        resume_done_row = self._resume_seq_completed_row(mode, group, pv_name)
        if resume_done_row is not None:
            best_x = float(resume_done_row.get("set_value", float("nan")))
            if np.isfinite(best_x):
                self.log_signal.emit(f"[RESUME] {device_label} already completed previously. Re-applying x={best_x:.6g}.")
                _ = self._evaluate_point(device_label, pv_name, best_x, mode=mode, group=group, note="RESUME_COMPLETED_SET")
                return

        resume_rows = self._resume_seq_rows.get(self._resume_seq_key(mode, group, pv_name), [])
        if resume_rows:
            dedup: Dict[float, Dict[str, Any]] = {}
            for row in resume_rows:
                note = str(row.get("note", ""))
                x = float(row.get("set_value", float("nan")))
                if (not np.isfinite(x)) or ("OPTIMIZED_SET" in note) or ("RESUME_COMPLETED_SET" in note):
                    continue
                key_x = round(x, 10)
                prev = dedup.get(key_x)
                if prev is None or float(row.get("score", float("-inf"))) >= float(prev.get("score", float("-inf"))):
                    dedup[key_x] = row
            if dedup:
                for _, row in sorted(dedup.items(), key=lambda item: item[0]):
                    X.append(float(row["set_value"]))
                    Y.append(float(row["score"]))
                    R.append(self._resume_eval_result(row))
                self.log_signal.emit(f"[RESUME] Warm start for {device_label}: loaded {len(X)} previous evaluations.")
    
        def eval_at(x: float, note: str = ""):
            reused = self._try_reuse_initial_point(
                device_label=device_label,
                pv_name=pv_name,
                set_value=float(x),
                mode=mode,
                group=group,
                note=note,
            )
            if reused is not None:
                X.append(float(x))
                Y.append(float(reused.score))
                R.append(reused)
                Ttot = reused.ict.get("Ttot", float("nan"))
                C = self._downstream_value(reused.ict)
                self.log_signal.emit(f"  x={x:.6g}  Ttot={Ttot:.6f}  {self.downstream_ict}={C:.6g}  [REUSE_INIT]")
                return reused
            r = self._evaluate_point(device_label, pv_name, float(x), mode=mode, group=group, note=note)
            X.append(float(x))
            Y.append(float(r.score))
            R.append(r)
            Ttot = r.ict.get("Ttot", float("nan"))
            C = self._downstream_value(r.ict)
            self.log_signal.emit(f"  x={x:.6g}  Ttot={Ttot:.6f}  {self.downstream_ict}={C:.6g}")
            return r
    
        
        # ------------------------------------------------------------------
        # Discrete ternary search (unimodal) on the candidate grid
        # ------------------------------------------------------------------
        if method in ("TERNARY", "TERNARY_SEARCH", "BINARY", "BINARY_SEARCH"):
            # Use the same evaluation budget knob for simplicity
            max_evals = int(self.config.get("bo_max_evals", min(17, len(candidates))))

            # Cache helper
            def _y_at(xv: float) -> float:
                # Ensure evaluated
                if xv not in set(X):
                    eval_at(xv, note="TERNARY_EVAL")
                # Return stored
                return float(Y[X.index(xv)])

            l = 0
            r = len(candidates) - 1

            # Ternary search loop (discrete)
            while self.is_running and (r - l) > 2 and len(X) < max_evals:
                m1 = l + (r - l) // 3
                m2 = r - (r - l) // 3
                x1 = float(candidates[m1])
                x2 = float(candidates[m2])

                y1 = _y_at(x1)
                if not self.is_running or len(X) >= max_evals:
                    break
                y2 = _y_at(x2)

                # Keep the side containing the higher value (maximize)
                if y1 < y2:
                    l = m1
                else:
                    r = m2

            # Final local exhaustive on the remaining small bracket (and within remaining budget)
            for j in range(l, r + 1):
                if not self.is_running or len(X) >= max_evals:
                    break
                xj = float(candidates[j])
                if xj not in set(X):
                    eval_at(xj, note="TERNARY_FINAL")

            idxb = int(np.argmax(Y))
            best_x, best_score, best_r = float(X[idxb]), float(Y[idxb]), R[idxb]

            # Refinement (step/5) is intentionally NOT used for phase/timing; it is controlled later (QA/QM only).
            # Jump to final set & return.
            self.log_signal.emit(
                f"-> Best for {device_label}: {best_x:.6g}  "
                f"Ttot={best_r.ict.get('Ttot', float('nan')):.6f}  {self.downstream_ict}={self._downstream_value(best_r.ict):.6g}"
            )
            _ = self._evaluate_point(device_label, pv_name, best_x, mode=mode, group=group, note="OPTIMIZED_SET")
            return

# 1) initial points: endpoints + mid (or fewer if grid is tiny)
        init_x = []
        init_x.append(float(candidates[0]))
        if len(candidates) > 1:
            init_x.append(float(candidates[-1]))
        init_x.append(float(candidates[len(candidates)//2]))
        init_x = list(dict.fromkeys(init_x))  # unique preserve order
    
        # If user wants more init, fill evenly
        if min_init > len(init_x) and len(candidates) > len(init_x):
            extra = np.linspace(candidates[0], candidates[-1], min_init)
            extra = [float(candidates[np.argmin(np.abs(candidates - e))]) for e in extra]
            for e in extra:
                if e not in init_x:
                    init_x.append(e)
    
        # evaluate init
        for x in init_x[:max_evals]:
            if not self.is_running:
                return
            if x in set(X):
                continue
            eval_at(x, note="BO_INIT")
    
        def current_best():
            idx = int(np.argmax(Y))
            return float(X[idx]), float(Y[idx]), R[idx]
    
        # helper: unimodal bracket shrink (based on evaluated points)
        def shrink_domain(all_candidates: np.ndarray) -> np.ndarray:
            if len(X) < 3:
                return all_candidates
            xb, yb, _ = current_best()
            # evaluated points sorted
            xs = np.array(sorted(set(X)), dtype=float)
            ys = np.array([Y[X.index(x)] for x in xs], dtype=float)
            i = int(np.where(xs == xb)[0][0])
    
            # find nearest left with lower score, and nearest right with lower score
            xl = all_candidates[0]
            xr = all_candidates[-1]
    
            # search left
            for j in range(i-1, -1, -1):
                if ys[j] < yb:
                    xl = xs[j]
                    break
            # search right
            for j in range(i+1, len(xs)):
                if ys[j] < yb:
                    xr = xs[j]
                    break
    
            # Keep a little margin: include one coarse step on each side if possible
            domain = all_candidates[(all_candidates >= xl) & (all_candidates <= xr)]
            if domain.size >= 3:
                return domain
            return all_candidates
    
        # 2) BO loop on coarse grid
        stall = 0
        prev_best_x = None
        domain = candidates.copy()
    
        while self.is_running and len(X) < max_evals:
            domain = shrink_domain(domain)
            remaining = np.array([c for c in domain if c not in set(X)], dtype=float)
            if remaining.size == 0:
                break
    
            x_train = np.array(X, dtype=float)
            y_train = np.array(Y, dtype=float)
            mu, std = self._gp_posterior(x_train, y_train, remaining, length_scale, sigma_f, sigma_n)
            y_best = float(np.max(y_train))
            ei = self._expected_improvement(mu, std, y_best, xi=xi)
            k = int(np.argmax(ei))
            if float(ei[k]) < ei_tol:
                break
    
            cand = float(remaining[k])
            eval_at(cand)
    
            bx, by, _ = current_best()
            if prev_best_x is not None and bx == prev_best_x:
                stall += 1
            else:
                stall = 0
                prev_best_x = bx
    
            if stall >= stall_iters:
                break
    
        best_x, best_score, best_r = current_best()

        pv_lower = pv_name.lower()
        is_qaqm = ("qa" in pv_lower) or ("qm" in pv_lower)

        if refine_enabled and is_qaqm and len(candidates) >= 2:
            # infer coarse step from candidates (median diff)
            diffs = np.diff(candidates)
            coarse_step = float(np.median(diffs[diffs > 0])) if np.any(diffs > 0) else 0.0
    
            if coarse_step > 0:
                fine_step = coarse_step / refine_factor
    
                # local window: from nearest *observed* points around current best (more consistent skirt/bracket)
                xs_obs = np.array(sorted(set(X)), dtype=float)
                left_obs = float(candidates[0])
                right_obs = float(candidates[-1])
                if xs_obs.size >= 2:
                    left_candidates = xs_obs[xs_obs < best_x]
                    right_candidates = xs_obs[xs_obs > best_x]
                    if left_candidates.size > 0:
                        left_obs = float(left_candidates.max())
                    if right_candidates.size > 0:
                        right_obs = float(right_candidates.min())
    
                lo = float(np.clip(left_obs, candidates[0], candidates[-1]))
                hi = float(np.clip(right_obs, candidates[0], candidates[-1]))
                if hi <= lo:
                    # fallback (should be rare): ±1 coarse step
                    lo = float(np.max([candidates[0], best_x - coarse_step]))
                    hi = float(np.min([candidates[-1], best_x + coarse_step]))
    
                # create fine candidates (still discrete)
                fine = np.arange(lo, hi + fine_step * 0.5, fine_step, dtype=float)
                fine = np.unique(np.clip(fine, candidates[0], candidates[-1]))
                fine.sort()
    
                # allow a few more evals, but keep bounded
                refine_budget = int(self.config.get("bo_refine_evals", min(10, len(fine))))
                max_total = max_evals + refine_budget
    
                self.log_signal.emit(
                    f"[BO-1D] Refinement: step {coarse_step:.6g} -> {fine_step:.6g}, window=[{lo:.6g},{hi:.6g}], budget={refine_budget}"
                )
    
                stall2 = 0
                prev_best_x2 = best_x
    
                while self.is_running and len(X) < max_total:
                    remaining = np.array([c for c in fine if c not in set(X)], dtype=float)
                    if remaining.size == 0:
                        break
    
                    x_train = np.array(X, dtype=float)
                    y_train = np.array(Y, dtype=float)
                    mu, std = self._gp_posterior(x_train, y_train, remaining, length_scale=max(fine_step*3, 1e-6),
                                                 sigma_f=sigma_f, sigma_n=sigma_n)
                    y_best = float(np.max(y_train))
                    ei = self._expected_improvement(mu, std, y_best, xi=xi)
                    k = int(np.argmax(ei))
                    if float(ei[k]) < ei_tol:
                        break
    
                    eval_at(float(remaining[k]), note="BO_REFINE")
    
                    bx, by, _ = current_best()
                    if bx == prev_best_x2:
                        stall2 += 1
                    else:
                        stall2 = 0
                        prev_best_x2 = bx
    
                    if stall2 >= stall_iters:
                        break
    
                idxb = int(np.argmax(Y))
            best_x, best_score, best_r = float(X[idxb]), float(Y[idxb]), R[idxb]
    
        if not self.is_running:
            return
    
        self.log_signal.emit(
            f"-> Best for {device_label}: {best_x:.6g}  "
            f"Ttot={best_r.ict.get('Ttot', float('nan')):.6f}  {self.downstream_ict}={self._downstream_value(best_r.ict):.6g}"
        )
        _ = self._evaluate_point(device_label, pv_name, best_x, mode=mode, group=group, note="OPTIMIZED_SET")
    
        # ----------------------------
    # Group-LBO (discrete / quantized)
    # ----------------------------
    def _quantize(self, x: float, x0: float, step: float, lo: float, hi: float) -> float:
        if step <= 0:
            return float(np.clip(x, lo, hi))
        xq = x0 + round((x - x0) / step) * step
        return float(np.clip(xq, lo, hi))

    def _read_current(self, pv_write: str, pv_read: Optional[str] = None) -> float:
        return self.interface.read_current(pv_write=pv_write, pv_read=pv_read, quantize_phase=True)

    
    def _lbo_group(self, group_name: str, params: List[tuple]):
        """
        params: list of (label, pv_write, step, half_range) for each dimension
        Optimization:
        - Start at current point x0
        - Repeat a few iterations:
            - Choose a direction (coordinate + random)
            - Sample candidates along that line (discrete/quantized)
            - Move to best candidate
        """
        if not self.is_running:
            return
    
        # current point
        x0 = []
        bounds = []
        steps = []
        labels = []
        pvs = []
        for p in params:
            label, pv_write, step, half = p[:4]
            cur = self._read_current(pv_write)  # use write as read by default
            lo = cur - half
            hi = cur + half
            if len(p) >= 6:
                lo = float(p[4])
                hi = float(p[5])
                if hi < lo:
                    lo, hi = hi, lo
            cur = float(np.clip(cur, lo, hi))
            x0.append(cur)
            bounds.append((lo, hi))
            steps.append(step)
            labels.append(label)
            pvs.append(pv_write)
    
        x = np.array(x0, dtype=float)
    
        # Evaluation helper
        def eval_vec(x_vec: np.ndarray, note: str = "") -> EvalResult:
            xq = np.asarray(x_vec, dtype=float)
            reused = self._try_reuse_initial_vector(labels=labels, pvs=pvs, x_vec=xq, mode="GROUP_LBO",
                                                    group=group_name, note=note)
            if reused is not None:
                self.log_signal.emit(
                    f"[{group_name}] Ttot={reused.ict.get('Ttot', float('nan')):.6f} "
                    f"{self.downstream_ict}={self._downstream_value(reused.ict):.6g}  x={np.array2string(xq, precision=6)}  [REUSE_INIT]"
                )
                return reused
            # Apply all PVs (sequential put), then single settle+read (practical)
            # Put all
            self.interface.pv_put_many({pv_name: float(v) for pv_name, v in zip(pvs, x_vec)})
            # settle
            t0 = time.time()
            while self.is_running and (time.time() - t0) < self.settle_sec:
                time.sleep(0.1)
            ict = self._read_icts()
            score = self._score(ict)
            r = EvalResult(
                t_iso=datetime.datetime.now().isoformat(timespec="seconds"),
                device_label=",".join(labels),
                pv_name=",".join(pvs),
                set_value=float("nan"),
                ict=ict,
                score=float(score),
                note=note,
                group=group_name,
                mode="GROUP_LBO",
            )
            # For vector, store set_value as NaN; still log.
            self._append_csv(r)
            self._record_evaluation(r, {pv_name: float(v) for pv_name, v in zip(pvs, x_vec)})
            # log message
            self.log_signal.emit(
                f"[{group_name}] Ttot={ict.get('Ttot', float('nan')):.6f} {self.downstream_ict}={self._downstream_value(ict):.6g}  x={np.array2string(x_vec, precision=6)}"
            )
            return r
    
        # initial eval
        best = eval_vec(x, note="LBO_INIT")
        best_x = x.copy()
    
        # iterations (small fixed number to avoid runaway)
        iters = int(self.config.get("lbo_iters", 4))
        line_samples = int(self.config.get("lbo_line_samples", 11))
    
        rng = np.random.default_rng()
    
        def clamp_quantize_vec(x_candidate: np.ndarray) -> np.ndarray:
            y = []
            for i in range(len(x_candidate)):
                lo, hi = bounds[i]
                y.append(self._quantize(float(x_candidate[i]), x0[i], steps[i], lo, hi))
            return np.array(y, dtype=float)
    
        for it in range(iters):
            if not self.is_running:
                return
    
            # Choose direction: coordinate directions + occasional random direction
            directions = []
            # coordinate directions
            for i in range(len(x)):
                d = np.zeros_like(x)
                d[i] = 1.0
                directions.append(d)
            # add one random direction
            rd = rng.normal(size=len(x))
            if np.linalg.norm(rd) > 0:
                rd = rd / np.linalg.norm(rd)
            directions.append(rd)
    
            improved_in_iter = False
            for d in directions:
                if not self.is_running:
                    return
    
                # sample alpha in [-1,1] then scale by half-range in that direction
                alphas = np.linspace(-1.0, 1.0, line_samples)
                cand = []
                for a in alphas:
                    # propose
                    prop = best_x + a * d
                    # scale to meaningful range per-dimension: use half-range as scale
                    # (so that alpha=1 can reach near bounds depending on direction)
                    scaled = best_x + a * d * np.array([b[1]-b[0] for b in bounds]) * 0.5
                    q = clamp_quantize_vec(scaled)
                    cand.append(q)
    
                # unique candidates
                uniq = []
                seen = set()
                for v in cand:
                    key = tuple(np.round(v / np.array(steps), 0)) if all(s>0 for s in steps) else tuple(v)
                    if key in seen:
                        continue
                    seen.add(key)
                    uniq.append(v)
    
                # evaluate
                for v in uniq:
                    if not self.is_running:
                        return
                    r = eval_vec(v)
                    if r.score > best.score:
                        best = r
                        best_x = v.copy()
                        improved_in_iter = True
    
            # if no improvement, stop early
            if not improved_in_iter:
                break
    
        # finalize: set best_x and log
        if self.is_running:
            self.interface.pv_put_many({pv_name: float(v) for pv_name, v in zip(pvs, best_x)})
            t0 = time.time()
            while self.is_running and (time.time() - t0) < self.settle_sec:
                time.sleep(0.1)
            _ = eval_vec(best_x, note="LBO_FINAL")
    
    # ----------------------------
    # Main run
    # ----------------------------
    def run(self):
        self.log_signal.emit(f"=== Optimization Started (mode={self.mode}) ===")
        try:
            self._dump_initial_snapshot()
            if self.mode == "GROUP_LBO":
                self._run_group_lbo()
            elif self.mode == "GROUP_BO":
                self._run_group_bo()
            else:
                self._run_sequential()
        except Exception as e:
            self._emit_progress({"kind": "run_error", "message": str(e)})
            self.log_signal.emit(f"Error: {str(e)}")
        finally:
            self.log_signal.emit("=== Optimization Finished ===")
            self.finished_signal.emit()

    def _run_sequential(self):
        # Scan settings (GUI-configurable)
        gun_phase_half = float(self.config.get("gun_phase_half_range_deg", GUN_PHASE_HALF_RANGE_DEG))
        gun_phase_step = float(self.config.get("gun_phase_step_deg", GUN_PHASE_STEP_DEG))
        sol_min = float(self.config.get("solenoide_min_a", SOLENOIDE_MIN_A))
        sol_max = float(self.config.get("solenoide_max_a", SOLENOIDE_MAX_A))
        sol_step = float(self.config.get("solenoide_step_a", SOLENOIDE_STEP_A))
        l0_phase_half = float(self.config.get("l0_phase_half_range_deg", L0_PHASE_HALF_RANGE_DEG))
        l0_phase_step = float(self.config.get("l0_phase_step_deg", L0_PHASE_STEP_DEG))
        phase_half = float(self.config.get("phase_half_range_deg", PHASE_HALF_RANGE_DEG))
        phase_step = float(self.config.get("phase_step_deg", PHASE_STEP_DEG))
        qa_half = float(self.config.get("qa_half_range_a", QA_HALF_RANGE_A))
        qa_step = float(self.config.get("qa_step_a", QA_STEP_A))
        qm_half = float(self.config.get("qm_half_range_a", QM_HALF_RANGE_A))
        qm_step = float(self.config.get("qm_step_a", QM_STEP_A))
        timing_step = float(self.config.get("timing_step_ns", TIMING_STEP_NS))
        timing_half_steps = int(self.config.get("timing_half_steps", TIMING_HALF_STEPS))
        gun_group_name = TARGET_LABELS["gun_sol_l0"]

        # 1) GUN/SOLENOIDE/L0 mode (head of sequence)
        if self.config.get("gun_sol_l0_phase", False) and self.is_running:
            self._emit_group_state("gun_sol_l0", "running")
            self.log_signal.emit(f"--- {gun_group_name} (GUN -> Solenoid -> L0) ---")
            sol_lo = min(sol_min, sol_max)
            sol_hi = max(sol_min, sol_max)
            specs = [
                ("GUN phase", "RFGUN:PHASE_WRITE", gun_phase_half, gun_phase_step),
                ("Solenoid current", "SOLENOIDE:internalCurrentWrite", None, sol_step),
                ("L0 phase", "CM0L:phaseWrite", l0_phase_half, l0_phase_step),
            ]
            for label, pv_write, half, step in specs:
                if not self.is_running:
                    break
                if "SOLENOIDE" in pv_write:
                    scan = np.arange(sol_lo, sol_hi + step * 0.5, step)
                else:
                    cur = self._read_current(pv_write, None)
                    scan = np.arange(cur - half, cur + half + step, step)
                self.perform_1d_scan(label, pv_write, scan, group=gun_group_name, mode="SEQUENTIAL")
            if self.is_running:
                self._emit_group_state("gun_sol_l0", "done")

        # 2) Klystron phases (1..8)
        if self.config.get("kly_phase", False) and self.is_running:
            self._emit_group_state("kly_phase", "running")
            self.log_signal.emit("--- Klystron Phase (1-8) ---")
            for i in range(1, 9):
                if not self.is_running:
                    break
                pv_write = f"CM{i}L:phaseWrite"
                pv_read = f"CM{i}L:phaseRead"
                cur = self._read_current(pv_write, pv_read)
                scan = np.arange(cur - phase_half, cur + phase_half + phase_step, phase_step)
                self.perform_1d_scan(f"Klystron {i} phase", pv_write, scan, group=f"L{i}", mode="SEQUENTIAL")
            if self.is_running:
                self._emit_group_state("kly_phase", "done")

        # 3) Timing (after phase)
        if self.config.get("timing", False) and self.is_running:
            self._emit_group_state("timing", "running")
            self.log_signal.emit("--- Timing ---")
            pv = "EVE_LINAC:OUT0:SetData"
            cur = self._read_current(pv, None)
            scan = cur + timing_step * np.arange(-timing_half_steps, timing_half_steps + 1, 1)
            self.perform_1d_scan("Timing", pv, scan, group="Timing", mode="SEQUENTIAL")
            if self.is_running:
                self._emit_group_state("timing", "done")

        # 4) QA
        if self.config.get("qa", False) and self.is_running:
            self._emit_group_state("qa", "running")
            self.log_signal.emit("--- QA Magnets (QA1L-QA5L) ---")
            for q in ["QA1L", "QA2L", "QA3L", "QA4L", "QA5L"]:
                if not self.is_running:
                    break
                pv_write = f"{q}:currentWrite"
                # optional read PV name if exists; fallback to write
                pv_read = f"{q}:currentRead"
                cur = self._read_current(pv_write, pv_read)
                scan = np.arange(cur - qa_half, cur + qa_half + qa_step, qa_step)
                self.perform_1d_scan(q, pv_write, scan, group="QA", mode="SEQUENTIAL")
            if self.is_running:
                self._emit_group_state("qa", "done")

        # 5) QM
        if self.config.get("qm", False) and self.is_running:
            self._emit_group_state("qm", "running")
            self.log_signal.emit("--- QM Magnets (QM1L-QM3L) ---")
            for m in ["QM1L", "QM2L", "QM3L"]:
                if not self.is_running:
                    break
                pv_write = f"{m}:currentWrite"
                pv_read = f"{m}:currentRead"
                cur = self._read_current(pv_write, pv_read)
                scan = np.arange(cur - qm_half, cur + qm_half + qm_step, qm_step)
                self.perform_1d_scan(m, pv_write, scan, group="QM", mode="SEQUENTIAL")
            if self.is_running:
                self._emit_group_state("qm", "done")

    def _run_group_lbo(self):
        # Scan settings (GUI-configurable)
        gun_phase_half = float(self.config.get("gun_phase_half_range_deg", GUN_PHASE_HALF_RANGE_DEG))
        gun_phase_step = float(self.config.get("gun_phase_step_deg", GUN_PHASE_STEP_DEG))
        sol_min = float(self.config.get("solenoide_min_a", SOLENOIDE_MIN_A))
        sol_max = float(self.config.get("solenoide_max_a", SOLENOIDE_MAX_A))
        sol_step = float(self.config.get("solenoide_step_a", SOLENOIDE_STEP_A))
        l0_phase_half = float(self.config.get("l0_phase_half_range_deg", L0_PHASE_HALF_RANGE_DEG))
        l0_phase_step = float(self.config.get("l0_phase_step_deg", L0_PHASE_STEP_DEG))
        phase_half = float(self.config.get("phase_half_range_deg", PHASE_HALF_RANGE_DEG))
        phase_step = float(self.config.get("phase_step_deg", PHASE_STEP_DEG))
        qa_half = float(self.config.get("qa_half_range_a", QA_HALF_RANGE_A))
        qa_step = float(self.config.get("qa_step_a", QA_STEP_A))
        qm_half = float(self.config.get("qm_half_range_a", QM_HALF_RANGE_A))
        qm_step = float(self.config.get("qm_step_a", QM_STEP_A))
        timing_step = float(self.config.get("timing_step_ns", TIMING_STEP_NS))
        timing_half_steps = int(self.config.get("timing_half_steps", TIMING_HALF_STEPS))
        # Group order: GUN&SOLENOIDE&L0, L1-4, L5-8, Timing, QA, QM
        if self.config.get("gun_sol_l0_phase", False) and self.is_running:
            sol_lo = min(sol_min, sol_max)
            sol_hi = max(sol_min, sol_max)
            params = [
                ("GUN phase", "RFGUN:PHASE_WRITE", gun_phase_step, gun_phase_half),
                ("SOLENOIDE current", "SOLENOIDE:internalCurrentWrite", sol_step, 0.0, sol_lo, sol_hi),
                ("L0 phase", "CM0L:phaseWrite", l0_phase_step, l0_phase_half),
            ]
            self.log_signal.emit("--- GROUP_LBO: GUN&SOLENOIDE&L0 ---")
            self._lbo_group("GUN&SOLENOIDE&L0", params)

        if self.config.get("kly_phase", False) and self.is_running:
            # L1-4
            if self.config.get("grp_L1_4", True):
                params = []
                for i in range(1, 5):
                    pv_write = f"CM{i}L:phaseWrite"
                    params.append((f"L{i}", pv_write, phase_step, phase_half))
                self.log_signal.emit("--- GROUP_LBO: L1-4 ---")
                self._lbo_group("L1-4", params)

            # L5-8
            if self.is_running and self.config.get("grp_L5_8", True):
                params = []
                for i in range(5, 9):
                    pv_write = f"CM{i}L:phaseWrite"
                    params.append((f"L{i}", pv_write, phase_step, phase_half))
                self.log_signal.emit("--- GROUP_LBO: L5-8 ---")
                self._lbo_group("L5-8", params)

        # Timing
        if self.config.get("timing", False) and self.is_running:
            pv = "EVE_LINAC:OUT0:SetData"
            params = [("Timing", pv, timing_step, timing_step * timing_half_steps)]
            self.log_signal.emit("--- GROUP_LBO: Timing ---")
            self._lbo_group("Timing", params)

        # QA
        if self.config.get("qa", False) and self.is_running:
            params = [(q, f"{q}:currentWrite", qa_step, qa_half) for q in ["QA1L","QA2L","QA3L","QA4L","QA5L"]]
            self.log_signal.emit("--- GROUP_LBO: QA ---")
            self._lbo_group("QA", params)

        # QM
        if self.config.get("qm", False) and self.is_running:
            params = [(m, f"{m}:currentWrite", qm_step, qm_half) for m in ["QM1L","QM2L","QM3L"]]
            self.log_signal.emit("--- GROUP_LBO: QM ---")
            self._lbo_group("QM", params)



    def _run_group_bo(self):
        # Scan settings (GUI-configurable)
        gun_phase_half = float(self.config.get("gun_phase_half_range_deg", GUN_PHASE_HALF_RANGE_DEG))
        gun_phase_step = float(self.config.get("gun_phase_step_deg", GUN_PHASE_STEP_DEG))
        sol_min = float(self.config.get("solenoide_min_a", SOLENOIDE_MIN_A))
        sol_max = float(self.config.get("solenoide_max_a", SOLENOIDE_MAX_A))
        sol_step = float(self.config.get("solenoide_step_a", SOLENOIDE_STEP_A))
        l0_phase_half = float(self.config.get("l0_phase_half_range_deg", L0_PHASE_HALF_RANGE_DEG))
        l0_phase_step = float(self.config.get("l0_phase_step_deg", L0_PHASE_STEP_DEG))
        phase_half = float(self.config.get("phase_half_range_deg", PHASE_HALF_RANGE_DEG))
        phase_step = float(self.config.get("phase_step_deg", PHASE_STEP_DEG))
        qa_half = float(self.config.get("qa_half_range_a", QA_HALF_RANGE_A))
        qa_step = float(self.config.get("qa_step_a", QA_STEP_A))
        qm_half = float(self.config.get("qm_half_range_a", QM_HALF_RANGE_A))
        qm_step = float(self.config.get("qm_step_a", QM_STEP_A))
        timing_step = float(self.config.get("timing_step_ns", TIMING_STEP_NS))
        timing_half_steps = int(self.config.get("timing_half_steps", TIMING_HALF_STEPS))
        gun_group_name = TARGET_LABELS["gun_sol_l0"]

        # Simultaneous Group BO:
        # - For multi-PV groups (L1-4, L5-8, QA, QM), use multi-dimensional BO that proposes a *vector*
        #   and applies all PVs in one shot (single wait + single measurement per iteration).
        # - For single-PV group (Timing), fall back to the 1D scan optimizer.
        self.log_signal.emit("[GROUP_BO] Using simultaneous multi-parameter BO for multi-PV groups.")

        # Group order: GUN&SOLENOIDE&L0, L1-4, L5-8, Timing, QA, QM
        if self.config.get("gun_sol_l0_phase", False) and self.is_running:
            self._emit_group_state("gun_sol_l0", "running")
            sol_lo = min(sol_min, sol_max)
            sol_hi = max(sol_min, sol_max)
            params = [
                ("GUN phase", "RFGUN:PHASE_WRITE", gun_phase_step, gun_phase_half),
                ("Solenoid current", "SOLENOIDE:internalCurrentWrite", sol_step, 0.0, sol_lo, sol_hi),
                ("L0 phase", "CM0L:phaseWrite", l0_phase_step, l0_phase_half),
            ]
            self._group_bo_simultaneous(gun_group_name, params)
            if self.is_running:
                self._emit_group_state("gun_sol_l0", "done")

        if self.config.get("kly_phase", False) and self.is_running:
            self._emit_group_state("kly_phase", "running")
            if self.config.get("grp_L1_4", True):
                self._emit_group_state("kly_group_1", "running")
                params = [(f"L{i}", f"CM{i}L:phaseWrite", phase_step, phase_half) for i in range(1, 5)]
                self._group_bo_simultaneous("L1-4", params)
                if self.is_running:
                    self._emit_group_state("kly_group_1", "done")
            if self.config.get("grp_L5_8", True):
                self._emit_group_state("kly_group_2", "running")
                params = [(f"L{i}", f"CM{i}L:phaseWrite", phase_step, phase_half) for i in range(5, 9)]
                self._group_bo_simultaneous("L5-8", params)
                if self.is_running:
                    self._emit_group_state("kly_group_2", "done")
            if self.is_running:
                self._emit_group_state("kly_phase", "done")

        if self.config.get("timing", False) and self.is_running:
            self._emit_group_state("timing", "running")
            pv = "EVE_LINAC:OUT0:SetData"
            cur = self._read_current(pv, None)
            scan = cur + timing_step * np.arange(-timing_half_steps, timing_half_steps + 1, 1)
            self.perform_1d_scan("Timing", pv, scan, group="Timing", mode="GROUP_BO")
            if self.is_running:
                self._emit_group_state("timing", "done")

        if self.config.get("qa", False) and self.is_running:
            self._emit_group_state("qa", "running")
            params = [(q, f"{q}:currentWrite", qa_step, qa_half) for q in ["QA1L","QA2L","QA3L","QA4L","QA5L"]]
            self._group_bo_simultaneous("QA", params)
            if self.is_running:
                self._emit_group_state("qa", "done")

        if self.config.get("qm", False) and self.is_running:
            self._emit_group_state("qm", "running")
            params = [(m, f"{m}:currentWrite", qm_step, qm_half) for m in ["QM1L","QM2L","QM3L"]]
            self._group_bo_simultaneous("QM", params)
            if self.is_running:
                self._emit_group_state("qm", "done")


# ----------------------------
# GUI
# ----------------------------
class ClickOpenComboBox(QComboBox):
    """Combo box that opens popup when the box body is clicked."""

    def mousePressEvent(self, event):  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton and self.isEnabled():
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton and self.isEnabled():
            self.showPopup()
            event.accept()
            return
        super().mouseReleaseEvent(event)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Linac Optimization GUI")
        self.resize(1180, 900)

        self.worker: Optional[OptimizationWorker] = None
        self.interface: Optional[InterfaceATF2_Linac] = None
        self.save_path = Path.cwd() / "Data"
        self.target_checks: Dict[str, QCheckBox] = {}
        self.target_status_labels: Dict[str, QLabel] = {}
        self.target_value_labels: Dict[str, QLabel] = {}
        self.target_states: Dict[str, str] = {}
        self.live_eval_index: List[int] = []
        self.live_ttot: List[float] = []
        self.live_downstream: List[float] = []
        self.live_downstream_label: str = "DR"
        self._run_mode: str = ""
        self._run_failed: bool = False
        self._current_value_refresh_failed: bool = False
        self.current_machine_origin: Optional[Dict[str, Any]] = None
        self.current_measurements_csv: Optional[Path] = None
        self.resume_snapshot_state: Optional[Dict[str, Any]] = None

        self._init_ui()
        self._current_value_timer = QTimer(self)
        self._current_value_timer.setInterval(3000)
        self._current_value_timer.timeout.connect(self._auto_refresh_current_values)
        self._current_value_timer.start()
        self._update_mode_ui()
        self._reset_target_states()
        self._refresh_current_values()
        self._set_status("Status: IDLE", state="idle")

    def _init_ui(self):
        cw = QWidget()
        self.setCentralWidget(cw)
        root = QVBoxLayout(cw)

        self.tabs = QTabWidget()
        self.tabs.setStyleSheet(
            "QTabBar::tab { font-size: 16px; font-weight: 600; padding: 8px 18px; min-width: 120px; }"
        )
        root.addWidget(self.tabs)
        self.main_tab = QWidget()
        self.config_tab = QWidget()
        self.tabs.addTab(self.main_tab, "Main")
        self.tabs.addTab(self.config_tab, "Config")

        self._build_main_tab()
        self._build_config_tab()

        self.mode_box.currentTextChanged.connect(self._update_mode_ui)
        self.mode_box.currentTextChanged.connect(self._refresh_current_values)
        self.chk_kly_phase.toggled.connect(self._update_mode_ui)
        for cb in (
            self.chk_gun_sol_l0_phase,
            self.chk_kly_phase,
            self.chk_kly_group1,
            self.chk_kly_group2,
            self.chk_timing,
            self.chk_qa,
            self.chk_qm,
        ):
            cb.toggled.connect(self._refresh_current_values)

    def _build_main_tab(self):
        layout = QVBoxLayout(self.main_tab)
        layout.setSpacing(10)
        self.main_tab.setStyleSheet(
            "QGroupBox { font-size: 19px; font-weight: 700; margin-top: 10px; } "
            "QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; } "
            "QLabel { font-size: 17px; } "
            "QCheckBox { font-size: 19px; font-weight: 500; spacing: 10px; } "
            "QCheckBox[knobCheck=\"true\"] { font-size: 21px; font-weight: 500; } "
            "QCheckBox[knobCheck=\"true\"]:checked { font-size: 24px; font-weight: 800; color: #111827; } "
            "QCheckBox::indicator { width: 22px; height: 22px; } "
            "QTextEdit { font-size: 15px; } "
            "QLineEdit, QComboBox { font-size: 17px; min-height: 34px; }"
        )

        grp_targets = QGroupBox("Knob Groups To Scan")
        layout.addWidget(grp_targets)
        lay_t = QVBoxLayout(grp_targets)
        self.chk_gun_sol_l0_phase = self._add_target_row(
            lay_t, "gun_sol_l0", TARGET_LABELS["gun_sol_l0"], checked=True, prominent=True
        )
        self.chk_kly_phase = self._add_target_row(
            lay_t, "kly_phase", TARGET_LABELS["kly_phase"], checked=True, prominent=True, show_value=False
        )
        self.chk_kly_group1 = self._add_target_row(
            lay_t, "kly_group_1", TARGET_LABELS["kly_group_1"], checked=True, prominent=False, indent=34
        )
        self.chk_kly_group2 = self._add_target_row(
            lay_t, "kly_group_2", TARGET_LABELS["kly_group_2"], checked=True, prominent=False, indent=34
        )
        self.chk_timing = self._add_target_row(lay_t, "timing", TARGET_LABELS["timing"], checked=True, prominent=True)
        self.chk_qa = self._add_target_row(lay_t, "qa", TARGET_LABELS["qa"], checked=True, prominent=True)
        self.chk_qm = self._add_target_row(lay_t, "qm", TARGET_LABELS["qm"], checked=True, prominent=True)

        ctrl_group = QGroupBox("Run Control")
        layout.addWidget(ctrl_group)
        ctrl = QVBoxLayout(ctrl_group)

        quick = QHBoxLayout()
        method_lbl = QLabel("Method")
        method_lbl.setStyleSheet("font-size: 24px; font-weight: 900; color: #111827;")
        quick.addWidget(method_lbl)
        self.mode_box = ClickOpenComboBox()
        self.mode_box.addItems(["SEQUENTIAL", "GROUP_BO"])
        self.mode_box.setCurrentText("SEQUENTIAL")
        self.mode_box.setEditable(True)
        self.mode_box.lineEdit().setReadOnly(True)
        self.mode_box.lineEdit().setAlignment(Qt.AlignmentFlag.AlignCenter)
        for i in range(self.mode_box.count()):
            self.mode_box.setItemData(i, Qt.AlignmentFlag.AlignCenter, Qt.ItemDataRole.TextAlignmentRole)
        self.mode_box.setStyleSheet(
            "QComboBox { font-size: 24px; font-weight: 800; min-height: 44px; padding: 2px 10px; }"
        )
        quick.addWidget(self.mode_box)
        quick.addSpacing(14)
        seq_lbl = QLabel("Sequential Method")
        seq_lbl.setStyleSheet("font-size: 24px; font-weight: 900; color: #111827;")
        quick.addWidget(seq_lbl)
        self.seq_method_box = ClickOpenComboBox()
        self.seq_method_box.addItems(["BO", "TERNARY"])
        self.seq_method_box.setCurrentText("BO")
        self.seq_method_box.setEditable(True)
        self.seq_method_box.lineEdit().setReadOnly(True)
        self.seq_method_box.lineEdit().setAlignment(Qt.AlignmentFlag.AlignCenter)
        for i in range(self.seq_method_box.count()):
            self.seq_method_box.setItemData(i, Qt.AlignmentFlag.AlignCenter, Qt.ItemDataRole.TextAlignmentRole)
        self.seq_method_box.setStyleSheet(
            "QComboBox { font-size: 24px; font-weight: 800; min-height: 44px; padding: 2px 10px; }"
        )
        quick.addWidget(self.seq_method_box)
        quick.addStretch(1)
        ctrl.addLayout(quick)

        btn_row = QHBoxLayout()
        self.btn_start = QPushButton("START")
        self.btn_stop = QPushButton("PAUSE")
        self.reset_initial_btn = QPushButton("Reset To Initial")
        self.btn_stop.setEnabled(False)
        self.btn_start.clicked.connect(self.start_optimization)
        self.btn_stop.clicked.connect(self.stop_optimization)
        self.reset_initial_btn.clicked.connect(self._on_reset_to_initial)
        big_button_css = (
            "QPushButton { font-size: 22px; font-weight: 700; padding: 16px 28px; min-height: 56px; }"
        )
        self.btn_start.setStyleSheet(big_button_css + " QPushButton { background: #1f7a1f; color: white; }")
        self.btn_stop.setStyleSheet(big_button_css + " QPushButton { background: #a32020; color: white; }")
        self.reset_initial_btn.setStyleSheet(
            "QPushButton { font-size: 18px; font-weight: 700; padding: 14px 22px; min-height: 52px; background: #585f66; color: white; }"
        )
        btn_row.addWidget(self.btn_start)
        btn_row.addWidget(self.btn_stop)
        btn_row.addWidget(self.reset_initial_btn)
        ctrl.addLayout(btn_row)

        resume_group = QGroupBox("Resume From Interrupted Run")
        layout.addWidget(resume_group)
        resume_layout = QHBoxLayout(resume_group)
        self.resume_file_edit = QLineEdit()
        self.resume_file_edit.setPlaceholderText("Select previous LiniacOptimization_Log_*.csv to continue from saved data")
        self.resume_file_browse_btn = QPushButton("Browse...")
        self.resume_file_clear_btn = QPushButton("Clear")
        self.resume_file_browse_btn.clicked.connect(self._browse_resume_file)
        self.resume_file_clear_btn.clicked.connect(self._clear_resume_file)
        resume_layout.addWidget(self.resume_file_edit, stretch=1)
        resume_layout.addWidget(self.resume_file_browse_btn)
        resume_layout.addWidget(self.resume_file_clear_btn)

        self.status_lbl = QLabel("Status: IDLE")
        self.status_lbl.setObjectName("statusBadge")
        self.status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_lbl.setMinimumHeight(54)
        self.status_lbl.setWordWrap(True)
        self.status_lbl.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Minimum)
        ctrl.addWidget(self.status_lbl)

        log_group = QGroupBox("Log")
        layout.addWidget(log_group, stretch=1)
        log_l = QVBoxLayout(log_group)
        self.eval_fig = Figure(figsize=(8.5, 4.2), tight_layout=True)
        self.eval_canvas = FigureCanvas(self.eval_fig)
        self.ax_ttot = self.eval_fig.add_subplot(211)
        self.ax_downstream = self.eval_fig.add_subplot(212, sharex=self.ax_ttot)
        log_l.addWidget(self.eval_canvas, stretch=2)
        self.txt_log = QTextEdit()
        self.txt_log.setReadOnly(True)
        log_l.addWidget(self.txt_log, stretch=3)
        self._refresh_eval_plot()

        self.result_lbl = QLabel("Result: -")
        self.result_lbl.setObjectName("resultBadge")
        self.result_lbl.setWordWrap(True)
        self.result_lbl.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.result_lbl.setStyleSheet(
            "QLabel#resultBadge { "
            "font-size: 18px; font-weight: 700; color: #0f172a; "
            "background: #ecf5ff; border: 2px solid #93c5fd; border-radius: 8px; "
            "padding: 10px 12px; }"
        )
        self.result_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.result_lbl)

    def _build_config_tab(self):
        layout = QVBoxLayout(self.config_tab)
        layout.setSpacing(10)
        self.config_tab.setStyleSheet(
            "QGroupBox { font-size: 18px; font-weight: 700; margin-top: 10px; } "
            "QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; } "
            "QLabel { font-size: 16px; color: #111827; } "
            "QDoubleSpinBox, QSpinBox, QComboBox { font-size: 16px; min-height: 32px; } "
            "QPushButton { font-size: 16px; font-weight: 700; min-height: 34px; }"
        )

        grp_scan = QGroupBox("Scan Settings")
        layout.addWidget(grp_scan)
        lay_seq = QVBoxLayout(grp_scan)

        def _row(label: str, w1, w2, unit1: str, unit2: str):
            h = QHBoxLayout()
            h.addWidget(QLabel(label))
            h.addWidget(QLabel("half-range"))
            h.addWidget(w1)
            h.addWidget(QLabel(unit1))
            h.addSpacing(12)
            h.addWidget(QLabel("step"))
            h.addWidget(w2)
            h.addWidget(QLabel(unit2))
            h.addStretch()
            lay_seq.addLayout(h)

        self.sp_gun_phase_half = QDoubleSpinBox()
        self.sp_gun_phase_half.setDecimals(2)
        self.sp_gun_phase_half.setRange(0.0, 360.0)
        self.sp_gun_phase_half.setValue(GUN_PHASE_HALF_RANGE_DEG)
        self.sp_gun_phase_step = QDoubleSpinBox()
        self.sp_gun_phase_step.setDecimals(3)
        self.sp_gun_phase_step.setRange(0.001, 180.0)
        self.sp_gun_phase_step.setValue(GUN_PHASE_STEP_DEG)
        _row("GUN phase", self.sp_gun_phase_half, self.sp_gun_phase_step, "deg", "deg")

        lay_sol = QHBoxLayout()
        lay_sol.addWidget(QLabel("Solenoid current"))
        lay_sol.addWidget(QLabel("min"))
        self.sp_sol_min = QDoubleSpinBox()
        self.sp_sol_min.setDecimals(2)
        self.sp_sol_min.setRange(-1000.0, 1000.0)
        self.sp_sol_min.setValue(SOLENOIDE_MIN_A)
        lay_sol.addWidget(self.sp_sol_min)
        lay_sol.addWidget(QLabel("A"))
        lay_sol.addSpacing(12)
        lay_sol.addWidget(QLabel("max"))
        self.sp_sol_max = QDoubleSpinBox()
        self.sp_sol_max.setDecimals(2)
        self.sp_sol_max.setRange(-1000.0, 1000.0)
        self.sp_sol_max.setValue(SOLENOIDE_MAX_A)
        lay_sol.addWidget(self.sp_sol_max)
        lay_sol.addWidget(QLabel("A"))
        lay_sol.addSpacing(12)
        lay_sol.addWidget(QLabel("step"))
        self.sp_sol_step = QDoubleSpinBox()
        self.sp_sol_step.setDecimals(3)
        self.sp_sol_step.setRange(0.001, 100.0)
        self.sp_sol_step.setValue(SOLENOIDE_STEP_A)
        lay_sol.addWidget(self.sp_sol_step)
        lay_sol.addWidget(QLabel("A"))
        lay_sol.addStretch()
        lay_seq.addLayout(lay_sol)

        self.sp_l0_phase_half = QDoubleSpinBox()
        self.sp_l0_phase_half.setDecimals(2)
        self.sp_l0_phase_half.setRange(0.0, 360.0)
        self.sp_l0_phase_half.setValue(L0_PHASE_HALF_RANGE_DEG)
        self.sp_l0_phase_step = QDoubleSpinBox()
        self.sp_l0_phase_step.setDecimals(3)
        self.sp_l0_phase_step.setRange(0.001, 180.0)
        self.sp_l0_phase_step.setValue(L0_PHASE_STEP_DEG)
        _row("L0 phase", self.sp_l0_phase_half, self.sp_l0_phase_step, "deg", "deg")

        self.sp_phase_half = QDoubleSpinBox()
        self.sp_phase_half.setDecimals(2)
        self.sp_phase_half.setRange(0.0, 360.0)
        self.sp_phase_half.setValue(PHASE_HALF_RANGE_DEG)
        self.sp_phase_step = QDoubleSpinBox()
        self.sp_phase_step.setDecimals(3)
        self.sp_phase_step.setRange(0.001, 180.0)
        self.sp_phase_step.setValue(PHASE_STEP_DEG)
        _row("Klystron phase (L1-L8)", self.sp_phase_half, self.sp_phase_step, "deg", "deg")

        self.sp_qa_half = QDoubleSpinBox()
        self.sp_qa_half.setDecimals(3)
        self.sp_qa_half.setRange(0.0, 50.0)
        self.sp_qa_half.setValue(QA_HALF_RANGE_A)
        self.sp_qa_step = QDoubleSpinBox()
        self.sp_qa_step.setDecimals(4)
        self.sp_qa_step.setRange(0.0001, 10.0)
        self.sp_qa_step.setValue(QA_STEP_A)
        _row("QA magnets", self.sp_qa_half, self.sp_qa_step, "A", "A")

        self.sp_qm_half = QDoubleSpinBox()
        self.sp_qm_half.setDecimals(3)
        self.sp_qm_half.setRange(0.0, 50.0)
        self.sp_qm_half.setValue(QM_HALF_RANGE_A)
        self.sp_qm_step = QDoubleSpinBox()
        self.sp_qm_step.setDecimals(4)
        self.sp_qm_step.setRange(0.0001, 10.0)
        self.sp_qm_step.setValue(QM_STEP_A)
        _row("QM magnets", self.sp_qm_half, self.sp_qm_step, "A", "A")

        lay_timing = QHBoxLayout()
        lay_timing.addWidget(QLabel("Timing"))
        lay_timing.addWidget(QLabel("step"))
        self.sp_timing_step = QDoubleSpinBox()
        self.sp_timing_step.setDecimals(3)
        self.sp_timing_step.setRange(0.001, 1000.0)
        self.sp_timing_step.setValue(TIMING_STEP_NS)
        lay_timing.addWidget(self.sp_timing_step)
        lay_timing.addWidget(QLabel("ns"))
        lay_timing.addSpacing(12)
        lay_timing.addWidget(QLabel("half-steps"))
        self.sp_timing_half_steps = QSpinBox()
        self.sp_timing_half_steps.setRange(1, 200)
        self.sp_timing_half_steps.setValue(TIMING_HALF_STEPS)
        lay_timing.addWidget(self.sp_timing_half_steps)
        lay_timing.addStretch()
        lay_seq.addLayout(lay_timing)

        grp_score = QGroupBox("Scoring")
        layout.addWidget(grp_score)
        lay_score = QHBoxLayout(grp_score)
        lay_score.addWidget(QLabel("w_t (Ttot)"))
        self.sp_score_w_ttot = QDoubleSpinBox()
        self.sp_score_w_ttot.setDecimals(3)
        self.sp_score_w_ttot.setRange(-1000.0, 1000.0)
        self.sp_score_w_ttot.setValue(1.0)
        lay_score.addWidget(self.sp_score_w_ttot)
        lay_score.addSpacing(12)
        lay_score.addWidget(QLabel("w_c (ICT downstream)"))
        self.sp_score_w_downstream = QDoubleSpinBox()
        self.sp_score_w_downstream.setDecimals(3)
        self.sp_score_w_downstream.setRange(-1000.0, 1000.0)
        self.sp_score_w_downstream.setValue(1.0)
        lay_score.addWidget(self.sp_score_w_downstream)
        lay_score.addSpacing(12)
        lay_score.addWidget(QLabel("Downstream ICT"))
        self.cb_downstream_ict = QComboBox()
        self.cb_downstream_ict.addItems(["DR", "LNE", "BTE", "LN0", "GUN", "BTM"])
        self.cb_downstream_ict.setCurrentText("DR")
        lay_score.addWidget(self.cb_downstream_ict)
        lay_score.addStretch(1)

        grp_adv = QGroupBox("Advanced")
        layout.addWidget(grp_adv)
        lay_adv = QHBoxLayout(grp_adv)
        lay_adv.addWidget(QLabel("Settle time"))
        self.sp_settle_sec = QDoubleSpinBox()
        self.sp_settle_sec.setDecimals(2)
        self.sp_settle_sec.setRange(0.0, 120.0)
        self.sp_settle_sec.setValue(SETTLE_SEC_DEFAULT)
        lay_adv.addWidget(self.sp_settle_sec)
        lay_adv.addWidget(QLabel("s"))
        lay_adv.addStretch(1)

        path_group = QGroupBox("Data Save Location")
        layout.addWidget(path_group)
        lay_p = QHBoxLayout(path_group)
        self.lbl_path = QLabel(str(self.save_path))
        self.lbl_path.setStyleSheet(
            "font-size: 18px; color: #0f172a; background: #ecf5ff; border: 2px solid #93c5fd; "
            "border-radius: 8px; padding: 8px 10px;"
        )
        self.btn_browse = QPushButton("Browse...")
        self.btn_browse.clicked.connect(self.browse_folder)
        self.btn_browse.setStyleSheet(
            "QPushButton { font-size: 18px; font-weight: 700; min-height: 46px; "
            "padding: 10px 18px; background: #585f66; color: white; }"
        )
        lay_p.addWidget(self.lbl_path, stretch=1)
        lay_p.addWidget(self.btn_browse)

        layout.addStretch(1)

    def _add_target_row(
        self,
        parent_layout,
        key: str,
        text: str,
        *,
        checked: bool,
        prominent: bool,
        indent: int = 0,
        show_value: bool = True,
    ):
        row = QHBoxLayout()
        row.setSpacing(10)
        if indent > 0:
            row.addSpacing(indent)

        box = QCheckBox(text)
        box.setChecked(bool(checked))
        if prominent:
            box.setProperty("knobCheck", True)
        else:
            box.setStyleSheet("font-size: 18px; font-weight: 500; color: #334155;")
        row.addWidget(box)

        status_lbl = QLabel("IDLE")
        status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        status_lbl.setMinimumWidth(88)
        status_lbl.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        row.addWidget(status_lbl)

        if show_value:
            value_lbl = QLabel("Current: -")
            value_lbl.setWordWrap(True)
            value_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            value_lbl.setStyleSheet("font-size: 14px; color: #475569;")
            row.addWidget(value_lbl, stretch=1)
            self.target_value_labels[key] = value_lbl
        else:
            row.addStretch(1)

        parent_layout.addLayout(row)

        self.target_checks[key] = box
        self.target_status_labels[key] = status_lbl
        self._set_target_state(key, "idle")
        return box

    def _set_target_state(self, key: str, state: str):
        lbl = self.target_status_labels.get(key)
        if lbl is None:
            return
        palette = {
            "idle": ("IDLE", "#334155", "#e2e8f0", "#94a3b8"),
            "waiting": ("WAITING", "#1d4ed8", "#dbeafe", "#60a5fa"),
            "running": ("RUNNING", "#166534", "#dcfce7", "#4ade80"),
            "done": ("DONE", "#1e3a8a", "#dbeafe", "#3b82f6"),
            "error": ("ERROR", "#991b1b", "#fee2e2", "#f87171"),
        }
        text, fg, bg, bd = palette.get(str(state).lower(), palette["idle"])
        lbl.setText(text)
        lbl.setStyleSheet(
            "QLabel {"
            f"font-size: 12px; font-weight: 800; color: {fg}; "
            f"background: {bg}; border: 1px solid {bd}; "
            "border-radius: 9px; padding: 5px 8px; }"
        )
        self.target_states[key] = str(state).lower()

    def _reset_target_states(self):
        for key in list(self.target_status_labels.keys()):
            self._set_target_state(key, "idle")

    def _selected_target_keys(self, mode: Optional[str] = None) -> List[str]:
        mode_text = str(mode or self.mode_box.currentText())
        keys: List[str] = []
        if self.chk_gun_sol_l0_phase.isChecked():
            keys.append("gun_sol_l0")
        if self.chk_kly_phase.isChecked():
            keys.append("kly_phase")
            if mode_text == "GROUP_BO":
                if self.chk_kly_group1.isChecked():
                    keys.append("kly_group_1")
                if self.chk_kly_group2.isChecked():
                    keys.append("kly_group_2")
        if self.chk_timing.isChecked():
            keys.append("timing")
        if self.chk_qa.isChecked():
            keys.append("qa")
        if self.chk_qm.isChecked():
            keys.append("qm")
        return keys

    def _prepare_target_states_for_run(self, mode: str):
        self._reset_target_states()
        for key in self._selected_target_keys(mode):
            self._set_target_state(key, "waiting")

    def _finalize_target_states_after_run(self):
        for key, state in list(self.target_states.items()):
            if state in ("waiting", "running"):
                self._set_target_state(key, "idle")

    def _update_value_labels(self, display_values: Dict[str, str]):
        for key, lbl in self.target_value_labels.items():
            txt = str(display_values.get(key, "")).strip()
            lbl.setText(f"Current: {txt}" if txt else "Current: -")

    def _ensure_interface(self) -> InterfaceATF2_Linac:
        if self.interface is None:
            self.interface = InterfaceATF2_Linac(nsamples=1)
        return self.interface

    def _refresh_current_values(self, *_args):
        try:
            interface = self._ensure_interface()
            pv_values: Dict[str, float] = {}
            for specs in TARGET_VALUE_SPECS.values():
                for _label, pv_write, pv_read, _unit in specs:
                    if pv_write in pv_values:
                        continue
                    pv_values[pv_write] = float(interface.read_current(pv_write, pv_read))
            self._update_value_labels(build_display_value_texts(pv_values))
            self._current_value_refresh_failed = False
        except Exception as exc:
            self._update_value_labels({})
            if not self._current_value_refresh_failed:
                self.append_log(f"[UI] current value refresh failed: {exc}")
            self._current_value_refresh_failed = True

    def _auto_refresh_current_values(self):
        if self.worker is not None and self.worker.isRunning():
            return
        self._refresh_current_values()

    def _reset_eval_plot(self, downstream_label: Optional[str] = None):
        self.live_eval_index = []
        self.live_ttot = []
        self.live_downstream = []
        if downstream_label is not None:
            self.live_downstream_label = str(downstream_label)
        self._refresh_eval_plot()

    def _refresh_eval_plot(self):
        if not hasattr(self, "ax_ttot"):
            return
        self.ax_ttot.clear()
        self.ax_downstream.clear()

        self.ax_ttot.set_title("Transmission vs evaluation")
        self.ax_ttot.set_ylabel("Ttot")
        self.ax_ttot.grid(True, alpha=0.3)

        down_label = str(self.live_downstream_label or "Downstream ICT")
        self.ax_downstream.set_title(f"{down_label} vs evaluation")
        self.ax_downstream.set_ylabel(down_label)
        self.ax_downstream.set_xlabel("Evaluation")
        self.ax_downstream.grid(True, alpha=0.3)

        if self.live_eval_index:
            self.ax_ttot.plot(self.live_eval_index, self.live_ttot, marker="o", color="#2563eb", linewidth=1.8)
            self.ax_downstream.plot(
                self.live_eval_index, self.live_downstream, marker="o", color="#0f766e", linewidth=1.8
            )

        self.eval_canvas.draw_idle()

    def _on_worker_progress(self, payload: dict):
        kind = str(payload.get("kind", ""))
        if kind == "group_state":
            key = str(payload.get("group_key", ""))
            state = str(payload.get("state", "idle")).lower()
            if state == "done":
                self._set_target_state(key, "done")
            elif state == "running":
                self._set_target_state(key, "running")
                label = TARGET_LABELS.get(key, key)
                if self._run_mode:
                    self._set_status(f"Status: RUNNING {self._run_mode} | {label}", state="running")
            else:
                self._set_target_state(key, state)
            return

        if kind == "current_values":
            self._update_value_labels(dict(payload.get("display_values") or {}))
            return

        if kind == "run_error":
            self._run_failed = True
            self._set_status("Status: FAILED", state="error")
            return

        if kind == "evaluation":
            self._update_value_labels(dict(payload.get("display_values") or {}))
            self.live_eval_index.append(int(payload.get("eval_index", len(self.live_eval_index) + 1)))
            self.live_ttot.append(float(payload.get("ttot", float("nan"))))
            self.live_downstream.append(float(payload.get("downstream_value", float("nan"))))
            self.live_downstream_label = str(payload.get("downstream_label", self.live_downstream_label))
            self._refresh_eval_plot()
            if self._run_mode:
                self._set_status(
                    f"Status: RUNNING {self._run_mode} | eval={self.live_eval_index[-1]} | Ttot={self.live_ttot[-1]:.6f}",
                    state="running",
                )

    def _set_status(self, text: str, *, state: str = "info") -> None:
        palette = {
            "idle": ("#374151", "#e5e7eb", "#9ca3af"),
            "running": ("#14532d", "#dcfce7", "#22c55e"),
            "paused": ("#713f12", "#fef3c7", "#f59e0b"),
            "warning": ("#7c2d12", "#ffedd5", "#fb923c"),
            "error": ("#7f1d1d", "#fee2e2", "#ef4444"),
            "success": ("#1e3a8a", "#dbeafe", "#3b82f6"),
            "info": ("#1f2937", "#e5e7eb", "#9ca3af"),
        }
        fg, bg, bd = palette.get(str(state).lower(), palette["info"])
        self.status_lbl.setText(text)
        self.status_lbl.setStyleSheet(
            "QLabel#statusBadge {"
            f"font-size: 24px; font-weight: 800; color: {fg}; "
            f"background: {bg}; border: 2px solid {bd}; "
            "border-radius: 10px; padding: 8px 14px; }"
        )

    def _update_mode_ui(self):
        is_seq = (self.mode_box.currentText() == "SEQUENTIAL")
        self.seq_method_box.setEnabled(is_seq)
        enable_kly_subgroups = (self.mode_box.currentText() == "GROUP_BO") and self.chk_kly_phase.isChecked()
        self.chk_kly_group1.setEnabled(enable_kly_subgroups)
        self.chk_kly_group2.setEnabled(enable_kly_subgroups)

    def _capture_machine_origin(self, config: Dict[str, Any]) -> Dict[str, Any]:
        interface = self._ensure_interface()
        setpoints = {pv: float(interface.read_current(pv, None)) for pv in RESTORE_PVS}
        initial_ict = interface.read_icts_for_optimizer(
            downstream_key=str(config.get("downstream_ict", "DR")).upper().replace("LN0", "L0"),
            dr_samples=3,
            dr_interval_s=0.5,
        )
        ttot = float(initial_ict.get("Ttot", float("nan")))
        downstream_key = str(config.get("downstream_ict", "DR")).upper()
        downstream_lookup = "L0" if downstream_key == "LN0" else downstream_key
        downstream_value = float(initial_ict.get(downstream_lookup, float("nan")))
        score = float(config.get("score_w_ttot", 1.0)) * ttot + float(config.get("score_w_downstream", 1.0)) * downstream_value
        return {
            "timestamp": datetime.datetime.now().isoformat(timespec="seconds"),
            "mode": str(config.get("mode", "")),
            "config": dict(config),
            "initial_setpoints": setpoints,
            "initial_ict": initial_ict,
            "initial_score": score,
        }

    def _apply_machine_origin(self, origin: Dict[str, Any]):
        setpoints = dict(origin.get("initial_setpoints", {}) or {})
        if not setpoints:
            raise ValueError("No initial setpoints were stored for this run.")
        self._ensure_interface().pv_put_many({str(k): float(v) for k, v in setpoints.items()})

    def _find_resume_snapshot_file(self, csv_path: Path) -> Optional[Path]:
        csv_path = csv_path.expanduser().resolve()
        stem = csv_path.stem
        tag = stem.split("LiniacOptimization_Log_", 1)[-1] if "LiniacOptimization_Log_" in stem else ""
        parent = csv_path.parent
        if tag:
            candidate = parent / f"InitialSnapshot_{tag}.json"
            if candidate.exists():
                return candidate
        tagged = sorted(parent.glob("InitialSnapshot_*.json"))
        return tagged[-1] if tagged else None

    def _load_resume_snapshot_state(self, csv_path: Path) -> Optional[Dict[str, Any]]:
        snap_path = self._find_resume_snapshot_file(csv_path)
        if snap_path is None:
            return None
        with open(snap_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _apply_config_to_ui(self, payload: Dict[str, Any]):
        mode = str(payload.get("mode", self.mode_box.currentText()))
        if mode not in ("SEQUENTIAL", "GROUP_BO"):
            mode = "SEQUENTIAL"
        self.mode_box.setCurrentText(mode)
        self.seq_method_box.setCurrentText(str(payload.get("seq_method", self.seq_method_box.currentText())))
        self.chk_gun_sol_l0_phase.setChecked(bool(payload.get("gun_sol_l0_phase", self.chk_gun_sol_l0_phase.isChecked())))
        self.chk_kly_phase.setChecked(bool(payload.get("kly_phase", self.chk_kly_phase.isChecked())))
        self.chk_kly_group1.setChecked(bool(payload.get("grp_L1_4", self.chk_kly_group1.isChecked())))
        self.chk_kly_group2.setChecked(bool(payload.get("grp_L5_8", self.chk_kly_group2.isChecked())))
        self.chk_timing.setChecked(bool(payload.get("timing", self.chk_timing.isChecked())))
        self.chk_qa.setChecked(bool(payload.get("qa", self.chk_qa.isChecked())))
        self.chk_qm.setChecked(bool(payload.get("qm", self.chk_qm.isChecked())))
        self.sp_settle_sec.setValue(float(payload.get("settle_sec", self.sp_settle_sec.value())))
        self.sp_score_w_ttot.setValue(float(payload.get("score_w_ttot", self.sp_score_w_ttot.value())))
        self.sp_score_w_downstream.setValue(float(payload.get("score_w_downstream", self.sp_score_w_downstream.value())))
        downstream = str(payload.get("downstream_ict", self.cb_downstream_ict.currentText()))
        if self.cb_downstream_ict.findText(downstream) >= 0:
            self.cb_downstream_ict.setCurrentText(downstream)
        self.sp_gun_phase_half.setValue(float(payload.get("gun_phase_half_range_deg", self.sp_gun_phase_half.value())))
        self.sp_gun_phase_step.setValue(float(payload.get("gun_phase_step_deg", self.sp_gun_phase_step.value())))
        self.sp_sol_min.setValue(float(payload.get("solenoide_min_a", self.sp_sol_min.value())))
        self.sp_sol_max.setValue(float(payload.get("solenoide_max_a", self.sp_sol_max.value())))
        self.sp_sol_step.setValue(float(payload.get("solenoide_step_a", self.sp_sol_step.value())))
        self.sp_l0_phase_half.setValue(float(payload.get("l0_phase_half_range_deg", self.sp_l0_phase_half.value())))
        self.sp_l0_phase_step.setValue(float(payload.get("l0_phase_step_deg", self.sp_l0_phase_step.value())))
        self.sp_phase_half.setValue(float(payload.get("phase_half_range_deg", self.sp_phase_half.value())))
        self.sp_phase_step.setValue(float(payload.get("phase_step_deg", self.sp_phase_step.value())))
        self.sp_qa_half.setValue(float(payload.get("qa_half_range_a", self.sp_qa_half.value())))
        self.sp_qa_step.setValue(float(payload.get("qa_step_a", self.sp_qa_step.value())))
        self.sp_qm_half.setValue(float(payload.get("qm_half_range_a", self.sp_qm_half.value())))
        self.sp_qm_step.setValue(float(payload.get("qm_step_a", self.sp_qm_step.value())))
        self.sp_timing_step.setValue(float(payload.get("timing_step_ns", self.sp_timing_step.value())))
        self.sp_timing_half_steps.setValue(int(payload.get("timing_half_steps", self.sp_timing_half_steps.value())))
        self._update_mode_ui()

    def _browse_resume_file(self):
        current = self.resume_file_edit.text().strip() or str(self.save_path.resolve())
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select interrupted Linac log CSV",
            current,
            "CSV (*.csv);;All files (*)",
        )
        if not path:
            return
        self.resume_file_edit.setText(path)
        self.resume_snapshot_state = None
        try:
            snapshot = self._load_resume_snapshot_state(Path(path))
            if snapshot:
                self.resume_snapshot_state = snapshot
                cfg_payload = dict(snapshot.get("config", {}) or {})
                if cfg_payload:
                    self._apply_config_to_ui(cfg_payload)
                self.append_log(f"Loaded resume snapshot from {self._find_resume_snapshot_file(Path(path))}")
                self._set_status(f"Status: resume file loaded -> {path}", state="info")
            else:
                self._set_status(f"Status: resume file selected -> {path}", state="info")
        except Exception as exc:
            self.append_log(f"Resume snapshot load failed: {exc}")
            self._set_status(f"Status: resume file selected -> {path}", state="info")

    def _clear_resume_file(self):
        self.resume_file_edit.clear()
        self.resume_snapshot_state = None

    def _update_result_label(self, text: Optional[str] = None):
        if text is not None:
            self.result_lbl.setText(str(text))
            return
        csv_path = self.current_measurements_csv
        if csv_path is None or (not csv_path.exists()):
            self.result_lbl.setText("Result: -")
            return
        best_row: Optional[Dict[str, Any]] = None
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    score = float(row.get("Score", "nan"))
                except Exception:
                    continue
                if not np.isfinite(score):
                    continue
                if best_row is None or score > float(best_row.get("Score", float("-inf"))):
                    best_row = dict(row)
        if best_row is None:
            self.result_lbl.setText(f"Result: no valid rows yet | file={csv_path}")
            return
        group = str(best_row.get("Group", "-"))
        device = str(best_row.get("DeviceLabel", "-"))
        ttot = float(best_row.get("Ttot", float("nan")))
        score = float(best_row.get("Score", float("nan")))
        downstream_name = str(best_row.get("ScoreDownstreamICT", self.live_downstream_label))
        downstream_column = "ICT_L0" if downstream_name == "LN0" else f"ICT_{downstream_name}"
        try:
            downstream_value = float(best_row.get(downstream_column, float("nan")))
        except Exception:
            downstream_value = float("nan")
        self.result_lbl.setText(
            f"Result: best score={score:.6g}, Ttot={ttot:.6f}, {downstream_name}={downstream_value:.6g}, "
            f"group={group}, device={device}, file={csv_path}"
        )

    def _on_reset_to_initial(self):
        if self.worker is not None and self.worker.isRunning():
            QMessageBox.warning(self, "Busy", "Stop the optimizer before resetting to the initial state.")
            return
        if not self.current_machine_origin:
            QMessageBox.information(
                self,
                "No Initial State",
                "No start-time machine state is stored yet. Press START once before using reset.",
            )
            return
        try:
            self._apply_machine_origin(self.current_machine_origin)
        except Exception as exc:
            self.append_log(f"Reset to initial failed: {exc}")
            QMessageBox.warning(self, "Reset failed", str(exc))
            return
        self._refresh_current_values()
        self._set_status("Status: restored to initial machine state", state="success")
        self.append_log(f"Reset to initial completed: restored {len(self.current_machine_origin.get('initial_setpoints', {}))} channels")

    def browse_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Save Directory", str(self.save_path))
        if folder:
            self.save_path = Path(folder)
            self.lbl_path.setText(str(self.save_path))

    def start_optimization(self):
        mode = str(self.mode_box.currentText())
        resume_path_text = self.resume_file_edit.text().strip()
        if resume_path_text:
            resume_path = Path(resume_path_text).expanduser()
            if not resume_path.exists():
                QMessageBox.warning(self, "Resume file", f"Resume CSV was not found:\n{resume_path}")
                return
        config = {
            "mode": mode,
            "settle_sec": float(self.sp_settle_sec.value()),
            "score_w_ttot": float(getattr(self, "sp_score_w_ttot").value()),
            "score_w_downstream": float(getattr(self, "sp_score_w_downstream").value()),
            "downstream_ict": str(getattr(self, "cb_downstream_ict").currentText()),
            "lbo_iters": 4,
            "lbo_line_samples": 11,
            "group_bo_passes": 2,
            "group_bo_score_eps": 0.0,
            "reuse_initial_eval": True,
            "gun_sol_l0_phase": self.chk_gun_sol_l0_phase.isChecked(),
            "kly_phase": self.chk_kly_phase.isChecked(),
            "timing": self.chk_timing.isChecked(),
            "qa": self.chk_qa.isChecked(),
            "qm": self.chk_qm.isChecked(),
            "grp_L1_4": self.chk_kly_group1.isChecked(),
            "grp_L5_8": self.chk_kly_group2.isChecked(),
            # Sequential method + scan settings
            "seq_method": str(self.seq_method_box.currentText()),
            "gun_phase_half_range_deg": float(getattr(self, "sp_gun_phase_half").value()),
            "gun_phase_step_deg": float(getattr(self, "sp_gun_phase_step").value()),
            "solenoide_min_a": float(getattr(self, "sp_sol_min").value()),
            "solenoide_max_a": float(getattr(self, "sp_sol_max").value()),
            "solenoide_step_a": float(getattr(self, "sp_sol_step").value()),
            "l0_phase_half_range_deg": float(getattr(self, "sp_l0_phase_half").value()),
            "l0_phase_step_deg": float(getattr(self, "sp_l0_phase_step").value()),
            "phase_half_range_deg": float(getattr(self, "sp_phase_half").value()),
            "phase_step_deg": float(getattr(self, "sp_phase_step").value()),
            "qa_half_range_a": float(getattr(self, "sp_qa_half").value()),
            "qa_step_a": float(getattr(self, "sp_qa_step").value()),
            "qm_half_range_a": float(getattr(self, "sp_qm_half").value()),
            "qm_step_a": float(getattr(self, "sp_qm_step").value()),
            "timing_step_ns": float(getattr(self, "sp_timing_step").value()),
            "timing_half_steps": int(getattr(self, "sp_timing_half_steps").value()),
            "resume_csv_path": str(Path(resume_path_text).expanduser().resolve()) if resume_path_text else "",
        }

        if not (config["gun_sol_l0_phase"] or config["kly_phase"] or config["timing"] or config["qa"] or config["qm"]):
            QMessageBox.warning(self, "Warning", "Please select at least one target.")
            return
        if config["mode"] == "GROUP_BO" and config["kly_phase"] and not (config["grp_L1_4"] or config["grp_L5_8"]):
            QMessageBox.warning(self, "Warning", "Please select Group 1 and/or Group 2 for Klystron phase.")
            return
        try:
            self.current_machine_origin = self._capture_machine_origin(config)
        except Exception as exc:
            QMessageBox.critical(self, "Machine readback error", str(exc))
            return

        # UI state
        self._run_mode = mode
        self._run_failed = False
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.txt_log.clear()
        self._update_result_label("Result: running...")
        self._prepare_target_states_for_run(mode)
        self._reset_eval_plot(config["downstream_ict"])
        self._refresh_current_values()
        self._set_status(f"Status: RUNNING {mode}", state="running")
        for w in [
            self.chk_gun_sol_l0_phase, self.chk_kly_phase, self.chk_kly_group1, self.chk_kly_group2,
            self.chk_timing, self.chk_qa, self.chk_qm,
            self.mode_box, self.seq_method_box, self.btn_browse, self.config_tab,
            self.resume_file_edit, self.resume_file_browse_btn, self.resume_file_clear_btn
        ]:
            w.setEnabled(False)

        self.worker = OptimizationWorker(config, self.save_path)
        self.current_measurements_csv = Path(self.worker.csv_path)
        self.worker.log_signal.connect(self.append_log)
        self.worker.progress_signal.connect(self._on_worker_progress)
        self.worker.finished_signal.connect(self.optimization_finished)
        self.worker.start()

    def stop_optimization(self):
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.btn_stop.setEnabled(False)
            self._set_status("Status: pause requested", state="paused")

    def optimization_finished(self):
        self.worker = None
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        for w in [
            self.chk_gun_sol_l0_phase, self.chk_kly_phase, self.chk_kly_group1, self.chk_kly_group2,
            self.chk_timing, self.chk_qa, self.chk_qm,
            self.mode_box, self.seq_method_box, self.btn_browse, self.config_tab,
            self.resume_file_edit, self.resume_file_browse_btn, self.resume_file_clear_btn
        ]:
            w.setEnabled(True)
        self._update_mode_ui()
        self._finalize_target_states_after_run()
        self._refresh_current_values()
        self._update_result_label()
        if self._run_failed:
            self._set_status("Status: FAILED", state="error")
        else:
            self._set_status("Status: DONE", state="success")
        self._run_mode = ""
        if self._run_failed:
            QMessageBox.warning(self, "Finished with Error", "Optimization ended with an error. Please check the log.")
        else:
            QMessageBox.information(self, "Finished", "Optimization process finished.")

    def append_log(self, text: str):
        self.txt_log.append(text)
        sb = self.txt_log.verticalScrollBar()
        sb.setValue(sb.maximum())


if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = MainWindow()
    w.show()
    sys.exit(app.exec())
