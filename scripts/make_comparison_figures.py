"""
WVF Mw 7.3 — Publication-quality Figure Suite (P7 Validation Track)
====================================================================
Generates the two committed thesis-vs-ours comparison figures:

  images/wvf73_original_vs_ours.png — 4-panel head-to-head (this work vs 2021 Thesis)
  images/wvf73_summary_table.png    — headline comparison table

Run from repo root:
    .venv/bin/python scripts/make_comparison_figures.py

Data dependencies (all gitignored — read-only at runtime):
    sandbox/portfolio-analysis/wvf73_arrays.npz
    sandbox/thesis-data/Portfolio_Analysis_Script/WVF_7_3_PA.mat
    bayanihan/data/inventory/manila_schools_real.geojson
    bayanihan/data/results/wvf73_portfolio_summary.json

References
----------
Jeswani, K. K. (2021). The Seismic Resilience of Critical Spatially-Distributed
    Building Portfolios. MASc thesis, University of Toronto.
Jeswani et al. (2022). Seismic risk assessment and
    mitigation analysis of large public school building portfolios in Metro Manila.
    Earthquake Spectra, 38(3), 1946–1971. https://doi.org/10.1177/87552930221086304
"""

from __future__ import annotations

import json
from pathlib import Path

import geopandas as gpd
import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import scipy.io

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
REPO = Path(__file__).resolve().parent.parent
NPZ_PATH  = REPO / "sandbox/portfolio-analysis/wvf73_arrays.npz"
MAT_PATH  = REPO / "sandbox/thesis-data/Portfolio_Analysis_Script/WVF_7_3_PA.mat"
INV_PATH  = REPO / "bayanihan/data/inventory/manila_schools_real.geojson"
JSON_PATH = REPO / "bayanihan/data/results/wvf73_portfolio_summary.json"
OUT_DIR   = REPO / "images"
OUT_DIR.mkdir(exist_ok=True)

# ---------------------------------------------------------------------------
# Palette
# ---------------------------------------------------------------------------
C_BLUE   = "#1D4ED8"   # this work (primary)
C_RED    = "#DC2626"   # thesis / mitigated contrast
C_GREEN  = "#16A34A"   # QC or secondary
C_ORANGE = "#D97706"   # Makati
C_PURPLE = "#7C3AED"   # fatalities
C_GRAY   = "#6B7280"
C_LG     = "#E5E7EB"
C_DARK   = "#111827"
C_BG     = "#F8FAFC"

mpl.rcParams.update({
    "font.family":      "DejaVu Sans",
    "font.size":        9,
    "axes.titlesize":   10,
    "axes.titleweight": "bold",
    "axes.titlepad":    6,
    "axes.labelsize":   9,
    "axes.spines.top":  False,
    "axes.spines.right": False,
    "axes.grid":        True,
    "grid.color":       C_LG,
    "grid.linewidth":   0.5,
    "grid.alpha":       0.8,
    "legend.fontsize":  8,
    "legend.framealpha": 0.92,
    "legend.edgecolor": C_LG,
    "xtick.labelsize":  8,
    "ytick.labelsize":  8,
    "figure.facecolor": "white",
    "axes.facecolor":   C_BG,
    "figure.dpi":       120,
    "savefig.dpi":      200,
    "savefig.bbox":     "tight",
    "savefig.facecolor": "white",
})

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def ecdf_xy(arr: np.ndarray):
    """Return (sorted_x, cdf_y) — P(X ≤ x)."""
    s = np.sort(arr)
    n = len(s)
    y = np.arange(1, n + 1) / n
    return s, y


def fmt_B(x: float, _=None) -> str:
    """Format billions as '₱7.8B'."""
    return f"₱{x:.1f}B"


def fmt_k(x: float, _=None) -> str:
    """Format thousands."""
    if x >= 1000:
        return f"{x/1000:.0f}k"
    return f"{x:.0f}"


def annotate_median(ax, val, color, y_frac=0.55, prefix="", fmt=".1f", units=""):
    """Draw a vertical dashed line with a text label."""
    ax.axvline(val, color=color, ls="--", lw=1.2, alpha=0.8)
    ax.text(val, y_frac, f"{prefix}{val:{fmt}}{units}",
            color=color, fontsize=7.5, ha="left", va="center",
            bbox=dict(fc="white", ec="none", alpha=0.8, pad=1))


# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------
print("Loading data …")

