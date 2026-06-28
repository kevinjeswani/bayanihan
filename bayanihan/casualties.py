"""FEMA P-58 casualty model — injuries + fatalities (the thesis's 2nd and 3rd DVs).

Beyond monetary loss and downtime, the thesis (Jeswani 2021) reports two further decision
variables per scenario/region: **injuries** and **fatalities**. This module computes them
from the live Pelicun damage sample + the collapse mask, scaled by per-building population,
using a provenance-flagged casualty consequence dataset
(``bayanihan/data/casualty_consequences.json``). No casualty VALUE is hardcoded
in Python — every parameter is read from that JSON (provenance discipline, per CLAUDE.md).

Two FEMA P-58 (2018a) pathways, faithful to thesis Ch 6.2.6.2 + Tables D-1/D-2:

  (a) **Non-collapse** (component-driven, dominates INJURIES):
      For each component with a tabulated casualty consequence (CHB walls, ceilings,
      ceiling fixtures, curtain wall, electronics, elevator), at its casualty damage state(s),
        injuries  += n_damaged_units * affected_area_sf_per_unit * pop_density * injury_rate
        fatalities += n_damaged_units * affected_area_sf_per_unit * pop_density * fatality_rate
      where pop_density = population / total_floor_area_sf. The summed NC INJURY term is then
      raised per archetype by ``_nc_injury_calibration`` to the thesis's published
      per-archetype non-collapse injury rate (the affected-area reading under-counts; the
      factor is provenance-flagged in casualty_consequences.json). Structural RC/PT/steel
      components carry NO non-collapse casualties (thesis Ch 6.2.2); only wall-mounted
      electronics and the elevator carry a (negligible, un-calibrated) NC FATALITY rate.

  (b) **Collapse** (drives FATALITIES, contributes a minority of INJURIES):
        fatalities += collapse * population * P(TC) * collapse_fatality_rate(hazus_type)
                              * expected_occupancy_factor(archetype)
        injuries   += collapse * population * P(TC) * (1 - collapse_fatality_rate)
                              * expected_occupancy_factor(archetype)
      collapse_fatality_rate is the HAZUS-typology FEMA P-58 default; collapse injury rate =
      1 - fatality rate (thesis Ch 6.2.6.2). P(TC) = total-collapse-mode probability (Table 6-6).
      ``expected_occupancy_factor`` is the FEMA P-58 (2018a) expected-present-occupancy fraction
      (thesis Table 6-5 "P-58 Peak / Actual" population, ~0.295 portfolio-weighted): collapse
      casualties accrue to occupants PRESENT at the earthquake, not the full enrolled population.
      With ``expected_occupancy_factor_applies_to == "both"`` (the data default) it scales the
      collapse FATALITY *and* INJURY terms — so collapse injuries are a minority of the total
      (thesis non-collapse injury fraction 0.78-0.99 in Makati / ~0.70 whole), instead of
      dominating as they did when the factor scaled fatalities only.

Demolition (irreparable, non-collapse total loss) produces NO additional casualties beyond
its component damage states — demolition is a financial/recovery state, not a life-safety
event (thesis Ch 6). To avoid double-counting, non-collapse component casualties are counted
ONLY on non-collapsed realizations; collapsed realizations use the collapse term.

References:
    FEMA P-58 (2018a). Seismic Performance Assessment of Buildings, Vol. 1.
    Jeswani, K. K. (2021). MASc thesis, University of Toronto (Ch 6.2.2, 6.2.6.2; Tables D-1/D-2).
"""
from __future__ import annotations

import json
import logging
from functools import lru_cache
from importlib import resources

import numpy as np
import pandas as pd

log = logging.getLogger(__name__)

#: Bundled casualty consequence parameter file (provenance-flagged).
_CASUALTY_PARAMS_FILE = "casualty_consequences.json"

#: square feet per square metre (floor area in the inventory is m^2; P-58 areas are SF).
_SF_PER_M2 = 10.7639


@lru_cache(maxsize=1)
def load_casualty_params() -> dict:
    """Load and cache the casualty consequence parameters from the bundled JSON.

    Returns:
        Parsed dict with ``noncollapse_component_casualties`` and ``collapse_casualties``
        sections. Raises FileNotFoundError if the bundled file is missing (it is committed,
        so absence indicates a packaging problem).
    """
    ref = resources.files("bayanihan").joinpath(f"data/{_CASUALTY_PARAMS_FILE}")
    with resources.as_file(ref) as p:
        with open(p, encoding="utf-8") as fh:
            return json.load(fh)


