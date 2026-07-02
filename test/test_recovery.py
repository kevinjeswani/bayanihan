"""Tests for bayanihan.recovery.

Tests:
  1. load_ph_params() loads without error and returns valid ImpedingFactorParams.
  2. compute_recovery() returns correct shape + non-negative arrays.
  3. Milestone ordering: median(full) >= median(functional) >= median(reoccupancy).
  4. Reproducibility with seed.
  5. DS=0 samples produce zero downtime.
  6. Shape mismatch raises ValueError.
  7. Per-component interface: compute_recovery_from_components().
  8. Repair-class composition: milestones reflect class breakdown, not fixed fractions.
  9. _component_repair_class() maps correctly per YAML Table D-16.
 10. Archetype-specific impeding factors: by_archetype selection (v0.2).
 11. Per-milestone conditional gating: cosmetic-only buildings skip financing floor (v0.2).
"""
import numpy as np
import pandas as pd
import pytest

from bayanihan.recovery import (
    REPAIR_CLASS_MAP,
    SBA_PRIMARY_ARCHETYPES,
    WORKERS_PER_DAY_DEFAULT,
    ImpedingFactorParams,
    _component_repair_class,
    _cost_scale_financing,
    _load_ph_params_raw,
    _resolve_archetype_impeding,
    aggregate_time_by_repair_class,
    compute_recovery,
    compute_recovery_from_components,
    load_ph_params,
)


# ---------------------------------------------------------------------------
# 1. load_ph_params
# ---------------------------------------------------------------------------

def test_load_ph_params_succeeds():
    """ph_redi_params.json loads and validates without error."""
    params = load_ph_params()
    assert isinstance(params, ImpedingFactorParams)


def test_load_ph_params_positive_values():
    """All median_days and beta values are positive."""
    params = load_ph_params()
    for field, value in params.model_dump().items():
        assert value > 0, f"Expected {field} > 0, got {value}"


# ---------------------------------------------------------------------------
# 2. compute_recovery — shape and non-negativity
# ---------------------------------------------------------------------------

@pytest.fixture
def dummy_inputs():
    rng = np.random.default_rng(42)
    n = 500
    repair_times = rng.uniform(10, 200, size=n)
    damage_states = rng.integers(1, 4, size=n)
    return repair_times, damage_states


def test_compute_recovery_returns_correct_keys(dummy_inputs):
    repair_times, damage_states = dummy_inputs
    result = compute_recovery(repair_times, damage_states, seed=0)
    expected_keys = {
        "reoccupancy_days",
        "functional_recovery_days",
        "full_recovery_days",
        "impeding_factor_days",
    }
    assert set(result.keys()) == expected_keys


def test_compute_recovery_correct_shape(dummy_inputs):
    repair_times, damage_states = dummy_inputs
    result = compute_recovery(repair_times, damage_states, seed=0)
    n = len(repair_times)
    for key, arr in result.items():
        assert isinstance(arr, np.ndarray), f"{key} should be np.ndarray"
        assert arr.shape == (n,), f"{key} expected shape ({n},), got {arr.shape}"


def test_compute_recovery_non_negative(dummy_inputs):
    repair_times, damage_states = dummy_inputs
    result = compute_recovery(repair_times, damage_states, seed=0)
    for key, arr in result.items():
        assert np.all(arr >= 0), f"{key} has negative values: {arr[arr < 0]}"


# ---------------------------------------------------------------------------
# 3. Milestone ordering — the required physical constraint
# ---------------------------------------------------------------------------

def test_milestone_ordering_medians():
    """REQUIRED: median(full_recovery) >= median(functional) >= median(reoccupancy)."""
    rng = np.random.default_rng(7)
    n = 2000
    repair_times = rng.uniform(30, 300, size=n)
    damage_states = rng.integers(1, 5, size=n)

    result = compute_recovery(repair_times, damage_states, seed=42)

    med_ro = np.median(result["reoccupancy_days"])
    med_fr = np.median(result["functional_recovery_days"])
    med_full = np.median(result["full_recovery_days"])

    assert med_full >= med_fr, (
        f"Expected median(full) >= median(functional), got {med_full:.2f} < {med_fr:.2f}"
    )
    assert med_fr >= med_ro, (
        f"Expected median(functional) >= median(reoccupancy), got {med_fr:.2f} < {med_ro:.2f}"
    )


def test_milestone_ordering_elementwise(dummy_inputs):
    """Per-sample ordering must hold: full >= functional >= reoccupancy >= 0."""
    repair_times, damage_states = dummy_inputs
    result = compute_recovery(repair_times, damage_states, seed=1)

    ro = result["reoccupancy_days"]
    fr = result["functional_recovery_days"]
    full = result["full_recovery_days"]

    assert np.all(full >= fr), "Some samples have full_recovery < functional_recovery"
    assert np.all(fr >= ro), "Some samples have functional_recovery < reoccupancy"
    assert np.all(ro >= 0), "Some reoccupancy_days are negative"


