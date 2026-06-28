# Pelicun Custom Component Library CSV Schema

**Confirmed against:** Pelicun 3.x (installed at `.venv/lib/python3.13/site-packages/pelicun`)
**Reference files inspected:**
- `resources/DamageAndLossModelLibrary/seismic/building/component/FEMA P-58 2nd Edition/fragility.csv`
- `resources/DamageAndLossModelLibrary/seismic/building/component/FEMA P-58 2nd Edition/consequence_repair.csv`
- `examples/0_tmp/fragility_Additional.csv`
- `examples/0_tmp/repair_Additional.csv`
- `tests/validation/v2/data/additional_damage_db.csv`
- `tests/validation/v2/data/additional_consequences.csv`

---

## Key findings

1. **Single-row header**: Pelicun loads CSVs with `pd.read_csv(filepath, header=0, index_col=0)` — a **single row of column names**, no MultiIndex. The bundled P-58 CSVs look like they have a 2-row structure when read with `header=[0,1]`, but internally Pelicun always uses `header=0`.

2. **No comment lines**: Pelicun's `file_io.load_from_file` does not pass `comment='#'` to `pd.read_csv`. Do NOT put `#`-prefixed comment lines in the CSV files — they will cause a `ParserError: Expected 1 fields`. Provenance must be carried in trailing data columns (`thesis_source`, `provenance_confidence`).

---

## 1. fragility.csv — Damage Model

### Loading mechanism

```python
assessment.damage.load_model_parameters(
    data_paths=["path/to/fragility.csv", "PelicunDefault/..."],
    cmp_set=set(...)
)
```

The `data_paths` list is ordered: custom definitions take precedence over later entries.

### Column schema

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| `ID` | str (index) | Component ID, thesis-native format | `IND-B.D.RCMRF.1S` |
| `Incomplete` | int | 0 = complete, 1 = placeholder only | `0` |
| `Demand-Type` | str | EDP type | `Peak Interstory Drift Ratio` |
| `Demand-Unit` | str | EDP unit | `unitless` (for PIDR), `g` (for PFA) |
| `Demand-Offset` | int | Floor offset for EDP (0 = same floor) | `0` |
| `Demand-Directional` | int | 1 = directional, 0 = non-directional | `1` |
| `LS1-Family` | str | Distribution family for LS1 | `lognormal` |
| `LS1-Theta_0` | float | Median (θ) for LS1 | `0.02` |
| `LS1-Theta_1` | float | Dispersion (β) for LS1 | `0.4` |
| `LS1-DamageStateWeights` | str | Weights for mutually exclusive DS within LS | `0.950000 \| 0.050000` |
| `LS2-Family` | str | As above for LS2 | `lognormal` |
| … | … | Repeat for LS3, LS4 as needed | … |

### Notes on EDP types (exact Pelicun strings)

| Thesis EDP | Pelicun `Demand-Type` | `Demand-Unit` |
|-----------|----------------------|--------------|
| PIDR [%] | `Peak Interstory Drift Ratio` | `unitless` |
| PFA [g] | `Peak Floor Acceleration` | `g` |
| PGA [g] | `Peak Floor Acceleration` | `g` (with `Demand-Offset` and floor assignment) |

**PIDR unit:** The thesis uses PIDR in `%` (e.g., θ=2.0 means 2%). Pelicun uses PIDR as a `unitless` ratio (e.g., 0.02 means 2%). **Division by 100 is applied during CSV generation.**

### Damage state weights (mutually exclusive DS)

When a limit state has mutually exclusive damage states (e.g., DS3 and DS4), the `DamageStateWeights` column carries the pipe-separated probabilities: `0.80 | 0.20`. Leave blank for single DS per LS.

### Simultaneous damage states (elevator)

Pelicun does not natively represent simultaneous damage states with conditional probabilities. The elevator component (simultaneous DS1–DS4 with P={0.26, 0.79, 0.68, 0.17}) cannot be exactly replicated in this schema. **Gap documented below.**

---

## 2. consequence_repair.csv — Loss Model (Cost + Time)

### Loading mechanism

```python
assessment.loss.bldg_repair.load_model_parameters(
    data_paths=["path/to/consequence_repair.csv", "PelicunDefault/..."],
    decision_variables=["Cost", "Time"]
)
```

