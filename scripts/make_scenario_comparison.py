"""Compare all 5 thesis scenarios (ours vs 2021 Thesis) + multi-scenario loss figure.

Reads the committable per-scenario portfolio summaries:
    bayanihan/data/results/{wvf65,wvf73,evf66,gnw72,mnlt815}_portfolio_summary.json
and the 2021-thesis validation targets (docs/thesis/data/portfolio_validation.yaml,
mirrored here as TARGETS), then:

  1. Prints a 5-scenario comparison table (Makati / QC / whole loss; injuries; recovery)
     with like-for-like deltas (median<->median, p90<->p90).
  2. Confirms WVF-7.3 governs (highest whole-portfolio loss).
  3. Writes a machine-readable comparison to
     bayanihan/data/results/all_scenarios_comparison.json.
  4. Renders images/all_scenarios_loss.png — a clean multi-scenario loss comparison
     (ours median+p90 vs 2021-Thesis median, ordered by severity), "2021 Thesis" labels.

The 2021-thesis loss targets: WVF-7.3 is high-confidence text (Ch.7); the other four are
medium/low-confidence CDF reads from Appendix E (figure values; the thesis used Mw labels
6.5 / 6.6 / 7.2 / 8.15 which differ from the Table 7-1 simulation Mw — see the yaml). We
compare against the LABELLED scenarios, which is what scenarios.json uses.

NOT tuned. HARD SCOPE compliant.

Run (after the portfolio runs):
    .venv/bin/python prototypes/2026-06-27_scenario_comparison.py

Refs: Jeswani et al. 2022 (EQ Spectra, 38(3), 1946-1971); Jeswani 2021 (MASc thesis, U of T).
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np

REPO = Path(__file__).resolve().parent.parent
RESULTS = REPO / "bayanihan" / "data" / "results"
OUT_JSON = RESULTS / "all_scenarios_comparison.json"
OUT_FIG = REPO / "images" / "all_scenarios_loss.png"

# Scenario id -> (results filename tag, display label).  Ordered by expected severity
# is handled later; this is just the registry.
SCENARIOS = [
    ("WVF_6.5", "wvf65", "WVF\nMw 6.5"),
    ("WVF_7.3", "wvf73", "WVF\nMw 7.3"),
    ("EVF_6.6", "evf66", "EVF\nMw 6.6"),
    ("GNW_7.2", "gnw72", "GNW\nMw 7.2"),
    ("MnlTrench_8.15", "mnlt815", "Manila Tr.\nMw 8.15"),
]

# 2021-Thesis loss-ratio targets (median, p90).  WVF-7.3 from Ch.7 text (high conf);
# others from Appendix E CDF reads (medium/low) — p90 only where the thesis text gives
# it (WVF-7.3). Mirrors docs/thesis/data/portfolio_validation.yaml.
TARGETS = {
    "WVF_6.5": {
        "MK": {"loss_median": 0.14, "loss_p90": None},
        "QC": {"loss_median": 0.09, "loss_p90": None},
        "MK_inj_ratio": 0.04, "QC_inj_ratio": 0.04,
        "MK_recov90": 450, "QC_recov90": 175,
        "confidence": "medium (Appendix E CDF read)",
    },
    "WVF_7.3": {
        "MK": {"loss_median": 0.26, "loss_p90": 0.42},
        "QC": {"loss_median": 0.31, "loss_p90": 0.47},
        "WHOLE": {"loss_median": 0.256, "loss_p90": 0.351},  # .mat PA_Loss anchor
        "MK_inj_ratio": 0.145, "QC_inj_ratio": 0.091,
        "MK_recov90": 970, "QC_recov90": 640,
        "confidence": "high (Ch.7 text; whole = .mat PA_Loss)",
    },
    "EVF_6.6": {
        "MK": {"loss_median": 0.07, "loss_p90": None},
        "QC": {"loss_median": 0.09, "loss_p90": None},
        "MK_inj_ratio": 0.06, "QC_inj_ratio": 0.03,
        "MK_recov90": 550, "QC_recov90": 150,
        "confidence": "medium (Appendix E CDF read; label Mw 6.6 / sim 6.9)",
    },
    "GNW_7.2": {
        "MK": {"loss_median": 0.045, "loss_p90": None},
        "QC": {"loss_median": 0.04, "loss_p90": None},
        "MK_inj_ratio": 0.06, "QC_inj_ratio": 0.025,
        "MK_recov90": 500, "QC_recov90": 200,
        "confidence": "medium (Appendix E CDF read; label Mw 7.2 / sim 7.6)",
    },
    "MnlTrench_8.15": {
        "MK": {"loss_median": 0.15, "loss_p90": None},
        "QC": {"loss_median": 0.065, "loss_p90": None},
        "MK_inj_ratio": 0.07, "QC_inj_ratio": 0.025,
        "MK_recov90": 400, "QC_recov90": 200,
        "confidence": "low (Appendix E CDF read; subduction; label 8.15 / sim 7.9)",
    },
}

C_OURS = "#DC2626"     # red = ours (median)
C_OURS_P90 = "#F59E0B"  # amber = ours p90 cap
C_THESIS = "#1D4ED8"   # blue = 2021 Thesis
C_GRAY = "#6B7280"

mpl.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 10,
    "axes.titlesize": 12,
    "axes.titleweight": "bold",
    "axes.labelsize": 10.5,
    "axes.grid": True,
    "grid.alpha": 0.25,
    "figure.dpi": 130,
})


def _load(tag: str) -> dict | None:
    p = RESULTS / f"{tag}_portfolio_summary.json"
    if not p.is_file():
        return None
    return json.loads(p.read_text())


def _delta_pct(ours: float, thesis: float | None) -> str:
    if thesis is None or thesis == 0:
        return "  —  "
    return f"{(ours - thesis) / thesis * 100:+.0f}%"


def build_comparison() -> dict:
    rows = {}
    for sid, tag, _label in SCENARIOS:
        s = _load(tag)
        if s is None:
            rows[sid] = {"present": False}
            continue
        tgt = TARGETS[sid]
        mk = s["makati_MC"]["loss_ratio"]
        qc = s["quezon_QC"]["loss_ratio"]
        wh = s["whole_portfolio"]["loss_ratio"]
        mkc = s["makati_MC"]["casualties"]
        qcc = s["quezon_QC"]["casualties"]
        r90 = s["recovery_90pct_functional_days"]
        rows[sid] = {
            "present": True,
            "label": sid,
            "ours": {
                "makati_loss_median": mk["median"], "makati_loss_mean": mk["mean"],
                "makati_loss_p90": mk["p90"],
                "qc_loss_median": qc["median"], "qc_loss_mean": qc["mean"],
                "qc_loss_p90": qc["p90"],
                "whole_loss_median": wh["median"], "whole_loss_mean": wh["mean"],
                "whole_loss_p90": wh["p90"],
                "makati_inj_ratio_median": mkc["injuries"]["ratio"]["median"],
                "qc_inj_ratio_median": qcc["injuries"]["ratio"]["median"],
                "makati_fat_ratio_median": mkc["fatalities"]["ratio"]["median"],
                "qc_fat_ratio_median": qcc["fatalities"]["ratio"]["median"],
                "makati_recov90_median": r90["makati_MC"]["functional_recovery"]["median"],
                "qc_recov90_median": r90["quezon_QC"]["functional_recovery"]["median"],
                "collapse_rate": s["collapse_rate_building_realizations"],
                "demolition_rate": s["demolition_rate_building_realizations"],
                "loss_source": s["loss_source_decomposition"],
                "extrapolated_above_stripe": s["extrapolated_fraction_above_edp_stripe"],
            },
            "thesis_2021": tgt,
        }
    return rows


def print_table(rows: dict) -> None:
    print("\n" + "=" * 104)
    print("FIVE-SCENARIO COMPARISON — ours vs 2021 Thesis  (loss ratio: median, p90)")
    print("=" * 104)
    hdr = (f"{'scenario':16s} | {'Makati med':>11s} {'(thesis)':>9s} {'Δ':>6s} | "
           f"{'whole med':>10s} {'(thesis)':>9s} {'Δ':>6s} | {'QC med':>8s} {'(th)':>6s}")
    print(hdr)
    print("-" * 104)
    for sid, _tag, _label in SCENARIOS:
        r = rows[sid]
        if not r.get("present"):
            print(f"{sid:16s} |   (not yet computed)")
            continue
        o = r["ours"]
        t = r["thesis_2021"]
        mk_t = t["MK"]["loss_median"]
        qc_t = t["QC"]["loss_median"]
        wh_t = t.get("WHOLE", {}).get("loss_median")
        mk_delta = _delta_pct(o["makati_loss_median"], mk_t)
        print(
            f"{sid:16s} | "
            f"{o['makati_loss_median']:>11.3f} {mk_t:>9.3f} {mk_delta:>6s} | "
            f"{o['whole_loss_median']:>10.3f} "
            f"{(f'{wh_t:.3f}' if wh_t is not None else '—'):>9s} "
            f"{_delta_pct(o['whole_loss_median'], wh_t):>6s} | "
            f"{o['qc_loss_median']:>8.3f} {qc_t:>6.3f}"
        )
    print("-" * 104)
    # Governance check
    present = {sid: rows[sid]["ours"]["whole_loss_median"]
               for sid, _t, _l in SCENARIOS if rows[sid].get("present")}
    if present:
        gov = max(present, key=present.get)
        print(f"Highest whole-portfolio median loss: {gov}  "
              f"({present[gov]:.3f})  -> WVF-7.3 governs: {gov == 'WVF_7.3'}")
        ordering = sorted(present.items(), key=lambda kv: -kv[1])
        print("Severity order (whole median loss): "
              + " > ".join(f"{k}={v:.3f}" for k, v in ordering))
    print("=" * 104)


def make_figure(rows: dict) -> None:
    present = [(sid, lbl) for sid, _tag, lbl in SCENARIOS if rows[sid].get("present")]
    if not present:
        print("No scenarios present — skipping figure.")
        return
    # Order by ours whole-portfolio median loss (descending severity).
    present.sort(key=lambda sl: -rows[sl[0]]["ours"]["whole_loss_median"])

    labels = [lbl for _sid, lbl in present]
    x = np.arange(len(present))

    fig, axes = plt.subplots(1, 2, figsize=(13.5, 5.6))

    # --- Panel 1: Makati + QC loss (ours median + p90 cap vs 2021 Thesis median) ---
    ax = axes[0]
    w = 0.38
    mk_med = [rows[s]["ours"]["makati_loss_median"] for s, _l in present]
    mk_p90 = [rows[s]["ours"]["makati_loss_p90"] for s, _l in present]
    mk_th = [rows[s]["thesis_2021"]["MK"]["loss_median"] for s, _l in present]
    qc_med = [rows[s]["ours"]["qc_loss_median"] for s, _l in present]
    qc_th = [rows[s]["thesis_2021"]["QC"]["loss_median"] for s, _l in present]

    # Makati bars (ours) with p90 whisker; thesis as blue marker
    ax.bar(x - w / 2, mk_med, w, color=C_OURS, alpha=0.85, label="Makati — ours (median)")
    ax.vlines(x - w / 2, mk_med, mk_p90, color=C_OURS_P90, lw=2.5, zorder=5)
    ax.scatter(x - w / 2, mk_p90, marker="_", s=240, color=C_OURS_P90, zorder=6,
               label="Makati — ours (p90)")
    ax.scatter(x - w / 2, mk_th, marker="D", s=70, color=C_THESIS, zorder=7,
               edgecolor="white", linewidth=0.7, label="Makati — 2021 Thesis (median)")
    # QC bars (ours) + thesis marker
    ax.bar(x + w / 2, qc_med, w, color="#9333EA", alpha=0.70, label="QC — ours (median)")
    ax.scatter(x + w / 2, qc_th, marker="D", s=70, color=C_THESIS, zorder=7,
               edgecolor="white", linewidth=0.7, label="QC — 2021 Thesis (median)")

    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=9)
    ax.set_ylabel("Portfolio loss ratio")
    ax.set_title("Per-region loss ratio by scenario\n(bars = ours median; ◆ = 2021 Thesis median)")
    ax.legend(fontsize=7.5, loc="upper right", framealpha=0.9, ncol=1)
    ax.set_ylim(0, max(max(mk_p90), max(qc_med), max(mk_th), max(qc_th)) * 1.18)

    # --- Panel 2: whole-portfolio median loss, ours vs thesis where available ---
    ax = axes[1]
    wh_med = [rows[s]["ours"]["whole_loss_median"] for s, _l in present]
    wh_p90 = [rows[s]["ours"]["whole_loss_p90"] for s, _l in present]
    ax.bar(x, wh_med, 0.55, color=C_OURS, alpha=0.85, label="ours (median)")
    ax.vlines(x, wh_med, wh_p90, color=C_OURS_P90, lw=2.5, zorder=5)
    ax.scatter(x, wh_p90, marker="_", s=300, color=C_OURS_P90, zorder=6, label="ours (p90)")
    # Thesis whole anchor only exists for WVF-7.3 (.mat); mark it.
    for i, (s, _l) in enumerate(present):
        wh_t = rows[s]["thesis_2021"].get("WHOLE", {}).get("loss_median")
        if wh_t is not None:
            ax.scatter([i], [wh_t], marker="D", s=85, color=C_THESIS, zorder=7,
                       edgecolor="white", linewidth=0.8,
                       label="2021 Thesis (.mat, WVF-7.3)")
    # de-dup legend
    h, lbl = ax.get_legend_handles_labels()
    seen = dict(zip(lbl, h))
    ax.legend(seen.values(), seen.keys(), fontsize=8, loc="upper right", framealpha=0.9)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=9)
    ax.set_ylabel("Whole-portfolio loss ratio")
    ax.set_title("Whole-portfolio loss ratio by scenario\n(ordered by severity — WVF-7.3 governs)")
    ax.set_ylim(0, max(wh_p90) * 1.15)

    fig.suptitle(
        "bayanihan — multi-scenario portfolio loss (1,021 Metro Manila school buildings, N=1000)",
        fontsize=12.5, fontweight="bold", y=1.0,
    )
    fig.text(0.5, -0.02,
             "GMPEs via openquake.hazardlib (crustal 4-branch; Manila Trench = "
             "subduction-interface 4-branch). "
             "Thesis targets: WVF-7.3 high-confidence text; others Appendix-E CDF reads.",
             ha="center", fontsize=7.5, color=C_GRAY)
    fig.tight_layout(rect=(0, 0, 1, 0.99))
    OUT_FIG.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT_FIG, bbox_inches="tight", facecolor="white")
    print(f"figure -> {OUT_FIG.relative_to(REPO)}")


def main() -> None:
    rows = build_comparison()
    print_table(rows)
    OUT_JSON.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    print(f"comparison JSON -> {OUT_JSON.relative_to(REPO)}")
    make_figure(rows)


if __name__ == "__main__":
    main()