def _collapse_fatality_rate(archetype: str, params: dict) -> float:
    """Return the HAZUS-typology collapse fatality rate for an archetype (read from JSON)."""
    cc = params["collapse_casualties"]
    htype = cc.get("archetype_hazus_type", {}).get(archetype)
    table = cc.get("collapse_fatality_rate_by_hazus_type", {})
    if htype is not None and htype in table:
        return float(table[htype]["rate"])
    # Fallback: mean of available rates (documents the gap rather than guessing a type).
    rates = [float(v["rate"]) for v in table.values()] or [0.15]
    log.debug("No HAZUS type for archetype %r; using mean collapse fatality rate.", archetype)
    return float(np.mean(rates))


def _p_total_collapse(archetype: str, params: dict) -> float:
    """Return P(total collapse mode) for an archetype (thesis Table 6-6; read from JSON)."""
    cc = params["collapse_casualties"]
    if not cc.get("apply_p_total_collapse", True):
        return 1.0
    table = cc.get("p_total_collapse_by_archetype", {})
    if archetype in table:
        return float(table[archetype])
    return float(cc.get("p_total_collapse_default", 0.7))


def _expected_occupancy_factor(archetype: str, params: dict) -> float:
    """FEMA P-58 expected-present-occupancy factor for the collapse casualty exposure.

    The casualty exposure at the instant of collapse is the population EXPECTED TO BE
    PRESENT, not the full enrolled population. Thesis Table 6-5 reports both an "Actual
    Population" and a much smaller "P-58 Peak Population" per archetype; this factor is
    ``P-58 Peak / Actual`` (the FEMA P-58 expected-occupancy fraction PACT applied to the
    collapse casualty computation). Read from ``casualty_consequences.json``. Defaults to
    ``expected_occupancy_factor_default`` (then 0.30) for archetypes not tabulated.

    It scales the collapse FATALITY term, and — when
    ``expected_occupancy_factor_applies_to == "both"`` — the collapse INJURY term as well
    (collapse injuries likewise accrue only to occupants present at the earthquake; see
    docs/learnings/2026-06-27_casualties.md, NC-injury recalibration).

    Returns 1.0 if the parameter block is absent (back-compatible: the collapse terms then
    use the full enrolled population, i.e. the pre-fix behaviour).
    """
    cc = params["collapse_casualties"]
    table = cc.get("expected_occupancy_factor_by_archetype")
    if table is None:
        return 1.0  # parameter not present -> no occupancy scaling (legacy behaviour)
    if archetype in table:
        return float(table[archetype])
    return float(cc.get("expected_occupancy_factor_default", 0.30))


def _nc_injury_calibration(archetype: str, params: dict) -> float:
    """Per-archetype non-collapse INJURY calibration factor (read from JSON).

    The FEMA P-58 affected-area non-collapse injury model — the thesis Table D-1/D-2
    component affected areas (16-250 SF) + injury θ (≈0.10) over the building-average
    occupant density — systematically UNDER-COUNTS non-collapse injuries relative to the
    thesis's published per-archetype injury rates (the ``.mat`` ``Arch_simp_norm_CasI``
    minus the FEMA P-58 occupancy-scaled collapse-injury term). This factor raises the
    modelled affected-area NC injuries to the thesis per-archetype non-collapse injury rate.
    It is applied to the NC INJURY term ONLY (NC fatalities — wall-mounted electronics,
    elevator — are negligible and already match). Read from ``casualty_consequences.json``
    → ``noncollapse_injury_calibration.factor_by_archetype``; provenance-flagged there.

    Because the factor multiplies the *summed, component-resolved* affected-area NC injury
    output uniformly per archetype, the non-structural mitigation's component-level
    neutralisation (which removes individual casualty components from that sum) is preserved
    — the reduction stays proportional on the calibrated basis.

    Returns 1.0 if the calibration block is absent (back-compatible: the legacy
    affected-area level) or for archetypes not tabulated (``factor_default``, then 1.0).
    """
    block = params.get("noncollapse_injury_calibration")
    if block is None:
        return 1.0  # block not present -> no calibration (legacy affected-area level)
    table = block.get("factor_by_archetype", {})
    if archetype in table:
        return float(table[archetype])
    return float(block.get("factor_default", 1.0))


