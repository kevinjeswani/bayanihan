"""Real EDP ingestion: multi-stripe PERFORM-3D / SPO2IDA demands -> Pelicun sample.

Turns the 32 recovered multi-stripe EDP tables (built into
``data/edps/edp_store.parquet`` + ``collapse_fragility.parquet`` + ``index.json``
by ``scripts/build_edp_store.py``) into a Pelicun-ready conditional
demand sample at an arbitrary scenario ``Sa(T_avg)``.

Earthquake-engineering decisions (full rationale:
``docs/learnings/2026-06-26_edp_ingestion_design.md``):

  * **Multi-stripe -> scenario Sa**: log-log interpolation of each stripe's lognormal
    demand parameters against the stripe conditioning intensity ``Sa`` (a local
    power-law ``EDP = a * Sa**b``). Monotonic non-decreasing in Sa. Reproduces the
    stripe values exactly at the stripe Sa's. Emulates the 2021 Thesis conditional demand
    distribution at the site Sa.
  * **Per-stripe distribution**: lognormal fit (median = geometric mean, beta =
    log-std) on the 11 GM realizations of the **Direction-3 SRSS resultant**.
  * **Dispersion**: ``beta_total = sqrt(beta_record**2 + BetaM**2)``. The 11-record
    empirical spread supplies the ground-motion (record-to-record) dispersion
    (``BetaGM = 0`` in the tables confirms it is not added separately); ``BetaM`` (~0.47)
    is the additional modeling/epistemic dispersion, added once. No double counting.
  * **Collapse**: the table's own ``Median Collapse Sa(g)`` + ``Beta Collapse`` give
    ``P_collapse = Phi(ln(Sa/median) / beta)`` at the scenario Sa; a per-realization
    Bernoulli mask routes collapsed realizations to Pelicun's collapse->replacement path.
  * **Units**: ``Story Drift Ratio`` -> PID (unitless, no conversion); ``Acceleration``
    -> PFA (g, no conversion). ``Building Residual Drift`` and ``Peak Floor Velocity``
    are NOT consumed by any component fragility and are not emitted to Pelicun.

Public API:
    demand_for(archetype, soil_bin, sa_t1, n_realizations, seed) -> DemandSample
"""
from __future__ import annotations

import importlib.resources as pkg_resources
import json
from dataclasses import dataclass
from functools import lru_cache

import numpy as np
import pandas as pd
from scipy.stats import norm

# EDP types we feed to Pelicun (the loss-bearing ones), with their axis-2 slot.
# Axis-2 layout matches building.py: [PID (unitless), PFA (g)].
_PID_TYPE = "Story Drift Ratio"
_PFA_TYPE = "Acceleration"
# Residual interstory drift ratio (RIDR). NOT a Pelicun component-fragility demand;
# consumed ONLY by the FEMA P-58 / Ramirez & Miranda (2012) residual-drift demolition
# trigger in building.py. Stored in the EDP store; exposed here via
# residual_drift_for_sa_field / residual_drift_demand (peak over stories, Direction-3).
_RDR_TYPE = "Building Residual Drift"
# Physical cap on residual drift (ratio); collapse/demolition handled by the trigger,
# this just guards against power-law blow-up far above the stripe range.
_RDR_CAP = 0.20
# Do NOT power-law-extrapolate the residual-drift MEDIAN above the top calibrated stripe.
# The RDR stripes come from NON-collapsed NRHA records; above the top stripe the records
# overwhelmingly collapsed (which is why no stripe exists there), so extrapolating residual
# drift fabricates "survived-with-large-residual" states that were actually collapse, firing
# spurious demolition on ductile frames. Above the top stripe the collapse fragility governs
# total loss, so the residual median is held flat at its top-stripe value. See
# docs/learnings/2026-06-27_demolition_recalibration.md.
_RDR_NO_EXTRAP_ABOVE_TOP_STRIPE = True

# The single direction we use as the scalar demand: Direction 3 = SRSS resultant
# sqrt(dir1**2 + dir2**2). See design note section 1.
_RESULTANT_DIRECTION = 3

# Generous collapse-region drift cap (collapse itself is handled separately).
_PID_CAP = 0.20
# Physical PFA cap (g).
_PFA_CAP = 5.0
# Floor on interpolated record-to-record dispersion (avoid degenerate zero-variance
# fits when a stripe's 11 records are nearly identical, as in some pseudo files).
_BETA_RECORD_FLOOR = 0.05

# Package archetype -> parent package archetype for the 5 merged archetypes that have
# no EDP table of their own (consistent with the merge map in archetypes.py).
_EDP_FALLBACK: dict[str, str] = {
    "PC-L": "C1-L (Pre/Lo)",
    "PTC1-M (Pre/Lo)": "C1-M (Pre/Lo)",
    "PTC4-M (Lo)": "PTC1-M (Mid)",
    "C4-L (Lo/Mid)": "C1-L (Mid/Hi)",
    "C4-M (Mid)": "C1-M (Hi)",
}


