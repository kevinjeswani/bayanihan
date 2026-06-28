"""Tests for bayanihan.building — Building.from_archetype + assess()."""
from __future__ import annotations

import numpy as np
import pytest

from bayanihan.archetypes import ARCHETYPE_IDS
from bayanihan.building import (
    Building,
    _build_cmp_marginals,
    _ns_mitigation_map,
    demolition_probability,
    sample_demolition,
)

# ---------------------------------------------------------------------------
# Fixtures (supplement conftest.py's dummy_edp_samples)
# ---------------------------------------------------------------------------

@pytest.fixture
def representative_archetype_id() -> str:
    """Return the representative archetype for end-to-end pipeline tests."""
    # C1-M (Hi) is the primary NRHA archetype with full fragility + consequence data
    return "C1-M (Hi)"


# ---------------------------------------------------------------------------
# Building.from_archetype()
# ---------------------------------------------------------------------------

def test_from_archetype_returns_building(representative_archetype_id: str):
    """from_archetype() must return a Building instance."""
    b = Building.from_archetype(representative_archetype_id)
    assert isinstance(b, Building)


def test_from_archetype_unknown_raises():
    """from_archetype() must raise ValueError for unknown ID."""
    with pytest.raises(ValueError, match="Unknown archetype"):
        Building.from_archetype("DOES_NOT_EXIST")


def test_from_archetype_sets_archetype_field(representative_archetype_id: str):
    """from_archetype() must set building.archetype to the requested ID."""
    b = Building.from_archetype(representative_archetype_id)
    assert b.archetype == representative_archetype_id


def test_from_archetype_overrides(representative_archetype_id: str):
    """from_archetype() must apply keyword overrides correctly."""
    b = Building.from_archetype(
        representative_archetype_id, lat=14.0, lon=120.0, site_class="C"
    )
    assert b.lat == 14.0
    assert b.lon == 120.0
    assert b.site_class == "C"


def test_from_archetype_stories_positive(representative_archetype_id: str):
    """stories must be a positive integer for all archetypes."""
    b = Building.from_archetype(representative_archetype_id)
    assert isinstance(b.stories, int)
    assert b.stories >= 1


# ---------------------------------------------------------------------------
# assess() — return structure
# ---------------------------------------------------------------------------

def test_assess_returns_dict(representative_archetype_id: str, dummy_edp_samples):
    """assess() must return a dict."""
    b = Building.from_archetype(representative_archetype_id)
    result = b.assess(dummy_edp_samples, seed=0)
    assert isinstance(result, dict)


def test_assess_required_keys(representative_archetype_id: str, dummy_edp_samples):
    """assess() result must contain all required keys."""
    b = Building.from_archetype(representative_archetype_id)
    result = b.assess(dummy_edp_samples, seed=0)
    required_keys = {
        "damage",
        "loss_ratio",
        "repair_cost",
        "repair_time",
        "reoccupancy_days",
        "functional_recovery_days",
        "full_recovery_days",
    }
    assert required_keys.issubset(set(result.keys())), (
        f"Missing keys: {required_keys - set(result.keys())}"
    )


def test_assess_damage_is_dict(representative_archetype_id: str, dummy_edp_samples):
    """assess()['damage'] must be a dict."""
    b = Building.from_archetype(representative_archetype_id)
    result = b.assess(dummy_edp_samples, seed=0)
    assert isinstance(result["damage"], dict)


def test_assess_repair_cost_array_shape(representative_archetype_id: str, dummy_edp_samples):
    """assess()['repair_cost'] must be a 1D array with length = n_simulations."""
    n_sims = dummy_edp_samples.shape[0]
    b = Building.from_archetype(representative_archetype_id)
    result = b.assess(dummy_edp_samples, seed=0)
    assert isinstance(result["repair_cost"], np.ndarray)
    assert result["repair_cost"].shape == (n_sims,)


def test_assess_repair_time_array_shape(representative_archetype_id: str, dummy_edp_samples):
    """assess()['repair_time'] must be a 1D array with length = n_simulations."""
    n_sims = dummy_edp_samples.shape[0]
    b = Building.from_archetype(representative_archetype_id)
    result = b.assess(dummy_edp_samples, seed=0)
    assert isinstance(result["repair_time"], np.ndarray)
    assert result["repair_time"].shape == (n_sims,)