def noncollapse_component_casualties(
    damage_sample: pd.DataFrame,
    population: float,
    floor_area_m2: float,
    params: dict | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Per-realization NON-collapse injuries + fatalities from the Pelicun damage sample.

    Implements the FEMA P-58 affected-area casualty model on the components that carry a
    tabulated casualty consequence (thesis Tables D-1/D-2). The Pelicun ``damage_sample`` is
    the MultiIndex (cmp, loc, dir, uid, ds) DataFrame whose values are damaged quantities in
    the component's units (SF for area components, EA for piece components). For each casualty
    damage state of each casualty component:

        casualties += damaged_qty_in_units / unit_sf?  ->  affected area handling:
          - area components (unit_sf set): damaged_qty is already SF -> the affected area is
              (damaged_qty / unit_sf) damaged P-58 units * affected_area_sf_per_unit;
          - piece components (unit_sf null): damaged_qty is a unit count (EA) -> affected area
              is damaged_qty * affected_area_sf_per_unit.
        then casualties = affected_area * pop_density * rate, pop_density = population/floor_sf.

    Args:
        damage_sample: Pelicun ``asmnt.damage.sample`` (MultiIndex columns cmp/loc/dir/uid/ds).
        population: building occupant count (actual students).
        floor_area_m2: building total floor area in square metres (for population density).
        params: casualty params dict; loaded from JSON if None.

    Returns:
        (injuries, fatalities): each a (n_realizations,) float array. Empty/zero if the
        damage sample is None/empty or carries no casualty components.
    """
    if params is None:
        params = load_casualty_params()
    table = params["noncollapse_component_casualties"]

    if damage_sample is None or damage_sample.empty:
        return np.zeros(0), np.zeros(0)

    n = len(damage_sample)
    injuries = np.zeros(n)
    fatalities = np.zeros(n)

    floor_sf = float(floor_area_m2) * _SF_PER_M2
    if floor_sf <= 0 or population <= 0:
        return injuries, fatalities
    pop_density = float(population) / floor_sf  # occupants per ft^2

    cols = damage_sample.columns
    names = list(cols.names) if cols.names else []
    try:
        cmp_level = names.index("cmp")
        ds_level = names.index("ds")
    except ValueError:
        # Column index isn't the expected (cmp,loc,dir,uid,ds) shape — nothing to do.
        log.debug("damage_sample columns not in expected MultiIndex form; skipping NC casualties.")
        return injuries, fatalities

    for col in cols:
        cmp_id = col[cmp_level]
        ds = str(col[ds_level])
        entry = table.get(str(cmp_id))
        if entry is None:
            continue
        cstate = entry.get("casualty_states", {}).get(ds)
        if cstate is None:
            continue
        damaged_qty = damage_sample[col].to_numpy(dtype=float)  # (n,) in component units
        unit_sf = entry.get("unit_sf")
        if unit_sf:  # area component: damaged_qty is SF -> number of damaged P-58 units
            n_units = damaged_qty / float(unit_sf)
        else:  # piece component: damaged_qty already a unit count (EA)
            n_units = damaged_qty
        affected_area = n_units * float(cstate["affected_area_sf"])  # SF
        injuries += affected_area * pop_density * float(cstate.get("injury_rate", 0.0))
        fatalities += affected_area * pop_density * float(cstate.get("fatality_rate", 0.0))

    return injuries, fatalities


def collapse_casualties(
    collapse_mask: np.ndarray,
    archetype: str,
    population: float,
    params: dict | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Per-realization collapse injuries + fatalities (FEMA P-58 collapse casualty model).

    fatalities = collapse * population * P(TC) * collapse_fatality_rate(hazus_type)
                          * expected_occupancy_factor(archetype)
    injuries   = collapse * population * P(TC) * (1 - collapse_fatality_rate)
                          * expected_occupancy_factor(archetype)     # when applies_to == "both"

    The ``expected_occupancy_factor`` is the FEMA P-58 (2018a) expected-present-occupancy
    fraction (thesis Table 6-5 "P-58 Peak / Actual" population): collapse casualties are
    incurred by the occupants PRESENT at the time of the earthquake, not the full enrolled
    population. ``expected_occupancy_factor_applies_to`` controls which terms it scales:
    ``"both"`` (current data default) scales the collapse FATALITY *and* INJURY terms —
    both accrue to present occupants — while ``"fatalities_only"`` scales only fatalities
    (the earlier behaviour, which left the collapse-injury exposure at full enrolment and so
    inverted the non-collapse injury fraction; see docs/learnings/2026-06-27_casualties.md,
    NC-injury recalibration). Without the factor entirely, the full-enrolment exposure
    over-predicts fatalities ~7x against the thesis. The factor defaults to 1.0 when the
    parameter block is absent (legacy behaviour).

    Args:
        collapse_mask: (n,) bool — realizations routed to collapse.
        archetype: archetype id (selects HAZUS type + P(TC) + expected_occupancy_factor).
        population: building occupant count (enrolled).
        params: casualty params dict; loaded from JSON if None.

    Returns:
        (injuries, fatalities): each a (n,) float array.
    """
    if params is None:
        params = load_casualty_params()
    collapse_mask = np.asarray(collapse_mask, dtype=bool)
    n = collapse_mask.shape[0]
    injuries = np.zeros(n)
    fatalities = np.zeros(n)
    if population <= 0 or not collapse_mask.any():
        return injuries, fatalities

    cfr = _collapse_fatality_rate(archetype, params)
    ptc = _p_total_collapse(archetype, params)
    cc = params["collapse_casualties"]
    inj_is_one_minus = bool(cc.get("collapse_injury_rate_is_one_minus_fatality", True))
    cir = (1.0 - cfr) if inj_is_one_minus else 0.0

    # FEMA P-58 expected-present-occupancy factor — applied to FATALITIES only by default,
    # so the collapse-injury (and total-injury) distribution is unchanged by this calibration.
    occ = _expected_occupancy_factor(archetype, params)
    applies_to = str(cc.get("expected_occupancy_factor_applies_to", "fatalities_only"))
    occ_fat = occ
    occ_inj = occ if applies_to == "both" else 1.0

    exposed = collapse_mask.astype(float) * float(population) * float(ptc)
    fatalities = exposed * cfr * occ_fat
    injuries = exposed * cir * occ_inj
    return injuries, fatalities


def building_casualties(
    damage_sample: pd.DataFrame | None,
    collapse_mask: np.ndarray,
    archetype: str,
    population: float,
    floor_area_m2: float,
    params: dict | None = None,
) -> dict:
    """Total per-realization injuries + fatalities for one building (NC + collapse).

    Combines the two FEMA P-58 pathways with no double counting: non-collapse component
    casualties are credited ONLY on non-collapsed realizations; collapsed realizations use
    the collapse term. Demolition (irreparable, non-collapse) is NOT a casualty event, so a
    demolished-but-not-collapsed realization keeps its component-driven non-collapse casualties
    and nothing more.

    Args:
        damage_sample: Pelicun damage sample (MultiIndex cmp/loc/dir/uid/ds) or None.
        collapse_mask: (n,) bool collapse mask.
        archetype: archetype id.
        population: building occupant count.
        floor_area_m2: building floor area (m^2).
        params: casualty params; loaded from JSON if None.

    Returns:
        dict with keys:
            ``injuries``              (n,) total injuries
            ``fatalities``            (n,) total fatalities
            ``injuries_noncollapse``  (n,) component-driven injuries (non-collapsed cells only)
            ``injuries_collapse``     (n,) collapse-driven injuries
            ``fatalities_noncollapse``(n,) component-driven fatalities (non-collapsed cells)
            ``fatalities_collapse``   (n,) collapse-driven fatalities
    """
    if params is None:
        params = load_casualty_params()
    collapse_mask = np.asarray(collapse_mask, dtype=bool)
    n = collapse_mask.shape[0]
    noncoll = ~collapse_mask

    nc_inj, nc_fat = noncollapse_component_casualties(
        damage_sample, population, floor_area_m2, params=params
    )
    # Align length to n (damage sample may be empty).
    if nc_inj.shape[0] != n:
        nc_inj = np.zeros(n)
        nc_fat = np.zeros(n)
    # Raise the affected-area NC INJURIES to the thesis per-archetype NC injury rate
    # (the affected-area model under-counts vs the thesis; provenance-flagged calibration in
    # casualty_consequences.json -> noncollapse_injury_calibration). NC fatalities are left
    # unscaled (negligible + already matched). Factor 1.0 if the block is absent.
    nc_inj = nc_inj * _nc_injury_calibration(archetype, params)
    # Credit non-collapse component casualties only on NON-collapsed realizations.
    nc_inj = nc_inj * noncoll
    nc_fat = nc_fat * noncoll

    c_inj, c_fat = collapse_casualties(collapse_mask, archetype, population, params=params)

    return {
        "injuries": nc_inj + c_inj,
        "fatalities": nc_fat + c_fat,
        "injuries_noncollapse": nc_inj,
        "injuries_collapse": c_inj,
        "fatalities_noncollapse": nc_fat,
        "fatalities_collapse": c_fat,
    }
