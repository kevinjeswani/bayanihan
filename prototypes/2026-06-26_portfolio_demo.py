"""Portfolio demo: WVF Mw=7.3 Makati + Quezon City scenario.

SYNTHETIC DEMO DATA — illustrative, not real buildings.

Runs the end-to-end pipeline on the 50-building synthetic demo inventory
(manila_schools_demo.geojson) and produces two figures:
  - images/demo_portfolio_loss_map.png
  - images/demo_portfolio_loss_distribution.png

Usage:
    uv run python prototypes/2026-06-26_portfolio_demo.py

References:
    Jeswani, K.K. (2021). MASc thesis, University of Toronto.
    Jeswani et al. (2022). Earthquake Spectra, 38(3), 1946-1971.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")  # non-interactive backend — no display required
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from matplotlib.lines import Line2D

# ---------------------------------------------------------------------------
# Repo root on path for dev-mode imports (when running without `pip install`)
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from bayanihan.portfolio import PortfolioAnalysis

logging.basicConfig(level=logging.WARNING)

# ---------------------------------------------------------------------------
# Scenario: West Valley Fault Mw=7.3 (thesis Chapter 7 reference event)
# Makati City + Quezon City, Metro Manila
# ---------------------------------------------------------------------------
WVF_RUPTURE = {
    "Mw": 7.3,
    "lat": 14.35,   # WVF epicentre (south of Makati)
    "lon": 121.10,
    "depth": 20.0,   # km
    "mechanism": "crustal",  # shallow crustal fault
}

N_SIMS = 500   # sufficient for stable median/CDF
SEED = 2026

IMAGES_DIR = REPO_ROOT / "images"
IMAGES_DIR.mkdir(exist_ok=True)

SYNTHETIC_DISCLAIMER = (
    "SYNTHETIC DEMO DATA — illustrative, not real buildings"
)


def run_demo() -> dict:
    print("=" * 70)
    print("bayanihan | Portfolio Demo")
    print(f"Scenario: WVF Mw={WVF_RUPTURE['Mw']} crustal | n_sims={N_SIMS}")
    print(SYNTHETIC_DISCLAIMER)
    print("=" * 70)

    pa = PortfolioAnalysis.from_demo_inventory(n_simulations=N_SIMS, seed=SEED)
    print(f"\nInventory: {len(pa.inventory)} buildings")
    print(f"  Cities: {pa.inventory['city'].value_counts().to_dict()}")
    print(f"  Total replacement cost: PHP {pa.inventory['replacement_cost_php'].sum()/1e9:.2f}B")
    print(f"\nRunning portfolio Monte Carlo ({N_SIMS} simulations)…")

    result = pa.run(WVF_RUPTURE)

    # Summary stats
    plr = result["portfolio_loss_ratio"]
    summary = result["summary"]

    print("\n--- Portfolio Loss Ratio (repair cost / total replacement cost) ---")
    print(f"  Median:  {np.median(plr):.4f}  ({np.median(plr)*100:.2f}%)")
    print(f"  Mean:    {np.mean(plr):.4f}")
    print(f"  5th pct: {np.percentile(plr, 5):.4f}")
    print(f"  95th pct:{np.percentile(plr, 95):.4f}")

    print("\n--- Per-Building Summary (top 10 by median loss ratio) ---")
    top10 = summary.nlargest(10, "median_loss_ratio")[
        ["id", "archetype_id", "city", "stories", "median_loss_ratio", "median_repair_cost_php"]
    ]
    print(top10.to_string(index=False))

    print(f"\n--- Total replacement cost: PHP {result['total_replacement_cost_php']/1e9:.3f}B ---")
    print(f"    Median total repair cost: PHP {np.median(result['portfolio_repair_cost'])/1e9:.3f}B")

    return result


def make_loss_map(result: dict, inventory) -> Path:
    """Figure 1: Loss map — buildings coloured by median loss ratio."""
    summary = result["summary"]
    out_path = IMAGES_DIR / "demo_portfolio_loss_map.png"

    fig, ax = plt.subplots(figsize=(10, 9))

    # --- Basemap attempt ---
    basemap_ok = False
    try:
        import contextily as ctx
        import geopandas as gpd

        gdf = inventory.copy()
        gdf["median_loss_ratio"] = summary["median_loss_ratio"].values
        gdf_web = gdf.to_crs(epsg=3857)

        norm = mcolors.Normalize(vmin=0.0, vmax=min(summary["median_loss_ratio"].max(), 0.5))
        cmap = plt.cm.RdYlGn_r

        gdf_web.plot(
            column="median_loss_ratio",
            cmap=cmap,
            norm=norm,
            markersize=80,
            alpha=0.85,
            ax=ax,
            zorder=3,
        )

        ctx.add_basemap(
            ax,
            crs=gdf_web.crs,
            source=ctx.providers.CartoDB.Positron,
            zoom=12,
        )
        basemap_ok = True
        ax.set_axis_off()

    except Exception as e:
        # Fallback: plain lat/lon scatter without basemap
        print(f"  [INFO] Basemap not available ({type(e).__name__}: {e}); using plain scatter.")
        lons = summary["lon"].values
        lats = summary["lat"].values
        lr = summary["median_loss_ratio"].values

        norm = mcolors.Normalize(vmin=0.0, vmax=max(lr.max(), 0.01))
        cmap = plt.cm.RdYlGn_r
        sc = ax.scatter(lons, lats, c=lr, cmap=cmap, norm=norm, s=80, alpha=0.85, zorder=3)
        plt.colorbar(sc, ax=ax, label="Median Loss Ratio", shrink=0.6)
        ax.set_xlabel("Longitude")
        ax.set_ylabel("Latitude")
        ax.set_aspect("equal")

    if basemap_ok:
        # Colorbar for contextily-backed plot
        sm = plt.cm.ScalarMappable(cmap=plt.cm.RdYlGn_r, norm=norm)
        sm.set_array([])
        cbar = fig.colorbar(sm, ax=ax, shrink=0.6, pad=0.02)
        cbar.set_label("Median Loss Ratio", fontsize=11)

    # Title and annotations
    ax.set_title(
        f"Portfolio Seismic Loss Map\nWVF Mw={WVF_RUPTURE['Mw']} Crustal Scenario | {N_SIMS} Simulations",
        fontsize=12, fontweight="bold", pad=12,
    )
    ax.annotate(
        SYNTHETIC_DISCLAIMER,
        xy=(0.5, 0.01), xycoords="axes fraction",
        ha="center", fontsize=8, color="dimgray",
        bbox=dict(boxstyle="round,pad=0.3", fc="white", alpha=0.7),
    )

    fig.tight_layout()
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"\n  Saved: {out_path}")
    return out_path


def make_loss_distribution(result: dict) -> Path:
    """Figure 2: Histogram + CDF of portfolio loss ratio."""
    plr = result["portfolio_loss_ratio"]
    out_path = IMAGES_DIR / "demo_portfolio_loss_distribution.png"

    median_plr = np.median(plr)
    p5 = np.percentile(plr, 5)
    p95 = np.percentile(plr, 95)

    fig, (ax_hist, ax_cdf) = plt.subplots(1, 2, figsize=(12, 5))

    # --- Histogram ---
    n_bins = min(30, max(10, N_SIMS // 20))
    ax_hist.hist(
        plr * 100,
        bins=n_bins,
        color="#2166AC",
        edgecolor="white",
        linewidth=0.5,
        alpha=0.85,
    )
    ax_hist.axvline(
        median_plr * 100, color="#D73027", linewidth=2,
        label=f"Median = {median_plr*100:.2f}%",
    )
    ax_hist.axvline(
        p5 * 100, color="gray", linewidth=1.5, linestyle="--",
        label=f"5th pct = {p5*100:.2f}%",
    )
    ax_hist.axvline(
        p95 * 100, color="gray", linewidth=1.5, linestyle=":",
        label=f"95th pct = {p95*100:.2f}%",
    )
    ax_hist.set_xlabel("Portfolio Loss Ratio (%)", fontsize=11)
    ax_hist.set_ylabel("Count", fontsize=11)
    ax_hist.set_title("Distribution (Histogram)", fontsize=11)
    ax_hist.legend(fontsize=9)

    # --- CDF ---
    sorted_plr = np.sort(plr) * 100
    cdf = np.arange(1, len(sorted_plr) + 1) / len(sorted_plr)
    ax_cdf.plot(sorted_plr, cdf, color="#2166AC", linewidth=2)
    ax_cdf.axvline(
        median_plr * 100, color="#D73027", linewidth=2, linestyle="-",
        label=f"Median = {median_plr*100:.2f}%",
    )
    ax_cdf.axhline(0.5, color="#D73027", linewidth=1, linestyle="--", alpha=0.5)
    ax_cdf.fill_betweenx(
        [0, 1],
        p5 * 100, p95 * 100,
        alpha=0.12, color="#2166AC",
        label=f"5th–95th pct range",
    )
    ax_cdf.set_xlabel("Portfolio Loss Ratio (%)", fontsize=11)
    ax_cdf.set_ylabel("Exceedance Probability", fontsize=11)
    ax_cdf.set_title("Empirical CDF", fontsize=11)
    ax_cdf.set_ylim(0, 1)
    ax_cdf.legend(fontsize=9)

    # Shared title
    fig.suptitle(
        f"Portfolio Loss Distribution | WVF Mw={WVF_RUPTURE['Mw']} Crustal | {N_SIMS} Simulations\n"
        f"{SYNTHETIC_DISCLAIMER}",
        fontsize=11, fontweight="bold",
    )
    fig.tight_layout()
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {out_path}")
    return out_path


if __name__ == "__main__":
    result = run_demo()

    print("\nGenerating figures…")
    pa = PortfolioAnalysis.from_demo_inventory(n_simulations=N_SIMS, seed=SEED)
    map_path = make_loss_map(result, pa.inventory)
    dist_path = make_loss_distribution(result)

    print("\n--- Done ---")
    print(f"  Loss map:          {map_path}")
    print(f"  Loss distribution: {dist_path}")
    print(f"\nPortfolio median loss ratio: {np.median(result['portfolio_loss_ratio'])*100:.2f}%")
    print(f"n_buildings={result['n_buildings']}, n_sims={result['n_simulations']}")
    print(SYNTHETIC_DISCLAIMER)
