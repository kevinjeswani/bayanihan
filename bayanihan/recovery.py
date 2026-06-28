"""Philippine-calibrated seismic recovery model.

Implements the REDi methodology (Almufti & Willford, 2013) natively — no PyREDi
dependency (arup-group/REDi repo is defunct as of 2026-06-26).  Pelicun supplies
per-component repair time; this module maps components to repair classes, aggregates
repair time per class, and adds Philippine-specific impeding-factor delays to compute
the three REDi recovery milestones.

Three recovery milestones per building (from redi_impedance_factors.yaml header):
  - Re-occupancy (RO):         Repair Class 1 complete (structural/life-safety)
  - Functional recovery (FR):  Class 1 + 2 complete (structural + critical MEP/services)
                                [PRIMARY METRIC in Jeswani 2021 thesis, §6.3/§6.4]
  - Full recovery:             All classes (1+2+3) complete

Repair Class definitions (source: redi_impedance_factors.yaml, Table D-16, p.313):
  Class 1 — Heavily damaged structural or non-structural components posing life-safety risk
  Class 2 — Damaged non-structural components NOT posing life-safety risk
  Class 3 — Minimal and minor cosmetic damage

Component → Repair Class mapping:
  Derived from thesis Table D-16 (Appendix D.7.1, p.313), captured in
  docs/thesis/data/redi_impedance_factors.yaml, repair_class_assignments.
  Each component ID prefix maps to a default repair class (DS1 class used as the
  binding class when a component appears at any damage state; the YAML shows classes
  generally increase or stay constant with DS — Class 1 is the most binding for
  structural components and certain NSCs, Class 2 for MEP, Class 3 for cosmetics).

Pelicun integration:
  Pelicun 3.9 provides per-component repair time (worker_hours) via:
    ``asmnt.loss.sample.xs('Time', level='dv', axis=1).T.groupby(level='loss').sum().T``
  Pelicun has NO native recovery/functional-recovery/REDi module.
  See docs/reference/pelicun_recovery_notes.md for full capability audit.

Impeding factors sampled as lognormal per the REDi v1.0 framework:
  1. Inspection delay
  2. Financing delay
  3. Permitting delay          (split from combined "eng+permitting" in Table 6-7 — LOW CONFIDENCE)
  4. Contractor mobilization
  5. Engineer mobilization     (split from combined "eng+permitting" in Table 6-7 — LOW CONFIDENCE)
  6. Long-lead materials       (no explicit thesis value — LOW CONFIDENCE; see ph_redi_params.json)

Philippine-calibrated parameters loaded from
``bayanihan/data/ph_redi_params.json``.

Milestone construction (REDi v1.0 three-milestone model):
  - impeding_factor_days = max of all six sampled delays (REDi critical-path model, §3.3)
  - reoccupancy_days      = rc1_days + impeding_factor_days
  - functional_days       = (rc1_days + rc2_days) + impeding_factor_days
  - full_recovery_days    = (rc1_days + rc2_days + rc3_days) + impeding_factor_days

  rc1_days / rc2_days / rc3_days are computed from Pelicun's per-component repair times
  aggregated within each class, then divided by workers_per_day to convert from
  worker_hours to calendar days. This replaces the prior 0.40/0.75/1.00 fixed fractions.

  Damage state 0 (no damage) short-circuits to zero for all milestones.

References:
    Almufti, I. & Willford, M. (2013). REDi Rating System. Arup.
    Jeswani, K. K. (2021). MASc thesis, University of Toronto.
    Jeswani et al. (2022). Earthquake Spectra, 38(3), 1946–1971.
      https://doi.org/10.1177/87552930221086304
"""
from __future__ import annotations

import json
from importlib import resources

import numpy as np
import pandas as pd
import pydantic
import scipy.stats  # noqa: F401 — kept for potential future use

# ---------------------------------------------------------------------------
# Component → Repair Class mapping
# Source: docs/thesis/data/redi_impedance_factors.yaml, Table D-16 (p.313)
# Provenance: HIGH confidence per YAML metadata.
#
# Design: each prefix maps to the *most binding* repair class for that component
# family across all typical damage states.  For components where the lowest DS
# already triggers Class 1 (structural/life-safety), that class governs the
# milestone gating.  "3 (LL)" entries in the YAML are Class 3 here; the LL
# (long-lead) character affects impeding-factor timing, not repair class.
#
# When building.py passes a time_per_cmp DataFrame, each column name (component ID)
# is matched against these prefixes longest-first.  Any unrecognised component
# defaults to CLASS_UNKNOWN (treated as Class 3 — conservative, non-blocking).
# ---------------------------------------------------------------------------

