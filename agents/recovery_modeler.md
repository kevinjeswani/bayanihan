# recovery_modeler — Implement recovery.py and create ph_redi_params.json

**Phase:** P6
**Status:** COMPLETE (as of 2026-06-26)
**Model tier:** Sonnet (research + implementation)
**Blocked on:** thesis_extractor (P0) must produce `docs/thesis/data/ph_redi_params.yaml` before this agent starts. Can run in parallel with pelicun_dbformatter (P1), edp_normalizer (P2), and archetype_modeler (P3).
**Unblocks:** thesis_replication_validator (P7)

---

## Purpose

Implement `bayanihan/recovery.py` using the REDi methodology (Almufti & Willford 2013) natively via Pelicun's repair-class machinery and Philippine-calibrated impeding factor distributions. The `arup-group/REDi` GitHub repo returned 404 as of 2026-06-26 — there is no PyREDi dependency. The methodology is implemented from first principles using the thesis parameters.

---

## Inputs

- `docs/thesis/data/ph_redi_params.yaml` — Philippine-calibrated REDi impeding factor distributions (from thesis_extractor)
- `docs/learnings/stack_research.md` — existing research notes on PyREDi and REDi implementation options
- `docs/reference/` — any captured reference materials (check for Aljawhari et al. 2023 summary)
- Pelicun installed package source — repair-class documentation and API

---

## Outputs

- `bayanihan/recovery.py` — fully implemented (replaces any stub)
- `bayanihan/data/ph_redi_params.json` — validated against the `ImpedingFactorParams` pydantic model
- `test/test_recovery.py` — tests that `compute_recovery()` returns physically plausible outputs

---

## Execution strategy

### Step 1 — Read existing research and stubs

Read `docs/learnings/stack_research.md` first. This file may contain prior conclusions about the PyREDi 404 situation and alternative approaches — do not repeat research already done.

Read `docs/reference/` for any Aljawhari et al. 2023 summary. This paper specifies distribution forms for impeding factors (beta for repair time, GEV for impeding factors). If the summary exists, use the distribution forms it specifies. If it does not exist, use the forms described in the thesis.

Read any existing stub in `bayanihan/recovery.py`. Note what function signatures are already defined — preserve them.

### Step 2 — Read ph_redi_params.yaml

Load `docs/thesis/data/ph_redi_params.yaml`. Extract:
- Impeding factor names (inspection, financing, engineering mobilization, contractor mobilization, permitting)
- Distribution type for each factor (beta, lognormal, or GEV — as specified in thesis or Aljawhari et al.)
- Distribution parameters (median, dispersion, or alpha/beta/mu/sigma as appropriate)
- Philippine-specific calibration notes

If any value has `provenance_confidence: low`, flag it in `docs/learnings/recovery_modeler_low_confidence.md` and use a conservative default with a comment.

### Step 3 — Read Pelicun's repair-class API

Find how Pelicun handles repair time in its `DL_calculation` output. Specifically:
- What repair-time outputs does Pelicun's damage/loss engine produce?
- How are repair classes (structural, non-structural drift-sensitive, non-structural acceleration-sensitive) aggregated?
- Does Pelicun have a built-in recovery model, or does it only produce raw repair times?

Write findings to `docs/learnings/pelicun_repair_class_notes.md`.

### Step 4 — Implement ImpedingFactorParams pydantic model

In `bayanihan/recovery.py`, define:

```python
class ImpedingFactorDist(BaseModel):
    distribution: Literal["beta", "lognormal", "gev"]
    # parameters vary by distribution type — use discriminated union or flexible dict
    params: dict[str, float]
    provenance: str  # thesis table reference

class ImpedingFactorParams(BaseModel):
    inspection: ImpedingFactorDist
    financing: ImpedingFactorDist
    engineering_mobilization: ImpedingFactorDist
    contractor_mobilization: ImpedingFactorDist
    permitting: ImpedingFactorDist
    model_version: str  # "ph_redi_v1" or similar
```

Adjust field names to match what `ph_redi_params.yaml` actually contains.

### Step 5 — Write ph_redi_params.json

Convert `docs/thesis/data/ph_redi_params.yaml` to `bayanihan/data/ph_redi_params.json`:
- Validate against `ImpedingFactorParams` (run `ImpedingFactorParams.model_validate(data)` before writing)
- If validation fails, fix the pydantic model to match the YAML structure — do not silently discard fields
- Write the validated model as JSON using `model.model_dump_json(indent=2)`

### Step 6 — Implement load_ph_params()

```python
def load_ph_params() -> ImpedingFactorParams:
    """Load Philippine REDi impeding factor parameters from package data."""
```