def test_assess_loss_ratio_array_shape(representative_archetype_id: str, dummy_edp_samples):
    """assess()['loss_ratio'] must be a 1D array with length = n_simulations."""
    n_sims = dummy_edp_samples.shape[0]
    b = Building.from_archetype(representative_archetype_id)
    result = b.assess(dummy_edp_samples, seed=0)
    assert isinstance(result["loss_ratio"], np.ndarray)
    assert result["loss_ratio"].shape == (n_sims,)


def test_assess_no_nan_in_repair_cost(representative_archetype_id: str, dummy_edp_samples):
    """repair_cost must not contain NaN."""
    b = Building.from_archetype(representative_archetype_id)
    result = b.assess(dummy_edp_samples, seed=0)
    assert not np.any(np.isnan(result["repair_cost"])), "NaN found in repair_cost"


def test_assess_no_nan_in_repair_time(representative_archetype_id: str, dummy_edp_samples):
    """repair_time must not contain NaN."""
    b = Building.from_archetype(representative_archetype_id)
    result = b.assess(dummy_edp_samples, seed=0)
    assert not np.any(np.isnan(result["repair_time"])), "NaN found in repair_time"


def test_assess_repair_cost_nonnegative(representative_archetype_id: str, dummy_edp_samples):
    """repair_cost values must be non-negative."""
    b = Building.from_archetype(representative_archetype_id)
    result = b.assess(dummy_edp_samples, seed=0)
    assert np.all(result["repair_cost"] >= 0), "Negative repair_cost found"


def test_assess_repair_time_nonnegative(representative_archetype_id: str, dummy_edp_samples):
    """repair_time values must be non-negative."""
    b = Building.from_archetype(representative_archetype_id)
    result = b.assess(dummy_edp_samples, seed=0)
    assert np.all(result["repair_time"] >= 0), "Negative repair_time found"


def test_assess_nonzero_loss_on_damaged_building(dummy_edp_samples):
    """At typical drift levels (median ~3%), most simulations should have non-zero loss."""
    # The dummy_edp_samples fixture has PID median ~3% which should cause damage
    # to CHB infill and structural components
    b = Building.from_archetype("C1-M (Hi)")
    result = b.assess(dummy_edp_samples, seed=42)
    # At 3% drift, CHB infill and DRCMRF joints should show damage and non-zero repair cost
    n_nonzero = (result["repair_cost"] > 0).sum()
    assert n_nonzero > 0, (
        "Expected at least some simulations with non-zero repair cost "
        "at ~3% drift level, got 0"
    )


def test_assess_recovery_keys_present(representative_archetype_id: str, dummy_edp_samples):
    """Recovery keys must be present and non-None (per-component path active)."""
    b = Building.from_archetype(representative_archetype_id)
    result = b.assess(dummy_edp_samples, seed=0)
    assert "reoccupancy_days" in result
    assert "functional_recovery_days" in result
    assert "full_recovery_days" in result
    # After refactor, recovery is always computed (not a stub)
    assert result["reoccupancy_days"] is not None, "reoccupancy_days should not be None"
    assert result["functional_recovery_days"] is not None, "functional_recovery_days should not be None"
    assert result["full_recovery_days"] is not None, "full_recovery_days should not be None"


def test_assess_recovery_milestone_ordering(representative_archetype_id: str, dummy_edp_samples):
    """Recovery milestone ordering: median(full) >= median(functional) >= median(reoccupancy)."""
    b = Building.from_archetype(representative_archetype_id)
    result = b.assess(dummy_edp_samples, seed=42)

    ro = result["reoccupancy_days"]
    fr = result["functional_recovery_days"]
    full = result["full_recovery_days"]

    # Skip if all zeros (no damage scenario)
    if np.all(full == 0):
        pytest.skip("All recovery times are zero — no damage in this run")

    assert np.all(full >= fr), "Some full_recovery < functional_recovery"
    assert np.all(fr >= ro), "Some functional_recovery < reoccupancy"
    assert np.all(ro >= 0), "Negative reoccupancy_days"


def test_assess_recovery_arrays_shape(representative_archetype_id: str, dummy_edp_samples):
    """Recovery arrays must be 1D with length = n_simulations."""
    n_sims = dummy_edp_samples.shape[0]
    b = Building.from_archetype(representative_archetype_id)
    result = b.assess(dummy_edp_samples, seed=0)
    for key in ("reoccupancy_days", "functional_recovery_days", "full_recovery_days"):
        arr = result[key]
        assert isinstance(arr, np.ndarray), f"{key} must be np.ndarray"
        assert arr.shape == (n_sims,), f"{key} expected shape ({n_sims},), got {arr.shape}"