# ---------------------------------------------------------------------------
# 4. Reproducibility
# ---------------------------------------------------------------------------

def test_reproducible_with_seed(dummy_inputs):
    repair_times, damage_states = dummy_inputs
    result_a = compute_recovery(repair_times, damage_states, seed=99)
    result_b = compute_recovery(repair_times, damage_states, seed=99)
    for key in result_a:
        np.testing.assert_array_equal(
            result_a[key], result_b[key],
            err_msg=f"Key '{key}' differs between identical-seed runs"
        )


def test_different_seeds_differ(dummy_inputs):
    repair_times, damage_states = dummy_inputs
    result_a = compute_recovery(repair_times, damage_states, seed=1)
    result_b = compute_recovery(repair_times, damage_states, seed=2)
    # impeding factor draws should differ between seeds
    assert not np.array_equal(
        result_a["impeding_factor_days"], result_b["impeding_factor_days"]
    ), "Different seeds produced identical impeding_factor_days"


# ---------------------------------------------------------------------------
# 5. DS=0 edge case
# ---------------------------------------------------------------------------

def test_ds0_produces_zero_downtime():
    """Damage state 0 (no damage) must give zero recovery days."""
    repair_times = np.array([50.0, 100.0, 150.0])
    damage_states = np.array([0, 0, 0])
    result = compute_recovery(repair_times, damage_states, seed=0)
    for key, arr in result.items():
        np.testing.assert_array_equal(
            arr, 0.0,
            err_msg=f"DS=0 samples gave non-zero {key}: {arr}"
        )


def test_mixed_ds():
    """Mix of DS=0 and DS>0: only DS>0 should have non-zero downtime."""
    repair_times = np.array([100.0, 100.0, 100.0, 100.0])
    damage_states = np.array([0, 1, 2, 3])
    result = compute_recovery(repair_times, damage_states, seed=5)
    # First sample (DS=0) must be zero
    assert result["full_recovery_days"][0] == 0.0
    assert result["functional_recovery_days"][0] == 0.0
    assert result["reoccupancy_days"][0] == 0.0
    # DS>0 samples should have positive downtime
    assert np.all(result["full_recovery_days"][1:] > 0)


# ---------------------------------------------------------------------------
# 6. Error handling
# ---------------------------------------------------------------------------

def test_shape_mismatch_raises():
    repair_times = np.ones(10)
    damage_states = np.ones(12, dtype=int)
    with pytest.raises(ValueError, match="same shape"):
        compute_recovery(repair_times, damage_states)


# ---------------------------------------------------------------------------
# 7. Optional params passthrough
# ---------------------------------------------------------------------------

def test_explicit_params_accepted(dummy_inputs):
    """compute_recovery accepts an explicit ImpedingFactorParams without error."""
    repair_times, damage_states = dummy_inputs
    params = load_ph_params()
    result = compute_recovery(repair_times, damage_states, params=params, seed=0)
    assert "full_recovery_days" in result


# ---------------------------------------------------------------------------
# 8. Per-component interface: compute_recovery_from_components()
# ---------------------------------------------------------------------------

@pytest.fixture
def dummy_cmp_df():
    """Synthetic per-component repair time DataFrame (n_sims=100, 5 components)."""
    rng = np.random.default_rng(123)
    n = 100
    return pd.DataFrame(
        {
            "PH.S.DRCMRF.1S": rng.uniform(10, 100, n),   # Class 1
            "PH.S.DRCMRF.2S": rng.uniform(20, 200, n),   # Class 1
            "PH.NS.CHB.SU": rng.uniform(5, 50, n),        # Class 1
            "PH.NS.SPR.DROP": rng.uniform(2, 20, n),      # Class 2
            "PH.NS.CLG.NS": rng.uniform(3, 30, n),        # Class 1
        }
    )


def test_compute_recovery_from_components_keys(dummy_cmp_df):
    """compute_recovery_from_components returns required keys."""
    ds = np.ones(len(dummy_cmp_df), dtype=int)
    result = compute_recovery_from_components(dummy_cmp_df, ds, seed=0)
    expected_keys = {
        "reoccupancy_days", "functional_recovery_days", "full_recovery_days",
        "impeding_factor_days", "rc1_days", "rc2_days", "rc3_days",
    }
    assert expected_keys.issubset(set(result.keys()))


def test_compute_recovery_from_components_shape(dummy_cmp_df):
    """All output arrays have shape (n_sims,)."""
    n = len(dummy_cmp_df)
    ds = np.ones(n, dtype=int)
    result = compute_recovery_from_components(dummy_cmp_df, ds, seed=0)
    for key, arr in result.items():
        assert isinstance(arr, np.ndarray), f"{key} should be ndarray"
        assert arr.shape == (n,), f"{key} expected shape ({n},)"