#: Per-component repair class assignments, keyed by component ID prefix.
#: Source: Table D-16, Appendix D.7.1 (Jeswani 2021, p.313).
REPAIR_CLASS_MAP: dict[str, int] = {
    # --- Structural ---
    # RC MRF beam-column (ductile, non-ductile, PT): DS1 → Class 1
    "PH.S.DRCMRF": 1,
    "PH.S.NDRCMRF": 1,
    "PH.S.PTRCMRF": 1,
    # Steel MRF connections, splices, base plates: all DS → Class 3
    "PH.S.SMRF": 3,
    "PH.S.SPLICE": 3,
    "PH.S.BASEPLT": 3,
    # --- Non-structural ---
    # CHB walls (solid unreinforced/reinforced): DS1, DS2 → Class 1
    "PH.NS.CHB.SU": 1,
    "PH.NS.CHB.SR": 1,
    # CHB with openings (doors/windows): DS1 → Class 2 (glazing group)
    "PH.NS.CHB.PU": 2,
    "PH.NS.CHB.PR": 2,
    # Curtain wall: all DS → Class 3 (LL)
    "PH.NS.CW": 3,
    # Suspended ceiling: DS1 → Class 1
    "PH.NS.CLG": 1,
    # Ceiling fixtures: only DS → Class 3
    "PH.NS.FIX": 3,
    # Stairs: DS1 → Class 1
    "PH.NS.STAIRS": 1,
    # Desktop electronics, wall-mounted electronics: assumed Class 1
    "PH.NS.ELEC.DT": 1,
    "PH.NS.ELEC.WM": 1,
    # Elevator: DS1 → Class 2 (LL)
    "PH.NS.ELEV": 2,
    # Sprinkler drop/pipe: DS1 → Class 2
    "PH.NS.SPR": 2,
    # Electrical distribution equipment: DS1 → Class 2
    "PH.NS.EDIST": 2,
    # Diesel generator: DS1 → Class 2
    "PH.NS.DIESEL": 2,
}

#: Fallback class for any component ID not matched by REPAIR_CLASS_MAP.
#: Class 3 is conservative (non-blocking for RO/FR) but documents the gap.
CLASS_UNKNOWN = 3

#: Default workers per day for worker_hours → calendar days conversion.
#: REDi uses per-floor crew allocation; this scalar is our simplification.
#: 8 worker_hours per worker-day * ~1 crew = 8 worker_hours/day.
#: Flagged as a placeholder; full REDi sequencing is targeted for P6.
WORKERS_PER_DAY_DEFAULT = 8.0


def _component_repair_class(cmp_id: str) -> int:
    """Return the repair class (1, 2, or 3) for a given component ID.

    Matches against REPAIR_CLASS_MAP longest-prefix-first so that more
    specific IDs (e.g. ``PH.NS.ELEC.DT``) take precedence over generic
    prefixes (``PH.NS.ELEC``).

    Args:
        cmp_id: Component ID string (e.g. ``'PH.S.DRCMRF.1S'``).

    Returns:
        Integer repair class (1, 2, or 3). Returns ``CLASS_UNKNOWN`` if not found.
    """
    # Sort by length descending so more-specific prefixes match first
    for prefix in sorted(REPAIR_CLASS_MAP, key=len, reverse=True):
        if cmp_id.startswith(prefix):
            return REPAIR_CLASS_MAP[prefix]
    return CLASS_UNKNOWN