def test_assess_seed_reproducibility(representative_archetype_id: str, dummy_edp_samples):
    """assess() with the same seed must produce identical results."""
    b = Building.from_archetype(representative_archetype_id)
    r1 = b.assess(dummy_edp_samples, seed=99)
    r2 = b.assess(dummy_edp_samples, seed=99)
    np.testing.assert_array_equal(r1["repair_cost"], r2["repair_cost"])
    np.testing.assert_array_equal(r1["repair_time"], r2["repair_time"])


# ---------------------------------------------------------------------------
# Low-rise archetype smoke test (different story count / fragility)
# ---------------------------------------------------------------------------

def test_assess_low_rise_archetype(dummy_edp_samples):
    """assess() must work for the low-rise archetype (C1-L Mid/Hi, 2 stories)."""
    b = Building.from_archetype("C1-L (Mid/Hi)")
    result = b.assess(dummy_edp_samples, seed=42)
    assert "repair_cost" in result
    assert result["repair_cost"].shape[0] == dummy_edp_samples.shape[0]


def test_assess_single_story_archetype(dummy_edp_samples):
    """assess() must work for single-story archetypes (W-L, 1 story)."""
    b = Building.from_archetype("W-L")
    result = b.assess(dummy_edp_samples, seed=42)
    assert "repair_cost" in result
    assert result["repair_cost"].shape[0] == dummy_edp_samples.shape[0]


def test_assess_merged_archetype(dummy_edp_samples):
    """assess() must work for merged archetypes (PC-L → uses C1-L Pre/Lo fragility)."""
    b = Building.from_archetype("PC-L")
    result = b.assess(dummy_edp_samples, seed=42)
    assert "repair_cost" in result
    assert isinstance(result["damage"], dict)


# ---------------------------------------------------------------------------
# loss_ratio correctness — the key fix for the replacement cost bug
# ---------------------------------------------------------------------------

def test_loss_ratio_nonzero_for_damaging_edps():
    """loss_ratio must be > 0 for clearly-damaging drift levels.

    Regression test for the replacement_cost=0 bug (fixed 2026-06-26):
    previously _get_replacement_cost() returned 0 because archetypes had no
    replacement_cost_PHP in metadata and replacement.csv had no DS1-Theta_0.
    Now per-archetype replacement_cost_PHP is in archetypes.yaml (single
    source of truth) and flows through to Building.metadata.
    """
    b = Building.from_archetype("C1-M (Hi)")
    rng = np.random.default_rng(42)
    n_sims, n_stories = 100, b.stories
    # 3% median drift — well above CHB infill damage threshold
    pid = rng.lognormal(mean=np.log(0.03), sigma=0.4, size=(n_sims, n_stories))
    pfa = rng.lognormal(mean=np.log(0.3), sigma=0.4, size=(n_sims, n_stories))
    edp = np.stack([pid, pfa], axis=-1)
    result = b.assess(edp, seed=42)
    lr = result["loss_ratio"]
    assert np.any(lr > 0), (
        "loss_ratio must be > 0 at ~3% drift; replacement_cost_PHP not flowing through"
    )
    assert np.all(lr >= 0), "loss_ratio must be non-negative"
    assert np.all(lr <= 1.0), "loss_ratio must be <= 1"


def test_loss_ratio_monotonic_with_severity():
    """Mean loss_ratio must increase monotonically with PID severity.

    Checks ~1%, ~3%, ~5% PID median levels. Mean over 200 sims should be
    strictly increasing — a basic sanity check that the Pelicun damage model
    is responding to EDP severity and replacement cost is nonzero.
    """
    b = Building.from_archetype("C1-M (Hi)")
    rng = np.random.default_rng(2026)
    n_sims, n_stories = 200, b.stories

    mean_loss_ratios = []
    for pid_pct in [0.01, 0.03, 0.05]:
        pid = rng.lognormal(mean=np.log(pid_pct), sigma=0.4, size=(n_sims, n_stories))
        pfa = rng.lognormal(mean=np.log(0.3), sigma=0.4, size=(n_sims, n_stories))
        edp = np.stack([pid, pfa], axis=-1)
        result = b.assess(edp, seed=42)
        mean_loss_ratios.append(float(np.mean(result["loss_ratio"])))

    lr_1pct, lr_3pct, lr_5pct = mean_loss_ratios
    assert lr_1pct > 0, f"loss_ratio at ~1% drift must be > 0, got {lr_1pct}"
    assert lr_3pct > lr_1pct, (
        f"loss_ratio at ~3% drift ({lr_3pct:.4f}) must exceed ~1% ({lr_1pct:.4f})"
    )
    assert lr_5pct > lr_3pct, (
        f"loss_ratio at ~5% drift ({lr_5pct:.4f}) must exceed ~3% ({lr_3pct:.4f})"
    )
    assert lr_5pct <= 1.0, f"loss_ratio must be <= 1.0, got {lr_5pct:.4f}"


