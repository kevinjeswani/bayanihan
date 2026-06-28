# thesis_extractor — Extract thesis PDF into chapter markdown and structured YAML

**Phase:** P0
**Model tier:** Sonnet (research synthesis, vision, structured output)
**Blocked on:** Nothing — this is the first phase.
**Unblocks:** pelicun_dbformatter (P1), recovery_modeler (P6)

---

## Purpose

Read the 374-page thesis PDF and produce two output types: (1) narrative markdown per chapter for human reference, and (2) structured YAML files with provenance flags for every parameter that downstream code will consume. This agent is the single source of truth for all numerical values in the package — nothing is hardcoded without tracing to a YAML value produced here.

---

## Inputs

- `docs/thesis/Jeswani_Kevin_Kamlesh_202103_MAS_thesis.pdf` — 374-page thesis PDF

---

## Outputs

### Narrative markdown

- `docs/thesis/00_abstract.md`
- `docs/thesis/01_introduction.md`
- `docs/thesis/02_literature_review.md`
- `docs/thesis/03_methodology.md`
- `docs/thesis/04_component_library.md`
- `docs/thesis/05_case_study.md`
- `docs/thesis/06_results.md`
- `docs/thesis/07_portfolio_assessment.md`
- `docs/thesis/08_conclusions.md`
- `docs/thesis/appendices/appendix_a.md` (and additional appendix files as needed)

### Structured YAML (high-value, consumed by downstream agents)

- `docs/thesis/data/archetypes.yaml` — archetype IDs, structural descriptions, design eras
- `docs/thesis/data/fragility_parameters.yaml` — median and dispersion per damage state per component
- `docs/thesis/data/consequence_parameters.yaml` — repair cost and time distributions per damage state
- `docs/thesis/data/edp_distributions.yaml` — EDP statistics from PERFORM-3D runs
- `docs/thesis/data/gmpe_weights.yaml` — GMPE names and logic-tree weights
- `docs/thesis/data/ph_redi_params.yaml` — Philippine-calibrated REDi impeding factor distributions
- `docs/thesis/data/replacement_costs.yaml` — total replacement cost per archetype

---

## Provenance structure

Every scalar value in every YAML file must use this structure. Never write a bare number.

```yaml
value: 0.3
unit: "g"
source:
  section: "3.4.2"
  table: "Table 3.2"
  page: 47
provenance_confidence: high  # high / medium / low
notes: "Optional clarification if the value required interpretation"
```

Use `provenance_confidence: low` for values read from figures (not tables), values that required interpolation, or values where the thesis text was ambiguous. Collect all low-confidence values in a list at the end of the run for Kevin review.

---

## Execution strategy

### Step 1 — Orient (do this before reading any pages)

Read the table of contents (typically pages 4–10). Record the exact page ranges for each chapter and each appendix. These ranges drive all subsequent batching.

### Step 2 — Spawn Haiku sub-agents for chapter narrative

For each chapter (01 through 08), spawn a Haiku sub-agent with:
- The specific page range
- The target output file path
- Instruction to write substantive prose markdown — not bullet lists, not "TODO" stubs
- Instruction to flag any tables or figures that look like they contain numerical parameters (mark them `[DATA TABLE: p.XX]` inline for the Sonnet pass)

Run all chapter sub-agents concurrently.

### Step 3 — Appendix extraction (Sonnet, sequential)

The appendices contain the component library, fragility parameters, and consequence functions. This is the highest-value content in the thesis. Do not delegate to Haiku.

For each appendix:
1. Read the page range with vision enabled
2. For every table: extract all values, assign provenance fields (section, table label, page number)
3. Write to the appropriate YAML file under `docs/thesis/data/`
4. If a table spans multiple pages, read all pages before writing any YAML

Process appendices in this priority order:
1. Component fragility tables (highest downstream impact)
2. Consequence function tables
3. Archetype descriptions and design parameters
4. GMPE logic-tree weights
5. Philippine REDi impeding factor calibrations
6. Replacement costs

### Step 4 — Cross-check archetype IDs

After extracting `archetypes.yaml`, verify the list contains exactly 20 archetype IDs (15 with independent structural models + 5 merged aliases that resolve to their parent's fragility). Confirm against the thesis — the canonical ID list is now in `bayanihan/archetypes.py::ARCHETYPE_IDS`. If the thesis uses different ID strings, document the mapping but use the canonical IDs in the YAML.

### Step 5 — Reconcile chapter data flags

Return to any chapter markdown where you flagged `[DATA TABLE: p.XX]`. Verify that the corresponding value appears in a YAML file. If it does not, extract it now.

### Step 6 — Low-confidence audit

Collect every YAML entry with `provenance_confidence: low`. Write them as a numbered list to `docs/learnings/thesis_extractor_low_confidence.md`. Each entry must include: the YAML file, the key path, the value, and the reason for low confidence.

### Step 7 — Decision log

Append the reporting block to `docs/orchestration/decision_log.md`.

---

## Success criteria

1. All 9 chapter markdown files exist at the paths listed above with substantive content (minimum 200 words each, no "TODO" stubs).
2. All appendix markdown files exist with content.
3. All 7 YAML files exist.
4. `docs/thesis/data/archetypes.yaml` contains exactly 20 archetype entries, each with `id`, `structural_system`, `height_class`, and `design_era` fields. 5 entries carry a `merged_parent` field referencing their parent archetype.
5. `docs/thesis/data/fragility_parameters.yaml` contains entries for all archetype/component/damage-state combinations found in the thesis — never fewer than what the thesis tables show.
6. Every YAML scalar value has `source.section`, `source.page`, and `provenance_confidence` populated.
7. `docs/learnings/thesis_extractor_low_confidence.md` exists (even if empty).
8. `docs/orchestration/decision_log.md` has been appended with this agent's report block.

---

## Prohibitions

- Never write a bare number to a YAML file without provenance fields.
- Never stub a YAML entry with `value: null` and move on — if a value is genuinely absent from the thesis, document why in `notes`.
- Never invent or interpolate a parameter value. If the thesis does not contain it, mark `provenance_confidence: low` and explain in `notes`.
- Never use generic section labels like "Chapter 3" — always use the specific section number (e.g., "3.4.2").

---

## Reporting template

Append this block to `docs/orchestration/decision_log.md` on completion:

```
Track: 0
Phase: thesis_extractor
Result: Extracted {N} YAML parameter entries across 7 files from 374-page thesis PDF.
Key metric: {N_low_confidence} low-confidence extractions flagged for Kevin review.
Files created: docs/thesis/00_abstract.md, docs/thesis/01_introduction.md, docs/thesis/02_literature_review.md, docs/thesis/03_methodology.md, docs/thesis/04_component_library.md, docs/thesis/05_case_study.md, docs/thesis/06_results.md, docs/thesis/07_portfolio_assessment.md, docs/thesis/08_conclusions.md, docs/thesis/appendices/*.md, docs/thesis/data/archetypes.yaml, docs/thesis/data/fragility_parameters.yaml, docs/thesis/data/consequence_parameters.yaml, docs/thesis/data/edp_distributions.yaml, docs/thesis/data/gmpe_weights.yaml, docs/thesis/data/ph_redi_params.yaml, docs/thesis/data/replacement_costs.yaml
Docs updated: docs/learnings/thesis_extractor_low_confidence.md, docs/orchestration/decision_log.md
Next step: pelicun_dbformatter (P1) and recovery_modeler (P6) are now unblocked.
```
