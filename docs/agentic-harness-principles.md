# Principles for Semi-Autonomous Agentic Research

A set of design principles for structuring a codebase and orchestration harness that lets AI agents do meaningful, unsupervised research work without creating chaos.

---

## 1. Orchestrator / Subagent Separation

The main agent is a **coordinator, not an executor.** It holds project state, makes sequencing decisions, and delegates discrete units of work to subagents or teammates. It does not write code or run experiments itself.

This separation keeps the orchestrator's context clean and prevents it from getting lost in implementation details. When a subagent returns, the orchestrator reads the summary and decides what to unblock — it doesn't auto-continue.

---

## 2. Tier-Based Agent Selection

Not all tasks need the same model. Explicitly routing by task type keeps cost down and quality up:

- **Complex coding, architecture decisions, research synthesis** → more capable / larger model
- **Admin, investigation, data inspection, enacting implementations** → faster / cheaper model

The routing rule lives in the project instructions, not in the agent's head.

---

## 3. Self-Contained Experiments

Every experiment is an isolated folder with its own dependency file and virtual environment. Nothing is shared between experiments at the code level.

This means:
- An experiment from 6 months ago still runs exactly as it did
- Agents can work on separate experiments in parallel without dependency conflicts
- Deleting an experiment deletes everything it touched

---

## 4. Strict Folder Discipline

Agents routinely dump files in wrong locations when not constrained. Rules are explicit and non-negotiable:

| Type | Location |
|------|----------|
| Experiment code + outputs | `experiments/{id}-{name}/` |
| Track planning docs | `docs/planning/{id}-{name}/` |
| Accumulated knowledge | `docs/learnings/` |
| Orchestration state | `docs/orchestration/` (restricted) |
| Scratchpad / throwaway | `sandbox/` |
| Source datasets | `data/` |

**No new top-level directories without explicit approval.** No notebooks. No loose scripts.

The rule is stated as *never do X*, not just *prefer Y* — agents respond better to hard prohibitions than soft guidance.

---

## 5. Structured Task Entries

Every delegated task must specify:

1. **Track / phase** — where in the project this lives
2. **Description** — what to do
3. **Explicit success criteria** — what "done" looks like

Agents mark tasks complete only after verifying success criteria — not when code runs, not when tests pass, but when the stated outcome is confirmed. If a task blocks on another, it's marked blocked with the dependency named explicitly.

---

## 6. Mailbox Protocol (Async Reporting)

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

## 7. Checkpoint-Driven Documentation

Docs update at every significant checkpoint, not just at phase completion. A checkpoint is any of:

- First results in (even partial or negative)
- Approach decision made (chosen or abandoned)
- Surprising discovery (expected X, got Y)
- Metric threshold crossed (good or bad)
- Phase complete

An agent that finishes work without updating docs hasn't finished. The work is incomplete until the paper trail exists.

---

## 8. Accumulated Knowledge Layer

There's a dedicated `docs/learnings/` folder for facts that took effort to discover and shouldn't be rediscovered. Agents read it before making assumptions; agents write to it when they learn something non-obvious.

This is the project's persistent memory — separate from planning docs (which track in-progress state) and orchestration docs (which track project-level status).

---

## 9. Restricted Orchestration Docs

Some documents are write-restricted for subagents:

- **The master dashboard** — only the orchestrator updates track status
- **The decision log** — append-only, never edit existing entries
- **Track alignment** — only the orchestrator updates

Subagents may read everything freely but write only to their own planning docs and the decision log (append only). This prevents an agent from silently clobbering project state.

---

## 10. Autonomy Is Explicit, Not Assumed

Agents default to pausing for approval on anything irreversible or ambiguous. The level of autonomy is stated per session ("proceed vs wait for approval") rather than inferred from context.

This makes the human-in-the-loop role explicit: the orchestrator decides what to run, reviews summaries before continuing, and is the only one who updates the project dashboard. Agents don't auto-continue after completing work.

---

## Summary

The harness works because it makes the **implicit explicit**: folder locations, task criteria, reporting format, doc update triggers, write restrictions, and autonomy boundaries are all stated in rules the agents can follow literally. The orchestrator's job is to hold state and make decisions. The agents' job is to execute and report. Neither bleeds into the other's role.
