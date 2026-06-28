# scripts/

**Production simulation runners.** These regenerate the committed result artifacts
(`bayanihan/data/results/*.json`) by running the real-data Monte-Carlo portfolio
pipeline end-to-end. They are **not** part of the test suite and **not** shipped in
the wheel — run them on demand (and on major lifts), not on every commit.

Each runner needs the gitignored real inventory
(`bayanihan/data/inventory/manila_schools_real.geojson`) and the per-scenario distance
tables. Without them the runners exit early; the fast test suite still passes (it does
not depend on the real data).

| Script | What it runs | Committed output |
|--------|--------------|------------------|
| `run_wvf73_portfolio.py` | Base WVF Mw 7.3 portfolio (the thesis Ch. 7 governing event), Makati + QC | `results/wvf73_portfolio_summary.json` |
| `run_wvf73_mitigated.py` | WVF 7.3 base **and** mitigated (structural FRP + non-structural equipment upgrades) + their delta | `results/wvf73_mitigated_portfolio_summary.json`, `results/wvf73_base_vs_mitigated.json` |
| `run_scenario_breadth.py` | The other four thesis scenarios (WVF 6.5, EVF 6.6, GNW 7.2, Manila Trench 8.15) | `results/{tag}_portfolio_summary.json` |

All three write only **identifier-free aggregates** to `bayanihan/data/results/`
(committable). Per-building / per-realization detail (which carries building IDs) is
written to `sandbox/portfolio-analysis/` — gitignored, never committed.

## Usage

```bash
# from the repo root, with the project venv
.venv/bin/python scripts/run_wvf73_portfolio.py            # N=1000, seed=12345 (defaults)
.venv/bin/python scripts/run_wvf73_portfolio.py 200 7      # custom N, seed (quick check)
.venv/bin/python scripts/run_wvf73_mitigated.py
.venv/bin/python scripts/run_scenario_breadth.py
```

Defaults reproduce the committed JSONs (N=1000, seed=12345). A full N=1000 real-data
run is minutes-scale per scenario — that is exactly why these live here and not in the
test suite.

## Scope

HARD-SCOPE compliant: these consume the author's recovered/derived analytical inputs
only — no structural re-analysis, no new ground motions. GMPEs via `openquake.hazardlib`.

Refs: Jeswani et al. (2022), *Earthquake Spectra* 38(3), 1946–1971;
Jeswani (2021), MASc thesis, University of Toronto.