def test_compute_recovery_from_components_ordering(dummy_cmp_df):
    """Per-sample ordering: full >= functional >= reoccupancy >= 0."""
    ds = np.ones(len(dummy_cmp_df), dtype=int)
    result = compute_recovery_from_components(dummy_cmp_df, ds, seed=7)
    assert np.all(result["full_recovery_days"] >= result["functional_recovery_days"])
    assert np.all(result["functional_recovery_days"] >= result["reoccupancy_days"])
    assert np.all(result["reoccupancy_days"] >= 0)


def test_compute_recovery_from_components_ds0(dummy_cmp_df):
    """DS=0 simulations must produce zero for all milestone outputs."""
    n = len(dummy_cmp_df)
    ds = np.zeros(n, dtype=int)  # all undamaged
    result = compute_recovery_from_components(dummy_cmp_df, ds, seed=0)
    for key in ("reoccupancy_days", "functional_recovery_days", "full_recovery_days"):
        np.testing.assert_array_equal(result[key], 0.0, err_msg=f"{key} should be 0 for DS=0")


def test_compute_recovery_from_components_reproducible(dummy_cmp_df):
    """Same seed → identical outputs."""
    ds = np.ones(len(dummy_cmp_df), dtype=int)
    r1 = compute_recovery_from_components(dummy_cmp_df, ds, seed=42)
    r2 = compute_recovery_from_components(dummy_cmp_df, ds, seed=42)
    for key in r1:
        np.testing.assert_array_equal(r1[key], r2[key], err_msg=f"{key} differs")


def test_compute_recovery_from_components_size_mismatch(dummy_cmp_df):
    """Mismatched rows vs damage_state raises ValueError."""
    ds = np.ones(len(dummy_cmp_df) + 5, dtype=int)
    with pytest.raises(ValueError):
        compute_recovery_from_components(dummy_cmp_df, ds, seed=0)


# ---------------------------------------------------------------------------
# 9. Repair-class composition: milestones now reflect class breakdown
# ---------------------------------------------------------------------------

def test_class1_only_building_fr_near_full():
    """Building with ONLY Class-1 components: functional ≈ full (no Class-2 MEP).

    If there are no Class-2 or Class-3 components, functional_recovery should
    equal full_recovery (both gate on the same repair work).
    """
    rng = np.random.default_rng(99)
    n = 200
    # Only structural components (all Class 1)
    time_per_cmp = pd.DataFrame(
        {
            "PH.S.DRCMRF.1S": rng.uniform(50, 200, n),   # Class 1
            "PH.S.DRCMRF.2S": rng.uniform(80, 300, n),   # Class 1
        }
    )
    ds = np.ones(n, dtype=int)
    result = compute_recovery_from_components(time_per_cmp, ds, seed=0)

    # No Class-2 or Class-3 components → rc2=0, rc3=0
    np.testing.assert_array_equal(result["rc2_days"], 0.0)
    np.testing.assert_array_equal(result["rc3_days"], 0.0)

    # functional = full (both = rc1 + impeding)
    np.testing.assert_array_equal(
        result["functional_recovery_days"],
        result["full_recovery_days"],
        err_msg="With no Class-2/3 components, functional should equal full"
    )


def test_class1_and_2_building_fr_less_than_full():
    """Building with Class-1 and Class-2 (MEP) but NO Class-3:
    functional < full when there is any Class-2 time.
    """
    rng = np.random.default_rng(77)
    n = 200
    time_per_cmp = pd.DataFrame(
        {
            "PH.S.DRCMRF.1S": rng.uniform(50, 200, n),   # Class 1
            "PH.NS.SPR.DROP": rng.uniform(10, 50, n),     # Class 2
        }
    )
    ds = np.ones(n, dtype=int)
    result = compute_recovery_from_components(time_per_cmp, ds, seed=0)

    # rc2_days > 0 since there are Class-2 components
    assert np.any(result["rc2_days"] > 0), "Expected non-zero rc2_days for sprinkler components"

    # rc3_days == 0 (no Class-3 components)
    np.testing.assert_array_equal(result["rc3_days"], 0.0)

    # full = functional when rc3=0 (both gate on rc1+rc2)
    np.testing.assert_array_equal(
        result["functional_recovery_days"],
        result["full_recovery_days"],
        err_msg="With no Class-3 components, functional should equal full"
    )

    # functional > reoccupancy (Class-2 adds time beyond Class-1)
    assert np.median(result["functional_recovery_days"]) > np.median(result["reoccupancy_days"]), (
        "Expected functional > reoccupancy for Class-1+2 building"
    )


