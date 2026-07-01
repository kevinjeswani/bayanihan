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

Archetype-specific impeding factors (v0.2 fidelity refinement):
  Financing, contractor, and engineer delays are now archetype-specific per Table 6-7
  (§6.3.2 impedance_factor_assignments in redi_impedance_factors.yaml).
  Inspection and long-lead remain the same for all archetypes.
  The ``archetype`` parameter selects the appropriate set; unknown archetypes fall back
  to the flat top-level defaults (primary school Max-RC-3) for backward compatibility.

Per-milestone conditional gating (v0.2 fidelity refinement):
  Impeding factors apply ONLY when the milestone has repair work in its classes.
  Let imp = archetype-specific max(sampled delays), insp = sampled inspection:
    reoccupancy   = rc1 > 0  → rc1 + imp        else (DS>0 → insp, DS=0 → 0)
    functional    = (rc1+rc2) > 0 → (rc1+rc2) + imp  else (DS>0 → insp, DS=0 → 0)
    full_recovery = (rc1+rc2+rc3) > 0 → (rc1+rc2+rc3) + imp  else 0
  This allows lightly-damaged buildings (cosmetic-only) to skip the long financing
  and contractor delays, restoring intensity-scaling of the 90% FR metric.

Milestone construction (REDi v1.0 three-milestone model):
  - impeding_factor_days = max of all six sampled delays (REDi critical-path model, §3.3)
  - reoccupancy_days      = rc1_days + impeding_factor_days    [gated — see above]
  - functional_days       = (rc1_days + rc2_days) + impeding_factor_days   [gated]
  - full_recovery_days    = (rc1_days + rc2_days + rc3_days) + impeding_factor_days  [gated]

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
from typing import Any

import numpy as np
import pandas as pd
import pydantic
import scipy.stats  # noqa: F401 — kept for potential future use