- Load from `bayanihan/data/ph_redi_params.json` via `importlib.resources`
- Parse and validate with `ImpedingFactorParams.model_validate_json()`
- Raise a clear error if the file is missing or malformed

### Step 7 — Implement sample_impeding_delays()

```python
def sample_impeding_delays(
    params: ImpedingFactorParams,
    n_samples: int,
    damage_state: str,
    rng: np.random.Generator | None = None,
) -> dict[str, np.ndarray]:
    """Sample impeding factor delays in days for each factor."""
```

- Sample from the specified distribution for each factor
- Return a dict mapping factor name to array of shape (n_samples,)
- Use `np.random.default_rng()` if `rng` is None (for reproducibility in tests, callers pass a seeded RNG)
- Impeding factor delays vary by damage state — implement the REDi lookup table for this dependency

### Step 8 — Implement compute_recovery()

```python
def compute_recovery(
    repair_time_samples: np.ndarray,
    damage_state: str,
    params: ImpedingFactorParams | None = None,
    rng: np.random.Generator | None = None,
) -> dict[str, np.ndarray]:
    """Compute reoccupancy, functional recovery, and full recovery time distributions."""
```

REDi recovery milestone definitions:
- **Reoccupancy** (`reoccupancy_days`): inspection delay + repair time to reoccupancy threshold
- **Functional recovery** (`functional_recovery_days`): reoccupancy + utility restoration + contractor mobilization
- **Full recovery** (`full_recovery_days`): all impeding factors + full repair time

Return dict with keys: `"reoccupancy_days"`, `"functional_recovery_days"`, `"full_recovery_days"` — each an array of shape `(n_samples,)` in days.

If `params` is None, call `load_ph_params()` internally.

### Step 9 — Write tests

Write `test/test_recovery.py`:

```python
def test_load_ph_params_validates():
    """load_ph_params() loads without pydantic validation errors."""

def test_compute_recovery_returns_non_negative():
    """All recovery time arrays contain only non-negative values."""

def test_full_recovery_geq_reoccupancy():
    """Median full_recovery_days >= median reoccupancy_days (physically required)."""

def test_compute_recovery_shapes(n_samples=500):
    """All output arrays have shape (n_samples,)."""

def test_compute_recovery_varies_by_damage_state():
    """Severe damage states produce longer median recovery times than minor ones."""
```

### Step 10 — Run tests

Run `pytest test/test_recovery.py -v`. Fix failures in the implementation, not the tests.

### Step 11 — Decision log

Append the reporting block to `docs/orchestration/decision_log.md`.

---

## Success criteria

1. `load_ph_params()` executes without pydantic validation errors.
2. `bayanihan/data/ph_redi_params.json` is valid JSON that passes `ImpedingFactorParams.model_validate_json()`.
3. `compute_recovery(repair_time_samples, damage_state)` returns a dict with keys `reoccupancy_days`, `functional_recovery_days`, `full_recovery_days`.
4. All three output arrays contain only non-negative values.
5. `np.median(full_recovery_days) >= np.median(reoccupancy_days)` for all tested damage states (physically required).
6. `pytest test/test_recovery.py -v` passes with zero failures.
7. `importlib.resources` is used for JSON file access — no hardcoded filesystem paths.
8. `docs/orchestration/decision_log.md` has been appended with this agent's report block.

---

## Prohibitions

- Never import or reference PyREDi — the repo is 404 and the package is unavailable.
- Never hardcode impeding factor parameters in `recovery.py` — all parameters load from `ph_redi_params.json`.
- Never use `os.path` or `pathlib.Path(__file__).parent` to locate data files — use `importlib.resources`.
- Never write `full_recovery_days` values that are less than `reoccupancy_days` values for the same sample — this violates the physical constraint and indicates a bug in the aggregation logic.
- Never modify a test to make it pass — fix the implementation.

---

## Reporting template

Append this block to `docs/orchestration/decision_log.md` on completion:

```
Track: 6
Phase: recovery_modeler
Result: Implemented REDi recovery model natively with Philippine impeding factor calibrations from thesis.
Key metric: All 5 test_recovery.py tests passing; median full_recovery > median reoccupancy confirmed.
Files created: bayanihan/recovery.py, bayanihan/data/ph_redi_params.json, test/test_recovery.py
Docs updated: docs/learnings/pelicun_repair_class_notes.md, docs/learnings/recovery_modeler_low_confidence.md (if any), docs/orchestration/decision_log.md
Next step: thesis_replication_validator (P7) is unblocked once archetype_modeler (P3) also completes.
```