npz = np.load(NPZ_PATH, allow_pickle=True)
loss_php_all    = npz["portfolio_loss_php"]          # (1000,) whole portfolio
loss_ratio_all  = npz["portfolio_loss_ratio"]         # (1000,)
per_bldg_lratio = npz["loss_ratio"]                   # (1021, 1000)
per_bldg_lphp   = npz["loss_php"]                     # (1021, 1000)
per_bldg_func   = npz["functional_recovery_days"]     # (1021, 1000)
collapse_mask   = npz["collapse_mask"]                # (1021, 1000) bool
city_arr        = npz["city"]                         # (1021,) 'MC'/'QC'
bid_arr         = npz["building_id"]                  # (1021,)

mc_mask = city_arr == "MC"   # 96 buildings
qc_mask = city_arr == "QC"   # 925 buildings

with open(JSON_PATH) as f:
    summ = json.load(f)

total_repl  = summ["total_replacement_cost_php"]      # ₱30.64B
pop_total   = summ["whole_portfolio"]["casualties"]["population"]  # 560,283
per_arch_lr = summ["per_archetype_loss_ratio"]
rc          = summ["recovery_curve_functional"]
rc_days     = np.array(rc["days"])                    # 0–1525 d, 120 pts
rc_frac     = np.array(rc["fraction_recovered"])      # 0.006 → 0.99

inv = gpd.read_file(INV_PATH)
arch_pop = inv.groupby("archetype")["population"].sum()
mc_repl  = inv.loc[mc_mask, "replacement_cost_php"].sum()
qc_repl  = inv.loc[qc_mask, "replacement_cost_php"].sum()
mc_pop   = inv.loc[mc_mask, "population"].sum()
qc_pop   = inv.loc[qc_mask, "population"].sum()

mat       = scipy.io.loadmat(str(MAT_PATH))
m_loss    = mat["PA_Loss"].flatten()                  # (1000,) ₱
m_inj     = mat["PA_CasI"].flatten()                  # (1000,)
m_fat     = mat["PA_CasF"].flatten()                  # (1000,)
# Recovery curve (2021 Thesis): 100-percentile x sorted functional recovery days
m_func_d  = mat["PA_Rtime_m"][:, 1]                  # (100,) sorted func days
m_func_p  = np.arange(1, 101) / 100.0                # CDF percentile fractions
m_arch_nm = [x[0] for x in mat["Arch_simp"].flatten()]
m_arch_lr = mat["Arch_simp_norm_Loss"].flatten()      # 14 normalized loss ratios
m_arch_ci = mat["Arch_simp_norm_CasI"].flatten()
m_arch_cf = mat["Arch_simp_norm_CasF"].flatten()

# Portfolio losses by city
mc_loss_php = per_bldg_lphp[mc_mask, :].sum(axis=0)   # (1000,)
qc_loss_php = per_bldg_lphp[qc_mask, :].sum(axis=0)   # (1000,)

# Reconstruct per-realization injury / fatality distributions
# (not in NPZ; fit log-normal to the summary percentiles)
rng = np.random.default_rng(42)
def lognorm_samples(p50, p16, p84, n=1000):
    ln_mu  = np.log(p50)
    ln_sig = (np.log(p84) - np.log(p16)) / 2.0
    return np.exp(rng.normal(ln_mu, ln_sig, n))

inj_ours = lognorm_samples(
    summ["whole_portfolio"]["casualties"]["injuries"]["count"]["p50"],
    summ["whole_portfolio"]["casualties"]["injuries"]["count"]["p16"],
    summ["whole_portfolio"]["casualties"]["injuries"]["count"]["p84"],
)
fat_ours = lognorm_samples(
    summ["whole_portfolio"]["casualties"]["fatalities"]["count"]["p50"],
    summ["whole_portfolio"]["casualties"]["fatalities"]["count"]["p16"],
    summ["whole_portfolio"]["casualties"]["fatalities"]["count"]["p84"],
)

# Per-archetype mean functional days (for disruption row)
ARCH_ORDER = list(per_arch_lr.keys())  # 14 archetypes
def arch_bldg_idx(arch):
    arch_bids = set(inv.loc[inv["archetype"] == arch, "building_id"].values)
    return np.array([i for i, b in enumerate(bid_arr) if b in arch_bids])

arch_func_mean = {
    arch: per_bldg_func[arch_bldg_idx(arch), :].mean()
    for arch in ARCH_ORDER
}
arch_disruption_Msd = {   # millions of student-days
    arch: arch_func_mean[arch] * arch_pop.get(arch, 0) / 1e6
    for arch in ARCH_ORDER
}

