# Pelicun 3.9 — Recovery-Relevant Capabilities

**Investigation date:** 2026-06-26
**Pelicun version:** >=3.9, <4 (installed in `.venv`)
**Purpose:** Documents what Pelicun provides natively vs what must remain in our REDi layer for the `recovery.py` refactor.

---

## 1. Per-Component Repair Time — Available

Pelicun exposes **per-component repair time** (in `worker_hour` units) after `loss.calculate()` via:

```python
sample = asmnt.loss.sample          # MultiIndex columns: ['dv', 'loss', 'dmg', 'ds', 'loc', 'dir', 'uid']
time_sample = sample.xs('Time', level='dv', axis=1)
# Aggregate to per-component (sum over ds, loc, dir, uid):
time_per_cmp = time_sample.T.groupby(level='loss').sum().T
# Result: DataFrame (n_sims, n_components), values in worker_hours
```

Column levels on `asmnt.loss.sample`:
- `dv` — decision variable (`'Cost'` or `'Time'`)
- `loss` — component ID (e.g. `'PH.S.DRCMRF.1S'`, `'PH.NS.CHB.SU'`)
- `dmg` — damage component ID (same as `loss` for this project)
- `ds` — damage state string (e.g. `'1'`, `'2'`, `'3'`)
- `loc` — floor/location
- `dir` — direction
- `uid` — unique ID

The `time_per_cmp` DataFrame is the correct input for per-repair-class aggregation.

**Confirmed via direct inspection (sandbox run, 20 simulations):**
Components observed: `PH.NS.CHB.SU`, `PH.NS.CLG.NS`, `PH.NS.ELEC.DT`, `PH.S.DRCMRF.1S`, `PH.S.DRCMRF.2S`
Values are in `worker_hours` (our registered unit); convert to calendar days via `/ workers_per_day`.

---

## 2. Repair Schedule / Sequencing — Not Natively Computed

Pelicun 3.9 does **not** compute a repair schedule with crew allocation or REDi-style sequencing. The `aggregate_losses()` method returns:

- `repair_time-sequential` — sum of all component repair times (fully serial, worst case)
- `repair_time-parallel` — max across locations (floors) at a given time (fully parallel, best case)

Neither is a REDi repair schedule. Pelicun does not implement REDi's 8-sequence labor allocation model. The per-component repair time is in **worker_hours**, which our layer converts to calendar days by dividing by an assumed crew size (`workers_per_day`).

---

## 3. Functional Recovery / REDi Recovery Module — Not Present

Pelicun 3.9 has **no native functional-recovery, re-occupancy, or REDi module**. There is no:
- Repair class assignment
- Milestone computation (re-occupancy / functional recovery / full recovery)
- Impeding factor delays
- REDi-style critical-path downtime model

Searched: `assessment.py`, `loss_model.py`, `damage_model.py`, all `tools/` modules. No hits for `recover`, `REDi`, `redi`, `functional`, `reoccupancy`, `milestone`, or `repair_class`.

---

## 4. What Pelicun Provides vs Our REDi Layer

| Capability | Pelicun 3.9 | Our `recovery.py` |
|---|---|---|
| Per-component repair time (worker_hours) | **YES** — `loss.sample` → `xs('Time')` → groupby `loss` | Consumes this |
| Per-repair-class aggregation | **NO** — must group by class using YAML mapping | Implements this |
| Repair sequencing (crew/labor model) | **NO** — only serial/parallel bounds | Implements simplified (worker_hours → calendar days) |
| Milestone gating (RO/FR/Full) | **NO** | Implements from repair-class sums |
| Impeding factor delays (inspection, financing, etc.) | **NO** | Implements with PH-calibrated lognormal params |
| Philippine-calibrated parameters | **NO** | Sources from `ph_redi_params.json` |

---

## 5. Repair-Class → Component Mapping (from YAML)

Source: `docs/thesis/data/redi_impedance_factors.yaml`, `repair_class_assignments`, Table D-16.

The YAML maps component *types* (thesis labels) to repair classes per damage state. For our
`_DEFAULT_CMP_INVENTORY` components (and the consequence_repair.csv set), the mapping is:

