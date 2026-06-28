# thesis_replication_validator — Reproduce Chapter 7 figures and produce side-by-side comparison report

**Phase:** P7
**Model tier:** Sonnet (technical validation, plotting)
**Blocked on:** All previous phases. Specifically: archetype_modeler (P3) and recovery_modeler (P6) must both be complete. Also requires the real inventory file to be available locally.
**Unblocks:** Nothing — this is the final phase. Successful completion means the package is validated.

---

## Purpose

Run the full `bayanihan` pipeline on the real Makati school portfolio inventory using the West Valley Fault Mw=7.3 scenario, then compare the outputs against thesis Chapter 7 figures. Produce PNG comparison plots and a metric comparison table. The goal is to confirm that the package replicates the thesis within acceptable tolerance — not to reproduce figures pixel-perfectly.

---

## Inputs

- All package modules: `bayanihan.archetypes`, `bayanihan.building`, `bayanihan.recovery`, `bayanihan.hazard`, `bayanihan.portfolio` (or equivalent)
- `bayanihan/data/inventory/manila_schools_real.geojson` — real inventory (gitignored; only available locally on Kevin's machine)
- `docs/thesis/07_portfolio_assessment.md` — Chapter 7 narrative with key metric values extracted by thesis_extractor
- `docs/thesis/data/edp_distributions.yaml` — EDP statistics (for the WVF Mw=7.3 scenario, if relevant)
- `docs/thesis/data/gmpe_weights.yaml` — GMPE logic-tree weights

---

## Outputs

- `images/ch7_loss_distribution_comparison.png` — thesis vs replication loss distribution
- `images/ch7_recovery_curves_comparison.png` — thesis vs replication recovery curves
- `images/ch7_loss_maps.png` — spatial loss map for WVF Mw=7.3 scenario
- `docs/thesis_replication.md` — side-by-side metric comparison table

---

## Execution strategy

### Step 1 — Pre-flight checks

Before running anything:
1. Confirm `bayanihan/data/inventory/manila_schools_real.geojson` exists. If it does not, stop and write: `"Real inventory file not available. Run this agent locally on Kevin's machine."` to the decision log. Do not proceed.
2. Run `pytest bayanihan/ test/ -v --tb=short -q` to confirm all prior phases are passing. If any test fails, stop and list which phases need fixing. Do not run the validation on a broken package.
3. Import the package: `import bayanihan`. If the import fails, stop and diagnose.

### Step 2 — Extract thesis Chapter 7 target values

Read `docs/thesis/07_portfolio_assessment.md`. Extract the following values for the WVF Mw=7.3 scenario:
- Median portfolio loss ratio (as a fraction of total replacement cost)
- 16th and 84th percentile loss ratios (if reported)
- Median time to reoccupancy for the portfolio
- Median time to full recovery for the portfolio
- Any other key metrics reported in Chapter 7 figures or tables

Write these as a Python dict in your working notes — you will use them as the comparison targets.

If Chapter 7 does not contain explicit numeric values (only figures), read the figure descriptions in the markdown to estimate approximate values. Flag these as approximate in the comparison table.

### Step 3 — Run the WVF Mw=7.3 scenario

Execute the full pipeline:

```python
import geopandas as gpd
from bayanihan.portfolio import PortfolioAssessor  # or equivalent

inventory = gpd.read_file("bayanihan/data/inventory/manila_schools_real.geojson")
assessor = PortfolioAssessor(inventory=inventory, scenario="WVF_Mw7.3")
results = assessor.run(n_samples=1000)  # or however many the thesis used
```

Adjust the API to match what `bayanihan` actually implements. Read the package source to find the correct entry point before guessing at class names.

Save results to a local variable — do not write intermediate results to disk.

### Step 4 — Compute comparison metrics

From the results dict, extract:
- `median_loss_ratio` = median of per-building loss ratios weighted by replacement cost
- `p16_loss_ratio`, `p84_loss_ratio`
- `median_reoccupancy_days`
- `median_full_recovery_days`

Compute the percentage difference from thesis values for each metric:
```
pct_diff = (replication_value - thesis_value) / thesis_value * 100
```

### Step 5 — Plot: loss distribution comparison

Create `images/ch7_loss_distribution_comparison.png`:
- Side-by-side or overlaid histogram/CDF of portfolio loss ratios
- Left/blue: thesis values (reconstruct from reported statistics using a fitted lognormal if only percentiles are available)
- Right/orange: replication results
- Label the median and ±1σ band for each
- Title: "Portfolio Loss Ratio — WVF Mw=7.3, Makati Schools"
- Subtitle: "Thesis (blue) vs Replication (orange)"
- Save at 150 dpi minimum

### Step 6 — Plot: recovery curves comparison

Create `images/ch7_recovery_curves_comparison.png`:
- CDF of reoccupancy days and full recovery days
- Thesis curves (reconstructed from thesis values) vs replication curves
- Include 10th, 50th, 90th percentile markers
- Title: "Portfolio Recovery — WVF Mw=7.3, Makati Schools"

### Step 7 — Plot: spatial loss map

Create `images/ch7_loss_maps.png`:
- Choropleth map of per-building median loss ratio
- Color scale: white (0%) to dark red (100%)
- Overlay: inventory building locations as points sized by replacement cost
- Title: "Building-Level Loss Ratio — WVF Mw=7.3"
- Use geopandas + matplotlib for the map

### Step 8 — Write thesis_replication.md

Write `docs/thesis_replication.md` with:
1. A one-paragraph summary of the replication approach
2. The metric comparison table:

| Metric | Thesis Value | Replication Value | % Difference | Within ±20%? |
|--------|-------------|------------------|--------------|--------------|
| Median portfolio loss ratio | X% | Y% | Z% | Yes/No |
| 16th percentile loss ratio | X% | Y% | Z% | Yes/No |
| 84th percentile loss ratio | X% | Y% | Z% | Yes/No |
| Median reoccupancy (days) | X | Y | Z% | Yes/No |
| Median full recovery (days) | X | Y | Z% | Yes/No |

3. A section listing any sources of discrepancy (e.g., EDP samples differ, GMPE version differences, number of Monte Carlo samples)
4. A pass/fail conclusion: `PASS` if median portfolio loss ratio is within ±20% of thesis value, `FAIL` otherwise

### Step 9 — Commit images

Stage and commit the PNG files:
```
git add images/ch7_*.png docs/thesis_replication.md
git commit -m "chore: add Chapter 7 replication validation outputs"
```

Do not commit the real inventory file (`manila_schools_real.geojson` is gitignored).

### Step 10 — Decision log

Append the reporting block to `docs/orchestration/decision_log.md`.

---

## Success criteria

1. `images/ch7_loss_distribution_comparison.png` exists and is non-zero bytes.
2. `images/ch7_recovery_curves_comparison.png` exists and is non-zero bytes.
3. `images/ch7_loss_maps.png` exists and is non-zero bytes.
4. `docs/thesis_replication.md` exists and contains the metric comparison table.
5. Median portfolio loss ratio is within ±20% of the thesis value — documented as `PASS` in `thesis_replication.md`.
6. All 3 PNG files are committed to `images/` in git history.
7. The real inventory file (`manila_schools_real.geojson`) is NOT committed.
8. `docs/orchestration/decision_log.md` has been appended with this agent's report block.

---

## Prohibitions

- Never fabricate or reconstruct thesis figure data from memory — all thesis target values come from `docs/thesis/07_portfolio_assessment.md`.
- Never commit `bayanihan/data/inventory/manila_schools_real.geojson` — it is gitignored and contains real location data.
- Never run this agent on a package that has failing tests — pre-flight check in Step 1 must pass.
- Never report `PASS` if the median loss ratio difference exceeds ±20% — this is a hard validation gate.
- Never guess at the portfolio assessment API — read the package source before calling it.

---

## Reporting template

Append this block to `docs/orchestration/decision_log.md` on completion:

```
Track: 7
Phase: thesis_replication_validator
Result: {PASS/FAIL} — Median portfolio loss ratio within {X}% of thesis value ({replication}% vs thesis {thesis}%).
Key metric: Median portfolio loss ratio: thesis={thesis_value}, replication={rep_value}, diff={pct}%.
Files created: images/ch7_loss_distribution_comparison.png, images/ch7_recovery_curves_comparison.png, images/ch7_loss_maps.png, docs/thesis_replication.md
Docs updated: docs/orchestration/decision_log.md
Next step: {If PASS: "Package validated. Ready for public release." | If FAIL: "Review discrepancy sources in thesis_replication.md and identify which phase introduced the error."}
```