### Column schema

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| `ID` | str (index) | Component ID + `-Cost` or `-Time` suffix | `IND-B.D.RCMRF.1S-Cost` |
| `Incomplete` | int | 0 = complete | `0` |
| `Quantity-Unit` | str | Component quantity unit | `1 EA`, `125 SF` |
| `DV-Unit` | str | Decision variable unit | `PHP_2020` (cost), `worker_hour` (time) |
| `DS1-Family` | str | Distribution family for DS1 consequence | `lognormal` or `normal` |
| `DS1-Theta_0` | str/float | Median value or `Cmax,Cmin\|Qmin,Qmax` for economy of scale | `44900` or `53880,35920\|5,20` |
| `DS1-Theta_1` | float | Dispersion (β or CV) | `0.50` |
| `DS1-LongLeadTime` | int | 1 = long lead time procurement needed | `0` or `1` |
| `DS2-Family` | str | As above for DS2 | … |
| … | … | Repeat for DS3, DS4 as needed | … |

### Economy-of-scale encoding in Theta_0

The format `Cmax,Cmin|Qmin,Qmax` encodes linear interpolation:
- At `Qmin` units: consequence = `Cmax` (cost is higher per unit for small quantities)
- At `Qmax` units: consequence = `Cmin` (cost is lower per unit for large quantities)
- Between: linear interpolation

Example: `53880,35920|5,20` means PHP 53,880 (at Q=5) to PHP 35,920 (at Q=20).

Formula: `Cmax = theta * C_T_max_factor`, `Cmin = theta * C_T_min_factor`

### Currency/unit decision

