"""Geospatial loss visualization — WVF Mw 7.3 per-building mean loss ratio.

Reads two GITIGNORED files at runtime (never committed):
  - sandbox/portfolio-analysis/wvf73_per_building.parquet
  - bayanihan/data/inventory/manila_schools_real.geojson

Produces ONE COMMITTED PNG in images/:
  - images/wvf73_loss_map_metro.png   — all 1,021 schools across Metro Manila

Usage (from repo root):
    .venv/bin/python scripts/make_loss_map.py

Dependencies (already in venv):
    geopandas, contextily, matplotlib, pandas, numpy, pyproj

Symbology notes (after Jeswani 2021 thesis Ch.7 Figs 7-6 and 7-15):
    - Bubble size   = absolute PHP loss (not floor area; not replacement cost).
                      Proportional to monetary loss in PHP; five reference sizes
                      shown in legend (~500M / 1B / 2B / 3B / 4B+ PHP).
    - Bubble color  = mean loss RATIO in five fixed bins:
                         green     0–10%
                         yellow    10–20%
                         orange    20–30%
                         red-orange 30–40%
                         red        ≥40%
    - WVF trace     = REAL GEM GAF geometry (GEMScienceTools/gem-global-active-faults,
                      CC-BY-4.0, fetched 2026-06-27). Solid red line, ~36 nodes
                      through Metro Manila.  Epicentre (121.09, 14.65) is 0.69 km
                      from nearest trace node — confirmed on-fault.
    - Epicentre     = sunburst star (like thesis Fig 7-6) at (121.09, 14.65).
    - Basemap       = CartoDB Positron (light/neutral, matches thesis style).

Fault-trace source:
    GEM Science Tools (2023). GEM Global Active Faults database.
    https://github.com/GEMScienceTools/gem-global-active-faults
    License: CC-BY-4.0. Coordinates extracted for the West Valley Fault
    feature (108 nodes); filtered to Metro Manila extent (36 nodes,
    lat 14.36–14.97, lon 121.04–121.20).

Notes:
    - Reprojected to EPSG:3857 for tile alignment; coords NOT written to outputs.
    - This work uses an open-stack reproduction (Pelicun 3 / openquake.hazardlib).
    - Run date: 2026-06-27.

Refs:
    Jeswani, K. K. (2021). The Seismic Resilience of Critical Spatially-Distributed
        Building Portfolios. MASc thesis, University of Toronto.
"""
from __future__ import annotations

import json
from pathlib import Path

import contextily as ctx
import geopandas as gpd
import matplotlib.patheffects as pe
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import BoundaryNorm, ListedColormap
from matplotlib.lines import Line2D

# ── Paths ─────────────────────────────────────────────────────────────────────
REPO = Path(__file__).resolve().parent.parent
PARQUET = REPO / "sandbox" / "portfolio-analysis" / "wvf73_per_building.parquet"
GEOJSON = REPO / "bayanihan" / "data" / "inventory" / "manila_schools_real.geojson"
SUMMARY = REPO / "bayanihan" / "data" / "results" / "wvf73_portfolio_summary.json"
IMAGES = REPO / "images"
IMAGES.mkdir(exist_ok=True)

# ── Style ─────────────────────────────────────────────────────────────────────
FONT_FAMILY = "sans-serif"
ALPHA_PT = 0.90
EDGECOLOR = "white"
EDGELW = 0.35
CAPTION_FS = 6
LABEL_FS = 8
TITLE_FS = 10
SUPTITLE_FS = 11
RUN_DATE = "2026-06-27"

# ── Thesis-matched loss-ratio color scheme (Figs 7-6, 7-15) ───────────────────
# Five fixed bins matching original legend:
#   0–10%: green  10–20%: yellow  20–30%: orange  30–40%: red-orange  ≥40%: red
LOSS_BINS = [0.00, 0.10, 0.20, 0.30, 0.40, 1.01]
LOSS_COLORS = ["#4dac26", "#f1b912", "#f07b00", "#e03010", "#99000d"]
LOSS_LABELS = ["0–10%", "10–20%", "20–30%", "30–40%", "≥40%"]
LOSS_CMAP = ListedColormap(LOSS_COLORS)
LOSS_NORM = BoundaryNorm(LOSS_BINS, len(LOSS_COLORS))

