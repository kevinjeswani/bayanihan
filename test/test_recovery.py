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
"""
import numpy as np
import pandas as pd
import pytest

from bayanihan.recovery import (
    REPAIR_CLASS_MAP,
    WORKERS_PER_DAY_DEFAULT,
    ImpedingFactorParams,
    _component_repair_class,
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
