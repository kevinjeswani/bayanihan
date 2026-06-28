"""Run the real-data WVF Mw 7.3 correlated portfolio loss + recovery (P5/P7).

Executes ``ScenarioPortfolio`` on the gitignored real 1,021-building inventory using
the spatially-correlated Sa(T1) field (``hazard.scenario_sa_field``) and the real
multi-stripe PERFORM-3D EDPs (``edp.demand_for_sa_field``), then writes:

  * COMMITTABLE aggregates JSON (no per-building identifiers/coords) ->
    ``bayanihan/data/results/wvf73_portfolio_summary.json``
  * GITIGNORED per-building / per-realization detail (derived real data) ->
    ``sandbox/portfolio-analysis/wvf73_*.{parquet,npz}``

Usage:
    .venv/bin/python scripts/run_wvf73_portfolio.py [N] [SEED]

Defaults: N=1000 (thesis-matching), SEED=12345.

This is HARD SCOPE compliant: it consumes recovered/derived inputs only — no
structural re-analysis, no new ground motions.

Refs: Jeswani et al. 2022 (EQ Spectra, 38(3), 1946-1971); Jeswani 2021 (MASc thesis, U of T).
"""
from __future__ import annotations

import json
import logging
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logging.getLogger("pelicun").setLevel(logging.ERROR)

from bayanihan.portfolio import (  # noqa: E402
    ScenarioPortfolio,
    summarise_scenario_result,
)

REPO = Path(__file__).resolve().parent.parent
RESULTS_DIR = REPO / "bayanihan" / "data" / "results"
SANDBOX_DIR = REPO / "sandbox" / "portfolio-analysis"