def test_archetype_has_replacement_cost_in_metadata():
    """All 20 archetypes must have a positive replacement_cost_PHP in metadata.

    Regression test: ensures archetypes.yaml has the replacement_cost_PHP
    field for every archetype and that archetypes.py reads it correctly.
    """
    for arch_id in ARCHETYPE_IDS:
        b = Building.from_archetype(arch_id)
        repl_cost = b.metadata.get("replacement_cost_PHP")
        assert repl_cost is not None, (
            f"{arch_id}: replacement_cost_PHP missing from metadata"
        )
        assert float(repl_cost) > 0, (
            f"{arch_id}: replacement_cost_PHP must be positive, got {repl_cost}"
        )


# ---------------------------------------------------------------------------
# Component-driven loss + recovery differentiation
# (regression for the collapse-dominated / degenerate-milestone placeholder)
# ---------------------------------------------------------------------------

def _moderate_edp(stories: int, pid_med: float = 0.025, pfa_med: float = 0.6,
                  n_sims: int = 300, seed: int = 7) -> np.ndarray:
    """Moderate non-collapse EDP sample (drift below the ~10% collapse proxy)."""
    rng = np.random.default_rng(seed)
    pid = np.clip(
        rng.lognormal(mean=np.log(pid_med), sigma=0.4, size=(n_sims, stories)),
        0.0, 0.09,
    )
    pfa = np.clip(
        rng.lognormal(mean=np.log(pfa_med), sigma=0.4, size=(n_sims, stories)),
        0.0, 5.0,
    )
    return np.stack([pid, pfa], axis=-1)


def test_component_repair_loss_is_meaningful_not_collapse_only():
    """Component repair loss must be a meaningful fraction at moderate drift.

    Regression for the placeholder inventory: with 5 generic Repair-Class-1
    components the non-collapse component repair loss was tiny (~5% of total) and
    portfolio loss was collapse-dominated. With the real Table D-13 population a
    typical ductile RC archetype must show substantial component repair loss
    (median loss ratio well above a few percent) WITHOUT any collapse override.
    """
    b = Building.from_archetype("C1-M (Hi)")
    edp = _moderate_edp(b.stories)
    result = b.assess(edp, seed=7)  # pure component path (no collapse override)
    lr = result["loss_ratio"]
    # Median component-only loss ratio should be clearly non-trivial (> 5%).
    assert np.median(lr) > 0.05, (
        f"component-only median loss ratio too low ({np.median(lr):.4f}); "
        "inventory may have fallen back to the sparse placeholder"
    )
    # And repair cost must be > 0 in the vast majority of sims.
    assert (result["repair_cost"] > 0).mean() > 0.9


@pytest.mark.parametrize("archetype_id", ["C1-M (Hi)", "C1-M (Mid)", "S1-M (Hi)"])
def test_recovery_milestones_differentiate(archetype_id):
    """RO/FR/FU must NOT be byte-identical for multi-repair-class archetypes.

    The placeholder inventory had every component in Repair Class 1, so rc2==rc3==0
    and reoccupancy == functional == full (byte-identical arrays). With the real
    multi-class population the milestones must separate: median(RO) < median(FR)
    and the FR array must differ from the RO array.
    """
    b = Building.from_archetype(archetype_id)
    edp = _moderate_edp(b.stories, seed=11)
    result = b.assess(edp, seed=11)
    ro = result["reoccupancy_days"]
    fr = result["functional_recovery_days"]
    fu = result["full_recovery_days"]
    assert ro is not None and fr is not None and fu is not None
    # Not byte-identical (the degeneracy the placeholder produced).
    assert not np.array_equal(ro, fr), (
        f"{archetype_id}: reoccupancy == functional (degenerate milestones)"
    )
    # Functional gate strictly later than reoccupancy at the median.
    assert np.median(fr) > np.median(ro), (
        f"{archetype_id}: median functional ({np.median(fr):.1f}) "
        f"not > median reoccupancy ({np.median(ro):.1f})"
    )
    # Ordering still holds element-wise.
    assert np.all(fu >= fr) and np.all(fr >= ro)