# Set of archetype IDs whose financing group is SBA/primary school.
# These are the archetypes eligible for cost-scaled financing (Part C).
# Simple (Insurance 42 d) and wood (Private 105 d) archetypes are NOT in this set.
# Source: ph_redi_params.json by_archetype — financing_median_days == 336.0.
SBA_PRIMARY_ARCHETYPES: frozenset[str] = frozenset({
    "C1-M (Hi)", "C1-M (Mid)", "C1-M (Pre/Lo)", "C1-M (Pre/Lo) FRP",
    "C1-L (Mid/Hi)", "C1-L (Pre/Lo)",
    "PTC1-M (Hi)", "PTC1-M (Mid)", "PTC1-M (Pre/Lo)",
    "PTC4-M (Lo)",
    "CWS-L", "C1-H (Hi)", "S1-M (Hi)",
    "PC-L", "C4-L (Lo/Mid)", "C4-M (Mid)",
})

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

    The flat top-level fields represent the fallback/default (primary school,
    Max Repair Class 3). Archetype-specific params are resolved separately via
    ``_resolve_archetype_impeding(archetype, raw_json)`` and passed in as overrides
    to the sampling step.

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
        Uses the flat top-level defaults (primary school Max-RC-3) regardless of
        archetype — for archetype-specific params use ``_resolve_archetype_impeding``.

    Raises:
        FileNotFoundError: if ph_redi_params.json is missing from the package data.
        pydantic.ValidationError: if JSON fields fail type/value validation.
    """
    pkg_data = resources.files("bayanihan") / "data" / "ph_redi_params.json"
    raw = json.loads(pkg_data.read_text(encoding="utf-8"))
    return ImpedingFactorParams(**raw)


def _load_ph_params_raw() -> dict[str, Any]:
    """Load the raw ph_redi_params.json dict (for archetype-specific lookup)."""
    pkg_data = resources.files("bayanihan") / "data" / "ph_redi_params.json"
    return json.loads(pkg_data.read_text(encoding="utf-8"))


def _resolve_archetype_impeding(
    archetype: str | None,
    raw: dict[str, Any],
) -> dict[str, float]:
    """Resolve the archetype-specific financing, contractor, and engineer params.

    Looks up ``raw["by_archetype"][archetype]`` and returns a dict with
    override fields for those three factors.  Inspection, permitting, and
    long_lead always come from the flat top-level defaults.

    If archetype is None or not found in by_archetype, returns an empty dict
    (caller uses flat defaults — no change from prior behavior).

    Args:
        archetype: Canonical archetype ID (e.g. ``"C1-M (Hi)"``).
        raw: The raw JSON dict loaded from ph_redi_params.json.

    Returns:
        Dict with zero or more of the keys:
            financing_median_days, financing_beta,
            contractor_median_days, contractor_beta,
            engineer_median_days, engineer_beta.
        Empty dict if archetype is unknown (fall back to flat defaults).
    """
    if archetype is None:
        return {}
    by_arch: dict[str, Any] = raw.get("by_archetype", {})
    entry = by_arch.get(archetype)
    if entry is None:
        return {}

    result: dict[str, float] = {}
    for factor in ("financing", "contractor", "engineer"):
        sub = entry.get(factor)
        if sub is not None:
            result[f"{factor}_median_days"] = float(sub["median_days"])
            result[f"{factor}_beta"] = float(sub["beta"])
    return result


def _sample_lognormal(
    median_days: float,
    beta: float,
    size: int,
    rng: np.random.Generator,
) -> np.ndarray:
    """Draw ``size`` samples from LN(log(median), beta) — strictly non-negative."""
    mu = np.log(max(median_days, 1e-9))  # log-space mean
    return rng.lognormal(mean=mu, sigma=max(beta, 1e-9), size=size).clip(min=0.0)


def _cost_scale_financing(
    repair_cost: np.ndarray,
    raw: dict[str, Any],
    fallback_median: float,
    fallback_beta: float,
    rng: np.random.Generator,
) -> np.ndarray:
    """Sample cost-scaled SBA financing delays (Part C — Table D-15 curve).

    For each realization, the financing MEDIAN is log-linearly interpolated from
    the Table D-15 replacement_cost → financing_days curve at that realization's
    repair_cost (PHP).  The beta is fixed at 0.57 (same as flat SBA beta, Table 6-7).
    Curve endpoints are used for costs below the minimum or above the maximum.

    This is a MEDIUM-confidence faithful extension: Table D-15 was originally a
    replacement-cost → replacement-time delay curve, applied here as a proxy for
    cost-dependent SBA repair financing (approved by Kevin Jeswani 2026-06-30).

    Args:
        repair_cost: (n,) per-realization repair cost in PHP_2020.
        raw: Raw JSON dict from ph_redi_params.json (must have ``financing_cost_scaling``).
        fallback_median: Median financing days to use when repair_cost <= 0 (i.e. cost unknown
            at a realization level, e.g. zero due to no damage — but caller should gate on DS=0).
        fallback_beta: Beta to use for fallback draws.
        rng: numpy random generator.

    Returns:
        (n,) array of sampled financing delay days (per-realization).
    """
    scaling = raw.get("financing_cost_scaling", {})
    curve = scaling.get("curve", [])
    beta = float(scaling.get("financing_beta", fallback_beta))

    if not curve:
        # No curve in JSON — fall back to flat median for all realizations
        return _sample_lognormal(fallback_median, fallback_beta, len(repair_cost), rng)

    # Extract curve arrays (sorted ascending by cost)
    costs = np.array([pt["replacement_cost_php"] for pt in curve], dtype=float)
    days = np.array([pt["financing_days"] for pt in curve], dtype=float)

    # Log-linear interpolation: linear in log-cost space
    log_costs = np.log(np.maximum(costs, 1.0))

    n = len(repair_cost)
    medians = np.empty(n, dtype=float)

    # For each realization, interpolate (or clamp) the median
    for i in range(n):
        rc = float(repair_cost[i])
        if rc <= 0.0:
            # Zero/unknown repair cost → fall back to flat default
            medians[i] = fallback_median
        elif rc <= costs[0]:
            medians[i] = days[0]  # clamp at lower bound
        elif rc >= costs[-1]:
            medians[i] = days[-1]  # clamp at upper bound
        else:
            # Log-linear interpolation between bracketing points
            log_rc = np.log(rc)
            idx = int(np.searchsorted(log_costs, log_rc, side="right")) - 1
            idx = max(0, min(idx, len(costs) - 2))
            t = (log_rc - log_costs[idx]) / (log_costs[idx + 1] - log_costs[idx])
            medians[i] = days[idx] + t * (days[idx + 1] - days[idx])

    # Sample lognormal per-realization with the interpolated median
    mu_arr = np.log(np.maximum(medians, 1e-9))
    sigma = max(beta, 1e-9)
    return rng.lognormal(mean=mu_arr, sigma=sigma).clip(min=0.0)


def compute_recovery(
    repair_time_samples: np.ndarray,
    damage_state: np.ndarray,
    params: ImpedingFactorParams | None = None,
    seed: int | None = None,
    archetype: str | None = None,
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
        archetype: Canonical archetype ID (e.g. ``"C1-M (Hi)"``).  Selects
            archetype-specific financing/contractor/engineer delays from
            ph_redi_params.json ``by_archetype`` section.  None → flat defaults
            (current / backward-compatible behavior).

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

    raw = _load_ph_params_raw()
    arch_overrides = _resolve_archetype_impeding(archetype, raw)

    impeding_factor_days, insp_days, no_damage = _sample_impeding_factors(
        n, params, rng, damage_state, arch_overrides
    )

    return _compute_milestones(rc_days, impeding_factor_days, insp_days, no_damage)


def compute_recovery_from_components(
    time_per_cmp: pd.DataFrame,
    damage_state: np.ndarray,
    params: ImpedingFactorParams | None = None,
    seed: int | None = None,
    workers_per_day: float = WORKERS_PER_DAY_DEFAULT,
    archetype: str | None = None,
    repair_cost: np.ndarray | None = None,
) -> dict:
    """Compute recovery milestones from Pelicun per-component repair times.

    Implements the REDi three-milestone model using Pelicun's per-component
    repair time output.  This is the primary interface after the P6 refactor.

    Milestone gating (redi_impedance_factors.yaml, Table D-16):
      - Re-occupancy     → Class 1 complete (structural/life-safety)
      - Functional Rec.  → Class 1 + 2 complete (structural + critical MEP) [PRIMARY]
      - Full Recovery     → All classes (1+2+3) complete

    Per-milestone conditional gating (v0.2 refinement):
      The impeding delay applies ONLY when the milestone has actual repair work.
      Let imp = archetype-specific max(impeding delays), insp = inspection delay:
        reoccupancy   = rc1 > 0  → rc1 + imp        else (DS>0 → insp, DS=0 → 0)
        functional    = (rc1+rc2) > 0 → (rc1+rc2) + imp  else (DS>0 → insp, DS=0 → 0)
        full_recovery = (rc1+rc2+rc3) > 0 → (rc1+rc2+rc3) + imp  else 0

    Archetype-specific impeding factors (v0.2 refinement):
      Financing, contractor, and engineer delays are selected per archetype from
      ph_redi_params.json ``by_archetype``.  Unknown archetypes fall back to the
      flat top-level defaults (primary school Max-RC-3) for backward compatibility.

    Args:
        time_per_cmp: DataFrame (n_sims, n_components) with repair time in
            **worker_hours** per component.  Column names must be component IDs.
            Source: ``asmnt.loss.sample.xs('Time', level='dv', axis=1)
                       .T.groupby(level='loss').sum().T``
        damage_state: (n_simulations,) integer damage state index (0 = undamaged).
        params: PH impeding factor parameters. Loads ph_redi_params.json if None.
        seed: integer random seed for reproducibility.
        workers_per_day: worker_hours per calendar day for scheduling conversion.
        archetype: Canonical archetype ID (e.g. ``"C1-M (Hi)"``).  Selects
            archetype-specific financing/contractor/engineer delays from
            ph_redi_params.json ``by_archetype`` section.  None → flat defaults
            (current / backward-compatible behavior).
        repair_cost: (n_simulations,) per-realization repair cost in **PHP_2020**.
            When provided AND archetype is in ``SBA_PRIMARY_ARCHETYPES``, the
            financing delay median is interpolated from the Table D-15 curve (Part C).
            When None or archetype is not SBA/primary, the flat archetype financing
            delay is used (backward-compatible — Parts A/B unchanged).

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

    raw = _load_ph_params_raw()
    arch_overrides = _resolve_archetype_impeding(archetype, raw)

    # --- Per-repair-class aggregation from Pelicun component times ---
    rc_days = aggregate_time_by_repair_class(time_per_cmp, workers_per_day=workers_per_day)

    # Prepare cost array for cost-scaled financing (Part C).
    # Only applies when archetype is SBA/primary AND repair_cost is provided.
    repair_cost_arr: np.ndarray | None = None
    if repair_cost is not None and archetype in SBA_PRIMARY_ARCHETYPES:
        repair_cost_arr = np.asarray(repair_cost, dtype=float)
        if repair_cost_arr.shape != (n,):
            raise ValueError(
                f"repair_cost must have shape ({n},); got {repair_cost_arr.shape}"
            )

    # --- Sample impeding factors ---
    impeding_factor_days, insp_days, no_damage = _sample_impeding_factors(
        n, params, rng, damage_state, arch_overrides, repair_cost=repair_cost_arr, raw=raw
    )

    result = _compute_milestones(rc_days, impeding_factor_days, insp_days, no_damage)
    result["rc1_days"] = np.where(no_damage, 0.0, rc_days[1])
    result["rc2_days"] = np.where(no_damage, 0.0, rc_days[2])
    result["rc3_days"] = np.where(no_damage, 0.0, rc_days[3])
    return result


