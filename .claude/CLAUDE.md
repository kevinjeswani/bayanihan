# CLAUDE.md — bayanihan

Read this at the start of every session. Single source of truth for project context, constraints, stack, folder conventions, and harness rules. If anything in the conversation contradicts this file, flag it and pause.

> **Private companion:** operational/personal context that is NOT public lives in `.claude/CLAUDE.local.md` (gitignored), imported below. Never move its content into this committed file.

@CLAUDE.local.md

---

## What you're building

`bayanihan` — an open-source Python package porting a 2021 University of Toronto MASc thesis (Jeswani 2021) and its peer-reviewed companion (Jeswani et al., *Earthquake Spectra* 2022) onto a free, modern PBEE stack.

The thesis assessed the seismic resilience of 1,021 public school buildings across Makati and Quezon City, Metro Manila, using commercial/proprietary tools (PERFORM-3D, PACT, and a proprietary risk-assessment platform) that no Filipino practitioner could access. This package rebuilds the loss/recovery pipeline on Pelicun + native recovery modeling so the methodology is free and usable.

**Kevin Jeswani (the author) directs at a high level. AI agents build it.** The agent-driven workflow is part of the artifact — definitions in `agents/`, memory here.

---

## Win condition

The repo exists, is published under Kevin Jeswani's name, is reproducible, and ships a clean v0.1. Adoption is welcome but NOT the success metric. Do not optimize for it.

---

## Hard scope — never cross these lines

- **No re-running structural analysis.** PERFORM-3D models are NOT rebuilt. Saved EDP outputs used as-is. No OpenSeesPy NRHA. No new ground motion generation.
- **No proprietary code or data reproduced.** Only the author's own analytical outputs + open-source tools + parameters extracted from the publicly-archived thesis.
- **Citations only.** Repo face cites the sole-authored thesis (see "Citation discipline"); the EQS 2022 paper stays in `CITATION.cff` references (exact author order there), not on the README face. Do NOT add anyone as repo author/contributor.
- **No scope creep into:** smartphone apps, web dashboards, Tagalog/Cebuano translation, formal academic collaboration, follow-up papers, or any stakeholder outreach before v0.1 ships.
- **No Sphinx/RST for v0.1.** Raw markdown. Defer mkdocs-material to v0.2.
- **GMPEs via `openquake.hazardlib`, not hand-coded.** Validated GMPE classes behind the `HazardModel` interface — same ecosystem as the GEM Philippine national model (PEM), so it's the on-ramp to a v0.2 national-hazard path. (Supersedes the original "no OpenQuake / implement GMPEs directly" plan — hand-coding was error-prone and redundant once the GEM PEM was confirmed OpenQuake-native.)

> Engagement/contact policy (who to approach or avoid, and when) is intentionally NOT in this public file. It lives in `CLAUDE.local.md`. Default: **suggest no outreach to anyone** unless `CLAUDE.local.md` explicitly permits it and v0.1 has shipped.

---

## The stack

| Component | Choice | Version pin |
|-----------|--------|-------------|
| Python | 3.13 | `>=3.13` |
| Damage + loss | Pelicun | `>=3.9,<4` |
| Recovery | Pelicun per-repair-class milestones + PH impeding factors | no PyREDi (see note) |
| Numerics | numpy, scipy, pandas | latest compatible |
| Geospatial | geopandas, shapely | latest compatible |
| GMPEs | **`openquake.hazardlib`** (validated GMPE classes) | `openquake-engine` 3.25.1 |
| Spatial correlation | Loth & Baker 2013 (native impl) | — |
| Surface caching | pyarrow (parquet) | latest |
| Visualization | matplotlib + contextily | latest |
| Build | pyproject.toml + hatchling | no setup.py |
| Dep mgmt | uv | committed lockfile |
| Lint + format | ruff | latest |
| Testing | pytest + pytest-cov | latest |
| Type checking | mypy | latest |
| Param validation | pydantic v2 | `>=2.0` |
| License | Apache-2.0 | — |
| Distribution | GitHub (`bayanihan`); PyPI deferred until E2E PoC proven | — |

**GMPEs (8-branch logic tree, evaluated via `openquake.hazardlib`):** shallow-crustal {CY08, BA08, BSSA14, Zhao06}; subduction-interface {Youngs97, AB03, Zhao06, Abrahamson16}; equal weights, per Peñarubia et al. (2020). The PH national model (GEM PEM) is this same OpenQuake ecosystem — the v0.2 national-hazard path is a `HazardModel` subclass, not a rewrite.

**PyREDi note (2026-06-26):** The `arup-group/REDi` GitHub repo returned 404. For v0.1, implement the REDi methodology (repair classes, impeding factors, three recovery milestones) natively via Pelicun's repair-class machinery. Build a thin `recovery.py`: Pelicun computes repair time with sequencing/labor; sample Philippine-calibrated impeding-factor delays; combine into downtime. Cite Almufti & Willford (2013) for methodology. Captured reference at `docs/reference/redi_methodology.md`.