# ── Bubble sizing: proportional to absolute PHP loss (thesis scheme) ───────────
# Thesis legend shows circles for ~500M / 1B / 2B / 3B / 4B+ PHP.
# We map sqrt(mean_loss_php) to marker area with explicit reference sizes.
SIZE_REF_PHP = [5e8, 1e9, 2e9, 3e9, 4e9]   # 500M, 1B, 2B, 3B, 4B PHP
SIZE_REF_S   = [10,  18,  36,  55,  80]     # corresponding marker areas (pts²)


def loss_to_size(loss_php: pd.Series) -> np.ndarray:
    """Map mean loss PHP → marker area; interpolates on sqrt scale."""
    sq = np.sqrt(loss_php.clip(lower=1).values)
    sq_ref = np.sqrt(SIZE_REF_PHP)
    return np.interp(sq, sq_ref, SIZE_REF_S, left=SIZE_REF_S[0], right=SIZE_REF_S[-1])


# ── WVF surface trace — REAL geometry from GEM GAF database ───────────────────
# Source: GEMScienceTools/gem-global-active-faults (CC-BY-4.0, fetched 2026-06-27)
# Feature "West Valley Fault", slip_type=Dextral-Normal, 108 total nodes.
# Filtered to Metro Manila (lat 14.36–14.97): 36 nodes.
# Epicentre (121.09, 14.65) is 0.69 km from nearest trace node (index 20).
WVF_TRACE_LONLAT = [
    (121.1950527, 14.96690238),
    (121.1940202, 14.96255456),
    (121.1919228, 14.95621739),
    (121.1890,    14.94476576),
    (121.1851259, 14.92647199),
    (121.1799007, 14.91114805),
    (121.1780898, 14.90450094),
    (121.1742217, 14.88897924),
    (121.1682806, 14.88238328),
    (121.1623335, 14.86695940),
    (121.1553322, 14.85167182),
    (121.1478879, 14.82916142),
    (121.1441451, 14.80441541),
    (121.1438604, 14.80371322),
    (121.1432203, 14.80249098),
    (121.1428298, 14.80183994),
    (121.1425829, 14.80116071),
    (121.1416072, 14.79579494),
    (121.1393119, 14.77277590),
    (121.1379620, 14.75923738),
    (121.0907256, 14.65616809),  # nearest to epicentre (0.69 km)
    (121.0806225, 14.63223971),
    (121.0669692, 14.56441418),
    (121.0653032, 14.55802326),
    (121.0600314, 14.54614509),
    (121.0561571, 14.52293832),
    (121.0545280, 14.51656442),
    (121.0542873, 14.50379766),
    (121.0527245, 14.48789410),
    (121.0481340, 14.43325907),
    (121.0490263, 14.42646924),
    (121.0477169, 14.40472032),
    (121.0446975, 14.38583577),
    (121.0411380, 14.37377852),
    (121.0400329, 14.36344424),
    (121.0377619, 14.35909033),
]

# ── EVF trace (scenario C, 103 nodes; Metro Manila segment shown for context) ──
EVF_TRACE_LONLAT = [
    (121.2048416, 14.79022348),
    (121.1992868, 14.78375008),
    (121.1938145, 14.77508974),
    (121.1871427, 14.76581546),
    (121.1830018, 14.76143308),
    (121.1779605, 14.75471659),
    (121.1747519, 14.74861130),
    (121.1713486, 14.74212537),
    (121.1681002, 14.73823450),
    (121.1639016, 14.73282450),
    (121.1608782, 14.72706751),
    (121.1588475, 14.72385723),
    (121.1578047, 14.72244476),
    (121.1565989, 14.72036638),
    (121.1553959, 14.71883526),
    (121.1521618, 14.71530516),
    (121.1497665, 14.71190317),
    (121.1456817, 14.70370572),
    (121.1437679, 14.69847275),
    (121.1423479, 14.69359816),
    (121.1389355, 14.69153970),
    (121.1316734, 14.68638313),
    (121.1297462, 14.68397804),
]


