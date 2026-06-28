"""Portfolio-level Monte Carlo assessment with spatial correlation.

Implements the hazard + loss + recovery pipeline from Jeswani (2021) Chapter 7
for the Makati + QC school portfolio.

Key steps:
  1. Sample spatially-correlated IM field (HazardModel + Loth-Baker)
  2. Sample EDPs conditioned on IM per archetype (from saved PERFORM-3D outputs)
  3. Run Pelicun damage + loss per building
  4. Run recovery.py for repair time + recovery milestones
  5. Aggregate to portfolio-level distributions

Validation target: reproduce thesis Ch 7 WVF Mw=7.3 Makati within ±20% median.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from importlib import resources

import geopandas as gpd
import numpy as np
import pandas as pd

from bayanihan import casualties as _casualties
from bayanihan import edp as _edp
from bayanihan import recovery as _recovery
from bayanihan.building import (
    Building,
    sample_demolition,
)
from bayanihan.hazard import ThesisHazardModel, scenario_sa_field

log = logging.getLogger(__name__)

#: Worker-hours per calendar day for replacement-time -> worker_hour conversion
#: (mirrors recovery.WORKERS_PER_DAY_DEFAULT; collapse->replacement uses the
#: building's own replacement_time_days from the inventory).
WORKER_HOURS_PER_DAY = _recovery.WORKERS_PER_DAY_DEFAULT


# ---------------------------------------------------------------------------
# PLACEHOLDER(P2): Synthetic IM→EDP model
#
# This function converts Sa(g) realizations → EDP samples using a simple
# lognormal regression model with fixed, archetype-class-dependent constants.
#
# PLACEHOLDER(P2): real per-archetype EDP-vs-IM comes from saved PERFORM-3D
# NRHA outputs (Kevin's laptop). This synthetic relation is illustrative only.
# When P2 data is recovered, replace this function with:
#   edps = load_edps_from_nrha(archetype_id, sa_samples, seed)
# which reads pre-computed EDP|IM surfaces from bayanihan/data/edps/.
# ---------------------------------------------------------------------------

# Archetype-class EDP sensitivity constants
# k_d: median PID ≈ k_d * Sa(g)     [unitless drift, capped at 0.10 = collapse proxy]
# k_a: median PFA ≈ k_a * Sa(g)     [g]
# beta: lognormal dispersion on both PID and PFA
#
# Values chosen to produce plausible Metro Manila school building behaviour:
#   - Low-rise RC: moderate drift sensitivity (PID ~0.5-1% at Sa=0.2g)
#   - Mid/High-rise RC: higher drift (~0.6-1.2% at 0.2g) but stiffer acceleration
#   - Steel (S1): more flexible, higher drift
#   - CHB/masonry: drift-brittle — low collapse threshold
#   - Wood (W-L) / composite (CWS-L): moderate
#
# PLACEHOLDER(P2): These constants are SYNTHETIC for demo purposes only.

_EDP_PARAMS: dict[str, dict] = {
    # Ductile RC moment frames — post-1992 (Hi code era)
    "C1-M (Hi)":        {"k_d": 0.030, "k_a": 1.4, "beta": 0.40},
    "C1-L (Mid/Hi)":    {"k_d": 0.025, "k_a": 1.3, "beta": 0.40},
    "C1-H (Hi)":        {"k_d": 0.022, "k_a": 1.2, "beta": 0.40},
    # Mid-code RC frames
    "C1-M (Mid)":       {"k_d": 0.035, "k_a": 1.5, "beta": 0.45},
    # Pre/low-code RC frames — more vulnerable
    "C1-M (Pre/Lo)":    {"k_d": 0.045, "k_a": 1.6, "beta": 0.50},
    "C1-M (Pre/Lo) FRP":{"k_d": 0.040, "k_a": 1.5, "beta": 0.45},
    "C1-L (Pre/Lo)":    {"k_d": 0.050, "k_a": 1.7, "beta": 0.50},
    # Prestressed/precast RC
    "PTC1-M (Mid)":     {"k_d": 0.032, "k_a": 1.4, "beta": 0.42},
    "PTC1-M (Hi)":      {"k_d": 0.028, "k_a": 1.3, "beta": 0.40},
    "PTC1-M (Pre/Lo)":  {"k_d": 0.048, "k_a": 1.6, "beta": 0.50},
    # Steel moment frame — more flexible
    "S1-M (Hi)":        {"k_d": 0.038, "k_a": 1.3, "beta": 0.42},
    "S3-L":             {"k_d": 0.030, "k_a": 1.2, "beta": 0.40},
    # Concrete shear wall (C4)
    "C4-L (Lo/Mid)":    {"k_d": 0.020, "k_a": 1.6, "beta": 0.38},
    "C4-M (Mid)":       {"k_d": 0.022, "k_a": 1.5, "beta": 0.38},
    "PTC4-M (Lo)":      {"k_d": 0.025, "k_a": 1.5, "beta": 0.40},
    # CHB (concrete hollow block) masonry — low collapse threshold
    "CHB-L":            {"k_d": 0.060, "k_a": 1.8, "beta": 0.55},
    # Wood
    "W-L":              {"k_d": 0.040, "k_a": 1.3, "beta": 0.45},
    # Composite wood-steel
    "CWS-L":            {"k_d": 0.038, "k_a": 1.3, "beta": 0.45},
    # Nipa/indigenous
    "N-L":              {"k_d": 0.055, "k_a": 1.5, "beta": 0.55},
    # Precast concrete
    "PC-L":             {"k_d": 0.042, "k_a": 1.5, "beta": 0.48},
}

# Default EDP params for any unknown archetype
_EDP_DEFAULT = {"k_d": 0.035, "k_a": 1.4, "beta": 0.45}

# Collapse-proxy PID cap (at this drift ratio, building is effectively at collapse DS)
_PID_COLLAPSE_CAP = 0.10


# ---------------------------------------------------------------------------
# Mitigation — the thesis ran TWO simultaneous mitigation layers (Jeswani 2021
# §7.3.2 "Mitigated: archetypal vulnerabilities replaced with mitigated counterparts
# wherever applicable"; §7.4; .mat WVF_7_3_R1_PA). The mitigated portfolio run
# (``mitigated=True``) applies BOTH:
#
#   (1) STRUCTURAL FRP retrofit of the non-ductile Pre/Low-code RCMRF — base archetype
#       -> retrofit archetype substitution (MITIGATION_RETROFIT_MAP below). Effect:
#       collapse capacity up -> collapse risk down -> FATALITY reduction. The thesis
#       retrofitted the WHOLE ductile/non-ductile RC moment-frame stock (the `_R1`
#       archetypes in the R1 .mat: C1-L MCHC, C1-M HC/MC/PCLC, PTC1-M HC/MC, all soils),
#       but we only RECOVERED the FRP-retrofit EDPs for C1-M (Pre/Lo) (`C1M_PCLC_R1_*`,
#       collapse Sa 1.11 g -> 2.12 g). Per the HARD SCOPE (no structural re-analysis) the
#       reproducible structural layer is the C1-M (Pre/Lo) -> FRP swap only — a data-
#       coverage limitation on the FATALITY reduction (NOT tuned).
#
#   (2) NON-STRUCTURAL equipment upgrade (Table 6-3; building.nonstructural_mitigated) —
#       a portfolio-wide COMPONENT-LEVEL fragility/consequence swap: brace ceilings, anchor/
#       safety-wire fixtures (fans/lights), secure desktop electronics, anchor wall-mounted
#       AC units. Effect: falling-hazard INJURY reduction (the headline non-structural
#       benefit — "non-structural mitigation neutralized non-collapse injuries", thesis
#       Ch 6). This is NOT new EDPs and NOT structural re-analysis; it changes only the
#       Pelicun component marginals (see building._build_cmp_marginals). It applies to
#       every building that carries the upgraded component classes (portfolio-wide for
#       those components), independent of the structural FRP coverage.
#
# Structural-layer mechanism: a structurally-retrofitted building substitutes its retrofit
# archetype for (a) the EDP / collapse-fragility dataset (higher collapse capacity), (b) the
# residual-drift demand feeding demolition, and (c) the Pelicun component model. Everything
# else (hazard field, inventory cost/population/city, all other archetypes) is unchanged.
MITIGATION_RETROFIT_MAP: dict[str, str] = {
    "C1-M (Pre/Lo)": "C1-M (Pre/Lo) FRP",
}


def mitigation_coverage(inventory: pd.DataFrame) -> dict:
    """Quantify the reach of each mitigation layer over an inventory.

    Two layers (see :data:`MITIGATION_RETROFIT_MAP` and ``building.nonstructural_mitigated``):

    * **Structural FRP** (fatality reduction): the buildings whose base archetype is in
      :data:`MITIGATION_RETROFIT_MAP` — i.e. retrofittable with the recovered R1 EDPs
      (C1-M (Pre/Lo) only). Reported as ``n_retrofitted`` / cost share per region. This
      is a data-coverage limitation vs the thesis's whole-RC-frame retrofit.
    * **Non-structural** (injury reduction): applied PORTFOLIO-WIDE to every building that
      carries one of the upgraded acceleration/drift-sensitive non-structural components.
      Reported as ``n_nonstructural_upgraded`` (buildings that own at least one upgradeable
      component) — for this school portfolio that is effectively the whole inventory, so
      the injury-reduction layer is NOT coverage-limited (unlike the structural layer).
    """
    inv = inventory
    arch = inv["archetype"].astype(str)
    retrofittable = arch.isin(MITIGATION_RETROFIT_MAP).to_numpy()

    # Which archetypes carry at least one non-structural component that the Table 6-3
    # swap upgrades (ceilings / fixtures / CHB / electronics)? Read from the packaged
    # component table so this stays data-driven.
    from bayanihan.building import (
        _load_component_table,
        _ns_mitigation_map,
        _resolve_component_archetype,
    )

    subs, removed = _ns_mitigation_map()
    upgradeable_ids = set(subs) | set(removed)
    ctab = _load_component_table()
    arch_has_ns: dict[str, bool] = {}
    for a in arch.unique():
        resolved = _resolve_component_archetype(str(a))
        rows = ctab[ctab["archetype"] == resolved] if not ctab.empty else ctab
        has_rows = rows is not None and not rows.empty
        ids = set(rows["component_id"].astype(str)) if has_rows else set()
        arch_has_ns[str(a)] = bool(ids & upgradeable_ids)
    ns_upgraded = arch.map(arch_has_ns).fillna(False).to_numpy(dtype=bool)

    repl = (
        inv["replacement_cost_php"].to_numpy(dtype=float)
        if "replacement_cost_php" in inv.columns
        else np.zeros(len(inv))
    )
    city = (
        inv["city"].astype(str).to_numpy()
        if "city" in inv.columns
        else np.array([""] * len(inv))
    )

    def _blk(mask: np.ndarray) -> dict:
        n = int(mask.sum())
        n_r = int((mask & retrofittable).sum())
        n_ns = int((mask & ns_upgraded).sum())
        repl_tot = float(repl[mask].sum())
        repl_r = float(repl[mask & retrofittable].sum())
        return {
            "n_buildings": n,
            "n_retrofitted": n_r,  # structural FRP layer (recovered-EDP coverage)
            "fraction_retrofitted_by_count": (n_r / n) if n else 0.0,
            "replacement_cost_php": repl_tot,
            "retrofitted_replacement_cost_php": repl_r,
            "fraction_retrofitted_by_cost": (repl_r / repl_tot) if repl_tot else 0.0,
            "n_nonstructural_upgraded": n_ns,  # non-structural layer (portfolio-wide)
            "fraction_nonstructural_upgraded": (n_ns / n) if n else 0.0,
        }

    return {
        "retrofit_map": dict(MITIGATION_RETROFIT_MAP),
        "nonstructural_substitutions": dict(subs),
        "nonstructural_removed": sorted(removed),
        "whole": _blk(np.ones(len(inv), dtype=bool)),
        "MC": _blk(city == "MC"),
        "QC": _blk(city == "QC"),
    }


def _synthetic_edp_samples(
    sa_samples: np.ndarray,
    n_stories: int,
    archetype_id: str,
    rng: np.random.Generator,
) -> np.ndarray:
    """Convert Sa(g) samples → EDP samples via synthetic lognormal IM-EDP model.

    # PLACEHOLDER(P2): real per-archetype EDP-vs-IM comes from saved PERFORM-3D
    # NRHA outputs (Kevin's laptop). This synthetic relation is illustrative only.
    # The EDP constants (k_d, k_a, beta) are tuned to produce plausible Metro Manila
    # school behaviour but are NOT derived from the thesis NRHA outputs.

    Parameters
    ----------
    sa_samples : np.ndarray
        (n_sims,) array of Sa(T) in g for this building.
    n_stories : int
        Number of stories (for height-wise profile).
    archetype_id : str
        Archetype label used to look up k_d, k_a, beta.
    rng : np.random.Generator
        Seeded RNG for reproducibility.

    Returns
    -------
    np.ndarray
        (n_sims, n_stories, 2) array where axis-2 = [PID (unitless), PFA (g)].
    """
    n_sims = len(sa_samples)
    params = _EDP_PARAMS.get(archetype_id, _EDP_DEFAULT)
    k_d = params["k_d"]
    k_a = params["k_a"]
    beta = params["beta"]

    # Height-wise profile factors: PID peaks at mid-height, PFA amplifies with height
    # Profile shapes consistent with first-mode-dominant response.
    story_idx = np.arange(1, n_stories + 1)
    # PID profile: peaks near 2/3 height (normalised), slight linear gradient
    pid_profile = 1.0 + 0.5 * (story_idx / n_stories - 0.5)
    pid_profile /= pid_profile.max()  # normalise to 1.0 at peak story

    # PFA profile: amplifies linearly from ~1.0 at base to ~2.5 at roof
    pfa_profile = 1.0 + 1.5 * (story_idx - 1) / max(n_stories - 1, 1)

    # Median EDP = k * Sa (lognormal; sample ln(EDP) ~ N(ln(k*Sa), beta^2))
    # Shape: (n_sims, n_stories)
    ln_sa = np.log(np.clip(sa_samples, 1e-6, None))  # (n_sims,)

    # PID — PLACEHOLDER(P2)
    ln_pid_median = np.log(k_d) + ln_sa[:, None] + np.log(pid_profile[None, :])
    eps_pid = rng.standard_normal((n_sims, n_stories)) * beta
    pid = np.exp(ln_pid_median + eps_pid)
    pid = np.clip(pid, 0.0, _PID_COLLAPSE_CAP)

    # PFA — PLACEHOLDER(P2)
    ln_pfa_median = np.log(k_a) + ln_sa[:, None] + np.log(pfa_profile[None, :])
    eps_pfa = rng.standard_normal((n_sims, n_stories)) * beta
    pfa = np.exp(ln_pfa_median + eps_pfa)
    pfa = np.clip(pfa, 0.0, 5.0)  # physical cap at 5g

    # Stack → (n_sims, n_stories, 2) : [PID, PFA]
    return np.stack([pid, pfa], axis=-1)


def _normalise_rupture(rupture: dict) -> dict:
    """Normalise rupture dict keys to lowercase (hazard.py requires lowercase 'mw').

    Accepts both 'Mw' and 'mw' as the magnitude key.
    """
    out = {}
    for k, v in rupture.items():
        out[k.lower()] = v
    return out


class PortfolioAnalysis:
    """Monte Carlo portfolio assessment over a building inventory.

    Spatial correlation: Loth & Baker (2013) intra-event model.
    Hazard: GMPEs from bayanihan.hazard.ThesisHazardModel.
    """

    def __init__(
        self,
        inventory: gpd.GeoDataFrame,
        hazard_model,
        n_simulations: int = 1000,
        seed: int | None = None,
    ):
        """
        Args:
            inventory: GeoDataFrame with columns: archetype_id, lat, lon,
                replacement_cost_usd, and any archetype-specific attributes.
            hazard_model: HazardModel instance (from hazard.py).
            n_simulations: Number of Monte Carlo realizations.
            seed: Random seed.
        """
        self.inventory = inventory
        self.hazard_model = hazard_model
        self.n_simulations = n_simulations
        self.seed = seed

    def run(self, rupture: dict) -> dict:
        """Execute the portfolio Monte Carlo for a given rupture scenario.

        Args:
            rupture: dict with keys: Mw (or mw), lat, lon, depth, mechanism.
                e.g. {"Mw": 7.3, "lat": 14.35, "lon": 121.1, "depth": 20,
                      "mechanism": "crustal"} for the WVF scenario.

        Returns:
            dict with:
                - loss_ratio: (n_buildings, n_simulations) repair cost fractions
                - repair_cost: (n_buildings, n_simulations) PHP_2020
                - repair_time: (n_buildings, n_simulations) worker_hours
                - reoccupancy_days: (n_buildings, n_simulations) or None
                - functional_recovery_days: (n_buildings, n_simulations) or None
                - full_recovery_days: (n_buildings, n_simulations) or None
                - portfolio_loss_ratio: (n_simulations,) aggregated
                - portfolio_repair_cost: (n_simulations,) total PHP_2020
                - summary: pandas DataFrame with per-building median results
        """
        rng = np.random.default_rng(self.seed)
        rup = _normalise_rupture(rupture)

        inv = self.inventory
        n_buildings = len(inv)
        n_sims = self.n_simulations

        # ------------------------------------------------------------------
        # 1. Build site array (n_buildings, 2) = [lat, lon]
        # ------------------------------------------------------------------
        lats = inv["lat"].values.astype(float)
        lons = inv["lon"].values.astype(float)
        sites = np.column_stack([lats, lons])

        # ------------------------------------------------------------------
        # 2. Sample spatially-correlated IM field → (n_sims, n_buildings)
        # ------------------------------------------------------------------
        log.info("Sampling IM field for %d buildings, %d simulations", n_buildings, n_sims)
        sa_field = self.hazard_model.sample_im(
            rupture=rup,
            sites=sites,
            n_simulations=n_sims,
            seed=int(rng.integers(0, 2**31)),
        )
        # sa_field shape: (n_sims, n_buildings)

        # ------------------------------------------------------------------
        # 3. Per-building assessment
        # ------------------------------------------------------------------
        loss_ratio_all = np.zeros((n_buildings, n_sims))
        repair_cost_all = np.zeros((n_buildings, n_sims))
        repair_time_all = np.zeros((n_buildings, n_sims))

        # Recovery arrays — may remain None if recovery module not available
        reoccupancy_all: np.ndarray | None = None
        functional_all: np.ndarray | None = None
        full_recovery_all: np.ndarray | None = None
        recovery_arrays_init = False

        for i, row in enumerate(inv.itertuples()):
            archetype_id = row.archetype_id
            stories = int(row.stories)
            replacement_cost_php = float(row.replacement_cost_php)
            lat = float(row.lat)
            lon = float(row.lon)
            year_built = int(row.year_built)
            site_class = str(row.site_class)

            # Sa samples for this building: (n_sims,)
            sa_b = sa_field[:, i]

            # --- Convert Sa → EDP using synthetic IM-EDP model ---
            # PLACEHOLDER(P2): see _synthetic_edp_samples docstring
            building_seed = int(rng.integers(0, 2**31))
            edp_samples = _synthetic_edp_samples(
                sa_samples=sa_b,
                n_stories=stories,
                archetype_id=archetype_id,
                rng=np.random.default_rng(building_seed),
            )
            # edp_samples: (n_sims, n_stories, 2)

            # --- Run Pelicun assessment ---
            try:
                bldg = Building.from_archetype(
                    archetype_id,
                    lat=lat,
                    lon=lon,
                    year_built=year_built,
                    site_class=site_class,
                )
                # Override replacement cost from inventory (not archetype default)
                if replacement_cost_php > 0:
                    bldg.metadata["replacement_cost_PHP"] = replacement_cost_php

                result = bldg.assess(edp_samples, seed=building_seed)

                lr = np.nan_to_num(np.asarray(result["loss_ratio"], dtype=float), nan=0.0)
                rc = np.nan_to_num(np.asarray(result["repair_cost"], dtype=float), nan=0.0)
                rt = np.nan_to_num(np.asarray(result["repair_time"], dtype=float), nan=0.0)

                loss_ratio_all[i] = lr[:n_sims]
                repair_cost_all[i] = rc[:n_sims]
                repair_time_all[i] = rt[:n_sims]

                # Recovery milestones
                if not recovery_arrays_init:
                    if result["reoccupancy_days"] is not None:
                        reoccupancy_all = np.zeros((n_buildings, n_sims))
                        functional_all = np.zeros((n_buildings, n_sims))
                        full_recovery_all = np.zeros((n_buildings, n_sims))
                    recovery_arrays_init = True

                if reoccupancy_all is not None:
                    if result["reoccupancy_days"] is not None:
                        ro = np.nan_to_num(
                            np.asarray(result["reoccupancy_days"], dtype=float), nan=0.0
                        )
                        # Use explicit None check ('or' on ndarray is ambiguous)
                        fr_raw = result["functional_recovery_days"]
                        fr_arr = fr_raw if fr_raw is not None else np.zeros(n_sims)
                        fr = np.nan_to_num(
                            np.asarray(fr_arr, dtype=float), nan=0.0
                        )
                        fu_raw = result["full_recovery_days"]
                        fu_arr = fu_raw if fu_raw is not None else np.zeros(n_sims)
                        fu = np.nan_to_num(
                            np.asarray(fu_arr, dtype=float), nan=0.0
                        )
                        reoccupancy_all[i] = ro[:n_sims]
                        assert functional_all is not None  # set alongside reoccupancy_all
                        assert full_recovery_all is not None  # set alongside reoccupancy_all
                        functional_all[i] = fr[:n_sims]
                        full_recovery_all[i] = fu[:n_sims]

            except Exception as exc:
                log.warning("Building %s (%s) assessment failed: %s", row.id, archetype_id, exc)
                # Leave zeros for this building (loss_ratio, repair_cost, repair_time)

        # ------------------------------------------------------------------
        # 4. Portfolio aggregation
        # ------------------------------------------------------------------
        replacement_costs = inv["replacement_cost_php"].values.astype(float)
        total_replacement_cost = replacement_costs.sum()

        # Portfolio repair cost = sum over buildings per simulation
        portfolio_repair_cost = repair_cost_all.sum(axis=0)  # (n_sims,)

        # Portfolio loss ratio = total repair / total replacement
        if total_replacement_cost > 0:
            portfolio_loss_ratio = np.clip(
                portfolio_repair_cost / total_replacement_cost, 0.0, 1.0
            )
        else:
            portfolio_loss_ratio = np.zeros(n_sims)

        # ------------------------------------------------------------------
        # 5. Per-building summary DataFrame (median across simulations)
        # ------------------------------------------------------------------
        default_ids = [f"B{i}" for i in range(n_buildings)]
        summary_data = {
            "id": inv["id"].values if "id" in inv.columns else default_ids,
            "archetype_id": inv["archetype_id"].values,
            "city": inv["city"].values if "city" in inv.columns else [""] * n_buildings,
            "lat": lats,
            "lon": lons,
            "stories": inv["stories"].values,
            "replacement_cost_php": replacement_costs,
            "median_loss_ratio": np.median(loss_ratio_all, axis=1),
            "median_repair_cost_php": np.median(repair_cost_all, axis=1),
            "median_repair_time_wh": np.median(repair_time_all, axis=1),
        }
        if reoccupancy_all is not None:
            summary_data["median_reoccupancy_days"] = np.median(reoccupancy_all, axis=1)
            assert functional_all is not None  # set alongside reoccupancy_all
            assert full_recovery_all is not None  # set alongside reoccupancy_all
            summary_data["median_functional_recovery_days"] = np.median(functional_all, axis=1)
            summary_data["median_full_recovery_days"] = np.median(full_recovery_all, axis=1)

        summary = pd.DataFrame(summary_data)

        return {
            # Per-building arrays: (n_buildings, n_simulations)
            "loss_ratio": loss_ratio_all,
            "repair_cost": repair_cost_all,
            "repair_time": repair_time_all,
            "reoccupancy_days": reoccupancy_all,
            "functional_recovery_days": functional_all,
            "full_recovery_days": full_recovery_all,
            # Portfolio-level: (n_simulations,)
            "portfolio_loss_ratio": portfolio_loss_ratio,
            "portfolio_repair_cost": portfolio_repair_cost,
            # Per-building summary (median)
            "summary": summary,
            # Metadata
            "n_buildings": n_buildings,
            "n_simulations": n_sims,
            "total_replacement_cost_php": total_replacement_cost,
            # IM field for diagnostics
            "_sa_field": sa_field,
        }

    @classmethod
    def from_demo_inventory(cls, **kwargs) -> PortfolioAnalysis:
        """Load the bundled synthetic demo inventory and return a PortfolioAnalysis.

        The demo inventory is ~50 synthetic Manila schools for CI/examples.
        Not the real 1,021-building dataset.

        Keyword args are passed to PortfolioAnalysis.__init__ (e.g. n_simulations, seed).
        """
        # Resolve path via importlib.resources (works in both dev + installed modes)
        pkg_files = resources.files("bayanihan")
        geojson_ref = pkg_files.joinpath("data/inventory/manila_schools_demo.geojson")
        geojson_path = str(geojson_ref)

        inventory = gpd.read_file(geojson_path)

        # Ensure required columns exist with the right dtypes
        if "lat" not in inventory.columns:
            inventory["lat"] = inventory.geometry.y
        if "lon" not in inventory.columns:
            inventory["lon"] = inventory.geometry.x
        inventory["lat"] = inventory["lat"].astype(float)
        inventory["lon"] = inventory["lon"].astype(float)
        inventory["stories"] = inventory["stories"].astype(int)
        inventory["replacement_cost_php"] = inventory["replacement_cost_php"].astype(float)

        hazard_model = ThesisHazardModel(im_period=1.0)

        return cls(
            inventory=inventory,
            hazard_model=hazard_model,
            **kwargs,
        )


# ===========================================================================
# REAL-DATA scenario portfolio (P5/P7) — the thesis-validation pipeline
# ===========================================================================
#
# ScenarioPortfolio replaces the synthetic IM->EDP placeholder above with the real
# pipeline: a spatially-correlated Sa(T1) field from hazard.scenario_sa_field
# (the CORRECT aleatory sigma — NOT ThesisHazardModel.sample_im, which RSS-combines
# the 4 equal GMPE branches to ~half the true sigma) feeding the real multi-stripe
# PERFORM-3D EDPs via edp.demand_for_sa_field, building by building, with each
# realization conditioned on its OWN field Sa so the cross-building hazard
# correlation propagates into portfolio-loss dispersion.


def _load_real_inventory() -> pd.DataFrame:
    """Load the gitignored real 1,021-building inventory as a plain DataFrame.

    Returns one row per building with the columns needed by the scenario pipeline:
    ``building_id, city, archetype, edp_soil_bin, period_s, replacement_cost_php,
    replacement_time_days, floor_area_m2, population``. The geometry/coords are not
    needed here (the spatial-correlation distance matrix is built inside
    ``hazard.scenario_sa_field`` directly from the geojson).

    Raises:
        FileNotFoundError: if the gitignored real inventory is absent (e.g. on CI).
    """
    inv_dir = resources.files("bayanihan").joinpath("data/inventory")
    path = inv_dir.joinpath("manila_schools_real.geojson")
    if not path.is_file():
        raise FileNotFoundError(
            "Real inventory geojson (manila_schools_real.geojson) not found; "
            "it is gitignored and must be present to run the real-data scenario."
        )
    with resources.as_file(path) as p:
        with open(p, encoding="utf-8") as fh:
            gj = json.load(fh)

    rows = []
    for feat in gj["features"]:
        pr = feat["properties"]
        rows.append(
            {
                "building_id": str(pr["building_id"]).strip(),
                "city": str(pr["city"]).strip(),
                "archetype": str(pr["archetype"]).strip(),
                "edp_soil_bin": str(pr["edp_soil_bin"]).strip(),
                "period_s": float(pr["period_s"]),
                "replacement_cost_php": float(pr["replacement_cost_php"]),
                "replacement_time_days": float(pr["replacement_time_days"]),
                "floor_area_m2": float(pr.get("floor_area_m2", 0.0) or 0.0),
                "population": float(pr.get("population", 0.0) or 0.0),
            }
        )
    return pd.DataFrame.from_records(rows)


@dataclass
class ScenarioPortfolioResult:
    """Container for a real-data scenario portfolio run.

    Arrays are aligned: axis 0 = building (inventory order), axis 1 = realization.
    Portfolio-level vectors are length ``n_realizations`` and preserve the hazard
    spatial correlation across buildings (realization ``i`` is one coherent field).
    """

    # Per-building x per-realization
    loss_ratio: np.ndarray                 # (n_buildings, n_real) in [0, 1]
    repair_cost_php: np.ndarray            # (n_buildings, n_real) PHP_2020
    collapse_mask: np.ndarray              # (n_buildings, n_real) bool
    # bool — RDR-demolished (non-collapsed)
    demolition_mask: np.ndarray
    reoccupancy_days: np.ndarray           # (n_buildings, n_real)
    functional_recovery_days: np.ndarray   # (n_buildings, n_real)
    full_recovery_days: np.ndarray         # (n_buildings, n_real)
    # FEMA P-58 casualties (injuries + fatalities), per-building x per-realization (counts)
    injuries: np.ndarray                   # (n_buildings, n_real) total injuries
    fatalities: np.ndarray                 # (n_buildings, n_real) total fatalities
    injuries_noncollapse: np.ndarray       # (n_buildings, n_real) component-driven (non-collapsed)
    fatalities_noncollapse: np.ndarray     # (n_buildings, n_real) component-driven (non-collapsed)
    population: np.ndarray                 # (n_buildings,) occupant count per building
    # Portfolio-level (length n_real)
    portfolio_loss_php: np.ndarray
    portfolio_loss_ratio: np.ndarray
    # Bookkeeping
    inventory: pd.DataFrame
    replacement_cost_php: np.ndarray       # (n_buildings,)
    sa_field: pd.DataFrame                 # (n_real, n_buildings)
    n_realizations: int
    scenario_id: str
    extrapolated_fraction: float           # fraction of building-realizations above stripe Sa max
    mitigated: bool = False                # True if the FRP retrofit was applied


class ScenarioPortfolio:
    """Correlated Monte-Carlo portfolio loss + recovery for a thesis scenario.

    Consumes the REAL inventory and the REAL multi-stripe EDPs. The hazard is the
    spatially-correlated Sa(T1) field from :func:`hazard.scenario_sa_field`; each
    building's loss is computed from its own per-realization field Sa via
    :func:`edp.demand_for_sa_field` + Pelicun (:meth:`building.Building.assess`),
    with collapsed realizations overridden to total loss using the building's OWN
    ``replacement_cost_php`` / ``replacement_time_days`` from the inventory.

    Use :meth:`run` to execute and :func:`summarise_scenario_result` to aggregate.
    """

    def __init__(
        self,
        inventory: pd.DataFrame | None = None,
        scenario_id: str = "WVF_7.3",
        n_realizations: int = 1000,
        seed: int = 12345,
        mitigated: bool = False,
    ):
        self.inventory = inventory if inventory is not None else _load_real_inventory()
        self.scenario_id = scenario_id
        self.n_realizations = int(n_realizations)
        self.seed = int(seed)
        self.mitigated = bool(mitigated)

    @classmethod
    def from_real_inventory(cls, **kwargs) -> ScenarioPortfolio:
        """Load the gitignored real 1,021-building inventory and return the portfolio."""
        return cls(inventory=_load_real_inventory(), **kwargs)

    @classmethod
    def mitigated_from_real_inventory(cls, **kwargs) -> ScenarioPortfolio:
        """Real-inventory portfolio with BOTH mitigation layers applied (``mitigated=True``).

        (1) structural FRP retrofit (:data:`MITIGATION_RETROFIT_MAP`, fatality reduction;
        coverage-limited) and (2) the portfolio-wide non-structural component upgrade
        (injury reduction; ``building.nonstructural_mitigated``). See
        :func:`mitigation_coverage` for the per-layer reach.
        """
        kwargs.pop("mitigated", None)
        return cls(inventory=_load_real_inventory(), mitigated=True, **kwargs)

    def mitigation_coverage(self) -> dict:
        """Report the reach of each mitigation layer over this portfolio's inventory.

        Thin wrapper around :func:`mitigation_coverage` (structural FRP + non-structural).
        """
        return mitigation_coverage(self.inventory)

    def run(self, *, progress_every: int = 100) -> ScenarioPortfolioResult:
        """Execute the correlated portfolio Monte-Carlo and return raw arrays.

        Steps:
          1. Draw the spatially-correlated Sa(T1) field (``scenario_sa_field``).
          2. HARD-ASSERT that all inventory buildings join the Sa field AND an EDP
             dataset (fail loudly on any unmatched ``(archetype, edp_soil_bin)``).
          3. Per building: build a per-realization demand sample at its field Sa,
             run Pelicun, then route each realization (collapse -> else residual-drift
             demolition -> else component repair). Collapsed AND demolished realizations
             are overridden to the building's own replacement cost/time (total loss);
             recovery milestones computed for the rest.
          4. Portfolio loss[i] = sum over buildings of loss_php_b[i].

        Args:
            progress_every: log a progress line every N buildings (0 to silence).

        Returns:
            ScenarioPortfolioResult.
        """
        inv = self.inventory.reset_index(drop=True)
        n_buildings = len(inv)
        N = self.n_realizations
        master_rng = np.random.default_rng(self.seed)

        # ---- 1. Spatially-correlated Sa(T1) field (CORRECT sigma) -------------
        log.info(
            "scenario_sa_field(%s): %d buildings x %d realizations",
            self.scenario_id, n_buildings, N,
        )
        sa_field = scenario_sa_field(
            scenario_id=self.scenario_id,
            n_realizations=N,
            seed=int(master_rng.integers(0, 2**31)),
        )  # (N, n_buildings_in_field) DataFrame, columns = building_id

        # ---- 2. HARD-ASSERT the 1021-join (hazard field + EDP datasets) -------
        inv_ids = inv["building_id"].astype(str).str.strip().tolist()
        field_ids = set(str(c).strip() for c in sa_field.columns)
        missing_in_field = [b for b in inv_ids if b not in field_ids]
        if missing_in_field:
            raise AssertionError(
                f"{len(missing_in_field)} inventory buildings have NO Sa-field column "
                f"(e.g. {missing_in_field[:5]}). Hazard field / inventory mismatch."
            )
        # Reorder field columns to inventory order so column i == building i.
        sa_field = sa_field[inv_ids]

        # Assert every (EFFECTIVE archetype, soil_bin) resolves to an EDP dataset — no
        # silent drops. Under mitigation the effective archetype is the retrofit
        # substitution (MITIGATION_RETROFIT_MAP), so the FRP datasets are asserted too.
        unmatched_edp = []
        arch_sbin_pairs = inv[["archetype", "edp_soil_bin"]].drop_duplicates()
        for arch, sbin in arch_sbin_pairs.itertuples(index=False):
            eff_arch = (
                MITIGATION_RETROFIT_MAP.get(str(arch), str(arch))
                if self.mitigated
                else str(arch)
            )
            try:
                _edp._resolve_dataset(eff_arch, str(sbin))
            except KeyError:
                unmatched_edp.append((eff_arch, sbin))
        if unmatched_edp:
            raise AssertionError(
                f"{len(unmatched_edp)} (archetype, edp_soil_bin) combos do NOT join an "
                f"EDP dataset: {unmatched_edp}. Refusing to run with silent drops."
            )
        log.info("1021-join assertion passed: all %d buildings matched.", n_buildings)

        # ---- 3. Per-building assessment --------------------------------------
        loss_ratio = np.zeros((n_buildings, N))
        repair_cost = np.zeros((n_buildings, N))
        collapse_all = np.zeros((n_buildings, N), dtype=bool)
        demolition_all = np.zeros((n_buildings, N), dtype=bool)
        reocc = np.zeros((n_buildings, N))
        func = np.zeros((n_buildings, N))
        full = np.zeros((n_buildings, N))
        # FEMA P-58 casualties (injuries + fatalities)
        injuries_all = np.zeros((n_buildings, N))
        fatalities_all = np.zeros((n_buildings, N))
        inj_nc_all = np.zeros((n_buildings, N))
        fat_nc_all = np.zeros((n_buildings, N))

        repl_cost_vec = inv["replacement_cost_php"].to_numpy(dtype=float)
        pop_vec = (
            inv["population"].to_numpy(dtype=float)
            if "population" in inv.columns
            else np.zeros(n_buildings)
        )
        farea_vec = (
            inv["floor_area_m2"].to_numpy(dtype=float)
            if "floor_area_m2" in inv.columns
            else np.zeros(n_buildings)
        )

        sa_arr = sa_field.to_numpy(dtype=float)  # (N, n_buildings)

        n_above_stripe = 0
        n_cells_total = n_buildings * N

        for i, row in enumerate(inv.itertuples(index=False)):
            base_arch = str(row.archetype)
            # ---- Mitigation: substitute the FRP-retrofit archetype in place ------
            # When mitigated, a retrofittable base archetype (MITIGATION_RETROFIT_MAP)
            # is replaced by its retrofit archetype for ALL physics: EDP/collapse,
            # residual drift, and the Pelicun component model. The inventory soil bin,
            # replacement cost/time, population and city are unchanged (same building,
            # stronger structure). Everything else routes exactly as the base path.
            arch = (
                MITIGATION_RETROFIT_MAP.get(base_arch, base_arch)
                if self.mitigated
                else base_arch
            )
            sbin = str(row.edp_soil_bin)
            repl_cost_b = float(row.replacement_cost_php)
            repl_days_b = float(row.replacement_time_days)
            sa_b = sa_arr[:, i]  # (N,) this building's correlated field

            # Extrapolation diagnostic: realizations above the EDP stripe Sa max.
            try:
                _, sa_max = _edp.stripe_sa_range(arch, sbin)
                n_above_stripe += int(np.sum(sa_b > sa_max))
            except Exception:
                pass

            bldg_seed = int(master_rng.integers(0, 2**31))

            try:
                sample = _edp.demand_for_sa_field(arch, sbin, sa_b, seed=bldg_seed)

                bldg = Building.from_archetype(
                    arch,
                    site_class=("D" if sbin == "D" else "C"),
                )
                # Per-building replacement cost from the inventory (not archetype default).
                bldg.metadata["replacement_cost_PHP"] = repl_cost_b
                # Non-structural mitigation layer (Table 6-3 component swap) — applied to
                # EVERY building in the mitigated run (portfolio-wide for the upgraded
                # acceleration/drift-sensitive non-structural components). This drives the
                # injury reduction and is independent of the structural FRP coverage above.
                bldg.nonstructural_mitigated = bool(self.mitigated)

                result = bldg.assess(sample.edp, seed=bldg_seed)

                lr = np.nan_to_num(np.asarray(result["loss_ratio"], dtype=float), nan=0.0)[:N]
                rc = np.nan_to_num(np.asarray(result["repair_cost"], dtype=float), nan=0.0)[:N]
                ro = result.get("reoccupancy_days")
                fr = result.get("functional_recovery_days")
                fu = result.get("full_recovery_days")
                def _to_arr(v: object) -> np.ndarray:
                    return (
                        np.nan_to_num(np.asarray(v, dtype=float), nan=0.0)[:N]
                        if v is not None
                        else np.zeros(N)
                    )
                ro = _to_arr(ro)
                fr = _to_arr(fr)
                fu = _to_arr(fu)

                collapse_mask = sample.collapse_mask[:N]

                # ---- Residual-drift demolition (FEMA P-58 §7.6 / Ramirez & Miranda 2012) --
                # MEDIAN peak RIDR at each realization's own field Sa (capped at the top
                # calibrated stripe — collapse governs above it), through the lognormal
                # demolition fragility (median = thesis Table 6-6 RIDR limit, beta=0.30),
                # then Bernoulli demolition among NON-collapsed realizations. Order:
                # collapse -> else demolition -> else component. The residual EDP's own
                # record-to-record scatter is NOT additionally sampled (the beta=0.30
                # demolition-fragility dispersion already carries the threshold uncertainty);
                # sampling it too double-counted the residual aleatory variability and fired
                # spurious demolition on ductile frames. See
                # docs/learnings/2026-06-27_demolition_recalibration.md.
                ridr_b = _edp.median_residual_drift_for_sa_field(arch, sbin, sa_b)[:N]
                median_ridr_pct = float(
                    bldg.metadata.get("residual_drift_limit_pct") or 0.0
                )
                demo_rng = np.random.default_rng(bldg_seed + 104729)
                demolition_mask = sample_demolition(
                    ridr_b, median_ridr_pct, collapse_mask, demo_rng
                )

                # ---- Total-loss override (collapse OR demolition) -> own repl. ----
                total_loss_mask = collapse_mask | demolition_mask
                if total_loss_mask.any():
                    lr = np.where(total_loss_mask, 1.0, lr)
                    rc = np.where(total_loss_mask, repl_cost_b, rc)
                    repl_days_eff = repl_days_b  # building's own replacement_time_days
                    ro = np.where(total_loss_mask, repl_days_eff, ro)
                    fr = np.where(total_loss_mask, repl_days_eff, fr)
                    fu = np.where(total_loss_mask, repl_days_eff, fu)

                # ---- FEMA P-58 casualties (injuries + fatalities) ----------------
                # Non-collapse component-driven (affected-area model) on non-collapsed
                # realizations + collapse-driven (HAZUS-typology rates), scaled by the
                # building's own population. Demolition is NOT a casualty event.
                cas = _casualties.building_casualties(
                    damage_sample=result.get("damage_sample"),
                    collapse_mask=collapse_mask,
                    # Casualty TYPOLOGY follows the physical building (HAZUS occupancy,
                    # P(total collapse), occupancy factor) — the FRP retrofit changes the
                    # building's collapse PROBABILITY (already in collapse_mask), not its
                    # occupancy class. So we pass the base archetype here.
                    archetype=base_arch,
                    population=float(pop_vec[i]),
                    floor_area_m2=float(farea_vec[i]),
                )

                loss_ratio[i] = lr
                repair_cost[i] = rc
                collapse_all[i] = collapse_mask
                demolition_all[i] = demolition_mask
                reocc[i] = ro
                func[i] = fr
                full[i] = fu
                injuries_all[i] = cas["injuries"]
                fatalities_all[i] = cas["fatalities"]
                inj_nc_all[i] = cas["injuries_noncollapse"]
                fat_nc_all[i] = cas["fatalities_noncollapse"]

            except Exception as exc:  # noqa: BLE001 — record + re-raise; no silent drop
                raise RuntimeError(
                    f"Building {row.building_id} ({arch}/{sbin}) assessment failed: {exc}"
                ) from exc

            if progress_every and (i + 1) % progress_every == 0:
                log.info("  assessed %d/%d buildings", i + 1, n_buildings)

        # ---- 4. Portfolio aggregation (preserves spatial correlation) --------
        # Per-building loss in PHP = loss_ratio * own replacement cost (collapse
        # rows already == repl_cost via loss_ratio=1).
        loss_php = loss_ratio * repl_cost_vec[:, None]      # (n_buildings, N)
        portfolio_loss_php = loss_php.sum(axis=0)           # (N,)
        total_repl = float(repl_cost_vec.sum())
        portfolio_loss_ratio = (
            np.clip(portfolio_loss_php / total_repl, 0.0, 1.0)
            if total_repl > 0 else np.zeros(N)
        )

        return ScenarioPortfolioResult(
            loss_ratio=loss_ratio,
            repair_cost_php=loss_php,  # PHP loss per building (== repair_cost for non-collapse)
            collapse_mask=collapse_all,
            demolition_mask=demolition_all,
            reoccupancy_days=reocc,
            functional_recovery_days=func,
            full_recovery_days=full,
            injuries=injuries_all,
            fatalities=fatalities_all,
            injuries_noncollapse=inj_nc_all,
            fatalities_noncollapse=fat_nc_all,
            population=pop_vec,
            portfolio_loss_php=portfolio_loss_php,
            portfolio_loss_ratio=portfolio_loss_ratio,
            inventory=inv,
            replacement_cost_php=repl_cost_vec,
            sa_field=sa_field,
            n_realizations=N,
            scenario_id=self.scenario_id,
            extrapolated_fraction=float(n_above_stripe) / float(max(n_cells_total, 1)),
            mitigated=self.mitigated,
        )


def _subset_loss_ratio(
    loss_php: np.ndarray, repl_cost: np.ndarray, mask: np.ndarray
) -> np.ndarray:
    """Per-realization loss ratio for a building subset: sum(loss)/sum(replacement)."""
    denom = float(repl_cost[mask].sum())
    if denom <= 0:
        return np.zeros(loss_php.shape[1])
    return np.clip(loss_php[mask].sum(axis=0) / denom, 0.0, 1.0)


def _pctile_block(arr: np.ndarray) -> dict:
    """Return mean + standard percentile summary of a 1D per-realization vector."""
    return {
        "mean": float(np.mean(arr)),
        "median": float(np.median(arr)),
        "std": float(np.std(arr)),
        "p05": float(np.percentile(arr, 5)),
        "p10": float(np.percentile(arr, 10)),
        "p16": float(np.percentile(arr, 16)),
        "p50": float(np.percentile(arr, 50)),
        "p84": float(np.percentile(arr, 84)),
        "p90": float(np.percentile(arr, 90)),
        "p95": float(np.percentile(arr, 95)),
    }


def _casualty_block(
    count_per_real: np.ndarray, population_total: float
) -> dict:
    """Summarise a per-realization casualty COUNT vector as count + ratio percentiles.

    Args:
        count_per_real: (n_real,) portfolio (or subset) casualty count per realization
            (sum over the relevant buildings).
        population_total: total exposed population of that building subset (the normaliser
            for the casualty RATIO, matching the thesis convention of casualties/population).

    Returns:
        dict ``{"count": _pctile_block(counts), "ratio": _pctile_block(counts/pop)}``.
    """
    counts = np.asarray(count_per_real, dtype=float)
    pop = float(population_total)
    ratio = counts / pop if pop > 0 else np.zeros_like(counts)
    return {"count": _pctile_block(counts), "ratio": _pctile_block(ratio)}


def portfolio_recovery_time_at_fraction(
    milestone_days: np.ndarray,
    fraction: float = 0.90,
    weights: np.ndarray | None = None,
) -> np.ndarray:
    """Per-realization time at which ``fraction`` of the portfolio has recovered.

    This is the thesis's PRIMARY resilience metric (Jeswani 2021 §7.3.4.1, p.162;
    ``Portfolio_Analysis_2021.m`` line 214):

    .. code-block:: matlab

        PA(v,s).R(5,:) = prctile(PAResults(s).R_Func(Arch_ind2>0,:), 90, 1);

    For each realization (column of ``milestone_days``), it returns the milestone day
    at which ``fraction`` of the buildings have reached that recovery milestone — i.e.
    the (100*fraction)-th percentile of the per-building milestone day **across the
    building axis**. Equivalently, it is the inverse of the portfolio recovery
    *function* ``f(t) = #{buildings recovered by t} / N`` evaluated at ``f = fraction``.

    Weighting basis (THESIS-FAITHFUL): the thesis uses an **unweighted percentile
    across buildings** — i.e. "fraction of the portfolio recovered" is by **building
    COUNT**, not floor area or population. (The thesis's population-weighted variant,
    ``R(7,:)`` "Total Student-Days", is a *separate* disruption DV, not the 90% FR
    metric.) ``weights=None`` reproduces the thesis exactly. A non-None ``weights``
    vector computes the weighted-quantile generalisation (floor-area / population
    weighting) for sensitivity studies only.

    The 90th percentile is chosen over 100% because the full-portfolio (100%) recovery
    time has a very large tail driven by collapsed/demolished buildings taking the full
    replacement duration (thesis §7.3.4.1).

    Args:
        milestone_days: (n_buildings, n_realizations) per-building recovery-milestone
            days (e.g. ``functional_recovery_days``). Total-loss (collapse/demolition)
            cells already carry the building's full replacement duration, so they
            correctly drive the upper tail.
        fraction: portfolio-recovered fraction (default 0.90 = the thesis 90% metric).
        weights: optional (n_buildings,) non-negative weights. ``None`` (default) =
            unweighted count basis (thesis). If given, a weighted quantile is used.

    Returns:
        (n_realizations,) array — the recovery day at which ``fraction`` of the
        portfolio (by count, or by ``weights``) has recovered, per realization.
    """
    arr = np.asarray(milestone_days, dtype=float)
    if arr.ndim != 2:
        raise ValueError(f"milestone_days must be 2D (n_buildings, n_real); got {arr.shape}")
    q = float(fraction) * 100.0

    # Empty building axis (e.g. an empty city/subset mask): no buildings -> undefined
    # recovery percentile. Return NaN per realization rather than letting np.percentile
    # raise (defensive; the real 1021-inventory always has both cities populated).
    if arr.shape[0] == 0:
        return np.full(arr.shape[1], np.nan)

    if weights is None:
        # Thesis-exact: unweighted percentile across the building axis (axis 0).
        return np.percentile(arr, q, axis=0)

    # Weighted-quantile generalisation (sensitivity only): for each realization,
    # sort buildings by milestone day and find the day at which the cumulative
    # weight fraction first reaches ``fraction``.
    w = np.asarray(weights, dtype=float)
    if w.shape[0] != arr.shape[0]:
        raise ValueError("weights length must equal n_buildings")
    if w.sum() <= 0:
        return np.percentile(arr, q, axis=0)
    n_real = arr.shape[1]
    out = np.empty(n_real)
    for r in range(n_real):
        order = np.argsort(arr[:, r], kind="mergesort")
        days_sorted = arr[order, r]
        w_sorted = w[order]
        cum = np.cumsum(w_sorted) / w_sorted.sum()
        idx = int(np.searchsorted(cum, float(fraction), side="left"))
        idx = min(idx, len(days_sorted) - 1)
        out[r] = days_sorted[idx]
    return out


def portfolio_recovery_curve(
    milestone_days: np.ndarray,
    time_grid: np.ndarray | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Mean portfolio recovery FUNCTION: fraction of the portfolio recovered vs time.

    At each time ``t`` in ``time_grid``, the recovered fraction for a single
    realization is ``#{buildings with milestone_days <= t} / n_buildings`` (count
    basis, thesis-faithful). This returns the **mean over realizations** of that
    fraction at each ``t`` — the curve the thesis plots (Figure 7-5 / 7-14 recovery
    panel; ``Portfolio_Analysis_2021.m`` ``R_time``/``R_time_m``).

    Args:
        milestone_days: (n_buildings, n_realizations) per-building milestone days.
        time_grid: 1D array of days at which to evaluate the curve. If ``None``, a
            default grid 0..ceil(p99 of the data) with ~120 points is used.

    Returns:
        (time_grid, mean_fraction_recovered): both 1D, same length. ``mean_fraction``
        rises monotonically from ~0 to 1 (if the grid extends past full recovery).
    """
    arr = np.asarray(milestone_days, dtype=float)
    if time_grid is None:
        t_max = float(np.percentile(arr, 99))
        t_max = max(t_max, 1.0)
        time_grid = np.linspace(0.0, np.ceil(t_max), 120)
    time_grid = np.asarray(time_grid, dtype=float)

    # Fraction recovered per (time, realization): broadcast compare then mean over
    # buildings, then mean over realizations. Memory-light loop over the time grid.
    mean_fraction = np.empty(len(time_grid))
    for k, t in enumerate(time_grid):
        # (n_buildings, n_real) bool -> fraction across buildings -> mean across real.
        mean_fraction[k] = float((arr <= t).mean())
    return time_grid, mean_fraction