# ---------------------------------------------------------------------------
# Residual-drift (irreparability) demolition trigger
# FEMA P-58 (2018a) / Ramirez & Miranda (2012); median RIDR = thesis Table 6-6.
# See docs/learnings/2026-06-27_rdr_demolition.md.
# ---------------------------------------------------------------------------
class TestDemolitionFragility:
    """Unit tests for the demolition_probability / sample_demolition primitives."""

    def test_probability_is_half_at_median(self):
        """P(demolition | RIDR = median) == 0.5 (lognormal fragility property)."""
        p = float(demolition_probability(np.array([0.01]), median_ridr_pct=1.0)[0])
        assert abs(p - 0.5) < 1e-9

    def test_probability_monotonic_in_ridr(self):
        """P(demolition) increases with residual drift."""
        ridr = np.array([0.002, 0.005, 0.01, 0.02, 0.05])
        p = demolition_probability(ridr, median_ridr_pct=1.0)
        assert np.all(np.diff(p) > 0)
        assert p[0] < 0.05 and p[-1] > 0.95

    def test_zero_median_means_never_demolish(self):
        """A 0.0% RIDR limit (residual drift NOT governing, e.g. CWS-L) -> P == 0.

        This is the thesis-faithful behaviour: archetype_fragilities.yaml records
        CWS-L residual_drift_limit = 0.0% ('not a governing criterion'), so the
        demolition fragility must be identically zero regardless of how large the
        residual drift gets.
        """
        p = demolition_probability(np.array([0.0001, 0.05, 0.20]), median_ridr_pct=0.0)
        assert np.all(p == 0.0)

    def test_sample_demolition_excludes_collapsed(self):
        """Demolition mask is mutually exclusive with the collapse mask.

        Order is collapse -> else demolition: a realization that already collapsed is
        never additionally flagged for demolition (no double-counting of total loss).
        """
        n = 5000
        ridr = np.full(n, 0.05)  # well above 1% median -> high demolition probability
        collapse = np.zeros(n, dtype=bool)
        collapse[: n // 2] = True  # first half collapsed
        rng = np.random.default_rng(0)
        demo = sample_demolition(ridr, 1.0, collapse, rng)
        assert not np.any(demo & collapse), "demolition must exclude collapsed cells"
        # Among non-collapsed, with RIDR=5% the demolition fraction is high (~1.0).
        assert demo[~collapse].mean() > 0.9

    def test_sample_demolition_high_ridr_triggers_total_loss(self):
        """High residual drift -> nearly all non-collapsed cells demolished."""
        n = 4000
        ridr = np.full(n, 0.03)
        collapse = np.zeros(n, dtype=bool)
        rng = np.random.default_rng(1)
        demo = sample_demolition(ridr, 1.0, collapse, rng)
        assert demo.mean() > 0.95


class TestAssessScenarioDemolition:
    """assess_scenario must route collapse -> demolition -> component, total loss = 1."""

    def test_demolition_mask_present_and_exclusive(self):
        b = Building.from_archetype("C1-L (Pre/Lo)")
        r = b.assess_scenario(0.85, soil_bin="C", n_realizations=1000, seed=3)
        assert "demolition_mask" in r and "p_demolition" in r
        cm, dm = r["collapse_mask"], r["demolition_mask"]
        assert cm.shape == dm.shape
        assert not np.any(cm & dm), "collapse and demolition masks must be disjoint"

    def test_demolished_realizations_are_total_loss(self):
        """Every demolished (non-collapsed) realization has loss_ratio == 1."""
        b = Building.from_archetype("C1-L (Pre/Lo)")
        r = b.assess_scenario(0.85, soil_bin="C", n_realizations=1000, seed=5)
        dm = r["demolition_mask"]
        assert dm.any(), "expected some demolition for C1-L (Pre/Lo) above 1% RIDR"
        assert np.all(r["loss_ratio"][dm] == 1.0)
        # Demolished recovery == collapsed recovery (full replacement duration).
        if r["full_recovery_days"] is not None and (r["collapse_mask"]).any():
            repl_days = float(np.unique(r["full_recovery_days"][r["collapse_mask"]])[0])
            assert np.allclose(r["full_recovery_days"][dm], repl_days)

    def test_cold_pre_code_archetype_rises_with_demolition(self):
        """C1-L (Pre/Lo): residual-drift demolition lifts loss well above component-only.

        At its field intensity the median peak RIDR exceeds the 1.0% demolition median
        (thesis Table 6-6), so a large fraction of non-collapsed buildings is demolished,
        pushing the mean loss ratio toward total loss (the previously 'cold' side).
        """
        b = Building.from_archetype("C1-L (Pre/Lo)")
        r = b.assess_scenario(0.85, soil_bin="C", n_realizations=2000, seed=7)
        assert r["demolition_mask"].mean() > 0.2
        assert float(np.mean(r["loss_ratio"])) > 0.7

    def test_ductile_low_ridr_minimal_demolition_at_median_sa(self):
        """A ductile frame at its near-design field Sa has little residual drift.

        C1-M (Hi) at Sa=0.55 g (its WVF field median) has median peak RIDR well below
        1%, so demolition is rare and the loss stays CHB-component-driven, NOT total
        loss. (The upper Sa tail does trigger some demolition in the portfolio; this
        test isolates the central tendency at the median field Sa.)
        """
        b = Building.from_archetype("C1-M (Hi)")
        r = b.assess_scenario(0.55, soil_bin="C1", n_realizations=2000, seed=7)
        assert r["p_collapse"] < 0.05
        assert r["demolition_mask"].mean() < 0.05
        assert float(np.mean(r["loss_ratio"])) < 0.35

    def test_cws_l_no_demolition_thesis_faithful(self):
        """CWS-L has a 0.0% residual-drift limit -> NO demolition, by thesis design.

        Even though CWS-L develops large residual drifts, the thesis explicitly records
        residual drift as NOT a governing criterion for CWS-L (residual_drift_limit =
        0.0%), so the demolition trigger must never fire for it. We honour the thesis
        value rather than tuning CWS-L toward its .mat anchor.
        """
        b = Building.from_archetype("CWS-L")
        assert float(b.metadata.get("residual_drift_limit_pct")) == 0.0
        r = b.assess_scenario(1.0, soil_bin="C", n_realizations=2000, seed=7)
        assert r["demolition_mask"].sum() == 0
        assert r["p_demolition"] == 0.0

    def test_ductile_demolition_capped_above_stripe_range(self):
        """A ductile frame does NOT demolish wholesale at extreme Sa (residual cap).

        Demolition recalibration (2026-06-27): the residual-drift demand is conditioned on
        the MEDIAN residual (not the EDP record-to-record scatter) and is NOT extrapolated
        above the top calibrated stripe — above that, the collapse fragility governs total
        loss. So at a high Sa (well past the C1-M (Hi) top RDR stripe ~1.04 g) the surviving
        (non-collapsed) realizations are NOT all demolished; the residual median is held at
        its top-stripe value (~0.8% < 1.0% limit), so the conditional demolition rate stays
        modest rather than -> 1.0. (Pre-2026-06-27 this over-fired to near-total demolition.)
        See docs/learnings/2026-06-27_demolition_recalibration.md.
        """
        b = Building.from_archetype("C1-M (Hi)")
        r = b.assess_scenario(2.0, soil_bin="C1", n_realizations=4000, seed=11)
        non_collapsed = ~r["collapse_mask"]
        assert non_collapsed.any()
        cond_demo = r["demolition_mask"][non_collapsed].mean()
        # Median residual at the clamped top stripe (~0.8%) is below the 1% limit, so the
        # conditional demolition rate is well under 0.5 (not the ~1.0 of the old blow-up).
        assert cond_demo < 0.5, f"ductile over-demolishing at high Sa: {cond_demo:.3f}"

    def test_demolition_differentiates_ductile_from_pre_code_at_high_sa(self):
        """At the SAME high Sa, pre-code demolishes far more than a ductile frame.

        The corrected mechanism keys demolition on the archetype's own median residual
        drift: a ductile RC frame re-centers (median residual << 1% limit even at high Sa,
        held flat by the cap), whereas a pre-code frame ratchets to a large residual that
        crosses its 1% limit. The conditional (non-collapsed) demolition rate must therefore
        be much higher for the pre-code archetype.
        """
        sa = 1.2
        rd = Building.from_archetype("C1-M (Hi)").assess_scenario(
            sa, soil_bin="C1", n_realizations=4000, seed=5)
        rp = Building.from_archetype("C1-L (Pre/Lo)").assess_scenario(
            sa, soil_bin="C", n_realizations=4000, seed=5)
        ductile = rd["demolition_mask"][~rd["collapse_mask"]].mean()
        precode = rp["demolition_mask"][~rp["collapse_mask"]].mean()
        assert precode > 3 * max(ductile, 1e-3), (
            f"expected pre-code >> ductile demolition; ductile={ductile:.3f} "
            f"pre-code={precode:.3f}"
        )

    def test_demolition_increases_monotonically_with_sa(self):
        """Demolition fraction rises with Sa for a residual-drift-governed archetype."""
        b = Building.from_archetype("C1-L (Pre/Lo)")
        fracs = []
        for sa in (0.4, 0.6, 0.85):
            r = b.assess_scenario(sa, soil_bin="C", n_realizations=3000, seed=11)
            # Demolition fraction among the NON-collapsed cells (isolate the RDR effect;
            # collapse also rises with Sa and would otherwise shrink the demolition pool).
            nc = ~r["collapse_mask"]
            fracs.append(float(r["demolition_mask"][nc].mean()) if nc.any() else 0.0)
        assert fracs[0] <= fracs[1] + 1e-9 <= fracs[2] + 1e-9, fracs


# ===========================================================================
# Non-structural mitigation (the thesis's SECOND mitigation layer, Table 6-3):
# a component-level fragility/consequence swap that upgrades acceleration-/drift-
# sensitive non-structural components to anchored/braced/seismic counterparts and
# REMOVES electronics, to reduce non-collapse INJURIES. CI-safe: the marginals
# builder + map need no real data; the assess-scenario tests use the bundled EDP store.
# ===========================================================================
class TestNonStructuralMitigation:
    """Table 6-3 component swap: braced ceilings, seismic/safety-wired fixtures,
    reinforced CHB, electronics removed — drives the injury-reduction layer."""

    def test_map_matches_thesis_table_6_3(self):
        subs, removed = _ns_mitigation_map()
        # Existing -> upgraded counterpart (Table 6-3).
        assert subs["PH.NS.CLG.NS"] == "PH.NS.CLG.BR"   # ceiling: non-seismic -> braced
        assert subs["PH.NS.FIX.NS"] == "PH.NS.FIX.SE"   # fixtures: -> seismic (no casualty)
        assert subs["PH.NS.CHB.SU"] == "PH.NS.CHB.SR"   # CHB solid: unreinf -> reinforced
        assert subs["PH.NS.CHB.PU"] == "PH.NS.CHB.PR"   # CHB perf: unreinf -> reinforced
        # Electronics removed entirely ("simulate no damage/casualty").
        assert "PH.NS.ELEC.DT" in removed
        assert "PH.NS.ELEC.WM" in removed

    def test_marginals_swap_components(self):
        """The mitigated marginals replace the upgradeable NS ids and drop electronics;
        structural components + quantities/locations are preserved."""
        m0 = _build_cmp_marginals(3, "C1-M (Pre/Lo)", nonstructural_mitigated=False)
        m1 = _build_cmp_marginals(3, "C1-M (Pre/Lo)", nonstructural_mitigated=True)
        base_ids = set(m0.index)
        mit_ids = set(m1.index)
        # Upgraded counterparts present, originals gone.
        assert "PH.NS.FIX.NS" in base_ids and "PH.NS.FIX.NS" not in mit_ids
        assert "PH.NS.FIX.SE" in mit_ids
        assert "PH.NS.CLG.NS" in base_ids and "PH.NS.CLG.BR" in mit_ids
        # Structural component rows are untouched.
        assert "PH.S.NDRCMRF.1S" in mit_ids
        # Same number of marginal rows (swaps, not additions) when nothing is removed
        # for this archetype (C1-M (Pre/Lo) carries no electronics).
        assert len(m0) == len(m1)

    def test_marginals_remove_electronics(self):
        """An archetype that carries electronics (PTC1-M (Hi)) loses those rows under
        the mitigation (removed, not swapped)."""
        m0 = _build_cmp_marginals(5, "PTC1-M (Hi)", nonstructural_mitigated=False)
        m1 = _build_cmp_marginals(5, "PTC1-M (Hi)", nonstructural_mitigated=True)
        if "PH.NS.ELEC.DT" in set(m0.index) or "PH.NS.ELEC.WM" in set(m0.index):
            assert "PH.NS.ELEC.DT" not in set(m1.index)
            assert "PH.NS.ELEC.WM" not in set(m1.index)
            assert len(m1) < len(m0)  # rows removed

    def test_building_flag_default_false(self):
        b = Building.from_archetype("C1-M (Pre/Lo)")
        assert b.nonstructural_mitigated is False

    def test_mitigation_neutralises_noncollapse_injuries(self):
        """Non-structural mitigation must sharply cut NON-collapse component injuries for
        a school archetype (fixtures/ceilings/CHB are the NC injury drivers); collapse
        is left untouched (that is the separate structural-FRP layer's job)."""
        def run(mit):
            b = Building.from_archetype("C1-M (Pre/Lo)")
            b.metadata["population"] = 846.0
            b.metadata["floor_area_m2"] = 916.0
            b.nonstructural_mitigated = mit
            return b.assess_scenario(0.8, soil_bin="D", n_realizations=1500, seed=2024)

        r0 = run(False)
        r1 = run(True)
        base_nc = float(r0["injuries_noncollapse"].mean())
        mit_nc = float(r1["injuries_noncollapse"].mean())
        assert base_nc > 0, "expected non-zero base NC injuries to begin with"
        # The thesis "neutralises non-collapse injuries" — expect a large reduction.
        assert mit_nc < 0.25 * base_nc, (
            f"NC injuries not neutralised: {mit_nc:.3f} vs {base_nc:.3f}"
        )
        # Collapse must be unchanged (NS mitigation is a component swap, not a retrofit).
        np.testing.assert_array_equal(r0["collapse_mask"], r1["collapse_mask"])

    def test_mitigation_does_not_increase_loss(self):
        """The component upgrade can only reduce (or hold) the mean loss ratio."""
        def run(mit):
            b = Building.from_archetype("C1-M (Pre/Lo)")
            b.nonstructural_mitigated = mit
            return b.assess_scenario(0.7, soil_bin="D", n_realizations=1500, seed=99)
        r0 = run(False)
        r1 = run(True)
        assert float(r1["loss_ratio"].mean()) <= float(r0["loss_ratio"].mean()) + 1e-9


# ---------------------------------------------------------------------------
# Degenerate zero-loss guard (building.py _run_pelicun)
# ---------------------------------------------------------------------------

class TestZeroLossGuard:
    """A legitimately-undamaged building must yield zero loss, not crash.

    At very low Sa with a small sample, EVERY realization can fall below the
    damage threshold; Pelicun's aggregate_loss then raises internally
    (assert isinstance(output, tuple)). building._run_pelicun catches that
    specific AssertionError and returns zero repair cost/time — the physically
    correct outcome — so the far-field / low-Sa scenarios are robust at small N.
    Surfaced by the GNW-7.2 / Manila Trench breadth runs on the W-L (wood)
    archetype; this locks the guard so it cannot regress.
    """

    def test_low_sa_small_sample_does_not_crash(self):
        b = Building.from_archetype("W-L", site_class="C")
        # Very low Sa, tiny sample → likely no damage in any realization.
        res = b.assess_scenario(0.02, soil_bin="C", n_realizations=8, seed=12345)
        assert res["loss_ratio"].shape == (8,)
        assert np.all(np.isfinite(res["loss_ratio"]))
        # Undamaged → ~zero loss (and certainly no NaN / no exception).
        assert float(np.mean(res["loss_ratio"])) >= 0.0
        assert float(np.mean(res["loss_ratio"])) < 0.05

    def test_high_sa_still_produces_loss(self):
        """Sanity counter-test: the guard does NOT suppress real losses."""
        b = Building.from_archetype("W-L", site_class="C")
        res = b.assess_scenario(0.9, soil_bin="C", n_realizations=200, seed=7)
        # A wood building at high Sa must show meaningful loss (guard inactive).
        assert float(np.mean(res["loss_ratio"])) > 0.05