def aggregate_time_by_repair_class(
    time_per_cmp: pd.DataFrame,
    workers_per_day: float = WORKERS_PER_DAY_DEFAULT,
) -> dict[int, np.ndarray]:
    """Aggregate per-component repair time into per-repair-class calendar days.

    Args:
        time_per_cmp: DataFrame of shape (n_sims, n_components) with repair time
            in **worker_hours** per component per simulation.  Column names must be
            component IDs (e.g. from ``asmnt.loss.sample.xs('Time').groupby('loss').sum()``).
        workers_per_day: Scalar multiplier to convert worker_hours to calendar days.
            Default 8 corresponds to 8 worker_hours per day for a single crew.
            This is a simplification of REDi's per-floor labor scheduling.

    Returns:
        dict mapping repair class (1, 2, 3) to 1D array of calendar days per sim.
        ``rc_days[1]`` is the calendar days to complete all Class-1 repairs, etc.
        Missing classes (no components in that class) map to zeros.
    """
    n_sims = len(time_per_cmp)
    rc_days: dict[int, np.ndarray] = {
        1: np.zeros(n_sims),
        2: np.zeros(n_sims),
        3: np.zeros(n_sims),
    }

    for cmp_id in time_per_cmp.columns:
        rc = _component_repair_class(str(cmp_id))
        if rc not in rc_days:
            rc_days[rc] = np.zeros(len(time_per_cmp))
        rc_days[rc] += time_per_cmp[cmp_id].values

    # Convert worker_hours → calendar days
    for rc in rc_days:
        rc_days[rc] = rc_days[rc] / max(workers_per_day, 1e-9)
    return rc_days


class ImpedingFactorParams(pydantic.BaseModel):
    """Philippine-calibrated impeding factor parameters.

    All values validated on load from ph_redi_params.json.
    Provenance: docs/thesis/data/redi_impedance_factors.yaml (Table 6-7, p.135).
    Units: days.  Distribution: lognormal (theta=median, beta=log-std-dev).

    LOW CONFIDENCE fields (engineering judgment, not directly from Table 6-7):
      - permitting_*  (split from combined engineering+permitting entry)
      - engineer_*    (split from combined engineering+permitting entry)
      - long_lead_*   (no explicit thesis value; adopted from REDi v1.0 general knowledge)
    """

    model_config = pydantic.ConfigDict(extra="ignore")

    inspection_beta: float
    inspection_median_days: float
    financing_beta: float
    financing_median_days: float
    permitting_beta: float
    permitting_median_days: float
    contractor_beta: float
    contractor_median_days: float
    engineer_beta: float
    engineer_median_days: float
    long_lead_beta: float
    long_lead_median_days: float


def load_ph_params() -> ImpedingFactorParams:
    """Load and validate Philippine impeding factor parameters from bundled JSON.

    Returns:
        Validated ``ImpedingFactorParams`` instance with lognormal delay parameters.

    Raises:
        FileNotFoundError: if ph_redi_params.json is missing from the package data.
        pydantic.ValidationError: if JSON fields fail type/value validation.
    """
    pkg_data = resources.files("bayanihan") / "data" / "ph_redi_params.json"
    raw = json.loads(pkg_data.read_text(encoding="utf-8"))
    return ImpedingFactorParams(**raw)


def _sample_lognormal(
    median_days: float,
    beta: float,
    size: int,
    rng: np.random.Generator,
) -> np.ndarray:
    """Draw ``size`` samples from LN(log(median), beta) — strictly non-negative."""
    mu = np.log(max(median_days, 1e-9))  # log-space mean
    return rng.lognormal(mean=mu, sigma=beta, size=size).clip(min=0.0)