---

## Phase plan (authoritative)

| Phase | Deliverable | Status |
|-------|-------------|--------|
| **P0** | Thesis → structured data (markdown + provenance YAMLs + appendices) | ✅ DONE |
| **P1** | Pelicun component DB (fragility + consequence CSVs, `PH.*` IDs) | ✅ DONE |
| **P2** | Real EDP ingestion (PERFORM-3D outputs → SimCenter naming) | ✅ DONE (EDPs recovered + ingested) |
| **P3** | All 20 archetypes + single-building assessment | ✅ DONE |
| **P4** | Synthetic demo inventory (~50 hypothetical Manila schools) | ✅ DONE |
| **P5** | Portfolio Monte Carlo (real correlated 1,021-building run) | ✅ DONE |
| **P6** | PH recovery model (`recovery.py` + `ph_redi_params.json`) | ✅ DONE |
| **P7** | Validation — reproduce thesis Ch 7 WVF Mw=7.3 (both cities) within tolerance | ✅ DONE (all 4 DVs within ~±25%) |
| **P8** | v0.1 release | 🟢 READY (public wrap-up in progress) |
| **P9** | Articles + optional post-ship outreach | 🔵 POST-SHIP |

The pipeline runs end-to-end on the **real recovered EDP data** (P2–P7 complete): the WVF Mw 7.3 portfolio reproduces the 2021 thesis decision variables (loss, casualties, recovery) within tolerance for both cities, with a synthetic demo path retained for users without the real inventory. Done: P0–P7; P8 (v0.1) in public wrap-up.

---

## Folder structure (canonical — enforced)

```
bayanihan/                    # repo root
├── README.md
├── SOUL.md                              # the "why" — personal statement of the project
├── LICENSE                              # Apache-2.0
├── pyproject.toml
├── .gitignore
├── .github/workflows/
├── bayanihan/                # the importable package
│   ├── __init__.py
│   ├── building.py  archetypes.py  portfolio.py  hazard.py  recovery.py
│   └── data/                            # bundled via importlib.resources
│       ├── fragility.csv  consequence_repair.csv  ph_redi_params.json  replacement.csv
│       ├── edps/                        # PERFORM-3D outputs (added when recovered)
│       └── inventory/                   # manila_schools_demo.geojson (synthetic, committed)
├── docs/
│   ├── agentic-harness-principles.md    # PUBLIC: agentic harness design principles
│   ├── thesis/                          # PUBLIC: thesis as markdown + data/*.yaml (PDFs gitignored)
│   ├── reference/                       # PUBLIC: captured technical refs (PDFs gitignored)
│   ├── outputs/                         # PUBLIC: committed validation summary (KPIs + figures)
│   ├── validation/                      # PUBLIC: detailed eval scorecard
│   ├── .local/                          # PRIVATE: gitignored working layer (README marker committed)
│   │   └── planning/                    #   strategy/working docs (lives under .local)
│   ├── learnings/                       # PRIVATE (gitignored) — research + agent working notes
│   └── orchestration/                   # PRIVATE (gitignored) — dashboard + decision log
├── scripts/                             # PUBLIC: simulation runners + figure scripts (run on demand)
├── examples/  prototypes/  test/  utils/  images/
├── sandbox/                             # PRIVATE: scratch, contents gitignored (README committed)
├── agents/                              # PUBLIC: agent definitions (the showcase)
└── .claude/
    ├── CLAUDE.md                        # this file (PUBLIC)
    └── CLAUDE.local.md                  # PRIVATE (gitignored) — personal/operational context
```

### Harness folder rules (hard — no exceptions without Kevin's approval)

| Content type | Location | Public? |
|-------------|----------|---------|
| Package code + bundled data | `bayanihan/` | yes |
| Simulation runners + figure scripts | `scripts/` | yes |
| Committed validation summary + scorecard | `docs/outputs/`, `docs/validation/` | yes |
| Thesis source + extracted data | `docs/thesis/` | yes (PDFs gitignored) |
| Captured technical references | `docs/reference/` | yes (PDFs gitignored) |
| Agent definitions | `agents/` | yes |
| Planning / strategy docs | `docs/.local/planning/` | **no — gitignored** |
| Accumulated knowledge / research notes | `docs/learnings/` | **no — gitignored** |
| Orchestration state (dashboard, decision log) | `docs/orchestration/` | **no — gitignored** |
| Anything private/personal | any `.local/` folder | **no — gitignored** |
| Throwaway scratch | `sandbox/` | **no — gitignored** |
| Dated dev prototypes (curated record) | `prototypes/` (`YYYY-MM-DD_*.py`) | yes |