@dataclass
class DemandSample:
    """Result of :func:`demand_for`.

    Attributes:
        edp: (n_realizations, n_stories, 2) array; axis-2 = [PID (unitless), PFA (g)].
            For collapsed realizations the demands are still populated (the caller
            overrides those to total loss via ``collapse_mask``).
        collapse_mask: (n_realizations,) bool — True where the realization collapsed.
        p_collapse: scalar collapse probability at the scenario Sa.
        n_stories: number of stories for this archetype dataset.
        archetype: package archetype ID actually used (after merged-archetype fallback).
        soil_bin: soil bin actually used.
        sa_t1: scenario Sa(T_avg) the sample was conditioned on.
        z_pid: (n_realizations,) standard-normal column that drove the PID (transient story
            drift) scatter. Exposed so the residual-drift demolition trigger can COUPLE the
            residual demand to the transient demand per realization (FEMA P-58 §7.6 after
            Ramirez & Miranda 2012) — see ``residual_drift_for_sa_field``. ``None`` only for
            legacy/hand-built samples.
    """

    edp: np.ndarray
    collapse_mask: np.ndarray
    p_collapse: float
    n_stories: int
    archetype: str
    soil_bin: str
    sa_t1: float
    z_pid: np.ndarray | None = None


# ---------------------------------------------------------------------------
# Data loading (cached once per process)
# ---------------------------------------------------------------------------
def _data_path(name: str) -> str:
    ref = pkg_resources.files("bayanihan").joinpath(f"data/edps/{name}")
    return str(ref)


@lru_cache(maxsize=1)
def _load_store() -> pd.DataFrame:
    return pd.read_parquet(_data_path("edp_store.parquet"))


@lru_cache(maxsize=1)
def _load_collapse() -> pd.DataFrame:
    return pd.read_parquet(_data_path("collapse_fragility.parquet"))


@lru_cache(maxsize=1)
def _load_index() -> dict:
    with open(_data_path("index.json"), encoding="utf-8") as fh:
        return json.load(fh)


def available_datasets() -> dict[str, list[str]]:
    """Return ``{package_archetype_id: [soil_bin, ...]}`` for all native EDP datasets."""
    idx = _load_index()
    return {a: sorted(bins) for a, bins in idx["archetypes"].items()}


def _resolve_dataset(archetype: str, soil_bin: str) -> tuple[str, str]:
    """Resolve (archetype, soil_bin) to an available dataset, applying:

      1. merged-archetype fallback (5 archetypes with no own EDP table -> parent), then
      2. soil-bin fallback within the chosen archetype (if the requested bin is absent,
         pick a sensible substitute: exact -> 'C' combined -> 'D' -> first available).

    Returns the (archetype, soil_bin) actually present in the store.
    """
    idx = _load_index()["archetypes"]

    arch = archetype
    if arch not in idx:
        if arch in _EDP_FALLBACK:
            arch = _EDP_FALLBACK[arch]
        if arch not in idx:
            raise KeyError(
                f"No EDP dataset for archetype {archetype!r} "
                f"(resolved to {arch!r}). Available: {sorted(idx)}"
            )

    bins = idx[arch]
    if soil_bin in bins:
        return arch, soil_bin
    # Soil-bin fallback order
    for cand in (soil_bin, "C", "D", "C1", "C2"):
        if cand in bins:
            return arch, cand
    # Last resort: first available bin
    return arch, sorted(bins)[0]


# ---------------------------------------------------------------------------
# Per-stripe lognormal parameter retrieval + log-log interpolation
# ---------------------------------------------------------------------------
def _stripe_params(
    store: pd.DataFrame, archetype: str, soil_bin: str, edp_type: str,
) -> tuple[np.ndarray, dict[int, np.ndarray], dict[int, np.ndarray]]:
    """Return per-stripe arrays for one EDP type, Direction-3 resultant.

    Returns:
        stripe_sa: (n_stripes,) sorted stripe conditioning Sa values.
        med_by_storey: {storey: (n_stripes,) median by stripe}.
        beta_by_storey: {storey: (n_stripes,) beta_record by stripe}.
    """
    sub = store[
        (store["archetype"] == archetype)
        & (store["soil_bin"] == soil_bin)
        & (store["edp_type"] == edp_type)
        & (store["direction"] == _RESULTANT_DIRECTION)
    ]
    if sub.empty:
        raise KeyError(
            f"No {edp_type!r} rows for {archetype!r}/{soil_bin!r} "
            f"direction {_RESULTANT_DIRECTION}"
        )

    stripes = sorted(sub["stripe"].unique())
    stripe_sa = np.array(
        [sub.loc[sub["stripe"] == s, "sa"].iloc[0] for s in stripes], dtype=float
    )

    med_by_storey: dict[int, np.ndarray] = {}
    beta_by_storey: dict[int, np.ndarray] = {}
    for storey in sorted(sub["storey"].unique()):
        ss = sub[sub["storey"] == storey].set_index("stripe")
        med_by_storey[storey] = np.array(
            [ss.loc[s, "median"] for s in stripes], dtype=float
        )
        beta_by_storey[storey] = np.array(
            [ss.loc[s, "beta_record"] for s in stripes], dtype=float
        )
    return stripe_sa, med_by_storey, beta_by_storey