**Currency: PHP (Philippine Peso), reference year 2020.**
- YAML values in `000 PHP` → multiply by 1000 → values in PHP for the CSV
- `DV-Unit` column uses `PHP_2020` (custom unit label; Pelicun won't do currency conversion)
- Exchange rate in thesis: USD 1.0 = PHP 50.8 (May 2020). Not applied — PHP is more faithful.
- Time unit: `worker_hour` (thesis calls these man-hours/MH)

---

## 3. replacement.csv — Replacement Cost + Time

Same schema as consequence_repair.csv. Two rows per archetype (or global):
- `replacement-Cost`: Quantity-Unit=`1 EA`, DV-Unit=`PHP_2020`
- `replacement-Time`: Quantity-Unit=`1 EA`, DV-Unit=`worker_hour`

Theta_0 for the replacement CSV has no DS prefix — just a single `DS1-Theta_0` representing the replacement value (no damage state distinction).

---

## 4. Component ID convention

Thesis components are mapped to IDs following a `PH.{category}.{name}` convention:

| Thesis key | Pelicun ID |
|-----------|------------|
| `ductile_rcmrf_1side` | `PH.S.DRCMRF.1S` |
| `ductile_rcmrf_2sides` | `PH.S.DRCMRF.2S` |
| `non_ductile_rcmrf_1side` | `PH.S.NDRCMRF.1S` |
| `non_ductile_rcmrf_2sides` | `PH.S.NDRCMRF.2S` |
| `pt_rcmrf_1side` | `PH.S.PTRCMRF.1S` |
| `pt_rcmrf_2sides` | `PH.S.PTRCMRF.2S` |
| `non_rbs_steel_mrf_1side` | `PH.S.SMRF.1S` |
| `non_rbs_steel_mrf_2sides` | `PH.S.SMRF.2S` |
| `steel_column_splice` | `PH.S.SPLICE` |
| `steel_column_base_plate` | `PH.S.BASEPLT` |
| `chb_wall_solid_unreinforced` | `PH.NS.CHB.SU` |
| `chb_wall_solid_reinforced` | `PH.NS.CHB.SR` |
| `chb_wall_perforated_unreinforced` | `PH.NS.CHB.PU` |
| `chb_wall_perforated_reinforced` | `PH.NS.CHB.PR` |
| `curtain_wall` | `PH.NS.CW` |
| `suspended_ceiling_non_seismic` | `PH.NS.CLG.NS` |
| `suspended_ceiling_braced` | `PH.NS.CLG.BR` |
| `ceiling_fixtures_non_seismic` | `PH.NS.FIX.NS` |
| `ceiling_fixtures_seismic` | `PH.NS.FIX.SE` |
| `cip_rc_stairs` | `PH.NS.STAIRS` |
| `desktop_electronics` | `PH.NS.ELEC.DT` |
| `wall_mounted_electronics` | `PH.NS.ELEC.WM` |
| `elevator` | `PH.NS.ELEV` |
| `sprinkler_drop` | `PH.NS.SPR.DROP` |
| `sprinkler_horizontal_piping` | `PH.NS.SPR.PIPE` |
| `electrical_distribution_equipment` | `PH.NS.EDIST` |
| `diesel_generator` | `PH.NS.DIESEL` |

---

## 5. Known gaps between thesis schema and Pelicun format

### Gap 1: Simultaneous damage states (elevator)
The elevator component uses simultaneous DS with conditional probabilities {DS1=0.26, DS2=0.79, DS3=0.68, DS4=0.17}. Pelicun's damage model supports sequential (Seq) or mutually exclusive (MutEx) DS, not simultaneous. **Workaround:** Elevator is treated as a sequential LS model with DS4 (most severe) for structural purposes. Consequence functions for each DS are mapped to the four simultaneous states as separate DS entries.

### Gap 2: DS1 zero-cost components (steel splice, base plate)
`steel_column_splice` and `steel_column_base_plate` have DS1 that "does not warrant repair" (zero cost). Pelicun handles this by leaving DS1-Theta_0 blank/NaN, which it interprets as zero or not applicable. **Implementation:** DS1-Family and DS1-Theta_0 left empty; DS2 and higher carry the consequence values.

### Gap 3: PIDR unit conversion
Thesis values are in `%` (e.g., θ=2.0%). Pelicun expects unitless ratio (0.02). All PIDR medians are divided by 100.

### Gap 4: PFA for ceiling/fixtures uses floor-above EDP
Pelicun handles this via `Demand-Offset` column (set to 1 for "floor above"). For suspended ceilings and fixtures: `Demand-Offset=1`.

### Gap 5: Repair-class metadata
REDi repair class assignments (from `redi_impedance_factors.yaml`) are not stored in the fragility/consequence CSVs. They belong in a separate mapping used by `recovery.py` (P6). Provenance reference: Table D-16, printed page 313.

### Gap 6: Elevator simultaneous-state consequence mapping
The consequence YAML lists 4 DS with different costs for the elevator simultaneous-state model. These map to DS1–DS4 in the consequence CSV as approximation.

---

## 6. Example rows

### fragility.csv (structural, 3-DS component)
```
ID,Incomplete,Demand-Type,Demand-Unit,Demand-Offset,Demand-Directional,LS1-Family,LS1-Theta_0,LS1-Theta_1,LS1-DamageStateWeights,LS2-Family,LS2-Theta_0,LS2-Theta_1,LS2-DamageStateWeights,LS3-Family,LS3-Theta_0,LS3-Theta_1,LS3-DamageStateWeights,LS4-Family,LS4-Theta_0,LS4-Theta_1,LS4-DamageStateWeights
PH.S.NDRCMRF.1S,0,Peak Interstory Drift Ratio,unitless,0,1,lognormal,0.015,0.4,,lognormal,0.02,0.4,,lognormal,0.025,0.4,,,,,
```

### consequence_repair.csv (cost and time rows)
```
ID,Incomplete,Quantity-Unit,DV-Unit,DS1-Family,DS1-Theta_0,DS1-Theta_1,DS1-LongLeadTime,DS2-Family,DS2-Theta_0,DS2-Theta_1,DS2-LongLeadTime,DS3-Family,DS3-Theta_0,DS3-Theta_1,DS3-LongLeadTime
PH.S.NDRCMRF.1S-Cost,0,1 EA,PHP_2020,lognormal,"21360,15702|5,20",0.50,0,normal,"38520,28908|5,20",0.48,0,normal,"66840,50130|5,20",0.49,0
PH.S.NDRCMRF.1S-Time,0,1 EA,worker_hour,lognormal,"10010,7315|5,20",0.51,0,normal,"23400,17100|5,20",0.53,0,normal,"36660,26730|5,20",0.48,0
```
