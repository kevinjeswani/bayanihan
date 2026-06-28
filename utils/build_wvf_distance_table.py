"""Extract per-building rupture distances from the thesis portfolio workbooks.

The thesis portfolio-analysis workbooks (``sandbox/portfolio-analysis/*.xlsx``, dated
2020-08-31) carry, per building, the rupture-distance metrics that were fed to each
GMPE — computed from each scenario's rupture plane.  Using these as-is is in HARD
SCOPE ("the author's own saved analytical outputs used as-is"); it avoids re-deriving
the fault geometry and exactly reproduces the thesis hazard inputs.

This builds a per-building distance parquet for EVERY thesis scenario in
``bayanihan/data/scenarios.json``:

  WVF_6.5, WVF_7.3, EVF_6.6, GNW_7.2   — shallow crustal (CY08 block layout)
  MnlTrench_8.15                       — subduction interface (Zhao SInter layout)

The output schema is IDENTICAL across all scenarios so ``hazard.scenario_sa_field``
/ ``hazard._evaluate_branch_lnsa`` consume them unchanged:

  building_id, period_s, rrup_km, rjb_km, ztor_km, dip_deg, rake_deg, rx_km,
  z1pt0_km, vs30

Two workbook layouts are handled (verified 2026-06-27):

* **Crustal** (WVF/EVF/GNW): the Chiou & Youngs 2008 block (cols 14-25) carries
  Rrup, Rjb, Ztor, dip (delta), rake (lambda), Rx, Z1.0 (Z10), Vs30.  The other three
  crustal blocks (BA08, BSSA14, Zhao06) carry identical Rrup/Rjb (verified per
  scenario), confirming a single shared rupture geometry.  Geometry differs per
  scenario (e.g. WVF dip 75 rake -120; EVF dip 65 rake -90; GNW dip 65 rake -120).

* **Subduction interface** (Manila Trench): the Zhao 2006 interface block (cols 14-18)
  carries T, Mw, Rrup, hypocentral depth (h/Zhyp), Vs30.  The interface GSIMs
  (Youngs 1997, Atkinson & Boore 2003, Zhao 2006 SInter, BC Hydro 2015) require ONLY
  ``rrup``, ``hypo_depth``, ``mag`` and ``vs30`` (confirmed via each GSIM's
  ``REQUIRES_*`` sets) — they do NOT use Rjb/Rx/Ztor/dip/rake.  All four interface
  blocks carry the SAME Rrup (verified), confirming a single shared rupture geometry.
  We populate the unused columns with thesis-faithful placeholders (Rjb=Rrup, Rx=0,
  Ztor=0, dip=20° typical interface, rake=90° pure thrust, Z1.0=0 → GSIM regression
  default) so the schema matches; the interface GSIMs ignore them.

Privacy: each output parquet is keyed ONLY by ``building_id`` and carries no
coordinates, costs, populations, or names — committable (derived from the author's
own outputs + open tooling).  The source .xlsx files stay gitignored in sandbox/.
(The parquets are gitignored by the ``*.parquet`` rule like the WVF-7.3 one — fine.)

Run:
    .venv/bin/python utils/build_wvf_distance_table.py            # all scenarios
    .venv/bin/python utils/build_wvf_distance_table.py WVF_7.3    # one scenario

Output:
    bayanihan/data/hazard/{scenario_id_with_underscores}_distances.parquet

Refs: Jeswani et al. 2022 (EQ Spectra, 38(3), 1946-1971); Jeswani 2021 (MASc thesis, U of T).
"""

from __future__ import annotations

import json
import pathlib
import sys

import numpy as np
import openpyxl
import pandas as pd

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
SOURCE_DIR = REPO_ROOT / "sandbox" / "portfolio-analysis"
_HAZARD_DIR = REPO_ROOT / "bayanihan" / "data" / "hazard"
_SCENARIOS_JSON = REPO_ROOT / "bayanihan" / "data" / "scenarios.json"

# Back-compat: the original WVF-7.3 output path other modules referenced.
OUTPUT_PARQUET = _HAZARD_DIR / "WVF_7_3_distances.parquet"

# --- Crustal layout: Chiou & Youngs 2008 block column indices (0-based) -----------
COL_BUILDING_ID = 2
_CRUSTAL = {
    "period_s": 15,  # 'T' — period used for the GMPE call (= building Tavg / T1)
    "rrup_km": 16,
    "rjb_km": 17,
    "ztor_km": 18,
    "dip_deg": 19,  # 'delta'
    "rake_deg": 20,  # 'lambda'
    "rx_km": 22,
    "z1pt0_km": 23,  # Z1.0 in km
    "vs30": 24,
}
# Cross-check columns in the other crustal blocks (must match CY08 distances).
_CRUSTAL_XCHECK = {
    "ba08_rjb": 29,
    "zhao_rrup": 35,
    "bssa_rjb": 45,
}