def _interp_loglog_median(stripe_sa: np.ndarray, medians: np.ndarray, sa_t1: float) -> float:
    """Interpolate the lognormal median at ``sa_t1`` by piecewise log-log interpolation.

    Linear in (ln Sa, ln median) between bracketing stripes — i.e. a local power-law
    EDP = a * Sa**b. Outside the stripe range, the nearest-segment slope is held
    (clamped power-law extrapolation). Monotone non-decreasing in Sa for monotone
    median sequences.
    """
    # Guard against non-positive medians (shouldn't happen for PID/PFA but be safe).
    valid = medians > 0
    if valid.sum() < 2:
        # Degenerate: return the single positive median or 0.
        return float(medians[valid][0]) if valid.any() else 0.0

    x = np.log(stripe_sa[valid])
    y = np.log(medians[valid])
    xq = np.log(max(sa_t1, 1e-6))

    # np.interp clamps to endpoints; we want slope-held extrapolation instead.
    if xq <= x[0]:
        slope = (y[1] - y[0]) / (x[1] - x[0])
        yq = y[0] + slope * (xq - x[0])
    elif xq >= x[-1]:
        slope = (y[-1] - y[-2]) / (x[-1] - x[-2])
        yq = y[-1] + slope * (xq - x[-1])
    else:
        yq = float(np.interp(xq, x, y))
    return float(np.exp(yq))


def _interp_beta(stripe_sa: np.ndarray, betas: np.ndarray, sa_t1: float) -> float:
    """Interpolate ``beta_record`` at ``sa_t1`` (linear in ln Sa, clamped at the ends)."""
    x = np.log(stripe_sa)
    xq = np.log(max(sa_t1, 1e-6))
    b = float(np.interp(xq, x, betas))  # np.interp clamps -> nearest-stripe beta outside range
    return max(b, _BETA_RECORD_FLOOR)


def _interp_loglog_median_vec(
    stripe_sa: np.ndarray, medians: np.ndarray, sa: np.ndarray
) -> np.ndarray:
    """Vectorised :func:`_interp_loglog_median` over an array of scenario Sa values.

    For each ``sa[i]`` returns the log-log-interpolated lognormal median, using the
    SAME slope-held power-law extrapolation outside the stripe range as the scalar
    helper. Reproduces ``_interp_loglog_median`` exactly for any single Sa.

    Args:
        stripe_sa: (n_stripes,) sorted stripe conditioning Sa.
        medians: (n_stripes,) per-stripe lognormal medians (one storey/floor).
        sa: (n_real,) per-realization scenario Sa in g.

    Returns:
        (n_real,) interpolated medians.
    """
    valid = medians > 0
    if valid.sum() < 2:
        fill = float(medians[valid][0]) if valid.any() else 0.0
        return np.full(sa.shape, fill, dtype=float)

    x = np.log(stripe_sa[valid])
    y = np.log(medians[valid])
    xq = np.log(np.clip(sa, 1e-6, None))

    # Interior: piecewise-linear in (ln Sa, ln median). np.interp clamps at the ends.
    yq = np.interp(xq, x, y)

    # Slope-held extrapolation below the first / above the last stripe.
    lo = xq < x[0]
    if lo.any():
        slope_lo = (y[1] - y[0]) / (x[1] - x[0])
        yq = np.where(lo, y[0] + slope_lo * (xq - x[0]), yq)
    hi = xq > x[-1]
    if hi.any():
        slope_hi = (y[-1] - y[-2]) / (x[-1] - x[-2])
        yq = np.where(hi, y[-1] + slope_hi * (xq - x[-1]), yq)

    return np.exp(yq)


def _interp_beta_vec(
    stripe_sa: np.ndarray, betas: np.ndarray, sa: np.ndarray
) -> np.ndarray:
    """Vectorised :func:`_interp_beta` over an array of scenario Sa (clamped at ends)."""
    x = np.log(stripe_sa)
    xq = np.log(np.clip(sa, 1e-6, None))
    b = np.interp(xq, x, betas)  # clamps to nearest-stripe beta outside the range
    return np.maximum(b, _BETA_RECORD_FLOOR)


