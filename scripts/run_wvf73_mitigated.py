"""Run the real-data WVF Mw 7.3 BASE vs MITIGATED portfolio (P7).

The thesis's headline contribution is a Base-vs-Mitigated comparison (Jeswani 2021
§7.4; companion EQ Spectra 2022) using TWO simultaneous mitigation layers:

  (1) STRUCTURAL FRP retrofit of the non-ductile RCMRF -> collapse-risk down -> FATALITY
      reduction. The thesis retrofitted the WHOLE ductile/non-ductile RC moment-frame
      stock (the ``_R1`` archetypes in ``WVF_7_3_R1_PA.mat``: C1-L MCHC, C1-M HC/MC/PCLC,
      PTC1-M HC/MC). We only RECOVERED the FRP-retrofit EDPs for ``C1-M (Pre/Lo)`` (collapse
      Sa 1.11 g -> 2.12 g), so the reproducible STRUCTURAL layer is the
      ``C1-M (Pre/Lo) -> C1-M (Pre/Lo) FRP`` swap only -> our FATALITY reduction is smaller
      than the thesis's by construction (reported honestly, NOT tuned).

  (2) NON-STRUCTURAL equipment upgrade (Table 6-3) -> falling-hazard INJURY reduction.
      Portfolio-wide component fragility swap: brace ceilings, safety-wire fixtures,
      reinforce CHB, remove electronics. NOT coverage-limited (applies to every building
      carrying those components). This is the headline INJURY benefit and is fully
      reproducible. Component swap only — no new EDPs.

The mitigated run applies BOTH layers simultaneously (``mitigated=True``).

Runs both the base and mitigated portfolios on the gitignored real 1,021-building
inventory (same seed/hazard field) and writes:

  * COMMITTABLE mitigated aggregates JSON (identifier-free) ->
    ``bayanihan/data/results/wvf73_mitigated_portfolio_summary.json``
  * COMMITTABLE base-vs-mitigated comparison JSON ->
    ``bayanihan/data/results/wvf73_base_vs_mitigated.json``
  * GITIGNORED per-realization arrays (derived real data) ->
    ``sandbox/portfolio-analysis/wvf73_mitigated_arrays.npz``

HARD SCOPE compliant: recovered/derived inputs only — no structural re-analysis.

Usage:
    .venv/bin/python scripts/run_wvf73_mitigated.py [N] [SEED]

Defaults: N=1000 (thesis-matching), SEED=12345.

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

# Thesis WVF-7.3 anchors (Jeswani 2021; docs/thesis/data/portfolio_validation.yaml).
THESIS = {
    "MC": {"base_loss_ratio": 0.26, "mit_loss_ratio": 0.18,
           "base_injury_ratio": 0.145, "mit_injury_ratio": 0.011,
           "base_fatality_ratio": 0.003, "mit_fatality_ratio": 0.0004},
    "QC": {"base_loss_ratio": 0.31, "mit_injury_ratio": 0.023,
           "mit_fatality_ratio": 0.001},
}
# .mat WVF_7_3(_R1)_PA whole-portfolio anchors (PA_*_prc col 7 = median, col 11 = p90).
MAT = {
    "base": {"loss_php_median": 7.826e9, "loss_php_p90": 1.074e10,
             "casI_median": 5.812e4, "casF_median": 2899.0},
    "mit": {"loss_php_median": 6.507e9, "loss_php_p90": 8.957e9,
            "casI_median": 1.627e4, "casF_median": 953.2},
}


def _run(mitigated: bool, n: int, seed: int, scenario_id: str):
    sp = ScenarioPortfolio.from_real_inventory(
        scenario_id=scenario_id, n_realizations=n, seed=seed, mitigated=mitigated
    )
    res = sp.run(progress_every=200)
    return res, summarise_scenario_result(res)


def _city(summary, key):
    lr = summary[key]["loss_ratio"]
    cas = summary[key]["casualties"]
    return {
        "loss_ratio_mean": lr["mean"],
        "loss_ratio_median": lr["p50"],
        "loss_ratio_p90": lr.get("p90"),
        "injury_ratio_median": cas["injuries"]["ratio"]["median"],
        "fatality_ratio_median": cas["fatalities"]["ratio"]["median"],
        "injuries_median": cas["injuries"]["count"]["median"],
        "fatalities_median": cas["fatalities"]["count"]["median"],
    }


def main(n_realizations: int = 1000, seed: int = 12345, scenario_id: str = "WVF_7.3") -> dict:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    SANDBOX_DIR.mkdir(parents=True, exist_ok=True)

    log = logging.getLogger("mitigated")
    log.info("=== BASE run (N=%d, seed=%d) ===", n_realizations, seed)
    base_res, base_sum = _run(False, n_realizations, seed, scenario_id)
    log.info("=== MITIGATED run (structural FRP + non-structural) (N=%d, seed=%d) ===", n_realizations, seed)
    mit_res, mit_sum = _run(True, n_realizations, seed, scenario_id)

    # ---- committable mitigated summary -----------------------------------
    (RESULTS_DIR / "wvf73_mitigated_portfolio_summary.json").write_text(
        json.dumps(mit_sum, indent=2), encoding="utf-8"
    )

    # ---- base-vs-mitigated comparison ------------------------------------
    struct = mit_sum["mitigation"]["structural_frp"]
    cov = struct["coverage"]
    ns = mit_sum["mitigation"]["nonstructural"]
    comparison = {
        "scenario_id": scenario_id,
        "n_realizations": n_realizations,
        "seed": seed,
        "mitigation_strategy": (
            "TWO simultaneous layers (thesis): (1) STRUCTURAL FRP retrofit of the non-ductile "
            "RCMRF (collapse-risk -> fatality reduction); (2) NON-STRUCTURAL equipment upgrade "
            "(Table 6-3 component swap: braced ceilings, safety-wired fixtures, reinforced CHB, "
            "electronics removed -> falling-hazard injury reduction)."
        ),
        "structural_layer": (
            "FRP retrofit of C1-M (Pre/Lo) RC moment frames (the only archetype with recovered "
            "R1 EDPs; collapse Sa 1.11 g -> 2.12 g). Those buildings swap to the C1-M (Pre/Lo) "
            "FRP EDP/collapse fragility + FRP component model. The thesis retrofitted the WHOLE "
            "RC moment-frame stock (C1-L MCHC, C1-M HC/MC/PCLC, PTC1-M HC/MC per "
            f"WVF_7_3_R1_PA.mat); we reach {cov['whole']['n_retrofitted']}/"
            f"{cov['whole']['n_buildings']} buildings "
            f"({cov['whole']['fraction_retrofitted_by_cost']*100:.1f}% of value; "
            f"MC {cov['makati_MC']['n_retrofitted']}/{cov['makati_MC']['n_buildings']}, "
            f"QC {cov['quezon_QC']['n_retrofitted']}/{cov['quezon_QC']['n_buildings']}). The "
            "structural layer -> FATALITY reduction is therefore smaller than the thesis's. Not tuned."
        ),
        "nonstructural_layer": (
            "Portfolio-wide component swap (NOT coverage-limited): "
            f"{ns['substitutions']} ; removed {ns['removed']}. Applied to every building carrying "
            f"these acceleration/drift-sensitive components ({cov['whole']['n_nonstructural_upgraded']}/"
            f"{cov['whole']['n_buildings']} buildings). This is the headline INJURY-reduction layer "
            "(neutralises non-collapse component injuries). Component fragility swap only — no new EDPs."
        ),
        "coverage": cov,
        "nonstructural": ns,
        "base": {
            "whole": _city(base_sum, "whole_portfolio"),
            "makati_MC": _city(base_sum, "makati_MC"),
            "quezon_QC": _city(base_sum, "quezon_QC"),
            "total_loss_php_median": base_sum["whole_portfolio"]["total_loss_php"]["p50"],
            "total_loss_php_p90": base_sum["whole_portfolio"]["total_loss_php"].get("p90"),
            "collapse_rate": base_sum["collapse_rate_building_realizations"],
            "demolition_rate": base_sum["demolition_rate_building_realizations"],
            "loss_source": base_sum["loss_source_decomposition"],
        },
        "mitigated": {
            "whole": _city(mit_sum, "whole_portfolio"),
            "makati_MC": _city(mit_sum, "makati_MC"),
            "quezon_QC": _city(mit_sum, "quezon_QC"),
            "total_loss_php_median": mit_sum["whole_portfolio"]["total_loss_php"]["p50"],
            "total_loss_php_p90": mit_sum["whole_portfolio"]["total_loss_php"].get("p90"),
            "collapse_rate": mit_sum["collapse_rate_building_realizations"],
            "demolition_rate": mit_sum["demolition_rate_building_realizations"],
            "loss_source": mit_sum["loss_source_decomposition"],
        },
        "thesis_targets": THESIS,
        "mat_anchors_whole_portfolio": MAT,
    }
    # Reduction summary (ours).
    def _red(b, m):
        return None if not b else round((b - m) / b, 4)
    comparison["reduction_ours"] = {
        "whole_loss_ratio_median": _red(
            comparison["base"]["whole"]["loss_ratio_median"],
            comparison["mitigated"]["whole"]["loss_ratio_median"],
        ),
        "makati_loss_ratio_median": _red(
            comparison["base"]["makati_MC"]["loss_ratio_median"],
            comparison["mitigated"]["makati_MC"]["loss_ratio_median"],
        ),
        "whole_total_loss_php_median": _red(
            comparison["base"]["total_loss_php_median"],
            comparison["mitigated"]["total_loss_php_median"],
        ),
        "whole_injuries_median": _red(
            comparison["base"]["whole"]["injuries_median"],
            comparison["mitigated"]["whole"]["injuries_median"],
        ),
        "makati_injuries_median": _red(
            comparison["base"]["makati_MC"]["injuries_median"],
            comparison["mitigated"]["makati_MC"]["injuries_median"],
        ),
        "qc_injuries_median": _red(
            comparison["base"]["quezon_QC"]["injuries_median"],
            comparison["mitigated"]["quezon_QC"]["injuries_median"],
        ),
        "makati_fatalities_median": _red(
            comparison["base"]["makati_MC"]["fatalities_median"],
            comparison["mitigated"]["makati_MC"]["fatalities_median"],
        ),
        "whole_fatalities_median": _red(
            comparison["base"]["whole"]["fatalities_median"],
            comparison["mitigated"]["whole"]["fatalities_median"],
        ),
    }
    (RESULTS_DIR / "wvf73_base_vs_mitigated.json").write_text(
        json.dumps(comparison, indent=2), encoding="utf-8"
    )

    # ---- gitignored per-realization arrays (mitigated) -------------------
    np.savez_compressed(
        SANDBOX_DIR / "wvf73_mitigated_arrays.npz",
        portfolio_loss_php=mit_res.portfolio_loss_php,
        portfolio_loss_ratio=mit_res.portfolio_loss_ratio,
        loss_php=mit_res.repair_cost_php,
        collapse_mask=mit_res.collapse_mask,
        demolition_mask=mit_res.demolition_mask,
        injuries=mit_res.injuries,
        fatalities=mit_res.fatalities,
        functional_recovery_days=mit_res.functional_recovery_days,
        city=mit_res.inventory["city"].to_numpy().astype(str),
        archetype=mit_res.inventory["archetype"].to_numpy().astype(str),
    )
    # Also stash the base arrays under a mitigation-run name for the figure script.
    np.savez_compressed(
        SANDBOX_DIR / "wvf73_base_arrays_for_mit.npz",
        portfolio_loss_php=base_res.portfolio_loss_php,
        portfolio_loss_ratio=base_res.portfolio_loss_ratio,
        loss_php=base_res.repair_cost_php,
        injuries=base_res.injuries,
        fatalities=base_res.fatalities,
        city=base_res.inventory["city"].to_numpy().astype(str),
    )

    # ---- console headline ------------------------------------------------
    b, m, r = comparison["base"], comparison["mitigated"], comparison["reduction_ours"]
    print("\n" + "=" * 72)
    print(f"WVF Mw 7.3  BASE vs MITIGATED (2 layers)  (N={n_realizations}, seed={seed})")
    print("=" * 72)
    print(f"Structural FRP coverage: {cov['whole']['n_retrofitted']}/{cov['whole']['n_buildings']} "
          f"buildings ({cov['whole']['fraction_retrofitted_by_cost']*100:.1f}% of value) "
          f"| MC {cov['makati_MC']['n_retrofitted']}/{cov['makati_MC']['n_buildings']}, "
          f"QC {cov['quezon_QC']['n_retrofitted']}/{cov['quezon_QC']['n_buildings']}")
    print(f"Non-structural upgrade:  {cov['whole']['n_nonstructural_upgraded']}/{cov['whole']['n_buildings']} "
          f"buildings (portfolio-wide for upgraded components)")
    print("-" * 72)
    print(f"{'metric':28s}{'base':>12s}{'mitigated':>12s}{'reduction':>11s}")
    print(f"{'whole loss ratio (p50)':28s}{b['whole']['loss_ratio_median']:>12.3f}"
          f"{m['whole']['loss_ratio_median']:>12.3f}{(r['whole_loss_ratio_median'] or 0)*100:>10.1f}%")
    print(f"{'Makati loss ratio (p50)':28s}{b['makati_MC']['loss_ratio_median']:>12.3f}"
          f"{m['makati_MC']['loss_ratio_median']:>12.3f}{(r['makati_loss_ratio_median'] or 0)*100:>10.1f}%"
          f"   thesis 0.26->0.18")
    print(f"{'QC loss ratio (p50)':28s}{b['quezon_QC']['loss_ratio_median']:>12.3f}"
          f"{m['quezon_QC']['loss_ratio_median']:>12.3f}")
    print(f"{'whole total loss (PHP)':28s}{b['total_loss_php_median']:>12.3e}"
          f"{m['total_loss_php_median']:>12.3e}{(r['whole_total_loss_php_median'] or 0)*100:>10.1f}%")
    print(f"{'  .mat anchor (PHP)':28s}{MAT['base']['loss_php_median']:>12.3e}"
          f"{MAT['mit']['loss_php_median']:>12.3e}")
    print(f"{'Makati injuries (p50)':28s}{b['makati_MC']['injuries_median']:>12.0f}"
          f"{m['makati_MC']['injuries_median']:>12.0f}{(r['makati_injuries_median'] or 0)*100:>10.1f}%")
    print(f"{'Makati fatalities (p50)':28s}{b['makati_MC']['fatalities_median']:>12.0f}"
          f"{m['makati_MC']['fatalities_median']:>12.0f}{(r['makati_fatalities_median'] or 0)*100:>10.1f}%")
    print(f"{'whole injuries (p50)':28s}{b['whole']['injuries_median']:>12.0f}"
          f"{m['whole']['injuries_median']:>12.0f}")
    print(f"{'  .mat anchor':28s}{MAT['base']['casI_median']:>12.0f}{MAT['mit']['casI_median']:>12.0f}")
    print(f"{'whole fatalities (p50)':28s}{b['whole']['fatalities_median']:>12.0f}"
          f"{m['whole']['fatalities_median']:>12.0f}{(r['whole_fatalities_median'] or 0)*100:>10.1f}%")
    print(f"{'  .mat anchor':28s}{MAT['base']['casF_median']:>12.0f}{MAT['mit']['casF_median']:>12.0f}")
    print(f"{'collapse rate':28s}{b['collapse_rate']:>12.3f}{m['collapse_rate']:>12.3f}")
    print(f"{'demolition rate':28s}{b['demolition_rate']:>12.3f}{m['demolition_rate']:>12.3f}")
    print("=" * 72)
    print(f"committable mitigated summary -> "
          f"{(RESULTS_DIR / 'wvf73_mitigated_portfolio_summary.json').relative_to(REPO)}")
    print(f"committable comparison        -> "
          f"{(RESULTS_DIR / 'wvf73_base_vs_mitigated.json').relative_to(REPO)}")
    return comparison


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 1000
    s = int(sys.argv[2]) if len(sys.argv) > 2 else 12345
    main(n_realizations=n, seed=s)
