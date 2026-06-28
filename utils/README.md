# utils/

One-off helper scripts. Not part of the package. Not imported by tests or the package.

These run once (or rarely) to produce a persisted artifact that then lives in the repo.

| Script | Purpose | Output |
|--------|---------|--------|
| `perform3d_to_simcenter_edp.py` | Convert legacy PERFORM-3D EDP CSVs to SimCenter naming convention | `bayanihan/data/edps/*.csv` |

Scripts here are excluded from the wheel. They're visible on GitHub as part of the build narrative.