def stripe_sa_range(archetype: str, soil_bin: str) -> tuple[float, float]:
    """Return the (min, max) conditioning Sa of the EDP stripes for a dataset.

    Used to report the fraction of buildings/realizations whose scenario Sa falls
    ABOVE the calibrated EDP stripe range (i.e. power-law extrapolated demands).
    Resolves merged-archetype / soil-bin fallback first.
    """
    arch, sbin = _resolve_dataset(archetype, soil_bin)
    store = _load_store()
    sa_pid, _, _ = _stripe_params(store, arch, sbin, _PID_TYPE)
    return float(sa_pid.min()), float(sa_pid.max())


# ---------------------------------------------------------------------------
# Residual interstory drift ratio (RIDR) — demand for the demolition trigger
# ---------------------------------------------------------------------------
#
# The "Building Residual Drift" channel is already in the EDP store (Direction-3
# SRSS resultant, per storey, per stripe). It feeds NO Pelicun component fragility;
# it is consumed ONLY by the FEMA P-58 / Ramirez & Miranda (2012) residual-drift
# demolition trigger in building.py. We expose the *peak-over-stories* RIDR at the
# scenario Sa, sampled with the SAME per-stripe log-log median / beta interpolation
# used by PID/PFA, so the trigger sees a per-realization residual-drift demand that
# is internally consistent with the demand sample driving component damage.
def has_residual_drift(archetype: str, soil_bin: str) -> bool:
    """Return True if the dataset carries a ``Building Residual Drift`` channel."""
    arch, sbin = _resolve_dataset(archetype, soil_bin)
    store = _load_store()
    sub = store[
        (store["archetype"] == arch)
        & (store["soil_bin"] == sbin)
        & (store["edp_type"] == _RDR_TYPE)
        & (store["direction"] == _RESULTANT_DIRECTION)
    ]
    return not sub.empty


def residual_drift_for_sa_field(
    archetype: str,
    soil_bin: str,
    sa_field: np.ndarray,
    seed: int | None = None,
    z: np.ndarray | None = None,
) -> np.ndarray:
    """Per-realization PEAK residual interstory drift ratio (RIDR) at each field Sa.

    Mirrors :func:`demand_for_sa_field` for the residual-drift channel: ``sa_field[i]``
    is realization ``i``'s scenario Sa(T_avg); for each storey the lognormal median and
    record-to-record dispersion are log-log interpolated against the stripe conditioning
    Sa, combined with ``BetaM`` in quadrature, and sampled. The **maximum over stories**
    is returned as the building's residual-drift demand for the demolition trigger.

    **Two FEMA-P-58-faithfulness fixes (2026-06-27, demolition recalibration):**

    1. **No extrapolation of the residual-drift MEDIAN above the calibrated stripe range**
       (``_RDR_NO_EXTRAP_ABOVE_TOP_STRIPE``). The "Building Residual Drift" stripes were
       extracted from NON-collapsed NRHA records; above the top stripe Sa the records
       overwhelmingly *collapsed*, so a power-law extrapolation of residual drift there
       fabricates "survived-with-huge-residual" states that the NRHA actually recorded as
       collapse — driving spurious demolition of ductile frames at high Sa (where the
       residual curve otherwise runs far ahead of the collapse fragility). Above the top
       stripe the **collapse fragility** governs total loss, so the median residual is
       held at its top-stripe value (the conditioning Sa is clamped before interpolation).
       The record-to-record ``beta_record`` is likewise clamped (``_interp_beta_vec`` already
       clamps), so the lognormal scatter does not blow up either.

    2. **Optional coupling to the transient-drift draw.** Residual drift is, per realization,
       a function of that realization's peak transient story drift (FEMA P-58 Vol 1 §7.6
       after Ramirez & Miranda 2012): they share the same record-to-record driver. Passing
       ``z`` (the SAME standard-normal column used for the PID channel) ties the residual
       demand to the transient demand rank-for-rank, so a realization is demolished only
       when it also has high transient drift (and hence heavy component damage / proximity
       to collapse) — eliminating the physically-impossible "low-damage-but-demolished"
       cells that the previous *independent* RNG stream produced. This does NOT change the
       residual marginal (same median/beta per Sa, so the mean demolition rate is unchanged)
       — it corrects the *joint* damage-state consistency and tightens the portfolio tail.
       When ``z`` is ``None`` the scatter is drawn from ``seed`` (back-compat; one column
       shared across stories).

    Args:
        archetype: package archetype ID (merged archetypes fall back to a parent).
        soil_bin: native soil bin (falls back within the archetype if absent).
        sa_field: (n_realizations,) per-realization scenario Sa(T_avg) in g.
        seed: RNG seed (used only when ``z`` is None).
        z: optional (n_realizations,) standard-normal column to couple residual drift to
            the transient-drift draw. If None, an independent column is drawn from ``seed``.

    Returns:
        (n_realizations,) peak RIDR (unitless). Zeros if the dataset has no RDR channel.
    """
    arch, sbin = _resolve_dataset(archetype, soil_bin)
    store = _load_store()
    sa_field = np.asarray(sa_field, dtype=float)
    n_real = sa_field.shape[0]

    if not has_residual_drift(arch, sbin):
        return np.zeros(n_real, dtype=float)

    beta_m = float(sub_any["beta_m"].dropna().iloc[0]) if not (
        sub_any := store[(store["archetype"] == arch) & (store["soil_bin"] == sbin)]
    ).empty else 0.0

    sa_rdr, med_rdr, beta_rdr = _stripe_params(store, arch, sbin, _RDR_TYPE)
    rdr_storeys = sorted(med_rdr)  # 1..N (residual drift is tabulated by storey 1..N)

    # Fix 1: clamp the conditioning Sa to the top calibrated stripe so the residual-drift
    # median is NOT power-law-extrapolated into the collapse-governed regime.
    sa_eval = sa_field
    if _RDR_NO_EXTRAP_ABOVE_TOP_STRIPE:
        sa_eval = np.minimum(sa_field, float(sa_rdr.max()))

    # Fix 2: couple to the transient draw when z is supplied; else independent stream.
    z_rdr: np.ndarray
    if z is None:
        z_rdr = np.asarray(np.random.default_rng(seed).standard_normal(n_real))
    else:
        z_rdr = np.asarray(z, dtype=float)
        if z_rdr.shape[0] != n_real:
            raise ValueError(
                f"coupling z has length {z_rdr.shape[0]} != n_realizations {n_real}"
            )

    peak = np.zeros(n_real, dtype=float)
    for storey in rdr_storeys:
        med = _interp_loglog_median_vec(sa_rdr, med_rdr[storey], sa_eval)  # (n_real,)
        beta_r = _interp_beta_vec(sa_rdr, beta_rdr[storey], sa_eval)
        beta_tot = np.sqrt(beta_r ** 2 + beta_m ** 2)
        vals = med * np.exp(beta_tot * z_rdr)
        peak = np.maximum(peak, np.clip(vals, 0.0, _RDR_CAP))
    return peak


