# edp_normalizer — Convert PERFORM-3D EDP CSVs to SimCenter naming convention

**Phase:** P2
**Model tier:** Haiku (mechanical data transformation)
**Blocked on:** EDP data availability — this agent runs once the raw PERFORM-3D EDP CSVs are available under `bayanihan/data/edps/raw/`.
**Unblocks:** archetype_modeler (P3)

---

## Purpose

Take the raw PERFORM-3D EDP output CSVs and rename columns to the SimCenter naming convention expected by Pelicun's EDP parser. This is a mechanical transformation — the schema target is fully specified below. Document any format quirks encountered for the benefit of archetype_modeler.

---

## Inputs

- `bayanihan/data/edps/raw/*.csv` — raw PERFORM-3D EDP outputs, one file per archetype, placed here by Kevin after data recovery
- `docs/thesis/data/archetypes.yaml` — to confirm the list of 20 archetype IDs and their story counts (15 with independent structural models + 5 merged aliases)

Before starting, verify that `bayanihan/data/edps/raw/` is non-empty. If it is empty, stop immediately and write `"EDP raw files not yet recovered"` to `docs/orchestration/decision_log.md`. Do not attempt to synthesize or fabricate EDP data.

---

## Outputs

- `bayanihan/data/edps/{archetype_id}_edps.csv` — one file per archetype, SimCenter column naming
- `docs/learnings/edp_format_notes.md` — format quirks, column mapping decisions, any ambiguities resolved

---

## SimCenter EDP naming convention

Column names follow the pattern: `{story}-{EDP_type}-{direction}-{component}`

Examples:
- `1-PID-1-1` — story 1, peak interstory drift, direction 1, component 1
- `2-PID-2-1` — story 2, peak interstory drift, direction 2, component 1
- `1-PFA-0-1` — story 1 (ground), peak floor acceleration, direction 0, component 1

EDP type codes:
- `PID` — peak interstory drift ratio (dimensionless)
- `PFA` — peak floor acceleration (in g)
- `PFV` — peak floor velocity (in in/s or m/s — check Pelicun's expected unit)
- `RID` — residual interstory drift ratio (if present)

Confirm the exact EDP types present in the PERFORM-3D outputs before writing any output CSVs.

---

## Execution strategy

### Step 1 — Read existing learnings

Read `docs/learnings/` for any notes about EDP format. Check for `edp_format_notes.md` in particular. If it exists, read it before examining any raw files.

### Step 2 — Inspect raw files

Read the first raw CSV file. Record:
- Column names exactly as they appear
- Number of rows (= number of ground motion records / EDP samples)
- Number of stories implied by the columns
- Units (if indicated in the file header or column names)
- Any non-numeric columns (e.g., ground motion ID, run ID)

Read two or three additional raw files to check for inconsistencies between archetypes.

### Step 3 — Build column mapping

Construct the mapping from PERFORM-3D column names to SimCenter names. Write this mapping explicitly as a Python dict in your working notes before applying it to any file. The mapping must account for:
- All story levels present
- All EDP types present
- Both horizontal directions (if available)

### Step 4 — Transform each archetype

For each of the archetypes with independent PERFORM-3D models (15 primary; 5 merged archetypes use their parent's EDP file — check archetypes.yaml for `merged_parent` field):
1. Identify the corresponding raw file (match by archetype ID or filename pattern)
2. Apply the column mapping
3. Drop any non-EDP columns (run IDs, metadata) — but log what was dropped
4. Write to `bayanihan/data/edps/{archetype_id}_edps.csv`
5. Confirm the output file has the correct number of rows (must equal the raw file row count)

### Step 5 — Validate against Pelicun

Run a minimal validation: load one output CSV and pass it to Pelicun's EDP parser (or the relevant parsing function). Confirm no column-name errors are raised. If errors occur, fix the column mapping and re-run all primary archetype files.

Specifically, the following must not raise an error:
```python
from bayanihan.building import Building
b = Building.from_archetype("C1-M_pre92")  # or whichever archetype exists
# (Building.from_archetype may not be fully implemented yet; if not, just validate
# that the CSV loads and columns are recognized by Pelicun's EDP parser directly)
```

If `Building.from_archetype` is not yet implemented (P3 not complete), run the Pelicun EDP parser directly instead. Document what you tested.

### Step 6 — Write learnings

Write `docs/learnings/edp_format_notes.md` with:
- The PERFORM-3D to SimCenter column mapping (full dict)
- Story counts per archetype
- Units used
- Any quirks encountered (e.g., missing directions, irregular story numbering, NaN rows)
- Whether the raw files were one-per-archetype or required splitting

### Step 7 — Decision log

Append the reporting block to `docs/orchestration/decision_log.md`.

---

## Success criteria

1. Files exist at `bayanihan/data/edps/{archetype_id}_edps.csv` for each of the 15 primary archetypes (merged archetypes reference their parent's EDP file — check archetypes.yaml).
2. All output CSVs have SimCenter-convention column names (pattern: `{story}-{EDP_type}-{direction}-{component}`).
3. Row counts in output CSVs match row counts in corresponding raw files (no samples dropped).
4. Pelicun's EDP parser loads at least one output CSV without column-name errors (confirmed by validation run in Step 5).
5. `docs/learnings/edp_format_notes.md` exists with the full column mapping documented.
6. `docs/orchestration/decision_log.md` has been appended with this agent's report block.

---

## Prohibitions

- Never fabricate or synthesize EDP samples. If raw files are absent, stop.
- Never rename a column without documenting the mapping in `edp_format_notes.md`.
- Never drop EDP rows — only drop non-EDP metadata columns, and log what was dropped.
- Never silently pass on a Pelicun column-name error — fix the mapping until the parser accepts the output.

---

## Reporting template

Append this block to `docs/orchestration/decision_log.md` on completion:

```
Track: 2
Phase: edp_normalizer
Result: Normalized {N} raw PERFORM-3D EDP files to SimCenter convention for primary archetypes.
Key metric: {N_samples} EDP samples per archetype (rows per output CSV).
Files created: bayanihan/data/edps/[primary archetype files], docs/learnings/edp_format_notes.md
Docs updated: docs/orchestration/decision_log.md
Next step: archetype_modeler (P3) now has both fragility CSVs (P1) and EDP files (P2) — fully unblocked.
```