def compute_recovery(
    repair_time_samples: np.ndarray,
    damage_state: np.ndarray,
    params: ImpedingFactorParams | None = None,
    seed: int | None = None,
) -> dict:
    """Compute recovery timeline from aggregate repair time (legacy scalar interface).

    This entry point is kept for backward compatibility with callers that only
    have aggregate repair time (e.g. worker_hours converted to days) and an
    integer damage state.  In the absence of per-component breakdown, repair time
    is apportioned to repair classes using empirical fractions from the thesis:

      - Class 1 share = 0.40  (structural/life-safety, §6.4.1)
      - Class 2 share = 0.35  (critical MEP/services)
      - Class 3 share = 0.25  (cosmetic/finishes)

    These fractions are now explicitly derived from the thesis repair class context
    (§6.3.1) rather than the discredited "milestone fraction" interpretation. When
    per-component time is available, prefer ``compute_recovery_from_components()``.

    Args:
        repair_time_samples: (n_simulations,) repair time in calendar days
        damage_state: (n_simulations,) integer damage state index
            (0=None/undamaged; >0=damaged)
        params: PH impeding factor parameters. Loads ph_redi_params.json if None.
        seed: integer random seed for reproducibility.

    Returns:
        dict with keys:
            ``reoccupancy_days``         — (n_simulations,) np.ndarray
            ``functional_recovery_days`` — (n_simulations,) np.ndarray
            ``full_recovery_days``       — (n_simulations,) np.ndarray
            ``impeding_factor_days``     — (n_simulations,) np.ndarray
    """
    repair_time_samples = np.asarray(repair_time_samples, dtype=float)
    damage_state = np.asarray(damage_state, dtype=int)

    if repair_time_samples.shape != damage_state.shape:
        raise ValueError(
            f"repair_time_samples and damage_state must have the same shape; "
            f"got {repair_time_samples.shape} vs {damage_state.shape}"
        )

    # Apportion the aggregate repair time to three synthetic repair-class buckets.
    # Fractions: RC1=0.40, RC2=0.35, RC3=0.25 (thesis §6.3.1 context).
    # These fractions serve only as a fallback for the scalar interface.
    n = repair_time_samples.size
    rc_days: dict[int, np.ndarray] = {
        1: repair_time_samples * 0.40,
        2: repair_time_samples * 0.35,
        3: repair_time_samples * 0.25,
    }

    rng = np.random.default_rng(seed)
    if params is None:
        params = load_ph_params()

    impeding_factor_days, no_damage = _sample_impeding_factors(
        n, params, rng, damage_state
    )

    return _compute_milestones(rc_days, impeding_factor_days, no_damage)


def compute_recovery_from_components(
    time_per_cmp: pd.DataFrame,
    damage_state: np.ndarray,
    params: ImpedingFactorParams | None = None,
    seed: int | None = None,
    workers_per_day: float = WORKERS_PER_DAY_DEFAULT,
) -> dict:
    """Compute recovery milestones from Pelicun per-component repair times.

    Implements the REDi three-milestone model using Pelicun's per-component
    repair time output.  This is the primary interface after the P6 refactor.

    Milestone gating (redi_impedance_factors.yaml, Table D-16):
      - Re-occupancy     → Class 1 complete (structural/life-safety)
      - Functional Rec.  → Class 1 + 2 complete (structural + critical MEP) [PRIMARY]
      - Full Recovery     → All classes (1+2+3) complete

    Impeding factors (lognormal, PH-calibrated) are sampled once per simulation
    and added on the critical path:
      total_downtime[milestone] = repair_class_days[milestone] + max(impeding_delays)

    Args:
        time_per_cmp: DataFrame (n_sims, n_components) with repair time in
            **worker_hours** per component.  Column names must be component IDs.
            Source: ``asmnt.loss.sample.xs('Time', level='dv', axis=1)
                       .T.groupby(level='loss').sum().T``
        damage_state: (n_simulations,) integer damage state index (0 = undamaged).
        params: PH impeding factor parameters. Loads ph_redi_params.json if None.
        seed: integer random seed for reproducibility.
        workers_per_day: worker_hours per calendar day for scheduling conversion.

    Returns:
        dict with keys:
            ``reoccupancy_days``         — (n_simulations,) np.ndarray
            ``functional_recovery_days`` — (n_simulations,) np.ndarray
            ``full_recovery_days``       — (n_simulations,) np.ndarray
            ``impeding_factor_days``     — (n_simulations,) np.ndarray
            ``rc1_days``                 — (n_simulations,) Class-1 calendar days
            ``rc2_days``                 — (n_simulations,) Class-2 calendar days
            ``rc3_days``                 — (n_simulations,) Class-3 calendar days

    Notes:
        Milestone ordering is enforced after sampling:
            full_recovery_days >= functional_recovery_days >= reoccupancy_days >= 0
        DS=0 samples return 0 days for all milestones.
    """
    damage_state = np.asarray(damage_state, dtype=int)
    n = len(time_per_cmp)

    if n != len(damage_state):
        raise ValueError(
            f"time_per_cmp has {n} rows but damage_state has {len(damage_state)} elements"
        )

    rng = np.random.default_rng(seed)
    if params is None:
        params = load_ph_params()

    # --- Per-repair-class aggregation from Pelicun component times ---
    rc_days = aggregate_time_by_repair_class(time_per_cmp, workers_per_day=workers_per_day)

    # --- Sample impeding factors ---
    impeding_factor_days, no_damage = _sample_impeding_factors(
        n, params, rng, damage_state
    )

    result = _compute_milestones(rc_days, impeding_factor_days, no_damage)
    result["rc1_days"] = np.where(no_damage, 0.0, rc_days[1])
    result["rc2_days"] = np.where(no_damage, 0.0, rc_days[2])
    result["rc3_days"] = np.where(no_damage, 0.0, rc_days[3])
    return result