def residual_drift_demand(
    archetype: str,
    soil_bin: str,
    sa_t1: float,
    n_realizations: int = 1000,
    seed: int | None = None,
    z: np.ndarray | None = None,
) -> np.ndarray:
    """Scalar-Sa version of :func:`residual_drift_for_sa_field`.

    Every realization shares the same scenario ``sa_t1``. Setting every entry of the
    field equal reproduces this exactly for the same ``seed`` / ``n_realizations``.

    Args:
        z: optional standard-normal column coupling residual drift to the transient draw
            (see :func:`residual_drift_for_sa_field`). If None, drawn from ``seed``.

    Returns:
        (n_realizations,) peak RIDR (unitless).
    """
    return residual_drift_for_sa_field(
        archetype, soil_bin, np.full(int(n_realizations), float(sa_t1)), seed=seed, z=z
    )


def median_residual_drift_for_sa_field(
    archetype: str,
    soil_bin: str,
    sa_field: np.ndarray,
) -> np.ndarray:
    """Per-realization **median** peak RIDR at each field Sa (NO record-to-record sampling).

    This is the demand the FEMA P-58 (2018a, Vol 1 §7.6) / Ramirez & Miranda (2012)
    residual-drift irreparability fragility is conditioned on: the **median** peak residual
    interstory drift at the realization's intensity. The demolition-fragility dispersion
    (``beta_demolition`` ≈ 0.30, in ``demolition_fragility.json``) already represents the
    threshold/transformation uncertainty, so the residual EDP's own record-to-record scatter
    is NOT additionally Monte-Carlo-sampled here — doing so (the pre-2026-06-27 behaviour)
    double-counted the residual aleatory variability and fired spurious demolitions on
    ductile frames whose median residual sits well below the limit. See
    ``docs/learnings/2026-06-27_demolition_recalibration.md``.

    For each ``sa_field[i]`` returns the peak-over-stories of the per-storey log-log
    interpolated lognormal **medians**, with the conditioning Sa clamped to the top
    calibrated stripe (``_RDR_NO_EXTRAP_ABOVE_TOP_STRIPE``) so the residual median is not
    extrapolated into the collapse-governed regime.

    Args:
        archetype: package archetype ID (merged archetypes fall back to a parent).
        soil_bin: native soil bin (falls back within the archetype if absent).
        sa_field: (n_realizations,) per-realization scenario Sa(T_avg) in g.

    Returns:
        (n_realizations,) per-realization median peak RIDR (unitless). Zeros if the dataset
        has no RDR channel.
    """
    arch, sbin = _resolve_dataset(archetype, soil_bin)
    store = _load_store()
    sa_field = np.asarray(sa_field, dtype=float)
    n_real = sa_field.shape[0]

    if not has_residual_drift(arch, sbin):
        return np.zeros(n_real, dtype=float)

    sa_rdr, med_rdr, _ = _stripe_params(store, arch, sbin, _RDR_TYPE)
    sa_eval = sa_field
    if _RDR_NO_EXTRAP_ABOVE_TOP_STRIPE:
        sa_eval = np.minimum(sa_field, float(sa_rdr.max()))

    peak = np.zeros(n_real, dtype=float)
    for storey in sorted(med_rdr):
        med = _interp_loglog_median_vec(sa_rdr, med_rdr[storey], sa_eval)
        peak = np.maximum(peak, np.clip(med, 0.0, _RDR_CAP))
    return peak


