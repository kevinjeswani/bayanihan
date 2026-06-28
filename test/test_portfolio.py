"""Tests for bayanihan.portfolio — PortfolioAnalysis + ScenarioPortfolio."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from bayanihan.portfolio import PortfolioAnalysis


# ---------------------------------------------------------------------------
# WVF Mw=7.3 scenario (shallow crustal — West Valley Fault, Makati + QC)
# Thesis Chapter 7 reference event.
# ---------------------------------------------------------------------------
WVF_RUPTURE = {
    "Mw": 7.3,
    "lat": 14.35,
    "lon": 121.10,
    "depth": 20.0,
    "mechanism": "crustal",
}

# Small n_sims for test speed — this is a smoke run (does the model run correctly),
# NOT a production simulation. Real N=1000 runs live in scripts/.
N_SIMS_TEST = 20


# ---------------------------------------------------------------------------
# from_demo_inventory()
# ---------------------------------------------------------------------------

class TestFromDemoInventory:
    def test_loads_50_buildings(self):
        """from_demo_inventory() must load exactly 50 buildings."""
        pa = PortfolioAnalysis.from_demo_inventory(n_simulations=N_SIMS_TEST, seed=42)
        assert len(pa.inventory) == 50

    def test_returns_portfolio_analysis_instance(self):
        """from_demo_inventory() must return a PortfolioAnalysis."""
        pa = PortfolioAnalysis.from_demo_inventory(n_simulations=N_SIMS_TEST, seed=42)
        assert isinstance(pa, PortfolioAnalysis)

    def test_inventory_has_required_columns(self):
        """Inventory must have the minimum columns for portfolio.run()."""
        pa = PortfolioAnalysis.from_demo_inventory(n_simulations=N_SIMS_TEST, seed=42)
        required = {"archetype_id", "lat", "lon", "stories", "replacement_cost_php"}
        assert required.issubset(set(pa.inventory.columns))

    def test_inventory_lat_lon_plausible(self):
        """All buildings must fall within Metro Manila bounding box."""
        pa = PortfolioAnalysis.from_demo_inventory(n_simulations=N_SIMS_TEST, seed=42)
        # Metro Manila rough bounds: lat 14.4–14.8, lon 120.9–121.2
        assert (pa.inventory["lat"].between(14.0, 15.5)).all()
        assert (pa.inventory["lon"].between(120.5, 122.0)).all()

    def test_kwargs_passed_through(self):
        """Constructor kwargs (n_simulations, seed) must be stored on the instance."""
        pa = PortfolioAnalysis.from_demo_inventory(n_simulations=123, seed=7)
        assert pa.n_simulations == 123
        assert pa.seed == 7


# ---------------------------------------------------------------------------
# run()
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def wvf_result():
    """Run WVF scenario once (module scope for speed)."""
    pa = PortfolioAnalysis.from_demo_inventory(n_simulations=N_SIMS_TEST, seed=42)
    return pa.run(WVF_RUPTURE)


class TestRunReturnStructure:
    def test_returns_dict(self, wvf_result):
        assert isinstance(wvf_result, dict)

    def test_required_keys_present(self, wvf_result):
        required = {
            "loss_ratio",
            "repair_cost",
            "repair_time",
            "portfolio_loss_ratio",
            "portfolio_repair_cost",
            "summary",
            "n_buildings",
            "n_simulations",
            "total_replacement_cost_php",
        }
        assert required.issubset(set(wvf_result.keys()))

    def test_loss_ratio_shape(self, wvf_result):
        """loss_ratio must be (n_buildings, n_simulations)."""
        lr = wvf_result["loss_ratio"]
        assert lr.shape == (50, N_SIMS_TEST)

    def test_repair_cost_shape(self, wvf_result):
        assert wvf_result["repair_cost"].shape == (50, N_SIMS_TEST)

    def test_repair_time_shape(self, wvf_result):
        assert wvf_result["repair_time"].shape == (50, N_SIMS_TEST)

    def test_portfolio_loss_ratio_shape(self, wvf_result):
        assert wvf_result["portfolio_loss_ratio"].shape == (N_SIMS_TEST,)

    def test_summary_is_dataframe(self, wvf_result):
        import pandas as pd
        assert isinstance(wvf_result["summary"], pd.DataFrame)

    def test_summary_rows_match_buildings(self, wvf_result):
        assert len(wvf_result["summary"]) == 50

    def test_n_buildings_metadata(self, wvf_result):
        assert wvf_result["n_buildings"] == 50

    def test_n_simulations_metadata(self, wvf_result):
        assert wvf_result["n_simulations"] == N_SIMS_TEST


class TestRunValueConstraints:
    def test_portfolio_loss_ratio_in_unit_interval(self, wvf_result):
        """Portfolio loss ratio must be in [0, 1] for every simulation."""
        plr = wvf_result["portfolio_loss_ratio"]
        assert np.all(plr >= 0.0), f"Min loss ratio: {plr.min()}"
        assert np.all(plr <= 1.0), f"Max loss ratio: {plr.max()}"

    def test_per_building_loss_ratio_in_unit_interval(self, wvf_result):
        lr = wvf_result["loss_ratio"]
        assert np.all(lr >= 0.0)
        assert np.all(lr <= 1.0)

    def test_no_nan_in_loss_ratio(self, wvf_result):
        assert not np.any(np.isnan(wvf_result["loss_ratio"]))

    def test_no_nan_in_portfolio_loss_ratio(self, wvf_result):
        assert not np.any(np.isnan(wvf_result["portfolio_loss_ratio"]))

    def test_no_nan_in_repair_cost(self, wvf_result):
        assert not np.any(np.isnan(wvf_result["repair_cost"]))

    def test_repair_cost_nonneg(self, wvf_result):
        assert np.all(wvf_result["repair_cost"] >= 0.0)

    def test_repair_time_nonneg(self, wvf_result):
        assert np.all(wvf_result["repair_time"] >= 0.0)

    def test_total_replacement_cost_positive(self, wvf_result):
        assert wvf_result["total_replacement_cost_php"] > 0

    def test_summary_median_loss_ratio_in_unit_interval(self, wvf_result):
        mlr = wvf_result["summary"]["median_loss_ratio"].values
        assert np.all(mlr >= 0.0)
        assert np.all(mlr <= 1.0)


@pytest.mark.integration
class TestReproducibility:
    def test_identical_seed_gives_identical_results(self):
        """Same seed must yield identical portfolio_loss_ratio."""
        pa1 = PortfolioAnalysis.from_demo_inventory(n_simulations=N_SIMS_TEST, seed=99)
        pa2 = PortfolioAnalysis.from_demo_inventory(n_simulations=N_SIMS_TEST, seed=99)
        r1 = pa1.run(WVF_RUPTURE)
        r2 = pa2.run(WVF_RUPTURE)
        np.testing.assert_array_equal(
            r1["portfolio_loss_ratio"],
            r2["portfolio_loss_ratio"],
        )

    def test_different_seed_gives_different_results(self):
        """Different seeds should give different (but valid) portfolio distributions."""
        pa1 = PortfolioAnalysis.from_demo_inventory(n_simulations=N_SIMS_TEST, seed=1)
        pa2 = PortfolioAnalysis.from_demo_inventory(n_simulations=N_SIMS_TEST, seed=2)
        r1 = pa1.run(WVF_RUPTURE)
        r2 = pa2.run(WVF_RUPTURE)
        # Should differ — probability of identical by chance is negligible
        assert not np.array_equal(
            r1["portfolio_loss_ratio"],
            r2["portfolio_loss_ratio"],
        )


@pytest.mark.integration
class TestRuptureKeyNormalisation:
    """Verify both 'Mw' and 'mw' are accepted as the magnitude key."""

    def test_uppercase_mw_accepted(self):
        pa = PortfolioAnalysis.from_demo_inventory(n_simulations=N_SIMS_TEST, seed=42)
        result = pa.run({"Mw": 7.3, "lat": 14.35, "lon": 121.10, "depth": 20.0, "mechanism": "crustal"})
        assert "portfolio_loss_ratio" in result

    def test_lowercase_mw_accepted(self):
        pa = PortfolioAnalysis.from_demo_inventory(n_simulations=N_SIMS_TEST, seed=42)
        result = pa.run({"mw": 7.3, "lat": 14.35, "lon": 121.10, "depth": 20.0, "mechanism": "crustal"})
        assert "portfolio_loss_ratio" in result


# ===========================================================================
# REAL-DATA scenario portfolio (P5/P7) — gated on the gitignored real inventory.
# Uses the correlated Sa(T1) field (scenario_sa_field) + real multi-stripe EDPs.
# ===========================================================================
from bayanihan.portfolio import (  # noqa: E402
    ScenarioPortfolio,
    summarise_scenario_result,
    _load_real_inventory,
)


def _real_scenario_available() -> bool:
    """True iff the real inventory AND the WVF_7.3 distance table are both present."""
    try:
        _load_real_inventory()
    except FileNotFoundError:
        return False
    from bayanihan.hazard import _load_distance_table
    try:
        _load_distance_table("WVF_7.3")
    except FileNotFoundError:
        return False
    return True


requires_real_scenario = pytest.mark.skipif(
    not _real_scenario_available(),
    reason="Real inventory geojson or WVF_7.3 distance table absent (gitignored).",
)

# Small N for test speed — 1021 buildings × N Pelicun assessments.
N_REAL_TEST = 12


@pytest.fixture(scope="module")
def real_wvf_result():
    """Run the real-data WVF_7.3 scenario once (module scope; small N).

    Skips at fixture setup if the gitignored real data is absent, so the gated
    test classes below skip cleanly on CI.
    """
    if not _real_scenario_available():
        pytest.skip("Real inventory / WVF_7.3 distance table absent (gitignored).")
    sp = ScenarioPortfolio.from_real_inventory(
        scenario_id="WVF_7.3", n_realizations=N_REAL_TEST, seed=12345
    )
    return sp.run(progress_every=0)


@pytest.mark.integration
@requires_real_scenario
class TestScenarioPortfolioRealData:
    def test_inventory_is_1021_buildings(self):
        inv = _load_real_inventory()
        assert len(inv) == 1021

    def test_runs_end_to_end(self, real_wvf_result):
        r = real_wvf_result
        assert r.loss_ratio.shape == (1021, N_REAL_TEST)
        assert r.portfolio_loss_ratio.shape == (N_REAL_TEST,)

    def test_makati_subset_is_96(self, real_wvf_result):
        inv = real_wvf_result.inventory
        assert int((inv["city"] == "MC").sum()) == 96
        assert int((inv["city"] == "QC").sum()) == 925

    def test_loss_ratios_in_unit_interval(self, real_wvf_result):
        r = real_wvf_result
        assert np.all(r.loss_ratio >= 0.0) and np.all(r.loss_ratio <= 1.0)
        plr = r.portfolio_loss_ratio
        assert np.all(plr >= 0.0) and np.all(plr <= 1.0)

    def test_no_nan_in_results(self, real_wvf_result):
        r = real_wvf_result
        assert not np.any(np.isnan(r.loss_ratio))
        assert not np.any(np.isnan(r.portfolio_loss_ratio))
        assert not np.any(np.isnan(r.portfolio_loss_php))

    def test_portfolio_dispersion_non_degenerate(self, real_wvf_result):
        """Spatial correlation + correct hazard sigma must yield a WIDE portfolio
        loss spread — a degenerate (near-constant) spread means the correlation was
        broken or the wrong (halved) sigma was used."""
        plr = real_wvf_result.portfolio_loss_ratio
        # Coefficient of variation across realizations must be clearly non-trivial.
        cov = float(np.std(plr) / max(np.mean(plr), 1e-9))
        assert cov > 0.10, f"portfolio loss CoV {cov:.3f} too low — dispersion collapsed"
        # And the p84/p16 ratio should be well above 1 (lognormal-like spread).
        p16, p84 = np.percentile(plr, [16, 84])
        assert p84 > p16 * 1.2, f"p84 {p84:.3f} not meaningfully above p16 {p16:.3f}"

    def test_summary_aggregates_present_and_consistent(self, real_wvf_result):
        s = summarise_scenario_result(real_wvf_result)
        assert s["n_buildings"] == 1021
        assert s["n_buildings_makati_MC"] == 96
        assert s["n_buildings_quezon_QC"] == 925
        for block in ("whole_portfolio", "makati_MC", "quezon_QC"):
            lr = s[block]["loss_ratio"]
            assert 0.0 <= lr["mean"] <= 1.0
            assert lr["p16"] <= lr["p50"] <= lr["p84"]
        # No per-building identifiers in the committable summary.
        flat = json.dumps(s)
        assert "building_id" not in flat
        # Recovery milestones ordered: full >= functional >= reoccupancy.
        rec = s["recovery_days_portfolio_mean"]
        assert rec["full_recovery"]["mean"] >= rec["functional_recovery"]["mean"] >= rec["reoccupancy"]["mean"] >= 0.0

    def test_loss_source_decomposition_3way_sums_to_one(self, real_wvf_result):
        """3-way loss-source split (collapse / demolition / component) sums to 1.0.

        The residual-drift demolition path (FEMA P-58 / Ramirez & Miranda 2012) adds a
        third mutually-exclusive total-loss source between collapse and component repair.
        The three shares must partition total loss exactly.
        """
        s = summarise_scenario_result(real_wvf_result)
        ls = s["loss_source_decomposition"]
        share_sum = (
            ls["collapse_share_of_total_loss"]
            + ls["demolition_share_of_total_loss"]
            + ls["component_share_of_total_loss"]
        )
        assert share_sum == pytest.approx(1.0, abs=1e-6)
        for k in (
            "collapse_share_of_total_loss",
            "demolition_share_of_total_loss",
            "component_share_of_total_loss",
        ):
            assert 0.0 <= ls[k] <= 1.0
        # Component repair must still be a non-trivial share (guardrail vs the sparse
        # all-Class-1 placeholder, which made loss ~94% collapse(replacement)).
        assert ls["component_share_of_total_loss"] > 0.10, (
            f"component share {ls['component_share_of_total_loss']:.3f} too low — "
            "inventory may have regressed to the sparse placeholder"
        )

    def test_demolition_disjoint_from_collapse_and_total_loss(self, real_wvf_result):
        """Demolition mask is disjoint from collapse; all total-loss cells have LR==1."""
        r = real_wvf_result
        assert r.demolition_mask.shape == r.collapse_mask.shape
        assert not np.any(r.demolition_mask & r.collapse_mask), (
            "demolition and collapse masks must be disjoint (no double-counted total loss)"
        )
        total_loss = r.collapse_mask | r.demolition_mask
        assert np.all(r.loss_ratio[total_loss] == 1.0), (
            "every collapsed-or-demolished realization must be total loss (LR==1)"
        )
        s = summarise_scenario_result(r)
        assert "demolition_rate_building_realizations" in s
        assert 0.0 <= s["demolition_rate_building_realizations"] <= 1.0

    def test_recovery_milestones_differentiate(self, real_wvf_result):
        """The three REDi milestones must now SEPARATE (not be byte-identical).

        Regression for the placeholder all-Class-1 inventory, which forced
        rc2==rc3==0 and reoccupancy==functional==full. With the real multi-class
        component population the milestones differentiate and the summary's
        degeneracy flag must be False.
        """
        s = summarise_scenario_result(real_wvf_result)
        assert s["model_caveats"]["recovery_milestones_degenerate"] is False
        r = real_wvf_result
        # Arrays must no longer be identical across the milestone hierarchy.
        assert not np.array_equal(r.reoccupancy_days, r.functional_recovery_days)
        assert not np.array_equal(r.functional_recovery_days, r.full_recovery_days)
        # Portfolio-mean ordering strict at the functional gate.
        rec = s["recovery_days_portfolio_mean"]
        assert rec["functional_recovery"]["mean"] > rec["reoccupancy"]["mean"]
        assert rec["full_recovery"]["mean"] >= rec["functional_recovery"]["mean"]

    def test_per_archetype_ordering_physical(self, real_wvf_result):
        """Ductile high-code frames must be far less damaged than brittle masonry."""
        s = summarise_scenario_result(real_wvf_result)
        pa = s["per_archetype_loss_ratio"]
        # CHB-L (unreinforced masonry, ~0.35g collapse median) must dominate a
        # ductile high-code RC frame.
        assert pa["CHB-L"]["mean_loss_ratio"] > pa["C1-M (Hi)"]["mean_loss_ratio"]
        assert pa["CHB-L"]["mean_loss_ratio"] > 0.5

    def test_join_assertion_fails_loudly_on_missing_building(self):
        """If an inventory building has no Sa-field column, run() must raise — no
        silent drop (guards the 6%-undercount failure mode)."""
        inv = _load_real_inventory()
        # Inject a bogus building the Sa field will never contain.
        bogus = inv.iloc[[0]].copy()
        bogus["building_id"] = "NONEXISTENT-BUILDING-999"
        inv2 = pd.concat([inv, bogus], ignore_index=True)
        sp = ScenarioPortfolio(inventory=inv2, scenario_id="WVF_7.3", n_realizations=4, seed=1)
        with pytest.raises(AssertionError, match="NO Sa-field column"):
            sp.run(progress_every=0)


# ===========================================================================
# Portfolio recovery-CDF aggregation (thesis 90% functional-recovery metric).
# Pure-function unit tests — no real data required (always run on CI).
# ===========================================================================
from bayanihan.portfolio import (  # noqa: E402  (mid-file: grouped with section)
    _recovery_90pct_block,
    portfolio_recovery_curve,
    portfolio_recovery_time_at_fraction,
)


class TestPortfolioRecoveryCDF:
    """The thesis PRIMARY resilience metric: time to 90% portfolio recovery.

    Definition (Portfolio_Analysis_2021.m line 214): per realization, the day at which
    a fraction of the portfolio (by building COUNT) has reached the milestone = the
    (100*fraction)-th percentile of per-building milestone days across the building
    axis. Median + p90 across realizations.
    """

    def test_time_at_fraction_is_percentile_across_buildings(self):
        """90% time == np.percentile(milestone_days, 90, axis=0) (thesis-exact)."""
        rng = np.random.default_rng(0)
        days = rng.uniform(10, 1000, size=(200, 50))
        got = portfolio_recovery_time_at_fraction(days, fraction=0.90)
        want = np.percentile(days, 90, axis=0)
        assert got.shape == (50,)
        np.testing.assert_allclose(got, want)

    def test_time_at_fraction_monotonic_in_fraction(self):
        """Higher recovered-fraction threshold => longer (or equal) recovery time."""
        rng = np.random.default_rng(1)
        days = rng.uniform(0, 500, size=(300, 40))
        t50 = portfolio_recovery_time_at_fraction(days, 0.50)
        t90 = portfolio_recovery_time_at_fraction(days, 0.90)
        t100 = portfolio_recovery_time_at_fraction(days, 1.00)
        assert np.all(t90 >= t50 - 1e-9)
        assert np.all(t100 >= t90 - 1e-9)

    def test_total_loss_tail_drives_the_90pct_time(self):
        """Buildings carrying the full replacement duration (collapse/demolition)
        must push the 90% time up — the metric is a high tail, not an average."""
        n_bldg, n_real = 100, 20
        # 80% recover fast (50 d), 20% are total loss (1500 d replacement).
        days = np.full((n_bldg, n_real), 50.0)
        days[80:, :] = 1500.0
        t90 = portfolio_recovery_time_at_fraction(days, 0.90)
        # 90th percentile across buildings sits in the total-loss tail.
        assert np.all(t90 >= 1000.0)
        # Whereas the building-mean (old metric) would be far lower.
        assert days.mean(axis=0).mean() < t90.mean()

    def test_curve_is_monotonic_and_spans_zero_to_one(self):
        """Recovery curve f(t) is non-decreasing and reaches ~1 on a wide grid."""
        rng = np.random.default_rng(2)
        days = rng.uniform(0, 600, size=(150, 30))
        t, frac = portfolio_recovery_curve(days, time_grid=np.linspace(0, 700, 50))
        assert t.shape == frac.shape == (50,)
        assert np.all(np.diff(frac) >= -1e-12)
        assert frac[0] <= 0.05
        assert frac[-1] >= 0.99

    def test_curve_crossing_equals_percentile_inverse(self):
        """The day where the mean curve crosses 0.90 must match the across-realization
        mean of the per-realization 90% time (the inverse relationship)."""
        rng = np.random.default_rng(3)
        days = rng.uniform(0, 800, size=(400, 60))
        grid = np.linspace(0, 800, 801)
        t, frac = portfolio_recovery_curve(days, time_grid=grid)
        cross = t[np.searchsorted(frac, 0.90)]
        mean90 = float(np.mean(portfolio_recovery_time_at_fraction(days, 0.90)))
        # Within one grid step (1 day) of each other.
        assert abs(cross - mean90) <= 5.0

    def test_block_keys_and_ordering(self):
        """_recovery_90pct_block returns the expected summary keys, p10<=median<=p90."""
        rng = np.random.default_rng(4)
        days = rng.uniform(0, 1000, size=(250, 80))
        b = _recovery_90pct_block(days, fraction=0.90)
        assert set(b) == {"mean", "median", "p10", "p16", "p84", "p90"}
        assert b["p10"] <= b["median"] <= b["p90"]

    def test_weighted_uniform_matches_count_basis(self):
        """Uniform weights reproduce the unweighted (count) basis."""
        rng = np.random.default_rng(5)
        days = rng.uniform(0, 500, size=(120, 25))
        count = portfolio_recovery_time_at_fraction(days, 0.90, weights=None)
        unif = portfolio_recovery_time_at_fraction(days, 0.90, weights=np.ones(120))
        # Weighted quantile (step inverse-CDF) ~ unweighted percentile; allow a small
        # discretisation gap from the interpolation difference.
        assert abs(float(np.median(count)) - float(np.median(unif))) <= 25.0

    def test_rejects_non_2d_input(self):
        with pytest.raises(ValueError, match="2D"):
            portfolio_recovery_time_at_fraction(np.zeros(10), 0.90)


@pytest.mark.integration
@requires_real_scenario
class TestScenarioRecovery90Summary:
    """The 90% recovery metric is wired into the committable summary per region."""

    def test_summary_has_recovery_90pct_block(self, real_wvf_result):
        s = summarise_scenario_result(real_wvf_result)
        assert "recovery_90pct_functional_days" in s
        blk = s["recovery_90pct_functional_days"]
        assert blk["weighting_basis"] == "building_count"
        for region in ("whole_portfolio", "makati_MC", "quezon_QC"):
            assert region in blk
            for milestone in ("reoccupancy", "functional_recovery", "full_recovery"):
                m = blk[region][milestone]
                assert {"median", "p90"} <= set(m)
                assert m["median"] >= 0.0 and m["p90"] >= m["median"] - 1e-6

    def test_recovery_90pct_milestone_ordering(self, real_wvf_result):
        """90% reoccupancy <= functional <= full, per region (median)."""
        s = summarise_scenario_result(real_wvf_result)
        blk = s["recovery_90pct_functional_days"]
        for region in ("whole_portfolio", "makati_MC", "quezon_QC"):
            ro = blk[region]["reoccupancy"]["median"]
            fr = blk[region]["functional_recovery"]["median"]
            fu = blk[region]["full_recovery"]["median"]
            assert ro <= fr + 1e-6 <= fu + 1e-6, f"{region}: {ro} <= {fr} <= {fu}"

    def test_90pct_exceeds_portfolio_mean_milestone(self, real_wvf_result):
        """The 90%-portfolio FR time (a high tail) must exceed the building-mean FR
        (the old per-realization average) — guards against confusing the two."""
        s = summarise_scenario_result(real_wvf_result)
        r90 = s["recovery_90pct_functional_days"]["whole_portfolio"]
        fr90 = r90["functional_recovery"]["median"]
        fr_mean = s["recovery_days_portfolio_mean"]["functional_recovery"]["median"]
        assert fr90 > fr_mean

    def test_recovery_curve_present_and_monotonic(self, real_wvf_result):
        s = summarise_scenario_result(real_wvf_result)
        curve = s["recovery_curve_functional"]
        days = np.asarray(curve["days"])
        frac = np.asarray(curve["fraction_recovered"])
        assert days.shape == frac.shape and days.size > 1
        assert np.all(np.diff(frac) >= -1e-9)

    def test_thesis_targets_recorded(self, real_wvf_result):
        """The committable summary carries the thesis WVF-7.3 90%-FR targets for
        downstream comparison (Makati 970/1070, QC 640/655)."""
        s = summarise_scenario_result(real_wvf_result)
        tgt = s["recovery_90pct_functional_days"]["thesis_targets_WVF73"]
        assert tgt["makati_MC"]["functional_recovery_median_days"] == 970
        assert tgt["quezon_QC"]["functional_recovery_median_days"] == 640


# ===========================================================================
# Mitigation (FRP retrofit) — base archetype -> retrofit archetype substitution.
# Unit tests on the coverage helper need NO real data (always run on CI); the
# real-data behaviour tests are gated like the rest of the scenario suite.
# ===========================================================================
from bayanihan.portfolio import (  # noqa: E402
    MITIGATION_RETROFIT_MAP,
    mitigation_coverage,
)


class TestMitigationCoverage:
    """The coverage helper quantifies (honestly) how little of the stock is retrofittable."""

    @staticmethod
    def _toy_inv():
        # 3 retrofittable C1-M (Pre/Lo) (2 MC, 1 QC) + 2 non-retrofittable.
        return pd.DataFrame(
            {
                "building_id": ["b1", "b2", "b3", "b4", "b5"],
                "city": ["MC", "MC", "QC", "QC", "MC"],
                "archetype": [
                    "C1-M (Pre/Lo)", "C1-M (Pre/Lo)", "C1-M (Pre/Lo)",
                    "C1-M (Hi)", "CHB-L",
                ],
                "replacement_cost_php": [100.0, 100.0, 100.0, 100.0, 100.0],
            }
        )

    def test_map_only_c1m_prelo(self):
        # Reproducible STRUCTURAL scope is exactly C1-M (Pre/Lo) -> its FRP archetype.
        assert MITIGATION_RETROFIT_MAP == {"C1-M (Pre/Lo)": "C1-M (Pre/Lo) FRP"}

    def test_counts_and_cost_fraction(self):
        cov = mitigation_coverage(self._toy_inv())
        assert cov["whole"]["n_buildings"] == 5
        # Structural FRP layer: coverage-limited to C1-M (Pre/Lo).
        assert cov["whole"]["n_retrofitted"] == 3
        assert cov["whole"]["fraction_retrofitted_by_count"] == pytest.approx(3 / 5)
        assert cov["whole"]["fraction_retrofitted_by_cost"] == pytest.approx(300 / 500)
        # City split.
        assert cov["MC"]["n_retrofitted"] == 2  # b1, b2 (b5 is CHB-L)
        assert cov["QC"]["n_retrofitted"] == 1  # b3

    def test_nonstructural_layer_is_portfolio_wide(self):
        """The NON-structural injury-reduction layer is NOT coverage-limited: every
        building carrying an upgradeable acceleration/drift-sensitive non-structural
        component is upgraded (here all 5 archetypes carry ceilings/fixtures/CHB)."""
        cov = mitigation_coverage(self._toy_inv())
        # All toy archetypes (C1-M (Pre/Lo), C1-M (Hi), CHB-L) carry at least one
        # upgradeable NS component, so the non-structural layer reaches all 5.
        assert cov["whole"]["n_nonstructural_upgraded"] == 5
        assert cov["whole"]["fraction_nonstructural_upgraded"] == pytest.approx(1.0)
        # The map exposes the substitution + removal sets (data-driven, Table 6-3).
        assert cov["nonstructural_substitutions"]["PH.NS.FIX.NS"] == "PH.NS.FIX.SE"
        assert cov["nonstructural_substitutions"]["PH.NS.CLG.NS"] == "PH.NS.CLG.BR"
        assert "PH.NS.ELEC.DT" in cov["nonstructural_removed"]
        assert "PH.NS.ELEC.WM" in cov["nonstructural_removed"]

    def test_empty_inventory_safe(self):
        empty = pd.DataFrame(
            {"building_id": [], "city": [], "archetype": [], "replacement_cost_php": []}
        )
        cov = mitigation_coverage(empty)
        assert cov["whole"]["n_buildings"] == 0
        assert cov["whole"]["fraction_retrofitted_by_cost"] == 0.0
        assert cov["whole"]["n_nonstructural_upgraded"] == 0


@pytest.fixture(scope="module")
def real_wvf_mitigated_result():
    """Run the real-data WVF_7.3 scenario with the FRP retrofit applied (small N)."""
    if not _real_scenario_available():
        pytest.skip("Real inventory / WVF_7.3 distance table absent (gitignored).")
    sp = ScenarioPortfolio.mitigated_from_real_inventory(
        scenario_id="WVF_7.3", n_realizations=N_REAL_TEST, seed=12345
    )
    return sp.run(progress_every=0)


@pytest.mark.integration
@requires_real_scenario
class TestScenarioMitigatedRealData:
    """The mitigated path applies BOTH layers: STRUCTURAL FRP (C1-M (Pre/Lo) only ->
    collapse/fatality reduction) and NON-STRUCTURAL component upgrade (portfolio-wide ->
    injury reduction). Collapse is touched ONLY by the structural layer; loss + injuries
    are touched by both."""

    def test_mitigated_flag_propagates(self, real_wvf_mitigated_result):
        r = real_wvf_mitigated_result
        assert r.mitigated is True
        s = summarise_scenario_result(r)
        assert s["mitigated"] is True
        assert s["mitigation"]["applied"] is True
        assert s["mitigation"]["structural_frp"]["retrofit_map"] == {
            "C1-M (Pre/Lo)": "C1-M (Pre/Lo) FRP"
        }
        # The non-structural layer is present and reports its component swap.
        ns = s["mitigation"]["nonstructural"]
        assert ns["substitutions"]["PH.NS.FIX.NS"] == "PH.NS.FIX.SE"
        assert "PH.NS.ELEC.DT" in ns["removed"]

    def test_base_flag_default_false(self, real_wvf_result):
        assert real_wvf_result.mitigated is False
        assert summarise_scenario_result(real_wvf_result)["mitigated"] is False

    def test_retrofit_reduces_c1m_prelo_collapse(self, real_wvf_result, real_wvf_mitigated_result):
        """STRUCTURAL FRP (collapse Sa 1.11 g -> 2.12 g) must cut C1-M (Pre/Lo) collapse."""
        inv = real_wvf_result.inventory
        m = (inv["archetype"] == "C1-M (Pre/Lo)").to_numpy()
        assert m.sum() == 71  # 20 MC + 51 QC
        base_cr = float(real_wvf_result.collapse_mask[m].mean())
        mit_cr = float(real_wvf_mitigated_result.collapse_mask[m].mean())
        assert mit_cr < base_cr, f"FRP collapse {mit_cr:.3f} !< base {base_cr:.3f}"

    def test_retrofit_reduces_c1m_prelo_loss(self, real_wvf_result, real_wvf_mitigated_result):
        inv = real_wvf_result.inventory
        m = (inv["archetype"] == "C1-M (Pre/Lo)").to_numpy()
        base_lr = float(real_wvf_result.loss_ratio[m].mean())
        mit_lr = float(real_wvf_mitigated_result.loss_ratio[m].mean())
        assert mit_lr < base_lr

    def test_collapse_unchanged_for_nonstructural_only_buildings(
        self, real_wvf_result, real_wvf_mitigated_result
    ):
        """The non-structural layer must NOT change collapse. Every building NOT in the
        STRUCTURAL retrofit map keeps a byte-identical collapse mask (same seed, same
        hazard field, same EDPs) between base and mitigated runs — only its loss +
        injuries may change (from the component swap)."""
        inv = real_wvf_result.inventory
        non_struct = ~inv["archetype"].isin(MITIGATION_RETROFIT_MAP).to_numpy()
        assert non_struct.sum() == 1021 - 71
        np.testing.assert_array_equal(
            real_wvf_result.collapse_mask[non_struct],
            real_wvf_mitigated_result.collapse_mask[non_struct],
        )

    def test_nonstructural_reduces_injuries_portfolio_wide(
        self, real_wvf_result, real_wvf_mitigated_result
    ):
        """The non-structural upgrade reduces NON-collapse injuries for buildings OUTSIDE
        the structural-FRP set too (its collapse is unchanged, so any injury reduction
        there is purely the component swap / injury layer). This is the headline
        non-structural benefit and is what the prior structural-only model missed."""
        inv = real_wvf_result.inventory
        non_struct = ~inv["archetype"].isin(MITIGATION_RETROFIT_MAP).to_numpy()
        base_r, mit_r = real_wvf_result, real_wvf_mitigated_result
        base_nc = float(base_r.injuries_noncollapse[non_struct].sum(axis=0).mean())
        mit_nc = float(mit_r.injuries_noncollapse[non_struct].sum(axis=0).mean())
        assert mit_nc < base_nc, f"NS injury layer not reducing NC injuries: {mit_nc} !< {base_nc}"
        # And the whole-portfolio total injuries must drop too.
        base_inj = float(np.median(base_r.injuries.sum(axis=0)))
        mit_inj = float(np.median(mit_r.injuries.sum(axis=0)))
        assert mit_inj < base_inj

    def test_mitigated_portfolio_loss_not_above_base(
        self, real_wvf_result, real_wvf_mitigated_result
    ):
        """Both mitigation layers can only reduce (or hold) the whole-portfolio median loss."""
        base_med = float(np.median(real_wvf_result.portfolio_loss_ratio))
        mit_med = float(np.median(real_wvf_mitigated_result.portfolio_loss_ratio))
        assert mit_med <= base_med + 1e-9

    def test_summary_coverage_block_consistent(self, real_wvf_mitigated_result):
        s = summarise_scenario_result(real_wvf_mitigated_result)
        cov = s["mitigation"]["structural_frp"]["coverage"]
        assert cov["whole"]["n_retrofitted"] == 71
        assert cov["makati_MC"]["n_retrofitted"] == 20
        assert cov["quezon_QC"]["n_retrofitted"] == 51
        # Honest STRUCTURAL coverage: a SMALL fraction of total replacement value.
        assert cov["whole"]["fraction_retrofitted_by_cost"] < 0.20
        # Non-structural layer reaches essentially the whole portfolio.
        assert cov["whole"]["n_nonstructural_upgraded"] > 900
        # Identifier-free.
        assert "building_id" not in json.dumps(s)


# ===========================================================================
# Multi-scenario breadth (P7) — the 4 non-WVF-7.3 thesis scenarios.
# Crustal (WVF-6.5, EVF-6.6, GNW-7.2) + subduction interface (Manila Trench).
# Live run is gated on the gitignored real inventory + each distance table;
# the committed result-JSON checks run unconditionally (validate the N=1000 output).
# ===========================================================================

_BREADTH_SCENARIOS = ["WVF_6.5", "EVF_6.6", "GNW_7.2", "MnlTrench_8.15"]


def _scenario_distance_available(scenario_id: str) -> bool:
    from bayanihan.hazard import _load_distance_table
    try:
        _load_distance_table(scenario_id)
        return True
    except FileNotFoundError:
        return False


def _breadth_live_available() -> bool:
    try:
        _load_real_inventory()
    except FileNotFoundError:
        return False
    return all(_scenario_distance_available(s) for s in _BREADTH_SCENARIOS)


requires_breadth_live = pytest.mark.skipif(
    not _breadth_live_available(),
    reason="Real inventory or one/more breadth distance tables absent (gitignored).",
)

_RESULTS_DIR = Path(__file__).resolve().parent.parent / "bayanihan" / "data" / "results"
_BREADTH_RESULT_TAGS = {
    "WVF_6.5": "wvf65",
    "WVF_7.3": "wvf73",
    "EVF_6.6": "evf66",
    "GNW_7.2": "gnw72",
    "MnlTrench_8.15": "mnlt815",
}


def _breadth_results_available() -> bool:
    return all(
        (_RESULTS_DIR / f"{tag}_portfolio_summary.json").is_file()
        for tag in _BREADTH_RESULT_TAGS.values()
    )


requires_breadth_results = pytest.mark.skipif(
    not _breadth_results_available(),
    reason="One or more committed scenario result JSONs absent "
    "(run scripts/run_scenario_breadth.py).",
)


@pytest.mark.integration
@requires_breadth_live
class TestBreadthScenarioPortfolios:
    """Each breadth scenario runs end-to-end through the correlated pipeline (small N)."""

    @pytest.mark.parametrize("scenario_id", _BREADTH_SCENARIOS)
    def test_runs_end_to_end(self, scenario_id):
        sp = ScenarioPortfolio.from_real_inventory(
            scenario_id=scenario_id, n_realizations=8, seed=12345
        )
        r = sp.run(progress_every=0)
        assert r.loss_ratio.shape == (1021, 8)
        assert np.all(r.loss_ratio >= 0.0) and np.all(r.loss_ratio <= 1.0)
        assert not np.any(np.isnan(r.portfolio_loss_ratio))

    def test_subduction_interface_runs_and_summarises(self):
        """Manila Trench (subduction interface) runs AND summarises with no NaNs.

        This is the key new path: the 4-branch interface GMPE logic tree
        (Youngs97 / AB03 / Zhao06-SInter / BC-Hydro) feeding the full
        loss + casualty + recovery aggregation.
        """
        sp = ScenarioPortfolio.from_real_inventory(
            scenario_id="MnlTrench_8.15", n_realizations=8, seed=12345
        )
        r = sp.run(progress_every=0)
        s = summarise_scenario_result(r)
        assert s["scenario_id"] == "MnlTrench_8.15"
        # Far-field subduction: loss is real but well below the near-fault WVF cases.
        assert 0.0 < s["whole_portfolio"]["loss_ratio"]["mean"] < 0.5
        # Aggregates present + finite.
        for blk in ("whole_portfolio", "makati_MC", "quezon_QC"):
            lr = s[blk]["loss_ratio"]
            assert np.isfinite(lr["median"]) and np.isfinite(lr["p90"])
        # Identifier-free committable summary.
        assert "building_id" not in json.dumps(s)


@requires_breadth_results
class TestBreadthResultsAndGovernance:
    """Validate the committed N=1000 scenario summaries + the governance ordering."""

    @staticmethod
    def _load(tag: str) -> dict:
        return json.loads((_RESULTS_DIR / f"{tag}_portfolio_summary.json").read_text())

    @pytest.mark.parametrize("scenario_id,tag", list(_BREADTH_RESULT_TAGS.items()))
    def test_summary_well_formed(self, scenario_id, tag):
        s = self._load(tag)
        assert s["scenario_id"] == scenario_id
        assert s["n_buildings"] == 1021
        assert s["n_realizations"] == 1000
        lr = s["whole_portfolio"]["loss_ratio"]
        assert 0.0 <= lr["median"] <= 1.0
        assert lr["p90"] >= lr["median"]
        # No raw per-building identifiers leaked into the committable aggregate.
        assert "building_id" not in json.dumps(s)

    def test_wvf73_governs(self):
        """WVF-7.3 has the highest whole-portfolio median loss (thesis: it governs)."""
        med = {
            sid: self._load(tag)["whole_portfolio"]["loss_ratio"]["median"]
            for sid, tag in _BREADTH_RESULT_TAGS.items()
        }
        assert med["WVF_7.3"] == max(med.values()), (
            f"WVF-7.3 should govern (highest whole-portfolio median loss); got {med}"
        )
        # Same-fault magnitude ordering and far-field attenuation.
        assert med["WVF_7.3"] > med["WVF_6.5"], "WVF-7.3 should exceed WVF-6.5"
        assert med["WVF_6.5"] > med["GNW_7.2"], "near-fault WVF-6.5 should exceed far-field GNW"

    def test_far_field_lower_than_near_fault(self):
        """The far-field crustal GNW is the least severe of the five scenarios."""
        med = {
            sid: self._load(tag)["whole_portfolio"]["loss_ratio"]["median"]
            for sid, tag in _BREADTH_RESULT_TAGS.items()
        }
        assert med["GNW_7.2"] == min(med.values()), (
            f"GNW-7.2 (far-field crustal) should be the least severe; got {med}"
        )
