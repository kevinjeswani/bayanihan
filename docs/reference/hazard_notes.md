# Hazard Model Implementation Notes

**Phase:** hazard_model_v2  
**Date:** 2026-06-26  
**Outcome:** OpenQuake path (STEP 2A) — openquake.hazardlib used for all GMPEs.

---

## Decision: openquake.hazardlib (preferred path)

OpenQuake Engine 3.25.1 installs cleanly on Python 3.13 via `uv add openquake.engine`,
with one additional dependency (`fiona`) required to satisfy a geospatial import.

Verification: `uv run python -c "import openquake.hazardlib.gsim; print('ok')"` returns `ok`.
Full test suite remains at 1 pre-existing failure (test_inventory.py) after install.

The CLAUDE.md constraint ("No OpenQuake for v0.1") was explicitly overridden for this
implementation phase by the task prompt. The v0.2 national-model path now uses the same
openquake.hazardlib foundation already in place.

---

## GSIM Class Mapping (openquake.hazardlib 3.25.1)

| Thesis label | openquake class | Module |
|---|---|---|
| CY08 | `ChiouYoungs2008` | `openquake.hazardlib.gsim.chiou_youngs_2008` |
| BA08 | `BooreAtkinson2008` | `openquake.hazardlib.gsim.boore_atkinson_2008` |
| BSSA14 | `BooreEtAl2014` | `openquake.hazardlib.gsim.boore_2014` |
| Zhao06 crustal | `ZhaoEtAl2006Asc` | `openquake.hazardlib.gsim.zhao_2006` |
| Zhao06 interface | `ZhaoEtAl2006SInter` | `openquake.hazardlib.gsim.zhao_2006` |
| Youngs97 | `YoungsEtAl1997SInter` | `openquake.hazardlib.gsim.youngs_1997` |
| AB03 | `AtkinsonBoore2003SInter` | `openquake.hazardlib.gsim.atkinson_boore_2003` |
| Abrahamson16 (BC Hydro) | `AbrahamsonEtAl2015SInter` | `openquake.hazardlib.gsim.abrahamson_2015` |

Note: The thesis cites "Abrahamson, Gregor & Addo (2016)" but the OQ class is labelled 2015
(the BC Hydro subduction GMPE publication timeline spans 2015–2016; same model).

---

## API Notes

OpenQuake hazardlib 3.25.1 uses the vectorised `compute()` API:

```python
gsim.compute(ctx, imts, mean, sig, tau, phi)
```

where `ctx` is a `numpy.recarray` containing all rupture, distance, and site parameters.
`mean`, `sig`, `tau`, `phi` are output arrays shaped `(n_imts, n_sites)`.

`sig` = total sigma, `tau` = inter-event, `phi` = intra-event.

**Youngs97 caveat:** `YoungsEtAl1997SInter` provides only Total standard deviation
(`DEFINED_FOR_STANDARD_DEVIATION_TYPES = {Total}`); `tau` and `phi` return zeros.
Implementation partitions total sigma as `tau = sqrt(0.25) * sig` and derives `phi`
from the remainder — a standard approximation for subduction GMPEs where
between-event variance typically accounts for ~25% of total variance.

---

## Loth-Baker (2013) Spatial Correlation

Implemented natively in `loth_baker_correlation()` using the published Table 1
coefficients from Loth & Baker (2013), EESD 42(3), 397–417.

Three-range exponential model:
```
C(h) = b1 * exp(-3h/a1) + b2 * exp(-3h/a2) + b3 * I(h < 1e-6)
```

The nugget `b3` is only added at zero inter-site separation. For some period combinations
(notably T=2.0s), the published LB13 coefficients give b1+b2+b3 = 1.01 at h=0.
Values are clipped to [0, 1] to preserve strict correlation matrix properties.

Periods outside the [0.01, 10.0s] table range are clamped to the nearest endpoint.
Periods within the table range use bilinear interpolation in (T1, T2) space.

---

## Key Context Requirements per GSIM

| GSIM | Sites | Distances | Rupture |
|---|---|---|---|
| CY08 | vs30, z1pt0, vs30measured | rrup, rjb, rx | mag, dip, ztor, rake |
| BA08 | vs30 | rjb | mag, rake |
| BSSA14 | vs30 | rjb | mag, rake |
| Zhao06 Asc | vs30 | rrup | mag, rake, hypo_depth |
| Zhao06 SInter | vs30 | rrup | mag, hypo_depth |
| Youngs97 | vs30 | rrup | mag, hypo_depth |
| AB03 | vs30 | rrup | mag, hypo_depth |
| Abrahamson15 | vs30, backarc | rrup | mag |

For vertical strike-slip faults (WVF, EVF): `Rjb ≈ Rrup` (surface projection = hypocentral
horizontal distance); `rx = 0`.

---

## Files Changed

- `bayanihan/hazard.py` — full implementation
- `test/test_hazard.py` — 25 tests, all passing
- `pyproject.toml` — openquake.engine added via `uv add`
- `uv.lock` — updated

---

## Test Results

```
hazard tests: 25 passed
full suite:   297 passed, 1 failed (pre-existing test_inventory.py failure, unrelated)
```