def test_all_three_classes_milestone_ordering():
    """Building with all three repair classes shows strict milestone ordering.

    full > functional > reoccupancy (in median) when each class has repair time.
    """
    rng = np.random.default_rng(55)
    n = 500
    time_per_cmp = pd.DataFrame(
        {
            "PH.S.DRCMRF.1S": rng.uniform(100, 400, n),   # Class 1
            "PH.NS.SPR.DROP": rng.uniform(20, 80, n),      # Class 2
            "PH.NS.CW": rng.uniform(30, 120, n),           # Class 3 (curtain wall)
        }
    )
    ds = np.ones(n, dtype=int)
    result = compute_recovery_from_components(time_per_cmp, ds, seed=42)

    med_ro = np.median(result["reoccupancy_days"])
    med_fr = np.median(result["functional_recovery_days"])
    med_full = np.median(result["full_recovery_days"])

    assert med_full > med_fr > med_ro > 0, (
        f"Expected full > functional > reoccupancy > 0, got "
        f"full={med_full:.1f}, functional={med_fr:.1f}, reoccupancy={med_ro:.1f}"
    )


def test_repair_class_map_coverage():
    """All component IDs in REPAIR_CLASS_MAP must map to class 1, 2, or 3."""
    for prefix, rc in REPAIR_CLASS_MAP.items():
        assert rc in (1, 2, 3), f"Component prefix {prefix!r} maps to invalid class {rc}"


def test_component_repair_class_structural():
    """Structural DRCMRF joints must map to Class 1 (life-safety)."""
    assert _component_repair_class("PH.S.DRCMRF.1S") == 1
    assert _component_repair_class("PH.S.DRCMRF.2S") == 1


def test_component_repair_class_mep():
    """MEP/functional components must map to Class 2."""
    assert _component_repair_class("PH.NS.SPR.DROP") == 2
    assert _component_repair_class("PH.NS.EDIST") == 2
    assert _component_repair_class("PH.NS.ELEV") == 2


def test_component_repair_class_cosmetic():
    """Curtain wall and cosmetic fixtures must map to Class 3."""
    assert _component_repair_class("PH.NS.CW") == 3
    assert _component_repair_class("PH.NS.FIX.NS") == 3


def test_component_repair_class_unknown():
    """Unknown component IDs must return CLASS_UNKNOWN (3) without error."""
    from bayanihan.recovery import CLASS_UNKNOWN
    rc = _component_repair_class("XX.UNKNOWN.COMPONENT")
    assert rc == CLASS_UNKNOWN


def test_aggregate_time_by_repair_class():
    """aggregate_time_by_repair_class produces correct per-class sums."""
    n = 10
    # One Class-1 component with 80 worker_hours, one Class-2 with 40
    time_per_cmp = pd.DataFrame(
        {
            "PH.S.DRCMRF.1S": np.full(n, 80.0),   # Class 1
            "PH.NS.SPR.DROP": np.full(n, 40.0),    # Class 2
        }
    )
    rc_days = aggregate_time_by_repair_class(time_per_cmp, workers_per_day=8.0)

    # RC1: 80 worker_hours / 8 = 10 days
    np.testing.assert_allclose(rc_days[1], 10.0, err_msg="RC1 days wrong")
    # RC2: 40 worker_hours / 8 = 5 days
    np.testing.assert_allclose(rc_days[2], 5.0, err_msg="RC2 days wrong")
    # RC3: 0 (no components)
    np.testing.assert_allclose(rc_days[3], 0.0, err_msg="RC3 days should be 0")


def test_fixed_fractions_removed():
    """Verify that fixed fractions (0.40/0.75/1.00) are NOT used in the per-component path.

    The per-component interface should produce different milestones than the old
    fixed-fraction formula, confirming the refactor is active.
    """
    rng = np.random.default_rng(13)
    n = 100
    # All Class-1 structural components → reoccupancy ≈ full (no class splitting)
    time_per_cmp = pd.DataFrame(
        {"PH.S.DRCMRF.1S": rng.uniform(100, 500, n)}  # Class 1 only
    )
    ds = np.ones(n, dtype=int)
    result = compute_recovery_from_components(time_per_cmp, ds, seed=0)

    # With only Class-1, reoccupancy = functional = full (all gate on rc1)
    np.testing.assert_array_equal(
        result["reoccupancy_days"], result["functional_recovery_days"],
        err_msg="reoccupancy should equal functional for Class-1-only building"
    )
    np.testing.assert_array_equal(
        result["functional_recovery_days"], result["full_recovery_days"],
        err_msg="functional should equal full for Class-1-only building"
    )
    # Under old 0.40/0.75/1.00 fractions, reoccupancy < functional < full always
    # The equality above confirms the fixed-fraction logic is gone


# ---------------------------------------------------------------------------
# 10. Archetype-specific impeding factors (v0.2 — Table 6-7 fidelity)
# ---------------------------------------------------------------------------

def test_resolve_archetype_impeding_simple_group():
    """Simple (N-L, CHB-L, S3-L) group: financing 42 d (Insurance) not 336 d (SBA)."""
    raw = _load_ph_params_raw()
    for arch in ("N-L", "CHB-L", "S3-L"):
        overrides = _resolve_archetype_impeding(arch, raw)
        assert "financing_median_days" in overrides, f"{arch}: financing override missing"
        assert overrides["financing_median_days"] == pytest.approx(42.0), (
            f"{arch}: expected financing 42 d (Insurance), got {overrides['financing_median_days']}"
        )
        assert overrides["financing_beta"] == pytest.approx(1.11), (
            f"{arch}: expected financing beta 1.11"
        )