def median_residual_drift(archetype: str, soil_bin: str, sa_t1: float) -> float:
    """Deterministic interpolated **median** peak RIDR at ``sa_t1`` (no sampling).

    Peak over stories of the per-storey log-log-interpolated lognormal medians.
    Used for monotonicity checks / diagnostics. Returns 0.0 if no RDR channel.
    """
    arch, sbin = _resolve_dataset(archetype, soil_bin)
    store = _load_store()
    if not has_residual_drift(arch, sbin):
        return 0.0
    sa_rdr, med_rdr, _ = _stripe_params(store, arch, sbin, _RDR_TYPE)
    # Match the production path: no extrapolation of the residual median above the top
    # calibrated stripe (collapse governs there); clamp the conditioning Sa.
    sa_eval = min(sa_t1, float(sa_rdr.max())) if _RDR_NO_EXTRAP_ABOVE_TOP_STRIPE else sa_t1
    return float(
        max(
            _interp_loglog_median(sa_rdr, med_rdr[s], sa_eval)
            for s in sorted(med_rdr)
        )
    )


# ---------------------------------------------------------------------------
# Collapse fragility
# ---------------------------------------------------------------------------
def collapse_probability(archetype: str, soil_bin: str, sa_t1: float) -> float:
    """Return P(collapse | Sa) from the dataset's own lognormal collapse fragility."""
    arch, sbin = _resolve_dataset(archetype, soil_bin)
    coll = _load_collapse()
    row = coll[(coll["archetype"] == arch) & (coll["soil_bin"] == sbin)]
    if row.empty:
        return 0.0
    median = float(row["median_collapse_sa"].iloc[0])
    beta = float(row["beta_collapse"].iloc[0])
    if median <= 0 or beta <= 0 or sa_t1 <= 0:
        return 0.0
    return float(norm.cdf(np.log(sa_t1 / median) / beta))


def collapse_fragility(archetype: str, soil_bin: str) -> dict:
    """Return ``{median_collapse_sa, beta_collapse, n_stories, modelled}`` for the dataset."""
    arch, sbin = _resolve_dataset(archetype, soil_bin)
    coll = _load_collapse()
    row = coll[(coll["archetype"] == arch) & (coll["soil_bin"] == sbin)].iloc[0]
    return {
        "archetype": arch,
        "soil_bin": sbin,
        "median_collapse_sa": float(row["median_collapse_sa"]),
        "beta_collapse": float(row["beta_collapse"]),
        "n_stories": int(row["n_stories"]),
        "modelled": bool(row["modelled"]),
    }