def main(n_realizations: int = 1000, seed: int = 12345, scenario_id: str = "WVF_7.3") -> dict:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    SANDBOX_DIR.mkdir(parents=True, exist_ok=True)

    sp = ScenarioPortfolio.from_real_inventory(
        scenario_id=scenario_id, n_realizations=n_realizations, seed=seed
    )
    result = sp.run(progress_every=100)
    summary = summarise_scenario_result(result)

    # ---- committable aggregates JSON (identifier-free) --------------------
    summary_path = RESULTS_DIR / "wvf73_portfolio_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    # ---- gitignored per-building / per-realization detail -----------------
    inv = result.inventory
    # Per-building summary across realizations (carries building_id -> sandbox only).
    per_bldg = pd.DataFrame(
        {
            "building_id": inv["building_id"].to_numpy(),
            "city": inv["city"].to_numpy(),
            "archetype": inv["archetype"].to_numpy(),
            "edp_soil_bin": inv["edp_soil_bin"].to_numpy(),
            "replacement_cost_php": result.replacement_cost_php,
            "mean_loss_ratio": result.loss_ratio.mean(axis=1),
            "median_loss_ratio": np.median(result.loss_ratio, axis=1),
            "p84_loss_ratio": np.percentile(result.loss_ratio, 84, axis=1),
            "collapse_rate": result.collapse_mask.mean(axis=1),
            "mean_reoccupancy_days": result.reoccupancy_days.mean(axis=1),
            "mean_functional_recovery_days": result.functional_recovery_days.mean(axis=1),
            "mean_full_recovery_days": result.full_recovery_days.mean(axis=1),
        }
    )
    per_bldg.to_parquet(SANDBOX_DIR / "wvf73_per_building.parquet")

    # Full per-building x per-realization arrays + portfolio vectors.
    np.savez_compressed(
        SANDBOX_DIR / "wvf73_arrays.npz",
        loss_ratio=result.loss_ratio,
        loss_php=result.repair_cost_php,
        collapse_mask=result.collapse_mask,
        demolition_mask=result.demolition_mask,
        reoccupancy_days=result.reoccupancy_days,
        functional_recovery_days=result.functional_recovery_days,
        full_recovery_days=result.full_recovery_days,
        portfolio_loss_php=result.portfolio_loss_php,
        portfolio_loss_ratio=result.portfolio_loss_ratio,
        building_id=inv["building_id"].to_numpy().astype(str),
        city=inv["city"].to_numpy().astype(str),
    )
    # Sa field (derived real data) -> sandbox.
    result.sa_field.to_parquet(SANDBOX_DIR / "wvf73_sa_field.parquet")

    # Per-building casualty detail -> sandbox (carries no extra identifiers beyond above).
    per_bldg_cas = pd.DataFrame(
        {
            "building_id": inv["building_id"].to_numpy(),
            "city": inv["city"].to_numpy(),
            "archetype": inv["archetype"].to_numpy(),
            "population": result.population,
            "median_injuries": np.median(result.injuries, axis=1),
            "median_fatalities": np.median(result.fatalities, axis=1),
            "median_injuries_noncollapse": np.median(result.injuries_noncollapse, axis=1),
        }
    )
    per_bldg_cas.to_parquet(SANDBOX_DIR / "wvf73_per_building_casualties.parquet")

    # ---- console headline -------------------------------------------------
    wp = summary["whole_portfolio"]["loss_ratio"]
    mc = summary["makati_MC"]["loss_ratio"]
    qc = summary["quezon_QC"]["loss_ratio"]
    rec = summary["recovery_days_portfolio_mean"]
    print("\n" + "=" * 64)
    print(f"WVF Mw 7.3 PORTFOLIO  (N={n_realizations}, seed={seed})")
    print("=" * 64)
    print(f"Whole-portfolio loss ratio : {wp['mean']:.3f}  "
          f"(p16 {wp['p16']:.3f} / p50 {wp['p50']:.3f} / p84 {wp['p84']:.3f})")
    print(f"Makati (MC) loss ratio     : {mc['mean']:.3f}  "
          f"(p16 {mc['p16']:.3f} / p84 {mc['p84']:.3f})   <-- thesis ~0.26")
    print(f"Quezon City (QC) loss ratio: {qc['mean']:.3f}")
    print(f"Total portfolio loss (PHP) : "
          f"{summary['whole_portfolio']['total_loss_php']['mean']:.3e}")
    print(f"Collapse rate (bldg-real)  : "
          f"{summary['collapse_rate_building_realizations']:.3f}")
    print(f"Demolition rate (bldg-real): "
          f"{summary['demolition_rate_building_realizations']:.3f}  (RDR-triggered, non-collapsed)")
    ls = summary["loss_source_decomposition"]
    print(f"Loss-source split          : "
          f"collapse {ls['collapse_share_of_total_loss']:.3f} / "
          f"demolition {ls['demolition_share_of_total_loss']:.3f} / "
          f"component {ls['component_share_of_total_loss']:.3f}")
    print(f"Extrapolated above stripe  : "
          f"{summary['extrapolated_fraction_above_edp_stripe']:.3f}")
    print("Recovery (portfolio-mean days):")
    print(f"   reoccupancy   mean {rec['reoccupancy']['mean']:.0f} "
          f"(p84 {rec['reoccupancy']['p84']:.0f})")
    print(f"   functional    mean {rec['functional_recovery']['mean']:.0f} "
          f"(p84 {rec['functional_recovery']['p84']:.0f})  [PRIMARY]")
    print(f"   full recovery mean {rec['full_recovery']['mean']:.0f} "
          f"(p84 {rec['full_recovery']['p84']:.0f})  "
          f"= {rec['full_recovery']['mean']/365.25:.2f} yr")
    # --- Casualties (FEMA P-58 injuries + fatalities) ---
    mcc = summary["makati_MC"]["casualties"]
    qcc = summary["quezon_QC"]["casualties"]
    whc = summary["whole_portfolio"]["casualties"]
    print("Casualties (median count | ratio):")
    print(f"   Makati  injuries {mcc['injuries']['count']['median']:.0f} "
          f"({mcc['injuries']['ratio']['median']*100:.1f}%)  <-- thesis 13650 (14.5%)")
    print(f"   Makati  fatalities {mcc['fatalities']['count']['median']:.0f} "
          f"({mcc['fatalities']['ratio']['median']*100:.2f}%)  <-- thesis 320 (0.3%)")
    print(f"   QC      injuries {qcc['injuries']['count']['median']:.0f} "
          f"({qcc['injuries']['ratio']['median']*100:.1f}%)  <-- thesis (9.1%)")
    print(f"   QC      fatalities {qcc['fatalities']['count']['median']:.0f} "
          f"({qcc['fatalities']['ratio']['median']*100:.2f}%)  <-- thesis 900 (0.2%)")
    print(f"   Whole   injuries {whc['injuries']['count']['median']:.0f}  "
          f"fatalities {whc['fatalities']['count']['median']:.0f}  "
          f"<-- .mat PA_CasI~58117 / PA_CasF~2899")
    print(f"   Non-collapse injury fraction (whole, median): "
          f"{whc['noncollapse_injury_fraction_median']:.2f}  <-- thesis 0.78-0.99")
    print("=" * 64)
    print(f"committable summary -> {summary_path.relative_to(REPO)}")
    print(f"sandbox detail      -> {SANDBOX_DIR.relative_to(REPO)}/")
    return summary


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 1000
    s = int(sys.argv[2]) if len(sys.argv) > 2 else 12345
    main(n_realizations=n, seed=s)