# ── Data loading + joining ────────────────────────────────────────────────────
def load_data() -> gpd.GeoDataFrame:
    """Merge loss parquet onto real inventory GeoJSON; compute mean_loss_php."""
    df_loss = pd.read_parquet(PARQUET)
    gdf = gpd.read_file(GEOJSON)
    merged = gdf.merge(
        df_loss[[
            "building_id", "mean_loss_ratio", "median_loss_ratio",
            "p84_loss_ratio", "collapse_rate",
            "mean_reoccupancy_days", "mean_full_recovery_days",
        ]],
        on="building_id",
        how="inner",
    )
    cost_col = "replacement_cost_php"
    merged["mean_loss_php"] = merged["mean_loss_ratio"] * merged[cost_col]
    merged = merged.to_crs(epsg=3857)
    return merged


def make_epicentre_gdf() -> gpd.GeoDataFrame:
    """Return 3857 GeoDataFrame for the WVF epicentre point."""
    epi = gpd.GeoDataFrame(
        {"name": ["WVF Mw 7.3 Epicentre"]},
        geometry=gpd.points_from_xy([121.09], [14.65]),
        crs="EPSG:4326",
    ).to_crs(epsg=3857)
    return epi


def make_fault_gdf(coords_lonlat: list) -> gpd.GeoDataFrame:
    """Return 3857 GeoDataFrame for a fault surface trace."""
    from shapely.geometry import LineString
    line = LineString(coords_lonlat)
    return gpd.GeoDataFrame(geometry=[line], crs="EPSG:4326").to_crs(epsg=3857)


# ── Legend helpers ─────────────────────────────────────────────────────────────
def size_legend_handles(loss_php_series: pd.Series) -> list:
    """Legend handles for bubble size (PHP loss scale)."""
    handles = []
    for php, s in zip(SIZE_REF_PHP, SIZE_REF_S):
        handles.append(Line2D(
            [0], [0], marker="o", color="none",
            markerfacecolor="#888888", markeredgecolor="white",
            markersize=np.sqrt(s),
            label=f"₱{php/1e9:.1g}B",
        ))
    return handles


def color_legend_handles() -> list:
    """Legend handles for bubble color (loss ratio bins)."""
    handles = []
    for color, lbl in zip(LOSS_COLORS, LOSS_LABELS):
        handles.append(Line2D(
            [0], [0], marker="o", color="none",
            markerfacecolor=color, markeredgecolor="white",
            markersize=8, label=lbl,
        ))
    return handles