# Recovery targets from JSON
r90 = summ["recovery_90pct_functional_days"]
mc_fr90_ours   = r90["makati_MC"]["functional_recovery"]["median"]
qc_fr90_ours   = r90["quezon_QC"]["functional_recovery"]["median"]
all_fr90_ours  = r90["whole_portfolio"]["functional_recovery"]["median"]
mc_fr90_thesis = r90["thesis_targets_WVF73"]["makati_MC"]["functional_recovery_median_days"]
qc_fr90_thesis = r90["thesis_targets_WVF73"]["quezon_QC"]["functional_recovery_median_days"]

# ======================================================================
# FIGURE 1 — 4×2 DV Grid (OUR results)
# ======================================================================
print("Building Figure 1: DV grid …")

SHORT = [a.replace(" (", "\n(") for a in ARCH_ORDER]

fig1, axes = plt.subplots(4, 2, figsize=(14, 18))
fig1.patch.set_facecolor("white")
fig1.suptitle(
    "WVF Mw 7.3 — Portfolio Decision Variable Grid\n"
    "Open-stack Reproduction: Pelicun 3 + openquake.hazardlib",
    fontsize=13, fontweight="bold", y=0.99,
)

# ── Row 0: Losses ──────────────────────────────────────────────────────
ax = axes[0, 0]
x_all, c_all = ecdf_xy(loss_php_all / 1e9)
x_mc,  c_mc  = ecdf_xy(mc_loss_php / 1e9)
x_qc,  c_qc  = ecdf_xy(qc_loss_php / 1e9)
ax.plot(x_all, c_all, color=C_BLUE,   lw=2,   label=f"Whole  (N=1,021, med=₱{np.median(loss_php_all)/1e9:.1f}B)")
ax.plot(x_mc,  c_mc,  color=C_ORANGE, lw=1.5, ls="--", label=f"Makati (N=96,   med=₱{np.median(mc_loss_php)/1e9:.1f}B)")
ax.plot(x_qc,  c_qc,  color=C_GREEN,  lw=1.5, ls=":",  label=f"QC     (N=925,  med=₱{np.median(qc_loss_php)/1e9:.1f}B)")
for val, col in [(np.median(loss_php_all)/1e9, C_BLUE),
                 (np.percentile(loss_php_all, 90)/1e9, C_BLUE)]:
    ax.axvline(val, color=col, ls=":", lw=0.8, alpha=0.6)
ax.set_xlabel("Portfolio Loss (₱ billions)")
ax.set_ylabel("Cumulative Probability P(Loss ≤ x)")
ax.set_title("Losses — CDF")
ax.legend(fontsize=7.5)
ax.set_xlim(left=0)
ax.set_ylim(0, 1)

ax = axes[0, 1]
arch_lr_vals = [per_arch_lr[a]["mean_loss_ratio"] for a in ARCH_ORDER]
arch_n_vals  = [per_arch_lr[a]["n_buildings"] for a in ARCH_ORDER]
y_pos = np.arange(len(ARCH_ORDER))
bar_colors = [C_RED if v > 0.65 else (C_ORANGE if v > 0.4 else C_BLUE) for v in arch_lr_vals]
bars = ax.barh(y_pos, arch_lr_vals, color=bar_colors, edgecolor="white", height=0.7, zorder=3)
for y, n, v in zip(y_pos, arch_n_vals, arch_lr_vals):
    ax.text(v + 0.015, y, f"n={n}", va="center", ha="left", fontsize=7, color=C_GRAY)
ax.set_yticks(y_pos)
ax.set_yticklabels(SHORT, fontsize=7.5)
ax.set_xlabel("Mean Loss Ratio (₱ loss / ₱ replacement)")
ax.set_title("Losses — Per-Archetype Mean")
ax.set_xlim(0, 1.15)
ax.invert_yaxis()
ax.axvline(np.median(loss_ratio_all), color=C_BLUE, ls="--", lw=1, alpha=0.7,
           label=f"Portfolio median {np.median(loss_ratio_all):.2f}")
ax.legend(fontsize=7.5)

# ── Row 1: Injuries ────────────────────────────────────────────────────
ax = axes[1, 0]
x_inj, c_inj = ecdf_xy(inj_ours / 1e3)
ax.plot(x_inj, c_inj, color=C_BLUE, lw=2,
        label=f"Whole — log-normal fit\n(med={summ['whole_portfolio']['casualties']['injuries']['count']['p50']/1e3:.0f}k, "
              f"p90={summ['whole_portfolio']['casualties']['injuries']['count']['p90']/1e3:.0f}k)")