# --- Subduction-interface layout: Zhao 2006 interface block (0-based) --------------
# Manila Trench workbook columns: T=14, Mw=15, Rrup=16, h(Zhyp)=17, Vs30=18.
# All four interface blocks carry the SAME Rrup (cross-checked below).
_SUBDUCTION = {
    "period_s": 14,  # 'T'
    "rrup_km": 16,
    "ztor_km": 17,  # hypocentral depth h (Zhyp) — interface GSIMs read this as hypo_depth
    "vs30": 18,
}
# Cross-check Rrup across the other three interface blocks.
_SUBDUCTION_XCHECK = {
    "abrahamson_rrup": 26,
    "youngs_rrup": 33,
    "ab03_rrup": 41,
}
# Thesis-faithful placeholders for the columns the interface GSIMs ignore (so the
# parquet schema matches the crustal one). dip 20° / rake 90° = typical thrust
# interface; Ztor handled separately (= hypo depth column is the rupture-param the
# GSIMs actually use via scenarios.json hypocenter.depth_km).
_INTERFACE_DIP_DEG = 20.0
_INTERFACE_RAKE_DEG = 90.0


def _load_scenarios() -> dict:
    with open(_SCENARIOS_JSON, encoding="utf-8") as fh:
        raw = json.load(fh)
    return {s["id"]: s for s in raw["scenarios"]}


def _data_rows(ws) -> list:
    """Building rows (row 4+ with a non-empty Building ID)."""
    return [
        r
        for r in ws.iter_rows(min_row=4, values_only=True)
        if r[COL_BUILDING_ID] is not None
    ]


def _build_crustal(ws) -> pd.DataFrame:
    """Extract the crustal CY08 distance block + cross-check the three other blocks."""
    rows = _data_rows(ws)
    records = []
    ba_rjb, zhao_rrup, bssa_rjb = [], [], []
    for r in rows:
        records.append(
            {
                # Strip stray whitespace/newlines from the workbook cell (one id,
                # 'MDO-1\n', carries a trailing newline in the source xlsx).
                "building_id": str(r[COL_BUILDING_ID]).strip(),
                "period_s": float(r[_CRUSTAL["period_s"]]),
                "rrup_km": float(r[_CRUSTAL["rrup_km"]]),
                "rjb_km": float(r[_CRUSTAL["rjb_km"]]),
                "ztor_km": float(r[_CRUSTAL["ztor_km"]]),
                "dip_deg": float(r[_CRUSTAL["dip_deg"]]),
                "rake_deg": float(r[_CRUSTAL["rake_deg"]]),
                "rx_km": float(r[_CRUSTAL["rx_km"]]),
                "z1pt0_km": float(r[_CRUSTAL["z1pt0_km"]]),
                "vs30": float(r[_CRUSTAL["vs30"]]),
            }
        )
        ba_rjb.append(float(r[_CRUSTAL_XCHECK["ba08_rjb"]]))
        zhao_rrup.append(float(r[_CRUSTAL_XCHECK["zhao_rrup"]]))
        bssa_rjb.append(float(r[_CRUSTAL_XCHECK["bssa_rjb"]]))

    df = pd.DataFrame.from_records(records)
    # Integrity: the four crustal blocks must share the rupture geometry.
    assert np.allclose(df["rjb_km"].values, ba_rjb), "BA08 Rjb differs from CY08 Rjb"
    assert np.allclose(df["rrup_km"].values, zhao_rrup), "Zhao Rrup differs from CY08 Rrup"
    assert np.allclose(df["rjb_km"].values, bssa_rjb), "BSSA Rjb differs from CY08 Rjb"
    return df


def _build_subduction(ws) -> pd.DataFrame:
    """Extract the subduction Zhao-SInter block; cross-check Rrup across all 4 blocks.

    Populates the columns the interface GSIMs ignore (Rjb, Rx, dip, rake, Z1.0) with
    thesis-faithful placeholders so the output schema matches the crustal one.  The
    hypocentral depth column (workbook col 17) is written to ``ztor_km`` so the schema
    has a slot for it; the interface GSIMs actually read hypo_depth from the scenario
    record (scenarios.json hypocenter.depth_km), which equals this column (verified).
    """
    rows = _data_rows(ws)
    records = []
    abr_rrup, you_rrup, ab_rrup = [], [], []
    for r in rows:
        rrup = float(r[_SUBDUCTION["rrup_km"]])
        records.append(
            {
                "building_id": str(r[COL_BUILDING_ID]).strip(),
                "period_s": float(r[_SUBDUCTION["period_s"]]),
                "rrup_km": rrup,
                "rjb_km": rrup,  # interface GSIMs ignore Rjb; set = Rrup for schema parity
                "ztor_km": float(r[_SUBDUCTION["ztor_km"]]),  # hypocentral depth (h/Zhyp)
                "dip_deg": _INTERFACE_DIP_DEG,  # ignored by interface GSIMs
                "rake_deg": _INTERFACE_RAKE_DEG,  # ignored by interface GSIMs
                "rx_km": 0.0,  # ignored by interface GSIMs
                "z1pt0_km": 0.0,  # 0 -> GSIM uses its Vs30 regression default
                "vs30": float(r[_SUBDUCTION["vs30"]]),
            }
        )
        abr_rrup.append(float(r[_SUBDUCTION_XCHECK["abrahamson_rrup"]]))
        you_rrup.append(float(r[_SUBDUCTION_XCHECK["youngs_rrup"]]))
        ab_rrup.append(float(r[_SUBDUCTION_XCHECK["ab03_rrup"]]))

    df = pd.DataFrame.from_records(records)
    # Integrity: all four interface blocks must share Rrup (single rupture geometry).
    assert np.allclose(df["rrup_km"].values, abr_rrup), "Abrahamson Rrup differs from Zhao Rrup"
    assert np.allclose(df["rrup_km"].values, you_rrup), "Youngs Rrup differs from Zhao Rrup"
    assert np.allclose(df["rrup_km"].values, ab_rrup), "AB03 Rrup differs from Zhao Rrup"
    return df