# ── Core plotting function ─────────────────────────────────────────────────────
def plot_loss_map(
    gdf: gpd.GeoDataFrame,
    epi_gdf: gpd.GeoDataFrame,
    wvf_gdf: gpd.GeoDataFrame,
    evf_gdf: gpd.GeoDataFrame,
    *,
    city_filter: str | None = None,
    buffer_deg: float = 0.015,
    figsize: tuple = (9, 8),
    title: str = "",
    out_path: Path,
    show_evf: bool = False,
    show_city_labels: bool = False,
) -> None:
    """Render one loss map in thesis-matched symbology and save to out_path."""
    sub = gdf if city_filter is None else gdf[gdf["city"] == city_filter]
    cost_col = "replacement_cost_php"

    fig, ax = plt.subplots(figsize=figsize, facecolor="white")
    ax.set_facecolor("white")

    # ── Data extent → tile extent ─────────────────────────────────────────────
    bounds = sub.total_bounds
    buf_m = buffer_deg * 111_000
    ax.set_xlim(bounds[0] - buf_m, bounds[2] + buf_m)
    ax.set_ylim(bounds[1] - buf_m, bounds[3] + buf_m)

    # ── Basemap ───────────────────────────────────────────────────────────────
    try:
        ctx.add_basemap(
            ax,
            crs=gdf.crs.to_string(),
            source=ctx.providers.CartoDB.Positron,
            zoom="auto",
            alpha=0.88,
        )
    except Exception:
        ax.set_facecolor("#f0f0f0")

    # ── EVF (if requested, shown dashed) ──────────────────────────────────────
    if show_evf:
        evf_gdf.plot(ax=ax, color="#0044cc", linewidth=1.2, linestyle="--",
                     zorder=3, alpha=0.6, label="EVF")

    # ── WVF surface trace (solid red, thesis style) ───────────────────────────
    wvf_gdf.plot(ax=ax, color="#cc1111", linewidth=2.2, zorder=4,
                 label="West Valley Fault")
    # Thin highlight line
    wvf_gdf.plot(ax=ax, color="#ff5555", linewidth=0.7, linestyle="-",
                 zorder=5, alpha=0.5)
    # WVF label — clip to axes extent so it doesn't escape on zoom views
    wvf_geom = wvf_gdf.geometry.iloc[0]
    xl, xr = ax.get_xlim()
    yb, yt = ax.get_ylim()
    from shapely.geometry import box as sbox
    clip_box = sbox(xl, yb, xr, yt)
    wvf_clip = wvf_geom.intersection(clip_box)
    if not wvf_clip.is_empty:
        mid_pt = wvf_clip.interpolate(0.65, normalized=True)
        p0 = wvf_clip.interpolate(0.60, normalized=True)
        p1 = wvf_clip.interpolate(0.70, normalized=True)
        angle_deg = float(np.degrees(np.arctan2(p1.y - p0.y, p1.x - p0.x)))
        ax.text(
            mid_pt.x + 3500, mid_pt.y,
            "West Valley Fault",
            fontsize=CAPTION_FS + 0.5, color="#cc1111", fontweight="bold",
            rotation=angle_deg, ha="left", va="center", zorder=9, clip_on=True,
            path_effects=[pe.withStroke(linewidth=1.5, foreground="white")],
        )

    # ── Buildings: size = PHP loss, color = loss ratio bin ────────────────────
    sizes = loss_to_size(sub["mean_loss_php"])
    color_indices = np.digitize(sub["mean_loss_ratio"].values, LOSS_BINS[1:])
    colors = [LOSS_COLORS[min(ci, len(LOSS_COLORS) - 1)] for ci in color_indices]

    ax.scatter(
        sub.geometry.x,
        sub.geometry.y,
        c=colors,
        s=sizes,
        alpha=ALPHA_PT,
        edgecolors=EDGECOLOR,
        linewidths=EDGELW,
        zorder=6,
    )

    # ── Epicentre (sunburst star, matching thesis style) ──────────────────────
    epi_x = epi_gdf.geometry.x.values[0]
    epi_y = epi_gdf.geometry.y.values[0]
    # Check if it's in the visible area (with generous buffer)
    xl, xr = ax.get_xlim()
    yb, yt = ax.get_ylim()
    if xl - buf_m * 2 < epi_x < xr + buf_m * 2 and yb - buf_m * 2 < epi_y < yt + buf_m * 2:
        ax.scatter(
            [epi_x], [epi_y],
            marker="*", s=320,
            color="#ff2200", edgecolors="white", linewidths=0.8,
            zorder=10, label="Epicentre (WVF Mw 7.3)",
        )
        ax.text(
            epi_x + 3500, epi_y + 2500,
            "WVF M7.3", fontsize=CAPTION_FS,
            color="#ff2200", fontweight="bold", zorder=11,
            path_effects=[pe.withStroke(linewidth=1.5, foreground="white")],
        )

    # ── City labels ───────────────────────────────────────────────────────────
    if show_city_labels:
        for city, group in gdf.groupby("city"):
            cx_pt = group.geometry.x.mean()
            cy_pt = group.geometry.y.mean()
            ax.text(
                cx_pt, cy_pt, {"MC": "MAKATI\nCITY", "QC": "QUEZON\nCITY"}.get(city, city),
                fontsize=LABEL_FS, fontweight="bold",
                ha="center", va="center",
                color="#333333", alpha=0.5, zorder=7,
                path_effects=[pe.withStroke(linewidth=2, foreground="white")],
            )

    # ── Legend: Loss ratio colors (left panel, like thesis) ───────────────────
    color_handles = color_legend_handles()
    leg_color = ax.legend(
        handles=color_handles,
        title="Loss Ratio\n(color)",
        title_fontsize=CAPTION_FS + 1,
        fontsize=CAPTION_FS + 1,
        loc="lower left",
        frameon=True, framealpha=0.92, edgecolor="#cccccc",
    )
    ax.add_artist(leg_color)

    # ── Legend: PHP loss sizes (lower right) ──────────────────────────────────
    size_handles = size_legend_handles(sub["mean_loss_php"])
    leg_size = ax.legend(
        handles=size_handles,
        title="Mean PHP Loss\n(bubble size)",
        title_fontsize=CAPTION_FS + 1,
        fontsize=CAPTION_FS + 1,
        loc="lower right",
        frameon=True, framealpha=0.92, edgecolor="#cccccc",
    )
    ax.add_artist(leg_size)

    # ── Legend: fault / epicentre (upper left) ────────────────────────────────
    fault_handle = Line2D([0], [0], color="#cc1111", linewidth=2, label="WVF surface trace")
    epi_handle = Line2D(
        [0], [0], marker="*", color="none",
        markerfacecolor="#ff2200", markeredgecolor="white",
        markersize=11, label="Epicentre (Mw 7.3)",
    )
    extra = []
    if show_evf:
        extra = [Line2D([0], [0], color="#0044cc", linewidth=1.5, linestyle="--", label="EVF")]
    leg_fault = ax.legend(
        handles=[fault_handle, epi_handle] + extra,
        fontsize=CAPTION_FS + 1,
        loc="upper left",
        frameon=True, framealpha=0.92, edgecolor="#cccccc",
    )
    ax.add_artist(leg_fault)

    # ── Title ─────────────────────────────────────────────────────────────────
    ax.set_title(title, fontsize=SUPTITLE_FS, fontweight="bold", pad=8)

    # ── Axis labels / ticks ───────────────────────────────────────────────────
    ax.set_xlabel("Easting (m, EPSG:3857)", fontsize=CAPTION_FS + 1, color="#666666")
    ax.set_ylabel("Northing (m, EPSG:3857)", fontsize=CAPTION_FS + 1, color="#666666")
    ax.tick_params(labelsize=CAPTION_FS, colors="#888888")

    # ── Attribution ───────────────────────────────────────────────────────────
    fig.text(
        0.01, 0.005,
        f"Basemap © CartoDB Positron  |  Fault: GEM GAF (CC-BY-4.0)  |  "
        f"This work — open-stack reproduction (Pelicun 3 / openquake.hazardlib)  |  {RUN_DATE}",
        fontsize=CAPTION_FS - 0.5, color="#aaaaaa", ha="left", va="bottom",
    )

    plt.subplots_adjust(bottom=0.03, top=0.96, left=0.07, right=0.97)
    fig.savefig(out_path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {out_path}")


# ── Main ──────────────────────────────────────────────────────────────────────
def main() -> None:
    print("Loading data …")
    gdf = load_data()
    epi_gdf = make_epicentre_gdf()
    wvf_gdf = make_fault_gdf(WVF_TRACE_LONLAT)
    evf_gdf = make_fault_gdf(EVF_TRACE_LONLAT)

    n_total = len(gdf)
    n_mc = int((gdf["city"] == "MC").sum())
    n_qc = int((gdf["city"] == "QC").sum())
    mean_loss = gdf["mean_loss_ratio"].mean()

    # Headline = the portfolio MEDIAN loss ratio from the committed summary
    # (consistent with every other reported KPI). The per-building bubbles encode
    # each building's MEAN loss ratio; the across-building mean is collapse-inflated
    # and reported only as a secondary context number.
    summ = json.loads(SUMMARY.read_text())
    median_loss = summ["whole_portfolio"]["loss_ratio"]["median"]
    print(
        f"N={n_total} (MC={n_mc}, QC={n_qc})  "
        f"portfolio median loss={median_loss:.1%}  (across-building mean={mean_loss:.1%})"
    )

    # ── Figure 1: Metro Manila (all schools) ──────────────────────────────────
    print("Rendering metro map …")
    plot_loss_map(
        gdf, epi_gdf, wvf_gdf, evf_gdf,
        city_filter=None,
        buffer_deg=0.012,
        figsize=(9, 8),
        title=(
            f"WVF Mw 7.3 — Seismic Loss, Metro Manila Public Schools\n"
            f"Makati City & Quezon City  |  N = {n_total:,}  |  "
            f"Portfolio median loss = {median_loss:.0%}  (per-building mean shown)"
        ),
        out_path=IMAGES / "wvf73_loss_map_metro.png",
        show_evf=False,
        show_city_labels=True,
    )

    print("Done.")


if __name__ == "__main__":
    main()
