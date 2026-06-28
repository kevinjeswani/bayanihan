# prototypes/

**Scratch directory. Not part of the release. Not imported by the package.**

Contains exploratory `.py` scripts from the development process — the journey made visible. Kept on GitHub as a record of how the package was built (agent-by-agent), but excluded from the wheel.

## Naming convention

`YYYY-MM-DD_short-description.py`

Date prefix sorts naturally and makes the build timeline legible at a glance.

## Rules

- Python only. No `.ipynb` files here.
- Don't import from `prototypes/` in the package or tests.
- Don't fix lint errors here — these are scratch.
- When a script's core logic matures enough to belong in the package, extract it, then archive or delete the prototype.
