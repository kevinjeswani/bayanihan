# REDi Recovery Methodology — sources

This package models post-earthquake recovery with the REDi methodology (three recovery
milestones plus impeding-factor delays). It does **not** reproduce the REDi guidelines here —
for the authoritative methodology and parameter values, consult the primary sources directly:

- **Almufti, I. & Willford, M. (2013).** *REDi Rating System: Resilience-based Earthquake
  Design Initiative for the Next Generation of Buildings.* Arup. — the methodology, the repair
  sequences, and the default impeding-factor distributions (Appendix A4.3).
- **Thesis Chapter 6** — how REDi (v1.0) was applied to this school-building portfolio (the
  three downtime components and resource allocation): [`docs/thesis/06_vulnerability_loss_estimation.md`](../thesis/06_vulnerability_loss_estimation.md).

We do not restate or reproduce numeric parameter values from those sources here; the
Philippine-calibrated values this package actually uses live in
[`bayanihan/data/ph_redi_params.json`](../../bayanihan/data/ph_redi_params.json).

## The three recovery milestones

REDi defines three thresholds of post-earthquake functionality (Almufti & Willford 2013):

| Milestone | Meaning |
|---|---|
| **Re-occupancy** | building safe to occupy again (structural repairs complete) |
| **Functional recovery** | primary function restored (structural + critical mechanical/electrical/plumbing) |
| **Full recovery** | pre-earthquake condition restored (all repairs, including finishes) |

## How this package implements it

Pelicun 3.9 has no native recovery module, so the milestone + impeding-factor layer is ours
([`bayanihan/recovery.py`](../../bayanihan/recovery.py)): Pelicun computes per-repair-class
repair time, we sample Philippine-calibrated impeding-factor delays, and combine them into the
three milestones.

| Package symbol | Role |
|---|---|
| `recovery.py` → `ImpedingFactorParams` | the six REDi impeding-factor delays (inspection, financing, permitting, contractor & engineer mobilization, long-lead procurement), each as `{factor}_beta` + `{factor}_median_days` |
| `recovery.py` → `compute_recovery()` | combines repair time + impeding delays → reoccupancy / functional / full recovery days |
| `bayanihan/data/ph_redi_params.json` | the Philippine-calibrated impeding-factor values |

The impeding-factor delay distribution follows Aljawhari et al. (2023) (GEV), a deliberate
Philippine-calibration departure from the original REDi lognormal assumption — see the
`recovery.py` docstring for the rationale.
