# prototypes/

**Curated, dated record of the development process — the build history made visible. Not imported by the package; not shipped in the wheel.**

As the build matured, production code moved into `bayanihan/` (the package) and the runnable runners + figure scripts into `scripts/`. What remains here is the one still-useful artifact:

- **`2026-06-26_portfolio_demo.py`** — the end-to-end **synthetic** demo (~50 hypothetical schools), referenced from the main README's Quick Start as the no-real-data way to watch the pipeline run end to end:
  `python prototypes/2026-06-26_portfolio_demo.py`

## Naming convention

`YYYY-MM-DD_short-description.py`

Date prefix sorts naturally and makes the build timeline legible at a glance.

## Rules

- Python only. No `.ipynb` files here.
- The package and tests never import from here.
- Lint is intentionally relaxed for this directory (dev scripts, not shipped code).
- When a script's logic matures enough to belong in the package, it graduates into `bayanihan/` or `scripts/`.