# ---------------------------------------------------------------------------
# Main demand sampler
# ---------------------------------------------------------------------------
def demand_for(
    archetype: str,
    soil_bin: str,
    sa_t1: float,
    n_realizations: int = 1000,
    seed: int | None = None,
) -> DemandSample:
    """Build a Pelicun-ready conditional demand sample at scenario ``Sa(T_avg)``.

    Args:
        archetype: package archetype ID (e.g. ``"C1-M (Hi)"``). Merged archetypes
            (PC-L, PTC1-M (Pre/Lo), PTC4-M (Lo), C4-L (Lo/Mid), C4-M (Mid)) fall back
            to a parent archetype's EDP dataset.
        soil_bin: native soil bin (``"C1"``, ``"C2"``, ``"D"``, or ``"C"``). Falls back
            within the archetype if the exact bin is absent.
        sa_t1: scenario spectral acceleration Sa(T_avg) in g.
        n_realizations: number of Monte-Carlo realizations to draw.
        seed: RNG seed for reproducibility.

    Returns:
        DemandSample. ``edp`` has shape (n_realizations, n_stories, 2) with
        axis-2 = [PID (unitless), PFA (g)], ready for ``building.py``'s assess path.
    """
    arch, sbin = _resolve_dataset(archetype, soil_bin)
    store = _load_store()
    rng = np.random.default_rng(seed)

    # BetaM is constant across stripes/EDP types for a dataset; read it once.
    sub_any = store[(store["archetype"] == arch) & (store["soil_bin"] == sbin)]
    beta_m = float(sub_any["beta_m"].dropna().iloc[0]) if not sub_any.empty else 0.0

    # --- Story Drift Ratio -> PID (storeys 1..N) ---
    sa_pid, med_pid, beta_pid = _stripe_params(store, arch, sbin, _PID_TYPE)
    pid_storeys = sorted(med_pid)  # 1..N
    n_stories = len(pid_storeys)

    # --- Acceleration -> PFA (floors 0..N); building.py wants stories 1..N ---
    sa_pfa, med_pfa, beta_pfa = _stripe_params(store, arch, sbin, _PFA_TYPE)
    pfa_floors = sorted(med_pfa)  # 0..N

    # Shared per-realization standard-normal draws (rank-preserving height-wise
    # correlation): one column per EDP type, broadcast across stories. PID and PFA
    # independent of each other.
    z_pid: np.ndarray = np.asarray(rng.standard_normal(n_realizations))
    z_pfa: np.ndarray = np.asarray(rng.standard_normal(n_realizations))

    edp = np.zeros((n_realizations, n_stories, 2), dtype=float)

    # PID per story (story s spans level s; index 0..N-1 -> story 1..N)
    for i, storey in enumerate(pid_storeys):
        med = _interp_loglog_median(sa_pid, med_pid[storey], sa_t1)
        beta_r = _interp_beta(sa_pid, beta_pid[storey], sa_t1)
        beta_tot = np.sqrt(beta_r ** 2 + beta_m ** 2)
        vals = med * np.exp(beta_tot * z_pid)
        edp[:, i, 0] = np.clip(vals, 0.0, _PID_CAP)

    # PFA per story: map building story s (1..N) to floor s (the floor at the TOP of
    # the story, the acceleration-relevant level). Floors available are 0..N; use floor
    # index s. If absent, clamp to the nearest available floor.
    for i in range(n_stories):
        target_floor = i + 1  # story i+1 -> floor i+1
        floor = target_floor if target_floor in med_pfa else max(pfa_floors)
        med = _interp_loglog_median(sa_pfa, med_pfa[floor], sa_t1)
        beta_r = _interp_beta(sa_pfa, beta_pfa[floor], sa_t1)
        beta_tot = np.sqrt(beta_r ** 2 + beta_m ** 2)
        vals = med * np.exp(beta_tot * z_pfa)
        edp[:, i, 1] = np.clip(vals, 0.0, _PFA_CAP)

    # --- Collapse ---
    p_collapse = collapse_probability(arch, sbin, sa_t1)
    collapse_mask = rng.random(n_realizations) < p_collapse

    return DemandSample(
        edp=edp,
        collapse_mask=collapse_mask,
        p_collapse=p_collapse,
        n_stories=n_stories,
        archetype=arch,
        soil_bin=sbin,
        sa_t1=float(sa_t1),
        z_pid=z_pid,
    )