ax.axvline(summ["whole_portfolio"]["casualties"]["injuries"]["count"]["p50"] / 1e3,
           color=C_BLUE, ls="--", lw=1, alpha=0.7)
ax.axvline(summ["whole_portfolio"]["casualties"]["injuries"]["count"]["p90"] / 1e3,
           color=C_ORANGE, ls=":", lw=1, alpha=0.7, label="P90")
ax.set_xlabel("Injuries (thousands)")
ax.set_ylabel("Cumulative Probability")
ax.set_title("Injuries — CDF")
ax.set_ylim(0, 1)
ax.legend(fontsize=7.5)

ax = axes[1, 1]
arch_ci_vals = [per_arch_lr[a]["mean_injury_rate"] for a in ARCH_ORDER]
bar_colors_i = [C_RED if v > 0.18 else (C_ORANGE if v > 0.10 else C_BLUE) for v in arch_ci_vals]
ax.barh(y_pos, arch_ci_vals, color=bar_colors_i, edgecolor="white", height=0.7, zorder=3)
for y, n, v in zip(y_pos, arch_n_vals, arch_ci_vals):
    ax.text(v + 0.003, y, f"n={n}", va="center", ha="left", fontsize=7, color=C_GRAY)
ax.set_yticks(y_pos)
ax.set_yticklabels(SHORT, fontsize=7.5)
ax.set_xlabel("Mean Injury Rate (injuries / building occupancy)")
ax.set_title("Injuries — Per-Archetype Mean")
ax.invert_yaxis()

# ── Row 2: Fatalities ──────────────────────────────────────────────────
ax = axes[2, 0]
x_fat, c_fat = ecdf_xy(fat_ours)
ax.plot(x_fat, c_fat, color=C_PURPLE, lw=2,
        label=f"Whole — log-normal fit\n(med={summ['whole_portfolio']['casualties']['fatalities']['count']['p50']:.0f}, "
              f"p90={summ['whole_portfolio']['casualties']['fatalities']['count']['p90']:.0f})")
ax.axvline(summ["whole_portfolio"]["casualties"]["fatalities"]["count"]["p50"],
           color=C_PURPLE, ls="--", lw=1, alpha=0.7)
ax.axvline(summ["whole_portfolio"]["casualties"]["fatalities"]["count"]["p90"],
           color=C_ORANGE, ls=":", lw=1, alpha=0.7, label="P90")
ax.set_xlabel("Fatalities (count)")
ax.set_ylabel("Cumulative Probability")
ax.set_title("Fatalities — CDF")
ax.set_ylim(0, 1)
ax.legend(fontsize=7.5)

ax = axes[2, 1]
arch_cf_vals = [per_arch_lr[a]["mean_fatality_rate"] for a in ARCH_ORDER]
bar_colors_f = [C_RED if v > 0.015 else (C_ORANGE if v > 0.005 else C_PURPLE) for v in arch_cf_vals]
ax.barh(y_pos, arch_cf_vals, color=bar_colors_f, edgecolor="white", height=0.7, zorder=3)
for y, n, v in zip(y_pos, arch_n_vals, arch_cf_vals):
    ax.text(v + 0.0005, y, f"n={n}", va="center", ha="left", fontsize=7, color=C_GRAY)
ax.set_yticks(y_pos)
ax.set_yticklabels(SHORT, fontsize=7.5)
ax.set_xlabel("Mean Fatality Rate (fatalities / building occupancy)")
ax.set_title("Fatalities — Per-Archetype Mean")
ax.invert_yaxis()

# ── Row 3: Disruption (student-days) ───────────────────────────────────
ax = axes[3, 0]
func_per_real     = per_bldg_func.mean(axis=0)  # mean building days per realization
mc_func_per_real  = per_bldg_func[mc_mask, :].mean(axis=0)
qc_func_per_real  = per_bldg_func[qc_mask, :].mean(axis=0)

sd_all = pop_total * func_per_real
sd_mc  = mc_pop   * mc_func_per_real
sd_qc  = qc_pop   * qc_func_per_real

x_sd,   c_sd   = ecdf_xy(sd_all / 1e6)
x_sdmc, c_sdmc = ecdf_xy(sd_mc  / 1e6)
x_sdqc, c_sdqc = ecdf_xy(sd_qc  / 1e6)
ax.plot(x_sd,   c_sd,   color=C_BLUE,   lw=2,   label=f"Whole  (med={np.median(sd_all)/1e6:.0f}M)")
ax.plot(x_sdmc, c_sdmc, color=C_ORANGE, lw=1.5, ls="--", label=f"Makati (med={np.median(sd_mc)/1e6:.0f}M)")
ax.plot(x_sdqc, c_sdqc, color=C_GREEN,  lw=1.5, ls=":",  label=f"QC     (med={np.median(sd_qc)/1e6:.0f}M)")
ax.set_xlabel("Disruption (millions of student-days lost)")
ax.set_ylabel("Cumulative Probability")
ax.set_title("Disruption (Functional Recovery) — CDF")
ax.set_ylim(0, 1)
ax.legend(fontsize=7.5)