def _recovery_90pct_block(
    milestone_days: np.ndarray, fraction: float = 0.90
) -> dict:
    """Summarise the per-realization X%-portfolio-recovery time as median + p90 (+spread).

    Returns mean/median/p10/p16/p84/p90 of the per-realization
    ``portfolio_recovery_time_at_fraction`` vector (count basis), so the headline is
    ``median`` (matches the thesis's reported median) with ``p90`` as the across-
    realization upper bound (matches the thesis's reported p90).
    """
    per_real = portfolio_recovery_time_at_fraction(milestone_days, fraction=fraction)
    return {
        "mean": float(np.mean(per_real)),
        "median": float(np.median(per_real)),
        "p10": float(np.percentile(per_real, 10)),
        "p16": float(np.percentile(per_real, 16)),
        "p84": float(np.percentile(per_real, 84)),
        "p90": float(np.percentile(per_real, 90)),
    }


def summarise_scenario_result(result: ScenarioPortfolioResult) -> dict:
    """Aggregate a ScenarioPortfolioResult into a committable, identifier-free summary.

    Contains ONLY aggregates (no per-building IDs/coords): whole / Makati (MC) / QC
    loss-ratio distributions, per-archetype mean loss ratios, recovery-milestone
    percentiles (building-mean per realization), total loss, and provenance.
    """
    inv = result.inventory
    loss_php = result.repair_cost_php
    repl = result.replacement_cost_php
    N = result.n_realizations

    city = inv["city"].to_numpy()
    mc_mask = city == "MC"
    qc_mask = city == "QC"

    whole_lr = result.portfolio_loss_ratio
    mc_lr = _subset_loss_ratio(loss_php, repl, mc_mask)
    qc_lr = _subset_loss_ratio(loss_php, repl, qc_mask)

    # Per-archetype mean loss ratio (loss-weighted across buildings of that archetype,
    # averaged over realizations).
    per_arch = {}
    for arch in sorted(inv["archetype"].unique()):
        amask = (inv["archetype"] == arch).to_numpy()
        a_lr = _subset_loss_ratio(loss_php, repl, amask)
        # Per-archetype mean normalized casualty rate (mean over realizations of
        # sum(casualties)/sum(population)); comparable to the thesis .mat
        # Arch_simp_norm_CasI / Arch_simp_norm_CasF.
        a_pop = float(result.population[amask].sum())
        a_inj_rate = (
            float(result.injuries[amask].sum(axis=0).mean() / a_pop) if a_pop > 0 else 0.0
        )
        a_fat_rate = (
            float(result.fatalities[amask].sum(axis=0).mean() / a_pop) if a_pop > 0 else 0.0
        )
        per_arch[arch] = {
            "n_buildings": int(amask.sum()),
            "mean_loss_ratio": float(np.mean(a_lr)),
            "p16_loss_ratio": float(np.percentile(a_lr, 16)),
            "p84_loss_ratio": float(np.percentile(a_lr, 84)),
            "collapse_rate": float(result.collapse_mask[amask].mean()),
            "demolition_rate": float(result.demolition_mask[amask].mean()),
            "mean_injury_rate": a_inj_rate,
            "mean_fatality_rate": a_fat_rate,
        }

    # Recovery: portfolio summary = building-MEAN milestone per realization (days).
    # (A single "portfolio recovery" scalar is ill-defined; the building-mean per
    # realization is the natural portfolio-average downtime.)
    reocc_pf = result.reoccupancy_days.mean(axis=0)
    func_pf = result.functional_recovery_days.mean(axis=0)
    full_pf = result.full_recovery_days.mean(axis=0)

    # --- THESIS PRIMARY METRIC: time to 90% portfolio Functional Recovery -----------
    # (Jeswani 2021 §7.3.4.1 p.162; Portfolio_Analysis_2021.m line 214:
    #   PA(v,s).R(5,:) = prctile(R_Func(Arch_ind2>0,:), 90, 1)  -> median/p90 across real.)
    # Per realization: the (count-basis) day at which 90% of the buildings have reached
    # the milestone = 90th percentile of per-building milestone days across the building
    # axis. Median + p90 are taken across realizations. Collapsed+demolished buildings
    # (which carry the full replacement duration) drive the high tail and ARE included.
    # Computed for whole / Makati (MC) / QC, for all three REDi milestones (the headline
    # is functional_recovery). Weighting basis = building COUNT (thesis-faithful; the
    # population-weighted "student-days" disruption DV is a separate thesis metric).
    def _recovery90_for(mask: np.ndarray) -> dict:
        return {
            "reoccupancy": _recovery_90pct_block(result.reoccupancy_days[mask]),
            "functional_recovery": _recovery_90pct_block(
                result.functional_recovery_days[mask]
            ),
            "full_recovery": _recovery_90pct_block(result.full_recovery_days[mask]),
        }

    recovery90_whole = _recovery90_for(np.ones(len(inv), dtype=bool))
    recovery90_mc = _recovery90_for(mc_mask)
    recovery90_qc = _recovery90_for(qc_mask)

    # Portfolio functional-recovery CURVE (fraction recovered vs day), mean over
    # realizations, on a shared 0..p99 grid — committable array for later plotting
    # (thesis Figure 7-5 / 7-14 recovery panel). Whole portfolio (count basis).
    fr_curve_t, fr_curve_frac = portfolio_recovery_curve(result.functional_recovery_days)

    collapse_rate = float(result.collapse_mask.mean())  # over all building-realizations
    demolition_rate = float(result.demolition_mask.mean())  # RDR-demolished (non-collapsed)

    # --- FEMA P-58 casualties (injuries + fatalities): the thesis's 2nd + 3rd DVs ----------
    # Portfolio (and city) casualty COUNT per realization = sum over the subset's buildings.
    # Ratio normaliser = that subset's total population (thesis: casualties / population).
    pop = result.population  # (n_buildings,)
    inj = result.injuries    # (n_buildings, n_real)
    fat = result.fatalities  # (n_buildings, n_real)
    inj_nc = result.injuries_noncollapse
    fat_nc = result.fatalities_noncollapse

    def _cas_for(mask: np.ndarray) -> dict:
        pop_sub = float(pop[mask].sum())
        inj_real = inj[mask].sum(axis=0)
        fat_real = fat[mask].sum(axis=0)
        inj_nc_real = inj_nc[mask].sum(axis=0)
        fat_nc_real = fat_nc[mask].sum(axis=0)
        # Non-collapse fraction of TOTAL injuries (thesis: 0.78-0.99 for existing case),
        # computed per realization then summarised (guard against zero-injury realizations).
        with np.errstate(divide="ignore", invalid="ignore"):
            nc_frac_inj = np.where(inj_real > 0, inj_nc_real / inj_real, np.nan)
            nc_frac_fat = np.where(fat_real > 0, fat_nc_real / fat_real, np.nan)
        return {
            "injuries": _casualty_block(inj_real, pop_sub),
            "fatalities": _casualty_block(fat_real, pop_sub),
            "population": pop_sub,
            "noncollapse_injury_fraction_median": (
                float(np.nanmedian(nc_frac_inj)) if np.isfinite(nc_frac_inj).any() else 0.0
            ),
            "noncollapse_injury_fraction_mean": (
                float(np.nanmean(nc_frac_inj)) if np.isfinite(nc_frac_inj).any() else 0.0
            ),
            "noncollapse_fatality_fraction_median": (
                float(np.nanmedian(nc_frac_fat)) if np.isfinite(nc_frac_fat).any() else 0.0
            ),
        }

    all_mask = np.ones(len(inv), dtype=bool)
    casualties_whole = _cas_for(all_mask)
    casualties_mc = _cas_for(mc_mask)
    casualties_qc = _cas_for(qc_mask)

    # --- 3-way loss-source decomposition: collapse / demolition / component --------
    # repair_cost_php holds the per-cell PHP loss; collapse AND demolition cells ==
    # own replacement cost (total loss). The three masks are mutually exclusive by
    # construction (sample_demolition excludes collapsed cells), so the shares sum to 1.
    cmask = result.collapse_mask
    dmask = result.demolition_mask
    comp_mask = ~(cmask | dmask)  # component repair only (non-collapsed, non-demolished)
    total_loss = float(loss_php.sum())
    collapse_loss = float(loss_php[cmask].sum())
    demolition_loss = float(loss_php[dmask].sum())
    component_loss = float(loss_php[comp_mask].sum())
    # Component-repair-only loss-ratio distribution (excludes both total-loss paths).
    comp_cell_lr = result.loss_ratio[comp_mask]
    nc_mean = float(comp_cell_lr.mean()) if comp_cell_lr.size else 0.0
    nc_median = float(np.median(comp_cell_lr)) if comp_cell_lr.size else 0.0
    loss_source = {
        "collapse_share_of_total_loss": (collapse_loss / total_loss) if total_loss > 0 else 0.0,
        "demolition_share_of_total_loss": (
            (demolition_loss / total_loss) if total_loss > 0 else 0.0
        ),
        "component_share_of_total_loss": (
            (component_loss / total_loss) if total_loss > 0 else 0.0
        ),
        "noncollapse_cell_loss_ratio_mean": nc_mean,
        "noncollapse_cell_loss_ratio_median": nc_median,
    }

    # --- Recovery-milestone degeneracy probe ------------------------------------
    # Guardrail: if every component mapped to Repair Class 1 (the old placeholder
    # inventory), rc2 == rc3 == 0 and the three REDi milestones would coincide exactly.
    # With the real per-archetype Table D-13 population this should be False; we keep
    # the probe to catch a silent regression back to a single-class inventory.
    ro_eq_fr = bool(np.array_equal(result.reoccupancy_days, result.functional_recovery_days))
    fr_eq_full = bool(np.array_equal(result.functional_recovery_days, result.full_recovery_days))
    milestones_degenerate = ro_eq_fr and fr_eq_full

    # --- Mitigation (TWO layers) flag + coverage --------------------------------------
    # The mitigated run applies BOTH the thesis layers: (1) STRUCTURAL FRP retrofit of the
    # non-ductile RCMRF (fatality reduction; coverage-limited to C1-M (Pre/Lo) by recovered
    # EDPs); (2) NON-STRUCTURAL equipment upgrade (injury reduction; portfolio-wide component
    # swap, not coverage-limited). Record both so the reduction is interpretable.
    mitigated = bool(getattr(result, "mitigated", False))
    coverage = mitigation_coverage(inv)

    return {
        "scenario_id": result.scenario_id,
        "mitigated": mitigated,
        "mitigation": {
            "applied": mitigated,
            "structural_frp": {
                "retrofit_map": coverage["retrofit_map"],
                "coverage": {
                    "whole": coverage["whole"],
                    "makati_MC": coverage["MC"],
                    "quezon_QC": coverage["QC"],
                },
                "effect": "collapse-risk reduction -> FATALITY reduction",
                "note": (
                    "Structural FRP retrofit. Reproducible coverage = C1-M (Pre/Lo) only (the "
                    "one archetype with recovered R1 EDPs, collapse Sa 1.11 g -> 2.12 g). The "
                    "thesis retrofitted the WHOLE ductile/non-ductile RC moment-frame stock "
                    "(C1-L MCHC, C1-M HC/MC/PCLC, PTC1-M HC/MC per WVF_7_3_R1_PA.mat), so the "
                    "thesis FATALITY reduction is larger than ours by construction. Not tuned."
                ),
            },
            "nonstructural": {
                "substitutions": coverage["nonstructural_substitutions"],
                "removed": coverage["nonstructural_removed"],
                "scope": (
                    "portfolio-wide for the upgraded acceleration/drift-sensitive "
                    "non-structural components"
                ),
                "effect": (
                    "falling-hazard INJURY reduction (neutralises non-collapse component injuries)"
                ),
                "note": (
                    "Non-structural equipment upgrade (thesis Table 6-3): brace ceilings "
                    "(CLG.NS->CLG.BR), anchor/safety-wire fixtures (FIX.NS->FIX.SE, no casualty), "
                    "reinforce CHB (SU/PU->SR/PR), remove desktop & wall-mounted electronics "
                    "from the mitigated models. Applied to every building carrying these "
                    "components -> NOT coverage-limited. This is the headline INJURY-reduction "
                    "layer. Component-level fragility swap only — no new EDPs. Not tuned."
                ),
            },
        },
        "n_realizations": N,
        "n_buildings": int(len(inv)),
        "n_buildings_makati_MC": int(mc_mask.sum()),
        "n_buildings_quezon_QC": int(qc_mask.sum()),
        "total_replacement_cost_php": float(repl.sum()),
        "whole_portfolio": {
            "loss_ratio": _pctile_block(whole_lr),
            "total_loss_php": _pctile_block(result.portfolio_loss_php),
            "casualties": casualties_whole,
        },
        "makati_MC": {"loss_ratio": _pctile_block(mc_lr), "casualties": casualties_mc},
        "quezon_QC": {"loss_ratio": _pctile_block(qc_lr), "casualties": casualties_qc},
        "per_archetype_loss_ratio": per_arch,
        "recovery_days_portfolio_mean": {
            "reoccupancy": _pctile_block(reocc_pf),
            "functional_recovery": _pctile_block(func_pf),
            "full_recovery": _pctile_block(full_pf),
        },
        # THESIS PRIMARY RESILIENCE METRIC: time (days) to 90% portfolio recovery.
        # Per realization = (count-basis) day at which 90% of buildings reached the
        # milestone (90th percentile of per-building days across buildings); median +
        # p90 are taken across the 1000 realizations. Headline = functional_recovery.
        # Thesis WVF-7.3 targets: Makati 970 (p90 1070); QC 640 (p90 655). [§7.3.4.1]
        "recovery_90pct_functional_days": {
            "weighting_basis": "building_count",
            "definition": (
                "per realization: 90th percentile across buildings of the per-building "
                "recovery-milestone day (= time at which 90% of buildings, by count, "
                "have recovered); median + p90 across realizations. Thesis "
                "Portfolio_Analysis_2021.m line 214 (prctile(R_Func,90,1)). "
                "Collapsed+demolished buildings carry full replacement duration and "
                "drive the tail."
            ),
            "whole_portfolio": recovery90_whole,
            "makati_MC": recovery90_mc,
            "quezon_QC": recovery90_qc,
            "thesis_targets_WVF73": {
                "makati_MC": {
                    "functional_recovery_median_days": 970,
                    "functional_recovery_p90_days": 1070,
                },
                "quezon_QC": {
                    "functional_recovery_median_days": 640,
                    "functional_recovery_p90_days": 655,
                },
                "source": (
                    "Jeswani 2021 §7.4.4 p.181 + WVF_7_3_PA.mat PA_R[4]"
                    " (QC Func-90% median=652, p90=661)"
                ),
                "provenance_confidence": "medium",
                "note": (
                    "Thesis used North American REDi impeding values"
                    " (authors flagged for further review)."
                ),
            },
        },
        # Mean portfolio functional-recovery CURVE (fraction recovered vs day) for
        # later plotting (thesis Fig 7-5 / 7-14 recovery panel). Whole portfolio, count
        # basis. Stored as parallel day/fraction arrays.
        "recovery_curve_functional": {
            "days": [float(x) for x in fr_curve_t],
            "fraction_recovered": [float(x) for x in fr_curve_frac],
            "basis": "whole_portfolio_building_count_mean_over_realizations",
        },
        "collapse_rate_building_realizations": collapse_rate,
        "demolition_rate_building_realizations": demolition_rate,
        "extrapolated_fraction_above_edp_stripe": result.extrapolated_fraction,
        "loss_source_decomposition": loss_source,
        "model_caveats": {
            # Honest, machine-readable flags so downstream readers (and the P7
            # formal validation) understand how the headline loss is composed.
            "loss_is_total_loss_dominated": bool(
                (
                    loss_source["collapse_share_of_total_loss"]
                    + loss_source["demolition_share_of_total_loss"]
                )
                > 0.5
            ),
            "loss_is_collapse_dominated": bool(
                loss_source["collapse_share_of_total_loss"] > 0.5
            ),
            "recovery_milestones_degenerate": milestones_degenerate,
            "note": (
                "Loss is decomposed 3 ways: collapse (Sa>collapse fragility -> "
                "replacement), residual-drift demolition (peak RIDR > the archetype's "
                "FEMA P-58 / Ramirez & Miranda 2012 demolition fragility, median = thesis "
                "Table 6-6 'Residual Drift Limit', beta=0.30 -> replacement), and component "
                "repair (Pelicun damage->loss on the real FEMA P-58 Table D-13 component "
                "inventory). The three shares sum to 1. Demolition closes the previously "
                "'cold' pre-code / pseudo-EDP archetypes (e.g. C1-L (Pre/Lo)) that the "
                "2021 Thesis demolished once residual drift passed ~1%; archetypes whose "
                "thesis residual-drift limit is 0.0% (residual drift NOT a governing "
                "criterion, e.g. CWS-L) get NO demolition by design. The three REDi "
                "recovery milestones (reoccupancy < functional < full) differentiate via "
                "the rc1/rc2/rc3 spread; total-loss (collapse OR demolition) cells take the "
                "full replacement duration. 'loss_is_total_loss_dominated' reports whether "
                "collapse+demolition exceeds 50% of total loss (a physical property of WVF "
                "Mw7.3, not an artefact). Real components + hazard (correct sigma) + "
                "collapse + residual-drift demolition + spatial correlation + per-building "
                "replacement are all live."
            ),
        },
        "provenance": {
            "hazard": "hazard.scenario_sa_field (Loth-Baker 2013 correlated; per-branch "
                      "mean tau/phi single-event aleatory sigma)",
            "edp": "real multi-stripe PERFORM-3D EDPs via edp.demand_for_sa_field "
                   "(per-realization Sa interpolation); residual-drift demolition demand "
                   "via edp.median_residual_drift_for_sa_field (MEDIAN peak RIDR, capped at "
                   "top calibrated stripe)",
            "loss": "Pelicun component damage->loss; collapse->replacement override AND "
                    "residual-drift demolition override (FEMA P-58 2018a sec 7.6 / Ramirez & "
                    "Miranda 2012: median-conditioned lognormal demolition fragility, median "
                    "RIDR = thesis Table 6-6, beta=0.30; residual median NOT extrapolated "
                    "above the calibrated stripe range) -> per-building replacement_cost_php "
                    "/ replacement_time_days",
            "recovery": "recovery.py REDi 3-milestone (PH-calibrated impeding factors)",
            "casualties": "casualties.py FEMA P-58 model: (a) non-collapse component injuries "
                          "via the affected-area model (thesis Tables D-1/D-2 thetas + areas, "
                          "casualty_consequences.json) on non-collapsed realizations; (b) "
                          "collapse injuries/fatalities = collapse * population * P(TC) * "
                          "{HAZUS-typology collapse fatality rate; injury = 1 - fatality} "
                          "(thesis Ch 6.2.6.2). Scaled by per-building actual population. "
                          "Demolition is NOT a casualty event. Collapse fatality rates inherit "
                          "the loss-pipeline collapse-rate (which runs higher than the "
                          "2021 Thesis), so fatalities run high vs the thesis anchor — see "
                          "docs/learnings/2026-06-27_casualties.md.",
            "generated_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        },
    }
