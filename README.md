# FlightSimulator's `Interface` description

This class defines how the user interacts with the real or simulated machine when reading beam instrumentation and steering devices and for writing corrector set-points in a control system for the specific accelerator facility. It wraps common operations on BPMs, ICTs, and corrector magnets.

---

## Constructor

### `__init__(nsamples: int = 1)`

Initializes the interface and builds internal lists of devices (sequence, BPMs, correctors) and EPICS-like indexes.

**Parameters**

* `nsamples` — number of consecutive samples to take when reading BPMs (with a 1 s pause between samples).

---

## Identification

### `get_name() -> str`

Returns a short identifier of this interface: e.g., `"ATF2_Ext"`.

---

## Lattice & device inventory

### `get_sequence() -> list[str]`

Returns the full **beamline-ordered** list of device names (BPMs and correctors).

### `get_bpms_names() -> list[str]`

Returns the list of BPM names known to EPICS and present in the configured sequence.

### `get_correctors_names() -> list[str]`

Returns the list of corrector names (both planes) present in the configured sequence.

### `get_hcorrectors_names() -> list[str]`

Returns the subset of correctors that are **horizontal** (names starting with `ZH`).

### `get_vcorrectors_names() -> list[str]`

Returns the subset of correctors that are **vertical** (names starting with `ZV`).

### `get_elements_position(names: list[str] | str) -> list[int]`

Returns the **sequence indices** of the specified element name(s). Useful to map devices to their lattice order.

---

## Beam instrumentation reads

### `get_bpms() -> dict`

Reads BPM data from `LINAC:monitors` for `nsamples` shots, one per second.
**Returns** a dictionary:

* `"names"` — list of BPM names
* `"x"` — `(nsamples × NBPM)` array of **x** positions in **mm**
* `"y"` — `(nsamples × NBPM)` array of **y** positions in **mm**
* `"tmit"` — `(nsamples × NBPM)` array of intensity/charge (TMIT), **zeroed where BPM status ≠ 1**

> Note: Internally selects only those rows corresponding to `self.bpms` using `self.bpm_indexes`.

### `get_icts() -> dict`

Reads charge from all configured ICT PVs.
**Returns** a dictionary:

* `"names"` — list of ICT PV names
* `"charge"` — 1-D NumPy array of the corresponding readings

---

## Corrector reads & writes

### `get_correctors() -> dict`

Reads corrector strengths for all devices in `self.corrs`.
**Returns** a dictionary:

* `"names"` — list of corrector names
* `"bdes"` — desired/setpoint currents from `:<name>:currentWrite`
* `"bact"` — readback/actual currents from `:<name>:currentRead`

### `push(names: list[str] | str, corr_vals: list[float] | np.ndarray | float) -> None`

**Sets** the desired current for one or more correctors. If a single name/value is provided, it’s coerced to a list. Lengths must match. Writes to `:<name>:currentWrite` and sleeps 1 s.

### `vary_correctors(names: list[str] | str, corr_vals: list[float] | np.ndarray | float) -> None`

**Increments** the desired current for one or more correctors by the given value(s). Reads current value from `:<name>:currentWrite`, adds the increment, writes back, then sleeps 1 s.

---

## Placeholder (not implemented)

These exist for API completeness but currently do nothing:

### `change_energy(*args) -> None`

No-op placeholder for changing beam energy.

### `reset_energy(*args) -> None`

No-op placeholder for restoring nominal energy.

### `change_intensity(*args) -> None`

No-op placeholder for changing beam intensity.

### `reset_intensity(*args) -> None`

No-op placeholder for restoring nominal intensity.

---

## Notes & best practices

* **Sampling**: Increase `nsamples` in the constructor if you want automatic multi-shot acquisition with per-shot 1 s spacing.
* **Units**: BPM positions are returned in **mm**; intensities are passed through the BPM status gate.
* **Safety**: `push` and `vary_correctors` talk directly to setpoint PVs. Use with care in live machines and follow your facility’s MPS/permit procedures.
* **Extensibility**: The placeholder energy/intensity methods can be filled with site-specific PVs or finite-state-machine hooks if needed.