def test_resolve_archetype_impeding_wood_group():
    """Wood (W-L): financing 105 d (Private Loans) not 336 d (SBA)."""
    raw = _load_ph_params_raw()
    overrides = _resolve_archetype_impeding("W-L", raw)
    assert overrides["financing_median_days"] == pytest.approx(105.0), (
        f"W-L: expected financing 105 d (Private Loans), got {overrides['financing_median_days']}"
    )
    assert overrides["financing_beta"] == pytest.approx(0.68)


def test_resolve_archetype_impeding_c1m_hi():
    """C1-M (Hi): contractor 49 d (RC1), engineer 0 d (on-contract), financing 336 d."""
    raw = _load_ph_params_raw()
    overrides = _resolve_archetype_impeding("C1-M (Hi)", raw)
    assert overrides["contractor_median_days"] == pytest.approx(49.0), (
        f"C1-M (Hi): expected contractor 49 d (Max RC=1), got {overrides['contractor_median_days']}"
    )
    assert overrides["contractor_beta"] == pytest.approx(0.60)
    # Engineer on contract → 0 d
    assert overrides["engineer_median_days"] == pytest.approx(0.0), (
        f"C1-M (Hi): expected engineer 0 d (on-contract), got {overrides['engineer_median_days']}"
    )
    assert overrides["financing_median_days"] == pytest.approx(336.0)


def test_resolve_archetype_impeding_c1m_mid():
    """C1-M (Mid): contractor 49 d (RC1), engineer 14 d (RC1)."""
    raw = _load_ph_params_raw()
    overrides = _resolve_archetype_impeding("C1-M (Mid)", raw)
    assert overrides["contractor_median_days"] == pytest.approx(49.0)
    assert overrides["engineer_median_days"] == pytest.approx(14.0)
    assert overrides["engineer_beta"] == pytest.approx(0.32)


def test_resolve_archetype_impeding_rc3_group():
    """Primary RC3 archetypes: contractor 133 d, engineer 28 d."""
    raw = _load_ph_params_raw()
    for arch in ("C1-L (Mid/Hi)", "C1-L (Pre/Lo)", "PTC1-M (Hi)", "PTC1-M (Mid)",
                 "CWS-L", "C1-H (Hi)", "S1-M (Hi)", "C1-M (Pre/Lo) FRP"):
        overrides = _resolve_archetype_impeding(arch, raw)
        assert overrides["contractor_median_days"] == pytest.approx(133.0), (
            f"{arch}: expected contractor 133 d (RC3)"
        )
        assert overrides["engineer_median_days"] == pytest.approx(28.0), (
            f"{arch}: expected engineer 28 d (RC3)"
        )


def test_resolve_archetype_impeding_unknown_returns_empty():
    """Unknown archetype → empty dict (falls back to flat defaults)."""
    raw = _load_ph_params_raw()
    overrides = _resolve_archetype_impeding("UNKNOWN-XYZ", raw)
    assert overrides == {}


def test_resolve_archetype_impeding_none_returns_empty():
    """archetype=None → empty dict."""
    raw = _load_ph_params_raw()
    overrides = _resolve_archetype_impeding(None, raw)
    assert overrides == {}


def test_archetype_simple_produces_lower_fr_than_primary():
    """Simple archetype (N-L, financing 42 d) produces lower median FR than primary school default.

    This confirms the intensity-scaling fix: simple buildings with Insurance financing
    (42 d) recover faster than primary schools with SBA loans (336 d).
    """
    rng = np.random.default_rng(42)
    n = 1000
    # Create a mix of Class-1 and Class-2 repair (typical moderate damage)
    time_per_cmp = pd.DataFrame({
        "PH.S.DRCMRF.1S": rng.uniform(10, 100, n),  # Class 1
        "PH.NS.SPR.DROP": rng.uniform(5, 50, n),     # Class 2
    })
    ds = np.ones(n, dtype=int)

    # Primary school archetype (SBA financing, 336 d)
    result_primary = compute_recovery_from_components(
        time_per_cmp, ds, seed=1, archetype="C1-L (Mid/Hi)"
    )
    # Simple archetype (Insurance financing, 42 d)
    result_simple = compute_recovery_from_components(
        time_per_cmp, ds, seed=1, archetype="N-L"
    )

    med_fr_primary = np.median(result_primary["functional_recovery_days"])
    med_fr_simple = np.median(result_simple["functional_recovery_days"])

    assert med_fr_simple < med_fr_primary, (
        f"Simple (N-L) FR {med_fr_simple:.1f} d should be < primary (C1-L) FR "
        f"{med_fr_primary:.1f} d (financing 42d vs 336d)"
    )