def _sample_impeding_factors(
    n: int,
    params: ImpedingFactorParams,
    rng: np.random.Generator,
    damage_state: np.ndarray,
    arch_overrides: dict[str, float] | None = None,
    repair_cost: np.ndarray | None = None,
    raw: dict[str, Any] | None = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Sample impeding factor delays and identify DS=0 (undamaged) simulations.

    Archetype-specific overrides (from ``by_archetype`` in ph_redi_params.json)
    replace the flat defaults for financing, contractor, and engineer.
    Inspection, permitting, and long_lead use the flat defaults for all archetypes.

    Part C — cost-scaled SBA financing:
      When ``repair_cost`` is provided (PHP_2020 per-realization array), the financing
      MEDIAN is log-linearly interpolated from the Table D-15 curve in
      ``financing_cost_scaling``.  This replaces the flat archetype financing median for
      that realization.  Beta remains 0.57 (SBA, Table 6-7).  This only applies when the
      caller (``compute_recovery_from_components``) has already verified the archetype is
      in ``SBA_PRIMARY_ARCHETYPES``.  When ``repair_cost`` is None the flat archetype
      financing is used (backward-compatible — Parts A/B unchanged).

    Args:
        n: Number of simulations.
        params: PH impeding factor parameters (flat defaults).
        rng: numpy random generator.
        damage_state: (n,) integer damage state array.
        arch_overrides: dict of archetype-specific param overrides, e.g.
            ``{"financing_median_days": 42.0, "financing_beta": 1.11, ...}``.
            Empty dict or None → use flat defaults.
        repair_cost: (n,) per-realization repair cost in PHP_2020, or None.
            When provided, triggers cost-scaled financing (Part C).
        raw: Raw ph_redi_params.json dict (needed for cost-scaling curve).
            If None and repair_cost is provided, cost scaling is skipped.

    Returns:
        (impeding_factor_days, insp_days, no_damage):
            impeding_factor_days — (n,) max impeding delay in calendar days
            insp_days            — (n,) inspection delay samples (for fallback gating)
            no_damage            — (n,) boolean mask, True where DS=0
    """
    if arch_overrides is None:
        arch_overrides = {}

    # Source: Table 6-7 (Jeswani 2021, p.135); distribution: lognormal per REDi v1.0
    _sl = _sample_lognormal

    # Inspection: same for all archetypes (provenance HIGH)
    delay_inspection = _sl(params.inspection_median_days, params.inspection_beta, n, rng)

    # Financing: archetype-specific (provenance HIGH for each group)
    financing_med = arch_overrides.get("financing_median_days", params.financing_median_days)
    financing_beta = arch_overrides.get("financing_beta", params.financing_beta)

    if repair_cost is not None and raw is not None:
        # Part C: cost-scaled SBA financing — per-realization median from Table D-15 curve.
        # Simple (Insurance 42 d) and wood (Private 105 d) archetypes never reach here
        # because compute_recovery_from_components only sets repair_cost_arr for
        # SBA_PRIMARY_ARCHETYPES (financing_med will be 336 d for all of them).
        delay_financing = _cost_scale_financing(
            repair_cost=repair_cost,
            raw=raw,
            fallback_median=financing_med,
            fallback_beta=financing_beta,
            rng=rng,
        )
    else:
        # Flat archetype financing (Parts A/B, backward-compat)
        delay_financing = _sl(financing_med, financing_beta, n, rng)

    # Permitting: flat default for all archetypes (LOW CONFIDENCE — split)
    delay_permitting = _sl(params.permitting_median_days, params.permitting_beta, n, rng)

    # Contractor: archetype-specific (provenance HIGH for each group)
    contractor_med = arch_overrides.get("contractor_median_days", params.contractor_median_days)
    contractor_beta = arch_overrides.get("contractor_beta", params.contractor_beta)
    delay_contractor = _sl(contractor_med, contractor_beta, n, rng)

    # Engineer: archetype-specific (provenance HIGH for primary; LOW for simple/wood)
    engineer_med = arch_overrides.get("engineer_median_days", params.engineer_median_days)
    engineer_beta = arch_overrides.get("engineer_beta", params.engineer_beta)
    delay_engineer = _sl(engineer_med, engineer_beta, n, rng)

    # Long-lead: same for all archetypes (LOW CONFIDENCE — no thesis value)
    delay_long_lead = _sl(params.long_lead_median_days, params.long_lead_beta, n, rng)

    # Critical-path: total impeding delay = max across all factors (REDi §3.3 model)
    impeding_factor_days: np.ndarray = np.stack(
        [delay_inspection, delay_financing, delay_permitting,
         delay_contractor, delay_engineer, delay_long_lead],
        axis=0,
    ).max(axis=0)

    no_damage: np.ndarray = damage_state == 0
    return impeding_factor_days, delay_inspection, no_damage


def _compute_milestones(
    rc_days: dict[int, np.ndarray],
    impeding_factor_days: np.ndarray,
    insp_days: np.ndarray,
    no_damage: np.ndarray,
) -> dict:
    """Compute the three REDi recovery milestones with per-milestone conditional gating.

    Gating rule (v0.2 refinement — faithful to REDi intent):
      Impeding factors apply ONLY when a milestone has actual repair work in its
      classes.  Buildings with only cosmetic damage (rc1=rc2=0, rc3>0) skip the
      financing/contractor floor for functional recovery, restoring intensity scaling.

      Let any_damage = DS>0, imp = impeding_factor_days, insp = inspection sample.
        reoccupancy   = rc1 > 0  → rc1 + imp        else (any_damage → insp, else 0)
        functional    = (rc1+rc2) > 0 → (rc1+rc2) + imp  else (any_damage → insp, else 0)
        full_recovery = (rc1+rc2+rc3) > 0 → (rc1+rc2+rc3) + imp  else 0

    Milestone ordering enforced: full >= functional >= reoccupancy >= 0.
    DS=0 → all zero (unchanged).

    Args:
        rc_days: dict {1: array, 2: array, 3: array} of calendar days per class.
        impeding_factor_days: (n,) array of max impeding delay per simulation.
        insp_days: (n,) array of inspection delay samples (for bare-inspection fallback).
        no_damage: (n,) boolean mask, True where DS=0.

    Returns:
        dict with keys: reoccupancy_days, functional_recovery_days,
            full_recovery_days, impeding_factor_days.
    """
    rc1 = rc_days.get(1, np.zeros_like(impeding_factor_days))
    rc2 = rc_days.get(2, np.zeros_like(impeding_factor_days))
    rc3 = rc_days.get(3, np.zeros_like(impeding_factor_days))

    any_damage = ~no_damage  # DS > 0

    # Per-milestone gating masks (checked BEFORE zeroing for DS=0)
    has_rc1 = rc1 > 0.0
    has_rc1_or_rc2 = (rc1 + rc2) > 0.0
    has_any_repair = (rc1 + rc2 + rc3) > 0.0

    # Reoccupancy: Class 1 work → rc1 + imp; else bare inspection (if damaged), else 0
    reoccupancy_days = np.where(
        has_rc1,
        rc1 + impeding_factor_days,
        np.where(any_damage, insp_days, 0.0),
    )

    # Functional recovery: Class 1+2 work → (rc1+rc2) + imp; else bare inspection (if damaged)
    functional_recovery_days = np.where(
        has_rc1_or_rc2,
        (rc1 + rc2) + impeding_factor_days,
        np.where(any_damage, insp_days, 0.0),
    )

    # Full recovery: any repair work → (rc1+rc2+rc3) + imp; else 0
    full_recovery_days = np.where(
        has_any_repair,
        (rc1 + rc2 + rc3) + impeding_factor_days,
        0.0,
    )

    # Zero out DS=0 samples (no damage → zero downtime for all milestones)
    impeding_factor_days = np.where(no_damage, 0.0, impeding_factor_days)
    reoccupancy_days = np.where(no_damage, 0.0, reoccupancy_days)
    functional_recovery_days = np.where(no_damage, 0.0, functional_recovery_days)
    full_recovery_days = np.where(no_damage, 0.0, full_recovery_days)

    # Clip non-negative and enforce ordering (holds by construction; clip for safety)
    reoccupancy_days = np.clip(reoccupancy_days, 0.0, None)
    functional_recovery_days = np.maximum(functional_recovery_days, reoccupancy_days)
    full_recovery_days = np.maximum(full_recovery_days, functional_recovery_days)

    return {
        "reoccupancy_days": reoccupancy_days,
        "functional_recovery_days": functional_recovery_days,
        "full_recovery_days": full_recovery_days,
        "impeding_factor_days": impeding_factor_days,
    }
