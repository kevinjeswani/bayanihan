# archetype_modeler — Implement all 20 archetype factories and Building.from_archetype()

**Phase:** P3
**Status:** COMPLETE (as of 2026-06-26)
**Model tier:** Sonnet (architecture + implementation)
**Blocked on:** pelicun_dbformatter (P1) for fragility CSVs AND edp_normalizer (P2) for EDP files. P1 complete; P2 still blocked on data recovery.
**Unblocks:** thesis_replication_validator (P7)

---

## Purpose

Replace stub implementations in `bayanihan/archetypes.py` and `bayanihan/building.py` with fully working code. All 20 archetype factories must load their parameters from the data files produced in P1 — no hardcoded values. `Building.assess()` must call Pelicun's `DL_calculation` and return a structured dict of loss and repair-time outputs.

**20 archetypes:** 15 with independent structural models (full fragility) + 5 merged aliases that resolve to their parent archetype's fragility. All component IDs use the `PH.*` prefix. Canonical archetype IDs are defined in `bayanihan/archetypes.py::ARCHETYPE_IDS`.

---

## Inputs

- `docs/thesis/data/archetypes.yaml` — archetype IDs, structural descriptions, design eras (from thesis_extractor)
- `bayanihan/data/fragility.csv` — Pelicun custom fragility format (from pelicun_dbformatter)
- `bayanihan/data/consequence_repair.csv` — Pelicun consequence format (from pelicun_dbformatter)
- `bayanihan/data/replacement.csv` — replacement costs (from pelicun_dbformatter)
- `bayanihan/data/edps/{archetype_id}_edps.csv` — SimCenter-named EDP samples (from edp_normalizer)
- `docs/learnings/edp_format_notes.md` — EDP column mapping and quirks (from edp_normalizer)
- `docs/learnings/pelicun_csv_schema.md` — confirmed Pelicun column schema (from pelicun_dbformatter)

---

## Outputs

- `bayanihan/archetypes.py` — 9 fully-implemented archetype factories
- `bayanihan/building.py` — `from_archetype()` and `assess()` fully implemented
- `test/test_archetypes.py` — parametrized tests over all 20 archetypes
- `test/test_building.py` — single-building assessment round-trip test
- `test/conftest.py` — `dummy_edp_samples` fixture (if not already present)

---

## Execution strategy

### Step 1 — Read existing code

Read the current state of `bayanihan/archetypes.py` and `bayanihan/building.py`. Identify what is stubbed vs what is partially implemented. Do not overwrite working code.

Read `docs/learnings/edp_format_notes.md` and `docs/learnings/pelicun_csv_schema.md` before writing any implementation.

### Step 2 — Read Pelicun's DL_calculation API

Find `DL_calculation` in the installed Pelicun package source. Understand:
- What arguments it accepts (particularly how to pass a custom component library path)
- What it returns
- How to configure it for a custom `CustomDLDataFolder`
- What EDP column format it expects (confirm against `edp_format_notes.md`)

Write a minimal Pelicun call in a scratch pad before implementing `assess()`. Confirm the call structure is correct.

### Step 3 — Implement archetype data loading

In `bayanihan/archetypes.py`:
- Load `bayanihan/data/fragility.csv` via `importlib.resources.files("bayanihan.data")` — never use a hardcoded filesystem path
- Define a `ArchetypeConfig` pydantic model (or dataclass) that holds the parameters for one archetype
- Implement a `get_archetype_config(archetype_id: str) -> ArchetypeConfig` function that reads from the CSV and returns the config for the given ID
- Raise `ValueError` with a clear message if the archetype ID is not found

### Step 4 — Implement the 20 factories

For each of the 20 archetype IDs:
- Implement a factory function `make_{sanitized_id}() -> ArchetypeConfig`
- Each factory calls `get_archetype_config("{archetype_id}")` — no hardcoded values in the factory body
- 5 merged archetypes resolve to their parent's fragility key (documented in `archetypes.yaml`)
- Register all 20 factories in a dict `ARCHETYPE_REGISTRY: dict[str, Callable[[], ArchetypeConfig]]`

The factory pattern must be extensible — adding a new archetype requires only adding one function and one registry entry.

### Step 5 — Implement Building.from_archetype()

In `bayanihan/building.py`:
- `Building.from_archetype(archetype_id: str, **overrides) -> Building` loads the archetype config and returns a configured `Building` instance
- The `Building` instance holds: archetype_id, archetype_config, and the path to the corresponding EDP file
- Raise `ValueError` if the archetype ID is not in `ARCHETYPE_REGISTRY`

