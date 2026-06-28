# EDP Source Tables

Raw archetype-level Engineering Demand Parameter (EDP) tables from the 2021 MASc thesis.

## Contents

- `modelled/` — 15 CSV files: archetypes with direct PERFORM-3D NRHA results (multi-stripe
  Story Drift Ratio, Peak Floor Acceleration, and Building Residual Drift tables).
- `non_modelled/` — 17 CSV files: archetypes derived via SPO2IDA scaling from a parent
  PERFORM-3D model (filename suffix `PSEUDO` denotes SPO2IDA-extended results).

## Provenance

These are the author's own analytical outputs, generated during the thesis research
(Jeswani, K. K. (2021). *The Seismic Resilience of Critical Spatially-Distributed Building
Portfolios.* MASc thesis, University of Toronto.). The underlying structural analyses used
PERFORM-3D; SPO2IDA was used to extend demand estimates to non-modelled archetypes.

Each file contains a single archetype (one representative location: latitude 14.55036,
longitude 121.00892). There is NO per-building inventory data here — these are
archetype-level (typology-level) demand tables, equivalent to the plots and tables in
Chapters 4–5 of the publicly-archived thesis.

## Usage

The build script `scripts/build_edp_store.py` reads these CSVs and
regenerates the processed artefacts:

- `bayanihan/data/edps/edp_store.parquet` — multi-stripe demand table (all archetypes)
- `bayanihan/data/edps/collapse_fragility.parquet` — per-archetype collapse fragility params
- `bayanihan/data/edps/index.json` — archetype → soil-bin lookup index

Run `python scripts/build_edp_store.py` from the repo root to regenerate.