**No new top-level directories without explicit approval from Kevin.**

### Privacy discipline (critical — this repo is destined to go public)

- **Anything sensitive — personal context, strategy, anyone's name in an avoid/contact list, the backstory — NEVER goes in a committed/public file.** It goes in `CLAUDE.local.md`, `docs/.local/`, or `docs/orchestration/` (all gitignored).
- Before the repo is ever made public, run a full audit: `git grep` the tracked tree for sensitive names/terms; only the published citation may contain co-author names.
- `.local/` (any depth) and `sandbox/` are gitignored except their committed `README.md` markers — the private-working layer is *visible as a convention*, never by content.

### Gitignored — never commit
- `docs/.local/` (planning, scratch, drafts), `docs/orchestration/`, `docs/learnings/` — private working docs
- `docs/.local/` and any `**/.local/` contents (except README markers); `sandbox/` contents
- `CLAUDE.local.md`, `.claude/CLAUDE.local.md`
- `bayanihan/data/inventory/manila_schools_real*.geojson` — real 1,021-building inventory
- `docs/thesis/*.pdf`, `docs/reference/*.pdf` — large source PDFs
- `.venv/`, `__pycache__/`, `*.egg-info/`, `dist/`, `.ruff_cache/`, `.mypy_cache/`, `.pytest_cache/`

---

## Data approach

**Committed (public):** synthetic demo inventory (~50 hypothetical Manila schools, generic IDs); all component fragility/consequence/replacement parameters from thesis appendices (provenance-flagged CSV); bundled archetype EDP samples once recovered; PH-calibrated impeding-factor parameters with provenance.

**Gitignored — never commit:** `bayanihan/data/inventory/manila_schools_real.geojson` (actual 1,021 buildings).

**Committed as PNG only:** real-data thesis Ch 7 replication figures → `images/`.

---

## Provenance discipline

Every parameter in `bayanihan/data/*.csv` traces to a specific thesis table.

1. `thesis_extractor` reads `docs/thesis/Jeswani_Kevin_Kamlesh_202103_MAS_thesis.pdf`
2. Outputs structured YAML in `docs/thesis/data/*.yaml` — each value carries `source` (section/table/page) and `provenance_confidence` (`high`/`medium`/`low`)
3. `pelicun_dbformatter` reads YAML → writes Pelicun-format CSVs in `bayanihan/data/`

**Never hardcode a fragility or consequence value in Python.** Code reads YAML. Low-confidence flags require Kevin's review before promotion to production CSVs.

---

## Citation discipline

