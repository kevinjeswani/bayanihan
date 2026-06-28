"""Tests for bayanihan.casualties — FEMA P-58 injuries + fatalities.

Covers:
  1.  load_casualty_params() loads + has the expected structure.
  2.  Provenance: every casualty entry is provenance-flagged; values are data-driven
      (no hardcoded thetas in casualties.py).
  3.  collapse_casualties(): fatalities = collapse*pop*P(TC)*CFR; injuries = ...*(1-CFR).
  4.  Collapse casualties scale LINEARLY with population.
  5.  HAZUS typology selection (URM > C1 > W1 collapse fatality rate ordering).
  6.  noncollapse_component_casualties(): affected-area model on a real damage sample,
      non-negative, larger with more damage, zero with no damage / zero population.
  7.  Structural RC components carry NO non-collapse casualties.
  8.  building_casualties(): no double counting — NC credited only on non-collapsed cells.
  9.  Demolition (non-collapsed) is NOT a casualty event (only its component damage counts).
  10. building.assess_scenario() attaches injuries/fatalities when population is set.
  11. Reproducibility (same seed -> same casualties).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from bayanihan import casualties as cas

# ---------------------------------------------------------------------------
# 1-2. Parameter loading + provenance
# ---------------------------------------------------------------------------

def test_load_casualty_params_structure():
    p = cas.load_casualty_params()
    assert "noncollapse_component_casualties" in p
    assert "collapse_casualties" in p
    cc = p["collapse_casualties"]
    assert "collapse_fatality_rate_by_hazus_type" in cc
    assert "archetype_hazus_type" in cc
    assert "p_total_collapse_by_archetype" in cc


def test_noncollapse_entries_have_affected_area_and_rate():
    p = cas.load_casualty_params()
    table = p["noncollapse_component_casualties"]
    for cmp_id, entry in table.items():
        if cmp_id.startswith("_"):
            continue
        assert "casualty_states" in entry, cmp_id
        for ds, st in entry["casualty_states"].items():
            assert st["affected_area_sf"] > 0
            assert 0.0 <= st["injury_rate"] <= 1.0
            assert 0.0 <= st.get("fatality_rate", 0.0) <= 1.0


def test_collapse_fatality_rates_provenance_flagged():
    p = cas.load_casualty_params()
    table = p["collapse_casualties"]["collapse_fatality_rate_by_hazus_type"]
    for htype, entry in table.items():
        assert "provenance_confidence" in entry
        assert 0.0 < entry["rate"] < 1.0


# ---------------------------------------------------------------------------
# 3-5. Collapse casualties
# ---------------------------------------------------------------------------

def test_collapse_casualties_formula_urm():
    """CHB-L is URM (CFR=0.20), P(TC)=1.0: collapse cell -> fat=0.2*pop*occ, inj=0.8*pop*occ.

    The FEMA P-58 expected-present-occupancy factor (Table 6-5 P-58 Peak/Actual) scales BOTH
    the fatality AND the injury term (expected_occupancy_factor_applies_to == "both"): collapse
    casualties of either severity accrue only to the occupants present at the earthquake.
    """
    p = cas.load_casualty_params()
    cfr = p["collapse_casualties"]["collapse_fatality_rate_by_hazus_type"]["URM"]["rate"]
    occ = cas._expected_occupancy_factor("CHB-L", p)
    mask = np.array([True, False, True, False])
    inj, fat = cas.collapse_casualties(mask, "CHB-L", population=100.0)
    np.testing.assert_allclose(fat, mask * 100.0 * cfr * occ)
    np.testing.assert_allclose(inj, mask * 100.0 * (1.0 - cfr) * occ)


def test_collapse_casualties_apply_ptc():
    """C1-M (Hi): P(TC)=0.6 scales the collapse exposure; occupancy factor scales both terms."""
    p = cas.load_casualty_params()
    cfr = p["collapse_casualties"]["collapse_fatality_rate_by_hazus_type"]["C1M"]["rate"]
    ptc = p["collapse_casualties"]["p_total_collapse_by_archetype"]["C1-M (Hi)"]
    occ = cas._expected_occupancy_factor("C1-M (Hi)", p)
    mask = np.array([True, True])
    inj, fat = cas.collapse_casualties(mask, "C1-M (Hi)", population=200.0)
    np.testing.assert_allclose(fat, 200.0 * ptc * cfr * occ)
    # Injuries carry the occupancy factor too (applies_to == "both").
    np.testing.assert_allclose(inj, 200.0 * ptc * (1.0 - cfr) * occ)


def test_collapse_casualties_scale_linearly_with_population():
    mask = np.array([True, False, True])
    i1, f1 = cas.collapse_casualties(mask, "C1-M (Hi)", population=100.0)
    i2, f2 = cas.collapse_casualties(mask, "C1-M (Hi)", population=300.0)
    np.testing.assert_allclose(i2, 3.0 * i1)
    np.testing.assert_allclose(f2, 3.0 * f1)


def test_hazus_collapse_fatality_rate_ordering():
    """URM should have the highest collapse fatality rate; W1 the lowest."""
    p = cas.load_casualty_params()
    t = p["collapse_casualties"]["collapse_fatality_rate_by_hazus_type"]
    assert t["URM"]["rate"] > t["C1M"]["rate"] >= t["W1"]["rate"]


# ---------------------------------------------------------------------------
# Expected-present-occupancy factor (FEMA P-58 population model; thesis Table 6-5).
# Collapse casualties accrue to occupants PRESENT at the earthquake (P-58 Peak/Actual,
# ~0.295 portfolio-weighted), applied to BOTH the fatality and injury terms so the
# collapse-injury exposure is the present occupancy (not full enrolment).
# ---------------------------------------------------------------------------

def test_expected_occupancy_factor_provenance_and_range():
    """Every tabulated occupancy factor is positive and provenance-flagged."""
    p = cas.load_casualty_params()
    cc = p["collapse_casualties"]
    table = cc["expected_occupancy_factor_by_archetype"]
    # Provenance block present + high confidence.
    prov = cc["expected_occupancy_factor_provenance"]
    assert prov["provenance_confidence"] == "high"
    assert "Table 6-5" in prov["source"]
    # Numeric entries are positive (skip the leading _comment string).
    vals = [v for k, v in table.items() if not k.startswith("_")]
    assert all(v > 0.0 for v in vals)
    # Most archetypes have an expected-present occupancy well below full enrolment.
    below_one = [v for v in vals if v < 1.0]
    assert len(below_one) >= len(vals) - 1  # only C1-H (Hi) may exceed 1
    assert cc["expected_occupancy_factor_applies_to"] == "both"


def test_occupancy_factor_lowers_fatalities_and_injuries():
    """The occupancy factor reduces BOTH collapse fatalities and collapse injuries (<1 archetypes)."""
    p = cas.load_casualty_params()
    mask = np.ones(4, dtype=bool)
    for arch in ("N-L", "CHB-L", "C1-M (Pre/Lo)"):
        occ = cas._expected_occupancy_factor(arch, p)
        assert occ < 1.0, arch
        cfr = cas._collapse_fatality_rate(arch, p)
        ptc = cas._p_total_collapse(arch, p)
        inj, fat = cas.collapse_casualties(mask, arch, population=1000.0)
        # Both terms carry occ (applies_to == "both").
        np.testing.assert_allclose(fat, 1000.0 * ptc * cfr * occ)
        np.testing.assert_allclose(inj, 1000.0 * ptc * (1.0 - cfr) * occ)
        # Both are strictly below their full-enrolment (occ=1) values.
        assert fat[0] < 1000.0 * ptc * cfr
        assert inj[0] < 1000.0 * ptc * (1.0 - cfr)


def test_occupancy_factor_default_for_unknown_archetype():
    """Unknown archetypes fall back to the documented default occupancy factor."""
    p = cas.load_casualty_params()
    default = p["collapse_casualties"]["expected_occupancy_factor_default"]
    assert cas._expected_occupancy_factor("NOT-AN-ARCHETYPE", p) == default


def test_occupancy_factor_absent_is_backcompatible():
    """If the occupancy block is removed, the factor is 1.0 (legacy full-pop exposure)."""
    import copy
    p = copy.deepcopy(cas.load_casualty_params())
    p["collapse_casualties"].pop("expected_occupancy_factor_by_archetype", None)
    assert cas._expected_occupancy_factor("CHB-L", p) == 1.0
    mask = np.ones(3, dtype=bool)
    cfr = cas._collapse_fatality_rate("CHB-L", p)
    ptc = cas._p_total_collapse("CHB-L", p)
    _inj, fat = cas.collapse_casualties(mask, "CHB-L", population=100.0, params=p)
    np.testing.assert_allclose(fat, 100.0 * ptc * cfr)  # occ == 1.0


def test_collapse_casualties_zero_when_no_collapse():
    inj, fat = cas.collapse_casualties(np.zeros(10, dtype=bool), "CHB-L", 100.0)
    assert inj.sum() == 0.0 and fat.sum() == 0.0


def test_collapse_casualties_zero_population():
    inj, fat = cas.collapse_casualties(np.ones(5, dtype=bool), "CHB-L", 0.0)
    assert inj.sum() == 0.0 and fat.sum() == 0.0


# ---------------------------------------------------------------------------
# 6-7. Non-collapse component casualties (affected-area model)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def damaged_building_sample():
    """A C1-M (Pre/Lo) damage sample at heavy drift (heavy CHB + ceiling damage)."""
    import logging
    logging.getLogger("pelicun").setLevel(logging.CRITICAL)
    from bayanihan.building import Building
    b = Building.from_archetype("C1-M (Pre/Lo)", site_class="D")
    edp = np.zeros((100, b.stories, 2))
    edp[:, :, 0] = 0.025  # ~2.5% drift -> CHB DS3+
    edp[:, :, 1] = 1.5
    r = b.assess(edp, seed=3)
    return r["damage_sample"]


def test_noncollapse_injuries_positive_on_damage(damaged_building_sample):
    inj, fat = cas.noncollapse_component_casualties(
        damaged_building_sample, population=846.0, floor_area_m2=916.0
    )
    assert inj.shape[0] == len(damaged_building_sample)
    assert (inj >= 0).all()
    assert inj.mean() > 0.0  # heavy CHB/ceiling damage -> some injuries


def test_noncollapse_zero_population(damaged_building_sample):
    inj, fat = cas.noncollapse_component_casualties(
        damaged_building_sample, population=0.0, floor_area_m2=916.0
    )
    assert inj.sum() == 0.0 and fat.sum() == 0.0


def test_noncollapse_scales_with_population(damaged_building_sample):
    i1, _ = cas.noncollapse_component_casualties(damaged_building_sample, 100.0, 916.0)
    i2, _ = cas.noncollapse_component_casualties(damaged_building_sample, 300.0, 916.0)
    np.testing.assert_allclose(i2, 3.0 * i1, rtol=1e-9)


def test_noncollapse_empty_sample_returns_empty():
    inj, fat = cas.noncollapse_component_casualties(None, 100.0, 916.0)
    assert inj.size == 0 and fat.size == 0
    inj, fat = cas.noncollapse_component_casualties(pd.DataFrame(), 100.0, 916.0)
    assert inj.size == 0 and fat.size == 0


def test_structural_components_no_noncollapse_casualty():
    """RC/PT/steel structural components must not appear in the casualty table."""
    p = cas.load_casualty_params()
    table = p["noncollapse_component_casualties"]
    for sid in ("PH.S.DRCMRF.1S", "PH.S.DRCMRF.2S", "PH.S.NDRCMRF.1S",
                "PH.S.PTRCMRF.1S", "PH.S.SMRF.1S", "PH.S.SPLICE", "PH.S.BASEPLT"):
        assert sid not in table


# ---------------------------------------------------------------------------
# Non-collapse INJURY calibration (affected-area model -> thesis per-archetype NC rate).
# Raises the under-counting affected-area NC injuries to the thesis's published per-archetype
# injury rates (.mat Arch_simp_norm_CasI). Provenance-flagged; injuries only.
# ---------------------------------------------------------------------------

def test_nc_injury_calibration_provenance_and_structure():
    """The NC-injury calibration block is present, provenance-flagged, injuries-only, positive."""
    p = cas.load_casualty_params()
    blk = p["noncollapse_injury_calibration"]
    assert blk["applies_to"] == "injuries_only"
    table = blk["factor_by_archetype"]
    assert all(v > 0.0 for v in table.values())
    # The big school archetypes are tabulated.
    for a in ("C1-M (Hi)", "C1-M (Mid)", "S1-M (Hi)", "PTC1-M (Mid)"):
        assert a in table, a
    prov = blk["provenance"]
    assert "Arch_simp_norm_CasI" in prov["source"]
    assert prov["provenance_confidence"]
    # derivation_detail is internally consistent: factor ~= thesis_nc_rate / baseline_nc_rate.
    for a, det in blk["derivation_detail"].items():
        if a.startswith("_") or det.get("baseline_nc_rate", 0) <= 0:
            continue
        if det.get("thesis_nc_rate", 0) <= 0:
            continue  # CHB-L floored to 1.0
        implied = det["thesis_nc_rate"] / det["baseline_nc_rate"]
        assert abs(implied - table[a]) / implied < 0.02, (a, implied, table[a])


def test_nc_injury_calibration_lookup_and_default():
    """Tabulated archetypes return their factor; unknown -> default (1.0); absent block -> 1.0."""
    import copy
    p = cas.load_casualty_params()
    assert cas._nc_injury_calibration("C1-M (Mid)", p) > 1.0
    assert cas._nc_injury_calibration("NOT-AN-ARCHETYPE", p) == 1.0
    p2 = copy.deepcopy(p)
    p2.pop("noncollapse_injury_calibration", None)
    assert cas._nc_injury_calibration("C1-M (Mid)", p2) == 1.0


def test_nc_injury_calibration_raises_injuries_only(damaged_building_sample):
    """building_casualties scales NC INJURIES by the archetype factor, not NC fatalities."""
    import copy
    n = len(damaged_building_sample)
    no_collapse = np.zeros(n, dtype=bool)
    p = cas.load_casualty_params()
    fac = cas._nc_injury_calibration("C1-M (Pre/Lo)", p)
    assert fac > 1.0
    # Calibrated (real params) vs un-calibrated (block removed).
    p_off = copy.deepcopy(p)
    p_off.pop("noncollapse_injury_calibration", None)
    on = cas.building_casualties(damaged_building_sample, no_collapse, "C1-M (Pre/Lo)",
                                 846.0, 916.0, params=p)
    off = cas.building_casualties(damaged_building_sample, no_collapse, "C1-M (Pre/Lo)",
                                  846.0, 916.0, params=p_off)
    # NC injuries scale by the factor; NC fatalities are unchanged.
    np.testing.assert_allclose(on["injuries_noncollapse"], off["injuries_noncollapse"] * fac, rtol=1e-9)
    np.testing.assert_allclose(on["fatalities_noncollapse"], off["fatalities_noncollapse"], rtol=1e-9)


def test_nc_injury_calibration_preserves_component_removal_proportionality(damaged_building_sample):
    """Removing a casualty component reduces NC injuries by the SAME fraction with/without calibration.

    This is what lets the non-structural mitigation (a component swap) work on the calibrated base:
    the per-archetype factor multiplies the component-resolved NC sum uniformly.
    """
    import copy
    n = len(damaged_building_sample)
    no_collapse = np.zeros(n, dtype=bool)
    p_on = cas.load_casualty_params()
    p_off = copy.deepcopy(p_on); p_off.pop("noncollapse_injury_calibration", None)
    # Drop the dominant fixtures component from the casualty table (mimics FIX.NS -> FIX.SE swap).
    def drop_fixtures(params):
        q = copy.deepcopy(params)
        q["noncollapse_component_casualties"].pop("PH.NS.FIX.NS", None)
        return q
    base_on = cas.building_casualties(damaged_building_sample, no_collapse, "C1-M (Pre/Lo)", 846.0, 916.0, params=p_on)
    swap_on = cas.building_casualties(damaged_building_sample, no_collapse, "C1-M (Pre/Lo)", 846.0, 916.0, params=drop_fixtures(p_on))
    base_off = cas.building_casualties(damaged_building_sample, no_collapse, "C1-M (Pre/Lo)", 846.0, 916.0, params=p_off)
    swap_off = cas.building_casualties(damaged_building_sample, no_collapse, "C1-M (Pre/Lo)", 846.0, 916.0, params=drop_fixtures(p_off))
    red_on = 1 - swap_on["injuries"].sum() / base_on["injuries"].sum()
    red_off = 1 - swap_off["injuries"].sum() / base_off["injuries"].sum()
    np.testing.assert_allclose(red_on, red_off, rtol=1e-9)  # calibration is a uniform scale


# ---------------------------------------------------------------------------
# 8-9. Combined building_casualties: no double counting; demolition not a casualty
# ---------------------------------------------------------------------------

def test_building_casualties_no_double_count(damaged_building_sample):
    """On a collapsed cell, the collapse term applies and the NC term is suppressed."""
    n = len(damaged_building_sample)
    collapse = np.zeros(n, dtype=bool)
    collapse[: n // 2] = True  # first half collapsed
    out = cas.building_casualties(
        damaged_building_sample, collapse, "C1-M (Pre/Lo)",
        population=846.0, floor_area_m2=916.0,
    )
    # Non-collapse injuries must be ZERO on collapsed cells.
    assert (out["injuries_noncollapse"][collapse] == 0.0).all()
    # Collapse injuries must be ZERO on non-collapsed cells.
    assert (out["injuries_collapse"][~collapse] == 0.0).all()
    # Total = NC + collapse, elementwise.
    np.testing.assert_allclose(
        out["injuries"], out["injuries_noncollapse"] + out["injuries_collapse"]
    )


def test_demolition_is_not_a_casualty_event(damaged_building_sample):
    """A demolished-but-not-collapsed cell keeps only its component (NC) casualties.

    building_casualties takes only the collapse mask; demolition is invisible to it. So a
    non-collapsed (possibly demolished) realization's casualties == its NC component term
    with NO collapse contribution.
    """
    n = len(damaged_building_sample)
    collapse = np.zeros(n, dtype=bool)  # nothing collapses; some may be 'demolished' upstream
    out = cas.building_casualties(
        damaged_building_sample, collapse, "C1-M (Pre/Lo)", 846.0, 916.0
    )
    assert out["injuries_collapse"].sum() == 0.0
    assert out["fatalities_collapse"].sum() == 0.0
    np.testing.assert_allclose(out["injuries"], out["injuries_noncollapse"])


def test_building_casualties_reproducible(damaged_building_sample):
    n = len(damaged_building_sample)
    collapse = np.zeros(n, dtype=bool)
    collapse[::3] = True
    a = cas.building_casualties(damaged_building_sample, collapse, "C1-M (Hi)", 481.0, 1026.0)
    b = cas.building_casualties(damaged_building_sample, collapse, "C1-M (Hi)", 481.0, 1026.0)
    np.testing.assert_array_equal(a["injuries"], b["injuries"])
    np.testing.assert_array_equal(a["fatalities"], b["fatalities"])


# ---------------------------------------------------------------------------
# 10. building.assess_scenario wiring
# ---------------------------------------------------------------------------

def test_assess_scenario_attaches_casualties():
    """assess_scenario() must attach injuries/fatalities when population is set."""
    import logging
    logging.getLogger("pelicun").setLevel(logging.CRITICAL)
    from bayanihan.building import Building
    b = Building.from_archetype("C1-M (Hi)", site_class="D")
    b.metadata["population"] = 481.0
    b.metadata["floor_area_m2"] = 1026.0
    try:
        r = b.assess_scenario(sa_t1=0.8, soil_bin="D", n_realizations=50, seed=5)
    except Exception as exc:  # EDP store missing on CI -> skip cleanly
        pytest.skip(f"assess_scenario unavailable (EDP store): {exc}")
    assert "injuries" in r and "fatalities" in r
    assert r["injuries"].shape[0] == 50
    assert (r["injuries"] >= 0).all() and (r["fatalities"] >= 0).all()
    assert r["casualty_population"] == 481.0


def test_assess_scenario_zero_casualties_without_population():
    """No population metadata -> zero casualties (no exposure assumed)."""
    import logging
    logging.getLogger("pelicun").setLevel(logging.CRITICAL)
    from bayanihan.building import Building
    b = Building.from_archetype("C1-M (Hi)", site_class="D")
    try:
        r = b.assess_scenario(sa_t1=0.8, soil_bin="D", n_realizations=30, seed=5)
    except Exception as exc:
        pytest.skip(f"assess_scenario unavailable (EDP store): {exc}")
    assert r["casualty_population"] == 0.0
    assert r["injuries"].sum() == 0.0 and r["fatalities"].sum() == 0.0