ax = axes[3, 1]
dis_vals = [arch_disruption_Msd[a] for a in ARCH_ORDER]
bar_colors_d = [C_RED if v > 5 else (C_ORANGE if v > 1 else C_BLUE) for v in dis_vals]
ax.barh(y_pos, dis_vals, color=bar_colors_d, edgecolor="white", height=0.7, zorder=3)
for y, n, v in zip(y_pos, arch_n_vals, dis_vals):
    ax.text(v + 0.2, y, f"n={n}", va="center", ha="left", fontsize=7, color=C_GRAY)
ax.set_yticks(y_pos)
ax.set_yticklabels(SHORT, fontsize=7.5)
ax.set_xlabel("Disruption (millions of student-days)")
ax.set_title("Disruption — Per-Archetype")
ax.invert_yaxis()

# ── Shared label and caption ────────────────────────────────────────────
caption1 = (
    "WVF Mw 7.3 scenario, N=1,000 realizations, 1,021 public school buildings "
    "(96 Makati, 925 Quezon City), population=560,283 students.  "
    "Injury/fatality CDFs approximated from log-normal fit to distribution statistics "
    "(per-realization arrays not stored in NPZ).  "
    "This work — open-stack reproduction (Pelicun 3 / openquake.hazardlib)."
)
fig1.text(0.5, -0.005, caption1, ha="center", fontsize=7, color=C_GRAY,
          wrap=True, transform=fig1.transFigure)

# The standalone 4×2 DV grid was retired — redundant with the Figure 2
# head-to-head comparison below — so it is built for reference but no
# longer saved or committed.
plt.close(fig1)

# ======================================================================
# FIGURE 2 — Head-to-head: 2021 Thesis vs. This Work
# ======================================================================
print("Building Figure 2: Original vs. Ours …")

fig2, axes2 = plt.subplots(2, 2, figsize=(13, 11))
fig2.patch.set_facecolor("white")
fig2.suptitle(
    "WVF Mw 7.3 — 2021 Thesis vs. This Work (Pelicun 3 / openquake.hazardlib)\n"
    "Head-to-Head Comparison, N=1,000 Realizations",
    fontsize=13, fontweight="bold", y=0.99,
)

# ── 2a: Loss CDF ────────────────────────────────────────────────────────
ax = axes2[0, 0]
x_ours_l, c_ours_l = ecdf_xy(loss_php_all / 1e9)
x_orig_l, c_orig_l = ecdf_xy(m_loss / 1e9)

ax.plot(x_ours_l, c_ours_l, color=C_BLUE,   lw=2.2, label=f"This work  (med=₱{np.median(loss_php_all)/1e9:.1f}B)")
ax.plot(x_orig_l, c_orig_l, color=C_RED,    lw=2.2, ls="--", label=f"2021 Thesis (med=₱{np.median(m_loss)/1e9:.1f}B)")

for val, col in [(np.median(loss_php_all) / 1e9, C_BLUE),
                 (np.median(m_loss) / 1e9, C_RED)]:
    ax.axvline(val, color=col, ls=":", lw=1.2, alpha=0.7)

delta_loss = (np.median(loss_php_all) - np.median(m_loss)) / np.median(m_loss) * 100
ax.text(0.97, 0.05,
        f"Δ median: {delta_loss:+.0f}%",
        ha="right", va="bottom", fontsize=9, transform=ax.transAxes,
        color=C_BLUE if delta_loss > 0 else C_RED,
        bbox=dict(boxstyle="round,pad=0.3", fc="white", ec=C_LG))

ax.set_xlabel("Portfolio Loss (₱ billions)")
ax.set_ylabel("Cumulative Probability P(Loss ≤ x)")
ax.set_title("(a) Portfolio Loss — CDF")
ax.legend()
ax.set_xlim(left=0)
ax.set_ylim(0, 1)

# ── 2b: Casualties CDF ──────────────────────────────────────────────────
ax = axes2[0, 1]
x_io, c_io = ecdf_xy(inj_ours / 1e3)
x_im, c_im = ecdf_xy(m_inj   / 1e3)
x_fo, c_fo = ecdf_xy(fat_ours)
x_fm, c_fm = ecdf_xy(m_fat)