| Component ID prefix | Thesis type | DS1 RC | DS2 RC | DS3 RC |
|---|---|---|---|---|
| `PH.S.DRCMRF.*` | ductile_rcmrf_and_pt_rcmrf | 1 | 3 | 3 |
| `PH.S.NDRCMRF.*` | non_ductile_rcmrf | 1 | 3 | 3 |
| `PH.S.PTRCMRF.*` | ductile_rcmrf_and_pt_rcmrf | 1 | 3 | 3 |
| `PH.S.SMRF.*` | non_rbs_steel_mrf | 3 | 3 | 3 |
| `PH.S.SPLICE` | steel_column_splice | 3 | 3 | 3 |
| `PH.S.BASEPLT` | steel_column_base_plate | 3 | 3 | 3 |
| `PH.NS.CHB.SU`, `PH.NS.CHB.SR` | chb_wall_solid_unreinforced/reinforced | 1 | 1 | 3 |
| `PH.NS.CHB.PU`, `PH.NS.CHB.PR` | chb_with_doors_windows | 2 | 3 (LL) | 3 (LL) |
| `PH.NS.CW` | curtain_wall | 3 (LL) | 3 (LL) | 3 (LL) |
| `PH.NS.CLG.NS`, `PH.NS.CLG.BR` | suspended_ceiling_non_seismic_and_braced | 1 | 3 | 3 |
| `PH.NS.FIX.*` | ceiling_fixtures | 3 | — | — |
| `PH.NS.STAIRS` | cip_rc_stairs | 1 | 3 | 3 |
| `PH.NS.ELEC.DT` | desktop_electronics | 1 | — | — |
| `PH.NS.ELEC.WM` | wall_mounted_electronics | 1 | — | — |
| `PH.NS.ELEV` | elevator | 2 (LL) | — | — |
| `PH.NS.SPR.DROP`, `PH.NS.SPR.PIPE` | sprinkler_drop/pipe | 2 | 3 | — |
| `PH.NS.EDIST` | electrical_distribution_equipment | 2 | — | — |
| `PH.NS.DIESEL` | diesel_generator | 2 | — | — |

**Repair class → milestone gating (from YAML header):**
- Class 1 (structural/life-safety) → **Re-occupancy**
- Class 1 + 2 (structural + critical MEP/services) → **Functional Recovery** [PRIMARY METRIC]
- All classes (1 + 2 + 3) → **Full Recovery**

Note: "3 (LL)" entries carry the same class 3 assignment; the LL (long-lead) flag gates
the `long_lead_median_days` impeding factor, which is modeled in `ImpedingFactorParams`.

---

## 6. Implementation Approach (adopted in `recovery.py`)

Since Pelicun provides per-component `worker_hours` but no native recovery module:

1. **`building.py`** extracts `time_per_cmp` from `asmnt.loss.sample` and passes it to `recovery.compute_recovery_from_components()`.
2. **`recovery.py`** maps component IDs → repair class using the YAML-sourced `REPAIR_CLASS_MAP`, groups worker_hours by repair class, converts to calendar days (÷ `workers_per_day`), and sums per-class to get `rc1_days`, `rc2_days`, `rc3_days`.
3. **Milestones** gate on cumulative class completion:
   - `reoccupancy = rc1_days + impeding`
   - `functional = (rc1_days + rc2_days) + impeding`
   - `full = (rc1_days + rc2_days + rc3_days) + impeding`
4. **Impeding factors** (lognormal, PH-calibrated) remain our layer — Pelicun has none.

The fixed fractions 0.40/0.75/1.00 are removed. The milestone times now come from actual
component-level repair time sums per repair class.

---

## 7. Limitations and Flagged Gaps

- **`workers_per_day` assumption:** REDi uses per-floor labor allocation with crew-size parameters. Without that logic, we divide total worker_hours by a scalar `workers_per_day` (default: 8 hours/day × crew size). This is a simplification; it is clearly documented as a placeholder pending P6's full sequencing implementation.
- **Repair class for DS0:** Per YAML, DS0 is not damaged; Pelicun returns zero repair time for DS0 → no issue.
- **"3 (LL)" vs "3" distinction:** Both map to Class 3. The `(LL)` flag affects `long_lead_median_days` impeding factor, not repair class assignment.
- **No Pelicun repair schedule:** The full REDi 8-sequence labor schedule is not implemented. This is correctly our REDi layer responsibility; flagged for P6.

---

*Written by recovery_pelicun_integration agent, 2026-06-26.*
