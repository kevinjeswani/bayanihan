"""WVF Mw 7.3 — Base vs Mitigated comparison figure (P7).

Reproduces the thesis's headline Base-vs-Mitigated layout for the TWO mitigation layers:

  (1) STRUCTURAL FRP retrofit of the non-ductile RCMRF  -> FATALITY reduction
  (2) NON-STRUCTURAL equipment upgrade (Table 6-3)       -> INJURY reduction (headline)

Panels: loss-ratio exceedance curves (Base vs Mitigated) for Makati (MC), Quezon City
(QC) and the whole portfolio; a loss-ratio median bar; a casualty-ratio reduction panel
(injuries + fatalities) with the 2021 Thesis targets marked; and a mitigation-summary box.

  images/wvf73_base_vs_mitigated.png

The thesis series is labelled "2021 Thesis". The thesis mitigated case
combined the structural FRP retrofit of the whole RC-frame stock with portfolio-wide
non-structural upgrades; we reproduce the non-structural layer fully (injury reduction)
and the structural layer for the recovered C1-M (Pre/Lo) EDPs (a fatality-reduction
coverage limit). NOT tuned.

Run from repo root (after 2026-06-27_run_wvf73_mitigated.py):
    .venv/bin/python prototypes/2026-06-27_figure_base_vs_mitigated.py

Data dependencies (gitignored, read-only):
    sandbox/portfolio-analysis/wvf73_base_arrays_for_mit.npz
    sandbox/portfolio-analysis/wvf73_mitigated_arrays.npz
    bayanihan/data/results/wvf73_base_vs_mitigated.json
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np

REPO = Path(__file__).resolve().parent.parent
BASE_NPZ = REPO / "sandbox/portfolio-analysis/wvf73_base_arrays_for_mit.npz"
MIT_NPZ = REPO / "sandbox/portfolio-analysis/wvf73_mitigated_arrays.npz"
CMP_JSON = REPO / "bayanihan/data/results/wvf73_base_vs_mitigated.json"
OUT = REPO / "images" / "wvf73_base_vs_mitigated.png"

C_BASE = "#DC2626"   # red = base (existing) — matches thesis convention
C_MIT = "#16A34A"    # green = mitigated (both layers)
C_THESIS = "#1D4ED8"  # blue = 2021 Thesis target markers
C_GRAY = "#6B7280"

mpl.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 11,
    "axes.titlesize": 12,
    "axes.titleweight": "bold",
    "axes.labelsize": 11,
    "axes.grid": True,
    "grid.alpha": 0.25,
    "figure.dpi": 130,
})


def _exceedance(x):
    """Return (sorted values, P[X >= x]) for a complementary CDF (exceedance) curve."""
    xs = np.sort(np.asarray(x, dtype=float))
    n = xs.size
    poe = (n - np.arange(n)) / n
    return xs, poe


def main() -> None:
    base = np.load(BASE_NPZ, allow_pickle=True)
    mit = np.load(MIT_NPZ, allow_pickle=True)
    cmp = json.loads(CMP_JSON.read_text())

    city = base["city"].astype(str)
    mc = city == "MC"
    qc = city == "QC"
    whole = np.ones(city.size, dtype=bool)

    cov = cmp["coverage"]
    repl_tot = {
        "MC": cov["makati_MC"]["replacement_cost_php"],
        "QC": cov["quezon_QC"]["replacement_cost_php"],
        "whole": cov["whole"]["replacement_cost_php"],
    }

    def city_lr(arrs, mask, key):
        lp = arrs["loss_php"][mask].sum(axis=0)
        return lp / repl_tot[key]

    # thesis loss-ratio targets (Makati base/mit, QC base) from the 2021 thesis text
    th = cmp["thesis_targets"]
    series = {
        "Makati (MC)": (city_lr(base, mc, "MC"), city_lr(mit, mc, "MC"),
                        th["MC"]["base_loss_ratio"], th["MC"]["mit_loss_ratio"]),
        "Quezon City (QC)": (city_lr(base, qc, "QC"), city_lr(mit, qc, "QC"),
                             th["QC"]["base_loss_ratio"], None),
        "Whole portfolio": (city_lr(base, whole, "whole"), city_lr(mit, whole, "whole"),
                            None, None),
    }

    fig = plt.figure(figsize=(15, 9))
    gs = fig.add_gridspec(2, 3, height_ratios=[1.0, 0.9], hspace=0.36, wspace=0.27)

    # ---- Row 1: loss-ratio exceedance curves (Base vs Mitigated) ----------
    for col, (title, (b, m, th_b, th_m)) in enumerate(series.items()):
        ax = fig.add_subplot(gs[0, col])
        xb, pb = _exceedance(b)
        xm, pm = _exceedance(m)
        ax.plot(xb, pb, color=C_BASE, lw=2.6, label="Base (existing)")
        ax.plot(xm, pm, color=C_MIT, lw=2.6, label="Mitigated (both layers)")
        ax.axvline(np.median(b), color=C_BASE, ls=":", lw=1.3, alpha=0.8)
        ax.axvline(np.median(m), color=C_MIT, ls=":", lw=1.3, alpha=0.8)
        if th_b is not None:
            ax.plot(th_b, 0.5, "o", color=C_THESIS, ms=8, mfc="white", mew=2,
                    label=f"2021 Thesis base ({th_b:.2f})", zorder=5)
        if th_m is not None:
            ax.plot(th_m, 0.5, "s", color=C_THESIS, ms=8, mfc="white", mew=2,
                    label=f"2021 Thesis mit. ({th_m:.2f})", zorder=5)
        ax.axhline(0.5, color=C_GRAY, lw=0.8, alpha=0.5)
        ax.set_title(title)
        ax.set_xlabel("Portfolio loss ratio")
        ax.set_ylabel("Probability of exceedance" if col == 0 else "")
        ax.set_xlim(0, max(0.8, np.percentile(b, 98) * 1.02))
        ax.set_ylim(0, 1)
        ax.legend(fontsize=8.0, loc="upper right", framealpha=0.92)
        ax.text(0.02, 0.06,
                f"median  base {np.median(b):.3f}\n        mit  {np.median(m):.3f}\n"
                f"reduction {100*(np.median(b)-np.median(m))/max(np.median(b),1e-9):.0f}%",
                transform=ax.transAxes, fontsize=8.2, va="bottom",
                bbox=dict(boxstyle="round,pad=0.3", fc="#F3F4F6", ec=C_GRAY, alpha=0.9))

    # ---- Row 2 panel A: loss-ratio median bar (base vs mit, 3 subsets + thesis) ----
    axL = fig.add_subplot(gs[1, 0])
    labels = ["Makati", "QC", "Whole"]
    base_med = [np.median(series["Makati (MC)"][0]), np.median(series["Quezon City (QC)"][0]),
                np.median(series["Whole portfolio"][0])]
    mit_med = [np.median(series["Makati (MC)"][1]), np.median(series["Quezon City (QC)"][1]),
               np.median(series["Whole portfolio"][1])]
    x = np.arange(len(labels)); w = 0.38
    axL.bar(x - w/2, base_med, w, color=C_BASE, label="Base")
    axL.bar(x + w/2, mit_med, w, color=C_MIT, label="Mitigated")
    # 2021 Thesis anchors (Makati base/mit, QC base) as ticks
    axL.plot([0 - w/2], [0.26], "_", color=C_THESIS, ms=18, mew=2.5)
    axL.plot([0 + w/2], [0.18], "_", color=C_THESIS, ms=18, mew=2.5)
    axL.plot([1 - w/2], [0.31], "_", color=C_THESIS, ms=18, mew=2.5,
             label="2021 Thesis median")
    for xi, (bm, mm) in enumerate(zip(base_med, mit_med)):
        axL.text(xi - w/2, bm + 0.008, f"{bm:.2f}", ha="center", fontsize=8)
        axL.text(xi + w/2, mm + 0.008, f"{mm:.2f}", ha="center", fontsize=8)
    axL.set_xticks(x); axL.set_xticklabels(labels)
    axL.set_ylabel("Loss ratio (median)")
    axL.set_title("Loss ratio: base vs mitigated")
    axL.legend(fontsize=8.5, loc="upper left")
    axL.set_ylim(0, max(base_med) * 1.28)

    # ---- Row 2 panel B: casualty-ratio reduction (Makati + QC), with 2021 Thesis ----
    axC = fig.add_subplot(gs[1, 1])
    cas_lab = ["MC inj", "MC fat", "QC inj", "QC fat"]
    cb = [cmp["base"]["makati_MC"]["injury_ratio_median"],
          cmp["base"]["makati_MC"]["fatality_ratio_median"],
          cmp["base"]["quezon_QC"]["injury_ratio_median"],
          cmp["base"]["quezon_QC"]["fatality_ratio_median"]]
    cm = [cmp["mitigated"]["makati_MC"]["injury_ratio_median"],
          cmp["mitigated"]["makati_MC"]["fatality_ratio_median"],
          cmp["mitigated"]["quezon_QC"]["injury_ratio_median"],
          cmp["mitigated"]["quezon_QC"]["fatality_ratio_median"]]
    # 2021 Thesis mitigated casualty-ratio targets (text-sourced).
    th_mit = [th["MC"]["mit_injury_ratio"], th["MC"]["mit_fatality_ratio"],
              th["QC"]["mit_injury_ratio"], th["QC"]["mit_fatality_ratio"]]
    th_base = [th["MC"]["base_injury_ratio"], th["MC"]["base_fatality_ratio"], None, None]
    xc = np.arange(len(cas_lab))
    axC.bar(xc - w/2, cb, w, color=C_BASE, label="Base")
    axC.bar(xc + w/2, cm, w, color=C_MIT, label="Mitigated")
    for xi, tv in enumerate(th_mit):
        if tv:
            axC.plot([xi + w/2], [tv], "v", color=C_THESIS, ms=8, mew=1.5, mfc="white",
                     zorder=5, label="2021 Thesis mit." if xi == 0 else None)
    for xi, tv in enumerate(th_base):
        if tv:
            axC.plot([xi - w/2], [tv], "^", color=C_THESIS, ms=8, mew=1.5, mfc="white",
                     zorder=5, label="2021 Thesis base" if xi == 0 else None)
    axC.set_yscale("log")
    axC.set_xticks(xc); axC.set_xticklabels(cas_lab, fontsize=9)
    axC.set_ylabel("Casualty ratio (median, log)")
    axC.set_title("Casualty ratios: base vs mitigated")
    axC.legend(fontsize=7.6, loc="lower left", ncol=2)

    # ---- Row 2 panel C: two-layer mitigation summary -----------------------
    axT = fig.add_subplot(gs[1, 2]); axT.axis("off")
    r = cmp["reduction_ours"]
    w_cov = cov["whole"]; mc_cov = cov["makati_MC"]
    mc_inj_red = 100 * (r.get("makati_injuries_median") or 0)
    whole_inj_red = 100 * (r.get("whole_injuries_median") or 0)
    txt = (
        "MITIGATION = TWO simultaneous layers\n\n"
        "(1) STRUCTURAL FRP retrofit of non-ductile RCMRF\n"
        "    -> collapse risk down -> FATALITY reduction.\n"
        f"    Reproducible: C1-M (Pre/Lo) only — {w_cov['n_retrofitted']}/"
        f"{w_cov['n_buildings']} bldgs\n"
        f"    ({100*w_cov['fraction_retrofitted_by_cost']:.0f}% of value; "
        f"MC {mc_cov['n_retrofitted']}/{mc_cov['n_buildings']}).\n"
        "    Thesis retrofitted the whole RC-frame stock,\n"
        "    so our FATALITY cut is smaller by coverage.\n\n"
        "(2) NON-STRUCTURAL equipment upgrade (Table 6-3)\n"
        "    brace ceilings, safety-wire fixtures, reinforce\n"
        "    CHB, remove electronics -> INJURY reduction.\n"
        f"    Portfolio-wide ({w_cov['n_nonstructural_upgraded']}/"
        f"{w_cov['n_buildings']} bldgs) — NOT coverage-limited.\n\n"
        f"Injury reduction: Makati −{mc_inj_red:.0f}%, whole −{whole_inj_red:.0f}%.\n"
        "Magnitude bounded by the base model's collapse-\n"
        "injury exposure (NC/collapse split); not tuned."
    )
    axT.text(0.0, 1.0, txt, transform=axT.transAxes, fontsize=8.7, va="top",
             family="DejaVu Sans",
             bbox=dict(boxstyle="round,pad=0.5", fc="#ECFDF5", ec=C_MIT, alpha=0.9))

    fig.suptitle(
        "WVF Mw 7.3 — Base vs Mitigated (structural FRP + non-structural upgrade)  ·  N=1000",
        fontsize=14, fontweight="bold", y=0.98)
    fig.savefig(OUT, bbox_inches="tight", facecolor="white")
    print(f"wrote {OUT.relative_to(REPO)}  ({OUT.stat().st_size//1024} KB)")


if __name__ == "__main__":
    main()