ax.plot(x_io, c_io, color=C_BLUE,   lw=2.2, label=f"Injuries — This work (med={np.median(inj_ours)/1e3:.0f}k)")
ax.plot(x_im, c_im, color=C_RED,    lw=2.2, ls="--", label=f"Injuries — Thesis   (med={np.median(m_inj)/1e3:.0f}k)")

# Secondary twin-x for fatalities
ax2b = ax.twiny()
ax2b.set_xlim(0, ax.get_xlim()[1] / 20)   # fatalities scale ~1/20 of injuries
ax2b.xaxis.set_visible(False)

ax.plot([], [], color=C_PURPLE, lw=1.5, label=f"Fatalities — This work (med={np.median(fat_ours):.0f})", zorder=10)
ax.plot([], [], color=C_GREEN,  lw=1.5, ls="--", label=f"Fatalities — Thesis  (med={np.median(m_fat):.0f})", zorder=10)
# Plot fatalities on primary axis (scaled to same 0-1 CDF y-axis)
ax.plot(x_fo / 1000, c_fo, color=C_PURPLE, lw=1.5)   # show on same axis, scaled
ax.plot(x_fm / 1000, c_fm, color=C_GREEN,  lw=1.5, ls="--")

# Inset note
ax.text(0.97, 0.05,
        "Fatalities shown at 1/1000 scale on x-axis",
        ha="right", va="bottom", fontsize=7, transform=ax.transAxes, color=C_GRAY)

ax.set_xlabel("Injuries (thousands)  |  Fatalities (÷1000, same axis)")
ax.set_ylabel("Cumulative Probability")
ax.set_title("(b) Casualties — Injuries & Fatalities CDF")
ax.legend(fontsize=7.5)
ax.set_xlim(left=0)
ax.set_ylim(0, 1)

# ── 2c: Functional Recovery Curve ───────────────────────────────────────
ax = axes2[1, 0]

# Ours: fraction-recovered CDF vs days (from JSON summary)
ax.plot(rc_days, rc_frac, color=C_BLUE, lw=2.2,
        label="This work (Pelicun/OQ)")

# 2021 Thesis: empirical CDF of per-building functional recovery times
# PA_Rtime_m[:,1] = sorted functional recovery days for percentile 1..100
ax.plot(m_func_d, m_func_p, color=C_RED, lw=2.2, ls="--",
        label="2021 Thesis")

# Annotate 90% FR milestones from JSON
ax.axhline(0.9, color=C_GRAY, ls=":", lw=0.8, alpha=0.6)
ax.axvline(qc_fr90_ours, color=C_BLUE, ls=":", lw=1.2, alpha=0.8)
ax.axvline(qc_fr90_thesis, color=C_RED, ls=":", lw=1.2, alpha=0.8)
ax.text(qc_fr90_ours   + 15, 0.62, f"QC 90%-FR\n{qc_fr90_ours:.0f} d\n(this work)",
        color=C_BLUE, fontsize=7.5, va="center")
ax.text(qc_fr90_thesis + 15, 0.72, f"QC 90%-FR\n{qc_fr90_thesis:.0f} d\n(thesis)",
        color=C_RED, fontsize=7.5, va="center")

ax.set_xlabel("Days after Earthquake")
ax.set_ylabel("Fraction of Portfolio Functionally Recovered")
ax.set_title("(c) Functional Recovery Curve — Whole Portfolio")
ax.set_ylim(0, 1.02)
ax.set_xlim(0, 1700)
ax.legend()
ax.grid(True, which="both", linestyle=":", alpha=0.5)

# ── 2d: Per-archetype loss-ratio grouped bars ────────────────────────────
ax = axes2[1, 1]
ours_lr = [per_arch_lr.get(a, {}).get("mean_loss_ratio", 0) for a in ARCH_ORDER]
orig_lr = dict(zip(m_arch_nm, m_arch_lr))
orig_lr_vals = [orig_lr.get(a, 0) for a in ARCH_ORDER]

y_pos2 = np.arange(len(ARCH_ORDER))
bw = 0.36
ax.barh(y_pos2 - bw / 2, ours_lr_v := ours_lr,    bw, color=C_BLUE, alpha=0.85,
        label="This work", edgecolor="white", zorder=3)
ax.barh(y_pos2 + bw / 2, orig_lr_vals, bw, color=C_RED, alpha=0.80,
        label="2021 Thesis", edgecolor="white", zorder=3)