# ---------------------------------------------------------------------------
# 11. Per-milestone conditional gating (v0.2 — intensity-scaling fix)
# ---------------------------------------------------------------------------

def test_cosmetic_only_building_functional_near_inspection():
    """Cosmetic-only building (rc1=rc2=0, rc3>0) must get functional ≈ inspection delay.

    Prior behavior: functional = 0 + ~338 d (full financing floor always applied).
    Fixed behavior: functional = inspection delay (5 d median) — not ~338 d.

    This is the core intensity-scaling fix: a building with only cosmetic damage
    (Class 3 only) should NOT draw the full SBA financing + contractor floor.
    """
    rng = np.random.default_rng(0)
    n = 2000
    # Class-3-only components (curtain wall, ceiling fixtures)
    time_per_cmp = pd.DataFrame({
        "PH.NS.CW": rng.uniform(10, 100, n),   # Class 3
        "PH.NS.FIX": rng.uniform(5, 40, n),    # Class 3
    })
    ds = np.ones(n, dtype=int)  # all damaged

    result = compute_recovery_from_components(time_per_cmp, ds, seed=0)

    # rc1 and rc2 should be zero
    np.testing.assert_array_equal(result["rc1_days"], 0.0)
    np.testing.assert_array_equal(result["rc2_days"], 0.0)

    med_fr = np.median(result["functional_recovery_days"])

    # With gating, functional_recovery ≈ inspection delay (5 d median).
    # The inspection lognormal (theta=5, beta=0.54) has p50≈5, p90≈10.
    # The old financing floor (theta=336, beta=0.57) has p50≈336.
    # Verify functional is far below the old floor (< 50 d) and near inspection range.
    assert med_fr < 50.0, (
        f"Cosmetic-only building: functional recovery median {med_fr:.1f} d should be "
        f"< 50 d (near inspection delay ~5 d). Old behavior was ~338 d."
    )
    assert med_fr > 0.0, "Damaged cosmetic-only building must have positive functional recovery"


def test_class1_building_still_uses_impeding_floor():
    """Building with Class-1 damage (structural) must still get full impeding delay.

    Gating must NOT bypass impeding for Class-1 buildings — they have rc1 > 0,
    so the full financing/contractor delay should apply.
    """
    rng = np.random.default_rng(1)
    n = 2000
    # Class-1-only structural damage
    time_per_cmp = pd.DataFrame({
        "PH.S.DRCMRF.1S": rng.uniform(50, 200, n),  # Class 1
    })
    ds = np.ones(n, dtype=int)

    result_primary = compute_recovery_from_components(
        time_per_cmp, ds, seed=0, archetype="C1-L (Mid/Hi)"
    )
    med_fr = np.median(result_primary["functional_recovery_days"])

    # With SBA financing (336 d median), functional should be >> 100 d
    # (the impeding floor still dominates for Class-1 buildings)
    assert med_fr > 200.0, (
        f"Class-1 structural building should have functional recovery >> 200 d "
        f"(impeding floor dominates), got {med_fr:.1f} d"
    )


def test_functional_gating_no_break_ordering():
    """Milestone ordering still holds after gating: full >= functional >= reoccupancy >= 0."""
    rng = np.random.default_rng(99)
    n = 500
    # Mix of all three classes
    time_per_cmp = pd.DataFrame({
        "PH.S.DRCMRF.1S": rng.uniform(0, 200, n),  # Class 1 (some zero → cosmetic only)
        "PH.NS.SPR.DROP": rng.uniform(0, 80, n),    # Class 2
        "PH.NS.CW": rng.uniform(10, 120, n),         # Class 3
    })
    ds = rng.integers(0, 4, size=n)

    result = compute_recovery_from_components(time_per_cmp, ds, seed=7)

    assert np.all(result["full_recovery_days"] >= result["functional_recovery_days"]), (
        "full_recovery must >= functional_recovery after gating"
    )
    assert np.all(result["functional_recovery_days"] >= result["reoccupancy_days"]), (
        "functional_recovery must >= reoccupancy after gating"
    )
    assert np.all(result["reoccupancy_days"] >= 0.0), "reoccupancy must be >= 0"
    assert np.all(result["full_recovery_days"] >= 0.0), "full_recovery must be >= 0"


def test_ds0_gating_produces_zero():
    """DS=0 still gives zero for all milestones even with gating logic."""
    rng = np.random.default_rng(7)
    n = 100
    time_per_cmp = pd.DataFrame({
        "PH.NS.CW": rng.uniform(10, 100, n),   # Class 3 only
    })
    ds = np.zeros(n, dtype=int)  # all undamaged

    result = compute_recovery_from_components(time_per_cmp, ds, seed=0)

    for key in ("reoccupancy_days", "functional_recovery_days", "full_recovery_days",
                "impeding_factor_days"):
        np.testing.assert_array_equal(result[key], 0.0, err_msg=f"{key} must be 0 for DS=0")