**Repo-face policy (Kevin's call, 2026-06-28):** the README "Citation" section and `CITATION.cff` `preferred-citation` point to the **sole-authored thesis only** — it stands on its own on the repo face. The peer-reviewed paper is **not** foregrounded as "cite this": it appears once as neutral provenance ("Jeswani et al. (2022), *Earthquake Spectra*" + DOI) under README "Sources & provenance", and in full (exact author order) in `CITATION.cff` `references`. **Do NOT re-promote the paper to the Citation section, and do NOT add the co-authors to the repo face.**

**Primary citation — repo face (sole-authored, cite exactly):**
```
Jeswani, K. K. (2021). The Seismic Resilience of Critical Spatially-Distributed Building Portfolios. MASc thesis, University of Toronto. https://utoronto.scholaris.ca/items/4e628627-fb5b-4674-bac1-e20cb503a1f5
```

**Peer-reviewed paper — provenance / `CITATION.cff` references only (exact author order when cited):**
```
Jeswani et al. (2022). Seismic risk assessment and mitigation analysis of large public school building portfolios in Metro Manila. Earthquake Spectra, 38(3), 1946–1971. https://doi.org/10.1177/87552930221086304
```

Add no further acknowledgments or attribution lines. Do NOT add anyone as repo author/contributor.

---

## Agent tier routing

| Task | Model |
|------|-------|
| Complex coding, architecture, research synthesis, writing agent definitions | Sonnet |
| Admin, investigation, data inspection, mechanical scaffolding, file ops, boilerplate | Haiku |
| Project state, phase sequencing, CLAUDE.md authoring, dashboard updates | Orchestrator (never delegate) |

---

## Subagent reporting protocol

On task completion, every subagent reports:
```
Track: {phase number}
Phase: {phase name}
Result: {one sentence}
Key metric: {if applicable}
Files created: {list}
Docs updated: {list}
Next step: {what's unblocked or what's needed}
```

Subagents append decisions to `docs/orchestration/decision_log.md` (gitignored local). The orchestrator updates `docs/orchestration/dashboard.md` after reviewing the report.

---

## How to engage with Kevin

- Direct, technical, opinionated. Senior software/AI engineer, P.Eng, deep PBEE background. Don't over-explain fundamentals.
- Match his energy. Blunt is fine. Be decisive; flag blockers with proposed solutions.
- Don't bring up project backstory during technical work.
- Further engagement notes (tone, boundaries, personal context) are in `CLAUDE.local.md` — read it locally.

---

## Agentic Harness Principles (embedded verbatim)

---

### 1. Orchestrator / Subagent Separation

The main agent is a **coordinator, not an executor.** It holds project state, makes sequencing decisions, and delegates discrete units of work to subagents or teammates. It does not write code or run experiments itself.

This separation keeps the orchestrator's context clean and prevents it from getting lost in implementation details. When a subagent returns, the orchestrator reads the summary and decides what to unblock — it doesn't auto-continue.

---

### 2. Tier-Based Agent Selection

Not all tasks need the same model. Explicitly routing by task type keeps cost down and quality up:

- **Complex coding, architecture decisions, research synthesis** → more capable / larger model (Sonnet)
- **Admin, investigation, data inspection, enacting implementations** → faster / cheaper model (Haiku)

The routing rule lives in the project instructions, not in the agent's head.

---

### 3. Self-Contained Experiments

Every experiment is an isolated folder with its own dependency file and virtual environment. Nothing is shared between experiments at the code level.

This means:
- An experiment from 6 months ago still runs exactly as it did
- Agents can work on separate experiments in parallel without dependency conflicts
- Deleting an experiment deletes everything it touched

---

### 4. Strict Folder Discipline

Agents routinely dump files in wrong locations when not constrained. Rules are explicit and non-negotiable:

| Type | Location |
|------|----------|
| Package code + outputs | `bayanihan/` |
| Track planning docs | `docs/planning/` |
| Accumulated knowledge | `docs/learnings/` |
| Orchestration state | `docs/orchestration/` (restricted) |
| Scratchpad / throwaway | `sandbox/` |
| Source datasets | `bayanihan/data/` |

**No new top-level directories without explicit approval.** No notebooks in prototypes. No loose scripts at root.

The rule is stated as *never do X*, not just *prefer Y* — agents respond better to hard prohibitions than soft guidance.

---

### 5. Structured Task Entries

Every delegated task must specify:

1. **Track / phase** — where in the project this lives
2. **Description** — what to do
3. **Explicit success criteria** — what "done" looks like

Agents mark tasks complete only after verifying success criteria — not when code runs, not when tests pass, but when the stated outcome is confirmed. If a task blocks on another, it's marked blocked with the dependency named explicitly.

---

### 6. Mailbox Protocol (Async Reporting)

Orchestrators don't poll. Teammates report when done.

Every completion message has the same structure:
```
Track: {number}
Phase: {name}
Result: {one sentence}
Key metric: {if applicable}
Files created: {list}
Docs updated: {list}
Next step: {what's unblocked or what's needed}
```

Inter-agent messages are only sent for genuine cross-agent dependencies — not as a general communication pattern.

---

### 7. Checkpoint-Driven Documentation

Docs update at every significant checkpoint, not just at phase completion. A checkpoint is any of:

- First results in (even partial or negative)
- Approach decision made (chosen or abandoned)
- Surprising discovery (expected X, got Y)
- Metric threshold crossed (good or bad)
- Phase complete

An agent that finishes work without updating docs hasn't finished. The work is incomplete until the paper trail exists.

---

### 8. Accumulated Knowledge Layer

There's a dedicated `docs/learnings/` folder for facts that took effort to discover and shouldn't be rediscovered. Agents read it before making assumptions; agents write to it when they learn something non-obvious.

This is the project's persistent memory — separate from planning docs (which track in-progress state) and orchestration docs (which track project-level status).

---

### 9. Restricted Orchestration Docs

Some documents are write-restricted for subagents:

- **The master dashboard** (`docs/orchestration/dashboard.md`) — only the orchestrator updates track status
- **The decision log** (`docs/orchestration/decision_log.md`) — append-only, never edit existing entries
- **Track alignment** — only the orchestrator updates

Subagents may read everything freely but write only to their own planning docs and the decision log (append only). This prevents an agent from silently clobbering project state.

---

### 10. Autonomy Is Explicit, Not Assumed

Agents default to pausing for approval on anything irreversible or ambiguous. The level of autonomy is stated per session ("proceed vs wait for approval") rather than inferred from context.

This makes the human-in-the-loop role explicit: the orchestrator decides what to run, reviews summaries before continuing, and is the only one who updates the project dashboard. Agents don't auto-continue after completing work.

---

### Summary

The harness works because it makes the **implicit explicit**: folder locations, task criteria, reporting format, doc update triggers, write restrictions, and autonomy boundaries are all stated in rules the agents can follow literally. The orchestrator's job is to hold state and make decisions. The agents' job is to execute and report. Neither bleeds into the other's role.
