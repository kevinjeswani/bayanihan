# pelicun_dbformatter — Transform thesis YAML into Pelicun-format component database CSVs

**Phase:** P1
**Model tier:** Sonnet (structured data transformation, Pelicun API knowledge)
**Blocked on:** thesis_extractor (P0) — all 7 YAML files must exist before starting.
**Unblocks:** archetype_modeler (P3)

---

## Purpose

Read the structured YAML files produced by thesis_extractor and write them into the CSV format expected by Pelicun's `CustomDLDataFolder` component library loader. Every row in every output CSV traces directly to a YAML entry — no value is hardcoded. This agent also writes the unit tests that verify the CSVs load correctly.

---

## Inputs

- `docs/thesis/data/fragility_parameters.yaml`
- `docs/thesis/data/consequence_parameters.yaml`
- `docs/thesis/data/replacement_costs.yaml`
- Pelicun installed package source or GitHub documentation for `CustomDLDataFolder` format

---

## Outputs

- `bayanihan/data/fragility.csv` — Pelicun custom fragility format
- `bayanihan/data/consequence_repair.csv` — Pelicun consequence format
- `bayanihan/data/replacement.csv` — replacement cost per archetype
- `test/test_component_db.py` — unit tests for all 3 CSVs

---

## Execution strategy

### Step 1 — Research Pelicun's CustomDLDataFolder format

Before writing any CSV, read Pelicun's documentation or installed source to determine the exact column names, required fields, and data types for:
- `CustomDLDataFolder` fragility input format
- `CustomDLDataFolder` consequence input format

Do this by:
1. Running `python -c "import pelicun; print(pelicun.__file__)"` to find the installed package location.
2. Reading the source files under the Pelicun package directory, particularly any file mentioning `CustomDLDataFolder`, `DL_calculation`, or component library loading.
3. If Pelicun has example CSVs bundled, read one to understand the exact schema.
4. Write a short schema note to `docs/learnings/pelicun_csv_schema.md` documenting the column names you confirmed. This is required — do not skip it.

Never guess column names. If the Pelicun source is unclear, run a minimal test in Python to probe what the loader expects.

### Step 2 — Read and validate YAML inputs

Load all three YAML input files. Before transforming, verify:
- `fragility_parameters.yaml` has entries for all 20 archetype IDs (read from `docs/thesis/data/archetypes.yaml`; note 5 merged archetypes reference their parent's fragility)
- Every entry has `value`, `source.section`, `source.page`, and `provenance_confidence`
- No `value: null` entries exist

If validation fails, write the specific failures to `docs/learnings/pelicun_dbformatter_yaml_errors.md` and stop. Do not produce partial CSVs — Kevin must fix the upstream YAML first.

### Step 3 — Write `bayanihan/data/fragility.csv`

Transform `fragility_parameters.yaml` into Pelicun fragility format. Rules:
- One row per component/damage-state combination
- Include a `provenance` column containing the thesis table reference (e.g., `"Table A.2, p.187"`)
- Distribution type follows Pelicun convention (typically `"lognormal"` for fragility curves)
- Use Pelicun's exact column names as confirmed in Step 1 — never approximate

### Step 4 — Write `bayanihan/data/consequence_repair.csv`

Transform `consequence_parameters.yaml` into Pelicun consequence format. Rules:
- One row per component/damage-state/consequence-type combination
- Include a `provenance` column
- Repair cost units must match what Pelicun expects (typically normalized ratios or dollar values — confirm from Pelicun source)

### Step 5 — Write `bayanihan/data/replacement.csv`

Transform `replacement_costs.yaml`. Structure:
- One row per archetype ID
- Columns: `archetype_id`, `replacement_cost`, `unit`, `provenance`

### Step 6 — Write unit tests

Write `test/test_component_db.py` with tests that:
1. Load `fragility.csv` using Pelicun's component library loader (not just pandas — use the actual Pelicun API)
2. Assert that all 20 archetype IDs appear in the loaded library (merged archetypes may share a fragility key with their parent)
3. Assert no NaN values in median or dispersion columns
4. Load `consequence_repair.csv` and assert it passes Pelicun's validation
5. Load `replacement.csv` and assert all 20 archetypes are present with positive replacement costs

### Step 7 — Run tests

Run `pytest test/test_component_db.py -v` and confirm all tests pass. If any test fails, fix the CSV (not the test) until the test passes.

### Step 8 — Decision log

Append the reporting block to `docs/orchestration/decision_log.md`.

---

## Provenance column format

Every CSV row must carry a provenance reference. Use a `provenance` column with values like:

```
Table A.2, p.187, Section A.1.3
```

This is not optional. A CSV row without a provenance column entry is a bug.

---

## Success criteria

1. `bayanihan/data/fragility.csv` exists and is non-empty.
2. `bayanihan/data/consequence_repair.csv` exists and is non-empty.
3. `bayanihan/data/replacement.csv` exists and is non-empty.
4. `pytest test/test_component_db.py -v` passes with zero failures.
5. Pelicun's component library loader loads `fragility.csv` without errors (confirmed by the test in Step 6).
6. Every row in all CSVs has a non-empty `provenance` column entry.
7. `docs/learnings/pelicun_csv_schema.md` exists documenting the confirmed column schema.
8. `docs/orchestration/decision_log.md` has been appended with this agent's report block.

---

## Prohibitions

- Never hardcode a numerical value. Every number comes from a YAML file read at runtime in the transformation script or at test time.
- Never produce partial CSVs. If any step fails, write the failure to `docs/learnings/` and stop.
- Never approximate Pelicun column names. Confirm the exact schema from the installed package before writing a single CSV row.
- Never write a CSV row without a `provenance` column entry.

---

## Reporting template

Append this block to `docs/orchestration/decision_log.md` on completion:

```
Track: 1
Phase: pelicun_dbformatter
Result: Produced 3 Pelicun-format CSVs from thesis YAML, all passing component library validation.
Key metric: {N_rows} total rows across fragility.csv and consequence_repair.csv.
Files created: bayanihan/data/fragility.csv, bayanihan/data/consequence_repair.csv, bayanihan/data/replacement.csv, test/test_component_db.py
Docs updated: docs/learnings/pelicun_csv_schema.md, docs/orchestration/decision_log.md
Next step: archetype_modeler (P3) is unblocked for the fragility side. edp_normalizer (P2) must also complete before P3 can finish.
```