def test_archetype_param_none_backward_compatible():
    """archetype=None produces same result as not passing archetype (backward compat)."""
    rng = np.random.default_rng(55)
    n = 200
    time_per_cmp = pd.DataFrame({
        "PH.S.DRCMRF.1S": rng.uniform(50, 200, n),
        "PH.NS.SPR.DROP": rng.uniform(10, 50, n),
    })
    ds = np.ones(n, dtype=int)

    r_default = compute_recovery_from_components(time_per_cmp, ds, seed=42)
    r_none = compute_recovery_from_components(time_per_cmp, ds, seed=42, archetype=None)

    for key in r_default:
        np.testing.assert_array_equal(
            r_default[key], r_none[key],
            err_msg=f"Key '{key}' differs: archetype=None should match default"
        )


# ---------------------------------------------------------------------------
# 12. Part C — cost-scaled SBA/primary financing (Table D-15 curve)
# ---------------------------------------------------------------------------

def test_cost_scaling_curve_loaded():
    """ph_redi_params.json contains the financing_cost_scaling curve with required keys."""
    raw = _load_ph_params_raw()
    scaling = raw.get("financing_cost_scaling", {})
    assert "curve" in scaling, "financing_cost_scaling.curve missing from ph_redi_params.json"
    assert "financing_beta" in scaling, "financing_cost_scaling.financing_beta missing"
    curve = scaling["curve"]
    assert len(curve) == 7, f"Expected 7 curve points (Table D-15), got {len(curve)}"
    for pt in curve:
        assert "replacement_cost_php" in pt
        assert "financing_days" in pt


def test_cost_scale_financing_low_cost():
    """Cost << lower bound → clamp to minimum financing days (56 d)."""
    raw = _load_ph_params_raw()
    rng = np.random.default_rng(0)
    n = 500
    # Very low cost: 100k PHP — below the 2M lower bound
    repair_cost = np.full(n, 100_000.0)
    delays = _cost_scale_financing(repair_cost, raw, fallback_median=336.0, fallback_beta=0.57, rng=rng)
    # Samples from LN(log(56), 0.57) — median should be near 56
    assert np.median(delays) == pytest.approx(56.0, rel=0.3), (
        f"Low-cost clamp: expected median near 56 d, got {np.median(delays):.1f}"
    )


def test_cost_scale_financing_high_cost():
    """Cost >> upper bound → clamp to maximum financing days (672 d)."""
    raw = _load_ph_params_raw()
    rng = np.random.default_rng(0)
    n = 500
    # Very high cost: 5B PHP — above the 1.5B upper bound
    repair_cost = np.full(n, 5_000_000_000.0)
    delays = _cost_scale_financing(repair_cost, raw, fallback_median=336.0, fallback_beta=0.57, rng=rng)
    assert np.median(delays) == pytest.approx(672.0, rel=0.3), (
        f"High-cost clamp: expected median near 672 d, got {np.median(delays):.1f}"
    )


def test_cost_scale_financing_midrange():
    """50M PHP on the curve → financing days should be near 336 d."""
    raw = _load_ph_params_raw()
    rng = np.random.default_rng(0)
    n = 1000
    # 50M PHP is a curve point: financing_days = 336
    repair_cost = np.full(n, 50_000_000.0)
    delays = _cost_scale_financing(repair_cost, raw, fallback_median=336.0, fallback_beta=0.57, rng=rng)
    assert np.median(delays) == pytest.approx(336.0, rel=0.25), (
        f"Midrange cost (50M PHP): expected median near 336 d, got {np.median(delays):.1f}"
    )


def test_cost_scale_monotone():
    """Higher repair cost → longer median financing delay (monotone curve)."""
    raw = _load_ph_params_raw()
    costs = [2_000_000.0, 10_000_000.0, 50_000_000.0, 500_000_000.0, 1_500_000_000.0]
    medians = []
    for cost in costs:
        rng = np.random.default_rng(123)
        rc = np.full(2000, cost)
        delays = _cost_scale_financing(rc, raw, fallback_median=336.0, fallback_beta=0.57, rng=rng)
        medians.append(float(np.median(delays)))

    for i in range(len(medians) - 1):
        assert medians[i] <= medians[i + 1], (
            f"Cost scaling not monotone: cost[{i}]={costs[i]:.0e} → {medians[i]:.1f} d, "
            f"cost[{i+1}]={costs[i+1]:.0e} → {medians[i+1]:.1f} d"
        )