ax.set_yticks(y_pos2)
ax.set_yticklabels(SHORT, fontsize=7.5)
ax.set_xlabel("Mean Loss Ratio")
ax.set_title("(d) Per-Archetype Mean Loss Ratio")
ax.set_xlim(0, 1.1)
ax.invert_yaxis()
ax.legend()

caption2 = (
    "Note: Injuries/fatalities (this work) approximated from log-normal fit to distribution statistics; "
    "per-realization casualty arrays not stored in NPZ.  "
    "Documented residuals: collapse-distribution tail heavier in this work → higher casualties.  "
    f"Recovery gap: this work 90%-FR (QC) {qc_fr90_ours:.0f} d vs thesis {qc_fr90_thesis:.0f} d ({(qc_fr90_ours - qc_fr90_thesis) / qc_fr90_thesis * 100:+.0f}%).  "
    "This work — open-stack reproduction (Pelicun 3 / openquake.hazardlib)."
)

fig2.text(0.5, -0.01, caption2, ha="center", fontsize=7, color=C_GRAY,
          wrap=True, transform=fig2.transFigure)

fig2.tight_layout(rect=[0, 0.02, 1, 0.98], h_pad=3, w_pad=3)
out2 = OUT_DIR / "wvf73_original_vs_ours.png"
fig2.savefig(out2)
print(f"  → {out2}")
plt.close(fig2)

# ======================================================================
# FIGURE 3 — Summary Table
# ======================================================================
print("Building Figure 3: Summary table …")

# Published thesis values
pub_mc_loss_ratio = 0.26  # thesis §7.4 stated ~26% median for Makati

mc_lr_ours = summ["makati_MC"]["loss_ratio"]["median"]
qc_lr_ours = summ["quezon_QC"]["loss_ratio"]["median"]
all_lr_ours = summ["whole_portfolio"]["loss_ratio"]["median"]

inj_med_ours = summ["whole_portfolio"]["casualties"]["injuries"]["count"]["p50"]
inj_p90_ours = summ["whole_portfolio"]["casualties"]["injuries"]["count"]["p90"]
fat_med_ours = summ["whole_portfolio"]["casualties"]["fatalities"]["count"]["p50"]
fat_p90_ours = summ["whole_portfolio"]["casualties"]["fatalities"]["count"]["p90"]

inj_med_mat = np.median(m_inj)
inj_p90_mat = np.percentile(m_inj, 90)
fat_med_mat = np.median(m_fat)
fat_p90_mat = np.percentile(m_fat, 90)

loss_med_mat = np.median(m_loss) / 1e9
loss_p90_mat = np.percentile(m_loss, 90) / 1e9
loss_med_ours = np.median(loss_php_all) / 1e9
loss_p90_ours = np.percentile(loss_php_all, 90) / 1e9

def delta(ours_v, ref_v):
    if ref_v == 0 or ref_v is None:
        return "—"
    return f"{(ours_v - ref_v) / ref_v * 100:+.0f}%"

rows = [
    ("Portfolio Loss (whole) — Median [₱B]",
     "—", f"₱{loss_med_mat:.1f}B", f"₱{loss_med_ours:.1f}B",
     delta(loss_med_ours, loss_med_mat)),

    ("Portfolio Loss (whole) — P90 [₱B]",
     "—", f"₱{loss_p90_mat:.1f}B", f"₱{loss_p90_ours:.1f}B",
     delta(loss_p90_ours, loss_p90_mat)),

    ("Loss Ratio (whole) — Median",
     "—",
     f"{loss_med_mat / (total_repl / 1e9):.2f}",
     f"{all_lr_ours:.2f}",
     delta(all_lr_ours, loss_med_mat / (total_repl / 1e9))),

    ("Loss Ratio (Makati) — Median",
     f"≈{pub_mc_loss_ratio:.0%} (thesis §7.4)",
     "—",
     f"{mc_lr_ours:.2f}",
     delta(mc_lr_ours, pub_mc_loss_ratio)),

    ("Loss Ratio (Quezon City) — Median",
     "—", "—", f"{qc_lr_ours:.2f}", "—"),

    ("Injuries — Median [count]",
     "—", f"{inj_med_mat:,.0f}", f"{inj_med_ours:,.0f}",
     delta(inj_med_ours, inj_med_mat)),

    ("Injuries — P90 [count]",
     "—", f"{inj_p90_mat:,.0f}", f"{inj_p90_ours:,.0f}",
     delta(inj_p90_ours, inj_p90_mat)),

    ("Fatalities — Median [count]",
     "—", f"{fat_med_mat:,.0f}", f"{fat_med_ours:,.0f}",
     delta(fat_med_ours, fat_med_mat)),

    ("Fatalities — P90 [count]",
     "—", f"{fat_p90_mat:,.0f}", f"{fat_p90_ours:,.0f}",
     delta(fat_p90_ours, fat_p90_mat)),

    ("90%-FR (Makati) — Median [days]",
     f"{mc_fr90_thesis:.0f} d (thesis)", "—", f"{mc_fr90_ours:.0f} d",
     delta(mc_fr90_ours, mc_fr90_thesis)),

    ("90%-FR (Quezon City) — Median [days]",
     f"{qc_fr90_thesis:.0f} d (thesis)", "—", f"{qc_fr90_ours:.0f} d",
     delta(qc_fr90_ours, qc_fr90_thesis)),

    ("90%-FR (whole) — Median [days]",
     "—", "—", f"{all_fr90_ours:.0f} d", "—"),
]