def build_scenario(scenario_id: str, scen: dict) -> pathlib.Path:
    """Build and write the per-building distance parquet for one scenario."""
    source_file = scen.get("source_file")
    src = SOURCE_DIR / source_file
    if not src.exists():
        raise FileNotFoundError(
            f"Thesis workbook not found: {src}\n"
            "This build step requires the gitignored sandbox/portfolio-analysis/ workbooks."
        )

    wb = openpyxl.load_workbook(src, read_only=True, data_only=True)
    ws = wb["Sheet1"]

    mechanism = str(scen.get("mechanism", "crustal")).lower()
    if mechanism in ("interface", "subduction_interface", "subduction"):
        df = _build_subduction(ws)
    else:
        df = _build_crustal(ws)
    wb.close()

    assert df["building_id"].is_unique, f"{scenario_id}: duplicate building_id in workbook"
    assert len(df) == 1021, f"{scenario_id}: expected 1021 buildings, got {len(df)}"

    out_name = scenario_id.replace(".", "_") + "_distances.parquet"
    out_path = _HAZARD_DIR / out_name
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out_path, index=False)

    rr, rj = df["rrup_km"], df["rjb_km"]
    n_fw = int((df["rx_km"] < 0).sum())
    n_hw = int((df["rx_km"] > 0).sum())
    print(f"[{scenario_id}] ({mechanism}) wrote {len(df)} records -> {out_path.name}")
    print(f"    Rrup (km): min={rr.min():.3f} med={rr.median():.3f} max={rr.max():.3f}")
    print(f"    Rjb  (km): min={rj.min():.3f} med={rj.median():.3f} max={rj.max():.3f}")
    if mechanism in ("interface", "subduction_interface", "subduction"):
        print(
            f"    hypo_depth (km, =ztor col): {df['ztor_km'].iloc[0]:.2f}   "
            f"Vs30: min={df['vs30'].min():.0f} med={df['vs30'].median():.0f} "
            f"max={df['vs30'].max():.0f}"
        )
    else:
        print(f"    Rx signed : footwall(neg)={n_fw} hangingwall(pos)={n_hw}")
        print(
            f"    dip/rake/Ztor: {df['dip_deg'].iloc[0]:.0f} / "
            f"{df['rake_deg'].iloc[0]:.0f} / {df['ztor_km'].iloc[0]:.0f}"
        )
    print(f"    periods (s): {sorted(df['period_s'].round(5).unique())}")
    return out_path


def main(scenario_ids: list[str] | None = None) -> None:
    scenarios = _load_scenarios()
    if scenario_ids:
        unknown = [s for s in scenario_ids if s not in scenarios]
        if unknown:
            raise KeyError(f"Unknown scenario id(s): {unknown}. Known: {sorted(scenarios)}")
        ids = scenario_ids
    else:
        ids = list(scenarios.keys())
    for sid in ids:
        build_scenario(sid, scenarios[sid])


def build_sa_field_cache(
    n_realizations: int = 1000, seed: int = 2021, scenario_id: str = "WVF_7.3"
) -> None:
    """Generate and cache a scenario Monte-Carlo Sa(T1) field to parquet.

    Imported here (not at module top) so the distance-table build above has no
    dependency on the hazard module.  The cached field is keyed ONLY by
    building_id (no coordinates/costs) and is committable.
    """
    from bayanihan.hazard import scenario_sa_field

    out = _HAZARD_DIR / (scenario_id.replace(".", "_") + "_sa_field.parquet")
    df = scenario_sa_field(scenario_id, n_realizations=n_realizations, seed=seed)
    df.to_parquet(out)
    flat = df.to_numpy().ravel()
    print(
        f"Wrote Sa(T1) field {df.shape} -> {out.name}\n"
        f"  realized: p5={pd.Series(flat).quantile(0.05):.4f} "
        f"median={pd.Series(flat).median():.4f} "
        f"p95={pd.Series(flat).quantile(0.95):.4f} g"
    )


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    main(args if args else None)
    # Cache the WVF-7.3 Sa field by default (back-compat with the original script).
    if not args or "WVF_7.3" in args:
        build_sa_field_cache(n_realizations=1000, seed=2021, scenario_id="WVF_7.3")