def demand_for_sa_field(
    archetype: str,
    soil_bin: str,
    sa_field: np.ndarray,
    seed: int | None = None,
) -> DemandSample:
    """Build a Pelicun demand sample where EACH realization has its OWN scenario Sa.

    This is the portfolio path. Unlike :func:`demand_for` (one scalar ``sa_t1`` shared
    by every realization), here ``sa_field[i]`` is the Sa(T_avg) for realization ``i``
    — i.e. the spatially-correlated hazard field drawn for this building by
    ``hazard.scenario_sa_field``. The demand for realization ``i`` is conditioned on
    ``sa_field[i]`` via the same per-stripe log-log median / beta interpolation used by
    the scalar path, so the cross-building hazard correlation (carried in the aligned
    realization index) propagates straight into the per-realization loss.

    The lognormal scatter draw uses ONE standard-normal column per EDP type, shared
    across stories (rank-preserving height-wise correlation), exactly as
    :func:`demand_for`. Setting every ``sa_field[i]`` equal therefore reproduces
    :func:`demand_for` for the same ``seed`` and ``n_realizations``.

    Args:
        archetype: package archetype ID. Merged archetypes fall back to a parent.
        soil_bin: native soil bin (falls back within the archetype if absent).
        sa_field: (n_realizations,) per-realization scenario Sa(T_avg) in g.
        seed: RNG seed for reproducibility.

    Returns:
        DemandSample with ``edp`` of shape (n_realizations, n_stories, 2),
        axis-2 = [PID (unitless), PFA (g)], a per-realization ``collapse_mask``, and
        ``p_collapse`` set to the MEAN collapse probability across the field (scalar
        summary; per-realization collapse is in ``collapse_mask``). ``sa_t1`` is set to
        the median of the field (diagnostic only).
    """
    arch, sbin = _resolve_dataset(archetype, soil_bin)
    store = _load_store()
    rng = np.random.default_rng(seed)

    sa_field = np.asarray(sa_field, dtype=float)
    n_real = sa_field.shape[0]

    beta_m = float(sub_any["beta_m"].dropna().iloc[0]) if not (
        sub_any := store[(store["archetype"] == arch) & (store["soil_bin"] == sbin)]
    ).empty else 0.0

    # --- Story Drift Ratio -> PID (storeys 1..N) ---
    sa_pid, med_pid, beta_pid = _stripe_params(store, arch, sbin, _PID_TYPE)
    pid_storeys = sorted(med_pid)
    n_stories = len(pid_storeys)

    # --- Acceleration -> PFA (floors 0..N) ---
    sa_pfa, med_pfa, beta_pfa = _stripe_params(store, arch, sbin, _PFA_TYPE)
    pfa_floors = sorted(med_pfa)

    # Shared per-realization standard-normal draws (one column per EDP type).
    z_pid: np.ndarray = np.asarray(rng.standard_normal(n_real))
    z_pfa: np.ndarray = np.asarray(rng.standard_normal(n_real))

    edp = np.zeros((n_real, n_stories, 2), dtype=float)

    # PID per story: median & beta interpolated at each realization's own Sa.
    for i, storey in enumerate(pid_storeys):
        med = _interp_loglog_median_vec(sa_pid, med_pid[storey], sa_field)   # (n_real,)
        beta_r = _interp_beta_vec(sa_pid, beta_pid[storey], sa_field)         # (n_real,)
        beta_tot = np.sqrt(beta_r ** 2 + beta_m ** 2)
        vals = med * np.exp(beta_tot * z_pid)
        edp[:, i, 0] = np.clip(vals, 0.0, _PID_CAP)

    # PFA per story: map building story s (1..N) to floor s (top-of-story level).
    for i in range(n_stories):
        target_floor = i + 1
        floor = target_floor if target_floor in med_pfa else max(pfa_floors)
        med = _interp_loglog_median_vec(sa_pfa, med_pfa[floor], sa_field)
        beta_r = _interp_beta_vec(sa_pfa, beta_pfa[floor], sa_field)
        beta_tot = np.sqrt(beta_r ** 2 + beta_m ** 2)
        vals = med * np.exp(beta_tot * z_pfa)
        edp[:, i, 1] = np.clip(vals, 0.0, _PFA_CAP)

    # --- Collapse: per-realization Bernoulli at each realization's own Sa ---
    coll = _load_collapse()
    crow = coll[(coll["archetype"] == arch) & (coll["soil_bin"] == sbin)]
    if crow.empty:
        p_field = np.zeros(n_real)
    else:
        c_med = float(crow["median_collapse_sa"].iloc[0])
        c_beta = float(crow["beta_collapse"].iloc[0])
        if c_med <= 0 or c_beta <= 0:
            p_field = np.zeros(n_real)
        else:
            safe_sa = np.clip(sa_field, 1e-9, None)
            p_field = norm.cdf(np.log(safe_sa / c_med) / c_beta)
    collapse_mask = rng.random(n_real) < p_field

    return DemandSample(
        edp=edp,
        collapse_mask=collapse_mask,
        p_collapse=float(np.mean(p_field)),
        n_stories=n_stories,
        archetype=arch,
        soil_bin=sbin,
        sa_t1=float(np.median(sa_field)),
        z_pid=z_pid,
    )


def median_demand(
    archetype: str, soil_bin: str, sa_t1: float
) -> dict[str, np.ndarray]:
    """Return the deterministic interpolated **median** PID/PFA profiles at ``sa_t1``.

    Useful for monotonicity checks and diagnostics (no sampling). Keys: ``pid`` (story
    1..N), ``pfa`` (story 1..N, using floor s for story s).
    """
    arch, sbin = _resolve_dataset(archetype, soil_bin)
    store = _load_store()
    sa_pid, med_pid, _ = _stripe_params(store, arch, sbin, _PID_TYPE)
    sa_pfa, med_pfa, _ = _stripe_params(store, arch, sbin, _PFA_TYPE)
    pid_storeys = sorted(med_pid)
    pfa_floors = sorted(med_pfa)
    pid = np.array(
        [_interp_loglog_median(sa_pid, med_pid[s], sa_t1) for s in pid_storeys]
    )
    pfa = np.array([
        _interp_loglog_median(
            sa_pfa, med_pfa[(i + 1) if (i + 1) in med_pfa else max(pfa_floors)], sa_t1
        )
        for i in range(len(pid_storeys))
    ])
    return {"pid": pid, "pfa": pfa}