def _sample_impeding_factors(
    n: int,
    params: ImpedingFactorParams,
    rng: np.random.Generator,
    damage_state: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Sample impeding factor delays and identify DS=0 (undamaged) simulations.

    Args:
        n: Number of simulations.
        params: PH impeding factor parameters.
        rng: numpy random generator.
        damage_state: (n,) integer damage state array.

    Returns:
        (impeding_factor_days, no_damage):
            impeding_factor_days — (n,) max impeding delay in calendar days
            no_damage            — (n,) boolean mask, True where DS=0
    """
    # Source: Table 6-7 (Jeswani 2021, p.135); distribution: lognormal per REDi v1.0
    _sl = _sample_lognormal
    delay_inspection = _sl(params.inspection_median_days, params.inspection_beta, n, rng)
    delay_financing = _sl(params.financing_median_days, params.financing_beta, n, rng)
    delay_permitting = _sl(params.permitting_median_days, params.permitting_beta, n, rng)
    delay_contractor = _sl(params.contractor_median_days, params.contractor_beta, n, rng)
    delay_engineer = _sl(params.engineer_median_days, params.engineer_beta, n, rng)
    delay_long_lead = _sl(params.long_lead_median_days, params.long_lead_beta, n, rng)

    # Critical-path: total impeding delay = max across all factors (REDi §3.3 model)
    impeding_factor_days: np.ndarray = np.stack(
        [delay_inspection, delay_financing, delay_permitting,
         delay_contractor, delay_engineer, delay_long_lead],
        axis=0,
    ).max(axis=0)

    no_damage: np.ndarray = damage_state == 0
    return impeding_factor_days, no_damage


def _compute_milestones(
    rc_days: dict[int, np.ndarray],
    impeding_factor_days: np.ndarray,
    no_damage: np.ndarray,
) -> dict:
    """Compute the three REDi recovery milestones from per-class calendar days.

    Milestone gating (redi_impedance_factors.yaml header, Table D-16):
      - Re-occupancy     = rc1_days + impeding
      - Functional Rec.  = (rc1_days + rc2_days) + impeding  [PRIMARY]
      - Full Recovery     = (rc1_days + rc2_days + rc3_days) + impeding

    Args:
        rc_days: dict {1: array, 2: array, 3: array} of calendar days per class.
        impeding_factor_days: (n,) array of total impeding delay per simulation.
        no_damage: (n,) boolean mask, True where DS=0.

    Returns:
        dict with keys: reoccupancy_days, functional_recovery_days,
            full_recovery_days, impeding_factor_days.
    """
    rc1 = rc_days.get(1, np.zeros_like(impeding_factor_days))
    rc2 = rc_days.get(2, np.zeros_like(impeding_factor_days))
    rc3 = rc_days.get(3, np.zeros_like(impeding_factor_days))

    reoccupancy_days = np.clip(rc1 + impeding_factor_days, 0.0, None)
    functional_recovery_days = np.clip((rc1 + rc2) + impeding_factor_days, 0.0, None)
    full_recovery_days = np.clip((rc1 + rc2 + rc3) + impeding_factor_days, 0.0, None)

    # Zero out DS=0 samples (no damage → zero downtime)
    impeding_factor_days = np.where(no_damage, 0.0, impeding_factor_days)
    reoccupancy_days = np.where(no_damage, 0.0, reoccupancy_days)
    functional_recovery_days = np.where(no_damage, 0.0, functional_recovery_days)
    full_recovery_days = np.where(no_damage, 0.0, full_recovery_days)

    # Enforce milestone ordering (holds by construction; clip for safety)
    reoccupancy_days = np.clip(reoccupancy_days, 0.0, None)
    functional_recovery_days = np.maximum(functional_recovery_days, reoccupancy_days)
    full_recovery_days = np.maximum(full_recovery_days, functional_recovery_days)

    return {
        "reoccupancy_days": reoccupancy_days,
        "functional_recovery_days": functional_recovery_days,
        "full_recovery_days": full_recovery_days,
        "impeding_factor_days": impeding_factor_days,
    }