col_labels = ["Metric", "Published / Thesis", ".mat (2021 Thesis)", "This Work", "Δ (ours vs. 2021 Thesis)"]

fig3 = plt.figure(figsize=(14, 6.5))
fig3.patch.set_facecolor("white")
ax3 = fig3.add_axes([0, 0, 1, 1])
ax3.axis("off")
fig3.suptitle(
    "WVF Mw 7.3 — Headline Comparison: Published Thesis · .mat (2021 Thesis) · This Work\n"
    "N=1,000 realizations, 1,021 buildings (96 Makati + 925 Quezon City), population=560,283",
    fontsize=12, fontweight="bold", y=0.97,
)

# Layout
COL_X   = [0.01, 0.38, 0.56, 0.68, 0.82]
ROW_H   = 0.065
Y_START = 0.88
N_ROWS  = len(rows) + 1  # +1 for header

# Header
for j, (hdr, cx) in enumerate(zip(col_labels, COL_X)):
    ax3.text(cx + 0.005, Y_START, hdr,
             ha="left", va="center", fontsize=9, fontweight="bold",
             color="white", transform=ax3.transAxes)
ax3.add_patch(mpl.patches.FancyBboxPatch(
    (COL_X[0] - 0.005, Y_START - ROW_H * 0.44), 1.0 - COL_X[0] + 0.004, ROW_H * 0.88,
    boxstyle="square,pad=0", fc=C_DARK, ec="none",
    transform=ax3.transAxes, zorder=0))

# Data rows
for i, row in enumerate(rows):
    y = Y_START - (i + 1) * ROW_H
    bg = "#F0F4FF" if i % 2 == 0 else "white"
    ax3.add_patch(mpl.patches.FancyBboxPatch(
        (COL_X[0] - 0.005, y - ROW_H * 0.44), 1.0 - COL_X[0] + 0.004, ROW_H * 0.88,
        boxstyle="square,pad=0", fc=bg, ec=C_LG, lw=0.4,
        transform=ax3.transAxes, zorder=0))

    for j, (val, cx) in enumerate(zip(row, COL_X)):
        fw = "bold" if j == 0 else "normal"
        color = C_DARK
        if j == 4 and val not in ("—", ""):
            try:
                pct = float(val.rstrip("%").lstrip("+"))
                color = "#DC2626" if abs(pct) > 30 else ("#D97706" if abs(pct) > 15 else "#16A34A")
            except ValueError:
                pass
        ax3.text(cx + 0.005, y, val,
                 ha="left", va="center", fontsize=8.5,
                 fontweight=fw, color=color, transform=ax3.transAxes)

caption3 = (
    "Δ column = (this work − 2021 Thesis) / 2021 Thesis. "
    "Green < 15%, amber 15–30%, red > 30%. "
    "Documented residuals: collapse tail heavier → higher P90 casualties. "
    f"Recovery gap: QC 90%-FR this work = {qc_fr90_ours:.0f} d vs thesis {qc_fr90_thesis:.0f} d. "
    "This work — open-stack reproduction (Pelicun 3 / openquake.hazardlib)."
)
ax3.text(0.5, -0.02, caption3, ha="center", va="bottom", fontsize=8, color=C_GRAY,
         transform=ax3.transAxes)

out3 = OUT_DIR / "wvf73_summary_table.png"
fig3.savefig(out3, bbox_inches="tight", facecolor="white")
print(f"  → {out3}")
plt.close(fig3)

# ======================================================================
print("\nDone:")
print(f"  {out2}")
print(f"  {out3}")
