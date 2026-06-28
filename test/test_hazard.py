"""Tests for bayanihan/hazard.py.

Covers:
  - HazardModel is abstract; ThesisHazardModel is concrete.
  - sample_im returns (n_sims, n_sites), strictly positive.
  - Median IM decreases with source distance.
  - Loth-Baker matrix: symmetric, unit diagonal, PSD, decreasing with distance.
  - Reproducibility with seed.
  - WVF Mw=7.3 scenario smoke test over ~10 Metro Manila sites.
"""
from __future__ import annotations

import numpy as np
import pytest

from bayanihan.hazard import (
    _CRUSTAL_GSIMS,
    _INTERFACE_GSIMS,
    _SCENARIO_BRANCHES,
    HazardModel,
    ThesisHazardModel,
    _load_distance_table,
    _load_inventory_coords,
    _load_scenarios,
    loth_baker_correlation,
    loth_baker_cross_correlation,
    scenario_sa_field,
)


def _wvf_data_available() -> bool:
    """True iff the WVF_7.3 distance table and real inventory are both present."""
    try:
        _load_distance_table("WVF_7.3")
        _load_inventory_coords()
        return True
    except (FileNotFoundError, ValueError):
        return False


requires_wvf_data = pytest.mark.skipif(
    not _wvf_data_available(),
    reason="WVF_7.3 distance table or real inventory geojson not present "
    "(gitignored source); run utils/build_wvf_distance_table.py",
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

WVF_RUPTURE_B = dict(
    mw=7.3,
    mechanism="crustal",
    depth=15.0,
    dip=90.0,
    rake=0.0,
    lat=14.55,
    lon=121.05,
)

# ~10 Metro Manila sites spanning Makati and Quezon City
METRO_MANILA_SITES = np.array([
    # lat, lon, vs30 (m/s)
    [14.5547, 121.0244, 450.0],  # Makati — near fault
    [14.5600, 121.0500, 520.0],
    [14.5700, 121.0700, 560.0],
    [14.5800, 121.0900, 580.0],
    [14.5900, 121.1100, 610.0],
    [14.6000, 121.1300, 640.0],
    [14.6200, 121.1500, 660.0],  # Quezon City — farther from fault
    [14.6400, 121.0400, 500.0],
    [14.6600, 121.0600, 530.0],
    [14.6800, 121.0800, 560.0],
])

# Simple 3-site array without Vs30 column (uses default)
THREE_SITES = np.array([
    [14.52, 121.02],
    [14.58, 121.08],
    [14.45, 121.15],
])


# ---------------------------------------------------------------------------
# Abstract base class tests
# ---------------------------------------------------------------------------

class TestHazardModelAbstract:
    def test_abstract_cannot_instantiate(self):
        """HazardModel is an ABC and cannot be instantiated directly."""
        with pytest.raises(TypeError):
            HazardModel()

    def test_thesis_model_is_hazard_model(self):
        """ThesisHazardModel is a concrete subclass."""
        model = ThesisHazardModel()
        assert isinstance(model, HazardModel)


# ---------------------------------------------------------------------------
# sample_im output shape and value tests
# ---------------------------------------------------------------------------

class TestSampleIM:
    @pytest.fixture
    def model(self):
        return ThesisHazardModel(im_period=1.0)

    def test_output_shape(self, model):
        """sample_im returns (n_simulations, n_sites)."""
        n_sim, n_sites = 50, 10
        sa = model.sample_im(WVF_RUPTURE_B, METRO_MANILA_SITES, n_simulations=n_sim, seed=0)
        assert sa.shape == (n_sim, n_sites)

    def test_strictly_positive(self, model):
        """All returned Sa values are strictly positive."""
        sa = model.sample_im(WVF_RUPTURE_B, METRO_MANILA_SITES, n_simulations=200, seed=1)
        assert np.all(sa > 0), "Sa must be positive; got zeros or negatives"

    def test_no_nans_or_infs(self, model):
        """No NaN or infinite values in output."""
        sa = model.sample_im(WVF_RUPTURE_B, METRO_MANILA_SITES, n_simulations=100, seed=2)
        assert np.all(np.isfinite(sa))

    def test_sites_without_vs30(self, model):
        """Sites array with only lat/lon (no Vs30 column) is accepted."""
        sa = model.sample_im(WVF_RUPTURE_B, THREE_SITES, n_simulations=20, seed=3)
        assert sa.shape == (20, 3)
        assert np.all(sa > 0)

    def test_single_site(self, model):
        """Works with a single site."""
        one_site = np.array([[14.55, 121.05, 560.0]])
        sa = model.sample_im(WVF_RUPTURE_B, one_site, n_simulations=10, seed=4)
        assert sa.shape == (10, 1)
        assert np.all(sa > 0)

    def test_rrup_rjb_input(self, model):
        """Accepts explicit rrup/rjb instead of source lat/lon."""
        rupture = dict(mw=7.3, mechanism="crustal", depth=15.0, dip=90.0, rake=0.0,
                       rrup=np.array([5.0, 15.0, 30.0]),
                       rjb=np.array([5.0, 15.0, 30.0]))
        sa = model.sample_im(rupture, THREE_SITES, n_simulations=20, seed=5)
        assert sa.shape == (20, 3)
        assert np.all(sa > 0)


# ---------------------------------------------------------------------------
# Attenuation with distance
# ---------------------------------------------------------------------------

class TestAttenuation:
    """Median IM should decrease as source-to-site distance increases."""

    def test_median_decreases_with_distance(self):
        """Closer sites have higher median Sa than distant sites."""
        model = ThesisHazardModel(im_period=1.0)
        n_sim = 500

        # Two collinear site groups at different distances from source
        near_sites = np.array([[14.553, 121.048, 560.0],
                                [14.556, 121.052, 560.0]])
        far_sites = np.array([[14.650, 121.200, 560.0],
                               [14.700, 121.250, 560.0]])

        rupture = dict(mw=7.3, mechanism="crustal", depth=15.0,
                       lat=14.55, lon=121.05)

        sa_near = model.sample_im(rupture, near_sites, n_simulations=n_sim, seed=10)
        sa_far = model.sample_im(rupture, far_sites, n_simulations=n_sim, seed=10)

        median_near = np.median(sa_near)
        median_far = np.median(sa_far)

        assert median_near > median_far, (
            f"Expected median Sa to be higher near the source "
            f"(near={median_near:.4f}g, far={median_far:.4f}g)"
        )

    def test_scalar_rrup_attenuation(self):
        """With explicit rrup, larger distance gives lower median."""
        model = ThesisHazardModel(im_period=1.0)
        n_sim = 500
        site = np.array([[14.55, 121.05, 560.0]])

        def median_at_distance(rrup_km):
            rup = dict(mw=7.3, mechanism="crustal", depth=15.0, rake=0.0,
                       rrup=np.array([rrup_km]), rjb=np.array([rrup_km]))
            sa = model.sample_im(rup, site, n_simulations=n_sim, seed=20)
            return float(np.median(sa))

        m5 = median_at_distance(5.0)
        m20 = median_at_distance(20.0)
        m60 = median_at_distance(60.0)

        assert m5 > m20 > m60, (
            f"Attenuation check failed: {m5:.4f} > {m20:.4f} > {m60:.4f}"
        )


# ---------------------------------------------------------------------------
# Loth-Baker correlation tests
# ---------------------------------------------------------------------------

class TestLothBakerCorrelation:
    """Matrix properties as required by Loth & Baker (2013)."""

    def test_unit_diagonal(self):
        """Diagonal elements must all be 1.0."""
        d = np.array([[0, 5, 20], [5, 0, 15], [20, 15, 0]], dtype=float)
        C = loth_baker_correlation(1.0, 1.0, d)
        assert np.allclose(np.diag(C), 1.0), "Diagonal must be 1"

    def test_symmetric(self):
        """Matrix must be symmetric."""
        d = np.array([[0, 5, 20], [5, 0, 15], [20, 15, 0]], dtype=float)
        C = loth_baker_correlation(1.0, 1.0, d)
        assert np.allclose(C, C.T, atol=1e-10)

    def test_positive_semidefinite(self):
        """All eigenvalues must be >= 0 (PSD)."""
        n = 8
        # Randomly spaced sites across 50 km
        rng = np.random.default_rng(0)
        coords = rng.uniform(0, 50, (n, 2))
        diff = coords[:, None, :] - coords[None, :, :]
        d = np.sqrt((diff**2).sum(axis=-1))
        C = loth_baker_correlation(1.0, 1.0, d)
        eigvals = np.linalg.eigvalsh(C)
        assert np.all(eigvals >= -1e-8), f"Negative eigenvalue detected: {eigvals.min():.3e}"

    def test_correlation_decreases_with_distance(self):
        """Off-diagonal entries decrease as separation increases."""
        d_near = 2.0
        d_far = 50.0
        d_near_mat = np.array([[0, d_near], [d_near, 0]], dtype=float)
        d_far_mat = np.array([[0, d_far], [d_far, 0]], dtype=float)
        C_near = loth_baker_correlation(1.0, 1.0, d_near_mat)
        C_far = loth_baker_correlation(1.0, 1.0, d_far_mat)
        assert C_near[0, 1] > C_far[0, 1], (
            f"Closer sites must be more correlated: {C_near[0,1]:.3f} vs {C_far[0,1]:.3f}"
        )

    def test_cross_period_correlation(self):
        """Cross-period correlation at zero distance equals LB13 nugget contribution."""
        d_zero = np.array([[0.0, 0.0], [0.0, 0.0]])
        C = loth_baker_correlation(0.5, 1.0, d_zero)
        # At h=0, all four entries should be equal (no distance dependence)
        assert np.allclose(C[0, 0], C[0, 1]), "Zero-distance cross-period should be uniform"

    def test_values_bounded(self):
        """All correlation values must lie in [-1, 1]."""
        n = 10
        rng = np.random.default_rng(7)
        coords = rng.uniform(0, 100, (n, 2))
        diff = coords[:, None, :] - coords[None, :, :]
        d = np.sqrt((diff**2).sum(axis=-1))
        for T in [0.1, 0.5, 1.0, 2.0]:
            C = loth_baker_correlation(T, T, d)
            assert np.all(C >= -1) and np.all(C <= 1), f"Values out of bounds at T={T}"


# ---------------------------------------------------------------------------
# Reproducibility
# ---------------------------------------------------------------------------

class TestReproducibility:
    def test_same_seed_same_output(self):
        """Two calls with the same seed return identical results."""
        model = ThesisHazardModel(im_period=1.0)
        sa1 = model.sample_im(WVF_RUPTURE_B, METRO_MANILA_SITES, n_simulations=50, seed=99)
        sa2 = model.sample_im(WVF_RUPTURE_B, METRO_MANILA_SITES, n_simulations=50, seed=99)
        np.testing.assert_array_equal(sa1, sa2)

    def test_different_seeds_different_output(self):
        """Different seeds produce different (but statistically similar) results."""
        model = ThesisHazardModel(im_period=1.0)
        sa1 = model.sample_im(WVF_RUPTURE_B, METRO_MANILA_SITES, n_simulations=50, seed=1)
        sa2 = model.sample_im(WVF_RUPTURE_B, METRO_MANILA_SITES, n_simulations=50, seed=2)
        assert not np.allclose(sa1, sa2), "Different seeds must not produce identical arrays"


# ---------------------------------------------------------------------------
# WVF Mw=7.3 smoke test
# ---------------------------------------------------------------------------

class TestWVFScenarioB:
    """WVF Mw≈7.3 scenario (Scenario B, Table 7-2, Jeswani 2021).

    Verifies the model runs end-to-end with realistic Metro Manila sites
    and produces plausible Sa(1.0s) values.
    """

    def test_wvf_b_runs_and_passes_sanity(self):
        model = ThesisHazardModel(im_period=1.0)
        sa = model.sample_im(WVF_RUPTURE_B, METRO_MANILA_SITES, n_simulations=500, seed=2021)

        assert sa.shape == (500, 10)
        assert np.all(sa > 0)
        assert np.all(np.isfinite(sa))

        # Plausibility: median Sa(1s) for near-fault Mw7.3 on stiff soil
        # should be in roughly 0.1g – 2.0g range (broad sanity check)
        median_sa = np.median(sa)
        assert 0.05 <= median_sa <= 3.0, f"Implausible median Sa: {median_sa:.4f}g"

    def test_wvf_b_spatial_pattern(self):
        """Sites closer to the fault should tend to have higher Sa."""
        model = ThesisHazardModel(im_period=1.0)
        n_sim = 1000
        sa = model.sample_im(WVF_RUPTURE_B, METRO_MANILA_SITES, n_simulations=n_sim, seed=42)

        # METRO_MANILA_SITES[0] is nearest to the WVF (lat=14.5547, near fault at 14.55)
        # METRO_MANILA_SITES[-1] is farthest (lat=14.68)
        median_near = float(np.median(sa[:, 0]))
        median_far = float(np.median(sa[:, -1]))

        # Near fault should be higher on average (allow for Vs30 differences)
        # Not a strict inequality since Vs30 also varies, but expect near > far
        assert median_near > median_far * 0.7, (
            f"Near-fault site should not be dramatically lower than far site: "
            f"near={median_near:.3f}g, far={median_far:.3f}g"
        )

    def test_interface_mechanism(self):
        """Interface scenario (Manila Trench) also runs without error."""
        model = ThesisHazardModel(im_period=1.0)
        rupture_e = dict(
            mw=7.9,
            mechanism="interface",
            depth=20.0,
            lat=14.7,
            lon=119.5,  # Manila Trench, ~110 km west
        )
        sa = model.sample_im(rupture_e, METRO_MANILA_SITES, n_simulations=100, seed=7)
        assert sa.shape == (100, 10)
        assert np.all(sa > 0)


# ---------------------------------------------------------------------------
# Parameter variation tests
# ---------------------------------------------------------------------------

class TestPeriodVariation:
    """Model should work across a range of spectral periods."""

    @pytest.mark.parametrize("period", [0.1, 0.5, 1.0, 2.0])
    def test_various_periods(self, period):
        model = ThesisHazardModel(im_period=period)
        sa = model.sample_im(WVF_RUPTURE_B, THREE_SITES, n_simulations=50, seed=0)
        assert sa.shape == (50, 3)
        assert np.all(sa > 0)
        assert np.all(np.isfinite(sa))


# ---------------------------------------------------------------------------
# Loth-Baker multi-period cross-correlation
# ---------------------------------------------------------------------------

class TestLothBakerCrossCorrelation:
    """Multi-period spatial correlation matrix (heterogeneous building T1)."""

    @staticmethod
    def _dist_matrix(coords: np.ndarray) -> np.ndarray:
        diff = coords[:, None, :] - coords[None, :, :]
        return np.sqrt((diff ** 2).sum(axis=-1))

    def test_unit_diagonal(self):
        """Diagonal renormalised to exactly 1.0 even at interpolated periods."""
        periods = np.array([0.297, 0.45165, 0.646, 1.319])
        d = self._dist_matrix(np.array([[0, 0], [3, 4], [10, 0], [0, 12]], float))
        C = loth_baker_cross_correlation(periods, d)
        assert np.allclose(np.diag(C), 1.0)

    def test_symmetric(self):
        periods = np.array([0.138, 0.45165, 0.842])
        d = self._dist_matrix(np.array([[0, 0], [5, 5], [12, 3]], float))
        C = loth_baker_cross_correlation(periods, d)
        assert np.allclose(C, C.T, atol=1e-10)

    def test_positive_semidefinite(self):
        """Realistic 8-period heterogeneous portfolio is PSD."""
        rng = np.random.default_rng(0)
        periods_pool = np.array([0.138, 0.297, 0.3665, 0.39665, 0.45165, 0.646, 0.842, 1.319])
        n = 80
        periods = rng.choice(periods_pool, n)
        coords = rng.uniform(0, 25, (n, 2))
        d = self._dist_matrix(coords)
        C = loth_baker_cross_correlation(periods, d)
        eig = np.linalg.eigvalsh(C)
        assert eig.min() >= -1e-8, f"not PSD: min eig = {eig.min():.3e}"

    def test_correlation_decreases_with_distance_same_period(self):
        """Two sites at the same period: closer => more correlated."""
        periods = np.array([0.5, 0.5])
        C_near = loth_baker_cross_correlation(periods, np.array([[0, 2.0], [2.0, 0]]))
        C_far = loth_baker_cross_correlation(periods, np.array([[0, 50.0], [50.0, 0]]))
        assert C_near[0, 1] > C_far[0, 1]

    def test_matches_single_period_offdiagonal(self):
        """When all periods equal, off-diagonals match loth_baker_correlation."""
        T = 0.646
        coords = np.array([[0, 0], [4, 3], [10, 10]], float)
        d = self._dist_matrix(coords)
        C_multi = loth_baker_cross_correlation(np.full(3, T), d)
        C_single = loth_baker_correlation(T, T, d)
        # Off-diagonals should match (diagonal differs: single uses b1+b2+b3,
        # multi renormalises to 1.0)
        iu = np.triu_indices(3, k=1)
        assert np.allclose(C_multi[iu], C_single[iu], atol=1e-12)

    def test_cross_period_decorrelates_at_zero_distance(self):
        """At h=0, far-apart periods decorrelate (<= same-period unit value).

        Note: the published LB13 Table-1 coefficients give b1+b2+b3 ~= 1.0 for
        some adjacent period pairs (a known internal-consistency artefact of the
        table), so we use a widely-separated pair (0.1 s vs 5.0 s) where the
        cross-period h=0 correlation is clearly below 1.
        """
        periods = np.array([0.1, 5.0])
        d = np.zeros((2, 2))
        C = loth_baker_cross_correlation(periods, d)
        assert np.isclose(C[0, 0], 1.0) and np.isclose(C[1, 1], 1.0)
        assert C[0, 1] < 1.0, "far-apart periods should decorrelate at h=0"
        assert C[0, 1] > 0.0
        # And the cross-period h=0 value never exceeds the same-period unit value.
        assert C[0, 1] <= 1.0 + 1e-12

    def test_marginal_correlation_recovered_by_sampling(self):
        """Cholesky-sampled fields reproduce the target correlation matrix."""
        rng = np.random.default_rng(7)
        periods = np.array([0.297, 0.646, 1.319, 0.45165])
        coords = np.array([[0, 0], [3, 4], [8, 0], [0, 6]], float)
        d = self._dist_matrix(coords)
        C = loth_baker_cross_correlation(periods, d)
        L = np.linalg.cholesky(C)
        z = rng.standard_normal((200_000, 4))
        field = z @ L.T
        emp = np.corrcoef(field, rowvar=False)
        assert np.allclose(emp, C, atol=0.02), (
            f"empirical correlation off target:\n{emp}\nvs\n{C}"
        )


# ---------------------------------------------------------------------------
# scenario_sa_field — thesis-faithful WVF 7.3 field
# ---------------------------------------------------------------------------

@requires_wvf_data
class TestScenarioSaField:
    """Building_id-indexed Sa(T1) field with thesis WVF distances + LB13."""

    def test_shape_and_columns(self):
        df = scenario_sa_field("WVF_7.3", n_realizations=100, seed=1)
        assert df.shape == (100, 1021)
        # Columns are building_ids; index labelled realization
        assert df.index.name == "realization"
        assert all(isinstance(c, str) for c in df.columns)
        assert df.columns.is_unique

    def test_positive_and_finite(self):
        df = scenario_sa_field("WVF_7.3", n_realizations=100, seed=2)
        v = df.to_numpy()
        assert np.all(v > 0)
        assert np.all(np.isfinite(v))

    def test_reproducible_with_seed(self):
        a = scenario_sa_field("WVF_7.3", n_realizations=50, seed=99)
        b = scenario_sa_field("WVF_7.3", n_realizations=50, seed=99)
        np.testing.assert_array_equal(a.to_numpy(), b.to_numpy())

    def test_columns_match_inventory_ids(self):
        df = scenario_sa_field("WVF_7.3", n_realizations=10, seed=0)
        coords = _load_inventory_coords()
        assert set(df.columns) == set(coords.index), (
            "Sa-field columns must be exactly the inventory building_ids"
        )

    def test_median_field_plausible(self):
        """Logic-tree median Sa(T1) sane for near-fault Mw7.3 crustal event."""
        _, comp = scenario_sa_field("WVF_7.3", n_realizations=10, seed=0,
                                    return_components=True)
        med = comp["sa_median"]
        assert 0.1 < np.median(med) < 1.5, f"implausible median {np.median(med):.3f}g"
        assert med.min() > 0.05
        assert med.max() < 4.0

    def test_aleatory_sigma_single_gmpe_magnitude(self):
        """tau/phi must NOT be RSS-collapsed; total ln-sigma ~0.5-0.8 (NGA)."""
        _, comp = scenario_sa_field("WVF_7.3", n_realizations=10, seed=0,
                                    return_components=True)
        total = np.sqrt(comp["tau"] ** 2 + comp["phi"] ** 2)
        assert 0.45 < np.median(total) < 0.85, (
            f"aleatory sigma {np.median(total):.3f} not at single-GMPE magnitude "
            "(RSS-of-weighted would give ~0.32)"
        )

    def test_realized_dispersion_recovers_target_sigma(self):
        """Realized per-building ln-sigma matches the target total sigma."""
        df, comp = scenario_sa_field("WVF_7.3", n_realizations=4000, seed=3,
                                     return_components=True)
        ln = np.log(df.to_numpy())
        realized_sigma = ln.std(axis=0)
        target = np.sqrt(comp["tau"] ** 2 + comp["phi"] ** 2)
        # Per-building realized sigma should track target within sampling noise
        assert np.allclose(np.median(realized_sigma), np.median(target), atol=0.03)

    def test_inter_event_is_common_across_buildings(self):
        """Removing the per-realization mean leaves only intra-event scatter.

        The inter-event residual is shared by all buildings, so the realization-
        to-realization variation of the cross-building mean of (lnSa - lnMedian)
        should be ~tau, materially larger than if it were independent per site.
        """
        df, comp = scenario_sa_field("WVF_7.3", n_realizations=5000, seed=4,
                                     return_components=True)
        ln = np.log(df.to_numpy())
        resid = ln - comp["ln_median"][None, :]      # (n_real, n_bldg)
        mean_resid = resid.mean(axis=1)              # cross-building mean per realization
        # Std of the common component ~ median tau (intra averages out over 1021)
        assert mean_resid.std() > 0.5 * np.median(comp["tau"]), (
            "inter-event component too weak — is the common residual being drawn?"
        )

    def test_distance_attenuation_within_period(self):
        """Within a fixed T1, median Sa is strongly anti-correlated with Rrup."""
        _, comp = scenario_sa_field("WVF_7.3", n_realizations=10, seed=0,
                                    return_components=True)
        T = comp["period_s"]
        rrup = comp["rrup_km"]
        med = comp["sa_median"]
        # Use the most populated period band
        vals, counts = np.unique(np.round(T, 5), return_counts=True)
        pmode = vals[counts.argmax()]
        m = np.isclose(T, pmode)
        r = np.corrcoef(rrup[m], np.log(med[m]))[0, 1]
        assert r < -0.7, f"closer should be hotter; corr(Rrup,lnSa)={r:.3f}"

    def test_unknown_scenario_raises(self):
        with pytest.raises(KeyError):
            scenario_sa_field("NOPE_9.9", n_realizations=5)

    def test_conditioning_im_is_per_archetype_sa_t1_not_sa05(self):
        """Lock the thesis intensity-measure basis: per-archetype Sa(T1), not Sa(0.5s).

        The thesis IM is documented as ``Sa(T1) = Sa(0.5s)`` (Ch.7 Key-Parameter
        table). Investigation (docs/learnings/2026-06-27_im_sa05_reconciliation.md)
        established that ``Sa(0.5s)`` is only a *representative portfolio label*
        (count-weighted mean T1 = 0.457 s; Figure 7-3 plots one Sa(0.5s) map),
        while the loss computation conditions EACH building's vulnerability surface
        on that building's OWN fundamental period — the EDP-Manager workbook states
        it outright ("Sa(T1), NOT Te"), and the per-archetype EDP stripe-Sa ladders
        differ by T1 (they would be identical on a shared Sa(0.5s) basis).

        This test guards against a regression that "aligns" the hazard field to a
        single Sa(0.5s) for every building: that would break the per-T1 consistency
        between the hazard field and the EDP stripe conditioning. The field's
        distinct conditioning periods must (a) be the archetype T1 set, and
        (b) contain values away from 0.5 s — i.e. NOT collapsed to a common 0.5 s.
        """
        _, comp = scenario_sa_field(
            "WVF_7.3", n_realizations=5, seed=0, return_components=True
        )
        periods = np.round(np.unique(comp["period_s"]), 5)
        # The thesis archetype T1 set (EDP-Manager BLDGs row "T1,code" /
        # BldgSpec_Inp period column). The field must draw from THIS set.
        workbook_t1 = np.array(
            [0.138, 0.297, 0.3665, 0.39665, 0.45165, 0.4747, 0.646, 0.842, 1.319]
        )
        for p in periods:
            assert np.min(np.abs(workbook_t1 - p)) < 0.01, (
                f"hazard conditioning period {p}s is not a thesis archetype T1 — "
                "the field must condition each building on its own Sa(T1)"
            )
        # Heterogeneous periods spanning short→long: NOT a single forced Sa(0.5s).
        assert periods.size >= 5, (
            "expected the full archetype-T1 spread; a single period would mean the "
            "field was collapsed onto a common Sa(0.5s) basis (wrong — breaks "
            "consistency with the per-T1 EDP stripe conditioning)"
        )
        assert periods.min() < 0.3 and periods.max() > 0.8, (
            "conditioning periods should span well below and above 0.5 s "
            f"(got {periods.min()}–{periods.max()}s); a clustering at 0.5 s would "
            "indicate an erroneous Sa(0.5s) override"
        )


# ---------------------------------------------------------------------------
# Multi-scenario breadth — the 4 additional thesis scenarios (P7 breadth)
# (WVF 6.5 / EVF 6.6 / GNW 7.2 crustal; Manila Trench 8.15 subduction interface)
# ---------------------------------------------------------------------------

# Scenario ids beyond WVF-7.3 that the breadth study adds.
_BREADTH_CRUSTAL = ["WVF_6.5", "EVF_6.6", "GNW_7.2"]
_BREADTH_SUBDUCTION = "MnlTrench_8.15"
_ALL_BREADTH = [*_BREADTH_CRUSTAL, _BREADTH_SUBDUCTION]

# Expected per-building distance-table schema (shared across crustal + subduction so
# hazard._evaluate_branch_lnsa consumes them unchanged).
_DIST_COLS = {
    "building_id",
    "period_s",
    "rrup_km",
    "rjb_km",
    "ztor_km",
    "dip_deg",
    "rake_deg",
    "rx_km",
    "z1pt0_km",
    "vs30",
}


def _scenario_data_available(scenario_id: str) -> bool:
    """True iff the scenario distance table AND real inventory coords are present."""
    try:
        _load_distance_table(scenario_id)
        _load_inventory_coords()
        return True
    except (FileNotFoundError, ValueError):
        return False


def _all_breadth_available() -> bool:
    return all(_scenario_data_available(s) for s in _ALL_BREADTH)


requires_breadth_data = pytest.mark.skipif(
    not _all_breadth_available(),
    reason="One or more breadth scenario distance tables (or the real inventory) are "
    "absent (gitignored source); run utils/build_wvf_distance_table.py",
)


class TestScenarioRegistry:
    """scenarios.json + the GMPE-set registry are internally consistent."""

    def test_all_five_scenarios_registered(self):
        scen = _load_scenarios()
        for sid in ["WVF_6.5", "WVF_7.3", "EVF_6.6", "GNW_7.2", "MnlTrench_8.15"]:
            assert sid in scen, f"{sid} missing from scenarios.json"

    def test_gmpe_sets_resolve_to_a_branch(self):
        scen = _load_scenarios()
        for sid, s in scen.items():
            assert s["gmpe_set"] in _SCENARIO_BRANCHES, (
                f"{sid}: gmpe_set '{s['gmpe_set']}' has no registered GMPE branch"
            )

    def test_manila_trench_is_subduction_interface(self):
        s = _load_scenarios()["MnlTrench_8.15"]
        assert s["mechanism"] == "interface"
        assert s["gmpe_set"] == "subduction_interface_4"
        # The interface branch must be exactly the 4 interface GSIMs (not crustal).
        assert _SCENARIO_BRANCHES["subduction_interface_4"] is _INTERFACE_GSIMS

    def test_crustal_scenarios_use_crustal_branch(self):
        scen = _load_scenarios()
        for sid in ["WVF_6.5", "WVF_7.3", "EVF_6.6", "GNW_7.2"]:
            s = scen[sid]
            assert s["mechanism"] == "crustal"
            assert _SCENARIO_BRANCHES[s["gmpe_set"]] is _CRUSTAL_GSIMS

    def test_branch_weights_sum_to_one(self):
        for name, branch in _SCENARIO_BRANCHES.items():
            w = sum(weight for _gsim, weight in branch)
            assert abs(w - 1.0) < 1e-9, f"{name} weights sum to {w}, not 1.0"
            assert len(branch) == 4, f"{name} should have 4 equal branches"


@requires_breadth_data
class TestBreadthDistanceTables:
    """Per-building distance parquets for all 4 breadth scenarios share one schema."""

    @pytest.mark.parametrize("scenario_id", _ALL_BREADTH)
    def test_schema_and_size(self, scenario_id):
        df = _load_distance_table(scenario_id)
        assert set(df.columns) == _DIST_COLS, (
            f"{scenario_id} distance table columns {set(df.columns)} != {_DIST_COLS}"
        )
        assert len(df) == 1021, f"{scenario_id} expected 1021 buildings, got {len(df)}"
        assert df["building_id"].is_unique

    @pytest.mark.parametrize("scenario_id", _ALL_BREADTH)
    def test_distances_finite_and_positive(self, scenario_id):
        df = _load_distance_table(scenario_id)
        assert np.isfinite(df["rrup_km"]).all()
        assert (df["rrup_km"] > 0).all(), "Rrup must be strictly positive"
        assert (df["rjb_km"] >= 0).all(), "Rjb must be non-negative"
        assert (df["vs30"] > 0).all()
        assert (df["period_s"] > 0).all()

    def test_subduction_far_field_distances(self):
        """Manila Trench is far-field subduction: Rrup ~100-125 km (thesis range)."""
        df = _load_distance_table(_BREADTH_SUBDUCTION)
        assert df["rrup_km"].min() > 90.0, "subduction Rrup should be far-field (>90 km)"
        assert df["rrup_km"].max() < 130.0
        # Hypocentral depth carried in ztor_km column (uniform for the interface plane).
        assert df["ztor_km"].iloc[0] > 20.0, "subduction hypo depth should be ~25 km"

    def test_wvf73_near_fault_distances(self):
        """WVF-7.3 (governing) is near-fault: Rrup <10 km (thesis 0-9.5 km)."""
        df = _load_distance_table("WVF_7.3")
        assert df["rrup_km"].max() < 10.0
        assert df["rjb_km"].min() == 0.0  # Rjb floors at 0 over the rupture


@requires_breadth_data
class TestBreadthScenarioSaField:
    """scenario_sa_field evaluates for every breadth scenario incl. subduction."""

    @pytest.mark.parametrize("scenario_id", _ALL_BREADTH)
    def test_field_shape_positive_finite(self, scenario_id):
        df = scenario_sa_field(scenario_id, n_realizations=50, seed=7)
        assert df.shape == (50, 1021)
        arr = df.to_numpy()
        assert np.all(arr > 0), f"{scenario_id} produced non-positive Sa"
        assert np.all(np.isfinite(arr)), f"{scenario_id} produced non-finite Sa"

    def test_subduction_interface_branch_evaluates(self):
        """The 4 interface GSIMs (incl. Youngs97 Total-only) evaluate without error.

        Youngs et al. (1997) reports only Total sigma; the field code partitions it
        into tau/phi. A finite, positive median field with positive tau AND phi
        confirms the partition fired and all four interface GSIMs ran.
        """
        _df, comp = scenario_sa_field(
            _BREADTH_SUBDUCTION, n_realizations=20, seed=11, return_components=True
        )
        sa_med = np.exp(comp["ln_median"])
        assert np.all(np.isfinite(sa_med)) and np.all(sa_med > 0)
        assert np.all(comp["tau"] > 0), "interface inter-event sigma must be > 0"
        assert np.all(comp["phi"] > 0), "interface intra-event sigma (partitioned) must be > 0"

    def test_wvf73_governs_among_crustal_near_fault(self):
        """WVF-7.3 (the governing scenario) has the highest median Sa field.

        Thesis states WVF-7.3 governs (highest loss). At the hazard level this must
        show as the largest per-building median Sa among the crustal scenarios — same
        fault smaller Mw (WVF-6.5), and the more-distant EVF/GNW are all lower.
        """
        med = {}
        for sid in ["WVF_7.3", *_BREADTH_CRUSTAL]:
            _df, comp = scenario_sa_field(
                sid, n_realizations=20, seed=3, return_components=True
            )
            med[sid] = float(np.median(np.exp(comp["ln_median"])))
        assert med["WVF_7.3"] == max(med.values()), (
            f"WVF-7.3 should give the highest median Sa among crustal; got {med}"
        )
        # Same-fault magnitude ordering: WVF-7.3 > WVF-6.5.
        assert med["WVF_7.3"] > med["WVF_6.5"]
        # Far-field GNW is the most attenuated crustal scenario.
        assert med["GNW_7.2"] < med["EVF_6.6"]

    def test_reproducible_with_seed(self):
        a = scenario_sa_field(_BREADTH_SUBDUCTION, n_realizations=30, seed=42)
        b = scenario_sa_field(_BREADTH_SUBDUCTION, n_realizations=30, seed=42)
        assert np.allclose(a.to_numpy(), b.to_numpy())
