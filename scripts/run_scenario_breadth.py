"""Run the real-data BASE portfolio for the non-WVF-7.3 thesis scenarios (P7 breadth).

Extends the WVF-7.3 runner to the other four thesis scenarios — three additional
shallow-crustal events and the Manila Trench subduction-interface event:

    WVF_6.5         West Valley Fault   Mw 6.5   crustal     (near-fault)
    EVF_6.6         East Valley Fault   Mw 6.6   crustal     (near/mid-field)
    GNW_7.2         General Nakar West  Mw 7.2   crustal     (far-field ~30-45 km)
    MnlTrench_8.15  Manila Trench       Mw 8.15  SUBDUCTION  (far-field ~100-118 km)

Each run uses ``ScenarioPortfolio`` on the gitignored real 1,021-building inventory
with the spatially-correlated Sa(T1) field (``hazard.scenario_sa_field`` — crustal_4
or subduction_interface_4 GMPE logic tree, picked from scenarios.json) and the real
multi-stripe PERFORM-3D EDPs (scenario-independent; only the hazard field changes).

Writes per scenario:
  * COMMITTABLE aggregates JSON (no per-building identifiers/coords) ->
    ``bayanihan/data/results/{tag}_portfolio_summary.json``
  * GITIGNORED per-realization arrays + Sa field (derived real data) ->
    ``sandbox/portfolio-analysis/{tag}_arrays.npz`` / ``{tag}_sa_field.parquet``

HARD SCOPE compliant: recovered/derived inputs only, GMPEs via openquake.hazardlib,
no structural re-analysis, no new ground motions. Distances used as-is from the thesis
workbooks. Not tuned.

Usage:
    .venv/bin/python scripts/run_scenario_breadth.py [N] [SEED] [scenario_id ...]

Defaults: N=1000, SEED=12345, all four non-WVF-7.3 scenarios.

Refs: Jeswani et al. 2022 (EQ Spectra, 38(3), 1946-1971); Jeswani 2021 (MASc thesis, U of T).
"""

from __future__ import annotations

import json
import logging
import sys
import warnings
from pathlib import Path

import numpy as np

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

# Filename tag per scenario id (keeps results filenames terse + stable).
TAG = {
    "WVF_6.5": "wvf65",
    "EVF_6.6": "evf66",
    "GNW_7.2": "gnw72",
    "MnlTrench_8.15": "mnlt815",
    "WVF_7.3": "wvf73",
}
DEFAULT_SCENARIOS = ["WVF_6.5", "EVF_6.6", "GNW_7.2", "MnlTrench_8.15"]


def run_one(scenario_id: str, n_realizations: int, seed: int) -> dict:
    tag = TAG.get(scenario_id, scenario_id.replace(".", "_"))
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    SANDBOX_DIR.mkdir(parents=True, exist_ok=True)

    sp = ScenarioPortfolio.from_real_inventory(
        scenario_id=scenario_id, n_realizations=n_realizations, seed=seed
    )
    result = sp.run(progress_every=250)
    summary = summarise_scenario_result(result)

    # ---- committable aggregates JSON (identifier-free) --------------------
    summary_path = RESULTS_DIR / f"{tag}_portfolio_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    # ---- gitignored per-realization arrays + Sa field --------------------
    inv = result.inventory
    np.savez_compressed(
        SANDBOX_DIR / f"{tag}_arrays.npz",
        loss_ratio=result.loss_ratio,
        loss_php=result.repair_cost_php,
        collapse_mask=result.collapse_mask,
        demolition_mask=result.demolition_mask,
        functional_recovery_days=result.functional_recovery_days,
        injuries=result.injuries,
        fatalities=result.fatalities,
        portfolio_loss_php=result.portfolio_loss_php,
        portfolio_loss_ratio=result.portfolio_loss_ratio,
        building_id=inv["building_id"].to_numpy().astype(str),
        city=inv["city"].to_numpy().astype(str),
    )
    result.sa_field.to_parquet(SANDBOX_DIR / f"{tag}_sa_field.parquet")

    _print_headline(scenario_id, n_realizations, seed, summary)
    print(f"committable summary -> {summary_path.relative_to(REPO)}")
    return summary


def _print_headline(scenario_id: str, n: int, seed: int, s: dict) -> None:
    wp = s["whole_portfolio"]["loss_ratio"]
    mc = s["makati_MC"]["loss_ratio"]
    qc = s["quezon_QC"]["loss_ratio"]
    mcc = s["makati_MC"]["casualties"]
    qcc = s["quezon_QC"]["casualties"]
    r90 = s["recovery_90pct_functional_days"]
    ls = s["loss_source_decomposition"]
    print("\n" + "=" * 66)
    print(f"{scenario_id} PORTFOLIO  (N={n}, seed={seed})")
    print("=" * 66)
    print(f"Whole loss ratio : median {wp['median']:.3f}  mean {wp['mean']:.3f}  "
          f"p90 {wp['p90']:.3f}")
    print(f"Makati loss ratio: median {mc['median']:.3f}  mean {mc['mean']:.3f}  "
          f"p90 {mc['p90']:.3f}")
    print(f"QC loss ratio    : median {qc['median']:.3f}  mean {qc['mean']:.3f}  "
          f"p90 {qc['p90']:.3f}")
    print(f"Collapse rate    : {s['collapse_rate_building_realizations']:.3f}  "
          f"Demolition rate: {s['demolition_rate_building_realizations']:.3f}")
    print(f"Loss-source split: collapse {ls['collapse_share_of_total_loss']:.2f} / "
          f"demolition {ls['demolition_share_of_total_loss']:.2f} / "
          f"component {ls['component_share_of_total_loss']:.2f}")
    print(f"Extrapolated above stripe: {s['extrapolated_fraction_above_edp_stripe']:.3f}")
    print(f"Injury ratio med : Makati {mcc['injuries']['ratio']['median']*100:.1f}%  "
          f"QC {qcc['injuries']['ratio']['median']*100:.1f}%")
    print(f"Fatality ratio md: Makati {mcc['fatalities']['ratio']['median']*100:.2f}%  "
          f"QC {qcc['fatalities']['ratio']['median']*100:.2f}%")
    print(f"90% FR (days) med: Makati {r90['makati_MC']['functional_recovery']['median']:.0f}  "
          f"QC {r90['quezon_QC']['functional_recovery']['median']:.0f}")


def main(n_realizations: int, seed: int, scenarios: list[str]) -> None:
    for sid in scenarios:
        run_one(sid, n_realizations=n_realizations, seed=seed)


if __name__ == "__main__":
    args = sys.argv[1:]
    n = int(args[0]) if len(args) >= 1 else 1000
    s = int(args[1]) if len(args) >= 2 else 12345
    scen = args[2:] if len(args) > 2 else DEFAULT_SCENARIOS
    main(n_realizations=n, seed=s, scenarios=scen)