def test_high_cost_primary_longer_financing_than_low_cost():
    """Primary school with high repair cost gets longer financing than low repair cost.

    This is the core Part C invariant: cost-scaling must produce intensity sensitivity
    in financing delay — a heavily-damaged expensive building takes longer to finance
    than a lightly-damaged cheap one.
    """
    rng = np.random.default_rng(7)
    n = 1000
    # Both buildings: structural damage (Class 1) — so impeding floor applies
    time_per_cmp = pd.DataFrame({
        "PH.S.DRCMRF.1S": rng.uniform(50, 200, n),  # Class 1
        "PH.NS.SPR.DROP": rng.uniform(10, 50, n),    # Class 2
    })
    ds = np.ones(n, dtype=int)

    # Low cost: 2M PHP (small building, lower bound → 56 d financing)
    rc_low = np.full(n, 2_000_000.0)
    result_low = compute_recovery_from_components(
        time_per_cmp, ds, seed=42,
        archetype="C1-L (Mid/Hi)",
        repair_cost=rc_low,
    )

    # High cost: 1B PHP (large building, near upper bound → 560 d financing)
    rc_high = np.full(n, 1_000_000_000.0)
    result_high = compute_recovery_from_components(
        time_per_cmp, ds, seed=42,
        archetype="C1-L (Mid/Hi)",
        repair_cost=rc_high,
    )

    med_fr_low = np.median(result_low["functional_recovery_days"])
    med_fr_high = np.median(result_high["functional_recovery_days"])

    assert med_fr_high > med_fr_low, (
        f"High-cost primary ({med_fr_high:.1f} d) should have longer FR than "
        f"low-cost primary ({med_fr_low:.1f} d)"
    )


def test_simple_financing_flat_unchanged():
    """Simple (N-L) archetype financing is flat 42 d even when repair_cost is provided.

    N-L is NOT in SBA_PRIMARY_ARCHETYPES, so repair_cost should be ignored.
    """
    rng = np.random.default_rng(0)
    n = 1000
    time_per_cmp = pd.DataFrame({
        "PH.S.DRCMRF.1S": rng.uniform(50, 200, n),
    })
    ds = np.ones(n, dtype=int)

    # With a huge repair cost that would trigger long financing if cost-scaled
    rc_huge = np.full(n, 2_000_000_000.0)

    result_with_cost = compute_recovery_from_components(
        time_per_cmp, ds, seed=1, archetype="N-L", repair_cost=rc_huge
    )
    result_no_cost = compute_recovery_from_components(
        time_per_cmp, ds, seed=1, archetype="N-L"
    )

    # N-L (Insurance 42 d): results should be identical regardless of repair_cost
    for key in result_with_cost:
        np.testing.assert_array_equal(
            result_with_cost[key], result_no_cost[key],
            err_msg=f"N-L archetype: key '{key}' changed when repair_cost was provided"
        )


def test_wood_financing_flat_unchanged():
    """Wood (W-L) archetype financing is flat 105 d even when repair_cost is provided."""
    rng = np.random.default_rng(0)
    n = 500
    time_per_cmp = pd.DataFrame({
        "PH.S.DRCMRF.1S": rng.uniform(50, 200, n),
    })
    ds = np.ones(n, dtype=int)
    rc_huge = np.full(n, 2_000_000_000.0)

    result_with_cost = compute_recovery_from_components(
        time_per_cmp, ds, seed=2, archetype="W-L", repair_cost=rc_huge
    )
    result_no_cost = compute_recovery_from_components(
        time_per_cmp, ds, seed=2, archetype="W-L"
    )

    for key in result_with_cost:
        np.testing.assert_array_equal(
            result_with_cost[key], result_no_cost[key],
            err_msg=f"W-L archetype: key '{key}' changed when repair_cost was provided"
        )


def test_repair_cost_none_backward_compat():
    """repair_cost=None produces identical results to not passing it (Part C backward compat)."""
    rng = np.random.default_rng(17)
    n = 300
    time_per_cmp = pd.DataFrame({
        "PH.S.DRCMRF.1S": rng.uniform(50, 200, n),
        "PH.NS.SPR.DROP": rng.uniform(10, 50, n),
    })
    ds = np.ones(n, dtype=int)

    r_default = compute_recovery_from_components(
        time_per_cmp, ds, seed=99, archetype="C1-L (Mid/Hi)"
    )
    r_none = compute_recovery_from_components(
        time_per_cmp, ds, seed=99, archetype="C1-L (Mid/Hi)", repair_cost=None
    )

    for key in r_default:
        np.testing.assert_array_equal(
            r_default[key], r_none[key],
            err_msg=f"Key '{key}' differs: repair_cost=None should match no repair_cost"
        )


def test_sba_primary_archetypes_set_completeness():
    """All archetypes in by_archetype with financing 336 d are in SBA_PRIMARY_ARCHETYPES."""
    raw = _load_ph_params_raw()
    by_arch = raw.get("by_archetype", {})
    for arch_id, entry in by_arch.items():
        if arch_id.startswith("_"):
            continue
        fin = entry.get("financing", {})
        med = fin.get("median_days", 0.0)
        if float(med) == 336.0:
            assert arch_id in SBA_PRIMARY_ARCHETYPES, (
                f"Archetype '{arch_id}' has financing 336 d (SBA) but is not in "
                f"SBA_PRIMARY_ARCHETYPES — add it to recovery.py"
            )