### Step 6 — Implement Building.assess()

`Building.assess(edp_samples: pd.DataFrame) -> dict` must:
1. Validate that `edp_samples` columns match SimCenter naming convention
2. Call Pelicun's `DL_calculation` with:
   - The EDP samples
   - The custom component library path pointing to `bayanihan/data/`
   - The archetype's replacement cost from `replacement.csv`
3. Return a dict with at minimum these keys:
   - `"loss_ratio"` — array of loss ratios (loss / replacement cost), shape (n_samples,)
   - `"repair_time_days"` — array of repair time in days, shape (n_samples,)
   - `"damage_state_counts"` — dict mapping damage state to count
   - `"archetype_id"` — string

### Step 7 — Vulnerability surface caching

After a successful `assess()` call, cache the resulting vulnerability surface (loss ratio vs IM, if IM is passed) as parquet in `vulnerability_surfaces/{archetype_id}.parquet`. This directory is gitignored.

If the parquet file exists and the EDP samples have not changed (check file mtime), load from cache instead of re-running Pelicun. The cache check is optional if it complicates the implementation — mark it as a TODO if skipping.

### Step 8 — Write conftest.py fixture

In `test/conftest.py`, add or update a `dummy_edp_samples` pytest fixture that returns a `pd.DataFrame` with:
- SimCenter-convention column names matching the most common story count (read from `edp_format_notes.md`)
- 50 rows of synthetic but physically plausible EDP values (IDR in range 0.0001–0.05, PFA in range 0.05–3.0 g)
- Fixture is parametrized over all 20 archetype IDs

### Step 9 — Write tests

Write `test/test_archetypes.py`:
- Parametrized over all 20 archetype IDs
- Test that `get_archetype_config(archetype_id)` returns a non-None config
- Test that the config has required fields (fragility median, dispersion, etc.)
- Test that `Building.from_archetype(archetype_id)` returns a `Building` instance without error

Write `test/test_building.py`:
- Test that `Building.from_archetype("C1-M (Hi)").assess(dummy_edp_samples)` returns a dict with all required keys
- Test that `loss_ratio` values are in [0, 1] (physically required)
- Test that `repair_time_days` values are non-negative
- Test that all 20 archetypes produce non-NaN outputs

### Step 10 — Run tests

Run `pytest test/test_archetypes.py test/test_building.py -v`. Fix any failures. Do not modify tests to make them pass — fix the implementation.

### Step 11 — Decision log

Append the reporting block to `docs/orchestration/decision_log.md`.

---

## Success criteria

1. `Building.from_archetype("C1-M (Hi)").assess(dummy_edp_samples)` executes without error and returns a dict.
2. Returned dict has all required keys: `loss_ratio`, `repair_time_days`, `damage_state_counts`, `archetype_id`.
3. `loss_ratio` values are all in [0.0, 1.0].
4. `repair_time_days` values are all >= 0.
5. All 20 archetypes produce non-NaN outputs using `dummy_edp_samples` from conftest.py.
6. `pytest test/test_archetypes.py test/test_building.py -v` passes with zero failures.
7. No hardcoded numerical values in `archetypes.py` or `building.py` — all parameters load from CSV files.
8. `importlib.resources` is used for data file access (no hardcoded filesystem paths).
9. `docs/orchestration/decision_log.md` has been appended with this agent's report block.

---

## Prohibitions

- Never hardcode a fragility median, dispersion, or consequence value. All parameters come from CSV files loaded via `importlib.resources`.
- Never use `os.path` or `pathlib.Path(__file__).parent` to locate data files — use `importlib.resources`.
- Never modify a test to make it pass — fix the implementation.
- Never call `DL_calculation` without first confirming the API from the installed Pelicun source.

---

## Reporting template

Append this block to `docs/orchestration/decision_log.md` on completion:

```
Track: 3
Phase: archetype_modeler
Result: Implemented 20 archetype factories (15 independent + 5 merged aliases) and Building.assess() with Pelicun DL_calculation integration.
Key metric: {N_tests} tests passing across test_archetypes.py and test_building.py.
Files created: bayanihan/archetypes.py, bayanihan/building.py, test/test_archetypes.py, test/test_building.py, test/conftest.py
Docs updated: docs/orchestration/decision_log.md
Next step: thesis_replication_validator (P7) is unblocked once recovery_modeler (P6) also completes.
```
