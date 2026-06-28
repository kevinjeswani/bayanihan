# agents/

This directory contains agent definition files for the `bayanihan` project.

## What this directory is

Each file here is a complete brief for a Claude Code AI agent responsible for one phase of building the package. The agents are part of the artifact — this repo was constructed by AI agents working from structured definitions, and publishing these definitions makes that process transparent and reproducible.

The definitions are not documentation of what was done. They are executable instructions: paste one into a fresh Claude Code session and the agent will execute its phase from scratch, using only the inputs listed in the file.

## How to use an agent definition

1. Open a new Claude Code session (CLI: `claude` in the repo root).
2. Paste the full contents of the agent file as your opening message, or use: `/run agents/<agent-name>.md`
3. The agent will read its inputs, execute its step-by-step strategy, produce its outputs, and append to `docs/orchestration/decision_log.md`.
4. Review outputs before unblocking downstream agents.

Each agent file is self-contained. It names its inputs explicitly — do not run an agent before its upstream dependencies are complete.

## Naming convention

`agents/<agent-name>.md` — the filename is the agent's role identifier, matching the `WRITTEN BY <agent-name>` provenance tags used in YAML and CSV outputs.

## Agents

| File | Phase | Role |
|------|-------|------|
| `thesis_extractor.md` | P0 | Extract the 374-page thesis PDF into chapter markdown and structured YAML with provenance flags |
| `pelicun_dbformatter.md` | P1 | Transform thesis YAML into Pelicun-format fragility and consequence CSVs |
| `edp_normalizer.md` | P2 | Convert raw PERFORM-3D EDP CSVs to SimCenter naming convention |
| `archetype_modeler.md` | P3 | Implement all 20 archetype factories (15 independent + 5 merged aliases) and `Building.from_archetype()` — **COMPLETE** |
| `recovery_modeler.md` | P6 | Implement `recovery.py` (Pelicun per-repair-class + PH impeding factors) and `ph_redi_params.json` — **COMPLETE** |
| `thesis_replication_validator.md` | P7 | Reproduce Chapter 7 figures and produce a side-by-side comparison report — **PENDING** (blocked on P2) |

Phases P4 (synthetic inventory) and P5 (hazard + portfolio modules) were implemented directly without dedicated agent files. The OpenQuake hazard module (`hazard.py`) uses `openquake.hazardlib` GMPE classes — not hand-coded coefficients.

## Mailbox protocol

After completing its outputs, each agent appends a structured report block to `docs/orchestration/decision_log.md`. The orchestrator reads this log to determine what is unblocked. Format:

```
Track: {phase number}
Phase: {phase name}
Result: {one sentence}
Key metric: {if applicable}
Files created: {list}
Docs updated: {list}
Next step: {what's unblocked or what's needed}
```

Agents never ping each other directly. The log is the only coordination surface.

## Tier routing

- **Sonnet** — agents doing research synthesis, vision-based PDF extraction, architecture decisions, or code that requires understanding Pelicun internals. Currently: thesis_extractor, pelicun_dbformatter, archetype_modeler, recovery_modeler, thesis_replication_validator.
- **Haiku** — agents doing mechanical, well-specified data transformation where the schema is fully defined before the agent starts. Currently: edp_normalizer.

When an agent spawns sub-agents (thesis_extractor does this for chapter narrative), chapter-range sub-agents run as Haiku; appendix extraction sub-agents run as Sonnet due to table density.
